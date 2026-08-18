"""
batch_projects/api/erp_link.py
────────────────────────────────
The ERP bridge: linking a BP Project to its real ERPNext Project so
the money queries (margin report, timesheets, workspace profitability,
invoice-ready) can join through a real FK instead of matching BP Project
names against ERPNext Project names (which can never match — BP Project is
autonamed field:project_name, ERPNext Project is autonamed by naming series).

Linking itself is free-tier plumbing — entitlement gates belong on the money
surfaces built on top of this, not on creating the link.
"""

import frappe
import json
import re

from frappe.utils import flt, add_days, nowdate

from batch_projects.api.board import _check_permission, _require_system_user
from batch_projects.entitlements import require_feature, require_workspace_feature
from batch_projects.billing_reservation import guard_timesheet_details


@frappe.whitelist()
def link_erpnext_project(project, erpnext_project):
    """Point an existing BP Project at an existing ERPNext Project."""
    _check_permission(project, "BP Admin")

    if not frappe.db.exists("Project", erpnext_project):
        frappe.throw(f"ERPNext Project {erpnext_project} does not exist.")

    claimed_by = frappe.db.get_value("BP Project", {"erpnext_project": erpnext_project}, "name")
    if claimed_by and claimed_by != project:
        frappe.throw(
            f"ERPNext Project {erpnext_project} is already linked to BP Project '{claimed_by}'."
        )

    doc = frappe.get_doc("BP Project", project)
    doc.erpnext_project = erpnext_project
    doc.save(ignore_permissions=True)
    doc.add_comment("Comment", f"Linked to ERPNext Project <b>{erpnext_project}</b>.")
    frappe.db.commit()
    return {"ok": True, "erpnext_project": erpnext_project}


@frappe.whitelist()
def create_and_link_erpnext_project(project):
    """One-click path when no matching ERPNext Project exists yet: create one
    from this BP Project's basics and link it.

    Sets status='Open' at creation time only. Subsequent BP Project status,
    date, and percent_complete changes are NOT written back to the linked
    ERPNext Project."""
    _check_permission(project, "BP Admin")

    doc = frappe.get_doc("BP Project", project)
    if doc.erpnext_project:
        frappe.throw(f"Already linked to ERPNext Project {doc.erpnext_project}.")

    company = doc.company or frappe.defaults.get_global_default("company")
    if not company:
        frappe.throw(
            "Set a Company on this project (or a site default Company) before "
            "creating an ERPNext Project."
        )

    erp_doc = frappe.get_doc({
        "doctype": "Project",
        "project_name": doc.project_name,
        "company": company,
        "customer": doc.client or None,
        "status": "Open",
    })
    erp_doc.insert(ignore_permissions=True)

    doc.erpnext_project = erp_doc.name
    doc.save(ignore_permissions=True)
    doc.add_comment("Comment", f"Created and linked ERPNext Project <b>{erp_doc.name}</b>.")
    frappe.db.commit()
    return {"ok": True, "erpnext_project": erp_doc.name}


@frappe.whitelist()
def unlink_erpnext_project(project):
    _check_permission(project, "BP Admin")

    doc = frappe.get_doc("BP Project", project)
    prev = doc.erpnext_project
    if not prev:
        return {"ok": True, "erpnext_project": None}

    doc.erpnext_project = None
    doc.save(ignore_permissions=True)
    doc.add_comment("Comment", f"Unlinked ERPNext Project <b>{prev}</b>.")
    frappe.db.commit()
    return {"ok": True, "erpnext_project": None}


@frappe.whitelist()
def search_erpnext_projects(txt=""):
    """Autocomplete for the link picker — matches name / project_name /
    customer. No BP project context yet at this point, so the gate is just
    "authenticated System User", same as the sibling search_erp_documents."""
    _require_system_user()

    rows = frappe.get_all(
        "Project",
        or_filters=(
            [["name", "like", f"%{txt}%"], ["project_name", "like", f"%{txt}%"],
             ["customer", "like", f"%{txt}%"]]
            if txt else []
        ),
        fields=["name", "project_name", "customer", "status"],
        limit=20,
        order_by="modified desc",
    )
    already_linked = set(frappe.get_all(
        "BP Project", filters={"erpnext_project": ["is", "set"]}, pluck="erpnext_project"
    ))
    return [
        {
            "name":           r["name"],
            "project_name":   r.get("project_name") or r["name"],
            "customer":       r.get("customer") or "",
            "status":         r.get("status") or "",
            "already_linked": r["name"] in already_linked,
        }
        for r in rows
    ]


# ─── Work arrives from sales ─────────────────────────────────────────────────

def _dedupe_project_name(base_name: str, so_name: str) -> str:
    """BP Project is autonamed field:project_name, so the name must be
    globally unique. A Sales Order's title defaults to just the customer
    name (Frappe's stock behaviour), so using it as-is collides with any
    other project for that customer — surfacing as a raw DuplicateEntryError
    ("BP Project {customer_name} already exists"). Disambiguate with the SO
    name, then fall back to a counter for the pathological case where even
    that's taken."""
    name = (base_name or "").strip() or "Untitled Project"
    if not frappe.db.exists("BP Project", {"project_name": name}):
        return name

    name = f"{name} — {so_name}"
    if not frappe.db.exists("BP Project", {"project_name": name}):
        return name

    n = 2
    candidate = f"{name} ({n})"
    while frappe.db.exists("BP Project", {"project_name": candidate}):
        n += 1
        candidate = f"{name} ({n})"
    return candidate


def _derive_project_key(source_name: str) -> str:
    """Same convention as the create-project UI (useCreateProject.js): first
    5 chars of a single word, or initials of multiple words (up to 6 chars).
    Server-side collision handling since there's no human here to fix it."""
    words = [w for w in re.split(r"\s+", (source_name or "").strip()) if w]
    if len(words) <= 1:
        base = re.sub(r"[^A-Z0-9]", "", (words[0] if words else "PROJECT")[:5].upper())
    else:
        base = re.sub(r"[^A-Z0-9]", "", "".join(w[0] for w in words).upper())[:6]
    if len(base) < 2:
        base = (base + "PROJECT")[:5]

    key = base
    n = 2
    while frappe.db.exists("BP Project", {"key": key}):
        key = f"{base}{n}"
        n += 1
    return key


def _guess_project_name(so) -> str:
    """Sales Order's title field defaults to the literal string "{customer_name}"
    (sales_order.json), a token that's only ever resolved client-side when
    the form is filled in the desk UI. Any SO touched via API/import/bench
    console can carry that raw, unrendered token straight through — fall
    back to the real field instead of trusting title verbatim."""
    raw_title = (so.title or "").strip()
    title_is_unrendered_template = "{" in raw_title and "}" in raw_title
    base = so.customer_name or so.customer if (not raw_title or title_is_unrendered_template) else raw_title
    return _dedupe_project_name(base, so.name)


@frappe.whitelist()
def suggest_project_name_for_sales_order(sales_order):
    """Best-guess, already-deduped project name — powers the "Create Batch
    Project" prompt's default value so a human confirms/edits the name
    before it's committed (BP Project is autonamed field:project_name, so
    it must be globally unique)."""
    so = frappe.get_doc("Sales Order", sales_order)
    so.check_permission("read")
    return _guess_project_name(so)


@frappe.whitelist()
def create_project_from_sales_order(sales_order, template=None, tasks_from_items=1, project_name=None):
    """Odoo's service_tracking, our way: one click on a submitted Sales Order
    creates a BP Project (+ its linked ERPNext Project), pre-populated from
    the SO's line items (or a project template), and stamps the SO both ways.
    Idempotent — a second call on an already-stamped SO refuses with the
    existing project named."""
    _require_system_user()
    require_feature("integrations")

    so = frappe.get_doc("Sales Order", sales_order)
    so.check_permission("write")  # about to stamp it; write implies read

    if so.docstatus != 1:
        frappe.throw("The Sales Order must be submitted first.")
    if so.custom_bp_project:
        frappe.throw(f"Already linked to Batch Project '{so.custom_bp_project}'.")

    from batch_projects.api.board import create_project, create_task
    from batch_projects.setup.project_templates import expand_template

    # A human-supplied name (from the "Create Batch Project" prompt) is
    # trusted as-is, modulo the same uniqueness dedupe every name goes
    # through — it can still collide with a project created since the
    # prompt was shown.
    project_name = (
        _dedupe_project_name(project_name.strip(), so.name)
        if project_name and project_name.strip()
        else _guess_project_name(so)
    )

    workflow_states = issue_types = enabled_views = template_used = None
    seed_from_items = bool(int(tasks_from_items or 0)) and not template

    if template:
        tpl = expand_template(template)
        workflow_states = json.dumps(tpl["workflow_states"])
        issue_types = json.dumps(tpl["issue_types"])
        enabled_views = json.dumps(tpl["views"])
        template_used = tpl["id"]

    created = create_project(
        project_name=project_name,
        key=_derive_project_key(project_name),
        project_type="tm",
        client=so.customer,
        company=so.company,
        currency=so.currency,
        workflow_states=workflow_states,
        issue_types=issue_types,
        enabled_views=enabled_views,
        template_used=template_used,
    )
    bp_project = created["name"]

    # Reuses the 8A one-click path — creates + links a real ERPNext Project.
    link_result = create_and_link_erpnext_project(bp_project)

    # Stamp both sides.
    frappe.db.set_value("BP Project", bp_project, "source_sales_order", so.name, update_modified=False)
    so.db_set("custom_bp_project", bp_project, update_modified=False)

    tasks_created = 0
    if seed_from_items:
        for item in so.items:
            title = item.item_name or item.item_code
            desc = f"{item.qty} × {item.uom}"
            if item.description and item.description.strip() != (item.item_name or "").strip():
                desc += f" — {item.description}"
            # Work sold on a Sales Order is billable by definition — timers
            # started on these tasks must produce billable Timesheet rows or
            # the hours never reach generate_invoice.
            create_task(project=bp_project, title=title, description=desc, billable=1)
            tasks_created += 1

    frappe.db.commit()

    return {
        "ok": True,
        "project": bp_project,
        "project_name": created["project_name"],
        "key": created["key"],
        "erpnext_project": link_result["erpnext_project"],
        "tasks_created": tasks_created,
    }


# ─── Create Project from Lead / Opportunity / Quotation ─────────────────────
# Same "Create Batch Project" button as Sales Order (above), one step earlier
# in the pipeline — a Lead or Opportunity has no committed line items or
# confirmed customer yet, so the shared core below tolerates both being
# absent. create_project_from_sales_order itself is left untouched (its own
# shipped call sites/behavior aren't part of this change); this is a new,
# parallel core the three functions below share instead of tripling the
# create+link+stamp+seed body three ways.

