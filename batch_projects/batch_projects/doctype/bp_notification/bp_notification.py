# Copyright (c) 2026, Batch Nepal and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class BPNotification(Document):
    def validate(self):
        """Never persist task metadata for a recipient who cannot see it now.

        This is deliberately below events.py: built-in notifications, custom
        notification rules and automation Notify actions all eventually create
        BP Notification rows, so stale routing data cannot bypass the check.
        """
        from batch_projects.notification_delivery import (
            can_receive_project_delivery,
            require_task_delivery,
        )

        if self.task:
            require_task_delivery(self.recipient, self.task, self.project)
            return

        # Permanent deletion is a tombstone event: there is no task row left to
        # authorize against. Once the task is gone, direct task-only assignment
        # access is gone too, so the minimum safe audience is current project
        # Viewer+. Other project-level notifications (role changes, finance,
        # sprint events) keep their own recipient contracts.
        if self.notification_type == "Task Deleted" and self.project:
            if not can_receive_project_delivery(self.recipient, self.project, "Viewer"):
                frappe.throw(
                    "Notification recipient no longer has access to this project.",
                    frappe.PermissionError,
                    title="Notification delivery blocked",
                )
