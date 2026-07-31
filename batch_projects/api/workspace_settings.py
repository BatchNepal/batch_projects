"""
batch_projects/api/workspace_settings.py
─────────────────────────────────────────
Org-wide settings, as opposed to the per-project settings board.py already
serves. One record for the whole site (BP Workspace Settings is a Single):
timesheet approval config (the approval engine wires the gate itself; this
tab stores config ahead of it) and the feature on/off switches every project's
Gantt/Money/Timesheets/Reports tabs check. Gated to workspace admins
(access.is_workspace_admin) — a project Admin has no say over a workspace-wide
record.
"""

import frappe
import json

from batch_projects import access
from batch_projects.entitlements import get_workspace_features, require_feature


def _guard():
    from batch_projects.gateway_guard import verify_gateway_request
    verify_gateway_request()


def _require_system_user():
    user = frappe.session.user
    if "System Manager" in frappe.get_roles(user):
        return
    if frappe.db.get_value("User", user, "user_type") != "System User":
        frappe.throw("Access denied.", frappe.PermissionError)


def _parse_json(value, default):
    if not value:
        return default
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


@frappe.whitelist()
def get_workspace_settings():
    """Every logged-in member gets the effective feature flags (what the SPA
    needs to hide gated tabs/routes). Workspace admins additionally get the
    full record, for the settings hub."""
    _guard()
    _require_system_user()

    features = get_workspace_features()
    if not access.is_workspace_admin():
        return {"is_admin": False, "features": features}

    doc = frappe.get_single("BP Workspace Settings")
    return {
        "is_admin": True,
        "features": features,
        "brand_name": doc.brand_name or "",
        "logo_url": doc.logo_url or "",
        "favicon_url": doc.favicon_url or "",
        "approval_mode": doc.approval_mode or "Self-Submit",
        "approvers": [{"user": a.user} for a in (doc.approvers or [])],
        "notify_approvers_on_submission": bool(doc.notify_approvers_on_submission),
        "notify_submitter_on_decision": bool(doc.notify_submitter_on_decision),
        # Roles & Permissions matrix. capability_registry ships
        # the metadata (label/group/overridable/min_role) so the matrix UI
        # doesn't hardcode a second copy of access.CAPABILITIES; role_
        # overrides is the raw, as-stored value (what the matrix's checkboxes
        # should start from — capability_matrix is the RESOLVED grid, which
        # already has Admin forced on and can't tell an override apart from
        # a default).
        "capability_registry": [
            {"key": k, **v} for k, v in access.CAPABILITIES.items()
        ],
        "capability_groups": access.CAPABILITY_GROUPS,
        "capability_matrix": access.get_capability_matrix(),
        "role_overrides": access.get_role_overrides_raw(),
    }


@frappe.whitelist()
def update_workspace_settings(approval_mode=None, approvers=None,
                               notify_approvers_on_submission=None,
                               notify_submitter_on_decision=None,
                               features_json=None, role_overrides_json=None,
                               brand_name=None, logo_url=None, favicon_url=None):
    """Admin-only write."""
    _guard()
    _require_system_user()
    if not access.is_workspace_admin():
        frappe.throw(
            "You need workspace admin access for this.", frappe.PermissionError
        )

    doc = frappe.get_single("BP Workspace Settings")

    if brand_name is not None or logo_url is not None or favicon_url is not None:
        require_feature("custom_branding")
        if brand_name is not None:
            doc.brand_name = brand_name
        if logo_url is not None:
            doc.logo_url = logo_url
        if favicon_url is not None:
            doc.favicon_url = favicon_url

    if approval_mode is not None:
        if approval_mode not in ("Auto-Approve", "Self-Submit", "Manager Approval"):
            frappe.throw("Invalid approval mode.")
        doc.approval_mode = approval_mode

    if approvers is not None:
        doc.set("approvers", [])
        for a in _parse_json(approvers, []):
            user = a.get("user") if isinstance(a, dict) else a
            if user:
                doc.append("approvers", {"user": user})

    if notify_approvers_on_submission is not None:
        doc.notify_approvers_on_submission = 1 if notify_approvers_on_submission else 0
    if notify_submitter_on_decision is not None:
        doc.notify_submitter_on_decision = 1 if notify_submitter_on_decision else 0

    if features_json is not None:
        parsed = _parse_json(features_json, {})
        # Keys are whitelisted against the known feature set; a key the
        # payload doesn't mention keeps its CURRENT value — a partial update
        # must never silently flip other features back on.
        current = get_workspace_features()
        clean = {k: (1 if parsed.get(k, current[k]) else 0) for k in current}
        doc.features_json = json.dumps(clean)

    if role_overrides_json is not None:
        parsed = _parse_json(role_overrides_json, {})
        # access.validate_and_merge_role_overrides IS the partial-update
        # guard here (same contract as features_json above, plus rejecting
        # Admin/unknown-role/non-overridable-capability keys) — it starts
        # from the CURRENT stored value and only touches what's mentioned.
        merged = access.validate_and_merge_role_overrides(
            parsed, access.get_role_overrides_raw()
        )
        doc.role_overrides_json = json.dumps(merged)

    doc.flags.ignore_permissions = True
    doc.save()
    frappe.db.commit()

    # The matrix is cached (access.get_capability_matrix) — a role override
    # save must be visible on the very next request, not after a restart.
    if role_overrides_json is not None:
        access.invalidate_capability_matrix_cache()

    return get_workspace_settings()