def _create_bp_project_from_source(*, source_doctype, source_name, source_field,
                                    client, company, currency, project_name, items=None):
    from batch_projects.api.board import create_project, create_task

    # create_project() requires a client for any billable project_type — a
    # Lead (and some Opportunities) legitimately have no confirmed customer
    # yet, so those fall back to "internal" rather than failing outright.
    # Once a real client IS known (Opportunity/Quotation with a Customer
    # party), it's billable ("tm") from the start, same as the Sales Order path.
    created = create_project(
        project_name=project_name,
        key=_derive_project_key(project_name),
        project_type="tm" if client else "internal",
        client=client,
        company=company,
        currency=currency,
    )
    bp_project = created["name"]

    # Reuses the 8A one-click path — creates + links a real ERPNext Project.
    link_result = create_and_link_erpnext_project(bp_project)

    # Stamp both sides. frappe.db.set_value bypasses controller validation/
    # docstatus checks (same reason create_project_from_sales_order uses
    # so.db_set) — a submitted Quotation must still be stampable.
    frappe.db.set_value("BP Project", bp_project, source_field, source_name, update_modified=False)
    frappe.db.set_value(source_doctype, source_name, "custom_bp_project", bp_project, update_modified=False)

    tasks_created = 0
    for item in (items or []):
        create_task(
            project=bp_project,
            title=item["title"],
            description=item.get("description", ""),
            billable=1,
        )
        tasks_created += 1

    frappe.db.commit()

    return {
        "ok": True,
        "project": bp_project,
        "project_name": created["project_name"],
        "key": created["key"],
        "erpnext_project": link_result["erpnext_project"],
        "tasks_created": tasks_created,
    }


@frappe.whitelist()
def suggest_project_name_for_lead(lead):
    doc = frappe.get_doc("Lead", lead)
    doc.check_permission("read")
    base = doc.company_name or doc.lead_name or "Lead"
    return _dedupe_project_name(base, doc.name)


@frappe.whitelist()
def create_project_from_lead(lead, project_name=None):
    """A Lead is pre-sales — no confirmed Customer, no line items, so the
    project starts as an empty scaffold (client left blank; Lead.customer
    means "came FROM this existing customer", not "bill this customer", so
    it's deliberately not used here) and the Lead itself just gets tagged."""
    _require_system_user()
    require_feature("integrations")

    doc = frappe.get_doc("Lead", lead)
    doc.check_permission("write")
    if doc.custom_bp_project:
        frappe.throw(f"Already linked to Batch Project '{doc.custom_bp_project}'.")

    base = doc.company_name or doc.lead_name or "Lead"
    project_name = (
        _dedupe_project_name(project_name.strip(), doc.name)
        if project_name and project_name.strip()
        else _dedupe_project_name(base, doc.name)
    )

    return _create_bp_project_from_source(
        source_doctype="Lead", source_name=doc.name, source_field="source_lead",
        client=None, company=doc.company, currency=None, project_name=project_name,
    )


@frappe.whitelist()
def suggest_project_name_for_opportunity(opportunity):
    doc = frappe.get_doc("Opportunity", opportunity)
    doc.check_permission("read")
    base = doc.customer_name or doc.party_name or "Opportunity"
    return _dedupe_project_name(base, doc.name)


@frappe.whitelist()
def create_project_from_opportunity(opportunity, tasks_from_items=1, project_name=None):
    _require_system_user()
    require_feature("integrations")

    doc = frappe.get_doc("Opportunity", opportunity)
    doc.check_permission("write")
    if doc.custom_bp_project:
        frappe.throw(f"Already linked to Batch Project '{doc.custom_bp_project}'.")

    base = doc.customer_name or doc.party_name or "Opportunity"
    project_name = (
        _dedupe_project_name(project_name.strip(), doc.name)
        if project_name and project_name.strip()
        else _dedupe_project_name(base, doc.name)
    )

    # party_name is a Dynamic Link (opportunity_from decides Lead vs
    # Customer) — BP Project.client is a fixed Link to Customer, so it's
    # only carried across when the party actually IS a Customer.
    client = doc.party_name if doc.opportunity_from == "Customer" else None

    items = []
    if bool(int(tasks_from_items or 0)):
        for item in doc.items:
            items.append({
                "title": item.item_name or item.item_code,
                "description": item.description or "",
            })

    return _create_bp_project_from_source(
        source_doctype="Opportunity", source_name=doc.name, source_field="source_opportunity",
        client=client, company=doc.company, currency=doc.currency, project_name=project_name,
        items=items,
    )


@frappe.whitelist()
def suggest_project_name_for_quotation(quotation):
    doc = frappe.get_doc("Quotation", quotation)
    doc.check_permission("read")
    base = doc.customer_name or doc.party_name or "Quotation"
    return _dedupe_project_name(base, doc.name)


@frappe.whitelist()
def create_project_from_quotation(quotation, tasks_from_items=1, project_name=None):
    _require_system_user()
    require_feature("integrations")

    doc = frappe.get_doc("Quotation", quotation)
    doc.check_permission("write")

    if doc.docstatus != 1:
        frappe.throw("The Quotation must be submitted first.")
    if doc.custom_bp_project:
        frappe.throw(f"Already linked to Batch Project '{doc.custom_bp_project}'.")

    base = doc.customer_name or doc.party_name or "Quotation"
    project_name = (
        _dedupe_project_name(project_name.strip(), doc.name)
        if project_name and project_name.strip()
        else _dedupe_project_name(base, doc.name)
    )

    client = doc.party_name if doc.quotation_to == "Customer" else None

    items = []
    if bool(int(tasks_from_items or 0)):
        for item in doc.items:
            desc = f"{item.qty} × {item.uom}"
            if item.description and item.description.strip() != (item.item_name or "").strip():
                desc += f" — {item.description}"
            items.append({"title": item.item_name or item.item_code, "description": desc})

    return _create_bp_project_from_source(
        source_doctype="Quotation", source_name=doc.name, source_field="source_quotation",
        client=client, company=doc.company, currency=doc.currency, project_name=project_name,
        items=items,
    )


# ─── Close the loop: real invoicing ──────────────────────────────────────────

def _service_item():
    """The optional workspace-wide service item. Everything about it is
    opt-in: when it isn't configured, invoice lines stay item-less exactly
    as before."""
    try:
        item = frappe.db.get_single_value("BP Workspace Settings", "default_service_item")
    except Exception:
        return None
    return item if item and frappe.db.exists("Item", item) else None


def _price_list_rate(customer, item_code):
    """Return the customer's contracted Item Price with its currency.

    ERPNext v15 makes Item Price.price_list_rate a Currency field whose
    currency is Item Price.currency, and ItemPrice.validate() copies that
    currency from the linked Price List. Returning a naked float discards
    money type information and makes cross-currency fallback unsafe.
    """
    if not customer or not item_code:
        return None

    price_list = frappe.db.get_value(
        "Customer", customer, "default_price_list"
    )
    if not price_list:
        return None

    row = frappe.db.get_value(
        "Item Price",
        {
            "item_code": item_code,
            "price_list": price_list,
            "selling": 1,
        },
        ["price_list_rate", "currency"],
        as_dict=True,
    )
    if not row or not flt(row.price_list_rate):
        return None

    currency = (row.currency or "").strip()
    if not currency:
        frappe.throw(
            f"Item Price for '{item_code}' in Price List '{price_list}' "
            "has a rate but no currency. Fix the Price List before billing."
        )

    return frappe._dict({
        "rate": flt(row.price_list_rate),
        "currency": currency,
    })

def _resolve_project_list(project):
    """`project` accepts ONE BP Project name (every existing caller, e.g.
    ProjectMoney.vue's per-project button) or a JSON list of them (the batch
    path). Returns a de-duplicated list, order preserved."""
    if isinstance(project, (list, tuple)):
        names = list(project)
    else:
        raw = str(project or "").strip()
        if raw.startswith("["):
            try:
                names = json.loads(raw)
            except Exception:
                frappe.throw("Invalid project list.")
        else:
            names = [raw] if raw else []
    names = [n for n in dict.fromkeys(names) if n]
    if not names:
        frappe.throw("No project given to invoice.")
    return names


def _effective_project_company(project):
    """Return the ERPNext Company this BP Project actually bills through.

    BP Project.company is optional in the schema, so billing historically fell
    back to ERPNext's global default Company. Financial validation, preview and
    invoice creation must all normalize that fallback identically; otherwise a
    batch containing an explicit company and a blank company can become
    order-dependent.
    """
    explicit = (
        (project.get("company") if hasattr(project, "get")
         else getattr(project, "company", None))
        or ""
    ).strip()

    if explicit:
        return explicit

    default_company = (
        frappe.defaults.get_global_default("company")
        or ""
    ).strip()

    if default_company:
        return default_company

    project_name = (
        (project.get("project_name") if hasattr(project, "get")
         else getattr(project, "project_name", None))
        or
        (project.get("name") if hasattr(project, "get")
         else getattr(project, "name", None))
        or "this project"
    )

    frappe.throw(
        f"Set a Company on '{project_name}', or configure ERPNext's "
        "global default Company, before invoicing."
    )


def _validated_invoice_company(projects):
    """Resolve and validate the one ledger company for an invoice batch."""
    companies = sorted({
        _effective_project_company(project)
        for project in projects
    })

    if len(companies) > 1:
        frappe.throw(
            "These projects belong to different companies ("
            + ", ".join(companies)
            + ") — one invoice can only post to one company."
        )

    # projects is non-empty by generate_invoice contract.
    return companies[0]


def _authoritative_billing_hours(row):
    """Return persisted Timesheet Detail.billing_hours for financial use.

    ERPNext v15 normal Timesheet validation already materializes
    billing_hours from worked hours for billable rows when appropriate.
    Financial code must therefore consume the persisted value directly:
    a stored 0 is 0, not a signal to infer worked hours again.
    """
    value = row.get("billing_hours") if hasattr(row, "get") else getattr(row, "billing_hours", None)
    return flt(value)


def _requires_billing_rate(row):
    """A zero-billing-hours row has no amount that requires pricing."""
    return _authoritative_billing_hours(row) != 0


