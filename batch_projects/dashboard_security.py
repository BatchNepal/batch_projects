"""Enterprise authorization boundary for ERP-backed dashboard widgets.

A dashboard is an alternate read/write API over ERPNext data. Doctype-level
permission alone is insufficient: Frappe User Permissions, shares and field
permlevels must remain authoritative for rows, filters, grouping, quick-view,
link option discovery and drag writes.
"""

from __future__ import annotations

import frappe


def _dashboard_module():
    from batch_projects.api import dashboards
    return dashboards


def _guard():
    d = _dashboard_module()
    d.require_feature("dashboards")
    d._require_system_user()


def _entry(doctype: str):
    d = _dashboard_module()
    return d._widget_source_entry(doctype)


def _permitted_names(doctype: str, permission_type: str = "read") -> set[str]:
    if doctype == "BP Task":
        return {row["fieldname"] for row in _dashboard_module()._readable_field_rows(doctype)}

    if not frappe.has_permission(
        doctype, permission_type, user=frappe.session.user, raise_exception=False
    ):
        return set()
    from frappe.model import get_permitted_fields
    return set(
        get_permitted_fields(
            doctype,
            user=frappe.session.user,
            permission_type=permission_type,
        )
    )


def _field_rows(doctype: str, permission_type: str = "read") -> list[dict]:
    d = _dashboard_module()
    allowed = _permitted_names(doctype, permission_type)
    if not allowed:
        return []
    return [row for row in d._readable_field_rows(doctype) if row["fieldname"] in allowed]


def _parse_filters(filters):
    d = _dashboard_module()
    return d._parse_json(filters, []) if isinstance(filters, str) else (filters or [])


def _assert_filter_fields(doctype: str, filters) -> None:
    allowed = {row["fieldname"] for row in _field_rows(doctype, "read")}
    for item in _parse_filters(filters):
        fieldname = (item or {}).get("fieldname")
        if not fieldname:
            continue
        if doctype == "BP Task" and fieldname == "assignee":
            continue
        if fieldname not in allowed:
            frappe.throw(
                f"You don't have permission to filter {doctype} by '{fieldname}'.",
                frappe.PermissionError,
                title="Dashboard field permission denied",
            )


def _filters(doctype: str, filters):
    _assert_filter_fields(doctype, filters)
    return _dashboard_module()._build_db_filters(doctype, filters)


def _assert_fields(doctype: str, fieldnames, permission_type="read") -> None:
    allowed = _permitted_names(doctype, permission_type)
    denied = sorted({f for f in (fieldnames or []) if f and f not in allowed and f != "name"})
    if denied:
        frappe.throw(
            f"You don't have {permission_type} permission for field(s): " + ", ".join(denied),
            frappe.PermissionError,
            title="Dashboard field permission denied",
        )


def _link_labels(target_dt: str, values) -> dict:
    values = sorted({v for v in values if v})
    if not values or not target_dt:
        return {}
    if not frappe.has_permission(
        target_dt, "read", user=frappe.session.user, raise_exception=False
    ):
        return {v: v for v in values}

    permitted = _permitted_names(target_dt, "read")
    title_field = frappe.db.get_value("DocType", target_dt, "title_field") or "name"
    fields = ["name"]
    if title_field != "name" and title_field in permitted:
        fields.append(title_field)
    rows = frappe.get_list(
        target_dt,
        filters={"name": ["in", values]},
        fields=fields,
        limit_page_length=0,
    )
    labels = {row.name: row.get(title_field) or row.name for row in rows}
    return {v: labels.get(v, v) for v in values}


def _read_rows(doctype: str, *, filters=None, fields=None, order_by=None, limit=0):
    _assert_fields(doctype, fields or [], "read")
    kwargs = {
        "filters": filters or [],
        "fields": fields or ["name"],
        "limit_page_length": int(limit or 0),
    }
    if order_by:
        kwargs["order_by"] = order_by
    return frappe.get_list(doctype, **kwargs)


@frappe.whitelist()
def get_widget_source_fields(doctype):
    _guard()
    _entry(doctype)
    d = _dashboard_module()
    if doctype == "BP Task":
        from batch_projects.task_reads import _INTERNAL_TASK_FIELDS, _MONEY_TASK_FIELDS
        rows = [
            row for row in d._readable_field_rows(doctype)
            if row["fieldname"] not in (_INTERNAL_TASK_FIELDS | _MONEY_TASK_FIELDS)
        ] + d._synthetic_fields(doctype)
    else:
        rows = _field_rows(doctype, "read")

    image_field = frappe.get_meta(doctype).image_field
    if image_field:
        for row in rows:
            if row["fieldname"] == image_field:
                row["is_identity_image"] = True
                break
    return rows


