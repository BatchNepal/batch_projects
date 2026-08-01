import frappe

from batch_projects.spa_assets import get_spa_entry

no_cache = 1
base_template_path = ""

def get_context(context):
    context.csrf_token = frappe.sessions.get_csrf_token()
    context.user_fullname = frappe.utils.get_fullname(frappe.session.user)
    context.no_breadcrumbs = True
    context.no_header = True
    context.show_sidebar = False
    entry = get_spa_entry()
    context.entry_js = entry["js"]
    context.entry_css = entry["css"]
    context.bp_bridge_url = frappe.conf.get("bp_bridge_url") or ""
