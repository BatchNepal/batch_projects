"""Single source of truth for project templates.

A *template* defines the shape a project takes the moment it is created:
its workflow states (statuses), its issue types, which views it exposes,
and its default billing type. Everything else in the app — the create
flow, the project detail page, the board — reads from here.

Adding a new industry template = add ONE entry to ``PROJECT_TEMPLATES``.
The frontend pulls these over the ``get_project_templates`` API, so the
definitions can never drift between client and server again.

NOTE: ``views`` only declares which views a project *exposes*. Whether a
view's heavy compute actually runs (e.g. Gantt critical-path) is decided
by the licensed gateway, not here. This file is the free, structural layer.
"""

import frappe

# ─── Issue type catalog ───────────────────────────────────────────────
# name -> presentation. Templates reference these by name.

ISSUE_TYPE_CATALOG = {
    # Universal
    "Task":         {"color": "#0B6BCB", "icon": "CheckSquare",    "description": "A unit of work to be completed."},
    "Milestone":    {"color": "#1F7A1F", "icon": "Flag",           "description": "A key delivery point or deadline."},
    "Sub-task":     {"color": "#636B74", "icon": "GitBranch",      "description": "A smaller piece of work under a task."},
    # Software
    "Bug":          {"color": "#C41C1C", "icon": "Bug",            "description": "A defect that needs fixing."},
    "Story":        {"color": "#7C3AED", "icon": "BookOpen",       "description": "A requirement from the user's perspective."},
    "Epic":         {"color": "#0E6B93", "icon": "Layers",         "description": "A large body of work spanning many tasks."},
    "Spike":        {"color": "#9A5B13", "icon": "Zap",            "description": "A time-boxed research or investigation."},
    # Construction / EPC
    "RFI":          {"color": "#0E6B93", "icon": "HelpCircle",     "description": "Request for information from a stakeholder."},
    "Submittal":    {"color": "#9A5B13", "icon": "FileCheck",      "description": "Material or shop drawing submitted for approval."},
    "Change Order": {"color": "#B45309", "icon": "FileDiff",       "description": "A change to scope, cost, or schedule."},
    "Punch Item":   {"color": "#C41C1C", "icon": "ClipboardCheck", "description": "A defect to fix before handover."},
    "Inspection":   {"color": "#1F7A1F", "icon": "SearchCheck",    "description": "A site or quality inspection."},
    # Services / Creative
    "Deliverable":  {"color": "#7C3AED", "icon": "Package",        "description": "A client-facing deliverable."},
    "Request":      {"color": "#0E6B93", "icon": "Inbox",          "description": "A client ask or support ticket."},
    "Approval":     {"color": "#1F7A1F", "icon": "CircleCheck",    "description": "A sign-off or approval gate."},
    "Revision":     {"color": "#9A5B13", "icon": "RotateCcw",      "description": "A round of requested changes."},
    "Asset":        {"color": "#BE185D", "icon": "Image",          "description": "A creative or media asset."},
    # Operations
    "Work Order":   {"color": "#0B6BCB", "icon": "ClipboardList",  "description": "A scheduled operational job."},
    "Incident":     {"color": "#C41C1C", "icon": "TriangleAlert",  "description": "An unplanned disruption to resolve."},
    "Maintenance":  {"color": "#9A5B13", "icon": "Wrench",         "description": "Preventive or scheduled maintenance."},
}

# The pool of types the editor offers, by template category — keeps the chooser
# industry-appropriate instead of dumping the whole catalog on every project.
ISSUE_TYPE_POOLS = {
    "Software":     ["Task", "Bug", "Story", "Epic", "Spike", "Sub-task", "Milestone"],
    "Construction": ["Task", "Milestone", "RFI", "Submittal", "Change Order", "Punch Item", "Inspection", "Sub-task"],
    "Services":     ["Task", "Milestone", "Deliverable", "Request", "Approval", "Revision", "Asset", "Sub-task"],
    "Operations":   ["Task", "Work Order", "Incident", "Maintenance", "Request", "Milestone", "Sub-task"],
    "General":      ["Task", "Milestone", "Sub-task", "Request"],
}