@frappe.whitelist()
def get_widget_source_field_options(doctype, fieldname, query=None, limit=20):
    _guard()
    _entry(doctype)
    field = next((row for row in _field_rows(doctype, "read") if row["fieldname"] == fieldname), None)
    if not field or field["fieldtype"] not in ("Select", "Link"):
        frappe.throw(
            f"Field '{fieldname}' is not readable/filterable on {doctype}.",
            frappe.PermissionError,
        )

    q = (query or "").strip().lower()
    if field["fieldtype"] == "Select":
        return [
            {"value": option, "label": option}
            for option in (field.get("options") or [])
            if not q or q in option.lower()
        ]

    target_dt = field.get("options")
    if not target_dt or not frappe.has_permission(
        target_dt, "read", user=frappe.session.user, raise_exception=False
    ):
        return []
    permitted = _permitted_names(target_dt, "read")
    title_field = frappe.db.get_value("DocType", target_dt, "title_field") or "name"
    can_title = title_field == "name" or title_field in permitted
    fields = ["name"] + ([title_field] if title_field != "name" and can_title else [])
    or_filters = [["name", "like", f"%{query}%"]] if query else None
    if query and title_field != "name" and can_title:
        or_filters.append([title_field, "like", f"%{query}%"])
    rows = frappe.get_list(
        target_dt,
        or_filters=or_filters,
        fields=fields,
        limit_page_length=min(max(int(limit or 20), 1), 100),
        order_by="modified desc",
    )
    return [{"value": row.name, "label": row.get(title_field) or row.name} for row in rows]


@frappe.whitelist()
def get_multi_source_count(sources, scope=None):
    _guard()
    d = _dashboard_module()
    sources = d._parse_json(sources, []) if isinstance(sources, str) else (sources or [])
    breakdown = []
    for source in sources:
        doctype = (source or {}).get("doctype")
        if not doctype:
            continue
        entry = _entry(doctype)
        if doctype == "BP Task":
            from batch_projects.dashboard_task_reads import assert_dashboard_task_fields
            assert_dashboard_task_fields(scope=scope or "all", filters=source.get("filters"))
        db_filters = _filters(doctype, source.get("filters"))
        if doctype == "BP Task":
            scope_filters, _, _ = d._resolve_scope(scope or "all")
            db_filters = [
                [key, *(value if isinstance(value, list) else ["=", value])]
                for key, value in scope_filters.items()
            ] + db_filters
            db_filters.append(["is_deleted", "=", 0])
            count = frappe.db.count("BP Task", filters=db_filters)
        else:
            count = len(_read_rows(doctype, filters=db_filters, fields=["name"], limit=0))
        breakdown.append({"doctype": doctype, "label": entry["label"], "count": count})
    return {"total": sum(row["count"] for row in breakdown), "breakdown": breakdown}


@frappe.whitelist()
def get_doctype_group_data(doctype, group_by, filters=None, scope=None):
    _guard()
    if doctype == "BP Task":
        frappe.throw("Use the BP Task dashboard endpoint for task grouping.")
    _entry(doctype)
    fields_meta = {row["fieldname"]: row for row in _field_rows(doctype, "read")}
    meta = fields_meta.get(group_by)
    if not meta or meta["fieldtype"] not in ("Select", "Link"):
        frappe.throw(
            f"You don't have permission to group {doctype} by '{group_by}'.",
            frappe.PermissionError,
        )
    db_filters = _filters(doctype, filters)
    rows = _read_rows(doctype, filters=db_filters, fields=["name", group_by], limit=0)
    counts = {}
    for row in rows:
        value = row.get(group_by)
        counts[value] = counts.get(value, 0) + 1
    labels = _link_labels(meta.get("options"), counts) if meta["fieldtype"] == "Link" else {}
    items = [
        {"key": key or "__none__", "label": labels.get(key, key) if key else "None", "value": value}
        for key, value in counts.items()
    ]
    items.sort(key=lambda item: -item["value"])
    return {"items": items, "total": sum(counts.values()), "group_by": group_by, "doctype": doctype}


