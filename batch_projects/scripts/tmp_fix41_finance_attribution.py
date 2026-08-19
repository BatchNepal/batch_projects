from pathlib import Path


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly 1 match, found {count}")
    return text.replace(old, new, 1)


root = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# 1. ERP financial events: shared Sales Invoice / Payment Entry fan-out.
# ---------------------------------------------------------------------------
path = root / "batch_projects" / "erp_triggers.py"
text = path.read_text()

text = replace_once(
    text,
    "import frappe\n",
    "import frappe\nfrom frappe.utils import flt\n",
    "erp_triggers import",
)

start = text.index("def on_sales_invoice_submit(")
end = text.index("def on_sales_order_submit(")

new_sales_block = '''def _row_value(row, field, default=None):
    if isinstance(row, dict):
        return row.get(field, default)
    return getattr(row, field, default)


def _sales_invoice_project_weights(name, header_project, items=None):
    """Return stable (ERP Project, net-share) pairs for one Sales Invoice.

    Sales Invoice Item.project is authoritative; blank item project inherits
    the header for legacy/single-project invoices. Net-line share is the only
    defensible basis for allocating invoice-level totals such as grand total,
    outstanding and a later Payment Entry allocation across projects.
    """
    if items is None:
        items = frappe.get_all(
            "Sales Invoice Item",
            filters={"parent": name},
            fields=["project", "net_amount"],
            order_by="idx asc",
        )

    totals = {}
    order = []

    for item in items or []:
        erp_project = _row_value(item, "project") or header_project
        if not erp_project:
            continue
        if erp_project not in totals:
            totals[erp_project] = 0.0
            order.append(erp_project)
        totals[erp_project] += flt(_row_value(item, "net_amount") or 0)

    if not totals:
        return [(header_project, 1.0)] if header_project else []

    denominator = sum(totals.values())
    if abs(denominator) <= 1e-12:
        # A zero-net mixed invoice has no financially meaningful denominator
        # for fan-out. Preserve the historical header attribution rather than
        # inventing an arbitrary split or duplicating the whole amount.
        return [(header_project, 1.0)] if header_project else []

    return [
        (erp_project, totals[erp_project] / denominator)
        for erp_project in order
    ]


def _apportion(total, project_weights):
    """Allocate a currency total while preserving its rounded sum exactly."""
    total = round(flt(total), 2)
    if not project_weights:
        return {}

    allocated = {}
    remaining = total

    for idx, (erp_project, weight) in enumerate(project_weights):
        if idx == len(project_weights) - 1:
            value = remaining
        else:
            value = round(total * weight, 2)
            remaining = round(remaining - value, 2)
        allocated[erp_project] = value

    return allocated


def on_sales_invoice_submit(doc, method=None):
    project_weights = _sales_invoice_project_weights(
        doc.name,
        doc.project,
        items=doc.items,
    )
    if not project_weights:
        return

    amounts = _apportion(doc.grand_total, project_weights)
    outstanding = _apportion(doc.outstanding_amount, project_weights)

    from batch_projects.events import emit
    for erp_project, _weight in project_weights:
        bp_project = _bp_project_for(
            "Sales Invoice",
            doc.name,
            erp_project,
        )
        if not bp_project:
            continue

        emit("erp.invoice_submitted", {
            "project": bp_project,
            "invoice": doc.name,
            "customer": doc.customer,
            "amount": amounts.get(erp_project, 0.0),
            "outstanding": outstanding.get(erp_project, 0.0),
            "currency": doc.currency,
        })


'''

text = text[:start] + new_sales_block + text[end:]

payment_start = text.index("def on_payment_entry_submit(")
if "\ndef " in text[payment_start + 1:]:
    raise SystemExit("erp_triggers payment handler is no longer the final function; inspect manually")

new_payment_block = '''def on_payment_entry_submit(doc, method=None):
    """Fan each Sales Invoice allocation out to its contributing BP Projects.

    A shared invoice is one legal document but several project financial
    claims. Payment Entry.references carries only the invoice-level allocation,
    so use the same Sales Invoice Item net-share model as invoice submission to
    avoid assigning the whole payment to the arbitrary header project.
    """
    invoice_refs = [
        r for r in (doc.references or [])
        if r.reference_doctype == "Sales Invoice"
    ]
    if not invoice_refs:
        return

    from batch_projects.events import emit

    for ref in invoice_refs:
        si = frappe.db.get_value(
            "Sales Invoice",
            ref.reference_name,
            [
                "project",
                "customer",
                "currency",
                "outstanding_amount",
            ],
            as_dict=True,
        )
        if not si:
            continue

        project_weights = _sales_invoice_project_weights(
            ref.reference_name,
            si.project,
        )
        if not project_weights:
            continue

        amounts = _apportion(
            ref.allocated_amount,
            project_weights,
        )
        outstanding = _apportion(
            si.outstanding_amount,
            project_weights,
        )

        for erp_project, _weight in project_weights:
            bp_project = _bp_project_for(
                "Sales Invoice",
                ref.reference_name,
                erp_project,
            )
            if not bp_project:
                continue

            emit("erp.payment_received", {
                "project": bp_project,
                "invoice": ref.reference_name,
                "payment_entry": doc.name,
                "customer": si.customer,
                "amount": amounts.get(erp_project, 0.0),
                "outstanding": outstanding.get(erp_project, 0.0),
                "currency": si.currency,
            })
'''

