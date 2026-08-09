"""
batch_projects/api/dashboards.py
───────────────────────────────────
BP Dashboard — live glance dashboards. Separate from BP Report (which stays
scheduled/exportable, see api/board.py's save_report/get_saved_reports). Paid
feature end to end: BPDashboard.validate() gates writes, but list/get/delete
don't go through validate(), so every whitelisted method here re-checks
require_feature("dashboards") itself. Gateway-side enforcement (the real
boundary, not just this Python check) lives in bp-gateway's urlToFeature table —
see internal/license/license.go.
"""

import frappe

from batch_projects.api.board import _check_permission, _as_bool, _parse_json, _resolve_scope, _require_system_user
from batch_projects.api.erp_link import _doctype_field_rows
from batch_projects.entitlements import require_feature


def _dashboard_out(doc, with_layout=False):
    out = {
        "id": doc.name,
        "dashboard_name": doc.dashboard_name,
        "icon": doc.icon or "LayoutDashboard",
        "color": doc.color or None,
        "starred": bool(doc.starred),
        "pinned": bool(doc.get("pinned")),
        "scope": doc.project or "all",
        "project": doc.project or None,
        "milestone": doc.milestone or None,
        "period": doc.period or "last_30_days",
        "visibility": doc.visibility or "private",
        "modified": str(doc.modified),
        "owner": doc.owner,
        "is_mine": doc.owner == frappe.session.user,
    }
    if with_layout:
        out["widgets"] = _parse_json(doc.layout, [])
    return out


@frappe.whitelist()
def list_dashboards():
    """List dashboards visible to the user: their own private ones, plus
    workspace-visible ones on projects they can access (or workspace-wide)."""
    require_feature("dashboards")
    from batch_projects.permissions import get_accessible_projects
    accessible = get_accessible_projects()
    rows = frappe.get_all(
        "BP Dashboard",
        fields=["name", "dashboard_name", "icon", "color", "starred", "pinned",
                "project", "milestone", "period", "visibility", "modified", "owner"],
        order_by="modified desc",
    )
    out = []
    for r in rows:
        if r.visibility == "private" and r.owner != frappe.session.user:
            continue
        if accessible is None or not r.project or r.project in accessible:
            out.append({
                "id": r.name, "dashboard_name": r.dashboard_name,
                "icon": r.icon or "LayoutDashboard", "color": r.color or None,
                "starred": bool(r.starred), "pinned": bool(r.pinned),
                "scope": r.project or "all",
                "project": r.project or None, "milestone": r.milestone or None,
                "period": r.period or "last_30_days",
                "visibility": r.visibility or "private",
                "modified": str(r.modified), "owner": r.owner,
                "is_mine": r.owner == frappe.session.user,
            })
    return out


@frappe.whitelist()
def get_dashboard(dashboard):
    require_feature("dashboards")
    doc = frappe.get_doc("BP Dashboard", dashboard)
    if doc.visibility == "private" and doc.owner != frappe.session.user:
        frappe.throw("Not permitted", frappe.PermissionError)
    if doc.project:
        _check_permission(doc.project, "BP Viewer")
    return _dashboard_out(doc, with_layout=True)


@frappe.whitelist()
def save_dashboard(dashboard_name=None, project=None, milestone=None, period="last_30_days",
                    icon="LayoutDashboard", color=None, layout=None, dashboard=None,
                    starred=None, pinned=None, visibility=None):
    """Create (dashboard omitted) or update (dashboard given) a BP Dashboard."""
    require_feature("dashboards")
    project = project or None
    if project:
        _check_permission(project, "BP Member")

    if dashboard:
        doc = frappe.get_doc("BP Dashboard", dashboard)
        if doc.visibility == "private" and doc.owner != frappe.session.user:
            frappe.throw("Not permitted", frappe.PermissionError)
        if doc.project:
            _check_permission(doc.project, "BP Member")
        if dashboard_name is not None: doc.dashboard_name = dashboard_name
        if project is not None or dashboard_name is not None: doc.project = project
        if milestone is not None: doc.milestone = milestone or None
        if period is not None: doc.period = period
        if icon is not None: doc.icon = icon
        if color is not None: doc.color = color
        if starred is not None: doc.starred = _as_bool(starred)
        if pinned is not None: doc.pinned = _as_bool(pinned)
        if visibility is not None: doc.visibility = visibility
        if layout is not None:
            doc.layout = layout if isinstance(layout, str) else frappe.as_json(layout)
        doc.save(ignore_permissions=True)
    else:
        doc = frappe.get_doc({
            "doctype": "BP Dashboard",
            "dashboard_name": dashboard_name or "Untitled dashboard",
            "project": project, "milestone": milestone or None,
            "period": period, "icon": icon, "color": color,
            "starred": _as_bool(starred) if starred is not None else 0,
            "pinned": _as_bool(pinned) if pinned is not None else 0,
            "visibility": visibility or "private",
            "layout": layout if isinstance(layout, str) else frappe.as_json(layout or []),
        })
        doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return _dashboard_out(doc, with_layout=True)


@frappe.whitelist()
def delete_dashboard(dashboard):
    require_feature("dashboards")
    doc = frappe.get_doc("BP Dashboard", dashboard)
    if doc.visibility == "private" and doc.owner != frappe.session.user:
        frappe.throw("Not permitted", frappe.PermissionError)
    if doc.project:
        _check_permission(doc.project, "BP Member")
    frappe.delete_doc("BP Dashboard", dashboard)
    frappe.db.commit()
    return {"deleted": dashboard}


# ─── Column widget data source ─────────────────────────────────────────────────
# A dashboard "column" widget is ONE column (one person, one status, ...) — the
# building block templates compose into a full board by adding N of them
# side by side, each independently positioned/resized on the grid. This is
# the deliberate opposite of an earlier draft that rendered many columns
# inside a single widget card: that read as a cramped table, not a real
# board. See ColumnWidget.vue.

_BUCKET_ORDER = ["overdue", "today", "this_week", "later", "no_date"]
_BUCKET_LABEL = {
    "overdue": "Overdue", "today": "Today", "this_week": "This week",
    "later": "Later", "no_date": "No due date",
}


def _bucket_for(due_date, today):
    if not due_date:
        return "no_date"
    d = due_date if hasattr(due_date, "year") else frappe.utils.getdate(due_date)
    if d < today:
        return "overdue"
    if d == today:
        return "today"
    if d <= frappe.utils.add_days(today, 6):
        return "this_week"
    return "later"


# ─── Grouping ──────────────────────────────────────────────────────────────
# A column widget's rows can be grouped three ways, chosen in Configure:
#   'date' (default) — the Overdue/Today/This week/Later time rail.
#   'none'           — one flat list, no group headers at all.
#   <fieldname>      — one group per distinct value of that field (status,
#                      priority, epic, project, labels, any Select/Link/Data
#                      field the doctype actually has).
# Every path returns the same {key,label,tasks} bucket shape, so the frontend
# renders grouped output identically no matter which mode produced it.
_GROUP_NONE_KEY = "__ungrouped__"
_GROUP_EMPTY_KEY = "__none__"


