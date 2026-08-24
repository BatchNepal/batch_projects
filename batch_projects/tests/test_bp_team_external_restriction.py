"""Regression coverage for the v1.1.7 BP Team external-user restriction.

Finding: a Website User (standard Guest role only, no BP Guest role) was
treated as a non-guest by bp_team_query_conditions/bp_team_has_permission and
could enumerate every BP Team via the list API. The intended policy is that
restricted external users — the unauthenticated Guest, BP Guest role holders,
and Website Users — may only see teams they are a BP Team Member of.

Run with:
    bench run-tests --module batch_projects.tests.test_bp_team_external_restriction
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from batch_projects import permissions as perm


def _make_user(email, user_type="Website User", roles=None):
    """Throwaway user fixture. Frappe's User controller ignores user_type on
    insert (the row lands as Website User); set it directly when a System
    User is wanted. Roles are added after insert, then the roles cache is
    cleared so get_roles() sees them."""
    if frappe.db.exists("User", email):
        frappe.delete_doc("User", email, ignore_permissions=True, force=True)
    doc = frappe.get_doc(
        {
            "doctype": "User",
            "email": email,
            "first_name": email.split("@")[0],
            "enabled": 1,
            "send_welcome_email": 0,
        }
    )
    doc.insert(ignore_permissions=True)
    if user_type:
        frappe.db.set_value("User", email, "user_type", user_type)
    for role in roles or []:
        frappe.get_doc(
            {
                "doctype": "Has Role",
                "parent": email,
                "parenttype": "User",
                "parentfield": "roles",
                "role": role,
            }
        ).insert(ignore_permissions=True)
    frappe.clear_cache(user=email)
    frappe.db.commit()
    return email


def _delete_user(email):
    if frappe.db.exists("User", email):
        frappe.delete_doc("User", email, ignore_permissions=True, force=True)


def _make_team(team_name, members=None):
    if frappe.db.exists("BP Team", team_name):
        frappe.delete_doc("BP Team", team_name, ignore_permissions=True, force=True)
    doc = frappe.get_doc(
        {
            "doctype": "BP Team",
            "team_name": team_name,
        }
    )
    doc.insert(ignore_permissions=True)
    # BP Team.validate() requires members to be enabled System Users, so a
    # Website User can only ever hold membership through a direct row (e.g. a
    # user downgraded after being added, or a legacy row). Insert member rows
    # directly to model that state.
    for m in members or []:
        frappe.db.sql(
            "INSERT INTO `tabBP Team Member` "
            "(name, parent, parenttype, parentfield, idx, user, full_name, role) "
            "VALUES (%s, %s, 'BP Team', 'members', %s, %s, %s, %s)",
            (
                frappe.generate_hash(length=10),
                doc.name,
                (m.get("idx") or 1),
                m["user"],
                m["user"],
                m["role"],
            ),
        )
    frappe.db.commit()
    return doc.name


class TestBpTeamExternalRestriction(FrappeTestCase):
    TEAM_A = "V117 Team Alpha"
    TEAM_B = "V117 Team Beta"
    WS_MEMBER = "test70+info@batchnepal.com"
    WS_NONMEMBER = "test71+info@batchnepal.com"
    BP_GUEST = "test68+info@batchnepal.com"
    SYS_USER = "test69+info@batchnepal.com"

    def setUp(self):
        frappe.set_user("Administrator")
        self.team_a = _make_team(self.TEAM_A, members=[{"user": self.WS_MEMBER, "role": "Member"}])
        self.team_b = _make_team(self.TEAM_B)  # no members
        _make_user(self.WS_MEMBER, user_type="Website User")
        _make_user(self.WS_NONMEMBER, user_type="Website User")
        # BP Guest role has desk_access=1, so in practice the user lands as a
        # System User — the restriction must still apply via the role check.
        _make_user(self.BP_GUEST, user_type="System User", roles=["BP Guest"])
        _make_user(self.SYS_USER, user_type="System User")
        frappe.db.commit()

    def tearDown(self):
        frappe.set_user("Administrator")
        for team in (self.team_a, self.team_b):
            if frappe.db.exists("BP Team", team):
                frappe.delete_doc("BP Team", team, ignore_permissions=True, force=True)
        for u in (self.WS_MEMBER, self.WS_NONMEMBER, self.BP_GUEST, self.SYS_USER):
            _delete_user(u)
        frappe.db.commit()

    def _team_doc(self, name):
        return frappe.get_doc("BP Team", name)

    def test_non_member_website_user_cannot_list_or_read_any_team(self):
        frappe.set_user(self.WS_NONMEMBER)
        teams = frappe.get_list("BP Team", pluck="name")
        self.assertEqual(teams, [])
        self.assertFalse(perm.bp_team_has_permission(
            self._team_doc(self.team_a), self.WS_NONMEMBER, "read"))
        self.assertFalse(perm.bp_team_has_permission(
            self._team_doc(self.team_b), self.WS_NONMEMBER, "read"))

    def test_website_user_member_sees_only_their_team(self):
        frappe.set_user(self.WS_MEMBER)
        teams = frappe.get_list("BP Team", pluck="name")
        self.assertEqual(teams, [self.team_a])
        self.assertTrue(perm.bp_team_has_permission(
            self._team_doc(self.team_a), self.WS_MEMBER, "read"))
        self.assertFalse(perm.bp_team_has_permission(
            self._team_doc(self.team_b), self.WS_MEMBER, "read"))

    def test_bp_guest_follows_same_restriction(self):
        frappe.set_user(self.BP_GUEST)
        teams = frappe.get_list("BP Team", pluck="name")
        self.assertEqual(teams, [])
        self.assertFalse(perm.bp_team_has_permission(
            self._team_doc(self.team_a), self.BP_GUEST, "read"))

    def test_unauthenticated_guest_is_restricted(self):
        self.assertIn("BP Team Member", perm.bp_team_query_conditions("Guest"))
        self.assertFalse(perm.bp_team_has_permission(
            self._team_doc(self.team_a), "Guest", "read"))

    def test_system_user_retains_existing_access(self):
        frappe.set_user(self.SYS_USER)
        teams = frappe.get_list("BP Team", pluck="name")
        self.assertIn(self.team_a, teams)
        self.assertIn(self.team_b, teams)
        self.assertTrue(perm.bp_team_has_permission(
            self._team_doc(self.team_a), self.SYS_USER, "read"))

    def test_administrator_retains_unrestricted_access(self):
        frappe.set_user("Administrator")
        teams = frappe.get_list("BP Team", pluck="name")
        self.assertIn(self.team_a, teams)
        self.assertIn(self.team_b, teams)
        self.assertTrue(perm.bp_team_has_permission(
            self._team_doc(self.team_a), "Administrator", "read"))

    def test_query_conditions_and_doc_permission_agree(self):
        # Non-member Website User: query conditions restrict to member teams
        # (none), and doc-level read is denied.
        qc = perm.bp_team_query_conditions(self.WS_NONMEMBER)
        self.assertIn("BP Team Member", qc)
        self.assertFalse(perm.bp_team_has_permission(
            self._team_doc(self.team_a), self.WS_NONMEMBER, "read"))
        # Member Website User: query conditions restrict to member teams, and
        # doc-level read is allowed for their team only.
        qc = perm.bp_team_query_conditions(self.WS_MEMBER)
        self.assertIn("BP Team Member", qc)
        self.assertTrue(perm.bp_team_has_permission(
            self._team_doc(self.team_a), self.WS_MEMBER, "read"))
        self.assertFalse(perm.bp_team_has_permission(
            self._team_doc(self.team_b), self.WS_MEMBER, "read"))
        # BP Guest: query conditions restrict, doc-level read denied.
        qc = perm.bp_team_query_conditions(self.BP_GUEST)
        self.assertIn("BP Team Member", qc)
        self.assertFalse(perm.bp_team_has_permission(
            self._team_doc(self.team_a), self.BP_GUEST, "read"))
        # System User: query conditions are open, doc-level read allowed.
        self.assertEqual(perm.bp_team_query_conditions(self.SYS_USER), "")
        self.assertTrue(perm.bp_team_has_permission(
            self._team_doc(self.team_a), self.SYS_USER, "read"))
        # Administrator: query conditions are open, doc-level read allowed.
        self.assertEqual(perm.bp_team_query_conditions("Administrator"), "")
        self.assertTrue(perm.bp_team_has_permission(
            self._team_doc(self.team_a), "Administrator", "read"))