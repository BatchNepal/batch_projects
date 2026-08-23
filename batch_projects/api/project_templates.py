"""
batch_projects/api/project_templates.py
─────────────────────────────────────────
user-defined project templates: "save as template" → "create from
template", on top of the hardcoded 11 built-ins in setup/project_templates.py.

Snapshot doctype, not a live copy-source project  — our
projects carry ERP wiring (erpnext_project, source_sales_order), members, and
counters that must NEVER leak into a template. `save_project_as_template`
copies exactly the JSON shape blobs BP Project already stores
(workflow_states/issue_types/labels/enabled_views) plus a curated task/
automation/custom-field snapshot — never client, company, erpnext_project,
source_sales_order, or members.

Dates are stored as offsets from the source project's start_date, recomputed against the new project's start_date at
create time — Odoo copies deadlines verbatim, we do better.

Same house pattern as api/task_templates.py: _guard(), require_feature
("templates") (the existing Team flag — no new one), JSON parsing, dict
serializers. Creation order (WORKPLAN 19A.3, fixed): project shell → owner_
project custom fields re-created (NEW ids) → global fields attached → tasks
inserted (dates = new start_date + offsets, parent_task set from an idx map
since a subtask's parent always precedes it in snapshot order) →
dependency wiring by idx map (a second pass — a dependency can point at a
LATER task, unlike parent/child) → automation rules cloned with project=new.
"""

import frappe
import json

from batch_projects import access
from batch_projects.entitlements import require_feature
from batch_projects.api import custom_fields as _cf


def _guard():
    from batch_projects.gateway_guard import verify_gateway_request

    verify_gateway_request()


def _require_system_user():
    from batch_projects.api.board import _require_system_user as _rsu

    _rsu()


def _parse_json(value, default):
    if not value:
        return default
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


def _template_dict(doc, usage_count=None) -> dict:
    tasks = _parse_json(doc.tasks_json, [])
    automations = _parse_json(doc.automations_json, [])
    cf = _parse_json(doc.custom_fields_json, {"global_ids": [], "owner_fields": []})
    return {
        "name": doc.name,
        "template_name": doc.template_name,
        "description": doc.description or "",
        "category": doc.category or "",
        "icon": doc.icon or "FilePlus",
        "color": doc.color or "#0B6BCB",
        "source_project": doc.source_project or None,
        "workflow_states": _parse_json(doc.workflow_states_json, []),
        "issue_types": _parse_json(doc.issue_types_json, []),
        "billing": _parse_json(doc.billing_json, {}),
        "task_count": len(tasks),
        "automation_count": len(automations),
        "custom_field_count": len(cf.get("global_ids", []))
        + len(cf.get("owner_fields", [])),
        "modified": doc.modified,
        "creation": doc.creation,
        "owner": doc.owner,
        "usage_count": usage_count if usage_count is not None else 0,
    }


def _require_save_permission(project):
    """Same bar as save_task_as_template: project Manager+ (an instance/
    workspace admin always passes via access.require's own is_instance_admin
    short-circuit)."""
    access.require(project, "Manager")


# ─── LIST / READ ─────────────────────────────────────────────────────────────


@frappe.whitelist()
def list_project_templates():
    """Every user template — workspace-wide, not project-scoped (mirrors the
    built-in 11's own workspace-wide visibility). Free to list, same posture
    as list_task_templates — the UI shows the locked state on write/create.
    usage_count is added via ONE batched query (BP Project.
    template_used carries "user:<template name>" — see
    create_project_from_template), not a query per template."""
    _require_system_user()
    names = frappe.get_all(
        "BP Project Template",
        pluck="name",
        order_by="template_name asc",
    )
    if not names:
        return []
    usage_rows = frappe.get_all(
        "BP Project",
        filters={"template_used": ["like", "user:%"]},
        fields=["template_used"],
    )
    usage_by_template = {}
    for r in usage_rows:
        tpl_name = (r["template_used"] or "").split("user:", 1)[-1]
        usage_by_template[tpl_name] = usage_by_template.get(tpl_name, 0) + 1
    return [
        _template_dict(
            frappe.get_doc("BP Project Template", n), usage_by_template.get(n, 0)
        )
        for n in names
    ]


