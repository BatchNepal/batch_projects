"""
batch_projects/entitlements.py
──────────────────────────────
Feature gating = how batch_projects is monetized.

The licensed Go gateway is the single ingress to this site. It validates the
license JWT and injects trusted headers on every proxied request:

    X-BP-Tier       starter | team | business | enterprise   (the plan)
    X-BP-Packs      comma-separated vertical packs (ps, construction, software, ai)
    X-BP-Max-Users  integer
    X-BP-Tenant     tenant id

Because the compose exposes ONLY the gateway (never Frappe directly), these
headers are trusted. When there is no header (no license, or direct dev
access) we default to the FREE tier — `starter`. That is the scarcity: the
app installs and runs free, premium features are locked until a license
raises the tier.

Resolution order for the current tier:
    1. X-BP-Tier request header — ONLY if gateway_guard verified this
       request's HMAC signature (frappe.local._bp_gateway_verified). An
       unsigned or unverifiable header is never trusted, same fail-closed
       rule current_max_users() already applies to X-BP-Max-Users.
    2. site_config "bp_dev_tier" — dev/testing override, but ONLY on sites
       that have NOT configured bp_gateway_shared_secret. A site with the
       secret set has declared itself gateway-enforced; honoring bp_dev_tier
       there would let a request that skips the gateway entirely (e.g. a
       direct curl to Frappe's own port) self-assert any paid tier for free.
       Both resolution steps are fail-closed for exactly this reason.
    3. last value cached from a prior request (for background jobs/scheduler)
    4. "starter"                       (free)
"""

import frappe


# Plan ranking — higher unlocks everything below it.
# Growth/Pro/Team share one feature tier (rank 1); Business (rank 2) and
# Enterprise (rank 3) are the only tiers with additional feature gates.
# The actual differentiator between Team/Growth/Pro is max_users, not features.
_TIER_RANK = {
    "starter":    0,
    "team":       1,
    "business":   2,
    "enterprise": 3,
    "growth":     1,
    "pro":        1,
    "dev":        99,  # local dev only — unlocks all
}

_TIER_LABEL = {
    "starter":    "Community",
    "growth":     "Growth",
    "pro":        "Pro",
    "team":       "Team",
    "business":   "Business",
    "enterprise": "Enterprise",
    "dev":        "Developer",
}

# Feature catalog: feature → minimum tier that unlocks it.
# This is the monetization map. Keep it as the single source of truth.
# Mirrors bp-gateway internal/license featureMinTier — the bridge is the
# authoritative enforcer; this copy gates in-app UI + server fallbacks.
_FEATURE_MIN_TIER = {
    # Team
    "automations": "team",
    "webhooks": "team",
    "templates": "team",
    "scheduler": "team",
    "integrations": "team",
    "intake_forms": "team",
    "time_tracking": "team",
    "realtime": "team",
    "share_links": "team",
    "draw": "team",
    # Deliberately NOT reusing "automations" (the Go-binary,
    # document-mutating tier). Notification rules are routing only; keeping
    # a separate flag preserves the open-core boundary — collapsing it
    # would blur the line between "routes a notification" and
    # "mutates a document".
    "notification_rules": "team",
    # Gates CREATE/EDIT of workspace-scoped or shared (visibility
    # =workspace) dashboards only. A private, project-scoped report is the
    # pre-existing free "Reports" feature and stays ungated — see
    # _require_dashboards_entitlement_if_shared in api/board.py.
    "dashboards": "team",
    "exports": "team",
    "custom_branding": "team",
    "goals": "business",
    # Business
    "profitability": "business",
    "portfolio": "business",
    "billing_writeback": "business",
    "api": "business",
    # Enterprise
    "sso": "enterprise",
    "audit_log": "enterprise",
}

_TIER_CACHE_KEY = "bp_current_tier"

# Workspace-admin-configurable on/off switches (BP Workspace Settings.features_json).
# Independent of the tier map above — a workspace admin can turn a free, core
# surface off for their org regardless of plan. Absent key = enabled (opt-out,
# not opt-in), so a stale record from before a new toggle shipped still passes.
_WORKSPACE_FEATURE_DEFAULTS = {
    "notes": True,
    "draw": True,
    "gantt": True,
    "money_tab": True,
    "timesheets": True,
    "reports": True,
}


class BPUpgradeRequired(frappe.ValidationError):
    """Raised when a gated feature is used below its required tier.
    Frontend detects this via exc_type and shows the upgrade CTA."""
    pass


class BPFeatureDisabled(frappe.ValidationError):
    """Raised when a workspace admin has switched a feature off. Distinct from
    BPUpgradeRequired (that's a plan limit; this is an admin's own choice) so
    the frontend can show "ask your admin" instead of an upgrade CTA."""
    pass


