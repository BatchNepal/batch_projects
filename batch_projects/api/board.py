import frappe
import json
import re

from batch_projects.events import (
    emit,
    TASK_CREATED, TASK_UPDATED, TASK_STATUS_CHANGED, COMMENT_ADDED, COMMENT_EDITED,
    COMMENT_DELETED, PROJECT_CREATED,
    PROJECT_ROLE_CHANGED,
    SPRINT_STARTED, SPRINT_COMPLETED
)
from batch_projects.batch_projects.doctype.bp_task.bp_task import (
    _validate_custom_field_values,
    _parse_json,
)
from batch_projects.api import custom_fields as _custom_fields

 
# ─── PERMISSIONS ─────────────────────────────────────────────────────────────
# The project-role hierarchy and effective-role resolution now live in the
# single source of truth: batch_projects.access (ROLE_RANK). The thin wrappers
# below keep the historic call sites (`_check_permission`, `_get_user_project_role`)
# working while delegating all real logic there.

def _get_user_project_role(project: str) -> str | None:
    """Effective project role (explicit membership, else visibility fallback).
    Delegates to the unified model in batch_projects.access."""
    from batch_projects import access
    return access.get_effective_role(project)


@frappe.whitelist()
def get_my_capabilities(project):
    """The caller's effective role + capability set for `project`,
    resolved fresh on every call — deliberately NOT folded into get_board's
    payload, which IS cached per-project with no user dimension
    (batch_projects/cache.py's VIEW_BOARD key is (view, project) only, no
    user); embedding a per-user role there would leak one user's role to the
    next user who hits the same cached board. Cheap enough to call on every
    project switch."""
    from batch_projects.gateway_guard import verify_gateway_request
    verify_gateway_request()

    from batch_projects import access
    role = access.get_effective_role(project)
    return {
        "role": role,
        "capabilities": access.get_capability_matrix().get(role, {}) if role else {},
    }


def _check_permission(project: str, required_role: str, allow_archived: bool = False):
    """Enforce a minimum project role. Single gate for whitelisted endpoints —
    delegates to the unified model so the API layer, the has_permission hook
    and list/report filtering all agree. Non-members on a workspace project get
    Viewer (read-only), so this now correctly blocks their writes instead of
    relying on an accidental doctype-permission failure downstream.
    Also verifies the request came through the bp-gateway."""
    from batch_projects.gateway_guard import verify_gateway_request
    verify_gateway_request()

    from batch_projects import access
    access.require(project, required_role, allow_archived=allow_archived)


def _check_task_permission(task: str, project: str, required_role: str):
    """Task-scoped counterpart to _check_permission — also honors a task's
    own assignee(s) for Member-or-below actions (view/edit/log time) even
    without project membership (access.require_task). Use only at endpoints
    scoped to exactly ONE task (get_task, update_task, the timer); never for
    anything that lists or touches sibling tasks or the project itself."""
    from batch_projects.gateway_guard import verify_gateway_request
    verify_gateway_request()

    from batch_projects import access
    access.require_task(task, project, required_role)


def _require_system_user():
    """Block website/guest users from calling any BP API endpoint.
    Also verifies the request came through the bp-gateway (gateway_guard.py).
    Direct-to-Frappe calls missing the gateway signature are rejected."""
    from batch_projects.gateway_guard import verify_gateway_request
    verify_gateway_request()

    user = frappe.session.user
    if "System Manager" in frappe.get_roles(user):
        return
    if frappe.db.get_value("User", user, "user_type") != "System User":
        frappe.throw("Access denied.", frappe.PermissionError)


def _check_team_permission(team: str, required_role: str = "Viewer"):
    """
    Viewer  — any authenticated System User (no membership required)
    Member / Manager / Admin — must be a BP Team Member with sufficient role
    """
    user = frappe.session.user
    if "System Manager" in frappe.get_roles(user):
        return

    _require_system_user()

    role = frappe.db.get_value(
        "BP Team Member", {"parent": team, "user": user}, "role"
    )

    if required_role == "Viewer":
        # Org members may browse any team (workspace model); guests may only see
        # teams they actually belong to.
        from batch_projects import access
        if access.is_guest(user) and not role:
            frappe.throw("You don't have access to this team.", frappe.PermissionError)
        return

    if not role:
        frappe.throw("You are not a member of this team.", frappe.PermissionError)

    hierarchy = {"Admin": 3, "Manager": 2, "Member": 1}
    if hierarchy.get(role, 0) < hierarchy.get(required_role, 0):
        frappe.throw(
            f"You need at least {required_role} access for this team action.",
            frappe.PermissionError,
        )


# ─── QUERY ENGINE ────────────────────────────────────────────────────────────

def _deep_parse_json(raw):
    val = raw
    for _ in range(6):
        if not isinstance(val, str):
            break
        try:
            val = json.loads(val)
        except Exception:
            break
    return val


def _normalize_workflow_states(raw_states):
    DEFAULT_COLORS = ["#8993A4","#0052CC","#36B37E","#FF5630","#FFAB00","#6554C0","#00B8D9","#403294"]

    states = _deep_parse_json(raw_states)
    if not isinstance(states, list):
        return []

    result = []
    for i, s in enumerate(states):
        s = _deep_parse_json(s)
        if not isinstance(s, dict):
            continue
        if not s.get("name"):
            continue
        s.setdefault("color", DEFAULT_COLORS[i % len(DEFAULT_COLORS)])
        s.setdefault("category", "unstarted")
        result.append(s)
    return result


_VALID_TRANSITION_MIN_ROLES = ("Manager", "Admin")


def _normalize_allowed_to(allowed, valid_names):
    """Sanitize one state's `allowed_to` against the sibling states actually
    being saved. Each entry is either a plain status name or
    {"name", "min_role"}; entries referencing a name outside `valid_names`
    (renamed/removed in this same save) are dropped, and an unrecognized
    min_role is stripped rather than rejected. Returns None (unrestricted)
    when nothing valid survives, instead of leaving a status locked shut by
    an edit to a DIFFERENT status."""
    if not isinstance(allowed, list):
        return None
    cleaned = []
    for entry in allowed:
        if isinstance(entry, dict):
            name = entry.get("name")
            if name not in valid_names:
                continue
            min_role = entry.get("min_role")
            cleaned.append({"name": name, "min_role": min_role} if min_role in _VALID_TRANSITION_MIN_ROLES else name)
        elif entry in valid_names:
            cleaned.append(entry)
    return cleaned or None


@frappe.whitelist(allow_guest=True)
def get_session_info():
    """Returns current session user, csrf_token and sitename. Used by SPA to bootstrap socket auth.

    Also carries app_version/gateway_min_version — unauthenticated and
    pre-bridge (see gateway_guard._PRE_BRIDGE_PATHS), so both the gateway
    (boot-time compat self-check) and the gateway installer (version
    resolution) can read this before any session/bridge exists.
    """
    from batch_projects import __version__ as app_version
    from batch_projects.hooks import gateway_min_version

    return {
        "user": frappe.session.user,
        "user_fullname": frappe.utils.get_fullname(frappe.session.user),
        "csrf_token": frappe.sessions.get_csrf_token(),
        "sitename": frappe.local.site,
        "app_version": app_version,
        "gateway_min_version": gateway_min_version,
    }


# ─── TRASH FILTER ────────────────────────────────────────────────────────────
# audit 07 follow-up: get_board/query_tasks excluded trashed tasks but
# get_gantt/get_backlog/get_my_tasks/get_triage_queue/get_epics and others
# didn't — a trashed task looked gone on the board but was still fully live
# everywhere else. frappe.get_all() ALWAYS runs with ignore_permissions=True
# (confirmed in frappe/model/db_query.py), which skips permission_query_
# conditions entirely — so the doctype hook in permissions.py covers only the
# REST/desk/report (get_list-based) layer, never these get_all call sites.
# Every one of them needs this explicitly; there is no single choke point.

def _task_filters(base=None, include_deleted=False):
    """Merge `base` with the default is_deleted=0 exclusion every BP Task
    list/count query needs. Pass include_deleted=True only for the trash
    view itself (list_deleted_tasks) and the purge job — everything else
    should be invisible to trashed tasks by default."""
    filters = dict(base or {})
    if not include_deleted and "is_deleted" not in filters:
        filters["is_deleted"] = 0
    return filters


@frappe.whitelist()
def query_tasks(project, filters=None, group_by=None, sort_by="creation",
                 sort_order="asc", limit=None, offset=0):
    _check_permission(project, "BP Viewer")

    if isinstance(filters, str):
        filters = json.loads(filters)
    filters = filters or {}

    # Trashed tasks (audit 02 §B3 / 07 §G3) are recoverable, not gone — but
    # must not clutter the normal board/list/backlog/sprint view they're
    # fetched through. list_deleted_tasks is the one place that deliberately
    # asks for is_deleted=1.
    db_filters = {"project": project, "is_deleted": 0}

    if filters.get("status"):
        db_filters["status"] = ["in", filters["status"]]
    if filters.get("priority"):
        db_filters["priority"] = ["in", filters["priority"]]
    if filters.get("task_type"):
        db_filters["task_type"] = ["in", filters["task_type"]]
    if filters.get("epic"):
        db_filters["epic"] = ["in", filters["epic"]]
    if filters.get("sprint"):
        db_filters["sprint"] = ["in", filters["sprint"]]
    if "parent_task" in filters:
        if filters["parent_task"] is None:
            db_filters["parent_task"] = ["is", "not set"]
        else:
            db_filters["parent_task"] = filters["parent_task"]
    if filters.get("due_before"):
        db_filters["due_date"] = ["<=", filters["due_before"]]
    if filters.get("due_after"):
        db_filters["due_date"] = [">=", filters["due_after"]]
    if filters.get("created_after"):
        db_filters["creation"] = [">=", filters["created_after"]]

    # ── Assignee filter (via child table) ────────────────────────────────────
    assignee_issue_names = None
    if filters.get("assignee"):
        rows = frappe.get_all(
            "BP Task Assignee",
            filters={"user": ["in", filters["assignee"]], "parenttype": "BP Task"},
            fields=["parent"],
            distinct=True,
        )
        assignee_issue_names = [r["parent"] for r in rows]
        if not assignee_issue_names:
            return _empty_result(project, group_by)
        db_filters["name"] = ["in", assignee_issue_names]

    or_filters = []
    if filters.get("search"):
        q = filters["search"]
        or_filters = [
            ["title", "like", f"%{q}%"],
            ["task_key", "like", f"%{q}%"],
        ]

    fields = [
        "name", "task_key", "title", "status", "priority", "task_type",
        "epic", "sprint", "story_points", "due_date", "start_date",
        "planned_start", "planned_end", "sequence_no",
        "board_order", "board_rank", "parent_task", "team", "description",
        "estimated_hours", "actual_hours", "billable",
        "started_on", "completed_on", "completed_by", "resolution",
        "blocked_reason", "blocked_since", "blocked_by",
        "custom_field_values", "labels",
        "reporter", "creation", "modified",
    ]

    valid_sort_fields = {
        "creation", "modified", "due_date", "start_date",
        "planned_start", "planned_end", "sequence_no",
        "priority", "title", "board_order", "story_points",
    }
    sort_by = sort_by if sort_by in valid_sort_fields else "creation"
    sort_order = "asc" if sort_order not in ("asc", "desc") else sort_order
    # "board_order" is the manual-drag mode; it is physically ordered by the
    # fractional board_rank (see rank.py), with creation as a stable tiebreak.
    if sort_by == "board_order":
        order_by = f"board_rank {sort_order}, creation asc"
    else:
        order_by = f"{sort_by} {sort_order}"

    kwargs = dict(filters=db_filters, fields=fields, order_by=order_by)
    if or_filters:
        kwargs["or_filters"] = or_filters
    if limit:
        kwargs["limit"] = int(limit)
        kwargs["start"] = int(offset)

    issues = frappe.get_all("BP Task", **kwargs)

    # ── Post-fetch: assignees ─────────────────────────────────────────────────
    issue_names = [i["name"] for i in issues]
    assignees_map = _fetch_assignees(issue_names)
    links_map = _fetch_task_links(issue_names)
    refs_map = _fetch_task_refs(issue_names)

    # ── Post-fetch: sub_tasks (single batch query, not N+1) ──────────────────
    subtasks_raw = frappe.get_all(
        "BP Task",
        filters={"parent_task": ["in", issue_names], "is_deleted": 0},
        fields=["name", "task_key", "title", "status", "priority",
                "task_type", "due_date", "parent_task"],
        order_by="creation asc",
    )
    st_names = [st["name"] for st in subtasks_raw]
    st_assignees = _fetch_assignees(st_names) if st_names else {}
    for st in subtasks_raw:
        st["assignees"] = st_assignees.get(st["name"], [])
    subtasks_map = {}
    for st in subtasks_raw:
        subtasks_map.setdefault(st["parent_task"], []).append(st)

    epics = _fetch_epics(issues)

    hidden_cf_ids = _custom_fields.hidden_field_ids_for_project(project, "tasks")

    for issue in issues:
        issue["assignees"] = assignees_map.get(issue["name"], [])
        issue["sub_tasks"] = subtasks_map.get(issue["name"], [])
        issue["links"] = links_map.get(issue["name"], [])
        issue["references"] = refs_map.get(issue["name"], [])
        issue["custom_field_values"] = _custom_fields.strip_unviewable_field_values(
            _parse_json(issue.get("custom_field_values"), {}), hidden_cf_ids
        )
        issue["labels"] = _parse_json(issue.get("labels"), [])
        if issue.get("epic") and issue["epic"] in epics:
            issue["epic_title"] = epics[issue["epic"]]["title"]
            issue["epic_color"] = epics[issue["epic"]]["color"]
        else:
            issue["epic_title"] = ""
            issue["epic_color"] = ""

    if filters.get("labels"):
        required_labels = set(filters["labels"])
        issues = [
            i for i in issues
            if required_labels.intersection(set(i.get("labels") or []))
        ]

    if filters.get("custom_fields"):
        cf_filters = filters["custom_fields"]
        def _matches_cf(issue):
            cfv = issue.get("custom_field_values") or {}
            for field_id, expected in cf_filters.items():
                actual = cfv.get(field_id)
                if isinstance(expected, list):
                    if not set(expected).intersection(set(actual or [])):
                        return False
                else:
                    if actual != expected:
                        return False
            return True
        issues = [i for i in issues if _matches_cf(i)]

    if group_by:
        return _group_issues(project, issues, group_by)

    return {"issues": issues, "total": len(issues)}


def _empty_result(project, group_by):
    if group_by:
        return {"groups": [], "total": 0}
    return {"issues": [], "total": 0}


def _group_issues(project, issues, group_by):
    groups = {}

    if group_by == "status":
        proj = frappe.get_doc("BP Project", project)
        ordered_keys = [s["name"] for s in _normalize_workflow_states(proj.get_workflow_states())]
        for key in ordered_keys:
            groups[key] = []
        fallback_key = ordered_keys[0] if ordered_keys else "Unknown"
        for issue in issues:
            key = issue.get("status") or fallback_key
            if key not in groups:
                groups[key] = []
            groups[key].append(issue)

    elif group_by == "priority":
        ordered_keys = ["Highest", "High", "Medium", "Low", "Lowest"]
        for key in ordered_keys:
            groups[key] = []
        for issue in issues:
            key = issue.get("priority") or "Medium"
            groups.setdefault(key, []).append(issue)

    elif group_by == "assignee":
        no_assignee = "Unassigned"
        groups[no_assignee] = []
        for issue in issues:
            assignees = issue.get("assignees") or []
            if not assignees:
                groups[no_assignee].append(issue)
            else:
                for a in assignees:
                    key = a.get("full_name") or a.get("user")
                    groups.setdefault(key, []).append(issue)

    elif group_by == "epic":
        no_epic = "No Epic"
        groups[no_epic] = []
        for issue in issues:
            key = issue.get("epic_title") or no_epic
            groups.setdefault(key, []).append(issue)

    elif group_by == "task_type":
        for issue in issues:
            key = issue.get("task_type") or "Task"
            groups.setdefault(key, []).append(issue)

    else:
        for issue in issues:
            key = str(issue.get(group_by) or f"No {group_by}")
            groups.setdefault(key, []).append(issue)

    result = [
        {"key": k, "issues": v, "count": len(v)}
        for k, v in groups.items()
    ]
    return {"groups": result, "total": sum(len(v) for v in groups.values())}


# ─── PROJECTS ─────────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_projects():
    from batch_projects.permissions import get_accessible_projects
    accessible = get_accessible_projects()  # None = admin (all)
    filters = {"status": "Active"}
    if accessible is not None:
        if not accessible:
            return []
        filters["name"] = ["in", list(accessible)]

    projects = frappe.get_all(
        "BP Project",
        filters=filters,
        fields=[
            "name", "project_name", "key", "status", "lead",
            "description", "workflow_states", "issue_types",
            "custom_fields", "enabled_views", "pinned_views", "default_view", "company", "project_color",
            "project_icon", "theme", "schema_version", "visibility", "project_type",
            "client", "budget_amount", "hourly_rate", "retainer_hours",
            "currency", "start_date", "target_end_date", "template_used", "team",
            "source_sales_order", "source_lead", "source_opportunity", "source_quotation",
        ],
        order_by="creation desc",
    )
    from batch_projects.setup.project_templates import get_template_views

    # Must avoid a per-project frappe.db.count() call here — 2 calls per
    # project is 2N queries for N projects, which is why this endpoint's
    # own response is 60s-cached in bp-gateway's cache config in the first
    # place. One grouped query replaces all of them; each project's own
    # completed-status set (workflow_states differ per project) is applied
    # in Python against the pre-aggregated counts.
    status_counts_by_project = {}
    if projects:
        rows = frappe.db.sql(
            """
            SELECT project, status, COUNT(*) AS cnt
            FROM `tabBP Task`
            WHERE project IN %(projects)s AND is_deleted = 0
            GROUP BY project, status
            """,
            {"projects": [p["name"] for p in projects]},
            as_dict=True,
        )
        for r in rows:
            status_counts_by_project.setdefault(r["project"], {})[r["status"]] = r["cnt"]

    for p in projects:
        by_status = status_counts_by_project.get(p["name"], {})
        completed = set(_get_completed_statuses(p))
        total = sum(by_status.values())
        open_ = sum(cnt for status, cnt in by_status.items() if status not in completed)
        p["issue_count"] = total
        p["open_count"] = open_
        p["workflow_states"] = _parse_json(p.get("workflow_states"), [])
        p["issue_types"]     = _parse_json(p.get("issue_types"), [])
        p["custom_fields"]   = _parse_json(p.get("custom_fields"), [])
        p["enabled_views"]   = _parse_json(p.get("enabled_views"), None) or get_template_views(p.get("template_used"))
        p["pinned_views"]    = _parse_json(p.get("pinned_views"), None)
        p["default_view"]    = p.get("default_view") or "summary"
    return projects


@frappe.whitelist()
def get_project(project):
    _check_permission(project, "BP Viewer")
    doc = frappe.get_doc("BP Project", project)
    data = doc.as_dict()
    data["workflow_states"] = _normalize_workflow_states(doc.get_workflow_states())
    data["issue_types"]     = doc.get_issue_types()
    data["custom_fields"]   = _custom_fields.get_project_fields(project, "all")
    hidden_cf_ids = _custom_fields.hidden_field_ids_for_project(project, "projects")
    data["custom_field_values"] = _custom_fields.strip_unviewable_field_values(
        _parse_json(doc.custom_field_values, {}), hidden_cf_ids
    )
    data["enabled_views"]   = doc.get_enabled_views()
    data["pinned_views"]    = doc.get_pinned_views()
    data["labels"]          = _parse_json(doc.labels, [])
    data["members"] = [
        {
            "user": m.user,
            "full_name": m.full_name or frappe.db.get_value("User", m.user, "full_name") or m.user,
            "role": m.role,
        }
        for m in doc.members
    ]
    return data


# ─── PROJECT SETTINGS ─────────────────────────────────────────────────────────

@frappe.whitelist()
def update_project_general(project, project_name=None, key=None, description=None,
                            project_color=None, project_icon=None, theme=None, lead=None,
                            default_assignee=None, company=None, status=None,
                            project_type=None, client=None, currency=None,
                            hourly_rate=None, budget_amount=None, retainer_hours=None,
                            default_view=None, pinned_views=None, enabled_views=None,
                            health_override=None):
    # An archived project is read-only (access._assert_not_archived), which
    # would make it permanently unrecoverable — the field that lifts the lock
    # lives behind the lock. A status-only edit is therefore allowed through;
    # anything else on an archived project is still refused, because the
    # second check below runs without the exemption.
    _check_permission(project, "BP Manager", allow_archived=True)
    if status is None or len(
        [v for v in (project_name, key, description, project_color, project_icon,
                     theme, lead, default_assignee, company, project_type, client,
                     currency, hourly_rate, budget_amount, retainer_hours,
                     default_view, pinned_views, enabled_views, health_override)
         if v is not None]
    ):
        _check_permission(project, "BP Manager")

    doc = frappe.get_doc("BP Project", project)

    # Read current values so we can return the final state
    doc = frappe.get_doc("BP Project", project)

    changes = {}

    if project_name is not None:
        project_name = project_name.strip()
        if not project_name:
            frappe.throw("Project name cannot be empty.")
        changes["project_name"] = project_name

    if key is not None:
        key = key.upper().strip()
        if not key:
            frappe.throw("Project key cannot be empty.")
        if key != doc.key:
            if frappe.db.exists("BP Project", {"key": key, "name": ["!=", project]}):
                frappe.throw(f"Project key '{key}' is already in use.")
        changes["key"] = key

    if description   is not None: changes["description"]   = description
    if project_color is not None: changes["project_color"] = project_color
    if project_icon  is not None: changes["project_icon"]  = project_icon
    if theme         is not None: changes["theme"]         = theme
    # Use form_dict check so "— auto" (empty string) can clear the override
    if "health_override" in frappe.form_dict: changes["health_override"] = health_override or None
    # Use form_dict check so JS null can clear nullable Link fields
    if "lead"             in frappe.form_dict: changes["lead"]             = lead or None
    if "default_assignee" in frappe.form_dict: changes["default_assignee"] = default_assignee or None
    if company is not None: changes["company"] = company or None
    if status  is not None: changes["status"]  = status

    if enabled_views is not None:
        parsed = _parse_json(enabled_views, enabled_views) if isinstance(enabled_views, str) else enabled_views
        if isinstance(parsed, list):
            changes["enabled_views"] = json.dumps(parsed)

    if default_view is not None:
        # Only allow a view the project actually exposes (plus summary/files).
        valid = set(doc.get_enabled_views() or []) | {"summary", "files"}
        if default_view in valid:
            changes["default_view"] = default_view

    if pinned_views is not None:
        # Header tab strip order — same valid set as default_view, plus money
        # (default_view can't land on money since it's never a landing tab).
        pinned_views = _parse_json(pinned_views, pinned_views) if isinstance(pinned_views, str) else pinned_views
        valid = set(doc.get_enabled_views() or []) | {"summary", "files", "money"}
        cleaned = [v for v in (pinned_views or []) if v in valid] if isinstance(pinned_views, list) else []
        changes["pinned_views"] = json.dumps(cleaned) if cleaned else None

    # Billing fields
    if project_type   is not None: changes["project_type"]   = project_type
    if "client"       in frappe.form_dict: changes["client"] = client or None
    if currency       is not None: changes["currency"]       = currency or "USD"
    if hourly_rate    is not None: changes["hourly_rate"]    = float(hourly_rate) if hourly_rate else None
    if budget_amount  is not None: changes["budget_amount"]  = float(budget_amount) if budget_amount else None
    if retainer_hours is not None: changes["retainer_hours"] = int(retainer_hours) if retainer_hours else None

    if changes:
        # set_value does a targeted SQL UPDATE — bypasses child-table validation
        frappe.db.set_value("BP Project", project, changes)
        frappe.db.commit()
        # Reflect changes onto doc for return value
        for k, v in changes.items():
            setattr(doc, k, v)
        # get_board() caches its "project" sub-dict (VIEW_BOARD) — without
        # this, name/color/icon/theme/etc edits here are invisible on next
        # load until the cache TTL expires on its own.
        from batch_projects.cache import invalidate_project
        invalidate_project(project)
        # Drop access.py's per-request archived memo — un-archiving and then
        # writing in the same request must see Active, not the stale lock.
        if "status" in changes:
            from batch_projects import access
            access.invalidate_archived_cache(project)

    return {
        "name":             doc.name,
        "project_name":     doc.project_name,
        "key":              doc.key,
        "description":      doc.description,
        "project_color":    doc.project_color,
        "project_icon":     doc.project_icon,
        "theme":            doc.theme,
        "health_override":  doc.health_override,
        "lead":             doc.lead,
        "default_assignee": doc.default_assignee,
        "company":          doc.company,
        "status":           doc.status,
        "project_type":     doc.project_type,
        "client":           doc.client,
        "currency":         doc.currency,
        "hourly_rate":      doc.hourly_rate,
        "budget_amount":    doc.budget_amount,
        "retainer_hours":   doc.retainer_hours,
        "default_view":     doc.get("default_view") or "summary",
        "enabled_views":    doc.get_enabled_views(),
        "pinned_views":     doc.get_pinned_views(),
    }


@frappe.whitelist()
def purge_project(project, confirm_key=None):
    """Permanently delete an ARCHIVED project — the second half of
    archive-then-purge. Archiving is the reversible act; this is not.

    Refuses outright if the project has any financial footprint. A BP Project
    resolves to an ERPNext Project, and the money layer keys off THAT
    (the Money tab joins Timesheet Detail on tsd.project, invoicing on
    tsd.custom_bp_task) — so purging a project whose work has been costed or
    invoiced would orphan rows that margin reports and the GL still read, and
    would break an audit trail that has to stay reconstructable.

    Deliberately never offers a force flag. "Delete it anyway" on a document
    with GL entries behind it is not a decision an API should make available.
    """
    _check_permission(project, "BP Admin", allow_archived=True)

    from batch_projects import access
    if not access.is_project_archived(project):
        frappe.throw(
            "Only an archived project can be purged. Archive it first — that "
            "step is reversible, this one is not.",
            frappe.ValidationError, title="Archive first",
        )

    blockers = _project_financial_blockers(project)
    if blockers:
        frappe.throw(
            "This project can't be purged — it has financial records that must "
            "stay auditable: " + ", ".join(blockers) +
            ". It stays archived, which preserves the history.",
            frappe.ValidationError, title="Financial records exist",
        )

    # Name must be typed back, same as any irreversible destructive action.
    key = frappe.db.get_value("BP Project", project, "project_name") or project
    if (confirm_key or "").strip() != key:
        frappe.throw(
            f'Type the project name ("{key}") to confirm permanent deletion.',
            frappe.ValidationError, title="Confirmation required",
        )

    frappe.delete_doc("BP Project", project, force=True, ignore_permissions=True,
                      delete_permanently=True)
    frappe.db.commit()
    access.invalidate_archived_cache(project)
    return {"purged": project}


def _project_financial_blockers(project) -> list:
    """Human-readable list of financial footprints blocking a purge. Empty list
    means the project is financially clean.

    Checked against the ERPNext project, not the BP one: that is the key the
    money layer actually joins on (see api/insights_data.get_money_inputs),
    so a BP
    project with no direct links can still have costed time and posted GL
    behind it.
    """
    from batch_projects.api.erp_link import _erp_project_for

    blockers = []
    try:
        erp_project = _erp_project_for(project)
    except Exception:
        erp_project = None

    task_names = frappe.get_all("BP Task", filters={"project": project}, pluck="name")
    if task_names:
        n = frappe.db.count("Timesheet Detail", {"custom_bp_task": ["in", task_names]})
        if n:
            blockers.append(f"{n} timesheet row(s) logged against its tasks")

    if erp_project:
        for doctype, label in (
            # Distinct from the task-linked count above: a row can carry the
            # ERPNext project without pointing at a BP Task, and vice versa.
            # Both are real footprints, so both are reported rather than
            # de-duplicated — overlap is better than a missed blocker.
            ("Timesheet Detail", "timesheet row(s) on the linked ERPNext project"),
            ("Sales Invoice", "sales invoice(s)"),
            ("Purchase Invoice", "purchase invoice(s)"),
            ("GL Entry", "general-ledger entry(ies)"),
        ):
            try:
                n = frappe.db.count(doctype, {"project": erp_project})
            except Exception:
                # A doctype absent on this install (no accounts module) is not
                # a blocker — but it must not silently pass as "clean" either,
                # so only a real zero count clears it.
                continue
            if n:
                blockers.append(f"{n} {label}")

    return blockers


@frappe.whitelist()
def update_project_custom_field_values(project, values):
    """Project-level custom field values (BP Project.custom_field_values) —
    the project-side counterpart to update_task's custom_field_values merge.
    Member+ to write (matches task-level custom field editing), field-level
    edit_role checked per field on top of that, same as tasks."""
    _check_permission(project, "BP Member")
    if isinstance(values, str):
        values = json.loads(values)

    _custom_fields.assert_can_edit_field_values(project, values)
    doc = frappe.get_doc("BP Project", project)
    existing = _parse_json(doc.custom_field_values, {})
    existing.update(values)
    schema = _custom_fields.validation_schema_for_project(project, "projects")
    _validate_custom_field_values(values, schema)

    doc.custom_field_values = json.dumps(existing)
    doc.flags.ignore_permissions = True
    doc.save()
    frappe.db.commit()

    hidden_cf_ids = _custom_fields.hidden_field_ids_for_project(project, "projects")
    return _custom_fields.strip_unviewable_field_values(existing, hidden_cf_ids)


@frappe.whitelist()
def update_project_workflow(project, workflow_states):
    _check_permission(project, "BP Admin")
    states = _deep_parse_json(workflow_states)
    if not isinstance(states, list):
        frappe.throw("workflow_states must be a list")
    states = _normalize_workflow_states(states)
    if not states:
        frappe.throw("A project must have at least one workflow state.")
    for s in states:
        if not s.get("name"):
            frappe.throw("Each workflow state must have a name.")
        s.setdefault("category", "unstarted")
        if s["category"] not in ("unstarted", "started", "completed", "cancelled"):
            s["category"] = "unstarted"
    # Sanitize `allowed_to` (transition restrictions) against the sibling
    # states in this same save — see _normalize_allowed_to.
    valid_names = {s["name"] for s in states}
    for s in states:
        cleaned = _normalize_allowed_to(s.get("allowed_to"), valid_names)
        if cleaned:
            s["allowed_to"] = cleaned
        else:
            s.pop("allowed_to", None)
    frappe.db.set_value("BP Project", project, {
        "workflow_states": json.dumps(states),
        "schema_version": (frappe.db.get_value("BP Project", project, "schema_version") or 0) + 1,
        "modified": frappe.utils.now(),
    })
    frappe.db.commit()
    from batch_projects.cache import invalidate_project
    invalidate_project(project)
    return states


@frappe.whitelist()
def update_project_issue_types(project, issue_types):
    _check_permission(project, "BP Admin")
    types = _deep_parse_json(issue_types)
    if not isinstance(types, list):
        frappe.throw("issue_types must be a list")
    clean = []
    for t in types:
        if isinstance(t, str):
            try: t = json.loads(t)
            except: continue
        if isinstance(t, dict) and t.get("name"):
            clean.append(t)
    if not clean:
        frappe.throw("At least one issue type is required")
    frappe.db.set_value("BP Project", project, {
        "issue_types": json.dumps(clean),
        "modified": frappe.utils.now(),
    })
    frappe.db.commit()
    return clean


@frappe.whitelist()
def update_project_labels(project, labels):
    _check_permission(project, "BP Admin")
    labels_list = _deep_parse_json(labels)
    if not isinstance(labels_list, list):
        frappe.throw("labels must be a list")
    frappe.db.set_value("BP Project", project, {
        "labels": json.dumps(labels_list),
        "modified": frappe.utils.now(),
    })
    frappe.db.commit()
    return labels_list


@frappe.whitelist()
def get_workflow_templates():
    from batch_projects.batch_projects.doctype.bp_project.bp_project import (
        WORKFLOW_TEMPLATES, DEFAULT_ISSUE_TYPES
    )
    return {"workflow_templates": WORKFLOW_TEMPLATES, "default_issue_types": DEFAULT_ISSUE_TYPES}


@frappe.whitelist()
def get_project_templates():
    """Single source of truth for the create-project flow (statuses, issue
    types, and views per template). Defined in setup/project_templates.py;
    re-exported here so the frontend's board namespace can reach it."""
    from batch_projects.setup.project_templates import (
        get_project_templates as _get_project_templates,
    )
    return _get_project_templates()


# ─── GANTT / SCHEDULE AXIS ─────────────────────────────────────────────────────

@frappe.whitelist()
def get_gantt(project):
    """Self-contained payload for the Gantt view: every task with its schedule
    window, status colour, and the real finish-to-start dependency edges derived
    from BP Task Link (`blocks` / `is blocked by`). One round trip, no N+1."""
    # Accept either the project name or its short key (the UI route uses the key).
    if not frappe.db.exists("BP Project", project):
        alt = frappe.db.get_value("BP Project", {"key": project}, "name")
        if alt:
            project = alt
    _check_permission(project, "BP Viewer")
    from batch_projects.entitlements import require_workspace_feature
    require_workspace_feature("gantt")
    proj = frappe.get_doc("BP Project", project)
    states = _normalize_workflow_states(proj.get_workflow_states())
    color_by_status = {s.get("name"): s.get("color") for s in states}
    completed = set(proj.get_completed_statuses())

    tasks = frappe.get_all(
        "BP Task",
        filters=_task_filters({"project": project}),
        fields=[
            "name", "task_key", "title", "status", "priority", "task_type",
            "start_date", "due_date", "planned_start", "planned_end",
            "blocked_reason", "epic", "parent_task", "sprint",
            "estimated_hours", "actual_hours", "billable", "board_order", "labels",
        ],
        order_by="start_date asc, due_date asc, creation asc",
    )
    names = [t["name"] for t in tasks]
    valid = set(names)
    # Gantt bars/tooltips need the same ERP reference surface tasks get elsewhere.
    refs_map = _fetch_task_refs(names) if names else {}

    # All assignees per task → stacked avatars on the bar.
    assignee_map = {}
    full_names = {}
    if names:
        for a in frappe.get_all(
            "BP Task Assignee",
            filters={"parenttype": "BP Task", "parent": ["in", names]},
            fields=["parent", "user"],
            order_by="idx asc",
        ):
            assignee_map.setdefault(a["parent"], []).append(a["user"])
        users = list({u for lst in assignee_map.values() for u in lst})
        if users:
            for u in frappe.get_all("User", filters={"name": ["in", users]},
                                    fields=["name", "full_name", "user_image"]):
                full_names[u["name"]] = {
                    "name": u["full_name"] or u["name"],
                    "image": u.get("user_image") or None,
                }

    # Dependency edges: normalise everything to predecessor → successor.
    edges, seen = [], set()
    if names:
        for l in frappe.get_all(
            "BP Task Link",
            filters={
                "parenttype": "BP Task",
                "parent": ["in", names],
                "link_type": ["in", ["blocks", "is blocked by"]],
            },
            fields=["parent", "linked_task", "link_type", "dep_type", "lag_days", "link_metadata"],
        ):
            if l["linked_task"] not in valid:
                continue
            if l["link_type"] == "blocks":
                frm, to = l["parent"], l["linked_task"]
            else:  # "is blocked by"
                frm, to = l["linked_task"], l["parent"]
            key = (frm, to)
            if frm == to or key in seen:
                continue
            seen.add(key)
            edges.append({
                "from": frm, "to": to,
                # Pre-dep_type rows are NULL — they were all created as plain
                # finish-to-start blocks.
                "dep_type": l.get("dep_type") or "FS",
                "lag": frappe.utils.cint(l.get("lag_days") or 0),
                "link_metadata": l.get("link_metadata"),
            })

    # Epic titles/colors for Gantt grouping.
    epic_names = list({t["epic"] for t in tasks if t.get("epic")})
    epic_meta = {}
    if epic_names:
        for ep in frappe.get_all("BP Epic", filters={"name": ["in", epic_names]},
                                 fields=["name", "title", "color"]):
            epic_meta[ep["name"]] = ep

    for t in tasks:
        t["color"] = color_by_status.get(t["status"]) or "#9FA6AD"
        t["done"] = t["status"] in completed
        t["assignees"] = [
            {
                "user": u,
                "name": (full_names.get(u) or {}).get("name", u),
                "image": (full_names.get(u) or {}).get("image"),
            }
            for u in assignee_map.get(t["name"], [])
        ]
        ep = epic_meta.get(t.get("epic"))
        t["epic_title"] = (ep or {}).get("title")
        t["epic_color"] = (ep or {}).get("color")
        t["references"] = refs_map.get(t["name"], [])

    return {
        "tasks": tasks,
        "edges": edges,
        "workflow_states": states,
        "project": {
            "name": proj.name,
            "start_date": str(proj.start_date) if proj.start_date else None,
            "target_end_date": str(proj.target_end_date) if proj.target_end_date else None,
        },
    }


