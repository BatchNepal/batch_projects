"""
batch_projects/access.py
────────────────────────
THE single source of truth for "what can this user do on this project".

Before this module there were three uncoordinated authorization systems:

  1. board.py `_check_permission`  — project roles (Admin/Manager/Member/Viewer)
  2. doctype JSON `permissions`   — Frappe roles (Projects User/Manager …)
  3. permissions.py visibility    — workspace / team / private

…and which one fired depended on whether an endpoint happened to call
`doc.save()` (→ doctype gate) or `frappe.db.set_value()` (→ no gate). Same
user, same board, different verdict. That is the bug this module removes.

Everything now resolves through `get_effective_role()`:

  • Administrator / System Manager            → Admin   (instance superuser)
  • explicit BP Project Member.role           → that role
  • non-member System User, project is …
        workspace                             → Viewer  (can see, can't edit)
        team   AND user in the project's team → Viewer
        private                               → None    (no access)
  • non System User (Website/Guest)           → None

Capabilities are derived from the role rank, never from the call path:

        VIEW  ≥ Viewer      COMMENT ≥ Member
        EDIT  ≥ Member      MANAGE  ≥ Manager
        ADMIN ≥ Admin

Both the API layer (board.py `_check_permission`) and the data layer
(permissions.py `has_permission` / query conditions) call into here, so the
generic REST API, reports, list views and the SPA all enforce the same rule.
"""

import frappe
import json

# Canonical project roles (must match BP Project Member.role select options).
ROLE_RANK = {
    "Admin":   4,
    "Manager": 3,
    "Member":  2,
    "Viewer":  1,
}

# Accept the legacy "BP "-prefixed spellings that older callers pass in.
_ROLE_ALIASES = {
    "BP Admin": "Admin",
    "BP Manager": "Manager",
    "BP Member": "Member",
    "BP Viewer": "Viewer",
}


def normalize_role(role: str | None) -> str | None:
    if not role:
        return None
    return _ROLE_ALIASES.get(role, role)


def rank(role: str | None) -> int:
    return ROLE_RANK.get(normalize_role(role), 0)


def is_instance_admin(user: str | None = None) -> bool:
    user = user or frappe.session.user
    return user == "Administrator" or "System Manager" in frappe.get_roles(user)


def is_workspace_admin(user: str | None = None) -> bool:
    """Org-wide admin, as opposed to a per-project Admin. Gates workspace-level
    surfaces (BP Workspace Settings and friends) that apply to every project at
    once — a project Admin has no say over those. Holding the Frappe Role
    'BP Admin' (assigned by an instance admin via the User doctype) or being an
    instance admin outright both qualify."""
    user = user or frappe.session.user
    return is_instance_admin(user) or "BP Admin" in frappe.get_roles(user)


# Role assigned to externally-invited accounts. A guest is NOT an org member:
# they only ever see projects they were explicitly invited to — the
# workspace/team visibility fallback does not apply to them. This is what makes
# invitation scoping real (invite to one project ≠ access to every workspace one).
GUEST_ROLE = "BP Guest"


def is_guest(user: str | None = None) -> bool:
    user = user or frappe.session.user
    return GUEST_ROLE in frappe.get_roles(user)


def get_effective_role(project: str, user: str | None = None) -> str | None:
    """The role `user` effectively holds on `project`, applying explicit
    membership first, then falling back to what the project's visibility
    grants. Returns None when the user has no access at all.

    Memoized per-request on frappe.local — `get_board`, list filtering and
    the has_permission hook can each call this many times per request.
    """
    user = user or frappe.session.user
    if is_instance_admin(user):
        return "Admin"

    cache = getattr(frappe.local, "_bp_effective_role", None)
    if cache is None:
        cache = {}
        frappe.local._bp_effective_role = cache
    ck = (project, user)
    if ck in cache:
        return cache[ck]

    role = _resolve_effective_role(project, user)
    cache[ck] = role
    return role