def _synthetic_fields(doctype):
    """Fields with no docfield behind them that are still real, useful things
    to filter, group or show a row by.

    BP Task's assignees live in the BP Task Assignee child table, so
    introspection can never surface them (_build_db_filters resolves the
    filter, _group_tasks_by_field the grouping). project_key/project_name are
    computed per row by get_column_widget_data — exposing them here is what
    lets a row show the short "SOLOV" key instead of a long project title
    eating the whole line.
    """
    if doctype != "BP Task":
        return []
    return [
        {"fieldname": "assignee", "label": "Assignee", "fieldtype": "Link",
         "read_only": True, "options": "User", "synthetic": True},
        {"fieldname": "project_key", "label": "Project key", "fieldtype": "Data",
         "read_only": True, "options": None, "synthetic": True},
        {"fieldname": "project_name", "label": "Project name", "fieldtype": "Data",
         "read_only": True, "options": None, "synthetic": True},
    ]


def _extra_fields(doctype, requested, exclude=()):
    """Validate caller-requested extra fieldnames against the doctype's real
    introspected schema and return the ones worth adding to a SELECT.

    Always schema-validated rather than passed through: these arrive from a
    saved row template, i.e. ultimately from the browser, and land directly
    in frappe.get_all's field list."""
    req = _parse_json(requested, []) if isinstance(requested, str) else (requested or [])
    if not req:
        return []
    valid = {f["fieldname"] for f in _readable_field_rows(doctype)}
    seen, out = set(exclude), []
    for f in req:
        if isinstance(f, str) and f in valid and f not in seen:
            out.append(f)
            seen.add(f)
    return out


def _group_rows_by_field(rows, fieldname, order_hint=None, label_map=None, empty_label="None"):
    """Bucket already-fetched rows by one field's value.

    order_hint: values in the order they should appear (a Select field's
    declared options, or a project's workflow_states). Anything not in the
    hint follows, alphabetically. The empty/unset group is always last —
    it's the residue, never the headline.

    label_map: raw value -> display label (Link fields resolve to titles).
    """
    grouped = {}
    for r in rows:
        raw = r.get("_group_value")
        key = _GROUP_EMPTY_KEY if raw in (None, "", []) else str(raw)
        grouped.setdefault(key, []).append(r)

    ordered = []
    seen = set()
    for v in (order_hint or []):
        k = str(v)
        if k in grouped and k not in seen:
            ordered.append(k)
            seen.add(k)
    rest = sorted(k for k in grouped if k not in seen and k != _GROUP_EMPTY_KEY)
    ordered.extend(rest)
    if _GROUP_EMPTY_KEY in grouped:
        ordered.append(_GROUP_EMPTY_KEY)

    out = []
    for k in ordered:
        for r in grouped[k]:
            r.pop("_group_value", None)
        out.append({
            "key": k,
            "label": empty_label if k == _GROUP_EMPTY_KEY else ((label_map or {}).get(k) or k),
            "tasks": grouped[k],
        })
    return out


@frappe.whitelist()
def get_column_widget_data(scope="all", filter_by=None, filter_value=None, status_filter="open",
                            filters=None, group_by="date", extra_fields=None):
    """One column's worth of tasks — read-mostly, click through to the real
    task to act on it. Deliberately NOT drag-and-drop; that interactivity
    already exists on the real per-project Board.vue.

    group_by: 'date' (Overdue/Today/This week/Later — the default),
    'none' (one flat list), or any groupable fieldname on BP Task
    (status/priority/project/epic/task_type/sprint/... plus the synthetic
    'assignee'). See _group_rows_by_field.

    filter_by/filter_value: the retired quick-picker, honoured only when
    explicitly passed so dashboards saved before the unified filter builder
    keep working. filter_by='assignee' with filter_value=None means
    "unassigned" — which is exactly why the default is now None rather than
    'assignee': the old default silently filtered every caller that didn't
    pass one down to unassigned tasks only, an easy trap for any new caller
    (and one this endpoint's own tests walked straight into).
    """
    require_feature("dashboards")
    # NOT `filters` — that name is this function's own parameter (the visual
    # filter-builder rows). Unpacking into it silently discarded every
    # builder filter the caller sent.
    scope_filters, proj_name, proj_names = _resolve_scope(scope)

    if proj_names:
        scope_projects = proj_names
    elif proj_name:
        scope_projects = [proj_name]
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

    db_filters = dict(scope_filters)
    if status_filter == "open" and completed:
        db_filters["status"] = ["not in", list(completed)]
    elif status_filter == "done" and completed:
        db_filters["status"] = ["in", list(completed)]

    task_names_for_assignee = None
    if filter_by == "assignee":
        if filter_value:
            task_names_for_assignee = frappe.get_all(
                "BP Task Assignee", filters={"parenttype": "BP Task", "user": filter_value},
                pluck="parent",
            )
            if not task_names_for_assignee:
                return {"buckets": []}
            db_filters["name"] = ["in", task_names_for_assignee]
        else:
            assigned = frappe.get_all("BP Task Assignee", filters={"parenttype": "BP Task"}, pluck="parent")
            if assigned:
                db_filters["name"] = ["not in", list(set(assigned))]
    elif filter_by == "status":
        db_filters["status"] = filter_value or ""
    elif filter_by == "priority":
        db_filters["priority"] = filter_value or ""
    elif filter_by == "project":
        db_filters["project"] = filter_value or ""

    # Generic filter-builder rows, on top of the legacy quick-picker above.
    # BP Task used to be the ONLY source locked to a fixed
    # assignee/status/priority/project choice while every other doctype got
    # the full visual builder — same builder, same operators (incl. relative
    # dates) now apply here too. frappe.get_all takes a dict OR a list, not a
    # mix, so the dict is flattened into the list form once there are any.
    extra = _build_db_filters("BP Task", filters) if filters else []
    if extra:
        listed = [[k, *(v if isinstance(v, list) else ["=", v])] for k, v in db_filters.items()]
        db_filters = listed + extra

    # The base set every row needs, PLUS whatever the caller's row template
    # and group-by actually reference. Without extra_fields the row designer
    # could offer any BP Task field while the query only ever returned these
    # eight — picking, say, "Story points" for a row silently rendered
    # nothing, because the value was simply never fetched.
    fields = ["name", "task_key", "title", "status", "priority", "task_type", "project", "due_date"]
    fields += _extra_fields("BP Task", extra_fields, exclude=fields)
    if group_by and group_by not in ("date", "none", "assignee") and group_by not in fields:
        fields += _extra_fields("BP Task", [group_by], exclude=fields)
    tasks = frappe.get_all("BP Task", filters=db_filters, fields=fields, order_by="due_date asc", limit_page_length=500)

    pinfo = {}
    type_colors = {}  # project -> {task_type: color}
    for t in tasks:
        p = t["project"]
        if p not in pinfo:
            row = frappe.db.get_value(
                "BP Project", p, ["project_name", "key", "theme"], as_dict=True
            ) or {}
            pinfo[p] = {
                "project_name": row.get("project_name") or p,
                # theme+key are the SAME identity pair Sidebar.vue's project
                # list renders via ProjectAvatar/resolveProjectTheme — a real
                # illustrated tile, not a Lucide icon name. project_icon (a
                # Select of line-icon names, used only by the project-icon
                # PICKER in ProjectSettings.vue) is a different, unrelated
                # field and was the wrong one to reach for here.
                "project_key": row.get("key") or p,
                "project_theme": row.get("theme") or None,
            }
        t["project_name"] = pinfo[p]["project_name"]
        t["project_key"] = pinfo[p]["project_key"]
        t["project_theme"] = pinfo[p]["project_theme"]
        # Resolve each task's type color from ITS OWN project's issue_types —
        # never the caller's currentProject (a cross-project column widget
        # has no single "current" project, and TaskCard.vue's client-side
        # store.taskTypeMap lookup would silently mismatch tasks that aren't
        # in whatever project happens to be loaded elsewhere in the app).
        if p not in type_colors:
            raw = frappe.db.get_value("BP Project", p, "issue_types")
            type_colors[p] = {it.get("name"): it.get("color") for it in _parse_json(raw, []) if it.get("name")}
        t["type_color"] = type_colors[p].get(t["task_type"]) or "var(--accent)"

    names = [t["name"] for t in tasks]
    amap = {}
    fullname = {}
    if names:
        for a in frappe.get_all("BP Task Assignee",
                                filters={"parenttype": "BP Task", "parent": ["in", names]},
                                fields=["parent", "user"]):
            amap.setdefault(a["parent"], []).append(a["user"])
        users = list({u for lst in amap.values() for u in lst})
        if users:
            for u in frappe.get_all("User", filters={"name": ["in", users]}, fields=["name", "full_name", "user_image"]):
                fullname[u["name"]] = {"full_name": u["full_name"] or u["name"], "user_image": u.get("user_image") or ""}
    for t in tasks:
        t["assignees"] = [
            {"user": u, "full_name": fullname.get(u, {}).get("full_name", u), "user_image": fullname.get(u, {}).get("user_image", "")}
            for u in amap.get(t["name"], [])
        ]

    group_by = (group_by or "date").strip()

    if group_by == "none":
        return {"buckets": [{"key": _GROUP_NONE_KEY, "label": "", "tasks": tasks}],
                "total": len(tasks), "group_by": "none"}

    if group_by and group_by != "date":
        buckets = _group_tasks_by_field(tasks, group_by, scope_projects)
        return {"buckets": buckets, "total": len(tasks), "group_by": group_by}

    today = frappe.utils.getdate()
    buckets = {}
    for t in tasks:
        b = _bucket_for(t["due_date"], today)
        buckets.setdefault(b, []).append(t)

    out = [{"key": b, "label": _BUCKET_LABEL[b], "tasks": buckets[b]} for b in _BUCKET_ORDER if buckets.get(b)]
    return {"buckets": out, "total": len(tasks), "group_by": "date"}


