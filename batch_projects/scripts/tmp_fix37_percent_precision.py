"""One-shot #37 correction: use Frappe field precision for milestone capacity."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def replace_exact(rel, old, new, expected=1):
    path = ROOT / rel
    text = path.read_text()
    count = text.count(old)
    if count != expected:
        raise SystemExit(f"STOP: {rel}: expected {expected} occurrence(s), found {count}")
    path.write_text(text.replace(old, new))


replace_exact(
    "batch_projects/milestone_billing.py",
    '''ACTIVE_STATUSES = frozenset({DRAFT, INVOICED})\n\n# Tolerate machine-level floating-point noise only. Material over-reservation\n# must still fail closed.\nPERCENT_CAPACITY_EPSILON = 1e-9\n\n\ndef _database(db=None):\n''',
    '''ACTIVE_STATUSES = frozenset({DRAFT, INVOICED})\n\n\ndef _percent_capacity_precision():\n    \"\"\"Return Frappe's configured precision for milestone percentages.\"\"\"\n    from frappe.model.meta import get_field_precision\n\n    field = frappe.get_meta(\"BP Milestone\").get_field(\"invoice_percent\")\n    if not field:\n        frappe.throw(\"BP Milestone.invoice_percent metadata is unavailable.\")\n\n    return get_field_precision(field)\n\n\ndef _database(db=None):\n''',
)

replace_exact(
    "batch_projects/milestone_billing.py",
    '''    requested = flt(invoice_percent)\n    total = already + requested\n\n    if total > 100 + PERCENT_CAPACITY_EPSILON:\n''',
    '''    precision = _percent_capacity_precision()\n    already = flt(already, precision)\n    requested = flt(invoice_percent, precision)\n    total = flt(already + requested, precision)\n\n    if total > flt(100, precision):\n''',
)

replace_exact(
    "batch_projects/tests/test_milestone_invoice_lifecycle.py",
    '''from unittest.mock import Mock\n''',
    '''from unittest.mock import Mock, patch\n''',
)

replace_exact(
    "batch_projects/tests/test_milestone_invoice_lifecycle.py",
    '''        already = milestone_billing.assert_percent_capacity(\n            \"BP-PROJECT\", \"MS-SECOND\", 50.00000000001, db=db\n        )\n        self.assertEqual(already, 50)\n''',
    '''        with patch.object(\n            milestone_billing,\n            \"_percent_capacity_precision\",\n            return_value=3,\n        ):\n            already = milestone_billing.assert_percent_capacity(\n                \"BP-PROJECT\", \"MS-SECOND\", 50.0004, db=db\n            )\n\n        self.assertEqual(already, 50)\n''',
)

replace_exact(
    "batch_projects/tests/test_milestone_invoice_lifecycle.py",
    '''        with self.assertRaisesRegex(\n            frappe.ValidationError,\n            \"over its 100% budget\",\n        ):\n            milestone_billing.assert_percent_capacity(\n                \"BP-PROJECT\", \"MS-SECOND\", 50.000001, db=db\n            )\n''',
    '''        with patch.object(\n            milestone_billing,\n            \"_percent_capacity_precision\",\n            return_value=3,\n        ):\n            with self.assertRaisesRegex(\n                frappe.ValidationError,\n                \"over its 100% budget\",\n            ):\n                milestone_billing.assert_percent_capacity(\n                    \"BP-PROJECT\", \"MS-SECOND\", 50.0006, db=db\n                )\n''',
)

Path(__file__).unlink()
print("PRECISION_PATCH_OK")
