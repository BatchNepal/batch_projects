"""
batch_projects/analytics.py
────────────────────────────
Stateless analytics engine for sprint/agile metrics.

Every function here is a PURE computation: it takes a project/sprint id, queries
the DB, and returns a clean dict ready for JSON serialisation. No side effects,
no doc saves, no cache writes. The cache layer (events.emit → cache invalidation)
and the API layer (api/sprint_analytics.py) sit above this.

Design principles for cross-industry use:
  • "Story Points" are just "effort units" — manufacturing uses batch counts,
    consulting uses billable days, agencies use story points. The engine works
    identically regardless.
  • Every metric supports both "count of tasks" AND "sum of effort units" modes
    so a team that doesn't use points still gets value.
  • No opinionated agile labels — the data is neutral; interpretation (scrum,
    kanban, lean, Gantt-pm) belongs in the UI layer.
"""

import frappe
from frappe.utils import getdate, today, add_days, date_diff
from datetime import timedelta


# ─────────────────────────────────────────────────────────────────────────────
# BURNDOWN — classic sprint remaining-work chart
# ─────────────────────────────────────────────────────────────────────────────

def compute_burndown(sprint: str) -> dict:
    """Return the day-by-day burndown data for a sprint.

    Returns:
      {
        "sprint": str,
        "sprint_name": str, ...
        "cycle_label": str,          # e.g. "Sprint" or "Production Run"
        "effort_label": str,         # e.g. "Story Points" or "Units"
        "effort_label_abbr": str,    # e.g. "pts" or "units"
      }
    """
    sprint_doc = frappe.get_doc("BP Sprint", sprint)
    labels = _get_project_labels(sprint_doc.project) if sprint_doc.project else _default_labels()

    if not sprint_doc.start_date or not sprint_doc.end_date:
        return _empty_burndown(sprint_doc, labels)

    start = getdate(sprint_doc.start_date)
    end = getdate(sprint_doc.end_date)
    today_dt = getdate(today())

    # Fetch all tasks that were ever in this sprint, with their history
    tasks = frappe.get_all("BP Task", filters={"sprint": sprint},
                           fields=["name", "title", "story_points", "status",
                                   "started_on", "completed_on", "creation"])

    # Total effort at sprint start = all tasks currently linked
    total_effort = sum(t.get("story_points") or 0 for t in tasks)
    total_tasks = len(tasks)

    # Build day-by-day: for each sprint day, count how many tasks were still
    # not-completed (status not in the project's "done" categories).
    project = sprint_doc.project
    done_statuses = _get_done_statuses(project) if project else {"Done", "Completed", "Closed"}

    dates = []
    ideal_line = []
    actual_effort = []
    actual_count = []

    day_count = date_diff(end, start) + 1
    if day_count <= 0:
        return _empty_burndown(sprint_doc)

    for i in range(day_count):
        d = add_days(start, i)
        dates.append(str(d))

        # Ideal: linear from total → 0
        ideal = total_effort * (1.0 - i / max(day_count - 1, 1))
        ideal_line.append(round(ideal, 1))

        # Actual remaining on day d:
        #   For past days, count tasks NOT completed by that day
        #   For future days, use today's snapshot
        remaining_effort = 0.0
        remaining_count = 0
        for t in tasks:
            done = _was_done_by(t, d)
            if not done:
                remaining_effort += t.get("story_points") or 0
                remaining_count += 1

        actual_effort.append(round(remaining_effort, 1))
        actual_count.append(remaining_count)

    # Completed so far (at today or end, whichever is earlier)
    cutoff = min(today_dt, end)
    completed_effort = 0.0
    completed_count = 0
    for t in tasks:
        if _was_done_by(t, cutoff):
            completed_effort += t.get("story_points") or 0
            completed_count += 1

    # Scope change: did total_effort grow vs what was committed at start?
    # Simple heuristic: if today's remaining + completed > total_effort, scope was added.
    # For a perfect world we'd snapshot at sprint start — this is a live approximation.
    todays_remaining = sum(t.get("story_points") or 0 for t in tasks
                          if not _was_done_by(t, min(today_dt, end)))
    scope_change = max(0.0, round((completed_effort + todays_remaining) - total_effort, 1))

    days_elapsed = date_diff(min(today_dt, end), start) + 1
    pct_complete_effort = round(completed_effort / max(total_effort, 1) * 100, 1)
    pct_complete_count = round(completed_count / max(total_tasks, 1) * 100, 1)

    return {
        "sprint": sprint_doc.name,
        "sprint_name": sprint_doc.sprint_name,
        "start_date": str(start),
        "end_date": str(end),
        "status": sprint_doc.status,
        "total_effort": total_effort,
        "total_tasks": total_tasks,
        "ideal_line": ideal_line,
        "actual_effort": actual_effort,
        "actual_count": actual_count,
        "dates": dates,
        "completed_effort": completed_effort,
        "completed_count": completed_count,
        "scope_change": scope_change,
        "days_elapsed": days_elapsed,
        "days_total": day_count,
        "pct_complete_effort": pct_complete_effort,
        "pct_complete_count": pct_complete_count,
        "cycle_label": labels["cycle_label"],
        "effort_label": labels["effort_label"],
        "effort_label_abbr": labels["effort_label_abbr"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# VELOCITY — rolling completed-effort history
# ─────────────────────────────────────────────────────────────────────────────

def compute_velocity(project: str, last_n: int = 8, use_effort: bool = True) -> dict:
    """Return velocity data for the last N completed sprints."""
    labels = _get_project_labels(project)

    sprints = frappe.get_all("BP Sprint",
        filters={"project": project, "status": "Completed"},
        fields=["name", "sprint_name", "start_date", "end_date"],
        order_by="end_date desc", limit=last_n)

    sprint_data = []
    for s in reversed(sprints):  # chronological
        tasks = frappe.get_all("BP Task", filters={"sprint": s.name},
                               fields=["name", "story_points", "status"])
        done_statuses = _get_done_statuses(project)
        completed_effort = sum(t.get("story_points") or 0 for t in tasks
                              if (t.get("status") or "").lower() in done_statuses)
        completed_count = sum(1 for t in tasks
                             if (t.get("status") or "").lower() in done_statuses)
        total_effort = sum(t.get("story_points") or 0 for t in tasks)
        completion_pct = round(completed_effort / max(total_effort, 1) * 100, 1)

        sprint_data.append({
            "name": s.name,
            "sprint_name": s.sprint_name,
            "status": "Completed",
            "completed_effort": completed_effort,
            "completed_count": completed_count,
            "total_effort": total_effort,
            "completion_pct": completion_pct,
            "start_date": str(s.start_date) if s.start_date else None,
            "end_date": str(s.end_date) if s.end_date else None,
        })

    efforts = [s["completed_effort"] for s in sprint_data if s["completed_effort"] > 0]
    counts = [s["completed_count"] for s in sprint_data if s["completed_count"] > 0]

    avg_effort = round(sum(efforts) / max(len(efforts), 1), 1)
    avg_count = round(sum(counts) / max(len(counts), 1), 1)

    # Simple trend: compare first half average to second half
    trend = "stable"
    if len(efforts) >= 4:
        mid = len(efforts) // 2
        first_half = sum(efforts[:mid]) / max(mid, 1)
        second_half = sum(efforts[mid:]) / max(len(efforts) - mid, 1)
        if second_half > first_half * 1.1:
            trend = "rising"
        elif second_half < first_half * 0.9:
            trend = "falling"

    return {
        "project": project,
        "sprints": sprint_data,
        "average_effort": avg_effort,
        "average_count": avg_count,
        "trend": trend,
        "sprint_count": len(sprint_data),
        "cycle_label": labels["cycle_label"],
        "effort_label": labels["effort_label"],
        "effort_label_abbr": labels["effort_label_abbr"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# BURNUP — tracks completed + total scope over time
# ─────────────────────────────────────────────────────────────────────────────

def compute_burnup(sprint: str) -> dict:
    """Burnup chart: shows completed work AND total scope over time."""
    sprint_doc = frappe.get_doc("BP Sprint", sprint)
    labels = _get_project_labels(sprint_doc.project) if sprint_doc.project else _default_labels()

    if not sprint_doc.start_date or not sprint_doc.end_date:
        return {}

    start = getdate(sprint_doc.start_date)
    end = getdate(sprint_doc.end_date)

    tasks = frappe.get_all("BP Task", filters={"sprint": sprint},
                           fields=["name", "story_points", "status",
                                   "completed_on", "creation"])
    done_statuses = _get_done_statuses(sprint_doc.project) if sprint_doc.project else set()

    day_count = date_diff(end, start) + 1
    if day_count <= 0:
        return {}

    dates, completed_line, scope_line, ideal_line = [], [], [], []
    total_effort = sum(t.get("story_points") or 0 for t in tasks)

    for i in range(day_count):
        d = add_days(start, i)
        dates.append(str(d))

        cum_completed = sum(t.get("story_points") or 0 for t in tasks
                           if _was_done_by(t, d))
        cum_scope = total_effort  # simplified: current total as snapshot
        ideal = total_effort * min((i + 1) / max(day_count, 1), 1.0)

        completed_line.append(round(cum_completed, 1))
        scope_line.append(round(cum_scope, 1))
        ideal_line.append(round(ideal, 1))

    return {
        "sprint": sprint_doc.name,
        "sprint_name": sprint_doc.sprint_name,
        "start_date": str(start),
        "end_date": str(end),
        "dates": dates,
        "completed_line": completed_line,
        "scope_line": scope_line,
        "ideal_line": ideal_line,
        "total_effort": total_effort,
        "cycle_label": labels["cycle_label"],
        "effort_label": labels["effort_label"],
        "effort_label_abbr": labels["effort_label_abbr"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# CYCLE TIME — time tasks spend in progress
# ─────────────────────────────────────────────────────────────────────────────

def compute_cycle_time(project: str, days: int = 90) -> dict:
    """Cycle time distribution for tasks completed in the last N days."""
    labels = _get_project_labels(project)

    cutoff = add_days(today(), -days)
    tasks = frappe.get_all("BP Task",
        filters={
            "project": project,
            "completed_on": [">=", str(cutoff)],
            "started_on": ["is", "set"],
        },
        fields=["name", "title", "status", "priority", "task_type",
                "creation", "started_on", "completed_on"])

    if not tasks:
        return _empty_cycle_time(project, days)

    cycle_times = []
    lead_times = []
    by_status = {}
    by_priority = {}
    by_type = {}

    for t in tasks:
        ct = _days_between(t.get("started_on"), t.get("completed_on"))
        lt = _days_between(t.get("creation"), t.get("completed_on"))
        if ct is not None and ct >= 0:
            cycle_times.append(ct)
        if lt is not None and lt >= 0:
            lead_times.append(lt)

        status = (t.get("status") or "Unknown").lower()
        priority = t.get("priority") or "Medium"
        ttype = t.get("task_type") or "Task"

        if ct is not None and ct >= 0:
            if status not in by_status:
                by_status[status] = {"sum": 0, "count": 0}
            by_status[status]["sum"] += ct
            by_status[status]["count"] += 1

            if priority not in by_priority:
                by_priority[priority] = {"sum": 0, "count": 0}
            by_priority[priority]["sum"] += ct
            by_priority[priority]["count"] += 1

            if ttype not in by_type:
                by_type[ttype] = {"sum": 0, "count": 0}
            by_type[ttype]["sum"] += ct
            by_type[ttype]["count"] += 1

    ct_sorted = sorted(cycle_times)
    lt_sorted = sorted(lead_times)

    p = lambda arr, pct: arr[int(len(arr) * pct / 100)] if arr else 0

    return {
        "project": project,
        "period_days": days,
        "task_count": len(tasks),
        "cycle_time_avg_days": round(sum(cycle_times) / max(len(cycle_times), 1), 1) if cycle_times else 0,
        "cycle_time_median_days": p(ct_sorted, 50),
        "cycle_time_p50": p(ct_sorted, 50),
        "cycle_time_p75": p(ct_sorted, 75),
        "cycle_time_p90": p(ct_sorted, 90),
        "cycle_time_p95": p(ct_sorted, 95),
        "lead_time_avg_days": round(sum(lead_times) / max(len(lead_times), 1), 1) if lead_times else 0,
        "lead_time_median_days": p(lt_sorted, 50),
        "histogram_cycle": _make_histogram(cycle_times, [1, 2, 3, 5, 7, 14, 30]),
        "histogram_lead": _make_histogram(lead_times, [1, 2, 3, 5, 7, 14, 30]),
        "by_status_avg": [{"status": k, "avg_cycle_days": round(v["sum"] / max(v["count"], 1), 1),
                           "count": v["count"]} for k, v in sorted(by_status.items())],
        "by_priority_avg": [{"priority": k, "avg_cycle_days": round(v["sum"] / max(v["count"], 1), 1),
                             "count": v["count"]} for k, v in sorted(by_priority.items())],
        "by_type_avg": [{"type": k, "avg_cycle_days": round(v["sum"] / max(v["count"], 1), 1),
                         "count": v["count"]} for k, v in sorted(by_type.items())],
        "cycle_label": labels["cycle_label"],
        "effort_label": labels["effort_label"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# SPRINT HEALTH — comprehensive one-shot dashboard
# ─────────────────────────────────────────────────────────────────────────────

def compute_sprint_health(sprint: str) -> dict:
    """Aggregate all sprint metrics into one response for the detail page."""
    burndown = compute_burndown(sprint)
    burnup = compute_burnup(sprint)

    sprint_doc = frappe.get_doc("BP Sprint", sprint)
    project = sprint_doc.project

    velocity = compute_velocity(project, last_n=6) if project else {}
    cycle_time = compute_cycle_time(project, days=60) if project else {}

    # Active tasks per status
    status_counts = {}
    if project:
        tasks = frappe.get_all("BP Task", filters={"sprint": sprint},
                               fields=["status", "priority", "task_type"])
        for t in tasks:
            s = t.get("status") or "Unknown"
            status_counts[s] = status_counts.get(s, 0) + 1

    return {
        "sprint": sprint_doc.name,
        "sprint_name": sprint_doc.sprint_name,
        "project": project,
        "status": sprint_doc.status,
        "start_date": str(sprint_doc.start_date) if sprint_doc.start_date else None,
        "end_date": str(sprint_doc.end_date) if sprint_doc.end_date else None,
        "goal": sprint_doc.goal or "",
        "burndown": burndown,
        "burnup": burnup,
        "velocity": velocity,
        "cycle_time": cycle_time,
        "status_counts": status_counts,
    }


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _get_project_labels(project: str) -> dict:
    """Read cycle_label and effort_label from the project, falling back to defaults."""
    if not project:
        return _default_labels()
    try:
        proj = frappe.get_doc("BP Project", project)
        cl = proj.cycle_label() if hasattr(proj, "cycle_label") else "Sprint"
        el = proj.effort_label() if hasattr(proj, "effort_label") else "Story Points"
        ab = proj.effort_label_abbr() if hasattr(proj, "effort_label_abbr") else "pts"
        return {"cycle_label": cl, "effort_label": el, "effort_label_abbr": ab}
    except Exception:
        return _default_labels()


def _default_labels() -> dict:
    return {"cycle_label": "Sprint", "effort_label": "Story Points", "effort_label_abbr": "pts"}


def _get_done_statuses(project: str) -> set:
    """Resolve which workflow states count as 'done' for this project."""
    proj = frappe.get_doc("BP Project", project)
    states = proj.get_workflow_states()
    if not states:
        return {"done", "completed", "closed", "resolved", "cancelled"}
    done_cats = {"done", "completed", "closed", "resolved", "cancelled"}
    result = set()
    for s in states:
        cat = (s.get("category") or "").lower()
        name = (s.get("name") or "").lower()
        if cat in done_cats or name in done_cats:
            result.add(name)
    return result or {"done", "completed", "closed", "resolved", "cancelled"}


def _was_done_by(task: dict, date) -> bool:
    """Did this task reach a 'done' status on or before `date`?"""
    completed = task.get("completed_on")
    if not completed:
        return False
    return getdate(completed) <= getdate(date)


def _days_between(a, b) -> int | None:
    """Days between two date/datetime values, or None if either is missing."""
    if not a or not b:
        return None
    try:
        return date_diff(b, a)
    except Exception:
        return None


def _make_histogram(values: list[int], buckets: list[int]) -> list[dict]:
    """Bucket integer values into a histogram."""
    if not values:
        return [{"bucket": f"≤{b}d", "max_days": b, "count": 0} for b in buckets]
    result = []
    prev = 0
    for b in buckets:
        count = sum(1 for v in values if prev < v <= b)
        result.append({"bucket": f"≤{b}d", "max_days": b, "count": count})
        prev = b
    # Overflow bucket
    overflow = sum(1 for v in values if v > buckets[-1])
    if overflow:
        result.append({"bucket": f">{buckets[-1]}d", "max_days": None, "count": overflow})
    return result


def _empty_burndown(sprint_doc, labels=None) -> dict:
    if labels is None:
        labels = _default_labels()
    return {
        "sprint": sprint_doc.name,
        "sprint_name": sprint_doc.sprint_name,
        "start_date": None,
        "end_date": None,
        "status": sprint_doc.status,
        "total_effort": 0, "total_tasks": 0,
        "ideal_line": [], "actual_effort": [], "actual_count": [], "dates": [],
        "completed_effort": 0, "completed_count": 0,
        "scope_change": 0, "days_elapsed": 0, "days_total": 0,
        "pct_complete_effort": 0, "pct_complete_count": 0,
        "cycle_label": labels["cycle_label"],
        "effort_label": labels["effort_label"],
        "effort_label_abbr": labels["effort_label_abbr"],
    }


def _empty_cycle_time(project: str, days: int) -> dict:
    return {
        "project": project, "period_days": days, "task_count": 0,
        "cycle_time_avg_days": 0, "cycle_time_median_days": 0,
        "cycle_time_p50": 0, "cycle_time_p75": 0, "cycle_time_p90": 0, "cycle_time_p95": 0,
        "lead_time_avg_days": 0, "lead_time_median_days": 0,
        "histogram_cycle": [], "histogram_lead": [],
        "by_status_avg": [], "by_priority_avg": [], "by_type_avg": [],
    }
