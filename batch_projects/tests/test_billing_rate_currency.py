"""Regression tests for typed billing-rate currency semantics."""

import unittest
from unittest.mock import patch

import frappe

from batch_projects.api import erp_link, timers


class TestBillingRateCurrency(unittest.TestCase):
    def test_currency_to_company_fx_same_currency_is_identity(self):
        with patch(
            "erpnext.setup.utils.get_exchange_rate"
        ) as get_exchange_rate:
            result = erp_link._currency_to_company_fx(
                "TEST-COMPANY", "NPR", company_currency="NPR"
            )

        self.assertEqual(result, 1.0)
        get_exchange_rate.assert_not_called()

    def test_currency_to_company_fx_uses_cache(self):
        cache = {}
        with patch(
            "erpnext.setup.utils.get_exchange_rate",
            return_value=150.0,
        ) as get_exchange_rate:
            first = erp_link._currency_to_company_fx(
                "TEST-COMPANY", "EUR",
                company_currency="NPR", fx_cache=cache,
            )
            second = erp_link._currency_to_company_fx(
                "TEST-COMPANY", "EUR",
                company_currency="NPR", fx_cache=cache,
            )

        self.assertEqual(first, 150.0)
        self.assertEqual(second, 150.0)
        self.assertEqual(cache[("TEST-COMPANY", "EUR")], 150.0)
        get_exchange_rate.assert_called_once()

    def test_currency_to_company_fx_missing_rate_fails_generically(self):
        with patch(
            "erpnext.setup.utils.get_exchange_rate",
            return_value=0,
        ):
            with self.assertRaisesRegex(
                frappe.ValidationError,
                "No exchange rate configured for EUR → NPR",
            ):
                erp_link._currency_to_company_fx(
                    "TEST-COMPANY", "EUR", company_currency="NPR"
                )

    def test_price_list_rate_preserves_item_price_currency(self):
        with patch.object(
            erp_link.frappe.db,
            "get_value",
            side_effect=[
                "CONTRACT-PL",
                frappe._dict({
                    "price_list_rate": 125,
                    "currency": "EUR",
                }),
            ],
        ):
            rate = erp_link._price_list_rate(
                "TEST-CUSTOMER",
                "SERVICE",
            )

        self.assertEqual(rate.rate, 125)
        self.assertEqual(rate.currency, "EUR")

    def test_row_company_rate_converts_to_invoice_currency(self):
        rate = erp_link._effective_billing_rate(
            row_rate=6875,
            row_currency="NPR",
            project_rate=0,
            project_currency="USD",
            client_rate=None,
            company_currency="NPR",
            target_currency="USD",
            company="TEST-COMPANY",
            customer="TEST-CUSTOMER",
            target_to_company=137.5,
        )
        self.assertEqual(rate, 50)

    def test_row_rate_uses_parent_timesheet_currency(self):
        with patch.object(
            erp_link,
            "_currency_to_company_fx",
            return_value=150.0,
        ):
            rate = erp_link._effective_billing_rate(
                row_rate=50,
                row_currency="EUR",
                project_rate=0,
                project_currency="USD",
                client_rate=None,
                company_currency="NPR",
                target_currency="USD",
                company="TEST-COMPANY",
                customer="TEST-CUSTOMER",
                target_to_company=137.5,
            )

        self.assertAlmostEqual(
            rate,
            50 * 150 / 137.5,
            places=6,
        )

    def test_nonzero_row_without_timesheet_currency_fails_closed(self):
        with self.assertRaisesRegex(
            frappe.ValidationError,
            "no source currency",
        ):
            erp_link._effective_billing_rate(
                row_rate=50,
                row_currency=None,
                project_rate=0,
                project_currency="USD",
                client_rate=None,
                company_currency="NPR",
                target_currency="USD",
                company="TEST-COMPANY",
                customer="TEST-CUSTOMER",
                target_to_company=137.5,
            )

    def test_project_rate_same_currency_is_identity(self):
        rate = erp_link._effective_billing_rate(
            row_rate=0,
            row_currency=None,
            project_rate=50,
            project_currency="USD",
            client_rate=None,
            company_currency="NPR",
            target_currency="USD",
            company="TEST-COMPANY",
            customer="TEST-CUSTOMER",
            target_to_company=137.5,
        )
        self.assertEqual(rate, 50)

    def test_project_rate_converts_for_explicit_invoice_override(self):
        with patch.object(
            erp_link,
            "_currency_to_company_fx",
            return_value=150.0,
        ):
            rate = erp_link._effective_billing_rate(
                row_rate=0,
                row_currency=None,
                project_rate=50,
                project_currency="EUR",
                client_rate=None,
                company_currency="NPR",
                target_currency="USD",
                company="TEST-COMPANY",
                customer="TEST-CUSTOMER",
                target_to_company=137.5,
            )

        self.assertAlmostEqual(
            rate,
            50 * 150 / 137.5,
            places=6,
        )

    def test_client_item_price_same_currency_is_identity(self):
        rate = erp_link._effective_billing_rate(
            row_rate=0,
            row_currency=None,
            project_rate=0,
            project_currency="USD",
            client_rate=frappe._dict({
                "rate": 50,
                "currency": "USD",
            }),
            company_currency="NPR",
            target_currency="USD",
            company="TEST-COMPANY",
            customer="TEST-CUSTOMER",
            target_to_company=137.5,
        )

        self.assertEqual(rate, 50)

    def test_client_item_price_converts_from_its_own_currency(self):
        with patch.object(
            erp_link,
            "_currency_to_company_fx",
            return_value=150.0,
        ):
            rate = erp_link._effective_billing_rate(
                row_rate=0,
                row_currency=None,
                project_rate=0,
                project_currency="USD",
                client_rate=frappe._dict({
                    "rate": 50,
                    "currency": "EUR",
                }),
                company_currency="NPR",
                target_currency="USD",
                company="TEST-COMPANY",
                customer="TEST-CUSTOMER",
                target_to_company=137.5,
            )

        self.assertAlmostEqual(
            rate,
            50 * 150 / 137.5,
            places=6,
        )

    def test_missing_source_fx_fails_closed(self):
        with patch.object(
            erp_link,
            "_currency_to_company_fx",
            side_effect=frappe.ValidationError(
                "No exchange rate configured for EUR → NPR"
            ),
        ):
            with self.assertRaisesRegex(
                frappe.ValidationError,
                "No exchange rate configured",
            ):
                erp_link._effective_billing_rate(
                    row_rate=0,
                    row_currency=None,
                    project_rate=50,
                    project_currency="EUR",
                    client_rate=None,
                    company_currency="NPR",
                    target_currency="USD",
                    company="TEST-COMPANY",
                    customer="TEST-CUSTOMER",
                    target_to_company=137.5,
                )

    def test_batch_preview_converts_client_price_list_rate(self):
        project = frappe._dict({
            "name": "BP-RATE-TEST",
            "project_name": "Rate Test",
            "client": "TEST-CUSTOMER",
            "company": "TEST-COMPANY",
            "currency": "USD",
            "hourly_rate": 0,
            "erpnext_project": "ERP-RATE-TEST",
        })
        row = frappe._dict({
            "erp_project": "ERP-RATE-TEST",
            "hours": 8,
            "billing_hours": 8,
            "billing_rate": 0,
            "timesheet_currency": "NPR",
        })

        with (
            patch.object(erp_link, "require_feature"),
            patch.object(erp_link, "_require_system_user"),
            patch(
                "batch_projects.permissions.get_accessible_projects",
                return_value=None,
            ),
            patch.object(
                erp_link.frappe,
                "get_all",
                return_value=[project],
            ),
            patch.object(
                erp_link.frappe.db,
                "sql",
                return_value=[row],
            ),
            patch.object(
                erp_link,
                "_service_item",
                return_value="SERVICE",
            ),
            patch.object(
                erp_link,
                "_price_list_rate",
                return_value=frappe._dict({
                    "rate": 50,
                    "currency": "EUR",
                }),
            ),
            patch.object(
                erp_link,
                "_resolve_invoice_currency",
                return_value=("NPR", "USD", 137.5),
            ),
            patch.object(
                erp_link,
                "_currency_to_company_fx",
                return_value=150.0,
            ),
        ):
            result = erp_link.get_batch_invoice_candidates()

        self.assertEqual(len(result), 1)
        self.assertEqual(
            result[0]["projects"][0]["currency"],
            "USD",
        )
        self.assertEqual(
            result[0]["projects"][0]["amount"],
            436.36,
        )

    def test_timer_timesheet_is_explicitly_company_currency(self):
        sentinel = object()

        with (
            patch.object(
                timers.frappe,
                "get_cached_value",
                return_value="NPR",
            ),
            patch.object(
                timers.frappe.db,
                "get_value",
                return_value=None,
            ) as get_value,
            patch.object(
                timers.frappe,
                "get_doc",
                return_value=sentinel,
            ) as get_doc,
        ):
            result = timers._get_or_create_draft_timesheet(
                "user@example.com",
                "EMP-TEST",
                "TEST-COMPANY",
                "ERP-PROJECT",
            )

        self.assertIs(result, sentinel)

        filters = get_value.call_args.args[1]
        self.assertEqual(filters["currency"], "NPR")
        self.assertEqual(filters["exchange_rate"], 1.0)

        doc = get_doc.call_args.args[0]
        self.assertEqual(doc["currency"], "NPR")
        self.assertEqual(doc["exchange_rate"], 1.0)

    def test_timer_missing_fx_keeps_hours_price_unresolved(self):
        with (
            patch.object(
                timers.frappe,
                "get_cached_value",
                return_value="NPR",
            ),
            patch(
                "erpnext.setup.utils.get_exchange_rate",
                return_value=0,
            ),
        ):
            rate = timers._rate_in_company_currency(
                50,
                "USD",
                "TEST-COMPANY",
            )

        self.assertEqual(rate, 0)

    def test_timer_same_currency_rate_remains_typed(self):
        with patch.object(
            timers.frappe,
            "get_cached_value",
            return_value="NPR",
        ):
            rate = timers._rate_in_company_currency(
                100,
                "NPR",
                "TEST-COMPANY",
            )

        self.assertEqual(rate, 100)


if __name__ == "__main__":
    unittest.main()
