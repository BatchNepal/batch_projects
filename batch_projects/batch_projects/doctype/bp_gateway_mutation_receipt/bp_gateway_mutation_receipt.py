from frappe.model.document import Document


class BPGatewayMutationReceipt(Document):
    """Minimal idempotency receipt for a committed gateway business mutation.

    This is not workflow/runtime state.  It exists only so an at-least-once
    gateway retry after a lost HTTP response cannot duplicate a final business
    side effect such as creating a task/comment/email.
    """

    pass