def _resolve_invoice_currency(company, customer, currency, conversion_rate,
                               project_currency=None):
    """Decide the invoice currency and its FX rate, or refuse.

    Order: explicit override -> the PROJECT's own currency ->
    Customer.default_currency -> company currency.

    The project's currency comes before the customer's and the company's
    because BP Project.hourly_rate is denominated in BP Project.currency.
    When that project rate is selected as a fallback, the invoice must keep
    the number and its unit together or explicitly convert it. Timesheet row
    rates are typed separately by their parent Timesheet.currency.
    The override exists for the payment-first case (money already landed in a
    known foreign amount; the invoice must state that exact currency/rate
    rather than have one guessed for it).

    When the result differs from company currency we need a conversion rate.
    If none is given and ERPNext has no Currency Exchange record for the pair,
    we THROW rather than silently falling back to company currency — the old
    behaviour did exactly that, producing an invoice denominated in the wrong
    currency at face value. A loud refusal is recoverable; a wrong invoice
    that someone submits is not."""
    company_currency = frappe.get_cached_value("Company", company, "default_currency")
    target = (
        currency
        or project_currency
        or frappe.db.get_value("Customer", customer, "default_currency")
        or company_currency
    )
    if target == company_currency:
        return company_currency, target, 1.0

    if conversion_rate:
        return company_currency, target, flt(conversion_rate)

    from erpnext.setup.utils import get_exchange_rate
    try:
        fx = get_exchange_rate(target, company_currency, nowdate())
    except Exception:
        fx = None
    if not fx:
        frappe.throw(
            f"This invoice would be in {target} but the company books in "
            f"{company_currency}, and no exchange rate is configured for "
            f"{target} → {company_currency}. Add a Currency Exchange record, or "
            f"pass an explicit conversion_rate (the payment-first flow, where "
            f"the received amount and rate are already known)."
        )
    return company_currency, target, flt(fx)


def _convert_billing_rate(
    rate,
    source_currency,
    target_currency,
    company,
    customer,
    *,
    company_currency=None,
    target_to_company=None,
    fx_cache=None,
):
    """Restate one typed billing rate into target_currency.

    All FX is expressed as currency -> company currency. Cross-currency
    conversion is therefore:

        amount_in_target =
            amount_in_source
            * source_to_company
            / target_to_company

    A non-zero rate without a source currency is invalid money and is
    refused rather than relabelled.
    """
    value = flt(rate)
    if not value:
        return 0.0

    source = (source_currency or "").strip()
    target = (target_currency or "").strip()

    if not source:
        frappe.throw(
            "A non-zero billing rate has no source currency. "
            "Set the project's/Price List's currency before billing."
        )
    if not target:
        frappe.throw(
            "Cannot calculate a billing rate because the invoice currency "
            "could not be resolved."
        )

    if source == target:
        return value

    company_currency = (
        (company_currency or "").strip()
        or frappe.get_cached_value(
            "Company", company, "default_currency"
        )
    )
    if not company_currency:
        frappe.throw(
            f"Company '{company}' has no Default Currency configured."
        )

    def to_company(currency_code):
        if currency_code == company_currency:
            return 1.0

        if (
            currency_code == target
            and target_to_company not in (None, "")
        ):
            resolved = flt(target_to_company)
            if resolved > 0:
                return resolved

        key = (company, currency_code)
        if fx_cache is not None and key in fx_cache:
            return fx_cache[key]

        cc, tc, resolved = _resolve_invoice_currency(
            company,
            customer,
            currency_code,
            None,
        )
        resolved = flt(resolved)

        if cc != company_currency or tc != currency_code or resolved <= 0:
            frappe.throw(
                f"Could not resolve a valid exchange rate for "
                f"{currency_code} → {company_currency}."
            )

        if fx_cache is not None:
            fx_cache[key] = resolved

        return resolved

    source_fx = to_company(source)
    target_fx = to_company(target)

    if source_fx <= 0 or target_fx <= 0:
        frappe.throw(
            f"Cannot convert billing rate from {source} to {target}: "
            "the required exchange rate is invalid."
        )

    return flt(value * source_fx / target_fx)


def _effective_billing_rate(
    *,
    row_rate,
    row_currency,
    project_rate,
    project_currency,
    client_rate,
    company_currency,
    target_currency,
    company,
    customer,
    target_to_company=None,
    fx_cache=None,
):
    """Resolve most-specific rate and preserve its source currency.

    Hierarchy:
      1. Timesheet row rate      -> Timesheet.currency
      2. BP Project hourly rate  -> BP Project.currency
      3. ERPNext Item Price      -> Item Price.currency

    Timer-created Timesheets are deliberately kept in company currency,
    but rows entered directly in ERPNext may legitimately use another
    Timesheet currency. Never infer their unit from the project/company.
    """
    row_value = flt(row_rate)
    project_value = flt(project_rate)

    client_value = 0.0
    client_currency = None
    if client_rate and hasattr(client_rate, "get"):
        client_value = flt(client_rate.get("rate"))
        client_currency = client_rate.get("currency")

    if row_value:
        value = row_value
        source_currency = row_currency
    elif project_value:
        value = project_value
        source_currency = project_currency
    elif client_value:
        value = client_value
        source_currency = client_currency
    else:
        return 0.0

    return _convert_billing_rate(
        value,
        source_currency,
        target_currency,
        company,
        customer,
        company_currency=company_currency,
        target_to_company=target_to_company,
        fx_cache=fx_cache,
    )


def _validate_invoice_period_contract(period):
    """Reject unsupported date-scoped invoice requests.

    Invoice selection is intentionally the all-time currently-unbilled
    billable balance. Keeping `period` in generate_invoice's public Python
    signature lets legacy/external callers fail with an explicit financial
    contract error instead of having the value silently ignored.
    """
    if period is None:
        return

    if isinstance(period, str) and not period.strip():
        return

    frappe.throw(
        "Period-scoped invoice generation is not supported. "
        "Omit 'period' to invoice all currently-unbilled billable hours. "
        "Use the task filter when you need to invoice specific approved work."
    )


