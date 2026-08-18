import frappe
from frappe.model.document import Document


class BPTaskSequence(Document):
    """Single-row global counter backing BP Task.sequence_no.

    The counter is bumped atomically by
    ``batch_projects.batch_projects.doctype.bp_task.bp_task.next_task_sequence()``
    using the same LAST_INSERT_ID pattern as BP Project.get_next_issue_number().
    This controller carries no logic of its own — it exists so Frappe's
    controller resolution (frappe.model.base_document.import_controller, which
    hard-fails without the class) never blocks migrate or doc loads.
    """

    pass
