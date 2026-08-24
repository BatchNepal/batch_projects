# Copyright (c) 2026, BatchNepal and contributors
# Regression coverage for workflow_security.py — the graph-canvas surface's
# authorization boundary. Two independent problems, two independent test
# groups: api/workflows.py's own pre-existing bugs (cross-project list leak,
# confused-deputy test-fire), and the action-node authority gap workflow
# nodes never had at all (mirrors automation_security.py's own tests).
# Run: bench --site <site> run-tests --app batch_projects

import json
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from batch_projects import hooks, workflow_security
from batch_projects.api.board import create_project

TEST_KEY = "WFSEC"


def _delete_project(key):
    name = frappe.db.get_value("BP Project", {"key": key})
    if not name:
        return
    for wf in frappe.get_all("BP Workflow", filters={"project": name}, pluck="name"):
        frappe.delete_doc("BP Workflow", wf, ignore_permissions=True, force=True)
    for task in frappe.get_all("BP Task", filters={"project": name}, pluck="name"):
        frappe.delete_doc("BP Task", task, ignore_permissions=True, force=True)
    frappe.delete_doc("BP Project", name, ignore_permissions=True, force=True)
    frappe.db.commit()


def _delete_workspace_workflows(*names):
    for name in names:
        if frappe.db.exists("BP Workflow", name):
            frappe.delete_doc("BP Workflow", name, ignore_permissions=True, force=True)
    frappe.db.commit()


def _workflow(**overrides):
    """Fake doc for direct unit tests — frappe._dict satisfies the same
    .get()/.scope/.project shape a real BP Workflow Document exposes."""
    doc = frappe._dict(
        scope="project",
        project="SOME-PROJECT",
        project_filter=None,
        nodes=None,
        is_active=1,
    )
    doc.update(overrides)
    return doc


def _trigger_node(node_id="n1"):
    return {"id": node_id, "type": "trigger.task_event", "config": {"event": "task.created"}}


def _ensure_user(email):
    """Throwaway System User fixture for Link-field validity only — never a
    real signup, never a real email. "Administrator" is explicitly reserved
    (task_invariants._RESERVED_ASSIGNEES) and can't stand in as a valid
    assignee the way it does for admin-authority checks elsewhere."""
    if frappe.db.exists("User", email):
        return email
    frappe.get_doc({
        "doctype": "User",
        "email": email,
        "first_name": email.split("@")[0],
        "user_type": "System User",
        "enabled": 1,
        "send_welcome_email": 0,
        "roles": [{"role": "BP Member"}],
    }).insert(ignore_permissions=True)
    frappe.clear_cache(user=email)
    return email


def _add_member(project, user, role="Member"):
    frappe.db.sql(
        """INSERT INTO `tabBP Project Member`
           (name, parent, parenttype, parentfield, idx, user, role, creation, modified, owner, modified_by)
           VALUES (%s, %s, 'BP Project', 'members', 1, %s, %s, NOW(), NOW(), %s, %s)""",
        (frappe.generate_hash(length=10), project, user, role, "Administrator", "Administrator"),
    )


class TestWorkflowSecurityWiring(FrappeTestCase):
    """Prove the hook registrations exist AND point at real, callable
    functions — the original automation_security bug was these entries being
    entirely absent."""

    def test_doc_event_is_registered(self):
        self.assertEqual(
            hooks.doc_events["BP Workflow"]["validate"],
            "batch_projects.workflow_security.validate_workflow_authority",
        )

    def test_whitelisted_overrides_are_registered(self):
        self.assertEqual(
            hooks.override_whitelisted_methods["batch_projects.api.workflows.list_workflows"],
            "batch_projects.workflow_security.list_workflows",
        )
        self.assertEqual(
            hooks.override_whitelisted_methods["batch_projects.api.workflows.test_workflow"],
            "batch_projects.workflow_security.test_workflow",
        )
        self.assertEqual(
            hooks.override_whitelisted_methods["batch_projects.api.automation.run_workflow_node"],
            "batch_projects.workflow_security.run_workflow_node",
        )
        self.assertEqual(
            hooks.override_whitelisted_methods["batch_projects.api.automation.run_local_workflow_step"],
            "batch_projects.workflow_security.run_local_workflow_step",
        )

    def test_override_targets_are_whitelisted(self):
        frappe.is_whitelisted(workflow_security.list_workflows)
        frappe.is_whitelisted(workflow_security.test_workflow)
        frappe.is_whitelisted(workflow_security.run_workflow_node)
        frappe.is_whitelisted(workflow_security.run_local_workflow_step)


