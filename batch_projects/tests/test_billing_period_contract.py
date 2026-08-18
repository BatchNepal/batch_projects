"""Regression tests for generate_invoice's fail-closed period contract."""

import unittest
from pathlib import Path
from unittest.mock import patch

import frappe

from batch_projects.api import erp_link


APP_ROOT = Path(__file__).resolve().parents[2]


class TestBillingPeriodContract(unittest.TestCase):
    def test_nonempty_period_fails_before_financial_selection(self):
        with (
            patch.object(erp_link, "_check_permission"),
            patch("batch_projects.access.require_capability"),
            patch.object(erp_link, "require_feature"),
            patch.object(erp_link.frappe, "get_doc") as get_doc,
            patch.object(erp_link.frappe.db, "sql") as sql,
            patch.object(
                erp_link,
                "guard_timesheet_details",
            ) as guard,
            patch.object(
                erp_link.frappe,
                "new_doc",
            ) as new_doc,
        ):
            with self.assertRaisesRegex(
                frappe.ValidationError,
                "Period-scoped invoice generation is not supported",
            ):
                erp_link.generate_invoice(
                    "BP-PERIOD-TEST",
                    period="last_30_days",
                )

        # Permission + entitlement checks are allowed to run, but no financial
        # source selection/reservation/draft construction may happen.
        get_doc.assert_not_called()
        sql.assert_not_called()
        guard.assert_not_called()
        new_doc.assert_not_called()

    def test_empty_period_values_are_supported_legacy_noops(self):
        for period in (None, "", "   "):
            with self.subTest(period=period):
                erp_link._validate_invoice_period_contract(period)

    def test_first_party_wrapper_has_no_period_argument(self):
        api = (
            APP_ROOT
            / "frontend"
            / "src"
            / "utils"
            / "api.js"
        ).read_text()

        self.assertIn(
            "export const generateInvoice = (project, opts = {}) =>",
            api,
        )
        self.assertNotIn(
            "export const generateInvoice = (project, period",
            api,
        )

        block = api.split(
            "export const generateInvoice =",
            1,
        )[1].split(
            "export const getBatchInvoiceCandidates",
            1,
        )[0]

        self.assertNotIn(
            "\n    period,",
            block,
        )

    def test_batch_invoicing_uses_opts_as_second_argument(self):
        page = (
            APP_ROOT
            / "frontend"
            / "src"
            / "pages"
            / "BatchInvoicing.vue"
        ).read_text()

        self.assertIn(
            """const res = await generateInvoice(
      confirm.projects.map(p => p.bp_project),
      {""",
            page,
        )

        self.assertNotIn(
            """confirm.projects.map(p => p.bp_project),
      null,
      {""",
            page,
        )


if __name__ == "__main__":
    unittest.main()