def _group_tasks_by_field(tasks, group_by, scope_projects):
    """Group BP Task rows by one field. Handles the three shapes a Task field
    can take: the synthetic multi-value 'assignee' (a task with two assignees
    genuinely belongs in both groups), 'labels' (a JSON list, same deal), and
    ordinary scalar fields."""
    fields_meta = {f["fieldname"]: f for f in _readable_field_rows("BP Task")}
    if group_by not in fields_meta and group_by != "assignee":
        frappe.throw(f"Cannot group BP Task by '{group_by}'.")

    # Multi-valued: one task appears under every value it holds. Anything
    # else would force an arbitrary "primary" pick and silently hide work.
    if group_by in ("assignee", "labels"):
        grouped, empty = {}, []
        label_map = {}
        for t in tasks:
            if group_by == "assignee":
                vals = [a["user"] for a in t.get("assignees") or []]
                for a in t.get("assignees") or []:
                    label_map[a["user"]] = a.get("full_name") or a["user"]
            else:
                vals = _parse_json(t.get("labels"), []) or []
                vals = [v if isinstance(v, str) else (v.get("value") or v.get("label")) for v in vals]
                vals = [v for v in vals if v]
            if not vals:
                empty.append(t)
                continue
            for v in vals:
                grouped.setdefault(str(v), []).append(t)
        out = [{"key": k, "label": label_map.get(k, k), "tasks": grouped[k]} for k in sorted(grouped)]
        if empty:
            out.append({"key": _GROUP_EMPTY_KEY,
                        "label": "Unassigned" if group_by == "assignee" else "No labels",
                        "tasks": empty})
        return out

    meta = fields_meta[group_by]
    order_hint, label_map = [], {}

    if group_by == "status":
        # A project's own workflow order, not alphabetical — "To Do, In
        # Progress, Done" is the only ordering that reads as a pipeline.
        for pn in scope_projects:
            try:
                for s in _parse_json(frappe.db.get_value("BP Project", pn, "workflow_states"), []):
                    if s.get("name") and s["name"] not in order_hint:
                        order_hint.append(s["name"])
            except Exception:
                continue
    elif meta["fieldtype"] == "Select":
        order_hint = meta.get("options") or []
    elif meta["fieldtype"] == "Link":
        label_map = _resolve_link_labels(meta.get("options"), [t.get(group_by) for t in tasks])

    for t in tasks:
        t["_group_value"] = t.get(group_by)
    return _group_rows_by_field(tasks, group_by, order_hint, label_map,
                                empty_label=f"No {(meta.get('label') or group_by).lower()}")


# ─── Generic doctype-source widget engine ──────────────────────────────────
# Doctype-agnostic sibling of the Task-only get_widget_data (board.py) and
# get_column_widget_data (above) — the "kanban" widget and the generalized
# "column" widget read through here for any doctype OTHER than BP Task, so a
# dashboard can show Leads/Deals/etc, not just tasks. Existing BP Task-
# sourced widgets keep calling the two functions above unchanged: their
# date-bucketing/multi-assignee/task-type-color logic is worth keeping
# exactly as-is, not worth re-deriving generically.
#
# Deliberately added to THIS module rather than a new one so every function
# below inherits bp-gateway's existing prefix gate
# ("/api/method/batch_projects.api.dashboards." → "dashboards", see
# internal/license/license.go) for free — that gate is the real enforcement
# boundary per this module's own header docstring; require_feature() here is
# the Python-side nicety on top of it, not a substitute for it.
#
# Security posture mirrors board.py's search_erp_documents /
# erp_link.py's get_erp_doc_summary: batch_projects System Users hold zero
# native Frappe role-permissions on these doctypes by design, so
# frappe.get_list()/doc.check_permission() would throw for every real user
# here. The WIDGET_SOURCE_DOCTYPES whitelist below IS the authorization
# boundary, not incidental style — extending it to a new doctype means
# deciding its scope_kind deliberately, not just adding a name.

# ─── Widget source catalogue ───────────────────────────────────────────────
# Declarative spec, one row per offerable doctype:
#   (doctype, label, icon, group, status_candidates, owner_candidates, date_candidates)
#
# Field names are CANDIDATE LISTS, never hardcoded single names: ERPNext
# renames/varies these across versions and apps (Quotation's party is
# `party_name`, Sales Order's is `customer`; Issue dates on `opening_date`,
# Sales Order on `transaction_date`). `_pick_field()` resolves each list
# against the doctype's REAL introspected fields at runtime and drops the
# config silently when nothing matches — so a spec row can never ship a
# field name that doesn't exist on this site's schema version.
#
# Everything here is workspace-scoped cross-project master data except
# BP Task, which carries batch_projects' own project-scoped permission
# model (get_accessible_projects / _resolve_scope).
_SOURCE_GROUPS = ("Work", "Sales", "Buying", "Stock", "Support", "People", "Finance")

