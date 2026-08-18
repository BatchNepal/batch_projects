"""Regressions for Expense Claim Detail billing-source reservation."""

import inspect
import unittest
from unittest.mock import Mock, patch

import frappe

from batch_projects import expense_reservation
from batch_projects.api import erp_link


def detail(
    name="ECD-1",
    *,
    parent="EC-1",
    docstatus=1,
    billable=1,
    invoice="",
    expense_type="Travel",
    amount=100,
):
    return frappe._dict({
        "name": name,
        "parent": parent,
        "source_docstatus": docstatus,
        "expense_type": expense_type,
        "sanctioned_amount": amount,
        "description": "Travel expense",
        "custom_is_billable": billable,
        "custom_sales_invoice": invoice,
    })


def parent(
    name="EC-1",
    *,
    project="ERP-PROJ",
    docstatus=1,
):
    return frappe._dict({
        "name": name,
        "project": project,
        "docstatus": docstatus,
        "posting_date": "2026-08-19",
    })


def expense_type(
    name="Travel",
    *,
    policy="At Cost",
    markup=0,
):
    return frappe._dict({
        "name": name,
        "policy": policy,
        "markup_percent": markup,
    })


def invoice(
    name,
    docstatus,
):
    return frappe._dict({
        "name": name,
        "docstatus": docstatus,
    })


class TestExpenseBillingReservation(unittest.TestCase):
    def _run(
        self,
        *,
        discovered=None,
        parents=None,
        details=None,
        types=None,
        invoices=None,
    ):
        discovered = (
            {"ECD-1": "EC-1"}
            if discovered is None
            else discovered
        )

        parents = (
            [parent()]
            if parents is None
            else parents
        )

        details = (
            [detail()]
            if details is None
            else details
        )

        types = (
            [expense_type()]
            if types is None
            else types
        )

        invoices = (
            []
            if invoices is None
            else invoices
        )

        with (
            patch.object(
                expense_reservation,
                "_discover_parent_names",
                return_value=discovered,
            ),
            patch.object(
                expense_reservation,
                "_lock_parent_rows",
                return_value=parents,
            ),
            patch.object(
                expense_reservation,
                "_lock_detail_rows",
                return_value=details,
            ),
            patch.object(
                expense_reservation,
                "_lock_type_rows",
                return_value=types,
            ),
            patch.object(
                expense_reservation,
                "_lock_invoice_rows",
                return_value=invoices,
            ),
        ):
            return (
                expense_reservation
                ._guard_expense_claim_details_with_db(
                    Mock(),
                    ["ECD-1"],
                    "ERP-PROJ",
                )
            )

    def test_returns_authoritative_locked_financial_rows(self):
        rows = self._run(
            details=[
                detail(
                    amount=250,
                )
            ],
            types=[
                expense_type(
                    policy="At Cost + Markup",
                    markup=12.5,
                )
            ],
        )

        self.assertEqual(
            len(rows),
            1,
        )

        row = rows[0]

        self.assertEqual(
            row.name,
            "ECD-1",
        )

        self.assertEqual(
            row.expense_claim,
            "EC-1",
        )

        self.assertEqual(
            row.sanctioned_amount,
            250,
        )

        self.assertEqual(
            row.policy,
            "At Cost + Markup",
        )

        self.assertEqual(
            row.markup_percent,
            12.5,
        )

    def test_cancelled_or_deleted_pointer_releases_source(self):
        cancelled = self._run(
            details=[
                detail(
                    invoice="SI-CANCELLED",
                )
            ],
            invoices=[
                invoice(
                    "SI-CANCELLED",
                    2,
                )
            ],
        )

        self.assertEqual(
            len(cancelled),
            1,
        )

        deleted = self._run(
            details=[
                detail(
                    invoice="SI-DELETED",
                )
            ],
            invoices=[],
        )

        self.assertEqual(
            len(deleted),
            1,
        )

    def test_live_draft_and_submitted_invoice_reserve_source(self):
        for docstatus in (0, 1):
            with self.subTest(
                docstatus=docstatus,
            ):
                with self.assertRaisesRegex(
                    frappe.ValidationError,
                    "already reserved by a live Sales Invoice",
                ):
                    self._run(
                        details=[
                            detail(
                                invoice="SI-LIVE",
                            )
                        ],
                        invoices=[
                            invoice(
                                "SI-LIVE",
                                docstatus,
                            )
                        ],
                    )

    def test_missing_source_fails_closed(self):
        with self.assertRaisesRegex(
            frappe.ValidationError,
            "no longer exist",
        ):
            self._run(
                details=[],
            )

    def test_source_parent_change_fails_closed(self):
        with self.assertRaisesRegex(
            frappe.ValidationError,
            "changed while the invoice was being prepared",
        ):
            self._run(
                discovered={
                    "ECD-1": "EC-OLD",
                },
                parents=[
                    parent(
                        name="EC-OLD",
                    )
                ],
                details=[
                    detail(
                        parent="EC-NEW",
                    )
                ],
            )

    def test_project_or_submission_change_fails_closed(self):
        cases = (
            (
                [parent(project="ERP-OTHER")],
                [detail()],
                "another project",
            ),
            (
                [parent(docstatus=2)],
                [detail()],
                "no longer submitted",
            ),
            (
                [parent()],
                [detail(docstatus=2)],
                "no longer submitted",
            ),
        )

        for parents, details, message in cases:
            with self.subTest(
                message=message,
            ):
                with self.assertRaisesRegex(
                    frappe.ValidationError,
                    message,
                ):
                    self._run(
                        parents=parents,
                        details=details,
                    )

    def test_billable_and_policy_changes_fail_closed(self):
        with self.assertRaisesRegex(
            frappe.ValidationError,
            "no longer marked billable",
        ):
            self._run(
                details=[
                    detail(
                        billable=0,
                    )
                ],
            )

        with self.assertRaisesRegex(
            frappe.ValidationError,
            "configured as Not Billable",
        ):
            self._run(
                types=[
                    expense_type(
                        policy="Not Billable",
                    )
                ],
            )

    def test_locking_queries_are_deterministic_current_reads(self):
        db = Mock()

        db.sql.return_value = []

        expense_reservation._lock_parent_rows(
            db,
            ["EC-B", "EC-A"],
        )

        query = db.sql.call_args.args[0]
        params = db.sql.call_args.args[1]

        self.assertIn(
            "FOR UPDATE",
            query,
        )

        self.assertEqual(
            params["parents"],
            ("EC-A", "EC-B"),
        )

        db.reset_mock()

        db.sql.return_value = []

        expense_reservation._lock_detail_rows(
            db,
            ["ECD-B", "ECD-A"],
        )

        query = db.sql.call_args.args[0]
        params = db.sql.call_args.args[1]

        self.assertIn(
            "FOR UPDATE",
            query,
        )

        self.assertEqual(
            params["details"],
            ("ECD-A", "ECD-B"),
        )

    def test_generator_must_use_guard_before_expense_pricing(self):
        source = " ".join(
            inspect.getsource(
                erp_link.generate_expense_invoice
            ).split()
        )

        guard_at = source.index(
            "rows = guard_expense_claim_details("
        )

        pricing_at = source.index(
            "r.eff_amount = round("
        )

        self.assertLess(
            guard_at,
            pricing_at,
        )


if __name__ == "__main__":
    unittest.main()
