import base64
import json
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

import frappe
from frappe import _
from frappe.utils import now_datetime, today

SETTINGS_DOCTYPE = "Exchange Rate Settings"
RECORD_DOCTYPE = "Exchange Rate Record"
ALLOWED_ROLES = {"System Manager", "Tools Manager", "Accounts Manager"}
SENSITIVE_KEYS = {"authorization", "appkey", "apikey", "api_key", "token", "secret", "sign", "password"}


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


def _json_object(raw, label):
    try:
        value = json.loads(raw or "{}")
    except (ValueError, TypeError):
        raise ValueError("{0} must be valid JSON".format(label))
    if not isinstance(value, dict):
        raise ValueError("{0} must be a JSON object".format(label))
    return value


def _render_value(value, source, target, rate_date):
    if isinstance(value, str):
        return value.format(from_currency=source, to_currency=target, date=rate_date)
    return value


def _json_path(payload, path):
    if not path:
        return None
    current = payload
    for part in path.split("."):
        if isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return None
        elif isinstance(current, dict):
            if part not in current:
                return None
            current = current[part]
        else:
            return None
    return current


def _redact_message(value, settings=None):
    # Provider errors may echo credential values; redact known secrets before storing/displaying.
    text = str(value or "")[:500]
    if settings:
        for fieldname in ("api_key", "api_secret", "basic_password"):
            secret = _secret(settings, fieldname)
            if secret:
                text = text.replace(secret, "[REDACTED]")
        if settings.basic_username:
            text = text.replace(str(settings.basic_username), "[REDACTED]")
    for marker in ("appkey", "api_key", "apikey", "token", "secret", "sign", "password", "authorization"):
        if marker in text.lower():
            return "Provider returned an error; inspect API configuration and provider response mapping."
    return text[:300]


def _fetch_rate(settings, source, target):
    endpoint = (settings.api_url or "").strip()
    if not endpoint.startswith("https://"):
        raise ValueError("API endpoint must use HTTPS")
    if urlsplit(endpoint).username or urlsplit(endpoint).password:
        raise ValueError("Credentials must not be embedded in the API endpoint URL")

    method = (settings.http_method or "GET").upper()
    if method not in {"GET", "POST"}:
        raise ValueError("HTTP method must be GET or POST")

    params = _json_object(settings.request_params_json, "Request Parameters")
    headers = _json_object(settings.request_headers_json, "Request Headers")
    rate_date = str(today())

    if settings.from_currency_param:
        params[settings.from_currency_param] = "{from_currency}"
    if settings.to_currency_param:
        params[settings.to_currency_param] = "{to_currency}"
    if settings.date_param:
        params[settings.date_param] = "{date}"

    params = {key: _render_value(value, source, target, rate_date) for key, value in params.items()}
    headers = {str(key): str(value) for key, value in headers.items()}
    if any(str(key).lower() in SENSITIVE_KEYS for key in headers):
        raise ValueError("Configure credentials in Authentication fields, not Additional HTTP Headers")

    auth_mode = settings.auth_mode or "None"
    api_key = _secret(settings, "api_key")
    api_secret = _secret(settings, "api_secret")
    basic_password = _secret(settings, "basic_password")
    key_name = (settings.api_key_name or "api_key").strip()
    secret_name = (settings.api_secret_name or "api_secret").strip()

    if auth_mode in {"API Key (Query)", "API Key + Secret (Query)"}:
        if not api_key:
            raise ValueError("API Key is required for selected authentication mode")
        params[key_name] = api_key
        if auth_mode == "API Key + Secret (Query)":
            if not api_secret:
                raise ValueError("API Secret is required for selected authentication mode")
            params[secret_name] = api_secret
    elif auth_mode in {"API Key (Header)", "API Key + Secret (Header)"}:
        if not api_key:
            raise ValueError("API Key is required for selected authentication mode")
        headers[key_name] = api_key
        if auth_mode == "API Key + Secret (Header)":
            if not api_secret:
                raise ValueError("API Secret is required for selected authentication mode")
            headers[secret_name] = api_secret
    elif auth_mode == "Bearer Token":
        if not api_key:
            raise ValueError("Token is required for selected authentication mode")
        headers["Authorization"] = "Bearer " + api_key
    elif auth_mode == "Basic Auth":
        if not settings.basic_username or not basic_password:
            raise ValueError("Basic Auth username and password are required")
        token = base64.b64encode((settings.basic_username + ":" + basic_password).encode("utf-8")).decode("ascii")
        headers["Authorization"] = "Basic " + token
    elif auth_mode != "None":
        raise ValueError("Unsupported authentication mode")

    headers.setdefault("Accept", "application/json")
    headers.setdefault("User-Agent", "ERPNext-Tools-ExchangeRates/1.0")

    body = None
    request_url = endpoint
    if method == "GET":
        split = urlsplit(endpoint)
        existing_query = split.query
        query = urlencode(params)
        request_url = urlunsplit((split.scheme, split.netloc, split.path, "&".join(x for x in [existing_query, query] if x), split.fragment))
    else:
        headers.setdefault("Content-Type", "application/json")
        body = json.dumps(params).encode("utf-8")

    # Never include request_url or headers in an exception or log: credentials may be in query params.
    request = Request(request_url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=max(3, min(int(settings.timeout or 10), 30))) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise ValueError("API returned HTTP status {0}".format(exc.code))
    except (URLError, TimeoutError, OSError):
        raise ValueError("Could not connect to the configured exchange-rate API")
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("API response was not valid UTF-8 JSON")

    if not isinstance(payload, (dict, list)):
        raise ValueError("API response must be a JSON object or array")

    success_path = (settings.response_success_path or "").strip()
    if success_path:
        actual = _json_path(payload, success_path)
        expected = str(settings.response_success_value if settings.response_success_value is not None else "1")
        if actual is None or str(actual).lower() != expected.lower():
            error = _json_path(payload, settings.response_error_path or "")
            raise ValueError("API reported failure: " + _redact_message(error or "success field did not match expected value"))

    returned_source = _json_path(payload, settings.response_source_currency_path or "")
    returned_target = _json_path(payload, settings.response_target_currency_path or "")
    if returned_source is not None and str(returned_source).upper() != source:
        raise ValueError("API returned a different source currency")
    if returned_target is not None and str(returned_target).upper() != target:
        raise ValueError("API returned a different target currency")

    raw_rate = _json_path(payload, settings.response_rate_path or "rate")
    try:
        rate = Decimal(str(raw_rate))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Configured rate JSON path did not resolve to a numeric value")
    if not rate.is_finite() or rate <= 0:
        raise ValueError("API returned a non-positive exchange rate")
    return float(rate)


def _upsert_record(rate_date, source, target, rate=None, status="Success", error=None, currency_exchange=None, provider=None):
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
        "source": (provider or "Configured API")[:140],
        "status": status,
        "fetched_at": now_datetime(),
        "error_message": (error or "")[:1000],
        "currency_exchange": currency_exchange,
    }
    if name:
        doc = frappe.get_doc(RECORD_DOCTYPE, name)
        # Do not destroy a previously valid rate when a later refresh fails.
        if status != "Success":
            values["exchange_rate"] = doc.exchange_rate
            values["currency_exchange"] = doc.currency_exchange
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
                currency_exchange=exchange_name, provider=settings.provider_name,
            )
            successes.append({"pair": f"{source}/{target}", "rate": rate, "record": record.name})
        except Exception as exc:
            error = _redact_message(exc, settings)
            _upsert_record(rate_date, source, target, status="Failed", error=error, provider=settings.provider_name)
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
