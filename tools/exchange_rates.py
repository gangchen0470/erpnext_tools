import json
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import frappe
from frappe import _
from frappe.utils import now_datetime, today

SETTINGS_DOCTYPE = "Exchange Rate Settings"
RECORD_DOCTYPE = "Exchange Rate Record"
ALLOWED_ROLES = {"System Manager", "Tools Manager", "Accounts Manager"}


def _require_manager():
    if frappe.session.user == "Guest" or not ALLOWED_ROLES.intersection(frappe.get_roles()):
        frappe.throw(_("Not permitted"), frappe.PermissionError)


def _secret(doc, fieldname):
    try:
        return doc.get_password(fieldname)
    except Exception:
        return None


def _parse_pairs(text):
    pairs = []
    for raw in (text or "").splitlines():
        raw = raw.strip().upper().replace(" ", "")
        if not raw:
            continue
        parts = raw.split("/")
        if len(parts) != 2 or any(len(part) != 3 or not part.isalpha() for part in parts):
            frappe.throw(_("Invalid currency pair '{0}'. Use format USD/CNY, one pair per line.").format(raw))
        if parts[0] == parts[1]:
            frappe.throw(_("Source and target currencies cannot be the same: {0}").format(raw))
        pair = (parts[0], parts[1])
        if pair not in pairs:
            pairs.append(pair)
    return pairs


def _fetch_rate(settings, source, target):
    appkey = _secret(settings, "appkey")
    sign = _secret(settings, "sign")
    if not appkey or not sign:
        raise ValueError("NowAPI AppKey and Sign must be configured in Exchange Rate Settings")

    params = {
        "app": "finance.rate",
        "scur": source,
        "tcur": target,
        "appkey": appkey,
        "sign": sign,
        "format": "json",
    }
    base_url = (settings.api_url or "https://sapi.k780.com/").strip()
    if not base_url.startswith("https://"):
        raise ValueError("API URL must use HTTPS")
    url = base_url + ("&" if "?" in base_url else "?") + urlencode(params)
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "ERPNext-Tools-ExchangeRates/1.0"})

    try:
        with urlopen(request, timeout=max(3, min(int(settings.timeout or 10), 30))) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        # Avoid storing exception text that can contain a URL with credentials.
        raise ValueError("Could not connect to NowAPI or parse its JSON response")

    if str(payload.get("success")) != "1":
        raise ValueError("NowAPI rejected the request: {0} {1}".format(
            str(payload.get("msgid", ""))[:100], str(payload.get("msg", ""))[:300]
        ))

    result = payload.get("result")
    if isinstance(result, list):
        result = next((row for row in result if row.get("scur") == source and row.get("tcur") == target), None)
    if not isinstance(result, dict):
        raise ValueError("NowAPI response did not contain a matching result object")
    if result.get("scur") and result.get("scur") != source:
        raise ValueError("NowAPI returned a different source currency")
    if result.get("tcur") and result.get("tcur") != target:
        raise ValueError("NowAPI returned a different target currency")

    try:
        rate = Decimal(str(result.get("rate", "")))
    except (InvalidOperation, TypeError):
        raise ValueError("NowAPI returned an invalid exchange rate")
    if not rate.is_finite() or rate <= 0:
        raise ValueError("NowAPI returned a non-positive exchange rate")
    return float(rate)


def _upsert_record(rate_date, source, target, rate=None, status="Success", error=None, currency_exchange=None):
    name = frappe.db.get_value(
        RECORD_DOCTYPE,
        {"date": rate_date, "from_currency": source, "to_currency": target},
        "name",
    )
    values = {
        "date": rate_date,
        "from_currency": source,
        "to_currency": target,
        "exchange_rate": float(rate or 0),
        "source": "NowAPI finance.rate",
        "status": status,
        "fetched_at": now_datetime(),
        "error_message": (error or "")[:1000],
        "currency_exchange": currency_exchange,
    }
    if name:
        doc = frappe.get_doc(RECORD_DOCTYPE, name)
        doc.update(values)
        doc.save(ignore_permissions=True)
    else:
        doc = frappe.get_doc({"doctype": RECORD_DOCTYPE, **values})
        doc.insert(ignore_permissions=True)
    return doc


def _sync_standard_currency_exchange(rate_date, source, target, rate):
    name = frappe.db.get_value(
        "Currency Exchange",
        {"date": rate_date, "from_currency": source, "to_currency": target},
        "name",
    )
    values = {
        "date": rate_date,
        "from_currency": source,
        "to_currency": target,
        "exchange_rate": rate,
        "for_buying": 1,
        "for_selling": 1,
    }
    if name:
        doc = frappe.get_doc("Currency Exchange", name)
        doc.update(values)
        doc.save(ignore_permissions=True)
    else:
        doc = frappe.get_doc({"doctype": "Currency Exchange", **values})
        doc.insert(ignore_permissions=True)
    return doc.name


@frappe.whitelist()
def sync_rates():
    _require_manager()
    settings = frappe.get_single(SETTINGS_DOCTYPE)
    if not settings.enabled:
        frappe.throw(_("Enable API Sync in Exchange Rate Settings first"))

    pairs = _parse_pairs(settings.currency_pairs)
    if not pairs:
        frappe.throw(_("Configure at least one currency pair"))

    rate_date = today()
    successes, failures = [], []
    for source, target in pairs:
        try:
            rate = _fetch_rate(settings, source, target)
            exchange_name = None
            if settings.sync_to_erpnext:
                exchange_name = _sync_standard_currency_exchange(rate_date, source, target, rate)
            record = _upsert_record(
                rate_date, source, target, rate=rate, status="Success",
                currency_exchange=exchange_name,
            )
            successes.append({"pair": f"{source}/{target}", "rate": rate, "record": record.name})
        except Exception as exc:
            error = str(exc)[:500]
            _upsert_record(rate_date, source, target, status="Failed", error=error)
            failures.append({"pair": f"{source}/{target}", "error": error})

    settings.last_sync_at = now_datetime()
    settings.last_sync_status = _("Success: {0}; Failed: {1}").format(len(successes), len(failures))
    settings.save(ignore_permissions=True)
    frappe.db.commit()
    return {"success": successes, "failed": failures}


def scheduled_sync_rates():
    settings = frappe.get_single(SETTINGS_DOCTYPE)
    if not settings.enabled or not settings.scheduler_enabled:
        return
    original_user = frappe.session.user
    try:
        frappe.set_user("Administrator")
        sync_rates()
    finally:
        frappe.set_user(original_user)


@frappe.whitelist()
def get_latest_rates():
    _require_manager()
    return frappe.get_all(
        RECORD_DOCTYPE,
        fields=[
            "date", "from_currency", "to_currency", "exchange_rate", "source",
            "status", "fetched_at", "error_message", "currency_exchange",
        ],
        order_by="date desc, modified desc",
        limit_page_length=200,
    )
