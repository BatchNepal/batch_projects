"""Temporary fail-closed patch helper for #37 billing internals.

Run once from any checkout of fix/37-billing-internals. It edits only the
four intended files and deletes itself after a successful patch so it cannot
remain in the final PR tree.
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


# 1) Generic currency -> company FX primitive.
replace_exact(
    "batch_projects/api/erp_link.py",
    '''    return (\n        company_currency,\n        target,\n        resolved_fx,\n    )\n\n\ndef _convert_billing_rate(\n''',
    '''    return (\n        company_currency,\n        target,\n        resolved_fx,\n    )\n\n\ndef _currency_to_company_fx(\n    company,\n    currency,\n    *,\n    company_currency=None,\n    fx_cache=None,\n):\n    \"\"\"Resolve one currency -> company-currency FX rate.\n\n    This helper is deliberately independent of invoice-target selection.\n    \"\"\"\n    source = _currency_code(currency)\n    company_currency = (\n        _currency_code(company_currency)\n        or _currency_code(\n            frappe.get_cached_value(\n                \"Company\", company, \"default_currency\"\n            )\n        )\n    )\n\n    if not company_currency:\n        frappe.throw(\n            f\"Company '{company}' has no Default Currency configured.\"\n        )\n    if not source:\n        frappe.throw(\n            \"Cannot resolve an exchange rate because the source currency is blank.\"\n        )\n    if source == company_currency:\n        return 1.0\n\n    key = (company, source)\n    if fx_cache is not None and key in fx_cache:\n        return fx_cache[key]\n\n    from erpnext.setup.utils import get_exchange_rate\n\n    try:\n        fx = get_exchange_rate(source, company_currency, nowdate())\n    except Exception:\n        fx = None\n\n    if fx in (None, \"\", 0, 0.0):\n        frappe.throw(\n            f\"No exchange rate configured for {source} → {company_currency}. \"\n            \"Add a Currency Exchange record before billing.\"\n        )\n\n    resolved = _validated_conversion_rate(\n        fx,\n        f\"Exchange rate {source} → {company_currency}\",\n    )\n    if fx_cache is not None:\n        fx_cache[key] = resolved\n    return resolved\n\n\ndef _convert_billing_rate(\n''',
)

replace_exact(
    "batch_projects/api/erp_link.py",
    '''    def to_company(currency_code):\n        if currency_code == company_currency:\n            return 1.0\n\n        if (\n            currency_code == target\n            and target_to_company not in (None, \"\")\n        ):\n            resolved = flt(target_to_company)\n            if resolved > 0:\n                return resolved\n\n        key = (company, currency_code)\n        if fx_cache is not None and key in fx_cache:\n            return fx_cache[key]\n\n        cc, tc, resolved = _resolve_invoice_currency(\n            company,\n            customer,\n            currency_code,\n            None,\n        )\n        resolved = flt(resolved)\n\n        if cc != company_currency or tc != currency_code or resolved <= 0:\n            frappe.throw(\n                f\"Could not resolve a valid exchange rate for \"\n                f\"{currency_code} → {company_currency}.\"\n            )\n\n        if fx_cache is not None:\n            fx_cache[key] = resolved\n\n        return resolved\n''',
    '''    def to_company(currency_code):\n        if currency_code == company_currency:\n            return 1.0\n\n        if (\n            currency_code == target\n            and target_to_company not in (None, \"\")\n        ):\n            resolved = flt(target_to_company)\n            if resolved > 0:\n                return resolved\n\n        return _currency_to_company_fx(\n            company,\n            currency_code,\n            company_currency=company_currency,\n            fx_cache=fx_cache,\n        )\n''',
)

# 2) Update rate-currency tests to patch the generic primitive.
replace_exact(
    "batch_projects/tests/test_billing_rate_currency.py",
    '''        with patch.object(\n            erp_link,\n            \"_resolve_invoice_currency\",\n            return_value=(\"NPR\", \"EUR\", 150.0),\n        ):\n''',
    '''        with patch.object(\n            erp_link,\n            \"_currency_to_company_fx\",\n            return_value=150.0,\n        ):\n''',
    expected=3,
)
replace_exact(
    "batch_projects/tests/test_billing_rate_currency.py",
    '''        with patch.object(\n            erp_link,\n            \"_resolve_invoice_currency\",\n            side_effect=frappe.ValidationError(\n                \"No exchange rate configured for EUR → NPR\"\n            ),\n        ):\n''',
    '''        with patch.object(\n            erp_link,\n            \"_currency_to_company_fx\",\n            side_effect=frappe.ValidationError(\n                \"No exchange rate configured for EUR → NPR\"\n            ),\n        ):\n''',
)
replace_exact(
    "batch_projects/tests/test_billing_rate_currency.py",
    '''            patch.object(\n                erp_link,\n                \"_resolve_invoice_currency\",\n                side_effect=[\n                    (\"NPR\", \"USD\", 137.5),\n                    (\"NPR\", \"EUR\", 150.0),\n                ],\n            ),\n''',
    '''            patch.object(\n                erp_link,\n                \"_resolve_invoice_currency\",\n                return_value=(\"NPR\", \"USD\", 137.5),\n            ),\n            patch.object(\n                erp_link,\n                \"_currency_to_company_fx\",\n                return_value=150.0,\n            ),\n''',
)
replace_exact(
    "batch_projects/tests/test_billing_rate_currency.py",
    '''class TestBillingRateCurrency(unittest.TestCase):\n    def test_price_list_rate_preserves_item_price_currency(self):\n''',
    '''class TestBillingRateCurrency(unittest.TestCase):\n    def test_currency_to_company_fx_same_currency_is_identity(self):\n        with patch(\n            \"erpnext.setup.utils.get_exchange_rate\"\n        ) as get_exchange_rate:\n            result = erp_link._currency_to_company_fx(\n                \"TEST-COMPANY\", \"NPR\", company_currency=\"NPR\"\n            )\n\n        self.assertEqual(result, 1.0)\n        get_exchange_rate.assert_not_called()\n\n    def test_currency_to_company_fx_uses_cache(self):\n        cache = {}\n        with patch(\n            \"erpnext.setup.utils.get_exchange_rate\",\n            return_value=150.0,\n        ) as get_exchange_rate:\n            first = erp_link._currency_to_company_fx(\n                \"TEST-COMPANY\", \"EUR\",\n                company_currency=\"NPR\", fx_cache=cache,\n            )\n            second = erp_link._currency_to_company_fx(\n                \"TEST-COMPANY\", \"EUR\",\n                company_currency=\"NPR\", fx_cache=cache,\n            )\n\n        self.assertEqual(first, 150.0)\n        self.assertEqual(second, 150.0)\n        self.assertEqual(cache[(\"TEST-COMPANY\", \"EUR\")], 150.0)\n        get_exchange_rate.assert_called_once()\n\n    def test_currency_to_company_fx_missing_rate_fails_generically(self):\n        with patch(\n            \"erpnext.setup.utils.get_exchange_rate\",\n            return_value=0,\n        ):\n            with self.assertRaisesRegex(\n                frappe.ValidationError,\n                \"No exchange rate configured for EUR → NPR\",\n            ):\n                erp_link._currency_to_company_fx(\n                    \"TEST-COMPANY\", \"EUR\", company_currency=\"NPR\"\n                )\n\n    def test_price_list_rate_preserves_item_price_currency(self):\n''',
)

# 3) Machine-noise tolerance for percent capacity only.
replace_exact(
    "batch_projects/milestone_billing.py",
    '''ACTIVE_STATUSES = frozenset({DRAFT, INVOICED})\n\n\ndef _database(db=None):\n''',
    '''ACTIVE_STATUSES = frozenset({DRAFT, INVOICED})\n\n# Tolerate machine-level floating-point noise only. Material over-reservation\n# must still fail closed.\nPERCENT_CAPACITY_EPSILON = 1e-9\n\n\ndef _database(db=None):\n''',
)
replace_exact(
    "batch_projects/milestone_billing.py",
    '''    if total > 100:\n''',
    '''    if total > 100 + PERCENT_CAPACITY_EPSILON:\n''',
)

# 4) Focused milestone regressions.
replace_exact(
    "batch_projects/tests/test_milestone_invoice_lifecycle.py",
    '''    def test_submit_moves_current_invoice_to_invoiced(self):\n''',
    '''    def test_percent_capacity_tolerates_binary_float_noise(self):\n        db = Mock()\n        db.sql.return_value = [\n            frappe._dict({\n                \"name\": \"MS-FIRST\",\n                \"invoice_percent\": 50,\n            })\n        ]\n\n        already = milestone_billing.assert_percent_capacity(\n            \"BP-PROJECT\", \"MS-SECOND\", 50.00000000001, db=db\n        )\n        self.assertEqual(already, 50)\n\n    def test_percent_capacity_still_rejects_material_overage(self):\n        db = Mock()\n        db.sql.return_value = [\n            frappe._dict({\n                \"name\": \"MS-FIRST\",\n                \"invoice_percent\": 50,\n            })\n        ]\n\n        with self.assertRaisesRegex(\n            frappe.ValidationError,\n            \"over its 100% budget\",\n        ):\n            milestone_billing.assert_percent_capacity(\n                \"BP-PROJECT\", \"MS-SECOND\", 50.000001, db=db\n            )\n\n    def test_submit_moves_current_invoice_to_invoiced(self):\n''',
)

# Remove this helper from the final tree after all replacements succeeded.
Path(__file__).unlink()
print("PATCH_OK")
