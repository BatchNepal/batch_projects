app_name = "batch_projects"
app_title = "BatchProjects"
app_publisher = "BatchNepal Consultancy"
app_description = "Enterprise Grade Project Management for ERPNext"
app_email = "info@batchnepal.com"
app_license = "AGPL-3.0"
# Single source of truth is __init__.py's __version__ — the same thing
# pyproject.toml resolves (dynamic = ["version"], flit reads it) and the same
# thing frappe.utils.get_app_version() returns. Hardcoding the number a second
# time here is what let the two drift silently; frappe's own hooks.py imports
# it exactly this way for the same reason.
from . import __version__ as app_version

# Minimum bp-gateway release this batch_projects version requires. Read by
# the gateway itself at boot (via get_session_info) to refuse starting
# against an incompatible batch_projects, and by the gateway installer to
# resolve which gateway version to install/update to.
#
# 1.0.23 is the first release carrying the /v1/insights/* plane. This app no
# longer computes the margin report, the portfolio rollup or the Money tab —
# it asks the gateway to. Against 1.0.22 or older those three pages get a 404
# from a gateway that has no such routes, so the floor has to move with them:
# a version mismatch must fail loudly at boot, not as three broken pages.
gateway_min_version = "1.0.23"

add_to_apps_screen = [
    {
        "name": "batch_projects",
        "logo": "/assets/batch_projects/images/bp-logo-new.svg",
        "title": "BatchProjects",
        "route": "/workspace",
    }
]

# app_include_js = ["/assets/batch_projects/js/batch_projects.js"]

# Website route rules — catch both /workspace and /workspace/<any path>
website_route_rules = [
    {"from_route": "/workspace", "to_route": "workspace"},
    {"from_route": "/workspace/<path:app_path>", "to_route": "workspace"},
    # Public, view-only share links — served by the same SPA bundle. The SPA
    # router resolves /share/:token and renders the chrome-less read-only page.
    {"from_route": "/share/<path:app_path>", "to_route": "workspace"},
    # Public intake forms — same shape, resolved by the SPA router's
    # /intake/:token route (IntakeForm.vue). Without this entry the request
    # never leaves Frappe's website-routing layer and 404s before reaching
    # the SPA at all.
    {"from_route": "/intake/<path:app_path>", "to_route": "workspace"},
]

# Fixtures for export — roles must match what board.py actually uses
fixtures = [
    {"dt": "Role", "filters": [[
        "name", "in", ["BP Admin", "BP Manager", "BP Member", "BP Viewer", "BP Guest"]
    ]]},
    # Custom fields on core ERPNext doctypes — NEVER edit erpnext JSON directly,
    # these ship as fixtures. Filtered to exactly the fields we own.
    {"dt": "Custom Field", "filters": [[
        "name", "in", ["Timesheet Detail-custom_bp_task", "Sales Order-custom_bp_project",
                       "Expense Claim Detail-custom_is_billable",
                       "Expense Claim Detail-custom_sales_invoice",
                       "Expense Claim Type-custom_reinvoice_policy",
                       "Expense Claim Type-custom_markup_percent",
                       "Lead-custom_bp_project", "Opportunity-custom_bp_project",
                       "Quotation-custom_bp_project"]
    ]]},
    # Client Script on Sales Order (8C) / Lead / Opportunity / Quotation —
    # the "Create Batch Project" button, one per stage of the pipeline.
    {"dt": "Client Script", "filters": [[
        "name", "in", ["Sales Order Batch Project Button", "Lead Batch Project Button",
                       "Opportunity Batch Project Button", "Quotation Batch Project Button"]
    ]]},
]

# Hooks
after_install = "batch_projects.setup.install.after_install"

# Runs inside frappe.auth.validate_auth() on every request. Re-scopes
# frappe.session.user from the gateway's service account (what actually
# authenticated a cross-origin browser call — Frappe has no notion of the
# gateway's own JWTs) to the real user the gateway's signed X-BP-Acting-User
# header asserts. No-ops for same-origin traffic and anything not proxied by
# the gateway. See gateway_guard.py's module docstring.
auth_hooks = ["batch_projects.gateway_guard.apply_gateway_identity"]

