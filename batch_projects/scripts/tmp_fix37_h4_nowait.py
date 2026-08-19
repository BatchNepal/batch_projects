"""Temporary one-shot helper for #37 H4 lock inversion hardening.

Applies a fail-fast NOWAIT claimant read, updates the unit contract, adds a
permanent MariaDB regression for the reproduced SI -> TSD / TSD -> SI cycle,
and then deletes itself so no helper remains in the PR tree.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def replace_exact(rel, old, new, expected=1):
    path = ROOT / rel
    text = path.read_text()
    count = text.count(old)
    if count != expected:
        raise SystemExit(
            f"STOP: {rel}: expected {expected} occurrence(s), found {count}"
        )
    path.write_text(text.replace(old, new))


replace_exact(
    "batch_projects/billing_reservation.py",
    '''    lock_clause = (\n        "FOR UPDATE"\n        if for_update\n        else ""\n    )\n\n    claims = db.sql(\n        f"""\n        SELECT\n            sit.timesheet_detail,\n            sit.parent,\n            si.docstatus\n        FROM `tabSales Invoice Timesheet` sit\n        INNER JOIN `tabSales Invoice` si\n            ON si.name = sit.parent\n        WHERE sit.timesheet_detail IN %(details)s\n          AND si.docstatus IN (0, 1)\n          {self_clause}\n        ORDER BY\n            sit.timesheet_detail ASC,\n            sit.parent ASC\n        {lock_clause}\n        """,\n        params,\n        as_dict=True,\n    )\n''',
    '''    lock_clause = (\n        "FOR UPDATE NOWAIT"\n        if for_update\n        else ""\n    )\n\n    try:\n        claims = db.sql(\n            f"""\n            SELECT\n                sit.timesheet_detail,\n                sit.parent,\n                si.docstatus\n            FROM `tabSales Invoice Timesheet` sit\n            INNER JOIN `tabSales Invoice` si\n                ON si.name = sit.parent\n            WHERE sit.timesheet_detail IN %(details)s\n              AND si.docstatus IN (0, 1)\n              {self_clause}\n            ORDER BY\n                sit.timesheet_detail ASC,\n                sit.parent ASC\n            {lock_clause}\n            """,\n            params,\n            as_dict=True,\n        )\n    except frappe.QueryTimeoutError:\n        if not for_update:\n            raise\n\n        _validation_error(\n            "These Timesheet Detail billing sources are being changed by "\n            "another Sales Invoice transaction. Nothing was created. "\n            "Retry after that transaction finishes."\n        )\n''',
)

replace_exact(
    "batch_projects/billing_reservation.py",
    '''    Generation calls this with ``for_update=True`` after locking its source\n    Timesheet Detail rows. That must remain a current locking read under\n    MariaDB/InnoDB Repeatable Read.\n''',
    '''    Generation calls this with ``for_update=True`` after locking its source\n    Timesheet Detail rows. That must remain a current locking read under\n    MariaDB/InnoDB Repeatable Read. The locking read is NOWAIT: waiting here\n    would invert ERPNext's Sales Invoice -> Timesheet update order during\n    submit/cancel and can deadlock with the already-held Timesheet Detail\n    mutex. Contention therefore fails closed and asks the caller to retry.\n''',
)

replace_exact(
    "batch_projects/tests/test_billing_reservation.py",
    '''        self.assertIn("FOR UPDATE", query)\n\n    def test_same_draft_is_self_excluded(self):\n''',
    '''        self.assertIn("FOR UPDATE", query)\n        self.assertIn("NOWAIT", query)\n\n    def test_same_draft_is_self_excluded(self):\n''',
)

new_test = ROOT / "batch_projects/tests/test_billing_lock_order_concurrency.py"
if new_test.exists():
    raise SystemExit(f"STOP: {new_test.relative_to(ROOT)} already exists")

new_test.write_text(r'''"""MariaDB regression for #37 Sales Invoice / Timesheet lock inversion."""

import threading
import time
import unittest

import frappe

from batch_projects.billing_reservation import (
    _live_claims,
    _lock_source_rows,
)
from batch_projects.tests.test_billing_reservation_concurrency import (
    _clone_current_connection,
    _connect_thread_site,
    _destroy_thread_site,
    _close,
)


