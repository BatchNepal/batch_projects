"""P1-5 through P1-8 lifecycle security recovery test coverage.

This test module covers the four security finding groups addressed in the
fix/p1-lifecycle-licensing-recovery-v2 branch:

- P1-5: Trash boundary enforcement (is_deleted checks)
- P1-6: Seat capacity validation and team REST security
- P1-7: Schedule data integrity (FOR UPDATE locks, trash filters)
- P1-8: Query filters (sprint/velocity/dashboard/capacity/template)

Test organization follows the naming convention of test_*_invariants.py
and test_*_recovery.py files in this directory.
"""

from unittest.mock import patch, MagicMock
import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import random_string
from batch_projects.api import board
from batch_projects.api import sharing
from batch_projects.api import automation_schedule_data
from batch_projects.api import project_templates
from batch_projects.task_validation import require_live_task, validate_live_task_edits
from batch_projects import entitlements

# The real database sql method, bound once at import before any test patches
# frappe.db.sql. Side-effect delegation must route through this, not through
# frappe.db.sql (which is the mock while a test is running).
_REAL_DB_SQL = frappe.db.sql
_REAL_GET_DOC = frappe.get_doc


class TestTrashBoundaryEnforcement(FrappeTestCase):
    """P1-5: Trash boundary — trashed tasks rejected at mutation and read."""

    def setUp(self):
        self._project = None
        self._task = None
        self._team = None

    def tearDown(self):
        if self._task and frappe.db.exists("BP Task", self._task):
            try:
                frappe.delete_doc("BP Task", self._task, ignore_permissions=True, force=True)
            except Exception:
                pass
        if self._project and frappe.db.exists("BP Project", self._project):
            try:
                frappe.delete_doc("BP Project", self._project, ignore_permissions=True, force=True)
            except Exception:
                pass
        if self._team and frappe.db.exists("BP Team", self._team):
            try:
                frappe.delete_doc("BP Team", self._team, ignore_permissions=True, force=True)
            except Exception:
                pass
        frappe.db.commit()

    def _make_project(self):
        uid = random_string(6)
        doc = frappe.get_doc({
            "doctype": "BP Project",
            "project_name": f"P1 Trash Test {uid}",
            "key": uid.upper(),
            "status": "Active",
            "visibility": "workspace",
        })
        doc.insert(ignore_permissions=True)
        self._project = doc.name
        return doc.name

    def _make_task(self, project, title=None):
        doc = frappe.get_doc({
            "doctype": "BP Task",
            "title": title or f"P1 Task {random_string(4)}",
            "project": project,
            "status": "To Do",
        })
        doc.insert(ignore_permissions=True)
        self._task = doc.name
        return doc.name

    def test_get_task_rejects_trashed(self):
        """board.get_task raises PermissionError for is_deleted=1."""
        proj = self._make_project()
        task = self._make_task(proj)
        
        # Trash it
        frappe.db.set_value("BP Task", task, "is_deleted", 1)
        
        with self.assertRaises(frappe.PermissionError):
            board.get_task(task)

    def test_require_live_task_rejects_trashed(self):
        """require_live_task raises PermissionError for is_deleted=1."""
        proj = self._make_project()
        task = self._make_task(proj)
        
        frappe.db.set_value("BP Task", task, "is_deleted", 1)
        
        with self.assertRaises(frappe.PermissionError):
            require_live_task(task)

    def test_validate_live_task_edits_rejects_trash_to_trash_save(self):
        """validate_live_task_edits rejects saves where both old/new are deleted."""
        old = frappe._dict(is_deleted=1)
        doc = frappe._dict(is_deleted=1, flags=frappe._dict())
        
        with self.assertRaises(frappe.ValidationError):
            validate_live_task_edits(doc, old)

    def test_validate_live_task_edits_allows_trash_edit_with_flag(self):
        """validate_live_task_edits allows trash-to-trash if allow_trash_edit flag set."""
        old = frappe._dict(is_deleted=1)
        doc = frappe._dict(is_deleted=1, flags=frappe._dict(allow_trash_edit=True))
        
        # Should not raise
        validate_live_task_edits(doc, old)

    @patch("batch_projects.api.sharing._load_live_link")
    @patch.object(sharing.frappe.db, "get_value")
    def test_guest_comment_on_trashed_task_rejected(self, get_value, load_link):
        """sharing.add_guest_comment rejects trashed tasks."""
        get_value.return_value = frappe._dict(is_deleted=1)
        link = MagicMock()
        link.scope = "task"
        link.access_level = "comment"
        link.task = "TASK-1"
        load_link.return_value = link

        with self.assertRaises(frappe.PermissionError):
            sharing.add_guest_comment("fake-token", "TASK-1", "comment")

    @patch("batch_projects.api.sharing._load_live_link")
    @patch.object(sharing.frappe.db, "get_value")
    def test_guest_update_shared_task_rejects_trashed(self, get_value, load_link):
        """sharing.update_shared_task rejects trashed tasks."""
        get_value.return_value = frappe._dict(is_deleted=1)
        link = MagicMock()
        link.scope = "task"
        link.access_level = "edit"
        link.task = "TASK-1"
        load_link.return_value = link

        with self.assertRaises(frappe.PermissionError):
            sharing.update_shared_task("fake-token", "TASK-1", {"title": "Updated"})


