import frappe
from frappe.model.document import Document


class BPNotificationRule(Document):
    def validate(self):
        """Keep static notification recipients inside the authorization graph.

        Dynamic recipients are safe by construction once watcher/assignee
        invariants hold: assignee and watcher refer to task-scoped principals,
        and project_role resolves project members. A literal ``user`` recipient
        is different: without this check a global rule can email/desktop-push
        private task titles to an unrelated account.
        """
        raw = self.recipients_json or []
        try:
            recipients = frappe.parse_json(raw) if isinstance(raw, str) else raw
        except Exception:
            frappe.throw("Recipients must be valid JSON.", frappe.ValidationError)
        if not isinstance(recipients, list):
            frappe.throw("Recipients must be a list.", frappe.ValidationError)

        from batch_projects import access

        for recipient in recipients:
            if not isinstance(recipient, dict) or recipient.get("type") != "user":
                continue
            user = (recipient.get("value") or "").strip()
            row = frappe.db.get_value(
                "User", user, ["enabled", "user_type"], as_dict=True
            ) if user else None
            if not row or not row.enabled or row.user_type != "System User":
                frappe.throw(
                    f"Notification recipient '{user or '(blank)'}' is not an enabled System User.",
                    frappe.ValidationError,
                )

            if self.project:
                if not access.has_at_least(self.project, "Viewer", user):
                    frappe.throw(
                        f"{user} cannot receive this rule because they do not have "
                        "access to the selected project.",
                        frappe.PermissionError,
                        title="Notification recipient has no project access",
                    )
            elif not access.is_instance_admin(user):
                # A workspace-wide rule may fire for private projects. There
                # is no single safe project to validate at save time, so only
                # an instance admin (who can view every project by definition)
                # may be a literal static recipient. Use project_role,
                # assignee or watchers for normal global routing.
                frappe.throw(
                    "A global notification rule cannot target a literal user "
                    "unless that user is an instance administrator. Use a "
                    "dynamic recipient such as project_role, assignee or watchers.",
                    frappe.ValidationError,
                    title="Unsafe global notification recipient",
                )
