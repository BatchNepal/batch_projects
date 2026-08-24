"""Regressions for item-authoritative Sales Invoice project attribution."""

import inspect
import unittest
from unittest.mock import patch

import frappe

from batch_projects.api import erp_link
from batch_projects.api import insights_data


def revenue_row(
    *,
    project,
    invoice="SINV-SHARED",
    amount,
    invoice_net=300,
    outstanding=30,
    conversion_rate=1,
    date="2026-08-19",
):
    # base_grand_total is deliberately present but must be ignored by the
    # shaper: 345 includes tax while project profitability is item NET sales.
    return frappe._dict({
        "project": project,
        "name": invoice,
        "date": date,
        "status": "Unpaid",
        "outstanding_amount": outstanding,
        "conversion_rate": conversion_rate,
        "base_net_total": invoice_net,
        "base_net_amount": amount,
        "base_grand_total": 345,
    })


class TestInvoiceProjectAttribution(unittest.TestCase):
    def test_shared_invoice_splits_net_revenue_and_outstanding(self):
        rows = [
            revenue_row(
                project="ERP-A",
                amount=60,
            ),
            revenue_row(
                project="ERP-A",
                amount=40,
            ),
            revenue_row(
                project="ERP-B",
                amount=200,
            ),
        ]

        result = (
            insights_data
            ._shape_sales_invoice_project_revenue_rows(
                rows
            )
        )

        by_project = {
            row["project"]: row
            for row in result
        }

        self.assertEqual(
            by_project["ERP-A"]["grand_total"],
            100.0,
        )

        self.assertEqual(
            by_project["ERP-B"]["grand_total"],
            200.0,
        )

        # 30 invoice-currency outstanding splits 1/3 + 2/3.
        self.assertEqual(
            by_project["ERP-A"]["outstanding_amount"],
            10.0,
        )

        self.assertEqual(
            by_project["ERP-B"]["outstanding_amount"],
            20.0,
        )

        # Tax-inclusive 345 must never become project revenue.
        self.assertEqual(
            sum(
                row["grand_total"]
                for row in result
            ),
            300.0,
        )

    def test_submitted_return_revenue_remains_negative(self):
        rows = [
            revenue_row(
                project="ERP-A",
                invoice="SINV-RETURN",
                amount=-25,
                invoice_net=-100,
                outstanding=-10,
            ),
            revenue_row(
                project="ERP-B",
                invoice="SINV-RETURN",
                amount=-75,
                invoice_net=-100,
                outstanding=-10,
            ),
        ]

        result = (
            insights_data
            ._shape_sales_invoice_project_revenue_rows(
                rows
            )
        )

        by_project = {
            row["project"]: row
            for row in result
        }

        self.assertEqual(
            by_project["ERP-A"]["grand_total"],
            -25.0,
        )

        self.assertEqual(
            by_project["ERP-B"]["grand_total"],
            -75.0,
        )

        self.assertEqual(
            by_project["ERP-A"]["outstanding_amount"],
            -2.5,
        )

        self.assertEqual(
            by_project["ERP-B"]["outstanding_amount"],
            -7.5,
        )

    def test_zero_invoice_net_never_duplicates_outstanding(self):
        rows = [
            revenue_row(
                project="ERP-A",
                amount=0,
                invoice_net=0,
                outstanding=100,
            ),
            revenue_row(
                project="ERP-B",
                amount=0,
                invoice_net=0,
                outstanding=100,
            ),
        ]

        result = (
            insights_data
            ._shape_sales_invoice_project_revenue_rows(
                rows
            )
        )

        self.assertTrue(
            all(
                row["outstanding_amount"] == 0
                for row in result
            )
        )

    def test_invoice_reader_uses_item_project_with_header_fallback(self):
        with patch.object(
            insights_data,
            "_query",
            return_value=[],
        ) as query:
            result = (
                insights_data
                ._sales_invoice_project_revenue_rows(
                    ["ERP-A", "ERP-B"],
                    "2026-08-01",
                    "2026-08-31",
                )
            )

        self.assertEqual(
            result,
            [],
        )

        table, sql, params = (
            query.call_args.args
        )

        normalized = " ".join(
            sql.split()
        )

        self.assertEqual(
            table,
            "Sales Invoice Item",
        )

        self.assertIn(
            "COALESCE( NULLIF(sii.project, ''), si.project ) AS project",
            normalized,
        )

        self.assertIn(
            "si.docstatus = 1",
            normalized,
        )

        self.assertIn(
            "sii.base_net_amount",
            normalized,
        )

        self.assertNotIn(
            "base_grand_total",
            normalized,
        )

        self.assertEqual(
            params["projects"],
            ("ERP-A", "ERP-B"),
        )

    def test_margin_feed_keeps_wire_shape_but_uses_item_revenue(self):
        projects = [
            frappe._dict({
                "name": "BP-A",
                "erpnext_project": "ERP-A",
            }),
            frappe._dict({
                "name": "BP-B",
                "erpnext_project": "ERP-B",
            }),
        ]

        invoice_rows = [
            {
                "project": "ERP-A",
                "name": "SI-1",
                "grand_total": 100.0,
            },
            {
                "project": "ERP-B",
                "name": "SI-1",
                "grand_total": 200.0,
            },
        ]

        with (
            patch.object(
                insights_data,
                "_assert_service_caller",
            ),
            patch.object(
                insights_data,
                "_visible_money_projects",
                return_value=projects,
            ),
            # Currency provenance is covered by dedicated #41 tests. This
            # regression owns invoice attribution/wire shape only.
            patch.object(
                insights_data,
                "_prepare_margin_project_currencies",
                return_value="NPR",
            ),
            patch.object(
                insights_data,
                "_sales_invoice_project_revenue_rows",
                return_value=invoice_rows,
            ) as revenue,
            patch.object(
                insights_data,
                "_query",
                return_value=[],
            ),
        ):
            result = (
                insights_data.get_margin_inputs(
                    "2026-08-01",
                    "2026-08-31",
                    "test67+info@batchnepal.com",
                )
            )

        revenue.assert_called_once_with(
            ["ERP-A", "ERP-B"],
            "2026-08-01",
            "2026-08-31",
        )

        self.assertEqual(
            result["invoices"],
            [
                {
                    "project": "ERP-A",
                    "revenue": 100.0,
                },
                {
                    "project": "ERP-B",
                    "revenue": 200.0,
                },
            ],
        )

    def test_money_feed_uses_project_attributed_invoice_rows(self):
        project = frappe._dict({
            "name": "BP-A",
            "erpnext_project": "ERP-A",
            "company": "TEST-COMPANY",
            "currency": "USD",
            "project_type": "tm",
            "hourly_rate": 0,
            "budget_amount": 0,
            "retainer_hours": 0,
        })

        invoice_rows = [
            {
                "project": "ERP-A",
                "name": "SI-1",
                "date": "2026-08-19",
                "status": "Unpaid",
                "grand_total": 100.0,
                "outstanding_amount": 10.0,
                "conversion_rate": 1,
            },
        ]

        with (
            patch.object(
                insights_data,
                "_assert_service_caller",
            ),
            patch(
                "batch_projects.access.require",
            ),
            patch(
                "batch_projects.access.require_capability",
            ),
            patch(
                "batch_projects.entitlements.require_workspace_feature",
            ),
            patch.object(
                insights_data.frappe,
                "get_doc",
                return_value=project,
            ),
            # Currency normalization is covered by dedicated #41 tests. This
            # regression owns the project-attributed invoice feed contract.
            patch.object(
                insights_data,
                "_project_money_reporting_values",
                return_value={
                    "currency": "NPR",
                    "project_currency": "USD",
                    "hourly_rate": 0.0,
                    "budget_amount": 0.0,
                },
            ),
            patch.object(
                insights_data,
                "_sales_invoice_project_revenue_rows",
                return_value=invoice_rows,
            ) as revenue,
            patch.object(
                insights_data,
                "_query",
                return_value=[],
            ),
        ):
            result = (
                insights_data.get_money_inputs(
                    "BP-A",
                    "2026-08-01",
                    "2026-08-31",
                    "test67+info@batchnepal.com",
                )
            )

        revenue.assert_called_once_with(
            ["ERP-A"],
            "2026-08-01",
            "2026-08-31",
        )

        self.assertEqual(
            result["revenue"],
            invoice_rows,
        )

        self.assertEqual(
            result["currency"],
            "NPR",
        )

    def test_sales_invoice_tenant_accepts_header_project(self):
        with (
            patch.object(
                erp_link.frappe.db,
                "get_value",
                return_value="ERP-A",
            ),
            patch.object(
                erp_link.frappe.db,
                "exists",
            ) as exists,
        ):
            allowed = erp_link._tenant_ok(
                "Sales Invoice",
                "SI-1",
                "ERP-A",
            )

        self.assertTrue(
            allowed
        )

        exists.assert_not_called()

    def test_sales_invoice_tenant_accepts_explicit_item_project(self):
        with (
            patch.object(
                erp_link.frappe.db,
                "get_value",
                return_value="ERP-A",
            ),
            patch.object(
                erp_link.frappe.db,
                "exists",
                return_value=True,
            ) as exists,
        ):
            allowed = erp_link._tenant_ok(
                "Sales Invoice",
                "SI-1",
                "ERP-B",
            )

        self.assertTrue(
            allowed
        )

        exists.assert_called_once_with(
            "Sales Invoice Item",
            {
                "parent": "SI-1",
                "project": "ERP-B",
            },
        )

    def test_sales_invoice_tenant_denies_unrelated_project(self):
        with (
            patch.object(
                erp_link.frappe.db,
                "get_value",
                return_value="ERP-A",
            ),
            patch.object(
                erp_link.frappe.db,
                "exists",
                return_value=False,
            ),
        ):
            allowed = erp_link._tenant_ok(
                "Sales Invoice",
                "SI-1",
                "ERP-C",
            )

        self.assertFalse(
            allowed
        )

    def test_shared_invoice_items_are_project_scoped(self):
        children = [
            frappe._dict({
                "item_name": "A explicit",
                "project": "ERP-A",
            }),
            frappe._dict({
                "item_name": "B explicit",
                "project": "ERP-B",
            }),
            frappe._dict({
                "item_name": "legacy/header",
                "project": "",
            }),
        ]

        a_rows = (
            erp_link._scope_sales_invoice_items(
                children,
                "ERP-A",
                "ERP-A",
            )
        )

        b_rows = (
            erp_link._scope_sales_invoice_items(
                children,
                "ERP-A",
                "ERP-B",
            )
        )

        self.assertEqual(
            [
                row["item_name"]
                for row in a_rows
            ],
            [
                "A explicit",
                "legacy/header",
            ],
        )

        self.assertEqual(
            [
                row["item_name"]
                for row in b_rows
            ],
            [
                "B explicit",
            ],
        )

        self.assertTrue(
            all(
                "project" not in row
                for row in a_rows + b_rows
            )
        )

    def test_shared_invoice_timesheets_are_project_scoped(self):
        rows = [
            frappe._dict({
                "time_sheet": "TS-A",
                "timesheet_detail": "TSD-A",
                "billing_hours": 1,
                "billing_amount": 100,
            }),
            frappe._dict({
                "time_sheet": "TS-B",
                "timesheet_detail": "TSD-B",
                "billing_hours": 2,
                "billing_amount": 200,
            }),
            frappe._dict({
                "time_sheet": "TS-UNKNOWN",
                "timesheet_detail": None,
                "billing_hours": 3,
                "billing_amount": 300,
            }),
        ]

        detail_projects = {
            "TSD-A": "ERP-A",
            "TSD-B": "ERP-B",
        }

        a_rows = (
            erp_link
            ._scope_sales_invoice_timesheets(
                rows,
                detail_projects,
                "ERP-A",
            )
        )

        b_rows = (
            erp_link
            ._scope_sales_invoice_timesheets(
                rows,
                detail_projects,
                "ERP-B",
            )
        )

        self.assertEqual(
            [
                row["time_sheet"]
                for row in a_rows
            ],
            ["TS-A"],
        )

        self.assertEqual(
            [
                row["time_sheet"]
                for row in b_rows
            ],
            ["TS-B"],
        )

    def test_generators_stamp_item_project_and_header_docs_are_truthful(self):
        milestone = inspect.getsource(
            erp_link.generate_milestone_invoice
        )

        expense = inspect.getsource(
            erp_link.generate_expense_invoice
        )

        generated = inspect.getsource(
            erp_link.generate_invoice
        )

        self.assertIn(
            '"project": project.erpnext_project',
            milestone,
        )

        self.assertIn(
            '"project": doc.erpnext_project',
            expense,
        )

        self.assertNotIn(
            "header `project` field is set only when invoicing exactly one project",
            generated,
        )

        # inspect.getsource() preserves source line wrapping, so normalize
        # whitespace before asserting the semantic header contract. The source
        # intentionally wraps "safety" / "sentinel" across two lines.
        normalized_generated = " ".join(
            generated.split()
        )

        self.assertIn(
            "ERPNext Timesheet-writeback safety sentinel",
            normalized_generated,
        )

        self.assertIn(
            "It is not the business attribution for the invoice",
            normalized_generated,
        )


if __name__ == "__main__":
    unittest.main()
