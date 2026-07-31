"""
Seed realistic demo data into a BP Project for UI design and QA work.

Usage:
    bench --site <site> execute batch_projects.scripts.seed_demo_data.run
    bench --site <site> execute batch_projects.scripts.seed_demo_data.run --kwargs '{"project": "BP-PROJECT-00001"}'
    bench --site <site> execute batch_projects.scripts.seed_demo_data.run --kwargs '{"reset": true}'
    bench --site <site> execute batch_projects.scripts.seed_demo_data.reset

Idempotent: running twice does nothing unless --kwargs '{"reset": true}' is passed.
Marker: tasks seeded by this script have DEMO_MARKER in their description field.
"""

import frappe
import random
from datetime import datetime, timedelta

DEMO_MARKER = "<!-- demo-seed -->"

TITLES = [
    "Design new user onboarding flow",
    "Integrate Stripe payment gateway",
    "Fix Safari mobile rendering bug",
    "Write API documentation for v2 endpoints",
    "Performance audit — reduce JS bundle size",
    "Set up CI/CD pipeline with GitHub Actions",
    "Migrate authentication to OAuth 2.0",
    "Accessibility audit (WCAG 2.1 AA compliance)",
    "Build customer analytics dashboard",
    "Add dark mode support to web app",
    "Fix race condition in task sync worker",
    "Refactor board drag-and-drop to use Sortable.js",
    "Add bulk task assignment feature",
    "Write E2E tests for checkout flow",
    "Set up error monitoring with Sentry",
    "Design system — button component audit",
    "Q2 sprint retrospective action items",
    "Update privacy policy for GDPR compliance",
    "Build webhook notification system",
    "Optimize slow database queries on list view",
    "Add CSV export for task and sprint reports",
    "Fix email notification delivery delays",
    "Implement task dependency graph visualization",
    "Push notification support for mobile app",
    "Migrate hosting to new infrastructure",
    "User interview synthesis — March cohort",
    "Spike: evaluate AI-assisted task categorization",
    "Write changelog and release notes for v2.1",
    "Remove deprecated v1 API endpoints",
    "Fix timezone edge case in due date display",
]

COMMENTS = [
    "Checked with the design team — the current approach looks good. Moving forward.",
    "Blocked on a response from the client. Following up today.",
    "PR is up for review. Waiting on CI to pass.",
    "Found a related issue in the mobile app — filed a separate task.",
    "The root cause was a missing index on the tasks table. Fixed.",
    "Spoke with @sarah about the design specs. We'll use the new component library.",
    "This is more complex than estimated. Adding 3 story points.",
    "Deployed to staging. Please verify and sign off before we push to prod.",
    "Done. Verified on Chrome, Firefox, and Safari.",
    "Needs a bit more testing on Edge — will follow up.",
    "Bumping priority — this is now blocking the Q2 release.",
    "Quick win. Done in 20 minutes. Closing.",
]

PRIORITIES = [
    "Highest", "Highest", "Highest",
    "High", "High", "High", "High", "High",
    "Medium", "Medium", "Medium", "Medium", "Medium",
    "Medium", "Medium", "Medium", "Medium", "Medium",
    "Low", "Low", "Low", "Low", "Low", "Low", "Low",
    "Lowest", "Lowest", "Lowest",
]


def run(project=None, reset=False):
    """Seed demo data. Pass project=<name> to target a specific project."""
    frappe.set_user("Administrator")

    proj_doc = _get_project(project)
    if not proj_doc:
        print("No BP Project found. Create a project first.")
        return

    print(f"Target project: {proj_doc.name} ({proj_doc.key})")

    if reset:
        _delete_demo_data(proj_doc.name)

    if _already_seeded(proj_doc.name):
        print("Demo data already present. Pass reset=True to re-seed.")
        return

    users = _get_users()
    if not users:
        print("No active System Users found. Seeding tasks without assignees.")

    states = proj_doc.get_workflow_states()
    types  = proj_doc.get_issue_types()
    if not states:
        print("Project has no workflow states. Configure the project first.")
        return

    type_names = [t["name"] for t in types] if types else ["Task"]
    status_names = [s["name"] for s in states]
    completed_statuses = {s["name"] for s in states if s.get("category") == "completed"}

    _seed_tasks(proj_doc, status_names, type_names, users)

    tasks = frappe.db.get_all(
        "BP Task",
        filters={"project": proj_doc.name, "description": ["like", f"%{DEMO_MARKER}%"]},
        fields=["name", "task_key", "status"],
    )
    _seed_activities(proj_doc.name, tasks, users, completed_statuses, status_names)

    frappe.db.commit()
    print(f"Seeded {len(tasks)} tasks and activities into {proj_doc.key}.")