class TestWorkflowAuthority(FrappeTestCase):
    """Direct unit coverage of validate_workflow_authority's real branches —
    mirrors automation_security.py's own TestRuleAuthority, since every check
    here is that module's real code, reused rather than reimplemented."""

    def test_project_scope_workspace_only_action_rejected(self):
        nodes = json.dumps([
            _trigger_node(), {"id": "n2", "type": "action.update_erpnext_document", "config": {}},
        ])
        with self.assertRaises(frappe.PermissionError):
            workflow_security.validate_workflow_authority(_workflow(nodes=nodes))

    def test_workspace_scope_erp_action_allowed(self):
        nodes = json.dumps([
            _trigger_node(), {"id": "n2", "type": "action.update_erpnext_document", "config": {}},
        ])
        workflow_security.validate_workflow_authority(
            _workflow(scope="workspace", project=None, nodes=nodes)
        )

    def test_ordinary_action_needs_no_extra_authority(self):
        nodes = json.dumps([
            _trigger_node(), {"id": "n2", "type": "action.change_status", "config": {"status": "Done"}},
        ])
        workflow_security.validate_workflow_authority(_workflow(nodes=nodes))

    def test_notify_node_rejects_money_field_token(self):
        nodes = json.dumps([
            _trigger_node(),
            {"id": "n2", "type": "action.notify", "config": {"message": "Rate: {{ task.billable }}"}},
        ])
        with self.assertRaises(frappe.PermissionError):
            workflow_security.validate_workflow_authority(_workflow(nodes=nodes))

    def test_send_email_node_rejects_internal_field_token(self):
        nodes = json.dumps([
            _trigger_node(),
            {"id": "n2", "type": "action.send_email", "config": {
                "to": ["test4+info@batchnepal.com"], "subject": "Job {{ task.bridge_job_id }}", "message": "hi",
            }},
        ])
        with self.assertRaises(frappe.PermissionError):
            workflow_security.validate_workflow_authority(_workflow(nodes=nodes))

    def test_notify_node_rejects_every_task_reads_internal_field(self):
        """Regression for the automation_security.py field-list drift fix —
        proves the fix's benefit is transitive to BP Workflow through reuse,
        not something workflow_security.py would need its own copy of."""
        from batch_projects.task_reads import _INTERNAL_TASK_FIELDS

        for field in _INTERNAL_TASK_FIELDS:
            nodes = json.dumps([
                _trigger_node(),
                {"id": "n2", "type": "action.notify", "config": {"message": f"Value: {{{{ task.{field} }}}}"}},
            ])
            with self.assertRaises(frappe.PermissionError):
                workflow_security.validate_workflow_authority(_workflow(nodes=nodes))

    def test_notify_node_allows_ordinary_field_token(self):
        nodes = json.dumps([
            _trigger_node(),
            {"id": "n2", "type": "action.notify", "config": {"message": "Status: {{ task.status }}"}},
        ])
        workflow_security.validate_workflow_authority(_workflow(nodes=nodes))

    def test_notify_node_static_recipient_without_project_visibility_rejected(self):
        nodes = json.dumps([
            _trigger_node(),
            {"id": "n2", "type": "action.notify", "config": {"message": "hi", "users": ["test5+info@batchnepal.com"]}},
        ])
        with (
            patch("batch_projects.automation_security.resolve_system_user", return_value="test5+info@batchnepal.com"),
            patch("batch_projects.automation_security.can_receive_project_delivery", return_value=False),
        ):
            with self.assertRaises(frappe.PermissionError):
                workflow_security.validate_workflow_authority(_workflow(nodes=nodes))

    def test_notify_node_static_recipient_with_project_visibility_allowed(self):
        nodes = json.dumps([
            _trigger_node(),
            {"id": "n2", "type": "action.notify", "config": {"message": "hi", "users": ["test6+info@batchnepal.com"]}},
        ])
        with (
            patch("batch_projects.automation_security.resolve_system_user", return_value="test6+info@batchnepal.com"),
            patch("batch_projects.automation_security.can_receive_project_delivery", return_value=True),
        ):
            workflow_security.validate_workflow_authority(_workflow(nodes=nodes))

    def test_assign_issue_invalid_assignee_rejected(self):
        nodes = json.dumps([
            _trigger_node(),
            {"id": "n2", "type": "action.assign_issue", "config": {"assignees": ["test7+info@batchnepal.com"]}},
        ])
        with self.assertRaises(frappe.ValidationError):
            workflow_security.validate_workflow_authority(_workflow(nodes=nodes))

    def test_assign_issue_valid_assignee_allowed(self):
        user = _ensure_user("test8+info@batchnepal.com")
        try:
            nodes = json.dumps([
                _trigger_node(),
                {"id": "n2", "type": "action.assign_issue", "config": {"assignees": [user]}},
            ])
            workflow_security.validate_workflow_authority(_workflow(nodes=nodes))
        finally:
            frappe.delete_doc("User", user, ignore_permissions=True, force=True)
            frappe.db.commit()

    def test_project_filter_rejected_on_project_scope_workflow(self):
        with self.assertRaises(frappe.ValidationError):
            workflow_security.validate_workflow_authority(
                _workflow(project_filter=json.dumps(["OTHER-PROJECT"]), nodes=json.dumps([_trigger_node()]))
            )

    def test_non_action_nodes_are_skipped(self):
        """Trigger/condition/delay nodes carry no {type: 'action.*'} mapping
        — the parser must not choke on or misclassify them."""
        nodes = json.dumps([_trigger_node(), {"id": "n2", "type": "condition.branch", "config": {}}])
        workflow_security.validate_workflow_authority(_workflow(nodes=nodes))


