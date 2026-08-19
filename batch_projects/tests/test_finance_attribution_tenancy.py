"""Regressions for #41 cross-module financial attribution and tenancy."""

from types import SimpleNamespace
import unittest
from unittest.mock import patch

import frappe

from batch_projects import erp_triggers
from batch_projects.api import erp_link, insights_data


class TestFinancialEventAttribution(unittest.TestCase):
    def _shared_invoice(self):
        return SimpleNamespace(
            name="SI-SHARED",
            project="ERP-A",
            customer="CUST-1",
            grand_total=330.0,
            net_total=300.0,
            outstanding_amount=33.0,
            currency="USD",
            items=[
                SimpleNamespace(project="ERP-A", net_amount=100.0),
                SimpleNamespace(project="ERP-B", net_amount=200.0),
            ],
        )

    def test_shared_sales_invoice_submit_fans_out_by_item_project(self):
        doc = self._shared_invoice()

        def bp_project_for(_doctype, _name, erp_project):
            return {
                "ERP-A": "BP-A",
                "ERP-B": "BP-B",
            }.get(erp_project)

        with (
            patch.object(
                erp_triggers,
                "_bp_project_for",
                side_effect=bp_project_for,
            ),
            patch(
                "batch_projects.events.emit",
            ) as emit,
        ):
            erp_triggers.on_sales_invoice_submit(doc)

        events = [call.args for call in emit.call_args_list]
        self.assertEqual(len(events), 2)
        self.assertEqual(
            {payload["project"] for _, payload in events},
            {"BP-A", "BP-B"},
        )

        by_project = {
            payload["project"]: payload
            for _, payload in events
        }

        self.assertEqual(by_project["BP-A"]["amount"], 110.0)
        self.assertEqual(by_project["BP-B"]["amount"], 220.0)
        self.assertEqual(by_project["BP-A"]["outstanding"], 11.0)
        self.assertEqual(by_project["BP-B"]["outstanding"], 22.0)
        self.assertTrue(
            all(event == "erp.invoice_submitted" for event, _ in events)
        )
        self.assertTrue(
            all(payload["currency"] == "USD" for _, payload in events)
        )

    def test_payment_entry_allocation_fans_out_by_invoice_item_project(self):
        ref = SimpleNamespace(
            reference_doctype="Sales Invoice",
            reference_name="SI-SHARED",
            allocated_amount=150.0,
        )
        payment = SimpleNamespace(
            name="PE-1",
            references=[ref],
        )

        si = frappe._dict({
            "project": "ERP-A",
            "customer": "CUST-1",
            "currency": "USD",
            "outstanding_amount": 30.0,
            "grand_total": 330.0,
            "net_total": 300.0,
        })

        def get_value(doctype, name, fields=None, as_dict=False):
            if doctype == "Sales Invoice" and name == "SI-SHARED":
                return si
            raise AssertionError((doctype, name, fields, as_dict))

        def get_all(doctype, filters=None, fields=None, **_kwargs):
            if doctype != "Sales Invoice Item":
                raise AssertionError(doctype)
            self.assertEqual(filters, {"parent": "SI-SHARED"})
            return [
                frappe._dict({"project": "ERP-A", "net_amount": 100.0}),
                frappe._dict({"project": "ERP-B", "net_amount": 200.0}),
            ]

        def bp_project_for(_doctype, _name, erp_project):
            return {
                "ERP-A": "BP-A",
                "ERP-B": "BP-B",
            }.get(erp_project)

        with (
            patch.object(
                erp_triggers.frappe.db,
                "get_value",
                side_effect=get_value,
            ),
            patch.object(
                erp_triggers.frappe,
                "get_all",
                side_effect=get_all,
            ),
            patch.object(
                erp_triggers,
                "_bp_project_for",
                side_effect=bp_project_for,
            ),
            patch(
                "batch_projects.events.emit",
            ) as emit,
        ):
            erp_triggers.on_payment_entry_submit(payment)

        events = [call.args for call in emit.call_args_list]
        self.assertEqual(len(events), 2)

        by_project = {
            payload["project"]: payload
            for _, payload in events
        }

        self.assertEqual(by_project["BP-A"]["amount"], 50.0)
        self.assertEqual(by_project["BP-B"]["amount"], 100.0)
        self.assertEqual(by_project["BP-A"]["outstanding"], 10.0)
        self.assertEqual(by_project["BP-B"]["outstanding"], 20.0)
        self.assertTrue(
            all(event == "erp.payment_received" for event, _ in events)
        )


class TestPurchaseInvoiceProjectProjection(unittest.TestCase):
    def test_purchase_invoice_tenant_accepts_explicit_item_project(self):
        def get_value(doctype, name, fieldname, **_kwargs):
            if doctype == "Purchase Invoice":
                self.assertEqual(name, "PI-1")
                self.assertEqual(fieldname, "project")
                return "ERP-A"
            raise AssertionError((doctype, name, fieldname))

        with (
            patch.object(
                erp_link.frappe.db,
                "get_value",
                side_effect=get_value,
            ),
            patch.object(
                erp_link.frappe.db,
                "exists",
                return_value=True,
            ) as exists,
        ):
            allowed = erp_link._tenant_ok(
                "Purchase Invoice",
                "PI-1",
                "ERP-B",
            )

        self.assertTrue(allowed)
        exists.assert_called_once_with(
            "Purchase Invoice Item",
            {
                "parent": "PI-1",
                "project": "ERP-B",
            },
        )

    def test_shared_purchase_invoice_items_are_project_scoped(self):
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

        a_rows = erp_link._scope_purchase_invoice_items(
            children,
            "ERP-A",
            "ERP-A",
        )
        b_rows = erp_link._scope_purchase_invoice_items(
            children,
            "ERP-A",
            "ERP-B",
        )

        self.assertEqual(
            [row["item_name"] for row in a_rows],
            ["A explicit", "legacy/header"],
        )
        self.assertEqual(
            [row["item_name"] for row in b_rows],
            ["B explicit"],
        )
        self.assertTrue(
            all("project" not in row for row in a_rows + b_rows)
        )

    def test_margin_purchase_reader_uses_item_project_with_header_fallback(self):
        projects = [
            frappe._dict({
                "name": "BP-A",
                "erpnext_project": "ERP-A",
            }),
        ]
        queries = []

        def query(table, sql, params):
            queries.append((table, " ".join(sql.split()), params))
            return []

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
            patch.object(
                insights_data,
                "_sales_invoice_project_revenue_rows",
                return_value=[],
            ),
            patch.object(
                insights_data,
                "_query",
                side_effect=query,
            ),
        ):
            insights_data.get_margin_inputs(
                "2026-08-01",
                "2026-08-31",
                "user@example.com",
            )

        purchase = next(
            row for row in queries
            if row[0] == "Purchase Invoice Item"
        )
        _, sql, params = purchase

        self.assertIn(
            "COALESCE(NULLIF(pii.project, ''), pi.project) AS project",
            sql,
        )
        self.assertIn(
            "COALESCE(NULLIF(pii.project, ''), pi.project) IN %(projects)s",
            sql,
        )
        self.assertEqual(params["projects"], ["ERP-A"])


if __name__ == "__main__":
    unittest.main()
