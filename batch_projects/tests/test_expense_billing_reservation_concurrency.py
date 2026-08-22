"""MariaDB integration regression for Expense Claim Detail reservation."""

import threading
import time
import unittest

import frappe

from frappe.database import get_db

from batch_projects.expense_reservation import (
    _guard_expense_claim_details_with_db,
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


def _connect_thread_site(
    site,
    sites_path,
):
    frappe.init(
        site=site,
        sites_path=sites_path,
    )

    frappe.connect()
    frappe.flags.in_test = True

    return frappe.db


def _destroy_thread_site():
    try:
        frappe.destroy()
    except Exception:
        pass


def _close(db):
    try:
        db.rollback()
    except Exception:
        pass

    connection = getattr(
        db,
        "_conn",
        None,
    )

    if connection is not None:
        try:
            connection.close()
        except Exception:
            pass


class TestExpenseBillingReservationConcurrency(
    unittest.TestCase
):
    def test_overlapping_transactions_cannot_both_claim_expense_source(self):
        if frappe.conf.db_type != "mariadb":
            self.skipTest(
                "This transaction-level probe targets MariaDB/InnoDB."
            )

        token = frappe.generate_hash(
            length=10
        )

        project = (
            f"BP-EXP-PROJ-{token}"
        )

        claim = (
            f"BP-EXP-EC-{token}"
        )

        detail = (
            f"BP-EXP-ECD-{token}"
        )

        invoice = (
            f"BP-EXP-SI-{token}"
        )

        site = frappe.local.site
        sites_path = (
            frappe.local.sites_path
        )

        setup = (
            _clone_current_connection()
        )

        a_locked = threading.Event()
        b_attempting = threading.Event()

        result = {
            "a_error": None,
            "b_error": None,
            "b_passed": False,
        }

        try:
            # Raw fixture rows are deliberate: this test proves database
            # serialization, not Expense Claim controller validation.
            setup.sql(
                """
                INSERT INTO `tabExpense Claim`
                    (
                        name,
                        creation,
                        modified,
                        modified_by,
                        owner,
                        docstatus,
                        idx,
                        project,
                        posting_date
                    )
                VALUES
                    (
                        %(name)s,
                        NOW(6),
                        NOW(6),
                        'Administrator',
                        'Administrator',
                        1,
                        0,
                        %(project)s,
                        CURDATE()
                    )
                """,
                {
                    "name": claim,
                    "project": project,
                },
            )

            setup.sql(
                """
                INSERT INTO `tabExpense Claim Detail`
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
                        sanctioned_amount,
                        custom_is_billable,
                        custom_sales_invoice
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
                        'expenses',
                        'Expense Claim',
                        100,
                        1,
                        ''
                    )
                """,
                {
                    "name": detail,
                    "parent": claim,
                },
            )

            setup.commit()

            def transaction_a():
                db_a = None

                try:
                    db_a = (
                        _connect_thread_site(
                            site,
                            sites_path,
                        )
                    )

                    rows = (
                        _guard_expense_claim_details_with_db(
                            db_a,
                            [detail],
                            project,
                        )
                    )

                    if len(rows) != 1:
                        raise AssertionError(
                            "transaction A did not lock exactly one source"
                        )

                    a_locked.set()

                    if not b_attempting.wait(
                        timeout=5
                    ):
                        raise AssertionError(
                            "transaction B never attempted the source"
                        )

                    # Give B a deterministic window to block behind A's
                    # parent/source locks.
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
                        {
                            "name": invoice,
                        },
                    )

                    db_a.sql(
                        """
                        UPDATE `tabExpense Claim Detail`
                        SET custom_sales_invoice = %(invoice)s
                        WHERE name = %(detail)s
                        """,
                        {
                            "invoice": invoice,
                            "detail": detail,
                        },
                    )

                    db_a.commit()

                except Exception as exc:
                    result["a_error"] = exc

                    if db_a is not None:
                        try:
                            db_a.rollback()
                        except Exception:
                            pass

                    a_locked.set()

                finally:
                    _destroy_thread_site()

            def transaction_b():
                db_b = None

                try:
                    if not a_locked.wait(
                        timeout=5
                    ):
                        raise AssertionError(
                            "transaction A never acquired the source lock"
                        )

                    db_b = (
                        _connect_thread_site(
                            site,
                            sites_path,
                        )
                    )

                    b_attempting.set()

                    _guard_expense_claim_details_with_db(
                        db_b,
                        [detail],
                        project,
                    )

                    result[
                        "b_passed"
                    ] = True

                    db_b.rollback()

                except Exception as exc:
                    result["b_error"] = exc

                    if db_b is not None:
                        try:
                            db_b.rollback()
                        except Exception:
                            pass

                finally:
                    _destroy_thread_site()

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

            thread_a.join(
                timeout=10
            )

            thread_b.join(
                timeout=10
            )

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
                "both transactions claimed the same expense source",
            )

            self.assertIsInstance(
                result["b_error"],
                frappe.ValidationError,
            )

            self.assertIn(
                invoice,
                str(
                    result["b_error"]
                ),
            )

        finally:
            try:
                setup.sql(
                    """
                    DELETE FROM `tabSales Invoice`
                    WHERE name = %(invoice)s
                    """,
                    {
                        "invoice": invoice,
                    },
                )

                setup.sql(
                    """
                    DELETE FROM `tabExpense Claim Detail`
                    WHERE name = %(detail)s
                    """,
                    {
                        "detail": detail,
                    },
                )

                setup.sql(
                    """
                    DELETE FROM `tabExpense Claim`
                    WHERE name = %(claim)s
                    """,
                    {
                        "claim": claim,
                    },
                )

                setup.commit()

            finally:
                _close(setup)


if __name__ == "__main__":
    unittest.main()
