"""Regression coverage for the P0 read-boundary recovery PR (fresh security
audit, 2026-08). Each test class below is one confirmed finding:

  1. cache.py leaked authorization-shaped data across users (no `user` in
     the cache key) — TestCachePerUserGeneration, TestBoardBacklogCacheUserIsolation.
  2. get_backlog() skipped the sanitization query_tasks() applies —
     TestBoardBacklogCacheUserIsolation, TestGetBacklogMoneyFieldGate.
  3. _fetch_task_links/_fetch_task_refs had no permission filtering —
     TestFetchTaskLinksAndRefsFiltering.
  4. _resolve_scope()'s invalid-scope edge case failed open —
     TestResolveScopeFailsClosed.
  5. get_workload() had no accessible-projects filter —
     TestGetWorkloadAccessibleProjectsFilter.
  6. search_tasks(project=None) was genuinely unscoped —
     TestSearchTasksAccessibleProjectsFilter.
  7. get_milestones/get_risks(project=None) were unscoped —
     TestMilestonesAndRisksAccessibleProjectsFilter.

Run with:
    bench run-tests --module batch_projects.tests.test_read_boundary_recovery
"""

import json
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from batch_projects import cache
from batch_projects.api import board
from batch_projects.api import custom_fields as cf


def _ensure_user(email):
    """Throwaway System User fixture for Link-field validity only — never a
    real signup, never a real email (send_welcome_email=0, plus-addressed
    testN+info@batchnepal.com addresses are used — SES bounce protection).
    IANA-reserved), matching this test suite's existing convention
    (test_membership_invariants.py).

    Also grants the baseline 'BP Member' role: Frappe's own User.validate()
    (user_type_mapper / has_desk_access()) silently downgrades a roleless
    user's user_type to "Website User" regardless of what's passed at
    insert, and _require_system_user()/task_invariants._assert_assignable_user
    both hard-require "System User". 'BP Member' (access.MEMBER_ROLE) is the
    established low-privilege role for this — desk_access=1, but no
    System Manager/instance-admin standing, so it doesn't defeat the
    accessible-projects checks these tests exercise."""
    if not frappe.db.exists("User", email):
        frappe.get_doc({
            "doctype": "User",
            "email": email,
            "first_name": email.split("@")[0],
            "user_type": "System User",
            "enabled": 1,
            "send_welcome_email": 0,
        }).insert(ignore_permissions=True)
    from batch_projects import access
    access.ensure_member_role(email)
    return email


def _delete_user(email):
    if frappe.db.exists("User", email):
        frappe.delete_doc("User", email, ignore_permissions=True, force=True)


def _delete_project(key):
    name = frappe.db.get_value("BP Project", {"key": key})
    if not name:
        return
    for task in frappe.get_all("BP Task", filters={"project": name}, pluck="name"):
        frappe.delete_doc("BP Task", task, ignore_permissions=True, force=True)
    for ms in frappe.get_all("BP Milestone", filters={"project": name}, pluck="name"):
        frappe.delete_doc("BP Milestone", ms, ignore_permissions=True, force=True)
    for rk in frappe.get_all("BP Risk", filters={"project": name}, pluck="name"):
        frappe.delete_doc("BP Risk", rk, ignore_permissions=True, force=True)
    for cf_row in frappe.get_all("BP Custom Field", filters={"owner_project": name}, pluck="name"):
        frappe.db.delete("BP Custom Field Project", {"custom_field": cf_row})
        frappe.delete_doc("BP Custom Field", cf_row, ignore_permissions=True, force=True)
    frappe.delete_doc("BP Project", name, ignore_permissions=True, force=True)


def _make_project(key, project_name, visibility="workspace"):
    frappe.set_user("Administrator")
    _delete_project(key)
    result = board.create_project(
        project_name=project_name,
        key=key,
        visibility=visibility,
        workflow_states=json.dumps([{"name": "To Do", "color": "#6B7280", "category": "open"}]),
        issue_types=json.dumps([{"name": "Task", "color": "#0B6BCB", "icon": "CheckSquare"}]),
    )
    return result["name"]


