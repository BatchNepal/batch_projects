"""
Normalize legacy 'BP '-prefixed role values on BP Project Member rows.

create_project's raw-SQL creator-INSERT (api/board.py) used to write the
Frappe Role name 'BP Admin' into the child table's role column instead of
the Select field's canonical 'Admin'. It never blew up because raw SQL
bypasses Select validation on write, and access.py's _ROLE_ALIASES silently
normalized it on every read. The first ever ORM .save() of a BP Project
(create_and_link_erpnext_project) is what finally caught it.

Every other writer (update_project_members, invitations._add_membership,
create_team/update_team_members) already used the canonical bare spelling —
this is a one-time backfill for the rows the buggy INSERT produced.
"""

import frappe

_PREFIXED_ROLES = ["BP Admin", "BP Manager", "BP Member", "BP Viewer"]


def execute():
    if not frappe.db.table_exists("BP Project Member"):
        return

    frappe.db.sql(
        """
        UPDATE `tabBP Project Member`
        SET role = SUBSTRING(role, 4)
        WHERE role IN %(roles)s
        """,
        {"roles": _PREFIXED_ROLES},
    )
    frappe.db.commit()