@frappe.whitelist()
def get_project_template(template):
    """Full detail incl. the task tree readout, for the preview drawer."""
    _require_system_user()
    doc = frappe.get_doc("BP Project Template", template)
    out = _template_dict(doc)
    out["tasks"] = _parse_json(doc.tasks_json, [])
    out["automations"] = _parse_json(doc.automations_json, [])
    out["custom_fields"] = _parse_json(
        doc.custom_fields_json, {"global_ids": [], "owner_fields": []}
    )
    return out


# ─── SNAPSHOT (save as template) ─────────────────────────────────────────────


def _snapshot_custom_fields(project):
    """{global_ids: [{id, required}], owner_fields: [{old_id, ...full def}]}
    — global fields keep their id (shared, unchanged at create time); owner-
    project fields carry their full definition (they get a NEW id at create
    time, via old_id -> new_id remap)."""
    global_ids, owner_fields = [], []
    for link, cf in _cf._attached_fields(project, "all"):
        if cf.owner_project == project:
            owner_fields.append(
                {
                    "old_id": cf.name,
                    "field_label": cf.field_label,
                    "description": cf.description or "",
                    "field_type": cf.field_type,
                    "options": _parse_json(cf.options_json, []),
                    "applies_to": cf.applies_to or "Tasks",
                    "view_role": cf.view_role or "Viewer",
                    "edit_role": cf.edit_role or "Member",
                    "conditional_rules": _parse_json(cf.conditional_rules_json, []),
                    "show_in_list": bool(cf.show_in_list),
                    "required": bool(link.required),
                }
            )
        else:
            global_ids.append({"id": cf.name, "required": bool(link.required)})
    return {"global_ids": global_ids, "owner_fields": owner_fields}


def _snapshot_tasks(project, project_start_date):
    """Every task (root + subtasks), snapshot order = creation order — a
    subtask is only ever created after its parent exists, so parent_idx
    always points at an EARLIER array index. depends_on only carries the
    "is blocked by" direction (the dependency, not its mirrored "blocks"
    inverse) — re-establishing one direction via add_task_link re-creates
    both, same as the live app does."""
    from frappe.utils import getdate

    rows = frappe.get_all(
        "BP Task",
        filters={"project": project, "is_deleted": 0},
        fields=[
            "name",
            "title",
            "description",
            "task_type",
            "status",
            "priority",
            "story_points",
            "labels",
            "estimated_hours",
            "billable",
            "custom_field_values",
            "parent_task",
            "start_date",
            "due_date",
        ],
        order_by="creation asc",
    )
    idx_of = {r.name: i for i, r in enumerate(rows)}
    start = getdate(project_start_date) if project_start_date else None

    links = (
        frappe.get_all(
            "BP Task Link",
            filters={
                "parent": ["in", [r.name for r in rows]],
                "link_type": "is blocked by",
            },
            fields=["parent", "linked_task", "dep_type", "lag_days"],
        )
        if rows
        else []
    )
    deps_by_task = {}
    for l in links:
        if l.linked_task in idx_of:
            deps_by_task.setdefault(l.parent, []).append(
                {
                    "idx": idx_of[l.linked_task],
                    "dep_type": l.dep_type or "FS",
                    "lag_days": l.lag_days or 0,
                }
            )

    def _offset(d):
        if not (start and d):
            return None
        return (getdate(d) - start).days

    tasks = []
    for r in rows:
        tasks.append(
            {
                "title": r.title,
                "description": r.description or "",
                "task_type": r.task_type or "Task",
                "status": r.status,
                "priority": r.priority or "Medium",
                "story_points": r.story_points or 0,
                "labels": _parse_json(r.labels, []),
                "estimated_hours": r.estimated_hours or 0,
                "billable": bool(r.billable),
                "custom_field_values": _parse_json(r.custom_field_values, {}),
                "parent_idx": idx_of.get(r.parent_task) if r.parent_task else None,
                "depends_on": deps_by_task.get(r.name, []),
                "start_offset_days": _offset(r.start_date),
                "due_offset_days": _offset(r.due_date),
            }
        )
    return tasks


