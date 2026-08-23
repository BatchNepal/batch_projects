"""
batch_projects/api/sharing.py
─────────────────────────────
View-only public **share links** — distinct from invitations.

  • Invitation = "come work on this project" → an account + membership + role.
  • Share link = "come look at this"        → a bearer token in the URL is the
    credential. No account, no login, strictly read-only, revocable, optionally
    expiring.

Three scopes: `board` (the kanban, read-only), `project` (project + board), and
`task` (a single task, read-only).

Authorization:
  • create / list / revoke  → project Manager+ (and the creating tier must be
    Team or above — see entitlements; the gate is on CREATION only, so a viewer
    is never blocked and an existing link keeps working after a downgrade).
  • get_shared              → anyone with the token (allow_guest). The token is
    the grant; the logged-in session is irrelevant and never trusted here.
"""

import frappe
from frappe import _
from frappe.utils import now_datetime, add_days, get_url, get_datetime

from batch_projects import access
from batch_projects.api.board import _normalize_workflow_states, _parse_json

VALID_SCOPES = {"board", "project", "task"}


# ─── helpers ──────────────────────────────────────────────────────────────────


def _resolve_project(project: str) -> str:
    """Accept either the project name or its short key."""
    if frappe.db.exists("BP Project", project):
        return project
    alt = frappe.db.get_value("BP Project", {"key": project}, "name")
    if not alt:
        frappe.throw(_("Project not found."), frappe.DoesNotExistError)
    return alt


def _share_url(token: str) -> str:
    return get_url(f"/share/{token}")


def _public_dict(link, with_url=True) -> dict:
    d = {
        "name": link.name,
        "scope": link.scope,
        "task": link.task,
        "label": link.label or "",
        "access_level": link.access_level,
        "expires_on": str(link.expires_on) if link.expires_on else None,
        "revoked": bool(link.revoked),
        "access_count": link.access_count or 0,
        "last_accessed": str(link.last_accessed) if link.last_accessed else None,
        "creation": str(link.creation),
    }
    if with_url:
        d["url"] = _share_url(link.token)
    return d


# ─── management endpoints (authenticated, Manager+) ─────────────────────────────


@frappe.whitelist()
def create_share_link(
    project,
    scope="board",
    task=None,
    expires_in_days=None,
    label=None,
    access_level="view",
):
    """Create a public link. Manager+ and Team tier or above.
    access_level: "view" (default), "comment" (task only), or "edit" (task only)."""
    from batch_projects.gateway_guard import verify_gateway_request

    verify_gateway_request()
    from batch_projects.entitlements import require_feature

    require_feature("share_links")

    project = _resolve_project(project)
    access.require(project, "Manager")

    scope = scope if scope in VALID_SCOPES else "board"
    if scope == "task":
        if not task or not frappe.db.exists("BP Task", task):
            frappe.throw(_("A valid task is required for a task share link."))
        if frappe.db.get_value("BP Task", task, "project") != project:
            frappe.throw(_("That task does not belong to this project."))

    # Validate access_level
    valid_levels = {"view", "comment", "edit"}
    if access_level not in valid_levels:
        access_level = "view"
    # Only task-scoped links can have comment or edit access
    if scope != "task" and access_level != "view":
        access_level = "view"

    expires_on = None
    if expires_in_days:
        try:
            days = int(expires_in_days)
            if days > 0:
                expires_on = add_days(now_datetime(), days)
        except (TypeError, ValueError):
            pass

    link = frappe.new_doc("BP Share Link")
    link.update(
        {
            "project": project,
            "scope": scope,
            "task": task if scope == "task" else None,
            "label": (label or "").strip() or None,
            "access_level": access_level,
            "expires_on": expires_on,
            "revoked": 0,
        }
    )
    link.insert(ignore_permissions=True)
    frappe.db.commit()
    return _public_dict(link)


@frappe.whitelist()
def list_share_links(project, scope=None):
    """Live (non-revoked) share links for a project. Manager+."""
    from batch_projects.gateway_guard import verify_gateway_request

    verify_gateway_request()
    project = _resolve_project(project)
    access.require(project, "Manager")

    filters = {"project": project, "revoked": 0}
    if scope in VALID_SCOPES:
        filters["scope"] = scope

    rows = frappe.get_all(
        "BP Share Link",
        filters=filters,
        fields=[
            "name",
            "scope",
            "task",
            "label",
            "access_level",
            "token",
            "expires_on",
            "revoked",
            "access_count",
            "last_accessed",
            "creation",
        ],
        order_by="creation desc",
    )
    out = []
    for r in rows:
        r["url"] = _share_url(r.pop("token"))
        r["expired"] = (
            bool(r["expires_on"]) and get_datetime(r["expires_on"]) < now_datetime()
        )
        r["expires_on"] = str(r["expires_on"]) if r["expires_on"] else None
        r["last_accessed"] = str(r["last_accessed"]) if r["last_accessed"] else None
        r["creation"] = str(r["creation"])
        out.append(r)
    return out


