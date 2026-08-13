"""
batch_projects/api/insights_data.py
───────────────────────────────────
Raw row feeds for the gateway's compute plane.

This module is deliberately arithmetic-free. It answers "which rows is this
user allowed to see, and what is in them" — nothing else. Every derived
number (labour cost, margin, margin %, budget utilisation, rollup totals) is
computed in bp-gateway's internal/insights package, in the compiled binary.

Why the split, and why the math is NOT here:
    batch_projects is the open, self-hostable half of an open-core product.
    A `require_feature("profitability")` check in front of a margin formula
    gates ACCESS to the formula while shipping the formula itself in the same
    public repo — a self-hoster deletes two lines and keeps the feature. The
    formula is the part customers pay for, so the formula is the part that
    lives in the binary. Frappe stays the data hub: it owns the schema, the
    permission model, and the rows. The gateway owns the analysis.

    This is the same decide-vs-write split the automation engine already
    uses (Go evaluates, Frappe executes) pointed the other way: Frappe reads,
    Go computes.

Caller contract:
    Service account ONLY (_assert_service_caller). These endpoints take the
    acting `user` as a parameter rather than reading frappe.session.user,
    because the gateway calls them with its own service credentials on behalf
    of a user its session middleware already authenticated — the same trust
    shape internal/billing uses when it forwards X-BP-User-Email to
    bp-license. The service-caller assertion is what makes that parameter
    safe: without it, an arbitrary `user=` would be a privilege-escalation
    surface, since these rows are financial.

    No require_feature() call here on purpose. Tier enforcement for these
    surfaces happens at the gateway, before Frappe is ever reached — see
    internal/license/license.go's urlToFeature and internal/insights'
    own Allows() check. Re-checking in Python would be the patchable gate
    this module exists to stop relying on.
"""

import frappe


def _assert_service_caller():
    """Only the bridge service account (System Manager / Administrator) may
    call. Same guard as api/automation.py's — these feeds return unfiltered
    financial rows for an arbitrary named user."""
    user = frappe.session.user
    if user == "Administrator":
        return
    if "System Manager" in frappe.get_roles(user):
        return
    frappe.throw("Not permitted", frappe.PermissionError)


def _visible_money_projects(user: str) -> list[dict]:
    """Active projects `user` may see AND holds `view_money` on.

    Both filters are load-bearing and neither is redundant:
    accessible_project_filter enforces ordinary project visibility (get_all
    ignores permission_query_conditions), while view_money is the per-project
    financial capability — `profitability` is a tier gate, not a role check,
    so a user on a paid plan still must not see money for a project where
    their role withholds it.
    """
    from batch_projects import access
    from batch_projects.permissions import (
        NO_ACCESSIBLE_PROJECTS,
        accessible_project_filter,
    )

    proj_filters = accessible_project_filter({"status": "Active"}, user=user)
    if proj_filters is NO_ACCESSIBLE_PROJECTS:
        return []

    projects = frappe.get_all(
        "BP Project",
        filters=proj_filters,
        fields=["name", "project_name", "key", "project_color", "theme",
                "project_type", "hourly_rate", "budget_amount", "retainer_hours",
                "currency", "client", "start_date", "target_end_date",
                "erpnext_project"],
    )
    return [p for p in projects if access.has_capability(p["name"], "view_money", user=user)]