@frappe.whitelist()
def get_doctype_column_data(doctype, filters=None, sort=None, limit=200, scope=None,
                             label_fields=None, date_field=None, group_by="date",
                             extra_fields=None):
    _guard()
    if doctype == "BP Task":
        frappe.throw("Use get_column_widget_data for BP Task.")
    entry = _entry(doctype)
    d = _dashboard_module()
    fields_meta = {row["fieldname"]: row for row in _field_rows(doctype, "read")}
    allowed = set(fields_meta)
    title_field = frappe.db.get_value("DocType", doctype, "title_field") or "name"
    if title_field != "name" and title_field not in allowed:
        title_field = "name"
    status_field = entry.get("status_field") if entry.get("status_field") in allowed else None
    owner_field = entry.get("owner_field") if entry.get("owner_field") in allowed else None

    if date_field is None:
        default_date = entry.get("date_field")
        date_field = default_date if default_date in allowed else None
    date_field = date_field or None
    if date_field and fields_meta.get(date_field, {}).get("fieldtype") not in ("Date", "Datetime"):
        frappe.throw(f"You don't have permission to use '{date_field}' as a date field.", frappe.PermissionError)

    labels_raw = d._parse_json(label_fields, []) if isinstance(label_fields, str) else (label_fields or [])
    labels_wanted = [field for field in labels_raw if field in allowed]
    if any(field for field in labels_raw if field and field not in allowed):
        frappe.throw("One or more dashboard label fields are not permitted.", frappe.PermissionError)

    group_by = (group_by or "date").strip()
    if group_by not in ("date", "none") and group_by not in allowed:
        frappe.throw(f"You don't have permission to group {doctype} by '{group_by}'.", frappe.PermissionError)

    extras = d._parse_json(extra_fields, []) if isinstance(extra_fields, str) else (extra_fields or [])
    if any(field for field in extras if field and field not in allowed):
        frappe.throw("One or more dashboard row fields are not permitted.", frappe.PermissionError)
    template_fields = list(dict.fromkeys(field for field in extras if field in allowed))

    wanted = ["name", "modified"]
    for field in (title_field, status_field, owner_field, date_field, *labels_wanted, *template_fields):
        if field and field not in wanted:
            wanted.append(field)
    if group_by not in ("date", "none") and group_by not in wanted:
        wanted.append(group_by)

    db_filters = _filters(doctype, filters)
    if sort and sort not in allowed:
        frappe.throw("You don't have permission to sort by that field.", frappe.PermissionError)
    order_by = f"{date_field} asc" if date_field else (f"{sort} desc" if sort else "modified desc")
    rows = _read_rows(
        doctype, filters=db_filters, fields=wanted, order_by=order_by,
        limit=min(max(int(limit or 200), 1), 500),
    )
    raw_by_name = {row.name: row for row in rows}

    status_labels = {}
    if status_field and fields_meta[status_field]["fieldtype"] == "Link":
        status_labels = _link_labels(fields_meta[status_field].get("options"), [row.get(status_field) for row in rows])

    owner_names = {}
    if owner_field:
        owners = {row.get(owner_field) for row in rows if row.get(owner_field)}
        target = fields_meta[owner_field].get("options") or "User"
        labels = _link_labels(target, owners)
        for owner in owners:
            owner_names[owner] = {"user": owner, "full_name": labels.get(owner, owner), "user_image": ""}
        if target == "User" and owners and frappe.has_permission(
            "User", "read", user=frappe.session.user, raise_exception=False
        ):
            user_fields = _permitted_names("User", "read")
            if "user_image" in user_fields:
                for row in frappe.get_list(
                    "User", filters={"name": ["in", list(owners)]},
                    fields=["name", "user_image"], limit_page_length=0
                ):
                    if row.name in owner_names:
                        owner_names[row.name]["user_image"] = row.user_image or ""

    label_links = {}
    for field in labels_wanted:
        meta = fields_meta[field]
        if meta["fieldtype"] == "Link":
            label_links[field] = _link_labels(meta.get("options"), [row.get(field) for row in rows])
    template_links = {}
    for field in template_fields:
        meta = fields_meta[field]
        if meta["fieldtype"] == "Link":
            template_links[field] = _link_labels(meta.get("options"), [row.get(field) for row in rows])

    out = []
    for source in rows:
        date_value = source.get(date_field) if date_field else None
        row = {
            "name": source.name,
            "title": source.get(title_field) or source.name,
            "modified": str(source.get("modified") or ""),
            "status": status_labels.get(source.get(status_field), source.get(status_field)) if status_field else None,
            "owner": owner_names.get(source.get(owner_field)) if owner_field else None,
            "date": str(date_value) if date_value else None,
            "labels": [
                {"label": fields_meta[field]["label"], "value": label_links.get(field, {}).get(source.get(field), source.get(field))}
                for field in labels_wanted if source.get(field) not in (None, "")
            ],
        }
        for field in template_fields:
            if field in row:
                continue
            value = source.get(field)
            row[field] = template_links.get(field, {}).get(value, value) if value is not None else None
        out.append(row)

    buckets = []
    if group_by == "none":
        buckets = [{"key": d._GROUP_NONE_KEY, "label": "", "tasks": out}]
    elif group_by != "date":
        meta = fields_meta[group_by]
        order_hint = meta.get("options") or [] if meta["fieldtype"] == "Select" else []
        label_map = _link_labels(meta.get("options"), [row.get(group_by) for row in rows]) if meta["fieldtype"] == "Link" else {}
        for row in out:
            row["_group_value"] = raw_by_name.get(row["name"], {}).get(group_by)
        buckets = d._group_rows_by_field(
            out, group_by, order_hint, label_map,
            empty_label=f"No {(meta.get('label') or group_by).lower()}",
        )
    elif date_field:
        today = frappe.utils.getdate()
        grouped = {}
        for row in out:
            grouped.setdefault(d._bucket_for(row["date"], today), []).append(row)
        no_date_label = f"No {(fields_meta.get(date_field, {}).get('label') or 'date').lower()}"
        buckets = [
            {"key": bucket, "label": no_date_label if bucket == "no_date" else d._BUCKET_LABEL[bucket], "tasks": grouped[bucket]}
            for bucket in d._BUCKET_ORDER if grouped.get(bucket)
        ]

    return {"rows": out, "buckets": buckets, "total": len(out), "doctype": doctype, "date_field": date_field, "group_by": group_by}


