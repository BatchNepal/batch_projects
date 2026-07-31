import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime
import json

# ─── RECURRENCE ────────────────────────────────────────────────────────────
_RECURRENCE_INTERVAL_SECONDS = {
    "Daily": 86400,
    "Weekly": 604800,
    "Biweekly": 1209600,
    "Monthly": 2592000,  # 30-day approximation
}


class BPTask(Document):

    def before_insert(self):
        # Auto-generate issue key
        project = None
        if not self.task_key:
            project = frappe.get_doc("BP Project", self.project)
            counter = project.get_next_issue_number()
            self.task_key = f"{project.key}-{counter}"

        # Auto-set reporter
        if not self.reporter:
            emp = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
            if emp:
                self.reporter = emp

        # Triage inbox opt-in — mark for triage only when the
        # project has triage_enabled AND no explicit status was given.
        if not self.status:
            if project is None:
                project = frappe.get_doc("BP Project", self.project)
            if project.get("triage_enabled"):
                self.needs_triage = 1

        # Default status to first workflow state (task still gets a workflow
        # column even when triaged — the Triage inbox is an overlay, not a
        # status replacement).
        if not self.status:
            if project is None:
                project = frappe.get_doc("BP Project", self.project)
            states = project.get_workflow_states()
            if states:
                self.status = states[0]["name"]

        # Default task_type
        if not self.task_type:
            self.task_type = "Task"

        # Manual-ordering key: append to the end of its column
        if not self.board_rank:
            from batch_projects.rank import end_rank
            self.board_rank = end_rank(self.project, self.status)

        # Seed custom_field_values with defaults from schema. The field
        # library (BP Custom Field) doesn't carry a `default` — this is now
        # effectively a no-op preserved for any stray pre-migration schema
        # blobs that still had one; harmless either way.
        if not self.custom_field_values:
            from batch_projects.api.custom_fields import validation_schema_for_project
            schema = validation_schema_for_project(self.project, "tasks")
            defaults = {}
            for field in schema:
                if field.get("default") is not None:
                    defaults[field["id"]] = field["default"]
            if defaults:
                self.custom_field_values = json.dumps(defaults)

    def validate(self):
        self._validate_status()
        self._validate_task_type()
        self._set_lifecycle_dates()
        self._validate_and_clean_custom_fields()
        self._validate_recurrence()
        self._flag_unplanned_if_active_sprint()

    # ─── UNPLANNED (sprint column catalog) ──────────────────────────────────

    def _flag_unplanned_if_active_sprint(self):
        """Auto-check Unplanned the moment a task is assigned into a sprint
        that's already Active — mid-sprint scope creep, the thing the column
        exists to surface. Stays a plain Check afterward: the user can
        un-flag it (e.g. it was actually agreed at planning) same as Monday's
        column is a manual toggle, this just seeds the common case instead of
        starting everything unchecked."""
        if not self.sprint:
            return
        old = self.get_doc_before_save()
        sprint_changed = (not old) or (old.sprint or None) != self.sprint
        if not sprint_changed:
            return
        status = frappe.db.get_value("BP Sprint", self.sprint, "status")
        if status == "Active":
            self.is_unplanned = 1

    # ─── STATUS ──────────────────────────────────────────────────────────────

    def _validate_status(self):
        if not self.status:
            return
        # Only validate when status is actually being changed.
        # If status wasn't touched (e.g. saving task_type, custom fields),
        # skip validation — the existing value may predate a workflow rename.
        old = self.get_doc_before_save()
        if old and old.status == self.status:
            return  # not changing — skip
        project = frappe.get_doc("BP Project", self.project)
        valid = project.get_status_names()
        if valid and self.status not in valid:
            frappe.throw(
                f"Status '{self.status}' is not a valid workflow state for this project. "
                f"Valid states: {', '.join(valid)}."
            )
        # Transition-graph enforcement (opt-in per status, see check_transition) —
        # only applies when actually moving from one existing status to another, never
        # on creation, and bypassable via flags for system-initiated changes (automation).
        if old and old.status and not self.flags.get("ignore_transition_check"):
            err = project.check_transition(old.status, self.status)
            if err:
                frappe.throw(err)

    # ─── TASK TYPE ──────────────────────────────────────────────────────────

    def _validate_task_type(self):
        if not self.task_type:
            return
        project = frappe.get_doc("BP Project", self.project)
        valid = [t["name"] for t in project.get_issue_types()]
        if valid and self.task_type not in valid:
            frappe.msgprint(
                f"Issue type '{self.task_type}' is not defined in project settings.",
                alert=True,
            )

    # ─── LIFECYCLE DATES ─────────────────────────────────────────────────────

    def _set_lifecycle_dates(self):
        old = self.get_doc_before_save()
        if not old:
            return

        project = frappe.get_doc("BP Project", self.project)

        if old.status != self.status:
            started = project.get_started_statuses()
            completed = project.get_completed_statuses()

            if self.status in started and not self.started_on:
                self.started_on = now_datetime()

            if self.status in completed and not self.completed_on:
                self.completed_on = now_datetime()

            # Resolution mirrors completion: default to "Done" when entering a
            # completed status, clear it when reopened. An explicit resolution
            # (e.g. "Won't Do") set on the same save is respected.
            if self.status in completed and not self.resolution:
                self.resolution = "Done"

            if self.status not in completed:
                self.completed_on = None
                self.resolution = None

    # ─── CUSTOM FIELDS ───────────────────────────────────────────────────────

    def _validate_and_clean_custom_fields(self):
        """
        1. Parse custom_field_values
        2. Remove orphaned keys (fields deleted from schema)
        3. Validate each value against its field schema
        """
        if not self.custom_field_values:
            return

        from batch_projects.api.custom_fields import validation_schema_for_project
        schema = validation_schema_for_project(self.project, "tasks")

        # Step 1: orphan cleanup
        active_ids = {f["id"] for f in schema if not f.get("archived")}
        values = _parse_json(self.custom_field_values, {})
        cleaned = {k: v for k, v in values.items() if k in active_ids}
        if len(cleaned) != len(values):
            self.custom_field_values = json.dumps(cleaned)
            values = cleaned

        # Step 2: validate
        _validate_custom_field_values(values, schema)

    # ─── ACTIVITY LOGGING ────────────────────────────────────────────────────

    def after_insert(self):
        self._log_activity("Created", None, self.status)
 
        # Emit event
        from batch_projects.events import emit, TASK_CREATED
        emit(TASK_CREATED, {
            "project": self.project,
            "task": self.name,
            "task_key": self.task_key,
            "title": self.title,
            "status": self.status,
            "changes": [],
        })

    def on_update(self):
        self._sync_recurrence()
        old = self.get_doc_before_save()
        if not old:
            return

        from batch_projects.events import (
            emit, build_changes, build_custom_field_changes,
            TASK_UPDATED, TASK_STATUS_CHANGED, TASK_ASSIGNED, TASK_UNASSIGNED
        )

        all_changes = []

        # Status
        if old.status != self.status:
            self._log_activity("Status Change", old.status, self.status)
            all_changes.append({"field": "status", "from": old.status, "to": self.status})
            emit(TASK_STATUS_CHANGED, {
                "project": self.project,
                "task": self.name,
                "task_key": self.task_key,
                "from_status": old.status,
                "to_status": self.status,
            })

        # Priority
        if old.priority != self.priority:
            self._log_activity("Field Edit", old.priority, self.priority, field_name="priority")
            all_changes.append({"field": "priority", "from": old.priority, "to": self.priority})

        # Resolution
        if (old.resolution or "") != (self.resolution or ""):
            self._log_activity("Field Edit", old.resolution, self.resolution, field_name="resolution")
            all_changes.append({"field": "resolution", "from": old.resolution, "to": self.resolution})

        # Issue type
        if old.task_type != self.task_type:
            self._log_activity("Field Edit", old.task_type, self.task_type, field_name="task_type")
            all_changes.append({"field": "task_type", "from": old.task_type, "to": self.task_type})

        # Title
        if old.title != self.title:
            self._log_activity("Field Edit", old.title, self.title, field_name="title")
            all_changes.append({"field": "title", "from": old.title, "to": self.title})

        # Due date
        if str(old.due_date or "") != str(self.due_date or ""):
            self._log_activity("Field Edit", old.due_date, self.due_date, field_name="due_date")
            all_changes.append({"field": "due_date", "from": str(old.due_date or ""), "to": str(self.due_date or "")})

        # Start date
        if str(old.start_date or "") != str(self.start_date or ""):
            self._log_activity("Field Edit", old.start_date, self.start_date, field_name="start_date")
            all_changes.append({"field": "start_date", "from": str(old.start_date or ""), "to": str(self.start_date or "")})

        # Story points
        if old.story_points != self.story_points:
            self._log_activity("Field Edit", old.story_points, self.story_points, field_name="story_points")
            all_changes.append({"field": "story_points", "from": old.story_points, "to": self.story_points})

        # Sprint (the task.moved_sprint automation trigger reads this)
        if (old.sprint or None) != (self.sprint or None):
            self._log_activity("Field Edit", old.sprint, self.sprint, field_name="sprint")
            all_changes.append({"field": "sprint", "from": old.sprint, "to": self.sprint})

        # Description — don't include content in payload (too large for socket)
        # Frontend detects this field and re-fetches the full issue
        if (old.description or "") != (self.description or ""):
            self._log_activity("Field Edit", "", "", field_name="description")
            all_changes.append({"field": "description", "from": None, "to": None})

        # Labels
        old_labels = _parse_json(old.labels, [])
        new_labels = _parse_json(self.labels, [])
        if old_labels != new_labels:
            self._log_activity(
                "Field Edit",
                ", ".join(old_labels) if isinstance(old_labels, list) else "",
                ", ".join(new_labels) if isinstance(new_labels, list) else "",
                field_name="labels",
            )
            all_changes.append({"field": "labels", "from": old_labels, "to": new_labels})

        # Assignees
        old_assignees = set(r.user for r in (old.assignees or []))
        new_assignees = set(r.user for r in (self.assignees or []))

        for usr in (new_assignees - old_assignees):
            full_name = frappe.db.get_value("User", usr, "full_name") or usr
            self._log_activity("Assignment", "", full_name)
            emit(TASK_ASSIGNED, {
                "project": self.project,
                "task": self.name,
                "task_key": self.task_key,
                # key is "assignee" (not "user") so the notification layer resolves
                # the actor as the session user, not the person being assigned
                "assignee": usr,
                "full_name": full_name,
            })

        for usr in (old_assignees - new_assignees):
            full_name = frappe.db.get_value("User", usr, "full_name") or usr
            self._log_activity("Assignment", full_name, "")
            emit(TASK_UNASSIGNED, {
                "project": self.project,
                "task": self.name,
                "task_key": self.task_key,
                "assignee": usr,
                "full_name": full_name,
            })

        # Custom field changes
        old_cfv = _parse_json(old.custom_field_values, {})
        new_cfv = _parse_json(self.custom_field_values, {})
        cf_changes = build_custom_field_changes(old_cfv, new_cfv)

        for change in cf_changes:
            self._log_activity(
                "Field Edit",
                _serialize_cf_value(change['from']),
                _serialize_cf_value(change['to']),
                field_name=change['field'],
            )
            all_changes.append(change)

        # Emit single issue.updated with all changes
        if all_changes:
            emit(TASK_UPDATED, {
                "project": self.project,
                "task": self.name,
                "task_key": self.task_key,
                "title": self.title,
                "parent_task": self.parent_task or None,
                "changes": all_changes,
            })


    # ─── RECURRENCE VALIDATION ──────────────────────────────────
    def _validate_recurrence(self):
        if self.is_recurring and not self.recurrence_frequency:
            frappe.throw("Recurring tasks require a Repeat Frequency.")

    def on_trash(self):
        if self.bridge_job_id:
            from batch_projects import bridge
            bridge.cancel_scheduled_job(self.bridge_job_id)

    def _sync_recurrence(self):
        from batch_projects import bridge
        from frappe.utils import getdate, nowdate

        # Always cancel+clear first (idempotent — covers edits, frequency changes, deactivation)
        if self.bridge_job_id:
            bridge.cancel_scheduled_job(self.bridge_job_id)
            self.db_set("bridge_job_id", None, update_modified=False)

        if not self.is_recurring:
            return

        # If end date has already passed, do not register
        if self.recurrence_end_date and getdate(self.recurrence_end_date) < getdate(nowdate()):
            return

        interval = _RECURRENCE_INTERVAL_SECONDS.get(self.recurrence_frequency)
        if not interval:
            return

        job_id = bridge.register_scheduled_job(
            kind="task.recurring",
            event="task.recurring",
            payload={"task": self.name, "project": self.project},
            delay_seconds=interval,
            interval_seconds=interval,
        )
        if job_id:
            self.db_set("bridge_job_id", job_id, update_modified=False)
        elif bridge.is_configured():
            frappe.msgprint(
                "Could not register recurrence with the automation agent. It will not fire until re-saved.",
                indicator="orange", alert=True,
            )

    def _log_activity(self, action_type, old_value, new_value, field_name=None):
        frappe.get_doc({
            "doctype": "BP Activity",
            "task": self.name,
            "project": self.project,
            "task_key": self.task_key,
            "action_type": action_type,
            "field_name": field_name or "",
            "old_value": str(old_value) if old_value is not None else "",
            "new_value": str(new_value) if new_value is not None else "",
            "user": frappe.session.user,
        }).insert(ignore_permissions=True)


