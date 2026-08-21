"""Permission- and trash-safe adapters for BP Task-backed dashboards."""

from __future__ import annotations

import frappe

from batch_projects import access
from batch_projects.task_reads import _INTERNAL_TASK_FIELDS, _MONEY_TASK_FIELDS


def _scope_projects(scope="all") -> list[str]:
    from batch_projects.api import dashboards
    _, project, projects = dashboards._resolve_scope(scope or "all")
    if projects:
        return list(projects)
    if project:
        return [project]
    from batch_projects.permissions import get_accessible_projects
    accessible = get_accessible_projects()
    if accessible is None:
        return frappe.get_all("BP Project", pluck="name")
    return list(accessible)


def _field_allowed(fieldname: str, projects: list[str]) -> bool:
    if not fieldname:
        return True
    if fieldname == "assignee":
        return True
    if fieldname in _INTERNAL_TASK_FIELDS:
        return False
    if fieldname in _MONEY_TASK_FIELDS:
        return bool(projects) and all(
            access.has_capability(project, "view_money") for project in projects
        )
    return True


def assert_dashboard_task_fields(scope="all", filters=None, group_by=None, extra_fields=None):
    """Block forbidden fields before they can influence rows/counts/buckets."""
    from batch_projects.api import dashboards
    projects = _scope_projects(scope)
    parsed_filters = dashboards._parse_json(filters, []) if isinstance(filters, str) else (filters or [])
    requested = {
        (row or {}).get("fieldname") for row in parsed_filters
        if isinstance(row, dict) and (row or {}).get("fieldname")
    }
    extras = dashboards._parse_json(extra_fields, []) if isinstance(extra_fields, str) else (extra_fields or [])
    requested.update(field for field in extras if isinstance(field, str))
    if group_by and group_by not in ("date", "none"):
        requested.add(group_by)

    denied = sorted(field for field in requested if not _field_allowed(field, projects))
    if denied:
        frappe.throw(
            "You don't have permission to use these task fields in this dashboard: "
            + ", ".join(denied),
            frappe.PermissionError,
            title="Dashboard field permission denied",
        )
    return projects


def _sanitize_task_row(row: dict) -> dict:
    project = row.get("project")
    for field in _INTERNAL_TASK_FIELDS:
        row.pop(field, None)
    if project and not access.has_capability(project, "view_money"):
        for field in _MONEY_TASK_FIELDS:
            row.pop(field, None)
    return row


@frappe.whitelist()
def get_column_widget_data(
    scope="all", filter_by=None, filter_value=None, status_filter="open",
    filters=None, group_by="date", extra_fields=None,
):
    """Preserve dashboard semantics while enforcing live + field policy."""
    assert_dashboard_task_fields(
        scope=scope, filters=filters, group_by=group_by, extra_fields=extra_fields
    )

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
    visible_names = set()
    from batch_projects.task_invariants import _user_can_view_task
    for row in frappe.get_all(
        "BP Task",
        filters={"name": ["in", sorted(live)]},
        fields=["name", "project"],
    ):
        if _user_can_view_task(row.project, row.name, frappe.session.user):
            visible_names.add(row.name)

    for bucket in buckets:
        safe = []
        for row in bucket.get("tasks") or []:
            if row.get("name") not in visible_names:
                continue
            safe.append(_sanitize_task_row(row))
        bucket["tasks"] = safe
    result["buckets"] = [bucket for bucket in buckets if bucket.get("tasks")]
    result["total"] = len(visible_names)
    return result


@frappe.whitelist()
def get_multi_source_count(sources, scope=None):
    """Backward-compatible entry point; dashboard_security is authoritative."""
    from batch_projects.dashboard_security import get_multi_source_count as secure
    return secure(sources, scope=scope)
