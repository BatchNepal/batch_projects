"""MariaDB regression for #49 Workflow Execution / Step lock inversion."""

import hashlib
import threading
import time
import unittest

import frappe

from batch_projects.tests.test_billing_reservation_concurrency import (
    _clone_current_connection,
    _connect_thread_site,
    _destroy_thread_site,
    _close,
)


def _step_key(execution_id, node_id):
    return hashlib.sha256(
        "\0".join(("workflow-step", execution_id, node_id)).encode()
    ).hexdigest()


class TestWorkflowLockOrderConcurrency(unittest.TestCase):
    def test_step_transitions_share_execution_then_step_lock_order(self):
        if frappe.conf.db_type != "mariadb":
            self.skipTest("This transaction-level regression targets MariaDB/InnoDB.")

        token = frappe.generate_hash(length=10)
        execution = f"BP-H4-WFE-{token}"
        step = f"BP-H4-WFS-{token}"
        node_id = "action"
        owner = f"gateway-{token}"
        generation = 1

        site = frappe.local.site
        sites_path = frappe.local.sites_path
        setup = _clone_current_connection()

        a_execution_locked = threading.Event()
        b_transition_started = threading.Event()

        result = {
            "a_error": None,
            "b_error": None,
            "a_transition_passed": False,
            "b_transition_passed": False,
        }

        try:
            setup.sql(
                """
                INSERT INTO `tabBP Workflow Execution`
                    (
                        name, creation, modified, modified_by, owner,
                        docstatus, idx, execution_key, workflow, event_id,
                        recovery_envelope, workflow_revision, definition_hash,
                        status, lease_owner, lease_generation, lease_expires_at
                    )
                VALUES
                    (
                        %(name)s, NOW(6), NOW(6), 'Administrator', 'Administrator',
                        0, 0, %(execution_key)s, %(workflow)s, %(event_id)s,
                        '{}', 1, %(definition_hash)s, 'running', %(lease_owner)s,
                        %(generation)s,
                        DATE_ADD(UTC_TIMESTAMP(6), INTERVAL 60 SECOND)
                    )
                """,
                {
                    "name": execution,
                    "execution_key": f"bp-h4-execution-{token}",
                    "workflow": f"BP-H4-WF-{token}",
                    "event_id": f"BP-H4-EVENT-{token}",
                    "definition_hash": f"hash-{token}",
                    "lease_owner": owner,
                    "generation": generation,
                },
            )
            setup.sql(
                """
                INSERT INTO `tabBP Workflow Step`
                    (
                        name, creation, modified, modified_by, owner,
                        docstatus, idx, step_key, execution, node_id,
                        effect_kind, status
                    )
                VALUES
                    (
                        %(name)s, NOW(6), NOW(6), 'Administrator', 'Administrator',
                        0, 0, %(step_key)s, %(execution)s, %(node_id)s,
                        'external', 'claimed'
                    )
                """,
                {
                    "name": step,
                    "step_key": _step_key(execution, node_id),
                    "execution": execution,
                    "node_id": node_id,
                },
            )
            setup.commit()

            def transaction_a():
                db = None
                try:
                    db = _connect_thread_site(site, sites_path)
                    db.sql("SET SESSION innodb_lock_wait_timeout = 3")

                    from batch_projects.workflow_execution import (
                        _require_live_lease,
                        begin_external_step,
                    )

                    _require_live_lease(
                        execution,
                        owner,
                        generation,
                        for_update=True,
                    )
                    a_execution_locked.set()

                    if not b_transition_started.wait(timeout=5):
                        raise AssertionError("transaction B never started its step transition")

                    # Pre-fix, finish_step() takes the Step lock from its joined
                    # UPDATE while waiting for this Execution lock. Give it a
                    # deterministic window to reach that wait before A asks for
                    # the same Step through begin_external_step().
                    time.sleep(0.30)

                    started = begin_external_step(
                        execution,
                        node_id,
                        owner,
                        generation,
                    )
                    if not started.get("dispatch_confirmed"):
                        raise AssertionError(
                            f"external transition was not confirmed: {started}"
                        )
                    result["a_transition_passed"] = True

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
                    if not a_execution_locked.wait(timeout=5):
                        raise AssertionError("transaction A never locked execution")

                    db = _connect_thread_site(site, sites_path)
                    db.sql("SET SESSION innodb_lock_wait_timeout = 3")

                    from batch_projects.workflow_execution import finish_step

                    b_transition_started.set()
                    finished = finish_step(
                        execution,
                        step,
                        owner,
                        generation,
                        "succeeded",
                        {"status": "Success"},
                    )
                    if finished.get("status") != "succeeded":
                        raise AssertionError(
                            f"finish transition did not succeed: {finished}"
                        )
                    result["b_transition_passed"] = True

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
            self.assertNotIsInstance(result["a_error"], frappe.QueryDeadlockError)
            self.assertNotIsInstance(result["b_error"], frappe.QueryDeadlockError)
            self.assertIsNone(result["a_error"])
            self.assertIsNone(result["b_error"])
            self.assertTrue(result["a_transition_passed"])
            self.assertTrue(result["b_transition_passed"])

        finally:
            try:
                setup.rollback()
                setup.sql(
                    "DELETE FROM `tabBP Workflow Step` WHERE name = %(name)s",
                    {"name": step},
                )
                setup.sql(
                    "DELETE FROM `tabBP Workflow Execution` WHERE name = %(name)s",
                    {"name": execution},
                )
                setup.commit()
            finally:
                _close(setup)


if __name__ == "__main__":
    unittest.main()
