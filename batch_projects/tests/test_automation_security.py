# Copyright (c) 2026, BatchNepal and contributors
# Regression coverage for automation_security.py actually being reachable and
# actually enforcing its authority boundary — not just present on disk.
# Run: bench --site <site> run-tests --app batch_projects

import json
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from batch_projects import access, automation_security, hooks
from batch_projects.api.board import create_project

TEST_KEY = "TASEC"


def _delete_project(key):
    name = frappe.db.get_value("BP Project", {"key": key})
    if not name:
        return
    for rule in frappe.get_all("BP Automation Rule", filters={"project": name}, pluck="name"):
        frappe.delete_doc("BP Automation Rule", rule, ignore_permissions=True, force=True)
    frappe.delete_doc("BP Project", name, ignore_permissions=True, force=True)
    frappe.db.commit()


def _rule(**overrides):
    doc = frappe._dict(
        scope="project",
        project="SOME-PROJECT",
        project_filter=None,
        actions=None,
        action_type=None,
    )
    doc.update(overrides)
    return doc


class TestAutomationSecurityWiring(FrappeTestCase):
    """Prove the hook registrations exist AND point at real, callable functions —
    the original bug was these entries being entirely absent, so this is a
    real regression guard, not just documentation."""

    def test_doc_event_is_registered(self):
        self.assertEqual(
            hooks.doc_events["BP Automation Rule"]["validate"],
            "batch_projects.automation_security.validate_rule_authority",
        )

    def test_whitelisted_overrides_are_registered(self):
        self.assertEqual(
            hooks.override_whitelisted_methods["batch_projects.api.automation.apply_action"],
            "batch_projects.automation_security.apply_action",
        )
        self.assertEqual(
            hooks.override_whitelisted_methods["batch_projects.api.automation.run_scheduled_event"],
            "batch_projects.automation_security.run_scheduled_event",
        )

    def test_override_targets_are_whitelisted(self):
        # A registered override that isn't itself @frappe.whitelist()'d 404s
        # at dispatch time instead of running — frappe.is_whitelisted is the
        # actual check Frappe's dispatcher runs, not a decorator attribute.
        frappe.is_whitelisted(automation_security.apply_action)
        frappe.is_whitelisted(automation_security.run_scheduled_event)


class TestRuleAuthority(FrappeTestCase):
    """Direct unit coverage of validate_rule_authority's real branches."""

    def test_instance_admin_bypasses_everything(self):
        with patch.object(access, "is_instance_admin", return_value=True):
            automation_security.validate_rule_authority(_rule(actions=json.dumps([])))

    def test_project_scope_requires_project_admin(self):
        with (
            patch.object(access, "is_instance_admin", return_value=False),
            patch.object(access, "has_at_least", return_value=False) as has_at_least,
        ):
            with self.assertRaises(frappe.PermissionError):
                automation_security.validate_rule_authority(_rule(actions=json.dumps([])))
        has_at_least.assert_called_once_with("SOME-PROJECT", "Admin")

    def test_project_scope_allowed_for_project_admin(self):
        with (
            patch.object(access, "is_instance_admin", return_value=False),
            patch.object(access, "has_at_least", return_value=True),
        ):
            automation_security.validate_rule_authority(_rule(actions=json.dumps([])))

    def test_workspace_scope_requires_workspace_admin(self):
        with (
            patch.object(access, "is_instance_admin", return_value=False),
            patch.object(access, "is_workspace_admin", return_value=False),
        ):
            with self.assertRaises(frappe.PermissionError):
                automation_security.validate_rule_authority(
                    _rule(scope="workspace", project=None, actions=json.dumps([]))
                )

    def test_erp_document_action_rejected_outside_workspace_scope(self):
        action = json.dumps([{"type": "Update ERPNext Document", "config": {}}])
        with (
            patch.object(access, "is_instance_admin", return_value=False),
            patch.object(access, "has_at_least", return_value=True),
        ):
            with self.assertRaises(frappe.PermissionError):
                automation_security.validate_rule_authority(_rule(actions=action))

    def test_erp_document_action_allowed_in_workspace_scope(self):
        action = json.dumps([{"type": "Update ERPNext Document", "config": {}}])
        with (
            patch.object(access, "is_instance_admin", return_value=False),
            patch.object(access, "is_workspace_admin", return_value=True),
        ):
            automation_security.validate_rule_authority(
                _rule(scope="workspace", project=None, actions=action)
            )

    def test_message_template_rejects_money_field_token(self):
        action = json.dumps([{
            "type": "Notify", "config": {"message": "Rate: {{ task.billable }}"}
        }])
        with (
            patch.object(access, "is_instance_admin", return_value=True),
        ):
            with self.assertRaises(frappe.PermissionError):
                automation_security.validate_rule_authority(_rule(actions=action))

    def test_message_template_allows_ordinary_field_token(self):
        action = json.dumps([{
            "type": "Notify", "config": {"message": "Status: {{ task.status }}"}
        }])
        with patch.object(access, "is_instance_admin", return_value=True):
            automation_security.validate_rule_authority(_rule(actions=action))

    def test_project_filter_rejected_on_project_scope_rule(self):
        with (
            patch.object(access, "is_instance_admin", return_value=False),
            patch.object(access, "has_at_least", return_value=True),
        ):
            with self.assertRaises(frappe.ValidationError):
                automation_security.validate_rule_authority(
                    _rule(project_filter=json.dumps(["OTHER-PROJECT"]), actions=json.dumps([]))
                )


