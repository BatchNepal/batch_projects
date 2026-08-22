# Copyright (c) 2026, BatchNepal and contributors
# Regression coverage for BPProject._validate_members_mutation_authority —
# BP Project Member is a child table, so Frappe's has_child_permission always
# resolves a write to plain parent-level write access and can never see that
# a specific mutation is a member/role change; this authority check has to
# live in the parent doctype's validate() instead, so it must run on every
# save regardless of which API surface triggered it.
# Run: bench --site <site> run-tests --app batch_projects

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from batch_projects import access


def _members(*pairs):
    return [frappe._dict(user=u, role=r) for u, r in pairs]


class TestBPProjectMemberMutationAuthority(FrappeTestCase):
    def _doc(self, members, is_new, name="TEST-PROJ-AUTH"):
        doc = frappe.get_doc({"doctype": "BP Project"})
        doc.set("__islocal", 1 if is_new else None)
        doc.name = name
        doc.members = members
        return doc

    # ── no-op when the member list didn't change ──────────────────────
    def test_unchanged_members_on_existing_project_skips_check(self):
        doc = self._doc(_members(("a@example.com", "Member")), is_new=False)
        with (
            patch.object(frappe, "get_all", return_value=_members(("a@example.com", "Member"))),
            patch.object(access, "require") as require,
        ):
            doc._validate_members_mutation_authority()
        require.assert_not_called()

    def test_empty_members_on_new_project_skips_check(self):
        doc = self._doc([], is_new=True)
        with patch.object(access, "require") as require:
            doc._validate_members_mutation_authority()
        require.assert_not_called()

    # ── new project: only self-as-Admin (or an instance admin) may pass ──
    def test_new_project_self_as_admin_allowed(self):
        doc = self._doc(_members((frappe.session.user, "Admin")), is_new=True)
        doc._validate_members_mutation_authority()  # must not raise

    def test_new_project_other_user_rejected(self):
        doc = self._doc(_members(("someone-else@example.com", "Admin")), is_new=True)
        with (
            patch.object(access, "is_instance_admin", return_value=False),
            self.assertRaises(frappe.PermissionError),
        ):
            doc._validate_members_mutation_authority()

    def test_new_project_self_as_non_admin_role_rejected(self):
        doc = self._doc(_members((frappe.session.user, "Member")), is_new=True)
        with (
            patch.object(access, "is_instance_admin", return_value=False),
            self.assertRaises(frappe.PermissionError),
        ):
            doc._validate_members_mutation_authority()

    def test_new_project_instance_admin_bypasses_shape_check(self):
        doc = self._doc(_members(("anyone@example.com", "Admin")), is_new=True)
        with patch.object(access, "is_instance_admin", return_value=True):
            doc._validate_members_mutation_authority()  # must not raise

    # ── existing project: any member-table change requires Admin ────────
    def test_existing_project_member_change_requires_admin_authority(self):
        doc = self._doc(_members(("a@example.com", "Admin")), is_new=False)
        with (
            patch.object(frappe, "get_all", return_value=_members(("a@example.com", "Member"))),
            patch.object(access, "require") as require,
        ):
            doc._validate_members_mutation_authority()
        require.assert_called_once_with(doc.name, "Admin")

    def test_existing_project_member_change_propagates_denial(self):
        doc = self._doc(_members(("a@example.com", "Admin")), is_new=False)
        with (
            patch.object(frappe, "get_all", return_value=_members(("a@example.com", "Member"))),
            patch.object(access, "require", side_effect=frappe.PermissionError("no")),
        ):
            with self.assertRaises(frappe.PermissionError):
                doc._validate_members_mutation_authority()

    def test_existing_project_member_change_allowed_when_authorized(self):
        doc = self._doc(_members(("a@example.com", "Admin")), is_new=False)
        with (
            patch.object(frappe, "get_all", return_value=_members(("a@example.com", "Member"))),
            patch.object(access, "require", return_value=None),
        ):
            doc._validate_members_mutation_authority()  # must not raise
