"""
batch_projects/api/custom_fields.py
──────────────────────────────────────
Custom Fields v2 — a workspace-level field library (BP Custom Field), reused
across projects via a join table (BP Custom Field Project on
BP Project.custom_field_links), instead of the old per-project-embedded JSON
schema (BP Project.custom_fields — left in place, deprecated, unused after
the migrate_custom_fields_to_library patch runs).

Three permission tiers, all delegating to access.py (read-only import, never
modified here) — nothing new invented:
  1. Field DEFINITION CRUD (name/type/options/conditional rules/view+edit
     roles) — access.is_workspace_admin(). Shared/global: changing one
     affects every project using it, so authorship stays narrow.
  2. Attach/detach a field to a project, set its per-project `required` —
     access.require(project, "Admin"). Same bar update_project_custom_fields
     used under the old model.
  3. Field VALUE view/edit on a specific project — access.has_at_least
     (project, field.view_role / field.edit_role). Enforced here (schema
     delivery strips fields below view_role) and in board.py (value
     read/write on tasks and projects) — "strip on read, reject on write,"
     the same contract require_workspace_feature and the view_money/
     view_files capabilities use.
"""

import frappe
import json

from batch_projects import access

_FIELD_TYPES = {
    "text", "textarea", "number", "date", "checkbox", "select", "multiselect",
    "currency", "percent", "rating", "email", "phone", "url", "user", "link",
}

# Doctypes a "link"-type field may point at — the same curated set
# board.search_erp_documents exposes (plus Item/Employee, natural link
# targets), NOT any doctype that exists. This is the enforcement boundary
# that lets search_field_link_options use permission-blind frappe.get_all
# below: SPA users hold zero ERPNext doctype perms by design (8B), so a
# permission-aware frappe.get_list here returns [] for every real user and
# the field type is dead on arrival. The BP project-role gate + this
# allowlist IS the authorization, same doctrine as the Money drawer.
_LINK_DOCTYPES = {
    "Sales Order", "Purchase Order", "Sales Invoice", "Purchase Invoice",
    "Project", "Customer", "Supplier", "Lead", "Opportunity",
    "Expense Claim", "Timesheet", "Delivery Note", "Stock Entry",
    "Payment Entry", "Journal Entry", "Work Order", "Quotation",
    "Item", "Employee",
}
_NUMERIC_TYPES = {"number", "currency", "percent", "rating"}
_ROLES = {"Admin", "Manager", "Member", "Viewer"}
_APPLIES_TO = {"Tasks", "Projects", "Both"}


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


def _library_dict(doc) -> dict:
    assigned = frappe.db.count("BP Custom Field Project", {"custom_field": doc.name})
    return {
        "name": doc.name,
        "field_label": doc.field_label,
        "description": doc.description or "",
        "field_type": doc.field_type,
        "options": _parse_json(doc.options_json, []),
        "applies_to": doc.applies_to or "Tasks",
        "view_role": doc.view_role or "Viewer",
        "edit_role": doc.edit_role or "Member",
        "conditional_rules": _parse_json(doc.conditional_rules_json, []),
        "show_in_list": bool(doc.show_in_list),
        "enabled": bool(doc.enabled),
        "assigned_projects": assigned,
        "owner": doc.owner,
        "owner_name": frappe.db.get_value("User", doc.owner, "full_name") or doc.owner,
        "modified": doc.modified,
        "creation": doc.creation,
    }


def _require_library_admin():
    if not access.is_workspace_admin():
        frappe.throw(
            "You need workspace admin access to manage the custom field library.",
            frappe.PermissionError,
        )


def _require_field_admin(owner_project):
    """The CRUD gate for a field definition: workspace admin for a shared
    library field (owner_project unset), or that specific project's Admin
    for a project-owned field. `owner_project` is immutable after create —
    this function is the only place that ever decides which gate applies,
    never a value the caller passes in for update/delete."""
    if owner_project:
        access.require(owner_project, "Admin")
    else:
        _require_library_admin()


