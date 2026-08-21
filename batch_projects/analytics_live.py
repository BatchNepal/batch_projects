"""Live-task sprint analytics.

This module mirrors the public result shapes from ``analytics.py`` but applies
``is_deleted = 0`` at every BP Task query boundary. Soft-deleted work must not
contribute to operational burndown, velocity, burnup, cycle time or sprint
status counts.

The small formatting/date helpers remain imported from analytics.py so the two
engines cannot drift on percentile/histogram/label semantics while the legacy
module remains available for historical comparison.
"""

from __future__ import annotations

import frappe
from frappe.utils import add_days, date_diff, getdate, today

from batch_projects import analytics as base


def _live_filters(filters=None):
    out = dict(filters or {})
    out["is_deleted"] = 0
    return out


def compute_burndown(sprint: str) -> dict:
    sprint_doc = frappe.get_doc("BP Sprint", sprint)
    labels = base._get_project_labels(sprint_doc.project) if sprint_doc.project else base._default_labels()

    if not sprint_doc.start_date or not sprint_doc.end_date:
        return base._empty_burndown(sprint_doc, labels)

    start = getdate(sprint_doc.start_date)
    end = getdate(sprint_doc.end_date)
    today_dt = getdate(today())
    tasks = frappe.get_all(
        "BP Task",
        filters=_live_filters({"sprint": sprint}),
        fields=[
            "name", "title", "story_points", "status", "started_on",
            "completed_on", "creation",
        ],
    )

    total_effort = sum(task.get("story_points") or 0 for task in tasks)
    total_tasks = len(tasks)
    dates, ideal_line, actual_effort, actual_count = [], [], [], []

    day_count = date_diff(end, start) + 1
    if day_count <= 0:
        return base._empty_burndown(sprint_doc, labels)

    for index in range(day_count):
        day = add_days(start, index)
        dates.append(str(day))
        ideal_line.append(round(total_effort * (1.0 - index / max(day_count - 1, 1)), 1))

        remaining = [task for task in tasks if not base._was_done_by(task, day)]
        actual_effort.append(round(sum(task.get("story_points") or 0 for task in remaining), 1))
        actual_count.append(len(remaining))

    cutoff = min(today_dt, end)
    completed = [task for task in tasks if base._was_done_by(task, cutoff)]
    completed_effort = sum(task.get("story_points") or 0 for task in completed)
    completed_count = len(completed)
    todays_remaining = sum(
        task.get("story_points") or 0
        for task in tasks
        if not base._was_done_by(task, min(today_dt, end))
    )
    scope_change = max(
        0.0,
        round((completed_effort + todays_remaining) - total_effort, 1),
    )
    days_elapsed = date_diff(min(today_dt, end), start) + 1

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
        "pct_complete_effort": round(completed_effort / max(total_effort, 1) * 100, 1),
        "pct_complete_count": round(completed_count / max(total_tasks, 1) * 100, 1),
        "cycle_label": labels["cycle_label"],
        "effort_label": labels["effort_label"],
        "effort_label_abbr": labels["effort_label_abbr"],
    }


def compute_velocity(project: str, last_n: int = 8, use_effort: bool = True) -> dict:
    labels = base._get_project_labels(project)
    sprints = frappe.get_all(
        "BP Sprint",
        filters={"project": project, "status": "Completed"},
        fields=["name", "sprint_name", "start_date", "end_date"],
        order_by="end_date desc",
        limit=last_n,
    )

    done_statuses = base._get_done_statuses(project)
    sprint_data = []
    for sprint in reversed(sprints):
        tasks = frappe.get_all(
            "BP Task",
            filters=_live_filters({"sprint": sprint.name}),
            fields=["name", "story_points", "status"],
        )
        completed = [
            task for task in tasks
            if (task.get("status") or "").lower() in done_statuses
        ]
        completed_effort = sum(task.get("story_points") or 0 for task in completed)
        completed_count = len(completed)
        total_effort = sum(task.get("story_points") or 0 for task in tasks)
        sprint_data.append(
            {
                "name": sprint.name,
                "sprint_name": sprint.sprint_name,
                "status": "Completed",
                "completed_effort": completed_effort,
                "completed_count": completed_count,
                "total_effort": total_effort,
                "completion_pct": round(completed_effort / max(total_effort, 1) * 100, 1),
                "start_date": str(sprint.start_date) if sprint.start_date else None,
                "end_date": str(sprint.end_date) if sprint.end_date else None,
            }
        )

    efforts = [row["completed_effort"] for row in sprint_data if row["completed_effort"] > 0]
    counts = [row["completed_count"] for row in sprint_data if row["completed_count"] > 0]
    trend = "stable"
    if len(efforts) >= 4:
        middle = len(efforts) // 2
        first = sum(efforts[:middle]) / max(middle, 1)
        second = sum(efforts[middle:]) / max(len(efforts) - middle, 1)
        if second > first * 1.1:
            trend = "rising"
        elif second < first * 0.9:
            trend = "falling"

    return {
        "project": project,
        "sprints": sprint_data,
        "average_effort": round(sum(efforts) / max(len(efforts), 1), 1),
        "average_count": round(sum(counts) / max(len(counts), 1), 1),
        "trend": trend,
        "sprint_count": len(sprint_data),
        "cycle_label": labels["cycle_label"],
        "effort_label": labels["effort_label"],
        "effort_label_abbr": labels["effort_label_abbr"],
    }


