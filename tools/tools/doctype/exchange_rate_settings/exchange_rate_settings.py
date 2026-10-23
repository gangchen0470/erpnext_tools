import json
from urllib.parse import urlsplit

import frappe
from frappe import _
from frappe.model.document import Document


class ExchangeRateSettings(Document):
    def validate(self):
        endpoint = (self.api_url or "").strip()
        parsed = urlsplit(endpoint)
        if parsed.scheme != "https" or not parsed.netloc:
            frappe.throw(_("API Endpoint must be a valid HTTPS URL"))
        if parsed.username or parsed.password:
            frappe.throw(_("Do not put credentials in the API URL. Use the Authentication fields."))
        if self.timeout and (self.timeout < 3 or self.timeout > 30):
            frappe.throw(_("Request timeout must be between 3 and 30 seconds"))
        if (self.http_method or "GET") not in {"GET", "POST"}:
            frappe.throw(_("HTTP Method must be GET or POST"))
        for fieldname, label in (
            ("request_params_json", "Request Parameters JSON"),
            ("request_headers_json", "Additional HTTP Headers JSON"),
        ):
            try:
                value = json.loads(self.get(fieldname) or "{}")
            except (ValueError, TypeError):
                frappe.throw(_("{0} must contain valid JSON").format(label))
            if not isinstance(value, dict):
                frappe.throw(_("{0} must be a JSON object").format(label))
        if not self.response_rate_path:
            frappe.throw(_("Rate JSON Path is required"))
