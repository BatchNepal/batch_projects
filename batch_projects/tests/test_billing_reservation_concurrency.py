"""MariaDB integration regression for overlapping billing reservations."""

import threading
import time
import unittest

import frappe

from frappe.database import get_db

from batch_projects.billing_reservation import (
    _guard_timesheet_details_with_db,
)


def _clone_current_connection():
    source = frappe.db

    db = get_db(
        host=source.host,
        user=source.user,
        password=source.password,
        port=source.port,
        cur_db_name=source.cur_db_name,
        socket=source.socket,
    )
    db.connect()
    return db


def _close(db):
    try:
        db.rollback()
    except Exception:
        pass

    connection = getattr(db, "_conn", None)
    if connection is not None:
        try:
            connection.close()
        except Exception:
            pass


class TestBillingReservationConcurrency(unittest.TestCase):
    def test_timesheet_detail_claim_index_exists(self):
        index = frappe.db.get_column_index(
            "tabSales Invoice Timesheet",
            "timesheet_detail",
        )
        self.assertIsNotNone(index)

    def test_overlapping_transactions_cannot_both_claim_source(self):
        if frappe.conf.db_type != "mariadb":
            self.skipTest(
                "This transaction-level probe currently targets MariaDB/InnoDB."
            )

        token = frappe.generate_hash(length=10)
        detail = f"BP-RES-TSD-{token}"
        timesheet = f"BP-RES-TS-{token}"
        task = f"BP-RES-TASK-{token}"
        invoice = f"BP-RES-SI-{token}"
        child = f"BP-RES-SIT-{token}"

        setup = _clone_current_connection()
        db_a = _clone_current_connection()
        db_b = _clone_current_connection()

        a_locked = threading.Event()
        b_attempting = threading.Event()

        result = {
            "a_error": None,
            "b_error": None,
            "b_passed": False,
        }

        try:
            # Raw fixture rows are deliberate here: the regression is testing
            # database serialization, not Sales Invoice business validation.
            # Frappe does not declare SQL foreign keys between these tables.
            setup.sql(
                """
                INSERT INTO `tabTimesheet Detail`
                    (
                        name,
                        creation,
                        modified,
                        modified_by,
                        owner,
                        docstatus,
                        idx,
                        parent,
                        parentfield,
                        parenttype,
                        custom_bp_task,
                        sales_invoice
                    )
                VALUES
                    (
                        %(name)s,
                        NOW(6),
                        NOW(6),
                        'Administrator',
                        'Administrator',
                        1,
                        1,
                        %(parent)s,
                        'time_logs',
                        'Timesheet',
                        %(task)s,
                        ''
                    )
                """,
                {
                    "name": detail,
                    "parent": timesheet,
                    "task": task,
                },
            )
            setup.commit()

            def transaction_a():
                try:
                    _guard_timesheet_details_with_db(
                        db_a,
                        [detail],
                        enforce_all_sources=False,
                    )

                    # Guard passed and this transaction still owns the source
                    # row lock.
                    a_locked.set()

                    if not b_attempting.wait(timeout=5):
                        raise AssertionError(
                            "transaction B never attempted the same source"
                        )

                    # Give B a deterministic window to reach the row lock and
                    # wait behind A before A creates the live draft claim.
                    time.sleep(0.25)

                    db_a.sql(
                        """
                        INSERT INTO `tabSales Invoice`
                            (
                                name,
                                creation,
                                modified,
                                modified_by,
                                owner,
                                docstatus,
                                idx
                            )
                        VALUES
                            (
                                %(name)s,
                                NOW(6),
                                NOW(6),
                                'Administrator',
                                'Administrator',
                                0,
                                0
                            )
                        """,
                        {"name": invoice},
                    )

                    db_a.sql(
                        """
                        INSERT INTO `tabSales Invoice Timesheet`
                            (
                                name,
                                creation,
                                modified,
                                modified_by,
                                owner,
                                docstatus,
                                idx,
                                parent,
                                parentfield,
                                parenttype,
                                timesheet_detail
                            )
                        VALUES
                            (
                                %(name)s,
                                NOW(6),
                                NOW(6),
                                'Administrator',
                                'Administrator',
                                0,
                                1,
                                %(parent)s,
                                'timesheets',
                                'Sales Invoice',
                                %(detail)s
                            )
                        """,
                        {
                            "name": child,
                            "parent": invoice,
                            "detail": detail,
                        },
                    )

                    db_a.commit()

                except Exception as exc:
                    result["a_error"] = exc
                    try:
                        db_a.rollback()
                    except Exception:
                        pass
                    a_locked.set()

            def transaction_b():
                try:
                    if not a_locked.wait(timeout=5):
                        raise AssertionError(
                            "transaction A never acquired the source lock"
                        )

                    b_attempting.set()

                    _guard_timesheet_details_with_db(
                        db_b,
                        [detail],
                        enforce_all_sources=False,
                    )

                    result["b_passed"] = True
                    db_b.rollback()

                except Exception as exc:
                    result["b_error"] = exc
                    try:
                        db_b.rollback()
                    except Exception:
                        pass

            thread_a = threading.Thread(
                target=transaction_a,
                daemon=True,
            )
            thread_b = threading.Thread(
                target=transaction_b,
                daemon=True,
            )

            thread_a.start()
            thread_b.start()

            thread_a.join(timeout=10)
            thread_b.join(timeout=10)

            self.assertFalse(
                thread_a.is_alive(),
                "transaction A deadlocked",
            )
            self.assertFalse(
                thread_b.is_alive(),
                "transaction B deadlocked",
            )

            if result["a_error"]:
                raise result["a_error"]

            self.assertFalse(
                result["b_passed"],
                "both overlapping transactions passed the reservation guard",
            )
            self.assertIsInstance(
                result["b_error"],
                frappe.ValidationError,
            )
            self.assertIn(
                invoice,
                str(result["b_error"]),
            )

        finally:
            # B has rolled back and released its row lock by this point.
            try:
                setup.sql(
                    """
                    DELETE FROM `tabSales Invoice Timesheet`
                    WHERE parent = %(invoice)s
                    """,
                    {"invoice": invoice},
                )
                setup.sql(
                    """
                    DELETE FROM `tabSales Invoice`
                    WHERE name = %(invoice)s
                    """,
                    {"invoice": invoice},
                )
                setup.sql(
                    """
                    DELETE FROM `tabTimesheet Detail`
                    WHERE name = %(detail)s
                    """,
                    {"detail": detail},
                )
                setup.commit()
            finally:
                _close(db_a)
                _close(db_b)
                _close(setup)


if __name__ == "__main__":
    unittest.main()
