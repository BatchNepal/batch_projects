# Copyright (c) 2026, BatchNepal and contributors
# Tests for the project lifecycle exposed through batch_projects.api.board.
# Run: bench --site <site> run-tests --app batch_projects

import json

import frappe
from frappe.tests.utils import FrappeTestCase

from batch_projects.api.board import create_project

# These are BP Project lifecycle tests, not ERPNext fixture-integration tests.
# Frappe's full-app bootstrap otherwise follows optional ERPNext Links from
# BP Project into unrelated finance/payment fixture graphs. None of these
# external records is a fixture prerequisite for the lifecycle tests below.
test_ignore = [
    "Company",
    "Customer",
    "Lead",
    "Opportunity",
    "Project",
    "Quotation",
    "Sales Order",
]

TEST_KEY = "TBPRJ"

WORKFLOW = json.dumps([
    {"name": "To Do", "color": "#6B7280", "category": "open"},
    {"name": "In Progress", "color": "#0B6BCB", "category": "active"},
    {"name": "Done", "color": "#16A34A", "category": "completed"},
])

ISSUE_TYPES = json.dumps([
    {"name": "Task", "color": "#0B6BCB", "icon": "CheckSquare"},
])


def delete_project_fixture(key):
    """Remove a test project and everything hanging off it."""
    name = frappe.db.get_value("BP Project", {"key": key})
    if not name:
        return
    for task in frappe.get_all("BP Task", filters={"project": name}, pluck="name"):
        for activity in frappe.get_all("BP Activity", filters={"task": task}, pluck="name"):
            frappe.delete_doc("BP Activity", activity, ignore_permissions=True, force=True)
        frappe.delete_doc("BP Task", task, ignore_permissions=True, force=True)
    for doctype in ("BP Milestone", "BP Risk", "BP Sprint", "BP Epic", "BP View"):
        for doc in frappe.get_all(doctype, filters={"project": name}, pluck="name"):
            frappe.delete_doc(doctype, doc, ignore_permissions=True, force=True)
    frappe.delete_doc("BP Project", name, ignore_permissions=True, force=True)
    frappe.db.commit()


def make_project(key=TEST_KEY, **overrides):
    params = dict(
        project_name="Test Project",
        key=key,
        workflow_states=WORKFLOW,
        issue_types=ISSUE_TYPES,
    )
    params.update(overrides)
    return create_project(**params)


class TestBPProject(FrappeTestCase):
    def setUp(self):
        frappe.set_user("Administrator")
        delete_project_fixture(TEST_KEY)

    def tearDown(self):
        delete_project_fixture(TEST_KEY)

    def test_create_project_basics(self):
        res = make_project()
        self.assertEqual(res["key"], TEST_KEY)
        self.assertEqual(res["project_name"], "Test Project")

        doc = frappe.get_doc("BP Project", res["name"])
        self.assertEqual(doc.status, "Active")
        # Creator must be auto-added as an Admin member (the child-table Select's
        # canonical value — 'BP Admin' is the Frappe Role name, a different thing).
        members = [(m.user, m.role) for m in doc.members]
        self.assertIn(("Administrator", "Admin"), members)

    def test_key_is_uppercased_and_trimmed(self):
        res = make_project(key=f"  {TEST_KEY.lower()} ")
        self.assertEqual(res["key"], TEST_KEY)

    def test_duplicate_key_rejected(self):
        make_project()
        with self.assertRaises(frappe.ValidationError):
            make_project()

    def test_short_key_rejected(self):
        with self.assertRaises(frappe.ValidationError):
            make_project(key="A")

    def test_billable_project_requires_client(self):
        with self.assertRaises(frappe.ValidationError):
            make_project(project_type="tm")

    def test_fixed_price_requires_budget(self):
        with self.assertRaises(frappe.ValidationError):
            make_project(project_type="fixed", client="Some Client")