class TestWorkflowDispatch(FrappeTestCase):
    """validate_workflow_dispatch is the runtime (not just save-time)
    boundary — legacy rows, direct DB tampering, and a stale/mismatched
    gateway payload must all be caught here."""

    def test_inactive_workflow_rejected(self):
        with self.assertRaises(frappe.PermissionError):
            workflow_security.validate_workflow_dispatch(
                _workflow(is_active=0, nodes=json.dumps([])), {"project": "SOME-PROJECT"}
            )

    def test_project_workflow_rejects_mismatched_payload_project(self):
        with self.assertRaises(frappe.PermissionError):
            workflow_security.validate_workflow_dispatch(
                _workflow(nodes=json.dumps([])), {"project": "OTHER-PROJECT"}
            )

    def test_project_workflow_cannot_execute_against_another_projects_task(self):
        with patch.object(
            frappe.db, "get_value",
            return_value=frappe._dict(name="TASK-1", project="OTHER-PROJECT", is_deleted=0),
        ):
            with self.assertRaises(frappe.PermissionError):
                workflow_security.validate_workflow_dispatch(
                    _workflow(nodes=json.dumps([])),
                    {"project": "SOME-PROJECT", "task": "TASK-1"},
                )

    def test_stale_erp_action_rejected_at_dispatch(self):
        """A row saved before this hook existed (or edited directly in the
        DB) must still be caught at fire time, not just at save time."""
        nodes = json.dumps([{"id": "n2", "type": "action.update_erpnext_document", "config": {}}])
        with self.assertRaises(frappe.PermissionError):
            workflow_security.validate_workflow_dispatch(
                _workflow(nodes=nodes), {"project": "SOME-PROJECT"}
            )

    def test_matching_scope_and_authorized_actions_pass(self):
        nodes = json.dumps([{"id": "n2", "type": "action.change_status", "config": {"status": "Done"}}])
        result = workflow_security.validate_workflow_dispatch(
            _workflow(nodes=nodes), {"project": "SOME-PROJECT"}
        )
        self.assertEqual(result["project"], "SOME-PROJECT")


