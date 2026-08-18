"""Regression tests for authoritative billing-hour semantics.

ERPNext v15 populates billing_hours from hours during normal Timesheet
validation. Once rows reach BatchProjects financial code, the persisted
billing_hours value is therefore authoritative and must never be replaced
because Python considers zero falsy.
"""

import inspect
import unittest

import frappe

from batch_projects.api import erp_link


class TestBillingHoursInvariant(unittest.TestCase):
    def _row(self, billing_hours_marker="__missing__", hours=8):
        values = {"hours": hours}
        if billing_hours_marker != "__missing__":
            values["billing_hours"] = billing_hours_marker
        return frappe._dict(values)

    def test_missing_does_not_fall_back_to_worked_hours(self):
        row = self._row(hours=8)
        self.assertEqual(erp_link._authoritative_billing_hours(row), 0)

    def test_explicit_zero_remains_zero(self):
        row = self._row(0, hours=8)
        self.assertEqual(erp_link._authoritative_billing_hours(row), 0)

    def test_fractional_billing_hours_are_preserved(self):
        row = self._row(2.5, hours=8)
        self.assertEqual(erp_link._authoritative_billing_hours(row), 2.5)

    def test_positive_billing_hours_are_preserved(self):
        row = self._row(8, hours=10)
        self.assertEqual(erp_link._authoritative_billing_hours(row), 8)

    def test_zero_hours_do_not_require_a_billing_rate(self):
        row = self._row(0, hours=8)
        self.assertFalse(erp_link._requires_billing_rate(row))

    def test_nonzero_hours_require_a_billing_rate(self):
        row = self._row(2.5, hours=8)
        self.assertTrue(erp_link._requires_billing_rate(row))

    def test_financial_module_has_no_worked_hours_fallback(self):
        source = inspect.getsource(erp_link)
        self.assertNotIn("billing_hours or r.hours", source)
        self.assertNotIn("billing_hours or row.hours", source)
