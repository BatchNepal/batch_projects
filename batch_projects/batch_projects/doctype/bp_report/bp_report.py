import frappe
import json
from frappe.model.document import Document


class BPReport(Document):
    def validate(self):
        # Shared/workspace-visible dashboards are a premium feature.
        # Private project-scoped reports stay free.
        if self.visibility == "workspace":
            from batch_projects.entitlements import require_feature
            require_feature("dashboards")
        if self.layout:
            try:
                json.loads(self.layout) if isinstance(self.layout, str) else self.layout
            except (json.JSONDecodeError, TypeError):
                frappe.throw("Report layout must be valid JSON.")
