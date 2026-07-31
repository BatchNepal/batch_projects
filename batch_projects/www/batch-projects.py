import frappe
import os

no_cache = 1
base_template_path = ""


def _asset_version():
    try:
        path = frappe.get_app_path("batch_projects", "public", "frontend", "assets", "index.js")
        return str(int(os.path.getmtime(path)))
    except Exception:
        return frappe.utils.random_string(8)


def get_context(context):
    context.csrf_token = frappe.sessions.get_csrf_token()
    context.user_fullname = frappe.utils.get_fullname(frappe.session.user)
    context.no_breadcrumbs = True
    context.no_header = True
    context.show_sidebar = False
    context.asset_version = _asset_version()
    context.bp_bridge_url = frappe.conf.get("bp_bridge_url") or ""