class TestDispatchScope(FrappeTestCase):
    """validate_dispatch is the runtime (not just save-time) boundary — legacy
    rows and direct DB tampering must still be caught here."""

    def test_project_rule_rejects_mismatched_payload_project(self):
        rule_doc = frappe._dict(scope="project", project="RULE-PROJECT", actions="[]")
        with self.assertRaises(frappe.PermissionError):
            automation_security.validate_dispatch(rule_doc, {"project": "OTHER-PROJECT"})

    def test_workspace_rule_rejects_project_outside_filter(self):
        rule_doc = frappe._dict(
            scope="workspace", project=None,
            project_filter=json.dumps(["ALLOWED-PROJECT"]), actions="[]",
        )
        with self.assertRaises(frappe.PermissionError):
            automation_security.validate_dispatch(rule_doc, {"project": "OTHER-PROJECT"})

    def test_workspace_rule_with_empty_filter_allows_any_known_project(self):
        rule_doc = frappe._dict(scope="workspace", project=None, project_filter=None, actions="[]")
        with patch.object(frappe.db, "exists", return_value=True):
            result = automation_security.validate_dispatch(rule_doc, {"project": "ANY-PROJECT"})
        self.assertEqual(result["project"], "ANY-PROJECT")

    def test_invalid_scope_rejected(self):
        rule_doc = frappe._dict(scope="bogus", project=None, actions="[]")
        with self.assertRaises(frappe.PermissionError):
            automation_security.validate_dispatch(rule_doc, {"project": "X"})

    def test_legacy_row_reevaluates_erp_document_action_at_dispatch(self):
        rule_doc = frappe._dict(
            scope="project", project="RULE-PROJECT",
            actions=json.dumps([{"type": "Update ERPNext Document", "config": {}}]),
        )
        with self.assertRaises(frappe.PermissionError):
            automation_security.validate_dispatch(rule_doc, {"project": "RULE-PROJECT"})


