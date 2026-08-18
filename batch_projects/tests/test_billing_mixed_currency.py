"""Regression tests for explicit mixed-currency batch invoicing."""

import unittest
from pathlib import Path
from unittest.mock import patch

import frappe

from batch_projects.api import erp_link


APP_ROOT = Path(__file__).resolve().parents[2]


def project(
    name,
    *,
    currency,
    hourly_rate,
    erp_project,
):
    return frappe._dict({
        "name": name,
        "project_name": name,
        "client": "TEST-CUSTOMER",
        "company": "TEST-COMPANY",
        "currency": currency,
        "hourly_rate": hourly_rate,
        "erpnext_project": erp_project,
    })


def invoice_row(
    erp_project,
    *,
    hours=1,
):
    return frappe._dict({
        "name": f"TSD-{erp_project}",
        "timesheet": f"TS-{erp_project}",
        "bp_task": None,
        "hours": hours,
        "billing_hours": hours,
        "billing_rate": 0,
        "billing_amount": 0,
        "timesheet_currency": "NPR",
        "activity_type": "Project Work",
        "description": "Mixed-currency regression",
        "from_time": "2026-08-19 09:00:00",
        "to_time": "2026-08-19 10:00:00",
        "project_name": erp_project,
        "erp_project": erp_project,
    })


class _FakeSalesInvoice:
    def __init__(self, name="SINV-MIXED"):
        self.flags = frappe._dict()
        self.items = []
        self.timesheets = []
        self.name = name
        self.grand_total = 0.0

    def append(self, table, value):
        row = frappe._dict(value)
        getattr(self, table).append(row)
        return row

    def run_method(self, method):
        if method != "set_missing_values":
            raise AssertionError(
                f"unexpected Sales Invoice method: {method}"
            )

    def insert(self, ignore_permissions=False):
        if not ignore_permissions:
            raise AssertionError(
                "Sales Invoice must use upstream BP authorization"
            )

        self.grand_total = round(
            sum(
                float(item.qty) * float(item.rate)
                for item in self.items
            ),
            2,
        )

        return self