# ─── VALIDATORS ──────────────────────────────────────────────────────────────

def _validate_custom_field_values(values: dict, schema: list):
    """
    Backend validation for custom field values.
    Called from BPTask.validate() and from board.py create/update endpoints.
    """
    import re

    errors = []
    schema_map = {f["id"]: f for f in schema if not f.get("archived")}

    for field_id, value in values.items():
        if field_id not in schema_map:
            continue  # orphan — already cleaned before this runs

        field = schema_map[field_id]
        ftype = field["type"]
        label = field["label"]

        # Required check
        is_empty = value is None or value == "" or value == []
        if field.get("required") and is_empty:
            errors.append(f"'{label}' is required.")
            continue

        if is_empty:
            continue  # optional + empty = fine, skip type checks

        # Type-specific validation
        if ftype in ("text", "textarea"):
            if not isinstance(value, str):
                errors.append(f"'{label}' must be text.")
            elif len(value) > 2000:
                errors.append(f"'{label}' must be 2000 characters or less.")

        elif ftype == "number":
            if not isinstance(value, (int, float)):
                errors.append(f"'{label}' must be a number.")
            else:
                if field.get("min") is not None and value < field["min"]:
                    errors.append(f"'{label}' must be at least {field['min']}.")
                if field.get("max") is not None and value > field["max"]:
                    errors.append(f"'{label}' must be at most {field['max']}.")

        elif ftype == "date":
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(value)):
                errors.append(f"'{label}' must be a date in YYYY-MM-DD format.")

        elif ftype == "select":
            valid_ids = {o["id"] for o in field.get("options", [])}
            if value not in valid_ids:
                errors.append(f"'{value}' is not a valid option for '{label}'.")

        elif ftype == "multiselect":
            if not isinstance(value, list):
                errors.append(f"'{label}' must be a list.")
            else:
                valid_ids = {o["id"] for o in field.get("options", [])}
                for v in value:
                    if v not in valid_ids:
                        errors.append(f"'{v}' is not a valid option for '{label}'.")

        elif ftype == "checkbox":
            if not isinstance(value, bool):
                errors.append(f"'{label}' must be true or false.")

        elif ftype == "user":
            if not frappe.db.exists("Employee", value):
                errors.append(f"Employee '{value}' not found for '{label}'.")

        elif ftype == "url":
            if not isinstance(value, str):
                errors.append(f"'{label}' must be a URL string.")

        elif ftype == "currency":
            if not isinstance(value, (int, float)):
                errors.append(f"'{label}' must be a number.")

        elif ftype == "percent":
            if not isinstance(value, (int, float)):
                errors.append(f"'{label}' must be a number.")
            elif value < 0 or value > 100:
                errors.append(f"'{label}' must be between 0 and 100.")

        elif ftype == "rating":
            if not isinstance(value, (int, float)):
                errors.append(f"'{label}' must be a number.")
            elif value < 1 or value > 5:
                errors.append(f"'{label}' must be between 1 and 5.")

        elif ftype == "email":
            if not isinstance(value, str) or not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", value):
                errors.append(f"'{label}' must be a valid email address.")

        elif ftype == "phone":
            if not isinstance(value, str):
                errors.append(f"'{label}' must be a phone number.")

        elif ftype == "link":
            if not isinstance(value, dict) or not value.get("name"):
                errors.append(f"'{label}' must be a linked record.")
            elif not field.get("link_doctype"):
                # Guard before frappe.db.exists — a link field saved with no
                # link_doctype configured would otherwise throw a raw
                # frappe.db.exists(None, ...) TypeError instead of a clean
                # message.
                errors.append(f"'{label}' has no linked document type configured.")
            elif not frappe.db.exists(field["link_doctype"], value["name"]):
                errors.append(f"'{label}' points at a record that no longer exists.")
            # NOTE: frappe.db.exists is permission-blind — it answers "does
            # this row exist," not "can this user see it." Anyone with
            # edit_role on this field can learn whether a given record name
            # exists even without read access to it (search_field_link_options
            # is the permission-aware path; this is just an existence check).
            # Accepted v1 tradeoff: the alternative (skip existence
            # validation) lets stale/bogus references persist silently,
            # which is worse.

    if errors:
        frappe.throw("<br>".join(errors), title="Custom Field Validation")