# ─── TIER RESOLUTION ─────────────────────────────────────────────────────────

def current_tier() -> str:
    tier = _tier_from_request()
    if tier:
        # write-through so background jobs (scheduler, hooks) see the latest
        try:
            frappe.cache().set_value(_TIER_CACHE_KEY, tier)
        except Exception:
            pass
        return tier

    # Inert on any site that has declared itself gateway-enforced (secret
    # configured) — see the module docstring.
    if not frappe.conf.get("bp_gateway_shared_secret"):
        override = frappe.conf.get("bp_dev_tier")
        if override:
            return override

    cached = None
    try:
        cached = frappe.cache().get_value(_TIER_CACHE_KEY)
    except Exception:
        pass
    return cached or "starter"


def _tier_from_request() -> str | None:
    """Fail-closed, mirrors current_max_users(): only trust X-BP-Tier if the
    gateway's HMAC signature was verified for this request (gateway_guard.
    apply_gateway_identity sets the flag). Otherwise a direct-to-Frappe call
    could self-assert any tier via a plain header."""
    try:
        if frappe.request and frappe.request.headers:
            tier = frappe.request.headers.get("X-BP-Tier")
            if tier and getattr(frappe.local, "_bp_gateway_verified", False):
                return tier.strip().lower()
    except Exception:
        pass
    return None


def current_packs() -> list[str]:
    try:
        if frappe.request and frappe.request.headers:
            raw = frappe.request.headers.get("X-BP-Packs") or ""
            return [p.strip() for p in raw.split(",") if p.strip()]
    except Exception:
        pass
    return []


# ─── FEATURE CHECKS ──────────────────────────────────────────────────────────

def is_feature_enabled(feature: str) -> bool:
    min_tier = _FEATURE_MIN_TIER.get(feature)
    if min_tier is None:
        return True  # uncatalogued features are free by default
    return _TIER_RANK.get(current_tier(), 0) >= _TIER_RANK.get(min_tier, 0)


def require_feature(feature: str):
    """Raise BPUpgradeRequired if the current tier can't use `feature`."""
    if not is_feature_enabled(feature):
        min_tier = _FEATURE_MIN_TIER.get(feature, "team")
        frappe.throw(
            f"This feature requires the {_TIER_LABEL.get(min_tier, min_tier.title())} "
            f"plan or higher. Upgrade to unlock it.",
            exc=BPUpgradeRequired,
            title="Upgrade Required",
        )


# ─── WORKSPACE FEATURE TOGGLES (admin-configured, tier-independent) ───────────

def get_workspace_features() -> dict:
    """The effective on/off state of every workspace-toggleable feature,
    defaults applied for anything the settings record doesn't mention yet."""
    import json
    flags = dict(_WORKSPACE_FEATURE_DEFAULTS)
    try:
        raw = frappe.db.get_single_value("BP Workspace Settings", "features_json")
        overrides = json.loads(raw) if raw else {}
        for k, v in overrides.items():
            if k in flags:
                flags[k] = bool(v)
    except Exception:
        # Doctype not migrated yet, or a malformed record — fail open to the
        # defaults rather than breaking bootstrap for the whole SPA.
        pass
    return flags


def is_workspace_feature_enabled(feature: str) -> bool:
    return get_workspace_features().get(feature, True)


def require_workspace_feature(feature: str):
    """Raise BPFeatureDisabled if a workspace admin has switched `feature` off.
    Independent of require_feature (tier) — call both where both apply."""
    if not is_workspace_feature_enabled(feature):
        frappe.throw(
            f"The {feature.replace('_', ' ').title()} feature has been turned "
            f"off for this workspace. Ask a workspace admin to re-enable it in "
            f"Workspace Settings.",
            exc=BPFeatureDisabled,
            title="Feature disabled",
        )


# ─── SEATS ───────────────────────────────────────────────────────────────────

# Fallback seat caps used ONLY when all other sources are unavailable:
#   - No HTTP request (background job)
#   - No bp_dev_max_users site config override
#   - Nothing cached from a prior request
#   - No gateway-signed X-BP-Max-Users header
#
# This is NOT the live tier ladder. The live cap comes from the license JWT's
# MaxUsers claim, injected by the gateway as X-BP-Max-Users with an HMAC
# signature that gateway_guard.py verifies. These fallbacks exist only so the
# app doesn't crash when the gateway is unreachable.
#
# 0 means unlimited.
_UNLICENSED_FALLBACK_MAX_USERS = {
    "starter": 5,      # Community (matches PLAN_USER_MAP/plans.py)
    "growth": 10,      # $29/mo
    "pro": 20,         # $59/mo
    "business": 50,    # $149/mo
    "team": 25,        # legacy tier
    "enterprise": 0,   # unlimited
    "dev": 0,          # unlimited
}
_MAX_USERS_CACHE_KEY = "bp_current_max_users"


