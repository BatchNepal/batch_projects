"""Engine-resolution + paid-matcher gate.

This covers the monetization boundary for automations, so it is deliberately
unit-level and dependency-free: it drives entitlements.automation_engine()
through frappe.conf directly rather than standing up rules and firing events.
The thing that must not silently regress is the RESOLUTION TABLE — which
engine a given deployment shape lands on — because the open Python matcher
refuses to run for anything but "gateway".

Run with:
    bench run-tests --module batch_projects.tests.test_automation_engine_gate
"""
import unittest
from contextlib import contextmanager

import frappe
from frappe.tests.utils import FrappeTestCase

from batch_projects.entitlements import automation_engine

_GATEWAY = "gateway"
_PYTHON = "python"


@contextmanager
def _conf(**overrides):
    """Temporarily set/remove site_config keys, restoring exactly what was
    there before — including keys that were genuinely absent, which a plain
    dict-assignment restore would resurrect as None and change behaviour."""
    sentinel = object()
    previous = {k: frappe.conf.get(k, sentinel) for k in overrides}
    try:
        for k, v in overrides.items():
            if v is None:
                frappe.conf.pop(k, None)
            else:
                frappe.conf[k] = v
        yield
    finally:
        for k, old in previous.items():
            if old is sentinel:
                frappe.conf.pop(k, None)
            else:
                frappe.conf[k] = old


class TestAutomationEngineResolution(FrappeTestCase):

    def test_gateway_fronted_site_derives_gateway(self):
        """The case this gate exists for: a licensed, gateway-fronted install
        that never hand-edited site_config. Nothing in the installer or
        bp-license bootstrap has ever set bp_automation_engine, so the old
        hardcoded "python" default silently put the PAID matcher on the open,
        patchable in-process path for every such tenant."""
        with _conf(bp_automation_engine=None, bp_gateway_shared_secret="a" * 64):
            self.assertEqual(automation_engine(), _GATEWAY)

    def test_site_without_gateway_stays_python(self):
        """No shared secret = no gateway = the tier can only ever resolve to
        `starter` (current_tier() only trusts a gateway-signed header), where
        automations are not entitled at all. Staying on "python" here is safe
        precisely because is_feature_enabled('automations') gates it first."""
        with _conf(bp_automation_engine=None, bp_gateway_shared_secret=None):
            self.assertEqual(automation_engine(), _PYTHON)

    def test_explicit_setting_wins_in_both_directions(self):
        """An operator who states an engine gets that engine — the derivation
        is only a DEFAULT, never an override."""
        with _conf(bp_automation_engine="gateway", bp_gateway_shared_secret=None):
            self.assertEqual(automation_engine(), _GATEWAY)
        with _conf(bp_automation_engine="python", bp_gateway_shared_secret="a" * 64):
            self.assertEqual(automation_engine(), _PYTHON)

    def test_value_is_normalised(self):
        """Casing/whitespace must not decide whether the paid matcher runs:
        every consumer compares against the literal "gateway"."""
        with _conf(bp_automation_engine="  GATEWAY  ", bp_gateway_shared_secret=None):
            self.assertEqual(automation_engine(), _GATEWAY)

    def test_empty_string_is_not_an_explicit_setting(self):
        """A blank value is an unset value, not a request for "" — otherwise
        it would fall through every == "gateway" check and disable automations
        on a gateway-fronted site."""
        with _conf(bp_automation_engine="", bp_gateway_shared_secret="a" * 64):
            self.assertEqual(automation_engine(), _GATEWAY)


class TestPaidMatcherRefusesOpenEngine(FrappeTestCase):
    """The gate itself: run_for_event/run_scheduled must not evaluate rules
    in-process when the engine is not the gateway, even for an entitled
    tenant. Action EXECUTION is deliberately NOT gated — the gateway engine
    calls back into it via api.automation.apply_action."""

    def test_run_scheduled_refuses_python_engine_while_entitled(self):
        from batch_projects.batch_projects.doctype.bp_automation_rule import (
            bp_automation_rule as engine_mod,
        )

        # Entitled tenant (so the tier check passes) pinned to the open engine.
        with _conf(bp_automation_engine="python", bp_gateway_shared_secret="a" * 64):
            frappe.cache().set_value("bp_current_tier", "business", expires_in_sec=60)
            try:
                status, message = engine_mod.run_scheduled("does-not-matter", {})
            finally:
                frappe.cache().delete_value("bp_current_tier")

        self.assertEqual(status, "Skipped")
        self.assertIn("gateway", message)
        # Must have refused on the ENGINE, not fallen through to the
        # rule-not-found branch — otherwise this test would still pass with
        # the gate deleted.
        self.assertNotIn("not found", message)


if __name__ == "__main__":
    unittest.main()
