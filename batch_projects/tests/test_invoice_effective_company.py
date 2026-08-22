"""Effective-company regressions for milestone and expense invoices."""

import unittest
from unittest.mock import patch

import frappe

from batch_projects.api import erp_link


def bp_project(company):
    return frappe._dict({
        "name": "BP-COMPANY-36",
        "project_name": "Company Contract Project",
        "erpnext_project": "ERP-COMPANY-36",
        "client": "CUSTOMER-36",
        "company": company,
        "currency": "USD",
        "budget_amount": 10000,
    })


def auth_milestone():
    return frappe._dict({
        "name": "MS-COMPANY-36",
        "project": "BP-COMPANY-36",
    })


def locked_milestone():
    return frappe._dict({
        "name": "MS-COMPANY-36",
        "project": "BP-COMPANY-36",
        "title": "Company contract milestone",
        "status": "Completed",
        "billing_type": "Fixed Amount",
        "invoice_amount": 5000,
        "invoice_percent": 0,
        "invoice_status": "Not Invoiced",
        "sales_invoice": "",
    })


def locked_expense():
    return frappe._dict({
        "name": "ECD-COMPANY-36",
        "expense_claim": "EC-COMPANY-36",
        "expense_type": "Travel",
        "sanctioned_amount": 100,
        "description": "Travel",
        "posting_date": "2026-08-19",
        "policy": "At Cost",
        "markup_percent": 0,
    })


class FakeSalesInvoice:
    def __init__(self, name):
        self.name = name
        self.flags = frappe._dict()
        self.items = []
        self.customer = None
        self.company = None
        self.project = None
        self.currency = None
        self.conversion_rate = None
        self.grand_total = 100

    def append(self, fieldname, value):
        assert fieldname == "items"
        row = frappe._dict(value)
        self.items.append(row)
        return row

    def run_method(self, method):
        assert method == "set_missing_values"

    def insert(self, ignore_permissions=False):
        assert ignore_permissions is True
        return self


class TestInvoiceEffectiveCompany(unittest.TestCase):

    def _milestone(self, company, default_company):
        project = bp_project(company)
        invoice = FakeSalesInvoice("SINV-MS-36")

        with (
            patch.object(
                erp_link.frappe,
                "get_doc",
                return_value=auth_milestone(),
            ),
            patch.object(erp_link, "_check_permission"),
            patch("batch_projects.access.require_capability"),
            patch.object(erp_link, "require_feature"),
            patch(
                "batch_projects.milestone_billing.lock_generation_scope",
                return_value=(
                    project,
                    locked_milestone(),
                ),
            ),
            patch.object(
                erp_link.frappe.defaults,
                "get_global_default",
                return_value=default_company,
            ) as default,
            patch.object(
                erp_link.frappe.db,
                "get_value",
                return_value="Income - 36",
            ) as account,
            patch.object(
                erp_link,
                "_resolve_invoice_currency",
                return_value=("NPR", "USD", 137.5),
            ) as fx,
            patch.object(
                erp_link.frappe,
                "new_doc",
                return_value=invoice,
            ) as new_doc,
            patch.object(
                erp_link.frappe.db,
                "set_value",
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
            error = None
            try:
                erp_link.generate_milestone_invoice(
                    "MS-COMPANY-36"
                )
            except frappe.ValidationError as exc:
                error = exc

        return {
            "invoice": invoice,
            "default": default,
            "account": account,
            "fx": fx,
            "new_doc": new_doc,
            "error": error,
        }

    def _expense(self, company, default_company):
        project = bp_project(company)
        invoice = FakeSalesInvoice("SINV-EXP-36")

        with (
            patch.object(erp_link, "_check_permission"),
            patch("batch_projects.access.require_capability"),
            patch.object(erp_link, "require_feature"),
            patch.object(
                erp_link.frappe,
                "get_doc",
                return_value=project,
            ),
            patch.object(
                erp_link.frappe.defaults,
                "get_global_default",
                return_value=default_company,
            ) as default,
            patch.object(
                erp_link.frappe.db,
                "sql",
                return_value=[
                    frappe._dict({
                        "name": "ECD-COMPANY-36",
                    })
                ],
            ),
            patch.object(
                erp_link,
                "guard_expense_claim_details",
                return_value=[locked_expense()],
            ),
            patch.object(
                erp_link.frappe.db,
                "get_value",
                return_value="Income - 36",
            ) as account,
            patch.object(
                erp_link,
                "_resolve_invoice_currency",
                return_value=("NPR", "USD", 137.5),
            ) as fx,
            patch.object(
                erp_link.frappe,
                "new_doc",
                return_value=invoice,
            ) as new_doc,
            patch.object(
                erp_link.frappe.share,
                "add_docshare",
            ),
            patch.object(
                erp_link.frappe.db,
                "set_value",
            ),
            patch.object(
                erp_link.frappe.db,
                "commit",
            ),
        ):
            error = None
            try:
                erp_link.generate_expense_invoice(
                    "BP-COMPANY-36"
                )
            except frappe.ValidationError as exc:
                error = exc

        return {
            "invoice": invoice,
            "default": default,
            "account": account,
            "fx": fx,
            "new_doc": new_doc,
            "error": error,
        }

    def test_explicit_company_is_authoritative_for_both_generators(self):
        for runner in (
            self._milestone,
            self._expense,
        ):
            with self.subTest(runner=runner.__name__):
                result = runner(
                    "COMPANY-EXPLICIT",
                    "COMPANY-GLOBAL",
                )

                self.assertIsNone(result["error"])

                self.assertEqual(
                    result["invoice"].company,
                    "COMPANY-EXPLICIT",
                )

                result["default"].assert_not_called()

                result["account"].assert_called_once_with(
                    "Company",
                    "COMPANY-EXPLICIT",
                    "default_income_account",
                )

                self.assertEqual(
                    result["fx"].call_args.args[0],
                    "COMPANY-EXPLICIT",
                )

    def test_global_default_is_used_for_both_blank_projects(self):
        for runner in (
            self._milestone,
            self._expense,
        ):
            with self.subTest(runner=runner.__name__):
                result = runner(
                    "",
                    "COMPANY-GLOBAL",
                )

                self.assertIsNone(result["error"])

                self.assertEqual(
                    result["invoice"].company,
                    "COMPANY-GLOBAL",
                )

                result["default"].assert_called_once_with(
                    "company"
                )

                result["account"].assert_called_once_with(
                    "Company",
                    "COMPANY-GLOBAL",
                    "default_income_account",
                )

                self.assertEqual(
                    result["fx"].call_args.args[0],
                    "COMPANY-GLOBAL",
                )

    def test_missing_company_fails_before_account_fx_or_invoice(self):
        for runner in (
            self._milestone,
            self._expense,
        ):
            with self.subTest(runner=runner.__name__):
                result = runner("", None)

                self.assertIsInstance(
                    result["error"],
                    frappe.ValidationError,
                )

                self.assertIn(
                    "global default Company",
                    str(result["error"]),
                )

                result["account"].assert_not_called()
                result["fx"].assert_not_called()
                result["new_doc"].assert_not_called()


if __name__ == "__main__":
    unittest.main()
