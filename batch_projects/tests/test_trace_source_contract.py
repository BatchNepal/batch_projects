import unittest

import frappe


class TestTraceSourceContract(unittest.TestCase):
    def setUp(self):
        self._old_depth = frappe.flags.get("bp_automation_depth")

    def tearDown(self):
        if self._old_depth is None:
            frappe.flags.pop("bp_automation_depth", None)
        else:
            frappe.flags.bp_automation_depth = self._old_depth

    def _activity(self, *, source=None):
        doc = frappe.new_doc("BP Activity")
        doc.task = "TRACE-TASK"
        doc.action_type = "Comment"
        doc.user = frappe.session.user
        if source is not None:
            doc.source = source
        doc.before_insert()
        return doc

    def _audit(self, event, *, source=None):
        doc = frappe.new_doc("BP Audit Log")
        doc.event = event
        doc.actor = "gateway:test"
        if source is not None:
            doc.source = source
        doc.before_insert()
        return doc

    def test_user_activity_defaults_to_user_source(self):
        frappe.flags.bp_automation_depth = 0
        self.assertEqual(self._activity().source, "user")

    def test_automation_activity_defaults_to_automation_source(self):
        frappe.flags.bp_automation_depth = 2
        self.assertEqual(self._activity().source, "automation")

    def test_explicit_activity_source_is_preserved(self):
        frappe.flags.bp_automation_depth = 2
        self.assertEqual(self._activity(source="system").source, "system")

    def test_audit_source_is_inferred_from_event_namespace(self):
        cases = {
            "billing.checkout": "billing",
            "automation.rule_fired": "automation",
            "workspace.settings_updated": "gateway",
        }
        for event, expected in cases.items():
            with self.subTest(event=event):
                self.assertEqual(self._audit(event).source, expected)

    def test_explicit_audit_source_is_preserved(self):
        self.assertEqual(
            self._audit("workspace.settings_updated", source="system").source,
            "system",
        )