def _serialize_cf_value(value):
    """Serialize a custom field value for activity log storage."""
    if value is None:
        return ""
    if isinstance(value, list):
        return ",".join(str(v) for v in value)
    return str(value)


def _parse_json(value, default):
    if not value:
        return default
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default
# ─── RECURRENCE SPAWN ─────────────────────────────────────────────────────────

def spawn_recurring_occurrence(task_name):
    """Called by the bridge scheduler when a task.recurring job fires.
    Creates one new sibling occurrence of the template task.
    Returns (status, message) tuple.
    """
    from batch_projects import bridge
    from frappe.utils import getdate, nowdate, add_to_date

    if not frappe.db.exists("BP Task", task_name):
        return ("Skipped", "template task no longer exists")

    template = frappe.get_doc("BP Task", task_name)

    if not template.is_recurring:
        return ("Skipped", "recurrence turned off")

    # Fire-time end-date check — the real termination point
    if template.recurrence_end_date:
        if getdate(nowdate()) > getdate(template.recurrence_end_date):
            try:
                if template.bridge_job_id:
                    bridge.cancel_scheduled_job(template.bridge_job_id)
            except Exception:
                pass
            frappe.db.set_value("BP Task", task_name, "is_recurring", 0, update_modified=False)
            frappe.db.set_value("BP Task", task_name, "bridge_job_id", None, update_modified=False)
            return ("Skipped", "recurrence end date passed")

    interval = _RECURRENCE_INTERVAL_SECONDS.get(template.recurrence_frequency or "", 86400)

    # Build the new occurrence
    doc = frappe.get_doc({
        "doctype": "BP Task",
        "project": template.project,
        "title": template.title,
        "priority": template.priority,
        "task_type": template.task_type,
        "epic": template.epic,
        "description": template.description,
        "estimated_hours": template.estimated_hours,
        "billable": template.billable,
        "labels": template.labels,
        "custom_field_values": template.custom_field_values,
        "recurrence_source": template.name,
    })

    # Shift due_date if template has one
    if template.due_date:
        days = interval // 86400
        doc.due_date = add_to_date(template.due_date, days=days)

    # Rebuild assignees
    if template.assignees:
        doc.assignees = []
        for a in template.assignees:
            doc.append("assignees", {"user": a.user, "full_name": a.full_name})

    doc.insert(ignore_permissions=True)

    from batch_projects import cache
    cache.invalidate_project(template.project)

    return ("Success", f"spawned {doc.name}")
