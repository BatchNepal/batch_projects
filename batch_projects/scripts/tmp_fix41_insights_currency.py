from pathlib import Path

PATH = Path("batch_projects/api/insights_data.py")
text = PATH.read_text()


def replace_once(source, old, new, label):
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"STOP {label}: expected 1 match, found {count}")
    return source.replace(old, new, 1)


text = replace_once(
    text,
    "import frappe\n\n\ndef _assert_service_caller():",
    "import math\n\nimport frappe\n\n\ndef _assert_service_caller():",
    "import math",
)

helpers = r'''

def _money_code(value):
    """Normalize a stored money/currency identifier without inventing one."""
    return str(value or "").strip()


def _project_money_currency_context(project):
    """Resolve the one company-currency context used by analytics for a BP Project.

    ERP financial rows consumed by this module are base/company-currency values.
    BP Project.hourly_rate and budget_amount are configured in BP Project.currency.
    When those currencies differ, analytics must use an authoritative commercial
    snapshot rather than today's FX rate; source_sales_order is that snapshot.
    """
    project_name = _money_code(project.get("project_name") or project.get("name")) or "this project"
    configured_company = _money_code(project.get("company"))
    erp_project = _money_code(project.get("erpnext_project"))

    linked_company = ""
    if erp_project:
        linked_company = _money_code(
            frappe.db.get_value("Project", erp_project, "company")
        )
        if not linked_company:
            frappe.throw(
                f"Linked ERPNext Project '{erp_project}' has no Company. "
                "Set its Company before viewing financial analytics."
            )
        if configured_company and configured_company != linked_company:
            frappe.throw(
                f"'{project_name}' is configured for company '{configured_company}', "
                f"but its linked ERPNext Project '{erp_project}' belongs to "
                f"'{linked_company}'. Fix the linked ERPNext Project/company mismatch "
                "before viewing financial analytics."
            )

    company = linked_company or configured_company or _money_code(
        frappe.defaults.get_global_default("company")
    )
    if not company:
        frappe.throw(
            f"Set a Company on '{project_name}' (or configure ERPNext's global "
            "default Company) before viewing financial analytics."
        )

    company_currency = _money_code(
        frappe.get_cached_value("Company", company, "default_currency")
    )
    if not company_currency:
        frappe.throw(
            f"Company '{company}' has no Default Currency configured."
        )

    project_currency = _money_code(project.get("currency"))
    if not project_currency:
        has_money = bool(
            float(project.get("hourly_rate") or 0)
            or float(project.get("budget_amount") or 0)
        )
        if has_money:
            frappe.throw(
                f"'{project_name}' has project money values but no project currency. "
                "Set the project currency before viewing financial analytics."
            )
        project_currency = company_currency

    if project_currency == company_currency:
        return {
            "company": company,
            "company_currency": company_currency,
            "project_currency": project_currency,
            "project_currency_to_company_rate": 1.0,
        }

    source_sales_order = _money_code(project.get("source_sales_order"))
    if not source_sales_order:
        frappe.throw(
            f"'{project_name}' is configured in {project_currency} while company "
            f"'{company}' reports in {company_currency}, but there is no source Sales Order "
            "with an authoritative contract conversion rate. Link/create this project from "
            "the submitted Sales Order before using cross-currency financial analytics."
        )

    so = frappe.db.get_value(
        "Sales Order",
        source_sales_order,
        ["company", "currency", "conversion_rate"],
        as_dict=True,
    )
    if not so:
        frappe.throw(
            f"The source Sales Order '{source_sales_order}' for '{project_name}' no longer exists."
        )

    so_company = _money_code(so.get("company"))
    if so_company != company:
        frappe.throw(
            f"The source Sales Order '{source_sales_order}' belongs to company "
            f"'{so_company or '—'}', but this project reports through '{company}'."
        )

    so_currency = _money_code(so.get("currency"))
    if so_currency != project_currency:
        frappe.throw(
            f"The source Sales Order '{source_sales_order}' uses currency "
            f"'{so_currency or '—'}', but this project is configured in "
            f"'{project_currency}'."
        )

    raw_rate = so.get("conversion_rate")
    if isinstance(raw_rate, bool):
        rate = 0.0
    else:
        try:
            rate = float(raw_rate)
        except (TypeError, ValueError):
            rate = 0.0

    if not math.isfinite(rate) or rate <= 0:
        frappe.throw(
            f"The source Sales Order '{source_sales_order}' has an invalid conversion rate. "
            "Fix the Sales Order before using cross-currency financial analytics."
        )

    return {
        "company": company,
        "company_currency": company_currency,
        "project_currency": project_currency,
        "project_currency_to_company_rate": rate,
    }


def _project_money_reporting_values(project):
    """Return BP project-configured money normalized to ERP company currency."""
    ctx = _project_money_currency_context(project)
    rate = ctx["project_currency_to_company_rate"]
    return {
        "currency": ctx["company_currency"],
        "project_currency": ctx["project_currency"],
        "hourly_rate": float(project.get("hourly_rate") or 0) * rate,
        "budget_amount": float(project.get("budget_amount") or 0) * rate,
    }


def _prepare_margin_project_currencies(projects):
    """Normalize project-configured money and prove one rollup currency.

    The gateway sums the project rows into one margin summary. Adding unlike
    company currencies would be false arithmetic, so the feed refuses that
    report rather than silently returning a mixed-currency total.
    """
    prepared = [
        _project_money_reporting_values(project)
        for project in projects
    ]
    currencies = sorted({row["currency"] for row in prepared if row["currency"]})

    if len(currencies) > 1:
        frappe.throw(
            "This margin report spans different company currencies ("
            + ", ".join(currencies)
            + "). Choose projects that report in one company currency; "
              "cross-currency portfolio translation needs an explicit reporting-currency policy."
        )

    for project, values in zip(projects, prepared):
        project["project_currency"] = values["project_currency"]
        project["currency"] = values["currency"]
        project["hourly_rate"] = values["hourly_rate"]
        project["budget_amount"] = values["budget_amount"]

    return currencies[0] if currencies else None
'''