def current_max_users() -> int:
    """Licensed seat cap (0 = unlimited). Header is live truth; cached for
    background jobs; falls back to the fallback table.

    Fail-closed: if the request carries an X-BP-Max-Users header but the
    gateway signature was NOT verified (gateway_guard.py sets the flag),
    the header is ignored — prevents spoofed headers on direct curls."""
    try:
        if frappe.request and frappe.request.headers:
            mu = frappe.request.headers.get("X-BP-Max-Users")
            if mu:
                # Fail-closed: only trust the header if the gateway signature
                # was verified for this request. Otherwise ignore it.
                if getattr(frappe.local, "_bp_gateway_verified", False):
                    val = int(mu)
                    try:
                        frappe.cache().set_value(_MAX_USERS_CACHE_KEY, val)
                    except Exception:
                        pass
                    return val
    except Exception:
        pass
    # Same fail-closed rule current_tier() applies to bp_dev_tier:
    # bp_dev_max_users must be inert on any site that
    # has declared itself gateway-enforced (bp_gateway_shared_secret set).
    # Without this guard, a request that arrives with no verified header at
    # all — a background job, or a direct-to-Frappe call that skips the
    # gateway entirely — would let a stale/misconfigured bp_dev_max_users
    # silently override the real cap on a site that's supposed to be
    # fully gateway-enforced.
    if not frappe.conf.get("bp_gateway_shared_secret"):
        override = frappe.conf.get("bp_dev_max_users")
        if override is not None:
            return int(override)
    try:
        cached = frappe.cache().get_value(_MAX_USERS_CACHE_KEY)
        if cached is not None:
            return int(cached)
    except Exception:
        pass
    return _UNLICENSED_FALLBACK_MAX_USERS.get(current_tier(), 3)


def _seated_users() -> set:
    seated = set(frappe.get_all("BP Project Member", pluck="user", distinct=True))
    seated |= set(frappe.get_all("BP Team Member", pluck="user", distinct=True))
    seated.discard(None)
    return seated


def count_active_seats() -> int:
    """A seat = a distinct enabled System User holding at least one project
    OR team membership. Guests count (they occupy collaboration capacity)."""
    seated = _seated_users()
    if not seated:
        return 0
    return len(frappe.get_all(
        "User",
        filters={"name": ["in", list(seated)], "enabled": 1,
                 "user_type": "System User"},
        pluck="name",
    ))


def is_seated(user: str) -> bool:
    return bool(
        frappe.db.exists("BP Project Member", {"user": user})
        or frappe.db.exists("BP Team Member", {"user": user})
    )


def assert_seat_available(new_user: str):
    """Raise BPUpgradeRequired when adding `new_user` would exceed the cap.
    A user who already holds any membership occupies a seat — re-adding them
    to another project is always allowed."""
    cap = current_max_users()
    if not cap:
        return
    if is_seated(new_user):
        return
    if count_active_seats() >= cap:
        frappe.throw(
            f"Your plan includes {cap} seats and all are in use. "
            f"Upgrade your plan to add more people.",
            exc=BPUpgradeRequired,
            title="Seat limit reached",
        )


def assert_seats_available(needed: int):
    """Bulk variant for call sites adding several users in one request — checking
    one-by-one against the same count would let N users through the last seat."""
    cap = current_max_users()
    if not cap or needed <= 0:
        return
    if count_active_seats() + needed > cap:
        frappe.throw(
            f"Your plan includes {cap} seats; adding {needed} more people would "
            f"exceed it. Upgrade your plan to add more seats.",
            exc=BPUpgradeRequired,
            title="Seat limit reached",
        )


# ─── DOC-EVENTS HOOKS (catches every insertion path, incl. generic REST API) ──

def before_member_insert(doc, method):
    """doc_events hook for BP Project Member and BP Team Member `before_insert`.
    Catches ALL insertion paths: ORM saves, batch operations, the generic REST
    API — without needing to hunt down every direct-SQL call site."""
    user = doc.get("user")
    if user:
        assert_seat_available(user)


# ─── SPA BOOTSTRAP ───────────────────────────────────────────────────────────