def _resolve_effective_role(project: str, user: str) -> str | None:
    # Only real System Users participate; website/guest never do.
    if frappe.db.get_value("User", user, "user_type") != "System User":
        return None

    # 1) explicit membership wins
    member_role = frappe.db.get_value(
        "BP Project Member", {"parent": project, "user": user}, "role"
    )
    if member_role:
        return normalize_role(member_role)

    # Guests get NO visibility fallback — only the projects they're a member of.
    if is_guest(user):
        return None

    # 2) fall back to visibility-granted access (read-only)
    visibility, team = frappe.db.get_value(
        "BP Project", project, ["visibility", "team"]
    ) or (None, None)

    if visibility in (None, "", "workspace"):
        return "Viewer"  # workspace: anyone in the org may look, not edit

    if visibility == "team" and team:
        in_team = frappe.db.exists(
            "BP Team Member", {"parent": team, "user": user}
        )
        if in_team:
            return "Viewer"

    # private, or team project the user isn't on
    return None


def has_at_least(project: str, min_role: str, user: str | None = None) -> bool:
    return rank(get_effective_role(project, user)) >= rank(min_role)


def require(project: str, min_role: str, user: str | None = None) -> None:
    """Throw PermissionError unless `user` holds at least `min_role` on
    `project`. The single enforcement primitive for whitelisted endpoints."""
    user = user or frappe.session.user
    if is_instance_admin(user):
        return

    eff = get_effective_role(project, user)
    if eff is None:
        frappe.throw(
            "You don't have access to this project.", frappe.PermissionError
        )
    if rank(eff) < rank(min_role):
        frappe.throw(
            f"You need at least {normalize_role(min_role)} access for this action "
            f"(you have {eff}).",
            frappe.PermissionError,
        )


# ─── Task-scoped assignee grant ─────────────────────────────────────────────
#
# Assigning a task has never required project membership (board.py's
# update_task just appends a row to BP Task.assignees, no check) — but
# get_effective_role only ever resolves membership/visibility on the
# PROJECT, so an assignee with no other standing on the project couldn't
# open the very task they were assigned. Mirrors how Jira/Asana/Monday treat
# "assigned to me": implicit access to that one row, never the parent
# project or its other tasks. Deliberately narrow — only wired into the
# single-task endpoints that need it (board.get_task/update_task, timers.
# start_timer), never into anything that lists or scopes by project.

def is_task_assignee(task: str, user: str | None = None) -> bool:
    """True if `user` is an explicit assignee on this specific BP Task."""
    user = user or frappe.session.user
    return bool(frappe.db.exists("BP Task Assignee", {"parent": task, "user": user}))


def require_task(task: str, project: str, min_role: str, user: str | None = None) -> None:
    """Task-scoped counterpart to require(): the normal project-role floor
    still applies and wins first. Failing that, an assignee on THIS task
    additionally clears any Member-or-below bar (view, edit, log time) on
    it alone — never Manager+ actions (submit/cancel/delete/share), and
    never anything project- or list-scoped. Being assigned one task never
    grants the project, sibling tasks, or Manager-level actions on this one."""
    user = user or frappe.session.user
    if is_instance_admin(user):
        return

    eff = get_effective_role(project, user)
    if eff is not None and rank(eff) >= rank(min_role):
        return

    if rank(min_role) <= rank("Member") and is_task_assignee(task, user):
        return

    frappe.throw("You don't have access to this task.", frappe.PermissionError)


# ─── capability → required role, for ptype-driven (has_permission) gating ─────

# Frappe permission_type → minimum project role required.
_PTYPE_MIN_ROLE = {
    "read": "Viewer",
    "select": "Viewer",
    "print": "Viewer",
    "email": "Viewer",
    "export": "Member",
    "report": "Viewer",
    "write": "Member",
    "create": "Member",
    "submit": "Manager",
    "cancel": "Manager",
    "delete": "Manager",
    "share": "Manager",
}


def min_role_for_ptype(ptype: str | None) -> str:
    return _PTYPE_MIN_ROLE.get(ptype or "read", "Member")