text = replace_once(
    text,
    "\ndef _shape_sales_invoice_project_revenue_rows(rows):",
    helpers + "\n\ndef _shape_sales_invoice_project_revenue_rows(rows):",
    "insert currency helpers",
)

text = replace_once(
    text,
    '        fields=["name", "project_name", "key", "project_color", "theme",\n'
    '                "project_type", "hourly_rate", "budget_amount", "retainer_hours",\n'
    '                "currency", "client", "start_date", "target_end_date",\n'
    '                "erpnext_project"],',
    '        fields=["name", "project_name", "key", "project_color", "theme",\n'
    '                "project_type", "hourly_rate", "budget_amount", "retainer_hours",\n'
    '                "currency", "client", "company", "source_sales_order",\n'
    '                "start_date", "target_end_date", "erpnext_project"],',
    "visible money project fields",
)

text = replace_once(
    text,
    "    projects = _visible_money_projects(user)\n"
    "    erpnext_names = [p[\"erpnext_project\"] for p in projects if p.get(\"erpnext_project\")]",
    "    projects = _visible_money_projects(user)\n"
    "    _prepare_margin_project_currencies(projects)\n"
    "    erpnext_names = [p[\"erpnext_project\"] for p in projects if p.get(\"erpnext_project\")]",
    "margin normalization",
)

text = replace_once(
    text,
    "    doc = frappe.get_doc(\"BP Project\", project)\n"
    "    if not doc.erpnext_project:\n"
    "        return {\"linked\": False, \"project\": project}\n\n"
    "    erp = doc.erpnext_project",
    "    doc = frappe.get_doc(\"BP Project\", project)\n"
    "    if not doc.erpnext_project:\n"
    "        return {\"linked\": False, \"project\": project}\n\n"
    "    reporting = _project_money_reporting_values(doc)\n"
    "    erp = doc.erpnext_project",
    "money normalization",
)

text = replace_once(
    text,
    "    # Currency is a lookup, not a calculation: the company's default currency,\n"
    "    # falling back to the project's cosmetic one. Every amount below is a\n"
    "    # base_* / company-currency figure (timesheet rates are written in company\n"
    "    # currency at timer-stop), so this is the label they all carry.\n"
    "    from batch_projects.api.board import _company_currency\n"
    "    currency = _company_currency(doc.company) or doc.currency or \"USD\"\n\n",
    "",
    "remove cosmetic currency lookup",
)

text = replace_once(
    text,
    '        "currency": currency,\n'
    '        "project_type": doc.project_type or "tm",\n'
    '        "hourly_rate": float(doc.hourly_rate or 0),\n'
    '        "budget_amount": float(doc.budget_amount or 0),',
    '        "currency": reporting["currency"],\n'
    '        "project_currency": reporting["project_currency"],\n'
    '        "project_type": doc.project_type or "tm",\n'
    '        "hourly_rate": reporting["hourly_rate"],\n'
    '        "budget_amount": reporting["budget_amount"],',
    "money response normalized values",
)

PATH.write_text(text)
print("FIX41_INSIGHTS_CURRENCY_PATCH_OK")