# The date column is DEADLINE candidates only — never a historical date.
# Buckets are Overdue/Today/This week/Later, which is a statement about a
# date you can still MISS. Bucketing a backward-looking field (creation,
# posting_date, date_of_joining) files every existing record under "Overdue",
# which is noise, not information. Doctypes with no genuine deadline get []
# and render as a flat, newest-first list; the user can still pick any date
# field explicitly in Configure if they actually want it bucketed.
_CORE_SOURCE_SPECS = [
    # doctype, label, icon, group, status, owner, deadline
    ("BP Task", "Task", "CheckSquare2", "Work",
     ["status"], [], ["due_date"]),
    ("BP Project", "Project (BatchProjects)", "FolderKanban", "Work",
     ["status"], ["lead"], ["target_end_date"]),
    ("BP Milestone", "Milestone", "Flag", "Work",
     ["status"], ["owner"], ["due_date"]),
    ("Project", "Project (ERPNext)", "FolderGit2", "Work",
     ["status"], ["project_lead"], ["expected_end_date"]),
    ("Task", "Task (ERPNext)", "ListChecks", "Work",
     ["status"], ["completed_by"], ["exp_end_date"]),
    ("Timesheet", "Timesheet", "Timer", "Work",
     ["status"], ["employee"], []),

    ("Lead", "Lead", "UserPlus", "Sales",
     ["status"], ["lead_owner"], ["contact_date"]),
    ("Opportunity", "Opportunity", "Target", "Sales",
     ["status"], ["opportunity_owner"], ["expected_closing"]),
    ("Quotation", "Quotation", "FileText", "Sales",
     ["status"], ["party_name"], ["valid_till"]),
    ("Sales Order", "Sales Order", "ShoppingCart", "Sales",
     ["status"], ["customer"], ["delivery_date"]),
    ("Sales Invoice", "Sales Invoice", "Receipt", "Finance",
     ["status"], ["customer"], ["due_date"]),
    ("Customer", "Customer", "Building2", "Sales",
     ["customer_group"], ["territory"], []),

    ("Supplier", "Supplier", "Truck", "Buying",
     ["supplier_group"], [], []),
    ("Purchase Order", "Purchase Order", "ClipboardList", "Buying",
     ["status"], ["supplier"], ["schedule_date"]),
    ("Purchase Invoice", "Purchase Invoice", "ReceiptText", "Finance",
     ["status"], ["supplier"], ["due_date"]),
    ("Material Request", "Material Request", "PackagePlus", "Buying",
     ["status"], ["material_request_type"], ["schedule_date"]),

    ("Item", "Item", "Package", "Stock",
     ["item_group"], ["brand"], []),
    ("Delivery Note", "Delivery Note", "PackageCheck", "Stock",
     ["status"], ["customer"], []),
    ("Stock Entry", "Stock Entry", "Boxes", "Stock",
     ["stock_entry_type"], [], []),

    ("Issue", "Issue (Support)", "LifeBuoy", "Support",
     ["status"], ["raised_by"], ["resolution_by"]),

    ("Employee", "Employee", "IdCard", "People",
     ["status"], ["department"], []),

    ("Payment Entry", "Payment Entry", "Banknote", "Finance",
     ["status"], ["party"], []),
    ("Journal Entry", "Journal Entry", "BookOpen", "Finance",
     ["docstatus"], [], []),
]

# App-gated specs — only offered when that app is actually installed.
_APP_SOURCE_SPECS = {
    "hrms": [
        ("Leave Application", "Leave Application", "CalendarOff", "People",
         ["status"], ["employee"], ["from_date"]),
        ("Expense Claim", "Expense Claim", "Wallet", "People",
         ["approval_status"], ["employee"], []),
        ("Job Applicant", "Job Applicant", "UserSearch", "People",
         ["status"], ["job_title"], []),
        ("Job Opening", "Job Opening", "Briefcase", "People",
         ["status"], ["department"], ["closes_on"]),
        ("Attendance", "Attendance", "CalendarCheck", "People",
         ["status"], ["employee"], []),
    ],
    # These are correctly app-gated (installed-apps check at line 517).
    # They activate only when the corresponding Frappe app is installed
    # on the site.
    "crm": [
        ("CRM Deal", "Deal (CRM)", "Handshake", "Sales",
         ["status"], ["deal_owner"], ["closed_date"]),
        ("CRM Lead", "Lead (CRM)", "UserPlus", "Sales",
         ["status"], ["lead_owner"], []),
    ],
    "helpdesk": [
        # HD Ticket has no native owner field — assignment is via Frappe's
        # standard _assign/ToDo mechanism, not a doctype field.
        ("HD Ticket", "Ticket (Helpdesk)", "LifeBuoy", "Support",
         ["status"], [], ["resolution_by"]),
    ],
}


_LAYOUT_FIELDTYPES = {
    "Section Break", "Column Break", "Tab Break", "Table", "Table MultiSelect",
    "HTML", "Button", "Fold", "Heading", "Image", "Attach", "Attach Image",
    "Signature", "Password", "Geolocation", "Code", "Barcode",
}


def _readable_field_rows(doctype):
    """Read-scoped field introspection — the same shape as erp_link.py's
    _doctype_field_rows, but WITHOUT its `read_only` exclusion.

    That exclusion is correct for erp_link's purpose (building a WRITE form),
    and wrong for every use in this module, which is read-only: grouping,
    filtering, sorting and displaying. `status` is read_only on every
    submittable doctype (Sales Order, Sales Invoice, Purchase Order, ...) —
    inheriting that exclusion silently made the single most useful field on
    exactly those doctypes ungroupable and unfilterable.

    Writes still go through update_widget_source_field(), which validates
    against erp_link's write-scoped list, so read-only fields stay
    unwritable — this widens reads only."""
    meta = frappe.get_meta(doctype)
    out = []
    for f in meta.fields:
        if f.fieldtype in _LAYOUT_FIELDTYPES or f.hidden:
            continue
        row = {
            "fieldname": f.fieldname,
            "label": f.label or f.fieldname,
            "fieldtype": f.fieldtype,
            "read_only": bool(f.read_only),
            "options": None,
        }
        if f.fieldtype == "Select":
            row["options"] = [o for o in (f.options or "").split("\n") if o]
        elif f.fieldtype == "Link":
            row["options"] = f.options
        out.append(row)
    # Standard columns every doctype has, useful for grouping/sorting and not
    # part of meta.fields.
    out.append({"fieldname": "owner", "label": "Created By", "fieldtype": "Link",
                "read_only": True, "options": "User"})
    out.append({"fieldname": "creation", "label": "Created On", "fieldtype": "Datetime",
                "read_only": True, "options": None})
    out.append({"fieldname": "modified", "label": "Last Modified", "fieldtype": "Datetime",
                "read_only": True, "options": None})
    return sorted(out, key=lambda r: r["label"])


def _pick_field(fields_meta, candidates):
    """First candidate that genuinely exists on the doctype, else None.
    `docstatus`/`creation`/`owner` are real columns on every doctype but are
    not returned by _doctype_field_rows' introspection, so accept those by
    name — everything else must be a genuine introspected field."""
    _ALWAYS = {"docstatus", "creation", "modified", "owner"}
    for c in candidates or []:
        if c in fields_meta or c in _ALWAYS:
            return c
    return None