def _make_task(project, title, assignees=None, **extra):
    doc = frappe.get_doc({
        "doctype": "BP Task",
        "project": project,
        "title": title,
        "task_type": "Task",
        "status": "To Do",
        **extra,
    })
    for user in (assignees or []):
        doc.append("assignees", {"user": user, "full_name": user})
    doc.insert(ignore_permissions=True)
    return doc.name


# ─── Finding 1: cache.py per-user isolation ────────────────────────────────

class TestCachePerUserGeneration(FrappeTestCase):
    """Unit coverage of cache.py's own key/generation mechanics — real Redis
    via frappe.cache(), no mocking."""

    PROJECT = "RBR-CACHE-UNIT-TEST"

    def tearDown(self):
        cache.invalidate_project(self.PROJECT)

    def test_different_users_do_not_share_a_cached_entry(self):
        cache.set(cache.VIEW_BOARD, self.PROJECT, {"secret": "admin-view"}, user="test49+info@batchnepal.com")
        self.assertEqual(
            cache.get(cache.VIEW_BOARD, self.PROJECT, user="test49+info@batchnepal.com"),
            {"secret": "admin-view"},
        )
        # A different user must get a cache MISS, never the first user's data.
        self.assertIsNone(cache.get(cache.VIEW_BOARD, self.PROJECT, user="test60+info@batchnepal.com"))

    def test_get_and_set_default_to_the_current_session_user(self):
        frappe.set_user("Administrator")
        cache.set(cache.VIEW_BOARD, self.PROJECT, {"v": 1})
        self.assertEqual(cache.get(cache.VIEW_BOARD, self.PROJECT), {"v": 1})

    def test_invalidate_project_orphans_every_previously_cached_entry(self):
        cache.set(cache.VIEW_BOARD, self.PROJECT, {"v": 1}, user="test49+info@batchnepal.com")
        cache.set(cache.VIEW_BACKLOG, self.PROJECT, {"v": 2}, user="test60+info@batchnepal.com")
        cache.invalidate_project(self.PROJECT)
        self.assertIsNone(cache.get(cache.VIEW_BOARD, self.PROJECT, user="test49+info@batchnepal.com"))
        self.assertIsNone(cache.get(cache.VIEW_BACKLOG, self.PROJECT, user="test60+info@batchnepal.com"))


