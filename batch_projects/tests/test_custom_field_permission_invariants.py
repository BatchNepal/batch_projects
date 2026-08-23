"""Regression coverage for custom-field role ordering and link-search
permission awareness.

Recovered gaps (BatchProjects git-audit, P0 #5 and #6):
  - view_role/edit_role were each validated as individually-real role names
    but never checked against each other, so edit_role could be configured
    weaker than view_role — granting edit rights to a role that can't even
    see the field.
  - search_field_link_options used frappe.get_all (permission-blind) against
    the caller's chosen ERPNext doctype, so the picker could enumerate
    records the session user has no ERPNext-level read permission for.

Run with:
    bench run-tests --module batch_projects.tests.test_custom_field_permission_invariants
"""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from batch_projects.api import custom_fields as cf


class TestCustomFieldRoleOrdering(FrappeTestCase):
    def test_edit_role_weaker_than_view_role_is_rejected(self):
        with self.assertRaises(frappe.ValidationError):
            cf._validate_field_payload("text", "Tasks", "Manager", "Viewer", None)

    def test_edit_role_equal_to_view_role_is_allowed(self):
        cf._validate_field_payload("text", "Tasks", "Member", "Member", None)

    def test_edit_role_stronger_than_view_role_is_allowed(self):
        cf._validate_field_payload("text", "Tasks", "Viewer", "Admin", None)


class TestSearchFieldLinkOptionsPermissionAwareness(FrappeTestCase):
    def _field(self, **overrides):
        row = frappe._dict(
            name="CF-1", field_type="link", view_role="Viewer", edit_role="Member",
            options_json='{"link_doctype": "Customer"}',
        )
        row.update(overrides)
        return row

    def test_user_with_no_doctype_read_permission_gets_empty_result_not_an_error(self):
        with (
            patch.object(cf, "_guard"),
            patch("batch_projects.access.require"),
            patch("batch_projects.api.custom_fields._attached_fields", return_value=[(None, self._field())]),
            patch.object(frappe, "get_cached_doc", return_value=self._field()),
            patch("batch_projects.access.has_at_least", return_value=True),
            patch.object(frappe.db, "exists", return_value=True),
            patch.object(frappe, "has_permission", return_value=False) as has_perm,
            patch.object(frappe, "get_list") as get_list,
        ):
            result = cf.search_field_link_options("PROJ-A", "CF-1", txt="acme")

        self.assertEqual(result, [])
        has_perm.assert_called_once_with("Customer", "read", user=frappe.session.user, raise_exception=False)
        get_list.assert_not_called()

    def test_user_with_doctype_read_permission_uses_permission_aware_get_list(self):
        with (
            patch.object(cf, "_guard"),
            patch("batch_projects.access.require"),
            patch("batch_projects.api.custom_fields._attached_fields", return_value=[(None, self._field())]),
            patch.object(frappe, "get_cached_doc", return_value=self._field()),
            patch("batch_projects.access.has_at_least", return_value=True),
            patch.object(frappe.db, "exists", return_value=True),
            patch.object(frappe.db, "get_value", return_value="customer_name"),
            patch.object(frappe, "has_permission", return_value=True),
            patch("frappe.model.get_permitted_fields", return_value=["customer_name"]),
            patch.object(frappe, "get_list", return_value=[{"name": "CUST-1", "customer_name": "Acme"}]) as get_list,
        ):
            result = cf.search_field_link_options("PROJ-A", "CF-1", txt="acme")

        self.assertEqual(result, [{"name": "CUST-1", "label": "Acme"}])
        get_list.assert_called_once()

    def test_field_not_attached_to_project_is_rejected(self):
        with (
            patch.object(cf, "_guard"),
            patch("batch_projects.access.require"),
            patch("batch_projects.api.custom_fields._attached_fields", return_value=[]),
            self.assertRaises(frappe.PermissionError),
        ):
            cf.search_field_link_options("PROJ-A", "CF-1")


if __name__ == "__main__":
    import unittest
    unittest.main()
