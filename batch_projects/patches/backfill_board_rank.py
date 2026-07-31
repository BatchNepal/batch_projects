"""
Backfill board_rank for existing tasks.

Each (project, status) column is re-spaced by its current manual order
(old board_order, then creation) so the new fractional ranking starts clean.
"""

import frappe
from batch_projects.rank import fmt, STEP


def execute():
    if not frappe.db.has_column("BP Task", "board_rank"):
        return

    columns = frappe.db.sql(
        "SELECT DISTINCT project, status FROM `tabBP Task`", as_dict=True)

    for col in columns:
        names = frappe.get_all(
            "BP Task",
            filters={"project": col.project, "status": col.status},
            order_by="board_order asc, creation asc",
            pluck="name",
        )
        for i, name in enumerate(names, start=1):
            frappe.db.set_value("BP Task", name, "board_rank", fmt(i * STEP),
                                update_modified=False)

    frappe.db.commit()
