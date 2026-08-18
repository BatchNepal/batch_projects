"""BP Task v2 fields backfill (2026-08-14).

Three things, in order:

1. `sequence_no` — a global monotonic sequence, the stable internal identity
   that survives task_key format changes. Existing rows are numbered in
   creation order (name as a stable tiebreak), and the BP Task Sequence
   single's `last_value` is set to the max so future inserts continue from
   there. Future inserts self-assign via BPTask.before_insert — nothing to
   do there.

2. `planned_start` / `planned_end` — the scheduling plan. Legacy rows carry
   their plan in start_date / due_date, so those are copied across (only
   where the new field is still empty) to keep the Gantt identical before
   and after this patch.

3. Blocked fields (blocked_reason/blocked_since/blocked_by) start empty —
   no backfill possible or needed.

Idempotent by construction: sequence numbering is only applied where
sequence_no is 0/empty, planned dates only where empty, and the sequence
single only ever moves forward to MAX.
"""
import frappe


def execute():
    # ── 1. sequence_no backfill (creation order, name tiebreak) ─────────
    tasks = frappe.db.sql(
        """SELECT name FROM `tabBP Task`
           WHERE COALESCE(sequence_no, 0) = 0
           ORDER BY creation ASC, name ASC""",
        as_dict=True,
    )
    seq = frappe.db.sql("SELECT COALESCE(MAX(sequence_no), 0) FROM `tabBP Task`")[0][0] or 0
    for i, row in enumerate(tasks, start=1):
        seq += 1
        frappe.db.set_value("BP Task", row["name"], "sequence_no", seq, update_modified=False)
        if i % 500 == 0:
            frappe.db.commit()

    # ── 2. sequence single: continue from the max we just assigned ───────
    if frappe.db.exists("BP Task Sequence", "BP Task Sequence"):
        frappe.db.set_value("BP Task Sequence", "BP Task Sequence", "last_value", seq, update_modified=False)
    else:
        frappe.get_doc({"doctype": "BP Task Sequence", "last_value": seq}).insert(ignore_permissions=True)

    # ── 3. planned dates inherit the legacy plan ─────────────────────────
    frappe.db.sql(
        "UPDATE `tabBP Task` SET planned_start = start_date "
        "WHERE planned_start IS NULL AND start_date IS NOT NULL"
    )
    frappe.db.sql(
        "UPDATE `tabBP Task` SET planned_end = due_date "
        "WHERE planned_end IS NULL AND due_date IS NOT NULL"
    )

    frappe.db.commit()
