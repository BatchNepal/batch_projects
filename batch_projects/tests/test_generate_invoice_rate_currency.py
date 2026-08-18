"""Behavioral regression for typed billing-rate conversion in generate_invoice."""

import unittest
from unittest.mock import patch

import frappe

from batch_projects.api import erp_link


class _FakeSalesInvoice:
    def __init__(self):
        self.flags = frappe._dict()
        self.items = []
        self.timesheets = []
        self.name = "SINV-RATE-TEST"
        self.grand_total = 0.0

    def append(self, table, value):
        row = frappe._dict(value)
        getattr(self, table).append(row)
        return row

    def run_method(self, method):
        if method != "set_missing_values":
            raise AssertionError(f"unexpected run_method: {method}")

    def insert(self, ignore_permissions=False):
        if not ignore_permissions:
            raise AssertionError("invoice must be inserted with upstream authorization")
        self.grand_total = round(
            sum(float(row.qty) * float(row.rate) for row in self.items), 2
        )
        return self


class TestGenerateInvoiceRateCurrency(unittest.TestCase):
    def test_explicit_invoice_currency_converts_project_rate_before_draft(self):
        project = frappe._dict({
            "name": "BP-RATE-TEST",
            "project_name": "Rate Test",
            "client": "TEST-CUSTOMER",
            "company": "TEST-COMPANY",
            "currency": "EUR",
            "hourly_rate": 50,
            "erpnext_project": "ERP-RATE-TEST",
        })
        row = frappe._dict({
            "name": "TSD-RATE-TEST",
            "timesheet": "TS-RATE-TEST",
            "bp_task": None,
            "hours": 2,
            "billing_hours": 2,
            "billing_rate": 0,
            "billing_amount": 0,
            "timesheet_currency": "NPR",
            "activity_type": "Project Work",
            "description": "Typed rate test",
            "from_time": "2026-08-18 09:00:00",
            "to_time": "2026-08-18 11:00:00",
            "project_name": "Rate Test",
            "erp_project": "ERP-RATE-TEST",
        })
        invoice = _FakeSalesInvoice()

        def resolve_currency(company, customer, currency, conversion_rate,
                             project_currency=None):
            self.assertEqual(company, "TEST-COMPANY")
            self.assertEqual(customer, "TEST-CUSTOMER")

            if currency == "USD":
                self.assertEqual(conversion_rate, 137.5)
                self.assertEqual(project_currency, "EUR")
                return "NPR", "USD", 137.5

            if currency == "EUR":
                self.assertIsNone(conversion_rate)
                self.assertIsNone(project_currency)
                return "NPR", "EUR", 150.0

            raise AssertionError(
                f"unexpected currency resolution: {currency!r}, {conversion_rate!r}"
            )

        with (
            patch.object(erp_link, "_check_permission"),
            patch("batch_projects.access.require_capability"),
            patch.object(erp_link, "require_feature"),
            patch.object(erp_link.frappe, "get_doc", return_value=project),
            patch.object(
                erp_link.frappe.db,
                "sql",
                side_effect=[[row], []],
            ),
            patch.object(erp_link, "_service_item", return_value=None),
            patch.object(erp_link, "_price_list_rate", return_value=None),
            patch.object(
                erp_link,
                "_resolve_invoice_currency",
                side_effect=resolve_currency,
            ),
            patch.object(erp_link.frappe, "get_all", return_value=[]),
            patch.object(
                erp_link.frappe.db,
                "get_value",
                return_value="Income - TEST",
            ),
            patch.object(erp_link.frappe, "new_doc", return_value=invoice),
            patch.object(erp_link.frappe.share, "add_docshare"),
            patch.object(erp_link.frappe.db, "commit"),
        ):
            result = erp_link.generate_invoice(
                "BP-RATE-TEST",
                currency="USD",
                conversion_rate=137.5,
                amount=109.09,
            )

        expected_rate = round(50 * 150 / 137.5, 4)
        self.assertEqual(len(invoice.items), 1)
        self.assertEqual(invoice.items[0].qty, 2)
        self.assertEqual(invoice.items[0].rate, expected_rate)
        self.assertNotEqual(invoice.items[0].rate, 50)

        self.assertEqual(invoice.currency, "USD")
        self.assertEqual(invoice.conversion_rate, 137.5)
        self.assertEqual(result["currency"], "USD")
        self.assertEqual(result["grand_total"], 109.09)
        self.assertEqual(result["projects"][0]["amount"], 109.09)
        self.assertEqual(result["hours_invoiced"], 2)


if __name__ == "__main__":
    unittest.main()