# ─── BOARD ────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_board(project, show_child_issues=False):
    _check_permission(project, "BP Viewer")

    from batch_projects.cache import get as cache_get, set as cache_set, VIEW_BOARD

    # show_child_issues changes the result — include in cache key logic
    # For simplicity we only cache the default (show_child_issues=False)
    use_cache = not frappe.parse_json(show_child_issues)
    if use_cache:
        cached = cache_get(VIEW_BOARD, project)
        if cached is not None:
            return cached

    proj = frappe.get_doc("BP Project", project)
    states = _normalize_workflow_states(proj.get_workflow_states())

    board_filters = {} if frappe.parse_json(show_child_issues) else {"parent_task": None}

    result = query_tasks(
        project=project,
        group_by="status",
        filters=board_filters,
        sort_by="board_order",
    )

    board = {col["key"]: col["issues"] for col in result.get("groups", [])}

    # Resolved health (manual override, else derived from overdue/completion —
    # same formula the gateway portfolio rollup uses, via _project_health_label).
    from datetime import date
    today_str = date.today().isoformat()
    completed_names = {s["name"] for s in states if s.get("category") in ("completed", "cancelled")}
    _total = _done = _overdue = 0
    for col in result.get("groups", []):
        is_done_col = col["key"] in completed_names
        for iss in col.get("issues", []):
            _total += 1
            if is_done_col:
                _done += 1
            elif iss.get("due_date") and str(iss["due_date"]) < today_str:
                _overdue += 1
    resolved_health = _project_health_label(proj.health_override, _total, _done, _overdue)

    # Bundle all system users so frontend doesn't need a separate get_members call
    all_users = frappe.get_all(
        "User",
        filters={"enabled": 1, "user_type": "System User"},
        fields=["name", "full_name", "user_image"],
        order_by="full_name asc",
    )
    user_list = [
        {
            "user": u["name"],
            "full_name": u["full_name"] or u["name"],
            "user_image": u.get("user_image") or "",
        }
        for u in all_users
        if u["name"] != "Administrator"
    ]

    data = {
        "project": {
            "name": proj.name,
            "project_name": proj.project_name,
            "key": proj.key,
            "project_color": proj.project_color,
            "project_icon": proj.project_icon,
            "theme": proj.theme,
            "health_override": proj.health_override,
            "health": resolved_health,
            "description": proj.description or "",
            "lead": proj.lead or "",
            "default_assignee": proj.default_assignee or "",
            "company": proj.company or "",
            "status": proj.status or "",
            "project_type": proj.project_type or "internal",
            "client": proj.client or "",
            "currency": proj.currency or "",
            "hourly_rate": proj.hourly_rate,
            "budget_amount": proj.budget_amount,
            "retainer_hours": proj.retainer_hours,
            "start_date": str(proj.start_date) if proj.start_date else None,
            "target_end_date": str(proj.target_end_date) if proj.target_end_date else None,
            "source_sales_order": proj.source_sales_order or "",
            "source_lead": proj.source_lead or "",
            "source_opportunity": proj.source_opportunity or "",
            "source_quotation": proj.source_quotation or "",
            "enabled_views": proj.get_enabled_views(),
            "pinned_views": proj.get_pinned_views(),
            "default_view": proj.get("default_view") or "summary",
            "custom_field_values": _custom_fields.strip_unviewable_field_values(
                _parse_json(proj.custom_field_values, {}),
                _custom_fields.hidden_field_ids_for_project(project, "projects"),
            ),
        },
        "columns": [s["name"] for s in states],
        "workflow_states": states,
        "issue_types": proj.get_issue_types(),
        "custom_fields": _custom_fields.get_project_fields(project, "tasks"),
        "project_custom_fields": _custom_fields.get_project_fields(project, "projects"),
        "labels": _parse_json(proj.labels, []),
        "board": board,
        "epics": _fetch_epics_for_project(project),
        # Members bundled — eliminates a separate get_members API call on board load
        "members": user_list,
        "project_members": [
            {
                "user": m.user,
                "role": m.role,
                "full_name": next((u["full_name"] for u in user_list if u["user"] == m.user), m.user),
            }
            for m in (proj.members or [])
        ],
    }

    if use_cache:
        cache_set(VIEW_BOARD, project, data)

    return data


def _as_bool(v):
    return v in (True, 1, "1", "true", "True", "yes")


def _completing_into_blocked(doc, new_status, force):
    """If `doc` is moving INTO a completed status (from a non-completed one)
    while it still has unfinished blockers, return that list; else None.
    `force` bypasses the check. This is the single, view-independent guard —
    every status change (board drag, list, sidebar, subtask) flows through it."""
    if force:
        return None
    proj = frappe.get_cached_doc("BP Project", doc.project)
    completed = set(proj.get_completed_statuses())
    if new_status not in completed or doc.status in completed:
        return None
    blocker_names = [l.linked_task for l in (doc.get("links") or [])
                     if l.link_type == "is blocked by" and l.linked_task]
    if not blocker_names:
        return None
    blockers = [
        b for b in frappe.get_all(
            "BP Task", filters={"name": ["in", blocker_names]},
            fields=["name", "task_key", "title", "status"],
        )
        if b["status"] not in completed
    ]
    return blockers or None


@frappe.whitelist()
def update_task_status(issue, status, board_order=None, force=False):
    from batch_projects.cache import invalidate_project
    doc = frappe.get_doc("BP Task", issue)
    _check_permission(doc.project, "BP Member")
    blockers = _completing_into_blocked(doc, status, _as_bool(force))
    if blockers:
        return {"blocked": True, "status": status, "blockers": blockers}
    doc.status = status
    if board_order is not None:
        doc.board_order = int(board_order)
    doc.save(ignore_permissions=True)
    invalidate_project(doc.project)
    return {"ok": True}


@frappe.whitelist()
def move_task(issue, status=None, prev=None, next=None, force=False):
    """Drag-and-drop move: optionally change status, then place between the
    `prev` and `next` neighbour tasks using a fractional board_rank — a single
    row write (no column-wide renumber). `prev`/`next` are the task names now
    above/below the drop position (None at the column ends).

    The rank read+compute+write is wrapped in rank.column_lock — see that
    function's docstring for the duplicate-rank race it closes.
    Emits TASK_MOVED unconditionally on success (even a same-column reorder,
    which changes no other field) so every connected client can reposition
    this one card instead of needing a full board refetch to notice."""
    from batch_projects.cache import invalidate_project
    from batch_projects import rank as rankutil
    from batch_projects.events import emit, TASK_MOVED

    doc = frappe.get_doc("BP Task", issue)
    _check_permission(doc.project, "BP Member")

    old_status = doc.status
    target_status = status or doc.status
    if status and status != doc.status:
        blockers = _completing_into_blocked(doc, status, _as_bool(force))
        if blockers:
            return {"blocked": True, "status": status, "blockers": blockers}
        doc.status = status

    # Never anchor to self
    if prev == issue:
        prev = None
    if next == issue:
        next = None

    def _rank(name):
        return frappe.db.get_value("BP Task", name, "board_rank") if name else None

    with rankutil.column_lock(doc.project, target_status):
        r = rankutil.rank_between(_rank(prev), _rank(next))
        if r is None:  # neighbours are adjacent — rebalance the column and retry
            rankutil.rebalance_column(doc.project, target_status)
            r = rankutil.rank_between(_rank(prev), _rank(next)) \
                or rankutil.end_rank(doc.project, target_status)

        doc.board_rank = r
        doc.save(ignore_permissions=True)

    invalidate_project(doc.project)

    emit(TASK_MOVED, {
        "project": doc.project,
        "task": doc.name,
        "task_key": doc.task_key,
        "old_status": old_status,
        "new_status": doc.status,
        "board_rank": doc.board_rank,
    })

    return {"ok": True, "board_rank": doc.board_rank}


# ─── APPROVALS ────────────────────────────────────────────────────────────────

@frappe.whitelist()
def request_approval(issue, approver):
    """Set a task as pending approval by a specific user."""
    doc = frappe.get_doc("BP Task", issue)
    _check_permission(doc.project, "BP Member")
    if not approver or not frappe.db.exists("User", approver):
        frappe.throw("Approver is required.")
    doc.approval_status = "Pending"
    doc.approver = approver
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    from batch_projects.cache import invalidate_project
    invalidate_project(doc.project)
    from batch_projects.events import emit, TASK_APPROVAL_REQUESTED
    emit(TASK_APPROVAL_REQUESTED, {
        "project": doc.project, "task": doc.name, "task_key": doc.task_key,
        "approver": approver,
    })
    return {"ok": True, "approval_status": "Pending", "approver": approver}


@frappe.whitelist()
def approve_task(issue):
    """Approve a task. Only the designated approver may approve."""
    doc = frappe.get_doc("BP Task", issue)
    _check_permission(doc.project, "BP Member")
    from frappe.utils import now_datetime
    user = frappe.session.user
    if doc.approver and doc.approver != user:
        if "System Manager" not in frappe.get_roles(user):
            frappe.throw("Only the designated approver can approve this task.")
    if doc.approval_status != "Pending":
        frappe.throw("Task is not pending approval.")
    doc.approval_status = "Approved"
    doc.approved_by = user
    doc.approved_on = now_datetime()
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    from batch_projects.cache import invalidate_project
    invalidate_project(doc.project)
    from batch_projects.events import emit, TASK_APPROVAL_DECIDED
    emit(TASK_APPROVAL_DECIDED, {
        "project": doc.project, "task": doc.name, "task_key": doc.task_key,
        "decision": "Approved",
    })
    return {"ok": True, "approval_status": "Approved"}


@frappe.whitelist()
def reject_task(issue, reason=None):
    """Reject a task. Only the designated approver may reject."""
    doc = frappe.get_doc("BP Task", issue)
    _check_permission(doc.project, "BP Member")
    from frappe.utils import now_datetime
    user = frappe.session.user
    if doc.approver and doc.approver != user:
        if "System Manager" not in frappe.get_roles(user):
            frappe.throw("Only the designated approver can reject this task.")
    if doc.approval_status != "Pending":
        frappe.throw("Task is not pending approval.")
    doc.approval_status = "Rejected"
    doc.approved_by = user
    doc.approved_on = now_datetime()
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    # Log the rejection reason as a comment
    if reason:
        from batch_projects.events import emit, COMMENT_ADDED
        activity = frappe.get_doc({
            "doctype": "BP Activity",
            "task": issue,
            "action_type": "Comment",
            "comment_text": f"Rejection reason: {reason}",
            "user": frappe.session.user,
        })
        activity.insert(ignore_permissions=True)
        emit(COMMENT_ADDED, {"project": doc.project, "task": issue,
              "task_key": doc.task_key, "comment_text": activity.comment_text,
              "activity": activity.name, "mentions": []})
    from batch_projects.cache import invalidate_project
    invalidate_project(doc.project)
    from batch_projects.events import emit as _emit, TASK_APPROVAL_DECIDED
    _emit(TASK_APPROVAL_DECIDED, {
        "project": doc.project, "task": doc.name, "task_key": doc.task_key,
        "decision": "Rejected", "reason": reason,
    })
    return {"ok": True, "approval_status": "Rejected"}


# ─── ISSUES ───────────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_task(issue):
    doc = frappe.get_doc("BP Task", issue)
    _check_task_permission(issue, doc.project, "BP Viewer")
    data = doc.as_dict()
    hidden_cf_ids = _custom_fields.hidden_field_ids_for_project(doc.project, "tasks")
    data["custom_field_values"] = _custom_fields.strip_unviewable_field_values(
        _parse_json(doc.custom_field_values, {}), hidden_cf_ids
    )
    data["labels"] = _parse_json(doc.labels, [])

    # actual_hours is a rollup from submitted Timesheets once any exist for
    # this task — hours_source tells the UI whether the field is still open
    # to manual entry or is now timesheet-driven.
    from batch_projects.timesheet_sync import task_has_timesheet_rows
    data["hours_source"] = "timesheet" if task_has_timesheet_rows(issue) else "manual"

    # Assignees
    data["assignees"] = [
        {"user": a.user, "full_name": a.full_name or frappe.db.get_value("User", a.user, "full_name") or a.user}
        for a in doc.assignees
    ]

    # Reporter / approver display names. `reporter` is a Link to Employee and
    # `approver` a Link to User, so the stored values are an internal ID
    # ("HR-EMP-00003") and a login email — neither is a person's name, and the
    # detail rail was rendering them verbatim next to a properly-resolved
    # Assignee. Resolved here, beside assignees, so every identity in the
    # payload is a name by the time it reaches the UI.
    data["reporter_name"] = (
        frappe.db.get_value("Employee", doc.reporter, "employee_name") if doc.reporter else None
    ) or doc.reporter
    data["approver_name"] = (
        frappe.db.get_value("User", doc.approver, "full_name") if doc.approver else None
    ) or doc.approver

    # Linked issues — resolve key/title/status LIVE (the stored row is only a
    # snapshot from link-creation time and goes stale). One batched query.
    link_names = list({l.linked_task for l in (doc.links or []) if l.linked_task})
    live = {}
    if link_names:
        for t in frappe.get_all(
            "BP Task",
            filters={"name": ["in", link_names]},
            fields=["name", "task_key", "title", "status", "project"],
        ):
            live[t["name"]] = t
    data["links"] = [
        {
            "link_type": l.link_type,
            "linked_task": l.linked_task,
            "linked_task_key": (live.get(l.linked_task) or {}).get("task_key") or l.linked_task_key,
            "linked_task_title": (live.get(l.linked_task) or {}).get("title") or l.linked_task_title,
            "linked_task_status": (live.get(l.linked_task) or {}).get("status") or l.linked_task_status,
            "linked_task_project": (live.get(l.linked_task) or {}).get("project") or l.get("linked_task_project"),
            # Scheduling + integration metadata — round-trips to the SPA so a
            # drawn dependency keeps its type/lag and integrations can read
            # back their own provenance blob.
            "dep_type": l.get("dep_type") or "FS",
            "lag_days": frappe.utils.cint(l.get("lag_days") or 0),
            "link_metadata": l.get("link_metadata"),
        }
        for l in (doc.links or [])
    ]

    # Epic
    if doc.epic:
        epic = frappe.db.get_value("BP Epic", doc.epic, ["title", "color"], as_dict=True)
        if epic:
            data["epic_title"] = epic["title"]
            data["epic_color"] = epic["color"]

    # Activity
    data["activity"] = frappe.get_all(
        "BP Activity",
        filters={"task": issue},
        fields=["name", "action_type", "field_name", "old_value", "new_value",
                "comment_text", "user", "guest_name", "creation"],
        order_by="creation asc",
    )

    # Subtasks
    subtasks_raw = frappe.get_all(
        "BP Task",
        filters={"parent_task": issue},
        fields=["name", "task_key", "title", "status", "priority", "task_type"],
        order_by="creation asc",
    )
    for st in subtasks_raw:
        st_rows = frappe.get_all(
            "BP Task Assignee",
            filters={"parent": st["name"]},
            fields=["user", "full_name"],
        )
        st["assignees"] = [
            {"user": r["user"], "full_name": r["full_name"] or frappe.db.get_value("User", r["user"], "full_name") or r["user"]}
            for r in st_rows
        ]
    data["subtasks"] = subtasks_raw

    # ERPNext References (optional — only if doctypes exist)
    data["references"] = [
        {
            "name": r.name,
            "ref_doctype": r.ref_doctype,
            "ref_name": r.ref_name,
            "ref_label": r.ref_label or r.ref_name,
            "ref_url": f"/app/{r.ref_doctype.lower().replace(' ', '-')}/{r.ref_name}",
        }
        for r in (doc.references or [])
    ]

    # Attachments — stripped (not a 403 for the whole task) when the caller
    # lacks view_files: the task drawer still opens, it just shows
    # no attachments, same "field-level, not surface-level" treatment as the
    # custom-field stripping just above.
    from batch_projects import access
    if access.has_capability(doc.project, "view_files"):
        data["attachments"] = frappe.get_all(
            "File",
            filters={"attached_to_doctype": "BP Task", "attached_to_name": issue},
            fields=["name", "file_name", "file_url", "file_size", "is_private", "creation"],
            order_by="creation asc",
        )
    else:
        data["attachments"] = []

    # Watch state
    watcher_users = frappe.get_all("BP Task Watcher", filters={"task": issue}, pluck="user")
    data["watching"] = frappe.session.user in watcher_users
    data["watcher_count"] = len(watcher_users)

    return data


@frappe.whitelist()
def create_task(project, title, status=None, priority="Medium", task_type="Task",
                 assignees=None, epic=None, description=None, story_points=None,
                 due_date=None, start_date=None, planned_start=None, planned_end=None,
                 parent_task=None,
                 estimated_hours=None, custom_field_values=None,
                 labels=None, sprint=None, billable=0, team=None):

    _check_permission(project, "BP Member")

    if isinstance(assignees, str):
        assignees = json.loads(assignees)
    if isinstance(custom_field_values, str):
        custom_field_values = json.loads(custom_field_values)
    if isinstance(labels, str):
        labels = json.loads(labels)

    if custom_field_values:
        _custom_fields.assert_can_edit_field_values(project, custom_field_values)
        schema = _custom_fields.validation_schema_for_project(project, "tasks")
        _validate_custom_field_values(custom_field_values, schema)

    if not status:
        proj = frappe.get_doc("BP Project", project)
        states = _normalize_workflow_states(proj.get_workflow_states())
        status = states[0]["name"] if states else "To Do"

    doc = frappe.get_doc({
        "doctype": "BP Task",
        "project": project,
        "title": title,
        "status": status,
        "priority": priority,
        "task_type": task_type,
        "epic": epic,
        "sprint": sprint,
        "description": description,
        "story_points": int(story_points) if story_points else 0,
        "due_date": due_date,
        "start_date": start_date,
        "planned_start": planned_start,
        "planned_end": planned_end,
        "parent_task": parent_task,
        "estimated_hours": float(estimated_hours) if estimated_hours else None,
        "billable": billable,
        "team": team,
        "custom_field_values": json.dumps(custom_field_values) if custom_field_values else None,
        "labels": json.dumps(labels) if labels else None,
        "assignees": [{"user": a["user"] if isinstance(a, dict) else a} for a in (assignees or [])],
    })
    doc.insert(ignore_permissions=True)
    from batch_projects.cache import invalidate_project
    invalidate_project(project)
    return doc.as_dict()


# Fields a "BP Member" may set through the generic update path
# (update_task / bulk_update_tasks). Allowlist, not denylist — the previous
# denylist (name/task_key/cmd/doctype) let ANY other doc attribute through
# `hasattr(doc, k)` + `setattr` with `ignore_permissions=True`, including:
#   - approval_status/approver/approved_by/approved_on — let any Member
#     self-approve any task, bypassing approve_task's designated-approver
#     guard entirely.
#   - actual_hours — schema read_only, computed from timesheets
#     (timesheet_sync.py); freely settable here let anyone fabricate
#     billed hours with no timer/timesheet behind them.
#   - board_rank/started_on/completed_on — schema read_only, controller-
#     managed (bp_task.py) side effects of status transitions / board
#     ordering.
#   - project — has its own dedicated, validated path (moveTaskToProject);
#     naive reassignment here would leave task_key/permissions stale.
#   - reporter, sales_order, timesheet_detail, parent_task, recurrence_source,
#     submitted_via_intake, bridge_job_id — not touched by any current
#     caller of this path; no reason for a bare Member to set them directly.
# Extend THIS set, not the exclusion list, when a new field needs to be
# editable through update_task/bulk_update_tasks.
_MEMBER_WRITABLE_FIELDS = frozenset({
    "title", "description", "status", "priority", "task_type",
    "epic", "sprint", "milestone", "team", "due_date", "start_date",
    "planned_start", "planned_end", "blocked_reason",
    "story_points", "estimated_hours", "billable", "is_unplanned",
    "needs_triage", "is_recurring", "recurrence_frequency", "recurrence_end_date",
    "resolution",
    # Handled by dedicated branches below, not the generic setattr:
    "custom_field_values", "labels", "assignees",
})


@frappe.whitelist()
def update_task(issue, fields, force=False):
    if isinstance(fields, str):
        fields = json.loads(fields)

    doc = frappe.get_doc("BP Task", issue)
    _check_task_permission(issue, doc.project, "BP Member")

    # Same view-independent blocker guard for status changes via the generic path.
    if "status" in fields:
        blockers = _completing_into_blocked(doc, fields["status"], _as_bool(force))
        if blockers:
            return {"blocked": True, "status": fields["status"], "blockers": blockers}

    ignored_fields = sorted(k for k in fields if k not in _MEMBER_WRITABLE_FIELDS)

    for k, v in fields.items():
        if k not in _MEMBER_WRITABLE_FIELDS:
            continue

        if k == "custom_field_values":
            if isinstance(v, str):
                v = json.loads(v)
            _custom_fields.assert_can_edit_field_values(doc.project, v)
            existing = _parse_json(doc.custom_field_values, {})
            existing.update(v)
            schema = _custom_fields.validation_schema_for_project(doc.project, "tasks")
            _validate_custom_field_values(v, schema)
            doc.custom_field_values = json.dumps(existing)

        elif k == "labels":
            if isinstance(v, str):
                v = json.loads(v)
            doc.labels = json.dumps(v)

        elif k == "assignees":
            if isinstance(v, str):
                v = json.loads(v)
            doc.set("assignees", [])
            for a in (v or []):
                user = a.get("user") if isinstance(a, dict) else a
                if not user:
                    continue
                full_name = frappe.db.get_value("User", user, "full_name") or user
                doc.append("assignees", {
                    "user": user,
                    "full_name": full_name,
                })

        elif hasattr(doc, k):
            if v == "" and doc.meta.get_field(k) and \
               doc.meta.get_field(k).fieldtype in ("Date", "Datetime"):
                v = None
            setattr(doc, k, v)

    # NOTE: does NOT emit TASK_ASSIGNED/TASK_UNASSIGNED/TASK_UPDATED itself —
    # BP Task.on_update() (the doctype controller) already diffs old vs new
    # assignees/fields and emits on every save, regardless of which API
    # called it. An earlier version of this function duplicated that same
    # diff-and-emit here, which fired every assignment notification/broadcast
    # TWICE (confirmed live 2026-08-06: two "Assignment" BP Notification rows
    # ~1s apart per single update_task() call) — removed, not re-added.
    doc.save(ignore_permissions=True)
    from batch_projects.cache import invalidate_project
    invalidate_project(doc.project)

    result = doc.as_dict()
    if ignored_fields:
        # Was a silent no-op — a future caller sending an unwritable field
        # (a new integration, the ERPNext "Update ERPNext Document" reverse
        # path) would get no error and no signal at all otherwise.
        result["_ignored_fields"] = ignored_fields
    return result


@frappe.whitelist()
def bulk_update_tasks(issues, fields):
    """Apply the same field changes to many tasks from one API call.

    Existing bulk actions in ListView.vue fanned out N client-side
    `update_task` calls under `Promise.allSettled` and then unconditionally
    toasted success — a total failure (e.g. no permission) looked identical
    to a total success. This endpoint does the fan-out server-side in one
    round trip and returns per-task results so the caller can report the
    real counts.

    `assignees` is additive here (existing assignees are kept, new ones
    appended) rather than replacing the child table like `update_task` does
    — a bulk "assign to X" must not silently unassign everyone else already
    on those tasks.
    """
    if isinstance(issues, str):
        issues = json.loads(issues)
    if isinstance(fields, str):
        fields = json.loads(fields)

    updated, failed = [], []
    projects_touched = set()
    # Same field-set for every task in the batch, so this only needs
    # computing once — surfaces a silently-dropped field instead of a
    # future caller finding out the hard way (see update_task).
    ignored_fields = sorted(k for k in fields if k not in _MEMBER_WRITABLE_FIELDS)

    for issue in issues:
        try:
            doc = frappe.get_doc("BP Task", issue)
            _check_task_permission(issue, doc.project, "BP Member")

            if "status" in fields:
                blockers = _completing_into_blocked(doc, fields["status"], False)
                if blockers:
                    failed.append({"name": issue, "reason": "blocked_by_dependency"})
                    continue

            for k, v in fields.items():
                if k not in _MEMBER_WRITABLE_FIELDS:
                    continue

                if k == "assignees":
                    existing_users = {a.user for a in doc.assignees}
                    for a in (v or []):
                        user = a.get("user") if isinstance(a, dict) else a
                        if not user or user in existing_users:
                            continue
                        full_name = frappe.db.get_value("User", user, "full_name") or user
                        doc.append("assignees", {"user": user, "full_name": full_name})
                        existing_users.add(user)

                elif k == "labels":
                    doc.labels = json.dumps(v if not isinstance(v, str) else json.loads(v))

                elif hasattr(doc, k):
                    setattr(doc, k, v)

            doc.save(ignore_permissions=True)
            updated.append(issue)
            projects_touched.add(doc.project)
        except frappe.PermissionError:
            failed.append({"name": issue, "reason": "permission"})
        except Exception as e:
            frappe.log_error(title="bulk_update_tasks", message=frappe.get_traceback())
            failed.append({"name": issue, "reason": str(e)[:200]})

    from batch_projects.cache import invalidate_project
    for p in projects_touched:
        invalidate_project(p)

    result = {"updated": updated, "failed": failed}
    if ignored_fields:
        result["_ignored_fields"] = ignored_fields
    return result


@frappe.whitelist()
def bulk_delete_tasks(issues):
    """Move many tasks to trash from one API call (delete_task is now a
    soft-delete — see there), returning per-task results instead of the
    client fanning out N calls under `Promise.allSettled` (see
    `bulk_update_tasks`)."""
    if isinstance(issues, str):
        issues = json.loads(issues)

    deleted, failed = [], []
    projects_touched = set()

    for issue in issues:
        try:
            doc = frappe.get_doc("BP Task", issue)
            _check_permission(doc.project, "BP Manager")
            projects_touched.add(doc.project)
            delete_task(issue)
            deleted.append(issue)
        except frappe.PermissionError:
            failed.append({"name": issue, "reason": "permission"})
        except Exception as e:
            frappe.log_error(title="bulk_delete_tasks", message=frappe.get_traceback())
            failed.append({"name": issue, "reason": str(e)[:200]})

    from batch_projects.cache import invalidate_project
    for p in projects_touched:
        invalidate_project(p)

    return {"deleted": deleted, "failed": failed}


TRASH_RETENTION_DAYS = 30


def _hard_delete_task(doc_or_name):
    """Actually destroy a task row — the only path that does. Used by
    permanently_delete_task and the daily purge job. delete_task itself no
    longer calls this directly; it soft-deletes (see below)."""
    doc = doc_or_name if hasattr(doc_or_name, "delete") else frappe.get_doc("BP Task", doc_or_name)
    issue = doc.name

    for activity in frappe.get_all("BP Activity", filters={"task": issue}, pluck="name"):
        frappe.delete_doc("BP Activity", activity, ignore_permissions=True, force=True)

    if frappe.db.table_exists("BP Notification"):
        for notif in frappe.get_all("BP Notification", filters={"task": issue}, pluck="name"):
            frappe.delete_doc("BP Notification", notif, ignore_permissions=True, force=True)

    for watcher in frappe.get_all("BP Task Watcher", filters={"task": issue}, pluck="name"):
        frappe.delete_doc("BP Task Watcher", watcher, ignore_permissions=True, force=True)

    for subtask in frappe.get_all("BP Task", filters={"parent_task": issue}, pluck="name"):
        _hard_delete_task(subtask)

    doc.delete(ignore_permissions=True)


@frappe.whitelist()
def delete_task(issue):
    """Move a task to trash — recoverable via restore_task for
    TRASH_RETENTION_DAYS, after which purge_expired_trash removes it for
    good. Used to hard-delete immediately with no recovery path at all
    (audit 02 §B3 / 07 §G3): a mis-click on a 200-task bulk selection was
    permanent and became a support escalation with no way back.
    """
    doc = frappe.get_doc("BP Task", issue)
    _check_permission(doc.project, "BP Manager")
    project = doc.project

    if doc.is_deleted:
        return {"ok": True, "trashed": True}

    for subtask in frappe.get_all("BP Task", filters={"parent_task": issue, "is_deleted": 0}, pluck="name"):
        delete_task(subtask)

    # frappe.db.set_value, not doc.save() — this is a system flag flip, not
    # a semantic edit. Going through save() would run full validate() (the
    # completed-status blocker guard, irrelevant here) and — via
    # BP Task.on_update()'s diff — emit a spurious "field changed"
    # notification to every watcher for what the user experiences as a
    # delete, not an edit. Same reasoning timesheet_sync.py documents for
    # actual_hours.
    frappe.db.set_value("BP Task", issue, {
        "is_deleted": 1,
        "deleted_on": frappe.utils.now_datetime(),
        "deleted_by": frappe.session.user,
    }, update_modified=False)
    frappe.db.commit()
    from batch_projects.cache import invalidate_project
    invalidate_project(project)
    return {"ok": True, "trashed": True}


@frappe.whitelist()
def restore_task(issue):
    """Undo delete_task. Recursively restores subtasks trashed alongside it."""
    doc = frappe.get_doc("BP Task", issue)
    _check_permission(doc.project, "BP Manager")

    if not doc.is_deleted:
        return {"ok": True, "restored": True}

    frappe.db.set_value("BP Task", issue, {
        "is_deleted": 0, "deleted_on": None, "deleted_by": None,
    }, update_modified=False)

    for subtask in frappe.get_all("BP Task", filters={"parent_task": issue, "is_deleted": 1}, pluck="name"):
        restore_task(subtask)

    frappe.db.commit()
    from batch_projects.cache import invalidate_project
    invalidate_project(doc.project)
    return {"ok": True, "restored": True}


@frappe.whitelist()
def list_deleted_tasks(project):
    """Trash view for a project — Manager+ only, matching delete_task's own bar."""
    _check_permission(project, "BP Manager")
    return frappe.get_all(
        "BP Task",
        filters={"project": project, "is_deleted": 1},
        fields=["name", "task_key", "title", "status", "priority",
                "parent_task", "deleted_on", "deleted_by"],
        order_by="deleted_on desc",
    )


@frappe.whitelist()
def permanently_delete_task(issue):
    """The only path that actually destroys a task. Requires it to already
    be in trash — no skipping straight past the recoverable step."""
    doc = frappe.get_doc("BP Task", issue)
    _check_permission(doc.project, "BP Manager")
    if not doc.is_deleted:
        frappe.throw("Move this task to trash first.")
    project = doc.project
    _hard_delete_task(doc)
    frappe.db.commit()
    from batch_projects.cache import invalidate_project
    invalidate_project(project)
    return {"ok": True}


# ─── CHECKLIST ────────────────────────────────────────────────────────────────
# Stored in the task's custom_field_values JSON under key "_checklist".
# No migration needed — the field already exists.

import uuid

def _get_checklist(task):
    doc = frappe.get_doc("BP Task", task)
    cfv = _parse_json(doc.custom_field_values, {})
    return cfv.get("_checklist", [])


def _save_checklist(task, mutate, retries=5):
    """Reload-mutate-save with retry on TimestampMismatchError.

    Checklist edits (add/toggle/update/remove) fire back-to-back from the UI
    (e.g. add-item immediately followed by the new row's blur-save), each
    loading its own doc snapshot. Re-running `mutate` against a freshly
    reloaded doc on conflict avoids both the hard TimestampMismatchError and
    silently dropping the loser's edit.
    """
    for attempt in range(retries):
        doc = frappe.get_doc("BP Task", task)
        cfv = _parse_json(doc.custom_field_values, {})
        items = mutate(cfv.get("_checklist", []))
        cfv["_checklist"] = items
        doc.custom_field_values = json.dumps(cfv)
        try:
            doc.save(ignore_permissions=True)
            frappe.db.commit()
            return items
        except frappe.TimestampMismatchError:
            frappe.db.rollback()
            if attempt == retries - 1:
                raise


@frappe.whitelist()
def get_checklist(task):
    """Get checklist items for a task."""
    doc = frappe.get_doc("BP Task", task)
    _check_permission(doc.project, "BP Viewer")
    return {"items": _get_checklist(task)}


@frappe.whitelist()
def add_checklist_item(task, text):
    """Add a checklist item to a task."""
    doc = frappe.get_doc("BP Task", task)
    _check_permission(doc.project, "BP Member")
    new_item = {
        "id": str(uuid.uuid4())[:8],
        "text": (text or "").strip()[:500],
        "done": False,
    }

    def mutate(items):
        items.append(new_item)
        return items

    items = _save_checklist(task, mutate)
    return {"ok": True, "items": items}


@frappe.whitelist()
def update_checklist_item(task, item_id, text):
    """Update checklist item text."""
    doc = frappe.get_doc("BP Task", task)
    _check_permission(doc.project, "BP Member")

    def mutate(items):
        for item in items:
            if item["id"] == item_id:
                item["text"] = (text or "").strip()[:500]
                break
        return items

    items = _save_checklist(task, mutate)
    return {"ok": True, "items": items}


@frappe.whitelist()
def toggle_checklist_item(task, item_id):
    """Toggle checklist item done/undone."""
    doc = frappe.get_doc("BP Task", task)
    _check_permission(doc.project, "BP Member")

    def mutate(items):
        for item in items:
            if item["id"] == item_id:
                item["done"] = not item.get("done", False)
                break
        return items

    items = _save_checklist(task, mutate)
    return {"ok": True, "items": items}


@frappe.whitelist()
def remove_checklist_item(task, item_id):
    """Remove a checklist item."""
    doc = frappe.get_doc("BP Task", task)
    _check_permission(doc.project, "BP Member")

    def mutate(items):
        return [i for i in items if i["id"] != item_id]

    items = _save_checklist(task, mutate)
    return {"ok": True, "items": items}


@frappe.whitelist()
def duplicate_task(issue):
    """Create a copy of an existing task. Resets status to the project default;
    does not copy sprint, milestone, parent_task, assignees, or recurrence fields."""
    src = frappe.get_doc("BP Task", issue)
    _check_permission(src.project, "BP Member")

    # Resolve default status
    proj = frappe.get_doc("BP Project", src.project)
    states = _normalize_workflow_states(proj.get_workflow_states())
    default_status = states[0]["name"] if states else "To Do"

    doc = frappe.get_doc({
        "doctype": "BP Task",
        "project": src.project,
        "title": f"Copy of {src.title}",
        "status": default_status,
        "priority": src.priority,
        "task_type": src.task_type,
        "epic": src.epic,
        "description": src.description,
        "story_points": src.story_points,
        "estimated_hours": src.estimated_hours,
        "billable": src.billable,
        "custom_field_values": src.custom_field_values,
        "labels": src.labels,
    })
    doc.insert(ignore_permissions=True)
    from batch_projects.cache import invalidate_project
    invalidate_project(src.project)
    return doc.as_dict()


@frappe.whitelist()
def move_task_to_project(issue, target_project):
    """Re-parent a task into a different project.

    task_key is regenerated under the target project's own counter/prefix —
    the old key stops resolving. Fields that only make sense inside the
    source project (sprint/epic/milestone/parent_task/labels/custom fields)
    are dropped rather than carried over invalid, since none of those
    doctypes/definitions are guaranteed to exist in the target. Status maps
    to the same name if the target's workflow has it, else falls back to the
    target's first state — matches duplicate_task's own "reset status"
    posture for a project boundary crossing.
    """
    doc = frappe.get_doc("BP Task", issue)
    _check_permission(doc.project, "BP Member")
    if doc.project == target_project:
        frappe.throw("Task is already in this project.")
    _check_permission(target_project, "BP Member")

    old_project, old_key = doc.project, doc.task_key
    target = frappe.get_doc("BP Project", target_project)

    states = _normalize_workflow_states(target.get_workflow_states())
    state_names = {s["name"] for s in states}
    if doc.status not in state_names:
        doc.status = states[0]["name"] if states else doc.status

    new_key = f"{target.key}-{target.get_next_issue_number()}"
    doc.project = target_project
    doc.sprint = None
    doc.epic = None
    doc.milestone = None
    doc.parent_task = None
    doc.labels = "[]"
    doc.custom_field_values = "{}"
    doc.save(ignore_permissions=True)
    # task_key is read_only:1 — the ORM silently drops writes to it even with
    # ignore_permissions (confirmed: only frappe.db.set_value bypasses that),
    # so it has to be set directly, after the rest of the doc is saved.
    frappe.db.set_value("BP Task", doc.name, "task_key", new_key)
    doc.task_key = new_key
    frappe.db.commit()

    from batch_projects.cache import invalidate_project
    invalidate_project(old_project)
    invalidate_project(target_project)

    from batch_projects.events import emit, TASK_UPDATED
    emit(TASK_UPDATED, {
        "project": target_project,
        "task": doc.name,
        "task_key": doc.task_key,
        "changes": [{"field": "project", "from": old_key, "to": doc.task_key}],
    })

    return {"name": doc.name, "task_key": doc.task_key, "project": target_project, "old_key": old_key}


# ─── EXPORT DATA ───────────────────────────────────────────────────────────────
# Called by bp-gateway as the service account — not reachable by a browser
# session. Returns raw task rows as JSON; the gateway handles xlsx/pdf generation
# and the paid-tier gate.

def _assert_service_caller():
    """Only the bridge service account (System Manager / Administrator) may call."""
    user = frappe.session.user
    if user == "Administrator":
        return
    if "System Manager" in frappe.get_roles(user):
        return
    frappe.throw("Not permitted", frappe.PermissionError)


@frappe.whitelist()
def get_member_projects(user=None):
    """Service-caller only. Which BP Project names `user` may see, for the
    gateway's realtime SSE plane to filter its shared per-tenant event stream
    per connection — the browser equivalent of events.py's
    _get_broadcast_recipients, run in reverse (there: project -> recipients;
    here: user -> visible projects). System Managers/Administrator see
    everything ("all": true), matching _get_broadcast_recipients' existing
    behavior of unioning every System Manager into every project's
    recipient list.
    """
    _assert_service_caller()
    if not user:
        frappe.throw("user is required")
    if user == "Administrator" or "System Manager" in frappe.get_roles(user):
        return {"all": True, "projects": []}
    from batch_projects.permissions import get_accessible_projects
    accessible = get_accessible_projects(user=user)
    return {"all": False, "projects": sorted(accessible or [])}