def _validate_field_payload(field_type, applies_to, view_role, edit_role, conditional_rules, options=None):
    if field_type not in _FIELD_TYPES:
        frappe.throw(f"Unknown field type '{field_type}'.")
    if applies_to not in _APPLIES_TO:
        frappe.throw(f"Invalid applies_to '{applies_to}'.")
    if view_role not in _ROLES or edit_role not in _ROLES:
        frappe.throw("Invalid role.")
    if conditional_rules and field_type not in _NUMERIC_TYPES:
        frappe.throw("Conditional markers only apply to number/currency/percent/rating fields.")
    if field_type == "link":
        link_doctype = (options or {}).get("link_doctype") if isinstance(options, dict) else None
        if not link_doctype:
            frappe.throw("Choose which ERPNext document type this field links to.")
        if link_doctype not in _LINK_DOCTYPES:
            frappe.throw(
                f"'{link_doctype}' is not a supported link target. "
                f"Supported: {', '.join(sorted(_LINK_DOCTYPES))}."
            )
        if not frappe.db.exists("DocType", link_doctype):
            frappe.throw(f"'{link_doctype}' is not a known ERPNext document type.")


def _assert_type_change_safe(field_id):
    """Same philosophy as the old per-project type-change guard
    (update_project_custom_fields): hard block, don't auto-migrate. Checked
    across every project this field is attached to, since the field is now
    shared — a heuristic LIKE match against custom_field_values, same as
    the guard it replaces."""
    projects = frappe.get_all(
        "BP Custom Field Project", filters={"custom_field": field_id}, pluck="parent"
    )
    if not projects:
        return
    count = frappe.db.sql(
        """SELECT COUNT(*) FROM `tabBP Task`
           WHERE project IN %(projects)s AND custom_field_values LIKE %(pat)s""",
        {"projects": projects, "pat": f"%{field_id}%"},
    )[0][0]
    if count:
        frappe.throw(
            f"Cannot change this field's type — {count} task(s) across "
            f"{len(projects)} project(s) have values for it."
        )


# ─── LIBRARY (workspace admin) ─────────────────────────────────────────────

@frappe.whitelist()
def list_library_fields():
    """The workspace-wide grid — shared fields only. Project-owned fields
    are private by construction: they never appear here, only in their
    owning project's own Fields tab (get_project_fields)."""
    _guard()
    _require_library_admin()

    names = frappe.get_all(
        "BP Custom Field", filters={"owner_project": ["is", "not set"]},
        pluck="name", order_by="field_label asc",
    )
    return [_library_dict(frappe.get_doc("BP Custom Field", n)) for n in names]


@frappe.whitelist()
def list_attachable_fields():
    """Minimal enabled-field list for the attach-to-project picker — any
    System User, not workspace-admin-only like list_library_fields(). Field
    names/types aren't sensitive; only definition CRUD and the full
    view_role/edit_role/marker detail are admin-gated. Excludes
    project-owned fields — those are private to their own project and are
    never offered for attaching onto a *different* one."""
    _guard()
    if frappe.db.get_value("User", frappe.session.user, "user_type") != "System User":
        frappe.throw("Access denied.", frappe.PermissionError)

    rows = frappe.get_all(
        "BP Custom Field", filters={"enabled": 1, "owner_project": ["is", "not set"]},
        fields=["name", "field_label", "field_type", "applies_to"],
        order_by="field_label asc",
    )
    return rows


@frappe.whitelist()
def create_field(field_label, field_type, description="", options=None,
                  applies_to="Tasks", view_role="Viewer", edit_role="Member",
                  conditional_rules=None, show_in_list=0, owner_project=None):
    _guard()
    _require_field_admin(owner_project)

    options = _parse_json(options, [])
    conditional_rules = _parse_json(conditional_rules, [])
    _validate_field_payload(field_type, applies_to, view_role, edit_role, conditional_rules, options)

    doc = frappe.get_doc({
        "doctype": "BP Custom Field",
        "field_label": field_label,
        "description": description or "",
        "field_type": field_type,
        "options_json": json.dumps(options),
        "applies_to": applies_to,
        "owner_project": owner_project or None,
        "view_role": view_role,
        "edit_role": edit_role,
        "conditional_rules_json": json.dumps(conditional_rules),
        "show_in_list": 1 if int(show_in_list or 0) else 0,
        "enabled": 1,
    })
    doc.insert(ignore_permissions=True)

    if owner_project:
        # Project-owned fields auto-attach to their own project atomically —
        # every value/permission/marker code path (_attached_fields and
        # everything built on it) already operates on BP Custom Field Project
        # join rows and doesn't care who owns the definition, so this is the
        # only special-case needed to make a private field behave identically
        # to an attached shared one everywhere else.
        proj = frappe.get_doc("BP Project", owner_project)
        proj.append("custom_field_links", {"custom_field": doc.name, "required": 0})
        proj.flags.ignore_permissions = True
        proj.save()

    frappe.db.commit()
    return _library_dict(doc)