@frappe.whitelist()
def revoke_share_link(name):
    """Revoke a link permanently. Manager+."""
    from batch_projects.gateway_guard import verify_gateway_request

    verify_gateway_request()
    link = frappe.get_doc("BP Share Link", name)
    access.require(link.project, "Manager")
    link.revoked = 1
    link.save(ignore_permissions=True)
    frappe.db.commit()
    return {"ok": True}


# ─── public read endpoint (allow_guest — token is the credential) ───────────────


def _load_live_link(token):
    name = frappe.db.get_value("BP Share Link", {"token": token}, "name")
    if not name:
        frappe.throw(_("This link is invalid."), frappe.DoesNotExistError)
    link = frappe.get_doc("BP Share Link", name)
    if link.revoked:
        frappe.throw(_("This link has been revoked."), frappe.PermissionError)
    if link.is_expired:
        frappe.throw(_("This link has expired."), frappe.PermissionError)
    return link


def _project_header(proj) -> dict:
    return {
        "name": proj.name,
        "project_name": proj.project_name,
        "key": proj.key,
        "project_color": proj.project_color,
        "project_icon": proj.project_icon,
        "theme": proj.theme,
        "description": proj.description or "",
    }


def _assignees_for(task_names):
    """user → full_name map of assignees, by task. Read-only, no emails leaked
    beyond display name."""
    out = {}
    if not task_names:
        return out
    rows = frappe.get_all(
        "BP Task Assignee",
        filters={"parenttype": "BP Task", "parent": ["in", task_names]},
        fields=["parent", "user"],
        order_by="idx asc",
    )
    users = list({r["user"] for r in rows})
    names = {}
    if users:
        for u in frappe.get_all(
            "User", filters={"name": ["in", users]}, fields=["name", "full_name"]
        ):
            names[u["name"]] = u["full_name"] or u["name"]
    for r in rows:
        out.setdefault(r["parent"], []).append(
            {"user": r["user"], "full_name": names.get(r["user"], r["user"])}
        )
    return out


def _read_board(project):
    """Self-contained read-only board payload. Bypasses session permissions on
    purpose — the share token already authorized this read."""
    proj = frappe.get_doc("BP Project", project)
    states = _normalize_workflow_states(proj.get_workflow_states())

    tasks = frappe.get_all(
        "BP Task",
        filters={"project": project, "parent_task": ["is", "not set"], "is_deleted": 0},
        fields=[
            "name",
            "task_key",
            "title",
            "status",
            "priority",
            "task_type",
            "due_date",
            "board_order",
            "labels",
        ],
        order_by="board_order asc, creation asc",
    )
    amap = _assignees_for([t["name"] for t in tasks])
    for t in tasks:
        t["assignees"] = amap.get(t["name"], [])
        t["labels"] = _parse_json(t.get("labels"), [])

    board = {}
    for s in states:
        board[s["name"]] = []
    for t in tasks:
        board.setdefault(t["status"], []).append(t)

    return {
        "project": _project_header(proj),
        "workflow_states": states,
        "columns": [s["name"] for s in states],
        "labels": _parse_json(proj.labels, []),
        "board": board,
    }


def _read_task(task_name):
    t = frappe.get_doc("BP Task", task_name)
    proj = frappe.get_doc("BP Project", t.project)
    states = _normalize_workflow_states(proj.get_workflow_states())
    color_by_status = {s.get("name"): s.get("color") for s in states}

    subtasks = frappe.get_all(
        "BP Task",
        filters={"parent_task": task_name, "is_deleted": 0},
        fields=["name", "task_key", "title", "status", "priority"],
        order_by="board_order asc, creation asc",
    )
    amap = _assignees_for([task_name] + [s["name"] for s in subtasks])
    for s in subtasks:
        s["assignees"] = amap.get(s["name"], [])
        s["status_color"] = color_by_status.get(s["status"]) or "#9FA6AD"

    return {
        "project": _project_header(proj),
        "task": {
            "name": t.name,
            "task_key": t.task_key,
            "title": t.title,
            "description": t.description or "",
            "status": t.status,
            "status_color": color_by_status.get(t.status) or "#9FA6AD",
            "priority": t.priority,
            "task_type": t.task_type,
            "due_date": str(t.due_date) if t.due_date else None,
            "labels": _parse_json(t.labels, []),
            "assignees": amap.get(task_name, []),
            "subtasks": subtasks,
            "comments": _comments_for(task_name),
        },
        "workflow_states": states,
    }