@frappe.whitelist()
def generate_invoice(project, period=None, tasks=None,
                      currency=None, conversion_rate=None, amount=None):
    """Draft Sales Invoice from every currently-unbilled billable Timesheet
    Detail row against the given project(s) — one item line per BP task.

    `project` is ONE BP Project name (unchanged for every existing caller) or
    a JSON list of them. The list form is the recurring/AMC billing pattern:
    N projects bundled into ONE invoice, each line tagged to its own ERPNext
    Project through the native `Sales Invoice Item.project` field — which is
    what keeps the invoice traceable back to each contributing project rather
    than collapsing into one opaque total. ERPNext then does the rest itself:
    Sales Invoice.update_project() derives its unique project set from those
    ITEM-level values and calls update_billed_amount() on each, and
    get_gl_entries uses `item.project or self.project`, so every contributing
    project's billed figure and GL rows stay correct with no extra work here.

    The header `project` field is set only when invoicing exactly one project.
    Leaving it blank for a batch is deliberate: a single header project would
    be a lie about the other N-1, and it also keeps ERPNext's validate_proj_cust
    (which only fires when a header project is set) from rejecting the invoice.

    `period` remains in the public signature only for compatibility with
    older/external callers. Period-scoped invoice generation is not currently
    implemented: any non-empty value is rejected explicitly below. Omitting it
    invoices the same all-time currently-unbilled balance shown by the Money
    tab's Unbilled figure.

    Draft only — submission (and the ERPNext-side billed-hours writeback
    that follows from it) stays a deliberate human act in ERPNext. Mirrors
    erpnext/projects/doctype/timesheet/timesheet.py's make_sales_invoice
    rather than reinventing the Timesheet <-> Sales Invoice linkage."""
    project_names = _resolve_project_list(project)
    from batch_projects import access
    for _p in project_names:
        _check_permission(_p, "BP Admin")
        access.require_capability(_p, "view_money")
    require_feature("billing_writeback")

    # Financial selectors must never be accepted and then ignored. Validate
    # this before candidate SQL, source reservation, pricing or draft creation.
    _validate_invoice_period_contract(period)

    docs = [frappe.get_doc("BP Project", p) for p in project_names]
    doc = docs[0]

    unlinked = [d.project_name for d in docs if not d.erpnext_project]
    if unlinked:
        frappe.throw(
            "Link these to an ERPNext Project before invoicing: " + ", ".join(unlinked)
        )
    clientless = [d.project_name for d in docs if not d.client]
    if clientless:
        frappe.throw("Set a Client on these before invoicing: " + ", ".join(clientless))

    # One invoice bills exactly one customer, in one company — otherwise the
    # bundle would silently bill customer A for customer B's hours, or post
    # across two companies' ledgers. Refuse rather than guess.
    clients = sorted({d.client for d in docs})
    if len(clients) > 1:
        frappe.throw(
            "These projects belong to different clients (" + ", ".join(clients) +
            ") — one invoice can only bill one client."
        )
    # A Sales Invoice belongs to exactly one ERPNext ledger company.
    # Normalize optional BP Project.company through the global default BEFORE
    # candidate SQL so blank-company projects cannot make this choice depend
    # on project order.
    company = _validated_invoice_company(docs)

    # Rates are denominated in each project's own currency, so bundling
    # projects that disagree would put numbers in different units on the same
    # invoice with a single currency label — silently wrong money.
    proj_currencies = sorted({(d.currency or "").strip() for d in docs if (d.currency or "").strip()})
    if len(proj_currencies) > 1:
        frappe.throw(
            "These projects are priced in different currencies (" +
            ", ".join(proj_currencies) + ") — one invoice can only be in one "
            "currency. Invoice them separately, or pass an explicit currency "
            "and conversion_rate."
        )

    erp_projects = [d.erpnext_project for d in docs]
    project_rate_by_erp = {
        d.erpnext_project: frappe._dict({
            "rate": flt(d.hourly_rate or 0),
            "currency": (d.currency or "").strip() or None,
        })
        for d in docs
    }
    name_by_erp = {d.erpnext_project: d.project_name for d in docs}
    multi = len(docs) > 1

    # The approval guard: a task someone has actually routed for sign-off and
    # not yet cleared must not be billed. Deliberately keyed on the two
    # blocking states rather than on "is Approved" — BP Task.approval_status
    # defaults to "Approval Not Required" (and legacy rows can be blank), so
    # requiring "Approved" would silently block every ordinary task in every
    # workspace that has never used approvals at all. Rows with no linked BP
    # Task (time logged outside a task) don't join and pass through unchanged.
    # `tasks` restricts the invoice to specific BP Tasks. This is the
    # change-order / "extras" path: an approved add-on gets signed off and
    # billed on its own cycle, separately from whatever the project's main
    # billing cadence is — without inventing a change-order doctype, since a
    # change order here IS just a task someone approved.
    task_filter = _resolve_project_list(tasks) if tasks else None
    rows = frappe.db.sql(
        """
        SELECT tsd.name, tsd.parent AS timesheet, tsd.custom_bp_task AS bp_task,
               tsd.hours, tsd.billing_hours, tsd.billing_rate, tsd.billing_amount,
               ts.currency AS timesheet_currency,
               tsd.activity_type, tsd.description, tsd.from_time, tsd.to_time,
               tsd.project_name, tsd.project AS erp_project
        FROM `tabTimesheet Detail` tsd
        JOIN `tabTimesheet` ts ON ts.name = tsd.parent AND ts.docstatus = 1
        LEFT JOIN `tabBP Task` bt ON bt.name = tsd.custom_bp_task
        WHERE tsd.project IN %(projs)s
          AND tsd.is_billable = 1
          AND (tsd.sales_invoice IS NULL OR tsd.sales_invoice = '')
          AND IFNULL(bt.approval_status, '') NOT IN ('Pending', 'Rejected')
          {task_clause}
        ORDER BY tsd.from_time ASC
        """.format(task_clause="AND tsd.custom_bp_task IN %(tasks)s" if task_filter else ""),
        {"projs": tuple(erp_projects),
         "tasks": tuple(task_filter) if task_filter else None},
        as_dict=True,
    )
    if not rows:
        frappe.throw(
            "Nothing to invoice — no unbilled billable hours "
            + ("on these projects." if multi else "on this project.")
            + " (Hours on tasks awaiting or refused approval are held back.)"
        )

    # Serialize the exact financial source rows before any pricing or draft
    # construction. These FOR UPDATE locks remain owned by this transaction
    # until the Sales Invoice is inserted and the explicit commit near the end
    # of this method completes. A second overlapping request therefore waits,
    # then re-checks current committed state rather than minting another draft.
    guard_timesheet_details(
        [r.name for r in rows],
        enforce_all_sources=True,
    )

    # Same billing_rate-or-project-rate fallback the Money tab's unbilled
    # figure already uses (bp-gateway internal/insights/money.go) — a row with billing_rate=0 (e.g. a Timesheet Detail
    # entered directly in ERPNext, outside the task timer, before a rate was
    # set) must price the same way here as it did in the number the human
    # saw on the button they just clicked, or it gets silently invoiced for
    # $0 and permanently marked billed for real hours worked.
    # ── Rate resolution, most-specific first ──────────────────────────────
    #   1. the row's own captured billing_rate (set at timer-stop)
    #   2. that row's OWN project's hourly_rate — never a single project's,
    #      since in a batch each row can come from a different project and
    #      pricing them all off the first would misprice the rest
    #   3. the CLIENT's contracted rate: Customer.default_price_list ->
    #      Item Price for the service item. This is ERPNext's native rate
    #      card, read not duplicated — the "one negotiation, applies to every
    #      project for a year" case.
    #   4. nothing -> 0, and the caller is told rather than silently billing
    #      real hours at zero (see the zero-rate guard below).
    # Resolved BEFORE rates are priced: converting any typed source rate
    # into the invoice's currency needs to know that target currency
    # first. Decided explicitly, never defaulted silently — see
    # _resolve_invoice_currency() for why falling back to company currency
    # was actively wrong for foreign clients.
    # `company` was normalized and validated across every selected project
    # above. Never derive it again from the first project.
    company_currency, inv_currency, fx = _resolve_invoice_currency(
        company, doc.client, currency, conversion_rate,
        project_currency=(proj_currencies[0] if proj_currencies else None),
    )

    service_item = _service_item()
    client_rate = _price_list_rate(doc.client, service_item)
    rate_fx_cache = {}

    for r in rows:
        project_rate = project_rate_by_erp.get(
            r.erp_project, frappe._dict()
        )

        eff_rate = _effective_billing_rate(
            row_rate=r.billing_rate,
            row_currency=r.timesheet_currency,
            project_rate=project_rate.get("rate"),
            project_currency=project_rate.get("currency"),
            client_rate=client_rate,
            company_currency=company_currency,
            target_currency=inv_currency,
            company=company,
            customer=doc.client,
            target_to_company=fx,
            fx_cache=rate_fx_cache,
        )

        r.eff_rate = eff_rate
        r.eff_amount = round(
            _authoritative_billing_hours(r) * eff_rate, 2
        )

    # Billing non-zero hours without a rate would permanently mark real work
    # billed for nothing. A zero-billing-hours row has no amount to price,
    # however, so it must not be blocked solely because no rate is configured.
    zero_rate_projects = sorted({
        name_by_erp.get(r.erp_project, r.erp_project)
        for r in rows
        if _requires_billing_rate(r) and not r.eff_rate
    })
    if zero_rate_projects:
        frappe.throw(
            "No billing rate resolved for: " + ", ".join(zero_rate_projects) +
            ". Set an hourly rate on the project, or a Price List rate for the "
            "client, before invoicing — billing hours at zero can't be undone."
        )

    # Grouped by (project, task): one line per task, never merging the same
    # task key across projects, so each line can carry its own project tag.
    by_task = {}
    for r in rows:
        by_task.setdefault((r.erp_project, r.bp_task or ""), []).append(r)

    task_meta = {
        t.name: t for t in frappe.get_all(
            "BP Task", filters={"name": ["in", [k[1] for k in by_task if k[1]]]},
            fields=["name", "task_key", "title"],
        )
    }

    income_account = frappe.db.get_value("Company", company, "default_income_account")
    if not income_account:
        frappe.throw(f"Set a Default Income Account on Company '{company}' before invoicing.")

    si = frappe.new_doc("Sales Invoice")
    si.customer = doc.client
    si.company = company

    # The header `project` MUST be set, even on a batch where it is
    # semantically ambiguous — this is a safety measure against a real
    # ERPNext behaviour, not a modelling choice.
    #
    # Sales Invoice.update_time_sheet_detail() (accounts/doctype/
    # sales_invoice/sales_invoice.py) stamps timesheet rows on submit as:
    #
    #     if ((self.project and args.timesheet_detail == data.name)
    #         or (not self.project and not data.sales_invoice) ...)
    #
    # With a blank header project, the second branch fires and stamps
    # `sales_invoice` onto EVERY not-yet-billed time log in every timesheet
    # this invoice touches — including logs belonging to projects outside
    # this batch, to other customers entirely, and even non-billable logs
    # (it never checks is_billable). Those hours are then permanently
    # unbillable. That's the long-standing partial-timesheet bug reported as
    # frappe/erpnext#44167.
    #
    # Setting the header keeps stamping on the precise first branch —
    # exactly the timesheet_detail rows we actually put on this invoice.
    # Cross-project traceability is unaffected: it rides on the per-ITEM
    # project tags below, and update_project() unions header + item projects
    # before calling update_billed_amount() on each, so every contributing
    # project is still updated correctly.
    si.project = doc.erpnext_project
    if multi:
        # ...and say plainly on the document what the header alone implies
        # wrongly, so a human reading the invoice sees the real scope.
        si.remarks = "Covers projects: " + ", ".join(
            f"{name_by_erp[e]} ({e})" for e in erp_projects
        )

    si.currency = inv_currency
    si.conversion_rate = fx
    # Timesheet amounts are already in company currency (billing_rate/
    # costing_rate were set in company currency at timer-stop time) — forcing
    # the project's own currency here throws when there's no exchange rate
    # configured for it. Let set_missing_values default to company currency.

    for (erp_project, bp_task), task_rows in by_task.items():
        hours = round(sum(_authoritative_billing_hours(r) for r in task_rows), 2)
        # NOT `amount` — that's this function's own parameter (the
        # payment-first expected total). Reusing the name here silently
        # overwrote it with the last line's subtotal, so the assertion below
        # always compared a value against itself and never fired.
        line_amount = round(sum(r.eff_amount for r in task_rows), 2)
        rate = round(line_amount / hours, 4) if hours else 0
        meta = task_meta.get(bp_task)
        description = f"{meta.task_key} — {meta.title}" if meta else "Other billable time"
        # On a batch the client is reading one invoice covering several jobs —
        # name the project on every line, or the bundle is untraceable on the
        # printed document even though the FK is right in the database.
        if multi:
            description = f"{name_by_erp.get(erp_project, erp_project)}: {description}"
        line = {
            "item_name": description,
            "description": description,
            # BP Task accounting dimension (9A) — item-level value wins over
            # the header in get_base_gl_dict, so this task lands on the GL
            # row. Untasked "Other billable time" rows stay unstamped.
            "bp_task": bp_task or None,
            # The traceability FK. Native Sales Invoice Item field — drives
            # both update_billed_amount() per project and the GL row's project.
            "project": erp_project,
            "qty": hours,
            "uom": "Hour",
            "rate": rate,
            # Without an item_code set_missing_values has nothing to fetch
            # this from — set it explicitly or the row fails GL posting.
            "income_account": income_account,
        }
        # item_code is opt-in but load-bearing where it's configured: India
        # Compliance defines Sales Invoice Item.gst_hsn_code with
        # fetch_from="item_code.gst_hsn_code", and validate_hsn_codes()
        # hard-throws on submit for any row with a missing HSN. An item-less
        # line therefore produces an invoice a GST-registered Indian company
        # literally cannot submit. Setting it also lets ERPNext apply the
        # customer's Item Price / tax template natively.
        if service_item:
            line["item_code"] = service_item
        si.append("items", line)

    for r in rows:
        si.append("timesheets", {
            "time_sheet": r.timesheet,
            "timesheet_detail": r.name,
            "billing_hours": _authoritative_billing_hours(r),
            "billing_amount": r.eff_amount,
            "activity_type": r.activity_type,
            "description": r.description,
            "from_time": r.from_time,
            "to_time": r.to_time,
            "project_name": r.project_name,
        })

    # batch_projects has already authorized this call in full (BP Admin on
    # every project, view_money capability, billing_writeback entitlement, and
    # the gateway signature). ERPNext's set_missing_values then does its OWN
    # check: selling_controller.set_missing_lead_customer_details() calls
    # _get_party_details(ignore_permissions=self.flags.ignore_permissions),
    # which throws PermissionError unless the user can read Customer.
    # Delivery-team users deliberately hold no native ERPNext role
    # permissions, so without this flag every real (non-Administrator) user
    # gets a bare 403 from the UI while it works fine from bench. Setting it
    # asserts "authorization already happened upstream" — the same posture as
    # the insert(ignore_permissions=True) that follows.
    si.flags.ignore_permissions = True
    si.run_method("set_missing_values")
    # set_missing_values can re-derive currency/rate from the price list; the
    # caller's explicit choice must survive it (that's the whole point of the
    # payment-first override).
    si.currency = inv_currency
    si.conversion_rate = fx

    # `amount` is an ASSERTION, not a fudge factor. In the payment-first flow
    # the money has already landed, and an invoice that doesn't match it to
    # the decimal is the failure mode being guarded against. If the computed
    # total differs we refuse and show both numbers, so a human fixes the
    # rates/hours — rather than silently writing an invoice that reconciles
    # against nothing.
    if amount not in (None, ""):
        expected = flt(amount)
        # From our own resolved rows, NOT si.items — item `amount` is only
        # populated by calculate_taxes_and_totals() during validate(), which
        # hasn't run yet at this point, so reading it here always yields 0.
        computed = round(sum(r.eff_amount for r in rows), 2)
        if abs(computed - expected) > 0.01:
            frappe.throw(
                f"Computed total {computed} {inv_currency} does not match the "
                f"expected {expected} {inv_currency}. Nothing was created. "
                "Adjust the hours or rates so the invoice matches the amount "
                "actually received, then try again."
            )

    si.insert(ignore_permissions=True)
    # ProjectMoney.vue's "Open" toast action deep-links straight to
    # /app/sales-invoice/<name> — SPA members hold zero native ERPNext role
    # by design, so grant the one document they just legitimately created.
    frappe.share.add_docshare(
        "Sales Invoice", si.name, frappe.session.user, read=1,
        flags={"ignore_share_permission": True})
    frappe.db.commit()

    return {
        "ok": True,
        "sales_invoice": si.name,
        "currency": si.currency,
        "conversion_rate": si.conversion_rate,
        "grand_total": si.grand_total,
        "hours_invoiced": round(sum(_authoritative_billing_hours(r) for r in rows), 2),
        # Per-project breakdown of what went onto this one invoice — the
        # batch caller needs it to show "6 projects, $600" without re-querying.
        "projects": [
            {
                "bp_project": d.name,
                "project_name": d.project_name,
                "erpnext_project": d.erpnext_project,
                "amount": round(
                    sum(r.eff_amount for r in rows if r.erp_project == d.erpnext_project), 2
                ),
                "hours": round(
                    sum(_authoritative_billing_hours(r) for r in rows
                        if r.erp_project == d.erpnext_project), 2
                ),
            }
            for d in docs
        ],
    }