text = text[:payment_start] + new_payment_block + "\n"
path.write_text(text)

# ---------------------------------------------------------------------------
# 2. Money Drawer Purchase Invoice tenancy + projection.
# ---------------------------------------------------------------------------
path = root / "batch_projects" / "api" / "erp_link.py"
text = path.read_text()

text = replace_once(
    text,
    '''    "Purchase Invoice": {
        "header": ["name", "status", "posting_date", "supplier", "currency", "grand_total"],
        "child_doctype": "Purchase Invoice Item",
        "child_key": "items",
        "child_fields": _ITEM_FIELDS,
    },''',
    '''    "Purchase Invoice": {
        "header": ["name", "status", "posting_date", "supplier", "currency", "grand_total"],
        "child_doctype": "Purchase Invoice Item",
        "child_key": "items",
        # Same security projection as Sales Invoice: item.project is
        # authoritative, with header fallback for blank legacy rows.
        "child_fields": _ITEM_FIELDS + ["project"],
    },''',
    "erp_link Purchase Invoice spec",
)

scope_marker = "\n\ndef _scope_sales_invoice_timesheets(\n"
if text.count(scope_marker) != 1:
    raise SystemExit("erp_link scope insertion marker changed")

purchase_scope = '''\n\ndef _scope_purchase_invoice_items(
    children,
    header_project,
    erp_project,
):
    """Return only Purchase Invoice Item rows attributable to `erp_project`.

    ERPNext accounting uses item.project or the Purchase Invoice header
    project. Mirror that exact precedence here, then remove the internal
    project field so the existing curated Money Drawer wire shape is stable.
    """
    scoped = []

    for child in children:
        item_project = (
            child.get("project")
            or header_project
        )

        if item_project != erp_project:
            continue

        row = dict(child)
        row.pop("project", None)
        scoped.append(row)

    return scoped
'''
text = text.replace(scope_marker, purchase_scope + scope_marker, 1)

tenant_marker = '''    return (
        frappe.db.get_value(
            doctype,
            name,
            "project",
        )
        == erp_project
    )
'''
if text.count(tenant_marker) != 1:
    raise SystemExit("erp_link tenant fallback marker changed")

purchase_tenant = '''    if doctype == "Purchase Invoice":
        header_project = frappe.db.get_value(
            "Purchase Invoice",
            name,
            "project",
        )

        if header_project == erp_project:
            return True

        # ERPNext posts PI accounting dimensions as item.project or the
        # header project. A project named explicitly on an item therefore owns
        # that slice of a shared PI even when the header names another project.
        return bool(frappe.db.exists(
            "Purchase Invoice Item",
            {
                "parent": name,
                "project": erp_project,
            },
        ))

'''
text = text.replace(tenant_marker, purchase_tenant + tenant_marker, 1)

sales_scope_block = '''    if doctype == "Sales Invoice":
        header_project = frappe.db.get_value(
            "Sales Invoice",
            name,
            "project",
        )

        children = _scope_sales_invoice_items(
            children,
            header_project,
            erp_project,
        )

'''
if text.count(sales_scope_block) != 1:
    raise SystemExit("erp_link Sales Invoice projection block changed")

purchase_projection = '''    if doctype == "Purchase Invoice":
        header_project = frappe.db.get_value(
            "Purchase Invoice",
            name,
            "project",
        )

        children = _scope_purchase_invoice_items(
            children,
            header_project,
            erp_project,
        )

'''
text = text.replace(
    sales_scope_block,
    sales_scope_block + purchase_projection,
    1,
)
path.write_text(text)

# ---------------------------------------------------------------------------
# 3. Margin Purchase Invoice costs: item project with header fallback.
# ---------------------------------------------------------------------------
path = root / "batch_projects" / "api" / "insights_data.py"
text = path.read_text()

old_purchase_query = '''    purchases = _query("Purchase Invoice Item", """
        SELECT pii.project, SUM(pii.base_net_amount) AS amount
        FROM `tabPurchase Invoice Item` pii
        JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent AND pi.docstatus = 1
        WHERE pii.project IN %(projects)s
          AND pi.posting_date >= %(from_date)s AND pi.posting_date <= %(to_date)s
        GROUP BY pii.project
    """, {"projects": erpnext_names, "from_date": from_date, "to_date": to_date})
'''

new_purchase_query = '''    purchases = _query("Purchase Invoice Item", """
        SELECT
            COALESCE(NULLIF(pii.project, ''), pi.project) AS project,
            SUM(pii.base_net_amount) AS amount
        FROM `tabPurchase Invoice Item` pii
        JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent AND pi.docstatus = 1
        WHERE COALESCE(NULLIF(pii.project, ''), pi.project) IN %(projects)s
          AND pi.posting_date >= %(from_date)s AND pi.posting_date <= %(to_date)s
        GROUP BY COALESCE(NULLIF(pii.project, ''), pi.project)
    """, {"projects": erpnext_names, "from_date": from_date, "to_date": to_date})
'''

text = replace_once(
    text,
    old_purchase_query,
    new_purchase_query,
    "insights_data Purchase Invoice margin query",
)
path.write_text(text)

# Self-delete so the branch contains only permanent code/tests after commit.
Path(__file__).unlink()
print("FIX41_PUBLIC_PATCH_OK")