def _comments_for(task_name):
    """Comment-type BP Activity rows for a shared task, oldest first — read
    side for both the member-facing view and the guest composer below."""
    rows = frappe.get_all(
        "BP Activity",
        filters={"task": task_name, "action_type": "Comment"},
        fields=["name", "user", "guest_name", "comment_text", "creation"],
        order_by="creation asc",
    )
    names = {}
    users = list({r["user"] for r in rows if r["user"] and r["user"] != "Guest"})
    if users:
        for u in frappe.get_all(
            "User", filters={"name": ["in", users]}, fields=["name", "full_name"]
        ):
            names[u["name"]] = u["full_name"] or u["name"]
    out = []
    for r in rows:
        out.append(
            {
                "name": r["name"],
                "user": r["user"],
                "full_name": names.get(r["user"]) if r["user"] != "Guest" else None,
                "guest_name": r["guest_name"] or None,
                "comment_text": r["comment_text"] or "",
                "creation": str(r["creation"]),
            }
        )
    return out


@frappe.whitelist(allow_guest=True)
def get_shared(token):
    """Resolve a share token to its read-only payload. Public — the token is the
    credential. Returns only display data; no edit endpoints are reachable."""
    if not token:
        frappe.throw(_("This link is invalid."), frappe.DoesNotExistError)
    link = _load_live_link(token)

    # Best-effort access accounting (don't fail the read if this errors).
    try:
        frappe.db.set_value(
            "BP Share Link",
            link.name,
            {
                "access_count": (link.access_count or 0) + 1,
                "last_accessed": now_datetime(),
            },
            update_modified=False,
        )
        frappe.db.commit()
    except Exception:
        pass

    base = {
        "scope": link.scope,
        "access_level": link.access_level,
        "label": link.label or "",
    }

    if link.scope == "task":
        if not link.task or not frappe.db.exists("BP Task", link.task):
            frappe.throw(
                _("The shared task no longer exists."), frappe.DoesNotExistError
            )
        base.update(_read_task(link.task))
    else:
        base.update(_read_board(link.project))
    return base


# ─── guest comments (allow_guest — one narrow, opt-in exception to read-only) ───
# access_level == "comment" must be set explicitly per link (§module docstring);
# an existing "view" link never gains this for free. Task-scoped only, plain
# text, no mentions — see bp_audit_2026_07_22 phase 26 plan for the full
# security rationale.

_GUEST_COMMENT_LIMIT = 5
_GUEST_COMMENT_WINDOW_SEC = 300
_GUEST_COMMENT_MAX_LEN = 2000


def _throttle_guest_comment(token):
    key = f"bp_guest_comment_throttle:{token}"
    # expires=True: this key always carries a TTL (set below), so reads must
    # skip frappe.local's request-local memoization and hit Redis directly —
    # otherwise the count freezes at whatever it read the first time.
    count = int(frappe.cache().get_value(key, expires=True) or 0)
    if count >= _GUEST_COMMENT_LIMIT:
        frappe.throw(
            _(
                "Too many comments from this link. Please wait a few minutes and try again."
            ),
            frappe.PermissionError,
        )
    frappe.cache().set_value(key, count + 1, expires_in_sec=_GUEST_COMMENT_WINDOW_SEC)


