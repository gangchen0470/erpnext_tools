from frappe.model.document import Document


class ExchangeRateSettings(Document):
    def validate(self):
        if self.api_url and not self.api_url.startswith("https://"):
            import frappe
            frappe.throw("API URL must use HTTPS")
        if self.timeout and (self.timeout < 3 or self.timeout > 30):
            import frappe
            frappe.throw("Request timeout must be between 3 and 30 seconds")