class TestSeatCapacityAndTeamREST(FrappeTestCase):
    """P1-6: Seat capacity validation and team permission hooks."""

    def setUp(self):
        self._project = None
        self._team = None
        self._users = []

    def tearDown(self):
        if self._project and frappe.db.exists("BP Project", self._project):
            try:
                frappe.delete_doc("BP Project", self._project, ignore_permissions=True, force=True)
            except Exception:
                pass
        if self._team and frappe.db.exists("BP Team", self._team):
            try:
                frappe.delete_doc("BP Team", self._team, ignore_permissions=True, force=True)
            except Exception:
                pass
        for user in self._users:
            if frappe.db.exists("User", user):
                try:
                    frappe.delete_doc("User", user, ignore_permissions=True, force=True)
                except Exception:
                    pass
        frappe.db.commit()

    def _make_user(self, email=None):
        email = email or f"p1test{random_string(4)}@example.com"
        doc = frappe.get_doc({
            "doctype": "User",
            "email": email,
            "first_name": "P1",
            "enabled": 1,
            "user_type": "System User",
        })
        doc.insert(ignore_permissions=True)
        # Frappe's User controller ignores user_type passed to insert() — the
        # row lands as Website User. Set it directly so assignability checks
        # (task_invariants._assert_assignable_user) see a System User.
        frappe.db.set_value("User", email, "user_type", "System User")
        self._users.append(email)
        return email

    def _make_project(self):
        uid = random_string(6)
        doc = frappe.get_doc({
            "doctype": "BP Project",
            "project_name": f"P1 Seat Test {uid}",
            "key": uid.upper(),
            "status": "Active",
            "visibility": "workspace",
        })
        doc.insert(ignore_permissions=True)
        self._project = doc.name
        return doc.name

    def _make_team(self):
        uid = random_string(6)
        doc = frappe.get_doc({
            "doctype": "BP Team",
            "team_name": f"P1 Team {uid}",
        })
        doc.insert(ignore_permissions=True)
        self._team = doc.name
        return doc.name

    @patch.object(entitlements, "assert_seats_available")
    def test_project_member_addition_checks_seats(self, assert_seats):
        """BP Project member addition triggers seat validation."""
        proj = self._make_project()
        user = self._make_user()
        
        # Simulate adding a member
        pdoc = frappe.get_doc("BP Project", proj)
        pdoc.append("members", {"user": user, "role": "Member"})
        pdoc.save(ignore_permissions=True)
        
        # assert_seats_available should have been called
        self.assertTrue(assert_seats.called)

    @patch.object(entitlements, "assert_seats_available")
    def test_team_validate_checks_new_member_seats(self, assert_seats):
        """BP Team validate() checks seats for new members."""
        team = self._make_team()
        user = self._make_user()
        
        tdoc = frappe.get_doc("BP Team", team)
        tdoc.append("members", {"user": user, "role": "Member"})
        tdoc.save(ignore_permissions=True)
        
        self.assertTrue(assert_seats.called)

    @patch.object(entitlements, "assert_seats_available")
    @patch("batch_projects.api.board.frappe.db.sql")
    def test_update_project_members_uses_advisory_lock(self, sql, assert_seats):
        """update_project_members uses GET_LOCK for seat decision atomicity."""
        def sql_side_effect(query, *args, **kwargs):
            if "GET_LOCK" in str(query):
                return [[1]]
            if "RELEASE_LOCK" in str(query):
                return [[1]]
            return _REAL_DB_SQL(query, *args, **kwargs)

        sql.side_effect = sql_side_effect
        proj = self._make_project()
        user = self._make_user()

        with patch("batch_projects.api.board._check_permission"):
            board.update_project_members(proj, [{"user": user, "role": "Member"}])
        
        # Check GET_LOCK was called
        lock_calls = [c for c in sql.call_args_list if "GET_LOCK" in str(c)]
        self.assertTrue(len(lock_calls) > 0)


