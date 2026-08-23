"""
batch_projects/permissions.py
─────────────────────────────
Data-layer access control for BP doctypes — the safety net beneath board.py.

board.py's whitelisted endpoints enforce project roles, but they mostly use
frappe.get_all (which ignores user permissions). Anyone hitting the generic
REST API (/api/resource/BP Task) or a report would otherwise bypass all of
it. These hooks close that gap and, in doing so, finally make the project
`visibility` field mean something:

    workspace  — visible to every System User (the default; preserves today's
                 open behavior so existing all-workspace installs don't change)
    team       — visible to members of the project's BP Team (+ project members)
    private    — visible only to explicit BP Project Members

System Managers (and Administrator) see everything.

Wired in hooks.py via `permission_query_conditions` (list/report/REST filtering)
and `has_permission` (single-document gate).
"""

import frappe
import json


# ─── ReBAC push-down ─────────────────────────────────────────────────────
#
# The gateway resolves each caller's allowed projects/tasks against its
# embedded OpenFGA store and hands them down as headers on the proxied
# request — X-BP-Allowed-Projects / X-BP-Allowed-Tasks — so Frappe's own SQL
# still does the actual filtering/pagination (see internal/proxy's Director
# in bp-gateway for the write side and why task IDs are assignee-only, not
# the full viewer closure).

def _rebac_scope(user):
    """(allowed_projects, allowed_tasks) from the gateway's push-down
    headers, or None if they don't apply and the caller should fall back to
    the SQL-hook model below. Trusted ONLY when:

      1. frappe.local._bp_gateway_verified is True — set EXCLUSIVELY by
         gateway_guard.apply_gateway_identity() after a real HMAC check on
         X-BP-Gateway-Sig (see that module's docstring: it runs on every
         request via auth_hooks). A direct-to-Frappe request with no valid
         gateway signature can never set this flag, so it can never reach
         here with a spoofed header trusted.
      2. `user` is the actual authenticated caller for this request — the
         headers describe the CURRENT session only, never an arbitrary
         other user some caller might pass in.

    X-BP-Rebac-Active absent ⇒ the gateway isn't running ReBAC for this
    deployment at all (dev without it, or a request that predates identity
    resolution) — returns None, meaning "use the model below," unchanged
    from before push-down existed. But once X-BP-Rebac-Active IS present,
    it is ALWAYS authoritative, even on a parse failure (returns ([], []),
    not None) — falling back to the SQL model on a malformed header would
    mean a broken gateway response could make access MORE permissive than
    intended, the opposite of fail-closed.
    """
    if not getattr(frappe.local, "_bp_gateway_verified", False):
        return None
    if user != frappe.session.user:
        return None
    if frappe.get_request_header("X-BP-Rebac-Active") != "1":
        return None
    try:
        projects = json.loads(frappe.get_request_header("X-BP-Allowed-Projects") or "[]")
        tasks = json.loads(frappe.get_request_header("X-BP-Allowed-Tasks") or "[]")
        if not isinstance(projects, list) or not isinstance(tasks, list):
            raise ValueError("non-list header payload")
    except (TypeError, ValueError):
        frappe.log_error("rebac: malformed X-BP-Allowed-* header, denying", "bp_rebac_scope")
        return [], []
    return projects, tasks


def _is_admin(user: str) -> bool:
    return user == "Administrator" or "System Manager" in frappe.get_roles(user)


def get_accessible_projects(user: str | None = None):
    """Set of BP Project names `user` may see, or None meaning 'all' (admin).
    Memoized per-request on frappe.local — called on every list query."""
    user = user or frappe.session.user
    if _is_admin(user):
        return None

    cache = getattr(frappe.local, "_bp_accessible_projects", None)
    if cache is None:
        cache = {}
        frappe.local._bp_accessible_projects = cache
    if user in cache:
        return cache[user]

    member = set(frappe.get_all(
        "BP Project Member", filters={"user": user}, pluck="parent"))

    # Guests are scoped strictly to their explicit memberships — no workspace
    # or team fallback. Keeps invited externals out of every other project.
    from batch_projects import access
    if access.is_guest(user):
        cache[user] = member
        return member

    # workspace (and legacy blank) visibility = open to all System Users
    workspace = set(frappe.get_all(
        "BP Project", filters={"visibility": ["in", ["workspace", "", None]]},
        pluck="name"))

    team_projects = set()
    user_teams = frappe.get_all("BP Team Member", filters={"user": user}, pluck="parent")
    if user_teams:
        team_projects = set(frappe.get_all(
            "BP Project",
            filters={"visibility": "team", "team": ["in", list(user_teams)]},
            pluck="name"))

    result = member | workspace | team_projects
    cache[user] = result
    return result