class TestBillingLockOrderConcurrency(unittest.TestCase):
    def test_claimant_contention_fails_fast_instead_of_deadlocking(self):
        if frappe.conf.db_type != "mariadb":
            self.skipTest(
                "This transaction-level regression targets MariaDB/InnoDB."
            )

        token = frappe.generate_hash(length=10)
        detail = f"BP-H4-TSD-{token}"
        timesheet = f"BP-H4-TS-{token}"
        task = f"BP-H4-TASK-{token}"
        invoice = f"BP-H4-SI-{token}"
        child = f"BP-H4-SIT-{token}"

        site = frappe.local.site
        sites_path = frappe.local.sites_path
        setup = _clone_current_connection()

        a_si_locked = threading.Event()
        b_tsd_locked = threading.Event()
        b_claiming = threading.Event()

        result = {
            "a_error": None,
            "b_error": None,
            "a_tsd_update_passed": False,
            "b_claim_passed": False,
        }

        try:
            setup.sql(
                """
                INSERT INTO `tabTimesheet Detail`
                    (
                        name, creation, modified, modified_by, owner,
                        docstatus, idx, parent, parentfield, parenttype,
                        custom_bp_task, sales_invoice, is_billable
                    )
                VALUES
                    (
                        %(name)s, NOW(6), NOW(6), 'Administrator',
                        'Administrator', 1, 1, %(parent)s, 'time_logs',
                        'Timesheet', %(task)s, '', 1
                    )
                """,
                {
                    "name": detail,
                    "parent": timesheet,
                    "task": task,
                },
            )
            setup.sql(
                """
                INSERT INTO `tabSales Invoice`
                    (
                        name, creation, modified, modified_by, owner,
                        docstatus, idx
                    )
                VALUES
                    (
                        %(name)s, NOW(6), NOW(6), 'Administrator',
                        'Administrator', 0, 0
                    )
                """,
                {"name": invoice},
            )
            setup.sql(
                """
                INSERT INTO `tabSales Invoice Timesheet`
                    (
                        name, creation, modified, modified_by, owner,
                        docstatus, idx, parent, parentfield, parenttype,
                        timesheet_detail
                    )
                VALUES
                    (
                        %(name)s, NOW(6), NOW(6), 'Administrator',
                        'Administrator', 0, 1, %(parent)s, 'timesheets',
                        'Sales Invoice', %(detail)s
                    )
                """,
                {
                    "name": child,
                    "parent": invoice,
                    "detail": detail,
                },
            )
            setup.commit()

            def transaction_a():
                db = None
                try:
                    db = _connect_thread_site(site, sites_path)
                    db.sql("SET SESSION innodb_lock_wait_timeout = 3")

                    # Frappe updates/locks the Sales Invoice parent before
                    # ERPNext on_submit/on_cancel reaches Timesheet updates.
                    db.sql(
                        """
                        SELECT name
                        FROM `tabSales Invoice`
                        WHERE name = %(invoice)s
                        FOR UPDATE
                        """,
                        {"invoice": invoice},
                    )
                    a_si_locked.set()

                    if not b_tsd_locked.wait(timeout=5):
                        raise AssertionError(
                            "transaction B never locked Timesheet Detail"
                        )
                    if not b_claiming.wait(timeout=5):
                        raise AssertionError(
                            "transaction B never attempted claimant read"
                        )

                    # Give B a window to hit NOWAIT and roll back its TSD lock.
                    time.sleep(0.25)

                    db.sql(
                        """
                        UPDATE `tabTimesheet Detail`
                        SET sales_invoice = %(invoice)s
                        WHERE name = %(detail)s
                        """,
                        {
                            "invoice": invoice,
                            "detail": detail,
                        },
                    )
                    result["a_tsd_update_passed"] = True

                except Exception as exc:
                    result["a_error"] = exc
                finally:
                    if db is not None:
                        try:
                            db.rollback()
                        except Exception:
                            pass
                    _destroy_thread_site()

            def transaction_b():
                db = None
                try:
                    if not a_si_locked.wait(timeout=5):
                        raise AssertionError(
                            "transaction A never locked Sales Invoice"
                        )

                    db = _connect_thread_site(site, sites_path)
                    db.sql("SET SESSION innodb_lock_wait_timeout = 3")

                    rows, missing = _lock_source_rows(db, [detail])
                    if missing or not rows:
                        raise AssertionError(
                            f"could not lock source: missing={missing}"
                        )

                    b_tsd_locked.set()
                    b_claiming.set()

                    _live_claims(db, [detail])
                    result["b_claim_passed"] = True

                except Exception as exc:
                    result["b_error"] = exc
                finally:
                    if db is not None:
                        try:
                            db.rollback()
                        except Exception:
                            pass
                    _destroy_thread_site()

            thread_a = threading.Thread(target=transaction_a, daemon=True)
            thread_b = threading.Thread(target=transaction_b, daemon=True)
            thread_a.start()
            thread_b.start()
            thread_a.join(timeout=8)
            thread_b.join(timeout=8)

            self.assertFalse(thread_a.is_alive(), "transaction A hung")
            self.assertFalse(thread_b.is_alive(), "transaction B hung")
            self.assertIsNone(result["a_error"])
            self.assertTrue(result["a_tsd_update_passed"])
            self.assertFalse(result["b_claim_passed"])
            self.assertIsInstance(
                result["b_error"],
                frappe.ValidationError,
            )
            self.assertIn(
                "another Sales Invoice transaction",
                str(result["b_error"]),
            )
            self.assertNotIsInstance(
                result["a_error"],
                frappe.QueryDeadlockError,
            )
            self.assertNotIsInstance(
                result["b_error"],
                frappe.QueryDeadlockError,
            )

        finally:
            try:
                setup.rollback()
                setup.sql(
                    "DELETE FROM `tabSales Invoice Timesheet` "
                    "WHERE parent = %(invoice)s",
                    {"invoice": invoice},
                )
                setup.sql(
                    "DELETE FROM `tabSales Invoice` WHERE name = %(invoice)s",
                    {"invoice": invoice},
                )
                setup.sql(
                    "DELETE FROM `tabTimesheet Detail` WHERE name = %(detail)s",
                    {"detail": detail},
                )
                setup.commit()
            finally:
                _close(setup)


if __name__ == "__main__":
    unittest.main()
''')

Path(__file__).unlink()
print("H4_NOWAIT_PATCH_OK")