@frappe.whitelist(allow_guest=True)
def add_guest_comment(token, comment_text, guest_name=None):
    """Post a plain-text comment as an anonymous guest via a share link.
    Requires the link to be task-scoped with access_level=="comment" — a
    board/project link or a plain "view" link can never reach this. No
    mentions are parsed (an anonymous link must not be a way to page an
    arbitrary internal user); HTML is stripped server-side before storage."""
    if not token:
        frappe.throw(_("This link is invalid."), frappe.DoesNotExistError)
    link = _load_live_link(token)

    if link.scope != "task":
        frappe.throw(
            _("Comments are only supported on a shared task."), frappe.PermissionError
        )
    if link.access_level != "comment":
        frappe.throw(_("This link does not allow commenting."), frappe.PermissionError)
    if not link.task or not frappe.db.exists("BP Task", link.task):
        frappe.throw(_("The shared task no longer exists."), frappe.DoesNotExistError)

    # Reject trashed tasks
    task_data = frappe.db.get_value("BP Task", link.task, ["is_deleted"], as_dict=True)
    if not task_data or task_data.is_deleted:
        frappe.throw(_("The shared task has been trashed."), frappe.PermissionError)

    comment_text = frappe.utils.strip_html((comment_text or "").strip())[
        :_GUEST_COMMENT_MAX_LEN
    ]
    if not comment_text:
        frappe.throw(_("Comment can't be empty."))
    guest_name = (guest_name or "").strip()[:140] or "Guest"

    _throttle_guest_comment(token)

    doc = frappe.get_doc("BP Task", link.task)
    activity = frappe.get_doc(
        {
            "doctype": "BP Activity",
            "task": link.task,
            "action_type": "Comment",
            "comment_text": comment_text,
            "user": "Guest",
            "guest_name": guest_name,
        }
    )
    activity.insert(ignore_permissions=True)

    from batch_projects.events import emit, COMMENT_ADDED

    emit(
        COMMENT_ADDED,
        {
            "project": doc.project,
            "task": link.task,
            "task_key": doc.task_key,
            "comment_text": comment_text,
            "activity": activity.name,
            "mentions": [],
            # Explicit, not left to _enrich's frappe.session.user fallback: a
            # logged-in teammate could have this same public link open in another
            # tab, and every guest comment must attribute as "Guest" regardless
            # of whose browser session happens to be attached to the request.
            "user": "Guest",
        },
    )

    return {
        "ok": True,
        "activity": activity.name,
        "guest_name": guest_name,
        "creation": str(activity.creation),
    }


# ─── guest task edit (allow_guest — second narrow exception to read-only) ─────
# access_level == "edit" must be set explicitly per link. Task-scoped only.
# Only a safe allowlist of fields can be changed: status, priority, description.
# The same throttle and HTML-stripping as guest comments apply.

_GUEST_EDIT_ALLOWLIST = {"status", "priority", "description"}


@frappe.whitelist(allow_guest=True)
def update_shared_task(token, task, fields=None):
    """Update a task via a share link with access_level=="edit".
    Only status, priority, and description may be changed."""
    import json

    if not token:
        frappe.throw(_("This link is invalid."), frappe.DoesNotExistError)
    link = _load_live_link(token)

    if link.scope != "task":
        frappe.throw(
            _("Task edits are only supported on a shared task."), frappe.PermissionError
        )
    if link.access_level != "edit":
        frappe.throw(_("This link does not allow editing."), frappe.PermissionError)
    if not link.task or not frappe.db.exists("BP Task", link.task):
        frappe.throw(_("The shared task no longer exists."), frappe.DoesNotExistError)

    # Reject trashed tasks
    task_data = frappe.db.get_value("BP Task", link.task, ["is_deleted"], as_dict=True)
    if not task_data or task_data.is_deleted:
        frappe.throw(_("The shared task has been trashed."), frappe.PermissionError)

    if link.task != task:
        frappe.throw(_("Token is not valid for this task."), frappe.PermissionError)

    if isinstance(fields, str):
        fields = json.loads(fields)
    if not isinstance(fields, dict):
        frappe.throw(_("fields must be a dict"))

    # Filter to allowlist only — silently drop disallowed keys
    safe = {k: v for k, v in fields.items() if k in _GUEST_EDIT_ALLOWLIST}
    if not safe:
        frappe.throw(_("No editable fields provided."))

    # Strip HTML from description (same sanitization as guest comments)
    if "description" in safe:
        safe["description"] = frappe.utils.strip_html(
            (safe["description"] or "").strip()
        )[:2000]

    # Throttle (same as guest comments)
    _throttle_guest_comment(token)

    doc = frappe.get_doc("BP Task", link.task)

    # Same dependency-blocker guard update_task applies (api/board.py's
    # _completing_into_blocked). Without it a share-link guest could close a
    # task whose blockers are still open — something no internal Member can
    # do. A guest has no way to override, so `force` is never offered here.
    if "status" in safe:
        from batch_projects.api.board import _completing_into_blocked

        blockers = _completing_into_blocked(doc, safe["status"], False)
        if blockers:
            frappe.throw(
                _("This task is still blocked by {0} unfinished task(s).").format(
                    len(blockers)
                ),
                frappe.ValidationError,
            )

    doc.update(safe)
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": True, "updated": list(safe.keys())}