def can_access_project(project: str, user: str | None = None) -> bool:
    accessible = get_accessible_projects(user)
    return accessible is None or project in accessible


# Sentinel distinct from `None` (which means "admin, no restriction needed")
# so callers of accessible_project_filter can tell "unrestricted" apart from
# "restricted to nothing" without re-deriving it themselves.
class _NoAccess:
    pass


NO_ACCESSIBLE_PROJECTS = _NoAccess()


def accessible_project_filter(base_filters: dict | None = None, user: str | None = None):
    """Merge an accessible-projects restriction into `base_filters` for a
    `frappe.get_all("BP Project", filters=...)` call.

    frappe.get_all ignores permission_query_conditions entirely (see the
    module docstring) — every cross-project board.py endpoint that lists
    BP Project directly with get_all must call this or it silently shows
    every project regardless of `visibility`/membership.

    Returns:
      - a filters dict (possibly with `base_filters` untouched, for admins)
      - NO_ACCESSIBLE_PROJECTS if the caller can see zero projects — callers
        must check for this sentinel and short-circuit (return an empty
        result) rather than run a query, since an empty `name in []` filter
        is not guaranteed to short-circuit safely everywhere it's threaded.
    """
    f = dict(base_filters or {})
    accessible = get_accessible_projects(user)
    if accessible is None:
        return f  # admin — unrestricted
    if not accessible:
        return NO_ACCESSIBLE_PROJECTS
    f["name"] = ["in", list(accessible)]
    return f


# ─── permission_query_conditions hooks ───────────────────────────────────────

def _project_in_clause(column: str, user: str) -> str:
    accessible = get_accessible_projects(user)
    if accessible is None:
        return ""           # admin — no restriction
    if not accessible:
        return "1=0"        # access to nothing
    vals = ", ".join(frappe.db.escape(p) for p in accessible)
    return f"{column} in ({vals})"


def _project_in_clause_or_null(column: str, user: str) -> str:
    """Same as _project_in_clause, but for a doctype whose `project` field
    isn't mandatory — some real rows are workspace-scoped (no single
    project), same as BP Report already carves out below. A blank/NULL
    project stays visible to everyone; a set project still follows normal
    project access."""
    accessible = get_accessible_projects(user)
    if accessible is None:
        return ""           # admin — no restriction
    base = f"({column} is null or {column} = '')"
    if not accessible:
        return base
    vals = ", ".join(frappe.db.escape(p) for p in accessible)
    return f"{base} or {column} in ({vals})"


