"""
Grants the "BP Member" Frappe Role baseline DocPerm on every project-scoped
BP doctype — the fix for a real gap: permissions.py's has_permission /
permission_query_conditions hooks (the project-scoped access model) never
ran for an ordinary invited member with no unrelated ERPNext role (e.g.
"Projects User"), because Frappe denies at the base DocPerm check before any
hook is consulted. access.ensure_member_role() now grants this role the
moment a user gets project standing; this patch opens the DocPerm door for
everyone who already held that standing before the fix shipped.

Read+write+create (no delete) only for BP Task / BP Project — the two
doctypes with a `has_permission` hook that further narrows write/create by
real project role rank (see bp_task_has_permission / bp_doc_has_permission).
Every other doctype below only has a permission_query_conditions hook (list
filtering, no single-doc role narrowing), so granting write there would let
ANY member bypass an Admin/Manager-only whitelisted endpoint (e.g. BP
Invitation, which invite_member/revoke_invitation gate to project Admin) via
raw REST — kept read-only on purpose.
"""

import frappe


READ_WRITE = ["BP Task", "BP Project"]

READ_ONLY = [
    "BP Sprint", "BP Epic", "BP Report", "BP Milestone", "BP Risk",
    "BP Automation Run", "BP Drawing", "BP Intake Form", "BP Invitation",
    "BP Note", "BP Share Link", "BP SLA Policy", "BP Task Template",
    "BP View", "BP Activity", "BP Audit Log", "BP Automation Rule",
    "BP Notification Mute", "BP Notification Rule", "BP SLA Breach",
    "BP Task Watcher", "BP View Preference", "BP Workflow",
]

ROLE = "BP Member"


def execute():
    if not frappe.db.exists("Role", ROLE):
        return  # fresh install order issue — role fixture didn't sync yet

    for doctype in READ_WRITE + READ_ONLY:
        if not frappe.db.exists("DocType", doctype):
            continue
        frappe.permissions.add_permission(doctype, ROLE, 0)  # read=1 default
        if doctype in READ_WRITE:
            frappe.permissions.update_permission_property(doctype, ROLE, 0, "write", 1)
            frappe.permissions.update_permission_property(doctype, ROLE, 0, "create", 1)

    # Backfill: existing members predate access.ensure_member_role(), which
    # only fires on new invite-accept/create-project/update-members calls
    # going forward.
    users = frappe.get_all("BP Project Member", pluck="user", distinct=True)
    for user in users:
        if not user or user in ("Administrator", "Guest"):
            continue
        if not frappe.db.exists("User", user):
            continue
        if ROLE in frappe.get_roles(user):
            continue
        frappe.get_doc("User", user).add_roles(ROLE)

    frappe.clear_cache()