@frappe.whitelist()
def update_field(name, field_label=None, description=None, field_type=None, options=None,
                  applies_to=None, view_role=None, edit_role=None,
                  conditional_rules=None, show_in_list=None, enabled=None):
    # NOTE: intentionally no `owner_project` param. owner_project is set once
    # at create_field time and is immutable — accepting it here would let a
    # project Admin re-home a field they own onto a project they don't
    # administer, or silently privatize a shared field out from under every
    # project attached to it. If a field needs a different owner, delete and
    # recreate it.
    _guard()
    doc = frappe.get_doc("BP Custom Field", name)
    _require_field_admin(doc.owner_project)

    if field_type is not None and field_type != doc.field_type:
        _assert_type_change_safe(name)
        doc.field_type = field_type

    if field_label is not None:
        doc.field_label = field_label
    if description is not None:
        doc.description = description
    if options is not None:
        doc.options_json = json.dumps(_parse_json(options, []))
    if applies_to is not None:
        doc.applies_to = applies_to
    if view_role is not None:
        doc.view_role = view_role
    if edit_role is not None:
        doc.edit_role = edit_role
    if conditional_rules is not None:
        doc.conditional_rules_json = json.dumps(_parse_json(conditional_rules, []))
    if show_in_list is not None:
        doc.show_in_list = 1 if int(show_in_list) else 0
    if enabled is not None:
        doc.enabled = 1 if int(enabled) else 0

    _validate_field_payload(
        doc.field_type, doc.applies_to, doc.view_role, doc.edit_role,
        _parse_json(doc.conditional_rules_json, []),
        _parse_json(doc.options_json, []),
    )

    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return _library_dict(doc)


@frappe.whitelist()
def delete_field(name):
    """Shared fields: hard delete blocked while any project still has this
    field attached (same "hard block, don't auto-migrate" philosophy as the
    old per-project type-change guard) — detach from every project first.

    Project-owned fields: cascade-delete instead of blocking. A project-owned
    field is EXPECTED to be attached to exactly its own project (and
    nowhere else — list_attachable_fields excludes it), but that's an
    invariant, not a guarantee enforced anywhere at the DB level, so deletion
    doesn't assume it: it strips every BP Custom Field Project row that
    references this field, across all parents, before deleting the field
    doc itself. No orphan join rows either way."""
    _guard()
    doc = frappe.get_doc("BP Custom Field", name)
    _require_field_admin(doc.owner_project)

    if doc.owner_project:
        frappe.db.delete("BP Custom Field Project", {"custom_field": name})
    else:
        assigned = frappe.db.count("BP Custom Field Project", {"custom_field": name})
        if assigned:
            frappe.throw(
                f"This field is still attached to {assigned} project(s). "
                f"Detach it from all projects before deleting."
            )

    frappe.delete_doc("BP Custom Field", name, ignore_permissions=True, force=True)
    frappe.db.commit()
    return {"ok": True}


# ─── PER-PROJECT ATTACH / CONFIGURE (project Admin) ────────────────────────

@frappe.whitelist()
def attach_field_to_project(project, custom_field, required=0):
    _guard()
    access.require(project, "Admin")

    if not frappe.db.exists("BP Custom Field", custom_field):
        frappe.throw("Custom field not found.")
    owner_project = frappe.db.get_value("BP Custom Field", custom_field, "owner_project")
    if owner_project and owner_project != project:
        # Project-owned fields are private by construction — list_attachable_fields
        # already excludes them from the picker, but that's a UI convenience, not
        # the enforcement boundary. Block it here too so a private field can never
        # leak onto a second project through a direct call to this endpoint.
        frappe.throw("This field is private to another project and can't be attached here.")

    proj = frappe.get_doc("BP Project", project)
    row = next((r for r in (proj.custom_field_links or []) if r.custom_field == custom_field), None)
    if row:
        row.required = 1 if int(required or 0) else 0
    else:
        proj.append("custom_field_links", {
            "custom_field": custom_field,
            "required": 1 if int(required or 0) else 0,
        })
    proj.flags.ignore_permissions = True
    proj.save()
    frappe.db.commit()
    return {"ok": True}


