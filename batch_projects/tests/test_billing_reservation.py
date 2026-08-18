"""Unit regressions for concurrency-safe Timesheet billing reservations."""

import unittest
from unittest.mock import Mock, patch

import frappe

from batch_projects import billing_reservation


def source(
    name,
    *,
    project="ERP-BP-TEST",
    bp_task="TASK-BP-TEST",
    sales_invoice="",
):
    return frappe._dict({
        "name": name,
        "parent": "TS-BP-TEST",
        "project": project,
        "custom_bp_task": bp_task,
        "sales_invoice": sales_invoice,
    })


class TestBillingReservation(unittest.TestCase):
    def test_normalization_is_deterministic(self):
        self.assertEqual(
            billing_reservation._normalize_detail_names(
                ["TSD-B", " TSD-A "]
            ),
            ["TSD-A", "TSD-B"],
        )

    def test_duplicate_within_invoice_is_refused(self):
        db = Mock()

        with self.assertRaisesRegex(
            frappe.ValidationError,
            "more than once",
        ):
            billing_reservation._guard_timesheet_details_with_db(
                db,
                ["TSD-A", "TSD-A"],
                enforce_all_sources=True,
            )

        db.sql.assert_not_called()

    def test_source_locks_are_ordered_and_current(self):
        db = Mock()
        db.sql.side_effect = [
            [
                source("TSD-A"),
                source("TSD-B"),
            ],
            [],
        ]

        result = (
            billing_reservation._guard_timesheet_details_with_db(
                db,
                ["TSD-B", "TSD-A"],
                enforce_all_sources=True,
            )
        )

        self.assertEqual(result, ["TSD-A", "TSD-B"])

        query = db.sql.call_args_list[0].args[0]
        params = db.sql.call_args_list[0].args[1]

        self.assertIn("ORDER BY tsd.name ASC", query)
        self.assertIn("FOR UPDATE", query)
        self.assertEqual(
            params["details"],
            ("TSD-A", "TSD-B"),
        )

    def test_missing_enforced_source_is_refused(self):
        db = Mock()
        db.sql.return_value = [source("TSD-A")]

        with self.assertRaisesRegex(
            frappe.ValidationError,
            "no longer exist",
        ):
            billing_reservation._guard_timesheet_details_with_db(
                db,
                ["TSD-A", "TSD-B"],
                enforce_all_sources=True,
            )

    def test_non_bp_native_invoice_is_noop(self):
        db = Mock()
        db.sql.side_effect = [
            [
                source(
                    "TSD-NATIVE",
                    project="ERP-NATIVE",
                    bp_task="",
                )
            ],
            [],  # no BP Project links this ERPNext Project
        ]

        result = (
            billing_reservation._guard_timesheet_details_with_db(
                db,
                ["TSD-NATIVE"],
                enforce_all_sources=False,
            )
        )

        self.assertEqual(result, [])
        # Source lock + BP ownership lookup only. No live-claim query.
        self.assertEqual(db.sql.call_count, 2)

    def test_already_billed_source_is_refused(self):
        db = Mock()
        db.sql.return_value = [
            source(
                "TSD-BILLED",
                sales_invoice="SINV-SUBMITTED",
            )
        ]

        with self.assertRaisesRegex(
            frappe.ValidationError,
            "SINV-SUBMITTED",
        ):
            billing_reservation._guard_timesheet_details_with_db(
                db,
                ["TSD-BILLED"],
                enforce_all_sources=True,
            )

        self.assertEqual(db.sql.call_count, 1)

    def test_existing_draft_conflict_names_blocker(self):
        db = Mock()
        db.sql.side_effect = [
            [source("TSD-A")],
            [
                frappe._dict({
                    "timesheet_detail": "TSD-A",
                    "parent": "SINV-DRAFT-001",
                    "docstatus": 0,
                })
            ],
        ]

        with self.assertRaisesRegex(
            frappe.ValidationError,
            "SINV-DRAFT-001",
        ):
            billing_reservation._guard_timesheet_details_with_db(
                db,
                ["TSD-A"],
                enforce_all_sources=True,
            )

    def test_submitted_child_claim_is_also_refused(self):
        db = Mock()
        db.sql.side_effect = [
            [source("TSD-A")],
            [
                frappe._dict({
                    "timesheet_detail": "TSD-A",
                    "parent": "SINV-SUB-001",
                    "docstatus": 1,
                })
            ],
        ]

        with self.assertRaisesRegex(
            frappe.ValidationError,
            "SINV-SUB-001",
        ):
            billing_reservation._guard_timesheet_details_with_db(
                db,
                ["TSD-A"],
                enforce_all_sources=True,
            )

    def test_claim_lookup_is_current_locking_read(self):
        db = Mock()
        db.sql.side_effect = [
            [source("TSD-A")],
            [],
        ]

        billing_reservation._guard_timesheet_details_with_db(
            db,
            ["TSD-A"],
            enforce_all_sources=True,
        )

        query = db.sql.call_args_list[1].args[0]

        self.assertIn(
            "sit.timesheet_detail IN %(details)s",
            query,
        )
        self.assertIn("si.docstatus IN (0, 1)", query)
        self.assertIn("FOR UPDATE", query)

    def test_same_draft_is_self_excluded(self):
        db = Mock()
        db.sql.side_effect = [
            [source("TSD-A")],
            [],
        ]

        result = (
            billing_reservation._guard_timesheet_details_with_db(
                db,
                ["TSD-A"],
                current_invoice="SINV-ME",
                enforce_all_sources=True,
            )
        )

        self.assertEqual(result, ["TSD-A"])

        query = db.sql.call_args_list[1].args[0]
        params = db.sql.call_args_list[1].args[1]

        self.assertIn(
            "sit.parent != %(current_invoice)s",
            query,
        )
        self.assertEqual(
            params["current_invoice"],
            "SINV-ME",
        )

    def test_sales_invoice_hook_uses_shared_guard(self):
        doc = frappe._dict({
            "name": "SINV-HOOK",
            "timesheets": [
                frappe._dict({
                    "timesheet_detail": "TSD-HOOK",
                })
            ],
        })

        with patch.object(
            billing_reservation,
            "guard_timesheet_details",
        ) as guard:
            billing_reservation.validate_sales_invoice_sources(
                doc,
                "validate",
            )

        guard.assert_called_once_with(
            ["TSD-HOOK"],
            current_invoice="SINV-HOOK",
            enforce_all_sources=False,
        )


if __name__ == "__main__":
    unittest.main()
