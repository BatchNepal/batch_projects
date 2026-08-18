"""Backfill BP Milestone invoice state from authoritative Sales Invoices."""

from batch_projects.milestone_billing import (
    reconcile_all_milestones,
)


def execute():
    # Idempotent by construction: each row is derived from current ERPNext
    # Sales Invoice existence/docstatus and only written when state differs.
    reconcile_all_milestones()
