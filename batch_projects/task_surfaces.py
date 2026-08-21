"""Legacy task surfaces that must operate on live tasks only."""

from __future__ import annotations

import frappe


@frappe.whitelist()
def complete_sprint(sprint, move_incomplete_to=None):
    """Complete a sprint without resurrecting or moving trashed tasks."""
    from batch_projects.api import board

    doc = frappe.get_doc("BP Sprint", sprint)
    board._check_permission(doc.project, "BP Member")
    if doc.status != "Active":
        frappe.throw("Only active sprints can be completed.")

    done_statuses = board._get_completed_statuses_by_project(doc.project)
    filters = {"sprint": sprint, "project": doc.project, "is_deleted": 0}
    if done_statuses:
        filters["status"] = ["not in", done_statuses]

    incomplete = frappe.get_all("BP Task", filters=filters, fields=["name"])
    target = move_incomplete_to or None

    if incomplete:
        names = [row["name"] for row in incomplete]
        if target:
            target_project = frappe.db.get_value("BP Sprint", target, "project")
            if target_project != doc.project:
                frappe.throw("Target sprint does not belong to the same project.")
        for name in names:
            task = frappe.get_doc("BP Task", name)
            task.sprint = target
            task.save(ignore_permissions=True)

    doc.status = "Completed"
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    board._invalidate_sprint_cache(doc.project)

    from batch_projects.events import emit, SPRINT_COMPLETED
    completed_count = (
        frappe.db.count(
            "BP Task",
            {
                "sprint": sprint,
                "project": doc.project,
                "is_deleted": 0,
                "status": ["in", done_statuses],
            },
        )
        if done_statuses
        else 0
    )
    emit(
        SPRINT_COMPLETED,
        {
            "project": doc.project,
            "sprint": doc.name,
            "sprint_name": doc.sprint_name,
            "completed_count": completed_count,
            "incomplete_count": len(incomplete),
            "moved_to": target,
        },
    )
    return {
        "sprint": doc.as_dict(),
        "moved_count": len(incomplete),
        "moved_to": target,
    }


@frappe.whitelist()
def get_project_files(project):
    """Project Files tab: direct project files + attachments of live tasks only."""
    from batch_projects.api import board
    from batch_projects import access

    board._check_permission(project, "BP Viewer")
    if not access.has_capability(project, "view_files"):
        return []

    files = frappe.db.sql(
        """
        SELECT f.name, f.file_name, f.file_url, f.file_size,
               f.is_private, f.creation, f.owner,
               f.attached_to_name AS task_name,
               t.title AS task_title,
               u.full_name AS uploaded_by_name
        FROM `tabFile` f
        JOIN `tabBP Task` t ON t.name = f.attached_to_name
        LEFT JOIN `tabUser` u ON u.name = f.owner
        WHERE f.attached_to_doctype = 'BP Task'
          AND t.project = %(project)s
          AND t.is_deleted = 0

        UNION ALL

        SELECT f.name, f.file_name, f.file_url, f.file_size,
               f.is_private, f.creation, f.owner,
               NULL AS task_name,
               NULL AS task_title,
               u.full_name AS uploaded_by_name
        FROM `tabFile` f
        LEFT JOIN `tabUser` u ON u.name = f.owner
        WHERE f.attached_to_doctype = 'BP Project'
          AND f.attached_to_name = %(project)s

        ORDER BY creation DESC
        """,
        {"project": project},
        as_dict=True,
    )

    return [
        {
            "name": row.name,
            "file_name": row.file_name,
            "file_url": row.file_url,
            "file_size": row.file_size,
            "is_private": bool(row.is_private),
            "creation": str(row.creation) if row.creation else None,
            "owner": row.owner,
            "uploaded_by_name": row.uploaded_by_name or row.owner,
            "task_name": row.task_name,
            "task_title": row.task_title or row.task_name,
        }
        for row in files
    ]