def bp_task_query_conditions(user=None):
    """Project access, OR-ed with tasks this user is an explicit assignee
    on — same task-scoped grant access.require_task enforces
    at the API layer, so an assignee with no other project standing still
    sees their own assigned task in list views/reports, never sibling
    tasks or the project itself (this only ever ADDS specific task names,
    never widens the project-level clause).

    When the gateway's ReBAC push-down is active for this request (see
    _rebac_scope), its resolved lists are used DIRECTLY instead of
    recomputing from BP Project Member/BP Task Assignee here — the gateway
    is the authority once it's in the loop, this just turns its answer
    into SQL.

    Also excludes trashed tasks (is_deleted=1) unconditionally — trash is
    recoverable, not gone, and the app's own get_all()-based endpoints
    exclude it too (see api/board.py's _task_filters). This hook is the
    ONLY thing standing between a trashed task and the generic REST API
    (/api/resource/BP Task), Desk list views, and Report Builder — every
    frappe.get_all() call in this codebase runs with ignore_permissions=True,
    which skips permission_query_conditions entirely (confirmed in
    frappe/model/db_query.py), so this hook covers a DIFFERENT set of call
    sites than api/board.py's explicit filters, not a superset or subset of
    them. Applied even for admins: the dedicated trash view
    (list_deleted_tasks) is the intended way to see it, not a raw list/
    report escaping trash by accident."""
    user = user or frappe.session.user
    not_deleted = "`tabBP Task`.`is_deleted` = 0"

    scope = _rebac_scope(user)
    if scope is not None:
        allowed_projects, allowed_tasks = scope
        parts = []
        if allowed_projects:
            vals = ", ".join(frappe.db.escape(p) for p in allowed_projects)
            parts.append(f"`tabBP Task`.`project` in ({vals})")
        if allowed_tasks:
            vals = ", ".join(frappe.db.escape(t) for t in allowed_tasks)
            parts.append(f"`tabBP Task`.`name` in ({vals})")
        scope_clause = " or ".join(parts) if parts else "1=0"
        return f"({scope_clause}) and {not_deleted}"

    base = _project_in_clause("`tabBP Task`.`project`", user)
    if base == "":
        return not_deleted  # admin — no project restriction, still hide trash
    assigned = f"""`tabBP Task`.`name` in (
        select parent from `tabBP Task Assignee` where user = {frappe.db.escape(user)}
    )"""
    if base == "1=0":
        return f"({assigned}) and {not_deleted}"
    return f"(({base}) or ({assigned})) and {not_deleted}"


def bp_sprint_query_conditions(user=None):
    return _project_in_clause("`tabBP Sprint`.`project`", user or frappe.session.user)


def bp_epic_query_conditions(user=None):
    return _project_in_clause("`tabBP Epic`.`project`", user or frappe.session.user)


def bp_report_query_conditions(user=None):
    """Reports: workspace reports (no project) are visible to all; project
    reports follow project access; private reports are visible only to their
    owner — the list twin of bp_report_has_permission."""
    from batch_projects import access
    user = user or frappe.session.user
    if access.is_instance_admin(user) or access.is_workspace_admin(user):
        return ""
    proj_clause = _project_in_clause_or_null("`tabBP Report`.`project`", user)
    owner = frappe.db.escape(user)
    private_own = f"(`tabBP Report`.`visibility` = 'private' and `tabBP Report`.`owner` = {owner})"
    return f"(`tabBP Report`.`visibility` != 'private' and {proj_clause}) or {private_own}"


def bp_dashboard_query_conditions(user=None):
    """Dashboards: same visibility/ownership list policy as BP Report.
    Previously no query-condition hook existed at all for this doctype."""
    from batch_projects import access
    user = user or frappe.session.user
    if access.is_instance_admin(user) or access.is_workspace_admin(user):
        return ""
    proj_clause = _project_in_clause_or_null("`tabBP Dashboard`.`project`", user)
    owner = frappe.db.escape(user)
    private_own = f"(`tabBP Dashboard`.`visibility` = 'private' and `tabBP Dashboard`.`owner` = {owner})"
    return f"(`tabBP Dashboard`.`visibility` != 'private' and {proj_clause}) or {private_own}"


def bp_project_query_conditions(user=None):
    user = user or frappe.session.user

    scope = _rebac_scope(user)
    if scope is not None:
        allowed_projects, _ = scope
        if not allowed_projects:
            return "1=0"
        vals = ", ".join(frappe.db.escape(p) for p in allowed_projects)
        return f"`tabBP Project`.`name` in ({vals})"

    accessible = get_accessible_projects(user)
    if accessible is None:
        return ""
    if not accessible:
        return "1=0"
    vals = ", ".join(frappe.db.escape(p) for p in accessible)
    return f"`tabBP Project`.`name` in ({vals})"


# BP Milestone, BP Risk and BP Automation Run are project-scoped like BP
# Task/Sprint/Epic above, but are granted to broad stock roles (Projects
# User/Manager) with no permission_query_conditions hook, so frappe.get_all
# is the ONLY thing standing between them and the generic REST API — and
# get_all ignores this hook entirely (see the module docstring), so any
# Projects User could pull every project's milestones (including
# invoice_amount/sales_invoice) via /api/resource directly.
def bp_milestone_query_conditions(user=None):
    return _project_in_clause("`tabBP Milestone`.`project`", user or frappe.session.user)


