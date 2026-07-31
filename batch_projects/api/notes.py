"""
batch_projects/api/notes.py
─────────────────────────────
BP Note — project-level, team-visible notes. A shared surface so
teams stop burying decisions inside random task descriptions. Content is the
same rich-text editor task descriptions already use (RichTextEditor.vue on
the frontend, a Text Editor field here).

Gating is two independent layers, exactly mirroring how Gantt works:
  - the workspace feature flag "notes" (BP Workspace Settings admin kill
    switch) — checked here, backend-enforced on every call.
  - per-project `enabled_views` membership — frontend tab visibility only;
    Gantt doesn't backend-enforce that either, so neither do we here.

Permission is project-role based, delegating entirely to access.py (read
only — this module never writes to it):
  read = Viewer+, create = Member+, edit/delete = author or Manager+.
"""

import frappe

from batch_projects import access
from batch_projects.entitlements import require_workspace_feature


def _guard():
    from batch_projects.gateway_guard import verify_gateway_request
    verify_gateway_request()


def _note_dict(doc) -> dict:
    return {
        "name": doc.name,
        "project": doc.project,
        "title": doc.title or "",
        "content": doc.content or "",
        "pinned": bool(doc.pinned),
        "owner": doc.owner,
        "owner_name": frappe.db.get_value("User", doc.owner, "full_name") or doc.owner,
        "modified": doc.modified,
        "creation": doc.creation,
    }


@frappe.whitelist()
def list_notes(project):
    _guard()
    access.require(project, "Viewer")
    require_workspace_feature("notes")

    names = frappe.get_all(
        "BP Note", filters={"project": project}, pluck="name",
        order_by="pinned desc, modified desc",
    )
    return [_note_dict(frappe.get_doc("BP Note", n)) for n in names]


@frappe.whitelist()
def create_note(project, title="", content="", pinned=0):
    _guard()
    access.require(project, "Member")
    require_workspace_feature("notes")

    doc = frappe.get_doc({
        "doctype": "BP Note",
        "project": project,
        "title": title or "Untitled note",
        "content": content or "",
        "pinned": 1 if int(pinned or 0) else 0,
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return _note_dict(doc)


def _load_and_authorize(name):
    """Base access is Viewer+ (covers a since-revoked author); editing beyond
    your own note additionally requires Manager+ — same shape as board.py's
    edit_comment/delete_comment (author OR manager, never a parallel check)."""
    doc = frappe.get_doc("BP Note", name)
    access.require(doc.project, "Viewer")
    if doc.owner != frappe.session.user:
        access.require(doc.project, "Manager")
    return doc


@frappe.whitelist()
def update_note(name, title=None, content=None, pinned=None):
    _guard()
    require_workspace_feature("notes")
    doc = _load_and_authorize(name)

    if title is not None:
        doc.title = title
    if content is not None:
        doc.content = content
    if pinned is not None:
        doc.pinned = 1 if int(pinned) else 0

    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return _note_dict(doc)


@frappe.whitelist()
def delete_note(name):
    _guard()
    require_workspace_feature("notes")
    doc = _load_and_authorize(name)

    frappe.delete_doc("BP Note", name, ignore_permissions=True, force=True)
    frappe.db.commit()
    return {"ok": True}