@frappe.whitelist()
def get_batch_invoice_candidates():
    """Everything invoiceable right now, grouped by client — the data behind
    the batch-invoicing screen.

    Deliberately mirrors generate_invoice's own filters (submitted timesheets,
    billable, unbilled, approval not Pending/Rejected) so the screen can never
    offer something that would then be refused, or hide something that would
    be billed. Rate resolution uses the same hierarchy too, so the amount
    shown is the amount that will be invoiced."""
    require_feature("billing_writeback")
    _require_system_user()

    from batch_projects.permissions import get_accessible_projects
    accessible = get_accessible_projects()

    projects = frappe.get_all(
        "BP Project",
        filters={"erpnext_project": ["is", "set"], "client": ["is", "set"]},
        fields=["name", "project_name", "client", "company", "currency",
                "hourly_rate", "erpnext_project"],
    )
    if accessible is not None:
        projects = [p for p in projects if p.name in accessible]
    if not projects:
        return []

    by_erp = {p.erpnext_project: p for p in projects}
    rows = frappe.db.sql(
        """
        SELECT tsd.project AS erp_project, tsd.hours, tsd.billing_hours,
               tsd.billing_rate, ts.currency AS timesheet_currency
        FROM `tabTimesheet Detail` tsd
        JOIN `tabTimesheet` ts ON ts.name = tsd.parent AND ts.docstatus = 1
        LEFT JOIN `tabBP Task` bt ON bt.name = tsd.custom_bp_task
        WHERE tsd.project IN %(projs)s
          AND tsd.is_billable = 1
          AND (tsd.sales_invoice IS NULL OR tsd.sales_invoice = '')
          AND IFNULL(bt.approval_status, '') NOT IN ('Pending', 'Rejected')
        """,
        {"projs": tuple(by_erp)},
        as_dict=True,
    )

    service_item = _service_item()
    client_rate_cache = {}
    effective_company_cache = {}
    fx_cache = {}
    preview_currency_cache = {}
    totals = {}

    for r in rows:
        p = by_erp.get(r.erp_project)
        if not p:
            continue

        if p.client not in client_rate_cache:
            client_rate_cache[p.client] = _price_list_rate(
                p.client, service_item
            )

        if p.name not in effective_company_cache:
            effective_company_cache[p.name] = (
                _effective_project_company(p)
            )

        effective_company = effective_company_cache[p.name]

        project_currency = (p.currency or "").strip() or None
        currency_key = (
            effective_company,
            p.client,
            project_currency,
        )

        if currency_key not in preview_currency_cache:
            company_currency, preview_currency, preview_fx = (
                _resolve_invoice_currency(
                    effective_company,
                    p.client,
                    None,
                    None,
                    project_currency,
                )
            )
            preview_currency_cache[currency_key] = (
                company_currency,
                preview_currency,
                preview_fx,
            )

        company_currency, preview_currency, preview_fx = (
            preview_currency_cache[currency_key]
        )

        eff_rate = _effective_billing_rate(
            row_rate=r.billing_rate,
            row_currency=r.timesheet_currency,
            project_rate=p.hourly_rate,
            project_currency=project_currency,
            client_rate=client_rate_cache[p.client],
            company_currency=company_currency,
            target_currency=preview_currency,
            company=effective_company,
            customer=p.client,
            target_to_company=preview_fx,
            fx_cache=fx_cache,
        )

        hrs = _authoritative_billing_hours(r)
        agg = totals.setdefault(
            r.erp_project,
            {
                "hours": 0.0,
                "amount": 0.0,
                "currency": preview_currency,
            },
        )
        agg["hours"] += hrs
        agg["amount"] += hrs * eff_rate

    out = {}
    for erp, agg in totals.items():
        p = by_erp[erp]
        effective_company = effective_company_cache[p.name]
        group_key = (
            p.client,
            effective_company,
        )

        entry = out.setdefault(group_key, {
            "client": p.client,
            "company": effective_company,
            "projects": [],
            "currencies": set(),
        })
        entry["currencies"].add(agg["currency"] or None)
        entry["projects"].append({
            "bp_project": p.name,
            "project_name": p.project_name,
            "erpnext_project": erp,
            "company": effective_company,
            "currency": agg["currency"] or None,
            "hours": round(agg["hours"], 2),
            "amount": round(agg["amount"], 2),
        })

    result = []
    for (client, company), entry in out.items():
        currencies = sorted(c for c in entry["currencies"] if c)
        result.append({
            "client": client,
            "company": entry["company"],
            # Surfaced so the screen can warn BEFORE the user selects a mix
            # that generate_invoice would refuse — a batch must be one currency.
            "currencies": currencies,
            "mixed_currency": len(currencies) > 1,
            "projects": sorted(entry["projects"], key=lambda x: -x["amount"]),
            "total_amount": round(sum(p["amount"] for p in entry["projects"]), 2),
            "total_hours": round(sum(p["hours"] for p in entry["projects"]), 2),
        })
    result.sort(key=lambda c: -c["total_amount"])
    return result


@frappe.whitelist()
def generate_milestone_invoice(milestone):
    """Draft Sales Invoice for a single completed, billing-enabled milestone —
    the milestone-based counterpart to generate_invoice's time-and-material
    flow above. One line item, no timesheets child rows.

    Draft only — submission stays a deliberate human act in ERPNext, same as
    generate_invoice."""
    doc = frappe.get_doc("BP Milestone", milestone)
    _check_permission(doc.project, "BP Admin")
    from batch_projects import access
    access.require_capability(doc.project, "view_money")
    require_feature("billing_writeback")

    # Billing eligibility was checked on an unlocked snapshot above only for
    # authorization. Financial state is re-read after deterministic locks:
    #
    #     BP Project → BP Milestone
    #
    # Project-level serialization is required because percentage milestones
    # share one 100%-of-budget invariant across different milestone rows.
    from batch_projects.milestone_billing import (
        DRAFT,
        INVOICED,
        assert_percent_capacity,
        lock_generation_scope,
    )

    # IMPORTANT: use the rows returned by the locking reads themselves.
    # Ordinary SELECT/get_doc calls after waiting on FOR UPDATE can still use
    # the transaction's older repeatable-read snapshot.
    project, doc = lock_generation_scope(
        doc.project,
        doc.name,
    )

    if doc.status != "Completed":
        frappe.throw("Complete this milestone before invoicing it.")
    if not doc.billing_type or doc.billing_type == "None":
        frappe.throw("Set a billing type on this milestone before invoicing it.")
    if doc.invoice_status in (DRAFT, INVOICED):
        state = "draft invoice" if doc.invoice_status == DRAFT else "submitted invoice"
        frappe.throw(
            f"This milestone already has {state} {doc.sales_invoice}. "
            "Delete/cancel that invoice before creating another."
        )

    if not project.erpnext_project:
        frappe.throw(f"Link '{project.project_name}' to an ERPNext Project before invoicing it.")
    if not project.client:
        frappe.throw(f"Set a Client on '{project.project_name}' before invoicing it.")

    if doc.billing_type == "Fixed Amount":
        amount = flt(doc.invoice_amount)
    else:
        # A Draft invoice already reserves part of this project's commercial
        # budget even though it has not reached the ledger yet. Count Draft +
        # Invoiced siblings while the BP Project row lock serializes different
        # milestones racing for the same remaining percentage.
        assert_percent_capacity(
            doc.project,
            doc.name,
            doc.invoice_percent,
        )
        amount = flt(project.budget_amount) * flt(doc.invoice_percent) / 100

    company = project.company or frappe.defaults.get_global_default("company")
    income_account = frappe.db.get_value("Company", company, "default_income_account")
    if not income_account:
        frappe.throw(f"Set a Default Income Account on Company '{company}' before invoicing.")

    si = frappe.new_doc("Sales Invoice")
    si.customer = project.client
    si.company = company
    si.project = project.erpnext_project

    # Milestone amounts come from BP Project.budget_amount / BP Milestone.
    # invoice_amount, both denominated in BP Project.currency — so the invoice
    # is raised in that currency and the figure passes through unconverted.
    # (The old behaviour let this default to company currency, which billed a
    # 5,000 USD milestone as 5,000 NPR. Same class of bug as the hourly path.)
    company_currency, inv_currency, fx = _resolve_invoice_currency(
        company, project.client, None, None,
        project_currency=(project.currency or "").strip() or None,
    )
    si.currency = inv_currency
    si.conversion_rate = fx

    si.append("items", {
        "item_name": doc.title,
        "description": doc.title,
        "qty": 1,
        "rate": amount,
        "income_account": income_account,
    })
    # batch_projects has already authorized this call in full (BP Admin on
    # every project, view_money capability, billing_writeback entitlement, and
    # the gateway signature). ERPNext's set_missing_values then does its OWN
    # check: selling_controller.set_missing_lead_customer_details() calls
    # _get_party_details(ignore_permissions=self.flags.ignore_permissions),
    # which throws PermissionError unless the user can read Customer.
    # Delivery-team users deliberately hold no native ERPNext role
    # permissions, so without this flag every real (non-Administrator) user
    # gets a bare 403 from the UI while it works fine from bench. Setting it
    # asserts "authorization already happened upstream" — the same posture as
    # the insert(ignore_permissions=True) that follows.
    si.flags.ignore_permissions = True
    si.run_method("set_missing_values")
    si.currency = inv_currency
    si.conversion_rate = fx
    si.insert(ignore_permissions=True)

    frappe.db.set_value(
        "BP Milestone",
        doc.name,
        {
            "invoice_status": DRAFT,
            "sales_invoice": si.name,
        },
        update_modified=False,
    )
    # The "Open" toast action deep-links straight to /app/sales-invoice/<name>
    # — same zero-native-ERPNext-role gap ensure_erp_doc_access exists for,
    # but this invoice has no BP Task Reference/project-field trail for that
    # generic lookup to find, so grant the share directly here instead, where
    # tenancy is already established (we just created it for this project).
    frappe.share.add_docshare(
        "Sales Invoice", si.name, frappe.session.user, read=1,
        flags={"ignore_share_permission": True})
    frappe.db.commit()

    return {
        "ok": True,
        "sales_invoice": si.name,
        "grand_total": si.grand_total,
        "invoice_status": DRAFT,
    }