def bp_risk_query_conditions(user=None):
    return _project_in_clause("`tabBP Risk`.`project`", user or frappe.session.user)


def bp_automation_run_query_conditions(user=None):
    return _project_in_clause("`tabBP Automation Run`.`project`", user or frappe.session.user)


# BP Notification is scoped to its `recipient`, not a project — a user's own
# notifications, never another user's, regardless of project access.
def bp_notification_query_conditions(user=None):
    user = user or frappe.session.user
    if _is_admin(user):
        return ""
    return f"`tabBP Notification`.`recipient` = {frappe.db.escape(user)}"


def bp_notification_has_permission(doc, user=None, permission_type=None):
    user = user or frappe.session.user
    if _is_admin(user):
        return True
    if doc.get("__islocal"):
        return True  # creation handled by the whitelisted API, not raw REST
    return doc.get("recipient") == user


# BP Webhook Token carries a plaintext routing token (the /v1/hooks/<token>
# path segment bp-gateway's webhook HMAC auth
# forwards through, alongside the separately-configured, deployment-wide
# webhook_secret — see internal/premium/premium.go verifySignature; the
# token isn't sufficient alone to forge a call). The doctype grants
# `Projects Manager: read` with no query condition, which is broader than
# the app's own model: the whitelisted API
# (automation.list_webhook_tokens/create_webhook_token/revoke_webhook_token)
# all gate on `access.is_workspace_admin()`, not the much more common
# per-project Projects Manager role. This hook realigns the generic REST
# API to the same bar the app already enforces everywhere else.
def bp_webhook_token_has_permission(doc, user=None, permission_type=None):
    from batch_projects import access
    user = user or frappe.session.user
    return access.is_instance_admin(user) or access.is_workspace_admin(user)


def bp_webhook_token_query_conditions(user=None):
    from batch_projects import access
    user = user or frappe.session.user
    if access.is_instance_admin(user) or access.is_workspace_admin(user):
        return ""
    return "1=0"


# Several more project-scoped BP doctypes carry a `project` field but no
# permission_query_conditions/has_permission hook — same bug class as
# above (frappe.get_all inside board.py is the only thing gating them; the
# generic REST API bypasses that entirely). Their current stock DocPerm
# roles happen to be narrow (mostly
# System Manager only) so this wasn't necessarily live-exploitable for every
# ordinary invited account today, but that's incidental, not a deliberate
# second line of defense — widening a DocPerm role later (an unremarkable-
# looking change) would silently reopen it. Closed the same way every prior
# instance of this bug was: wire the existing _project_in_clause /
# _project_in_clause_or_null primitives, reusing bp_doc_has_permission below
# (already generic — reads doc.get("project") regardless of doctype).
#
# Mandatory `project` (reqd=1 in the doctype JSON) — strict, no null carve-out:
def bp_drawing_query_conditions(user=None):
    return _project_in_clause("`tabBP Drawing`.`project`", user or frappe.session.user)


def bp_intake_form_query_conditions(user=None):
    return _project_in_clause("`tabBP Intake Form`.`project`", user or frappe.session.user)


def bp_invitation_query_conditions(user=None):
    return _project_in_clause("`tabBP Invitation`.`project`", user or frappe.session.user)


def bp_note_query_conditions(user=None):
    return _project_in_clause("`tabBP Note`.`project`", user or frappe.session.user)


def bp_share_link_query_conditions(user=None):
    return _project_in_clause("`tabBP Share Link`.`project`", user or frappe.session.user)


def bp_sla_policy_query_conditions(user=None):
    return _project_in_clause("`tabBP SLA Policy`.`project`", user or frappe.session.user)


def bp_task_template_query_conditions(user=None):
    return _project_in_clause("`tabBP Task Template`.`project`", user or frappe.session.user)


