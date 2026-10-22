from urllib.parse import urlparse

import frappe
from frappe import _

ALLOWED_ROLES = {"System Manager", "Tools User", "Tools Manager"}


def has_app_permission():
    if frappe.session.user == "Guest":
        return False
    return bool(ALLOWED_ROLES.intersection(frappe.get_roles()))


def _can_use_tool(required_role):
    roles = set(frappe.get_roles())
    return (
        "System Manager" in roles
        or "Tools Manager" in roles
        or not required_role
        or required_role in roles
    )


def _safe_route(route_type, route):
    route = (route or "").strip()
    if route_type == "External URL":
        parsed = urlparse(route)
        if parsed.scheme != "https" or not parsed.netloc:
            frappe.throw(_("External tools must use a valid HTTPS URL"))
        return route

    if not route.startswith("/") or route.startswith("//"):
        frappe.throw(_("Desk routes must start with one slash"))
    return route


@frappe.whitelist()
def get_tools():
    if not has_app_permission():
        frappe.throw(_("Not permitted"), frappe.PermissionError)

    enabled_categories = frappe.get_all(
        "Tool Category", filters={"enabled": 1}, pluck="name"
    )
    if not enabled_categories:
        return []

    rows = frappe.get_all(
        "Tool Definition",
        filters={"enabled": 1, "category": ["in", enabled_categories]},
        fields=[
            "name",
            "title",
            "category",
            "description",
            "icon",
            "color",
            "route_type",
            "route",
            "required_role",
            "open_in_new_tab",
            "sequence",
        ],
        order_by="sequence asc, title asc",
    )

    allowed = []
    for row in rows:
        if _can_use_tool(row.required_role):
            row.route = _safe_route(row.route_type, row.route)
            allowed.append(row)
    return allowed