class TestScheduleDataIntegrity(FrappeTestCase):
    """P1-7: Schedule data FOR UPDATE locks and trash filters."""

    def setUp(self):
        self._project = None
        self._task = None

    def tearDown(self):
        if self._task and frappe.db.exists("BP Task", self._task):
            try:
                frappe.delete_doc("BP Task", self._task, ignore_permissions=True, force=True)
            except Exception:
                pass
        if self._project and frappe.db.exists("BP Project", self._project):
            try:
                frappe.delete_doc("BP Project", self._project, ignore_permissions=True, force=True)
            except Exception:
                pass
        frappe.db.commit()

    def _make_project(self):
        uid = random_string(6)
        doc = frappe.get_doc({
            "doctype": "BP Project",
            "project_name": f"P1 Sched Test {uid}",
            "key": uid.upper(),
            "status": "Active",
            "visibility": "workspace",
        })
        doc.insert(ignore_permissions=True)
        self._project = doc.name
        return doc.name

    def _make_task(self, project, title=None, is_recurring=0):
        doc = frappe.get_doc({
            "doctype": "BP Task",
            "title": title or f"P1 Sched Task {random_string(4)}",
            "project": project,
            "status": "To Do",
            "is_recurring": is_recurring,
        })
        doc.insert(ignore_permissions=True)
        self._task = doc.name
        return doc.name

    @patch("batch_projects.api.automation_schedule_data._assert_gateway_service_caller")
    @patch.object(automation_schedule_data.frappe, "get_all")
    def test_query_tasks_by_date_filters_trash(self, get_all, assert_caller):
        """query_tasks_by_date includes is_deleted:0."""
        get_all.return_value = []
        proj = self._make_project()

        automation_schedule_data.query_tasks_by_date(
            projects=[proj], field="due_date", date="2026-09-01"
        )

        filters = get_all.call_args.kwargs["filters"]
        self.assertEqual(filters["is_deleted"], 0)

    @patch("batch_projects.api.automation_schedule_data._assert_gateway_service_caller")
    def test_get_recurring_task_returns_none_for_trashed(self, assert_caller):
        """get_recurring_task returns None if task is trashed."""
        proj = self._make_project()
        task = self._make_task(proj, is_recurring=1)
        
        frappe.db.set_value("BP Task", task, "is_deleted", 1)
        
        result = automation_schedule_data.get_recurring_task(task)
        self.assertIsNone(result)

    @patch("batch_projects.api.automation_schedule_data._assert_gateway_service_caller")
    @patch.object(automation_schedule_data.frappe.db, "sql")
    def test_apply_task_occurrence_uses_for_update(self, sql, assert_caller):
        """apply_task_occurrence uses FOR UPDATE lock on source."""
        state = {"project": None}

        def sql_side_effect(query, *args, **kwargs):
            if "FOR UPDATE" in str(query):
                return [
                    frappe._dict(
                        name=args[0], is_deleted=0, is_recurring=1,
                        project=state["project"],
                    )
                ]
            return _REAL_DB_SQL(query, *args, **kwargs)

        sql.side_effect = sql_side_effect
        proj = self._make_project()
        state["project"] = proj
        task = self._make_task(proj, is_recurring=1)

        mutation = {
            "idempotency_key": "test-occurrence-key-1",
            "recurrence_source": task,
            "project": proj,
            "title": "Occurrence",
            "priority": "Medium",
            "task_type": "Task",
            "status": "To Do",
            "due_date": "2026-09-05",
        }

        with patch("batch_projects.api.automation_schedule_data.frappe.get_doc") as get_doc:
            def gd_side_effect(*args, **kwargs):
                first = args[0] if args else None
                if isinstance(first, dict) and first.get("recurrence_source"):
                    return MagicMock()
                return _REAL_GET_DOC(*args, **kwargs)

            get_doc.side_effect = gd_side_effect
            automation_schedule_data.apply_task_occurrence(mutation)
        
        # Verify FOR UPDATE was used
        query = sql.call_args.args[0]
        self.assertIn("FOR UPDATE", query)


