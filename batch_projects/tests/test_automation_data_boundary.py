"""Boundary tests for the gateway-only automation architecture.

These tests intentionally exercise the public Frappe adapter without running a
workflow. The adapter is allowed to read business facts and commit final
business mutations only; workflow/runtime semantics belong to bp-gateway.

Run with:
    bench run-tests --module batch_projects.tests.test_automation_data_boundary
"""

from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from batch_projects.api import automation_data


class _FakeTask:
    def __init__(self):
        self.name = "TASK-1"
        self.assignees = [SimpleNamespace(user="old@example.com")]
        self.labels = '["old-label"]'
        self.saved = False

    def set(self, fieldname, value):
        setattr(self, fieldname, value)

    def append(self, fieldname, value):
        rows = getattr(self, fieldname)
        rows.append(SimpleNamespace(**value))

    def save(self, **_):
        self.saved = True
        return self


class TestAutomationFinalDataBoundary(FrappeTestCase):
    def _valid_update(self, **extra):
        mutation = {
            "operation": "task.update",
            "idempotency_key": "bpn_" + "a" * 64,
            "task": "TASK-1",
            "fields": {"status": "Done"},
        }
        mutation.update(extra)
        return mutation

    def test_runtime_fields_are_rejected_explicitly(self):
        for field in (
            "workflow", "workflow_id", "node_type", "rule", "config",
            "conditions", "branch", "retry", "attempt", "wait",
            "execution_state", "ready_queue", "outputs", "provider_response",
        ):
            with self.subTest(field=field):
                with self.assertRaises(frappe.ValidationError) as raised:
                    automation_data._validate_envelope(self._valid_update(**{field: "forbidden"}))
                self.assertIn("runtime data", str(raised.exception).lower())

    def test_unknown_non_runtime_fields_are_rejected(self):
        with self.assertRaises(frappe.ValidationError):
            automation_data._validate_envelope(self._valid_update(surprise="value"))

    def test_idempotency_key_is_capped_for_frappe_document_name(self):
        good = self._valid_update(idempotency_key="k" * automation_data._MAX_IDEMPOTENCY_KEY_LEN)
        automation_data._validate_envelope(good)

        bad = self._valid_update(idempotency_key="k" * (automation_data._MAX_IDEMPOTENCY_KEY_LEN + 1))
        with self.assertRaises(frappe.ValidationError):
            automation_data._validate_envelope(bad)

    def test_assignee_mutation_sets_exact_final_state_instead_of_merging(self):
        task = _FakeTask()
        mutation = {
            "task": task.name,
            "users": ["new@example.com"],
        }
        with patch.object(automation_data, "_task", return_value=task), patch.object(
            frappe.db, "get_value", return_value="New User"
        ):
            status, result = automation_data._apply_task_assignees(mutation)

        self.assertEqual(status, "applied")
        self.assertEqual([row.user for row in task.assignees], ["new@example.com"])
        self.assertNotIn("old@example.com", [row.user for row in task.assignees])
        self.assertTrue(task.saved)
        self.assertEqual(result["assignees"], ["new@example.com"])

    def test_label_mutation_sets_exact_final_state_instead_of_merging(self):
        task = _FakeTask()
        with patch.object(automation_data, "_task", return_value=task):
            status, result = automation_data._apply_task_labels({
                "task": task.name,
                "labels": ["new-label"],
            })

        self.assertEqual(status, "applied")
        self.assertEqual(automation_data._parse_labels(task.labels), ["new-label"])
        self.assertNotIn("old-label", automation_data._parse_labels(task.labels))
        self.assertEqual(result["labels"], ["new-label"])

    def test_task_create_refuses_to_invent_gateway_defaults(self):
        base = {
            "project": "PROJ-1",
            "title": "Created by gateway",
            "status": "Open",
            "task_type": "Task",
            "priority": "Medium",
            "assignees": [],
        }
        with patch.object(frappe.db, "exists", return_value=True):
            for field in ("status", "task_type", "priority"):
                mutation = dict(base)
                mutation.pop(field)
                with self.subTest(field=field), self.assertRaises(frappe.ValidationError):
                    automation_data._apply_task_create(mutation)

    def test_email_refuses_to_invent_subject(self):
        with self.assertRaises(frappe.ValidationError):
            automation_data._apply_email({
                "recipients": ["user@example.com"],
                "message": "Final message",
            })


if __name__ == "__main__":
    import unittest
    unittest.main()
