"""Regression coverage for the P0 ownership-boundary recovery PR (fresh
security audit, 2026-08). Each test class is one confirmed finding:

  1. BP Report: private rows readable/writable/deletable by other users;
     projectless rows had no authorization at all — TestReportOwnershipBoundary.
  2. BP Dashboard: workspace-visible rows editable/deletable by any project
     Member; projectless workspace rows by any authenticated caller —
     TestDashboardOwnershipBoundary.
  3. BP View Preference / BP Notification Mute: personal rows keyed on
     `user`, but generic REST had only the project-level gate —
     TestPersonalRowOwnershipBoundary.
  4. update_intake_form wrote every field except a metadata denylist, so
     `project` was movable across the authorization boundary —
     TestIntakeFormProjectMoveBoundary.

Run with:
    bench run-tests --module batch_projects.tests.test_ownership_boundary_recovery
"""

import json

import frappe
from frappe.tests.utils import FrappeTestCase

from batch_projects.api import board, dashboards, forms
from batch_projects import permissions

_patched_gates = None


def setUpModule():
    """The entitlement tier gate (require_feature) resolves to starter in the
    test environment — the gate itself is not what this module exercises, so
    patch the shared entrypoint the BP Report / BP Dashboard doctype
    validators import at call time. api.dashboards/api.forms are patched
    per-class (they bind the symbol at import time)."""
    global _patched_gates
    from unittest.mock import patch
    _patched_gates = patch("batch_projects.entitlements.require_feature",
                           side_effect=lambda *a, **k: None)
    _patched_gates.start()


def tearDownModule():
    global _patched_gates
    if _patched_gates is not None:
        _patched_gates.stop()
        _patched_gates = None


def _ensure_user(email):
    """Throwaway System User fixture — same convention as
    test_read_boundary_recovery.py: never a real signup, never a real email."""
    if not frappe.db.exists("User", email):
        frappe.get_doc(
            {
                "doctype": "User",
                "email": email,
                "first_name": email.split("@")[0],
                "user_type": "System User",
                "enabled": 1,
                "send_welcome_email": 0,
            }
        ).insert(ignore_permissions=True)
    from batch_projects import access

    access.ensure_member_role(email)
    return email


def _delete_user(email):
    frappe.set_user("Administrator")
    if frappe.db.exists("User", email):
        frappe.delete_doc("User", email, ignore_permissions=True, force=True)


def _make_project(key, project_name, visibility="workspace"):
    frappe.set_user("Administrator")
    _delete_project(key)
    return board.create_project(
        project_name=project_name,
        key=key,
        visibility=visibility,
        workflow_states=json.dumps(
            [{"name": "To Do", "color": "#6B7280", "category": "open"}]
        ),
        issue_types=json.dumps(
            [{"name": "Task", "color": "#0B6BCB", "icon": "CheckSquare"}]
        ),
    )["name"]


def _add_project_member(project, user, role):
    """Idempotent: replaces any existing membership row for `user` — tests
    running in alphabetical order must not leak a role granted by an earlier
    test into a later one."""
    frappe.set_user("Administrator")
    doc = frappe.get_doc("BP Project", project)
    doc.members = [r for r in (doc.members or []) if r.user != user]
    doc.append("members", {"user": user, "role": role})
    doc.save(ignore_permissions=True)
    frappe.db.commit()


def _delete_project(key):
    frappe.set_user("Administrator")
    name = frappe.db.get_value("BP Project", {"key": key}, "name")
    if name:
        frappe.delete_doc("BP Project", name, ignore_permissions=True, force=True)


def _make_report(project, report_name, visibility="private", owner=None):
    frappe.set_user("Administrator")
    doc = frappe.get_doc(
        {
            "doctype": "BP Report",
            "report_name": report_name,
            "project": project or None,
            "visibility": visibility,
            "layout": "[]",
        }
    )
    doc.insert(ignore_permissions=True)
    if owner:
        frappe.db.set_value("BP Report", doc.name, "owner", owner)
    frappe.db.commit()
    return doc.name


def _make_dashboard(project, dashboard_name, visibility="private", owner=None):
    frappe.set_user("Administrator")
    doc = frappe.get_doc(
        {
            "doctype": "BP Dashboard",
            "dashboard_name": dashboard_name,
            "project": project or None,
            "visibility": visibility,
            "layout": "[]",
        }
    )
    doc.insert(ignore_permissions=True)
    if owner:
        frappe.db.set_value("BP Dashboard", doc.name, "owner", owner)
    frappe.db.commit()
    return doc.name