# ─── CAPABILITIES REGISTRY ──────────────────────────────────────────────────
#
# Everything ABOVE this line is untouched — this section is purely additive,
# reusing ROLE_RANK/get_effective_role/normalize_role as-is.
#
# Representation choice: capability -> {min_role, ...} (a monotonic threshold),
# not a bare per-role boolean matrix, because it maps directly onto the
# existing rank-based model (VIEW>=Viewer, COMMENT/EDIT>=Member, MANAGE>=
# Manager, ADMIN>=Admin per the module docstring) — one field expresses the
# same thing has_at_least()/require() already compute from ROLE_RANK, instead
# of spelling out 4 redundant booleans per capability. The RESOLVED matrix
# (what get_capability_matrix() returns) IS a per-role boolean grid, because
# that's what a role override actually needs to express: "Member is normally
# >= Viewer's view_money default, but this workspace switched it off for
# Member specifically" is not a single threshold anymore once overridden.
#
# `overridable=False` entries (view/comment/edit/manage/admin) are the
# EXISTING role-rank ladder, included so the matrix UI can show the full
# picture (Projects/Tasks/Boards/Members context) — but they are NOT
# independently enforced anywhere; they simply mirror ROLE_RANK. Making them
# independently toggleable would mean every access.require(...) call site in
# the app switching from its own hardcoded min-role string to a registry
# lookup — a much larger refactor that would risk altering existing
# semantics. Only view_money/view_files are real, enforced, overridable
# capabilities today.
CAPABILITIES = {
    "view":    {"min_role": "Viewer",  "group": "Projects", "label": "View projects, tasks and boards", "overridable": False},
    "comment": {"min_role": "Member",  "group": "Tasks",    "label": "Comment on tasks",                 "overridable": False},
    "edit":    {"min_role": "Member",  "group": "Boards",   "label": "Create and edit tasks",            "overridable": False},
    "manage":  {"min_role": "Manager", "group": "Members",  "label": "Manage members and project settings", "overridable": False},
    "admin":   {"min_role": "Admin",   "group": "Projects", "label": "Full project administration",      "overridable": False},
    # The only two capabilities a workspace admin can actually turn off per
    # role. Both default to Viewer (today's behavior:
    # every role sees money/files) so shipping this is a no-op until an
    # admin visits the matrix and switches one off.
    "view_money": {"min_role": "Viewer", "group": "Money", "label": "View Money tab, margin report and money fields", "overridable": True},
    "view_files": {"min_role": "Viewer", "group": "Files", "label": "View Files tab and task attachments",           "overridable": True},
}

# UI display order for the matrix's grouped rows.
CAPABILITY_GROUPS = ["Projects", "Tasks", "Boards", "Members", "Money", "Files"]

# Roles a workspace admin may override. Admin is deliberately absent —
# immutable full-access, enforced at both save time (validate_and_merge_
# role_overrides throws) and read time (get_capability_matrix forces it back
# to all-True regardless of what's stored, in case of a direct DB edit).
_OVERRIDABLE_ROLES = ("Manager", "Member", "Viewer")

_CAPABILITY_MATRIX_CACHE_KEY = "bp_capability_matrix"


def _default_matrix() -> dict:
    return {
        role: {cap: rank(role) >= rank(meta["min_role"]) for cap, meta in CAPABILITIES.items()}
        for role in ROLE_RANK
    }


def get_role_overrides_raw() -> dict:
    """The raw, as-stored role_overrides_json — {role: {cap: 0/1}} — used by
    both get_capability_matrix() (to merge onto defaults) and the settings
    API (as the "current" value a partial update must preserve unmentioned
    keys of). Never trust this as authorization by itself; only the merged,
    Admin-forced matrix from get_capability_matrix() is."""
    try:
        raw = frappe.db.get_single_value("BP Workspace Settings", "role_overrides_json")
        parsed = json.loads(raw) if raw else {}
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        # Doctype not migrated yet, or a malformed record — fail open to
        # "no overrides" (today's behavior) rather than breaking bootstrap.
        return {}


def validate_and_merge_role_overrides(parsed_overrides: dict, current_raw: dict) -> dict:
    """Validate an incoming (possibly partial) role_overrides_json payload
    and merge it onto `current_raw`, preserving every role/capability the
    payload doesn't mention — the same partial-update contract the workspace
    feature-toggle's features_json merge uses, so a save from one tab of the
    matrix can never silently reset another. Throws PermissionError/ValidationError on:
      - a role that isn't a real, overridable role (Admin included — Admin's
        immutability is enforced HERE, not just hidden in the UI)
      - a capability key that doesn't exist or isn't overridable
    """
    result = {role: dict(caps) for role, caps in (current_raw or {}).items()}

    for role, caps in (parsed_overrides or {}).items():
        if role == "Admin":
            frappe.throw(
                "Admin has full access and cannot be overridden.", frappe.PermissionError
            )
        if role not in _OVERRIDABLE_ROLES:
            frappe.throw(f"Unknown role '{role}'.")
        if not isinstance(caps, dict):
            frappe.throw(f"Invalid overrides for role '{role}'.")

        bucket = result.setdefault(role, {})
        for cap, val in caps.items():
            meta = CAPABILITIES.get(cap)
            if not meta or not meta["overridable"]:
                frappe.throw(f"'{cap}' cannot be overridden.")
            bucket[cap] = 1 if val else 0

    return result


