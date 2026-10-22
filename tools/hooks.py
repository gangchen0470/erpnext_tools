from . import __version__ as app_version

app_name = "tools"
app_title = "Tools"
app_publisher = "Internal IT"
app_description = "Unified entry point for internal tools"
app_email = ""
app_license = "MIT"
app_version = app_version
required_apps = ["erpnext"]

app_logo_url = "/assets/tools/images/tools-logo.svg"
app_home = "/app/tools"

add_to_apps_screen = [
    {
        "name": "tools",
        "logo": app_logo_url,
        "title": "Tools",
        "route": app_home,
        "has_permission": "tools.api.has_app_permission",
        "sequence_id": 20,
    }
]

before_install = "tools.setup.before_install"
after_install = "tools.setup.after_install"
after_migrate = "tools.setup.after_migrate"