@frappe.whitelist()
def detach_field_from_project(project, custom_field):
    _guard()
    access.require(project, "Admin")

    proj = frappe.get_doc("BP Project", project)
    kept = [r for r in (proj.custom_field_links or []) if r.custom_field != custom_field]
    if len(kept) == len(proj.custom_field_links or []):
        return {"ok": True}  # wasn't attached — no-op
    proj.set("custom_field_links", [])
    for r in kept:
        proj.append("custom_field_links", {"custom_field": r.custom_field, "required": r.required})
    proj.flags.ignore_permissions = True
    proj.save()
    frappe.db.commit()
    return {"ok": True}


# ─── SCHEMA DELIVERY (project Viewer+, per-field view_role strip) ──────────

def _schema_dict(cf, link=None, project=None) -> dict:
    """The OLD embedded-JSON field shape (id/label/type/options/required/
    archived/show_in_list), not the library's Frappe-native shape
    (_library_dict). TaskDetail.vue/CreateTask.vue/ListView.vue/
    CustomFieldInput.vue all already know how to render this exact shape —
    keeping it means none of those existing consumers need to change how
    they read a field, only where the list comes from. Adds the new
    permission/marker fields on top: view_role, edit_role, can_edit,
    conditional_rules, and (Custom Fields v3) owner_project/is_shared so
    ProjectSettings.vue can tell a project-owned field apart from an
    attached shared one and show Edit/Delete vs Detach accordingly."""
    return {
        "id": cf.name,
        "label": cf.field_label,
        "description": cf.description or "",
        "type": cf.field_type,
        "options": _parse_json(cf.options_json, []),
        "show_in_list": bool(cf.show_in_list),
        "archived": not cf.enabled,
        "required": bool(link.required) if link else False,
        "view_role": cf.view_role or "Viewer",
        "edit_role": cf.edit_role or "Member",
        "conditional_rules": _parse_json(cf.conditional_rules_json, []),
        "owner_project": cf.owner_project or None,
        "is_shared": cf.owner_project != project,
    }


@frappe.whitelist()
def get_project_fields(project, scope="tasks"):
    """The schema TaskDetail/CreateTask/ListView/ProjectSettings all read
    instead of the old BP Project.custom_fields. `scope`: 'tasks' | 'projects'
    | 'all' — filters by applies_to. Fields the caller can't meet view_role
    for are stripped entirely (not just hidden client-side)."""
    _guard()
    access.require(project, "Viewer")

    out = []
    for link, cf in _attached_fields(project, scope):
        if not access.has_at_least(project, cf.view_role or "Viewer"):
            continue
        d = _schema_dict(cf, link, project)
        d["can_edit"] = access.has_at_least(project, cf.edit_role or "Member")
        out.append(d)
    return out


# ─── INTERNAL — used by board.py, not whitelisted ──────────────────────────

_SCOPE_MAP = {
    "tasks": {"Tasks", "Both"},
    "projects": {"Projects", "Both"},
    "all": {"Tasks", "Projects", "Both"},
}


def _attached_fields(project, scope="tasks"):
    """[(link_row, BP Custom Field doc), ...] for this project's enabled,
    scope-matching fields — no per-user view_role filtering (that's a
    read-time concern for get_project_fields; validation/edit-role checks
    need to see every attached field regardless of who's asking)."""
    wanted = _SCOPE_MAP.get(scope, _SCOPE_MAP["tasks"])
    proj = frappe.get_doc("BP Project", project)
    out = []
    for link in (proj.custom_field_links or []):
        cf = frappe.get_cached_doc("BP Custom Field", link.custom_field)
        if cf.enabled and (cf.applies_to or "Tasks") in wanted:
            out.append((link, cf))
    return out


def validation_schema_for_project(project, scope="tasks"):
    """The old embedded-JSON schema shape _validate_custom_field_values
    expects: [{id, label, type, required, options, archived}, ...] — built
    from the library instead of BP Project.custom_fields. link_doctype rides
    along for "link"-type fields so the validator can existence-check the
    stored record without a second lookup."""
    schema = []
    for link, cf in _attached_fields(project, scope):
        options = _parse_json(cf.options_json, [])
        entry = {
            "id": cf.name,
            "label": cf.field_label,
            "type": cf.field_type,
            "required": bool(link.required),
            "options": options,
            "archived": False,
        }
        if cf.field_type == "link" and isinstance(options, dict):
            entry["link_doctype"] = options.get("link_doctype")
        schema.append(entry)
    return schema