class TestBoardBacklogCacheUserIsolation(FrappeTestCase):
    """The audit's own suggested regression, built for real: a Manager-only
    custom field is set on a task; an Admin's get_board/get_backlog call
    warms the cache (and legitimately sees the field); a real low-privilege
    Viewer's very next call — inside the same 60s TTL window — must NOT
    receive it. Before the cache.py fix this test fails: the Viewer gets the
    Admin's cached payload verbatim."""

    KEY = "RBRBCU"
    VIEWER = "test50+info@batchnepal.com"

    def setUp(self):
        frappe.set_user("Administrator")
        self.project = _make_project(self.KEY, "RBR Cache Isolation Test")
        _ensure_user(self.VIEWER)
        self.field = cf.create_field(
            field_label="RBR Manager Secret",
            field_type="text",
            applies_to="Tasks",
            view_role="Manager",
            edit_role="Manager",
            owner_project=self.project,
        )["name"]
        self.task = _make_task(
            self.project, "task with a manager-only field",
            custom_field_values=json.dumps({self.field: "top-secret-value"}),
        )
        frappe.db.commit()

    def tearDown(self):
        frappe.set_user("Administrator")
        _delete_project(self.KEY)
        _delete_user(self.VIEWER)
        frappe.db.commit()

    @staticmethod
    def _find(rows, name):
        return next(r for r in rows if r["name"] == name)

    def test_get_board_hides_manager_only_field_from_viewer_after_admin_warms_cache(self):
        frappe.set_user("Administrator")
        admin_view = board.get_board(self.project)
        admin_task = self._find(
            [t for col in admin_view["board"].values() for t in col], self.task
        )
        self.assertEqual(admin_task["custom_field_values"].get(self.field), "top-secret-value")
        self.assertIn(self.field, {f["id"] for f in admin_view["custom_fields"]})

        # Within the same cache TTL window, a genuinely different, lower-
        # privilege caller must get its OWN sanitized view, not the Admin's.
        frappe.set_user(self.VIEWER)
        viewer_view = board.get_board(self.project)
        viewer_task = self._find(
            [t for col in viewer_view["board"].values() for t in col], self.task
        )
        self.assertNotIn(self.field, viewer_task["custom_field_values"])
        self.assertNotIn(self.field, {f["id"] for f in viewer_view["custom_fields"]})

    def test_get_backlog_hides_manager_only_field_from_viewer_after_admin_warms_cache(self):
        frappe.set_user("Administrator")
        admin_backlog = board.get_backlog(self.project)
        admin_row = self._find(admin_backlog, self.task)
        self.assertEqual(admin_row["custom_field_values"].get(self.field), "top-secret-value")

        frappe.set_user(self.VIEWER)
        viewer_backlog = board.get_backlog(self.project)
        viewer_row = self._find(viewer_backlog, self.task)
        self.assertNotIn(self.field, viewer_row["custom_field_values"])

    def test_get_backlog_strips_hidden_field_even_on_a_cold_cache(self):
        # Isolates finding #2 (get_backlog's own sanitization) from finding
        # #1 (cross-user cache leak) — no prior Admin call in this test.
        frappe.set_user(self.VIEWER)
        viewer_backlog = board.get_backlog(self.project)
        viewer_row = self._find(viewer_backlog, self.task)
        self.assertNotIn(self.field, viewer_row["custom_field_values"])


class TestGetBacklogMoneyFieldGate(FrappeTestCase):
    """get_backlog() must strip `billable` the same way task_reads.py's
    _sanitize_task_fields() does for the single-task detail view, gated on
    the view_money capability. view_money defaults to True for every role
    (access.CAPABILITIES) — a workspace admin can flip it off per role via
    BP Workspace Settings.role_overrides_json, which get_backlog reads
    through access.has_capability(). Mocked at that one seam (rather than
    mutating the shared BP Workspace Settings singleton, which every test
    and every real user on this bench reads) to isolate the gate itself."""

    KEY = "RBRMNY"

    def setUp(self):
        frappe.set_user("Administrator")
        self.project = _make_project(self.KEY, "RBR Money Gate Test")
        self.task = _make_task(self.project, "billable task", billable=1)
        frappe.db.commit()

    def tearDown(self):
        frappe.set_user("Administrator")
        _delete_project(self.KEY)
        frappe.db.commit()

    def test_billable_is_stripped_when_caller_lacks_view_money(self):
        with patch("batch_projects.access.has_capability", return_value=False):
            rows = board.get_backlog(self.project)
        row = next(r for r in rows if r["name"] == self.task)
        self.assertNotIn("billable", row)

    def test_billable_is_kept_when_caller_has_view_money(self):
        with patch("batch_projects.access.has_capability", return_value=True):
            rows = board.get_backlog(self.project)
        row = next(r for r in rows if r["name"] == self.task)
        self.assertEqual(row.get("billable"), 1)


# ─── Finding 3: _fetch_task_links / _fetch_task_refs permission filtering ──

