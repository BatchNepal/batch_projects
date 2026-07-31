import frappe
import json

DEFAULT_STATES = [
    {"name": "To Do",       "color": "#94a3b8", "category": "unstarted"},
    {"name": "In Progress", "color": "#3b82f6", "category": "started"},
    {"name": "Review",      "color": "#f59e0b", "category": "started"},
    {"name": "Done",        "color": "#22c55e", "category": "completed"},
]

DEFAULT_TYPES = [
    {"name": "Task",  "color": "#3b82f6", "icon": "check-square"},
    {"name": "Bug",   "color": "#ef4444", "icon": "bug"},
    {"name": "Story", "color": "#8b5cf6", "icon": "book-open"},
]

def execute():
    projects = frappe.get_all("BP Project", fields=["name", "board_columns", "workflow_states", "issue_types"])
    for p in projects:
        updates = {}
        if not p.get("workflow_states"):
            if p.get("board_columns"):
                try:
                    old_cols = json.loads(p["board_columns"]) if isinstance(p["board_columns"], str) else p["board_columns"]
                    states = []
                    for col in old_cols:
                        cat = "unstarted"
                        if col.lower() in ("done", "completed", "closed", "delivered", "invoiced"): cat = "completed"
                        elif col.lower() in ("cancelled", "rejected"): cat = "cancelled"
                        elif col.lower() in ("in progress", "in review", "review", "doing"): cat = "started"
                        states.append({"name": col, "color": _cat_color(cat), "category": cat})
                    updates["workflow_states"] = json.dumps(states)
                except Exception:
                    updates["workflow_states"] = json.dumps(DEFAULT_STATES)
            else:
                updates["workflow_states"] = json.dumps(DEFAULT_STATES)
        if not p.get("issue_types"):
            updates["issue_types"] = json.dumps(DEFAULT_TYPES)
        if updates:
            frappe.db.set_value("BP Project", p["name"], updates)
            print(f"  Migrated: {p['name']}")
    frappe.db.commit()

def _cat_color(cat):
    return {"unstarted": "#94a3b8", "started": "#3b82f6", "completed": "#22c55e", "cancelled": "#ef4444"}.get(cat, "#94a3b8")