def compute_burnup(sprint: str) -> dict:
    sprint_doc = frappe.get_doc("BP Sprint", sprint)
    labels = base._get_project_labels(sprint_doc.project) if sprint_doc.project else base._default_labels()
    if not sprint_doc.start_date or not sprint_doc.end_date:
        return {}

    start = getdate(sprint_doc.start_date)
    end = getdate(sprint_doc.end_date)
    tasks = frappe.get_all(
        "BP Task",
        filters=_live_filters({"sprint": sprint}),
        fields=["name", "story_points", "status", "completed_on", "creation"],
    )

    day_count = date_diff(end, start) + 1
    if day_count <= 0:
        return {}

    total_effort = sum(task.get("story_points") or 0 for task in tasks)
    dates, completed_line, scope_line, ideal_line = [], [], [], []
    for index in range(day_count):
        day = add_days(start, index)
        dates.append(str(day))
        completed_line.append(
            round(
                sum(
                    task.get("story_points") or 0
                    for task in tasks
                    if base._was_done_by(task, day)
                ),
                1,
            )
        )
        scope_line.append(round(total_effort, 1))
        ideal_line.append(
            round(total_effort * min((index + 1) / max(day_count, 1), 1.0), 1)
        )

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


def compute_cycle_time(project: str, days: int = 90) -> dict:
    labels = base._get_project_labels(project)
    cutoff = add_days(today(), -days)
    tasks = frappe.get_all(
        "BP Task",
        filters=_live_filters(
            {
                "project": project,
                "completed_on": [">=", str(cutoff)],
                "started_on": ["is", "set"],
            }
        ),
        fields=[
            "name", "title", "status", "priority", "task_type", "creation",
            "started_on", "completed_on",
        ],
    )
    if not tasks:
        result = base._empty_cycle_time(project, days)
        result["cycle_label"] = labels["cycle_label"]
        result["effort_label"] = labels["effort_label"]
        return result

    cycle_times, lead_times = [], []
    by_status, by_priority, by_type = {}, {}, {}
    for task in tasks:
        cycle = base._days_between(task.get("started_on"), task.get("completed_on"))
        lead = base._days_between(task.get("creation"), task.get("completed_on"))
        if cycle is not None and cycle >= 0:
            cycle_times.append(cycle)
        if lead is not None and lead >= 0:
            lead_times.append(lead)
        if cycle is None or cycle < 0:
            continue

        for store, key in (
            (by_status, (task.get("status") or "Unknown").lower()),
            (by_priority, task.get("priority") or "Medium"),
            (by_type, task.get("task_type") or "Task"),
        ):
            bucket = store.setdefault(key, {"sum": 0, "count": 0})
            bucket["sum"] += cycle
            bucket["count"] += 1

    cycle_sorted = sorted(cycle_times)
    lead_sorted = sorted(lead_times)

    def percentile(values, pct):
        return values[int(len(values) * pct / 100)] if values else 0

    return {
        "project": project,
        "period_days": days,
        "task_count": len(tasks),
        "cycle_time_avg_days": round(sum(cycle_times) / max(len(cycle_times), 1), 1) if cycle_times else 0,
        "cycle_time_median_days": percentile(cycle_sorted, 50),
        "cycle_time_p50": percentile(cycle_sorted, 50),
        "cycle_time_p75": percentile(cycle_sorted, 75),
        "cycle_time_p90": percentile(cycle_sorted, 90),
        "cycle_time_p95": percentile(cycle_sorted, 95),
        "lead_time_avg_days": round(sum(lead_times) / max(len(lead_times), 1), 1) if lead_times else 0,
        "lead_time_median_days": percentile(lead_sorted, 50),
        "histogram_cycle": base._make_histogram(cycle_times, [1, 2, 3, 5, 7, 14, 30]),
        "histogram_lead": base._make_histogram(lead_times, [1, 2, 3, 5, 7, 14, 30]),
        "by_status_avg": [
            {"status": key, "avg_cycle_days": round(value["sum"] / max(value["count"], 1), 1), "count": value["count"]}
            for key, value in sorted(by_status.items())
        ],
        "by_priority_avg": [
            {"priority": key, "avg_cycle_days": round(value["sum"] / max(value["count"], 1), 1), "count": value["count"]}
            for key, value in sorted(by_priority.items())
        ],
        "by_type_avg": [
            {"type": key, "avg_cycle_days": round(value["sum"] / max(value["count"], 1), 1), "count": value["count"]}
            for key, value in sorted(by_type.items())
        ],
        "cycle_label": labels["cycle_label"],
        "effort_label": labels["effort_label"],
    }


def compute_sprint_health(sprint: str) -> dict:
    burndown = compute_burndown(sprint)
    burnup = compute_burnup(sprint)
    sprint_doc = frappe.get_doc("BP Sprint", sprint)
    project = sprint_doc.project
    velocity = compute_velocity(project, last_n=6) if project else {}
    cycle_time = compute_cycle_time(project, days=60) if project else {}

    status_counts = {}
    if project:
        tasks = frappe.get_all(
            "BP Task",
            filters=_live_filters({"sprint": sprint, "project": project}),
            fields=["status", "priority", "task_type"],
        )
        for task in tasks:
            status = task.get("status") or "Unknown"
            status_counts[status] = status_counts.get(status, 0) + 1

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
