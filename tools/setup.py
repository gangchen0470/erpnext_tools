import frappe

ROLES = ("Tools User", "Tools Manager")


def ensure_roles():
    for role_name in ROLES:
        if not frappe.db.exists("Role", role_name):
            frappe.get_doc(
                {"doctype": "Role", "role_name": role_name, "desk_access": 1}
            ).insert(ignore_permissions=True)


def ensure_default_category():
    if not frappe.db.exists("Tool Category", "General"):
        frappe.get_doc(
            {
                "doctype": "Tool Category",
                "title": "General",
                "description": "General internal tools",
                "icon": "tool",
                "color": "blue",
                "enabled": 1,
                "sequence": 100,
            }
        ).insert(ignore_permissions=True)


def before_install():
    ensure_roles()


def after_install():
    ensure_roles()
    ensure_default_category()


def after_migrate():
    ensure_roles()
    ensure_default_category()