@frappe.whitelist()
def get_margin_inputs(from_date, to_date, user):
    """Every row bp-gateway needs to compute the margin report, already
    scoped to what `user` may see. Returns raw values only.

    Timesheet rows are returned PER ROW rather than pre-summed because the
    labour-cost rule is per row (a row's real ERPNext costing_amount when it
    has one, the project's flat rate as an estimate otherwise). Summing here
    would force the rule into Python and silently discard real costing — the
    exact bug batch_projects/costing.py was written to end. The gateway
    applies that rule now; Frappe just hands over hours + costing_amount.

    Purchase invoices and expense claims are pre-grouped by project because
    their contribution genuinely IS a plain SUM with no per-row rule — there
    is no analysis to give away, only bytes to save.
    """
    _assert_service_caller()

    projects = _visible_money_projects(user)
    erpnext_names = [p["erpnext_project"] for p in projects if p.get("erpnext_project")]
    if not erpnext_names:
        # Nothing bridged to ERPNext: the gateway still needs the project
        # list (they legitimately report as all-zero rows), just no ERP rows.
        return {"projects": projects, "invoices": [], "timesheets": [],
                "purchases": [], "expenses": []}

    from_dt = f"{from_date} 00:00:00"
    to_dt = f"{to_date} 23:59:59"

    def _query(table_exists, sql, params):
        """Each ERP source is optional — a bench without ERPNext, or with a
        module uninstalled, must degrade to "contributes nothing" rather than
        failing the whole report. Mirrors the per-source try/except the
        previous in-Frappe implementation used."""
        if not frappe.db.table_exists(table_exists):
            return []
        try:
            return frappe.db.sql(sql, params, as_dict=True)
        except Exception as exc:
            frappe.log_error(f"get_margin_inputs {table_exists}: {exc}")
            return []

    invoices = _query("Sales Invoice", """
        SELECT project, SUM(base_grand_total) AS revenue
        FROM `tabSales Invoice`
        WHERE docstatus = 1 AND project IN %(projects)s
          AND posting_date >= %(from_date)s AND posting_date <= %(to_date)s
        GROUP BY project
    """, {"projects": erpnext_names, "from_date": from_date, "to_date": to_date})

    timesheets = _query("Timesheet Detail", """
        SELECT tsd.project, tsd.hours, tsd.costing_amount
        FROM `tabTimesheet Detail` tsd
        JOIN `tabTimesheet` ts ON ts.name = tsd.parent AND ts.docstatus = 1
        WHERE tsd.project IN %(projects)s
          AND tsd.from_time >= %(from_dt)s AND tsd.from_time <= %(to_dt)s
    """, {"projects": erpnext_names, "from_dt": from_dt, "to_dt": to_dt})

    purchases = _query("Purchase Invoice Item", """
        SELECT pii.project, SUM(pii.base_net_amount) AS amount
        FROM `tabPurchase Invoice Item` pii
        JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent AND pi.docstatus = 1
        WHERE pii.project IN %(projects)s
          AND pi.posting_date >= %(from_date)s AND pi.posting_date <= %(to_date)s
        GROUP BY pii.project
    """, {"projects": erpnext_names, "from_date": from_date, "to_date": to_date})

    expenses = _query("Expense Claim", """
        SELECT project, SUM(total_sanctioned_amount) AS amount
        FROM `tabExpense Claim`
        WHERE docstatus = 1 AND project IN %(projects)s
          AND posting_date >= %(from_date)s AND posting_date <= %(to_date)s
        GROUP BY project
    """, {"projects": erpnext_names, "from_date": from_date, "to_date": to_date})

    return {
        "projects": projects,
        "invoices": invoices,
        "timesheets": timesheets,
        "purchases": purchases,
        "expenses": expenses,
    }


@frappe.whitelist()
def get_portfolio_inputs(user):
    """Raw rows for the cross-project portfolio rollup, scoped to `user`.

    Returns no derived values: no task categorisation, no health verdict, no
    completion percentages, no ordering. The gateway
    (internal/insights/portfolio.go) does all of that.

    Two things here ARE decisions rather than rows, and both are deliberately
    Frappe's to make because both are permission questions:
      - which projects appear at all (accessible_project_filter), and
      - `money_visible`, the per-project view_money verdict the gateway uses
        to null out client/budget per row. view_money is per-project in
        access.py's capability matrix, so a user with money access on ONE
        project must not see budgets for the others in the same response.

    Dates are stringified here rather than left as date objects so the wire
    format is unambiguous — the gateway parses fixed YYYY-MM-DD.
    """
    _assert_service_caller()

    from batch_projects import access
    from batch_projects.api.board import _task_filters
    from batch_projects.permissions import (
        NO_ACCESSIBLE_PROJECTS,
        accessible_project_filter,
    )

    proj_filters = accessible_project_filter({"status": "Active"}, user=user)
    if proj_filters is NO_ACCESSIBLE_PROJECTS:
        return {"projects": [], "tasks": [], "milestones": [], "money_visible": {}}

    projects = frappe.get_all(
        "BP Project",
        filters=proj_filters,
        fields=["name", "project_name", "key", "project_color", "theme",
                "health_override", "client", "lead", "start_date",
                "target_end_date", "budget_amount", "currency",
                "workflow_states", "company"],
        order_by="creation asc",
    )
    if not projects:
        return {"projects": [], "tasks": [], "milestones": [], "money_visible": {}}

    pnames = [p["name"] for p in projects]

    # Resolve lead display names here: it is a join, not a calculation, and
    # the gateway has no business knowing how Frappe stores user full names.
    leads = list({p["lead"] for p in projects if p.get("lead")})
    lead_names = {}
    if leads:
        for u in frappe.get_all("User", filters={"name": ["in", leads]},
                                fields=["name", "full_name"]):
            lead_names[u["name"]] = u["full_name"] or u["name"]

    for p in projects:
        p["lead_name"] = lead_names.get(p.get("lead"), "")
        for f in ("start_date", "target_end_date"):
            p[f] = str(p[f]) if p.get(f) else None

    tasks = frappe.get_all(
        "BP Task",
        filters=_task_filters({"project": ["in", pnames]}),
        fields=["project", "status", "due_date"],
    )
    for t in tasks:
        t["due_date"] = str(t["due_date"])[:10] if t.get("due_date") else None

    milestones = frappe.get_all(
        "BP Milestone",
        filters={"project": ["in", pnames]},
        fields=["name", "title", "status", "due_date", "project"],
    )
    for m in milestones:
        m["due_date"] = str(m["due_date"]) if m.get("due_date") else None

    return {
        "projects": projects,
        "tasks": tasks,
        "milestones": milestones,
        "money_visible": {
            p["name"]: access.has_capability(p["name"], "view_money", user=user)
            for p in projects
        },
    }
