"""MariaDB proof for project-level milestone percentage serialization."""

import threading
import time
import unittest

import frappe
from frappe.database import get_db

from batch_projects.milestone_billing import (
    assert_percent_capacity,
    lock_generation_scope,
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


def _connect_thread_site(site, sites_path):
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

    connection = getattr(db, "_conn", None)
    if connection is not None:
        try:
            connection.close()
        except Exception:
            pass


class TestMilestoneInvoiceConcurrency(unittest.TestCase):
    def test_two_60_percent_milestones_cannot_both_reserve(self):
        if frappe.conf.db_type != "mariadb":
            self.skipTest(
                "Transaction proof currently targets MariaDB/InnoDB."
            )

        token = frappe.generate_hash(length=10)

        project = f"BP-MP-{token}"
        first = f"BP-MS-A-{token}"
        second = f"BP-MS-B-{token}"

        site = frappe.local.site
        sites_path = frappe.local.sites_path

        setup = _clone_current_connection()

        a_locked = threading.Event()
        b_attempting = threading.Event()

        result = {
            "a_error": None,
            "b_error": None,
            "b_passed": False,
        }

        try:
            setup.sql(
                """
                INSERT INTO `tabBP Project`
                    (
                        name,
                        creation,
                        modified,
                        modified_by,
                        owner,
                        docstatus,
                        idx,
                        project_name
                    )
                VALUES
                    (
                        %(name)s,
                        NOW(6),
                        NOW(6),
                        'Administrator',
                        'Administrator',
                        0,
                        0,
                        %(name)s
                    )
                """,
                {"name": project},
            )

            for name, title in (
                (first, "First 60%"),
                (second, "Second 60%"),
            ):
                setup.sql(
                    """
                    INSERT INTO `tabBP Milestone`
                        (
                            name,
                            creation,
                            modified,
                            modified_by,
                            owner,
                            docstatus,
                            idx,
                            project,
                            title,
                            status,
                            billing_type,
                            invoice_percent,
                            invoice_status
                        )
                    VALUES
                        (
                            %(name)s,
                            NOW(6),
                            NOW(6),
                            'Administrator',
                            'Administrator',
                            0,
                            0,
                            %(project)s,
                            %(title)s,
                            'Completed',
                            'Percent of Budget',
                            60,
                            'Not Invoiced'
                        )
                    """,
                    {
                        "name": name,
                        "project": project,
                        "title": title,
                    },
                )

            setup.commit()

            def transaction_a():
                db = None
                try:
                    db = _connect_thread_site(
                        site,
                        sites_path,
                    )

                    lock_generation_scope(
                        project,
                        first,
                        db=db,
                    )
                    assert_percent_capacity(
                        project,
                        first,
                        60,
                        db=db,
                    )

                    a_locked.set()

                    if not b_attempting.wait(timeout=5):
                        raise AssertionError(
                            "transaction B never attempted project lock"
                        )

                    # Give B time to reach the same project mutex.
                    time.sleep(0.25)

                    db.sql(
                        """
                        UPDATE `tabBP Milestone`
                        SET
                            invoice_status = 'Draft',
                            sales_invoice = 'SINV-FIRST'
                        WHERE name = %(name)s
                        """,
                        {"name": first},
                    )
                    db.commit()

                except Exception as exc:
                    result["a_error"] = exc
                    if db is not None:
                        try:
                            db.rollback()
                        except Exception:
                            pass
                    a_locked.set()
                finally:
                    _destroy_thread_site()

            def transaction_b():
                db = None
                try:
                    if not a_locked.wait(timeout=5):
                        raise AssertionError(
                            "transaction A never acquired reservation"
                        )

                    db = _connect_thread_site(
                        site,
                        sites_path,
                    )

                    b_attempting.set()

                    lock_generation_scope(
                        project,
                        second,
                        db=db,
                    )

                    assert_percent_capacity(
                        project,
                        second,
                        60,
                        db=db,
                    )

                    result["b_passed"] = True
                    db.rollback()

                except Exception as exc:
                    result["b_error"] = exc
                    if db is not None:
                        try:
                            db.rollback()
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
                "both 60% milestones reserved the same project budget",
            )

            self.assertIsInstance(
                result["b_error"],
                frappe.ValidationError,
            )

            self.assertIn(
                "over its 100% budget",
                str(result["b_error"]),
            )

        finally:
            try:
                setup.sql(
                    """
                    DELETE FROM `tabBP Milestone`
                    WHERE name IN %(names)s
                    """,
                    {"names": (first, second)},
                )
                setup.sql(
                    """
                    DELETE FROM `tabBP Project`
                    WHERE name = %(name)s
                    """,
                    {"name": project},
                )
                setup.commit()
            finally:
                _close(setup)


if __name__ == "__main__":
    unittest.main()