class TestWorkflowWrapperDelegation(FrappeTestCase):
    """Prove run_workflow_node/run_local_workflow_step actually call
    validate_workflow_dispatch before delegating — not just that hooks.py
    names them correctly. Also prove node_type/config are never accepted as
    parameters: the executed node is always resolved from the workflow's
    own stored graph by node id, so validation (over that same stored
    graph) and execution can never disagree about what a node does."""

    def test_run_workflow_node_rejects_unknown_workflow_without_delegating(self):
        with (
            patch("batch_projects.api.automation._assert_service_caller"),
            patch.object(frappe.db, "exists", return_value=False),
            patch("batch_projects.api.automation.run_workflow_node") as real_run,
        ):
            result = workflow_security.run_workflow_node(workflow="nope", node="n1")
        self.assertEqual(result["status"], "Failed")
        real_run.assert_not_called()

    def test_run_workflow_node_blocks_inactive_workflow_before_delegating(self):
        nodes = json.dumps([{"id": "n1", "type": "action.change_status", "config": {"status": "Done"}}])
        with (
            patch("batch_projects.api.automation._assert_service_caller"),
            patch.object(frappe.db, "exists", return_value=True),
            patch("batch_projects.api.automation.run_workflow_node") as real_run,
            patch.object(frappe, "get_doc", return_value=_workflow(is_active=0, nodes=nodes)),
        ):
            with self.assertRaises(frappe.PermissionError):
                workflow_security.run_workflow_node(workflow="wf-1", node="n1")
        real_run.assert_not_called()

    def test_run_workflow_node_blocks_mismatched_project_before_delegating(self):
        nodes = json.dumps([{"id": "n1", "type": "action.change_status", "config": {"status": "Done"}}])
        with (
            patch("batch_projects.api.automation._assert_service_caller"),
            patch.object(frappe.db, "exists", return_value=True),
            patch("batch_projects.api.automation.run_workflow_node") as real_run,
            patch.object(frappe, "get_doc", return_value=_workflow(nodes=nodes)),
        ):
            with self.assertRaises(frappe.PermissionError):
                workflow_security.run_workflow_node(
                    workflow="wf-1", node="n1", payload={"project": "OTHER-PROJECT"},
                )
        real_run.assert_not_called()

    def test_run_workflow_node_rejects_node_id_absent_from_stored_graph(self):
        """The wrapper's own resolution must fail closed on an id that isn't
        in the graph at all — this is the check that stands between a
        caller and 'execute anything under this workflow's name'."""
        nodes = json.dumps([{"id": "n1", "type": "action.change_status", "config": {"status": "Done"}}])
        with (
            patch("batch_projects.api.automation._assert_service_caller"),
            patch.object(frappe.db, "exists", return_value=True),
            patch("batch_projects.api.automation.run_workflow_node") as real_run,
            patch.object(frappe, "get_doc", return_value=_workflow(nodes=nodes)),
        ):
            result = workflow_security.run_workflow_node(
                workflow="wf-1", node="does-not-exist", payload={"project": "SOME-PROJECT"},
            )
        self.assertEqual(result["status"], "Failed")
        self.assertEqual(result["json"]["error_code"], "unknown_action_node")
        real_run.assert_not_called()

    def test_run_workflow_node_delegates_once_checks_pass(self):
        nodes = json.dumps([{"id": "n1", "type": "action.change_status", "config": {"status": "Done"}}])
        with (
            patch("batch_projects.api.automation._assert_service_caller"),
            patch.object(frappe.db, "exists", return_value=True),
            patch(
                "batch_projects.api.automation.run_workflow_node", return_value={"status": "Success"},
            ) as real_run,
            patch.object(frappe, "get_doc", return_value=_workflow(nodes=nodes)),
        ):
            result = workflow_security.run_workflow_node(
                workflow="wf-1", node="n1", payload={"project": "SOME-PROJECT"},
            )
        self.assertEqual(result["status"], "Success")
        real_run.assert_called_once()
        # No node_type/config crosses the wrapper boundary — there is nothing
        # left for a caller to have supplied that the delegate could trust.
        self.assertNotIn("node_type", real_run.call_args.kwargs)
        self.assertNotIn("config", real_run.call_args.kwargs)

    def test_run_local_workflow_step_rejects_unresolvable_execution(self):
        with (
            patch("batch_projects.api.automation._assert_service_caller"),
            patch.object(frappe.db, "get_value", return_value=None),
            patch("batch_projects.api.automation.run_local_workflow_step") as real_run,
        ):
            with self.assertRaises(frappe.PermissionError):
                workflow_security.run_local_workflow_step(execution_id="exec-1", node_id="n1")
        real_run.assert_not_called()

    def test_run_local_workflow_step_rejects_node_not_local_atomic(self):
        """A node whose STORED type is external (e.g. Notify) must not run
        through the local-atomic path even if a caller asks for that node id
        here instead of via run_workflow_node."""
        nodes = json.dumps([{"id": "n1", "type": "action.notify", "config": {"message": "hi"}}])
        with (
            patch("batch_projects.api.automation._assert_service_caller"),
            patch.object(frappe.db, "get_value", return_value="wf-1"),
            patch.object(frappe.db, "exists", return_value=True),
            patch("batch_projects.api.automation.run_local_workflow_step") as real_run,
            patch.object(frappe, "get_doc", return_value=_workflow(nodes=nodes)),
        ):
            with self.assertRaises(frappe.ValidationError):
                workflow_security.run_local_workflow_step(
                    execution_id="exec-1", node_id="n1", owner="w1", lease_generation=1,
                    payload={"project": "SOME-PROJECT"},
                )
        real_run.assert_not_called()

    def test_run_local_workflow_step_delegates_once_checks_pass(self):
        nodes = json.dumps([{"id": "n1", "type": "action.change_status", "config": {"status": "Done"}}])
        with (
            patch("batch_projects.api.automation._assert_service_caller"),
            patch.object(frappe.db, "get_value", return_value="wf-1"),
            patch.object(frappe.db, "exists", return_value=True),
            patch(
                "batch_projects.api.automation.run_local_workflow_step", return_value={"status": "Success"},
            ) as real_run,
            patch.object(frappe, "get_doc", return_value=_workflow(nodes=nodes)),
        ):
            result = workflow_security.run_local_workflow_step(
                execution_id="exec-1", node_id="n1", payload={"project": "SOME-PROJECT"},
            )
        self.assertEqual(result["status"], "Success")
        real_run.assert_called_once()
        self.assertNotIn("node_type", real_run.call_args.kwargs)
        self.assertNotIn("config", real_run.call_args.kwargs)


