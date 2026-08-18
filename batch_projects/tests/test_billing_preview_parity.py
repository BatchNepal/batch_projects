"""Regressions for batch-invoice preview ↔ generation parity."""

import inspect
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import frappe

from batch_projects import billing_reservation
from batch_projects.api import erp_link


APP_ROOT = Path(__file__).resolve().parents[2]


def candidate(
    name,
    *,
    billing_hours=1,
    worked_hours=None,
):
    if worked_hours is None:
        worked_hours = billing_hours

    return frappe._dict({
        "name": name,
        "erp_project": "ERP-PREVIEW",
        "hours": worked_hours,
        "billing_hours": billing_hours,
        "billing_rate": 0,
        "timesheet_currency": "USD",
    })


def preview_project():
    return frappe._dict({
        "name": "BP-PREVIEW",
        "project_name": "Preview Project",
        "client": "CUSTOMER-PREVIEW",
        "company": "COMPANY-PREVIEW",
        "currency": "USD",
        "hourly_rate": 100,
        "erpnext_project": "ERP-PREVIEW",
    })


class _PayableDoc:
    def __init__(
        self,
        *,
        grand_total,
        rounded_total,
        rounded_disabled,
    ):
        self.grand_total = grand_total
        self.rounded_total = rounded_total
        self._rounded_disabled = (
            rounded_disabled
        )

    def get(self, field):
        return getattr(
            self,
            field,
            None,
        )

    def is_rounded_total_disabled(self):
        return self._rounded_disabled


