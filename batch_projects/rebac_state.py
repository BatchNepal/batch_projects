"""ReBAC rebuild source filtered to durable live task state.

MariaDB is authoritative and OpenFGA is a rebuildable materialized index.
Soft-deleted tasks therefore must not be emitted during a full rebuild; doing
so would resurrect permissions that the task.trashed event already revoked.
"""

from __future__ import annotations

import frappe


def _page(offset=0, limit=500):
    offset = max(int(offset or 0), 0)
    limit = min(max(int(limit or 500), 1), 1000)
    return offset, limit


@frappe.whitelist()
def sync_rebac_state(resource, offset=0, limit=500):
    from batch_projects.api import board

    board._assert_service_caller()
    offset, limit = _page(offset, limit)

    if resource == "tasks":
        rows = frappe.get_all(
            "BP Task",
            filters={"is_deleted": 0},
            fields=["name as task", "project"],
            limit_start=offset,
            limit_page_length=limit,
            order_by="creation asc",
        )
    elif resource == "task_assignees":
        # Child rows carry no is_deleted flag, so filter through their live
        # parent task in SQL. Pagination must happen AFTER the join/filter;
        # filtering a generic child-table page in Python could return fewer
        # than limit and make the gateway stop before later live rows.
        rows = frappe.db.sql(
            """
            SELECT a.parent AS task, a.user
            FROM `tabBP Task Assignee` a
            INNER JOIN `tabBP Task` t
                ON t.name = a.parent
               AND COALESCE(t.is_deleted, 0) = 0
            WHERE a.parenttype = 'BP Task'
            ORDER BY a.creation ASC
            LIMIT %(limit)s OFFSET %(offset)s
            """,
            {"limit": limit, "offset": offset},
            as_dict=True,
        )
    else:
        # Projects/project-members are unaffected by task soft deletion; keep
        # the established serializer/role normalization for those resources.
        return board.sync_rebac_state(resource, offset=offset, limit=limit)

    return {
        "items": rows,
        "has_more": len(rows) == limit,
        "next_offset": offset + len(rows),
    }