def _spec_to_entry(spec):
    doctype, label, icon, group, status_c, owner_c, date_c = spec
    fields_meta = {f["fieldname"]: f for f in _readable_field_rows(doctype)}
    return {
        "label": label,
        "icon": icon,
        "group": group,
        "scope_kind": "project" if doctype == "BP Task" else "workspace",
        "status_field": _pick_field(fields_meta, status_c),
        "owner_field": _pick_field(fields_meta, owner_c),
        "date_field": _pick_field(fields_meta, date_c),
    }


def _widget_source_registry():
    """Dict insertion order = picker order (Work first, then Sales, ...).
    Only doctypes that actually EXIST on this site are included — a spec row
    for an app-gated doctype that was later uninstalled just disappears."""
    specs = list(_CORE_SOURCE_SPECS)
    installed = set(frappe.get_installed_apps())
    for app, app_specs in _APP_SOURCE_SPECS.items():
        if app in installed:
            specs.extend(app_specs)

    reg = {}
    for spec in specs:
        doctype = spec[0]
        if not frappe.db.exists("DocType", doctype):
            continue
        try:
            reg[doctype] = _spec_to_entry(spec)
        except Exception:
            # A doctype present but not introspectable (broken custom app,
            # partial install) must not take the whole picker down with it.
            continue
    return reg


def _can_read(doctype):
    """Real Frappe read permission for the current user.

    BP Task is exempt: batch_projects System Users deliberately hold zero
    native role-permissions on BP doctypes — their access runs through
    get_accessible_projects()/_check_permission() instead, which every
    BP Task path here already applies via _resolve_scope().

    Every OTHER source is real ERP data (Sales Invoice, Payment Entry,
    Employee, ...), so the whitelist alone is NOT a sufficient authorization
    boundary — a user who cannot read Sales Invoice in ERPNext must not read
    it through a dashboard widget either."""
    if doctype == "BP Task":
        return True
    return bool(frappe.has_permission(doctype, "read"))


def _can_write(doctype):
    """Real Frappe write permission for the current user.

    BP Task is exempt (same reasoning as _can_read — batch_projects System
    Users have zero native role-permissions on BP doctypes; their access
    runs through get_accessible_projects()/_check_permission()).

    Every OTHER source doctype (Sales Invoice, Payment Entry, ...) must
    pass Frappe's real write-permission check before any drag-and-drop
    save — the whitelist alone gates visibility, not mutability."""
    if doctype == "BP Task":
        return True
    return bool(frappe.has_permission(doctype, "write"))


def _widget_source_entry(doctype):
    entry = _widget_source_registry().get(doctype)
    if not entry:
        frappe.throw(f"DocType '{doctype}' is not available as a dashboard widget source.")
    if not _can_read(doctype):
        frappe.throw(f"You don't have permission to read {doctype}.", frappe.PermissionError)
    return entry


@frappe.whitelist()
def get_widget_source_doctypes():
    """Doctypes offered in the widget Configure modal's doctype picker —
    only ones actually installed/whitelisted, never an open-ended dropdown
    of every doctype on the site, and only ones THIS user can really read
    (so the picker never advertises a source whose data would then 403)."""
    require_feature("dashboards")
    _require_system_user()
    return [
        {"doctype": dt, "label": e["label"], "icon": e["icon"],
         "group": e["group"], "scope_kind": e["scope_kind"],
         "status_field": e["status_field"], "date_field": e["date_field"]}
        for dt, e in _widget_source_registry().items()
        if _can_read(dt)
    ]


@frappe.whitelist()
def get_widget_source_fields(doctype):
    """Real filterable field list for `doctype`, for the visual filter
    builder's field dropdown — delegates to erp_link.py's generic
    frappe.get_meta()-based introspection instead of a second copy, plus the
    synthetic fields below that have no docfield but are genuinely
    filterable/groupable (see _synthetic_fields)."""
    require_feature("dashboards")
    _require_system_user()
    _widget_source_entry(doctype)
    return _readable_field_rows(doctype) + _synthetic_fields(doctype)


@frappe.whitelist()
def get_widget_source_field_options(doctype, fieldname, query=None, limit=20):
    """Value options for one Link/Select field on `doctype`, for the filter
    builder's value picker. Only reachable for fields erp_link.py's
    introspection already exposes (skips hidden/read-only/layout fields) on
    a whitelisted source doctype — every Link target here is shared,
    non-tenant master data (User, Territory, Lead Source, Industry, CRM
    Lead/Deal Status, ...), same posture as board.py's search_erp_documents
    treating Lead/Opportunity as unscoped cross-project master data."""
    require_feature("dashboards")
    _require_system_user()
    _widget_source_entry(doctype)
    field = next((f for f in _readable_field_rows(doctype) if f["fieldname"] == fieldname), None)
    if not field or field["fieldtype"] not in ("Select", "Link"):
        frappe.throw(f"Field '{fieldname}' is not filterable on {doctype}.")

    q = (query or "").strip().lower()
    if field["fieldtype"] == "Select":
        return [{"value": o, "label": o} for o in (field["options"] or []) if not q or q in o.lower()]

    target_dt = field["options"]
    title_field = frappe.db.get_value("DocType", target_dt, "title_field") or "name"
    filters = [[title_field, "like", f"%{query}%"]] if query else []
    pluck_fields = ["name"] if title_field == "name" else ["name", title_field]
    rows = frappe.get_all(target_dt, filters=filters, fields=pluck_fields,
                           limit_page_length=int(limit or 20), order_by="modified desc")
    return [{"value": r["name"], "label": r.get(title_field) or r["name"]} for r in rows]


@frappe.whitelist()
def get_multi_source_count(sources, scope=None):
    """Sum of FILTERED RECORD COUNTS across one or more doctypes, for the
    'metric' widget's multi-source mode — e.g. "open Leads" + "active
    Deals" as one KPI number, instead of one BP-Task rollup.

    sources: [{doctype, filters}, ...] — each doctype must be in the same
    whitelisted, permission-checked registry the column/kanban widgets'
    doctype picker already uses (_widget_source_entry); an unlisted or
    unreadable doctype throws rather than silently contributing 0, so a
    misconfigured widget is visibly wrong, not quietly undercounting.

    A BP Task source additionally gets the widget's own project `scope`
    folded in (_resolve_scope) — the same project-scoping every other
    Task-sourced widget on this dashboard already respects. Other
    doctypes have no such concept here and use only their own filters.

    Returns {total, breakdown: [{doctype, label, count}, ...]} — shaped
    like get_widget_data's {total, ...} so WidgetView.vue's Metric
    template (`widget.data.total`) needs no special case for this mode.
    """
    require_feature("dashboards")
    _require_system_user()
    sources = _parse_json(sources, []) if isinstance(sources, str) else (sources or [])
    if not sources:
        return {"total": 0, "breakdown": []}

    breakdown = []
    for src in sources:
        doctype = (src or {}).get("doctype")
        if not doctype:
            continue
        entry = _widget_source_entry(doctype)  # validates registry membership + real read permission
        db_filters = _build_db_filters(doctype, src.get("filters"))
        if doctype == "BP Task":
            scope_filters, _, _ = _resolve_scope(scope or "all")
            db_filters = [[k, *(v if isinstance(v, list) else ["=", v])] for k, v in scope_filters.items()] + db_filters
        count = frappe.db.count(doctype, filters=db_filters)
        breakdown.append({"doctype": doctype, "label": entry["label"], "count": count})

    return {"total": sum(b["count"] for b in breakdown), "breakdown": breakdown}


