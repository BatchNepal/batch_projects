"""Source contract: realtime badge events are invalidations, not trusted counts."""

from pathlib import Path

from frappe.tests.utils import FrappeTestCase


class TestNotificationRealtimeContract(FrappeTestCase):
    def test_realtime_badge_refetches_authorized_count(self):
        root = Path(__file__).resolve().parents[2]
        source = (root / "frontend" / "src" / "utils" / "realtime.js").read_text()

        self.assertIn("getNotificationCount", source)
        self.assertIn('payload?.event === "notification.badge"', source)
        self.assertIn("result?.unread_count", source)
        self.assertIn("count_authoritative: true", source)

        # The raw SSE value may remain in the spread payload, but it must be
        # overwritten by a secure API result before delivery to listeners.
        secure_override = source.index("unread_count: result?.unread_count")
        handler_delivery = source.index("_deliver({", source.index('payload?.event === "notification.badge"'))
        self.assertGreaterEqual(secure_override, handler_delivery)
