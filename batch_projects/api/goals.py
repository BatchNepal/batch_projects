"""Goals/OKRs — workspace-scoped cross-project alignment. Business tier+."""

import json
import frappe
from frappe import _

from batch_projects.entitlements import require_feature
from batch_projects.api.board import _require_system_user


def _guard():
    """Verify gateway signature — reject direct-to-Frappe calls."""
    from batch_projects.gateway_guard import verify_gateway_request
    verify_gateway_request()


def _require_gates():
    """Tier gate: goals are a Business-tier feature."""
    require_feature("goals")


def _assert_workspace_admin():
    """Goals are workspace-scoped; only workspace admins may create/delete them."""
    from batch_projects.access import is_workspace_admin
    if not is_workspace_admin():
        frappe.throw(_("You need workspace admin access for this."), frappe.PermissionError)


def _compute_progress(goal_name):
    """Derive progress live as the average of each linked epic's progress."""
    links = frappe.get_all("BP Goal Epic Link", filters={"parent": goal_name}, fields=["epic"])
    if not links:
        return 0.0
    total = 0.0
    count = 0
    for link in links:
        p = frappe.db.get_value("BP Epic", link["epic"], "progress") or 0
        total += float(p)
        count += 1
    return round(total / count, 1) if count > 0 else 0.0


@frappe.whitelist()
def list_goals():
    """List all goals with live-computed progress."""
    _guard()
    _require_gates()
    # _guard/_require_gates check the request came through the gateway and
    # the workspace's tier — neither checks WHO is calling. Without this,
    # any BP Guest/Website User could read every workspace goal.
    _require_system_user()
    goals = frappe.get_all("BP Goal",
        fields=["name", "title", "status", "color", "owner_field", "start_date", "end_date", "description"],
        order_by="creation desc")
    for g in goals:
        g["progress"] = _compute_progress(g["name"])
        g["linked_epics"] = [row["epic"] for row in
            frappe.get_all("BP Goal Epic Link", filters={"parent": g["name"]}, fields=["epic"])]
    return goals


@frappe.whitelist()
def get_goal(goal):
    """Get a single goal with live-computed progress."""
    _guard()
    _require_gates()
    _require_system_user()
    doc = frappe.get_doc("BP Goal", goal)
    return {
        "name": doc.name, "title": doc.title, "status": doc.status,
        "color": doc.color, "owner": doc.owner_field,
        "start_date": str(doc.start_date or ""), "end_date": str(doc.end_date or ""),
        "description": doc.description or "",
        "progress": _compute_progress(doc.name),
        "linked_epics": [row.epic for row in (doc.linked_epics or [])],
    }


@frappe.whitelist()
def create_goal(title, status=None, color=None, owner=None,
                start_date=None, end_date=None, description=None):
    _guard()
    _require_gates()
    _assert_workspace_admin()
    if not (title or "").strip():
        frappe.throw("Goal title is required.")
    doc = frappe.get_doc({
        "doctype": "BP Goal",
        "title": title.strip(),
        "status": status or "On Track",
        "color": color or "#6366f1",
        "owner_field": owner or None,
        "start_date": start_date or None,
        "end_date": end_date or None,
        "description": description or "",
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return {"name": doc.name, "title": doc.title, "status": doc.status,
            "color": doc.color, "progress": 0.0, "linked_epics": []}


@frappe.whitelist()
def update_goal(goal, fields):
    _guard()
    _require_gates()
    if isinstance(fields, str):
        fields = json.loads(fields)
    doc = frappe.get_doc("BP Goal", goal)
    _assert_workspace_admin()
    for k, v in fields.items():
        if k in ("name", "doctype", "cmd", "progress") or k.startswith("_"):
            continue
        if hasattr(doc, k):
            if v == "" and doc.meta.get_field(k) and \
               doc.meta.get_field(k).fieldtype in ("Date", "Datetime"):
                v = None
            setattr(doc, k, v)
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {"ok": True}


@frappe.whitelist()
def delete_goal(goal):
    _guard()
    _require_gates()
    _assert_workspace_admin()
    # Delete child epic links first
    for link in frappe.get_all("BP Goal Epic Link", filters={"parent": goal}, pluck="name"):
        frappe.delete_doc("BP Goal Epic Link", link, ignore_permissions=True)
    frappe.delete_doc("BP Goal", goal, ignore_permissions=True)
    frappe.db.commit()
    return {"ok": True}


@frappe.whitelist()
def link_epic_to_goal(goal, epic):
    """Add an epic to a goal's linked_epics table."""
    _guard()
    _require_gates()
    _assert_workspace_admin()
    doc = frappe.get_doc("BP Goal", goal)
    # Avoid duplicates
    existing = [r.epic for r in (doc.linked_epics or [])]
    if epic in existing:
        return {"ok": True, "message": "already linked"}
    doc.append("linked_epics", {"epic": epic})
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {"ok": True}


@frappe.whitelist()
def unlink_epic_from_goal(goal, epic):
    """Remove an epic from a goal's linked_epics table."""
    _guard()
    _require_gates()
    _assert_workspace_admin()
    doc = frappe.get_doc("BP Goal", goal)
    for row in list(doc.linked_epics or []):
        if row.epic == epic:
            frappe.delete_doc("BP Goal Epic Link", row.name, ignore_permissions=True)
    frappe.db.commit()
    return {"ok": True}