def bp_view_query_conditions(user=None):
    return _project_in_clause("`tabBP View`.`project`", user or frappe.session.user)


# Optional `project` (some real rows are workspace-scoped) — null-safe:
def bp_activity_query_conditions(user=None):
    return _project_in_clause_or_null("`tabBP Activity`.`project`", user or frappe.session.user)


def bp_audit_log_query_conditions(user=None):
    return _project_in_clause_or_null("`tabBP Audit Log`.`project`", user or frappe.session.user)


def bp_automation_rule_query_conditions(user=None):
    return _project_in_clause_or_null("`tabBP Automation Rule`.`project`", user or frappe.session.user)


def bp_notification_mute_query_conditions(user=None):
    from batch_projects import access
    user = user or frappe.session.user
    if access.is_instance_admin(user) or access.is_workspace_admin(user):
        return ""
    return f"`tabBP Notification Mute`.`user` = {frappe.db.escape(user)}"


def bp_notification_rule_query_conditions(user=None):
    return _project_in_clause_or_null("`tabBP Notification Rule`.`project`", user or frappe.session.user)


def bp_sla_breach_query_conditions(user=None):
    return _project_in_clause_or_null("`tabBP SLA Breach`.`project`", user or frappe.session.user)


def bp_task_watcher_query_conditions(user=None):
    return _project_in_clause_or_null("`tabBP Task Watcher`.`project`", user or frappe.session.user)


def bp_view_preference_query_conditions(user=None):
    from batch_projects import access
    user = user or frappe.session.user
    if access.is_instance_admin(user) or access.is_workspace_admin(user):
        return ""
    return f"`tabBP View Preference`.`user` = {frappe.db.escape(user)}"


def bp_workflow_query_conditions(user=None):
    return _project_in_clause_or_null("`tabBP Workflow`.`project`", user or frappe.session.user)


# ─── has_permission hook (single-document gate) ───────────────────────────────

def bp_doc_has_permission(doc, user=None, permission_type=None):
    """Per-document gate for the generic REST API / desk / reports — the
    data-layer twin of board.py `_check_permission`. Both resolve the user's
    effective project role through batch_projects.access, so a request is judged
    the same whether it arrives via a whitelisted endpoint or raw REST.

    permission_type aware: read needs Viewer, write/create need Member,
    delete/submit need Manager (see access.min_role_for_ptype). This is what
    lets "workspace" visibility mean read-only for non-members."""
    from batch_projects import access

    user = user or frappe.session.user
    if access.is_instance_admin(user):
        return True

    project = doc.name if doc.doctype == "BP Project" else doc.get("project")
    if not project:
        return True  # not project-scoped — leave to default perms

    # A brand-new doc being created: no row exists yet. Creating a project is
    # open to any System User (they become its Admin); creating a project-scoped
    # child requires Member+ on the parent project.
    if doc.doctype == "BP Project" and doc.get("__islocal"):
        return frappe.db.get_value("User", user, "user_type") == "System User"

    min_role = access.min_role_for_ptype(permission_type)
    return access.has_at_least(project, min_role, user)


def bp_task_has_permission(doc, user=None, permission_type=None):
    """BP Task's own has_permission — same as bp_doc_has_permission
    above, plus the task-scoped assignee grant access.require_task enforces
    at the API layer (board.get_task/update_task): an explicit assignee on
    THIS task additionally clears any Member-or-below permission_type (read/
    write/create), even with zero project standing. Manager+ ptypes
    (delete/submit/cancel/share) still require real project access — being
    assigned one task never grants those on it."""
    from batch_projects import access

    user = user or frappe.session.user
    if access.is_instance_admin(user):
        return True

    project = doc.get("project")
    if not project:
        return True  # not project-scoped — leave to default perms

    min_role = access.min_role_for_ptype(permission_type)
    if access.has_at_least(project, min_role, user):
        return True

    if access.rank(min_role) <= access.rank("Member") and not doc.get("__islocal"):
        return access.is_task_assignee(doc.name, user)

    return False


