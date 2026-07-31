/**
 * entitlements.js — the install's plan/tier and which premium features are unlocked.
 * Sourced from the licensed gateway (see batch_projects/entitlements.py). Fetched
 * once at app bootstrap; components read `can(feature)` to gate premium UI.
 */
import { defineStore } from "pinia";
import { ref, computed } from "vue";
import { toast } from "vue-sonner";
import * as api from "@/utils/api";
import { onRealtimeEvent } from "@/utils/realtime";

export const useEntitlementsStore = defineStore("entitlements", () => {
  const tier = ref("starter");
  const tierLabel = ref("Free");
  const features = ref({});          // { automations: true|false, ... } — tier gate
  const featureMinTier = ref({});    // { automations: "team", ... }
  const workspaceFeatures = ref({}); // { gantt: true|false, ... } — admin on/off toggle
  const isWorkspaceAdmin = ref(false);
  const limits = ref({});
  const loaded = ref(false);
  // License expiry info (from gateway headers)
  const expiresAt = ref(null);
  const daysRemaining = ref(null);
  const isExpiringSoon = computed(() => {
    if (daysRemaining.value === null) return false;
    return daysRemaining.value > 0 && daysRemaining.value <= 14;
  });
  const isExpired = computed(() => {
    return daysRemaining.value !== null && daysRemaining.value <= 0;
  });
  // { role: { capability: bool } }, same for every project (a
  // workspace-wide policy, not project data). Combine with the per-project
  // role from the project store's my_capabilities call to answer "can I see
  // money/files HERE" — see stores/project.js `hasCapability`.
  const capabilityMatrix = ref({});
  // Cross-project surfaces (margin report) have no single project to
  // resolve a role against — pre-resolved by the backend instead.
  const viewMoneyAnywhere = ref(true);
  // White-label branding (Team plan+) — null fields = default app branding.
  const branding = ref({ brand_name: null, logo_url: null, favicon_url: null });
  // Distinguishes "this workspace has zero projects at all" (true
  // first-run, App.vue shows the create-workspace wizard) from "my own
  // project list is empty because nothing's shared with me yet" (an
  // invited teammate — App.vue shows a lighter join/waiting state instead).
  const workspaceHasProjects = ref(true); // fail-open: don't wizard-trap an existing workspace on a slow/failed bootstrap
  const onboardingDismissed = ref(false);
  // Dismissable nudge/announcement cards (floating, bottom-corner — see
  // ui/NudgeCard.vue). Per-user, per-nudge-id persistence via frappe.defaults
  // (batch_projects.entitlements.dismiss_nudge), same mechanism as onboarding.
  const dismissedNudges = ref(new Set());

  const isPaid = computed(() => tier.value !== "starter");

  // ── Seat consumption ─────────────────────────────────────────────────
  const seatsUsed = computed(() => {
    // Backend emits seats_used in get_entitlements response
    return limits.value.seats_used ?? 0;
  });
  const seatsTotal = computed(() => {
    const v = limits.value.max_users;
    if (v === undefined || v === null) return 0;
    return v;
  });
  const seatsRemaining = computed(() => {
    if (seatsTotal.value === 0) return Infinity; // unlimited
    return Math.max(0, seatsTotal.value - seatsUsed.value);
  });
  const isAtCapacity = computed(() => {
    return seatsTotal.value > 0 && seatsRemaining.value <= 0;
  });

  const _LABELS = { starter: "Community", growth: "Growth", pro: "Pro", team: "Team", business: "Business", enterprise: "Enterprise", dev: "Developer" };

  /** Apply an entitlements payload from either source:
   *  - Frappe `get_entitlements`: features is a {name:bool} map, limits is an object.
   *  - bridge bootstrap/entitlements: features is a string[] (enabled list), max_users top-level.
   *  The bridge is authoritative for tier (it holds the license), so on Frappe Cloud
   *  — where Frappe-direct can't see the gateway's X-BP-Tier header — we seed from the
   *  bridge bootstrap rather than the Frappe mirror. */
  function applyEntitlements(e) {
    if (!e) return;
    tier.value = e.tier || "starter";
    tierLabel.value = e.tier_label || _LABELS[e.tier] || "Free";
    featureMinTier.value = e.feature_min_tier || {};
    if (Array.isArray(e.features)) {
      const enabled = new Set(e.features);
      const keys = Object.keys(featureMinTier.value);
      const map = {};
      if (keys.length) for (const k of keys) map[k] = enabled.has(k);
      else for (const f of e.features) map[f] = true;
      features.value = map;
    } else {
      features.value = e.features || {};
    }
    // Merge: limits from backend (which may contain max_users) + top-level
    // seats_used field — the backend emits both shapes depending on source.
    const base = e.limits || {};
    if (e.max_users != null) base.max_users = e.max_users;
    if (e.seats_used != null) base.seats_used = e.seats_used;
    limits.value = base;
    workspaceFeatures.value = e.workspace_features || {};
    isWorkspaceAdmin.value = e.is_workspace_admin === true;
    capabilityMatrix.value = e.capability_matrix || {};
    viewMoneyAnywhere.value = e.view_money_anywhere !== false;
    branding.value = e.branding || { brand_name: null, logo_url: null, favicon_url: null };
    // License expiry
    expiresAt.value = e.expires_at || null;
    daysRemaining.value = e.days_remaining != null ? e.days_remaining : null;
    // Only the Frappe mirror (batch_projects.entitlements.get_entitlements)
    // carries these two — the bridge bootstrap payload doesn't, so leave
    // them untouched (at their fail-open defaults) when seeded from there;
    // loadBranding-style behavior isn't needed since App.vue's onMounted
    // always also calls entitlements.load() as a fallback/second source.
    if (e.workspace_has_projects !== undefined) workspaceHasProjects.value = e.workspace_has_projects;
    if (e.onboarding_dismissed !== undefined) onboardingDismissed.value = e.onboarding_dismissed;
    if (Array.isArray(e.dismissed_nudges)) dismissedNudges.value = new Set(e.dismissed_nudges);
    loaded.value = true;
  }

  // Call when the onboarding wizard (or the lighter "nothing shared
  // with you yet" state) is dismissed, skipped, or completed. Optimistic:
  // flips the local flag immediately so it can't re-fire later in the same
  // session even if the request is slow; the server call is what makes it
  // stick across reloads/devices.
  async function dismissOnboarding() {
    onboardingDismissed.value = true;
    try {
      await api.dismissOnboarding();
    } catch {
      // Best-effort — worst case it re-prompts next session, not a lockout.
    }
  }

  async function load() {
    try {
      applyEntitlements(await api.getEntitlements());
    } catch {
      // On failure assume free — never accidentally unlock premium features.
      tier.value = "starter";
      features.value = {};
      loaded.value = true;
    }
  }

  /** Branding (brand_name/logo_url/favicon_url) lives in Frappe's BP
   *  Workspace Settings, not the gateway's license/tier data — the bridge
   *  bootstrap path (authoritative for tier) has no reason to know about it.
   *  Fetched separately so it's correct regardless of which path seeded the
   *  rest of entitlements. Only touches `branding` — never overwrites the
   *  tier/features the bridge already applied.
   *
   *  Also carries workspace_has_projects/onboarding_dismissed for
   *  the same reason: those two are Frappe-mirror-only fields the bridge's
   *  own bootstrap payload doesn't have, and App.vue's bridge branch only
   *  falls back to entitlements.load() on bridge FAILURE — so without this,
   *  a cross-origin/Frappe-Cloud install (bridge succeeds) would never
   *  learn either value and the onboarding fix wouldn't take effect there. */
  async function loadBranding() {
    try {
      const e = await api.getEntitlements();
      branding.value = e.branding || { brand_name: null, logo_url: null, favicon_url: null };
      if (e.workspace_has_projects !== undefined) workspaceHasProjects.value = e.workspace_has_projects;
      if (e.onboarding_dismissed !== undefined) onboardingDismissed.value = e.onboarding_dismissed;
      if (Array.isArray(e.dismissed_nudges)) dismissedNudges.value = new Set(e.dismissed_nudges);
    } catch {
      // Leave whatever's already loaded — a transient failure here
      // shouldn't strip a workspace's custom branding or re-wizard-trap.
    }
  }

  /** True once the user has dismissed this specific nudge (any device, any session). */
  const isNudgeDismissed = (nudgeId) => dismissedNudges.value.has(nudgeId);

  /** Optimistic, same pattern as dismissOnboarding — flips locally so it can't
   *  re-render later in this session even if the request is slow. */
  async function dismissNudge(nudgeId) {
    dismissedNudges.value.add(nudgeId);
    try {
      await api.dismissNudge(nudgeId);
    } catch {
      // Best-effort — worst case it reappears next session, not a lockout.
    }
  }

  // Live plan changes (bp-gateway's premium.LicenseRefresh, pushed over the
  // same always-on realtime connection project.js uses) — a payment going
  // through unlocks the new tier immediately, no reload needed. Only fires
  // when the gateway itself decided something actually changed (see
  // LicenseRefresh's own no-op guard), so this can't spam a toast on a
  // bp-license heartbeat re-send of the same plan.
  onRealtimeEvent((payload) => {
    if (payload?.event !== "entitlement.changed") return;
    const previousTier = tier.value;
    applyEntitlements({ tier: payload.tier, features: payload.features });
    if (payload.tier !== previousTier) {
      toast.success(`Your plan is now ${_LABELS[payload.tier] || payload.tier}.`);
    }
  });

  /** True if the current plan unlocks `feature`. */
  const can = (feature) => features.value[feature] === true;

  /** True unless a workspace admin explicitly switched `feature` off
   *  (BP Workspace Settings). Absent key = enabled — default open, not closed. */
  const canWorkspace = (feature) => workspaceFeatures.value[feature] !== false;

  /** The plan label required to unlock `feature` (for upgrade copy). */
  const requiredPlanFor = (feature) => {
    const t = featureMinTier.value[feature] || "team";
    return t.charAt(0).toUpperCase() + t.slice(1);
  };

  /** Pure lookup, given an already-resolved role string (the
   *  project store resolves the caller's role per project via
   *  get_my_capabilities; this store only holds the role-keyed matrix,
   *  which is identical for every project). Defaults to true when the
   *  bootstrap hasn't loaded yet or the role is unknown — cosmetic-only,
   *  same "fail open, server re-checks" posture as canWorkspace. */
  const hasCapability = (role, cap) => {
    if (!role) return false;
    const row = capabilityMatrix.value[role];
    return row ? row[cap] !== false : true;
  };

  /** Show an upgrade toast. Call from components when a seat/feature action is
   *  blocked. Redirects to the Pricing page on action click. */
  let _router = null;
  function showUpgradePrompt(reason = "feature", message) {
    const text = message || (
      reason === "seat_limit"
        ? `Your plan covers ${seatsTotal.value} seats and all are in use. Upgrade to add more people.`
        : "This feature requires a higher plan."
    );
    toast.error(text, {
      action: {
        label: "Upgrade",
        onClick: () => {
          // Lazy-import router to avoid circular deps
          if (!_router) _router = new URL("/workspace/pricing", window.location.origin);
          window.location.href = _router.href;
        },
      },
      duration: 8000,
    });
  }

  return {
    tier, tierLabel, features, workspaceFeatures, isWorkspaceAdmin, limits, loaded, isPaid,
    capabilityMatrix, viewMoneyAnywhere, branding,
    workspaceHasProjects, onboardingDismissed,
    dismissedNudges, isNudgeDismissed, dismissNudge,
    seatsUsed, seatsTotal, seatsRemaining, isAtCapacity,
    expiresAt, daysRemaining, isExpiringSoon, isExpired,
    load, loadBranding, applyEntitlements, can, canWorkspace, requiredPlanFor, hasCapability,
    showUpgradePrompt, dismissOnboarding,
  };
});