class TestBillingPreviewParity(unittest.TestCase):
    def _preview(
        self,
        rows,
        *,
        effective_rate=100,
        claimed=(),
    ):
        p = preview_project()

        with (
            patch.object(
                erp_link,
                "require_feature",
            ),
            patch.object(
                erp_link,
                "_require_system_user",
            ),
            patch(
                "batch_projects.permissions.get_accessible_projects",
                return_value=None,
            ),
            patch.object(
                erp_link.frappe,
                "get_all",
                return_value=[p],
            ),
            patch.object(
                erp_link.frappe.db,
                "sql",
                return_value=rows,
            ),
            patch.object(
                erp_link,
                "get_live_claimed_timesheet_details",
                return_value=set(claimed),
            ),
            patch.object(
                erp_link,
                "_service_item",
                return_value=None,
            ),
            patch.object(
                erp_link,
                "_price_list_rate",
                return_value=None,
            ),
            patch.object(
                erp_link,
                "_resolve_invoice_currency",
                return_value=(
                    "USD",
                    "USD",
                    1.0,
                ),
            ),
            patch.object(
                erp_link,
                "_effective_billing_rate",
                return_value=effective_rate,
            ) as rate,
        ):
            result = (
                erp_link
                .get_batch_invoice_candidates()
            )

        return result, rate

    def test_preview_live_claim_reader_is_read_only_with_same_live_states(self):
        db = Mock()

        db.sql.return_value = [
            frappe._dict({
                "timesheet_detail": "TSD-A",
                "parent": "SINV-DRAFT",
                "docstatus": 0,
            }),
            frappe._dict({
                "timesheet_detail": "TSD-B",
                "parent": "SINV-SUBMITTED",
                "docstatus": 1,
            }),
        ]

        claimed = (
            billing_reservation
            ._live_claimed_timesheet_details_with_db(
                db,
                [
                    "TSD-B",
                    "TSD-A",
                ],
            )
        )

        self.assertEqual(
            claimed,
            {
                "TSD-A",
                "TSD-B",
            },
        )

        query = db.sql.call_args.args[0]
        params = db.sql.call_args.args[1]

        self.assertIn(
            "si.docstatus IN (0, 1)",
            query,
        )

        self.assertNotIn(
            "FOR UPDATE",
            query,
        )

        self.assertEqual(
            params["details"],
            (
                "TSD-A",
                "TSD-B",
            ),
        )

    def test_preview_excludes_live_draft_and_submitted_claimants(self):
        result, _rate = self._preview(
            [
                candidate(
                    "TSD-FREE",
                    billing_hours=1,
                ),
                candidate(
                    "TSD-DRAFT",
                    billing_hours=2,
                ),
                candidate(
                    "TSD-SUBMITTED",
                    billing_hours=3,
                ),
            ],
            claimed={
                "TSD-DRAFT",
                "TSD-SUBMITTED",
            },
        )

        self.assertEqual(
            len(result),
            1,
        )

        entry = result[0]

        self.assertEqual(
            entry["total_hours"],
            1.0,
        )

        self.assertEqual(
            entry["total_amount"],
            100.0,
        )

        self.assertEqual(
            entry["projects"][0]["amount"],
            100.0,
        )

    def test_claim_filter_runs_before_rate_validation(self):
        result, rate = self._preview(
            [
                candidate(
                    "TSD-RESERVED",
                    billing_hours=1,
                )
            ],
            effective_rate=0,
            claimed={
                "TSD-RESERVED",
            },
        )

        self.assertEqual(
            result,
            [],
        )

        rate.assert_not_called()

    def test_preview_sums_row_rounded_amounts(self):
        # Per source:
        #   1h × 0.006 = 0.006 -> 0.01
        #
        # Two sources therefore preview at 0.02. The old preview accumulated
        # 0.012 first and rounded once at project level -> 0.01.
        result, _rate = self._preview(
            [
                candidate(
                    "TSD-A",
                    billing_hours=1,
                ),
                candidate(
                    "TSD-B",
                    billing_hours=1,
                ),
            ],
            effective_rate=0.006,
        )

        self.assertEqual(
            result[0]["projects"][0]["amount"],
            0.02,
        )

        self.assertEqual(
            result[0]["total_amount"],
            0.02,
        )

    def test_preview_fails_closed_on_required_zero_rate(self):
        with self.assertRaisesRegex(
            frappe.ValidationError,
            "No billing rate resolved for: Preview Project",
        ):
            self._preview(
                [
                    candidate(
                        "TSD-NO-RATE",
                        billing_hours=1,
                    )
                ],
                effective_rate=0,
            )

    def test_zero_billing_hours_does_not_require_rate(self):
        result, _rate = self._preview(
            [
                candidate(
                    "TSD-ZERO",
                    billing_hours=0,
                    worked_hours=5,
                )
            ],
            effective_rate=0,
        )

        self.assertEqual(
            result[0]["total_hours"],
            0.0,
        )

        self.assertEqual(
            result[0]["total_amount"],
            0.0,
        )

    def test_generation_and_preview_use_same_row_amount_primitive(self):
        generation = inspect.getsource(
            erp_link.generate_invoice
        )

        preview = inspect.getsource(
            erp_link.get_batch_invoice_candidates
        )

        self.assertIn(
            "r.eff_amount = _billing_row_amount(",
            generation,
        )

        self.assertIn(
            'agg["amount"] += _billing_row_amount(',
            preview,
        )

        row = candidate(
            "TSD-ROUND",
            billing_hours=1,
        )

        self.assertEqual(
            erp_link._billing_row_amount(
                row,
                0.006,
            ),
            0.01,
        )

    def test_payable_total_matches_erpnext_rounding_mode(self):
        rounded = _PayableDoc(
            grand_total=99.60,
            rounded_total=100,
            rounded_disabled=False,
        )

        self.assertEqual(
            erp_link._sales_invoice_payable_total(
                rounded
            ),
            100.0,
        )

        unrounded = _PayableDoc(
            grand_total=99.60,
            rounded_total=0,
            rounded_disabled=True,
        )

        self.assertEqual(
            erp_link._sales_invoice_payable_total(
                unrounded
            ),
            99.60,
        )

        # Backward-compatible fake/non-controller documents fall back to
        # grand_total instead of requiring ERPNext controller methods.
        fake = frappe._dict({
            "grand_total": 12.34,
        })

        self.assertEqual(
            erp_link._sales_invoice_payable_total(
                fake
            ),
            12.34,
        )

    def test_batch_success_toast_uses_payable_total(self):
        page = (
            APP_ROOT
            / "frontend"
            / "src"
            / "pages"
            / "BatchInvoicing.vue"
        ).read_text()

        self.assertIn(
            "res.payable_total ?? res.grand_total",
            page,
        )


if __name__ == "__main__":
    unittest.main()