class TestFetchTaskLinksAndRefsFiltering(FrappeTestCase):
    """board.py's board/list/backlog reads went through these two helpers
    with zero visibility filtering, unlike task_reads.py's single-task
    get_task(). Same mocking pattern test_task_read_security.py already
    uses for the underlying helpers — this covers the NEW wiring: that
    _fetch_task_links/_fetch_task_refs actually call them and drop rows."""

    @patch.object(board.frappe, "get_all")
    @patch("batch_projects.task_reads._visible_link_names")
    def test_fetch_task_links_drops_invisible_linked_tasks(self, visible_names, get_all):
        get_all.return_value = [
            frappe._dict(parent="T-1", link_type="relates to", linked_task="T-VIS",
                         linked_task_key="K1", linked_task_title="Visible",
                         linked_task_status="Open", linked_task_project="P"),
            frappe._dict(parent="T-1", link_type="relates to", linked_task="T-HIDDEN",
                         linked_task_key="K2", linked_task_title="Hidden",
                         linked_task_status="Open", linked_task_project="P-PRIVATE"),
        ]
        visible_names.return_value = {"T-VIS"}

        out = board._fetch_task_links(["T-1"])

        self.assertEqual([r["linked_task"] for r in out.get("T-1", [])], ["T-VIS"])

    @patch.object(board.frappe, "get_all")
    def test_fetch_task_links_returns_empty_when_nothing_visible(self, get_all):
        get_all.return_value = [
            frappe._dict(parent="T-1", link_type="relates to", linked_task="T-HIDDEN",
                         linked_task_key="K2", linked_task_title="Hidden",
                         linked_task_status="Open", linked_task_project="P-PRIVATE"),
        ]
        with patch("batch_projects.task_reads._visible_link_names", return_value=set()):
            out = board._fetch_task_links(["T-1"])
        self.assertEqual(out.get("T-1", []), [])

    @patch.object(board.frappe, "get_all")
    @patch("batch_projects.task_reads._can_read_reference")
    def test_fetch_task_refs_drops_unreadable_references(self, can_read, get_all):
        get_all.return_value = [
            frappe._dict(name="REF-1", parent="T-1", ref_doctype="Sales Invoice",
                         ref_name="SINV-1", ref_label="Readable"),
            frappe._dict(name="REF-2", parent="T-1", ref_doctype="Sales Invoice",
                         ref_name="SINV-2", ref_label="Unreadable"),
        ]
        can_read.side_effect = lambda row: row["ref_name"] == "SINV-1"

        out = board._fetch_task_refs(["T-1"])

        self.assertEqual([r["ref_name"] for r in out.get("T-1", [])], ["SINV-1"])


# ─── Finding 4: _resolve_scope() invalid-scope fail-closed ────────────────

class TestResolveScopeFailsClosed(FrappeTestCase):
    _BOGUS = ["definitely-not-a-real-project-xyz", "also-not-real-abc"]

    def setUp(self):
        frappe.set_user("Administrator")

    def test_invalid_multi_item_list_scope_raises_instead_of_unrestricted(self):
        with self.assertRaises(frappe.ValidationError):
            board._resolve_scope(list(self._BOGUS))

    def test_invalid_single_scope_raises_instead_of_unrestricted(self):
        with self.assertRaises(frappe.ValidationError):
            board._resolve_scope("definitely-not-a-real-project-xyz")

    def test_get_report_tasks_propagates_the_throw(self):
        with self.assertRaises(frappe.ValidationError):
            board.get_report_tasks(scope=json.dumps(self._BOGUS))

    def test_get_widget_data_propagates_the_throw(self):
        config = json.dumps({"scope": self._BOGUS})
        with self.assertRaises(frappe.ValidationError):
            board.get_widget_data(config)

    def test_query_bql_group_by_propagates_the_throw(self):
        with self.assertRaises(frappe.ValidationError):
            board.query_bql_group_by(list(self._BOGUS), "{}")


# ─── Finding 5: get_workload() accessible-projects filter ─────────────────

