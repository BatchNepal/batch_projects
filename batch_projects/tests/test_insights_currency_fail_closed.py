"""Fail-closed edge cases for #41 analytics currency provenance."""

import unittest
from unittest.mock import patch

import frappe

from batch_projects.api import insights_data


class TestProjectMoneyCurrencyFailClosed(unittest.TestCase):
    def _project(self):
        return frappe._dict({
            "name": "BP-P1",
            "project_name": "Project One",
            "company": "ACME",
            "currency": "USD",
            "erpnext_project": "ERP-P1",
            "source_sales_order": "SO-001",
            "hourly_rate": 10,
            "budget_amount": 100,
        })

    def _get_value(self, *, so_company="ACME", so_currency="USD", conversion_rate=130):
        def get_value(doctype, name, fieldname=None, **kwargs):
            if doctype == "Project" and name == "ERP-P1":
                self.assertEqual(fieldname, "company")
                return "ACME"
            if doctype == "Sales Order" and name == "SO-001":
                self.assertEqual(fieldname, ["company", "currency", "conversion_rate"])
                self.assertTrue(kwargs.get("as_dict"))
                return frappe._dict({
                    "company": so_company,
                    "currency": so_currency,
                    "conversion_rate": conversion_rate,
                })
            raise AssertionError((doctype, name, fieldname, kwargs))

        return get_value

    def test_source_sales_order_company_must_match_reporting_company(self):
        with (
            patch.object(
                insights_data.frappe.db,
                "get_value",
                side_effect=self._get_value(so_company="OTHER-CO"),
            ),
            patch.object(insights_data.frappe, "get_cached_value", return_value="NPR"),
        ):
            with self.assertRaisesRegex(frappe.ValidationError, "source Sales Order.*company"):
                insights_data._project_money_currency_context(self._project())

    def test_source_sales_order_currency_must_match_project_currency(self):
        with (
            patch.object(
                insights_data.frappe.db,
                "get_value",
                side_effect=self._get_value(so_currency="EUR"),
            ),
            patch.object(insights_data.frappe, "get_cached_value", return_value="NPR"),
        ):
            with self.assertRaisesRegex(frappe.ValidationError, "source Sales Order.*currency"):
                insights_data._project_money_currency_context(self._project())

    def test_source_sales_order_conversion_rate_must_be_positive_and_finite(self):
        for bad_rate in (0, -1, float("inf"), float("nan")):
            with self.subTest(conversion_rate=bad_rate):
                with (
                    patch.object(
                        insights_data.frappe.db,
                        "get_value",
                        side_effect=self._get_value(conversion_rate=bad_rate),
                    ),
                    patch.object(insights_data.frappe, "get_cached_value", return_value="NPR"),
                ):
                    with self.assertRaisesRegex(frappe.ValidationError, "conversion rate"):
                        insights_data._project_money_currency_context(self._project())


if __name__ == "__main__":
    unittest.main()
