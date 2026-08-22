"""Backfill immutable Runtime V2 identity for existing automation rules."""

import frappe

from batch_projects.batch_projects.doctype.bp_automation_rule.bp_automation_rule import (
    automation_rule_definition_hash,
)


def execute():
    for name in frappe.get_all("BP Automation Rule", pluck="name"):
        rule = frappe.get_doc("BP Automation Rule", name)
        definition_hash = automation_rule_definition_hash(rule)
        revision = max(1, int(rule.automation_revision or 0))
        if (
            revision != int(rule.automation_revision or 0)
            or definition_hash != (rule.automation_definition_hash or "")
        ):
            frappe.db.set_value(
                "BP Automation Rule",
                name,
                {
                    "automation_revision": revision,
                    "automation_definition_hash": definition_hash,
                },
                update_modified=False,
            )
