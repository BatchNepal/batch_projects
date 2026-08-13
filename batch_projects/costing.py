"""
batch_projects/costing.py
──────────────────────────
"What did this labour actually cost" for the Money tab
(api/erp_link.py get_project_money).

⚠️ NO LONGER THE ONLY COPY. The margin report used to call this too, but its
arithmetic now lives in bp-gateway's internal/insights (margin.go's
labourCost), because the formula is a paid feature and this repo is public —
see api/insights_data.py. The two implementations MUST agree: they are the
same rule applied to the same Timesheet Detail rows, and the whole reason
this module exists is that the Money tab and the margin report once disagreed
about the cost of the same project. If you change the rule here, change
margin.go's labourCost in the same breath (its tests encode the rule).

These two screens must never compute labour cost differently for the
same project/period again — that was a real bug: the Money tab used a per-row
fallback — a Timesheet Detail row's real `costing_amount` when ERPNext had
one (an employee's configured cost rate), the project's flat `hourly_rate`
as an estimate otherwise — with a comment claiming get_margin_report used
"the same semantics". It didn't: get_margin_report summed hours first, then
multiplied the total by the flat rate, never reading costing_amount at all.
Same project, same period, two different costs — whichever real costing
existed on any row, the margin report silently discarded it.

This function is the one place that logic lives now. Both callers pass in
Timesheet Detail rows (each needs `hours` and `costing_amount`) plus the
project's flat rate.
"""


def labour_cost(rows, project_rate: float) -> float:
    """Per-row cost: real ERPNext costing_amount when present and non-zero,
    the project's flat hourly_rate as an estimate otherwise (a row with no
    employee cost configured when it was logged carries costing_amount 0).
    `rows` items are dicts / frappe._dict rows with `hours` and
    `costing_amount` (missing/None treated as 0)."""
    total = 0.0
    for r in rows:
        costing = float(r.get("costing_amount") or 0)
        hours = float(r.get("hours") or 0)
        total += costing or (hours * project_rate)
    return round(total, 2)
