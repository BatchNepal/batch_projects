"""#41 regressions for project-money currency provenance in analytics."""

import unittest
from unittest.mock import patch

import frappe

from batch_projects.api import insights_data


class TestProjectMoneyCurrencyContext(unittest.TestCase):
    def _project(
        self,
        *,
        company="ACME",
        currency="NPR",
        erpnext_project="ERP-P1",
        source_sales_order="",
    ):
        return frappe._dict({
            "name": "BP-P1",
            "project_name": "Project One",
            "company": company,
            "currency": currency,
            "erpnext_project": erpnext_project,
            "source_sales_order": source_sales_order,
        })

    def test_same_currency_is_identity_without_sales_order(self):
        project = self._project(currency="NPR")

        def get_value(doctype, name, fieldname=None, **kwargs):
            if doctype == "Project" and name == "ERP-P1":
                self.assertEqual(fieldname, "company")
                return "ACME"
            raise AssertionError((doctype, name, fieldname, kwargs))

        with (
            patch.object(
                insights_data.frappe.db,
                "get_value",
                side_effect=get_value,
            ),
            patch.object(
                insights_data.frappe,
                "get_cached_value",
                return_value="NPR",
            ),
        ):
            ctx = insights_data._project_money_currency_context(project)

        self.assertEqual(ctx["company"], "ACME")
        self.assertEqual(ctx["company_currency"], "NPR")
        self.assertEqual(ctx["project_currency"], "NPR")
        self.assertEqual(ctx["project_currency_to_company_rate"], 1.0)

    def test_foreign_currency_uses_source_sales_order_snapshot(self):
        project = self._project(
            currency="USD",
            source_sales_order="SO-001",
        )

        def get_value(doctype, name, fieldname=None, **kwargs):
            if doctype == "Project" and name == "ERP-P1":
                return "ACME"
            if doctype == "Sales Order" and name == "SO-001":
                self.assertEqual(
                    fieldname,
                    ["company", "currency", "conversion_rate"],
                )
                self.assertTrue(kwargs.get("as_dict"))
                return frappe._dict({
                    "company": "ACME",
                    "currency": "USD",
                    "conversion_rate": 130,
                })
            raise AssertionError((doctype, name, fieldname, kwargs))

        with (
            patch.object(
                insights_data.frappe.db,
                "get_value",
                side_effect=get_value,
            ),
            patch.object(
                insights_data.frappe,
                "get_cached_value",
                return_value="NPR",
            ),
        ):
            ctx = insights_data._project_money_currency_context(project)

        self.assertEqual(ctx["company_currency"], "NPR")
        self.assertEqual(ctx["project_currency"], "USD")
        self.assertEqual(ctx["project_currency_to_company_rate"], 130.0)

    def test_foreign_currency_without_contract_rate_fails_closed(self):
        project = self._project(currency="USD")

        with (
            patch.object(
                insights_data.frappe.db,
                "get_value",
                return_value="ACME",
            ),
            patch.object(
                insights_data.frappe,
                "get_cached_value",
                return_value="NPR",
            ),
        ):
            with self.assertRaisesRegex(
                frappe.ValidationError,
                "source Sales Order",
            ):
                insights_data._project_money_currency_context(project)

    def test_linked_erp_project_company_mismatch_fails_closed(self):
        project = self._project(
            company="ACME",
            currency="NPR",
        )

        with patch.object(
            insights_data.frappe.db,
            "get_value",
            return_value="OTHER-CO",
        ):
            with self.assertRaisesRegex(
                frappe.ValidationError,
                "linked ERPNext Project",
            ):
                insights_data._project_money_currency_context(project)

    def test_margin_rollup_rejects_multiple_company_currencies(self):
        projects = [
            frappe._dict({"name": "BP-A"}),
            frappe._dict({"name": "BP-B"}),
        ]

        with patch.object(
            insights_data,
            "_project_money_currency_context",
            side_effect=[
                {
                    "company": "ACME-NP",
                    "company_currency": "NPR",
                    "project_currency": "NPR",
                    "project_currency_to_company_rate": 1.0,
                },
                {
                    "company": "ACME-US",
                    "company_currency": "USD",
                    "project_currency": "USD",
                    "project_currency_to_company_rate": 1.0,
                },
            ],
        ):
            with self.assertRaisesRegex(
                frappe.ValidationError,
                "different company currencies",
            ):
                insights_data._prepare_margin_project_currencies(projects)

    def test_margin_preparation_attaches_contract_fx(self):
        projects = [frappe._dict({"name": "BP-A", "currency": "USD"})]

        with patch.object(
            insights_data,
            "_project_money_currency_context",
            return_value={
                "company": "ACME",
                "company_currency": "NPR",
                "project_currency": "USD",
                "project_currency_to_company_rate": 130.0,
            },
        ):
            currency = insights_data._prepare_margin_project_currencies(projects)

        self.assertEqual(currency, "NPR")
        self.assertEqual(projects[0]["currency"], "USD")
        self.assertEqual(
            projects[0]["project_currency_to_company_rate"],
            130.0,
        )


if __name__ == "__main__":
    unittest.main()