@frappe.whitelist()
def save_project_as_template(
    project,
    template_name,
    description="",
    category="",
    icon=None,
    color=None,
    include_tasks=1,
    include_automations=1,
    include_custom_fields=1,
):
    _guard()
    _require_save_permission(project)
    require_feature("templates")

    if not template_name or not template_name.strip():
        frappe.throw("Template name is required.")

    proj = frappe.get_doc("BP Project", project)

    # Templates are workspace-wide visible to every
    # System User (list_project_templates/get_project_template, by design —
    # that's the whole point of a shared template library), but this
    # snapshot copies the source project's REAL task titles/descriptions/
    # custom field values. Saving a private/team-restricted project as a
    # template would leak its actual content past the visibility boundary
    # the project was deliberately given. Block it rather than half-build a
    # separate "private template" concept nobody asked for.
    if (proj.visibility or "workspace") in ("private", "team"):
        frappe.throw(
            "This project is set to private/team visibility. Templates are "
            "visible workspace-wide, so saving it as one would expose its "
            "real task content beyond that. Change the project's visibility "
            "first if you want to share it as a template."
        )

    tpl = frappe.new_doc("BP Project Template")
    tpl.template_name = template_name.strip()
    tpl.description = description or ""
    tpl.category = category or ""
    tpl.icon = icon or proj.project_icon or "FilePlus"
    tpl.color = color or proj.project_color or "#0B6BCB"
    tpl.source_project = project
    # Passthrough copy — these are already JSON text on BP Project (see
    # bp_project.py get_workflow_states/get_issue_types), never client/
    # company/erpnext_project/source_sales_order/members.
    tpl.workflow_states_json = proj.workflow_states or "[]"
    tpl.issue_types_json = proj.issue_types or "[]"
    tpl.labels_json = proj.labels or "[]"
    tpl.enabled_views_json = proj.enabled_views or "[]"
    tpl.default_view = proj.default_view or "summary"
    tpl.billing_json = json.dumps(
        {
            "project_type": proj.project_type or "internal",
            "hourly_rate": float(proj.hourly_rate or 0),
            "retainer_hours": int(proj.retainer_hours or 0),
            # Defaults only — create_project_from_template lets the wizard
            # override every one of these (a fixed-price template without a
            # budget default would otherwise hard-fail create_project's
            # "Total budget is required" validation).
            "budget_amount": float(proj.budget_amount or 0),
            "currency": proj.currency or "",
        }
    )

    tpl.custom_fields_json = json.dumps(
        _snapshot_custom_fields(project)
        if int(include_custom_fields or 0)
        else {"global_ids": [], "owner_fields": []}
    )

    automations = []
    if int(include_automations or 0):
        # Project-scope only — a workspace-scope rule attached to this
        # project via project_filter isn't "this project's own" automation
        # and must never leak into a template as if it were.
        automations = frappe.get_all(
            "BP Automation Rule",
            filters={"scope": "project", "project": project},
            fields=[
                "rule_name",
                "trigger_event",
                "trigger_config",
                "conditions",
                "actions",
                "action_type",
                "action_config",
                "is_active",
            ],
        )
        for a in automations:
            a["actions"] = _parse_json(a.get("actions"), []) or (
                [
                    {
                        "type": a.get("action_type"),
                        "config": _parse_json(a.get("action_config"), {}),
                    }
                ]
                if a.get("action_type")
                else []
            )
            a["trigger_config"] = _parse_json(a.get("trigger_config"), {})
            a["conditions"] = _parse_json(a.get("conditions"), [])
            a.pop("action_type", None)
            a.pop("action_config", None)
        # A rule that ended up with zero actions (half-authored, or a legacy
        # row that never migrated) has nothing to clone — snapshotting it
        # would only create junk no-op rules at create time.
        automations = [a for a in automations if a["actions"]]
    tpl.automations_json = json.dumps(automations)

    tasks = _snapshot_tasks(project, proj.start_date) if int(include_tasks or 0) else []
    tpl.tasks_json = json.dumps(tasks)

    tpl.insert(ignore_permissions=True)
    frappe.db.commit()
    return _template_dict(tpl)


