"""
batch_projects/api/task_templates.py
─────────────────────────────────────
Task Templates — reusable task blueprints (title/type/priority/description/
labels/story points + a fixed set of subtasks) that stamp out a new task in
one call. Team-tier feature; listing stays free so the UI can show the
locked state on write/apply actions, same pattern as automations.
"""

import frappe
import json
from batch_projects import access
from batch_projects.entitlements import require_feature


def _guard():
    from batch_projects.gateway_guard import verify_gateway_request
    verify_gateway_request()


def _parse_json(value, default):
    if not value:
        return default
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


def _template_dict(doc) -> dict:
    return {
        "name": doc.name,
        "template_name": doc.template_name,
        "project": doc.project,
        "task_type": doc.task_type,
        "priority": doc.priority,
        "title_template": doc.title_template or "",
        "description": doc.description or "",
        "labels": _parse_json(doc.labels, []),
        "story_points": doc.story_points or 0,
        "items": [{"title": i.title, "task_type": i.task_type} for i in (doc.items or [])],
    }


@frappe.whitelist()
def list_task_templates(project):
    """All templates for a project. Free — the UI shows the locked state on
    write/apply actions, not on this list."""
    _guard()
    access.require(project, "Viewer")

    names = frappe.get_all(
        "BP Task Template", filters={"project": project},
        pluck="name", order_by="template_name asc",
    )
    return [_template_dict(frappe.get_doc("BP Task Template", n)) for n in names]


@frappe.whitelist()
def save_task_as_template(task, template_name):
    """Snapshot an existing task (+ its subtasks) into a reusable template."""
    _guard()
    task_doc = frappe.get_doc("BP Task", task)
    access.require(task_doc.project, "Manager")
    require_feature("templates")

    tpl = frappe.new_doc("BP Task Template")
    tpl.update({
        "template_name": template_name,
        "project": task_doc.project,
        "task_type": task_doc.task_type,
        "priority": task_doc.priority,
        "title_template": task_doc.title,
        "description": task_doc.description or "",
        "labels": task_doc.labels or "[]",
        "story_points": task_doc.story_points or 0,
    })

    subtasks = frappe.get_all(
        "BP Task", filters={"parent_task": task}, fields=["title", "task_type"],
        order_by="board_order asc, creation asc",
    )
    for st in subtasks:
        tpl.append("items", {"title": st["title"], "task_type": st["task_type"]})

    tpl.insert(ignore_permissions=True)
    frappe.db.commit()
    return _template_dict(tpl)


@frappe.whitelist()
def create_task_template(project, template_name, **fields):
    """Create a template from scratch (not derived from an existing task)."""
    _guard()
    access.require(project, "Manager")
    require_feature("templates")

    labels = fields.get("labels")
    if isinstance(labels, (list, dict)):
        labels = json.dumps(labels)

    tpl = frappe.new_doc("BP Task Template")
    tpl.update({
        "template_name": template_name,
        "project": project,
        "task_type": fields.get("task_type") or "Task",
        "priority": fields.get("priority") or "Medium",
        "title_template": fields.get("title_template") or "",
        "description": fields.get("description") or "",
        "labels": labels or "[]",
        "story_points": int(fields.get("story_points") or 0),
    })

    for item in _parse_json(fields.get("items"), []):
        if not item.get("title"):
            continue
        tpl.append("items", {
            "title": item["title"],
            "task_type": item.get("task_type") or "Task",
        })

    tpl.insert(ignore_permissions=True)
    frappe.db.commit()
    return _template_dict(tpl)


@frappe.whitelist()
def update_task_template(template, **fields):
    _guard()
    tpl = frappe.get_doc("BP Task Template", template)
    access.require(tpl.project, "Manager")
    require_feature("templates")

    if "template_name" in fields:
        tpl.template_name = fields["template_name"]
    if "task_type" in fields:
        tpl.task_type = fields["task_type"]
    if "priority" in fields:
        tpl.priority = fields["priority"]
    if "title_template" in fields:
        tpl.title_template = fields["title_template"]
    if "description" in fields:
        tpl.description = fields["description"]
    if "story_points" in fields:
        tpl.story_points = int(fields["story_points"] or 0)
    if "labels" in fields:
        labels = fields["labels"]
        tpl.labels = json.dumps(labels) if isinstance(labels, (list, dict)) else (labels or "[]")
    if "items" in fields:
        tpl.items = []
        for item in _parse_json(fields["items"], []):
            if not item.get("title"):
                continue
            tpl.append("items", {
                "title": item["title"],
                "task_type": item.get("task_type") or "Task",
            })

    tpl.save(ignore_permissions=True)
    frappe.db.commit()
    return _template_dict(tpl)


@frappe.whitelist()
def delete_task_template(template):
    _guard()
    tpl = frappe.get_doc("BP Task Template", template)
    access.require(tpl.project, "Manager")
    require_feature("templates")
    tpl.delete(ignore_permissions=True)
    frappe.db.commit()
    return {"ok": True}


@frappe.whitelist()
def create_task_from_template(template, overrides=None):
    """Stamp out a new task (+ its subtasks) from a template. Reuses
    board.create_task so status defaulting, task_key generation, activity
    logging and events.emit(TASK_CREATED) all happen exactly once, the
    standard way — never reimplement task creation here."""
    _guard()
    tpl = frappe.get_doc("BP Task Template", template)
    access.require(tpl.project, "Member")
    require_feature("templates")

    overrides = _parse_json(overrides, {})

    from batch_projects.api.board import create_task

    task = create_task(
        project=tpl.project,
        title=overrides.get("title") or tpl.title_template or tpl.template_name,
        status=overrides.get("status"),
        priority=overrides.get("priority") or tpl.priority,
        task_type=overrides.get("task_type") or tpl.task_type,
        assignees=overrides.get("assignees"),
        epic=overrides.get("epic"),
        description=overrides["description"] if "description" in overrides else tpl.description,
        story_points=overrides["story_points"] if "story_points" in overrides else tpl.story_points,
        due_date=overrides.get("due_date"),
        start_date=overrides.get("start_date"),
        labels=_parse_json(tpl.labels, []),
        sprint=overrides.get("sprint"),
    )

    for item in (tpl.items or []):
        create_task(
            project=tpl.project,
            title=item.title,
            task_type=item.task_type or "Task",
            parent_task=task["name"],
        )

    return task