class TestWorkflowNodeExecutionMatchesStoredDefinition(FrappeTestCase):
    """The regression this whole PR exists for: a request that names a real
    workflow/node but tries to make it perform a DIFFERENT action than what
    is actually stored must either run the stored action or be rejected —
    never the caller's claimed one. node_type/config aren't parameters
    anymore, so there's no field left for such a request to set; these tests
    prove that removing them didn't just move the trust elsewhere."""

    def _workflow_with_notify_node(self):
        nodes = json.dumps([
            {"id": "trigger", "type": "trigger.task_event", "config": {"event": "task.updated"}},
            {"id": "n2", "type": "action.notify", "config": {"message": "hi"}},
        ])
        return _workflow(scope="project", project="SOME-PROJECT", nodes=nodes, is_active=1)

    def test_run_workflow_node_executes_the_stored_notify_not_an_erp_update(self):
        workflow_doc = self._workflow_with_notify_node()
        executed_actions = []

        def fake_execute(action, ctx, payload):
            executed_actions.append(action)
            return "Success", "ok"

        with (
            patch("batch_projects.api.automation._assert_service_caller"),
            patch("batch_projects.entitlements.is_feature_enabled", return_value=True),
            patch.object(frappe.db, "exists", return_value=True),
            patch.object(frappe, "get_doc", return_value=workflow_doc),
            patch(
                "batch_projects.batch_projects.doctype.bp_automation_rule.bp_automation_rule._execute",
                side_effect=fake_execute,
            ),
            patch(
                "batch_projects.batch_projects.doctype.bp_automation_rule.bp_automation_rule._build_context",
                return_value={},
            ),
        ):
            # A caller (or a compromised/buggy gateway) asking to execute
            # node "n2" gets whatever "n2" actually is in the stored graph —
            # Notify — regardless of any extra field it might try to send;
            # there is no node_type/config parameter left to smuggle
            # "Update ERPNext Document" through anymore.
            result = workflow_security.run_workflow_node(
                workflow="wf-1", node="n2", payload={"project": "SOME-PROJECT"},
                node_type="action.update_erpnext_document",
                config={"doctype": "Sales Invoice", "name": "SINV-0001", "fields": {"grand_total": 0}},
            )

        self.assertEqual(result["status"], "Success")
        self.assertEqual(len(executed_actions), 1)
        self.assertEqual(executed_actions[0]["type"], "Notify")
        self.assertEqual(executed_actions[0]["config"], {"message": "hi"})

    def test_run_workflow_node_rejects_when_claimed_node_id_has_no_stored_action(self):
        workflow_doc = self._workflow_with_notify_node()
        with (
            patch("batch_projects.api.automation._assert_service_caller"),
            patch.object(frappe.db, "exists", return_value=True),
            patch.object(frappe, "get_doc", return_value=workflow_doc),
            patch(
                "batch_projects.batch_projects.doctype.bp_automation_rule.bp_automation_rule._execute",
            ) as execute_mock,
        ):
            result = workflow_security.run_workflow_node(
                workflow="wf-1", node="trigger", payload={"project": "SOME-PROJECT"},
                node_type="action.update_erpnext_document",
                config={"doctype": "Sales Invoice", "name": "SINV-0001", "fields": {"grand_total": 0}},
            )
        self.assertEqual(result["status"], "Failed")
        self.assertEqual(result["json"]["error_code"], "unknown_action_node")
        execute_mock.assert_not_called()


