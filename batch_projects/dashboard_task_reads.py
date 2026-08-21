"""Trash-safe adapters for BP Task-backed dashboard widgets."""

from __future__ import annotations

import frappe


@frappe.whitelist()
def get_column_widget_data(
    scope="all", filter_by=None, filter_value=None, status_filter="open",
    filters=None, group_by="date", extra_fields=None,
):
    """Preserve dashboard row semantics while stripping soft-deleted tasks.

    The legacy dashboard engine predates task trash and calls frappe.get_all()
    directly without is_deleted=0. This adapter is the public boundary until
    that large engine is decomposed; it filters every returned bucket against a
    fresh live-task set and recomputes the unique task total.
    """
    from batch_projects.api import dashboards

    result = dashboards.get_column_widget_data(
        scope=scope,
        filter_by=filter_by,
        filter_value=filter_value,
        status_filter=status_filter,
        filters=filters,
        group_by=group_by,
        extra_fields=extra_fields,
    )
    buckets = result.get("buckets") or []
    names = {
        row.get("name")
        for bucket in buckets
        for row in (bucket.get("tasks") or [])
        if row.get("name")
    }
    if not names:
        result["total"] = 0
        return result

    live = set(
        frappe.get_all(
            "BP Task",
            filters={"name": ["in", sorted(names)], "is_deleted": 0},
            pluck="name",
        )
    )
    for bucket in buckets:
        bucket["tasks"] = [
            row for row in (bucket.get("tasks") or []) if row.get("name") in live
        ]
    result["buckets"] = [bucket for bucket in buckets if bucket.get("tasks")]
    result["total"] = len(live)
    return result


@frappe.whitelist()
def get_multi_source_count(sources, scope=None):
    """Multi-source KPI count with an unconditional live-task predicate."""
    from batch_projects.api import dashboards

    dashboards.require_feature("dashboards")
    dashboards._require_system_user()
    sources = dashboards._parse_json(sources, []) if isinstance(sources, str) else (sources or [])
    if not sources:
        return {"total": 0, "breakdown": []}

    breakdown = []
    for source in sources:
        doctype = (source or {}).get("doctype")
        if not doctype:
            continue
        entry = dashboards._widget_source_entry(doctype)
        db_filters = dashboards._build_db_filters(doctype, source.get("filters"))

        if doctype == "BP Task":
            scope_filters, _, _ = dashboards._resolve_scope(scope or "all")
            db_filters = [
                [key, *(value if isinstance(value, list) else ["=", value])]
                for key, value in scope_filters.items()
            ] + db_filters
            db_filters.append(["is_deleted", "=", 0])

        count = frappe.db.count(doctype, filters=db_filters)
        breakdown.append(
            {"doctype": doctype, "label": entry["label"], "count": count}
        )

    return {"total": sum(row["count"] for row in breakdown), "breakdown": breakdown}