@frappe.whitelist()
def update_project_template(
    template, template_name=None, description=None, category=None, icon=None, color=None
):
    """Rename/describe only — snapshots are immutable. Refresh = re-save
    from the source project (a new template), not an edit of this one."""
    _guard()
    require_feature("templates")
    doc = frappe.get_doc("BP Project Template", template)
    if doc.source_project:
        _require_save_permission(doc.source_project)
    elif not access.is_workspace_admin():
        frappe.throw(
            "You need workspace admin access for this.", frappe.PermissionError
        )

    if template_name is not None:
        doc.template_name = template_name.strip()
    if description is not None:
        doc.description = description
    if category is not None:
        doc.category = category
    if icon is not None:
        doc.icon = icon
    if color is not None:
        doc.color = color
    doc.flags.ignore_permissions = True
    doc.save()
    frappe.db.commit()
    return _template_dict(doc)


@frappe.whitelist()
def delete_project_template(template):
    _guard()
    require_feature("templates")
    doc = frappe.get_doc("BP Project Template", template)
    if doc.source_project:
        _require_save_permission(doc.source_project)
    elif not access.is_workspace_admin():
        frappe.throw(
            "You need workspace admin access for this.", frappe.PermissionError
        )
    frappe.delete_doc("BP Project Template", template, ignore_permissions=True)
    frappe.db.commit()
    return {"ok": True}


# ─── CREATE FROM TEMPLATE ─────────────────────────────────────────────────────


