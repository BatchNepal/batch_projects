"""Regression coverage for BP Activity comment-mention authorization.

Recovered gap (BatchProjects git-audit, P0 #1): validate_comment_mentions()
already existed in task_invariants.py but was never wired into BPActivity, so
a comment (via board.py's add_comment/edit_comment, or any other doc.insert()/
doc.save() call — the doctype hook is what closes the direct-insert gap) could
mention a user with zero access to the task/project.

Run with:
    bench run-tests --module batch_projects.tests.test_activity_mention_invariants
"""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase


def _mention(name, uid):
    return f"@[{name}]({uid})"


class TestActivityMentionInvariant(FrappeTestCase):
    def test_comment_mentioning_unauthorized_user_is_rejected(self):
        activity = frappe.get_doc({
            "doctype": "BP Activity",
            "task": "TASK-1",
            "action_type": "Comment",
            "comment_text": f"heads up {_mention('Outsider', 'outsider@example.com')}",
            "user": "author@example.com",
        })

        with (
            patch.object(
                frappe.db, "get_value",
                return_value=frappe._dict(project="PROJ-A", name="TASK-1"),
            ),
            patch("batch_projects.task_invariants._user_can_view_task", return_value=False) as can_view,
            self.assertRaises(frappe.PermissionError),
        ):
            activity.validate()

        can_view.assert_called_once_with("PROJ-A", "TASK-1", "outsider@example.com", ())

    def test_comment_mentioning_authorized_user_is_allowed(self):
        activity = frappe.get_doc({
            "doctype": "BP Activity",
            "task": "TASK-1",
            "action_type": "Comment",
            "comment_text": f"cc {_mention('Viewer', 'viewer@example.com')}",
            "user": "author@example.com",
        })

        with (
            patch.object(
                frappe.db, "get_value",
                return_value=frappe._dict(project="PROJ-A", name="TASK-1"),
            ),
            patch("batch_projects.task_invariants._user_can_view_task", return_value=True) as can_view,
        ):
            activity.validate()

        can_view.assert_called_once_with("PROJ-A", "TASK-1", "viewer@example.com", ())

    def test_non_comment_activity_skips_mention_check_entirely(self):
        activity = frappe.get_doc({
            "doctype": "BP Activity",
            "task": "TASK-1",
            "action_type": "Assignment",
            "new_value": f"assigned to {_mention('Someone', 'someone@example.com')}",
            "user": "author@example.com",
        })

        with patch.object(frappe.db, "get_value") as get_value:
            activity.validate()

        get_value.assert_not_called()

    def test_comment_on_a_deleted_task_is_rejected(self):
        activity = frappe.get_doc({
            "doctype": "BP Activity",
            "task": "GONE-1",
            "action_type": "Comment",
            "comment_text": "no mentions here",
            "user": "author@example.com",
        })

        with (
            patch.object(frappe.db, "get_value", return_value=None),
            self.assertRaises(frappe.ValidationError),
        ):
            activity.validate()


if __name__ == "__main__":
    import unittest
    unittest.main()
