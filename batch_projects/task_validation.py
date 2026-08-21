"""Composite BP Task validation entrypoint.

Keeps the existing high-blast-radius invariants in task_invariants.py while
allowing additional schema checks to be composed without growing api/board.py
or relying on one write path.
"""

from __future__ import annotations

import json

import frappe

from batch_projects import task_invariants


def _labels(raw) -> list[str]:
    if not raw:
        return []
    value = raw
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            frappe.throw("Task labels must be valid JSON.", frappe.ValidationError)
    if not isinstance(value, list):
        frappe.throw("Task labels must be a list.", frappe.ValidationError)
    return [str(v) for v in value if v not in (None, "")]


def validate_task_labels(doc, old=None) -> None:
    """New/changed task labels must exist in the project's label catalog.

    Task label storage is currently name-backed. Unchanged historical values
    are grandfathered; once the task's labels or project changes, the complete
    submitted set must be valid and duplicate-free.
    """
    if old and old.project == doc.project and _labels(old.labels) == _labels(doc.labels):
        return

    labels = _labels(doc.labels)
    if len(labels) != len(set(labels)):
        frappe.throw("A task cannot contain the same label more than once.", frappe.ValidationError)
    if not labels:
        return

    raw_catalog = frappe.db.get_value("BP Project", doc.project, "labels") or "[]"
    try:
        catalog = json.loads(raw_catalog) if isinstance(raw_catalog, str) else raw_catalog
    except (TypeError, ValueError):
        frappe.throw(
            "Project labels contain invalid JSON. Repair the project label schema first.",
            frappe.ValidationError,
        )
    if not isinstance(catalog, list):
        frappe.throw("Project label schema must be a list.", frappe.ValidationError)

    valid_names = {
        str(row.get("label") or "").strip()
        for row in catalog
        if isinstance(row, dict) and row.get("label")
    }
    unknown = sorted(set(labels) - valid_names)
    if unknown:
        frappe.throw(
            "Unknown project label(s): " + ", ".join(unknown) + ". Create the label in project settings before assigning it to a task.",
            frappe.ValidationError,
            title="Invalid task label",
        )


def validate_task(doc, method=None):
    """One durable validation boundary for BP Task mutations."""
    task_invariants.validate_task_assignees(doc, method=method)
    old = doc.get_doc_before_save() if hasattr(doc, "get_doc_before_save") else None
    validate_task_labels(doc, old)