@frappe.whitelist()
def get_entitlements():
    """Drives the SPA: which tier the install is on and which features are unlocked."""
    from batch_projects.gateway_guard import verify_gateway_request
    verify_gateway_request()
    tier = current_tier()
    max_users = None
    try:
        if frappe.request and frappe.request.headers:
            mu = frappe.request.headers.get("X-BP-Max-Users")
            max_users = int(mu) if mu else None
    except Exception:
        pass

    from batch_projects import access

    # Read license expiry info from gateway-injected headers
    expires_at = None
    days_remaining = None
    try:
        if frappe.request and frappe.request.headers:
            exp_str = frappe.request.headers.get("X-BP-Expires-At")
            if exp_str:
                expires_at = exp_str
            days_str = frappe.request.headers.get("X-BP-Days-Remaining")
            if days_str:
                days_remaining = int(days_str)
    except Exception:
        pass

    return {
        "tier": tier,
        "tier_label": _TIER_LABEL.get(tier, tier.title()),
        "packs": current_packs(),
        "features": {f: is_feature_enabled(f) for f in _FEATURE_MIN_TIER},
        "feature_min_tier": dict(_FEATURE_MIN_TIER),
        # License expiry info (from gateway headers)
        "expires_at": expires_at,
        "days_remaining": days_remaining,
        # Admin on/off switches (BP Workspace Settings) — orthogonal to the
        # tier map above; a feature must clear BOTH to render/act.
        "workspace_features": get_workspace_features(),
        # Cheap boolean so the sidebar/router can show the Workspace Settings
        # entry without a second bootstrap round trip — the settings API
        # re-checks this server-side regardless, this is UI-visibility only.
        "is_workspace_admin": access.is_workspace_admin(),
        "limits": {"max_users": max_users},
        "seats_used": count_active_seats(),
        # The resolved {role: {capability: bool}} grid. Same role
        # for every project (it's a workspace-wide policy, not project data),
        # so it's piggybacked on this existing bootstrap rather than a new
        # endpoint — the frontend combines it with the per-project role it
        # already resolves per project switch (project store's
        # get_my_capabilities call) to decide "can I see money/files HERE".
        "capability_matrix": access.get_capability_matrix(),
        # Cross-project surfaces (the margin report has no single project to
        # resolve a role against) get a pre-resolved boolean instead — UI-
        # visibility only, the endpoint re-checks server-side regardless.
        "view_money_anywhere": access.has_capability_anywhere("view_money"),
        # White-label branding — applies to every member's shell (sidebar +
        # favicon), not just admins, so it rides this bootstrap rather than
        # the admin-only get_workspace_settings. Null fields = default
        # branding; only populated when the workspace is entitled, so a
        # downgrade silently reverts every session to stock branding without
        # needing to touch the stored record.
        "branding": get_branding(),
        # The SPA's own get_projects is deliberately access-filtered, so
        # "my project list is empty" can mean either "this workspace has
        # no projects at all"
        # (true first-run — show the create-workspace wizard) or "projects
        # exist but none are shared with me yet" (an invited teammate —
        # show a lightweight join/waiting state instead). This is the
        # workspace-wide, unfiltered fact the SPA can't derive from its own
        # already-scoped project list.
        "workspace_has_projects": bool(frappe.db.exists("BP Project", {})),
        # Per-user "I've already seen/skipped onboarding" — without this,
        # onboarding re-fired on every reload for anyone who skipped it
        # (the old trigger was purely "do I currently see zero projects").
        # frappe.defaults (core per-user key/value store) rather than a new
        # User custom field — no schema change needed for one boolean flag.
        "onboarding_dismissed": frappe.defaults.get_user_default("bp_onboarding_dismissed") == "1",
        "dismissed_nudges": _dismissed_nudges(),
    }


def get_branding():
    if not is_feature_enabled("custom_branding"):
        return {"brand_name": None, "logo_url": None, "favicon_url": None}
    doc = frappe.get_single("BP Workspace Settings")
    return {
        "brand_name": doc.brand_name or None,
        "logo_url": doc.logo_url or None,
        "favicon_url": doc.favicon_url or None,
    }


@frappe.whitelist()
def dismiss_onboarding():
    """Persist that the current user has seen/skipped/completed the
    onboarding wizard, so it stops re-firing on every reload."""
    frappe.defaults.set_user_default("bp_onboarding_dismissed", "1", frappe.session.user)
    frappe.db.commit()
    return {"ok": True}


NUDGE_DEFAULT_PREFIX = "bp_nudge_dismissed_"


@frappe.whitelist()
def dismiss_nudge(nudge_id: str):
    """Persist that the current user dismissed a specific nudge card
    (see get_entitlements' dismissed_nudges) so it never reappears for them."""
    frappe.defaults.set_user_default(f"{NUDGE_DEFAULT_PREFIX}{nudge_id}", "1", frappe.session.user)
    frappe.db.commit()
    return {"ok": True}


def _dismissed_nudges() -> list[str]:
    defaults = frappe.defaults.get_defaults() or {}
    return [
        key[len(NUDGE_DEFAULT_PREFIX):]
        for key, value in defaults.items()
        if key.startswith(NUDGE_DEFAULT_PREFIX) and value == "1"
    ]