# Data-layer access control — closes the generic-REST bypass and enforces
# project `visibility`. See batch_projects/permissions.py.
#
# BP Milestone / BP Risk / BP Automation Run are project-scoped but granted
# to broad stock roles (Projects User/Manager) with no hook at all, so the
# generic REST API bypasses project access entirely for them (including
# BP Milestone's invoice_amount/sales_invoice billing fields). BP
# Notification is scoped to `recipient`, not a project; it has `All: write`,
# letting any user mark ANY other user's notification read/unread via raw
# REST (mark_notification_read/_unread are the correct, redundant-but-
# harmless whitelisted path for the SPA).
permission_query_conditions = {
    "BP Task":            "batch_projects.permissions.bp_task_query_conditions",
    "BP Project":         "batch_projects.permissions.bp_project_query_conditions",
    "BP Sprint":          "batch_projects.permissions.bp_sprint_query_conditions",
    "BP Epic":            "batch_projects.permissions.bp_epic_query_conditions",
    "BP Report":          "batch_projects.permissions.bp_report_query_conditions",
    "BP Milestone":       "batch_projects.permissions.bp_milestone_query_conditions",
    "BP Risk":            "batch_projects.permissions.bp_risk_query_conditions",
    "BP Automation Run":  "batch_projects.permissions.bp_automation_run_query_conditions",
    "BP Notification":    "batch_projects.permissions.bp_notification_query_conditions",
    "BP Webhook Token":   "batch_projects.permissions.bp_webhook_token_query_conditions",
    # Project-scoped doctypes with a `project` field but no hook without
    # this (see permissions.py for the shared query-condition primitives).
    "BP Drawing":           "batch_projects.permissions.bp_drawing_query_conditions",
    "BP Intake Form":       "batch_projects.permissions.bp_intake_form_query_conditions",
    "BP Invitation":        "batch_projects.permissions.bp_invitation_query_conditions",
    "BP Note":              "batch_projects.permissions.bp_note_query_conditions",
    "BP Share Link":        "batch_projects.permissions.bp_share_link_query_conditions",
    "BP SLA Policy":        "batch_projects.permissions.bp_sla_policy_query_conditions",
    "BP Task Template":     "batch_projects.permissions.bp_task_template_query_conditions",
    "BP View":              "batch_projects.permissions.bp_view_query_conditions",
    "BP Activity":          "batch_projects.permissions.bp_activity_query_conditions",
    "BP Audit Log":         "batch_projects.permissions.bp_audit_log_query_conditions",
    "BP Automation Rule":   "batch_projects.permissions.bp_automation_rule_query_conditions",
    "BP Notification Mute": "batch_projects.permissions.bp_notification_mute_query_conditions",
    "BP Notification Rule": "batch_projects.permissions.bp_notification_rule_query_conditions",
    "BP SLA Breach":        "batch_projects.permissions.bp_sla_breach_query_conditions",
    "BP Task Watcher":      "batch_projects.permissions.bp_task_watcher_query_conditions",
    "BP View Preference":   "batch_projects.permissions.bp_view_preference_query_conditions",
    "BP Workflow":          "batch_projects.permissions.bp_workflow_query_conditions",
}
has_permission = {
    "BP Task":            "batch_projects.permissions.bp_task_has_permission",
    "BP Project":         "batch_projects.permissions.bp_doc_has_permission",
    "BP Sprint":          "batch_projects.permissions.bp_doc_has_permission",
    "BP Epic":            "batch_projects.permissions.bp_doc_has_permission",
    "BP Report":          "batch_projects.permissions.bp_doc_has_permission",
    "BP Milestone":       "batch_projects.permissions.bp_doc_has_permission",
    "BP Risk":            "batch_projects.permissions.bp_doc_has_permission",
    "BP Automation Run":  "batch_projects.permissions.bp_doc_has_permission",
    "BP Notification":    "batch_projects.permissions.bp_notification_has_permission",
    "BP Webhook Token":   "batch_projects.permissions.bp_webhook_token_has_permission",
    "BP Drawing":           "batch_projects.permissions.bp_doc_has_permission",
    "BP Intake Form":       "batch_projects.permissions.bp_doc_has_permission",
    "BP Invitation":        "batch_projects.permissions.bp_doc_has_permission",
    "BP Note":              "batch_projects.permissions.bp_doc_has_permission",
    "BP Share Link":        "batch_projects.permissions.bp_doc_has_permission",
    "BP SLA Policy":        "batch_projects.permissions.bp_doc_has_permission",
    "BP Task Template":     "batch_projects.permissions.bp_doc_has_permission",
    "BP View":              "batch_projects.permissions.bp_doc_has_permission",
    "BP Activity":          "batch_projects.permissions.bp_doc_has_permission",
    "BP Audit Log":         "batch_projects.permissions.bp_doc_has_permission",
    "BP Automation Rule":   "batch_projects.permissions.bp_doc_has_permission",
    "BP Notification Mute": "batch_projects.permissions.bp_doc_has_permission",
    "BP Notification Rule": "batch_projects.permissions.bp_doc_has_permission",
    "BP SLA Breach":        "batch_projects.permissions.bp_doc_has_permission",
    "BP Task Watcher":      "batch_projects.permissions.bp_doc_has_permission",
    "BP View Preference":   "batch_projects.permissions.bp_doc_has_permission",
    "BP Workflow":          "batch_projects.permissions.bp_doc_has_permission",
}