class TestBillingMixedCurrency(unittest.TestCase):
    def _mixed_projects(self):
        return {
            "BP-EUR": project(
                "BP-EUR",
                currency="EUR",
                hourly_rate=50,
                erp_project="ERP-EUR",
            ),
            "BP-USD": project(
                "BP-USD",
                currency="USD",
                hourly_rate=60,
                erp_project="ERP-USD",
            ),
        }

    def test_mixed_projects_require_explicit_target_before_sql(self):
        projects = self._mixed_projects()

        with (
            patch.object(
                erp_link,
                "_check_permission",
            ),
            patch(
                "batch_projects.access.require_capability",
            ),
            patch.object(
                erp_link,
                "require_feature",
            ),
            patch.object(
                erp_link.frappe,
                "get_doc",
                side_effect=lambda doctype, name: projects[name],
            ),
            patch.object(
                erp_link.frappe.db,
                "sql",
            ) as sql,
            patch.object(
                erp_link.frappe,
                "new_doc",
            ) as new_doc,
        ):
            with self.assertRaisesRegex(
                frappe.ValidationError,
                "explicit invoice currency",
            ):
                erp_link.generate_invoice(
                    ["BP-EUR", "BP-USD"]
                )

        sql.assert_not_called()
        new_doc.assert_not_called()

    def test_conversion_rate_alone_does_not_choose_mixed_target(self):
        projects = self._mixed_projects()

        with (
            patch.object(
                erp_link,
                "_check_permission",
            ),
            patch(
                "batch_projects.access.require_capability",
            ),
            patch.object(
                erp_link,
                "require_feature",
            ),
            patch.object(
                erp_link.frappe,
                "get_doc",
                side_effect=lambda doctype, name: projects[name],
            ),
            patch.object(
                erp_link.frappe.db,
                "sql",
            ) as sql,
        ):
            with self.assertRaisesRegex(
                frappe.ValidationError,
                "explicit invoice currency",
            ):
                erp_link.generate_invoice(
                    ["BP-EUR", "BP-USD"],
                    conversion_rate=137.5,
                )

        sql.assert_not_called()

    def test_mixed_projects_convert_into_explicit_target_with_or_without_fx_override(self):
        projects = self._mixed_projects()

        for explicit_fx in (None, 137.5):
            with self.subTest(
                explicit_fx=explicit_fx,
            ):
                invoice = _FakeSalesInvoice(
                    "SINV-AUTO-FX"
                    if explicit_fx is None
                    else "SINV-EXPLICIT-FX"
                )

                rows = [
                    invoice_row("ERP-EUR"),
                    invoice_row("ERP-USD"),
                ]

                seen_target = []

                def resolve_currency(
                    company,
                    customer,
                    currency,
                    conversion_rate,
                    project_currency=None,
                ):
                    self.assertEqual(
                        company,
                        "TEST-COMPANY",
                    )
                    self.assertEqual(
                        customer,
                        "TEST-CUSTOMER",
                    )

                    if currency == "USD":
                        self.assertIsNone(
                            project_currency
                        )
                        self.assertEqual(
                            conversion_rate,
                            explicit_fx,
                        )
                        seen_target.append(currency)
                        return (
                            "NPR",
                            "USD",
                            137.5,
                        )

                    if currency == "EUR":
                        self.assertIsNone(
                            conversion_rate
                        )
                        self.assertIsNone(
                            project_currency
                        )
                        return (
                            "NPR",
                            "EUR",
                            150.0,
                        )

                    raise AssertionError(
                        f"unexpected currency resolution: {currency!r}"
                    )

                with (
                    patch.object(
                        erp_link,
                        "_check_permission",
                    ),
                    patch(
                        "batch_projects.access.require_capability",
                    ),
                    patch.object(
                        erp_link,
                        "require_feature",
                    ),
                    patch.object(
                        erp_link.frappe,
                        "get_doc",
                        side_effect=lambda doctype, name: projects[name],
                    ),
                    patch.object(
                        erp_link.frappe.db,
                        "sql",
                        return_value=rows,
                    ),
                    patch.object(
                        erp_link,
                        "guard_timesheet_details",
                    ),
                    patch.object(
                        erp_link,
                        "_service_item",
                        return_value=None,
                    ),
                    patch.object(
                        erp_link,
                        "_price_list_rate",
                        return_value=None,
                    ),
                    patch.object(
                        erp_link,
                        "_resolve_invoice_currency",
                        side_effect=resolve_currency,
                    ),
                    patch.object(
                        erp_link.frappe,
                        "get_all",
                        return_value=[],
                    ),
                    patch.object(
                        erp_link.frappe.db,
                        "get_value",
                        return_value="Income - TEST",
                    ),
                    patch.object(
                        erp_link.frappe,
                        "new_doc",
                        return_value=invoice,
                    ),
                    patch.object(
                        erp_link.frappe.share,
                        "add_docshare",
                    ),
                    patch.object(
                        erp_link.frappe.db,
                        "commit",
                    ),
                ):
                    result = (
                        erp_link.generate_invoice(
                            ["BP-EUR", "BP-USD"],
                            currency="USD",
                            conversion_rate=explicit_fx,
                        )
                    )

                # EUR project:
                # 50 EUR/h * 150 NPR/EUR / 137.5 NPR/USD
                # = 54.545... USD -> financial row rounds to 54.55.
                amounts = {
                    p["bp_project"]: p["amount"]
                    for p in result["projects"]
                }

                self.assertEqual(
                    amounts,
                    {
                        "BP-EUR": 54.55,
                        "BP-USD": 60.0,
                    },
                )

                self.assertEqual(
                    invoice.company,
                    "TEST-COMPANY",
                )

                self.assertEqual(
                    invoice.currency,
                    "USD",
                )

                self.assertEqual(
                    invoice.conversion_rate,
                    137.5,
                )

                self.assertEqual(
                    result["grand_total"],
                    114.55,
                )

                self.assertEqual(
                    seen_target,
                    ["USD"],
                )

    def test_explicit_conversion_rate_must_be_finite_and_positive(self):
        invalid = (
            0,
            "0",
            -1,
            "-2.5",
            "nan",
            "inf",
            "-inf",
        )

        with patch.object(
            erp_link.frappe,
            "get_cached_value",
            return_value="NPR",
        ):
            for value in invalid:
                with self.subTest(value=value):
                    with self.assertRaisesRegex(
                        frappe.ValidationError,
                        "finite number greater than zero",
                    ):
                        erp_link._resolve_invoice_currency(
                            "TEST-COMPANY",
                            "TEST-CUSTOMER",
                            "USD",
                            value,
                        )

    def test_company_currency_rejects_non_one_explicit_rate(self):
        with patch.object(
            erp_link.frappe,
            "get_cached_value",
            return_value="NPR",
        ):
            with self.assertRaisesRegex(
                frappe.ValidationError,
                "conversion rate must be 1",
            ):
                erp_link._resolve_invoice_currency(
                    "TEST-COMPANY",
                    "TEST-CUSTOMER",
                    "NPR",
                    2,
                )

    def test_explicit_target_can_use_erpnext_fx_when_override_omitted(self):
        with (
            patch.object(
                erp_link.frappe,
                "get_cached_value",
                return_value="NPR",
            ),
            patch(
                "erpnext.setup.utils.get_exchange_rate",
                return_value=137.5,
            ) as exchange,
        ):
            result = (
                erp_link._resolve_invoice_currency(
                    "TEST-COMPANY",
                    "TEST-CUSTOMER",
                    "USD",
                    None,
                )
            )

        self.assertEqual(
            result,
            ("NPR", "USD", 137.5),
        )

        exchange.assert_called_once()

    def test_mixed_preview_exposes_currency_totals_without_fake_sum(self):
        projects = [
            project(
                "BP-EUR",
                currency="EUR",
                hourly_rate=50,
                erp_project="ERP-EUR",
            ),
            project(
                "BP-USD",
                currency="USD",
                hourly_rate=60,
                erp_project="ERP-USD",
            ),
        ]

        rows = [
            frappe._dict({
                "erp_project": "ERP-EUR",
                "hours": 1,
                "billing_hours": 1,
                "billing_rate": 0,
                "timesheet_currency": "NPR",
            }),
            frappe._dict({
                "erp_project": "ERP-USD",
                "hours": 2,
                "billing_hours": 2,
                "billing_rate": 0,
                "timesheet_currency": "NPR",
            }),
        ]

        def resolve_currency(
            company,
            customer,
            currency,
            conversion_rate,
            project_currency=None,
        ):
            self.assertEqual(
                company,
                "TEST-COMPANY",
            )

            if project_currency == "EUR":
                return (
                    "NPR",
                    "EUR",
                    150.0,
                )

            if project_currency == "USD":
                return (
                    "NPR",
                    "USD",
                    137.5,
                )

            raise AssertionError(
                f"unexpected preview project currency: {project_currency!r}"
            )

        with (
            patch.object(
                erp_link,
                "require_feature",
            ),
            patch.object(
                erp_link,
                "_require_system_user",
            ),
            patch(
                "batch_projects.permissions.get_accessible_projects",
                return_value=None,
            ),
            patch.object(
                erp_link.frappe,
                "get_all",
                return_value=projects,
            ),
            patch.object(
                erp_link.frappe.db,
                "sql",
                return_value=rows,
            ),
            patch.object(
                erp_link,
                "_service_item",
                return_value=None,
            ),
            patch.object(
                erp_link,
                "_price_list_rate",
                return_value=None,
            ),
            patch.object(
                erp_link,
                "_resolve_invoice_currency",
                side_effect=resolve_currency,
            ),
        ):
            result = (
                erp_link.get_batch_invoice_candidates()
            )

        self.assertEqual(
            len(result),
            1,
        )

        entry = result[0]

        self.assertTrue(
            entry["mixed_currency"]
        )

        self.assertIsNone(
            entry["total_amount"]
        )

        self.assertEqual(
            entry["currency_totals"],
            [
                {
                    "currency": "EUR",
                    "amount": 50.0,
                },
                {
                    "currency": "USD",
                    "amount": 120.0,
                },
            ],
        )

        self.assertEqual(
            entry["total_hours"],
            3.0,
        )

    def test_batch_ui_requires_target_without_fake_mixed_total(self):
        page = (
            APP_ROOT
            / "frontend"
            / "src"
            / "pages"
            / "BatchInvoicing.vue"
        ).read_text()

        self.assertIn(
            "Multiple currencies",
            page,
        )

        self.assertIn(
            "selectedCurrencyTotals(c)",
            page,
        )

        self.assertIn(
            'label="Invoice currency"',
            page,
        )

        self.assertIn(
            "confirm.mixed && !confirm.overrideCurrency.trim()",
            page,
        )

        self.assertIn(
            "currency: confirm.overrideCurrency.trim() || undefined",
            page,
        )

        self.assertNotIn(
            "busy === batchKey(c) || mixedSelected(c)",
            page,
        )


if __name__ == "__main__":
    unittest.main()