def _assignee_filter(operator, value):
    """Translate an `assignee` filter row into plain BP Task `name` filters.

    Returns a list of get_all filter triples. The child-table lookup happens
    here (one query, no join), which keeps every caller — column widget,
    kanban, metric counts — filtering assignees identically.
    """
    if operator in ("is_set", "is_not_set"):
        assigned = set(frappe.get_all("BP Task Assignee",
                                      filters={"parenttype": "BP Task"}, pluck="parent"))
        if operator == "is_set":
            return [["name", "in", list(assigned) or [""]]]
        return [["name", "not in", list(assigned)]] if assigned else []

    vals = value if isinstance(value, (list, tuple)) else [value]
    vals = [v for v in vals if v not in (None, "")]
    if not vals:
        # An explicit "assignee is <nothing>" is the unassigned filter, which
        # is a real thing people want — not a no-op.
        assigned = set(frappe.get_all("BP Task Assignee",
                                      filters={"parenttype": "BP Task"}, pluck="parent"))
        return [["name", "not in", list(assigned)]] if assigned else []

    names = set(frappe.get_all("BP Task Assignee",
                               filters={"parenttype": "BP Task", "user": ["in", vals]},
                               pluck="parent"))
    negate = operator in ("!=", "not in")
    if negate:
        return [["name", "not in", list(names)]] if names else []
    # Empty match set must still filter everything out, hence the [""] —
    # an empty IN list is silently dropped by the query builder and would
    # widen the result to "all tasks", the exact opposite of the intent.
    return [["name", "in", list(names) or [""]]]


_SAFE_FILTER_OPERATORS = {
    "=", "!=", "in", "not in", "like", "not like", "is_set", "is_not_set",
    # Comparisons — needed for every Date/Datetime/Int/Float/Currency field.
    # Without these a date field could only be matched for exact equality,
    # which is never what anyone actually wants from a date.
    ">", "<", ">=", "<=", "between",
    # Relative dates, resolved server-side from a token (see _DATE_PRESETS).
    # This is the "rich filtering without writing queries" path: the user
    # picks "in the next 7 days", not two calendar dates that go stale the
    # moment the dashboard is saved.
    "date_preset",
}

# token -> (operator, value) built fresh on every query, relative to today.
# A saved dashboard filter therefore keeps meaning "the next 7 days" forever
# instead of freezing the week it was authored.
def _date_preset_filter(token):
    from frappe.utils import add_days, add_months, get_first_day, get_last_day, getdate

    today = getdate()
    week_start = add_days(today, -today.weekday())          # Monday
    presets = {
        "today":        ("=", today),
        "yesterday":    ("=", add_days(today, -1)),
        "tomorrow":     ("=", add_days(today, 1)),
        "overdue":      ("<", today),
        "this_week":    ("between", [week_start, add_days(week_start, 6)]),
        "last_week":    ("between", [add_days(week_start, -7), add_days(week_start, -1)]),
        "next_week":    ("between", [add_days(week_start, 7), add_days(week_start, 13)]),
        "next_7_days":  ("between", [today, add_days(today, 7)]),
        "next_14_days": ("between", [today, add_days(today, 14)]),
        "next_30_days": ("between", [today, add_days(today, 30)]),
        "last_7_days":  ("between", [add_days(today, -7), today]),
        "last_30_days": ("between", [add_days(today, -30), today]),
        "last_90_days": ("between", [add_days(today, -90), today]),
        "this_month":   ("between", [get_first_day(today), get_last_day(today)]),
        "last_month":   ("between", [get_first_day(add_months(today, -1)),
                                     get_last_day(add_months(today, -1))]),
        "next_month":   ("between", [get_first_day(add_months(today, 1)),
                                     get_last_day(add_months(today, 1))]),
    }
    if token not in presets:
        frappe.throw(f"Unknown date preset: {token}")
    return presets[token]


@frappe.whitelist()
def get_date_presets():
    """The relative-date vocabulary the filter builder offers. Served from
    the backend so the token list can never drift from what
    _date_preset_filter() actually knows how to resolve."""
    require_feature("dashboards")
    _require_system_user()
    return [
        {"value": "overdue", "label": "Overdue"},
        {"value": "today", "label": "Today"},
        {"value": "tomorrow", "label": "Tomorrow"},
        {"value": "yesterday", "label": "Yesterday"},
        {"value": "this_week", "label": "This week"},
        {"value": "next_week", "label": "Next week"},
        {"value": "last_week", "label": "Last week"},
        {"value": "next_7_days", "label": "Next 7 days"},
        {"value": "next_14_days", "label": "Next 14 days"},
        {"value": "next_30_days", "label": "Next 30 days"},
        {"value": "last_7_days", "label": "Last 7 days"},
        {"value": "last_30_days", "label": "Last 30 days"},
        {"value": "last_90_days", "label": "Last 90 days"},
        {"value": "this_month", "label": "This month"},
        {"value": "next_month", "label": "Next month"},
        {"value": "last_month", "label": "Last month"},
    ]


def _build_db_filters(doctype, filters):
    """Turn the filter builder's [{fieldname, operator, value}, ...] into
    frappe.get_all filters, validating every fieldname against the
    doctype's real (introspected) field list first — never trust the
    frontend's fieldname/operator strings directly into a query."""
    fields_meta = {f["fieldname"]: f for f in _readable_field_rows(doctype)}
    valid_fields = set(fields_meta)
    parsed = _parse_json(filters, []) if isinstance(filters, str) else (filters or [])
    out = []
    for f in parsed:
        fieldname = f.get("fieldname")
        operator = f.get("operator")
        value = f.get("value")

        # 'assignee' is not a docfield — BP Task keeps assignees in the
        # BP Task Assignee child table — so the introspected field list can
        # never contain it and the visual builder had no way to express
        # "assigned to X" at all. Resolve it here into a name-in-set filter
        # so the builder covers everything the retired quick picker did.
        if doctype == "BP Task" and fieldname == "assignee":
            out.extend(_assignee_filter(operator, value))
            continue

        if fieldname not in valid_fields:
            frappe.throw(f"Unknown filter field: {fieldname}")

        # Frappe's query builder wraps nullable columns in IFNULL() for
        # comparisons, so `due_date < today` also matches rows where due_date
        # is NULL (IFNULL(due_date,'0001-01-01') is less than any real date).
        # For "before"-style comparisons on a date that silently turns
        # "overdue" into "overdue OR has no date at all" — 14 undated tasks
        # were showing up as overdue here. Pair every such comparison with an
        # explicit is-set guard.
        _is_date = fields_meta[fieldname]["fieldtype"] in ("Date", "Datetime")
        _before_op = operator in ("<", "<=") or (
            operator == "date_preset" and str(value) in ("overdue", "yesterday")
        )
        if _is_date and _before_op:
            out.append([fieldname, "is", "set"])
        if operator not in _SAFE_FILTER_OPERATORS:
            frappe.throw(f"Unsupported filter operator: {operator}")
        if operator == "is_set":
            out.append([fieldname, "is", "set"])
        elif operator == "is_not_set":
            out.append([fieldname, "is", "not set"])
        elif operator == "like":
            out.append([fieldname, "like", f"%{value}%"])
        elif operator == "not like":
            out.append([fieldname, "not like", f"%{value}%"])
        elif operator == "date_preset":
            op, val = _date_preset_filter(value)
            out.append([fieldname, op, val])
        elif operator == "between":
            # Two concrete bounds from the UI's from/to pair. Anything that
            # isn't a usable 2-item range is a bad request, not a silent
            # no-op that would quietly widen the result set.
            pair = value if isinstance(value, (list, tuple)) else str(value or "").split(",")
            pair = [str(p).strip() for p in pair if str(p).strip()]
            if len(pair) != 2:
                frappe.throw(f"'between' on {fieldname} needs exactly two values.")
            out.append([fieldname, "between", pair])
        elif operator in ("in", "not in"):
            # A single-value pick from the UI arrives as a bare string.
            vals = value if isinstance(value, (list, tuple)) else [value]
            vals = [v for v in vals if v not in (None, "")]
            if not vals:
                continue        # an empty "is any of" filters nothing
            out.append([fieldname, operator, list(vals)])
        else:
            out.append([fieldname, operator, value])
    return out


