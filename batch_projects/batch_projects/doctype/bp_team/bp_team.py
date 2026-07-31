import frappe
from frappe.model.document import Document


class BPTeam(Document):
	def before_insert(self):
		# Auto-generate team_key from team_name if not set
		if not self.team_key:
			self.team_key = self._generate_key(self.team_name)

	def validate(self):
		self.team_key = self.team_key.upper().strip()
		if not self.team_key:
			frappe.throw("Team key is required")
		# Ensure uniqueness
		existing = frappe.db.get_value("BP Team", {"team_key": self.team_key, "name": ["!=", self.name]}, "name")
		if existing:
			frappe.throw(f"Team key '{self.team_key}' is already in use")

	def _generate_key(self, name):
		import re
		words = re.sub(r"[^a-zA-Z0-9\s]", "", name).split()
		if len(words) >= 2:
			return "".join(w[0] for w in words[:4]).upper()
		return name[:4].upper().replace(" ", "")