def get_capability_matrix() -> dict:
    """The resolved {role: {capability: bool}} grid — defaults from
    CAPABILITIES' min_role ladder, with BP Workspace Settings.
    role_overrides_json punched on top. Cached (frappe.cache) since this is
    read on nearly every gated endpoint; invalidated by
    invalidate_capability_matrix_cache() on settings save."""
    try:
        cached = frappe.cache().get_value(_CAPABILITY_MATRIX_CACHE_KEY)
        if cached is not None:
            return cached
    except Exception:
        pass

    matrix = _default_matrix()
    for role, caps in get_role_overrides_raw().items():
        if role == "Admin" or role not in matrix:
            continue  # defensive — save-time validation should prevent this
        for cap, val in caps.items():
            if cap in matrix[role] and CAPABILITIES.get(cap, {}).get("overridable"):
                matrix[role][cap] = bool(val)

    # Admin is IMMUTABLE full-access — forced here too (not just at save),
    # in case role_overrides_json was ever edited directly in the DB.
    matrix["Admin"] = {cap: True for cap in CAPABILITIES}

    try:
        frappe.cache().set_value(_CAPABILITY_MATRIX_CACHE_KEY, matrix)
    except Exception:
        pass
    return matrix


def invalidate_capability_matrix_cache() -> None:
    try:
        frappe.cache().delete_value(_CAPABILITY_MATRIX_CACHE_KEY)
    except Exception:
        pass


def has_capability(project: str, cap: str, user: str | None = None) -> bool:
    """Does `user` hold capability `cap` on `project` — resolving their
    effective project role (incl. the implicit workspace-Viewer fallback)
    and checking it against the merged capability matrix. Instance admins
    and per-project Admin members always pass (matrix["Admin"] is forced
    all-True above)."""
    user = user or frappe.session.user
    role = get_effective_role(project, user)
    if role is None:
        return False
    return bool(get_capability_matrix().get(role, {}).get(cap, False))


def require_capability(project: str, cap: str, user: str | None = None) -> None:
    """Throw PermissionError unless `user` holds `cap` on `project`. Meant to
    run ALONGSIDE the existing require()/tier-gate calls on an endpoint, not
    replace them — this checks the capability matrix only, not the base role
    floor (that's still require()'s job)."""
    if not has_capability(project, cap, user):
        frappe.throw(
            f"You don't have permission to view {cap.replace('view_', '')} on this project.",
            frappe.PermissionError,
        )


def has_capability_anywhere(cap: str, user: str | None = None) -> bool:
    """For cross-project surfaces with no single project to resolve a role
    against (the margin report spans every project at once). True if the
    user is an instance admin, or holds a role — explicit membership, or the
    implicit workspace-Viewer fallback every System User gets — on at least
    one project whose matrix entry for `cap` is on. Deliberately permissive
    (OR across roles, not AND): this only ADDS a gate in front of the report;
    it doesn't re-scope which projects the report already includes (that's
    unrelated, existing behavior)."""
    user = user or frappe.session.user
    if is_instance_admin(user):
        return True

    matrix = get_capability_matrix()
    roles = {normalize_role(r) for r in
             frappe.get_all("BP Project Member", filters={"user": user}, pluck="role")}
    # Any workspace-visibility project grants Viewer to every System User by
    # definition (_resolve_effective_role's own fallback) — so a real System
    # User always has at least Viewer's row available to check, even with
    # zero explicit memberships.
    if frappe.db.get_value("User", user, "user_type") == "System User":
        roles.add("Viewer")

    return any(matrix.get(r, {}).get(cap, False) for r in roles if r)
