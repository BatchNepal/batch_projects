# Copyright (c) 2026, Batch Nepal and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class BPTaskWatcher(Document):
    def validate(self):
        """A watcher is a delivery subscription, never an access grant.

        Therefore a watcher row may exist only while its user can already view
        the task through project membership/admin standing or an assignee edge.
        Enforcing this at the DocType boundary covers manual follows,
        auto-watch from assignment/comment/mention/approval, REST and ORM.
        """
        from batch_projects.task_invariants import _user_can_view_task

        task = frappe.db.get_value(
            "BP Task", self.task, ["project", "is_deleted"], as_dict=True
        )
        if not task or task.is_deleted:
            frappe.throw("Cannot watch a task that does not exist or is in trash.")

        if self.project and self.project != task.project:
            frappe.throw("Watcher project does not match the task project.")
        self.project = task.project

        if not _user_can_view_task(task.project, self.task, self.user):
            frappe.throw(
                "You cannot watch this task because you do not have access to it.",
                frappe.PermissionError,
            )

        duplicate = frappe.db.exists(
            "BP Task Watcher",
            {"task": self.task, "user": self.user, "name": ["!=", self.name or ""]},
        )
        if duplicate:
            frappe.throw("This user is already watching the task.", frappe.ValidationError)
