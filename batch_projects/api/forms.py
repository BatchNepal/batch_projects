"""
batch_projects/api/forms.py
─────────────────────────────
Intake/request forms — public form rendering and submission.

  • Forms are managed by project admins (BP Manager+) in project settings.
  • Each form has a unique name and belongs to a project.
  • Fields are defined in JSON (type, label, required, options).
  • Public submission endpoint creates a task in the project.
  • Rate-limited same as guest comments.
"""

import json
import frappe
from frappe import _

from batch_projects.api.board import _check_permission
from batch_projects.api.sharing import _throttle_guest_comment
from batch_projects.entitlements import require_feature


# ─── Management endpoints (authenticated) ─────────────────────────────────────

@frappe.whitelist()
def list_intake_forms(project):
    """List active intake forms for a project."""
    _check_permission(project, "BP Viewer")
    require_feature("intake_forms")
    return frappe.get_all("BP Intake Form",
        filters={"project": project},
        fields=["name", "form_title", "is_active", "task_type", "default_status"],
        order_by="creation desc")


@frappe.whitelist()
def get_intake_form_detail(form):
    """Get full form definition with fields."""
    doc = frappe.get_doc("BP Intake Form", form)
    _check_permission(doc.project, "BP Viewer")
    require_feature("intake_forms")
    fields = _parse_fields(doc.fields_json)
    return {
        "name": doc.name,
        "form_title": doc.form_title,
        "project": doc.project,
        "is_active": doc.is_active,
        "fields": fields,
        "task_type": doc.task_type,
        "default_status": doc.default_status,
    }


@frappe.whitelist()
def create_intake_form(project, form_title, fields_json=None,
                        task_type=None, default_status=None):
    """Create a new intake form."""
    _check_permission(project, "BP Manager")
    require_feature("intake_forms")
    doc = frappe.get_doc({
        "doctype": "BP Intake Form",
        "project": project,
        "form_title": form_title,
        "fields_json": fields_json or "[]",
        "task_type": task_type or "Task",
        "default_status": default_status or "",
        "is_active": 1,
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return {"name": doc.name, "form_title": doc.form_title}


@frappe.whitelist()
def update_intake_form(form, fields):
    """Update an intake form's fields/title/etc."""
    if isinstance(fields, str):
        fields = json.loads(fields)
    doc = frappe.get_doc("BP Intake Form", form)
    _check_permission(doc.project, "BP Manager")
    require_feature("intake_forms")
    for k, v in fields.items():
        if k in ("name", "doctype", "cmd") or k.startswith("_"):
            continue
        setattr(doc, k, v)
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {"ok": True}


@frappe.whitelist()
def delete_intake_form(form):
    """Delete an intake form."""
    doc = frappe.get_doc("BP Intake Form", form)
    _check_permission(doc.project, "BP Admin")
    require_feature("intake_forms")
    frappe.delete_doc("BP Intake Form", form, ignore_permissions=True)
    frappe.db.commit()
    return {"ok": True}


# ─── Public endpoint (allow_guest — form is accessed by token) ────────────────

@frappe.whitelist(allow_guest=True)
def get_public_form(form):
    """Return form definition for public rendering. No auth needed.

    `project` is intentionally still returned:
    BP Project autonames on `field:project_name` (see bp_project.json), so
    this is the project's human display name, not an internal id — the SPA
    (IntakeForm.vue) renders it as the form's subtitle. The actual
    vulnerability this endpoint had was the guessable /intake/<name> URL
    (BP Intake Form used to autoname on form_title); that's fixed at the
    doctype level (now `hash`) plus the rename_intake_forms_to_random
    patch for pre-existing records. Once the token itself is unguessable,
    disclosing the project name to whoever holds it is the same accepted
    pattern BP Share Link already uses for its own token holders."""
    if not frappe.db.exists("BP Intake Form", form):
        frappe.throw(_("Form not found."), frappe.DoesNotExistError)
    doc = frappe.get_doc("BP Intake Form", form)
    if not doc.is_active:
        frappe.throw(_("This form is no longer active."), frappe.PermissionError)
    fields = _parse_fields(doc.fields_json)
    return {
        "name": doc.name,
        "form_title": doc.form_title,
        "project": doc.project,
        "fields": fields,
    }


@frappe.whitelist(allow_guest=True)
def submit_intake_form(form, values=None):
    """Submit an intake form — creates a task in the project. Public endpoint."""
    if isinstance(values, str):
        values = json.loads(values)
    if not isinstance(values, dict):
        frappe.throw(_("Values must be a dict."))

    if not frappe.db.exists("BP Intake Form", form):
        frappe.throw(_("Form not found."), frappe.DoesNotExistError)
    doc = frappe.get_doc("BP Intake Form", form)
    if not doc.is_active:
        frappe.throw(_("This form is no longer active."), frappe.PermissionError)

    # Throttle
    _throttle_guest_comment(f"intake:{form}")

    fields = _parse_fields(doc.fields_json)

    # Build task title from first required text field, or form title
    title = None
    description_parts = []
    for fdef in fields:
        val = values.get(fdef.get("label"), "")
        if fdef.get("required") and not val:
            frappe.throw(_("{0} is required.").format(fdef["label"]))
        if title is None and val and fdef.get("type") in ("text", "textarea"):
            title = str(val)[:140]
        if val:
            description_parts.append(f"**{fdef['label']}**: {val}")

    if not title:
        title = doc.form_title

    description = "\n\n".join(description_parts)
    if description:
        description = f"**Submitted via intake form: {doc.form_title}**\n\n{description}"

    task = frappe.get_doc({
        "doctype": "BP Task",
        "project": doc.project,
        "title": title,
        "task_type": doc.task_type or "Task",
        "status": doc.default_status or None,
        "description": description,
        "submitted_via_intake": doc.name,
    })
    task.insert(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": True, "task": task.name, "task_key": task.task_key}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _parse_fields(raw):
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
