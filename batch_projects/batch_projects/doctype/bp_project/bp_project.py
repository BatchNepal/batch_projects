import frappe
import json
from frappe.model.document import Document

from batch_projects.setup.project_templates import (
    WORKFLOW_PRESETS,
    expand_issue_types,
    expand_template,
)

# ─── Backward-compat exports ──────────────────────────────
# These names are imported by api/board.py:get_workflow_templates(). They now
# resolve to the single registry in setup/project_templates.py, so the client
# and server template definitions can never drift apart again.
WORKFLOW_TEMPLATES = WORKFLOW_PRESETS
DEFAULT_ISSUE_TYPES = expand_issue_types(["Task", "Bug", "Story", "Epic", "Milestone"])
DEFAULT_STATES = WORKFLOW_PRESETS["simple"]


class BPProject(Document):
    def before_insert(self):
        # Resolve the chosen template once; unknown/missing falls back to default.
        tpl = expand_template(self.template_used)

        if not self.workflow_states:
            self.workflow_states = json.dumps(tpl["workflow_states"])

        if not self.issue_types:
            self.issue_types = json.dumps(tpl["issue_types"])

        if not self.custom_fields:
            self.custom_fields = json.dumps([])

        # Views the project exposes follow the template (board/list/gantt/…).
        if not getattr(self, "enabled_views", None):
            self.enabled_views = json.dumps(tpl["views"])

        if not self.issue_counter:
            self.issue_counter = 0

    def validate(self):
        if self.key:
            self.key = self.key.upper().strip()
            if len(self.key) > 6:
                frappe.throw("Project key must be 6 characters or less")

        # Ensure JSON-config fields hold valid JSON of the expected shape
        self._validate_json_field("workflow_states", list)
        self._validate_json_field("issue_types", list)
        self._validate_json_field("custom_fields", list)
        self._validate_json_field("enabled_views", list)

    def _validate_json_field(self, fieldname, expected_type):
        val = getattr(self, fieldname, None)
        if not val:
            return
        # Deep-parse handles single or double encoding
        parsed = val
        for _ in range(4):
            if not isinstance(parsed, str):
                break
            try:
                parsed = json.loads(parsed)
            except Exception:
                frappe.throw(f"{fieldname} contains invalid JSON")
                return
        if not isinstance(parsed, expected_type):
            frappe.throw(f"{fieldname} must be a JSON {expected_type.__name__}")

    def get_next_issue_number(self):
        """Atomically increment and return the counter reserved for this connection.
        LAST_INSERT_ID(expr) stores the value in a connection-local variable so
        concurrent requests each read back their own increment, not a shared read.
        MariaDB/MySQL only — use a SEQUENCE on Postgres."""
        frappe.db.sql(
            "UPDATE `tabBP Project` SET issue_counter = LAST_INSERT_ID(issue_counter + 1) WHERE name = %s",
            self.name,
        )
        return frappe.db.sql("SELECT LAST_INSERT_ID()")[0][0]

    def get_workflow_states(self):
        raw = self.workflow_states
        if not raw:
            return DEFAULT_STATES
        # Deep-parse: handles single, double, or triple JSON encoding
        val = raw
        for _ in range(6):
            if not isinstance(val, str):
                break
            try:
                val = json.loads(val)
            except Exception:
                break
        if not isinstance(val, list):
            return DEFAULT_STATES
        # Normalize each state
        DEFAULT_COLORS = ["#8993A4", "#0052CC", "#36B37E", "#FF5630", "#FFAB00", "#6554C0"]
        result = []
        for i, s in enumerate(val):
            # Each element may itself be encoded
            if isinstance(s, str):
                try:
                    s = json.loads(s)
                except Exception:
                    continue
            if not isinstance(s, dict) or not s.get("name"):
                continue
            s.setdefault("color", DEFAULT_COLORS[i % len(DEFAULT_COLORS)])
            s.setdefault("category", "unstarted")
            result.append(s)
        return result if result else DEFAULT_STATES

    def get_issue_types(self):
        raw = self.issue_types
        if not raw:
            return DEFAULT_ISSUE_TYPES
        parsed = json.loads(raw) if isinstance(raw, str) else raw
        return parsed

    def get_enabled_views(self):
        raw = getattr(self, "enabled_views", None)
        fallback = expand_template(self.template_used)["views"]
        if not raw:
            return fallback
        parsed = json.loads(raw) if isinstance(raw, str) else raw
        return parsed if isinstance(parsed, list) and parsed else fallback

    def get_pinned_views(self):
        """Ordered view keys pinned inline in the header tab strip. None means
        the frontend applies its own default split (summary/board/list/gantt
        pinned, the rest — e.g. files/money — behind the overflow drawer)."""
        raw = getattr(self, "pinned_views", None)
        if not raw:
            return None
        parsed = json.loads(raw) if isinstance(raw, str) else raw
        return parsed if isinstance(parsed, list) and parsed else None

    def get_custom_fields_schema(self):
        raw = self.custom_fields
        if not raw:
            return []
        parsed = json.loads(raw) if isinstance(raw, str) else raw
        return parsed

    def get_status_names(self):
        return [s["name"] for s in self.get_workflow_states()]

    def get_completed_statuses(self):
        return [s["name"] for s in self.get_workflow_states() if s.get("category") == "completed"]

    def get_started_statuses(self):
        return [s["name"] for s in self.get_workflow_states() if s.get("category") == "started"]

    def check_transition(self, from_status, to_status, user=None):
        """Validate from_status -> to_status against this project's workflow
        graph. Returns None if the move is allowed, else a human-readable
        error string. Each `allowed_to` entry on a state is either a plain
        status name (reachable, no extra role requirement) or
        {"name": ..., "min_role": "Manager"|"Admin"} (reachable only for
        that role or higher, on top of the normal edit permission floor).
        Absent `allowed_to` means unrestricted — the default for every
        state unless an admin opts in via the workflow editor."""
        for s in self.get_workflow_states():
            if s["name"] != from_status:
                continue
            allowed = s.get("allowed_to")
            if not isinstance(allowed, list):
                return None  # unrestricted
            for entry in allowed:
                name = entry.get("name") if isinstance(entry, dict) else entry
                if name != to_status:
                    continue
                min_role = entry.get("min_role") if isinstance(entry, dict) else None
                if min_role:
                    from batch_projects import access
                    if not access.has_at_least(self.name, min_role, user):
                        return (
                            f"You need at least {access.normalize_role(min_role)} access "
                            f"to move '{from_status}' to '{to_status}'."
                        )
                return None  # reachable, role satisfied (or none required)
            return (
                f"'{from_status}' can't move directly to '{to_status}' — "
                f"this transition isn't allowed by this project's workflow."
            )
        return None  # from_status not found in the workflow — fail open

    # ── Industry-agnostic terminology (Sprint/Agile) ───────────────────────

    def cycle_label(self) -> str:
        """What this project calls a time-boxed work cycle. Falls back to 'Sprint'."""
        return (getattr(self, "cycle_label", None) or "").strip() or "Sprint"

    def effort_label(self) -> str:
        """What unit this project estimates effort in. Falls back to 'Story Points'."""
        return (getattr(self, "effort_label", None) or "").strip() or "Story Points"

    def cycle_label_plural(self) -> str:
        return self.cycle_label() + "s"

    def effort_label_abbr(self) -> str:
        """Short form for chart axes. 'pts' for Story Points, 'hrs' for Hours, etc."""
        label = self.effort_label().lower()
        if "point" in label: return "pts"
        if "hour" in label:  return "hrs"
        if "unit" in label:  return "units"
        if "day" in label:   return "days"
        if "batch" in label: return "batch"
        return label[:4]
