"""Phase B + C integration tests: lifecycle hooks & reconciliation.

Run with:
    bench run-tests --module batch_projects.tests.test_erp_link
"""
import unittest
import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import random_string


class TestERPLinkIntegration(FrappeTestCase):
    """Covers Phase B (after_insert / on_update hooks in bp_project.py)
    and Phase C (reconcile_erpnext_sync background job in erp_link.py)."""

    # ── class-level fixtures ──────────────────────────────────────────────

    @classmethod
    def setUpClass(cls):
        """Resolve shared fixtures once per class.

        Skips the entire suite when the site has no default company.
        Primes the tier cache to 'dev' so the 'integrations' feature is
        always unlocked during the test run — the real resolution path
        (gateway header / site_config / cached tier) has no HTTP request
        to work with inside a test runner.
        """
        super().setUpClass()
        cls.company = frappe.defaults.get_global_default("company")
        if not cls.company:
            raise unittest.SkipTest(
                "No default company set — cannot run ERPNext integration tests"
            )

        # Unlock every feature for the duration of this test class.
        # Rank 99 ('dev') sits above every _FEATURE_MIN_TIER entry.
        try:
            frappe.cache().set_value(
                "bp_current_tier", "dev", expires_in_sec=600
            )
        except Exception:
            pass  # cache may be unavailable; tests will use whatever tier is active

    @classmethod
    def tearDownClass(cls):
        """Remove the dev-tier cache entry so later test classes see the
        real tier again."""
        try:
            frappe.cache().delete_value("bp_current_tier")
        except Exception:
            pass
        super().tearDownClass()

    # ── per-test state ────────────────────────────────────────────────────

    def setUp(self):
        """Clean flag state + initialise tracking lists before every test."""
        frappe.flags.in_bp_project_sync = False
        self._bp_names = []
        self._erp_names = []

    def tearDown(self):
        """Delete every document created during the test, newest first.
        Swallow all exceptions — cleanup must never mask a test failure."""
        for name in reversed(self._erp_names):
            try:
                if frappe.db.exists("Project", name):
                    frappe.delete_doc(
                        "Project", name, ignore_permissions=True, force=True
                    )
            except Exception:
                pass
        for name in reversed(self._bp_names):
            try:
                if frappe.db.exists("BP Project", name):
                    frappe.delete_doc(
                        "BP Project", name, ignore_permissions=True, force=True
                    )
            except Exception:
                pass
        frappe.flags.in_bp_project_sync = False

    # ── helpers ───────────────────────────────────────────────────────────

    def _make_bp_project(self, **kwargs):
        """Insert a BP Project with a unique name and register for cleanup."""
        uid = random_string(6)
        doc = frappe.get_doc({
            "doctype": "BP Project",
            "project_name": f"ERP Link Test {uid}",
            "company": self.company,
            "key": uid.upper(),  # mandatory, <=6 chars — random_string(6) fits exactly
            **kwargs,
        })
        doc.insert()
        self._bp_names.append(doc.name)
        # Re-fetch so after_insert side-effects (auto-link) are visible.
        doc.reload()
        return doc

    def _track_erp(self, name):
        """Register an ERPNext Project name for cleanup and return it."""
        if name:
            self._erp_names.append(name)
        return name

    # ═══════════════════════════════════════════════════════════════════════
    # Test cases
    # ═══════════════════════════════════════════════════════════════════════

    def test_auto_link_on_insert(self):
        """BP Project insert with company → ERPNext Project auto-created."""
        doc = self._make_bp_project()
        erp = self._track_erp(doc.erpnext_project)

        self.assertIsNotNone(
            erp, "erpnext_project should be populated by after_insert"
        )
        self.assertTrue(
            frappe.db.exists("Project", erp),
            f"ERPNext Project '{erp}' should exist in tabProject",
        )
        self.assertEqual(
            frappe.db.get_value("Project", erp, "status"),
            "Open",
            "New ERPNext Project should start as 'Open'",
        )

    def test_status_writeback_mapping(self):
        """Status changes on BP Project → mapped status on ERPNext Project."""
        doc = self._make_bp_project()
        erp = self._track_erp(doc.erpnext_project)

        # Active → Open  (on_update via _BP_TO_ERP_STATUS)
        doc.status = "On Hold"
        doc.save()
        self.assertEqual(
            frappe.db.get_value("Project", erp, "status"),
            "Hold",
            "On Hold should map to Hold",
        )

        # Archived → Completed
        doc.status = "Archived"
        doc.save()
        self.assertEqual(
            frappe.db.get_value("Project", erp, "status"),
            "Completed",
            "Archived should map to Completed",
        )

        # Active → Open
        doc.status = "Active"
        doc.save()
        self.assertEqual(
            frappe.db.get_value("Project", erp, "status"),
            "Open",
            "Active should map to Open",
        )

    def test_recursion_guard_blocks_reentry(self):
        """frappe.flags.in_bp_project_sync = True prevents write-back."""
        doc = self._make_bp_project()
        erp = self._track_erp(doc.erpnext_project)

        # Baseline: normal sync works.
        doc.status = "On Hold"
        doc.save()
        self.assertEqual(
            frappe.db.get_value("Project", erp, "status"),
            "Hold",
        )

        # Activate the guard, then change status.
        frappe.flags.in_bp_project_sync = True
        try:
            doc.status = "Archived"
            doc.save()
            # The ERPNext Project MUST still show the previous value.
            self.assertEqual(
                frappe.db.get_value("Project", erp, "status"),
                "Hold",
                "ERPNext status should be unchanged when recursion guard is active",
            )
        finally:
            frappe.flags.in_bp_project_sync = False

        # After removing the guard, a normal save should sync again.
        doc.status = "Active"
        doc.save()
        self.assertEqual(
            frappe.db.get_value("Project", erp, "status"),
            "Open",
        )

    def test_reconciliation_job(self):
        """reconcile_erpnext_sync repairs a manually-induced status drift."""
        doc = self._make_bp_project()
        erp = self._track_erp(doc.erpnext_project)

        # Set BP Project to Archived → ERPNext goes to Completed.
        doc.status = "Archived"
        doc.save()
        self.assertEqual(
            frappe.db.get_value("Project", erp, "status"),
            "Completed",
        )

        # Simulate drift: manually revert ERPNext Project back to Open.
        frappe.db.set_value("Project", erp, "status", "Open")
        self.assertEqual(
            frappe.db.get_value("Project", erp, "status"),
            "Open",
            "Pre-condition: drift must be in place before reconcile runs",
        )

        # Run reconciliation.
        from batch_projects.api.erp_link import reconcile_erpnext_sync

        reconcile_erpnext_sync()

        # The test project's drift must be repaired.
        self.assertEqual(
            frappe.db.get_value("Project", erp, "status"),
            "Completed",
            "Reconcile should restore ERPNext Project status to match BP Project",
        )