@frappe.whitelist()
def generate_expense_invoice(project):
    """Draft Sales Invoice from every currently-unbilled, billable Expense
    Claim Detail row against this project — the expense-side counterpart to
    generate_invoice's timesheet flow above. One line per Expense Claim Type.

    Re-invoicing policy lives on Expense Claim Type (custom_reinvoice_policy /
    custom_markup_percent) — the same expense_policy pattern ERPNext's own
    Odoo counterpart uses on the product (verified against odoo-src's
    sale_project/sale_timesheet reinvoice tests), adapted from a flat
    "sales price" to a cost/cost+markup% choice, since a markup on
    reimbursable expenses (not a fixed resale price) is the pattern
    professional-services billing tools actually use. See
    docs/APP-OVERVIEW.md §4.1 for the full reasoning.

    The per-row custom_is_billable checkbox stays the human trigger — same
    "a person always decides what gets billed" posture as generate_invoice
    and generate_milestone_invoice above. A type's 'Not Billable' policy is a
    hard ceiling on top of that checkbox, not a replacement for it: it
    excludes the type's rows from this query even if one was individually
    (mis-)flagged billable.

    Draft only — submission stays a deliberate human act in ERPNext."""
    _check_permission(project, "BP Admin")
    from batch_projects import access
    access.require_capability(project, "view_money")
    require_feature("billing_writeback")

    doc = frappe.get_doc("BP Project", project)
    if not doc.erpnext_project:
        frappe.throw(f"Link '{doc.project_name}' to an ERPNext Project before invoicing it.")
    if not doc.client:
        frappe.throw(f"Set a Client on '{doc.project_name}' before invoicing it.")

    # A row counts as unbilled if it's never been stamped, OR if the invoice
    # it was stamped with no longer exists / was cancelled since — otherwise
    # a deleted or cancelled draft would permanently lock a real expense out
    # of ever being re-invoiced.
    rows = frappe.db.sql(
        """
        SELECT ecd.name, ecd.parent AS expense_claim, ecd.expense_type,
               ecd.sanctioned_amount, ecd.description, ec.posting_date,
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
        ORDER BY ec.posting_date ASC
        """,
        {"proj": doc.erpnext_project},
        as_dict=True,
    )
    if not rows:
        frappe.throw("Nothing to invoice — no unbilled billable expenses on this project.")

    for r in rows:
        r.eff_amount = round(
            flt(r.sanctioned_amount) * (1 + flt(r.markup_percent) / 100)
            if r.policy == "At Cost + Markup" else flt(r.sanctioned_amount),
            2,
        )

    by_type = {}
    for r in rows:
        by_type.setdefault(r.expense_type or "Other", []).append(r)

    company = doc.company or frappe.defaults.get_global_default("company")
    income_account = frappe.db.get_value("Company", company, "default_income_account")
    if not income_account:
        frappe.throw(f"Set a Default Income Account on Company '{company}' before invoicing.")

    si = frappe.new_doc("Sales Invoice")
    si.customer = doc.client
    si.company = company
    si.project = doc.erpnext_project

    # Expense Claim Detail.sanctioned_amount is in COMPANY currency (ERPNext
    # books expense claims against the company), unlike milestone amounts.
    # So when this invoice is raised in the project's currency the amounts
    # must be converted DOWN by the same rate — the opposite direction from
    # generate_milestone_invoice, where the figure is already project-currency.
    company_currency, inv_currency, fx = _resolve_invoice_currency(
        company, doc.client, None, None,
        project_currency=(doc.currency or "").strip() or None,
    )
    si.currency = inv_currency
    si.conversion_rate = fx
    _exp_fx = flt(fx) if (inv_currency != company_currency and fx) else 1.0

    for expense_type, type_rows in by_type.items():
        amount = round(sum(r.eff_amount for r in type_rows) / _exp_fx, 2)
        marked_up = any(r.policy == "At Cost + Markup" for r in type_rows)
        description = f"{expense_type} (reimbursed expenses{', incl. markup' if marked_up else ''})"
        si.append("items", {
            "item_name": description,
            "description": description,
            "qty": 1,
            "rate": amount,
            "income_account": income_account,
        })

    # batch_projects has already authorized this call in full (BP Admin on
    # every project, view_money capability, billing_writeback entitlement, and
    # the gateway signature). ERPNext's set_missing_values then does its OWN
    # check: selling_controller.set_missing_lead_customer_details() calls
    # _get_party_details(ignore_permissions=self.flags.ignore_permissions),
    # which throws PermissionError unless the user can read Customer.
    # Delivery-team users deliberately hold no native ERPNext role
    # permissions, so without this flag every real (non-Administrator) user
    # gets a bare 403 from the UI while it works fine from bench. Setting it
    # asserts "authorization already happened upstream" — the same posture as
    # the insert(ignore_permissions=True) that follows.
    si.flags.ignore_permissions = True
    si.run_method("set_missing_values")
    si.currency = inv_currency
    si.conversion_rate = fx
    si.insert(ignore_permissions=True)
    # ProjectMoney.vue's "Open" toast action deep-links straight to
    # /app/sales-invoice/<name> — SPA members hold zero native ERPNext role
    # by design, so grant the one document they just legitimately created.
    frappe.share.add_docshare(
        "Sales Invoice", si.name, frappe.session.user, read=1,
        flags={"ignore_share_permission": True})

    for r in rows:
        frappe.db.set_value("Expense Claim Detail", r.name, "custom_sales_invoice", si.name, update_modified=False)
    frappe.db.commit()

    return {
        "ok": True,
        "sales_invoice": si.name,
        "grand_total": si.grand_total,
        "expenses_invoiced": len(rows),
    }


# ─── Task-driven procurement ──────────────────────────────────────────────────

@frappe.whitelist()
def search_non_stock_items(txt=""):
    """Item picker for "Create Purchase Order" — restricted to
    non-stock/service items for v1: core erpnext's stock validation demands
    a warehouse on stock-item PO rows, and the v1 drawer form has no
    warehouse field (a deliberate scope decision)."""
    _require_system_user()
    # has_variants=1 = template items, not transactable on a PO row.
    filters = {"is_stock_item": 0, "disabled": 0, "has_variants": 0}
    return frappe.get_all(
        "Item", filters=filters,
        or_filters=(
            [["item_code", "like", f"%{txt}%"], ["item_name", "like", f"%{txt}%"]]
            if txt else []
        ),
        fields=["item_code", "item_name", "stock_uom"],
        order_by="modified desc", limit=20,
    )