def _resolve_link_labels(target_dt, values):
    """Batch-resolve display labels for a set of Link field values (e.g.
    CRM Lead Status names) via that target doctype's own title_field — most
    of these registry doctypes autoname their status docs FROM the label
    field already (so name IS the label), but this stays correct even when
    that's not true."""
    values = [v for v in set(values) if v]
    if not values:
        return {}
    title_field = frappe.db.get_value("DocType", target_dt, "title_field") or "name"
    if title_field == "name":
        return {v: v for v in values}
    rows = frappe.get_all(target_dt, filters={"name": ["in", values]}, fields=["name", title_field])
    return {r["name"]: (r.get(title_field) or r["name"]) for r in rows}


@frappe.whitelist()
def get_doctype_group_data(doctype, group_by, filters=None, scope=None):
    """Doctype-agnostic group/aggregate engine for the 'kanban' widget's
    auto-columns and chart widgets sourced from a non-Task doctype —
    parametrized sibling of board.py's Task-only get_widget_data."""
    require_feature("dashboards")
    _require_system_user()
    entry = _widget_source_entry(doctype)

    fields_meta = {f["fieldname"]: f for f in _readable_field_rows(doctype)}
    gb_meta = fields_meta.get(group_by)
    if not gb_meta or gb_meta["fieldtype"] not in ("Select", "Link"):
        frappe.throw(f"'{group_by}' is not a groupable field on {doctype}.")

    db_filters = _build_db_filters(doctype, filters)
    if entry["scope_kind"] == "project":
        scope_filters, _, _ = _resolve_scope(scope)
        for k, v in scope_filters.items():
            db_filters.append([k, *(v if isinstance(v, list) else ["=", v])])

    rows = frappe.get_all(doctype, filters=db_filters, fields=[group_by], limit_page_length=0)
    counts = {}
    for r in rows:
        counts[r[group_by]] = counts.get(r[group_by], 0) + 1

    labels = _resolve_link_labels(gb_meta["options"], counts.keys()) if gb_meta["fieldtype"] == "Link" else {}
    items = [
        {"key": k or "__none__", "label": (labels.get(k, k) if k else "None"), "value": v}
        for k, v in counts.items()
    ]
    items.sort(key=lambda i: -i["value"])
    return {"items": items, "total": sum(counts.values()), "group_by": group_by, "doctype": doctype}