class TestReportOwnershipBoundary(FrappeTestCase):
    KEY = "RBOWNR"
    OWNER = "rbr-own-report@example.com"
    OTHER = "rbr-other-report@example.com"

    def setUp(self):
        frappe.set_user("Administrator")
        self.project = _make_project(self.KEY, "RBR Ownership Report Project")
        _ensure_user(self.OWNER)
        _ensure_user(self.OTHER)
        self.private = _make_report(
            self.project, "owner private report", "private", owner=self.OWNER
        )
        self.workspace = _make_report(
            self.project, "owner workspace report", "workspace", owner=self.OWNER
        )
        _add_project_member(self.project, self.OTHER, "Member")
        frappe.set_user("Administrator")

    def tearDown(self):
        frappe.set_user("Administrator")
        _delete_project(self.KEY)
        _delete_user(self.OWNER)
        _delete_user(self.OTHER)
        frappe.db.commit()

    def test_private_report_not_listed_for_other_user(self):
        frappe.set_user(self.OTHER)
        names = {r["id"] for r in board.get_saved_reports()}
        self.assertNotIn(self.private, names)
        self.assertIn(self.workspace, names)

    def test_owner_lists_own_private_report(self):
        frappe.set_user(self.OWNER)
        names = {r["id"] for r in board.get_saved_reports()}
        self.assertIn(self.private, names)

    def test_private_report_read_denied_for_other_user(self):
        frappe.set_user(self.OTHER)
        with self.assertRaises(frappe.PermissionError):
            board.get_saved_report(self.private)

    def test_private_report_update_denied_for_other_user(self):
        frappe.set_user(self.OTHER)
        with self.assertRaises(frappe.PermissionError):
            board.save_report(report=self.private, report_name="stolen")

    def test_private_report_delete_denied_for_other_user(self):
        frappe.set_user(self.OTHER)
        with self.assertRaises(frappe.PermissionError):
            board.delete_saved_report(self.private)

    def test_owner_can_update_and_delete_own_private_report(self):
        frappe.set_user(self.OWNER)
        board.save_report(report=self.private, report_name="renamed by owner")
        self.assertEqual(
            frappe.db.get_value("BP Report", self.private, "report_name"),
            "renamed by owner",
        )
        board.delete_saved_report(self.private)
        self.assertFalse(frappe.db.exists("BP Report", self.private))

    def test_workspace_report_not_editable_by_plain_member(self):
        _add_project_member(self.project, self.OTHER, "Member")
        frappe.set_user(self.OTHER)
        with self.assertRaises(frappe.PermissionError):
            board.save_report(report=self.workspace, report_name="hijacked")

    def test_workspace_report_editable_by_project_admin(self):
        _add_project_member(self.project, self.OTHER, "Admin")
        frappe.set_user(self.OTHER)
        board.save_report(report=self.workspace, report_name="edited by admin")
        self.assertEqual(
            frappe.db.get_value("BP Report", self.workspace, "report_name"),
            "edited by admin",
        )

    def test_admin_can_read_any_private_report(self):
        frappe.set_user("Administrator")
        out = board.get_saved_report(self.private)
        self.assertEqual(out["name"], self.private)

    def test_has_permission_private_is_owner_only(self):
        doc = frappe.get_doc("BP Report", self.private)
        self.assertTrue(
            permissions.bp_report_has_permission(
                doc, user=self.OWNER, permission_type="write"
            )
        )
        self.assertFalse(
            permissions.bp_report_has_permission(
                doc, user=self.OTHER, permission_type="read"
            )
        )