# ─── Workflow presets ─────────────────────────────────────────────────
# template id -> ordered list of workflow states.

WORKFLOW_PRESETS = {
    "blank": [
        {"name": "Backlog", "color": "#9FA6AD", "category": "unstarted"},
        {"name": "Done",    "color": "#1F7A1F", "category": "completed"},
    ],
    "kanban": [
        {"name": "To Do",       "color": "#9FA6AD", "category": "unstarted"},
        {"name": "In Progress", "color": "#0B6BCB", "category": "started"},
        {"name": "In Review",   "color": "#9A5B13", "category": "started"},
        {"name": "Done",        "color": "#1F7A1F", "category": "completed"},
        {"name": "Cancelled",   "color": "#C41C1C", "category": "cancelled"},
    ],
    "scrum": [
        {"name": "Backlog",     "color": "#9FA6AD", "category": "unstarted"},
        {"name": "To Do",       "color": "#636B74", "category": "unstarted"},
        {"name": "In Progress", "color": "#0B6BCB", "category": "started"},
        {"name": "In Review",   "color": "#9A5B13", "category": "started"},
        {"name": "Done",        "color": "#1F7A1F", "category": "completed"},
    ],
    "bug-tracking": [
        {"name": "New",         "color": "#9FA6AD", "category": "unstarted"},
        {"name": "Triaged",     "color": "#0B6BCB", "category": "started"},
        {"name": "In Progress", "color": "#4393E4", "category": "started"},
        {"name": "Resolved",    "color": "#1F7A1F", "category": "completed"},
    ],
    "client-delivery": [
        {"name": "Scoping",     "color": "#9FA6AD", "category": "unstarted"},
        {"name": "In Progress", "color": "#0B6BCB", "category": "started"},
        {"name": "In Review",   "color": "#9A5B13", "category": "started"},
        {"name": "Delivered",   "color": "#1F7A1F", "category": "completed"},
        {"name": "Invoiced",    "color": "#7C3AED", "category": "completed"},
    ],
    "retainer": [
        {"name": "To Do",       "color": "#9FA6AD", "category": "unstarted"},
        {"name": "In Progress", "color": "#0B6BCB", "category": "started"},
        {"name": "In Review",   "color": "#9A5B13", "category": "started"},
        {"name": "Done",        "color": "#1F7A1F", "category": "completed"},
        {"name": "Cancelled",   "color": "#C41C1C", "category": "cancelled"},
    ],
    "site-management": [
        {"name": "Planned",   "color": "#9FA6AD", "category": "unstarted"},
        {"name": "Active",    "color": "#0B6BCB", "category": "started"},
        {"name": "Inspected", "color": "#9A5B13", "category": "started"},
        {"name": "Approved",  "color": "#1F7A1F", "category": "completed"},
        {"name": "Closed",    "color": "#636B74", "category": "completed"},
    ],
    "rfi-tracking": [
        {"name": "Open",              "color": "#9FA6AD", "category": "unstarted"},
        {"name": "Awaiting Response", "color": "#0B6BCB", "category": "started"},
        {"name": "Resolved",          "color": "#1F7A1F", "category": "completed"},
        {"name": "Cancelled",         "color": "#C41C1C", "category": "cancelled"},
    ],
    "recurring-ops": [
        {"name": "To Do", "color": "#9FA6AD", "category": "unstarted"},
        {"name": "In Progress", "color": "#0B6BCB", "category": "started"},
        {"name": "Done",  "color": "#1F7A1F", "category": "completed"},
    ],
    "asset-tracking": [
        {"name": "Active",            "color": "#0B6BCB", "category": "started"},
        {"name": "Under Maintenance", "color": "#9A5B13", "category": "started"},
        {"name": "Decommissioned",    "color": "#636B74", "category": "cancelled"},
    ],
    "simple": [
        {"name": "To Do", "color": "#9FA6AD", "category": "unstarted"},
        {"name": "In Progress", "color": "#0B6BCB", "category": "started"},
        {"name": "Done",  "color": "#1F7A1F", "category": "completed"},
    ],
}