@frappe.whitelist()
def create_project_from_template(
    template,
    project_name,
    key,
    start_date=None,
    client=None,
    budget_amount=None,
    hourly_rate=None,
    retainer_hours=None,
    currency=None,
):
    # Same bar as create_project itself (any real system user, no special
    # role — the new project doesn't exist yet, so there's no project-role
    # to check against) — the workspace-admin-or-project-admin gate applies
    # to the template CRUD above, not to consuming a template.
    _require_system_user()
    require_feature("templates")

    from batch_projects.api.board import (
        create_project,
        create_task,
        create_automation_rule,
        add_task_link,
    )
    from frappe.utils import add_days, getdate

    tpl = frappe.get_doc("BP Project Template", template)
    billing = _parse_json(tpl.billing_json, {})
    ptype = billing.get("project_type") or "internal"

    # Wizard-supplied billing wins over the template's snapshot defaults —
    # the numbers change per engagement, the shape doesn't. Fail the
    # unfixable combination HERE, before any document exists (create_project
    # would throw the same thing, but a clear message beats a generic one
    # and nothing has been committed yet either way).
    budget = (
        budget_amount
        if budget_amount not in (None, "", 0, "0")
        else billing.get("budget_amount")
    )
    if ptype == "fixed" and not budget:
        frappe.throw(
            "This template creates a fixed-price project — a total budget is required."
        )
    if ptype != "internal" and not client:
        frappe.throw("This template creates a billable project — pick a client first.")

    created = create_project(
        project_name=project_name,
        key=key,
        project_type=ptype,
        client=client or None,  # only ever from the explicit param — never the template
        budget_amount=budget or None,
        hourly_rate=hourly_rate or billing.get("hourly_rate") or None,
        retainer_hours=retainer_hours or billing.get("retainer_hours") or None,
        currency=currency or billing.get("currency") or None,
        start_date=start_date,
        workflow_states=tpl.workflow_states_json,
        issue_types=tpl.issue_types_json,
        enabled_views=tpl.enabled_views_json,
        template_used=f"user:{tpl.name}",
        project_color=tpl.color,
        project_icon=tpl.icon,
    )
    new_project = created["name"]

    # labels + default_view aren't create_project params.
    updates = {}
    if tpl.labels_json:
        updates["labels"] = tpl.labels_json
    if tpl.default_view:
        updates["default_view"] = tpl.default_view
    if updates:
        frappe.db.set_value("BP Project", new_project, updates)

    # ── Custom fields — owner fields FIRST (new ids), then global attach ────
    cf_snapshot = _parse_json(
        tpl.custom_fields_json, {"global_ids": [], "owner_fields": []}
    )
    old_to_new_field_id = {}
    carried_field_ids = set()

    for of in cf_snapshot.get("owner_fields", []):
        new_field = _cf.create_field(
            field_label=of["field_label"],
            field_type=of["field_type"],
            description=of.get("description", ""),
            options=of.get("options", []),
            applies_to=of.get("applies_to", "Tasks"),
            view_role=of.get("view_role", "Viewer"),
            edit_role=of.get("edit_role", "Member"),
            conditional_rules=of.get("conditional_rules", []),
            show_in_list=1 if of.get("show_in_list") else 0,
            owner_project=new_project,
        )
        old_to_new_field_id[of["old_id"]] = new_field["name"]
        carried_field_ids.add(new_field["name"])
        # create_field auto-attaches owner fields but has no `required`
        # param — restore the snapshot's required flag on the link row.
        if of.get("required"):
            frappe.db.set_value(
                "BP Custom Field Project",
                {"parent": new_project, "custom_field": new_field["name"]},
                "required",
                1,
            )

    for gf in cf_snapshot.get("global_ids", []):
        if frappe.db.exists("BP Custom Field", gf["id"]):
            _cf.attach_field_to_project(
                new_project, gf["id"], required=1 if gf.get("required") else 0
            )
            carried_field_ids.add(gf["id"])

    # ── Tasks — single pass (parent_idx always precedes current index) ──────
    tasks = _parse_json(tpl.tasks_json, [])
    idx_to_name = {}
    new_start = getdate(start_date) if start_date else None

    for i, t in enumerate(tasks):
        task_start = (
            add_days(new_start, t["start_offset_days"])
            if (new_start and t.get("start_offset_days") is not None)
            else None
        )
        task_due = (
            add_days(new_start, t["due_offset_days"])
            if (new_start and t.get("due_offset_days") is not None)
            else None
        )

        remapped_cfv = {}
        for old_id, val in (t.get("custom_field_values") or {}).items():
            new_id = old_to_new_field_id.get(
                old_id, old_id if old_id in carried_field_ids else None
            )
            if new_id:
                remapped_cfv[new_id] = val

        parent_idx = t.get("parent_idx")
        parent_name = idx_to_name.get(parent_idx) if parent_idx is not None else None

        # No assignees — members never cross into a template (WORKPLAN 19A.2).
        # status is always valid here: the new project's workflow states are a
        # verbatim copy of the ones the snapshot was taken against.
        new_task = create_task(
            project=new_project,
            title=t["title"],
            description=t.get("description", ""),
            status=t.get("status") or None,
            task_type=t.get("task_type", "Task"),
            priority=t.get("priority", "Medium"),
            story_points=t.get("story_points", 0),
            labels=t.get("labels", []),
            estimated_hours=t.get("estimated_hours", 0),
            billable=1 if t.get("billable") else 0,
            start_date=task_start,
            due_date=task_due,
            parent_task=parent_name,
            custom_field_values=remapped_cfv or None,
        )
        idx_to_name[i] = new_task["name"]

    # ── Dependencies — second pass (can point at a LATER index) ─────────────
    for i, t in enumerate(tasks):
        for dep in t.get("depends_on") or []:
            if dep["idx"] in idx_to_name and i in idx_to_name:
                add_task_link(
                    idx_to_name[i],
                    idx_to_name[dep["idx"]],
                    "is blocked by",
                    dep.get("dep_type", "FS"),
                    dep.get("lag_days", 0),
                )

    # ── Automation rules ──────────────────────────────────────────────────
    # Snapshotted rules are always project-scope (see save_project_as_template)
    # — a template never carries a workspace-scope rule that merely happened
    # to apply to the source project via project_filter.
    for r in _parse_json(tpl.automations_json, []):
        actions = r.get("actions") or (
            [{"type": r["action_type"], "config": r.get("action_config") or {}}]
            if r.get("action_type")
            else []
        )
        if not actions:
            continue
        # Per-rule isolation: one rule failing validation on THIS site (e.g.
        # an "Update ERPNext Document" action on a site whose engine isn't
        # the gateway) must not abort a creation that has already committed
        # the project, fields, and tasks — log it and keep going.
        try:
            create_automation_rule(
                rule_name=r["rule_name"],
                trigger_event=r["trigger_event"],
                actions=actions,
                scope="project",
                project=new_project,
                conditions=r.get("conditions"),
                trigger_config=r.get("trigger_config"),
                is_active=1 if r.get("is_active") else 0,
            )
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"template automation clone failed: {tpl.name} → {new_project} ({r.get('rule_name')})",
            )

    frappe.db.commit()
    return created
