import frappe
from frappe.model.document import Document


class BPActivity(Document):
    def validate(self):
        # Comment mentions are an information-disclosure boundary: a mention
        # must never become an implicit grant to a task the target could not
        # otherwise see.  Keep this on BP Activity itself so create + edit,
        # API + REST + ORM all share the same contract.
        if self.action_type == "Comment" and self.task:
            from batch_projects.task_invariants import validate_comment_mentions

            validate_comment_mentions(self)

    def before_insert(self):
        """Every durable activity row must carry an origin.

        Keep an explicit caller-supplied source unchanged. Otherwise infer at
        the DocType boundary so every creation path (task lifecycle, comments,
        guest comments, automations, imports) inherits the invariant instead
        of relying on each API call site to remember the field.
        """
        if self.source:
            return

        if int(frappe.flags.get("bp_automation_depth", 0) or 0) > 0:
            self.source = "automation"
            return

        # Recurring occurrences are created by the bridge scheduler through a
        # service-account request, not by the human represented by session.user.
        # The inserted BP Task is already durable by the time after_insert logs
        # its "Created" activity, so recurrence_source is authoritative here.
        if self.action_type == "Created" and self.task:
            recurrence_source = frappe.db.get_value(
                "BP Task", self.task, "recurrence_source"
            )
            if recurrence_source:
                self.source = "system"
                return

        self.source = "user"
