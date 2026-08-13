"""
Deletes BP Project Member rows whose `user` no longer exists.

Deleting a User does not clean up the child rows that referenced them, and
Frappe validates every Link field on the WHOLE document at save time — so one
orphaned member row makes the entire BP Project undoctorable:

    LinkValidationError: Could not find Row #3: User: <deleted user>

Every save path for that project fails, including ones that never touch the
members table (renaming it, changing its budget, adding a different member).
Found on test1-erp 2026-08-14, where a deleted test account left a row behind
on a project and blocked adding any new member through the normal doc API.

Scoped deliberately to BP Project Member.user, which is the reference proven
to break saves. This is not a general orphan sweep: other BP link fields
point at doctypes we do not delete rows from the same way, and a patch that
silently prunes references across the schema is a worse failure mode than the
error it replaces.

Runs as a plain DELETE rather than through the ORM on purpose — loading the
parent doc to remove the row is exactly the operation the orphan prevents.
"""

import frappe


def execute():
    if not frappe.db.table_exists("BP Project Member"):
        return

    orphans = frappe.db.sql(
        """
        SELECT m.name, m.parent, m.user
        FROM `tabBP Project Member` m
        LEFT JOIN `tabUser` u ON u.name = m.user
        WHERE m.user IS NOT NULL AND m.user != '' AND u.name IS NULL
        """,
        as_dict=True,
    )
    if not orphans:
        return

    frappe.db.sql(
        """
        DELETE m FROM `tabBP Project Member` m
        LEFT JOIN `tabUser` u ON u.name = m.user
        WHERE m.user IS NOT NULL AND m.user != '' AND u.name IS NULL
        """
    )

    # Named individually: these are membership grants disappearing, and the
    # next person to wonder why a project lost a member deserves the list.
    for row in orphans:
        frappe.logger().info(
            f"clean_orphaned_project_members: removed {row.user} from "
            f"{row.parent} (user no longer exists)"
        )
