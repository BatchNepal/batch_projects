"""BP Report gains `scope` (project/workspace) and `visibility`
(private/workspace). Existing rows get visibility="workspace" uniformly
(every report is workspace-readable today regardless of who made it — that's
the real de-facto behavior being preserved). `scope` is DERIVED per row from
whether `project` is already set, not set uniformly to "project" — a
pre-existing cross-project report (project blank, which the field's own
description already documents as meaning "cross-project") must migrate to
scope="workspace" to match its actual current behavior; forcing scope=
"project" on a project-less row would silently mislabel it. Additive only,
no data loss."""

import frappe


def execute():
    frappe.db.sql("""
        UPDATE `tabBP Report`
        SET visibility = 'workspace',
            scope = CASE WHEN project IS NOT NULL AND project != '' THEN 'project' ELSE 'workspace' END
        WHERE scope IS NULL OR scope = ''
    """)
    frappe.db.commit()