def assert_can_edit_field_values(project, values: dict):
    """Throws PermissionError if the current user is below edit_role for any
    field id present in `values`. Silent drop would be a worse UX than a
    clear rejection, and matches how every other write-gate in this app
    behaves (board.py's blocked-status guard, access.require, etc.)."""
    if not values:
        return
    for field_id in values:
        cf_data = frappe.db.get_value(
            "BP Custom Field", field_id, ["field_label", "edit_role"], as_dict=True
        )
        if not cf_data:
            continue  # orphan id — _validate_custom_field_values already ignores it
        if not access.has_at_least(project, cf_data.edit_role or "Member"):
            frappe.throw(
                f"You need at least {cf_data.edit_role} access to edit '{cf_data.field_label}'.",
                frappe.PermissionError,
            )


def hidden_field_ids_for_project(project, scope="tasks") -> set:
    """The set of attached field ids the current user is below view_role
    for — compute ONCE per project/request (frappe.get_cached_doc keeps the
    per-field lookups cheap within it), then reuse across every task's
    custom_field_values in that response. Doing a fresh DB lookup per task
    per field would be an N+1 query storm on a board with hundreds of tasks."""
    return {
        cf.name for _, cf in _attached_fields(project, scope)
        if not access.has_at_least(project, cf.view_role or "Viewer")
    }


def strip_unviewable_field_values(values: dict, hidden_ids: set) -> dict:
    """Strips values for fields in `hidden_ids`, before a task/project
    payload goes out over the API. Backend-enforced, not just
    frontend-hidden. Pair with hidden_field_ids_for_project(), computed once
    per request/project, not per task."""
    if not values or not hidden_ids:
        return values
    return {k: v for k, v in values.items() if k not in hidden_ids}


# ─── "link" FIELD TYPE — ERPNext record autocomplete (project Viewer+) ─────

@frappe.whitelist()
def search_field_link_options(project, field, txt=""):
    """Autocomplete for a 'link'-type custom field's value picker: searches
    real records of whatever ERPNext doctype the field was configured
    against. Uses frappe.get_list (permission-aware for the *current
    session user* on that doctype), not frappe.get_all — the row-level
    enforcement is real, not cosmetic."""
    _guard()
    access.require(project, "Viewer")

    # Binding check: `field` must actually be attached to (or owned by)
    # `project` — without this, any Viewer on any project could pass an
    # arbitrary field id belonging to a project they have no relationship
    # to and ride its edit_role/link_doctype config to go probing a
    # different project's ERPNext data.
    attached_ids = {cf.name for _, cf in _attached_fields(project, "all")}
    if field not in attached_ids:
        frappe.throw("This field is not available on this project.", frappe.PermissionError)

    cf = frappe.get_cached_doc("BP Custom Field", field)
    if cf.field_type != "link":
        frappe.throw("Not a linked-record field.")
    if not access.has_at_least(project, cf.edit_role or "Member"):
        frappe.throw("You don't have permission to edit this field.", frappe.PermissionError)

    link_doctype = _parse_json(cf.options_json, {}).get("link_doctype")
    # The allowlist check applies at search time too, not just field
    # create/update — it covers any field configured before the list
    # existed (or edited outside these endpoints).
    if not link_doctype or link_doctype not in _LINK_DOCTYPES:
        return []
    if not frappe.db.exists("DocType", link_doctype):
        return []

    title_field = frappe.db.get_value("DocType", link_doctype, "title_field") or "name"
    fields = ["name"] if title_field == "name" else ["name", title_field]
    or_filters = [["name", "like", f"%{txt}%"]]
    if title_field != "name":
        or_filters.append([title_field, "like", f"%{txt}%"])

    # frappe.get_all (permission-blind), NOT frappe.get_list: SPA users hold
    # zero ERPNext doctype perms by design, so get_list throws
    # PermissionError for every real user and this endpoint would return []
    # forever. The project-role gate + binding
    # check + edit_role check above plus the _LINK_DOCTYPES allowlist are
    # the authorization, same posture as board.search_erp_documents.
    rows = frappe.get_all(
        link_doctype,
        or_filters=or_filters if txt else None,
        fields=fields, limit=20, order_by="modified desc",
    )
    return [{"name": r["name"], "label": r.get(title_field) or r["name"]} for r in rows]
