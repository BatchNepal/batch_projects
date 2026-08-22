"""Keep Sales Invoice Timesheet.timesheet_detail indexed for reservation reads."""

import frappe

from frappe.custom.doctype.property_setter.property_setter import (
    make_property_setter,
)


DOCTYPE = "Sales Invoice Timesheet"
FIELD = "timesheet_detail"
INDEX_NAME = "bp_timesheet_detail_index"


def execute():
    # A naked custom DB index would be removed by a later Frappe schema sync
    # because ERPNext's stock DocField does not declare search_index=1.
    # Persist that metadata first.
    filters = {
        "doc_type": DOCTYPE,
        "field_name": FIELD,
        "property": "search_index",
    }

    existing = frappe.db.get_value(
        "Property Setter",
        filters,
        "name",
    )

    if existing:
        frappe.db.set_value(
            "Property Setter",
            existing,
            "value",
            "1",
            update_modified=False,
        )
    else:
        make_property_setter(
            DOCTYPE,
            FIELD,
            "search_index",
            "1",
            "Check",
            for_doctype=False,
            validate_fields_for_doctype=True,
            is_system_generated=True,
        )

    frappe.clear_cache(doctype=DOCTYPE)

    # MariaDB's add_index is idempotent by index name. This runs only during
    # migration, never inside the billing transaction.
    frappe.db.add_index(
        DOCTYPE,
        [FIELD],
        INDEX_NAME,
    )