def bp_team_query_conditions(user=None):
    """BP Team list visibility: instance admins bypass; org System Users
    (non-guest) may read any team; guests may read only teams where they are
    a BP Team Member."""
    user = user or frappe.session.user
    if _is_admin(user):
        return ""
    from batch_projects import access
    if access.is_guest(user):
        return f"""
            `tabBP Team`.`name` IN (
                SELECT parent FROM `tabBP Team Member` WHERE user = {frappe.db.escape(user)}
            )
        """
    return ""


def bp_team_has_permission(doc, user=None, permission_type=None):
    """BP Team per-document gate: instance admins bypass; org System Users may
    read any team; guests may read only teams where they are a BP Team Member;
    write/delete require team membership with sufficient role."""
    from batch_projects import access
    user = user or frappe.session.user
    if access.is_instance_admin(user):
        return True
    if doc.get("__islocal"):
        return frappe.db.get_value("User", user, "user_type") == "System User"
    if permission_type == "read":
        if access.is_guest(user):
            member_row = frappe.db.get_value(
                "BP Team Member", {"parent": doc.name, "user": user}, "role"
            )
            return bool(member_row)
        return True
    member_role = frappe.db.get_value(
        "BP Team Member", {"parent": doc.name, "user": user}, "role"
    )
    if not member_role:
        return False
    hierarchy = {"Admin": 3, "Manager": 2, "Member": 1}
    if permission_type in ("write", "create"):
        required = "Member"
    elif permission_type in ("delete", "submit", "cancel"):
        required = "Admin"
    else:
        required = "Viewer"
    return hierarchy.get(member_role, 0) >= hierarchy.get(required, 0)


# ─── Owned/workspace rows: BP Report / BP Dashboard ────────────────────────
#
# The one documented ownership policy for both doctypes (mirrored at the API
# layer in api/board.py's report helpers and api/dashboards.py):
#   - instance/workspace admins: everything;
#   - private rows: owner only, every permission type;
#   - workspace rows: read = any System User (a project-scoped row still
#     requires project visibility); write/delete = owner, the project's
#     Admin when project-scoped, or an instance/workspace admin;
#   - create: authenticated System User; Member+ on the project when the
#     new row is project-scoped.
def _owned_or_workspace_has_permission(doc, user=None, permission_type=None):
    from batch_projects import access

    user = user or frappe.session.user
    if access.is_instance_admin(user) or access.is_workspace_admin(user):
        return True

    ptype = permission_type or "read"

    if doc.get("__islocal") or ptype == "create":
        if frappe.db.get_value("User", user, "user_type") != "System User":
            return False
        project = doc.get("project")
        if project:
            return access.has_at_least(project, "Member", user)
        return True

    if doc.get("visibility") == "private":
        return doc.get("owner") == user

    # workspace rows
    if ptype == "read":
        project = doc.get("project")
        if not project:
            return True  # projectless workspace rows are visible to all System Users
        return access.has_at_least(project, "Viewer", user)

    # write/delete/anything beyond read
    project = doc.get("project")
    if doc.get("owner") == user:
        return True
    if project:
        return access.has_at_least(project, "Admin", user)
    return False


def bp_report_has_permission(doc, user=None, permission_type=None):
    """Per-document gate for BP Report — private rows owner-only; workspace
    rows follow the policy documented above. Replaces the generic project-only
    hook, which could not express ownership/visibility at all."""
    return _owned_or_workspace_has_permission(doc, user, permission_type)


def bp_dashboard_has_permission(doc, user=None, permission_type=None):
    """Per-document gate for BP Dashboard — same documented policy as BP
    Report. BP Dashboard previously had NO has_permission hook, so the generic
    REST API bypassed api/dashboards.py's checks entirely."""
    return _owned_or_workspace_has_permission(doc, user, permission_type)


def bp_user_owned_has_permission(doc, user=None, permission_type=None):
    """Per-document gate for personal rows keyed on a `user` field
    (BP View Preference / BP Notification Mute). These are never shared:
    owner or an instance/workspace admin only, every permission type —
    including create-as-someone-else through the generic REST/ORM path."""
    from batch_projects import access

    user = user or frappe.session.user
    if access.is_instance_admin(user) or access.is_workspace_admin(user):
        return True
    return doc.get("user") == user
