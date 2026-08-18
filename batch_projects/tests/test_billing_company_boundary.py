"""Regression tests for the authoritative batch-invoice company boundary."""

import unittest
from pathlib import Path
from unittest.mock import patch

import frappe

from batch_projects.api import erp_link


APP_ROOT = Path(__file__).resolve().parents[2]


def project(
    name,
    *,
    company,
    client="CUSTOMER-1",
    currency="USD",
    erp_project=None,
):
    return frappe._dict({
        "name": name,
        "project_name": name,
        "client": client,
        "company": company,
        "currency": currency,
        "hourly_rate": 100,
        "erpnext_project": erp_project or f"ERP-{name}",
    })


def row(erp_project, hours=1):
    return frappe._dict({
        "erp_project": erp_project,
        "hours": hours,
        "billing_hours": hours,
        "billing_rate": 100,
        "timesheet_currency": "USD",
    })


class TestBillingCompanyBoundary(unittest.TestCase):
    def test_missing_explicit_and_default_company_fails_closed(self):
        p = project(
            "BP-NO-COMPANY",
            company="",
        )

        with patch.object(
            erp_link.frappe.defaults,
            "get_global_default",
            return_value=None,
        ):
            with self.assertRaisesRegex(
                frappe.ValidationError,
                "global default Company",
            ):
                erp_link._effective_project_company(p)

    def test_blank_and_explicit_same_default_are_order_independent(self):
        blank = project(
            "BP-BLANK",
            company="",
        )
        explicit = project(
            "BP-EXPLICIT",
            company="COMPANY-A",
        )

        with patch.object(
            erp_link.frappe.defaults,
            "get_global_default",
            return_value="COMPANY-A",
        ):
            forward = erp_link._validated_invoice_company(
                [blank, explicit]
            )
            reverse = erp_link._validated_invoice_company(
                [explicit, blank]
            )

        self.assertEqual(
            forward,
            "COMPANY-A",
        )
        self.assertEqual(
            reverse,
            "COMPANY-A",
        )

    def test_generate_invoice_rejects_mixed_companies_before_candidate_sql(self):
        projects = {
            "BP-A": project(
                "BP-A",
                company="COMPANY-A",
            ),
            "BP-B": project(
                "BP-B",
                company="COMPANY-B",
            ),
        }

        with (
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
            patch.object(
                erp_link.frappe,
                "get_doc",
                side_effect=lambda doctype, name: projects[name],
            ),
            patch.object(
                erp_link.frappe.db,
                "sql",
            ) as sql,
            patch.object(
                erp_link.frappe,
                "new_doc",
            ) as new_doc,
        ):
            with self.assertRaisesRegex(
                frappe.ValidationError,
                "different companies",
            ):
                erp_link.generate_invoice(
                    ["BP-A", "BP-B"]
                )

        sql.assert_not_called()
        new_doc.assert_not_called()

    def test_candidates_split_same_client_across_effective_companies(self):
        projects = [
            project(
                "BP-A",
                company="COMPANY-A",
                erp_project="ERP-A",
            ),
            project(
                "BP-B",
                company="COMPANY-B",
                erp_project="ERP-B",
            ),
        ]

        rows = [
            row("ERP-A", 1),
            row("ERP-B", 2),
        ]

        seen_companies = []

        def resolve_currency(
            company,
            customer,
            currency,
            conversion_rate,
            project_currency=None,
        ):
            seen_companies.append(company)
            self.assertEqual(
                customer,
                "CUSTOMER-1",
            )
            self.assertEqual(
                project_currency,
                "USD",
            )
            return "USD", "USD", 1.0

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
                return_value=projects,
            ),
            patch.object(
                erp_link.frappe.db,
                "sql",
                return_value=rows,
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
                side_effect=resolve_currency,
            ),
            patch.object(
                erp_link,
                "_effective_billing_rate",
                return_value=100,
            ),
        ):
            result = (
                erp_link.get_batch_invoice_candidates()
            )

        self.assertEqual(
            len(result),
            2,
        )

        self.assertEqual(
            {entry["company"] for entry in result},
            {"COMPANY-A", "COMPANY-B"},
        )

        self.assertEqual(
            {entry["client"] for entry in result},
            {"CUSTOMER-1"},
        )

        project_companies = {
            p["bp_project"]: p["company"]
            for entry in result
            for p in entry["projects"]
        }

        self.assertEqual(
            project_companies,
            {
                "BP-A": "COMPANY-A",
                "BP-B": "COMPANY-B",
            },
        )

        self.assertEqual(
            set(seen_companies),
            {"COMPANY-A", "COMPANY-B"},
        )

    def test_candidates_coalesce_blank_company_with_same_default(self):
        projects = [
            project(
                "BP-BLANK",
                company="",
                erp_project="ERP-BLANK",
            ),
            project(
                "BP-EXPLICIT",
                company="COMPANY-A",
                erp_project="ERP-EXPLICIT",
            ),
        ]

        rows = [
            row("ERP-BLANK", 1),
            row("ERP-EXPLICIT", 2),
        ]

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
                erp_link.frappe.defaults,
                "get_global_default",
                return_value="COMPANY-A",
            ),
            patch.object(
                erp_link.frappe,
                "get_all",
                return_value=projects,
            ),
            patch.object(
                erp_link.frappe.db,
                "sql",
                return_value=rows,
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
                return_value=100,
            ),
        ):
            result = (
                erp_link.get_batch_invoice_candidates()
            )

        self.assertEqual(
            len(result),
            1,
        )

        entry = result[0]

        self.assertEqual(
            entry["company"],
            "COMPANY-A",
        )

        self.assertEqual(
            {p["bp_project"] for p in entry["projects"]},
            {"BP-BLANK", "BP-EXPLICIT"},
        )

        self.assertTrue(
            all(
                p["company"] == "COMPANY-A"
                for p in entry["projects"]
            )
        )

    def test_batch_ui_is_company_aware(self):
        page = (
            APP_ROOT
            / "frontend"
            / "src"
            / "pages"
            / "BatchInvoicing.vue"
        ).read_text()

        self.assertIn(
            ':key="batchKey(c)"',
            page,
        )

        self.assertIn(
            "function batchKey(c)",
            page,
        )

        self.assertIn(
            "{{ c.company }}",
            page,
        )

        self.assertIn(
            "company: c.company",
            page,
        )

        self.assertIn(
            "busy.value = confirm.batchKey",
            page,
        )

        self.assertNotIn(
            'busy === c.client',
            page,
        )


if __name__ == "__main__":
    unittest.main()
