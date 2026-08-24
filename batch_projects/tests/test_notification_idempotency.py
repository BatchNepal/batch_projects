"""Regression coverage for notification delivery idempotency (v1.1.8).

A double-fired event (retry, double-save, automation + built-in both
matching) must not create duplicate in-app records or duplicate emails for
the same (recipient, type, task, project, actor, message) within the dedup
window. Distinct occurrences (different message, different recipient, or
after the window) must still notify.

Fixtures use real team email addresses (shopyamuna@gmail.com,
batchnepal@gmail.com, hamrotimesofficial@gmail.com) so that no test ever
targets a fake address that could bounce and damage SES reputation. The
email channel is additionally disabled per-user (email_enabled=0) so no
email is actually sent during the run — the in-app dedup path is what is
under test.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from batch_projects import events


def _make_user(email, created):
    """Reuse an existing user (never delete a real account); create + track
    only when absent. Always returns the user name."""
    if frappe.db.exists("User", email):
        frappe.db.set_value("User", email, "enabled", 1)
        frappe.db.set_value("User", email, "user_type", "System User")
        frappe.clear_cache(user=email)
        frappe.db.commit()
        return email
    frappe.get_doc(
        {
            "doctype": "User",
            "email": email,
            "first_name": email.split("@")[0],
            "enabled": 1,
            "send_welcome_email": 0,
        }
    ).insert(ignore_permissions=True)
    frappe.db.set_value("User", email, "user_type", "System User")
    frappe.clear_cache(user=email)
    frappe.db.commit()
    created.append(email)
    return email


def _make_project(name):
    if frappe.db.exists("BP Project", name):
        frappe.delete_doc("BP Project", name, ignore_permissions=True, force=True)
    doc = frappe.get_doc(
        {
            "doctype": "BP Project",
            "project_name": name,
            "key": "IDEM01",
            "status": "Active",
            "visibility": "workspace",
        }
    )
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return doc.name


def _make_task(project, title):
    doc = frappe.get_doc(
        {
            "doctype": "BP Task",
            "title": title,
            "project": project,
            "status": "To Do",
        }
    )
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return doc.name


class TestNotificationIdempotency(FrappeTestCase):
    # Real team addresses — never fake/@example.com (SES bounce protection).
    USER_A = "shopyamuna@gmail.com"
    USER_B = "batchnepal@gmail.com"
    ACTOR = "hamrotimesofficial@gmail.com"

    def setUp(self):
        frappe.set_user("Administrator")
        self._created_users = []
        self.user_a = _make_user(self.USER_A, self._created_users)
        self.user_b = _make_user(self.USER_B, self._created_users)
        self.actor = _make_user(self.ACTOR, self._created_users)
        self.project = _make_project("Idem Project")
        self.task = _make_task(self.project, "Idem Task")
        # Disable the email channel for every test recipient so no real email
        # is ever sent during the run (outgoing SES is configured on this
        # bench). The in-app dedup path is what is under test.
        self._prefs = []
        for u in (self.user_a, self.user_b, self.actor):
            if frappe.db.exists("BP Notification Preference", u):
                frappe.delete_doc(
                    "BP Notification Preference", u, ignore_permissions=True, force=True
                )
            pref = frappe.get_doc(
                {
                    "doctype": "BP Notification Preference",
                    "user": u,
                    "email_enabled": 0,
                    "inapp_enabled": 1,
                }
            )
            pref.insert(ignore_permissions=True)
            self._prefs.append(u)
        frappe.db.commit()

    def tearDown(self):
        frappe.set_user("Administrator")
        # Remove every notification row the tests created (a stale row with
        # the same dedup_key would otherwise suppress the first delivery of a
        # later run — the dedup window is content-addressed).
        for u in (self.USER_A, self.USER_B, self.ACTOR):
            frappe.db.delete("BP Notification", {"recipient": u})
            # test_dedup_respects_mute creates a mute row; without cleanup it
            # survives into the next run and (because the task name is
            # regenerated identically) suppresses every delivery for that user.
            frappe.db.delete("BP Notification Mute", {"user": u})
        # Restore/remove preferences.
        for u in self._prefs:
            if frappe.db.exists("BP Notification Preference", u):
                frappe.delete_doc(
                    "BP Notification Preference", u, ignore_permissions=True, force=True
                )
        if frappe.db.exists("BP Task", self.task):
            frappe.delete_doc("BP Task", self.task, ignore_permissions=True, force=True)
        if frappe.db.exists("BP Project", self.project):
            frappe.delete_doc(
                "BP Project", self.project, ignore_permissions=True, force=True
            )
        # Only delete users this run created (never a pre-existing real one).
        for u in self._created_users:
            if frappe.db.exists("User", u):
                frappe.delete_doc("User", u, ignore_permissions=True, force=True)
        # Clear any Redis dedup markers left behind.
        frappe.cache().delete_keys("bp:notif_dedup:*")
        frappe.db.commit()

    def _count(self, recipient, ntype):
        return frappe.db.count(
            "BP Notification",
            {
                "recipient": recipient,
                "notification_type": ntype,
                "task": self.task,
            },
        )

    def test_duplicate_event_creates_single_notification(self):
        """The same event fired twice within the window → one in-app record."""
        msg = "actor assigned you to IDEM-1: Idem Task"
        events._create_notification(
            self.user_a, "Assignment", self.task, self.project, self.actor, msg
        )
        events._create_notification(
            self.user_a, "Assignment", self.task, self.project, self.actor, msg
        )
        self.assertEqual(self._count(self.user_a, "Assignment"), 1)

    def test_distinct_message_is_not_collapsed(self):
        """Two different messages (e.g. two distinct comments) both notify."""
        events._create_notification(
            self.user_a, "Comment", self.task, self.project, self.actor, "first comment"
        )
        events._create_notification(
            self.user_a,
            "Comment",
            self.task,
            self.project,
            self.actor,
            "second comment",
        )
        self.assertEqual(self._count(self.user_a, "Comment"), 2)

    def test_distinct_recipients_are_not_collapsed(self):
        """Each recipient is deduplicated independently."""
        msg = "actor commented on IDEM-1: first"
        events._create_notification(
            self.user_a, "Comment", self.task, self.project, self.actor, msg
        )
        events._create_notification(
            self.user_b, "Comment", self.task, self.project, self.actor, msg
        )
        self.assertEqual(self._count(self.user_a, "Comment"), 1)
        self.assertEqual(self._count(self.user_b, "Comment"), 1)

    def test_rule_notification_is_idempotent(self):
        """Rule fan-out deduplicates the same (recipient, message) too."""
        rule = frappe._dict({"rule_name": "Idem Rule", "name": "idem-rule"})
        events._create_rule_notification(
            self.user_a,
            rule,
            self.task,
            self.project,
            self.actor,
            "Routed by rule: Idem Rule",
            {"in_app"},
        )
        events._create_rule_notification(
            self.user_a,
            rule,
            self.task,
            self.project,
            self.actor,
            "Routed by rule: Idem Rule",
            {"in_app"},
        )
        self.assertEqual(self._count(self.user_a, "Rule"), 1)

    def test_dedup_key_is_stored_on_record(self):
        """The created record carries the dedup_key for durable dedup."""
        msg = "actor assigned you to IDEM-1: Idem Task"
        events._create_notification(
            self.user_a, "Assignment", self.task, self.project, self.actor, msg
        )
        row = frappe.db.get_value(
            "BP Notification",
            {
                "recipient": self.user_a,
                "notification_type": "Assignment",
                "task": self.task,
            },
            "dedup_key",
        )
        expected = events._dedup_key(
            self.user_a, "Assignment", self.task, self.project, self.actor, msg
        )
        self.assertEqual(row, expected)

    def test_dedup_key_is_content_addressed(self):
        """Same fields → same key; any field change → different key."""
        k1 = events._dedup_key(
            self.user_a, "Comment", self.task, self.project, self.actor, "hello"
        )
        k2 = events._dedup_key(
            self.user_a, "Comment", self.task, self.project, self.actor, "hello"
        )
        k3 = events._dedup_key(
            self.user_a, "Comment", self.task, self.project, self.actor, "world"
        )
        k4 = events._dedup_key(
            self.user_b, "Comment", self.task, self.project, self.actor, "hello"
        )
        self.assertEqual(k1, k2)
        self.assertNotEqual(k1, k3)
        self.assertNotEqual(k1, k4)

    def test_dedup_respects_mute(self):
        """A muted recipient gets nothing even on first delivery."""
        frappe.get_doc(
            {
                "doctype": "BP Notification Mute",
                "user": self.user_a,
                "task": self.task,
            }
        ).insert(ignore_permissions=True)
        frappe.db.commit()
        events._create_notification(
            self.user_a, "Comment", self.task, self.project, self.actor, "hello"
        )
        self.assertEqual(self._count(self.user_a, "Comment"), 0)