# ─── Template registry ────────────────────────────────────────────────
# 'board', 'list' and 'gantt' are universal (Pricing promises Board+List+
# Gantt on the free tier — per-template gantt gating contradicted that and
# made users hunt for the tab). Agile templates additionally get a backlog.
# 'notes' and 'draw' are universal too — shared team
# surfaces, not something any one template should opt out of. Both also carry
# their own gates on top of this membership: 'draw' is Team+ tier as well.

TEMPLATE_CATEGORIES = ["Software", "Services", "Construction", "Operations", "General"]

PROJECT_TEMPLATES = [
    {"id": "blank", "label": "Blank", "category": None, "icon": "FilePlus",
     "description": "Start from scratch with no presets.",
     "default_project_type": "internal", "issue_types": ["Task"],
     "views": ["board", "list", "backlog", "gantt", "notes", "draw"]},

    {"id": "kanban", "label": "Kanban", "category": "Software", "icon": "LayoutGrid",
     "description": "Continuous flow for engineering teams.",
     "default_project_type": "internal", "issue_types": ["Task", "Bug", "Story"],
     "views": ["board", "list", "backlog", "gantt", "notes", "draw"]},

    {"id": "scrum", "label": "Scrum", "category": "Software", "icon": "Repeat",
     "description": "Sprint-based delivery with backlog.",
     "default_project_type": "internal", "issue_types": ["Task", "Bug", "Story", "Epic"],
     "views": ["board", "backlog", "list", "gantt", "notes", "draw"]},

    {"id": "bug-tracking", "label": "Bug tracking", "category": "Software", "icon": "Bug",
     "description": "Triage, fix, and close defects fast.",
     "default_project_type": "internal", "issue_types": ["Bug", "Task", "Sub-task"],
     "views": ["board", "list", "backlog", "gantt", "notes", "draw"]},

    {"id": "client-delivery", "label": "Client delivery", "category": "Services", "icon": "Briefcase",
     "description": "Scoping through invoicing.",
     "default_project_type": "tm", "issue_types": ["Task", "Deliverable", "Milestone"],
     "views": ["board", "list", "backlog", "gantt", "notes", "draw"]},

    {"id": "retainer", "label": "Retainer", "category": "Services", "icon": "RefreshCw",
     "description": "Monthly recurring engagements.",
     "default_project_type": "retainer", "issue_types": ["Task", "Request", "Revision"],
     "views": ["board", "list", "backlog", "gantt", "notes", "draw"]},

    {"id": "site-management", "label": "Site management", "category": "Construction", "icon": "HardHat",
     "description": "Phases, inspections, approvals.",
     "default_project_type": "internal", "issue_types": ["Task", "RFI", "Submittal", "Inspection", "Milestone"],
     "views": ["board", "list", "backlog", "gantt", "notes", "draw"]},

    {"id": "rfi-tracking", "label": "RFI tracking", "category": "Construction", "icon": "HelpCircle",
     "description": "Request for information workflow.",
     "default_project_type": "internal", "issue_types": ["RFI", "Submittal", "Sub-task"],
     "views": ["board", "list", "backlog", "gantt", "notes", "draw"]},

    {"id": "recurring-ops", "label": "Recurring ops", "category": "Operations", "icon": "Calendar",
     "description": "Repeating operational tasks.",
     "default_project_type": "internal", "issue_types": ["Task", "Work Order", "Maintenance"],
     "views": ["board", "list", "backlog", "gantt", "notes", "draw"]},

    {"id": "asset-tracking", "label": "Asset tracking", "category": "Operations", "icon": "Package",
     "description": "Track assets by ID, serial, location.",
     "default_project_type": "internal", "issue_types": ["Task", "Work Order", "Incident"],
     "views": ["list", "board", "notes", "draw"]},

    {"id": "simple", "label": "Simple", "category": "General", "icon": "CircleDashed",
     "description": "Three states, one task type.",
     "default_project_type": "internal", "issue_types": ["Task"],
     "views": ["board", "list", "backlog", "gantt", "notes", "draw"]},
]

