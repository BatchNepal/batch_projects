"""
Create the "Project Work" Activity Type the task timer depends on.

after_install only runs on fresh installs; sites that installed
batch_projects before the task timer shipped need this backfilled via bench migrate.
"""

import frappe

from batch_projects.setup.install import ensure_timer_activity_type


def execute():
    ensure_timer_activity_type()
    frappe.db.commit()
