"""Regression tests for strict FX handling in batch invoice preview."""

import unittest
from unittest.mock import patch

import frappe

from batch_projects.api import erp_link


class TestBatchInvoicePreviewFX(unittest.TestCase):
    def _project(self, *, currency="USD"):
        return frappe._dict({
            "name": "BP-FX-TEST",
            "project_name": "FX Test Project",
            "client": "TEST-CUSTOMER",
            "company": "TEST-COMPANY",
            "currency": currency,
            "hourly_rate": 0,
            "erpnext_project": "ERP-FX-TEST",
        })

    def _row(self, *, billing_rate, billing_hours=8, currency="USD"):
        return frappe._dict({
            "erp_project": "ERP-FX-TEST",
            "hours": billing_hours,
            "billing_hours": billing_hours,
            "billing_rate": billing_rate,
            "timesheet_currency": currency,
        })

    def _candidates(self, project, row, *, resolver_return=None, resolver_error=None):
        with (
            patch.object(erp_link, "require_feature"),
            patch.object(erp_link, "_require_system_user"),
            patch(
                "batch_projects.permissions.get_accessible_projects",
                return_value=None,
            ),
            patch.object(erp_link.frappe, "get_all", return_value=[project]),
            patch.object(erp_link.frappe.db, "sql", return_value=[row]),
            patch.object(erp_link, "_service_item", return_value=None),
            patch.object(erp_link, "_price_list_rate", return_value=0),
            patch.object(erp_link, "_resolve_invoice_currency") as resolver,
        ):
            if resolver_error is not None:
                resolver.side_effect = resolver_error
            else:
                resolver.return_value = resolver_return

            result = erp_link.get_batch_invoice_candidates()
            return result, resolver

    def test_same_currency_keeps_company_rate_without_conversion(self):
        result, resolver = self._candidates(
            self._project(currency="USD"),
            self._row(billing_rate=100, billing_hours=8),
            resolver_return=("USD", "USD", 1.0),
        )

        self.assertEqual(result[0]["projects"][0]["hours"], 8)
        self.assertEqual(result[0]["projects"][0]["amount"], 800.0)
        self.assertEqual(result[0]["total_amount"], 800.0)
        resolver.assert_called_once_with(
            "TEST-COMPANY", "TEST-CUSTOMER", None, None, "USD"
        )

    def test_foreign_currency_uses_real_resolved_fx(self):
        # Timesheet billing_rate is 6,875 NPR/hour.
        # Project/invoice currency is USD and 1 USD = 137.5 NPR.
        # Preview must therefore use 50 USD/hour, not 6,875 USD/hour.
        result, resolver = self._candidates(
            self._project(currency="USD"),
            self._row(
                billing_rate=6875,
                billing_hours=8,
                currency="NPR",
            ),
            resolver_return=("NPR", "USD", 137.5),
        )

        self.assertEqual(result[0]["projects"][0]["hours"], 8)
        self.assertEqual(result[0]["projects"][0]["amount"], 400.0)
        self.assertEqual(result[0]["total_amount"], 400.0)
        resolver.assert_called_once_with(
            "TEST-COMPANY", "TEST-CUSTOMER", None, None, "USD"
        )

    def test_unresolved_fx_fails_closed_instead_of_assuming_one_to_one(self):
        with self.assertRaisesRegex(
            frappe.ValidationError,
            "No exchange rate configured",
        ):
            self._candidates(
                self._project(currency="USD"),
                self._row(
                    billing_rate=6875,
                    billing_hours=8,
                    currency="NPR",
                ),
                resolver_error=frappe.ValidationError(
                    "No exchange rate configured for USD → NPR"
                ),
            )


if __name__ == "__main__":
    unittest.main()