# actual_hours rollup — resync every BP Task a submitted/cancelled
# Timesheet's rows point at (via the custom_bp_task fixture field).
# erp.* automation triggers fire onto the same events.emit() bus every
# task/comment/schedule trigger already rides. Tenancy-checked no-ops for
# anything outside a BP Project.
doc_events = {
    "Timesheet": {
        "on_submit": "batch_projects.timesheet_sync.on_timesheet_submit",
        "on_cancel": "batch_projects.timesheet_sync.on_timesheet_cancel",
    },
    "Sales Invoice": {
        # P0 billing reservation: native ERPNext draft creation/editing must
        # obey the same Timesheet Detail exclusivity as BatchProjects.
        "validate": "batch_projects.billing_reservation.validate_sales_invoice_sources",
        "on_submit": "batch_projects.erp_triggers.on_sales_invoice_submit",
    },
    "Sales Order": {
        "on_submit": "batch_projects.erp_triggers.on_sales_order_submit",
    },
    "Payment Entry": {
        "on_submit": "batch_projects.erp_triggers.on_payment_entry_submit",
    },
    # Generic doc-event trigger — widens erp.* coverage beyond the 4
    # hardcoded doctypes above. "*" fires for EVERY doctype site-wide;
    # on_any_doctype_event() bails in ~microseconds via a cached "does any
    # active rule even care" check before doing any real work, so this is
    # near-zero overhead for the common case of zero erp.doc_event rules.
    # The 4 specific handlers above stay as-is (real project-resolution
    # logic worth keeping, and they predate/are unaffected by this).
    "*": {
        "after_insert": "batch_projects.erp_triggers.on_any_doctype_event",
        "on_update": "batch_projects.erp_triggers.on_any_doctype_event",
        "on_submit": "batch_projects.erp_triggers.on_any_doctype_event",
        "on_cancel": "batch_projects.erp_triggers.on_any_doctype_event",
        "on_trash": "batch_projects.erp_triggers.on_any_doctype_event",
    },
    # Seat-limit enforcement — catches EVERY insertion path for BP Project
    # Member and BP Team Member, including the generic REST API, batch
    # operations, and ORM saves. See entitlements.before_member_insert.
    "BP Project Member": {
        "before_insert": "batch_projects.entitlements.before_member_insert",
    },
    "BP Team Member": {
        "before_insert": "batch_projects.entitlements.before_member_insert",
    },
}

# Scheduled jobs
scheduler_events = {
    "hourly": [
        "batch_projects.events.send_scheduled_reports",
        "batch_projects.api.timers.send_timer_reminders",
    ],
    "daily": [
        "batch_projects.events.send_due_date_reminders",
        "batch_projects.events.run_due_soon_automations",
        "batch_projects.events.run_overdue_automations",
        "batch_projects.api.erp_link.reconcile_erpnext_sync",
        "batch_projects.events.purge_expired_trash",
        # Repairs BP Task.actual_hours when it drifts from the submitted
        # timesheets. The live rollup only fires on Timesheet submit/cancel,
        # so anything that moves hours outside that path (failed hook, patch,
        # import, direct row edit) silently desynced a field that feeds
        # billing and margin.
        "batch_projects.timesheet_sync.reconcile_actual_hours",
    ],
    "daily_long": [
        "batch_projects.events.send_daily_digest",
        "batch_projects.events.send_view_subscriptions_daily",
    ],
    "weekly_long": [
        "batch_projects.events.send_weekly_project_summary",
    ],
}