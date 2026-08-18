"""Initialize durable definition identity for workflows created before this field."""

import frappe


def execute():
    from batch_projects.batch_projects.doctype.bp_workflow.bp_workflow import workflow_definition_hash

    rows = frappe.get_all(
        "BP Workflow", fields=["name", "automation_revision", "automation_definition_hash"],
    )
    for row in rows:
        if int(row.automation_revision or 0) and row.automation_definition_hash:
            continue
        workflow = frappe.get_doc("BP Workflow", row.name)
        frappe.db.set_value("BP Workflow", row.name, {
            "automation_revision": max(1, int(workflow.automation_revision or 0)),
            "automation_definition_hash": workflow_definition_hash(workflow),
        }, update_modified=False)
