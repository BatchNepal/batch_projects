"""Backfill watch_reason on existing BP Task Watcher rows.

Existing watchers predate the watch_reason column. We can't reconstruct
the original cause (manual vs mentioned vs assigned etc.), so they all
get 'manual' — the safest default since it makes no claim we can't verify.

Idempotent: only touches rows where watch_reason is NULL or empty.
"""
import frappe


def execute():
    frappe.db.sql(
        "UPDATE `tabBP Task Watcher` SET watch_reason = 'manual' "
        "WHERE watch_reason IS NULL OR watch_reason = ''"
    )
    frappe.db.commit()