class TestListWorkflowsScopeLeak(FrappeTestCase):
    """Regression for the confirmed cross-project data leak: the original
    or_filters composition returned every scope="project" workflow instance-
    wide to any single-project viewer, not just this project's own rows."""

    def setUp(self):
        frappe.set_user("Administrator")
        _delete_project(TEST_KEY)
        self.project_a = create_project(
            project_name="Workflow Security Leak Test A", key=TEST_KEY, visibility="private",
            workflow_states=json.dumps([{"name": "To Do", "color": "#6B7280", "category": "open"}]),
            issue_types=json.dumps([{"name": "Task", "color": "#0B6BCB", "icon": "CheckSquare"}]),
        )["name"]
        self.project_b = create_project(
            project_name="Workflow Security Leak Test B", key="WFSCB", visibility="private",
            workflow_states=json.dumps([{"name": "To Do", "color": "#6B7280", "category": "open"}]),
            issue_types=json.dumps([{"name": "Task", "color": "#0B6BCB", "icon": "CheckSquare"}]),
        )["name"]
        self.wf_a = frappe.get_doc({
            "doctype": "BP Workflow", "title": "Workflow A", "scope": "project",
            "project": self.project_a, "nodes": "[]", "edges": "[]", "is_active": 1,
        }).insert(ignore_permissions=True).name
        self.wf_b = frappe.get_doc({
            "doctype": "BP Workflow", "title": "Workflow B (must not leak)", "scope": "project",
            "project": self.project_b, "nodes": "[]", "edges": "[]", "is_active": 1,
        }).insert(ignore_permissions=True).name

    def tearDown(self):
        _delete_project(TEST_KEY)
        _delete_project("WFSCB")

    def test_project_viewer_sees_only_own_projects_workflows(self):
        with patch("batch_projects.workflow_security._guard"):
            rows = workflow_security.list_workflows(project=self.project_a)
        names = {r["name"] for r in rows}
        self.assertIn(self.wf_a, names)
        self.assertNotIn(self.wf_b, names)


class TestWorkflowTestFixtureBinding(FrappeTestCase):
    """Regression for the confirmed confused-deputy execution: the original
    test_workflow fired the real gateway pipeline using an arbitrary task's
    own project in place of the workflow's, with no cross-check."""

    def setUp(self):
        frappe.set_user("Administrator")
        _delete_project(TEST_KEY)
        self.project_a = create_project(
            project_name="Workflow Fixture Binding Test A", key=TEST_KEY, visibility="private",
            workflow_states=json.dumps([{"name": "To Do", "color": "#6B7280", "category": "open"}]),
            issue_types=json.dumps([{"name": "Task", "color": "#0B6BCB", "icon": "CheckSquare"}]),
        )["name"]
        self.project_b = create_project(
            project_name="Workflow Fixture Binding Test B", key="WFSCB", visibility="private",
            workflow_states=json.dumps([{"name": "To Do", "color": "#6B7280", "category": "open"}]),
            issue_types=json.dumps([{"name": "Task", "color": "#0B6BCB", "icon": "CheckSquare"}]),
        )["name"]
        self.task_in_b = frappe.get_doc({
            "doctype": "BP Task", "project": self.project_b, "title": "b's task",
            "task_type": "Task", "status": "To Do",
        }).insert(ignore_permissions=True).name
        self.task_in_a = frappe.get_doc({
            "doctype": "BP Task", "project": self.project_a, "title": "a's task",
            "task_type": "Task", "status": "To Do",
        }).insert(ignore_permissions=True).name
        self.workflow_a = frappe.get_doc({
            "doctype": "BP Workflow", "title": "Workflow A", "scope": "project",
            "project": self.project_a,
            "nodes": json.dumps([_trigger_node()]), "edges": "[]", "is_active": 1,
        }).insert(ignore_permissions=True).name

    def tearDown(self):
        _delete_project(TEST_KEY)
        _delete_project("WFSCB")

    def test_cross_project_task_binding_is_rejected(self):
        with (
            patch("batch_projects.workflow_security._guard"),
            patch("batch_projects.api.workflows.test_workflow") as original,
        ):
            with self.assertRaises(frappe.PermissionError):
                workflow_security.test_workflow(self.workflow_a, task=self.task_in_b)
        original.assert_not_called()

    def test_same_project_task_binding_delegates(self):
        with (
            patch("batch_projects.workflow_security._guard"),
            patch("batch_projects.api.workflows.test_workflow", return_value={"status": "fired"}) as original,
        ):
            result = workflow_security.test_workflow(self.workflow_a, task=self.task_in_a)
        self.assertEqual(result["status"], "fired")
        original.assert_called_once()


