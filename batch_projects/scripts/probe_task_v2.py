"""Temporary verification probe for BP Task v2 fields (sequence_no,
planned_start/planned_end, completed_by, blocked_*). Run via:

    batch bench freedom-erp-dev execute batch_projects.scripts.probe_task_v2.run

Creates one throwaway task, verifies the new-field behaviour end to end,
then deletes it (plus its activity rows). Prints a receipt per check.
"""
import frappe


def run():
    from batch_projects.api.board import create_task, update_task

    meta = frappe.get_meta("BP Task")
    out = []
    out.append(("FIELDS", {f: bool(meta.get_field(f)) for f in (
        "sequence_no", "planned_start", "planned_end", "completed_by",
        "blocked_reason", "blocked_since", "blocked_by")}))
    out.append(("MAX_SEQ", frappe.db.sql("SELECT MAX(sequence_no) FROM `tabBP Task`")[0][0]))
    out.append(("NULL_SEQ_COUNT", frappe.db.sql(
        "SELECT COUNT(*) FROM `tabBP Task` WHERE sequence_no IS NULL OR sequence_no=0")[0][0]))
    out.append(("SEQ_SINGLE", frappe.db.get_value("BP Task Sequence", "BP Task Sequence", "last_value")))
    out.append(("PLANNED_NULLS", frappe.db.sql(
        "SELECT COUNT(*) FROM `tabBP Task` WHERE start_date IS NOT NULL AND planned_start IS NULL")[0][0]))

    proj = frappe.db.get_value("BP Project", {"status": "Active"}, "name", order_by="creation asc")
    created_name = None
    try:
        if not proj:
            out.append(("ERROR", "no active project to test against"))
            for k, v in out:
                print(f"{k}: {v}")
            return
        created = create_task(
            project=proj, title="__bp_v2_probe__",
            planned_start="2026-09-01", planned_end="2026-09-05",
        )
        created_name = created["name"]
        doc = frappe.get_doc("BP Task", created_name)
        out.append(("CREATED", {
            "name": doc.name, "task_key": doc.task_key, "seq": doc.sequence_no,
            "planned_start": str(doc.planned_start), "planned_end": str(doc.planned_end),
        }))
        out.append(("SEQ_SINGLE_AFTER_CREATE",
                    frappe.db.get_value("BP Task Sequence", "BP Task Sequence", "last_value")))

        # Blocked via the generic member write path (allowlist + controller sync)
        update_task(created_name, {"blocked_reason": "Waiting for Client"})
        doc.reload()
        out.append(("BLOCKED_SET", {
            "reason": doc.blocked_reason, "since": str(doc.blocked_since), "by": doc.blocked_by,
        }))
        update_task(created_name, {"blocked_reason": ""})
        doc.reload()
        out.append(("BLOCKED_CLEARED", {
            "reason": doc.blocked_reason, "since": doc.blocked_since, "by": doc.blocked_by,
        }))

        # completed_by on entering a completed status
        states = frappe.get_cached_doc("BP Project", proj).get_completed_statuses()
        if states:
            update_task(created_name, {"status": states[0]})
            doc.reload()
            out.append(("COMPLETED", {
                "status": doc.status, "completed_on": str(doc.completed_on),
                "completed_by": doc.completed_by,
            }))
        else:
            out.append(("COMPLETED_SKIP", "no completed workflow state on probe project"))
    finally:
        if created_name:
            frappe.delete_doc("BP Task", created_name, force=True, ignore_permissions=True)
            frappe.db.delete("BP Activity", {"task": created_name})
        frappe.db.commit()

    for k, v in out:
        print(f"{k}: {v}")
    return "probe done"
