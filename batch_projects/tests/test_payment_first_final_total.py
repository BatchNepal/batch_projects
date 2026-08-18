"""Regressions for payment-first final ERPNext Sales Invoice equality."""

import inspect
import unittest
from unittest.mock import patch

import frappe

from erpnext.accounts.doctype.sales_invoice.sales_invoice import (
    SalesInvoice,
)

from batch_projects import billing_reservation
from batch_projects.api import erp_link


class _FinalTotalDoc:
    def __init__(
        self,
        *,
        expected=None,
        expected_currency="USD",
        currency="USD",
        grand_total=0,
        rounded_total=0,
        rounded_disabled=False,
        precision=2,
    ):
        self.flags = frappe._dict()

        if expected is not None:
            self.flags.bp_expected_received_amount = (
                expected
            )

            self.flags.bp_expected_received_currency = (
                expected_currency
            )

        self.currency = currency
        self.grand_total = grand_total
        self.rounded_total = rounded_total
        self._rounded_disabled = rounded_disabled
        self._precision = precision

    def get(self, field):
        return getattr(
            self,
            field,
            None,
        )

    def precision(self, field):
        return self._precision

    def is_rounded_total_disabled(self):
        return self._rounded_disabled


class TestPaymentFirstFinalTotal(unittest.TestCase):
    def test_native_invoice_without_flags_mapping_is_untouched(self):
        # validate_sales_invoice_sources is a site-wide Sales Invoice hook.
        # Absence of BatchProjects transient state must therefore be a cheap
        # no-op even for lightweight/custom document-like objects.
        doc = frappe._dict({
            "name": "SINV-NATIVE",
        })

        self.assertIsNone(
            billing_reservation
            ._validate_payment_first_final_total(
                doc
            )
        )

    def test_native_invoice_without_transient_contract_is_untouched(self):
        doc = _FinalTotalDoc(
            grand_total=999,
            rounded_total=1000,
        )

        self.assertIsNone(
            billing_reservation
            ._validate_payment_first_final_total(
                doc
            )
        )

    def test_rounded_total_is_authoritative_when_enabled(self):
        doc = _FinalTotalDoc(
            expected=100,
            grand_total=99.60,
            rounded_total=100,
            rounded_disabled=False,
        )

        billing_reservation._validate_payment_first_final_total(
            doc
        )

        doc = _FinalTotalDoc(
            expected=99.60,
            grand_total=99.60,
            rounded_total=100,
            rounded_disabled=False,
        )

        with self.assertRaisesRegex(
            frappe.ValidationError,
            "final rounded total 100",
        ):
            billing_reservation._validate_payment_first_final_total(
                doc
            )

    def test_grand_total_is_authoritative_when_rounding_disabled(self):
        doc = _FinalTotalDoc(
            expected=99.60,
            grand_total=99.60,
            rounded_total=100,
            rounded_disabled=True,
        )

        billing_reservation._validate_payment_first_final_total(
            doc
        )

        doc = _FinalTotalDoc(
            expected=100,
            grand_total=99.60,
            rounded_total=100,
            rounded_disabled=True,
        )

        with self.assertRaisesRegex(
            frappe.ValidationError,
            "final grand total 99.6",
        ):
            billing_reservation._validate_payment_first_final_total(
                doc
            )

    def test_currency_precision_is_respected_including_zero_precision(self):
        zero_precision = _FinalTotalDoc(
            expected=101.4,
            grand_total=101.49,
            rounded_total=101.49,
            rounded_disabled=True,
            precision=0,
        )

        # Both values are interpreted at the actual ERPNext Currency field
        # precision, not hard-coded two-decimal cents.
        billing_reservation._validate_payment_first_final_total(
            zero_precision
        )

        three_precision = _FinalTotalDoc(
            expected=10.123,
            grand_total=10.1234,
            rounded_total=10.1234,
            rounded_disabled=True,
            precision=3,
        )

        billing_reservation._validate_payment_first_final_total(
            three_precision
        )

    def test_tax_or_charge_difference_fails_payment_first(self):
        doc = _FinalTotalDoc(
            expected=100,
            grand_total=118,
            rounded_total=118,
            rounded_disabled=True,
        )

        with self.assertRaisesRegex(
            frappe.ValidationError,
            "final grand total 118",
        ):
            billing_reservation._validate_payment_first_final_total(
                doc
            )

    def test_rate_quantity_round_trip_difference_fails(self):
        # A grouped invoice line can legitimately exceed 100 billable hours.
        #
        # Intended source-row total:
        #     558.13
        #
        # generate_invoice emits:
        #     qty  = 159.76
        #     rate = round(558.13 / 159.76, 4) = 3.4936
        #
        # ERPNext then recalculates:
        #     round(159.76 * 3.4936, 2) = 558.14
        #
        # The old #29-era pre-insert check compared expected=558.13 against
        # the intermediate source-row total 558.13 and incorrectly passed.
        hours = 159.76
        intended = 558.13

        rate = round(
            intended / hours,
            4,
        )

        erpnext_amount = round(
            hours * rate,
            2,
        )

        self.assertEqual(
            rate,
            3.4936,
        )

        self.assertEqual(
            erpnext_amount,
            558.14,
        )

        doc = _FinalTotalDoc(
            expected=intended,
            grand_total=erpnext_amount,
            rounded_total=erpnext_amount,
            rounded_disabled=True,
        )

        with self.assertRaisesRegex(
            frappe.ValidationError,
            "558.14",
        ):
            billing_reservation._validate_payment_first_final_total(
                doc
            )

    def test_currency_change_during_erpnext_validation_fails_closed(self):
        doc = _FinalTotalDoc(
            expected=100,
            expected_currency="USD",
            currency="EUR",
            grand_total=100,
            rounded_total=100,
            rounded_disabled=True,
        )

        with self.assertRaisesRegex(
            frappe.ValidationError,
            "changed the invoice currency",
        ):
            billing_reservation._validate_payment_first_final_total(
                doc
            )

    def test_nonfinite_transient_contract_fails_closed(self):
        for value in (
            float("nan"),
            float("inf"),
            True,
        ):
            with self.subTest(
                value=value,
            ):
                doc = _FinalTotalDoc(
                    expected=value,
                    grand_total=0,
                    rounded_total=0,
                    rounded_disabled=True,
                )

                with self.assertRaisesRegex(
                    frappe.ValidationError,
                    "finite number",
                ):
                    billing_reservation._validate_payment_first_final_total(
                        doc
                    )

    def test_real_frappe_validate_hook_runs_after_controller_validate(self):
        """Prove the actual Frappe hook order used by #34.

        No Sales Invoice is inserted here. We replace the ERPNext controller
        validate() body with a deterministic final-total calculation, then call
        Document.run_method("validate"). Frappe must execute that controller
        method first and our configured Sales Invoice doc-event hook second.
        """
        doc = frappe.new_doc(
            "Sales Invoice"
        )

        doc.currency = "USD"
        doc.disable_rounded_total = 1

        doc.flags.bp_expected_received_amount = (
            100
        )

        doc.flags.bp_expected_received_currency = (
            "USD"
        )

        controller_seen = {
            "value": False,
        }

        def fake_controller_validate(self):
            controller_seen[
                "value"
            ] = True

            # This represents the FINAL value produced by ERPNext core.
            self.grand_total = 100.01

        with patch.object(
            SalesInvoice,
            "validate",
            fake_controller_validate,
        ):
            with self.assertRaisesRegex(
                frappe.ValidationError,
                "final grand total 100.01",
            ):
                doc.run_method(
                    "validate"
                )

        self.assertTrue(
            controller_seen["value"]
        )

    def test_generate_invoice_no_longer_checks_intermediate_row_sum(self):
        source = inspect.getsource(
            erp_link.generate_invoice
        )

        normalized = " ".join(
            source.split()
        )

        self.assertNotIn(
            "computed = round(sum(r.eff_amount for r in rows), 2)",
            normalized,
        )

        self.assertIn(
            "bp_expected_received_amount",
            source,
        )

        self.assertIn(
            "bp_expected_received_currency",
            source,
        )


if __name__ == "__main__":
    unittest.main()
