from urllib.parse import urlparse

import frappe
from frappe import _
from frappe.model.document import Document


class ToolDefinition(Document):
    def validate(self):
        self.route = (self.route or "").strip()
        if self.route_type == "External URL":
            parsed = urlparse(self.route)
            if parsed.scheme != "https" or not parsed.netloc:
                frappe.throw(_("External tools must use a valid HTTPS URL"))
        elif not self.route.startswith("/") or self.route.startswith("//"):
            frappe.throw(_("Desk routes must start with one slash"))