@frappe.whitelist()
def update_widget_source_field(doctype, name, fieldname, value):
    _guard()
    if doctype == "BP Task":
        frappe.throw("Use the task workflow/status APIs for BP Task.")
    _entry(doctype)
    if fieldname not in _permitted_names(doctype, "write"):
        frappe.throw(f"You don't have permission to modify field '{fieldname}' on {doctype}.", frappe.PermissionError)
    if not frappe.has_permission(
        doctype, "write", doc=name, user=frappe.session.user, raise_exception=False
    ):
        frappe.throw("You don't have permission to modify this record.", frappe.PermissionError)

    doc = frappe.get_doc(doctype, name)
    if doc.get("docstatus") == 1:
        frappe.throw("This record is submitted and can't be changed here.")
    if doc.get(fieldname) == value:
        return {"ok": True, "changed": False}
    doc.set(fieldname, value)
    doc.save()
    frappe.db.commit()
    return {"ok": True, "changed": True}


@frappe.whitelist()
def get_widget_source_doc_quickview(doctype, name):
    _guard()
    if doctype == "BP Task":
        frappe.throw("Use the Task detail panel for BP Task records.")
    _entry(doctype)
    if not frappe.has_permission(
        doctype, "read", doc=name, user=frappe.session.user, raise_exception=False
    ):
        frappe.throw("Not found.", frappe.DoesNotExistError)

    fields = _field_rows(doctype, "read")
    title_field = frappe.db.get_value("DocType", doctype, "title_field") or "name"
    allowed = _permitted_names(doctype, "read")
    if title_field != "name" and title_field not in allowed:
        title_field = "name"
    names = ["name"] + [row["fieldname"] for row in fields]
    if title_field not in names:
        names.append(title_field)
    rows = _read_rows(doctype, filters={"name": name}, fields=list(dict.fromkeys(names)), limit=1)
    if not rows:
        frappe.throw("Not found.", frappe.DoesNotExistError)
    source = rows[0]

    out_fields = []
    for field in fields:
        value = source.get(field["fieldname"])
        if value in (None, ""):
            continue
        if field["fieldtype"] == "Link":
            value = _link_labels(field.get("options"), [value]).get(value, value)
        out_fields.append({
            "label": field["label"], "value": value,
            "fieldname": field["fieldname"], "fieldtype": field["fieldtype"],
        })
    return {"doctype": doctype, "name": name, "title": source.get(title_field) or name, "fields": out_fields}