class TestDashboardOwnershipBoundary(FrappeTestCase):
    KEY = "RBOWND"
    OWNER = "rbr-own-dash@example.com"
    OTHER = "rbr-other-dash@example.com"

    def setUp(self):
        # require_feature resolves through the licensed tier, which is
        # starter in the test environment — the gate itself is not what this
        # class exercises, so patch the check rather than faking a license.
        from unittest.mock import patch
        self._feat = patch("batch_projects.api.dashboards.require_feature", side_effect=lambda *a, **k: None)
        self._feat.start()
        frappe.set_user("Administrator")
        self.project = _make_project(self.KEY, "RBR Ownership Dashboard Project")
        _ensure_user(self.OWNER)
        _ensure_user(self.OTHER)
        self.private = _make_dashboard(
            self.project, "owner private dash", "private", owner=self.OWNER
        )
        self.workspace = _make_dashboard(
            self.project, "owner workspace dash", "workspace", owner=self.OWNER
        )
        self.projectless = _make_dashboard(
            None, "owner projectless dash", "workspace", owner=self.OWNER
        )
        _add_project_member(self.project, self.OTHER, "Member")
        frappe.set_user("Administrator")

    def tearDown(self):
        frappe.set_user("Administrator")
        _delete_project(self.KEY)
        _delete_user(self.OWNER)
        _delete_user(self.OTHER)
        self._feat.stop()
        frappe.db.commit()

    def test_private_dashboard_update_denied_for_other_user(self):
        frappe.set_user(self.OTHER)
        with self.assertRaises(frappe.PermissionError):
            dashboards.save_dashboard(dashboard=self.private, dashboard_name="stolen")

    def test_workspace_dashboard_update_denied_for_plain_member(self):
        _add_project_member(self.project, self.OTHER, "Member")
        frappe.set_user(self.OTHER)
        with self.assertRaises(frappe.PermissionError):
            dashboards.save_dashboard(
                dashboard=self.workspace, dashboard_name="hijacked"
            )

    def test_projectless_workspace_dashboard_not_editable_by_other_user(self):
        frappe.set_user(self.OTHER)
        with self.assertRaises(frappe.PermissionError):
            dashboards.save_dashboard(
                dashboard=self.projectless, dashboard_name="hijacked"
            )

    def test_workspace_dashboard_delete_denied_for_plain_member(self):
        frappe.set_user(self.OTHER)
        with self.assertRaises(frappe.PermissionError):
            dashboards.delete_dashboard(self.workspace)

    def test_owner_can_update_own_workspace_dashboard(self):
        frappe.set_user(self.OWNER)
        dashboards.save_dashboard(dashboard=self.workspace, dashboard_name="mine")
        self.assertEqual(
            frappe.db.get_value("BP Dashboard", self.workspace, "dashboard_name"),
            "mine",
        )

    def test_workspace_dashboard_editable_by_project_admin(self):
        _add_project_member(self.project, self.OTHER, "Admin")
        frappe.set_user(self.OTHER)
        dashboards.save_dashboard(dashboard=self.workspace, dashboard_name="admin edit")
        self.assertEqual(
            frappe.db.get_value("BP Dashboard", self.workspace, "dashboard_name"),
            "admin edit",
        )

    def test_has_permission_workspace_write_is_owner_or_admin(self):
        doc = frappe.get_doc("BP Dashboard", self.workspace)
        self.assertTrue(
            permissions.bp_dashboard_has_permission(
                doc, user=self.OWNER, permission_type="write"
            )
        )
        self.assertFalse(
            permissions.bp_dashboard_has_permission(
                doc, user=self.OTHER, permission_type="write"
            )
        )
        self.assertTrue(
            permissions.bp_dashboard_has_permission(
                doc, user=self.OTHER, permission_type="read"
            )
        )


class TestPersonalRowOwnershipBoundary(FrappeTestCase):
    OWNER = "rbr-own-personal@example.com"
    OTHER = "rbr-other-personal@example.com"

    def setUp(self):
        frappe.set_user("Administrator")
        self.project = _make_project("RBPER", "RBR Ownership Personal Project")
        _ensure_user(self.OWNER)
        _ensure_user(self.OTHER)
        self.pref = (
            frappe.get_doc(
                {
                    "doctype": "BP View Preference",
                    "user": self.OWNER,
                    "project": self.project,
                    "view": "list",
                    "prefs": "{}",
                }
            )
            .insert(ignore_permissions=True)
            .name
        )
        self.mute = (
            frappe.get_doc(
                {
                    "doctype": "BP Notification Mute",
                    "user": self.OWNER,
                    "project": self.project,
                }
            )
            .insert(ignore_permissions=True)
            .name
        )
        frappe.db.commit()

    def tearDown(self):
        frappe.set_user("Administrator")
        for name in (self.pref, self.mute):
            try:
                frappe.delete_doc(
                    "BP View Preference", name, ignore_permissions=True, force=True
                )
            except frappe.DoesNotExistError:
                pass
            try:
                frappe.delete_doc(
                    "BP Notification Mute", name, ignore_permissions=True, force=True
                )
            except frappe.DoesNotExistError:
                pass
        _delete_user(self.OWNER)
        _delete_user(self.OTHER)
        _delete_project("RBPER")
        frappe.db.commit()

    def test_preference_has_permission_owner_only(self):
        doc = frappe.get_doc("BP View Preference", self.pref)
        self.assertTrue(
            permissions.bp_user_owned_has_permission(
                doc, user=self.OWNER, permission_type="write"
            )
        )
        self.assertFalse(
            permissions.bp_user_owned_has_permission(
                doc, user=self.OTHER, permission_type="read"
            )
        )

    def test_mute_has_permission_owner_only(self):
        doc = frappe.get_doc("BP Notification Mute", self.mute)
        self.assertTrue(
            permissions.bp_user_owned_has_permission(
                doc, user=self.OWNER, permission_type="write"
            )
        )
        self.assertFalse(
            permissions.bp_user_owned_has_permission(
                doc, user=self.OTHER, permission_type="read"
            )
        )

    def test_create_as_someone_else_denied(self):
        doc = frappe.get_doc(
            {
                "doctype": "BP View Preference",
                "user": self.OWNER,
                "project": self.project,
                "view": "list",
                "prefs": "{}",
            }
        )
        self.assertFalse(
            permissions.bp_user_owned_has_permission(
                doc, user=self.OTHER, permission_type="create"
            )
        )


