"""
batch_projects/api/invitations.py
─────────────────────────────────
Project invitations: invite by email, pending until accepted,
role chosen at invite time, revocable, with a clear accept flow.

Authorization is the unified model (batch_projects.access):
  • invite / revoke / resend / list  → project Admin (or instance admin)
  • accept                           → the invited person themselves
"""

import frappe
from frappe import _
from frappe.utils import now_datetime, add_days, get_url, validate_email_address

from batch_projects import access

INVITE_TTL_DAYS = 14
VALID_ROLES = {"Admin", "Manager", "Member", "Viewer"}


# ─── helpers ──────────────────────────────────────────────────────────────────

def _normalize_email(email: str) -> str:
    email = (email or "").strip().lower()
    if not email or not validate_email_address(email):
        frappe.throw(_("Please provide a valid email address."))
    return email


def _accept_url(token: str) -> str:
    return get_url(f"/workspace/invite/{token}")


def _is_member(project: str, user: str) -> bool:
    return bool(frappe.db.exists(
        "BP Project Member", {"parent": project, "user": user}))


def _add_membership(project: str, user: str, role: str):
    """Insert (or upgrade) a BP Project Member row. Mirrors the direct-SQL
    pattern used by board.update_project_members so child-table perms never bite."""
    existing = frappe.db.get_value(
        "BP Project Member", {"parent": project, "user": user}, ["name", "role"], as_dict=True)
    from batch_projects.events import emit, PROJECT_ROLE_CHANGED
    access.ensure_member_role(user)

    if existing:
        if existing.role != role:
            frappe.db.set_value("BP Project Member", existing.name, "role", role)
            emit(PROJECT_ROLE_CHANGED, {
                "project": project, "user": user,
                "old_role": existing.role, "new_role": role,
            })
        return
    idx = (frappe.db.sql(
        "SELECT COALESCE(MAX(idx),0)+1 FROM `tabBP Project Member` WHERE parent=%s",
        project)[0][0]) or 1
    frappe.db.sql(
        """INSERT INTO `tabBP Project Member`
           (name, parent, parenttype, parentfield, idx, user, role,
            full_name, owner, creation, modified, modified_by)
           VALUES (%s, %s, 'BP Project', 'members', %s, %s, %s, %s, %s,
                   NOW(), NOW(), %s)""",
        (
            frappe.generate_hash(length=10), project, idx, user, role,
            frappe.db.get_value("User", user, "full_name") or user,
            frappe.session.user, frappe.session.user,
        ),
    )
    frappe.db.sql(
        "UPDATE `tabBP Project` SET modified=NOW(), modified_by=%s WHERE name=%s",
        (frappe.session.user, project))

    emit(PROJECT_ROLE_CHANGED, {
        "project": project, "user": user,
        "old_role": None, "new_role": role,
    })


def _send_invite_email(inv, project_title: str, new_account: bool):
    link = _accept_url(inv.token)
    inviter = frappe.db.get_value("User", inv.invited_by, "full_name") or inv.invited_by
    intro = (
        _("You have been invited to collaborate on the project "
          "<b>{0}</b> as <b>{1}</b>.").format(project_title, inv.role))
    extra = ""
    if new_account:
        extra = _(
            "<p>An account has been created for you. Click the button below to "
            "set your password and join the project.</p>")
    frappe.sendmail(
        recipients=[inv.email],
        subject=_("{0} invited you to {1}").format(inviter, project_title),
        message=f"""
            <p>{intro}</p>
            {extra}
            <p style="margin:24px 0;">
              <a href="{link}"
                 style="background:#0052CC;color:#fff;padding:10px 18px;
                        border-radius:6px;text-decoration:none;">
                {_('Accept invitation')}
              </a>
            </p>
            <p style="color:#6B778C;font-size:12px;">
              {_('This invitation expires on {0}.').format(inv.expires_on)}
            </p>
        """,
        now=True,
    )


# ─── endpoints ────────────────────────────────────────────────────────────────