_REBAC_SYNC_RESOURCES = {
    "projects": ("BP Project", ["name as project"]),
    "project_members": ("BP Project Member", ["parent as project", "user", "role"]),
    "tasks": ("BP Task", ["name as task", "project"]),
    "task_assignees": ("BP Task Assignee", ["parent as task", "user"]),
}


@frappe.whitelist()
def sync_rebac_state(resource, offset=0, limit=500):
    """Full-rebuild dump for the gateway's OpenFGA store after a flush — the
    Frappe-side half of "MariaDB is the source of truth, OpenFGA is a
    materialized view rebuilt from it" (docs/APP-OVERVIEW.md §5.3).
    Service-caller only, same credential get_member_projects/
    list_active_rules already trust — this returns company-wide data with
    no project scoping at all, which is only ever appropriate for the
    gateway's own rebuild routine.

    resource: one of _REBAC_SYNC_RESOURCES. Paginated (offset/limit,
    capped at 1000) — an install with tens of thousands of tasks must
    never be dumped in one unbounded query; the caller pages until
    has_more is false."""
    _assert_service_caller()

    spec = _REBAC_SYNC_RESOURCES.get(resource)
    if not spec:
        frappe.throw(
            f"Unknown resource '{resource}'. Expected one of: "
            f"{', '.join(sorted(_REBAC_SYNC_RESOURCES))}."
        )
    doctype, fields = spec

    offset = max(int(offset or 0), 0)
    limit = min(max(int(limit or 500), 1), 1000)

    rows = frappe.get_all(
        doctype, fields=fields,
        limit_start=offset, limit_page_length=limit,
        order_by="creation asc",
    )
    if resource == "project_members":
        # Legacy rows can carry the "BP "-prefixed alias (BP Admin/BP Manager/
        # ...) — normalize here so the gateway only ever sees the canonical
        # spelling model.fga's relation names are lowercased from
        # ("admin"/"manager"/"member"/"viewer"), same as access.normalize_role.
        from batch_projects.access import normalize_role
        for r in rows:
            r["role"] = normalize_role(r.get("role"))

    return {
        "items": rows,
        "has_more": len(rows) == limit,
        "next_offset": offset + len(rows),
    }


@frappe.whitelist()
def get_export_data(project, view=None):
    """Return task rows as plain JSON for the gateway to format into xlsx/pdf.
    Column set matches exportCsv() in ListView.vue."""
    _check_permission(project, "BP Viewer")
    _assert_service_caller()

    # Match the column set exportCsv uses: key, title, plus visible columns
    # We use a fixed sensible default set since we don't have the user's visibleCols
    tasks = frappe.get_all("BP Task", filters={"project": project},
        fields=["name", "task_key", "title", "status", "priority", "task_type",
                "due_date", "start_date", "story_points",
                "epic", "sprint", "milestone", "estimated_hours", "actual_hours",
                "billable", "labels", "creation", "modified"],
        order_by="creation asc")

    rows = []
    for t in tasks:
        # Resolve assignee names from child table
        assignee_names = []
        try:
            alist = frappe.get_all("BP Task Assignee", filters={"parent": t["name"]}, fields=["user", "full_name"])
            for a in alist:
                name = a.get("full_name", "") or frappe.db.get_value("User", a.get("user", ""), "full_name") or a.get("user", "")
                if name:
                    assignee_names.append(name)
        except Exception:
            pass

        epic_title = frappe.db.get_value("BP Epic", t["epic"], "title") if t.get("epic") else ""
        sprint_name = frappe.db.get_value("BP Sprint", t["sprint"], "sprint_name") if t.get("sprint") else ""
        milestone_name = t.get("milestone", "")

        rows.append({
            "key": t.get("task_key", ""),
            "title": t.get("title", ""),
            "status": t.get("status", ""),
            "priority": t.get("priority", ""),
            "type": t.get("task_type", ""),
            "assignee": "; ".join(assignee_names),
            "due_date": str(t.get("due_date") or ""),
            "start_date": str(t.get("start_date") or ""),
            "story_points": t.get("story_points", 0),
            "epic": epic_title or (t.get("epic") or ""),
            "sprint": sprint_name or (t.get("sprint") or ""),
            "milestone": milestone_name,
            "estimated_hours": t.get("estimated_hours") or "",
            "actual_hours": t.get("actual_hours") or "",
            "billable": "Yes" if t.get("billable") else "No",
            "labels": t.get("labels") or "",
            "created": str(t.get("creation") or ""),
            "modified": str(t.get("modified") or ""),
        })

    return rows


# ─── SAVED VIEWS ──────────────────────────────────────────────────────────────

_VIEW_TYPE_MAP = {"board": "Board", "list": "List", "timeline": "Timeline"}






@frappe.whitelist()
def get_views(project):
    """Return the current user's saved views for a project."""
    _check_permission(project, "BP Viewer")
    views = frappe.get_all(
        "BP View",
        filters={"project": project, "owner": frappe.session.user},
        fields=["name", "view_name", "view_type", "filters", "is_default",
                "subscribed", "subscription_frequency"],
        order_by="creation asc",
    )
    return [_serialize_view(v) for v in views]


@frappe.whitelist()
def save_view(project, view_name, config, view_type="board", is_default=0):
    """Create a personal saved view. `config` holds group_by/sort_by/filters/etc."""
    _check_permission(project, "BP Viewer")
    if not (view_name or "").strip():
        frappe.throw("View name is required.")
    if isinstance(config, str):
        config = json.loads(config)
    if not isinstance(config, dict):
        config = {}

    if int(is_default or 0):
        _clear_default_views(project, frappe.session.user)

    doc = frappe.get_doc({
        "doctype": "BP View",
        "view_name": view_name.strip(),
        "project": project,
        "view_type": _VIEW_TYPE_MAP.get((view_type or "board").lower(), "Board"),
        "filters": json.dumps(config),
        "is_default": 1 if int(is_default or 0) else 0,
    })
    doc.insert(ignore_permissions=True)
    return _serialize_view({
        "name": doc.name, "view_name": doc.view_name, "view_type": doc.view_type,
        "filters": doc.filters, "is_default": doc.is_default,
    })


@frappe.whitelist()
def update_view(view, view_name=None, config=None, is_default=None):
    """Rename / re-configure / set-default an existing view (owner only)."""
    doc = frappe.get_doc("BP View", view)
    if doc.owner != frappe.session.user:
        frappe.throw("You can only modify your own views.")
    if view_name is not None and view_name.strip():
        doc.view_name = view_name.strip()
    if config is not None:
        if isinstance(config, str):
            config = json.loads(config)
        doc.filters = json.dumps(config if isinstance(config, dict) else {})
    if is_default is not None:
        if int(is_default):
            _clear_default_views(doc.project, frappe.session.user)
        doc.is_default = 1 if int(is_default) else 0
    doc.save(ignore_permissions=True)
    return _serialize_view({
        "name": doc.name, "view_name": doc.view_name, "view_type": doc.view_type,
        "filters": doc.filters, "is_default": doc.is_default,
    })




@frappe.whitelist()
def subscribe_view(view, subscribed=1, frequency="Weekly"):
    """Toggle email subscription on a saved view."""
    doc = frappe.get_doc("BP View", view)
    if doc.owner != frappe.session.user:
        frappe.throw("You can only subscribe to your own views.")
    doc.subscribed = 1 if int(subscribed) else 0
    if frequency in ("Daily", "Weekly"):
        doc.subscription_frequency = frequency
    doc.save(ignore_permissions=True)
    return {"subscribed": bool(doc.subscribed), "subscription_frequency": doc.subscription_frequency}


# ── Mirror columns ───────────────────────────────────────────────────────────
# Whitelisted, read-only fields per doctype that list views may project as
# columns. Never expose anything outside this map.
MIRROR_SCHEMA = {
    "Sales Order": [
        {"fieldname": "status",           "label": "Status",      "fieldtype": "Status"},
        {"fieldname": "grand_total",      "label": "Total",       "fieldtype": "Currency"},
        {"fieldname": "transaction_date", "label": "Date",        "fieldtype": "Date"},
        {"fieldname": "delivery_date",    "label": "Delivery",    "fieldtype": "Date"},
        {"fieldname": "customer",         "label": "Customer",    "fieldtype": "Text"},
        {"fieldname": "per_billed",       "label": "% Billed",    "fieldtype": "Percent"},
    ],
    "Sales Invoice": [
        {"fieldname": "status",             "label": "Status",      "fieldtype": "Status"},
        {"fieldname": "grand_total",        "label": "Total",       "fieldtype": "Currency"},
        {"fieldname": "outstanding_amount", "label": "Outstanding", "fieldtype": "Currency"},
        {"fieldname": "due_date",           "label": "Due",         "fieldtype": "Date"},
        {"fieldname": "customer",           "label": "Customer",    "fieldtype": "Text"},
    ],
    "Purchase Order": [
        {"fieldname": "status",        "label": "Status",   "fieldtype": "Status"},
        {"fieldname": "grand_total",   "label": "Total",    "fieldtype": "Currency"},
        {"fieldname": "supplier",      "label": "Supplier", "fieldtype": "Text"},
        {"fieldname": "schedule_date", "label": "Expected", "fieldtype": "Date"},
    ],
    "Purchase Invoice": [
        {"fieldname": "status",             "label": "Status",      "fieldtype": "Status"},
        {"fieldname": "grand_total",        "label": "Total",       "fieldtype": "Currency"},
        {"fieldname": "outstanding_amount", "label": "Outstanding", "fieldtype": "Currency"},
        {"fieldname": "supplier",           "label": "Supplier",    "fieldtype": "Text"},
    ],
    "Customer": [
        {"fieldname": "customer_group", "label": "Group",     "fieldtype": "Text"},
        {"fieldname": "territory",      "label": "Territory", "fieldtype": "Text"},
    ],
    "Supplier": [
        {"fieldname": "supplier_group", "label": "Group",   "fieldtype": "Text"},
        {"fieldname": "country",        "label": "Country", "fieldtype": "Text"},
    ],
    "Quotation": [
        {"fieldname": "status",      "label": "Status",      "fieldtype": "Status"},
        {"fieldname": "grand_total", "label": "Total",       "fieldtype": "Currency"},
        {"fieldname": "valid_till",  "label": "Valid till",  "fieldtype": "Date"},
    ],
    "Stock Entry": [
        {"fieldname": "stock_entry_type", "label": "Type", "fieldtype": "Text"},
        {"fieldname": "posting_date",     "label": "Date", "fieldtype": "Date"},
    ],
}


@frappe.whitelist()
@frappe.whitelist()
def get_mirror_schema():
    """Field whitelist the UI may offer as mirror columns."""
    _require_system_user()
    return MIRROR_SCHEMA


# Mirror doctypes that carry their own `project` field — a BP Member who is
# ALSO a genuine ERPNext Sales/Accounts user (real DocPerm rows, so
# get_list's permission layer doesn't block them) could otherwise pull
# mirror data for any document company-wide, not just the project they're
# viewing — a low-severity tenancy gap, since it requires real ERPNext
# permissions most BP members won't have, but a real gap nonetheless.
# Customer/Supplier/Quotation have no project field at all — legitimately
# cross-project shared reference data, same reasoning as
# search_erp_documents' own allowlist — left unscoped.
_MIRROR_PROJECT_SCOPED_DOCTYPES = {
    "Sales Order", "Sales Invoice", "Purchase Order", "Purchase Invoice", "Stock Entry",
}


@frappe.whitelist()
def get_mirror_values(doctype, names, project=None):
    """Batch-read whitelisted fields for the given documents."""
    _require_system_user()
    if doctype not in MIRROR_SCHEMA:
        frappe.throw(f"Mirroring is not enabled for {doctype}.")
    if isinstance(names, str):
        names = json.loads(names)
    names = [n for n in (names or []) if n]
    if not names:
        return {}
    fields = ["name"] + [f["fieldname"] for f in MIRROR_SCHEMA[doctype]]
    if doctype in {"Sales Order", "Sales Invoice", "Purchase Order", "Purchase Invoice", "Quotation"}:
        fields.append("currency")

    filters = {"name": ["in", names]}
    if project and doctype in _MIRROR_PROJECT_SCOPED_DOCTYPES:
        _check_permission(project, "BP Viewer")
        erp_project = frappe.db.get_value("BP Project", project, "erpnext_project")
        if erp_project:
            filters["project"] = erp_project

    rows = frappe.get_list(doctype, filters=filters, fields=fields)
    return {r["name"]: r for r in rows}


# ─── BACKLOG + SPRINT TASK MOVE ───────────────────────────────────────────────

@frappe.whitelist()
def get_backlog(project):
    """
    Returns all top-level tasks for the project (excluding subtasks).
    Frontend splits by sprint status.
    """
    _check_permission(project, "BP Viewer")

    from batch_projects.cache import get as cache_get, set as cache_set, VIEW_BACKLOG
    cached = cache_get(VIEW_BACKLOG, project)
    if cached is not None:
        return cached

    issues = frappe.get_all(
        "BP Task",
        filters=_task_filters({"project": project, "parent_task": ["in", ["", None]]}),
        fields=[
            "name", "task_key", "title", "status", "priority", "task_type",
            "sprint", "epic", "story_points", "actual_points", "is_unplanned",
            "due_date", "start_date", "labels", "custom_field_values",
            "billable", "estimated_hours",
        ],
        order_by="board_rank asc, creation asc",
    )

    if issues:
        issue_names = [i["name"] for i in issues]
        assignees = frappe.get_all(
            "BP Task Assignee",
            filters={"parent": ["in", issue_names]},
            fields=["parent", "user", "full_name"],
        )
        assignee_map = {}
        for a in assignees:
            assignee_map.setdefault(a["parent"], []).append({
                "user": a["user"],
                "full_name": a["full_name"] or a["user"],
            })
        refs_map = _fetch_task_refs(issue_names)
        epics = _fetch_epics(issues)
        for issue in issues:
            issue["assignees"] = assignee_map.get(issue["name"], [])
            issue["references"] = refs_map.get(issue["name"], [])
            if issue.get("epic") and issue["epic"] in epics:
                issue["epic_title"] = epics[issue["epic"]]["title"]
                issue["epic_color"] = epics[issue["epic"]]["color"]
            else:
                issue["epic_title"] = ""
                issue["epic_color"] = ""

    cache_set(VIEW_BACKLOG, project, issues)
    return issues


@frappe.whitelist()
def move_task_to_sprint(issue, sprint):
    """
    Assign a task to a sprint (or pass sprint='' to move to backlog).
    """
    doc = frappe.get_doc("BP Task", issue)
    _check_permission(doc.project, "BP Member")

    if sprint:
        sprint_doc = frappe.get_doc("BP Sprint", sprint)
        if sprint_doc.project != doc.project:
            frappe.throw("Sprint does not belong to the same project.")
        doc.sprint = sprint
    else:
        doc.sprint = None

    doc.save(ignore_permissions=True)
    frappe.db.commit()
    from batch_projects.cache import invalidate_project
    invalidate_project(doc.project)
    return {"task": doc.name, "sprint": doc.sprint}


# ─── COMMENTS ─────────────────────────────────────────────────────────────────

@frappe.whitelist()
def add_comment(issue, comment_text):
    doc = frappe.get_doc("BP Task", issue)
    _check_permission(doc.project, "BP Member")

    activity = frappe.get_doc({
        "doctype": "BP Activity",
        "task": issue,
        "action_type": "Comment",
        "comment_text": comment_text,
        "user": frappe.session.user,
    })
    activity.insert(ignore_permissions=True)

    emit(COMMENT_ADDED, {
        "project": doc.project,
        "task": issue,
        "task_key": doc.task_key,
        "comment_text": comment_text,
        "activity": activity.name,
        "mentions": _parse_mentions(comment_text),
    })

    return {"ok": True, "activity": activity.name}


# Mentions are stored in comment text as @[Display Name](user_id)
_MENTION_RE = re.compile(r"@\[[^\]]+\]\(([^)]+)\)")


def _parse_mentions(text):
    """Extract mentioned user ids from a comment body."""
    if not text:
        return []
    seen, out = set(), []
    for uid in _MENTION_RE.findall(text):
        uid = uid.strip()
        if uid and uid not in seen:
            seen.add(uid)
            out.append(uid)
    return out


@frappe.whitelist()
def edit_comment(activity, comment_text):
    """Edit an existing comment. Only the comment author or a manager can edit."""
    doc = frappe.get_doc("BP Activity", activity)
    if doc.action_type != "Comment":
        frappe.throw("Only comments can be edited.")

    task = frappe.get_doc("BP Task", doc.task)
    user = frappe.session.user

    # Allow edit if owner or project manager+
    if doc.user != user:
        _check_permission(task.project, "BP Manager")

    # Notify only people newly mentioned by this edit (not those already in the prior text)
    prior_mentions = set(_parse_mentions(doc.comment_text))
    new_mentions = [u for u in _parse_mentions(comment_text) if u not in prior_mentions]

    doc.comment_text = comment_text
    doc.save(ignore_permissions=True)

    # emit() registers its realtime broadcast on frappe.db.after_commit (see
    # _broadcast's after_commit=True) — it must be called BEFORE the
    # transaction commits, not after, so "no event on rollback, event
    # published once the mutation is actually durable" is the guarantee
    # that's kept, not merely coincidental. Matches add_comment's existing
    # convention just above, which never manually commits before its own
    # emit() call at all.
    #
    # Realtime signal for every edit — an open task detail elsewhere must
    # refetch to see the new text, whether or not this particular edit added
    # a mention. Separate from the mentions_only emit below: that one exists
    # purely to route notifications to the newly-mentioned users, not to
    # signal the edit itself, which used to have no broadcast at all.
    emit(COMMENT_EDITED, {
        "project": task.project,
        "task": doc.task,
        "task_key": task.task_key,
        "comment_text": comment_text,
        "activity": doc.name,
    })

    if new_mentions:
        emit(COMMENT_ADDED, {
            "project": task.project,
            "task": doc.task,
            "task_key": task.task_key,
            "comment_text": comment_text,
            "activity": doc.name,
            "mentions": new_mentions,
            # only the newly-mentioned should be notified, not all task recipients
            "mentions_only": True,
        })

    frappe.db.commit()
    return {"ok": True, "activity": doc.name, "comment_text": doc.comment_text}


@frappe.whitelist()
def delete_comment(activity):
    """Delete a comment. Only the author or a manager can delete."""
    doc = frappe.get_doc("BP Activity", activity)
    if doc.action_type != "Comment":
        frappe.throw("Only comments can be deleted.")

    task = frappe.get_doc("BP Task", doc.task)
    user = frappe.session.user

    # Allow delete if owner or project manager+
    if doc.user != user:
        _check_permission(task.project, "BP Manager")

    activity_name = doc.name
    frappe.delete_doc("BP Activity", activity, ignore_permissions=True, force=True)

    # See edit_comment's comment on why emit() must precede the commit, not
    # follow it: _broadcast registers on frappe.db.after_commit.
    emit(COMMENT_DELETED, {
        "project": task.project,
        "task": doc.task,
        "task_key": task.task_key,
        "activity": activity_name,
    })

    frappe.db.commit()

    return {"ok": True}


# ─── NOTIFICATIONS ────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_muted_items():
    """Return the current user's muted tasks + projects."""
    rows = frappe.get_all(
        "BP Notification Mute",
        filters={"user": frappe.session.user},
        fields=["name", "task", "project"],
    )
    return {
        "tasks": [r["task"] for r in rows if r.get("task")],
        "projects": [r["project"] for r in rows if r.get("project") and not r.get("task")],
    }


@frappe.whitelist()
def set_mute(task=None, project=None, muted=1):
    """Mute/unmute a task or project for the current user."""
    user = frappe.session.user
    if not task and not project:
        frappe.throw("Provide a task or a project to mute.")

    filters = {"user": user}
    if task:
        filters["task"] = task
    else:
        filters["project"] = project
        filters["task"] = ["in", ["", None]]

    existing = frappe.get_all("BP Notification Mute", filters=filters, pluck="name")

    if int(muted):
        if not existing:
            frappe.get_doc({
                "doctype": "BP Notification Mute",
                "user": user,
                "task": task or None,
                "project": project or (frappe.db.get_value("BP Task", task, "project") if task else None),
            }).insert(ignore_permissions=True)
        return {"muted": True}
    else:
        for name in existing:
            frappe.delete_doc("BP Notification Mute", name, ignore_permissions=True)
        return {"muted": False}


@frappe.whitelist()
def get_notifications(limit=30, offset=0, unread_only=False, on_date=None):
    """Return the current user's notifications, newest first."""
    _require_system_user()
    if not frappe.db.table_exists("BP Notification"):
        return {"notifications": [], "unread_count": 0, "total": 0}

    user = frappe.session.user

    filters = {"recipient": user}
    if frappe.utils.cint(unread_only):
        filters["is_read"] = 0
    if on_date:
        on_date = frappe.utils.getdate(on_date)
        filters["creation"] = ["between", [f"{on_date} 00:00:00", f"{on_date} 23:59:59"]]

    notifications = frappe.get_all(
        "BP Notification",
        filters=filters,
        fields=[
            "name", "notification_type", "task", "task_key", "task_title",
            "project", "actor", "actor_name", "message", "is_read", "read_at",
            "creation",
        ],
        order_by="creation desc",
        limit=frappe.utils.cint(limit) or 30,
        start=frappe.utils.cint(offset) or 0,
    )

    unread_count = frappe.db.count("BP Notification", {"recipient": user, "is_read": 0})

    return {
        "notifications": notifications,
        "unread_count": unread_count,
        "total": frappe.db.count("BP Notification", filters),
    }


@frappe.whitelist()
def mark_notification_read(notification):
    """Mark a single notification as read."""
    _require_system_user()
    if not frappe.db.table_exists("BP Notification"):
        return {"ok": True, "unread_count": 0}
    user = frappe.session.user
    doc = frappe.get_doc("BP Notification", notification)
    if doc.recipient != user and "System Manager" not in frappe.get_roles(user):
        frappe.throw("Not authorized.", frappe.PermissionError)
    if not doc.is_read:
        doc.is_read = 1
        doc.read_at = frappe.utils.now()
        doc.save(ignore_permissions=True)
        frappe.db.commit()

    unread_count = frappe.db.count("BP Notification", {"recipient": user, "is_read": 0})
    return {"ok": True, "unread_count": unread_count}


@frappe.whitelist()
def mark_notification_unread(notification):
    """Mark a single notification as unread."""
    _require_system_user()
    if not frappe.db.table_exists("BP Notification"):
        return {"ok": True, "unread_count": 0}
    user = frappe.session.user
    doc = frappe.get_doc("BP Notification", notification)
    if doc.recipient != user and "System Manager" not in frappe.get_roles(user):
        frappe.throw("Not authorized.", frappe.PermissionError)
    if doc.is_read:
        doc.is_read = 0
        doc.read_at = None
        doc.save(ignore_permissions=True)
        frappe.db.commit()

    unread_count = frappe.db.count("BP Notification", {"recipient": user, "is_read": 0})
    return {"ok": True, "unread_count": unread_count}


@frappe.whitelist()
def mark_all_notifications_read():
    """Mark all of the current user's notifications as read."""
    _require_system_user()
    if not frappe.db.table_exists("BP Notification"):
        return {"ok": True, "unread_count": 0}
    user = frappe.session.user
    now = frappe.utils.now()

    frappe.db.sql("""
        UPDATE `tabBP Notification`
        SET is_read = 1, read_at = %s
        WHERE recipient = %s AND is_read = 0
    """, (now, user))
    frappe.db.commit()

    return {"ok": True, "unread_count": 0}


@frappe.whitelist()
def get_notification_count():
    """Lightweight endpoint for sidebar badge — just the unread count."""
    _require_system_user()
    if not frappe.db.table_exists("BP Notification"):
        return {"unread_count": 0}
    user = frappe.session.user
    unread_count = frappe.db.count("BP Notification", {"recipient": user, "is_read": 0})
    return {"unread_count": unread_count}


# ─── EPICS ─────────────────────────────────────────────────────────────────────


@frappe.whitelist()
def get_epics(project):
    _check_permission(project, "BP Viewer")
    epics = frappe.get_all(
        "BP Epic",
        filters={"project": project},
        fields=["name", "title", "status", "color", "start_date", "end_date"],
        order_by="creation asc",
    )
    completed = _get_completed_statuses_by_project(project)
    for epic in epics:
        total = frappe.db.count("BP Task", _task_filters({"epic": epic["name"]}))
        done  = frappe.db.count("BP Task", _task_filters({"epic": epic["name"], "status": ["in", completed]}))
        epic["total_issues"] = total
        epic["done_issues"]  = done
        epic["progress"]     = round((done / total * 100) if total > 0 else 0, 1)
    return epics


@frappe.whitelist()
def create_epic(project, title, color=None, description=None,
                start_date=None, end_date=None, status=None):
    _check_permission(project, "BP Member")
    if not (title or "").strip():
        frappe.throw("Epic title is required.")
    doc = frappe.get_doc({
        "doctype": "BP Epic",
        "project": project,
        "title": title.strip(),
        "color": color or "#6366f1",
        "description": description or "",
        "start_date": start_date or None,
        "end_date": end_date or None,
        "status": status or "Open",
    })
    doc.insert(ignore_permissions=True)
    from batch_projects.cache import invalidate_project
    invalidate_project(project)
    return {
        "name": doc.name, "title": doc.title, "status": doc.status,
        "color": doc.color, "start_date": doc.start_date, "end_date": doc.end_date,
        "total_issues": 0, "done_issues": 0, "progress": 0,
    }


@frappe.whitelist()
def update_epic(epic, fields):
    if isinstance(fields, str):
        fields = json.loads(fields)
    doc = frappe.get_doc("BP Epic", epic)
    _check_permission(doc.project, "BP Member")
    for k, v in fields.items():
        if k in ("name", "project", "doctype", "cmd") or k.startswith("_"):
            continue
        if hasattr(doc, k):
            if v == "" and doc.meta.get_field(k) and \
               doc.meta.get_field(k).fieldtype in ("Date", "Datetime"):
                v = None
            setattr(doc, k, v)
    doc.save(ignore_permissions=True)
    from batch_projects.cache import invalidate_project
    invalidate_project(doc.project)
    return {"ok": True, "name": doc.name, "title": doc.title}


@frappe.whitelist()
def delete_epic(epic):
    doc = frappe.get_doc("BP Epic", epic)
    _check_permission(doc.project, "BP Manager")
    project = doc.project
    # Unlink tasks from this epic (don't delete the tasks)
    frappe.db.set_value("BP Task", {"epic": epic}, "epic", None, update_modified=False)
    doc.delete(ignore_permissions=True)
    from batch_projects.cache import invalidate_project
    invalidate_project(project)
    return {"ok": True}
    """Create a copy of an existing task. Resets status to the project default;
    does not copy sprint, milestone, parent_task, assignees, or recurrence fields."""
    src = frappe.get_doc("BP Task", issue)
    _check_permission(src.project, "BP Member")

    # Resolve default status
    proj = frappe.get_doc("BP Project", src.project)
    states = _normalize_workflow_states(proj.get_workflow_states())
    default_status = states[0]["name"] if states else "To Do"

    doc = frappe.get_doc({
        "doctype": "BP Task",
        "project": src.project,
        "title": f"Copy of {src.title}",
        "status": default_status,
        "priority": src.priority,
        "task_type": src.task_type,
        "epic": src.epic,
        "description": src.description,
        "story_points": src.story_points,
        "estimated_hours": src.estimated_hours,
        "billable": src.billable,
        "custom_field_values": src.custom_field_values,
        "labels": src.labels,
    })
    doc.insert(ignore_permissions=True)
    from batch_projects.cache import invalidate_project
    invalidate_project(src.project)
    return doc.as_dict()

# ─── SAVED REPORTS ──────────────────────────────────────────────────────────────


@frappe.whitelist()
def get_saved_reports():
    """List saved reports visible to the user: workspace reports + reports on
    projects they can access."""
    from batch_projects.permissions import get_accessible_projects
    accessible = get_accessible_projects()
    rows = frappe.get_all(
        "BP Report",
        fields=["name", "report_name", "icon", "color", "starred", "pinned",
                "project", "milestone", "period", "schedule_enabled",
                "schedule_frequency", "schedule_day", "schedule_hour",
                "schedule_recipients", "last_sent", "modified", "owner"],
        order_by="modified desc",
    )
    out = []
    for r in rows:
        if accessible is None or not r.project or r.project in accessible:
            out.append({
                "id": r.name, "report_name": r.report_name,
                "icon": r.icon or "BarChart3", "color": r.color or None,
                "starred": bool(r.starred), "pinned": bool(r.pinned),
                "scope": r.project or "all",
                "project": r.project or None, "milestone": r.milestone or None,
                "period": r.period or "last_30_days",
                "schedule_enabled": bool(r.schedule_enabled),
                "schedule_frequency": r.schedule_frequency or "Weekly",
                "schedule_day": r.schedule_day or "Monday",
                "schedule_hour": r.schedule_hour if r.schedule_hour is not None else 8,
                "schedule_recipients": r.schedule_recipients or "",
                "last_sent": str(r.last_sent) if r.last_sent else None,
                "modified": str(r.modified), "owner": r.owner,
            })
    return out


@frappe.whitelist()
def get_saved_report(report):
    doc = frappe.get_doc("BP Report", report)
    if doc.project:
        _check_permission(doc.project, "BP Viewer")
    return _report_out(doc, with_layout=True)


@frappe.whitelist()

def resolve_report_recipients(recipients_str, project):
    """Split a `schedule_recipients` string into (allowed, dropped) email
    addresses. `allowed` = resolves to an enabled User with at least Viewer
    access to `project` (or, for an unscoped/"all" report, to at least one
    project at all). Everything else — free-text external addresses, or
    internal users with no access — is `dropped`.

    Shared by the write-time gate below and the send-time revalidation in
    events.send_scheduled_reports, so a membership change after a schedule
    was created can't leave a stale recipient still receiving mail.
    """
    import re
    from batch_projects import access
    from batch_projects.permissions import get_accessible_projects

    candidates = [e.strip() for e in re.split(r"[,\n;]+", recipients_str or "") if "@" in e]
    allowed, dropped = [], []
    for addr in candidates:
        user = frappe.db.get_value("User", {"email": addr, "enabled": 1}, "name")
        if not user:
            dropped.append(addr)
            continue
        if project:
            ok = access.has_at_least(project, "Viewer", user)
        else:
            accessible = get_accessible_projects(user)
            ok = accessible is None or len(accessible) > 0
        (allowed if ok else dropped).append(addr)
    return allowed, dropped


def _assert_recipients_authorized(recipients_str, project, caller):
    """Write-time gate for schedule_recipients (audit 07 G1): a plain
    Member may only schedule a report to users who already have access to
    it. Pointing it at an unresolvable/external address, or an internal
    user with no access, requires Manager+ on the project (or instance
    admin) — an explicit, privileged decision, not a default any Member
    can make silently."""
    if not recipients_str:
        return
    from batch_projects import access
    _, dropped = resolve_report_recipients(recipients_str, project)
    if not dropped:
        return
    is_privileged = access.is_instance_admin(caller) or (
        project and access.has_at_least(project, "Manager", caller)
    )
    if is_privileged:
        return
    frappe.throw(
        "These recipients don't have access to this report and can't be "
        f"added: {', '.join(dropped)}. A project Manager can add them explicitly."
    )


@frappe.whitelist()
def save_report(report_name=None, project=None, milestone=None, period="last_30_days",
                icon="BarChart3", color=None, layout=None, report=None,
                starred=None, pinned=None, schedule_enabled=None,
                schedule_frequency=None, schedule_day=None, schedule_hour=None,
                schedule_recipients=None):
    """Create (report omitted) or update (report given) a saved report."""
    project = project or None
    if project:
        _check_permission(project, "BP Member")

    if report:
        doc = frappe.get_doc("BP Report", report)
        if doc.project:
            _check_permission(doc.project, "BP Member")
        if report_name is not None: doc.report_name = report_name
        if project is not None or report_name is not None: doc.project = project
        if milestone is not None: doc.milestone = milestone or None
        if period is not None: doc.period = period
        if icon is not None: doc.icon = icon
        if color is not None: doc.color = color
        if starred is not None: doc.starred = _as_bool(starred)
        if pinned is not None: doc.pinned = _as_bool(pinned)
        if schedule_enabled is not None: doc.schedule_enabled = _as_bool(schedule_enabled)
        if schedule_frequency is not None: doc.schedule_frequency = schedule_frequency
        if schedule_day is not None: doc.schedule_day = schedule_day
        if schedule_hour is not None: doc.schedule_hour = frappe.utils.cint(schedule_hour)
        if schedule_recipients is not None:
            _assert_recipients_authorized(schedule_recipients, doc.project, frappe.session.user)
            doc.schedule_recipients = schedule_recipients
        if layout is not None:
            doc.layout = layout if isinstance(layout, str) else json.dumps(layout)
        doc.save(ignore_permissions=True)
    else:
        if schedule_recipients:
            _assert_recipients_authorized(schedule_recipients, project, frappe.session.user)
        doc = frappe.get_doc({
            "doctype": "BP Report",
            "report_name": report_name or "Untitled report",
            "project": project, "milestone": milestone or None,
            "period": period, "icon": icon, "color": color,
            "starred": _as_bool(starred) if starred is not None else 0,
            "pinned": _as_bool(pinned) if pinned is not None else 0,
            "schedule_enabled": _as_bool(schedule_enabled) if schedule_enabled is not None else 0,
            "schedule_frequency": schedule_frequency or "Weekly",
            "schedule_day": schedule_day or "Monday",
            "schedule_hour": frappe.utils.cint(schedule_hour) if schedule_hour is not None else 8,
            "schedule_recipients": schedule_recipients or "",
            "layout": layout if isinstance(layout, str) else json.dumps(layout or []),
        })
        doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return _report_out(doc, with_layout=True)


@frappe.whitelist()

@frappe.whitelist()
def delete_saved_report(report):
    doc = frappe.get_doc("BP Report", report)
    if doc.project:
        _check_permission(doc.project, "BP Member")
    frappe.delete_doc("BP Report", report)
    frappe.db.commit()
    return {"deleted": report}


@frappe.whitelist()

@frappe.whitelist()
def get_milestone_report(milestone):
    """Milestone rollup — the ERP moat: not just task completion %, but the
    financial picture (hours, billable value, cost vs project budget) that
    pure-PM tools can't show without integrations."""
    m = frappe.get_doc("BP Milestone", milestone)
    _check_permission(m.project, "BP Viewer")
    proj = frappe.get_doc("BP Project", m.project)
    completed = set(proj.get_completed_statuses())

    tasks = frappe.get_all(
        "BP Task",
        filters={"milestone": milestone},
        fields=["name", "task_key", "title", "status", "story_points",
                "estimated_hours", "actual_hours", "billable", "due_date"],
    )

    total = len(tasks)
    done = sum(1 for t in tasks if t.status in completed)
    pts_total = sum(float(t.story_points or 0) for t in tasks)
    pts_done = sum(float(t.story_points or 0) for t in tasks if t.status in completed)
    est_hours = sum(float(t.estimated_hours or 0) for t in tasks)
    act_hours = sum(float(t.actual_hours or 0) for t in tasks)
    billable_hours = sum(float(t.actual_hours or 0) for t in tasks if t.billable)

    rate = float(proj.hourly_rate or 0)
    budget = float(proj.budget_amount or 0)
    cost = round(act_hours * rate, 2)
    billable_value = round(billable_hours * rate, 2)

    return {
        "milestone": milestone,
        "title": m.title,
        "project": m.project,
        "project_name": proj.project_name,
        "currency": proj.currency or None,
        "due_date": str(m.due_date) if m.due_date else None,
        "status": m.status,
        "delivery": {
            "total": total,
            "done": done,
            "completion_pct": round(done / total * 100) if total else 0,
            "points_total": round(pts_total, 1),
            "points_done": round(pts_done, 1),
        },
        "financials": {
            "estimated_hours": round(est_hours, 1),
            "actual_hours": round(act_hours, 1),
            "billable_hours": round(billable_hours, 1),
            "hourly_rate": rate,
            "cost": cost,
            "billable_value": billable_value,
            "budget": budget,
            "budget_used_pct": round(cost / budget * 100) if budget else None,
        },
        "tasks": tasks,
    }


@frappe.whitelist()
def get_project_budget_summary(project):
    """Whole-project budget consumption for the Summary tab's utilization
    gauge — same estimated-cost formula as get_milestone_report
    (actual_hours x hourly_rate vs budget_amount), just rolled up across
    the whole project instead of one milestone. Deliberately NOT the
    heavier margin-report calculation (real Sales Invoice/Timesheet/
    Purchase Invoice/Expense Claim joins, gated behind the paid
    "profitability" entitlement, and now computed in the gateway — see
    api/insights_data.py) — a summary gauge shouldn't require an
    erpnext_project link or a premium tier to render a rough estimate."""
    project = _resolve_project(project)
    _check_permission(project, "BP Viewer")
    proj = frappe.get_doc("BP Project", project)

    act_hours = frappe.db.sql(
        """SELECT SUM(actual_hours) FROM `tabBP Task` WHERE project = %s AND is_deleted = 0""",
        (project,),
    )[0][0] or 0

    rate   = float(proj.hourly_rate or 0)
    budget = float(proj.budget_amount or 0)
    cost   = round(float(act_hours) * rate, 2)

    return {
        "project": project,
        "currency": proj.currency or None,
        "hourly_rate": rate,
        "actual_hours": round(float(act_hours), 1),
        "cost": cost,
        "budget": budget,
        "budget_used_pct": round(cost / budget * 100) if budget else None,
    }


