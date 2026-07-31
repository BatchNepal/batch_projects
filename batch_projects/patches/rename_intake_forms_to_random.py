"""
BP Intake Form used to autoname on
`form_title` — the exact text an admin typed as the form's title — and that
name IS the public URL (`/intake/<name>`, allow_guest=True). A form titled
"Bug Report" or "Contact Us" lived at a guessable, enumerable public URL,
unlike every other token-bearing doctype in this app (BP Share Link, BP
Webhook Token, BP Invitation), which all use random hash naming.

The doctype JSON now autonames on `hash` going forward (see
bp_intake_form.json). This patch renames every EXISTING record to a random
hash name so already-created forms stop living at a guessable URL too.
frappe.rename_doc updates any Link-field references site-wide (there are
none into BP Intake Form today, but this is the correct primitive
regardless — it's what the framework itself uses for its own renames).

This intentionally changes the public URL of any intake form created before
this patch runs. That is the point, not a side effect — call it out in
release notes for any site that already has forms distributed to guests.
"""

import frappe


def execute():
    if not frappe.db.table_exists("BP Intake Form"):
        return

    forms = frappe.get_all("BP Intake Form", pluck="name")
    for old_name in forms:
        new_name = frappe.generate_hash(length=10)
        # Vanishingly unlikely, but stay correct if it ever collides.
        while frappe.db.exists("BP Intake Form", new_name):
            new_name = frappe.generate_hash(length=10)
        frappe.rename_doc("BP Intake Form", old_name, new_name, force=True, ignore_permissions=True)

    frappe.db.commit()