class TestWhitelistedWrappers(FrappeTestCase):
    """Prove apply_action/run_scheduled_event actually call validate_dispatch
    before delegating — not just that hooks.py names them correctly."""

    def test_apply_action_blocks_mismatched_project_before_delegating(self):
        rule_name = "fake-rule-001"
        with (
            patch("batch_projects.api.automation._assert_service_caller"),
            patch.object(frappe.db, "exists", return_value=True),
            patch(
                "batch_projects.api.automation.apply_action"
            ) as real_apply_action,
            patch.object(
                frappe, "get_doc",
                return_value=frappe._dict(
                    scope="project", project="REAL-PROJECT", is_active=1, actions="[]",
                ),
            ),
        ):
            with self.assertRaises(frappe.PermissionError):
                automation_security.apply_action(
                    rule=rule_name, payload={"project": "WRONG-PROJECT"}
                )
        real_apply_action.assert_not_called()

    def test_apply_action_skips_inactive_rule_without_delegating(self):
        with (
            patch("batch_projects.api.automation._assert_service_caller"),
            patch.object(frappe.db, "exists", return_value=True),
            patch("batch_projects.api.automation.apply_action") as real_apply_action,
            patch.object(
                frappe, "get_doc",
                return_value=frappe._dict(scope="project", project="P", is_active=0, actions="[]"),
            ),
        ):
            result = automation_security.apply_action(rule="r", payload={})
        self.assertEqual(result["status"], "skipped")
        real_apply_action.assert_not_called()

    def test_apply_action_delegates_once_scope_checks_pass(self):
        with (
            patch("batch_projects.api.automation._assert_service_caller"),
            patch.object(frappe.db, "exists", return_value=True),
            patch(
                "batch_projects.api.automation.apply_action", return_value={"status": "ok"}
            ) as real_apply_action,
            patch.object(
                frappe, "get_doc",
                return_value=frappe._dict(
                    scope="project", project="REAL-PROJECT", is_active=1, actions="[]",
                ),
            ),
        ):
            result = automation_security.apply_action(
                rule="r", payload={"project": "REAL-PROJECT"}
            )
        real_apply_action.assert_called_once()
        self.assertEqual(result["status"], "ok")


class TestAutomationRuleSaveIntegration(FrappeTestCase):
    """End-to-end: the doc_events hook must actually fire on a real save, not
    just exist as a function that works when called directly."""

    def setUp(self):
        frappe.set_user("Administrator")
        _delete_project(TEST_KEY)
        self.project = create_project(
            project_name="Automation Security Test",
            key=TEST_KEY,
            workflow_states=json.dumps([{"name": "To Do", "color": "#6B7280", "category": "open"}]),
            issue_types=json.dumps([{"name": "Task", "color": "#0B6BCB", "icon": "CheckSquare"}]),
        )["name"]

    def tearDown(self):
        _delete_project(TEST_KEY)

    def test_real_save_enforces_project_admin_requirement(self):
        # Administrator triggers is_instance_admin's bypass, so this isolates
        # the branch a genuine non-admin user would hit on a real save.
        with patch.object(access, "is_instance_admin", return_value=False), \
             patch.object(access, "has_at_least", return_value=False):
            with self.assertRaises(frappe.PermissionError):
                frappe.get_doc({
                    "doctype": "BP Automation Rule",
                    "rule_name": "Unauthorized rule attempt",
                    "scope": "project",
                    "project": self.project,
                    "trigger_doctype": "BP Task",
                    "trigger_event": "task.created",
                    "actions": json.dumps([{"type": "Change Status", "config": {"status": "Done"}}]),
                    "is_active": 1,
                }).insert(ignore_permissions=True)

    def test_real_save_succeeds_for_project_admin(self):
        with patch.object(access, "is_instance_admin", return_value=False), \
             patch.object(access, "has_at_least", return_value=True):
            doc = frappe.get_doc({
                "doctype": "BP Automation Rule",
                "rule_name": "Authorized rule",
                "scope": "project",
                "project": self.project,
                "trigger_doctype": "BP Task",
                "trigger_event": "task.created",
                "actions": json.dumps([{"type": "Change Status", "config": {"status": "Done"}}]),
                "is_active": 1,
            }).insert(ignore_permissions=True)
        self.assertTrue(doc.name)
