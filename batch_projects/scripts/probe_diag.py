"""Temporary read-only diagnostic: is the BP Task Sequence doctype/table
really present on the site, and did the backfill patch get logged?"""
import frappe


def run():
    print("DOCTYPE_ROW:", frappe.db.exists("DocType", "BP Task Sequence"))
    print("TABLE_TASK_SEQ:", frappe.db.sql("SHOW TABLES LIKE 'tabBP Task Sequence'"))
    print("TABLE_TASK:", frappe.db.sql("SHOW TABLES LIKE 'tabBP Task'"))
    print("TABLE_DOCTYPE:", frappe.db.sql("SHOW TABLES LIKE 'tabDocType'"))
    print("PATCH_LOG:", frappe.get_all(
        "Patch Log",
        filters={"patch": ["like", "%backfill_task_sequence%"]},
        fields=["patch", "creation"],
        order_by="creation desc", limit=3,
    ))
    print("TASK_COUNT:", frappe.db.count("BP Task"))
    print("SEQ_COL:", frappe.db.sql(
        "SELECT COUNT(*) FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'tabBP Task' "
        "AND COLUMN_NAME IN ('sequence_no','planned_start','planned_end','completed_by',"
        "'blocked_reason','blocked_since','blocked_by')"))
    return "diag done"
