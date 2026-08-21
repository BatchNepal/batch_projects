"""Trash-safe task analytics adapters.

Several legacy analytics endpoints predate the shared task query engine and read
``BP Task`` directly with ``frappe.get_all``. Because ``get_all`` ignores Frappe
permission query conditions, soft-deleted tasks must be excluded explicitly at
every such aggregation boundary.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import frappe


def _check(project: str, role: str = "BP Viewer") -> None:
    from batch_projects.api.board import _check_permission
    _check_permission(project, role)


@frappe.whitelist()
def get_milestone_report(milestone):
    m = frappe.get_doc("BP Milestone", milestone)
    _check(m.project)
    proj = frappe.get_doc("BP Project", m.project)
    completed = set(proj.get_completed_statuses())

    tasks = frappe.get_all(
        "BP Task",
        filters={"milestone": milestone, "project": m.project, "is_deleted": 0},
        fields=[
            "name", "task_key", "title", "status", "story_points",
            "estimated_hours", "actual_hours", "billable", "due_date",
        ],
    )

    total = len(tasks)
    done = sum(1 for t in tasks if t.status in completed)
    pts_total = sum(float(t.story_points or 0) for t in tasks)
    pts_done = sum(float(t.story_points or 0) for t in tasks if t.status in completed)
    est_hours = sum(float(t.estimated_hours or 0) for t in tasks)
    act_hours = sum(float(t.actual_hours or 0) for t in tasks)
    billable_hours = sum(float(t.actual_hours or 0) for t in tasks if t.billable)

    rate = float(proj.hourly_rate or 0)
    budget = float(proj.budget_amount or 0)
    cost = round(act_hours * rate, 2)
    billable_value = round(billable_hours * rate, 2)

    # Rate/cost/budget are money data, not delivery-progress data — a plain
    # project Viewer has no view_money capability by default (matches the
    # gate task_reads.py already applies to task-level billable/sales_order).
    from batch_projects import access
    financials = None
    if access.has_capability(m.project, "view_money"):
        financials = {
            "estimated_hours": round(est_hours, 1),
            "actual_hours": round(act_hours, 1),
            "billable_hours": round(billable_hours, 1),
            "hourly_rate": rate,
            "cost": cost,
            "billable_value": billable_value,
            "budget": budget,
            "budget_used_pct": round(cost / budget * 100) if budget else None,
        }

    return {
        "milestone": milestone,
        "title": m.title,
        "project": m.project,
        "project_name": proj.project_name,
        "currency": proj.currency or None,
        "due_date": str(m.due_date) if m.due_date else None,
        "status": m.status,
        "delivery": {
            "total": total,
            "done": done,
            "completion_pct": round(done / total * 100) if total else 0,
            "points_total": round(pts_total, 1),
            "points_done": round(pts_done, 1),
        },
        "financials": financials,
        "tasks": tasks,
    }


@frappe.whitelist()
def get_sprint_capacity(sprint):
    doc = frappe.get_doc("BP Sprint", sprint)
    _check(doc.project)

    tasks = frappe.get_all(
        "BP Task",
        filters={"sprint": sprint, "project": doc.project, "is_deleted": 0},
        fields=["name", "estimated_hours"],
    )
    task_names = [t["name"] for t in tasks]
    hours_by_task = {t["name"]: (t["estimated_hours"] or 0) for t in tasks}

    assignee_rows = frappe.get_all(
        "BP Task Assignee",
        filters={"parent": ["in", task_names], "parenttype": "BP Task"},
        fields=["parent", "user", "full_name"],
    ) if task_names else []

    allocated, names, task_count = {}, {}, {}
    for row in assignee_rows:
        user = row["user"]
        allocated[user] = allocated.get(user, 0) + hours_by_task.get(row["parent"], 0)
        task_count[user] = task_count.get(user, 0) + 1
        names[user] = row["full_name"] or user

    from batch_projects.api.board import _get_member_capacities
    caps = _get_member_capacities(list(allocated.keys()))
    members = [
        {
            "user": user,
            "full_name": names[user],
            "allocated_hours": round(allocated[user], 1),
            "capacity_hours": caps.get(user, 40.0),
            "task_count": task_count[user],
        }
        for user in allocated
    ]
    members.sort(key=lambda m: m["allocated_hours"], reverse=True)
    assigned_names = {row["parent"] for row in assignee_rows}
    return {
        "sprint": sprint,
        "sprint_name": doc.sprint_name,
        "members": members,
        "unassigned_task_count": sum(1 for t in tasks if t["name"] not in assigned_names),
    }


def _resolve_report_projects(project):
    import json

    if isinstance(project, str) and project.strip().startswith("["):
        try:
            project = json.loads(project)
        except Exception:
            pass

    if isinstance(project, (list, tuple)):
        requested = [p for p in project if p]
    elif not project or project == "all":
        requested = None
    else:
        requested = [project]

    if requested is None:
        from batch_projects.permissions import get_accessible_projects
        accessible = get_accessible_projects(frappe.session.user)
        return frappe.get_all("BP Project", pluck="name") if accessible is None else list(accessible)

    resolved = []
    for value in requested:
        name = value if frappe.db.exists("BP Project", value) else frappe.db.get_value(
            "BP Project", {"key": value}, "name"
        )
        if name:
            _check(name)
            resolved.append(name)
    return resolved


def _as_date(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except Exception:
        return None


@frappe.whitelist()
def get_reports(project, period="last_30_days", from_date=None, to_date=None):
    """Delivery analytics computed exclusively from live (non-trashed) tasks."""
    from batch_projects.api.board import _normalize_workflow_states

    projects = _resolve_report_projects(project)
    if not projects:
        frappe.throw("No accessible project in scope for this report.", frappe.ValidationError)

    project_filter = projects[0] if len(projects) == 1 else ["in", projects]

    states, completed, seen_states = [], set(), set()
    for name in projects:
        pdoc = frappe.get_cached_doc("BP Project", name)
        for state in _normalize_workflow_states(pdoc.get_workflow_states()):
            state_name = state.get("name")
            if state_name and state_name not in seen_states:
                seen_states.add(state_name)
                states.append(state)
        completed |= set(pdoc.get_completed_statuses())

    today = date.today()
    period_days = {"last_7_days": 7, "last_30_days": 30, "last_90_days": 90}
    if from_date and to_date:
        from_date = _as_date(from_date) or today - timedelta(days=30)
        to_date = _as_date(to_date) or today
    elif period in period_days:
        from_date, to_date = today - timedelta(days=period_days[period]), today
    elif isinstance(period, str) and period.startswith("month:"):
        import calendar
        year, month = (int(v) for v in period.split(":", 1)[1].split("-"))
        from_date = date(year, month, 1)
        to_date = date(year, month, calendar.monthrange(year, month)[1])
    else:
        from_date, to_date = today - timedelta(days=30), today

    tasks = frappe.get_all(
        "BP Task",
        filters={"project": project_filter, "is_deleted": 0},
        fields=[
            "name", "status", "story_points", "sprint", "started_on",
            "completed_on", "creation",
        ],
    )

    counts = {}
    for task in tasks:
        counts[task["status"]] = counts.get(task["status"], 0) + 1
    status_breakdown = [
        {
            "name": state.get("name"),
            "color": state.get("color") or "#9FA6AD",
            "category": state.get("category"),
            "count": counts.get(state.get("name"), 0),
        }
        for state in states
    ]
    known = {state.get("name") for state in states}
    for status, count in counts.items():
        if status not in known:
            status_breakdown.append(
                {"name": status, "color": "#9FA6AD", "category": "unstarted", "count": count}
            )

    start_week = from_date - timedelta(days=from_date.weekday())
    buckets, cursor = [], start_week
    while cursor <= to_date:
        buckets.append({"start": cursor, "label": cursor.strftime("%b %d"), "created": 0, "completed": 0})
        cursor += timedelta(days=7)

    def bucket_index(day):
        if not buckets or not day or day < buckets[0]["start"] or day > to_date:
            return None
        return min((day - buckets[0]["start"]).days // 7, len(buckets) - 1)

    cycle_days, cycle_scatter = [], []
    for task in tasks:
        idx = bucket_index(_as_date(task.get("creation")))
        if idx is not None:
            buckets[idx]["created"] += 1
        done = _as_date(task.get("completed_on"))
        idx = bucket_index(done)
        if idx is not None:
            buckets[idx]["completed"] += 1
        started = _as_date(task.get("started_on"))
        if started and done and done >= started:
            days = (done - started).days
            cycle_days.append(days)
            cycle_scatter.append({"date": done.isoformat(), "days": days})

    throughput = [
        {"label": b["label"], "created": b["created"], "completed": b["completed"]}
        for b in buckets
    ]

    def percentile(values, pct):
        if not values:
            return 0
        ordered = sorted(values)
        k = (len(ordered) - 1) * pct / 100
        floor = int(k)
        ceil = min(floor + 1, len(ordered) - 1)
        return round(ordered[floor] + (ordered[ceil] - ordered[floor]) * (k - floor), 1)

    sprints = frappe.get_all(
        "BP Sprint",
        filters={"project": project_filter},
        fields=["name", "sprint_name", "status", "start_date", "end_date"],
        order_by="start_date asc, creation asc",
    )
    committed, done_points = {}, {}
    for task in tasks:
        sprint = task.get("sprint")
        if not sprint:
            continue
        points = float(task.get("story_points") or 0)
        committed[sprint] = committed.get(sprint, 0) + points
        if task["status"] in completed:
            done_points[sprint] = done_points.get(sprint, 0) + points
    velocity = [
        {
            "name": sprint["name"],
            "label": sprint["sprint_name"],
            "status": sprint["status"],
            "committed": committed.get(sprint["name"], 0),
            "completed": done_points.get(sprint["name"], 0),
        }
        for sprint in sprints
    ]

    live_names = [task["name"] for task in tasks]
    activities = frappe.get_all(
        "BP Activity",
        filters={
            "project": project_filter,
            "field_name": "status",
            "task": ["in", live_names or ["__none__"]],
        },
        fields=["task", "old_value", "new_value", "creation"],
        order_by="creation asc",
    )
    transitions = {}
    for activity in activities:
        transitions.setdefault(activity["task"], []).append(activity)
    task_by_name = {task["name"]: task for task in tasks}

    def status_on(task_name, day):
        task = task_by_name.get(task_name)
        if not task:
            return None
        created = _as_date(task.get("creation"))
        if not created or created > day:
            return None
        timeline = transitions.get(task_name, [])
        current = timeline[0]["old_value"] if timeline else task["status"]
        for activity in timeline:
            activity_day = _as_date(activity["creation"])
            if activity_day and activity_day <= day:
                current = activity["new_value"]
            else:
                break
        return current

    cfd_order = [state["name"] for state in status_breakdown]
    cfd_color = {state["name"]: state["color"] for state in status_breakdown}
    cfd_counts = {name: [] for name in cfd_order}
    for bucket in buckets:
        snapshot = min(bucket["start"] + timedelta(days=6), to_date)
        snapshot_counts = {name: 0 for name in cfd_order}
        for task in tasks:
            status = status_on(task["name"], snapshot)
            if status in snapshot_counts:
                snapshot_counts[status] += 1
        for name in cfd_order:
            cfd_counts[name].append(snapshot_counts[name])
    cumulative_flow = {
        "labels": [bucket["label"] for bucket in buckets],
        "series": [
            {"name": name, "color": cfd_color[name], "counts": cfd_counts[name]}
            for name in cfd_order
        ],
    }

    dated_sprints = [s for s in sprints if s.get("start_date") and s.get("end_date")]
    chosen = next((s for s in dated_sprints if s["status"] == "Active"), None)
    if not chosen and dated_sprints:
        chosen = sorted(dated_sprints, key=lambda s: s["start_date"])[-1]
    burndown = None
    if chosen:
        sprint_start, sprint_end = _as_date(chosen["start_date"]), _as_date(chosen["end_date"])
        sprint_tasks = [t for t in tasks if t.get("sprint") == chosen["name"]]
        total_points = sum(float(t.get("story_points") or 0) for t in sprint_tasks)
        ndays = (sprint_end - sprint_start).days + 1 if sprint_start and sprint_end else 0
        days = []
        for index in range(max(ndays, 0)):
            day = sprint_start + timedelta(days=index)
            ideal = round(total_points * (1 - index / (ndays - 1)), 1) if ndays > 1 else total_points
            burned = sum(
                float(t.get("story_points") or 0)
                for t in sprint_tasks
                if t["status"] in completed
                and _as_date(t.get("completed_on"))
                and _as_date(t["completed_on"]) <= day
            )
            days.append(
                {
                    "label": day.strftime("%b %d"),
                    "ideal": ideal,
                    "remaining": round(total_points - burned, 1) if day <= today else None,
                }
            )
        burndown = {"sprint": chosen["sprint_name"], "total": total_points, "days": days}

    average_cycle = round(sum(cycle_days) / len(cycle_days), 1) if cycle_days else 0
    completed_in_period = sum(bucket["completed"] for bucket in buckets)
    return {
        "period": period,
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "total_tasks": len(tasks),
        "status_breakdown": status_breakdown,
        "throughput": throughput,
        "cycle_time": {
            "avg_days": average_cycle,
            "completed_count": completed_in_period,
            "sample": len(cycle_days),
            "p50": percentile(cycle_days, 50),
            "p85": percentile(cycle_days, 85),
            "p95": percentile(cycle_days, 95),
            "scatter": cycle_scatter,
        },
        "velocity": velocity,
        "cumulative_flow": cumulative_flow,
        "burndown": burndown,
    }