class TestGetWorkloadAccessibleProjectsFilter(FrappeTestCase):
    KEY_A = "RBRWLA"
    KEY_B = "RBRWLB"
    CALLER = "test61+info@batchnepal.com"
    TEAM_NAME = "RBR Workload Filter Test Team"

    def setUp(self):
        frappe.set_user("Administrator")
        self.proj_a = _make_project(self.KEY_A, "RBR Workload Visible", visibility="workspace")
        self.proj_b = _make_project(self.KEY_B, "RBR Workload Private", visibility="private")
        _ensure_user(self.CALLER)

        self.task_a = _make_task(self.proj_a, "workload task in visible project",
                                  estimated_hours=5, assignees=[self.CALLER])
        self.task_b = _make_task(self.proj_b, "workload task in private project",
                                  estimated_hours=5, assignees=[self.CALLER])

        if frappe.db.exists("BP Team", self.TEAM_NAME):
            frappe.delete_doc("BP Team", self.TEAM_NAME, ignore_permissions=True, force=True)
        team = frappe.get_doc({
            "doctype": "BP Team",
            "team_name": self.TEAM_NAME,
            "members": [{"user": self.CALLER, "role": "Member"}],
        })
        team.insert(ignore_permissions=True)
        self.team = team.name
        frappe.db.commit()

    def tearDown(self):
        frappe.set_user("Administrator")
        if frappe.db.exists("BP Team", self.team):
            frappe.delete_doc("BP Team", self.team, ignore_permissions=True, force=True)
        _delete_project(self.KEY_A)
        _delete_project(self.KEY_B)
        _delete_user(self.CALLER)
        frappe.db.commit()

    @staticmethod
    def _all_task_names(result):
        return {
            t["name"]
            for m in result["members"]
            for wk in m["weekly"]
            for t in wk["tasks"]
        }

    def test_private_project_task_excluded_for_non_member_caller(self):
        frappe.set_user(self.CALLER)
        result = board.get_workload(weeks=2, team=self.team)
        names = self._all_task_names(result)
        self.assertIn(self.task_a, names)
        self.assertNotIn(self.task_b, names)

    def test_admin_caller_sees_both_projects(self):
        frappe.set_user("Administrator")
        result = board.get_workload(weeks=2, team=self.team)
        names = self._all_task_names(result)
        self.assertIn(self.task_a, names)
        self.assertIn(self.task_b, names)


# ─── Finding 6: search_tasks(project=None) accessible-projects scoping ────

class TestSearchTasksAccessibleProjectsFilter(FrappeTestCase):
    KEY_A = "RBRSRA"
    KEY_B = "RBRSRB"
    CALLER = "test59+info@batchnepal.com"
    QUERY = "RbrSearchUniqueMarkerXyz"

    def setUp(self):
        frappe.set_user("Administrator")
        self.proj_a = _make_project(self.KEY_A, "RBR Search Visible", visibility="workspace")
        self.proj_b = _make_project(self.KEY_B, "RBR Search Private", visibility="private")
        _ensure_user(self.CALLER)
        self.task_a = _make_task(self.proj_a, f"{self.QUERY} in visible project")
        self.task_b = _make_task(self.proj_b, f"{self.QUERY} in private project")
        frappe.db.commit()

    def tearDown(self):
        frappe.set_user("Administrator")
        _delete_project(self.KEY_A)
        _delete_project(self.KEY_B)
        _delete_user(self.CALLER)
        frappe.db.commit()

    def test_no_project_search_is_scoped_to_accessible_projects(self):
        frappe.set_user(self.CALLER)
        results = board.search_tasks(self.QUERY, project=None)
        names = {r["name"] for r in results}
        self.assertIn(self.task_a, names)
        self.assertNotIn(self.task_b, names)

    def test_admin_no_project_search_sees_both(self):
        frappe.set_user("Administrator")
        results = board.search_tasks(self.QUERY, project=None)
        names = {r["name"] for r in results}
        self.assertIn(self.task_a, names)
        self.assertIn(self.task_b, names)

    def test_project_scoped_search_is_unaffected(self):
        frappe.set_user("Administrator")
        results = board.search_tasks(self.QUERY, project=self.proj_a)
        names = {r["name"] for r in results}
        self.assertEqual(names, {self.task_a})


