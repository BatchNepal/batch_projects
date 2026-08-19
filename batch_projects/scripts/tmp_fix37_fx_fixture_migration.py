"""Temporary one-shot helper to migrate two integration fixtures to #37 FX seams.

This file deletes itself after exact replacements succeed so it is absent from
the final PR tree.
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


# generate_invoice integration: target resolver owns USD invoice FX only;
# generic source helper owns EUR -> NPR.
replace_exact(
    "batch_projects/tests/test_generate_invoice_rate_currency.py",
    '''            if currency == "EUR":\n                self.assertIsNone(conversion_rate)\n                self.assertIsNone(project_currency)\n                return "NPR", "EUR", 150.0\n\n            raise AssertionError(\n''',
    '''            raise AssertionError(\n''',
)

replace_exact(
    "batch_projects/tests/test_generate_invoice_rate_currency.py",
    '''            raise AssertionError(\n                f"unexpected currency resolution: {currency!r}, {conversion_rate!r}"\n            )\n\n        with (\n''',
    '''            raise AssertionError(\n                f"unexpected currency resolution: {currency!r}, {conversion_rate!r}"\n            )\n\n        def resolve_source_fx(\n            company, currency, *, company_currency=None, fx_cache=None\n        ):\n            self.assertEqual(company, "TEST-COMPANY")\n            self.assertEqual(currency, "EUR")\n            self.assertEqual(company_currency, "NPR")\n            self.assertIsNotNone(fx_cache)\n            return 150.0\n\n        with (\n''',
)

replace_exact(
    "batch_projects/tests/test_generate_invoice_rate_currency.py",
    '''            patch.object(\n                erp_link,\n                "_resolve_invoice_currency",\n                side_effect=resolve_currency,\n            ),\n            patch.object(erp_link.frappe, "get_all", return_value=[]),\n''',
    '''            patch.object(\n                erp_link,\n                "_resolve_invoice_currency",\n                side_effect=resolve_currency,\n            ),\n            patch.object(\n                erp_link,\n                "_currency_to_company_fx",\n                side_effect=resolve_source_fx,\n            ),\n            patch.object(erp_link.frappe, "get_all", return_value=[]),\n''',
)

# Mixed-currency integration: same seam split, once per subtest.
replace_exact(
    "batch_projects/tests/test_billing_mixed_currency.py",
    '''                    if currency == "EUR":\n                        self.assertIsNone(\n                            conversion_rate\n                        )\n                        self.assertIsNone(\n                            project_currency\n                        )\n                        return (\n                            "NPR",\n                            "EUR",\n                            150.0,\n                        )\n\n                    raise AssertionError(\n''',
    '''                    raise AssertionError(\n''',
)

replace_exact(
    "batch_projects/tests/test_billing_mixed_currency.py",
    '''                    raise AssertionError(\n                        f"unexpected currency resolution: {currency!r}"\n                    )\n\n                with (\n''',
    '''                    raise AssertionError(\n                        f"unexpected currency resolution: {currency!r}"\n                    )\n\n                def resolve_source_fx(\n                    company, currency, *, company_currency=None, fx_cache=None\n                ):\n                    self.assertEqual(company, "TEST-COMPANY")\n                    self.assertEqual(currency, "EUR")\n                    self.assertEqual(company_currency, "NPR")\n                    self.assertIsNotNone(fx_cache)\n                    return 150.0\n\n                with (\n''',
)

replace_exact(
    "batch_projects/tests/test_billing_mixed_currency.py",
    '''                    patch.object(\n                        erp_link,\n                        "_resolve_invoice_currency",\n                        side_effect=resolve_currency,\n                    ),\n                    patch.object(\n                        erp_link.frappe,\n                        "get_all",\n''',
    '''                    patch.object(\n                        erp_link,\n                        "_resolve_invoice_currency",\n                        side_effect=resolve_currency,\n                    ),\n                    patch.object(\n                        erp_link,\n                        "_currency_to_company_fx",\n                        side_effect=resolve_source_fx,\n                    ),\n                    patch.object(\n                        erp_link.frappe,\n                        "get_all",\n''',
)

Path(__file__).unlink()
print("FX_FIXTURE_PATCH_OK")
