"""
Clear all needs_triage=1 flags that were set by the old
schema default (bp_task.json had "default": "1"). Under the corrected
design, no project could have legitimately earned a triage flag before
the BP Project.triage_enabled opt-in field existed, so all existing
flags are false positives.
"""

import frappe


def execute():
    """Blanket-clear — safe because the triage_enabled project gate
    didn't exist before this patch, so no needs_triage flag was earned."""
    frappe.db.sql("UPDATE `tabBP Task` SET needs_triage = 0 WHERE needs_triage = 1")
    frappe.db.commit()