@frappe.whitelist()
def get_doctype_column_data(doctype, filters=None, sort=None, limit=200, scope=None,
                             label_fields=None, date_field=None, group_by="date",
                             extra_fields=None):
    """Doctype-agnostic row-list engine for the generalized 'column' widget
    (glance row list) and the 'kanban' widget's non-Task cards —
    parametrized sibling of get_column_widget_data above (which stays
    BP-Task-only: its date-bucketing/assignee/type-color logic is worth
    keeping exactly as-is).

    label_fields: fieldnames shown as chips on the row's second line (the
    pre-row-designer path; no count limit — WidgetRow collapses overflow).
    date_field: one Date/Datetime fieldname shown right-aligned, or None —
    None IS the "hide date" option (one control, nothing to get out of sync).
    """
    require_feature("dashboards")
    if doctype == "BP Task":
        frappe.throw("Use get_column_widget_data for BP Task — this endpoint is for other doctypes.")
    _require_system_user()
    entry = _widget_source_entry(doctype)

    fields_meta = {f["fieldname"]: f for f in _readable_field_rows(doctype)}
    title_field = frappe.db.get_value("DocType", doctype, "title_field") or "name"
    status_field = entry.get("status_field")
    owner_field = entry.get("owner_field")

    # An unset date_field falls back to the registry's per-doctype default
    # (Sales Order → delivery_date, Issue → opening_date, ...) so a freshly
    # added column widget buckets by the RIGHT date for its doctype with no
    # configuration. Explicit "" (not None) means the user deliberately chose
    # "no date" and must stay unbucketed.
    if date_field is None:
        date_field = entry.get("date_field")
    date_field = date_field or None
    if date_field and fields_meta.get(date_field, {}).get("fieldtype") not in ("Date", "Datetime"):
        frappe.throw(f"'{date_field}' is not a Date/Datetime field on {doctype}.")
    label_parsed = _parse_json(label_fields, []) if isinstance(label_fields, str) else (label_fields or [])
    group_by = (group_by or "date").strip()
    if group_by not in ("date", "none") and group_by not in fields_meta:
        frappe.throw(f"Cannot group {doctype} by '{group_by}'.")
    # No artificial cap: the row designer decides what shows and WidgetRow
    # measures real width to collapse the overflow into "+N". A hard [:3]
    # here silently dropped the 4th chip onwards with no feedback anywhere.
    labels_wanted = [f for f in label_parsed if f in fields_meta]

    wanted = ["name", "modified"]
    if title_field != "name":
        wanted.append(title_field)
    if status_field:
        wanted.append(status_field)
    if owner_field:
        wanted.append(owner_field)
    if date_field and date_field not in wanted:
        wanted.append(date_field)
    for f in labels_wanted:
        if f not in wanted:
            wanted.append(f)
    # Fields the caller's row template / group-by reference but nothing above
    # already selected. Without this the row designer could offer any field
    # while the query returned only the handful hard-coded here, so the block
    # rendered blank with no error anywhere.
    wanted += _extra_fields(doctype, extra_fields, exclude=wanted)
    if group_by not in ("date", "none") and group_by not in wanted:
        wanted.append(group_by)

    db_filters = _build_db_filters(doctype, filters)
    order_by = f"{date_field} asc" if date_field else (f"{sort} desc" if sort and sort in fields_meta else "modified desc")
    rows = frappe.get_all(doctype, filters=db_filters, fields=wanted,
                           order_by=order_by, limit_page_length=int(limit or 200))

    # Grouping keys off the RAW stored value, not the display label in `out`
    # — two records with the same label but different underlying links must
    # not collapse into one group.
    raw_by_name = {r["name"]: r for r in rows}

    status_labels = {}
    if status_field and fields_meta.get(status_field, {}).get("fieldtype") == "Link":
        status_labels = _resolve_link_labels(fields_meta[status_field]["options"],
                                              [r.get(status_field) for r in rows])

    # Generic across whatever doctype owner_field actually links to (User for
    # Lead/Opportunity/CRM Deal/Lead today, but not guaranteed for a future
    # registry entry) — resolve the label via _resolve_link_labels the same
    # way status values are, and only additionally fetch user_image when the
    # target really is User. A non-User owner still gets a real name; Avatar
    # already renders initials fine with no image (used that way elsewhere).
    owners = {r.get(owner_field) for r in rows if owner_field and r.get(owner_field)}
    owner_names = {}
    if owners:
        owner_target_dt = fields_meta.get(owner_field, {}).get("options") or "User"
        labels = _resolve_link_labels(owner_target_dt, owners)
        images = {}
        if owner_target_dt == "User":
            for u in frappe.get_all("User", filters={"name": ["in", list(owners)]},
                                     fields=["name", "user_image"]):
                images[u["name"]] = u.get("user_image") or ""
        for o in owners:
            owner_names[o] = {"user": o, "full_name": labels.get(o, o), "user_image": images.get(o, "")}

    # Batch-resolve label-field values that are themselves Link fields (e.g.
    # a "territory" label column) the same way status/owner already are.
    label_link_lookups = {}
    for f in labels_wanted:
        if fields_meta[f]["fieldtype"] == "Link":
            label_link_lookups[f] = _resolve_link_labels(fields_meta[f]["options"], [r.get(f) for r in rows])

    # Row-template fields, resolved to what a row should DISPLAY. A Link
    # stores a docname (`CRM-LEAD-2026-00004`, a User id) but a row wants the
    # human title, same as the label/status/owner paths above already do.
    template_fields = _extra_fields(doctype, extra_fields)
    template_link_lookups = {}
    for f in template_fields:
        if fields_meta.get(f, {}).get("fieldtype") == "Link":
            template_link_lookups[f] = _resolve_link_labels(fields_meta[f]["options"], [r.get(f) for r in rows])

    out = []
    for r in rows:
        date_val = r.get(date_field) if date_field else None
        row = {
            "name": r["name"],
            "title": r.get(title_field) or r["name"],
            "modified": str(r.get("modified") or ""),
            "status": (status_labels.get(r.get(status_field), r.get(status_field)) if status_field else None),
            "owner": owner_names.get(r.get(owner_field)) if owner_field else None,
            "date": str(date_val) if date_val else None,
            "labels": [
                {"label": fields_meta[f]["label"], "value": label_link_lookups.get(f, {}).get(r.get(f), r.get(f))}
                for f in labels_wanted if r.get(f) not in (None, "")
            ],
        }
        # THE bug this block fixes: `out` was a fixed-shape rebuild, so every
        # field a row template asked for was fetched by the query above and
        # then silently dropped here — the designer let you add First Name /
        # Company / Country and the widget rendered an empty row, with the
        # data plainly visible in the record's own detail panel. Only fields
        # not already occupying a reserved key are copied, so a template
        # referencing `status` can't clobber the resolved status label.
        for f in template_fields:
            if f in row:
                continue
            v = r.get(f)
            row[f] = template_link_lookups.get(f, {}).get(v, v) if v is not None else None
        out.append(row)

    # Grouping — the same three modes BP Task columns get (see the Grouping
    # block near _bucket_for). `rows` is still returned unchanged so callers
    # that want the flat list keep working.
    buckets = []
    if group_by == "none":
        buckets = [{"key": _GROUP_NONE_KEY, "label": "", "tasks": out}]
    elif group_by != "date":
        meta = fields_meta[group_by]
        order_hint = meta.get("options") or [] if meta["fieldtype"] == "Select" else []
        label_map = {}
        if meta["fieldtype"] == "Link":
            label_map = _resolve_link_labels(meta.get("options"), [r.get(group_by) for r in raw_by_name.values()])
        for row in out:
            row["_group_value"] = raw_by_name.get(row["name"], {}).get(group_by)
        buckets = _group_rows_by_field(out, group_by, order_hint, label_map,
                                       empty_label=f"No {(meta.get('label') or group_by).lower()}")
    elif date_field:
        today = frappe.utils.getdate()
        grouped = {}
        for row in out:
            grouped.setdefault(_bucket_for(row["date"], today), []).append(row)
        # "No due date" is BP Task's wording; a Sales Order column bucketing
        # on delivery_date needs that field's own name instead.
        no_date_label = f"No {(fields_meta.get(date_field, {}).get('label') or 'date').lower()}"
        buckets = [
            {"key": b, "label": (no_date_label if b == "no_date" else _BUCKET_LABEL[b]),
             "tasks": grouped[b]}
            for b in _BUCKET_ORDER if grouped.get(b)
        ]

    return {"rows": out, "buckets": buckets, "total": len(out),
            "doctype": doctype, "date_field": date_field, "group_by": group_by}


@frappe.whitelist()
def update_widget_source_field(doctype, name, fieldname, value):
    """Drag-and-drop write for the 'kanban' widget's non-Task columns —
    mirrors bp_automation_rule.py's _update_erpnext_document() body exactly:
    whitelist check (the existing WIDGET_SOURCE_DOCTYPES registry, no new
    list to maintain), docstatus!=1 guard, skip-if-unchanged, then
    doc.set()+save(). Frappe's own doctype validate() hooks ARE the "proper
    validation" here — no new state machine, same posture as that function."""
    require_feature("dashboards")
    if doctype == "BP Task":
        frappe.throw("Use update_task_status/move_task for BP Task.")
    _widget_source_entry(doctype)
    if not _can_write(doctype):
        frappe.throw(f"You don't have permission to modify {doctype}.", frappe.PermissionError)
    _require_system_user()

    valid_fields = {f["fieldname"] for f in _doctype_field_rows(doctype)}
    if fieldname not in valid_fields:
        frappe.throw(f"'{fieldname}' is not a writable field on {doctype}.")

    doc = frappe.get_doc(doctype, name)
    if doc.get("docstatus") == 1:
        frappe.throw("This record is submitted and can't be changed here.")
    if doc.get(fieldname) == value:
        return {"ok": True, "changed": False}

    doc.set(fieldname, value)
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {"ok": True, "changed": True}


@frappe.whitelist()
def get_widget_source_doc_quickview(doctype, name):
    """Curated, read-only summary of one record from a non-Task widget-
    source doctype, for the generic quickview drawer. BP Task keeps using
    the real TaskDetail sidebar instead — never routed here. Gated only by
    require_feature('dashboards'), NOT the money/profitability entitlement
    chain get_erp_doc_summary (erp_link.py) uses — this isn't financial
    data and that function's scope is deliberately narrower than this."""
    require_feature("dashboards")
    if doctype == "BP Task":
        frappe.throw("Use the Task detail panel for BP Task records.")
    _widget_source_entry(doctype)
    _require_system_user()

    fields = _readable_field_rows(doctype)
    title_field = frappe.db.get_value("DocType", doctype, "title_field") or "name"
    fieldnames = list({title_field, *[f["fieldname"] for f in fields]})
    row = frappe.db.get_value(doctype, name, fieldnames, as_dict=True)
    if not row:
        frappe.throw("Not found.", frappe.DoesNotExistError)

    out_fields = []
    for f in fields:
        v = row.get(f["fieldname"])
        if v in (None, ""):
            continue
        if f["fieldtype"] == "Link":
            v = _resolve_link_labels(f["options"], [v]).get(v, v)
        out_fields.append({"label": f["label"], "value": v, "fieldname": f["fieldname"], "fieldtype": f["fieldtype"]})

    return {
        "doctype": doctype, "name": name,
        "title": row.get(title_field) or name,
        "fields": out_fields,
    }
