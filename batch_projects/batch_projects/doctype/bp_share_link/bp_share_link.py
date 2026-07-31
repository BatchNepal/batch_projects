import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime, get_datetime


class BPShareLink(Document):
    def before_insert(self):
        if not self.token:
            # High-entropy bearer token — this is a capability URL. The doctype
            # is not web-readable, and the guest endpoint looks links up by token.
            self.token = frappe.generate_hash(length=48)
        if not self.access_level:
            self.access_level = "view"

    @property
    def is_expired(self) -> bool:
        return bool(self.expires_on) and get_datetime(self.expires_on) < now_datetime()

    @property
    def is_live(self) -> bool:
        return not self.revoked and not self.is_expired