# Universal fallback when a project has no template / an unknown one.
DEFAULT_TEMPLATE_ID = "simple"
DEFAULT_VIEWS = ["board", "list", "backlog", "gantt", "notes", "draw"]

STATUS_COLOR_PALETTE = [
    "#9FA6AD", "#636B74", "#0B6BCB", "#4393E4", "#7C3AED",
    "#9A5B13", "#C41C1C", "#1F7A1F", "#0E6B93", "#BE185D",
]

CATEGORY_STYLES = {
    "unstarted": {"bg": "#F0F4F8", "color": "#636B74", "label": "Unstarted"},
    "started":   {"bg": "#E3EFFB", "color": "#0B6BCB", "label": "Started"},
    "completed": {"bg": "#E3FBE3", "color": "#1F7A1F", "label": "Completed"},
    "cancelled": {"bg": "#FCE4E4", "color": "#C41C1C", "label": "Cancelled"},
}

_TEMPLATES_BY_ID = {t["id"]: t for t in PROJECT_TEMPLATES}


# ─── Helpers ──────────────────────────────────────────────────────────

def expand_issue_types(names):
    """Turn a list of issue-type names into full objects from the catalog."""
    out = []
    for name in names or []:
        meta = ISSUE_TYPE_CATALOG.get(name, {})
        out.append({
            "name": name,
            "color": meta.get("color", "#0B6BCB"),
            "icon": meta.get("icon", "CheckSquare"),
        })
    return out


def expand_template(template_id):
    """Return a fully-resolved template (states, issue type objects, views).

    Falls back to the default template for unknown / missing ids so callers
    always get a usable shape.
    """
    tpl = _TEMPLATES_BY_ID.get(template_id) or _TEMPLATES_BY_ID[DEFAULT_TEMPLATE_ID]
    pool = ISSUE_TYPE_POOLS.get(tpl.get("category") or "General", ISSUE_TYPE_POOLS["General"])
    return {
        "id": tpl["id"],
        "label": tpl["label"],
        "category": tpl["category"],
        "icon": tpl["icon"],
        "description": tpl["description"],
        "default_project_type": tpl.get("default_project_type", "internal"),
        "workflow_states": WORKFLOW_PRESETS.get(tpl["id"], WORKFLOW_PRESETS["simple"]),
        "issue_types": expand_issue_types(tpl.get("issue_types", ["Task"])),
        "issue_type_pool": list(pool),
        "views": tpl.get("views", list(DEFAULT_VIEWS)),
    }


def get_template_views(template_id):
    """Views a template exposes, with a safe fallback."""
    tpl = _TEMPLATES_BY_ID.get(template_id)
    return list(tpl["views"]) if tpl else list(DEFAULT_VIEWS)


def get_all_templates():
    """Every template, fully expanded — the payload the create flow needs."""
    return [expand_template(t["id"]) for t in PROJECT_TEMPLATES]


@frappe.whitelist()
def get_project_templates():
    """Single source the frontend reads so client/server can never drift."""
    return {
        "templates": get_all_templates(),
        "categories": TEMPLATE_CATEGORIES,
        "issue_type_catalog": ISSUE_TYPE_CATALOG,
        "issue_type_pools": ISSUE_TYPE_POOLS,
        "status_palette": STATUS_COLOR_PALETTE,
        "category_styles": CATEGORY_STYLES,
    }