class TestWorkflowSaveIntegration(FrappeTestCase):
    """End-to-end: the doc_events hook must actually fire on a real save,
    for both structural authority (this hook) and caller authority
    (api/workflows.py's pre-existing _require_workflow_admin). Runs as a
    real project-Admin member, not Administrator + mocks — _require_
    workflow_admin's real chain (board._check_permission -> access.require
    -> get_effective_role) reads BP Project Member rows directly and never
    calls access.has_at_least at all, so mocking that function is inert;
    Administrator is also auto-added as a real Admin member by
    create_project, which would make an authority mock's effect
    unverifiable either way."""

    def setUp(self):
        frappe.set_user("Administrator")
        _delete_project(TEST_KEY)
        self.project = create_project(
            project_name="Workflow Save Integration Test", key=TEST_KEY, visibility="private",
            workflow_states=json.dumps([{"name": "To Do", "color": "#6B7280", "category": "open"}]),
            issue_types=json.dumps([{"name": "Task", "color": "#0B6BCB", "icon": "CheckSquare"}]),
        )["name"]
        self.admin_user = _ensure_user("test9+info@batchnepal.com")
        _add_member(self.project, self.admin_user, "Admin")
        self.outsider = _ensure_user("test10+info@batchnepal.com")
        frappe.local._bp_effective_role = {}

    def tearDown(self):
        frappe.set_user("Administrator")
        _delete_project(TEST_KEY)
        for user in (self.admin_user, self.outsider):
            if frappe.db.exists("User", user):
                frappe.delete_doc("User", user, ignore_permissions=True, force=True)
        frappe.db.commit()

    def test_project_admin_can_create_valid_project_workflow(self):
        from batch_projects.api.workflows import save_workflow

        nodes = [_trigger_node(), {"id": "n2", "type": "action.change_status", "config": {"status": "Done"}}]
        edges = [{"id": "e1", "source": "n1", "target": "n2"}]
        frappe.set_user(self.admin_user)
        with patch("batch_projects.api.workflows.require_feature"):
            result = save_workflow(
                title="Valid project workflow", scope="project", project=self.project,
                nodes=json.dumps(nodes), edges=json.dumps(edges),
            )
        self.assertTrue(result["name"])

    def test_project_admin_cannot_create_workspace_only_action(self):
        from batch_projects.api.workflows import save_workflow

        nodes = [_trigger_node(), {"id": "n2", "type": "action.update_erpnext_document", "config": {}}]
        edges = [{"id": "e1", "source": "n1", "target": "n2"}]
        frappe.set_user(self.admin_user)
        with patch("batch_projects.api.workflows.require_feature"):
            with self.assertRaises(frappe.PermissionError):
                save_workflow(
                    title="Should be rejected", scope="project", project=self.project,
                    nodes=json.dumps(nodes), edges=json.dumps(edges),
                )

    def test_unauthorized_user_cannot_modify_workflow(self):
        """A real user with no membership on this (private-visibility)
        project."""
        from batch_projects.api.workflows import save_workflow

        frappe.set_user(self.outsider)
        with patch("batch_projects.api.workflows.require_feature"):
            with self.assertRaises(frappe.PermissionError):
                save_workflow(
                    title="Should be rejected", scope="project", project=self.project,
                    nodes=json.dumps([_trigger_node()]), edges="[]",
                )
