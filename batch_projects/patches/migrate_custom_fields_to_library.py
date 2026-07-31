"""
Migrate BP Project.custom_fields (per-project embedded JSON schema) into the
new workspace-level BP Custom Field library + BP Custom Field Project join
rows.

Each existing field becomes its own BP Custom Field document, keeping its
original id as the new document's name — BP Task.custom_field_values already
references that id, so preserving it means zero task data needs touching —
and attached back to only the project it came from via a BP Custom Field
Project row on that project's custom_field_links table.

No cross-project merging or deduplication: two differently-authored
"Priority" fields in two different projects stay two separate library
entries. Sharing a field across projects is an admin's explicit choice going
forward (attach an existing library field to another project); this patch
can't safely infer "these look like the same field."

BP Project.custom_fields itself is left untouched (deprecated, unused after
this patch runs — see the field's own JSON description).

Field ids were generated client-side as "cf_" + 8 hex chars (~32 bits) with
no server-side global-uniqueness guarantee, so an existing BP Custom Field
with the same id is not automatically "the same field already migrated" —
only treated that way if its label+type match; otherwise a fresh id is
minted so two unrelated fields never get silently merged into one identity.
"""

import json

import frappe


def execute():
    if not frappe.db.table_exists("BP Project") or not frappe.db.table_exists("BP Custom Field"):
        return

    projects = frappe.get_all(
        "BP Project",
        fields=["name", "custom_fields", "owner"],
        filters={"custom_fields": ["is", "set"]},
    )

    for p in projects:
        raw = p.get("custom_fields")
        if not raw:
            continue
        try:
            schema = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            continue
        if not isinstance(schema, list) or not schema:
            continue

        proj = frappe.get_doc("BP Project", p["name"])
        existing_links = {r.custom_field for r in (proj.custom_field_links or [])}
        changed = False

        for field in schema:
            if not isinstance(field, dict) or not field.get("id"):
                continue

            fid = field["id"]
            label = field.get("label") or "Untitled field"
            ftype = field.get("type") or "text"

            current = frappe.db.get_value(
                "BP Custom Field", fid, ["field_label", "field_type"], as_dict=True
            )
            if current is None:
                _create_library_field(fid, label, ftype, field, p.get("owner"))
            elif current.field_label != label or current.field_type != ftype:
                # Id collision with an unrelated field — never merge identities.
                # The re-mint must also rewrite THIS project's task values from
                # the old id to the new one, or they'd stay keyed to the OTHER
                # project's field: not delivered here (field not attached) and
                # silently swept as orphans on the next task save.
                old_fid = fid
                fid = frappe.generate_hash(length=10)
                _create_library_field(fid, label, ftype, field, p.get("owner"))
                _rewrite_task_values(p["name"], old_fid, fid)
            # else: same id, same label+type — already migrated, reuse it.

            if fid not in existing_links:
                proj.append("custom_field_links", {
                    "custom_field": fid,
                    "required": 1 if field.get("required") else 0,
                })
                existing_links.add(fid)
                changed = True

        if changed:
            proj.flags.ignore_permissions = True
            proj.save()

    frappe.db.commit()


def _rewrite_task_values(project, old_id, new_id):
    """Re-key one project's task values after an id-collision re-mint.
    frappe.db.set_value with update_modified=False — a data migration must
    not touch modified stamps or fire timeline events."""
    rows = frappe.get_all(
        "BP Task",
        filters={"project": project, "custom_field_values": ["like", f"%{old_id}%"]},
        fields=["name", "custom_field_values"],
    )
    for r in rows:
        try:
            vals = json.loads(r.custom_field_values or "{}")
        except Exception:
            continue
        if not isinstance(vals, dict) or old_id not in vals:
            continue
        vals[new_id] = vals.pop(old_id)
        frappe.db.set_value(
            "BP Task", r.name, "custom_field_values",
            json.dumps(vals), update_modified=False,
        )


def _create_library_field(fid, label, ftype, field, owner):
    cf = frappe.new_doc("BP Custom Field")
    cf.field_label = label
    cf.description = field.get("description") or ""
    cf.field_type = ftype
    cf.options_json = json.dumps(field.get("options") or [])
    cf.applies_to = "Tasks"
    cf.view_role = "Viewer"
    cf.edit_role = "Member"
    cf.show_in_list = 1 if field.get("show_in_list") else 0
    cf.enabled = 0 if field.get("archived") else 1
    cf.conditional_rules_json = "[]"
    if owner:
        cf.owner = owner
    cf.flags.ignore_permissions = True
    cf.insert(ignore_permissions=True, set_name=fid)
