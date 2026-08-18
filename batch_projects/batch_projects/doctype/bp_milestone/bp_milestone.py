from frappe.model.document import Document

from batch_projects.milestone_billing import (
    assert_milestone_deletable,
)


class BPMilestone(Document):
    def on_trash(self):
        # `self` may have been loaded before a competing invoice transaction.
        # The lifecycle helper re-reads this exact milestone with FOR UPDATE.
        assert_milestone_deletable(
            self.name
        )
