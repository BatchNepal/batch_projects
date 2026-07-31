"""
batch_projects/api/drawings.py
─────────────────────────────────
BP Drawing — project-level Excalidraw whiteboards. Multiple
drawings per project: a light list, then a full scene per drawing.

Gating is TWO independent layers (both must pass, same contract Notes/Gantt
use): the workspace feature flag "draw" (admin kill switch) AND the
Team+ tier gate (this is a paid surface, unlike Notes). Permission is
project-role based, delegating entirely to access.py (read-only import,
never modified here):
  read = Viewer+, create/save = Member+, delete = Manager+ (delete is the one
  destructive action here, so it gets access.py's own "delete" ptype floor —
  see access.py's _PTYPE_MIN_ROLE — rather than a bespoke rule).

No per-drawing authorship gate — a whiteboard is a shared, continuously-edited
surface, not an authored note; anyone who can write can edit anyone's scene.

Conflict policy: last-write-wins + a stale-load warning. The caller sends the
`modified` timestamp it loaded the doc with; if the doc has moved on since,
the save still goes through (never blocks a save) but the response carries
`stale: true` so the frontend can tell the user someone else's change was
just overwritten.
"""

import frappe

from batch_projects import access
from batch_projects.entitlements import require_workspace_feature, require_feature


def _guard():
    from batch_projects.gateway_guard import verify_gateway_request
    verify_gateway_request()


def _require_gates():
    require_workspace_feature("draw")
    require_feature("draw")


def _drawing_list_dict(doc) -> dict:
    return {
        "name": doc.name,
        "project": doc.project,
        "title": doc.title or "",
        "owner": doc.owner,
        "owner_name": frappe.db.get_value("User", doc.owner, "full_name") or doc.owner,
        "modified": doc.modified,
        "creation": doc.creation,
    }


def _drawing_full_dict(doc) -> dict:
    d = _drawing_list_dict(doc)
    d["scene_json"] = doc.scene_json or ""
    return d


@frappe.whitelist()
def list_drawings(project):
    _guard()
    access.require(project, "Viewer")
    _require_gates()

    names = frappe.get_all(
        "BP Drawing", filters={"project": project}, pluck="name",
        order_by="modified desc",
    )
    return [_drawing_list_dict(frappe.get_doc("BP Drawing", n)) for n in names]


@frappe.whitelist()
def get_drawing(name):
    _guard()
    doc = frappe.get_doc("BP Drawing", name)
    access.require(doc.project, "Viewer")
    _require_gates()
    return _drawing_full_dict(doc)


@frappe.whitelist()
def create_drawing(project, title=""):
    _guard()
    access.require(project, "Member")
    _require_gates()

    doc = frappe.get_doc({
        "doctype": "BP Drawing",
        "project": project,
        "title": title or "Untitled drawing",
        "scene_json": "",
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return _drawing_full_dict(doc)


@frappe.whitelist()
def save_drawing(name, scene_json=None, title=None, base_modified=None):
    """Autosave target. Never blocks on a stale base_modified (last-write-wins)
    — it just reports back whether this save clobbered a newer change."""
    _guard()
    doc = frappe.get_doc("BP Drawing", name)
    access.require(doc.project, "Member")
    _require_gates()

    stale = bool(base_modified) and str(doc.modified) != str(base_modified)

    if scene_json is not None:
        doc.scene_json = scene_json
    if title is not None:
        doc.title = title or "Untitled drawing"

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    result = _drawing_full_dict(doc)
    result["stale"] = stale
    return result


@frappe.whitelist()
def delete_drawing(name):
    _guard()
    doc = frappe.get_doc("BP Drawing", name)
    access.require(doc.project, "Manager")
    _require_gates()

    frappe.delete_doc("BP Drawing", name, ignore_permissions=True, force=True)
    frappe.db.commit()
    return {"ok": True}
