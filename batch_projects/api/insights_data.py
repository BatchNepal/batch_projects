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


def _query(table_exists, sql, params):
    """Run one ERP-source query, degrading to "contributes nothing" instead of
    failing the whole report.

    Each source is optional: a bench without ERPNext, or with a module
    uninstalled, has no such table, and a report that 500s because a customer
    never installed HR is worse than one that shows no expenses. Mirrors the
    per-source try/except the previous in-Frappe implementations used.
    """
    if not frappe.db.table_exists(table_exists):
        return []
    try:
        return frappe.db.sql(sql, params, as_dict=True)
    except Exception as exc:
        frappe.log_error(f"insights_data {table_exists}: {exc}")
        return []


def _shape_sales_invoice_project_revenue_rows(rows):
    """Collapse submitted Sales Invoice Item rows by (project, invoice).

    `grand_total` is intentionally retained as the wire key consumed by the
    current gateway, but its value is PROJECT-ATTRIBUTED NET REVENUE in company
    currency, not the invoice header's grand total.

    Outstanding is still an invoice-level receivable. For a shared invoice it
    is apportioned by the same base-net share so the same unpaid balance is not
    repeated in every contributing project's Money tab.
    """
    grouped = {}

    for row in rows:
        project = row.get("project")
        invoice = row.get("name")

        if not project or not invoice:
            continue

        key = (project, invoice)

        current = grouped.setdefault(
            key,
            {
                "project": project,
                "name": invoice,
                "date": row.get("date"),
                "status": row.get("status"),
                "grand_total": 0.0,
                "outstanding_amount": 0.0,
                "conversion_rate": float(
                    row.get("conversion_rate") or 0
                ),
                "_invoice_base_net_total": float(
                    row.get("base_net_total") or 0
                ),
                "_invoice_outstanding": float(
                    row.get("outstanding_amount") or 0
                ),
            },
        )

        current["grand_total"] += float(
            row.get("base_net_amount") or 0
        )

    result = []

    for current in grouped.values():
        project_revenue = round(
            current["grand_total"],
            2,
        )

        invoice_net = current.pop(
            "_invoice_base_net_total"
        )

        invoice_outstanding = current.pop(
            "_invoice_outstanding"
        )

        if abs(invoice_net) > 1e-12:
            current["outstanding_amount"] = round(
                invoice_outstanding
                * project_revenue
                / invoice_net,
                2,
            )
        else:
            # There is no financially meaningful denominator with which to
            # allocate an invoice-level receivable to this project's lines.
            # Do not duplicate the whole invoice outstanding as a fallback.
            current["outstanding_amount"] = 0.0

        current["grand_total"] = project_revenue

        result.append(current)

    # SQL delivers invoice/date order and dict insertion order preserves it.
    return result


