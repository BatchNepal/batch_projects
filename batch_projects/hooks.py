app_name = "batch_projects"
app_title = "BatchProjects"
app_publisher = "BatchNepal Consultancy"
app_description = "Enterprise Grade Project Management for ERPNext"
app_email = "info@batchnepal.com"
app_license = "AGPL-3.0"
from . import __version__ as app_version

gateway_min_version = "1.0.23"

add_to_apps_screen = [
    {
        "name": "batch_projects",
        "logo": "/assets/batch_projects/images/bp-logo-new.svg",
        "title": "BatchProjects",
        "route": "/workspace",
    }
]

website_route_rules = [
    {"from_route": "/workspace", "to_route": "workspace"},
    {"from_route": "/workspace/<path:app_path>", "to_route": "workspace"},
    {"from_route": "/share/<path:app_path>", "to_route": "workspace"},
    {"from_route": "/intake/<path:app_path>", "to_route": "workspace"},
]

fixtures = [
    {"dt": "Role", "filters": [[
        "name", "in", ["BP Admin", "BP Manager", "BP Member", "BP Viewer", "BP Guest"]
    ]]},
    {"dt": "Custom Field", "filters": [[
        "name", "in", ["Timesheet Detail-custom_bp_task", "Sales Order-custom_bp_project",
                       "Expense Claim Detail-custom_is_billable",
                       "Expense Claim Detail-custom_sales_invoice",
                       "Expense Claim Type-custom_reinvoice_policy",
                       "Expense Claim Type-custom_markup_percent",
                       "Lead-custom_bp_project", "Opportunity-custom_bp_project",
                       "Quotation-custom_bp_project"]
    ]]},
    {"dt": "Client Script", "filters": [[
        "name", "in", ["Sales Order Batch Project Button", "Lead Batch Project Button",
                       "Opportunity Batch Project Button", "Quotation Batch Project Button"]
    ]]},
]

after_install = "batch_projects.setup.install.after_install"
auth_hooks = ["batch_projects.gateway_guard.apply_gateway_identity"]

override_whitelisted_methods = {
    "batch_projects.api.board.get_task":
        "batch_projects.task_reads.get_task",
    "batch_projects.api.board.get_export_data":
        "batch_projects.task_reads.get_export_data",
    "batch_projects.api.board.get_milestone_report":
        "batch_projects.task_aggregates.get_milestone_report",
    "batch_projects.api.board.get_sprint_capacity":
        "batch_projects.task_aggregates.get_sprint_capacity",
    "batch_projects.api.board.get_reports":
        "batch_projects.task_aggregates.get_reports",
    "batch_projects.api.board.delete_task":
        "batch_projects.task_lifecycle.delete_task",
    "batch_projects.api.board.restore_task":
        "batch_projects.task_lifecycle.restore_task",
    "batch_projects.api.board.bulk_delete_tasks":
        "batch_projects.task_lifecycle.bulk_delete_tasks",
    "batch_projects.api.board.sync_rebac_state":
        "batch_projects.rebac_state.sync_rebac_state",
    "batch_projects.api.board.update_project_workflow":
        "batch_projects.project_schema.update_project_workflow",
    "batch_projects.api.board.update_project_issue_types":
        "batch_projects.project_schema.update_project_issue_types",
    "batch_projects.api.board.update_project_labels":
        "batch_projects.project_schema.update_project_labels",
}

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

doc_events = {
    "Timesheet": {
        "on_submit": "batch_projects.timesheet_sync.on_timesheet_submit",
        "on_cancel": "batch_projects.timesheet_sync.on_timesheet_cancel",
    },
    "Sales Invoice": {
        "validate": "batch_projects.billing_reservation.validate_sales_invoice_sources",
        "after_insert": "batch_projects.milestone_billing.on_sales_invoice_after_insert",
        "on_submit": "batch_projects.milestone_billing.on_sales_invoice_submit",
        "on_cancel": "batch_projects.milestone_billing.on_sales_invoice_cancel",
        "on_trash": "batch_projects.milestone_billing.on_sales_invoice_trash",
    },
    "Sales Order": {
        "on_submit": "batch_projects.erp_triggers.on_sales_order_submit",
    },
    "Payment Entry": {
        "on_submit": "batch_projects.erp_triggers.on_payment_entry_submit",
    },
    "BP Task": {
        "before_insert": "batch_projects.task_invariants.before_task_insert",
        "validate": "batch_projects.task_validation.validate_task",
        "after_insert": "batch_projects.task_invariants.after_task_insert",
    },
    "*": {
        "after_insert": "batch_projects.erp_triggers.on_any_doctype_event",
        "on_update": "batch_projects.erp_triggers.on_any_doctype_event",
        "on_submit": "batch_projects.erp_triggers.on_any_doctype_event",
        "on_cancel": "batch_projects.erp_triggers.on_any_doctype_event",
        "on_trash": "batch_projects.erp_triggers.on_any_doctype_event",
    },
    "BP Project Member": {
        "before_insert": "batch_projects.entitlements.before_member_insert",
    },
    "BP Team Member": {
        "before_insert": "batch_projects.entitlements.before_member_insert",
    },
}

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