import frappe
from frappe.tests.utils import FrappeTestCase


class TestToolDefinition(FrappeTestCase):
    def test_rejects_insecure_external_url(self):
        doc = frappe.get_doc(
            {
                "doctype": "Tool Definition",
                "title": "Unsafe Example",
                "category": "General",
                "route_type": "External URL",
                "route": "http://example.com",
            }
        )
        self.assertRaises(frappe.ValidationError, doc.insert)

    def test_accepts_desk_route(self):
        doc = frappe.get_doc(
            {
                "doctype": "Tool Definition",
                "title": "Test Desk Tool",
                "category": "General",
                "route_type": "Desk Route",
                "route": "/app/user",
            }
        ).insert()
        self.assertEqual(doc.route, "/app/user")
