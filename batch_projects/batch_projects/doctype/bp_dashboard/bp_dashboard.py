import frappe
import json
from frappe.model.document import Document


class BPDashboard(Document):
    def validate(self):
        # Dashboards are the paid differentiator (unlike BP Report, where only
        # workspace-visibility is gated and per-project reports stay free) —
        # every BP Dashboard requires the feature, regardless of scope/visibility.
        from batch_projects.entitlements import require_feature
        require_feature("dashboards")
        if self.layout:
            try:
                json.loads(self.layout) if isinstance(self.layout, str) else self.layout
            except (json.JSONDecodeError, TypeError):
                frappe.throw("Dashboard layout must be valid JSON.")
