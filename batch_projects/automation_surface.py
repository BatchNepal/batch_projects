"""Automation-builder extensions for durable task lifecycle events."""

from __future__ import annotations

import frappe


_LIFECYCLE_TRIGGERS = (
    {"value": "task.trashed", "label": "When a task is moved to trash"},
    {"value": "task.restored", "label": "When a task is restored from trash"},
)


@frappe.whitelist()
def get_automation_options(project=None):
    """Preserve the existing option payload and append first-class lifecycle triggers."""
    from batch_projects.api import board

    result = board.get_automation_options(project)
    triggers = [dict(row) for row in (result.get("triggers") or [])]
    existing = {row.get("value") for row in triggers}
    for trigger in _LIFECYCLE_TRIGGERS:
        if trigger["value"] not in existing:
            triggers.append(dict(trigger))
    result["triggers"] = triggers
    return result
