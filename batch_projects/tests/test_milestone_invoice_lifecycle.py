"""Regression tests for BP Milestone ↔ Sales Invoice lifecycle."""

import unittest
from pathlib import Path
from unittest.mock import Mock

import frappe

from batch_projects import milestone_billing


APP_ROOT = Path(__file__).resolve().parents[2]


def milestone_row(
    *,
    name="MS-TEST",
    invoice_status="Not Invoiced",
    sales_invoice="",
):
    return frappe._dict({
        "name": name,
        "invoice_status": invoice_status,
        "sales_invoice": sales_invoice,
    })


class TestMilestoneInvoiceLifecycle(unittest.TestCase):
    def test_invoice_state_maps_erpnext_docstatus(self):
        db = Mock()

        db.get_value.side_effect = [
            0,
            1,
            2,
            None,
        ]

        self.assertEqual(
            milestone_billing.invoice_state(
                "SINV-DRAFT",
                db=db,
            ),
            ("Draft", "SINV-DRAFT"),
        )

        self.assertEqual(
            milestone_billing.invoice_state(
                "SINV-SUB",
                db=db,
            ),
            ("Invoiced", "SINV-SUB"),
        )

        self.assertEqual(
            milestone_billing.invoice_state(
                "SINV-CANCELLED",
                db=db,
            ),
            ("Not Invoiced", "SINV-CANCELLED"),
        )

        self.assertEqual(
            milestone_billing.invoice_state(
                "SINV-DELETED",
                db=db,
            ),
            ("Not Invoiced", None),
        )

        self.assertEqual(
            milestone_billing.invoice_state(
                "",
                db=db,
            ),
            ("Not Invoiced", None),
        )

    def test_generation_lock_order_is_project_then_milestone(self):
        db = Mock()

        db.sql.side_effect = [
            [frappe._dict({"name": "BP-PROJECT"})],
            [
                frappe._dict({
                    "name": "MS-TEST",
                    "project": "BP-PROJECT",
                    "invoice_status": "Not Invoiced",
                    "sales_invoice": "",
                    "billing_type": "Percent of Budget",
                    "invoice_percent": 60,
                })
            ],
        ]

        milestone_billing.lock_generation_scope(
            "BP-PROJECT",
            "MS-TEST",
            db=db,
        )

        project_query = db.sql.call_args_list[0].args[0]
        milestone_query = db.sql.call_args_list[1].args[0]

        self.assertIn(
            "FROM `tabBP Project`",
            project_query,
        )
        self.assertIn(
            "FOR UPDATE",
            project_query,
        )

        self.assertIn(
            "FROM `tabBP Milestone`",
            milestone_query,
        )
        self.assertIn(
            "FOR UPDATE",
            milestone_query,
        )

    def test_percent_reservation_counts_draft_and_invoiced(self):
        db = Mock()
        db.sql.return_value = [(75,)]

        reserved = milestone_billing.reserved_percent(
            "BP-PROJECT",
            exclude_milestone="MS-ME",
            db=db,
        )

        self.assertEqual(reserved, 75)

        query = db.sql.call_args.args[0]

        self.assertIn(
            "invoice_status IN ('Draft', 'Invoiced')",
            query,
        )

    def test_percent_capacity_fails_closed_over_100(self):
        db = Mock()
        db.sql.return_value = [(60,)]

        with self.assertRaisesRegex(
            frappe.ValidationError,
            "live milestone invoice reservations",
        ):
            milestone_billing.assert_percent_capacity(
                "BP-PROJECT",
                "MS-SECOND",
                60,
                db=db,
            )

    def test_submit_moves_current_invoice_to_invoiced(self):
        db = Mock()

        db.get_value.return_value = "MS-TEST"
        db.sql.return_value = [
            milestone_row(
                invoice_status="Draft",
                sales_invoice="SINV-001",
            )
        ]

        doc = frappe._dict({
            "name": "SINV-001",
        })

        changed = (
            milestone_billing._on_sales_invoice_submit_with_db(
                doc,
                db,
            )
        )

        self.assertTrue(changed)

        db.set_value.assert_called_once_with(
            "BP Milestone",
            "MS-TEST",
            {
                "invoice_status": "Invoiced",
                "sales_invoice": "SINV-001",
            },
            update_modified=False,
        )

    def test_cancel_reopens_but_retains_invoice_lineage(self):
        db = Mock()

        db.get_value.return_value = "MS-TEST"
        db.sql.return_value = [
            milestone_row(
                invoice_status="Invoiced",
                sales_invoice="SINV-001",
            )
        ]

        doc = frappe._dict({
            "name": "SINV-001",
        })

        changed = (
            milestone_billing._on_sales_invoice_cancel_with_db(
                doc,
                db,
            )
        )

        self.assertTrue(changed)

        db.set_value.assert_called_once_with(
            "BP Milestone",
            "MS-TEST",
            {
                "invoice_status": "Not Invoiced",
                "sales_invoice": "SINV-001",
            },
            update_modified=False,
        )

    def test_amendment_insert_moves_pointer_to_new_draft(self):
        db = Mock()

        db.get_value.return_value = "MS-TEST"
        db.sql.return_value = [
            milestone_row(
                invoice_status="Not Invoiced",
                sales_invoice="SINV-OLD",
            )
        ]

        doc = frappe._dict({
            "name": "SINV-NEW",
            "amended_from": "SINV-OLD",
        })

        changed = (
            milestone_billing._on_sales_invoice_after_insert_with_db(
                doc,
                db,
            )
        )

        self.assertTrue(changed)

        db.set_value.assert_called_once_with(
            "BP Milestone",
            "MS-TEST",
            {
                "invoice_status": "Draft",
                "sales_invoice": "SINV-NEW",
            },
            update_modified=False,
        )

    def test_trash_initial_draft_reopens_and_clears_pointer(self):
        db = Mock()

        db.get_value.return_value = "MS-TEST"
        db.sql.return_value = [
            milestone_row(
                invoice_status="Draft",
                sales_invoice="SINV-DRAFT",
            )
        ]

        doc = frappe._dict({
            "name": "SINV-DRAFT",
            "amended_from": None,
        })

        changed = (
            milestone_billing._on_sales_invoice_trash_with_db(
                doc,
                db,
            )
        )

        self.assertTrue(changed)

        db.set_value.assert_called_once_with(
            "BP Milestone",
            "MS-TEST",
            {
                "invoice_status": "Not Invoiced",
                "sales_invoice": None,
            },
            update_modified=False,
        )

    def test_trash_amendment_restores_cancelled_predecessor(self):
        db = Mock()

        db.get_value.return_value = "MS-TEST"
        db.sql.return_value = [
            milestone_row(
                invoice_status="Draft",
                sales_invoice="SINV-AMEND-1",
            )
        ]

        doc = frappe._dict({
            "name": "SINV-AMEND-1",
            "amended_from": "SINV-ORIGINAL",
        })

        milestone_billing._on_sales_invoice_trash_with_db(
            doc,
            db,
        )

        db.set_value.assert_called_once_with(
            "BP Milestone",
            "MS-TEST",
            {
                "invoice_status": "Not Invoiced",
                "sales_invoice": "SINV-ORIGINAL",
            },
            update_modified=False,
        )

    def test_stale_event_cannot_overwrite_newer_pointer(self):
        db = Mock()

        # Discovery found MS-TEST by SINV-OLD, but after acquiring the exact
        # milestone lock it already points at a newer draft.
        db.get_value.return_value = "MS-TEST"
        db.sql.return_value = [
            milestone_row(
                invoice_status="Draft",
                sales_invoice="SINV-NEW",
            )
        ]

        doc = frappe._dict({
            "name": "SINV-OLD",
        })

        changed = (
            milestone_billing._on_sales_invoice_cancel_with_db(
                doc,
                db,
            )
        )

        self.assertFalse(changed)
        db.set_value.assert_not_called()

    def test_unrelated_sales_invoice_is_noop(self):
        db = Mock()
        db.get_value.return_value = None

        doc = frappe._dict({
            "name": "SINV-NATIVE",
        })

        changed = (
            milestone_billing._on_sales_invoice_cancel_with_db(
                doc,
                db,
            )
        )

        self.assertFalse(changed)
        db.sql.assert_not_called()
        db.set_value.assert_not_called()

    def test_project_summary_treats_new_invoice_as_draft(self):
        page = (
            APP_ROOT
            / "frontend"
            / "src"
            / "pages"
            / "ProjectSummary.vue"
        ).read_text()

        self.assertIn(
            "m.invoice_status = res.invoice_status || 'Draft'",
            page,
        )

        self.assertIn(
            "m.invoice_status === 'Not Invoiced'",
            page,
        )

        self.assertIn(
            "m.invoice_status === 'Draft'",
            page,
        )

        self.assertNotIn(
            "m.invoice_status = 'Invoiced'",
            page,
        )


if __name__ == "__main__":
    unittest.main()