def _sales_invoice_project_revenue_rows(
    projects,
    from_date,
    to_date,
):
    """Submitted invoice revenue for the requested ERPNext Projects.

    Effective project is item.project first, header project only as a fallback
    for legacy/single-project invoices whose items were not explicitly tagged.

    The row-level read is intentional. A combined invoice is one legal/accounting
    document but several project revenue claims.
    """
    if not projects:
        return []

    raw = _query(
        "Sales Invoice Item",
        """
        SELECT
            COALESCE(
                NULLIF(sii.project, ''),
                si.project
            ) AS project,
            si.name,
            si.posting_date AS date,
            si.status,
            si.outstanding_amount,
            si.conversion_rate,
            si.base_net_total,
            sii.base_net_amount
        FROM `tabSales Invoice Item` sii
        JOIN `tabSales Invoice` si
          ON si.name = sii.parent
         AND si.docstatus = 1
        WHERE COALESCE(
                NULLIF(sii.project, ''),
                si.project
              ) IN %(projects)s
          AND si.posting_date >= %(from_date)s
          AND si.posting_date <= %(to_date)s
        ORDER BY
            si.posting_date DESC,
            si.name DESC,
            sii.idx ASC
        """,
        {
            "projects": tuple(projects),
            "from_date": from_date,
            "to_date": to_date,
        },
    )

    return _shape_sales_invoice_project_revenue_rows(
        raw
    )


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
    exact bug that once had the margin report and the Money tab quoting two
    different costs for one project. The gateway applies that rule to both
    surfaces now; Frappe just hands over hours + costing_amount.

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

    # Revenue follows Sales Invoice Item.project, not the invoice header.
    # Header project is only a legacy/single-project fallback. Item
    # base_net_amount is company-currency net sales: taxes/charges never become
    # project revenue.
    invoice_rows = _sales_invoice_project_revenue_rows(
        erpnext_names,
        from_date,
        to_date,
    )

    invoices = [
        {
            "project": row["project"],
            "revenue": row["grand_total"],
        }
        for row in invoice_rows
    ]

    timesheets = _query("Timesheet Detail", """
        SELECT tsd.project, tsd.hours, tsd.costing_amount
        FROM `tabTimesheet Detail` tsd
        JOIN `tabTimesheet` ts ON ts.name = tsd.parent AND ts.docstatus = 1
        WHERE tsd.project IN %(projects)s
          AND tsd.from_time >= %(from_dt)s AND tsd.from_time <= %(to_dt)s
    """, {"projects": erpnext_names, "from_dt": from_dt, "to_dt": to_dt})

    purchases = _query("Purchase Invoice Item", """
        SELECT
            COALESCE(NULLIF(pii.project, ''), pi.project) AS project,
            SUM(pii.base_net_amount) AS amount
        FROM `tabPurchase Invoice Item` pii
        JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent AND pi.docstatus = 1
        WHERE COALESCE(NULLIF(pii.project, ''), pi.project) IN %(projects)s
          AND pi.posting_date >= %(from_date)s AND pi.posting_date <= %(to_date)s
        GROUP BY COALESCE(NULLIF(pii.project, ''), pi.project)
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
def get_money_inputs(project, from_date, to_date, user):
    """Every row the Money tab is built from, for ONE project, scoped to
    `user`. Raw values only — bp-gateway's internal/insights/money.go turns
    these into the tab.

    Three gates, all of them Frappe's to answer because none is a tier
    question:
      - the project role (BP Viewer) `user` holds,
      - the per-project `view_money` capability, and
      - the workspace's own `money_tab` switch, which a workspace admin can
        turn off for everyone regardless of plan.
    The `profitability` tier gate is NOT here: that one is the gateway's, and
    re-checking it in this repo would rebuild the patchable gate this module
    exists to stop relying on.

    Two row sets are deliberately returned unaggregated even though the old
    in-Frappe version summed them in SQL, because in both cases the SUM
    carried a rule rather than just adding numbers:
      - `task_labour`, which applied the costing_amount-or-flat-rate fallback
        inside a CASE expression, and
      - `task_committed`, which applied ERPNext's non-billed formula
        (base_amount − billed × rate − returns) inside the SELECT.
    Both rules now live in money.go with the rest of the arithmetic. The
    genuinely rule-free sums (materials and expenses per task) stay grouped in
    SQL, where they only save bytes.
    """
    _assert_service_caller()

    from batch_projects import access
    from batch_projects.entitlements import require_workspace_feature

    access.require(project, "BP Viewer", user=user)
    access.require_capability(project, "view_money", user=user)
    require_workspace_feature("money_tab")

    doc = frappe.get_doc("BP Project", project)
    if not doc.erpnext_project:
        return {"linked": False, "project": project}

    erp = doc.erpnext_project
    from_dt = f"{from_date} 00:00:00"
    to_dt = f"{to_date} 23:59:59"
    window = {"proj": erp, "from_date": from_date, "to_date": to_date,
              "from_dt": from_dt, "to_dt": to_dt}

    # Currency is a lookup, not a calculation: the company's default currency,
    # falling back to the project's cosmetic one. Every amount below is a
    # base_* / company-currency figure (timesheet rates are written in company
    # currency at timer-stop), so this is the label they all carry.
    from batch_projects.api.board import _company_currency
    currency = _company_currency(doc.company) or doc.currency or "USD"

    # One legal invoice may cover several projects. The Money tab therefore
    # reads project-attributed item revenue rather than trusting the invoice's
    # single header project.
    revenue = _sales_invoice_project_revenue_rows(
        [erp],
        from_date,
        to_date,
    )

    timesheets = _query("Timesheet Detail", """
        SELECT tsd.hours, tsd.costing_amount
        FROM `tabTimesheet Detail` tsd
        JOIN `tabTimesheet` ts ON ts.name = tsd.parent AND ts.docstatus = 1
        WHERE tsd.project = %(proj)s
          AND tsd.from_time >= %(from_dt)s AND tsd.from_time <= %(to_dt)s
    """, window)

    # Unbilled and draft are all-time, not period-scoped: both answer "what is
    # outstanding right now", which a date window would silently truncate.
    unbilled = _query("Timesheet Detail", """
        SELECT tsd.hours, tsd.billing_rate
        FROM `tabTimesheet Detail` tsd
        JOIN `tabTimesheet` ts ON ts.name = tsd.parent AND ts.docstatus = 1
        WHERE tsd.project = %(proj)s AND tsd.is_billable = 1
          AND (tsd.sales_invoice IS NULL OR tsd.sales_invoice = '')
    """, {"proj": erp})

    # One row per draft Timesheet so the UI can deep-link to it. Hours logged
    # by the task timer are invisible to every submitted-only figure above
    # until submission — without this the tab reads "I just tracked 41 minutes
    # and it shows zeros".
    drafts = _query("Timesheet Detail", """
        SELECT tsd.parent AS timesheet, ts.owner,
               SUM(tsd.hours) AS hours, MAX(tsd.to_time) AS last_logged
        FROM `tabTimesheet Detail` tsd
        JOIN `tabTimesheet` ts ON ts.name = tsd.parent AND ts.docstatus = 0
        WHERE tsd.project = %(proj)s
        GROUP BY tsd.parent, ts.owner
        ORDER BY last_logged DESC
    """, {"proj": erp})

    materials = _query("Purchase Invoice", """
        SELECT name, posting_date AS date, base_grand_total AS grand_total, status
        FROM `tabPurchase Invoice`
        WHERE project = %(proj)s AND docstatus = 1
          AND posting_date >= %(from_date)s AND posting_date <= %(to_date)s
        ORDER BY posting_date DESC
    """, window)

    expenses = _query("Expense Claim", """
        SELECT name, posting_date AS date,
               total_sanctioned_amount AS amount, status
        FROM `tabExpense Claim`
        WHERE project = %(proj)s AND docstatus = 1
          AND posting_date >= %(from_date)s AND posting_date <= %(to_date)s
        ORDER BY posting_date DESC
    """, window)

    # Unbilled expenses: all-time, and a real invoiced-tracker rather than a
    # visibility-only sum — custom_sales_invoice gives Expense Claim Detail the
    # equivalent of Timesheet Detail's sales_invoice. The reinvoice policy and
    # markup travel as-is; applying them is money.go's job, and it must apply
    # them the same way generate_expense_invoice does, or this number stops
    # being what that button will actually invoice.
    unbilled_expenses = _query("Expense Claim Detail", """
        SELECT ecd.sanctioned_amount,
               IFNULL(ect.custom_reinvoice_policy, 'At Cost') AS policy,
               ect.custom_markup_percent AS markup_percent
        FROM `tabExpense Claim Detail` ecd
        JOIN `tabExpense Claim` ec ON ec.name = ecd.parent AND ec.docstatus = 1
        LEFT JOIN `tabExpense Claim Type` ect ON ect.name = ecd.expense_type
        WHERE ec.project = %(proj)s
          AND ecd.custom_is_billable = 1
          AND IFNULL(ect.custom_reinvoice_policy, 'At Cost') != 'Not Billable'
          AND (ecd.custom_sales_invoice IS NULL OR ecd.custom_sales_invoice = ''
               OR NOT EXISTS (
                   SELECT 1 FROM `tabSales Invoice` si2
                   WHERE si2.name = ecd.custom_sales_invoice AND si2.docstatus < 2
               ))
    """, {"proj": erp})

    sales_orders = _query("Sales Order", """
        SELECT name, base_grand_total AS grand_total, per_billed, status
        FROM `tabSales Order`
        WHERE project = %(proj)s AND docstatus = 1
          AND transaction_date >= %(from_date)s AND transaction_date <= %(to_date)s
        ORDER BY transaction_date DESC
    """, window)

    # ── Per-task attribution ─────────────────────────────────────────────────
    # The bp_task accounting dimension, left raw: rows with no task keep an
    # empty value here and money.go folds them into its own untasked bucket,
    # rather than this module inventing a sentinel the gateway has to know.
    task_labour = _query("Timesheet Detail", """
        SELECT tsd.custom_bp_task AS task, tsd.hours, tsd.costing_amount
        FROM `tabTimesheet Detail` tsd
        JOIN `tabTimesheet` ts ON ts.name = tsd.parent AND ts.docstatus = 1
        WHERE tsd.project = %(proj)s
          AND tsd.from_time >= %(from_dt)s AND tsd.from_time <= %(to_dt)s
    """, window)

    task_materials = _query("Purchase Invoice Item", """
        SELECT pii.bp_task AS task, SUM(pii.base_net_amount) AS amount
        FROM `tabPurchase Invoice Item` pii
        JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent AND pi.docstatus = 1
        WHERE COALESCE(NULLIF(pii.project, ''), pi.project) = %(proj)s
          AND pi.posting_date >= %(from_date)s AND pi.posting_date <= %(to_date)s
        GROUP BY 1
    """, window)

    task_expenses = _query("Expense Claim Detail", """
        SELECT ecd.bp_task AS task, SUM(ecd.sanctioned_amount) AS amount
        FROM `tabExpense Claim Detail` ecd
        JOIN `tabExpense Claim` ec ON ec.name = ecd.parent AND ec.docstatus = 1
        WHERE COALESCE(NULLIF(ecd.project, ''), ec.project) = %(proj)s
          AND ec.posting_date >= %(from_date)s AND ec.posting_date <= %(to_date)s
        GROUP BY 1
    """, window)

    # Committed spend: open Purchase Order lines, all-time. Per line, not
    # per (task, PO) as before, because the sum being taken is ERPNext's
    # non-billed formula — see the docstring.
    task_committed = _query("Purchase Order Item", """
        SELECT poi.bp_task AS task, poi.parent AS purchase_order, po.status,
               poi.base_amount, poi.billed_amt, poi.base_rate,
               IFNULL(poi.returned_qty, 0) AS returned_qty,
               IFNULL(po.conversion_rate, 1) AS conversion_rate
        FROM `tabPurchase Order Item` poi
        JOIN `tabPurchase Order` po ON po.name = poi.parent AND po.docstatus = 1
        WHERE COALESCE(NULLIF(poi.project, ''), po.project) = %(proj)s
          AND po.status NOT IN ('Closed', 'Cancelled')
    """, {"proj": erp})

    # Task display names for whatever the ERP rows referenced. A plain join,
    # and deliberately not an inner one: an ERP row may name a task belonging
    # to another project or one since deleted, and those still have to render
    # (by name) rather than vanish from a financial total.
    referenced = {
        r["task"] for r in (task_labour + task_materials + task_expenses + task_committed)
        if r.get("task")
    }
    tasks = frappe.get_all(
        "BP Task", filters={"name": ["in", list(referenced)]},
        fields=["name", "task_key", "title"],
    ) if referenced else []

    for r in drafts:
        r["last_logged"] = str(r["last_logged"]) if r.get("last_logged") else None
    for rows in (revenue, materials, expenses):
        for r in rows:
            r["date"] = str(r["date"]) if r.get("date") else None

    return {
        "linked": True,
        "project": project,
        "erpnext_project": erp,
        "currency": currency,
        "project_type": doc.project_type or "tm",
        "hourly_rate": float(doc.hourly_rate or 0),
        "budget_amount": float(doc.budget_amount or 0),
        "retainer_hours": float(doc.retainer_hours or 0),
        "revenue": revenue,
        "timesheets": timesheets,
        "unbilled": unbilled,
        "drafts": drafts,
        "materials": materials,
        "expenses": expenses,
        "unbilled_expenses": unbilled_expenses,
        "sales_orders": sales_orders,
        "task_labour": task_labour,
        "task_materials": task_materials,
        "task_expenses": task_expenses,
        "task_committed": task_committed,
        "tasks": tasks,
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