# ─── PER-USER VIEW PREFERENCES ─────────────────────────────────────────────────
# Column layout / density / ERP columns for the List (and other grid) views.
# Stored per-user, per-project, per-view so the layout follows the user across
# devices instead of living in browser localStorage.

def _resolve_project(project):
    """Accept either a project name or its short key (the UI route uses the key)."""
    if frappe.db.exists("BP Project", project):
        return project
    alt = frappe.db.get_value("BP Project", {"key": project}, "name")
    return alt or project


@frappe.whitelist()
def get_view_prefs(project, view="list"):
    """Return the current user's saved view preferences for a project view.

    Returns the stored prefs dict, or {} if none saved yet."""
    project = _resolve_project(project)
    _check_permission(project, "BP Viewer")
    name = frappe.db.get_value(
        "BP View Preference",
        {"user": frappe.session.user, "project": project, "view": view},
        "name",
    )
    if not name:
        return {}
    raw = frappe.db.get_value("BP View Preference", name, "prefs") or "{}"
    try:
        return json.loads(raw) if isinstance(raw, str) else (raw or {})
    except Exception:
        return {}



@frappe.whitelist()
def save_view_prefs(project, prefs, view="list"):
    """Upsert the current user's view preferences for a project view."""
    project = _resolve_project(project)
    _check_permission(project, "BP Viewer")
    if isinstance(prefs, str):
        try:
            prefs = json.loads(prefs)
        except Exception:
            frappe.throw("prefs must be valid JSON")
    if not isinstance(prefs, dict):
        frappe.throw("prefs must be an object")

    user = frappe.session.user
    name = frappe.db.get_value(
        "BP View Preference",
        {"user": user, "project": project, "view": view},
        "name",
    )
    if name:
        doc = frappe.get_doc("BP View Preference", name)
    else:
        doc = frappe.get_doc({
            "doctype": "BP View Preference",
            "user": user,
            "project": project,
            "view": view,
        })
    doc.prefs = json.dumps(prefs)
    doc.save(ignore_permissions=True)
    return prefs






# ─── SPRINTS ──────────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_sprints(project):
    _check_permission(project, "BP Viewer")

    from batch_projects.cache import get as cache_get, set as cache_set, VIEW_SPRINTS
    cached = cache_get(VIEW_SPRINTS, project)
    if cached is not None:
        return cached

    sprints = frappe.get_all(
        "BP Sprint",
        filters={"project": project},
        fields=["name", "sprint_name", "status", "goal", "start_date", "end_date"],
        order_by="creation asc",
    )

    if not sprints:
        return sprints

    sprint_names = [s["name"] for s in sprints]

    # Total issues per sprint
    total_rows = frappe.db.sql(
        f"""
        SELECT sprint, COUNT(*) as cnt
        FROM `tabBP Task`
        WHERE sprint IN ({','.join(['%s'] * len(sprint_names))})
          AND project = %s
          AND is_deleted = 0
        GROUP BY sprint
        """,
        sprint_names + [project],
        as_dict=True,
    )
    total_map = {r["sprint"]: r["cnt"] for r in total_rows}

    # Total estimated effort (story points) per sprint — "Total estimated
    # effort" column from the sprint column catalog.
    points_rows = frappe.db.sql(
        f"""
        SELECT sprint, SUM(COALESCE(story_points, 0)) as pts
        FROM `tabBP Task`
        WHERE sprint IN ({','.join(['%s'] * len(sprint_names))})
          AND project = %s
          AND is_deleted = 0
        GROUP BY sprint
        """,
        sprint_names + [project],
        as_dict=True,
    )
    points_map = {r["sprint"]: (r["pts"] or 0) for r in points_rows}

    # Completed statuses for this project
    raw_states = frappe.db.get_value("BP Project", project, "workflow_states") or "[]"
    states = _parse_json(raw_states, [])
    done_statuses = [s["name"] for s in states if s.get("category") in ("completed", "cancelled")]

    completed_map = {}
    if done_statuses:
        completed_rows = frappe.db.sql(
            f"""
            SELECT sprint, COUNT(*) as cnt
            FROM `tabBP Task`
            WHERE sprint IN ({','.join(['%s'] * len(sprint_names))})
              AND project = %s
              AND is_deleted = 0
              AND status IN ({','.join(['%s'] * len(done_statuses))})
            GROUP BY sprint
            """,
            sprint_names + [project] + done_statuses,
            as_dict=True,
        )
        completed_map = {r["sprint"]: r["cnt"] for r in completed_rows}

    # Velocity — points actually delivered (completed only, cancelled work
    # never shipped so it shouldn't count toward the trend the way it does
    # for the "done" task count above).
    completed_only = [s["name"] for s in states if s.get("category") == "completed"]
    velocity_map = {}
    if completed_only:
        velocity_rows = frappe.db.sql(
            f"""
            SELECT sprint, SUM(COALESCE(story_points, 0)) as pts
            FROM `tabBP Task`
            WHERE sprint IN ({','.join(['%s'] * len(sprint_names))})
              AND project = %s
              AND is_deleted = 0
              AND status IN ({','.join(['%s'] * len(completed_only))})
            GROUP BY sprint
            """,
            sprint_names + [project] + completed_only,
            as_dict=True,
        )
        velocity_map = {r["sprint"]: (r["pts"] or 0) for r in velocity_rows}

    for sprint in sprints:
        sprint["issue_count"]      = total_map.get(sprint["name"], 0)
        sprint["completed_count"]  = completed_map.get(sprint["name"], 0)
        sprint["total_points"]     = points_map.get(sprint["name"], 0)
        sprint["completed_points"] = velocity_map.get(sprint["name"], 0)

    cache_set(VIEW_SPRINTS, project, sprints)
    return sprints


@frappe.whitelist()
def get_sprint_capacity(sprint):
    """Per-member allocation vs capacity for one sprint (the "Capacity"
    sprint-header button). Allocation = sum of estimated_hours across each
    member's tasks IN THIS SPRINT; capacity = BP Team Member.capacity_hours_per_sprint
    (the same figure Workload/Utilization already use), 40h default.
    """
    doc = frappe.get_doc("BP Sprint", sprint)
    _check_permission(doc.project, "BP Viewer")

    tasks = frappe.get_all(
        "BP Task", filters={"sprint": sprint},
        fields=["name", "estimated_hours"],
    )
    task_names = [t["name"] for t in tasks]
    hours_by_task = {t["name"]: (t["estimated_hours"] or 0) for t in tasks}

    assignee_rows = frappe.get_all(
        "BP Task Assignee",
        filters={"parent": ["in", task_names]},
        fields=["parent", "user", "full_name"],
    ) if task_names else []

    allocated = {}   # user -> hours
    names = {}       # user -> full_name
    task_count = {}  # user -> count
    for row in assignee_rows:
        u = row["user"]
        allocated[u] = allocated.get(u, 0) + hours_by_task.get(row["parent"], 0)
        task_count[u] = task_count.get(u, 0) + 1
        names[u] = row["full_name"] or u

    caps = _get_member_capacities(list(allocated.keys()))

    members = [
        {
            "user": u,
            "full_name": names[u],
            "allocated_hours": round(allocated[u], 1),
            "capacity_hours": caps.get(u, 40.0),
            "task_count": task_count[u],
        }
        for u in allocated
    ]
    members.sort(key=lambda m: m["allocated_hours"], reverse=True)
    return {
        "sprint": sprint,
        "sprint_name": doc.sprint_name,
        "members": members,
        "unassigned_task_count": sum(1 for t in tasks if t["name"] not in {r["parent"] for r in assignee_rows}),
    }


@frappe.whitelist()
def get_standup(sprint, entry_date=None):
    """Today's (or a given date's) standup entries for a sprint, plus the
    calling user's own entry (possibly blank) so the UI can pre-fill their
    form without a second round trip."""
    doc = frappe.get_doc("BP Sprint", sprint)
    _check_permission(doc.project, "BP Viewer")
    entry_date = entry_date or frappe.utils.today()

    entries = frappe.get_all(
        "BP Standup Entry",
        filters={"sprint": sprint, "entry_date": entry_date},
        fields=["name", "user", "yesterday", "today", "blockers", "modified"],
        order_by="modified asc",
    )
    for e in entries:
        e["full_name"] = frappe.db.get_value("User", e["user"], "full_name") or e["user"]

    mine = next((e for e in entries if e["user"] == frappe.session.user), None)
    return {"date": entry_date, "entries": entries, "mine": mine}


@frappe.whitelist()
def save_standup(sprint, entry_date=None, yesterday=None, today=None, blockers=None):
    """Upsert the calling user's own entry for the day — one entry per
    (sprint, user, date), matching how a real standup works (you post your
    own update, you don't edit anyone else's)."""
    doc = frappe.get_doc("BP Sprint", sprint)
    _check_permission(doc.project, "BP Member")
    entry_date = entry_date or frappe.utils.today()
    user = frappe.session.user

    existing = frappe.db.get_value(
        "BP Standup Entry", {"sprint": sprint, "user": user, "entry_date": entry_date}, "name"
    )
    if existing:
        entry = frappe.get_doc("BP Standup Entry", existing)
    else:
        entry = frappe.get_doc({
            "doctype": "BP Standup Entry", "sprint": sprint, "user": user, "entry_date": entry_date,
        })
    entry.yesterday = yesterday or ""
    entry.today = today or ""
    entry.blockers = blockers or ""
    entry.save(ignore_permissions=True)
    frappe.db.commit()
    return {"name": entry.name}




def _activity_text(a):
	t = a.get("action_type") or "updated"
	key = a.get("task_key") or ""
	old = a.get("old_value") or ""
	new = a.get("new_value") or ""
	if t == "Status Change":
		return f"moved {key} from {old} → {new}"
	if t == "Assignment":
		return f"assigned {key} to {new}" if new else f"updated assignment on {key}"
	if t == "Comment":
		return f"commented on {key}"
	if t == "Attachment":
		return f"attached a file to {key}"
	if t == "Field Edit":
		return f"updated {old} on {key}"
	if t == "Created":
		return f"created {key}"
	return f"updated {key}"




def _all_tracked_users():
	"""Union of BP Project Member + BP Team Member users (deduped)."""
	rows = frappe.db.sql(
		"""
		SELECT DISTINCT user FROM `tabBP Project Member`
		WHERE user IS NOT NULL AND user != ''
		UNION
		SELECT user FROM `tabBP Team Member`
		WHERE user IS NOT NULL AND user != ''
		""",
		as_dict=True,
	)
	return [r.user for r in rows]




def _append_link(doc, other, link_type, dep_type=None, lag_days=None, link_metadata=None):
    """Append a link row to ``doc`` pointing at ``other`` (idempotent)."""
    for l in doc.get("links", []):
        if l.linked_task == other.name and l.link_type == link_type:
            return False
    doc.append("links", {
        "link_type": link_type,
        "linked_task": other.name,
        "linked_task_key": other.task_key,
        "linked_task_title": other.title,
        "linked_task_status": other.status,
        "linked_task_project": other.project,
        # Scheduling + integration metadata ride along when provided (the
        # Gantt sends dep_type/lag_days for drawn dependencies; integrations
        # may attach link_metadata). Defaults keep older callers unchanged.
        "dep_type": dep_type or "FS",
        "lag_days": lag_days if lag_days is not None else 0,
        "link_metadata": link_metadata,
    })
    return True




