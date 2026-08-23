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

		# Validate members: users exist, are assignable, no duplicates, and
		# incremental seat accounting covers the generic parent-save path
		# (child before_insert does not fire when members are appended here).
		if self.members:
			from batch_projects.task_invariants import _assert_assignable_user
			seen_users = set()
			for m in self.members:
				if not m.user:
					frappe.throw("Team member must have a user.", frappe.ValidationError)
				if m.user in seen_users:
					frappe.throw(f"Duplicate user in team members: {m.user}", frappe.ValidationError)
				seen_users.add(m.user)
				_assert_assignable_user(m.user)

			from batch_projects.entitlements import assert_seats_available, is_seated
			if not self.is_new():
				old_users = {
					r.user
					for r in frappe.get_all(
						"BP Team Member", filters={"parent": self.name}, fields=["user"]
					)
				}
				new_users = [u for u in seen_users - old_users if not is_seated(u)]
			else:
				new_users = [u for u in seen_users if not is_seated(u)]
			if new_users:
				assert_seats_available(len(new_users))

	def _generate_key(self, name):
		import re
		words = re.sub(r"[^a-zA-Z0-9\s]", "", name).split()
		if len(words) >= 2:
			return "".join(w[0] for w in words[:4]).upper()
		return name[:4].upper().replace(" ", "")