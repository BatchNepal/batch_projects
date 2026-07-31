import frappe

# The Activity Type every task-timer-generated Timesheet Detail row is
# stamped with. Named as a constant since timers.py needs the
# exact same string.
TIMER_ACTIVITY_TYPE = "Project Work"


def after_install():
    """Create custom roles for batch_projects"""
    roles = [
        {"role_name": "BP Admin",   "desk_access": 1},
        {"role_name": "BP Manager", "desk_access": 1},
        {"role_name": "BP Member",  "desk_access": 1},
        {"role_name": "BP Viewer",  "desk_access": 0},
        # desk_access MUST be 1: the app only works for System Users, and a
        # user whose only role has desk_access=0 gets demoted by Frappe to
        # "Website User" (locking guests out of their own invited project).
        {"role_name": "BP Guest",   "desk_access": 1},
    ]
    for role in roles:
        if not frappe.db.exists("Role", role["role_name"]):
            frappe.get_doc({"doctype": "Role", **role}).insert(ignore_permissions=True)
            print(f"  Created role: {role['role_name']}")

    ensure_timer_activity_type()
    ensure_bp_task_accounting_dimension()

    frappe.db.commit()
    print("batch_projects installed successfully!")


def ensure_bp_task_accounting_dimension():
    """Register BP Task as an ERPNext Accounting Dimension.

    Idempotent — called from after_install AND from the
    create_bp_task_accounting_dimension patch, because on a fresh install
    Frappe marks all patches as already-executed without running them
    (set_all_patches_as_completed), so a patch alone would skip new sites.

    fieldname MUST be "bp_task" (= frappe.scrub("BP Task")): ERPNext's
    validate_company_in_accounting_dimension reads dimension values via
    scrub(document_type), not the registered fieldname, so any other name
    would silently bypass that validation path.

    Registering the dimension stamps `bp_task` onto all 56 doctypes ERPNext+
    HRMS list under accounting_dimension_doctypes — that's a side effect of
    reusing ERPNext's own mechanism, not 56 deliberate integration points.
    Only Purchase Invoice Item/Purchase Order Item are actually read
    anywhere (api/erp_link.py's materials cost) — Stock Entry/Stock Ledger
    Entry/GL Entry etc. carry the field but nothing in this app reads it,
    zero live usage today. Deliberately not
    wired further: no current template/customer signal for physical stock-
    consumption costing, and it's a large build for that thin a signal.
    """
    if not frappe.db.exists("DocType", "Accounting Dimension"):
        return  # erpnext not installed on this site

    if frappe.db.exists("Accounting Dimension", {"document_type": "BP Task"}):
        return

    from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import (
        make_dimension_in_accounting_doctypes,
    )

    dim = frappe.get_doc({
        "doctype": "Accounting Dimension",
        "document_type": "BP Task",
        "label": "BP Task",
        "fieldname": "bp_task",
    }).insert(ignore_permissions=True)

    # after_insert only ENQUEUES the custom-field creation (long queue,
    # after commit) — run it synchronously too so the fields exist by the
    # time this returns; the enqueued run then no-ops on its
    # field-already-exists check.
    make_dimension_in_accounting_doctypes(doc=dim)
    print("  Created Accounting Dimension: BP Task (fieldname=bp_task)")


def ensure_timer_activity_type():
    """Idempotent — also called from the create_project_work_activity_type
    patch so sites that installed batch_projects before the task timer
    shipped pick this up via bench migrate instead of a reinstall."""
    if frappe.db.exists("Activity Type", TIMER_ACTIVITY_TYPE):
        return
    frappe.get_doc({
        "doctype": "Activity Type",
        "activity_type": TIMER_ACTIVITY_TYPE,
    }).insert(ignore_permissions=True)
    print(f"  Created Activity Type: {TIMER_ACTIVITY_TYPE}")