import frappe
from frappe.model.document import Document


class BPIntakeForm(Document):
    def validate(self):
        # Project-move authority: an intake form's project can't change once
        # the form exists (its public token would otherwise grant task
        # creation inside a project the mover can't access). api/forms.py's
        # update_intake_form already rejects it at the API layer; this closes
        # the generic REST/ORM/import path. A future dedicated "move form"
        # operation may set flags.allow_project_move after proving Manager+
        # on BOTH projects and rotating the public form identifier.
        previous = self.get_doc_before_save()
        if (previous and previous.project and self.project
                and previous.project != self.project
                and not self.flags.get("allow_project_move")):
            frappe.throw(
                "An intake form can't be moved to a different project.",
                frappe.PermissionError,
            )
        self._validate_task_config()

    def _validate_task_config(self):
        """task_type / default_status must exist in the target project's own
        workflow configuration — a form otherwise advertises (and later
        creates) tasks with values the project never configured."""
        project = self.project
        if not project or not frappe.db.exists("BP Project", project):
            return
        try:
            proj = frappe.get_cached_doc("BP Project", project)
        except Exception:
            return
        if self.task_type:
            try:
                valid_types = proj.get_issue_types()
            except Exception:
                valid_types = []
            if valid_types and self.task_type not in valid_types:
                frappe.throw(
                    f"Task type '{self.task_type}' is not configured for this project.",
                    frappe.ValidationError,
                )
        if self.default_status:
            try:
                valid_states = proj.get_status_names()
            except Exception:
                valid_states = []
            if valid_states and self.default_status not in valid_states:
                frappe.throw(
                    f"Status '{self.default_status}' is not a valid workflow state for this project.",
                    frappe.ValidationError,
                )