@frappe.whitelist()
def invite_member(project, email, role="Member"):
    """Invite someone (by email) to a project. Admin only.
    Creates a System User account if the email isn't registered yet."""
    from batch_projects.gateway_guard import verify_gateway_request
    verify_gateway_request()
    access.require(project, "Admin")

    email = _normalize_email(email)
    role = role if role in VALID_ROLES else "Member"
    project_title = frappe.db.get_value("BP Project", project, "project_name") or project

    user = frappe.db.get_value("User", {"email": email}, "name") or \
        (email if frappe.db.exists("User", email) else None)

    if user and _is_member(project, user):
        frappe.throw(_("{0} is already a member of this project.").format(email))

    # Reuse an existing pending invite for the same email+project
    existing = frappe.db.get_value(
        "BP Invitation",
        {"project": project, "email": email, "status": "Pending"},
        "name")
    inv = frappe.get_doc("BP Invitation", existing) if existing \
        else frappe.new_doc("BP Invitation")

    new_account = False
    if not user:
        user = _create_invited_user(email)
        new_account = True

    inv.update({
        "email": email,
        "project": project,
        "role": role,
        "status": "Pending",
        "invited_by": frappe.session.user,
        "expires_on": add_days(now_datetime(), INVITE_TTL_DAYS),
    })
    inv.save(ignore_permissions=True)
    frappe.db.commit()

    try:
        _send_invite_email(inv, project_title, new_account)
        email_sent = True
    except Exception:
        frappe.log_error(frappe.get_traceback(), "BP invite email failed")
        email_sent = False

    return {
        "name": inv.name, "email": inv.email, "role": inv.role,
        "status": inv.status, "expires_on": str(inv.expires_on),
        "email_sent": email_sent, "accept_url": _accept_url(inv.token),
    }


def _create_invited_user(email: str) -> str:
    """Create a minimal enabled System User for a brand-new invitee, tagged as a
    guest. They have no password yet — they set one inline on the accept page
    (signup_and_accept). Guests only ever see projects they're invited to."""
    _ensure_guest_role()
    first = email.split("@")[0].replace(".", " ").title()
    u = frappe.get_doc({
        "doctype": "User",
        "email": email,
        "first_name": first,
        "user_type": "System User",
        "enabled": 1,
        "send_welcome_email": 0,
    })
    u.insert(ignore_permissions=True)
    u.add_roles(access.GUEST_ROLE)
    return u.name


def _ensure_guest_role():
    # desk_access=1 is required: a System User whose only role has desk_access=0
    # is auto-demoted by Frappe to "Website User", which this app blocks — so the
    # guest would be locked out of the very project they were invited to.
    if not frappe.db.exists("Role", access.GUEST_ROLE):
        frappe.get_doc({
            "doctype": "Role", "role_name": access.GUEST_ROLE,
            "desk_access": 1,
        }).insert(ignore_permissions=True)
    elif not frappe.db.get_value("Role", access.GUEST_ROLE, "desk_access"):
        frappe.db.set_value("Role", access.GUEST_ROLE, "desk_access", 1)


def _is_fresh_guest(user: str) -> bool:
    """A guest account we created that has never been used (no password set /
    never logged in) — eligible for inline signup on the accept page."""
    if not user or not frappe.db.exists("User", user):
        return False
    if access.GUEST_ROLE not in frappe.get_roles(user):
        return False
    return not frappe.db.get_value("User", user, "last_login")


@frappe.whitelist()
def list_invitations(project, include_resolved=0):
    """Pending (and optionally resolved) invitations for a project. Manager+."""
    from batch_projects.gateway_guard import verify_gateway_request
    verify_gateway_request()
    access.require(project, "Manager")
    filters = {"project": project}
    if not int(include_resolved or 0):
        filters["status"] = "Pending"
    rows = frappe.get_all(
        "BP Invitation",
        filters=filters,
        fields=["name", "email", "role", "status", "invited_by",
                "expires_on", "creation", "accepted_user", "accepted_on"],
        order_by="creation desc",
    )
    now = now_datetime()
    for r in rows:
        if r["status"] == "Pending" and r["expires_on"] and r["expires_on"] < now:
            r["status"] = "Expired"
    return rows


@frappe.whitelist()
def revoke_invitation(name):
    from batch_projects.gateway_guard import verify_gateway_request
    verify_gateway_request()
    inv = frappe.get_doc("BP Invitation", name)
    access.require(inv.project, "Admin")
    if inv.status != "Pending":
        frappe.throw(_("Only pending invitations can be revoked."))
    inv.status = "Revoked"
    inv.save(ignore_permissions=True)
    frappe.db.commit()
    return {"ok": True}


@frappe.whitelist()
def resend_invitation(name):
    from batch_projects.gateway_guard import verify_gateway_request
    verify_gateway_request()
    inv = frappe.get_doc("BP Invitation", name)
    access.require(inv.project, "Admin")
    if inv.status != "Pending":
        frappe.throw(_("Only pending invitations can be resent."))
    inv.expires_on = add_days(now_datetime(), INVITE_TTL_DAYS)
    inv.save(ignore_permissions=True)
    frappe.db.commit()
    project_title = frappe.db.get_value(
        "BP Project", inv.project, "project_name") or inv.project
    new_account = not frappe.db.get_value("User", inv.email, "last_login")
    _send_invite_email(inv, project_title, new_account)
    return {"ok": True}