class TestIntakeFormProjectMoveBoundary(FrappeTestCase):
    KEY_A = "RBIFA"
    KEY_B = "RBIFB"
    MANAGER = "rbr-form-manager@example.com"

    def setUp(self):
        # Same rationale as TestDashboardOwnershipBoundary: the entitlement
        # tier gate is not what this class exercises.
        from unittest.mock import patch
        self._feat = patch("batch_projects.api.forms.require_feature", side_effect=lambda *a, **k: None)
        self._feat.start()
        frappe.set_user("Administrator")
        self.proj_a = _make_project(self.KEY_A, "RBR Form Project A")
        self.proj_b = _make_project(
            self.KEY_B, "RBR Form Project B", visibility="private"
        )
        _ensure_user(self.MANAGER)
        _add_project_member(self.proj_a, self.MANAGER, "Manager")
        frappe.set_user("Administrator")
        self.form = (
            frappe.get_doc(
                {
                    "doctype": "BP Intake Form",
                    "form_title": "RBR intake form",
                    "project": self.proj_a,
                    "task_type": "Task",
                    "default_status": "To Do",
                    "fields_json": "[]",
                    "is_active": 1,
                }
            )
            .insert(ignore_permissions=True)
            .name
        )
        frappe.db.commit()

    def tearDown(self):
        frappe.set_user("Administrator")
        if frappe.db.exists("BP Intake Form", self.form):
            frappe.delete_doc(
                "BP Intake Form", self.form, ignore_permissions=True, force=True
            )
        _delete_project(self.KEY_A)
        _delete_project(self.KEY_B)
        _delete_user(self.MANAGER)
        self._feat.stop()
        frappe.db.commit()

    def test_api_project_move_rejected(self):
        frappe.set_user(self.MANAGER)
        with self.assertRaises(frappe.PermissionError):
            forms.update_intake_form(self.form, {"project": self.proj_b})

    def test_api_allowed_fields_still_updatable(self):
        frappe.set_user(self.MANAGER)
        forms.update_intake_form(self.form, {"form_title": "renamed form"})
        self.assertEqual(
            frappe.db.get_value("BP Intake Form", self.form, "form_title"),
            "renamed form",
        )

    def test_api_unknown_fields_ignored(self):
        frappe.set_user(self.MANAGER)
        forms.update_intake_form(self.form, {"evil_field": "x", "project": self.proj_a})
        doc = frappe.get_doc("BP Intake Form", self.form)
        self.assertEqual(doc.project, self.proj_a)

    def test_doctype_validate_rejects_project_move(self):
        frappe.set_user("Administrator")
        doc = frappe.get_doc("BP Intake Form", self.form)
        doc.project = self.proj_b
        with self.assertRaises(frappe.PermissionError):
            doc.save(ignore_permissions=True)

    def test_doctype_validate_accepts_invalid_task_config_guard(self):
        frappe.set_user("Administrator")
        doc = frappe.get_doc("BP Intake Form", self.form)
        doc.task_type = "Not A Real Type"
        with self.assertRaises(frappe.ValidationError):
            doc.save(ignore_permissions=True)


if __name__ == "__main__":
    import unittest

    unittest.main()