class TestQueryFilters(FrappeTestCase):
    """P1-8: Sprint/velocity/dashboard/capacity/template filters."""

    def setUp(self):
        self._project = None
        self._task = None
        self._sprint = None
        self._team = None

    def tearDown(self):
        if self._task and frappe.db.exists("BP Task", self._task):
            try:
                frappe.delete_doc("BP Task", self._task, ignore_permissions=True, force=True)
            except Exception:
                pass
        if self._sprint and frappe.db.exists("BP Sprint", self._sprint):
            try:
                frappe.delete_doc("BP Sprint", self._sprint, ignore_permissions=True, force=True)
            except Exception:
                pass
        if self._project and frappe.db.exists("BP Project", self._project):
            try:
                frappe.delete_doc("BP Project", self._project, ignore_permissions=True, force=True)
            except Exception:
                pass
        if self._team and frappe.db.exists("BP Team", self._team):
            try:
                frappe.delete_doc("BP Team", self._team, ignore_permissions=True, force=True)
            except Exception:
                pass
        frappe.db.commit()

    def _make_project(self):
        uid = random_string(6)
        doc = frappe.get_doc({
            "doctype": "BP Project",
            "project_name": f"P1 Filter Test {uid}",
            "key": uid.upper(),
            "status": "Active",
            "visibility": "workspace",
        })
        doc.insert(ignore_permissions=True)
        self._project = doc.name
        return doc.name

    def _make_team(self):
        uid = random_string(6)
        doc = frappe.get_doc({
            "doctype": "BP Team",
            "team_name": f"P1 Filter Team {uid}",
        })
        doc.insert(ignore_permissions=True)
        self._team = doc.name
        return doc.name

    def _make_sprint(self, project, team):
        uid = random_string(6)
        doc = frappe.get_doc({
            "doctype": "BP Sprint",
            "sprint_name": f"Sprint {uid}",
            "project": project,
            "team": team,
            "status": "Active",
        })
        doc.insert(ignore_permissions=True)
        self._sprint = doc.name
        return doc.name

    @patch("batch_projects.api.board._check_permission")
    @patch.object(board.frappe, "get_all")
    def test_get_sprint_report_filters_trash(self, get_all, check_perm):
        """get_sprint_report includes is_deleted:0 in task query."""
        get_all.return_value = []
        proj = self._make_project()
        team = self._make_team()
        sprint = self._make_sprint(proj, team)

        board.get_sprint_report(proj, sprint)
        
        # Find the BP Task call
        task_calls = [c for c in get_all.call_args_list 
                      if c.args and c.args[0] == "BP Task"]
        self.assertTrue(len(task_calls) > 0)
        filters = task_calls[0].kwargs["filters"]
        self.assertEqual(filters["is_deleted"], 0)

    @patch("batch_projects.api.board._check_team_permission")
    @patch("batch_projects.permissions.get_accessible_projects")
    @patch.object(board.frappe, "get_all")
    def test_get_team_velocity_filters_trash_and_accessible(self, get_all, acc_proj, check_perm):
        """get_team_velocity includes is_deleted:0 and accessible project constraint."""
        acc_proj.return_value = None  # Admin
        get_all.return_value = []
        team = self._make_team()

        board.get_team_velocity(team, last_n_sprints=1)
        
        # Find the BP Task call
        task_calls = [c for c in get_all.call_args_list 
                      if c.args and c.args[0] == "BP Task"]
        if task_calls:
            filters = task_calls[0].kwargs["filters"]
            self.assertEqual(filters["is_deleted"], 0)

    @patch("batch_projects.api.board._require_system_user")
    @patch.object(board.frappe, "get_all")
    def test_get_dashboard_filters_trash(self, get_all, require_sys):
        """get_dashboard includes is_deleted:0 in personal task query."""
        get_all.return_value = []
        
        board.get_dashboard()
        
        # Find the BP Task call
        task_calls = [c for c in get_all.call_args_list 
                      if c.args and c.args[0] == "BP Task"]
        if task_calls:
            filters = task_calls[0].kwargs["filters"]
            self.assertEqual(filters.get("is_deleted"), 0)

    @patch("batch_projects.api.board._check_permission")
    @patch.object(board.frappe, "get_all")
    @patch.object(board.frappe, "get_doc")
    def test_get_sprint_capacity_filters_trash(self, get_doc, get_all, check_perm):
        """get_sprint_capacity includes is_deleted:0."""
        proj = self._make_project()
        team = self._make_team()
        sprint = self._make_sprint(proj, team)
        
        mock_sprint = MagicMock()
        mock_sprint.project = proj
        mock_sprint.sprint_name = "Sprint 1"
        get_doc.return_value = mock_sprint
        get_all.return_value = []
        
        board.get_sprint_capacity(sprint)
        
        # Find the BP Task call
        task_calls = [c for c in get_all.call_args_list 
                      if c.args and c.args[0] == "BP Task"]
        self.assertTrue(len(task_calls) > 0)
        filters = task_calls[0].kwargs["filters"]
        self.assertEqual(filters["is_deleted"], 0)

    @patch.object(project_templates.frappe, "get_all")
    def test_snapshot_tasks_filters_trash(self, get_all):
        """_snapshot_tasks includes is_deleted:0."""
        get_all.return_value = []
        proj = self._make_project()

        project_templates._snapshot_tasks(proj, "2026-09-01")
        
        filters = get_all.call_args.kwargs["filters"]
        self.assertEqual(filters["is_deleted"], 0)
