"""Generic REST must not be able to forge BP Notification rows."""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from batch_projects import notification_permissions as perms


class TestNotificationRestCreation(FrappeTestCase):
    @patch.object(perms, "_is_admin", return_value=False)
    def test_non_admin_cannot_create_local_notification_row(self, is_admin):
        doc = frappe._dict(
            __islocal=1,
            recipient="test72+info@batchnepal.com",
            notification_type="Comment",
            task="TASK-1",
            project="PRIVATE",
        )
        self.assertFalse(
            perms.has_permission(doc, user="test34+info@batchnepal.com", permission_type="create")
        )

    @patch.object(perms, "_is_admin", return_value=True)
    def test_instance_admin_keeps_maintenance_access(self, is_admin):
        doc = frappe._dict(__islocal=1, recipient="test72+info@batchnepal.com")
        self.assertTrue(
            perms.has_permission(doc, user="Administrator", permission_type="create")
        )