def reset(project=None):
    """Delete all demo data from the project."""
    frappe.set_user("Administrator")
    proj_doc = _get_project(project)
    if not proj_doc:
        print("No BP Project found.")
        return
    _delete_demo_data(proj_doc.name)
    frappe.db.commit()
    print(f"Demo data removed from {proj_doc.key}.")


# ── Internal helpers ──────────────────────────────────────────────────────────

def _get_project(project_name):
    if project_name:
        try:
            return frappe.get_doc("BP Project", project_name)
        except frappe.DoesNotExistError:
            print(f"Project {project_name!r} not found.")
            return None
    names = frappe.db.get_all("BP Project", limit=1, order_by="creation asc", pluck="name")
    return frappe.get_doc("BP Project", names[0]) if names else None


def _already_seeded(project_name):
    return frappe.db.count(
        "BP Task",
        {"project": project_name, "description": ["like", f"%{DEMO_MARKER}%"]},
    ) > 0


def _delete_demo_data(project_name):
    tasks = frappe.db.get_all(
        "BP Task",
        filters={"project": project_name, "description": ["like", f"%{DEMO_MARKER}%"]},
        pluck="name",
    )
    for name in tasks:
        # Delete linked activities first
        for act in frappe.db.get_all("BP Activity", {"task": name}, pluck="name"):
            frappe.delete_doc("BP Activity", act, ignore_permissions=True, force=True)
        frappe.delete_doc("BP Task", name, ignore_permissions=True, force=True)
    print(f"Removed {len(tasks)} demo tasks.")


def _get_users():
    users = frappe.db.get_all(
        "User",
        filters={"enabled": 1, "user_type": "System User", "name": ["!=", "Administrator"]},
        fields=["name", "full_name"],
        limit=6,
    )
    # Always include Administrator as a fallback user
    users.append({"name": "Administrator", "full_name": "Administrator"})
    return users[:5] if len(users) >= 5 else users


def _seed_tasks(proj_doc, status_names, type_names, users):
    now = datetime.now()
    titles = random.sample(TITLES, min(len(TITLES), 28))
    priorities_pool = PRIORITIES[:]
    random.shuffle(priorities_pool)

    # Distribute statuses: weight toward middle statuses (in-progress work)
    n = len(titles)
    status_weights = _distribute_statuses(status_names, n)

    for i, title in enumerate(titles):
        status    = status_weights[i]
        priority  = priorities_pool[i % len(priorities_pool)]
        task_type = type_names[i % len(type_names)]
        due_date  = _pick_due_date(now, i)
        assignees = _pick_assignees(users, i)

        doc = frappe.get_doc({
            "doctype":     "BP Task",
            "title":       title,
            "project":     proj_doc.name,
            "status":      status,
            "priority":    priority,
            "task_type":   task_type,
            "due_date":    due_date,
            "description": f"<p>Task created for design and QA purposes.</p>{DEMO_MARKER}",
            "assignees":   [{"user": u["name"], "full_name": u["full_name"]} for u in assignees],
        })
        doc.insert(ignore_permissions=True)

        # Back-date creation to spread tasks over the past 30 days
        days_ago = random.randint(1, 30)
        created_at = (now - timedelta(days=days_ago)).strftime("%Y-%m-%d %H:%M:%S")
        frappe.db.set_value("BP Task", doc.name, "creation", created_at)


