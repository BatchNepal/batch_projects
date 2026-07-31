# Changelog

All notable changes to BatchProjects are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Pre-1.0 versions are not listed — the schema was not stable.

---

## [1.0.0] — 2026-05-20

First release with a canonical, stable schema. Install fresh; no migration
path from pre-1.0 exists by design (no production data to migrate).

### Breaking changes

- **Renamed `BP Issue` → `BP Task`** (and all child tables)
  - `BP Issue Assignee` → `BP Task Assignee`
  - `BP Issue Link` → `BP Task Link`
  - `BP Issue Reference` → `BP Task Reference`
- **Field renames on `BP Task`**
  - `issue_key` → `task_key`
  - `issue_type` → `task_type`
  - `parent_issue` → `parent_task`
  - `linked_issue` / `linked_issue_key` / `linked_issue_title` / `linked_issue_status` → `linked_task` / `linked_task_key` / `linked_task_title` / `linked_task_status`
- **Field renames on `BP Activity`**
  - `issue` → `task`
  - `issue_key` → `task_key`
- **API endpoint renames** (all in `batch_projects.api.board`)
  - `create_issue` → `create_task`
  - `update_issue` → `update_task`
  - `get_issue` → `get_task`
  - `delete_issue` → `delete_task`
  - `query_issues` → `query_tasks`
  - `search_issues` → `search_tasks`
  - `update_issue_status` → `update_task_status`
  - `reorder_issues` → `reorder_tasks`
  - `add_issue_link` → `add_task_link`
  - `remove_issue_link` → `remove_task_link`
  - `move_issue_to_sprint` → `move_task_to_sprint`
- **Realtime event names** changed from `issue.*` to `task.*`
  - `issue.created` → `task.created`
  - `issue.updated` → `task.updated`
  - `issue.deleted` → `task.deleted`
  - `issue.status_changed` → `task.status_changed`
  - `issue.assigned` → `task.assigned`
  - `issue.unassigned` → `task.unassigned`
- **Frontend component renames**
  - `IssueDetail.vue` → `TaskDetail.vue`
  - `IssueCard.vue` → `TaskCard.vue`
  - `CreateIssue.vue` → `CreateTask.vue`
  - `IssueAttachments.vue` → `TaskAttachments.vue`
  - `IssueContextMenu.vue` → `TaskContextMenu.vue`

### Bug fixes

- **Task key race condition**: fixed duplicate key generation under concurrent
  inserts using MariaDB `LAST_INSERT_ID(expr)` connection-local atomicity.
  Removes the window where two tasks created simultaneously could get the same
  key (e.g. `PROJ-7` assigned to both).
- **`schema_version` increment**: operator-precedence bug caused `or 0 + 1`
  to evaluate as `or (0+1)`, always returning 1 for null values instead of
  incrementing. Fixed to `(or 0) + 1`.
- **`CreateProject.vue` casing**: was `Createproject.vue` — broke silently on
  case-sensitive Linux filesystems. Renamed with `git mv` to preserve history.
- **`TaskDetail.vue` missing imports**: `nextTick` and `toast` were used but
  not imported. Fixed.
- **Migration patch idempotency**: `migrate_to_workflow_states` omitted
  `issue_types` from the `frappe.get_all` fields list, causing it to
  unconditionally overwrite existing issue types on every run.

### Security

- **15 unauthenticated Team API endpoints** now require `_check_team_permission`
  or `_require_system_user`. Previously any unauthenticated request could read
  and mutate team data.
- **`create_project`, `search_tasks`, `get_dashboard`** audited and gated with
  `_require_system_user()` so website users cannot reach them.
- **Realtime broadcasts** scoped to project members + System Managers instead
  of broadcasting to all connected users. Prevents data leakage across
  projects.

### Behavior changes

- **Status validation now throws** instead of silently auto-correcting to an
  arbitrary state. Clients will receive an explicit error for invalid statuses.
- **Concurrent edit detection**: removed `ignore_version=True` from
  `update_task`. Concurrent edits to the same task now surface
  `TimestampMismatchError` instead of silently overwriting the earlier save.
- **Realtime recipient list cached** at 60 s TTL (via Redis) to avoid two DB
  queries per event emit. Bust with `invalidate_recipients(project)` after
  membership changes.

---

## [Unreleased]

- Sprint Mode toggle (project-level setting)
- `api/board.py` decomposition into focused modules
- `TaskDetail.vue` composable extraction
- Workflow templates per vertical (software, services, construction)