@frappe.whitelist(allow_guest=True)
def get_invitation(token):
    """Preview an invitation for the accept page. Callable before login (the
    token is the secret). Returns a `needs` hint telling the UI what to render:
        accept   — logged in as the right user, just confirm
        login    — existing account, must sign in first
        signup   — fresh guest account, set a password inline to join
        mismatch — logged in as someone else
    """
    inv = frappe.db.get_value(
        "BP Invitation", {"token": token},
        ["name", "email", "project", "role", "status", "expires_on"],
        as_dict=True)
    if not inv:
        frappe.throw(_("This invitation link is invalid."), frappe.DoesNotExistError)

    project_title = frappe.db.get_value(
        "BP Project", inv.project, "project_name") or inv.project
    state = inv.status
    if state == "Pending" and inv.expires_on and inv.expires_on < now_datetime():
        state = "Expired"

    session_user = frappe.session.user if frappe.session.user != "Guest" else None
    needs = _accept_state(inv.email, session_user)

    return {
        "email": inv.email, "project": inv.project,
        "project_title": project_title, "role": inv.role, "status": state,
        "logged_in_as": session_user, "needs": needs,
    }


def _accept_state(invite_email: str, session_user: str | None) -> str:
    if session_user:
        cur = (frappe.db.get_value("User", session_user, "email") or session_user).lower()
        return "accept" if cur == invite_email.lower() else "mismatch"
    target = frappe.db.get_value("User", {"email": invite_email}, "name") or \
        (invite_email if frappe.db.exists("User", invite_email) else None)
    if target and _is_fresh_guest(target):
        return "signup"
    return "login"


def _finalize_accept(inv, user):
    """Add membership + mark the invitation accepted. Caller has authenticated
    `user` and verified the email matches."""
    from batch_projects.entitlements import assert_seat_available
    assert_seat_available(user)
    _add_membership(inv.project, user, inv.role)
    inv.status = "Accepted"
    inv.accepted_user = user
    inv.accepted_on = now_datetime()
    inv.save(ignore_permissions=True)
    frappe.db.commit()
    from batch_projects.cache import invalidate_project
    invalidate_project(inv.project)
    return {
        "ok": True, "project": inv.project, "role": inv.role,
        "project_key": frappe.db.get_value("BP Project", inv.project, "key"),
    }


def _load_pending(token):
    name = frappe.db.get_value("BP Invitation", {"token": token}, "name")
    if not name:
        frappe.throw(_("This invitation link is invalid."), frappe.DoesNotExistError)
    inv = frappe.get_doc("BP Invitation", name)
    if inv.status == "Accepted":
        return inv, True
    if inv.status != "Pending":
        frappe.throw(_("This invitation is no longer valid ({0}).").format(inv.status))
    if inv.is_expired:
        inv.status = "Expired"
        inv.save(ignore_permissions=True)
        frappe.db.commit()
        frappe.throw(_("This invitation has expired."))
    return inv, False


@frappe.whitelist(allow_guest=True)
def signup_and_accept(token, password, full_name=None):
    """Set a password on a fresh guest account, log them in, and accept — the
    one-step join used by brand-new invitees. Only works for guest accounts we
    created that have never been used; existing accounts must use real login."""
    inv, already = _load_pending(token)
    if already:
        frappe.throw(_("This invitation was already accepted. Please log in."))

    target = frappe.db.get_value("User", {"email": inv.email}, "name") or \
        (inv.email if frappe.db.exists("User", inv.email) else None)
    if not target or not _is_fresh_guest(target):
        frappe.throw(
            _("This account already exists. Please log in to accept."),
            frappe.PermissionError)

    from frappe.utils.password import update_password
    if full_name and str(full_name).strip():
        frappe.db.set_value("User", target, "first_name", str(full_name).strip())
    update_password(target, password)
    frappe.db.commit()

    # Establish a session for the freshly-activated guest, then accept.
    frappe.local.login_manager.login_as(target)
    return _finalize_accept(inv, target)


@frappe.whitelist()
def accept_invitation(token):
    """Accept as the currently logged-in user (email must match the invite)."""
    from batch_projects.gateway_guard import verify_gateway_request
    verify_gateway_request()
    if frappe.session.user == "Guest":
        frappe.throw(_("Please log in to accept this invitation."),
                     frappe.PermissionError)

    inv, already = _load_pending(token)
    if already:
        return {"ok": True, "project": inv.project, "already": True,
                "project_key": frappe.db.get_value("BP Project", inv.project, "key")}

    user_email = (frappe.db.get_value("User", frappe.session.user, "email")
                  or frappe.session.user).lower()
    if user_email != inv.email.lower():
        frappe.throw(
            _("This invitation was sent to {0}. Please log in as that user.")
            .format(inv.email), frappe.PermissionError)

    return _finalize_accept(inv, frappe.session.user)
