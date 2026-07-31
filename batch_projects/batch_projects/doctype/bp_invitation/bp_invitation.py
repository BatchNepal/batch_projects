import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime, get_datetime


class BPInvitation(Document):
    def before_insert(self):
        if not self.token:
            self.token = frappe.generate_hash(length=40)
        if not self.status:
            self.status = "Pending"

    @property
    def is_expired(self) -> bool:
        return bool(self.expires_on) and get_datetime(self.expires_on) < now_datetime()
