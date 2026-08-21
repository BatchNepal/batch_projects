# Copyright (c) 2026, Batch Nepal and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class BPNotification(Document):
    """Durable notification record.

    Task authorization is intentionally enforced when the notification is
    READ, not when this row is inserted. Recipient fan-out can contain stale
    watcher/rule entries; raising here for one revoked user would abort delivery
    to later authorized recipients in the same event. The notification center
    and generic REST permission hooks re-check current task access before any
    stored task metadata is exposed, while email/desktop re-check immediately
    before their own delivery.
    """

    pass
