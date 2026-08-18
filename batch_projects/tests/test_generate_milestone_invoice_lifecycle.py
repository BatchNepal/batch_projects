"""Behavioral regressions for generate_milestone_invoice."""

import unittest
from unittest.mock import patch

import frappe

from batch_projects.api import erp_link


class _FakeSalesInvoice:
    def __init__(self):
        self.name = "SINV-MILESTONE-DRAFT"
        self.flags = frappe._dict()
        self.items = []
        self.currency = None
        self.conversion_rate = None
        self.customer = None
        self.company = None
        self.project = None
        self.grand_total = 5000

    def append(self, fieldname, value):
        if fieldname != "items":
            raise AssertionError(
                f"unexpected child table: {fieldname}"
            )
        row = frappe._dict(value)
        self.items.append(row)
        return row

    def run_method(self, method):
        if method != "set_missing_values":
            raise AssertionError(
                f"unexpected Sales Invoice method: {method}"
            )

    def insert(self, ignore_permissions=False):
        if not ignore_permissions:
            raise AssertionError(
                "milestone invoice must insert after BP authorization"
            )


def _auth_milestone():
    return frappe._dict({
        "name": "MS-LIFECYCLE",
        "project": "BP-PROJECT",
    })


def _locked_project():
    return frappe._dict({
        "name": "BP-PROJECT",
        "project_name": "Lifecycle Project",
        "erpnext_project": "ERP-PROJECT",
        "client": "CUSTOMER-1",
        "company": "Test Company",
        "currency": "USD",
        "budget_amount": 10000,
    })


def _locked_milestone(**overrides):
    row = frappe._dict({
        "name": "MS-LIFECYCLE",
        "project": "BP-PROJECT",
        "title": "Design complete",
        "status": "Completed",
        "billing_type": "Fixed Amount",
        "invoice_amount": 5000,
        "invoice_percent": 0,
        "invoice_status": "Not Invoiced",
        "sales_invoice": "",
    })
    row.update(overrides)
    return row


class TestGenerateMilestoneInvoiceLifecycle(unittest.TestCase):
    def test_draft_creation_persists_draft_not_invoiced(self):
        invoice = _FakeSalesInvoice()

        with (
            patch.object(
                erp_link.frappe,
                "get_doc",
                return_value=_auth_milestone(),
            ),
            patch.object(
                erp_link,
                "_check_permission",
            ),
            patch(
                "batch_projects.access.require_capability",
            ),
            patch.object(
                erp_link,
                "require_feature",
            ),
            patch(
                "batch_projects.milestone_billing.lock_generation_scope",
                return_value=(
                    _locked_project(),
                    _locked_milestone(),
                ),
            ),
            patch.object(
                erp_link.frappe.db,
                "get_value",
                return_value="Income - TC",
            ),
            patch.object(
                erp_link,
                "_resolve_invoice_currency",
                return_value=(
                    "NPR",
                    "USD",
                    137.5,
                ),
            ),
            patch.object(
                erp_link.frappe,
                "new_doc",
                return_value=invoice,
            ),
            patch.object(
                erp_link.frappe.db,
                "set_value",
            ) as set_value,
            patch.object(
                erp_link.frappe.share,
                "add_docshare",
            ),
            patch.object(
                erp_link.frappe.db,
                "commit",
            ),
        ):
            result = erp_link.generate_milestone_invoice(
                "MS-LIFECYCLE"
            )

        self.assertEqual(
            result["invoice_status"],
            "Draft",
        )
        self.assertEqual(
            result["sales_invoice"],
            "SINV-MILESTONE-DRAFT",
        )

        self.assertEqual(
            len(invoice.items),
            1,
        )
        self.assertEqual(
            invoice.items[0].rate,
            5000,
        )

        set_value.assert_called_once_with(
            "BP Milestone",
            "MS-LIFECYCLE",
            {
                "invoice_status": "Draft",
                "sales_invoice": "SINV-MILESTONE-DRAFT",
            },
            update_modified=False,
        )

    def test_existing_draft_refuses_second_generation(self):
        with (
            patch.object(
                erp_link.frappe,
                "get_doc",
                return_value=_auth_milestone(),
            ),
            patch.object(
                erp_link,
                "_check_permission",
            ),
            patch(
                "batch_projects.access.require_capability",
            ),
            patch.object(
                erp_link,
                "require_feature",
            ),
            patch(
                "batch_projects.milestone_billing.lock_generation_scope",
                return_value=(
                    _locked_project(),
                    _locked_milestone(
                        invoice_status="Draft",
                        sales_invoice="SINV-EXISTING",
                    ),
                ),
            ),
            patch.object(
                erp_link.frappe,
                "new_doc",
            ) as new_doc,
        ):
            with self.assertRaisesRegex(
                frappe.ValidationError,
                "already has draft invoice SINV-EXISTING",
            ):
                erp_link.generate_milestone_invoice(
                    "MS-LIFECYCLE"
                )

        new_doc.assert_not_called()


if __name__ == "__main__":
    unittest.main()