# ─── Finding 7: get_milestones/get_risks(project=None) scoping ────────────

class TestMilestonesAndRisksAccessibleProjectsFilter(FrappeTestCase):
    KEY_A = "RBRMRA"
    KEY_B = "RBRMRB"
    CALLER = "test52+info@batchnepal.com"

    def setUp(self):
        frappe.set_user("Administrator")
        self.proj_a = _make_project(self.KEY_A, "RBR MR Visible", visibility="workspace")
        self.proj_b = _make_project(self.KEY_B, "RBR MR Private", visibility="private")
        _ensure_user(self.CALLER)
        self.ms_a = frappe.get_doc({
            "doctype": "BP Milestone", "project": self.proj_a, "title": "MS Visible",
        }).insert(ignore_permissions=True).name
        self.ms_b = frappe.get_doc({
            "doctype": "BP Milestone", "project": self.proj_b, "title": "MS Private",
        }).insert(ignore_permissions=True).name
        self.risk_a = frappe.get_doc({
            "doctype": "BP Risk", "project": self.proj_a, "title": "Risk Visible",
        }).insert(ignore_permissions=True).name
        self.risk_b = frappe.get_doc({
            "doctype": "BP Risk", "project": self.proj_b, "title": "Risk Private",
        }).insert(ignore_permissions=True).name
        frappe.db.commit()

    def tearDown(self):
        frappe.set_user("Administrator")
        _delete_project(self.KEY_A)
        _delete_project(self.KEY_B)
        _delete_user(self.CALLER)
        frappe.db.commit()

    def test_milestones_without_project_scoped_to_accessible_projects(self):
        frappe.set_user(self.CALLER)
        rows = board.get_milestones(project=None)
        names = {r["name"] for r in rows}
        self.assertIn(self.ms_a, names)
        self.assertNotIn(self.ms_b, names)

    def test_risks_without_project_scoped_to_accessible_projects(self):
        frappe.set_user(self.CALLER)
        rows = board.get_risks(project=None)
        names = {r["name"] for r in rows}
        self.assertIn(self.risk_a, names)
        self.assertNotIn(self.risk_b, names)

    def test_admin_without_project_sees_both(self):
        frappe.set_user("Administrator")
        ms_names = {r["name"] for r in board.get_milestones(project=None)}
        risk_names = {r["name"] for r in board.get_risks(project=None)}
        self.assertIn(self.ms_a, ms_names)
        self.assertIn(self.ms_b, ms_names)
        self.assertIn(self.risk_a, risk_names)
        self.assertIn(self.risk_b, risk_names)


if __name__ == "__main__":
    import unittest
    unittest.main()


class TestWidgetAndBqlAggregationsExcludeTrashedTasks(FrappeTestCase):
    """get_widget_data()/query_bql_group_by() aggregated over a bare
    frappe.get_all with no live-task filter — a trashed task still counted
    toward dashboard widget metrics. Both now wrap their task query in
    _task_filters (is_deleted=0), same as every other task collection."""

    KEY = "RBRWBQ"

    def setUp(self):
        self.project = _make_project(self.KEY, "RBR Widget Trash Test")
        self.live = _make_task(self.project, "widget live task")
        self.trashed = _make_task(self.project, "widget trashed task")
        frappe.db.set_value("BP Task", self.trashed, "is_deleted", 1)
        frappe.db.commit()

    def tearDown(self):
        frappe.set_user("Administrator")
        _delete_project(self.KEY)
        frappe.db.commit()

    def test_get_widget_data_excludes_trashed_tasks(self):
        result = board.get_widget_data({
            "scope": self.project, "group_by": "status", "metric": "count",
        })
        self.assertEqual(result["total"], 1, result)

    def test_query_bql_group_by_excludes_trashed_tasks(self):
        result = board.query_bql_group_by(self.project, {}, "status", "count")
        self.assertEqual(result["total"], 1, result)