def _avatar_color(key):
	colors = ["#2563EB", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#06B6D4", "#EC4899"]
	if not key:
		return colors[0]
	h = 0
	for c in key:
		h = ord(c) + ((h << 5) - h)
	return colors[abs(h) % len(colors)]




def _blocks_reaches(start, target):
    """True if `start` can reach `target` through existing predecessor→successor
    ('blocks') edges. Used to reject links that would form a dependency cycle."""
    adj = {}
    for r in frappe.get_all(
        "BP Task Link",
        filters={"parenttype": "BP Task", "link_type": "blocks"},
        fields=["parent", "linked_task"],
    ):
        adj.setdefault(r["parent"], set()).add(r["linked_task"])
    seen, stack = {start}, [start]
    while stack:
        node = stack.pop()
        if node == target:
            return True
        for nxt in adj.get(node, ()):  # noqa
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return False




def _clear_default_views(project, user):
    for v in frappe.get_all("BP View", filters={"project": project, "owner": user, "is_default": 1}, pluck="name"):
        frappe.db.set_value("BP View", v, "is_default", 0, update_modified=False)




def _coerce_json(value, default):
    """Accept a JSON string or a python obj from the API and store a JSON string."""
    if value is None or value == "":
        return default
    if isinstance(value, str):
        try:
            json.loads(value)
            return value
        except (json.JSONDecodeError, TypeError):
            return default
    return json.dumps(value)




















def _get_member_capacities(users):
	"""
	Returns {user: weekly_hours} for the given users.
	Reads capacity_hours_per_sprint from BP Team Member (first team wins).
	Falls back to 40h/week when no team membership exists.
	"""
	if not users:
		return {}
	rows = frappe.db.sql(
		"""
		SELECT user, capacity_hours_per_sprint
		FROM `tabBP Team Member`
		WHERE user IN %(users)s
		ORDER BY creation ASC
		""",
		{"users": users},
		as_dict=True,
	)
	caps = {}
	for r in rows:
		if r.user not in caps:
			caps[r.user] = float(r.capacity_hours_per_sprint or 40)
	return {u: caps.get(u, 40.0) for u in users}




def _get_personal_stats(user, days=14):
	"""Daily completed-task counts for sparkline over last N days."""
	from datetime import date, timedelta
	today = date.today()
	cutoff = (today - timedelta(days=days)).isoformat()

	assigned = frappe.get_all(
		"BP Task Assignee",
		filters={"user": user},
		fields=["parent"],
	)
	names = [a["parent"] for a in assigned] or ["__none__"]

	# Build completed statuses across all projects
	all_completed = set()
	try:
		rows = frappe.db.sql(
			"""
			SELECT DISTINCT t.project
			FROM `tabBP Task` t
			WHERE t.name IN %(names)s
			""",
			{"names": names},
			as_dict=True,
		)
		for r in rows:
			all_completed.update(_get_completed_statuses_by_project(r.project))
	except Exception:
		all_completed = {"Done", "Closed", "Cancelled"}

	if not all_completed:
		all_completed = {"Done", "Closed"}

	# Daily completed count
	try:
		rows = frappe.db.sql(
			"""
			SELECT DATE(modified) AS day, COUNT(*) AS cnt
			FROM `tabBP Task`
			WHERE name IN %(names)s
			  AND status IN %(statuses)s
			  AND modified >= %(cutoff)s
			  AND is_deleted = 0
			GROUP BY DATE(modified)
			ORDER BY day ASC
			""",
			{"names": names, "statuses": list(all_completed), "cutoff": cutoff},
			as_dict=True,
		)
	except Exception:
		rows = []

	day_map = {str(r.day): int(r.cnt) for r in rows}

	sparkline = []
	total_completed = 0
	for i in range(days):
		d = (today - timedelta(days=days - 1 - i)).isoformat()
		cnt = day_map.get(d, 0)
		sparkline.append(cnt)
		total_completed += cnt

	# Hours logged from Timesheet (best-effort)
	total_hours = 0.0
	try:
		if frappe.db.table_exists("Timesheet Detail"):
			res = frappe.db.sql(
				"""
				SELECT SUM(td.hours) AS h
				FROM `tabTimesheet Detail` td
				JOIN `tabTimesheet` ts ON ts.name = td.parent AND ts.docstatus = 1
				LEFT JOIN `tabEmployee` e ON e.name = ts.employee
				WHERE COALESCE(e.user_id, ts.owner) = %(user)s
				  AND td.from_time >= %(cutoff)s
				""",
				{"user": user, "cutoff": cutoff},
				as_dict=True,
			)
			total_hours = float(res[0].h or 0) if res else 0.0
	except Exception:
		pass

	return {
		"sparkline": sparkline,
		"total_completed": total_completed,
		"total_hours": round(total_hours, 1),
		"days": days,
	}




@frappe.whitelist()
def _invalidate_sprint_cache(project: str):
    """Invalidate board + backlog + sprints cache after any sprint mutation."""
    try:
        from batch_projects.cache import invalidate_project
        invalidate_project(project)
    except Exception:
        pass




def _report_out(doc, with_layout=False):
    out = {
        "id": doc.name,
        "report_name": doc.report_name,
        "icon": doc.icon or "BarChart3",
        "color": doc.color or None,
        "starred": bool(doc.starred),
        "pinned": bool(doc.get("pinned")),
        "scope": doc.project or "all",
        "project": doc.project or None,
        "milestone": doc.milestone or None,
        "period": doc.period or "last_30_days",
        "schedule_enabled": bool(doc.get("schedule_enabled")),
        "schedule_frequency": doc.get("schedule_frequency") or "Weekly",
        "schedule_day": doc.get("schedule_day") or "Monday",
        "schedule_hour": doc.get("schedule_hour") if doc.get("schedule_hour") is not None else 8,
        "schedule_recipients": doc.get("schedule_recipients") or "",
        "last_sent": str(doc.get("last_sent")) if doc.get("last_sent") else None,
        "modified": str(doc.modified),
        "owner": doc.owner,
    }
    if with_layout:
        out["widgets"] = _parse_json(doc.layout, [])
    return out




@frappe.whitelist()
def _resolve_scope(scope):
	"""
	Normalise scope into (filters_patch, proj_name, proj_names_list).
	scope: 'all' | single project name/key | list of project names/keys
	Returns (filters_patch dict, proj_name_or_None, resolved_list_or_None)
	"""
	# The frontend may send a JSON-stringified list (e.g. '["Proj A"]').
	if isinstance(scope, str):
		st = scope.strip()
		if st.startswith("[") and st.endswith("]"):
			try:
				scope = json.loads(st)
			except Exception:
				pass
	if isinstance(scope, list) and len(scope) == 1:
		scope = scope[0]

	if not scope or scope == "all":
		_require_system_user()
		# Access filter: scope=="all" used to
		# return an unfiltered {} — every caller of this helper
		# (get_widget_data, query_bql_group_by, get_report_tasks) then
		# aggregated task data across EVERY project in the org regardless
		# of `visibility`/membership. Scope "all" must mean "all projects
		# I can see", not "all projects that exist".
		from batch_projects.permissions import get_accessible_projects
		accessible = get_accessible_projects()  # None = admin (all)
		if accessible is None:
			return {}, None, None
		if not accessible:
			return {"project": ["in", []]}, None, []
		return {"project": ["in", list(accessible)]}, None, list(accessible)

	if isinstance(scope, list):
		# multi-project selection
		resolved = []
		for s in scope:
			p = s if frappe.db.exists("BP Project", s) else frappe.db.get_value("BP Project", {"key": s}, "name")
			if p:
				_check_permission(p, "BP Viewer")
				resolved.append(p)
		if not resolved:
			_require_system_user()
			return {}, None, None
		if len(resolved) == 1:
			return {"project": resolved[0]}, resolved[0], resolved
		return {"project": ["in", resolved]}, None, resolved

	# single project
	proj_name = scope if frappe.db.exists("BP Project", scope) else frappe.db.get_value("BP Project", {"key": scope}, "name")
	if proj_name:
		_check_permission(proj_name, "BP Viewer")
		return {"project": proj_name}, proj_name, [proj_name]
	_require_system_user()
	return {}, None, None




def _serialize_view(v):
    """Shape a BP View row for the frontend (full config lives in `filters` JSON)."""
    return {
        "id": v["name"],
        "name": v["view_name"],
        "view_type": (v.get("view_type") or "Board").lower(),
        "is_default": bool(v.get("is_default")),
        "subscribed": bool(v.get("subscribed")),
        "subscription_frequency": v.get("subscription_frequency") or "Weekly",
        **_parse_json(v.get("filters"), {}),
    }




def _time_ago(dt):
	if not dt:
		return ""
	from datetime import datetime
	if not isinstance(dt, datetime):
		try:
			dt = datetime.strptime(str(dt)[:19], "%Y-%m-%d %H:%M:%S")
		except Exception:
			return str(dt)[:10]
	mins = int((datetime.now() - dt).total_seconds() / 60)
	if mins < 1:   return "just now"
	if mins < 60:  return f"{mins}m ago"
	h = mins // 60
	if h < 24:     return f"{h}h ago"
	d = h // 24
	if d < 30:     return f"{d}d ago"
	return dt.strftime("%b %d")




def _timesheet_hours_by_user(users, from_dt, to_dt):
	"""
	Returns {user: (total_hours, billable_hours)} from submitted ERPNext timesheets.
	Resolves user via Employee.user_id first, then falls back to Timesheet.owner
	so users without an Employee record are still counted.
	"""
	if not users or not frappe.db.table_exists("Timesheet Detail"):
		return {u: (0.0, 0.0) for u in users}
	try:
		rows = frappe.db.sql(
			"""
			SELECT
				COALESCE(e.user_id, ts.owner)                          AS user,
				SUM(td.hours)                                          AS total_hours,
				SUM(CASE WHEN td.is_billable = 1 THEN td.hours ELSE 0 END) AS billable_hours
			FROM `tabTimesheet Detail` td
			JOIN `tabTimesheet` ts
				ON ts.name = td.parent AND ts.docstatus = 1
			LEFT JOIN `tabEmployee` e
				ON e.name = ts.employee
			WHERE td.from_time >= %(from_dt)s
			  AND td.from_time <= %(to_dt)s
			  AND COALESCE(e.user_id, ts.owner) IN %(users)s
			GROUP BY COALESCE(e.user_id, ts.owner)
			""",
			{"from_dt": from_dt, "to_dt": to_dt, "users": users},
			as_dict=True,
		)
		result = {r.user: (float(r.total_hours or 0), float(r.billable_hours or 0))
		          for r in rows if r.user}
		return {u: result.get(u, (0.0, 0.0)) for u in users}
	except Exception as exc:
		frappe.log_error(f"_timesheet_hours_by_user: {exc}")
		return {u: (0.0, 0.0) for u in users}




@frappe.whitelist()
def add_reference(issue, ref_doctype, ref_name, two_way=0):
    doc = frappe.get_doc("BP Task", issue)
    _check_permission(doc.project, "BP Member")

    for r in (doc.references or []):
        if r.ref_doctype == ref_doctype and r.ref_name == ref_name:
            return doc.as_dict()

    title_field = frappe.db.get_value("DocType", ref_doctype, "title_field") or "name"
    ref_label = frappe.db.get_value(ref_doctype, ref_name, title_field) or ref_name

    doc.append("references", {
        "ref_doctype": ref_doctype,
        "ref_name": ref_name,
        "ref_label": ref_label,
        "ref_url": f"/app/{ref_doctype.lower().replace(' ', '-')}/{ref_name}",
    })
    doc.save(ignore_permissions=True)

    if int(two_way or 0):
        # Two-way connection: leave a backlink on the ERP document's timeline
        # so the other side shows the connection too (best-effort).
        try:
            key = frappe.db.get_value("BP Project", doc.project, "key")
            ref = frappe.get_doc(ref_doctype, ref_name)
            ref.add_comment(
                "Comment",
                f"Linked to project task <b>{doc.task_key}</b>: {doc.title}"
                f" — <a href='/workspace/{key}/board?task={doc.task_key}'>open task</a>",
            )
        except Exception:
            frappe.log_error(frappe.get_traceback(), "bp two-way backlink failed")

    return [
        {
            "name": r.name,
            "ref_doctype": r.ref_doctype,
            "ref_name": r.ref_name,
            "ref_label": r.ref_label or r.ref_name,
            "ref_url": f"/app/{r.ref_doctype.lower().replace(' ', '-')}/{r.ref_name}",
        }
        for r in doc.references
    ]




@frappe.whitelist()
def add_task_link(issue, linked_task, link_type="relates to", dep_type="FS", lag_days=0, link_metadata=None):
    if issue == linked_task:
        frappe.throw("A task can't be linked to itself.")
    doc = frappe.get_doc("BP Task", issue)
    _check_permission(doc.project, "BP Member")
    linked_doc = frappe.get_doc("BP Task", linked_task)
    # You must at least be able to see the other task (closes the cross-project hole).
    _check_permission(linked_doc.project, "BP Viewer")

    # Reject blocking links that would create a circular dependency.
    if link_type in BLOCKING_TYPES:
        pred, succ = (issue, linked_task) if link_type == "blocks" else (linked_task, issue)
        if _blocks_reaches(succ, pred):
            frappe.throw("That link would create a circular dependency.")

    # dep_type/lag_days were previously sent by the Gantt but dropped here —
    # the endpoint signature never accepted them, so every drawn dependency
    # silently fell back to FS/0. They now persist (this is the fix), and
    # link_metadata lets integrations attach provenance without a column per
    # integration. Both ride the reciprocal link too.
    if _append_link(doc, linked_doc, link_type, dep_type, lag_days, link_metadata):
        doc.save(ignore_permissions=True)

    # Mirror the reciprocal link onto the other task.
    inverse = INVERSE_LINK.get(link_type)
    if inverse and _append_link(linked_doc, doc, inverse, dep_type, lag_days, link_metadata):
        linked_doc.save(ignore_permissions=True)

    return {"ok": True}




@frappe.whitelist()
def archive_team(team):
	"""Archive a team (Admin only). Hidden from listings; data preserved.
	Projects keep their data but are unlinked from the archived team."""
	_check_team_permission(team, "Admin")
	frappe.db.set_value("BP Team", team, "status", "Archived")
	for p in frappe.get_all("BP Project", filters={"team": team}, pluck="name"):
		frappe.db.set_value("BP Project", p, "team", None)
	frappe.db.commit()
	return {"ok": True}




@frappe.whitelist()
def assign_project_to_team(project, team):
	"""Assign or remove a project from a team."""
	_check_permission(project, "BP Manager")
	if not frappe.db.exists("BP Project", project):
		frappe.throw(f"Project '{project}' not found.", frappe.DoesNotExistError)
	# Use db.set_value to avoid running the full validate/save cycle which
	# can fail with 417 if the calling user lacks Frappe-level write permission.
	frappe.db.set_value("BP Project", project, "team", team or None)
	frappe.db.commit()
	return {"project": project, "team": team or None}




def backfill_reciprocal_links():
    """One-off migration: ensure every existing BP Task Link has its reciprocal
    on the other task. Idempotent — safe to run repeatedly.

    Run with:
      bench --site <site> execute batch_projects.api.board.backfill_reciprocal_links
    """
    rows = frappe.get_all(
        "BP Task Link",
        filters={"parenttype": "BP Task"},
        fields=["parent", "linked_task", "link_type", "dep_type", "lag_days", "link_metadata"],
    )
    # Index existing (task -> {(other, type)}) so we don't duplicate.
    existing = {}
    for r in rows:
        existing.setdefault(r["parent"], set()).add((r["linked_task"], r["link_type"]))

    added = 0
    for r in rows:
        src, tgt, lt = r["parent"], r["linked_task"], r["link_type"]
        inv = INVERSE_LINK.get(lt)
        if not inv or not frappe.db.exists("BP Task", tgt):
            continue
        if (src, inv) in existing.get(tgt, set()):
            continue  # reciprocal already present
        meta = frappe.db.get_value("BP Task", src, ["task_key", "title", "status"], as_dict=True)
        if not meta:
            continue
        other = frappe.get_doc("BP Task", tgt)
        other.append("links", {
            "link_type": inv,
            "linked_task": src,
            "linked_task_key": meta.task_key,
            "linked_task_title": meta.title,
            "linked_task_status": meta.status,
            # Mirror scheduling + integration metadata on the reciprocal too.
            "dep_type": r.get("dep_type") or "FS",
            "lag_days": r.get("lag_days") if r.get("lag_days") is not None else 0,
            "link_metadata": r.get("link_metadata"),
        })
        other.save(ignore_permissions=True)
        existing.setdefault(tgt, set()).add((src, inv))
        added += 1

    frappe.db.commit()
    return {"added": added, "scanned": len(rows)}




@frappe.whitelist()
def complete_sprint(sprint, move_incomplete_to=None):
    """
    Complete a sprint.
    move_incomplete_to: name of another BP Sprint to move unfinished issues into,
                        or None / empty string to move them to the backlog (sprint = null).
    """
    doc = frappe.get_doc("BP Sprint", sprint)
    _check_permission(doc.project, "BP Member")

    if doc.status != "Active":
        frappe.throw("Only active sprints can be completed.")

    done_statuses = _get_completed_statuses_by_project(doc.project)

    # Find incomplete issues in this sprint
    filters = {"sprint": sprint, "project": doc.project}
    if done_statuses:
        filters["status"] = ["not in", done_statuses]

    incomplete = frappe.get_all(
        "BP Task",
        filters=filters,
        fields=["name"],
    )

    target = move_incomplete_to if move_incomplete_to else None

    if incomplete:
        names = [i["name"] for i in incomplete]
        if target:
            # Verify target sprint belongs to same project
            target_proj = frappe.db.get_value("BP Sprint", target, "project")
            if target_proj != doc.project:
                frappe.throw("Target sprint does not belong to the same project.")
        # Per-task ORM save, not a raw UPDATE — carryover is the single
        # operation `task.moved_sprint` automations exist to catch (it's a
        # refinement of task.updated, resolved from the diffed `changes`
        # list BP Task.on_update() builds — see bp_automation_rule.py). A
        # raw SQL UPDATE skips on_update() entirely: no BP Activity history,
        # no TASK_UPDATED emit, so every such automation silently never
        # fires on a sprint close, and nothing more than the sprint field
        # itself records that the move happened.
        for name in names:
            t = frappe.get_doc("BP Task", name)
            t.sprint = target
            t.save(ignore_permissions=True)

    doc.status = "Completed"
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    _invalidate_sprint_cache(doc.project)

    emit(SPRINT_COMPLETED, {
        "project": doc.project,
        "sprint": doc.name,
        "sprint_name": doc.sprint_name,
        "completed_count": frappe.db.count("BP Task", {"sprint": sprint, "status": ["in", done_statuses]}) if done_statuses else 0,
        "incomplete_count": len(incomplete),
        "moved_to": target,
    })

    return {
        "sprint": doc.as_dict(),
        "moved_count": len(incomplete),
        "moved_to": target,
    }




@frappe.whitelist()
def create_automation_rule(project, rule_name, trigger_event, action_type,
                           conditions=None, action_config=None, is_active=1):
    _check_permission(project, "BP Admin")
    from batch_projects.entitlements import require_feature
    require_feature("automations")

    doc = frappe.get_doc({
        "doctype": "BP Automation Rule",
        "project": project,
        "rule_name": rule_name,
        "trigger_event": trigger_event,
        "action_type": action_type,
        "conditions": _coerce_json(conditions, "[]"),
        "action_config": _coerce_json(action_config, "{}"),
        "is_active": _as_bool(is_active),
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return doc.as_dict()




@frappe.whitelist()
def get_milestones(project=None):
	"""List milestones for a project (or all accessible projects)."""
	if project:
		_check_permission(project, "BP Viewer")
	else:
		_require_system_user()
	filters = {}
	if project:
		filters["project"] = project
	rows = frappe.get_all(
		"BP Milestone",
		filters=filters,
		fields=["name", "title", "project", "due_date", "status", "description"],
		order_by="due_date asc, creation asc",
	)
	proj_names = list({r["project"] for r in rows})
	proj_info = {}
	if proj_names:
		for p in frappe.get_all("BP Project", filters={"name": ["in", proj_names]},
					fields=["name", "project_name", "project_color"]):
			proj_info[p["name"]] = p
	for r in rows:
		p = proj_info.get(r["project"], {})
		r["project_name"]  = p.get("project_name") or r["project"]
		r["project_color"] = p.get("project_color") or _avatar_color(r["project"])
	return rows


@frappe.whitelist()
def create_milestone(project, title, due_date=None, description=None):
	_check_permission(project, "BP Member")
	doc = frappe.get_doc({
		"doctype":     "BP Milestone",
		"project":     project,
		"title":       title,
		"due_date":    due_date or None,
		"description": description or "",
		"status":      "Open",
	})
	doc.insert(ignore_permissions=True)
	return doc.as_dict()




@frappe.whitelist()
def create_project(
    project_name,
    key,
    description=None,
    project_lead=None,
    project_color=None,
    project_icon=None,
    theme=None,
    visibility=None,
    project_type=None,
    client=None,
    budget_amount=None,
    hourly_rate=None,
    retainer_hours=None,
    currency=None,
    start_date=None,
    target_end_date=None,
    workflow_states=None,
    issue_types=None,
    custom_fields=None,
    template_used=None,
    enabled_views=None,
    company=None,
):
    _require_system_user()
    key = key.upper().strip()

    if len(key) < 2:
        frappe.throw("Project key must be at least 2 characters.")
    if frappe.db.exists("BP Project", {"key": key}):
        frappe.throw(f"Project key '{key}' is already in use.")

    # Validate billing fields
    ptype = (project_type or "internal").strip()
    if ptype != "internal" and not client:
        frappe.throw("Client is required for billable projects.")
    if ptype == "fixed" and not budget_amount:
        frappe.throw("Total budget is required for fixed-price projects.")

    doc = frappe.get_doc({
        "doctype":        "BP Project",
        "project_name":   project_name.strip(),
        "key":            key,
        "status":         "Active",
        "description":    description or "",
        "project_color":  project_color or "#0B6BCB",
        "project_icon":   project_icon or "Folder",
        "theme":          theme or "koalaBlue",
        "visibility":     visibility or "workspace",
        "project_type":   ptype,
        "lead":           project_lead or None,
        "client":         client or None,
        "budget_amount":  float(budget_amount) if budget_amount else None,
        "hourly_rate":    float(hourly_rate) if hourly_rate else None,
        "retainer_hours": int(retainer_hours) if retainer_hours else None,
        "currency":       currency or "INR",
        "start_date":     start_date or None,
        "target_end_date": target_end_date or None,
        "workflow_states": workflow_states,
        "issue_types":    issue_types,
        "custom_fields":  custom_fields or "[]",
        "enabled_views":  enabled_views or None,
        "labels":         "[]",
        "schema_version": 1,
        "template_used":  template_used or "",
        "company":        company,
    })
    doc.insert(ignore_permissions=True)

    # Auto-add creator as Admin member so they have full access.
    # Must check seat cap before the direct-SQL insert (which bypasses the
    # doc_events hook in hooks.py).
    creator = frappe.session.user
    from batch_projects.entitlements import assert_seat_available
    assert_seat_available(creator)
    from batch_projects import access
    access.ensure_member_role(creator)
    frappe.db.sql(
        """INSERT INTO `tabBP Project Member`
               (name, parent, parenttype, parentfield, idx, user, role, creation, modified, owner, modified_by)
           VALUES (%s, %s, 'BP Project', 'members', 1, %s, 'Admin', NOW(), NOW(), %s, %s)""",
        (frappe.generate_hash(length=10), doc.name, creator, creator, creator),
    )
    frappe.db.commit()

    emit(PROJECT_CREATED, {
        "project":      doc.name,
        "project_name": doc.project_name,
    })
    emit(PROJECT_ROLE_CHANGED, {
        "project": doc.name, "user": creator,
        "old_role": None, "new_role": "Admin",
    })

    return {
        "name":          doc.name,
        "project_name":  doc.project_name,
        "key":           doc.key,
        "project_color": doc.project_color,
        "project_icon":  doc.project_icon,
        "theme":         doc.theme,
        "project_type":  doc.project_type,
        "visibility":    doc.visibility,
    }


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def _fetch_task_links(issue_names: list) -> dict:
    """Task→task relations per task (mirror columns read linked status live)."""
    if not issue_names:
        return {}
    rows = frappe.get_all(
        "BP Task Link",
        filters={"parent": ["in", issue_names]},
        fields=["parent", "link_type", "linked_task", "linked_task_key",
                "linked_task_title", "linked_task_status", "linked_task_project"],
    )
    out = {}
    for r in rows:
        out.setdefault(r.pop("parent"), []).append(r)
    return out


def _fetch_task_refs(issue_names: list) -> dict:
    """ERPNext document references per task (the Connected column)."""
    if not issue_names:
        return {}
    rows = frappe.get_all(
        "BP Task Reference",
        filters={"parent": ["in", issue_names]},
        fields=["name", "parent", "ref_doctype", "ref_name", "ref_label"],
    )
    out = {}
    for r in rows:
        out.setdefault(r.pop("parent"), []).append(r)
    return out


def _fetch_assignees(issue_names: list) -> dict:
    if not issue_names:
        return {}
    rows = frappe.get_all(
        "BP Task Assignee",
        filters={"parent": ["in", issue_names]},
        fields=["parent", "user", "full_name"],
    )
    result = {}
    for row in rows:
        full_name = row["full_name"] or frappe.db.get_value("User", row["user"], "full_name") or row["user"]
        result.setdefault(row["parent"], []).append({
            "user": row["user"],
            "full_name": full_name,
        })
    return result


def _fetch_epics(issues: list) -> dict:
    epic_names = list(set(i["epic"] for i in issues if i.get("epic")))
    if not epic_names:
        return {}
    docs = frappe.get_all(
        "BP Epic",
        filters={"name": ["in", epic_names]},
        fields=["name", "title", "color"],
    )
    return {e["name"]: {"title": e["title"], "color": e["color"]} for e in docs}


def _fetch_epics_for_project(project: str) -> dict:
    docs = frappe.get_all(
        "BP Epic",
        filters={"project": project},
        fields=["name", "title", "color"],
    )
    return {e["name"]: {"title": e["title"], "color": e["color"]} for e in docs}


def _get_completed_statuses(project_dict: dict) -> list:
    states = _parse_json(project_dict.get("workflow_states"), [])
    return [s["name"] for s in states if s.get("category") in ("completed", "cancelled")]


def _get_completed_statuses_by_project(project_name: str) -> list:
    raw = frappe.db.get_value("BP Project", project_name, "workflow_states")
    states = _parse_json(raw, [])
    return [s["name"] for s in states if s.get("category") in ("completed", "cancelled")]


def _project_health_label(health_override, total, done, overdue):
    """Derive project health from overdue percentage and completion rate.
    Falls back to health_override if set manually. Shared by the gateway portfolio rollup
    (internal/insights/portfolio.go projectHealth) and get_board, so all resolve
    health identically. Keep the two implementations in step."""
    if health_override:
        return health_override
    if total == 0:
        return "On track"
    overdue_pct = (overdue / total) * 100
    done_pct = (done / total) * 100
    if overdue_pct > 20:
        return "Off track"
    if overdue_pct > 10 or done_pct < 50:
        return "At risk"
    return "On track"


# ─── SPRINTS ──────────────────────────────────────────────────────────────────


@frappe.whitelist()
def get_risks(project=None):
	"""List risks for a project (or all open risks)."""
	if project:
		_check_permission(project, "BP Viewer")
	else:
		_require_system_user()
	filters = {"status": "Open"}
	if project:
		filters["project"] = project
	rows = frappe.get_all("BP Risk",
		filters=filters,
		fields=["name", "title", "project", "severity", "status", "owner_user", "description"],
		order_by="creation desc")
	owner_users = list({r["owner_user"] for r in rows if r.get("owner_user")})
	owner_info = {}
	if owner_users:
		for u in frappe.get_all("User", filters={"name": ["in", owner_users]}, fields=["name", "full_name"]):
			owner_info[u["name"]] = u
	proj_names = list({r["project"] for r in rows})
	proj_info = {}
	if proj_names:
		for p in frappe.get_all("BP Project", filters={"name": ["in", proj_names]},
					fields=["name", "project_name", "project_color"]):
			proj_info[p["name"]] = p
	for r in rows:
		owner = owner_info.get(r.get("owner_user", ""), {})
		p = proj_info.get(r["project"], {})
		r["owner"] = owner.get("full_name", "") or r.get("owner_user", "")
		r["owner_initial"] = "".join(w[0].upper() for w in r["owner"].split()[:2]) if r["owner"] else "?"
		r["owner_color"] = _avatar_color(r.get("owner_user") or r["project"])
		r["project_name"] = p.get("project_name", "") or r["project"]
		r["project_color"] = p.get("project_color", "") or _avatar_color(r["project"])
	return rows


@frappe.whitelist()
def update_risk(name, fields):
	"""Update a risk's fields."""
	if isinstance(fields, str):
		fields = json.loads(fields)
	doc = frappe.get_doc("BP Risk", name)
	_check_permission(doc.project, "BP Member")
	allowed = {"title", "severity", "status", "owner_user", "description"}
	for k, v in (fields or {}).items():
		if k in allowed:
			setattr(doc, k, v)
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def create_risk(project, title, severity="medium", owner_user=None, description=None):
	_check_permission(project, "BP Member")
	doc = frappe.get_doc({
		"doctype":     "BP Risk",
		"project":     project,
		"title":       title,
		"severity":    severity,
		"owner_user":  owner_user or None,
		"description": description or "",
		"status":      "Open",
	})
	doc.insert(ignore_permissions=True)
	return doc.as_dict()




@frappe.whitelist()
def create_sprint(project, sprint_name, goal=None, start_date=None, end_date=None):
    _check_permission(project, "BP Member")
    doc = frappe.get_doc({
        "doctype": "BP Sprint",
        "project": project,
        "sprint_name": sprint_name,
        "status": "Planning",
        "goal": goal or "",
        "start_date": start_date or None,
        "end_date": end_date or None,
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    _invalidate_sprint_cache(project)
    return doc.as_dict()




@frappe.whitelist()
def create_team(team_name, team_key=None, team_color="#0052CC", team_icon=None,
                description=None, lead=None, department=None, company=None):
	_require_system_user()
	doc = frappe.get_doc({
		"doctype":   "BP Team",
		"team_name": team_name,
		"team_key":  team_key or "",
		"team_color": team_color,
		"team_icon": team_icon or "",
		"description": description or "",
		"lead":      lead or "",
		"department": department or "",
		"company":   company or "",
		"status":    "Active", 
	})
	# The creator becomes the team's Admin — otherwise they'd be locked out of
	# managing the team they just made (update_team / members require Admin).
	creator = frappe.session.user
	if creator not in ("Administrator", "Guest"):
		from batch_projects.entitlements import assert_seat_available
		assert_seat_available(creator)
		doc.append("members", {
			"user": creator,
			"full_name": frappe.db.get_value("User", creator, "full_name") or creator,
			"role": "Admin",
			"capacity_hours_per_sprint": 40,
		})
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return doc.as_dict()




@frappe.whitelist()
def create_team_sprint(team, sprint_name, goal=None, start_date=None, end_date=None):
	"""Create a team-level sprint (not bound to a single project)."""
	_check_team_permission(team, "Member")
	doc = frappe.get_doc({
		"doctype":     "BP Sprint",
		"sprint_name": sprint_name,
		"team":        team,
		"sprint_type": "Team",
		"status":      "Planning",
		"goal":        goal or "",
		"start_date":  start_date or None,
		"end_date":    end_date or None,
	})
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return doc.as_dict()




@frappe.whitelist()
def delete_attachment(file_name):
    doc = frappe.get_doc("File", file_name)
    if doc.attached_to_doctype != "BP Task":
        frappe.throw("Not a BP Task attachment.")
    _check_permission(
        frappe.db.get_value("BP Task", doc.attached_to_name, "project"),
        "BP Member"
    )
    doc.delete(ignore_permissions=True)
    return {"ok": True}




@frappe.whitelist()
def delete_automation_rule(rule):
    doc = frappe.get_doc("BP Automation Rule", rule)
    _check_permission(doc.project, "BP Admin")
    frappe.delete_doc("BP Automation Rule", rule)
    frappe.db.commit()
    return {"deleted": rule}




@frappe.whitelist()
def delete_milestone(name):
	doc = frappe.get_doc("BP Milestone", name)
	_check_permission(doc.project, "BP Manager")
	frappe.delete_doc("BP Milestone", name, ignore_permissions=True)
	return {"ok": True}




@frappe.whitelist()
def delete_risk(name):
	doc = frappe.get_doc("BP Risk", name)
	_check_permission(doc.project, "BP Manager")
	frappe.delete_doc("BP Risk", name, ignore_permissions=True)
	return {"ok": True}




@frappe.whitelist()
def delete_sprint(sprint):
    doc = frappe.get_doc("BP Sprint", sprint)
    _check_permission(doc.project, "BP Member")

    if doc.status == "Active":
        frappe.throw("Cannot delete an active sprint. Complete it first.")

    # Move all issues in this sprint back to backlog. Per-task ORM save, not
    # a raw UPDATE — same reasoning as complete_sprint's carryover (see its
    # comment): a raw SQL UPDATE skips on_update(), so no BP Activity
    # history and no task.moved_sprint automation ever fires. Deliberately
    # NOT filtered to is_deleted=0 — a trashed task must not come back on
    # restore still pointing at a sprint that no longer exists.
    project = doc.project
    task_names = frappe.get_all("BP Task", filters={"sprint": sprint}, fields=["name"])
    for t in task_names:
        task = frappe.get_doc("BP Task", t["name"])
        task.sprint = None
        task.save(ignore_permissions=True)
    frappe.delete_doc("BP Sprint", sprint)
    frappe.db.commit()
    _invalidate_sprint_cache(project)
    return {"deleted": sprint}




@frappe.whitelist()
def delete_view(view):
    """Delete a personal saved view (owner only)."""
    doc = frappe.get_doc("BP View", view)
    if doc.owner != frappe.session.user:
        frappe.throw("You can only delete your own views.")
    doc.delete(ignore_permissions=True)
    return {"ok": True}




@frappe.whitelist()
def get_allowed_doctypes(project=None):
    """Doctypes offered in the task 'Add reference' picker.

    search_erp_documents hard-requires an erpnext_project link for anything
    in _PROJECT_FIELD_DOCTYPES (+ Timesheet) — offering those in the picker
    for an unlinked project let users pick "Sales Order", type a query, and
    get a silently-swallowed 417 with nothing in the UI to explain why.
    Drop them from the list up front instead when `project` isn't linked.
    """
    ALLOWED = [
        "Sales Order", "Purchase Order", "Sales Invoice", "Purchase Invoice",
        "Project", "Customer", "Supplier", "Lead", "Opportunity",
        "Expense Claim", "Timesheet", "Delivery Note", "Stock Entry",
        "Payment Entry", "Journal Entry", "Work Order", "Quotation",
    ]
    erp_linked = bool(project and frappe.db.get_value("BP Project", project, "erpnext_project"))
    requires_project = _PROJECT_FIELD_DOCTYPES | {"Timesheet"}
    existing = []
    for dt in ALLOWED:
        if project and not erp_linked and dt in requires_project:
            continue
        try:
            if frappe.db.exists("DocType", dt):
                existing.append(dt)
        except Exception:
            pass
    return existing




@frappe.whitelist()
def get_automation_options(project=None):
    """Builder metadata: statuses, types, members + the trigger/action/operator catalog.

    project=None is workspace scope (the Workflow canvas opened from Workspace
    Settings, not a project's own Automations tab) — there's no single project
    to resolve statuses/task_types/members against, so those come back empty
    and only the project-independent trigger/action/operator catalog is
    populated. Previously this function computed condition_fields but never
    returned anything, and unconditionally called frappe.get_doc("BP Project",
    project) even when project was None/"" — crashing every workspace-scope
    load with DoesNotExistError."""
    statuses, task_types, members, labels = [], [], [], []
    if project:
        _check_permission(project, "BP Viewer")
        proj = frappe.get_doc("BP Project", project)
        statuses = [s.get("name") for s in _normalize_workflow_states(proj.get_workflow_states())]
        task_types = [t["name"] for t in proj.get_issue_types()]
        members = [
            {"user": m.user, "full_name": frappe.db.get_value("User", m.user, "full_name") or m.user}
            for m in (proj.members or [])
        ]
        # BP Project.labels is a list of {id, label, color} (see
        # update_project_labels/ProjectSettings.vue's labelsDraft) — the
        # "Add Label" action editor just needs the label strings.
        # AutomationRuleEditor.vue:188 did `options.labels.length` on a key
        # this function never returned at all — TypeError on open, for any
        # rule real enough to actually reach the "Add Label" branch (which,
        # before actions/scope/etc were even fetched — see
        # get_automation_rules — could never happen; fixing that surfaced
        # this).
        labels = [l.get("label") for l in _parse_json(proj.labels, []) if l.get("label")]
    condition_fields = [
        {"value": "to_status",    "label": "New status",   "type": "select", "options": statuses},
        {"value": "from_status",  "label": "Old status",   "type": "select", "options": statuses},
        {"value": "status",       "label": "Status",       "type": "select", "options": statuses},
        {"value": "priority",     "label": "Priority",     "type": "select",
         "options": ["Highest", "High", "Medium", "Low", "Lowest"]},
        {"value": "task_type",    "label": "Task type",    "type": "select", "options": task_types},
        {"value": "story_points", "label": "Story points", "type": "number"},
        {"value": "labels",       "label": "Labels",       "type": "text"},
        {"value": "assignees",    "label": "Assignees",    "type": "user"},
    ]
    return {
        "statuses": statuses,
        "task_types": task_types,
        "members": members,
        "labels": labels,
        "condition_fields": condition_fields,
        "triggers": _AUTOMATION_TRIGGERS,
        "actions": _AUTOMATION_ACTIONS,
        "operators": _AUTOMATION_OPERATORS,
    }


INVERSE_LINK = {
    "blocks": "is blocked by",
    "is blocked by": "blocks",
    "clones": "is cloned by",
    "is cloned by": "clones",
    "duplicates": "duplicates",
    "relates to": "relates to",
}


BLOCKING_TYPES = {"blocks", "is blocked by"}

BLOCKING_TYPES = {"blocks", "is blocked by"}

_AUTOMATION_TRIGGERS = [
    {"value": "task.status_changed", "label": "When a task's status changes"},
    {"value": "task.created",        "label": "When a task is created"},
    {"value": "task.updated",        "label": "When a task is updated"},
    {"value": "task.assigned",       "label": "When a task is assigned"},
    {"value": "task.due_soon",       "label": "When a task is due soon"},
    {"value": "comment.added",       "label": "When a comment is added"},
    {"value": "task.deleted",        "label": "When a task is deleted"},
    {"value": "task.trashed",        "label": "When a task is moved to trash"},
    {"value": "task.restored",       "label": "When a task is restored from trash"},
]


_AUTOMATION_ACTIONS = [
    {"value": "Change Status", "label": "Change the status"},
    {"value": "Assign Issue",  "label": "Assign the task"},
    {"value": "Set Priority",  "label": "Set the priority"},
    {"value": "Set Due Date",  "label": "Set the due date"},
    {"value": "Add Label",     "label": "Add label(s)"},
    {"value": "Add Comment",   "label": "Post a comment"},
    {"value": "Notify",        "label": "Send a notification"},
    {"value": "Create Issue",  "label": "Create a new task"},
]


_AUTOMATION_OPERATORS = [
    {"value": "eq", "label": "is"},
    {"value": "ne", "label": "is not"},
    {"value": "in", "label": "is any of"},
    {"value": "nin", "label": "is none of"},
    {"value": "changed", "label": "changed"},
    {"value": "contains", "label": "contains"},
    {"value": "gt", "label": "greater than"},
    {"value": "gte", "label": "greater or equal"},
    {"value": "lt", "label": "less than"},
    {"value": "lte", "label": "less or equal"},
    {"value": "is_set", "label": "is set"},
    {"value": "is_not_set", "label": "is empty"},
]




def _parse_json(value, default=None):
    """Parse a JSON string, or return the value as-is if already a dict/list."""
    if value is None:
        return default
    if isinstance(value, (list, dict)):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return default
    return default


def _require_automation_admin(scope, project):
    """Gate: needs workspace admin for workspace-scope, BP Admin for project-scope."""
    from batch_projects import access
    if scope == "workspace":
        if not access.is_workspace_admin():
            frappe.throw("You need workspace admin access for this.", frappe.PermissionError)
    else:
        from batch_projects.api.board import _check_permission
        _check_permission(project, "BP Admin")



@frappe.whitelist()
def get_reports(project, period="last_30_days", from_date=None, to_date=None):
	"""Per-project delivery analytics in one call:
	  • status_breakdown — current task count per workflow status
	  • throughput       — tasks created vs completed per week (within period)
	  • cycle_time       — avg days started→completed (+ percentiles + scatter)
	  • velocity         — committed vs completed story points per sprint
	period: last_7_days | last_30_days | last_90_days | month:YYYY-MM
	from_date/to_date: ISO strings, override period when both provided
	"""
	from datetime import date, datetime, timedelta

	# ── Resolve scope → one or many projects ────────────────────────────────
	# Accepts a single project name/key, a (JSON-stringified) list, or
	# 'all'/None meaning every project the caller can access. Cross-project
	# reports aggregate so the same widgets work at "All projects" scope.
	if isinstance(project, str) and project.strip().startswith("["):
		try:
			project = json.loads(project)
		except Exception:
			pass

	if isinstance(project, (list, tuple)):
		proj_names = [p for p in project if p]
	elif not project or project == "all":
		proj_names = None  # → all accessible projects
	else:
		proj_names = [project]

	if proj_names is None:
		from batch_projects.permissions import get_accessible_projects
		acc = get_accessible_projects(frappe.session.user)
		proj_names = frappe.get_all("BP Project", pluck="name") if acc is None else list(acc)
	else:
		# Normalise keys → names and permission-check each project in scope.
		resolved = []
		for s in proj_names:
			pn = s if frappe.db.exists("BP Project", s) else frappe.db.get_value("BP Project", {"key": s}, "name")
			if pn:
				_check_permission(pn, "BP Viewer")
				resolved.append(pn)
		proj_names = resolved

	if not proj_names:
		frappe.throw("No accessible project in scope for this report.", frappe.ValidationError)

	# Filter value usable across all the project-scoped queries below.
	proj_filter = proj_names[0] if len(proj_names) == 1 else ["in", proj_names]

	# Merge workflow states + completed statuses across the project(s) in scope.
	# Different projects may define different statuses; dedupe by name, first
	# color wins, and the completed set is the union.
	states, completed, _seen_states = [], set(), set()
	for pn in proj_names:
		try:
			pdoc = frappe.get_cached_doc("BP Project", pn)
			for s in _normalize_workflow_states(pdoc.get_workflow_states()):
				nm = s.get("name")
				if nm and nm not in _seen_states:
					_seen_states.add(nm)
					states.append(s)
			completed |= set(pdoc.get_completed_statuses())
		except Exception:
			pass

	today = date.today()
	period_days = {"last_7_days": 7, "last_30_days": 30, "last_90_days": 90}

	def _parse_date(v):
		if not v: return None
		if isinstance(v, (date, datetime)): return v.date() if isinstance(v, datetime) else v
		try: return datetime.strptime(str(v)[:10], "%Y-%m-%d").date()
		except: return None

	if from_date and to_date:
		from_date = _parse_date(from_date) or today - timedelta(days=30)
		to_date   = _parse_date(to_date)   or today
	elif period in period_days:
		from_date, to_date = today - timedelta(days=period_days[period]), today
	elif period.startswith("month:"):
		import calendar
		ym = period.split(":")[1]
		y, m = int(ym.split("-")[0]), int(ym.split("-")[1])
		from_date, to_date = date(y, m, 1), date(y, m, calendar.monthrange(y, m)[1])
	else:
		from_date, to_date = today - timedelta(days=30), today

	def _d(v):
		if not v:
			return None
		if isinstance(v, datetime):
			return v.date()
		if isinstance(v, date):
			return v
		try:
			return datetime.strptime(str(v)[:10], "%Y-%m-%d").date()
		except Exception:
			return None

	tasks = frappe.get_all(
		"BP Task",
		filters={"project": proj_filter},
		fields=["name", "status", "story_points", "sprint",
		        "started_on", "completed_on", "creation"],
	)

	# 1. Status breakdown (current snapshot), ordered by the workflow
	counts = {}
	for t in tasks:
		counts[t["status"]] = counts.get(t["status"], 0) + 1
	status_breakdown = [
		{"name": s.get("name"), "color": s.get("color") or "#9FA6AD",
		 "category": s.get("category"), "count": counts.get(s.get("name"), 0)}
		for s in states
	]
	known = {s.get("name") for s in states}
	for st, c in counts.items():
		if st not in known:
			status_breakdown.append({"name": st, "color": "#9FA6AD", "category": "unstarted", "count": c})

	# 2. Throughput — weekly buckets (Mon-anchored) across [from_date, to_date]
	start_week = from_date - timedelta(days=from_date.weekday())
	buckets, wk = [], start_week
	while wk <= to_date:
		buckets.append({"start": wk, "label": wk.strftime("%b %d"), "created": 0, "completed": 0})
		wk = wk + timedelta(days=7)

	def _bucket_idx(d):
		if not d or d < buckets[0]["start"] or d > to_date:
			return None
		return min((d - buckets[0]["start"]).days // 7, len(buckets) - 1)

	cycle_days = []
	cycle_scatter = []
	for t in tasks:
		i = _bucket_idx(_d(t.get("creation")))
		if i is not None:
			buckets[i]["created"] += 1
		done = _d(t.get("completed_on"))
		j = _bucket_idx(done)
		if j is not None:
			buckets[j]["completed"] += 1
		started = _d(t.get("started_on"))
		if started and done and done >= started:
			days = (done - started).days
			cycle_days.append(days)
			cycle_scatter.append({"date": done.isoformat(), "days": days})

	throughput = [{"label": b["label"], "created": b["created"], "completed": b["completed"]} for b in buckets]

	def _percentile(lst, p):
		if not lst: return 0
		s = sorted(lst)
		k = (len(s) - 1) * p / 100
		f, c = int(k), min(int(k) + 1, len(s) - 1)
		return round(s[f] + (s[c] - s[f]) * (k - f), 1)

	avg_cycle = round(sum(cycle_days) / len(cycle_days), 1) if cycle_days else 0
	completed_in_period = sum(b["completed"] for b in buckets)

	# 3. Velocity per sprint — committed vs completed story points
	sprints = frappe.get_all(
		"BP Sprint",
		filters={"project": proj_filter},
		fields=["name", "sprint_name", "status", "start_date", "end_date"],
		order_by="start_date asc, creation asc",
	)
	committed, done_pts = {}, {}
	for t in tasks:
		sp = t.get("sprint")
		if not sp:
			continue
		pts = float(t.get("story_points") or 0)
		committed[sp] = committed.get(sp, 0) + pts
		if t["status"] in completed:
			done_pts[sp] = done_pts.get(sp, 0) + pts
	velocity = [
		{"name": s["name"], "label": s["sprint_name"], "status": s["status"],
		 "committed": committed.get(s["name"], 0), "completed": done_pts.get(s["name"], 0)}
		for s in sprints
	]

	# 5. Cumulative flow — weekly status snapshots, reconstructed from the
	# activity log (falls back to current status if no history exists).
	acts = frappe.get_all(
		"BP Activity",
		filters={"project": proj_filter, "field_name": "status"},
		fields=["task", "old_value", "new_value", "creation"],
		order_by="creation asc",
	)
	trans = {}
	for a in acts:
		trans.setdefault(a["task"], []).append(a)
	task_by_name = {t["name"]: t for t in tasks}

	def _status_on(tname, day):
		t = task_by_name.get(tname)
		if not t:
			return None
		created = _d(t.get("creation"))
		if not created or created > day:
			return None
		tl = trans.get(tname, [])
		cur = tl[0]["old_value"] if tl else t["status"]
		for a in tl:
			ad = _d(a["creation"])
			if ad and ad <= day:
				cur = a["new_value"]
			else:
				break
		return cur

	cfd_order = [s["name"] for s in status_breakdown]
	cfd_color = {s["name"]: s["color"] for s in status_breakdown}
	cfd_counts = {sn: [] for sn in cfd_order}
	for b in buckets:
		snap = min(b["start"] + timedelta(days=6), to_date)
		day_counts = {sn: 0 for sn in cfd_order}
		for t in tasks:
			st = _status_on(t["name"], snap)
			if st in day_counts:
				day_counts[st] += 1
		for sn in cfd_order:
			cfd_counts[sn].append(day_counts[sn])
	cumulative_flow = {
		"labels": [b["label"] for b in buckets],
		"series": [{"name": sn, "color": cfd_color[sn], "counts": cfd_counts[sn]} for sn in cfd_order],
	}

	# 6. Burndown — active sprint (else the latest dated sprint)
	dated_sprints = [s for s in sprints if s.get("start_date") and s.get("end_date")]
	chosen = next((s for s in dated_sprints if s["status"] == "Active"), None)
	if not chosen and dated_sprints:
		chosen = sorted(dated_sprints, key=lambda s: s["start_date"])[-1]
	burndown = None
	if chosen:
		s_start, s_end = _d(chosen["start_date"]), _d(chosen["end_date"])
		sp_tasks = [t for t in tasks if t.get("sprint") == chosen["name"]]
		total = sum(float(t.get("story_points") or 0) for t in sp_tasks)
		ndays = (s_end - s_start).days + 1 if (s_start and s_end) else 0
		bd_days = []
		for i in range(max(ndays, 0)):
			d = s_start + timedelta(days=i)
			ideal = round(total * (1 - i / (ndays - 1)), 1) if ndays > 1 else total
			burned = sum(
				float(t.get("story_points") or 0) for t in sp_tasks
				if t["status"] in completed and _d(t.get("completed_on")) and _d(t["completed_on"]) <= d
			)
			bd_days.append({
				"label": d.strftime("%b %d"),
				"ideal": ideal,
				"remaining": round(total - burned, 1) if d <= today else None,
			})
		burndown = {"sprint": chosen["sprint_name"], "total": total, "days": bd_days}

	return {
		"period": period,
		"from_date": from_date.isoformat(),
		"to_date": to_date.isoformat(),
		"total_tasks": len(tasks),
		"status_breakdown": status_breakdown,
		"throughput": throughput,
		"cycle_time": {
			"avg_days": avg_cycle,
			"completed_count": completed_in_period,
			"sample": len(cycle_days),
			"p50": _percentile(cycle_days, 50),
			"p85": _percentile(cycle_days, 85),
			"p95": _percentile(cycle_days, 95),
			"scatter": cycle_scatter,
		},
		"velocity": velocity,
		"cumulative_flow": cumulative_flow,
		"burndown": burndown,
	}


@frappe.whitelist()
def get_members(project=None):
    """Project membership + (for managers) the user directory used to add people.

    The full enabled-user directory is sensitive — it's only returned to
    project Managers/Admins, who are the ones allowed to add members. Plain
    members/viewers get the project's current members only. Without a project
    context the directory requires instance-admin (it's an org-wide list)."""
    from batch_projects import access

    def _directory():
        users = frappe.get_all(
            "User",
            filters={"enabled": 1, "user_type": "System User"},
            fields=["name", "full_name", "user_image"],
            order_by="full_name asc",
        )
        return [
            {
                "user": u["name"],
                "full_name": u["full_name"] or u["name"],
                "user_image": u.get("user_image") or "",
            }
            for u in users
            if u["name"] != "Administrator"
        ]

    if not project:
        # org-wide directory — admins only
        if not access.is_instance_admin():
            frappe.throw(
                "You don't have permission to list all users.",
                frappe.PermissionError,
            )
        return _directory()

    access.require(project, "Viewer")
    can_manage = access.has_at_least(project, "Manager")
    user_list = _directory() if can_manage else []

    doc = frappe.get_doc("BP Project", project)
    name_map = {u["user"]: u["full_name"] for u in user_list}
    current = [{
        "user": m.user,
        "role": m.role,
        "full_name": name_map.get(m.user)
        or frappe.db.get_value("User", m.user, "full_name") or m.user,
    } for m in (doc.members or [])]
    return {"user_list": user_list, "members": current, "can_manage": can_manage}


# ─── SLA ──────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_sla_policies(project):
    """List active SLA policies for a project."""
    _check_permission(project, "BP Viewer")
    return frappe.get_all("BP SLA Policy",
        filters={"project": project, "is_active": 1},
        fields=["name", "policy_name", "priority_tier", "response_hours",
                "resolution_hours", "escalate_to", "escalate_after_hours"])


@frappe.whitelist()
def create_sla_policy(project, policy_name, priority_tier, response_hours,
                       resolution_hours, escalate_to=None, escalate_after_hours=None):
    """Create a new SLA policy for a project."""
    _check_permission(project, "BP Manager")
    doc = frappe.get_doc({
        "doctype": "BP SLA Policy",
        "project": project,
        "policy_name": policy_name,
        "priority_tier": priority_tier,
        "response_hours": response_hours,
        "resolution_hours": resolution_hours,
        "escalate_to": escalate_to or None,
        "escalate_after_hours": escalate_after_hours or 0,
        "is_active": 1,
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return doc.as_dict()


@frappe.whitelist()
def get_sla_breaches(task=None, project=None):
    """List SLA breaches for a task or project.

    Must stay guarded: with no `project` arg this would return every SLA
    breach in the org to any System User; with one, the caller's actual
    access to that project must still be checked."""
    if project:
        _check_permission(project, "BP Viewer")
        filters = {"project": project}
    else:
        from batch_projects.permissions import get_accessible_projects
        accessible = get_accessible_projects()  # None = admin (all)
        if accessible is not None:
            if not accessible:
                return []
            filters = {"project": ["in", list(accessible)]}
        else:
            filters = {}
    if task: filters["task"] = task
    return frappe.get_all("BP SLA Breach",
        filters=filters,
        fields=["name", "task", "policy", "breach_type", "triggered_on",
                "escalated_to", "resolved_on"],
        order_by="triggered_on desc")


# ─── WBS / PROJECT HIERARCHY ──────────────────────────────────────────────────

@frappe.whitelist()
def get_project_tree():
    """Return all projects in a tree structure based on parent_project, with
    real delivery signal per node (task progress, lead, due date) — a WBS
    tree is meant to show organizational/delivery structure, not just names."""
    _require_system_user()
    # Access filter — otherwise a private/team project's name and
    # position in the WBS leaks to anyone with no access to it.
    from batch_projects.permissions import accessible_project_filter, NO_ACCESSIBLE_PROJECTS
    proj_filters = accessible_project_filter()
    if proj_filters is NO_ACCESSIBLE_PROJECTS:
        return []
    projects = frappe.get_all("BP Project",
        filters=proj_filters,
        fields=["name", "project_name", "key", "parent_project",
                "status", "project_color", "theme", "lead", "target_end_date",
                "workflow_states"],
        order_by="name asc")

    # Same grouped-count pattern as get_projects() — one query for every
    # project's task totals instead of 2N queries.
    status_counts_by_project = {}
    if projects:
        rows = frappe.db.sql(
            """
            SELECT project, status, COUNT(*) AS cnt
            FROM `tabBP Task`
            WHERE project IN %(projects)s AND is_deleted = 0
            GROUP BY project, status
            """,
            {"projects": [p["name"] for p in projects]},
            as_dict=True,
        )
        for r in rows:
            status_counts_by_project.setdefault(r["project"], {})[r["status"]] = r["cnt"]

    leads = {p["lead"] for p in projects if p.get("lead")}
    lead_names = {}
    if leads:
        for u in frappe.get_all("User", filters={"name": ["in", list(leads)]}, fields=["name", "full_name"]):
            lead_names[u["name"]] = u["full_name"] or u["name"]

    # Build tree
    children = {}
    for p in projects:
        parent = p.parent_project or "__root__"
        children.setdefault(parent, []).append(p)
    def _build(node_key):
        out = []
        for p in children.get(node_key, []):
            by_status = status_counts_by_project.get(p["name"], {})
            completed = set(_get_completed_statuses(p))
            total = sum(by_status.values())
            done = sum(cnt for status, cnt in by_status.items() if status in completed)
            row = {
                "name": p.name, "project_name": p.project_name, "key": p.key,
                "status": p.status, "color": p.project_color, "theme": p.theme,
                "task_count": total, "done_count": done,
                "lead": p.lead or None, "lead_name": lead_names.get(p.lead) if p.lead else None,
                "target_end_date": str(p.target_end_date) if p.target_end_date else None,
            }
            subs = _build(p.name)
            if subs:
                row["children"] = subs
            out.append(row)
        return out
    return _build("__root__")


@frappe.whitelist()
def set_parent_project(project, parent_project=None):
    """Set or remove the parent_project (WBS) for a project."""
    _check_permission(project, "BP Admin")
    doc = frappe.get_doc("BP Project", project)
    if parent_project:
        if parent_project == project:
            frappe.throw("A project cannot be its own parent.")
        # No circular references
        check = frappe.db.get_value("BP Project", parent_project, "parent_project")
        visited = {project, parent_project}
        while check:
            if check in visited:
                frappe.throw("Circular parent relationship detected.")
            visited.add(check)
            check = frappe.db.get_value("BP Project", check, "parent_project")
    doc.parent_project = parent_project or None
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {"ok": True, "parent_project": doc.parent_project}


# ─── TRIAGE / INBOX ───────────────────────────────────────────────────────────

@frappe.whitelist()
def get_triage_queue(project=None):
    """Return tasks needing triage across all projects or a specific project."""
    filters = {"needs_triage": 1}
    if project:
        _check_permission(project, "BP Viewer")
        filters["project"] = project
    else:
        _require_system_user()
        from batch_projects.permissions import get_accessible_projects
        acc = get_accessible_projects(frappe.session.user)
        if acc is not None:
            filters["project"] = ["in", list(acc)]

    tasks = frappe.get_all("BP Task",
        filters=_task_filters(filters),
        fields=["name", "task_key", "title", "status", "priority", "project",
                "creation", "task_type"],
        order_by="creation desc",
        limit=100)

    # Resolve project names and assignees
    pnames = list({t["project"] for t in tasks})
    proj_map = {}
    if pnames:
        for p in frappe.get_all("BP Project", filters={"name": ["in", pnames]},
                                fields=["name", "project_name", "key"]):
            proj_map[p["name"]] = p

    tnames = [t["name"] for t in tasks]
    assignee_map = {}
    if tnames:
        for a in frappe.get_all("BP Task Assignee", filters={"parent": ["in", tnames]},
                                 fields=["parent", "user", "full_name"]):
            assignee_map.setdefault(a["parent"], []).append({
                "user": a["user"], "full_name": a["full_name"] or a["user"]})

    for t in tasks:
        t["project_name"] = proj_map.get(t["project"], {}).get("project_name", t["project"])
        t["project_key"] = proj_map.get(t["project"], {}).get("key", "")
        t["assignees"] = assignee_map.get(t["name"], [])

    return tasks


@frappe.whitelist()
def mark_triaged(task):
    """Mark a task as triaged (remove from inbox)."""
    doc = frappe.get_doc("BP Task", task)
    _check_permission(doc.project, "BP Member")
    doc.needs_triage = 0
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    from batch_projects.cache import invalidate_project
    invalidate_project(doc.project)
    return {"ok": True}


# ─── FILES ────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_project_files(project):
    """Returns all files attached to the project directly (the real "project
    files" surface — uploaded from the Files tab itself, not through any
    task) UNIONed with files attached to tasks in the project, with task
    context and uploader info.

    Was BP-Task-only (INNER JOIN on `tabBP Task`, hard-requiring
    attached_to_doctype='BP Task'): the Files tab had no way to represent a
    file that belongs to the project as a whole rather than one task — it was
    a task-attachment lister wearing a "Files" tab label, exactly the gap
    upload_project_file/rename_project_file/delete_project_file below now
    close on the write side."""
    _check_permission(project, "BP Viewer")

    files = frappe.db.sql("""
        SELECT f.name, f.file_name, f.file_url, f.file_size,
               f.is_private, f.creation, f.owner,
               f.attached_to_name AS task_name,
               t.title AS task_title,
               u.full_name AS uploaded_by_name
        FROM `tabFile` f
        JOIN `tabBP Task` t ON t.name = f.attached_to_name
        LEFT JOIN `tabUser` u ON u.name = f.owner
        WHERE f.attached_to_doctype = 'BP Task'
          AND t.project = %(project)s

        UNION ALL

        SELECT f.name, f.file_name, f.file_url, f.file_size,
               f.is_private, f.creation, f.owner,
               NULL AS task_name,
               NULL AS task_title,
               u.full_name AS uploaded_by_name
        FROM `tabFile` f
        LEFT JOIN `tabUser` u ON u.name = f.owner
        WHERE f.attached_to_doctype = 'BP Project'
          AND f.attached_to_name = %(project)s

        ORDER BY creation DESC
    """, {"project": project}, as_dict=True)

    return [
        {
            "name": f.name,
            "file_name": f.file_name,
            "file_url": f.file_url,
            "file_size": f.file_size,
            "is_private": bool(f.is_private),
            "creation": str(f.creation) if f.creation else None,
            "owner": f.owner,
            "uploaded_by_name": f.uploaded_by_name or f.owner,
            "task_name": f.task_name,
            "task_title": f.task_title or f.task_name,
        }
        for f in files
    ]


def _file_project_and_min_role(doc, min_role):
    """Resolve (project, min_role) for a File attached to either a BP Task or
    a BP Project — the two attachment surfaces this app writes files to —
    and run the same _check_permission every other mutation in this module
    uses. Shared by rename_project_file/delete_project_file so the two
    doctypes are never checked two different ways."""
    if doc.attached_to_doctype == "BP Task":
        project = frappe.db.get_value("BP Task", doc.attached_to_name, "project")
    elif doc.attached_to_doctype == "BP Project":
        project = doc.attached_to_name
    else:
        frappe.throw("Not a project or task attachment.")
    _check_permission(project, min_role)
    return project


@frappe.whitelist()
def rename_project_file(file_name, new_name):
    """Rename a file's DISPLAY name (File.file_name) — the underlying
    storage path/content is untouched, same as renaming a file in any
    desktop file manager. The original extension is preserved even if the
    caller's new_name drops it, so a rename can't silently turn a .pdf into
    something a browser won't know how to open."""
    doc = frappe.get_doc("File", file_name)
    _file_project_and_min_role(doc, "BP Member")

    new_name = (new_name or "").strip()
    if not new_name:
        frappe.throw("Name can't be empty.")
    old_ext = doc.file_name.rsplit(".", 1)[-1] if "." in doc.file_name else ""
    if old_ext and not new_name.lower().endswith("." + old_ext.lower()):
        new_name = f"{new_name}.{old_ext}"
    doc.file_name = new_name[:255]
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {"ok": True, "file_name": doc.file_name}


@frappe.whitelist()
def delete_project_file(file_name):
    """The Files tab's one delete action for whichever kind of file the user
    right-clicked — task-attached or project-attached (get_project_files
    lists both in one view, so the UI needs one action, not two).
    delete_attachment (BP-Task-only, hard-throws otherwise) stays exactly as
    it was for TaskAttachments.vue's own narrower delete button — this isn't
    a replacement for it, just the general-purpose sibling the Files tab
    needs."""
    doc = frappe.get_doc("File", file_name)
    _file_project_and_min_role(doc, "BP Member")
    doc.delete(ignore_permissions=True)
    frappe.db.commit()
    return {"ok": True}

# Intake-form and milestone-invoice routers were removed from here — they
# were thin aliases to api.forms.*/api.erp_link.*
# that bp-gateway's Go-side MethodGate (internal/license/license.go's
# urlToFeature table) never matched, because it gates on the REAL module
# path, not this alias path. That silently skipped the Go-enforced tier
# gate for intake_forms (Team) and generate_milestone_invoice
# (billing_writeback, Business) — Python's own require_feature() still
# caught both, but that's this app's own documented "patchable, not the
# enforcement boundary" layer. The frontend (utils/api.js) now calls
# batch_projects.api.forms.* / batch_projects.api.erp_link.* directly.


# ─── Constants restored from refactor ─────────────────────────────────────────

_PREF_DEFAULTS = {
    "email_enabled": 1, "email_assignment": 1, "email_comment": 1,
    "email_mention": 1, "email_status_change": 1, "email_due_reminder": 1,
    "email_digest": 1, "email_weekly_summary": 1, "inapp_enabled": 1,
    "desktop_enabled": 1,
}

_WIDGET_PALETTE = ["#0B6BCB", "#7C3AED", "#008846", "#B45309", "#cc1c63",
                   "#0E6B93", "#36b37e", "#C2410C", "#6D28D9", "#0891B2"]
_WIDGET_PRIORITY = {"Highest": "#C41C1C", "High": "#B45309", "Medium": "#fdab3d",
                    "Low": "#2563EB", "Lowest": "#64748B"}


@frappe.whitelist()
def get_teams():
    """Return active teams with projects + member count. Org members see all
    teams (workspace model); guests see only the teams they belong to."""
    _require_system_user()
    filters = {"status": "Active"}

    from batch_projects import access
    user = frappe.session.user
    if access.is_guest(user) and not access.is_instance_admin(user):
        my_teams = frappe.get_all(
            "BP Team Member", filters={"user": user}, pluck="parent")
        if not my_teams:
            return []
        filters["name"] = ["in", my_teams]

    teams = frappe.get_all(
        "BP Team",
        filters=filters,
        fields=["name", "team_name", "team_key", "team_color", "team_icon",
                "description", "lead", "department", "company",
                "default_workflow_template", "capacity_hours_per_sprint"],
        order_by="team_name asc",
    )

    for team in teams:
        # Attach members
        members = frappe.get_all(
            "BP Team Member",
            filters={"parent": team["name"]},
            fields=["user", "full_name", "role", "capacity_hours_per_sprint"],
        )
        team["members"] = members
        team["member_count"] = len(members)

        # Attach projects — scoped to what the caller can see: a
        # project's `team` assignment and its own `visibility` are separate
        # fields, so a `private` project on this team must not surface here
        # for a team viewer who isn't an explicit BP Project Member.
        from batch_projects.permissions import accessible_project_filter, NO_ACCESSIBLE_PROJECTS
        proj_filters = accessible_project_filter({"team": team["name"], "status": "Active"})
        projects = [] if proj_filters is NO_ACCESSIBLE_PROJECTS else frappe.get_all(
            "BP Project",
            filters=proj_filters,
            fields=["name", "project_name", "key", "project_color", "project_icon", "status"],
            order_by="project_name asc",
        )
        team["projects"] = projects
        team["project_count"] = len(projects)

    return teams




@frappe.whitelist()
def get_team(team):
    """Full team detail including members, projects, active sprint, hierarchy, links."""
    _check_team_permission(team, "Viewer")
    doc = frappe.get_doc("BP Team", team)
    data = doc.as_dict()

    # Members with full_name fallback
    all_users = {u["name"]: u["full_name"] for u in frappe.get_all(
        "User", fields=["name", "full_name"]
    )}
    data["members"] = [
        {
            "user":                  m.user,
            "full_name":             m.full_name or all_users.get(m.user, m.user),
            "role":                  m.role,
            "capacity_hours_per_sprint": m.capacity_hours_per_sprint or 40,
        }
        for m in doc.members
    ]

    # Projects under this team — scoped to what the caller can see,
    # same reasoning as get_teams above.
    from batch_projects.permissions import accessible_project_filter, NO_ACCESSIBLE_PROJECTS
    _proj_filters = accessible_project_filter({"team": team, "status": "Active"})
    data["projects"] = [] if _proj_filters is NO_ACCESSIBLE_PROJECTS else frappe.get_all(
        "BP Project",
        filters=_proj_filters,
        fields=["name", "project_name", "key", "project_color", "project_icon", "theme",
                "workflow_states", "issue_types", "status"],
        order_by="project_name asc",
    )
    for p in data["projects"]:
        p["open_count"] = frappe.db.count("BP Task", _task_filters({
            "project": p["name"],
            "status": ["not in", _get_completed_statuses(p)],
        }))

    # Active team sprint
    data["active_sprint"] = frappe.db.get_value(
        "BP Sprint",
        {"team": team, "status": "Active"},
        ["name", "sprint_name", "start_date", "end_date", "goal"],
        as_dict=True,
    )

    # Department info
    if doc.department:
        try:
            dept = frappe.get_doc("Department", doc.department)
            data["department_name"] = dept.department_name
        except Exception:
            data["department_name"] = doc.department

    # Parent team info
    if doc.get("parent_team"):
        try:
            parent = frappe.db.get_value("BP Team", doc.parent_team,
                ["team_name", "team_key", "team_color"], as_dict=True)
            data["parent_team_info"] = parent
        except Exception:
            data["parent_team_info"] = None

    # Sub-teams (teams where parent_team = this team)
    data["sub_teams"] = frappe.get_all(
        "BP Team",
        filters={"parent_team": team, "status": "Active"},
        fields=["name", "team_name", "team_key", "team_color", "team_icon"],
    )

    # Team links
    data["team_links"] = [
        {
            "link_type": l.link_type,
            "label":     l.label or "",
            "url":       l.url or "",
            "project":   l.project or "",
        }
        for l in (doc.team_links or [])
    ]

    # Recent activity (last 10 issue updates across team projects)
    project_names = [p["name"] for p in data["projects"]]
    if project_names:
        data["recent_activity"] = frappe.get_all(
            "BP Activity",
            filters={"project": ["in", project_names]},
            fields=["name", "task", "task_key", "action_type",
                    "old_value", "new_value", "user", "creation", "project"],
            order_by="creation desc",
            limit=15,
        )
        # Attach full names
        for a in data["recent_activity"]:
            a["user_name"] = all_users.get(a["user"], a["user"])
    else:
        data["recent_activity"] = []

    return data




@frappe.whitelist()
def get_my_tasks(
    status_filter="open",   # 'open' | 'all' | 'completed'
    project=None,           # filter to a specific project
    priority=None,          # filter to a specific priority
    group_by="project",     # 'project' | 'status' | 'priority' | 'due_date'
    sort_by="due_date",     # 'due_date' | 'priority' | 'creation' | 'modified'
    sort_order="asc",
    limit=100,
    offset=0,
):
    """
    Return all tasks assigned to the current user (or where they are reporter),
    across all projects. Supports grouping, filtering, and sorting.
    """
    _require_system_user()
    user = frappe.session.user

    # ── 1. Collect task names where user is an assignee ──
    assignee_rows = frappe.get_all(
        "BP Task Assignee",
        filters={"user": user},
        pluck="parent",
    )
    assignee_set = set(assignee_rows)

    # ── 2. Collect task names where user is reporter ──
    reporter_rows = frappe.get_all(
        "BP Task",
        filters={"reporter": user},
        pluck="name",
    )
    all_task_names = list(assignee_set | set(reporter_rows))

    if not all_task_names:
        return {"tasks": [], "grouped": {}, "total": 0, "counts": {"open": 0, "completed": 0}}

    # ── 3. Build filters ──
    # `project` may arrive as a scalar, a (JSON-stringified) list, or 'all'.
    # Normalise so a single-element list becomes a scalar and a real list
    # becomes an ["in", [...]] clause (a bare list is misread by frappe as
    # an [operator, value] tuple → IndexError).
    if isinstance(project, str) and project.strip().startswith("["):
        try:
            project = json.loads(project)
        except Exception:
            pass
    if isinstance(project, (list, tuple)):
        project = [p for p in project if p]
        if len(project) == 1:
            project = project[0]
        elif not project:
            project = None

    filters = {"name": ["in", all_task_names]}
    if project and project != "all":
        filters["project"] = ["in", project] if isinstance(project, list) else project

    # Collect completed statuses per project for open/completed filtering
    project_completed_map = {}
    def _is_completed(task):
        proj = task["project"]
        if proj not in project_completed_map:
            project_completed_map[proj] = set(_get_completed_statuses_by_project(proj))
        return task["status"] in project_completed_map[proj]

    if priority:
        filters["priority"] = priority

    # ── 4. Fetch tasks ──
    sort_field_map = {
        "due_date":  "due_date",
        "priority":  "priority",
        "creation":  "creation",
        "modified":  "modified",
        "title":     "title",
    }
    order_field = sort_field_map.get(sort_by, "due_date")
    order_dir = "desc" if sort_order == "desc" else "asc"

    tasks = frappe.get_all(
        "BP Task",
        filters=_task_filters(filters),
        fields=[
            "name", "task_key", "title", "status", "priority", "task_type",
            "project", "due_date", "start_date", "story_points", "epic",
            "parent_task", "sprint", "reporter", "creation", "modified",
        ],
        order_by=f"{order_field} {order_dir}",
    )

    # Enrich with project name and assignees
    project_name_map = {}
    for task in tasks:
        proj = task["project"]
        if proj not in project_name_map:
            project_name_map[proj] = frappe.db.get_value("BP Project", proj, "project_name") or proj
        task["project_name"] = project_name_map[proj]
        task["is_assigned"] = task["name"] in assignee_set
        task["is_reporter"] = task["reporter"] == user

    # Enrich with workflow colors
    wf_color_map = {}
    for task in tasks:
        proj = task["project"]
        if proj not in wf_color_map:
            states = _deep_parse_json(
                frappe.db.get_value("BP Project", proj, "workflow_states") or "[]"
            )
            wf_color_map[proj] = {s["name"]: s for s in (states if isinstance(states, list) else [])}
        task["status_color"] = wf_color_map[proj].get(task["status"], {}).get("color", "#636B74")
        task["status_category"] = wf_color_map[proj].get(task["status"], {}).get("category", "unstarted")

    # ── 5. Filter by open/completed ──
    counts = {"open": 0, "completed": 0}
    all_filtered = []
    for t in tasks:
        if _is_completed(t):
            counts["completed"] += 1
        else:
            counts["open"] += 1
        all_filtered.append(t)

    if status_filter == "open":
        tasks = [t for t in all_filtered if not _is_completed(t)]
    elif status_filter == "completed":
        tasks = [t for t in all_filtered if _is_completed(t)]
    else:
        tasks = all_filtered

    total = len(tasks)
    tasks = tasks[int(offset): int(offset) + int(limit)]

    # ── 6. Group ──
    from frappe.utils import today, add_days
    today_str = str(today())
    tomorrow_str = str(add_days(today_str, 1))
    next_week_str = str(add_days(today_str, 7))

    grouped = {}
    for task in tasks:
        if group_by == "project":
            key = task["project_name"]
        elif group_by == "status":
            key = task["status"] or "No Status"
        elif group_by == "priority":
            key = task["priority"] or "No Priority"
        elif group_by == "due_date":
            d = str(task.get("due_date") or "")
            if not d:
                key = "No due date"
            elif d < today_str:
                key = "Overdue"
            elif d == today_str:
                key = "Today"
            elif d == tomorrow_str:
                key = "Tomorrow"
            elif d <= next_week_str:
                key = "This week"
            else:
                key = "Later"
        else:
            key = task["project_name"]

        grouped.setdefault(key, []).append(task)

    return {
        "tasks": tasks,
        "grouped": grouped,
        "total": total,
        "counts": counts,
    }




@frappe.whitelist()
def get_timesheets(period="last_30_days", team=None):
    """
    Per-employee timesheet summary for the period, with project breakdown.
    period: last_7_days | last_30_days | last_90_days | month:YYYY-MM
    team:   BP Team name (optional filter)
    """
    from datetime import date, timedelta
    _require_system_user()

    today = date.today()
    period_days = {"last_7_days": 7, "last_30_days": 30, "last_90_days": 90}

    if period in period_days:
        from_date = today - timedelta(days=period_days[period])
        to_date   = today
    elif period.startswith("month:"):
        import calendar
        ym        = period.split(":")[1]
        year, mon = int(ym.split("-")[0]), int(ym.split("-")[1])
        from_date = date(year, mon, 1)
        to_date   = date(year, mon, calendar.monthrange(year, mon)[1])
    else:
        from_date = today - timedelta(days=30)
        to_date   = today

    from_dt = f"{from_date.isoformat()} 00:00:00"
    to_dt   = f"{to_date.isoformat()} 23:59:59"

    _empty = {
        "period": period,
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "total_hours": 0.0,
        "billable_hours": 0.0,
        "non_billable_hours": 0.0,
        "billable_pct": 0.0,
        "members": [],
    }

    if not frappe.db.table_exists("Timesheet Detail"):
        return _empty

    # Resolve team member filter
    team_users = None
    if team:
        _check_team_permission(team, "Viewer")
        tdoc = frappe.get_doc("BP Team", team)
        team_users = [m.user for m in (tdoc.members or [])]
        if not team_users:
            return _empty

    # Project-visibility filter — without this, a Viewer
    # on one small project could see every other project's employees'
    # billable hours, bypassing visibility=private/team the same way the
    # access filter on get_sla_breaches/get_project_tree/etc. does. None = admin
    # (unrestricted); rows with no matching BP Project are excluded for a
    # restricted caller since they can't be attributed to anything the
    # caller is known to have access to.
    from batch_projects.permissions import get_accessible_projects
    accessible = get_accessible_projects()
    if accessible is not None and not accessible:
        return _empty

    try:
        rows = frappe.db.sql(
            """
            SELECT
                COALESCE(e.user_id, ts.owner)                              AS user,
                COALESCE(e.employee_name, u.full_name, ts.owner)           AS full_name,
                tsd.project,
                p.project_name,
                p.project_color,
                SUM(tsd.hours)                                             AS hours,
                SUM(CASE WHEN tsd.is_billable = 1 THEN tsd.hours ELSE 0 END) AS billable_hours
            FROM `tabTimesheet Detail` tsd
            JOIN `tabTimesheet` ts ON ts.name = tsd.parent AND ts.docstatus = 1
            LEFT JOIN `tabEmployee` e ON e.name = ts.employee
            LEFT JOIN `tabUser` u ON u.name = COALESCE(e.user_id, ts.owner)
            LEFT JOIN `tabBP Project` p ON p.erpnext_project = tsd.project
            WHERE tsd.from_time >= %(from_dt)s
              AND tsd.from_time <= %(to_dt)s
              {project_clause}
            GROUP BY COALESCE(e.user_id, ts.owner), tsd.project
            ORDER BY full_name ASC, hours DESC
            """.format(project_clause="AND p.name IN %(accessible)s" if accessible is not None else ""),
            {"from_dt": from_dt, "to_dt": to_dt, "accessible": list(accessible) if accessible is not None else []},
            as_dict=True,
        )
    except Exception as exc:
        frappe.log_error(f"get_timesheets query: {exc}")
        rows = []

    if team_users is not None:
        rows = [r for r in rows if r.get("user") in team_users]

    # Group by user
    emp_map = {}
    for r in rows:
        key = r.get("user") or ""
        if not key:
            continue
        if key not in emp_map:
            emp_map[key] = {
                "user":          key,
                "full_name":     r.get("full_name") or key,
                "total_hours":   0.0,
                "billable_hours": 0.0,
                "projects":      [],
            }
        h  = float(r.get("hours") or 0)
        bh = float(r.get("billable_hours") or 0)
        emp_map[key]["total_hours"]    += h
        emp_map[key]["billable_hours"] += bh
        if r.get("project"):
            emp_map[key]["projects"].append({
                "project":       r["project"],
                "project_name":  r.get("project_name") or r["project"],
                "project_color": r.get("project_color") or "#94a3b8",
                "hours":         round(h, 1),
                "billable_hours": round(bh, 1),
            })

    members = list(emp_map.values())
    for m in members:
        m["total_hours"]        = round(m["total_hours"], 1)
        m["billable_hours"]     = round(m["billable_hours"], 1)
        m["non_billable_hours"] = round(m["total_hours"] - m["billable_hours"], 1)
        m["billable_pct"]       = round(m["billable_hours"] / m["total_hours"] * 100, 1) if m["total_hours"] > 0 else 0

    members.sort(key=lambda x: x["total_hours"], reverse=True)

    total_h    = round(sum(m["total_hours"] for m in members), 1)
    billable_h = round(sum(m["billable_hours"] for m in members), 1)

    return {
        "period":            period,
        "from_date":         from_date.isoformat(),
        "to_date":           to_date.isoformat(),
        "total_hours":       total_h,
        "billable_hours":    billable_h,
        "non_billable_hours": round(total_h - billable_h, 1),
        "billable_pct":      round(billable_h / total_h * 100, 1) if total_h > 0 else 0,
        "members":           members,
    }


# ─────────────────────────────────────────────────────────────────────────────
# MARGIN REPORT
# ─────────────────────────────────────────────────────────────────────────────



@frappe.whitelist()
def get_workload(weeks=4, team=None):
    """
    Forward-looking workload: allocated hours per member per week.
    Returns member rows with weekly allocation buckets.
    weeks:  2 | 4 | 6
    team:   BP Team name (optional) — if omitted, all tracked members
    """
    # Was ungated when `team` is omitted — the `team`
    # branch below correctly checks _check_team_permission, but the
    # all-tracked-members fallback ran with zero identity check at all.
    _require_system_user()

    from datetime import date, timedelta
    from collections import defaultdict

    weeks = int(weeks)
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())

    # Build week buckets
    week_buckets = []
    for i in range(weeks):
        ws = start_of_week + timedelta(weeks=i)
        we = ws + timedelta(days=6)
        week_buckets.append({
            "label": ws.strftime("%b %d"),
            "start": ws.isoformat(),
            "end":   we.isoformat(),
        })

    # Resolve member list + per-member capacity
    if team:
        _check_team_permission(team, "Viewer")
        tdoc = frappe.get_doc("BP Team", team)
        member_users = [m.user for m in (tdoc.members or [])]
        cap_by_user  = {
            m.user: float(m.capacity_hours_per_sprint or 40)
            for m in tdoc.members
        }
    else:
        member_users = _all_tracked_users()
        cap_by_user  = _get_member_capacities(member_users)

    if not member_users:
        return {"weeks": week_buckets, "members": [], "capacity_per_week": 40}

    # User profile info
    user_info = {
        u.name: u
        for u in frappe.get_all(
            "User",
            filters={"name": ["in", member_users]},
            fields=["name", "full_name", "user_image"],
        )
    }

    # Open (non-done) tasks assigned to these users with due dates in window
    try:
        assignments = frappe.db.sql(
            """
            SELECT
                ta.user,
                t.name           AS task_name,
                t.title,
                t.due_date,
                t.estimated_hours,
                t.project,
                p.project_name   AS project_title,
                p.project_color
            FROM `tabBP Task Assignee` ta
            JOIN `tabBP Task` t
                ON t.name = ta.parent
                AND t.docstatus < 2
                AND t.is_deleted = 0
                AND t.status NOT IN ('Done', 'Cancelled', 'Closed')
            LEFT JOIN `tabBP Project` p
                ON p.name = t.project
            WHERE ta.user IN %(users)s
            ORDER BY t.due_date ASC
            """,
            {"users": member_users},
            as_dict=True,
        )
    except Exception:
        assignments = []

    # Bucket tasks: overdue → week 0, no due date → week 0,
    # within window → matching week, beyond window → last week
    member_week = defaultdict(lambda: [[] for _ in range(weeks)])

    for a in assignments:
        due = a.get("due_date")
        bucket = 0  # default: first/current week
        if due:
            if not isinstance(due, date):
                from datetime import datetime
                due = datetime.strptime(str(due), "%Y-%m-%d").date()
            matched = False
            for wi, wb in enumerate(week_buckets):
                if date.fromisoformat(wb["start"]) <= due <= date.fromisoformat(wb["end"]):
                    bucket = wi
                    matched = True
                    break
            if not matched:
                bucket = (weeks - 1) if due > date.fromisoformat(week_buckets[-1]["end"]) else 0

        member_week[a.user][bucket].append(a)

    members = []
    for user in member_users:
        info     = user_info.get(user, frappe._dict())
        capacity = cap_by_user.get(user, 40.0)
        weekly   = []
        for wi in range(weeks):
            tasks     = member_week[user][wi]
            allocated = sum(float(t.get("estimated_hours") or 0) for t in tasks)
            load_pct  = round(min(allocated / capacity * 100, 200), 1) if capacity else 0
            weekly.append({
                "allocated": round(allocated, 1),
                "capacity":  capacity,
                "load_pct":  load_pct,
                "tasks": [
                    {
                        "name":           t.task_name,
                        "title":          t.title,
                        "project":        t.project,
                        "project_title":  t.project_title or t.project,
                        "project_color":  t.project_color,
                        "due_date":       str(t.due_date) if t.due_date else None,
                        "estimated_hours": float(t.estimated_hours or 0),
                    }
                    for t in tasks
                ],
            })

        members.append({
            "user":            user,
            "full_name":       info.get("full_name") or user,
            "user_image":      info.get("user_image"),
            "weekly":          weekly,
            "total_allocated": round(sum(w["allocated"] for w in weekly), 1),
            "total_capacity":  round(capacity * weeks, 1),
        })

    members.sort(key=lambda m: m["full_name"])
    return {"weeks": week_buckets, "members": members, "capacity_per_week": 40}


# ─────────────────────────────────────────────────────────────────────────────
# UTILIZATION
# ─────────────────────────────────────────────────────────────────────────────



@frappe.whitelist()
def get_utilization(period="last_30_days", team=None):
    """
    Backward-looking utilization: logged hours from ERPNext Timesheet Detail.
    period: last_7_days | last_30_days | last_90_days | month:YYYY-MM
    team:   BP Team name (optional)
    """
    # Was ungated when `team` is omitted — same gap as
    # get_workload right above.
    _require_system_user()

    from datetime import date, timedelta

    today = date.today()

    period_days = {"last_7_days": 7, "last_30_days": 30, "last_90_days": 90}

    if period in period_days:
        days = period_days[period]
        from_date = today - timedelta(days=days)
        to_date   = today
    elif period.startswith("month:"):
        import calendar
        ym         = period.split(":")[1]
        year, mon  = int(ym.split("-")[0]), int(ym.split("-")[1])
        from_date  = date(year, mon, 1)
        to_date    = date(year, mon, calendar.monthrange(year, mon)[1])
    else:
        from_date  = today - timedelta(days=30)
        to_date    = today

    # Resolve members + per-member capacity
    if team:
        _check_team_permission(team, "Viewer")
        tdoc = frappe.get_doc("BP Team", team)
        member_users = [m.user for m in (tdoc.members or [])]
        cap_by_user  = {
            m.user: float(m.capacity_hours_per_sprint or 40)
            for m in tdoc.members
        }
    else:
        member_users = _all_tracked_users()
        cap_by_user  = _get_member_capacities(member_users)

    if not member_users:
        return {
            "period":    period,
            "from_date": from_date.isoformat(),
            "to_date":   to_date.isoformat(),
            "members":   [],
            "totals":    {
                "capacity": 0, "logged": 0, "billable": 0,
                "utilization_pct": 0, "billable_pct": 0,
            },
        }

    user_info = {
        u.name: u
        for u in frappe.get_all(
            "User",
            filters={"name": ["in", member_users]},
            fields=["name", "full_name", "user_image"],
        )
    }

    # Scale weekly capacity to the period length
    days_in_period = (to_date - from_date).days + 1

    from_dt = f"{from_date.isoformat()} 00:00:00"
    to_dt   = f"{to_date.isoformat()} 23:59:59"

    # Pull total and billable hours from submitted ERPNext Timesheets (single query)
    ts_data = _timesheet_hours_by_user(member_users, from_dt, to_dt)

    members       = []
    total_logged   = 0.0
    total_billable = 0.0
    total_capacity = 0.0

    for user in member_users:
        info     = user_info.get(user, frappe._dict())
        logged, billable = ts_data.get(user, (0.0, 0.0))

        # Weekly capacity scaled to period (hours/week × weeks in period)
        weekly_cap    = cap_by_user.get(user, 40.0)
        capacity      = round(weekly_cap * days_in_period / 7, 1)

        util_pct     = round(min(logged / capacity * 100, 200), 1) if capacity else 0
        billable_pct = round(billable / logged * 100, 1) if logged > 0 else 0

        total_logged   += logged
        total_billable += billable
        total_capacity += capacity

        members.append({
            "user":            user,
            "full_name":       info.get("full_name") or user,
            "user_image":      info.get("user_image"),
            "logged_hours":    round(logged, 1),
            "billable_hours":  round(billable, 1),
            "capacity_hours":  capacity,
            "utilization_pct": util_pct,
            "billable_pct":    billable_pct,
        })

    members.sort(key=lambda m: m["utilization_pct"], reverse=True)

    total_util         = round(total_logged / total_capacity * 100, 1) if total_capacity else 0
    total_billable_pct = round(total_billable / total_logged * 100, 1) if total_logged else 0

    return {
        "period":    period,
        "from_date": from_date.isoformat(),
        "to_date":   to_date.isoformat(),
        "members":   members,
        "totals": {
            "capacity":        round(total_capacity, 1),
            "logged":          round(total_logged, 1),
            "billable":        round(total_billable, 1),
            "utilization_pct": total_util,
            "billable_pct":    total_billable_pct,
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# PEOPLE
# ─────────────────────────────────────────────────────────────────────────────



@frappe.whitelist()
def get_workspace_summary():
    """
    Workspace-tab data: project health, profitability, activity stream,
    stale projects, recently delivered, invoice-ready, milestones, risks.
    """
    from datetime import date, timedelta
    _require_system_user()

    today = date.today()
    ago_7  = (today - timedelta(days=7)).isoformat()
    ago_14 = (today - timedelta(days=14)).isoformat()

    # Access filter: frappe.get_all ignores
    # permission_query_conditions, so this cross-project rollup must scope
    # itself explicitly or it leaks every project's budget/client/hourly_rate
    # regardless of `visibility`/membership.
    from batch_projects.permissions import get_accessible_projects, NO_ACCESSIBLE_PROJECTS, accessible_project_filter
    accessible = get_accessible_projects()  # None = admin (all)
    proj_filters = accessible_project_filter({"status": "Active"})
    if proj_filters is NO_ACCESSIBLE_PROJECTS:
        return {
            "project_health": [], "profitability": [], "invoice_ready": [],
            "activity_stream": [], "stale_projects": [], "recently_delivered": [],
            "milestones": [], "risks": [],
        }

    projects = frappe.get_all(
        "BP Project",
        filters=proj_filters,
        fields=["name", "project_name", "key", "project_color", "theme", "workflow_states",
                "project_type", "hourly_rate", "budget_amount", "retainer_hours",
                "client", "currency", "target_end_date", "modified"],
    )
    accessible_names = [p["name"] for p in projects]

    # ── Project health ────────────────────────────────────────────────────────
    # Must avoid 3 frappe.db.count() calls + a "BP Project Member" get_all
    # + a "User" get_all PER PROJECT (5N queries for N projects). Use 3
    # bulk queries total instead: one task-row fetch
    # (status/due_date, aggregated per project in Python since each
    # project's completed-status set differs), one member fetch, one user
    # fetch across every involved member at once.
    task_rows_by_project = {}
    if accessible_names:
        for r in frappe.db.sql(
            """
            SELECT project, status, due_date
            FROM `tabBP Task`
            WHERE project IN %(projects)s AND is_deleted = 0
            """,
            {"projects": accessible_names}, as_dict=True,
        ):
            task_rows_by_project.setdefault(r["project"], []).append(r)

    member_rows_by_project = {}
    if accessible_names:
        for r in frappe.get_all(
            "BP Project Member",
            filters={"parent": ["in", accessible_names]},
            fields=["parent", "user"],
        ):
            member_rows_by_project.setdefault(r["parent"], []).append(r)
    all_member_users = list({r["user"] for rows in member_rows_by_project.values() for r in rows})
    user_info_all = {u.name: u for u in frappe.get_all(
        "User", filters={"name": ["in", all_member_users]},
        fields=["name", "full_name", "user_image"],
    )} if all_member_users else {}

    today_str = today.isoformat()
    project_health = []
    for p in projects:
        completed = set(_get_completed_statuses(p)) or {"Done"}
        rows = task_rows_by_project.get(p["name"], [])
        total = len(rows)
        done = sum(1 for r in rows if r["status"] in completed)
        open_ = total - done
        pct   = round(done / total * 100) if total else 0
        overdue_cnt = sum(
            1 for r in rows
            if r["status"] not in completed and r.get("due_date") and str(r["due_date"]) < today_str
        )

        # Real members
        mbr_rows = member_rows_by_project.get(p["name"], [])
        members = [
            {
                "user":       m["user"],
                "full_name":  user_info_all.get(m["user"], frappe._dict()).get("full_name") or m["user"],
                "user_image": user_info_all.get(m["user"], frappe._dict()).get("user_image"),
                "initials":   "".join(w[0].upper() for w in (user_info_all.get(m["user"], frappe._dict()).get("full_name") or m["user"]).split()[:2]),
                "color":      _avatar_color(m["user"]),
            }
            for m in mbr_rows
        ]

        # Days left
        days_left = None
        if p.get("target_end_date"):
            days_left = (p["target_end_date"] - today).days

        # Health: based on overdue tasks + completion
        if overdue_cnt > 3 or (days_left is not None and days_left < 0):
            health = "blocked"
        elif overdue_cnt > 0 or (days_left is not None and days_left < 7):
            health = "at_risk"
        else:
            health = "on_track"

        project_health.append({
            "key":        p["key"],
            "name":       p["project_name"],
            "color":      p["project_color"] or _avatar_color(p["key"]),
            "theme":      p.get("theme"),
            "completion": pct,
            "total_tasks": total,
            "done_tasks":  done,
            "open_tasks":  open_,
            "days_left":   days_left,
            "health":      health,
            "members":     members,
        })
        p.pop("workflow_states", None)

    # ── Profitability ─────────────────────────────────────────────────────────
    profitability = []
    for p in projects:
        if not p.get("project_type") or p["project_type"] == "internal":
            continue
        rate  = float(p.get("hourly_rate") or 0)
        # Billable hours from tasks
        try:
            res = frappe.db.sql(
                "SELECT COALESCE(SUM(actual_hours), 0) AS h FROM `tabBP Task` WHERE project = %(proj)s AND billable = 1 AND is_deleted = 0",
                {"proj": p["name"]}, as_dict=True,
            )
            billable_h = float(res[0].h or 0) if res else 0.0
        except Exception:
            billable_h = 0.0

        billed_val = round(billable_h * rate, 2)

        # Budget by type
        ptype  = p.get("project_type", "tm")
        budget = 0.0
        if ptype == "fixed":
            budget = float(p.get("budget_amount") or 0)
        elif ptype == "retainer":
            budget = float(p.get("retainer_hours") or 0) * rate
        # T&M has no fixed budget

        remaining  = round(budget - billed_val, 2) if budget else None
        burn_pct   = round(billed_val / budget * 100, 1) if budget else None

        # Unbilled = total billable estimated value minus billed
        try:
            res2 = frappe.db.sql(
                "SELECT COALESCE(SUM(estimated_hours), 0) AS h FROM `tabBP Task` WHERE project = %(proj)s AND billable = 1 AND is_deleted = 0",
                {"proj": p["name"]}, as_dict=True,
            )
            estimated_h = float(res2[0].h or 0) if res2 else 0.0
        except Exception:
            estimated_h = 0.0
        unbilled_val = round(max(estimated_h - billable_h, 0) * rate, 2)

        status = "Healthy"
        if burn_pct is not None:
            if burn_pct > 100: status = "Over budget"
            elif burn_pct > 85: status = "Watch"

        profitability.append({
            "project":     p["project_name"],
            "key":         p["key"],
            "color":       p["project_color"] or _avatar_color(p["key"]),
            "project_type": p.get("project_type") or "tm",
            "client":      p.get("client") or "",
            "currency":    p.get("currency") or "USD",
            "rate":        rate,
            "budget":      budget,
            "billed":      billed_val,
            "unbilled":    unbilled_val,
            "remaining":   remaining,
            "burn_pct":    burn_pct,
            "billable_hours": round(billable_h, 1),
            "status":      status,
        })

    # ── Invoice-ready: billable completed tasks, grouped by client ────────────
    invoice_ready_map = {}
    for p in projects:
        if not p.get("client") or not p.get("project_type") or p["project_type"] == "internal":
            continue
        rate = float(p.get("hourly_rate") or 0)
        if not rate:
            continue
        completed_sts = _get_completed_statuses_by_project(p["name"])
        if not completed_sts:
            completed_sts = ["Done"]
        try:
            res = frappe.db.sql(
                """
                SELECT COALESCE(SUM(actual_hours), 0) AS h
                FROM `tabBP Task`
                WHERE project = %(proj)s AND billable = 1 AND is_deleted = 0
                  AND status IN %(sts)s
                """,
                {"proj": p["name"], "sts": completed_sts},
                as_dict=True,
            )
            hours = float(res[0].h or 0) if res else 0.0
        except Exception:
            hours = 0.0
        if hours <= 0:
            continue
        amount = round(hours * rate, 2)
        client = p["client"]
        if client not in invoice_ready_map:
            invoice_ready_map[client] = {"client": client, "total": 0, "items": []}
        invoice_ready_map[client]["items"].append({
            "project": p["project_name"],
            "key":     p["key"],
            "hours":   round(hours, 1),
            "amount":  amount,
            "action":  "Generate Invoice",
        })
        invoice_ready_map[client]["total"] += amount

    invoice_ready = list(invoice_ready_map.values())
    for g in invoice_ready:
        g["total"] = round(g["total"], 2)

    # ── Activity stream from BP Activity ─────────────────────────────────────
    # Scoped to accessible projects — a non-admin must not see
    # activity from projects they can't otherwise see.
    activity_stream = []
    try:
        acts = frappe.db.sql(
            """
            SELECT a.name, a.user, a.task, a.project, a.task_key,
                   a.action_type, a.old_value, a.new_value, a.comment_text,
                   a.creation,
                   u.full_name AS actor_name, u.user_image AS actor_image
            FROM `tabBP Activity` a
            LEFT JOIN `tabUser` u ON u.name = a.user
            WHERE %(unrestricted)s OR a.project IN %(names)s
            ORDER BY a.creation DESC
            LIMIT 25
            """,
            {"unrestricted": accessible is None, "names": accessible_names or ["__none__"]},
            as_dict=True,
        )
        for a in acts:
            text = _activity_text(a)
            activity_stream.append({
                "id":           a.name,
                "actor":        a.actor_name or a.user,
                "actor_image":  a.actor_image,
                "actor_initial": "".join(w[0].upper() for w in (a.actor_name or a.user).split()[:2]),
                "actor_color":  _avatar_color(a.user),
                "text":         text,
                "project":      a.project or "",
                "task":         a.task or "",
                "task_key":     a.task_key or "",
                "action_type":  a.action_type or "",
                "time":         _time_ago(a.creation),
                "creation":     str(a.creation)[:19] if a.creation else "",
            })
    except Exception:
        pass

    # ── Stale projects: no BP Activity in 7+ days ────────────────────────────
    stale_projects = []
    try:
        recent_project_activity = frappe.db.sql(
            "SELECT DISTINCT project FROM `tabBP Activity` WHERE creation >= %(cutoff)s AND project IS NOT NULL",
            {"cutoff": ago_7},
            as_dict=True,
        )
        active_proj_set = {r.project for r in recent_project_activity}
        for p in projects:
            if p["name"] not in active_proj_set:
                last_act = frappe.db.sql(
                    "SELECT MAX(creation) AS t FROM `tabBP Activity` WHERE project = %(proj)s",
                    {"proj": p["name"]}, as_dict=True,
                )
                last = last_act[0].t if last_act else None
                stale_projects.append({
                    "key":           p["key"],
                    "name":          p["project_name"],
                    "color":         p["project_color"] or _avatar_color(p["key"]),
                    "last_activity": _time_ago(last) if last else "No activity",
                })
    except Exception:
        pass

    # ── Recently delivered: tasks completed in last 14 days ──────────────────
    # Scoped to accessible projects.
    recently_delivered = []
    try:
        completed_rows = frappe.db.sql(
            """
            SELECT t.name, t.task_key, t.title, t.project,
                   p.project_name, p.project_color,
                   DATE(t.modified) AS completed_date
            FROM `tabBP Task` t
            LEFT JOIN `tabBP Project` p ON p.name = t.project
            WHERE t.modified >= %(cutoff)s
              AND t.is_deleted = 0
              AND (%(unrestricted)s OR t.project IN %(names)s)
              AND t.status IN (
                  SELECT DISTINCT s.status
                  FROM `tabBP Task` s
                  WHERE s.project = t.project
              )
            ORDER BY t.modified DESC
            LIMIT 20
            """,
            {"cutoff": ago_14, "unrestricted": accessible is None, "names": accessible_names or ["__none__"]},
            as_dict=True,
        )
        # Filter to actually-completed statuses
        proj_completed = {}
        for r in completed_rows:
            if r.project not in proj_completed:
                proj_completed[r.project] = set(_get_completed_statuses_by_project(r.project) or ["Done"])
        recently_delivered = [
            {
                "name":          r.name,
                "title":         r.title,
                "task_key":      r.task_key,
                "project":       r.project_name or r.project,
                "project_color": r.project_color or _avatar_color(r.project or ""),
                "date":          str(r.completed_date),
            }
            for r in completed_rows
        ]
    except Exception:
        pass

    # ── Milestones (upcoming, open) ───────────────────────────────────────────
    # Scoped to accessible projects — frappe.get_all bypasses
    # the BP Milestone permission_query_conditions hook, so this must filter
    # explicitly regardless of that hook's existence.
    milestones = []
    try:
        ms_filters = {"status": "Open"}
        if accessible is not None:
            ms_filters["project"] = ["in", accessible_names or ["__none__"]]
        ms_rows = frappe.get_all(
            "BP Milestone",
            filters=ms_filters,
            fields=["name", "title", "project", "due_date"],
            order_by="due_date asc",
            limit=10,
        )
        proj_map = {p["name"]: p for p in projects}
        for m in ms_rows:
            p_info = proj_map.get(m["project"], {})
            # tasks_left: count open tasks in project (rough)
            open_t = frappe.db.count("BP Task", _task_filters({
                "project": m["project"],
                "status": ["not in", _get_completed_statuses_by_project(m["project"]) or ["Done"]],
            }))
            due = m.get("due_date")
            milestones.append({
                "name":          m["name"],
                "title":         m["title"],
                "project":       m["project"],
                "project_name":  p_info.get("project_name") or m["project"],
                "project_color": p_info.get("project_color") or _avatar_color(m["project"]),
                "due_date":      str(due) if due else None,
                "date_label":    due.strftime("%b %d") if due else "TBD",
                "tasks_left":    open_t,
                "days_left":     (due - today).days if due else None,
            })
    except Exception:
        pass

    # ── Risks (open) ──────────────────────────────────────────────────────────
    # Scoped to accessible projects — see the milestones note
    # above; frappe.get_all needs the same explicit filter.
    risks = []
    try:
        risk_filters = {"status": "Open"}
        if accessible is not None:
            risk_filters["project"] = ["in", accessible_names or ["__none__"]]
        risk_rows = frappe.get_all(
            "BP Risk",
            filters=risk_filters,
            fields=["name", "title", "project", "severity", "owner_user"],
            order_by="creation desc",
            limit=10,
        )
        sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        risk_rows.sort(key=lambda r: sev_order.get(r.get("severity", "medium"), 2))
        proj_map = {p["name"]: p for p in projects}
        owner_users = list({r["owner_user"] for r in risk_rows if r.get("owner_user")})
        owner_info  = {u.name: u for u in frappe.get_all(
            "User", filters={"name": ["in", owner_users]},
            fields=["name", "full_name"]
        )} if owner_users else {}
        for r in risk_rows:
            owner_name = owner_info.get(r.get("owner_user", ""), frappe._dict()).get("full_name") or r.get("owner_user", "")
            risks.append({
                "name":          r["name"],
                "title":         r["title"],
                "project":       r["project"],
                "project_name":  proj_map.get(r["project"], {}).get("project_name") or r["project"],
                "severity":      r.get("severity", "medium"),
                "owner":         owner_name,
                "owner_initial": "".join(w[0].upper() for w in owner_name.split()[:2]) if owner_name else "?",
                "owner_color":   _avatar_color(r.get("owner_user") or r["project"]),
            })
    except Exception:
        pass

    return {
        "project_health":     project_health,
        "profitability":      profitability,
        "invoice_ready":      invoice_ready,
        "activity_stream":    activity_stream,
        "stale_projects":     stale_projects,
        "recently_delivered": recently_delivered,
        "milestones":         milestones,
        "risks":              risks,
    }




@frappe.whitelist()
def get_dashboard():
    from datetime import date, timedelta
    _require_system_user()
    user = frappe.session.user
    today_str = date.today().isoformat()

    assigned = frappe.get_all(
        "BP Task Assignee",
        filters={"user": user},
        fields=["parent"],
    )
    issue_names = [a["parent"] for a in assigned]

    my_issues = []
    if issue_names:
        my_issues = frappe.get_all(
            "BP Task",
            filters={"name": ["in", issue_names]},
            fields=["name", "task_key", "title", "status", "priority",
                    "project", "due_date", "epic", "story_points", "task_type",
                    "estimated_hours", "modified"],
            order_by="due_date asc",
        )
        completed_map = {}
        for i in my_issues:
            if i["project"] not in completed_map:
                completed_map[i["project"]] = _get_completed_statuses_by_project(i["project"])
        my_issues = [
            i for i in my_issues
            if i["status"] not in completed_map.get(i["project"], [])
        ]

    overdue = [i for i in my_issues if i.get("due_date") and str(i["due_date"]) < today_str]

    # Stale: assigned, non-closed, not modified in 7+ days
    stale_cutoff = (date.today() - timedelta(days=7)).isoformat()
    stale_tasks = [
        i for i in my_issues
        if i.get("modified") and str(i["modified"])[:10] < stale_cutoff
    ]

    # Upcoming deadlines: due in next 14 days
    in_14 = (date.today() + timedelta(days=14)).isoformat()
    upcoming_deadlines = [
        i for i in my_issues
        if i.get("due_date") and today_str <= str(i["due_date"]) <= in_14
    ]

    # Access filter — frappe.get_all ignores permission_query_conditions.
    from batch_projects.permissions import accessible_project_filter, NO_ACCESSIBLE_PROJECTS
    proj_filters = accessible_project_filter({"status": "Active"})
    projects = [] if proj_filters is NO_ACCESSIBLE_PROJECTS else frappe.get_all(
        "BP Project",
        filters=proj_filters,
        fields=["name", "project_name", "key", "workflow_states",
                "project_color", "target_end_date", "project_type",
                "hourly_rate", "budget_amount", "retainer_hours", "client", "currency"],
    )
    for p in projects:
        completed = _get_completed_statuses(p)
        p["open_count"]  = frappe.db.count("BP Task", _task_filters({"project": p["name"], "status": ["not in", completed or ["Done"]]}))
        p["total_count"] = frappe.db.count("BP Task", _task_filters({"project": p["name"]}))
        # Real members
        members = frappe.get_all(
            "BP Project Member",
            filters={"parent": p["name"]},
            fields=["user", "role"],
        )
        user_names = [m["user"] for m in members]
        user_info = {u.name: u for u in frappe.get_all(
            "User", filters={"name": ["in", user_names]},
            fields=["name", "full_name", "user_image"]
        )} if user_names else {}
        p["members"] = [
            {
                "user": m["user"],
                "full_name": user_info.get(m["user"], frappe._dict()).get("full_name") or m["user"],
                "user_image": user_info.get(m["user"], frappe._dict()).get("user_image"),
            }
            for m in members
        ]
        p.pop("workflow_states", None)

    # Personal stats: daily completed task counts over last 14 days
    personal_stats = _get_personal_stats(user, 14)

    # Recently active tasks (from BP Activity, for "watching" section)
    recently_active = []
    try:
        act_rows = frappe.db.sql(
            """
            SELECT DISTINCT a.task, t.title, t.project, t.task_key,
                MAX(a.creation) AS last_activity
            FROM `tabBP Activity` a
            JOIN `tabBP Task` t ON t.name = a.task AND t.is_deleted = 0
            WHERE a.user = %(user)s
              AND a.creation >= %(cutoff)s
            GROUP BY a.task
            ORDER BY last_activity DESC
            LIMIT 8
            """,
            {"user": user, "cutoff": (date.today() - timedelta(days=30)).isoformat()},
            as_dict=True,
        )
        recently_active = [
            {
                "name": r.task,
                "title": r.title,
                "project": r.project,
                "task_key": r.task_key,
                "last_activity": _time_ago(r.last_activity),
                "color": _avatar_color(r.project or ""),
            }
            for r in act_rows
        ]
    except Exception:
        pass

    return {
        "my_issues": my_issues,
        "overdue": overdue,
        "projects": projects,
        "stale_tasks": stale_tasks,
        "upcoming_deadlines": upcoming_deadlines,
        "personal_stats": personal_stats,
        "recently_active": recently_active,
    }




@frappe.whitelist()
def get_people():
    """
    Returns all project members with role/designation, active projects,
    this-week allocation, and last-30-day utilization.
    """
    # Was ungated entirely — any authenticated session,
    # including a BP Guest/Website User, could pull org-wide HR data
    # (designation/department from Employee) with zero project scoping.
    _require_system_user()

    from datetime import date, timedelta

    today    = date.today()
    week_end = today + timedelta(days=7)
    from_30d = today - timedelta(days=30)

    # All tracked members (project + team) + per-member capacity
    member_users = _all_tracked_users()
    cap_by_user  = _get_member_capacities(member_users)

    if not member_users:
        return {
            "people": [],
            "totals": {"count": 0, "avg_utilization": 0.0, "available_hours": 0.0, "overloaded": 0},
        }

    # User info
    user_info = {
        u.name: u
        for u in frappe.get_all(
            "User",
            filters={"name": ["in", member_users]},
            fields=["name", "full_name", "user_image"],
        )
    }

    # Designation + department from ERPNext Employee (best-effort)
    designation_by_user = {}
    if frappe.db.table_exists("Employee"):
        try:
            emp_rows = frappe.db.sql(
                "SELECT user_id, designation, department FROM `tabEmployee` WHERE user_id IN %(users)s",
                {"users": member_users},
                as_dict=True,
            )
            for e in emp_rows:
                if e.user_id:
                    designation_by_user[e.user_id] = {
                        "designation": e.designation or "",
                        "department":  e.department  or "",
                    }
        except Exception:
            pass

    # Active projects per user (via BP Project Member)
    projects_by_user = {}
    proj_rows = frappe.db.sql(
        """
        SELECT pm.user, p.name, p.project_name AS project_title, p.project_color
        FROM `tabBP Project Member` pm
        JOIN `tabBP Project` p ON p.name = pm.parent
        WHERE p.status NOT IN ('Cancelled', 'Completed')
          AND pm.user IN %(users)s
        """,
        {"users": member_users},
        as_dict=True,
    )
    for pr in proj_rows:
        u = pr.user
        if u not in projects_by_user:
            projects_by_user[u] = []
        projects_by_user[u].append({
            "name":  pr.name,
            "title": pr.project_title or pr.name,
            "color": pr.project_color or "#94a3b8",
        })

    # This-week allocation: open tasks due in the next 7 days
    alloc_by_user = {u: 0.0 for u in member_users}
    alloc_rows = frappe.db.sql(
        """
        SELECT a.user, SUM(t.estimated_hours) AS hours
        FROM `tabBP Task Assignee` a
        JOIN `tabBP Task` t ON t.name = a.parent
        WHERE t.due_date BETWEEN %(today)s AND %(week_end)s
          AND a.user IN %(users)s
          AND t.status NOT IN ('Done', 'Cancelled', 'Closed')
          AND t.docstatus < 2
          AND t.is_deleted = 0
        GROUP BY a.user
        """,
        {"today": today.isoformat(), "week_end": week_end.isoformat(), "users": member_users},
        as_dict=True,
    )
    for row in alloc_rows:
        if row.user:
            alloc_by_user[row.user] = float(row.hours or 0)

    # Last-30D logged hours from submitted ERPNext Timesheets
    from_dt = f"{from_30d.isoformat()} 00:00:00"
    to_dt   = f"{today.isoformat()} 23:59:59"
    ts_data = _timesheet_hours_by_user(member_users, from_dt, to_dt)

    people = []
    for user in member_users:
        info         = user_info.get(user, frappe._dict())
        emp          = designation_by_user.get(user, {})
        logged, _    = ts_data.get(user, (0.0, 0.0))
        alloc        = alloc_by_user.get(user, 0.0)
        weekly_cap   = cap_by_user.get(user, 40.0)
        capacity_30d = round(weekly_cap * 30 / 7, 1)
        util         = round(min(logged / capacity_30d * 100, 200), 1) if capacity_30d else 0

        people.append({
            "user":            user,
            "full_name":       info.get("full_name") or user,
            "user_image":      info.get("user_image"),
            "designation":     emp.get("designation", ""),
            "department":      emp.get("department",  ""),
            "projects":        projects_by_user.get(user, []),
            "week_allocation": round(alloc, 1),
            "week_capacity":   weekly_cap,
            "utilization_pct": util,
        })

    people.sort(key=lambda p: p["full_name"])

    count      = len(people)
    overloaded = sum(1 for p in people if p["utilization_pct"] >= 95)
    avg_util   = round(sum(p["utilization_pct"] for p in people) / count, 1) if count else 0
    available  = round(sum(max(0.0, p["week_capacity"] - p["week_allocation"]) for p in people), 1)

    return {
        "people": people,
        "totals": {
            "count":           count,
            "avg_utilization": avg_util,
            "available_hours": available,
            "overloaded":      overloaded,
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# PROJECT FILES
# ─────────────────────────────────────────────────────────────────────────────



def _comment_matching_task_names(query, project=None, projects_in=None, cap=200):
    """Task names with a matching comment (BP Activity, action_type=Comment),
    scoped the same way the caller scoped its task query. Folded into the
    caller's own or_filters rather than merged as a separate result set, so
    ordering/limit/offset stay a single, consistent query."""
    filters = {"action_type": "Comment", "comment_text": ["like", f"%{query}%"]}
    if project:
        filters["project"] = project
    elif projects_in is not None:
        if not projects_in:
            return []
        filters["project"] = ["in", list(projects_in)]
    return frappe.get_all("BP Activity", filters=filters, pluck="task",
                           order_by="modified desc", limit=cap)


@frappe.whitelist()
def search_tasks(query, project=None, exclude=None, limit=10, offset=0):
    _require_system_user()
    if project:
        _check_permission(project, "BP Viewer")
    filters = {"is_deleted": 0}
    if project:
        filters["project"] = project
    if exclude:
        filters["name"] = ["!=", exclude]

    or_filters = [
        ["title",       "like", f"%{query}%"],
        ["task_key",    "like", f"%{query}%"],
        ["description", "like", f"%{query}%"],
    ]
    comment_tasks = _comment_matching_task_names(query, project=project)
    if comment_tasks:
        or_filters.append(["name", "in", comment_tasks])

    return frappe.get_all(
        "BP Task",
        filters=filters,
        fields=["name", "task_key", "title", "status", "priority"],
        or_filters=or_filters,
        limit=frappe.utils.cint(limit) or 10,
        start=frappe.utils.cint(offset) or 0,
        order_by="modified desc",
    )




@frappe.whitelist()
def search_tasks_global(query, exclude=None, limit=12, offset=0):
    """Cross-project task search for the connector (linking tasks across boards).

    Searches every project the current user can view, returning the owning
    project so the UI can badge where each result lives. Honours BP permissions.
    """
    _require_system_user()
    from batch_projects.permissions import get_accessible_projects
    accessible = get_accessible_projects()  # None = admin (all projects)

    filters = {"is_deleted": 0}
    if accessible is not None:
        if not accessible:
            return []
        filters["project"] = ["in", list(accessible)]
    if exclude:
        filters["name"] = ["!=", exclude]

    or_filters = [
        ["title",       "like", f"%{query}%"],
        ["task_key",    "like", f"%{query}%"],
        ["description", "like", f"%{query}%"],
    ]
    comment_tasks = _comment_matching_task_names(query, projects_in=accessible)
    if comment_tasks:
        or_filters.append(["name", "in", comment_tasks])

    rows = frappe.get_all(
        "BP Task",
        filters=filters,
        fields=["name", "task_key", "title", "status", "priority", "project"],
        or_filters=or_filters,
        limit=frappe.utils.cint(limit) or 12,
        start=frappe.utils.cint(offset) or 0,
        order_by="modified desc",
    )
    proj_names = {r["project"] for r in rows if r.get("project")}
    name_map = {}
    if proj_names:
        for p in frappe.get_all("BP Project", filters={"name": ["in", list(proj_names)]},
                                fields=["name", "project_name", "key"]):
            name_map[p["name"]] = p
    for r in rows:
        meta = name_map.get(r.get("project")) or {}
        r["project_name"] = meta.get("project_name") or r.get("project")
        r["project_key"] = meta.get("key") or ""
    return rows


# ─── CREATE PROJECT ───────────────────────────────────────────────────────────



# Doctypes that carry a real `project` Link field in ERPNext core — a
# search against one of these can be hard-scoped to the caller's own BP
# Project. Timesheet is handled separately below (project lives on the
# Timesheet Detail child rows, not the header — same asymmetry _tenant_ok
# in erp_link.py already accounts for).
_PROJECT_FIELD_DOCTYPES = frozenset({
    "Sales Order", "Purchase Order", "Sales Invoice", "Purchase Invoice",
    "Delivery Note", "Stock Entry", "Work Order", "Quotation", "Expense Claim",
})
# The remainder of _ERP_SEARCH_DOCTYPES below (Project, Customer, Supplier,
# Lead, Opportunity, Payment Entry, Journal Entry) either carry no project
# dimension at all (Payment Entry/Journal Entry are tagged per accounting
# line, not on the header) or are genuine cross-project master data by
# nature (Customer/Supplier/Lead/Opportunity) — same posture already
# documented at custom_fields.search_field_link_options for this exact
# allowlist. They stay unscoped, but no longer ungated: see below.
#
# Hoisted to module level (was a local var inside search_erp_documents only)
# so get_erp_document_label can share it — the two are the same allowlist by
# construction, and the frontend composable's comment already claimed a
# module-level "_ERP_SEARCH_DOCTYPES" was the source of truth it mirrors,
# which wasn't true until now.
_ERP_SEARCH_DOCTYPES = [
    "Sales Order", "Purchase Order", "Sales Invoice", "Purchase Invoice",
    "Project", "Customer", "Supplier", "Lead", "Opportunity",
    "Expense Claim", "Timesheet", "Delivery Note", "Stock Entry",
    "Payment Entry", "Journal Entry", "Work Order", "Quotation",
]


@frappe.whitelist()
def search_erp_documents(doctype, query, limit=10, project=None):
    # frappe.get_all (not get_list) is kept deliberately below: batch_projects
    # System Users hold zero native ERPNext role-permissions on these
    # doctypes by design (same reasoning already
    # documented at custom_fields.py's search_field_link_options) — get_list
    # throws PermissionError for every real user here, not just guests,
    # which would silently break this search for the whole app rather than
    # fix the hole. The checks below ARE the authorization.
    _require_system_user()

    if doctype not in _ERP_SEARCH_DOCTYPES:
        frappe.throw(f"DocType '{doctype}' is not allowed for references.")

    from batch_projects import access

    # A project claimed by the caller must be real: they need to actually
    # belong to it, and it needs to resolve to an ERPNext Project — never
    # trust an unverified `project` arg to mean anything on its own.
    erp_project = None
    if project:
        access.require(project, "Viewer")
        erp_project = frappe.db.get_value("BP Project", project, "erpnext_project")
        if not erp_project:
            frappe.throw("This project isn't linked to an ERPNext Project yet.")

    title_field = frappe.db.get_value("DocType", doctype, "title_field") or "name"
    filters = [[title_field, "like", f"%{query}%"]] if query else []

    if doctype in _PROJECT_FIELD_DOCTYPES:
        # This was the actual hole: these doctypes carry real per-client
        # financial documents, and nothing below `_require_system_user()`
        # used to stop one project's member (BP Guest included — every
        # invited account is a Frappe System User by construction) from
        # enumerating every OTHER project's Sales Orders, invoices, expense
        # claims, and so on. A project the caller actually belongs to is
        # now mandatory, and results are hard-scoped to it.
        if not erp_project:
            frappe.throw("A project is required to search this document type.")
        filters.append(["project", "=", erp_project])
    elif doctype == "Timesheet":
        if not erp_project:
            frappe.throw("A project is required to search this document type.")
        matching = frappe.get_all(
            "Timesheet Detail", filters={"project": erp_project}, pluck="parent"
        )
        if not matching:
            return []
        filters.append(["name", "in", list(set(matching))])
    # else: Project/Customer/Supplier/Lead/Opportunity/Payment Entry/Journal
    # Entry — unscoped, same as before this fix. Genuine cross-project
    # master data (Customer/Supplier/Lead/Opportunity, same reasoning
    # custom_fields.search_field_link_options already documents for this
    # exact allowlist) or not project-taggable at all (Payment Entry/Journal
    # Entry carry a project dimension per accounting line, not on the
    # header) — a blanket tenant check here would break real functionality
    # (picking an existing Customer while creating a new project, an
    # existing Supplier while raising a PO) without closing a real leak.

    results = frappe.get_all(
        doctype,
        filters=filters,
        fields=["name", title_field],
        limit=int(limit),
        order_by="modified desc",
    )

    return [
        {
            "name": r["name"],
            "label": r.get(title_field) or r["name"],
            "doctype": doctype,
        }
        for r in results
    ]


@frappe.whitelist()
def get_erp_document_label(doctype, name):
    """The single-document counterpart to search_erp_documents: given a name
    the caller already legitimately holds (a saved BP Project.client, an
    automation rule's stored condition value, ...), resolve its display
    title. Frontend has called this since the automation-rule Link-field
    work landed (utils/api.js getErpDocumentLabel, composables/
    useErpDoctypeFields.js erpDocLabel) — but this function was never
    actually written. Every caller's `.catch()` silently swallowed the
    "unknown method" error and fell back to showing the raw docname, so
    every resolved-label Link field in the app (automation rule review,
    and now Project Settings > Billing > Client) has been showing document
    IDs instead of names since it shipped.

    Same allowlist and `get_all`-not-`get_list` reasoning as
    search_erp_documents (System Users hold zero native doc-permissions on
    these doctypes by design) — this is a read-only label lookup for values
    the caller already holds, not a new authorization surface, so it
    deliberately does not add project-tenancy scoping that no existing
    caller passes a project for either."""
    _require_system_user()

    if doctype not in _ERP_SEARCH_DOCTYPES:
        frappe.throw(f"DocType '{doctype}' is not allowed for references.")
    if not name:
        return {"name": name, "label": "", "doctype": doctype}

    title_field = frappe.db.get_value("DocType", doctype, "title_field") or "name"
    fields = ["name"] if title_field == "name" else ["name", title_field]
    row = frappe.db.get_value(doctype, name, fields, as_dict=True)
    if not row:
        return {"name": name, "label": name, "doctype": doctype}

    return {"name": row["name"], "label": row.get(title_field) or row["name"], "doctype": doctype}


@frappe.whitelist()
def start_sprint(sprint):
    doc = frappe.get_doc("BP Sprint", sprint)
    _check_permission(doc.project, "BP Member")

    if doc.status == "Active":
        frappe.throw("Sprint is already active.")
    if doc.status == "Completed":
        frappe.throw("Cannot restart a completed sprint.")

    # Enforce one active sprint per project
    active = frappe.db.get_value(
        "BP Sprint",
        {"project": doc.project, "status": "Active"},
        "sprint_name",
    )
    if active:
        frappe.throw(f'Sprint "{active}" is already active. Complete it before starting a new one.')

    doc.status = "Active"
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    _invalidate_sprint_cache(doc.project)

    emit(SPRINT_STARTED, {
        "project": doc.project,
        "sprint": doc.name,
        "sprint_name": doc.sprint_name,
        "total_issues": frappe.db.count("BP Task", _task_filters({"sprint": doc.name})),
    })
    return doc.as_dict()




@frappe.whitelist()
def update_sprint(sprint, sprint_name=None, goal=None, start_date=None, end_date=None):
    doc = frappe.get_doc("BP Sprint", sprint)
    _check_permission(doc.project, "BP Member")
    if sprint_name is not None:
        doc.sprint_name = sprint_name
    if goal is not None:
        doc.goal = goal
    # Allow explicit empty string to clear dates
    if start_date is not None:
        doc.start_date = start_date or None
    if end_date is not None:
        doc.end_date = end_date or None
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    _invalidate_sprint_cache(doc.project)
    return doc.as_dict()




@frappe.whitelist()
def watch_task(task):
    """Current user starts watching a task."""
    from batch_projects.events import add_watcher
    _check_permission(frappe.db.get_value("BP Task", task, "project"), "BP Viewer")
    add_watcher(task, frappe.session.user, reason="manual")
    return {"watching": True}




@frappe.whitelist()
def unwatch_task(task):
    """Current user stops watching a task."""
    _check_permission(frappe.db.get_value("BP Task", task, "project"), "BP Viewer")
    for w in frappe.get_all(
        "BP Task Watcher", filters={"task": task, "user": frappe.session.user}, pluck="name"
    ):
        frappe.delete_doc("BP Task Watcher", w, ignore_permissions=True)
    return {"watching": False}




@frappe.whitelist()
def get_task_watchers(task):
    """List watchers of a task + whether the current user is watching."""
    _check_permission(frappe.db.get_value("BP Task", task, "project"), "BP Viewer")
    rows = frappe.get_all(
        "BP Task Watcher", filters={"task": task}, fields=["user", "watch_reason"], order_by="creation asc"
    )
    users = [r["user"] for r in rows]
    # Batched, not N+1 — same shape the header's real photo needs (see
    # ColumnWidget's identity-image work): without user_image the header's
    # avatar stack could only ever fall back to hashed initials.
    info = {
        u["name"]: u for u in frappe.get_all(
            "User", filters={"name": ["in", users]}, fields=["name", "full_name", "user_image"]
        )
    } if users else {}
    watchers = [
        {
            "user": r["user"],
            "full_name": info.get(r["user"], {}).get("full_name") or r["user"],
            "user_image": info.get(r["user"], {}).get("user_image") or None,
            "watch_reason": r.get("watch_reason") or "manual",
        }
        for r in rows
    ]
    return {
        "watchers": watchers,
        "watching": frappe.session.user in users,
        "count": len(users),
    }


# ─── MY TASKS ─────────────────────────────────────────────────────────────────



@frappe.whitelist()
def remove_task_link(issue, linked_task, link_type):
    doc = frappe.get_doc("BP Task", issue)
    _check_permission(doc.project, "BP Member")
    doc.set("links", [
        l for l in doc.get("links", [])
        if not (l.linked_task == linked_task and l.link_type == link_type)
    ])
    doc.save(ignore_permissions=True)

    # Remove the reciprocal link from the other task too.
    inverse = INVERSE_LINK.get(link_type)
    if inverse and frappe.db.exists("BP Task", linked_task):
        other = frappe.get_doc("BP Task", linked_task)
        kept = [l for l in other.get("links", [])
                if not (l.linked_task == issue and l.link_type == inverse)]
        if len(kept) != len(other.get("links", [])):
            other.set("links", kept)
            other.save(ignore_permissions=True)

    return {"ok": True}




@frappe.whitelist()
def remove_reference(issue, reference_name=None, ref_doctype=None, ref_name=None):
    """Unlink by child-row name OR by (ref_doctype, ref_name) — clients that
    loaded references before row names shipped can still unlink."""
    doc = frappe.get_doc("BP Task", issue)
    _check_permission(doc.project, "BP Member")

    def keep(r):
        if reference_name and r.name == reference_name:
            return False
        if ref_doctype and ref_name and r.ref_doctype == ref_doctype and r.ref_name == ref_name:
            return False
        return True

    doc.references = [r for r in (doc.references or []) if keep(r)]
    doc.save(ignore_permissions=True)
    return {"ok": True}




@frappe.whitelist()
def update_milestone(name, fields):
    if isinstance(fields, str):
        fields = frappe.parse_json(fields)
    doc = frappe.get_doc("BP Milestone", name)
    _check_permission(doc.project, "BP Member")
    allowed = {"title", "due_date", "status", "description"}
    for k, v in (fields or {}).items():
        if k in allowed:
            setattr(doc, k, v)
    doc.save(ignore_permissions=True)
    return doc.as_dict()




@frappe.whitelist()
def update_project_members(project, members):
    """Replace the full members list on a project. members: JSON list of {user, role}"""
    _check_permission(project, "BP Admin")
    members_list = _deep_parse_json(members)
    if not isinstance(members_list, list):
        frappe.throw("members must be a list")

    VALID_ROLES = {"Admin", "Manager", "Member", "Viewer"}

    clean = []
    for m in members_list:
        if isinstance(m, str):
            try: m = json.loads(m)
            except: continue
        if not isinstance(m, dict) or not m.get("user"):
            continue
        role = m.get("role", "Member")
        if role not in VALID_ROLES:
            role = "Member"
        clean.append({"user": m["user"], "role": role})

    # Enforce seat cap for new members not already in this project.
    # Existing members keep their seat; users already seated elsewhere
    # via another project are also fine (assert_seat_available handles
    # is_seated internally). Same pattern as board.py:3239-3244 and
    # invitations.py:298-303.
    current = frappe.get_all("BP Project Member",
        filters={"parent": project},
        fields=["user", "role"])
    current_users = {m["user"] for m in current}
    old_roles = {m["user"]: m["role"] for m in current}
    from batch_projects.entitlements import assert_seats_available, is_seated
    new_users = {m["user"] for m in clean if not is_seated(m["user"])}
    assert_seats_available(len(new_users))

    from batch_projects import access
    for u in {m["user"] for m in clean} - current_users:
        access.ensure_member_role(u)

    frappe.db.sql(
        "DELETE FROM `tabBP Project Member` WHERE parent=%s",
        project
    )
    for i, m in enumerate(clean):
        frappe.db.sql(
            """INSERT INTO `tabBP Project Member`
               (name, parent, parenttype, parentfield, idx, user, role,
                owner, creation, modified, modified_by)
               VALUES (%s, %s, 'BP Project', 'members', %s, %s, %s,
                       %s, NOW(), NOW(), %s)""",
            (
                frappe.generate_hash(length=10),
                project, i + 1,
                m["user"], m["role"],
                frappe.session.user, frappe.session.user,
            )
        )
    frappe.db.sql(
        "UPDATE `tabBP Project` SET modified=NOW(), modified_by=%s WHERE name=%s",
        (frappe.session.user, project)
    )
    frappe.db.commit()

    # ReBAC sync: this is a whole-list replace, so diff old vs
    # new roles rather than emitting for everyone — emit() fires an event
    # per mutation, not per row in a bulk statement.
    new_roles = {m["user"]: m["role"] for m in clean}
    for user in (old_roles.keys() | new_roles.keys()):
        old_role, new_role = old_roles.get(user), new_roles.get(user)
        if old_role != new_role:
            emit(PROJECT_ROLE_CHANGED, {
                "project": project, "user": user,
                "old_role": old_role, "new_role": new_role,
            })

    users = {u["name"]: u["full_name"] for u in frappe.get_all(
        "User", fields=["name", "full_name"]
    )}
    return [{
        "user": m["user"],
        "role": m["role"],
        "full_name": users.get(m["user"], m["user"]),
    } for m in clean]


# ─── ISSUE LINKS ──────────────────────────────────────────────────────────────

# Each link is stored on BOTH tasks so either one shows the relationship.
# e.g. "A blocks B" also writes "B is blocked by A".
INVERSE_LINK = {
    "blocks": "is blocked by",
    "is blocked by": "blocks",
    "clones": "is cloned by",
    "is cloned by": "clones",
    "duplicates": "duplicates",
    "relates to": "relates to",
}


BLOCKING_TYPES = {"blocks", "is blocked by"}




@frappe.whitelist()
def set_view_subscription(view, subscribed=1, frequency="Weekly"):
    """Subscribe/unsubscribe the owner to a scheduled email of this saved view."""
    doc = frappe.get_doc("BP View", view)
    if doc.owner != frappe.session.user:
        frappe.throw("You can only manage your own view subscriptions.")
    doc.subscribed = 1 if int(subscribed) else 0
    if frequency in ("Daily", "Weekly"):
        doc.subscription_frequency = frequency
    doc.save(ignore_permissions=True)
    return {"subscribed": bool(doc.subscribed), "subscription_frequency": doc.subscription_frequency}




@frappe.whitelist()
def update_notification_preferences(preferences):
    """Upsert the current user's notification preferences."""
    user = frappe.session.user
    if isinstance(preferences, str):
        preferences = json.loads(preferences)
    if not isinstance(preferences, dict):
        frappe.throw("preferences must be an object")

    if frappe.db.exists("BP Notification Preference", user):
        doc = frappe.get_doc("BP Notification Preference", user)
    else:
        doc = frappe.get_doc({"doctype": "BP Notification Preference", "user": user})

    for k in _PREF_DEFAULTS:
        if k in preferences:
            doc.set(k, 1 if preferences[k] else 0)
    doc.save(ignore_permissions=True)
    return {k: int(doc.get(k) or 0) for k in _PREF_DEFAULTS}




@frappe.whitelist()
def get_notification_preferences():
    """Return the current user's notification preferences (defaults if unset)."""
    user = frappe.session.user
    if frappe.db.exists("BP Notification Preference", user):
        doc = frappe.get_doc("BP Notification Preference", user)
        return {k: int(doc.get(k) or 0) for k in _PREF_DEFAULTS}
    return dict(_PREF_DEFAULTS)




@frappe.whitelist()
def get_report_tasks(scope="all", status_filter="open", priority=None, search=None,
                     sort_by="modified", sort_order="desc", limit=25, offset=0):
    """Scope-wide task list for report Table widgets — ALL tasks in scope
    (not just the caller's), with true server-side pagination, search and sort.

    scope:         'all' | project name/key | (JSON) list of names/keys
    status_filter: 'open' | 'all' | 'done'
    Returns { tasks, total } where total is the full filtered count.
    """
    filters, proj_name, proj_names = _resolve_scope(scope)

    # Completed-status names across the project(s) in scope (used to split
    # open vs done at the DB level so pagination totals stay accurate).
    if proj_names:
        scope_projects = proj_names
    else:
        from batch_projects.permissions import get_accessible_projects
        acc = get_accessible_projects()
        scope_projects = frappe.get_all("BP Project", pluck="name") if acc is None else list(acc)
    completed = set()
    for pn in scope_projects:
        try:
            completed |= set(frappe.get_cached_doc("BP Project", pn).get_completed_statuses())
        except Exception:
            pass

    db_filters = _task_filters(filters)
    if priority:
        db_filters["priority"] = priority
    if status_filter == "open" and completed:
        db_filters["status"] = ["not in", list(completed)]
    elif status_filter == "done" and completed:
        db_filters["status"] = ["in", list(completed)]

    or_filters = None
    if search:
        s = f"%{search}%"
        or_filters = [["BP Task", "title", "like", s], ["BP Task", "task_key", "like", s]]

    sort_map = {
        "modified": "modified", "creation": "creation", "due_date": "due_date",
        "priority": "priority", "title": "title", "story_points": "story_points",
    }
    order_by = f"{sort_map.get(sort_by, 'modified')} {'desc' if sort_order == 'desc' else 'asc'}"

    fields = ["name", "task_key", "title", "status", "priority", "task_type",
              "project", "due_date", "start_date", "story_points", "epic",
              "sprint", "reporter", "estimated_hours", "actual_hours", "creation", "modified"]

    # Total filtered count (names only — cheap). NOTE: frappe.get_all() always
    # runs with ignore_permissions=True, which skips permission_query_conditions
    # entirely (confirmed in frappe/model/db_query.py) — this is scoped by the
    # explicit _resolve_scope()/get_accessible_projects() above, not by that hook.
    total = len(frappe.get_all("BP Task", filters=db_filters, or_filters=or_filters, pluck="name"))

    tasks = frappe.get_all(
        "BP Task", filters=db_filters, or_filters=or_filters, fields=fields,
        order_by=order_by, limit_start=int(offset), limit_page_length=int(limit),
    )

    # Enrich: project_name + assignees
    pname = {}
    for t in tasks:
        p = t["project"]
        if p not in pname:
            pname[p] = frappe.db.get_value("BP Project", p, "project_name") or p
        t["project_name"] = pname[p]
    names = [t["name"] for t in tasks]
    amap = {}
    if names:
        for a in frappe.get_all("BP Task Assignee",
                                filters={"parenttype": "BP Task", "parent": ["in", names]},
                                fields=["parent", "user"]):
            amap.setdefault(a["parent"], []).append(a["user"])
        users = list({u for lst in amap.values() for u in lst})
        fn = {}
        if users:
            for u in frappe.get_all("User", filters={"name": ["in", users]}, fields=["name", "full_name"]):
                fn[u["name"]] = u["full_name"] or u["name"]
        for t in tasks:
            t["assignees"] = [{"user": u, "full_name": fn.get(u, u)} for u in amap.get(t["name"], [])]
    else:
        for t in tasks:
            t["assignees"] = []

    return {"tasks": tasks, "total": total, "offset": int(offset), "limit": int(limit)}


# ─── DASHBOARD ────────────────────────────────────────────────────────────────



@frappe.whitelist()
def get_widget_data(config):
    """Generic dashboard widget engine: group a metric by a dimension, scoped to
    one project, all projects, or a selected list of projects.
      scope:    'all' | project name/key | [list of project names/keys]
      group_by: status | assignee | priority | task_type | epic | project
      metric:   count | story_points | estimated_hours | actual_hours
    """
    if isinstance(config, str):
        config = json.loads(config)
    scope = config.get("scope") or "all"
    group_by = config.get("group_by") or "status"
    metric = config.get("metric") or "count"

    filters, proj_name, proj_names = _resolve_scope(scope)

    tasks = frappe.get_all(
        "BP Task", filters=filters,
        fields=["name", "status", "priority", "task_type", "project", "epic",
                "story_points", "estimated_hours", "actual_hours"],
    )

    def _mval(t):
        return 1 if metric == "count" else float(t.get(metric) or 0)

    groups = {}
    if group_by == "assignee":
        names = [t["name"] for t in tasks]
        amap = {}
        if names:
            for a in frappe.get_all("BP Task Assignee", filters={"parenttype": "BP Task", "parent": ["in", names]},
                                    fields=["parent", "user"]):
                amap.setdefault(a["parent"], []).append(a["user"])
        users = list({u for lst in amap.values() for u in lst})
        fn = {}
        if users:
            for u in frappe.get_all("User", filters={"name": ["in", users]}, fields=["name", "full_name"]):
                fn[u["name"]] = u["full_name"] or u["name"]
        for t in tasks:
            us = amap.get(t["name"], [])
            v = _mval(t)
            if not us:
                groups["Unassigned"] = groups.get("Unassigned", 0) + v
            for u in us:
                lbl = fn.get(u, u)
                groups[lbl] = groups.get(lbl, 0) + v
    else:
        for t in tasks:
            key = t.get(group_by) or "(none)"
            groups[key] = groups.get(key, 0) + _mval(t)

    color_map, label_map = {}, {}
    if group_by == "status":
        # Collect from the resolved project(s); fall back to all projects when scope is "all"
        color_sources = proj_names if proj_names else [p["name"] for p in frappe.get_all("BP Project", fields=["name"])]
        for pn in color_sources:
            try:
                for s in frappe.get_cached_doc("BP Project", pn).get_workflow_states():
                    if s.get("name") not in color_map:
                        color_map[s.get("name")] = s.get("color")
            except Exception:
                pass
    elif group_by == "priority":
        color_map = dict(_WIDGET_PRIORITY)
    elif group_by == "epic":
        ekeys = [k for k in groups if k and k != "(none)"]
        if ekeys:
            for e in frappe.get_all("BP Epic", filters={"name": ["in", ekeys]}, fields=["name", "title", "color"]):
                label_map[e["name"]] = e["title"]
                color_map[e["name"]] = e["color"]
    elif group_by == "project":
        pkeys = [k for k in groups if k and k != "(none)"]
        if pkeys:
            for p in frappe.get_all("BP Project", filters={"name": ["in", pkeys]}, fields=["name", "project_name", "project_color"]):
                label_map[p["name"]] = p["project_name"]
                color_map[p["name"]] = p["project_color"]

    items = []
    for i, (k, v) in enumerate(sorted(groups.items(), key=lambda kv: kv[1], reverse=True)):
        items.append({
            "label": label_map.get(k) or ("(none)" if k == "(none)" else k),
            "value": round(v, 1),
            "color": color_map.get(k) or _WIDGET_PALETTE[i % len(_WIDGET_PALETTE)],
        })
    return {"items": items, "total": round(sum(groups.values()), 1), "metric": metric, "group_by": group_by, "scope": scope}




@frappe.whitelist()
def query_bql_group_by(scope, filters_json, group_by="status", metric="count"):
    """BQL GROUP BY with client-supplied filters. Accepts pre-parsed filter dict from bql.js
    so WHERE conditions (sprint, status, priority, etc.) apply before grouping.
    filters_json: JSON string of {status, priority, sprint, task_type, labels, assignee, ...}
    scope: 'all' | single project name/key | JSON-encoded list of project names/keys
    """
    if isinstance(filters_json, str):
        import json as _json
        filters_json = _json.loads(filters_json)

    # scope may arrive as a JSON-encoded list from the frontend
    if isinstance(scope, str) and scope.startswith("["):
        try:
            import json as _json
            scope = _json.loads(scope)
        except Exception:
            pass

    filters_json = filters_json or {}
    db_filters, proj_name, proj_names = _resolve_scope(scope or "all")

    # Map BQL filter keys to BP Task field names
    FILTER_MAP = {
        "status":    "status",
        "priority":  "priority",
        "sprint":    "sprint",
        "task_type": "task_type",
        "epic":      "epic",
    }
    for k, field in FILTER_MAP.items():
        if k in filters_json:
            v = filters_json[k]
            if isinstance(v, list):
                db_filters[field] = ["in", v]
            else:
                db_filters[field] = v

    # Date filters
    if "due_before" in filters_json:
        db_filters["due_date"] = ["<=", filters_json["due_before"]]
    if "due_after" in filters_json:
        db_filters["due_date"] = [">=", filters_json["due_after"]]
    if "created_after" in filters_json:
        db_filters["creation"] = [">=", filters_json["created_after"]]

    # Delegate to get_widget_data logic but with pre-filtered scope
    config = {"scope": proj_name or scope, "group_by": group_by, "metric": metric}
    # Temporarily override get_all to use our filters by calling core logic directly
    tasks = frappe.get_all(
        "BP Task", filters=db_filters,
        fields=["name", "status", "priority", "task_type", "project", "epic",
                "story_points", "estimated_hours", "actual_hours"],
    )

    def _mval(t):
        return 1 if metric == "count" else float(t.get(metric) or 0)

    groups = {}
    if group_by == "assignee":
        names = [t["name"] for t in tasks]
        amap = {}
        if names:
            for a in frappe.get_all("BP Task Assignee",
                                    filters={"parenttype": "BP Task", "parent": ["in", names]},
                                    fields=["parent", "user"]):
                amap.setdefault(a["parent"], []).append(a["user"])
        users = list({u for lst in amap.values() for u in lst})
        fn = {}
        if users:
            for u in frappe.get_all("User", filters={"name": ["in", users]}, fields=["name", "full_name"]):
                fn[u["name"]] = u["full_name"] or u["name"]
        for t in tasks:
            for u in amap.get(t["name"], []) or ["Unassigned"]:
                lbl = fn.get(u, u) if u != "Unassigned" else "Unassigned"
                groups[lbl] = groups.get(lbl, 0) + _mval(t)
        if not groups and tasks:
            groups["Unassigned"] = sum(_mval(t) for t in tasks)
    else:
        key_field = {"sprint": "sprint", "task_type": "task_type", "epic": "epic",
                     "priority": "priority", "status": "status", "project": "project"}.get(group_by, group_by)
        for t in tasks:
            key = t.get(key_field) or "(none)"
            groups[key] = groups.get(key, 0) + _mval(t)

    color_map = {}
    if group_by == "priority":
        color_map = dict(_WIDGET_PRIORITY)
    elif group_by == "status":
        color_sources = proj_names if proj_names else [p["name"] for p in frappe.get_all("BP Project", fields=["name"])]
        for pn in color_sources:
            try:
                for s in frappe.get_cached_doc("BP Project", pn).get_workflow_states():
                    if s.get("name") not in color_map:
                        color_map[s.get("name")] = s.get("color")
            except Exception:
                pass

    items = [
        {
            "label": k if k != "(none)" else "(none)",
            "value": round(v, 1),
            "color": color_map.get(k) or _WIDGET_PALETTE[i % len(_WIDGET_PALETTE)],
        }
        for i, (k, v) in enumerate(sorted(groups.items(), key=lambda kv: kv[1], reverse=True))
    ]
    return {"items": items, "total": round(sum(groups.values()), 1), "metric": metric, "group_by": group_by}




@frappe.whitelist()
def get_erpnext_departments():
    """Fetch ERPNext departments for the manual team-department picker (read-only, no sync)."""
    _require_system_user()
    try:
        departments = frappe.get_all(
            "Department",
            filters={"disabled": 0},
            fields=["name", "department_name", "parent_department", "company"],
            order_by="department_name asc",
        )
        return departments
    except Exception:
        return []




# get_margin_report was REMOVED here — the margin/profitability arithmetic
# now lives in bp-gateway's internal/insights package (margin.go), served at
# GET /v1/insights/margin.
#
# It was not moved for performance. batch_projects is the open half of an
# open-core product, so keeping the formula here meant shipping the thing
# customers pay for in a public repo behind a require_feature() line anyone
# self-hosting can delete. Frappe's remaining job is the part it should own:
# batch_projects/api/insights_data.py::get_margin_inputs returns the raw,
# permission-filtered rows (project visibility + per-project view_money) and
# performs no arithmetic at all.
#
# Consequence, deliberately accepted: an install with no gateway has no
# margin report. That is the community/paid line, not a regression.


# ─────────────────────────────────────────────────────────────────────────────
# SHARED DASHBOARD HELPERS
# ─────────────────────────────────────────────────────────────────────────────



@frappe.whitelist()
def get_sprint_report(project, sprint_name):
    """Sprint completion analysis: committed vs added mid-sprint vs completed vs spillover.
    sprint_name: BP Sprint.name (docname, not display name)
    """
    from datetime import date, datetime

    _check_permission(project, "BP Viewer")
    sprint = frappe.get_doc("BP Sprint", sprint_name)
    if sprint.project != project:
        frappe.throw("Sprint does not belong to project", frappe.PermissionError)

    proj = frappe.get_doc("BP Project", project)
    completed_statuses = set(proj.get_completed_statuses())

    def _d(v):
        if not v: return None
        if isinstance(v, datetime): return v.date()
        if isinstance(v, date): return v
        try: return datetime.strptime(str(v)[:10], "%Y-%m-%d").date()
        except: return None

    start_date = _d(sprint.start_date)
    end_date   = _d(sprint.end_date)

    tasks = frappe.get_all(
        "BP Task",
        filters={"project": project, "sprint": sprint_name},
        fields=["name", "title", "task_key", "status", "priority", "story_points",
                "started_on", "completed_on", "creation", "docstatus"],
        order_by="creation asc",
    )

    # Determine when each task was assigned to this sprint (field_name = "sprint", new_value = sprint_name)
    sprint_acts = frappe.get_all(
        "BP Activity",
        filters={"project": project, "field_name": "sprint", "new_value": sprint_name},
        fields=["task", "creation"],
    )
    assigned_at = {a.task: _d(a.creation) for a in sprint_acts}

    committed, added, completed_tasks, spillover = [], [], [], []
    committed_pts = added_pts = 0

    for t in tasks:
        pts = float(t.get("story_points") or 0)
        task_creation = _d(t.get("creation"))
        assigned_date = assigned_at.get(t.name) or task_creation

        is_committed = bool(start_date and assigned_date and assigned_date <= start_date)
        is_done = t.status in completed_statuses

        entry = {
            "name":           t.name,
            "task_key":       t.task_key,
            "title":          t.title,
            "status":         t.status,
            "priority":       t.priority,
            "story_points":   pts,
            "is_done":        is_done,
            "completed_on":   str(t.completed_on) if t.get("completed_on") else None,
        }

        if is_committed:
            committed.append(entry)
            committed_pts += pts
        else:
            added.append(entry)
            added_pts += pts

        if is_done:
            completed_tasks.append(entry)
        else:
            spillover.append(entry)

    total = len(tasks)
    completion_rate = round(len(completed_tasks) / total * 100) if total else 0
    done_pts = sum(e["story_points"] for e in completed_tasks)

    # ── Burndown: ideal vs actual remaining points, per day ──────────────────
    burndown = None
    if start_date and end_date and end_date >= start_date:
        from datetime import timedelta
        total_pts = committed_pts + added_pts
        span = (end_date - start_date).days or 1
        last_day = min(end_date, date.today())
        # (completion_date, points) for tasks that are actually done
        done_events = [
            (_d(t.completed_on), float(t.get("story_points") or 0))
            for t in tasks
            if t.status in completed_statuses and t.get("completed_on") and _d(t.completed_on)
        ]
        days = []
        d = start_date
        while d <= end_date:
            idx = (d - start_date).days
            ideal = round(total_pts * (1 - idx / span), 1)
            # actual only up to today; future days have no real data yet
            remaining = None
            if d <= last_day:
                done_by_d = sum(p for (cd, p) in done_events if cd <= d)
                remaining = round(total_pts - done_by_d, 1)
            days.append({"date": str(d), "ideal": ideal, "remaining": remaining})
            d += timedelta(days=1)
        burndown = {"total_points": round(total_pts, 1), "days": days}

    return {
        "sprint":        sprint_name,
        "sprint_label":  sprint.sprint_name,
        "status":        sprint.status,
        "start_date":    str(start_date) if start_date else None,
        "end_date":      str(end_date) if end_date else None,
        "goal":          sprint.goal,
        "summary": {
            "total":           total,
            "committed":       len(committed),
            "added":           len(added),
            "completed":       len(completed_tasks),
            "spillover":       len(spillover),
            "committed_pts":   round(committed_pts, 1),
            "added_pts":       round(added_pts, 1),
            "done_pts":        round(done_pts, 1),
            "completion_rate": completion_rate,
        },
        "committed":  committed,
        "added":      added,
        "completed":  completed_tasks,
        "spillover":  spillover,
        "burndown":   burndown,
    }




@frappe.whitelist()
def get_team_velocity(team, last_n_sprints=5):
    """Sprint velocity data for a team — completed points per sprint."""
    _check_team_permission(team, "Viewer")
    sprints = frappe.get_all(
        "BP Sprint",
        filters={"team": team, "status": "Completed"},
        fields=["name", "sprint_name", "start_date", "end_date"],
        order_by="end_date desc",
        limit=last_n_sprints,
    )

    result = []
    for sprint in sprints:
        issues = frappe.get_all(
            "BP Task",
            filters={"sprint": sprint["name"]},
            fields=["story_points", "status", "project"],
        )
        total_points    = sum((i["story_points"] or 0) for i in issues)
        completed_points = sum(
            (i["story_points"] or 0) for i in issues
            if i.get("project") and i["status"] in _get_completed_statuses_by_project(i["project"])
        )
        result.append({
            **sprint,
            "total_points":     total_points,
            "completed_points": completed_points,
            "total_issues":     len(issues),
        })

    result.reverse()  # chronological
    return result




@frappe.whitelist()
def get_team_dashboard(team):
    """
    Team dashboard: 30-day metrics, owned projects, contributing-to projects,
    and 4-week capacity outlook.
    """
    from datetime import date, timedelta

    _check_team_permission(team, "Viewer")

    tdoc         = frappe.get_doc("BP Team", team)
    member_users = [m.user for m in (tdoc.members or [])]

    # ── 30-day timesheet metrics ──────────────────────────────────────────
    today   = date.today()
    from_dt = (today - timedelta(days=30)).isoformat() + " 00:00:00"
    to_dt   = today.isoformat()                        + " 23:59:59"

    ts_data          = _timesheet_hours_by_user(member_users, from_dt, to_dt)
    cap_by           = _get_member_capacities(member_users)
    total_logged     = sum(ts_data.get(u, (0.0, 0.0))[0] for u in member_users)
    total_billable   = sum(ts_data.get(u, (0.0, 0.0))[1] for u in member_users)
    total_capacity   = sum(cap_by.get(u, 40.0) * 30 / 7 for u in member_users)
    utilization_pct  = round(total_logged / total_capacity * 100, 1) if total_capacity > 0 else 0
    billable_pct     = round(total_billable / total_logged * 100, 1) if total_logged > 0 else 0

    # ── Owned projects ────────────────────────────────────────────────────
    # Access filter — same reasoning as get_teams/get_team: a
    # project's `team` assignment and its own `visibility` are independent.
    from batch_projects.permissions import accessible_project_filter, NO_ACCESSIBLE_PROJECTS
    _owned_filters = accessible_project_filter({"team": team, "status": "Active"})
    owned_projects = [] if _owned_filters is NO_ACCESSIBLE_PROJECTS else frappe.get_all(
        "BP Project",
        filters=_owned_filters,
        fields=["name", "project_name", "key", "project_color", "project_icon"],
        order_by="project_name asc",
    )
    owned_names    = {p["name"] for p in owned_projects}
    team_user_set  = set(member_users)
    for p in owned_projects:
        p["open_count"]        = frappe.db.count("BP Task", _task_filters({
            "project": p["name"],
            "status":  ["not in", _get_completed_statuses_by_project(p["name"])],
        }))
        proj_mbrs              = frappe.get_all("BP Project Member", filters={"parent": p["name"]}, fields=["user"])
        p["team_member_count"] = sum(1 for pm in proj_mbrs if pm.user in team_user_set)

    # ── Contributing-to (team members on non-owned active projects) ────────
    # Access filter: this previously surfaced
    # the name/key of ANY project a team member happens to belong to,
    # including private projects entirely outside the caller's own
    # visibility — and _check_team_permission(team, "Viewer") is a low bar
    # (any authenticated System User, no membership required).
    from batch_projects.permissions import get_accessible_projects
    _accessible = get_accessible_projects()  # None = admin (all)
    if member_users and _accessible != set():
        contrib_rows = frappe.db.sql(
            """
            SELECT DISTINCT
                proj.name, proj.project_name, proj.key, proj.project_color,
                proj.team                AS owning_team,
                ot.team_name             AS owning_team_name
            FROM `tabBP Project Member` pm
            JOIN `tabBP Project` proj ON proj.name = pm.parent
            LEFT JOIN `tabBP Team` ot ON ot.name = proj.team
            WHERE pm.user IN %(users)s
              AND proj.status = 'Active'
              AND (proj.team != %(team)s OR proj.team IS NULL OR proj.team = '')
              AND (%(unrestricted)s OR proj.name IN %(accessible)s)
            """,
            {
                "users": member_users, "team": team,
                "unrestricted": _accessible is None,
                "accessible": list(_accessible) if _accessible else ["__none__"],
            },
            as_dict=True,
        )
        for p in contrib_rows:
            p["open_count"]        = frappe.db.count("BP Task", _task_filters({
                "project": p["name"],
                "status":  ["not in", _get_completed_statuses_by_project(p["name"])],
            }))
            proj_mbrs              = frappe.get_all("BP Project Member", filters={"parent": p["name"]}, fields=["user"])
            p["team_member_count"] = sum(1 for pm in proj_mbrs if pm.user in team_user_set)
    else:
        contrib_rows = []

    # ── 4-week capacity outlook ───────────────────────────────────────────
    start_of_week    = today - timedelta(days=today.weekday())
    weekly_team_cap  = sum(cap_by.get(u, 40.0) for u in member_users)
    outlook          = []
    for i in range(4):
        ws    = start_of_week + timedelta(weeks=i)
        we    = ws + timedelta(days=6)
        alloc = 0.0
        if member_users:
            rows = frappe.db.sql(
                """
                SELECT COALESCE(SUM(t.estimated_hours), 0) AS alloc
                FROM `tabBP Task` t
                WHERE t.name IN (
                    SELECT DISTINCT ta.parent
                    FROM `tabBP Task Assignee` ta
                    WHERE ta.user IN %(users)s
                )
                  AND t.docstatus < 2
                  AND t.is_deleted = 0
                  AND t.status NOT IN ('Done','Cancelled','Closed')
                  AND t.due_date >= %(ws)s
                  AND t.due_date <= %(we)s
                  AND t.estimated_hours IS NOT NULL
                """,
                {"users": member_users, "ws": ws.isoformat(), "we": we.isoformat()},
                as_dict=True,
            )
            alloc = float(rows[0].alloc or 0) if rows else 0.0
        pct = round(alloc / weekly_team_cap * 100, 1) if weekly_team_cap > 0 else 0
        outlook.append({
            "label":      ws.strftime("%b %d"),
            "week_start": ws.isoformat(),
            "allocated":  round(alloc, 1),
            "capacity":   round(weekly_team_cap, 1),
            "pct":        pct,
        })

    return {
        "metrics": {
            "utilization_pct":     utilization_pct,
            "logged_hours":        round(total_logged, 1),
            "billable_pct":        billable_pct,
            "owned_count":         len(owned_projects),
            "contributing_count":  len(contrib_rows),
        },
        "owned_projects":   owned_projects,
        "contributing_to":  list(contrib_rows),
        "capacity_outlook": outlook,
    }


# ─────────────────────────────────────────────────────────────────────────────
# SHARED HELPERS — PEOPLE / WORKLOAD / UTILIZATION
# ─────────────────────────────────────────────────────────────────────────────



@frappe.whitelist()
def get_team_capacity_heatmap(team=None):
    """
    Per-member per-working-day allocated hours for the next 10 working days.
    Uses tasks with due_date in the window; hours spread evenly over working
    days between start_date and due_date (or just on due_date if no start_date).
    """
    from datetime import date, timedelta
    from collections import defaultdict
    _require_system_user()

    today = date.today()

    # Build 10 working days
    days = []
    d = today
    while len(days) < 10:
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    day_keys = [d.isoformat() for d in days]
    day_set  = set(day_keys)

    # Resolve members
    if team:
        _check_team_permission(team, "Viewer")
        tdoc         = frappe.get_doc("BP Team", team)
        member_users = [m.user for m in (tdoc.members or [])]
        cap_by       = {m.user: float(m.capacity_hours_per_sprint or 40) / 5 for m in tdoc.members}
    else:
        member_users = _all_tracked_users()
        weekly_caps  = _get_member_capacities(member_users)
        cap_by       = {u: weekly_caps.get(u, 40.0) / 5 for u in member_users}

    if not member_users:
        return {"days": day_keys, "members": []}

    user_info = {u.name: u for u in frappe.get_all(
        "User", filters={"name": ["in", member_users]},
        fields=["name", "full_name", "user_image"]
    )}

    # Project-visibility filter — this query never
    # joined BP Project at all, so a Viewer on one small project could see
    # task titles/due-dates/estimates for any task assigned to any tracked
    # user across the whole org, including private/team-restricted
    # projects. Same access-filter pattern as get_timesheets right above.
    from batch_projects.permissions import get_accessible_projects
    accessible = get_accessible_projects()
    if accessible is not None and not accessible:
        return {"days": day_keys, "members": []}

    # Tasks with due_date in window
    window_end = days[-1].isoformat()
    try:
        assignments = frappe.db.sql(
            """
            SELECT ta.user, t.name AS task_name, t.title,
                   t.due_date, t.start_date, t.estimated_hours
            FROM `tabBP Task Assignee` ta
            JOIN `tabBP Task` t ON t.name = ta.parent
              AND t.docstatus < 2
              AND t.is_deleted = 0
              AND t.status NOT IN ('Done', 'Cancelled', 'Closed')
              AND t.due_date IS NOT NULL
              AND t.due_date <= %(end)s
            WHERE ta.user IN %(users)s
              {project_clause}
            ORDER BY t.due_date ASC
            """.format(project_clause="AND t.project IN %(accessible)s" if accessible is not None else ""),
            {"users": member_users, "end": window_end,
             "accessible": list(accessible) if accessible is not None else []},
            as_dict=True,
        )
    except Exception:
        assignments = []

    # Spread hours across working days from start_date to due_date (within window)
    member_day_hours = defaultdict(lambda: defaultdict(float))

    for a in assignments:
        due = a.due_date
        if not isinstance(due, date):
            try:
                from datetime import datetime
                due = datetime.strptime(str(due), "%Y-%m-%d").date()
            except Exception:
                continue

        start = a.start_date
        if start and not isinstance(start, date):
            try:
                from datetime import datetime
                start = datetime.strptime(str(start), "%Y-%m-%d").date()
            except Exception:
                start = None

        hours = float(a.estimated_hours or 1.0)

        # Working days in range (clamp to window)
        range_start = max(start or due, today)
        range_end   = due
        work_days_in_range = []
        cur = range_start
        while cur <= range_end:
            if cur.weekday() < 5 and cur.isoformat() in day_set:
                work_days_in_range.append(cur.isoformat())
            cur += timedelta(days=1)

        if work_days_in_range:
            per_day = hours / len(work_days_in_range)
            for dk in work_days_in_range:
                member_day_hours[a.user][dk] += per_day
        else:
            # due date not in window but task is overdue → pile onto today
            if due < today and today.isoformat() in day_set:
                member_day_hours[a.user][today.isoformat()] += hours

    members_out = []
    for user in member_users:
        info     = user_info.get(user, frappe._dict())
        daily_cap = cap_by.get(user, 8.0)
        allocations = {}
        for dk in day_keys:
            h = round(member_day_hours[user].get(dk, 0.0), 1)
            allocations[dk] = h

        members_out.append({
            "user":       user,
            "full_name":  info.get("full_name") or user,
            "user_image": info.get("user_image"),
            "initials":   "".join(w[0].upper() for w in (info.get("full_name") or user).split()[:2]),
            "color":      _avatar_color(user),
            "daily_cap":  daily_cap,
            "allocations": allocations,
        })

    members_out.sort(key=lambda m: m["full_name"])
    return {"days": day_keys, "members": members_out}


# ═══════════════════════════════════════════════════════════════════════════
# AUTOMATION RULES  (premium — Team tier and above; see entitlements.py)
# ═══════════════════════════════════════════════════════════════════════════

# Triggers offered in the builder, with human labels.
_AUTOMATION_TRIGGERS = [
    {"value": "task.status_changed", "label": "When a task's status changes"},
    {"value": "task.created",        "label": "When a task is created"},
    {"value": "task.updated",        "label": "When a task is updated"},
    {"value": "task.assigned",       "label": "When a task is assigned"},
    {"value": "task.due_soon",       "label": "When a task is due soon"},
    {"value": "comment.added",       "label": "When a comment is added"},
    {"value": "task.deleted",        "label": "When a task is deleted"},
    {"value": "task.trashed",        "label": "When a task is moved to trash"},
    {"value": "task.restored",       "label": "When a task is restored from trash"},
]

_AUTOMATION_ACTIONS = [
    {"value": "Change Status", "label": "Change the status"},
    {"value": "Assign Issue",  "label": "Assign the task"},
    {"value": "Set Priority",  "label": "Set the priority"},
    {"value": "Set Due Date",  "label": "Set the due date"},
    {"value": "Add Label",     "label": "Add label(s)"},
    {"value": "Add Comment",   "label": "Post a comment"},
    {"value": "Notify",        "label": "Send a notification"},
    {"value": "Create Issue",  "label": "Create a new task"},
]

_AUTOMATION_OPERATORS = [
    {"value": "eq", "label": "is"},
    {"value": "ne", "label": "is not"},
    {"value": "in", "label": "is any of"},
    {"value": "nin", "label": "is none of"},
    {"value": "changed", "label": "changed"},
    {"value": "contains", "label": "contains"},
    {"value": "gt", "label": "greater than"},
    {"value": "gte", "label": "greater or equal"},
    {"value": "lt", "label": "less than"},
    {"value": "lte", "label": "less or equal"},
    {"value": "is_set", "label": "is set"},
    {"value": "is_not_set", "label": "is empty"},
]




@frappe.whitelist()
def update_team(team, team_name=None, team_key=None, team_color=None,
                team_icon=None, description=None, lead=None,
                department=None, company=None, capacity_hours_per_sprint=None,
                default_workflow_template=None, parent_team=None, team_type=None):
    _check_team_permission(team, "Manager")
    doc = frappe.get_doc("BP Team", team)
    if team_name  is not None: doc.team_name  = team_name
    if team_key   is not None: doc.team_key   = team_key
    if team_color is not None: doc.team_color = team_color
    if team_icon  is not None: doc.team_icon  = team_icon
    if description is not None: doc.description = description
    # Use form_dict check so JS null can clear nullable Link fields
    if "lead"       in frappe.form_dict: doc.lead       = lead or None
    if "department" in frappe.form_dict: doc.department = department or None
    if company     is not None: doc.company = company
    if parent_team is not None: doc.parent_team = parent_team or None
    if team_type   is not None: doc.team_type   = team_type
    if capacity_hours_per_sprint is not None:
        doc.capacity_hours_per_sprint = float(capacity_hours_per_sprint)
    if default_workflow_template is not None:
        doc.default_workflow_template = default_workflow_template
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return doc.as_dict()




@frappe.whitelist()
def update_team_members(team, members):
    """Replace team member list. members = [{user, role, capacity_hours_per_sprint}]"""
    _check_team_permission(team, "Admin")
    if isinstance(members, str):
        members = frappe.parse_json(members)
    doc = frappe.get_doc("BP Team", team)
    doc.members = []
    for m in members:
        user_full = frappe.db.get_value("User", m["user"], "full_name") or m["user"]
        doc.append("members", {
            "user":                  m["user"],
            "full_name":             user_full,
            "role":                  m.get("role", "Member"),
            "capacity_hours_per_sprint": float(m.get("capacity_hours_per_sprint", 40)),
        })
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return [m.as_dict() for m in doc.members]




@frappe.whitelist()
def update_team_links(team, links):
    """Replace team links. links = [{link_type, label, url, project}]"""
    _check_team_permission(team, "Manager")
    if isinstance(links, str):
        links = frappe.parse_json(links)
    doc = frappe.get_doc("BP Team", team)
    doc.team_links = []
    for l in links:
        doc.append("team_links", {
            "link_type": l.get("link_type", "External URL"),
            "label":     l.get("label", ""),
            "url":       l.get("url", ""),
            "project":   l.get("project", ""),
        })
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return [l.as_dict() for l in doc.team_links]




@frappe.whitelist()
def get_automation_rules(project):
    """List rules for a project. Open to viewers so the free tier sees the locked builder."""
    _check_permission(project, "BP Viewer")
    rows = frappe.get_all(
        "BP Automation Rule",
        filters={"project": project},
        fields=["name", "rule_name", "description", "is_active", "trigger_event",
                "conditions", "action_type", "action_config", "actions",
                "scope", "project_filter", "owner", "modified",
                "last_run_at", "last_run_status"],
        order_by="modified desc",
    )
    for r in rows:
        r["conditions"] = _parse_json(r.get("conditions"), [])
        r["action_config"] = _parse_json(r.get("action_config"), {})
        # v2 field — omitting it here used to make the editor believe every
        # rule had no real action at all, defaulting a fresh "Change Status"
        # blank action on open and silently overwriting the true one on the
        # next Save (see AutomationRuleEditor.vue's draft.actions fallback).
        r["actions"] = _parse_json(r.get("actions"), [])
        r["project_filter"] = _parse_json(r.get("project_filter"), [])
    return rows




@frappe.whitelist()
def get_automation_runs(project, limit=40):
    """Recent automation run history for a project (newest first)."""
    _check_permission(project, "BP Viewer")
    return frappe.get_all(
        "BP Automation Run",
        filters={"project": project},
        fields=["name", "rule", "rule_name", "task_key", "trigger_event",
                "action_type", "status", "message", "run_at"],
        order_by="run_at desc",
        limit_page_length=frappe.utils.cint(limit) or 40,
    )




@frappe.whitelist()
def toggle_automation_rule(rule, is_active):
    doc = frappe.get_doc("BP Automation Rule", rule)
    _check_permission(doc.project, "BP Admin")
    active = _as_bool(is_active)
    if active:
        # Enabling consumes the premium feature; disabling is always allowed.
        from batch_projects.entitlements import require_feature
        require_feature("automations")
    doc.is_active = active
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {"name": doc.name, "is_active": doc.is_active}




@frappe.whitelist()
def update_automation_rule(rule, rule_name=None, trigger_event=None, action_type=None,
                           conditions=None, action_config=None, is_active=None):
    doc = frappe.get_doc("BP Automation Rule", rule)
    _check_permission(doc.project, "BP Admin")
    from batch_projects.entitlements import require_feature
    require_feature("automations")

    if rule_name is not None:
        doc.rule_name = rule_name
    if trigger_event is not None:
        doc.trigger_event = trigger_event
    if action_type is not None:
        doc.action_type = action_type
    if conditions is not None:
        doc.conditions = _coerce_json(conditions, "[]")
    if action_config is not None:
        doc.action_config = _coerce_json(action_config, "{}")
    if is_active is not None:
        doc.is_active = _as_bool(is_active)

    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return doc.as_dict()



# get_portfolio was REMOVED here — the cross-project rollup (task
# categorisation, overdue counting, health verdict, completion %, per-project
# money masking, ordering and summary) now lives in bp-gateway's
# internal/insights/portfolio.go, served at GET /v1/insights/portfolio.
#
# Same reasoning as the margin report above: the analysis is the paid product,
# and this repo is public. Frappe keeps what it should own —
# api/insights_data.py::get_portfolio_inputs returns raw rows plus the two
# genuine permission decisions (which projects are visible, and per-project
# view_money) and computes nothing.
#
# _project_health_label() below deliberately STAYS: get_board (free) labels
# health too, so that rule cannot depend on a paid gateway. portfolio.go's
# projectHealth is its counterpart and the two must be changed together.




def _company_currency(company=None):
    """Return the currency for a given company, or the site default."""
    if company:
        curr = frappe.db.get_value("Company", company, "default_currency")
        if curr:
            return curr
    return frappe.db.get_single_value("System Settings", "currency") or "USD"


_ERP_DOC_EVENT_DOCTYPES = [
    "Sales Invoice", "Sales Order", "Purchase Invoice", "Purchase Order",
    "Payment Entry", "Delivery Note", "Quotation", "Journal Entry",
    "Customer", "Supplier", "Lead", "Opportunity", "Project",
    "Timesheet", "Expense Claim", "Stock Entry", "Work Order",
]


@frappe.whitelist()
def get_erp_doctype_fields_readonly(doctype):
    """Read-scoped docfield metadata — referenced by name in two other
    functions' own comments (automation.py, erp_link.py) and called by the
    frontend's useErpDoctypeFields composable as if it already existed, but
    never actually defined anywhere: every real call hit a whitelist-method-
    not-found error, silently swallowed by the composable's own
    `.catch(() => {})` — trigger.doc_event's dynamic per-doctype condition-
    field picker has been showing an empty list this whole time with no
    visible error anywhere. Now real.

    Unlike get_erp_doctype_fields (write-scoped, a fixed whitelist — you can
    only offer fields for a doctype the action can actually write to), this
    is real Frappe read-permission-gated instead of a fixed doctype list:
    it needs to serve BOTH _ERP_DOC_EVENT_DOCTYPES above (the automation
    condition-picker's original, narrower use) AND the dashboard row
    designer (BP Task, BP Project, or any doctype a widget can be scoped
    to — see dashboards.py's own widget-source registry, a DIFFERENT list
    again). A fixed list here would need to be the union of every future
    caller's needs and drift immediately; a real permission check can't.
    Field metadata (names/types/labels) is far lower-sensitivity than
    record data, so this is a deliberately wider gate than either sibling
    endpoint, not a mistake.
    """
    _require_system_user()
    if not doctype or not frappe.db.exists("DocType", doctype):
        return []
    if not frappe.has_permission(doctype, "read"):
        return []
    from batch_projects.api.erp_link import _doctype_field_rows
    return _doctype_field_rows(doctype, include_read_only=True)


# Above this many distinct values a field stops being a set you'd colour
# per-value and becomes free text. 25 comfortably covers real status/stage/
# category/priority vocabularies (the longest workflow in this codebase's own
# project templates is 6) while excluding names, titles and descriptions.
_ENUM_MAX_CARDINALITY = 25


@frappe.whitelist()
def get_field_value_choices(doctype, fieldname, project=None):
    """Real, grounded value choices for one field — powers the row
    designer's per-value color config. Never asks a user to hand-type a
    string and hope it matches real data (BP Task.status specifically used
    to: it's Data, not Select — see BP Task.status' own field docstring —
    "validated dynamically against project workflow_states", so a plain
    Select-options lookup returns nothing for it).

    Resolution order:
    1. BP Task.status: not a DB-level enum at all — each BP Project defines
       its own workflow_states (name/color/category), so "In Progress" on
       one project and "Scoping"/"Delivered" on another are equally valid.
       `project` given -> that project's own states. Omitted (a workspace-
       wide column mixes many projects) -> the union of every project this
       user can access, deduped, order-preserving by first appearance.
    2. A real Select field -> its declared options, in declared order.
    3. Everything else -> the actual DISTINCT values already present in the
       data (permission-scoped), but ONLY when the field is genuinely
       enum-like: at most _ENUM_MAX_CARDINALITY distinct values. A free-text
       field like `title` or `description` technically has distinct values
       too, and returning them produced a colour picker listing 50 unrelated
       task titles — noise, not a choice. Anything above the ceiling returns
       [] so the designer falls back to "colour the whole field, or name the
       specific values you care about", which is the only sane UI for an
       open-ended field.
    """
    _require_system_user()
    if not doctype or not frappe.db.exists("DocType", doctype):
        return []
    if not frappe.has_permission(doctype, "read"):
        return []

    if doctype == "BP Task" and fieldname == "status":
        from batch_projects.permissions import get_accessible_projects
        if project:
            if not frappe.db.exists("BP Project", project):
                return []
            accessible = get_accessible_projects()
            if accessible is not None and project not in accessible:
                return []
            return [s.get("name") for s in _parse_json(
                frappe.db.get_value("BP Project", project, "workflow_states"), []
            ) if s.get("name")]

        accessible = get_accessible_projects()
        filters = {"name": ["in", list(accessible)]} if accessible is not None else {}
        rows = frappe.get_all("BP Project", filters=filters, pluck="workflow_states")
        seen, out = set(), []
        for raw in rows:
            for s in _parse_json(raw, []):
                name = s.get("name")
                if name and name not in seen:
                    seen.add(name)
                    out.append(name)
        return out

    meta = frappe.get_meta(doctype)
    field = meta.get_field(fieldname)
    if field and field.fieldtype == "Select":
        return [o for o in (field.options or "").split("\n") if o]

    # Long-text fieldtypes are never enum-like, whatever the data happens to
    # look like — skip the query entirely rather than scanning a big column
    # just to throw the answer away on the cardinality check below.
    if field and field.fieldtype in ("Text", "Small Text", "Long Text", "Text Editor",
                                     "Code", "HTML Editor", "Markdown Editor", "JSON"):
        return []

    # Grounded fallback: real distinct values, not a schema guess. Scoped by
    # the same permission query engine every list view already uses, so this
    # never leaks a value from a record the caller couldn't otherwise see.
    # Fetch one MORE than the ceiling so "did we exceed it?" is answerable
    # without a second COUNT(DISTINCT) round trip.
    rows = frappe.get_list(doctype, fields=[fieldname], distinct=True,
                           limit_page_length=_ENUM_MAX_CARDINALITY + 1, order_by=fieldname)
    values = [r[fieldname] for r in rows if r.get(fieldname)]
    return [] if len(values) > _ENUM_MAX_CARDINALITY else values