def _seed_activities(project_name, tasks, users, completed_statuses, status_names):
    if not tasks or not users:
        return

    now = datetime.now()
    unstarted = [s for s in status_names if s not in completed_statuses]
    in_progress = [s for s in status_names if s not in completed_statuses and s not in (unstarted[:1] if unstarted else [])]

    for i, task in enumerate(tasks):
        user = users[i % len(users)]

        # Every task gets a "Created" activity
        _make_activity(
            project=project_name, task=task["name"], task_key=task["task_key"],
            user=user["name"], action_type="Created",
            days_ago=random.randint(10, 28),
        )

        # Some tasks get a Status Change
        if i % 3 != 0 and len(status_names) > 1:
            old_s = status_names[0]
            new_s = task["status"] if task["status"] != old_s else (status_names[1] if len(status_names) > 1 else old_s)
            if old_s != new_s:
                _make_activity(
                    project=project_name, task=task["name"], task_key=task["task_key"],
                    user=users[(i + 1) % len(users)]["name"],
                    action_type="Status Change", old_value=old_s, new_value=new_s,
                    days_ago=random.randint(2, 9),
                )

        # Some tasks get an Assignment activity
        if i % 4 == 0 and users:
            assignee = users[i % len(users)]
            _make_activity(
                project=project_name, task=task["name"], task_key=task["task_key"],
                user=user["name"], action_type="Assignment",
                new_value=assignee["full_name"],
                days_ago=random.randint(3, 12),
            )

        # Some tasks get a Comment
        if i % 5 < 3:
            _make_activity(
                project=project_name, task=task["name"], task_key=task["task_key"],
                user=users[(i + 2) % len(users)]["name"], action_type="Comment",
                days_ago=random.randint(0, 7),
            )


def _make_activity(project, task, task_key, user, action_type,
                   old_value="", new_value="", days_ago=1):
    now = datetime.now()
    comment = random.choice(COMMENTS) if action_type == "Comment" else ""
    doc = frappe.get_doc({
        "doctype":      "BP Activity",
        "task":         task,
        "project":      project,
        "task_key":     task_key,
        "action_type":  action_type,
        "user":         user,
        "old_value":    old_value,
        "new_value":    new_value,
        "comment_text": comment,
    })
    doc.insert(ignore_permissions=True)
    ts = (now - timedelta(days=days_ago, hours=random.randint(0, 23),
                          minutes=random.randint(0, 59))).strftime("%Y-%m-%d %H:%M:%S")
    frappe.db.set_value("BP Activity", doc.name, "creation", ts)


def _distribute_statuses(status_names, n):
    """Distribute n tasks across statuses, weighting middle statuses."""
    if len(status_names) == 1:
        return [status_names[0]] * n
    weights = _status_weights(len(status_names))
    result = []
    for i, s in enumerate(status_names):
        count = round(n * weights[i])
        result.extend([s] * count)
    # Trim or pad to exactly n
    while len(result) < n:
        result.append(status_names[len(status_names) // 2])
    return result[:n]


def _status_weights(count):
    """Return per-status weights that favour middle (in-progress) statuses."""
    if count == 1:  return [1.0]
    if count == 2:  return [0.4, 0.6]
    if count == 3:  return [0.25, 0.45, 0.30]
    if count == 4:  return [0.15, 0.35, 0.30, 0.20]
    if count == 5:  return [0.12, 0.22, 0.28, 0.22, 0.16]
    if count == 6:  return [0.10, 0.18, 0.24, 0.20, 0.16, 0.12]
    # Fallback: uniform
    return [1.0 / count] * count


def _pick_due_date(now, index):
    """Spread due dates: some overdue, some due soon, some later, some none."""
    bucket = index % 6
    if bucket == 0:  return (now - timedelta(days=random.randint(1, 14))).strftime("%Y-%m-%d")   # overdue
    if bucket == 1:  return (now + timedelta(days=random.randint(1, 6))).strftime("%Y-%m-%d")    # due this week
    if bucket == 2:  return (now + timedelta(days=random.randint(7, 21))).strftime("%Y-%m-%d")   # due next 2 weeks
    if bucket == 3:  return (now + timedelta(days=random.randint(22, 60))).strftime("%Y-%m-%d")  # later
    return None  # buckets 4 and 5 → no due date


def _pick_assignees(users, index):
    """Most tasks get 1 assignee; some get 2; some unassigned."""
    if not users:
        return []
    bucket = index % 5
    if bucket == 4:
        return []  # 20% unassigned
    if bucket == 3 and len(users) >= 2:
        return [users[index % len(users)], users[(index + 1) % len(users)]]  # 20% two assignees
    return [users[index % len(users)]]