@frappe.whitelist()
def create_purchase_order_from_task(task, supplier, items):
    """Mirror image of create_project_from_sales_order — one click on a task
    creates a DRAFT Purchase Order (accountants review + submit in ERPNext,
    same precedent as generate_invoice), every item row pre-stamped with the
    bp_task accounting dimension + project, so it shows up in the
    per-task cost breakdown's committed column the moment it's submitted.

    items: [{item_code, qty, rate}, ...]. item_code is NOT optional — core
    erpnext requires it (`reqd: 1`) on every Purchase Order Item; there is no
    free-text-only row (verified, docs/PLAN-phase9-task-costing.md)."""
    _require_system_user()
    require_feature("integrations")

    if isinstance(items, str):
        items = json.loads(items)
    if not items:
        frappe.throw("Add at least one item.")

    task_doc = frappe.get_doc("BP Task", task)

    from batch_projects import access
    access.require(task_doc.project, "Manager")
    access.require_capability(task_doc.project, "view_money")

    doc = frappe.get_doc("BP Project", task_doc.project)
    if not doc.erpnext_project:
        frappe.throw(f"Link '{doc.project_name}' to an ERPNext Project before creating a Purchase Order from it.")

    company = doc.company or frappe.defaults.get_global_default("company")
    schedule_date = add_days(nowdate(), 7)

    po = frappe.new_doc("Purchase Order")
    # BP users hold zero ERPNext doctype permissions by design (per 8B) — SPA
    # users' Frappe accounts have no Buying/Accounts role, so buying_
    # controller.set_missing_values's own internal get_party_details(supplier,
    # ...) call (a live frappe.has_permission("Supplier", ...) check,
    # independent of insert()'s ignore_permissions=True below) throws
    # PermissionError for anyone but Administrator. Same posture as the
    # tenancy checks elsewhere: our access.require(Manager) above IS the
    # authorization; core doctype perms are irrelevant to a BP user.
    po.flags.ignore_permissions = True
    po.supplier = supplier
    po.company = company
    po.project = doc.erpnext_project
    po.schedule_date = schedule_date

    for item in items:
        qty = flt(item.get("qty"))
        rate = flt(item.get("rate"))
        if not item.get("item_code") or qty <= 0:
            frappe.throw("Every item needs an Item and a quantity greater than 0.")
        # The picker only offers non-stock items, but the endpoint must
        # enforce it too (locked v1 decision): a stock-item row has no
        # warehouse here and would mint a draft the accountant can never
        # submit — fail honestly at creation instead.
        is_stock = frappe.db.get_value("Item", item["item_code"], "is_stock_item")
        if is_stock is None:
            frappe.throw(f"Item '{item['item_code']}' does not exist.")
        if is_stock:
            frappe.throw(
                f"'{item['item_code']}' is a stock item — task purchase orders "
                "support non-stock/service items only (no warehouse in this form). "
                "Create stock POs in ERPNext."
            )
        po.append("items", {
            "item_code": item["item_code"],
            "qty": qty,
            "rate": rate,
            "schedule_date": schedule_date,
            # Stamped explicitly at creation — never relying on the
            # header-fallback COALESCE the read side (9B) added for
            # desk-created POs that only set the header project.
            "bp_task": task_doc.name,
            "project": doc.erpnext_project,
        })

    po.run_method("set_missing_values")
    po.insert(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": True, "purchase_order": po.name, "grand_total": po.grand_total}


# ─── The Money drawer ─────────────────────────────────────────────────────────

_DENIED = "Document not found on this project."

_ITEM_FIELDS = ["item_name", "description", "qty", "uom", "rate", "amount"]

_DOC_SPECS = {
    "Sales Invoice": {
        "header": ["name", "status", "posting_date", "due_date", "customer",
                   "currency", "grand_total", "outstanding_amount"],
        "child_doctype": "Sales Invoice Item",
        "child_key": "items",
        "child_fields": _ITEM_FIELDS,
    },
    "Purchase Invoice": {
        "header": ["name", "status", "posting_date", "supplier", "currency", "grand_total"],
        "child_doctype": "Purchase Invoice Item",
        "child_key": "items",
        "child_fields": _ITEM_FIELDS,
    },
    "Sales Order": {
        "header": ["name", "status", "transaction_date", "delivery_date", "customer",
                   "currency", "grand_total", "per_billed", "per_delivered"],
        "child_doctype": "Sales Order Item",
        "child_key": "items",
        "child_fields": _ITEM_FIELDS,
    },
    "Purchase Order": {
        "header": ["name", "status", "transaction_date", "supplier",
                   "currency", "grand_total", "per_billed", "per_received"],
        "child_doctype": "Purchase Order Item",
        "child_key": "items",
        # billed_amt (doc currency, same as rate/amount) on top of the
        # standard item fields so the drawer can show the per-line committed
        # remainder — deliberately not base_amount, which is
        # company currency and would mix currencies with amount/rate in the
        # same row. returned_qty feeds the same per-line remainder math.
        "child_fields": _ITEM_FIELDS + ["billed_amt", "returned_qty"],
    },
    "Timesheet": {
        "header": ["name", "docstatus", "status", "employee", "employee_name",
                   "start_date", "end_date", "total_hours"],
        "child_doctype": "Timesheet Detail",
        "child_key": "time_logs",
        "child_fields": ["activity_type", "from_time", "to_time", "hours",
                          "is_billable", "billing_amount", "custom_bp_task"],
    },
    "Expense Claim": {
        "header": ["name", "status", "posting_date", "employee_name", "total_sanctioned_amount"],
        "child_doctype": "Expense Claim Detail",
        "child_key": "expenses",
        "child_fields": ["expense_type", "expense_date", "amount",
                          "sanctioned_amount", "custom_is_billable", "bp_task"],
    },
}


def _erp_project_for(project: str) -> str:
    """BP Project -> its linked ERPNext Project, or the generic denial if
    either the BP Project or the link doesn't resolve — same "don't tell an
    attacker which part failed" posture as the tenancy check itself."""
    erp_project = frappe.db.get_value("BP Project", project, "erpnext_project")
    if not erp_project:
        frappe.throw(_DENIED)
    return erp_project


def _tenant_ok(doctype: str, name: str, erp_project: str) -> bool:
    """THE security boundary: does this ERPNext doc actually belong to this
    project? Checked with raw field reads (frappe.db.get_value/exists) so a
    nonexistent doc and a foreign doc both just fail this check the same
    way — no frappe.get_doc() that could throw its own, distinguishing,
    DoesNotExistError first."""
    if doctype == "Timesheet":
        parent_project = frappe.db.get_value("Timesheet", name, "parent_project")
        if parent_project:
            return parent_project == erp_project
        # No header project set — fall back to any time_logs row landing on
        # this project (mirrors how the timer itself stamps rows: project
        # is set per-row, parent_project is never set by our own code).
        return bool(frappe.db.exists("Timesheet Detail", {"parent": name, "project": erp_project}))
    return frappe.db.get_value(doctype, name, "project") == erp_project


@frappe.whitelist()
def get_erp_doc_summary(project, doctype, name):
    """Curated, read-only summary of one ERPNext document for the Money
    drawer — never `frappe.get_doc(...).check_permission()` (SPA users hold
    zero ERPNext doc perms by design); the tenancy check below IS
    the authorization. Exactly 4 doctypes, exactly the fields listed —
    that's the scope contract, not an oversight."""
    _check_permission(project, "BP Viewer")
    from batch_projects import access
    access.require_capability(project, "view_money")
    require_feature("profitability")
    require_workspace_feature("money_tab")

    spec = _DOC_SPECS.get(doctype)
    if not spec:
        frappe.throw(_DENIED)

    erp_project = _erp_project_for(project)
    if not _tenant_ok(doctype, name, erp_project):
        frappe.throw(_DENIED)

    header = frappe.db.get_value(doctype, name, spec["header"], as_dict=True)
    if not header:
        frappe.throw(_DENIED)

    # Expense Claim (and Timesheet) carry no `currency` field of their own —
    # ERPNext always books them in the Company's default currency — so
    # `header` never has one, and the drawer's fmtMoney() fell back to a
    # hardcoded 'USD', showing "$13,750" for an NPR-booked claim. Every other
    # spec's header already has `currency` from the doctype itself; this
    # backfills it the same way for the two that don't.
    if "currency" not in header:
        company = frappe.db.get_value(doctype, name, "company")
        if company:
            header["currency"] = frappe.get_cached_value("Company", company, "default_currency")

    # Timesheets can legitimately span projects (manual weekly entry in
    # ERPNext desk; our own timer used to share one draft per day) and the
    # tenancy check passes on ANY matching row — so the row read must be
    # scoped to this project too, or one project's drawer exposes another
    # project's hours and billing amounts. Non-transitivity applies inside
    # child tables, not just across documents.
    child_filters = {"parent": name}
    if doctype == "Timesheet":
        child_filters["project"] = erp_project

    children = frappe.get_all(
        spec["child_doctype"], filters=child_filters,
        fields=spec["child_fields"], order_by="idx asc",
    )

    if doctype == "Timesheet":
        task_names = list({c["custom_bp_task"] for c in children if c.get("custom_bp_task")})
        task_meta = {}
        if task_names:
            task_meta = {
                t["name"]: t for t in frappe.get_all(
                    "BP Task", filters={"name": ["in", task_names]},
                    fields=["name", "task_key", "title"],
                )
            }
        for c in children:
            meta = task_meta.get(c.get("custom_bp_task"))
            c["task_key"] = meta["task_key"] if meta else None
            c["task_title"] = meta["title"] if meta else None

    out = {"doctype": doctype, **header, spec["child_key"]: children}

    if doctype == "Sales Invoice":
        # The hours behind the invoice — an SI generated by generate_invoice
        # carries its backing Timesheet references, and hiding them made the
        # revenue drawer a dead end (user-reported). Name-only pointers per
        # the non-transitivity rule: opening one re-enters this same gate.
        ts_rows = frappe.get_all(
            "Sales Invoice Timesheet", filters={"parent": name},
            fields=["time_sheet", "billing_hours", "billing_amount"],
            order_by="idx asc",
        )
        grouped = {}
        for r in ts_rows:
            if not r.time_sheet:
                continue
            g = grouped.setdefault(r.time_sheet, {"timesheet": r.time_sheet, "hours": 0.0, "amount": 0.0})
            g["hours"] = round(g["hours"] + float(r.billing_hours or 0), 2)
            g["amount"] = round(g["amount"] + float(r.billing_amount or 0), 2)
        out["timesheets"] = list(grouped.values())

    return out


# Doctypes outside the Money drawer's 6-doctype scope that still get a raw
# "Open in ERPNext" desk link somewhere in the SPA (ProjectHeader's pipeline
# source, Connect-column references) — the BP Project field each is trusted
# from. Anything not listed here is only ever trusted via a BP Task
# Reference row (see _projects_referencing below).
_PROJECT_FIELD_FOR_DOCTYPE = {
    "Sales Order":  "source_sales_order",
    "Quotation":    "source_quotation",
    "Opportunity":  "source_opportunity",
    "Lead":         "source_lead",
    "Customer":     "client",
}


def _projects_referencing(doctype: str, name: str) -> set:
    """Every BP Project that genuinely references (doctype, name) — via its
    own pipeline-source/client field, or via a task's BP Task Reference.
    Purely DB-derived, never trusts a client-supplied project."""
    projects = set()
    field = _PROJECT_FIELD_FOR_DOCTYPE.get(doctype)
    if field:
        projects |= set(frappe.get_all("BP Project", filters={field: name}, pluck="name"))
    rows = frappe.db.sql(
        """SELECT DISTINCT t.project FROM `tabBP Task Reference` r
           JOIN `tabBP Task` t ON t.name = r.parent
           WHERE r.ref_doctype=%s AND r.ref_name=%s""",
        (doctype, name),
    )
    projects |= {r[0] for r in rows if r[0]}
    return projects


@frappe.whitelist()
def ensure_erp_doc_access(doctype, name):
    """Grant the caller a per-document read share on an ERPNext doc the SPA
    is about to deep-link to (raw /app/<doctype>/<name> navigation) — SPA
    members hold zero ERPNext DocPerm by design (see get_erp_doc_summary
    above), so that link 403s for anyone without an unrelated ERPNext role.
    Tenancy (does a project the caller can see genuinely reference this doc)
    IS the authorization, same posture as get_erp_doc_summary; this just
    covers doctypes outside the Money drawer's scope (Customer, Quotation,
    Opportunity, Lead, Supplier, Stock Entry, ...). A per-document DocShare
    (not a doctype-wide DocPerm grant) keeps the exposure to exactly the one
    document the project actually links, never the whole doctype."""
    from batch_projects import access

    if not frappe.db.exists(doctype, name):
        frappe.throw(_DENIED)

    user = frappe.session.user
    projects = _projects_referencing(doctype, name)
    if not any(access.has_at_least(p, "Viewer", user) for p in projects):
        frappe.throw(_DENIED)

    frappe.share.add_docshare(
        doctype, name, user, read=1, flags={"ignore_share_permission": True})
    return {"ok": True}


@frappe.whitelist()
def submit_timesheet(project, timesheet):
    """The ONLY mutation the Money drawer exposes. GL-posting documents
    (SI/PI/SO) are never submitted from here — that stays a deliberate act
    in ERPNext, same precedent as generate_invoice's draft-only return."""
    _check_permission(project, "BP Admin")
    require_feature("time_tracking")
    require_workspace_feature("timesheets")

    # Respect Timesheet Approval mode. When set to "Manager
    # Approval", only workspace approvers may submit.
    ws = frappe.get_single("BP Workspace Settings")
    if ws.approval_mode == "Manager Approval":
        approver_users = {a.user for a in (ws.approvers or [])}
        if frappe.session.user not in approver_users:
            frappe.throw(
                "This workspace requires Manager Approval for timesheet submission. "
                "Ask a workspace approver to submit this timesheet.",
                title="Approval Required",
            )

    erp_project = _erp_project_for(project)
    if not _tenant_ok("Timesheet", timesheet, erp_project):
        frappe.throw(_DENIED)

    ts = frappe.get_doc("Timesheet", timesheet)
    if ts.docstatus != 0:
        frappe.throw("Only a draft Timesheet can be submitted.")

    # Submit is doc-level: it would also submit rows belonging to OTHER
    # projects (manual weekly timesheets legitimately mix projects), which
    # this project's Admin can't even see in the drawer — the read above is
    # project-scoped. A mixed timesheet is ERPNext's call, not ours.
    foreign_rows = [
        d for d in ts.time_logs if (d.project or "") != erp_project
    ]
    if foreign_rows:
        frappe.throw(
            "This timesheet also contains time for other projects — "
            "review and submit it in ERPNext instead."
        )

    ts.flags.ignore_permissions = True
    ts.submit()
    frappe.db.commit()

    return get_erp_doc_summary(project, "Timesheet", timesheet)


# ─── FIELD METADATA ────────────────────────────────────────────────────────

def _doctype_field_rows(doctype, include_read_only=False):
    """Shared row-shaping for doctype field metadata — used by both the
    write-scoped get_erp_doctype_fields below and board.py's read-scoped
    get_erp_doctype_fields_readonly (condition builders, the dashboard row
    designer). Same shape either way: only the caller's doctype whitelist
    differs (write vs. read) — and, now, whether read_only/computed fields
    (task_key, modified, owner, ...) are worth offering at all: never for a
    WRITE target (include_read_only=False, the default — you can't set
    them), but exactly what a read-only DISPLAY context wants (a row
    designer showing "Modified" or a computed field is completely
    reasonable, unlike trying to write to one)."""
    meta = frappe.get_meta(doctype)
    skip_types = {
        "Section Break", "Column Break", "Tab Break", "Table", "Table MultiSelect",
        "HTML", "Button", "Fold", "Heading", "Image", "Attach", "Attach Image",
        "Signature", "Password", "Read Only", "Geolocation", "Code", "Barcode",
    }
    out = []
    for f in meta.fields:
        if f.fieldtype in skip_types or f.hidden:
            continue
        if f.read_only and not include_read_only:
            continue
        row = {
            "fieldname": f.fieldname,
            "label": f.label or f.fieldname,
            "fieldtype": f.fieldtype,
            "options": None,
        }
        if f.fieldtype == "Select":
            row["options"] = [o for o in (f.options or "").split("\n") if o]
        elif f.fieldtype == "Link":
            row["options"] = f.options  # target doctype name
        out.append(row)
    return sorted(out, key=lambda r: r["label"])


# NOT the same list as _ERP_SEARCH_DOCTYPES in board.py (that one is a
# read-only reference/typeahead allowlist, deliberately wider). This is
# field metadata for CONFIGURING "Update ERPNext Document" — it must never
# offer more doctypes than that action can actually write to, so it's
# scoped to the same write-safety boundary the action itself enforces.
@frappe.whitelist()
def get_erp_doctype_fields(doctype):
    """Writable docfields for `doctype`, for the automation builder's
    "Fields to set" Combobox — kills the free-text fieldname
    guess. Scoped to the doctypes "Update ERPNext Document" may actually
    target (bp_automation_rule.py's _ERPNEXT_DOCTYPE_WHITELIST) — offering
    metadata for a doctype the action can't write to would be misleading,
    not just inconsistent.
    """
    _require_system_user()
    from batch_projects.batch_projects.doctype.bp_automation_rule.bp_automation_rule import (
        _ERPNEXT_DOCTYPE_WHITELIST,
    )
    if doctype not in _ERPNEXT_DOCTYPE_WHITELIST:
        frappe.throw(f"DocType '{doctype}' is not allowed here.")
    return _doctype_field_rows(doctype)


# ═══════════════════════════════════════════════════════════════════════════════
# Internal helpers — called ONLY from doctype controller hooks (bp_project.py).
# No @frappe.whitelist(), no gateway check, no permission check.
# ═══════════════════════════════════════════════════════════════════════════════

# Status mapping: BP Project → ERPNext Project.
# BP Project has 3 statuses (Active / Archived / On Hold — bp_project.json:65).
# ERPNext Project uses Open / Completed / Cancelled / Hold.
_BP_TO_ERP_STATUS = {
    "Active":    "Open",
    "Archived":  "Completed",
    "On Hold":   "Hold",
}


def _auto_link_erpnext_project(project):
    """Create and link an ERPNext Project for `project` (a BP Project name).

    Called from bp_project.py after_insert. No gateway signature, no
    @frappe.whitelist() — the BP Project was already created through a
    gateway-verified path, so re-verifying here would always fail inside
    a doc event.

    Degrades silently: a missing company, a lapsed license, or an ERPNext
    insert failure are all logged and swallowed — the BP Project save
    succeeds regardless.
    """
    doc = frappe.get_doc("BP Project", project)
    if not doc.company or doc.erpnext_project:
        return

    company = doc.company or frappe.defaults.get_global_default("company")
    if not company:
        return

    # Honour the entitlements gate (reads 24h-cached tier; no-ops if lapsed).
    try:
        from batch_projects.entitlements import require_feature
        require_feature("integrations")
    except Exception:
        return

    erp_doc = frappe.get_doc({
        "doctype": "Project",
        "project_name": doc.project_name,
        "company": company,
        "customer": doc.client or None,
        "status": "Open",
    })
    erp_doc.insert(ignore_permissions=True)

    # Write the link back. Uses frappe.db.set_value (not doc.save()) so the
    # recursion guard in bp_project.py.on_update catches the resulting
    # on_update fire and bails immediately.
    frappe.db.set_value("BP Project", project, "erpnext_project", erp_doc.name)
    doc.add_comment(
        "Comment",
        f"Auto-linked to ERPNext Project <b>{erp_doc.name}</b>.",
    )


def _sync_to_erpnext_project(bp_project_name):
    """Write-back status and target_end_date to the linked ERPNext Project.

    Called from bp_project.py on_update. Uses frappe.db.set_value (never
    doc.save()) on the ERPNext Project to avoid re-entrant lifecycle hooks.
    No @frappe.whitelist(), no gateway check — the caller already verified
    the user had permission to save the BP Project.
    """
    bp = frappe.get_doc("BP Project", bp_project_name)
    if not bp.erpnext_project:
        return

    if not frappe.db.exists("Project", bp.erpnext_project):
        return

    updates = {}

    erp_status = _BP_TO_ERP_STATUS.get(bp.status)
    if erp_status:
        updates["status"] = erp_status

    if bp.target_end_date:
        updates["expected_end_date"] = bp.target_end_date

    if updates:
        frappe.db.set_value("Project", bp.erpnext_project, updates)


def reconcile_erpnext_sync():
    """Daily background job: reconcile BP Project ↔ ERPNext Project.

    Two passes, capped per run so a large site never exceeds the scheduler
    timeout:

    1. Un-linked projects where company is set → auto-link them (up to
       50 per run). Respects the per-project `auto_create_erpnext_project`
       flag when present (defaults True).
    2. Linked projects → compare status and target_end_date against the
       live ERPNext Project. Sync any that drifted (up to 200 per run).

    Individual failures are logged and skipped — one broken project never
    aborts the whole batch. Runs under `frappe.flags.in_bp_project_sync` so
    document hooks (bp_project.py on_update) bail immediately on every
    frappe.db.set_value call inside the helpers.
    """
    from batch_projects.entitlements import require_feature

    # Honour entitlements (reads 24h-cached tier; no-ops if lapsed).
    try:
        require_feature("integrations")
    except Exception:
        return

    frappe.flags.in_bp_project_sync = True
    stats = {"auto_linked": 0, "synced": 0, "skipped": 0, "failed": 0}

    try:
        # ── Pass 1: Auto-link un-linked projects with a company ──────
        unlinked = frappe.db.get_all(
            "BP Project",
            filters={
                "erpnext_project": ["is", "not set"],
                "company": ["is", "set"],
            },
            pluck="name",
            limit_page_length=50,
        )

        for bp_name in unlinked:
            try:
                bp = frappe.get_doc("BP Project", bp_name)
                # Honour opt-out flag (field may not exist yet — default
                # True so the feature works until the migration ships).
                if not getattr(bp, "auto_create_erpnext_project", True):
                    stats["skipped"] += 1
                    continue
                _auto_link_erpnext_project(bp_name)
                stats["auto_linked"] += 1
            except Exception:
                frappe.log_error(
                    title="Reconcile auto-link failed",
                    message=frappe.get_traceback(),
                    reference_doctype="BP Project",
                    reference_name=bp_name,
                )
                stats["failed"] += 1

        # ── Pass 2: Sync status / date drift on linked projects ───
        linked = frappe.db.get_all(
            "BP Project",
            filters={"erpnext_project": ["is", "set"]},
            fields=["name", "status", "target_end_date", "erpnext_project"],
            limit_page_length=200,
        )

        # Build a lookup of ERPNext Project state in one query (avoids
        # N+1 frappe.get_doc / frappe.db.get_value calls in the loop).
        erp_names = list({
            r["erpnext_project"]
            for r in linked
            if r.get("erpnext_project")
        })
        erp_map = {}
        if erp_names:
            for erp in frappe.db.get_all(
                "Project",
                filters={"name": ["in", erp_names]},
                fields=["name", "status", "expected_end_date"],
            ):
                erp_map[erp["name"]] = erp

        for bp_row in linked:
            try:
                erp = erp_map.get(bp_row["erpnext_project"])
                if not erp:
                    stats["skipped"] += 1
                    continue

                needs_sync = False

                # Status mismatch?
                expected_status = _BP_TO_ERP_STATUS.get(bp_row["status"])
                if expected_status and erp.get("status") != expected_status:
                    needs_sync = True

                # Date mismatch?
                bp_date = str(bp_row.get("target_end_date") or "")
                erp_date = str(erp.get("expected_end_date") or "")
                if bp_date and bp_date != erp_date:
                    needs_sync = True

                if needs_sync:
                    _sync_to_erpnext_project(bp_row["name"])
                    stats["synced"] += 1
                else:
                    stats["skipped"] += 1
            except Exception:
                frappe.log_error(
                    title="Reconcile sync failed",
                    message=frappe.get_traceback(),
                    reference_doctype="BP Project",
                    reference_name=bp_row["name"],
                )
                stats["failed"] += 1

    finally:
        frappe.flags.in_bp_project_sync = False

    from frappe.utils.logger import get_logger

    logger = get_logger("batch_projects.reconcile")
    logger.info(
        "ERPNext reconcile complete: auto_linked=%d synced=%d skipped=%d failed=%d",
        stats["auto_linked"],
        stats["synced"],
        stats["skipped"],
        stats["failed"],
    )

    return stats
