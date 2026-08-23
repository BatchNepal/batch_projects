"""Contract coverage for the Frappe endpoints required by bp-gateway Runtime V2."""

import json
import unittest
from pathlib import Path
from unittest.mock import patch

import frappe

from batch_projects.api import (
    automation,
    automation_data,
    automation_definitions,
    automation_permissions,
    automation_webhooks,
)
from batch_projects.batch_projects.doctype.bp_automation_rule.bp_automation_rule import (
    automation_rule_definition_hash,
)


class TestGatewayServiceBoundary(unittest.TestCase):
    """The session user must be swapped with ``patch.dict``, never ``patch.object``.

    ``frappe.session`` proxies a ``frappe._dict``, which declares ``__slots__ = ()``
    and ``__getattr__ = dict.get``.  Reading ``.__dict__`` off it therefore returns
    ``None`` instead of a mapping, and ``mock._patch.get_original()`` -- which does
    ``target.__dict__[name]`` -- dies with "'NoneType' object is not subscriptable"
    before the test body ever runs.  Patching the underlying dict entry sidesteps it.
    """

    def test_browser_session_is_rejected(self):
        with patch.object(frappe, "get_request_header", return_value=""), patch.dict(
            frappe.local.session, {"user": "Administrator"}
        ), self.assertRaises(frappe.PermissionError):
            automation_data._assert_gateway_service_caller()

    def test_token_user_requires_system_manager(self):
        with patch.object(frappe, "get_request_header", return_value="token key:secret"), patch.dict(
            frappe.local.session, {"user": "gateway@example.com"}
        ), patch.object(frappe, "get_roles", return_value=["Projects User"]), self.assertRaises(
            frappe.PermissionError
        ):
            automation_data._assert_gateway_service_caller()

    def test_token_system_manager_is_accepted(self):
        with patch.object(frappe, "get_request_header", return_value="token key:secret"), patch.dict(
            frappe.local.session, {"user": "gateway@example.com"}
        ), patch.object(frappe, "get_roles", return_value=["System Manager"]):
            automation_data._assert_gateway_service_caller()


class TestRuntimeDefinitionContract(unittest.TestCase):
    def test_project_bucket_returns_active_rule_and_workflow_definitions(self):
        rows = {
            "BP Automation Rule": [{"name": "RULE-1"}],
            "BP Workflow": [{"name": "WF-1"}],
        }

        def fake_get_all(doctype, **_):
            return rows[doctype]

        with patch.object(automation_definitions, "_assert_gateway_service_caller"), patch.object(
            frappe, "get_all", side_effect=fake_get_all
        ) as get_all:
            result = automation_definitions.get_active(bucket="PROJ-1")

        self.assertEqual(result, {"rules": rows["BP Automation Rule"], "workflows": rows["BP Workflow"]})
        self.assertEqual(get_all.call_count, 2)
        for invocation in get_all.call_args_list:
            self.assertEqual(invocation.kwargs["filters"], {"scope": "project", "project": "PROJ-1", "is_active": 1})
        workflow_call = get_all.call_args_list[1]
        self.assertIn("automation_revision", workflow_call.kwargs["fields"])
        self.assertIn("automation_definition_hash", workflow_call.kwargs["fields"])
        rule_call = get_all.call_args_list[0]
        self.assertIn("automation_revision", rule_call.kwargs["fields"])
        self.assertIn("automation_definition_hash", rule_call.kwargs["fields"])

    def test_empty_bucket_returns_no_definitions_without_querying(self):
        with patch.object(automation_definitions, "_assert_gateway_service_caller"), patch.object(
            frappe, "get_all"
        ) as get_all:
            result = automation_definitions.get_active(bucket="")
        self.assertEqual(result, {"rules": [], "workflows": []})
        get_all.assert_not_called()


class TestStoredRuleNodeContract(unittest.TestCase):
    def test_rule_action_node_resolves_stored_action_by_index(self):
        rule = frappe._dict(
            name="RULE-1",
            is_active=1,
            scope="project",
            project="PROJ-1",
            project_filter="[]",
            actions=json.dumps(
                [
                    {"type": "Add Comment", "config": {"comment": "first"}},
                    {"type": "Set Priority", "config": {"priority": "High"}},
                ]
            ),
        )
        with patch.object(automation, "_assert_service_caller"), patch(
            "batch_projects.entitlements.is_feature_enabled", return_value=True
        ), patch.object(frappe.db, "exists", return_value=True), patch.object(
            frappe, "get_doc", return_value=rule
        ), patch(
            "batch_projects.automation_security.validate_dispatch", side_effect=lambda _rule, payload: payload
        ), patch(
            "batch_projects.batch_projects.doctype.bp_automation_rule.bp_automation_rule._build_context",
            return_value={},
        ), patch(
            "batch_projects.batch_projects.doctype.bp_automation_rule.bp_automation_rule._execute",
            return_value=("Success", "priority updated"),
        ) as execute:
            result = automation.run_rule_node(
                rule="RULE-1",
                node="action-2",
                payload={"project": "PROJ-1", "task": "TASK-1"},
            )

        self.assertEqual(result["status"], "Success")
        self.assertEqual(execute.call_args.args[0]["type"], "Set Priority")

    def test_unknown_rule_action_node_fails_closed(self):
        rule = frappe._dict(
            name="RULE-1",
            is_active=1,
            scope="project",
            project="PROJ-1",
            project_filter="[]",
            actions=json.dumps([{"type": "Add Comment", "config": {"comment": "only"}}]),
        )
        with patch.object(automation, "_assert_service_caller"), patch(
            "batch_projects.entitlements.is_feature_enabled", return_value=True
        ), patch.object(frappe.db, "exists", return_value=True), patch.object(
            frappe, "get_doc", return_value=rule
        ), patch(
            "batch_projects.automation_security.validate_dispatch", side_effect=lambda _rule, payload: payload
        ):
            result = automation.run_rule_node(rule="RULE-1", node="action-9", payload={"project": "PROJ-1"})

        self.assertEqual(result["status"], "Failed")
        self.assertEqual(result["json"]["error_code"], "unknown_rule_action_node")


class TestWorkflowRevisionBinding(unittest.TestCase):
    def test_current_gateway_revision_matches_stored_workflow(self):
        workflow = frappe._dict(automation_revision=7, automation_definition_hash="hash-7")
        self.assertTrue(automation._workflow_revision_is_current(workflow, "workflow:7:hash-7"))

    def test_stale_or_malformed_gateway_revision_fails_closed(self):
        workflow = frappe._dict(automation_revision=8, automation_definition_hash="hash-8")
        for revision_id in ("workflow:7:hash-7", "workflow:8:wrong", "rule:hash-8", "bad"):
            with self.subTest(revision_id=revision_id):
                self.assertFalse(automation._workflow_revision_is_current(workflow, revision_id))

    def test_rule_revision_is_bound_too(self):
        rule = frappe._dict(automation_revision=3, automation_definition_hash="rule-hash-3")
        self.assertTrue(automation._rule_revision_is_current(rule, "rule:3:rule-hash-3"))
        self.assertFalse(automation._rule_revision_is_current(rule, "rule:2:rule-hash-2"))

    def test_rule_definition_hash_changes_with_business_semantics(self):
        base = frappe._dict(
            is_active=1,
            scope="project",
            project="PROJ-1",
            project_filter="[]",
            trigger_event="task.updated",
            trigger_config="{}",
            conditions="[]",
            actions=json.dumps([{"type": "Set Priority", "config": {"priority": "High"}}]),
            interval_seconds=0,
            first_run=None,
            action_type=None,
            action_config="{}",
        )
        changed = frappe._dict(base)
        changed.actions = json.dumps([{"type": "Set Priority", "config": {"priority": "Low"}}])
        self.assertNotEqual(automation_rule_definition_hash(base), automation_rule_definition_hash(changed))


class TestRuntimePermissionContract(unittest.TestCase):
    def test_named_user_permissions_are_batch_checked_and_fail_closed(self):
        ids = ["workflow:WF-1", "workflow:deleted"]
        with patch.object(automation_permissions, "_assert_gateway_service_caller"), patch.object(
            frappe.db, "exists", side_effect=lambda dt, name: dt == "User"
        ), patch.object(
            automation_permissions, "_definition", side_effect=[{"scope": "project", "project": "PROJ-1"}, None]
        ), patch.object(automation_permissions, "_allowed", side_effect=[True, False]):
            result = automation_permissions.check(user="member@example.com", workflow_ids=json.dumps(ids), mode="view")
        self.assertEqual(result, {ids[0]: True, ids[1]: False})

    def test_unknown_mode_is_rejected(self):
        with patch.object(automation_permissions, "_assert_gateway_service_caller"), self.assertRaises(
            frappe.ValidationError
        ):
            automation_permissions.check(user="member@example.com", workflow_ids=[], mode="write")


class TestWebhookContract(unittest.TestCase):
    def test_create_returns_per_hook_secret_once(self):
        class FakeWebhook:
            def __init__(self, values):
                self.__dict__.update(values)
                self.name = "HOOK-1"

            def insert(self, **_):
                return self

        with patch.object(automation_webhooks, "_require_webhook_admin"), patch.object(
            frappe.db, "exists", return_value=True
        ), patch.object(
            automation_webhooks.secrets, "token_urlsafe", side_effect=["route-token", "signing-secret"]
        ), patch.object(
            frappe, "get_doc", side_effect=lambda values: FakeWebhook(values)
        ), patch.object(frappe.db, "commit"):
            result = automation_webhooks.create_webhook_token("Payments", project="PROJ-1")

        self.assertEqual(result["token"], "route-token")
        self.assertEqual(result["signing_secret"], "signing-secret")
        self.assertEqual(result["signature_version"], "v2")

    def test_doctype_schema_keeps_secret_password_and_receipt_key_unique(self):
        root = Path(__file__).resolve().parents[1]
        webhook = json.loads(
            (root / "batch_projects/doctype/bp_webhook_token/bp_webhook_token.json").read_text(encoding="utf-8")
        )
        secret = next(field for field in webhook["fields"] if field.get("fieldname") == "signing_secret")
        self.assertEqual(secret["fieldtype"], "Password")
        self.assertEqual(secret["hidden"], 1)
        self.assertEqual(secret["no_copy"], 1)

        receipt = json.loads(
            (root / "batch_projects/doctype/bp_gateway_mutation_receipt/bp_gateway_mutation_receipt.json").read_text(
                encoding="utf-8"
            )
        )
        key = next(field for field in receipt["fields"] if field.get("fieldname") == "idempotency_key")
        self.assertEqual(key["unique"], 1)


if __name__ == "__main__":
    unittest.main()
