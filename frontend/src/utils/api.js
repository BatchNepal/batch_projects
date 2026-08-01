/**
 * api.js — All Frappe API calls for batch_projects
 * Single source of truth. Every component imports from here.
 */

const BASE = "batch_projects.api.board";

/** Thrown when a gated (premium) feature is used below its required tier.
 *  Components catch this to show the upgrade CTA instead of a generic error. */
export class UpgradeRequiredError extends Error {
  constructor(message) {
    super(message || "This feature requires a higher plan.");
    this.name = "UpgradeRequiredError";
    this.upgradeRequired = true;
  }
}

/** Thrown when a workspace admin has switched a feature off (BP Workspace
 *  Settings). Distinct from UpgradeRequiredError — this isn't a plan limit,
 *  it's the admin's own choice, so the UI should say "ask your admin" rather
 *  than showing an upgrade CTA. */
export class FeatureDisabledError extends Error {
  constructor(message) {
    super(message || "This feature has been turned off for this workspace.");
    this.name = "FeatureDisabledError";
    this.featureDisabled = true;
  }
}

// ─── SESSION EXPIRY ──────────────────────────────────────────────────────────
// Frappe's own is_whitelisted() check uses the EXACT SAME error message/shape
// for two different things: "this method genuinely isn't whitelisted" and
// "you're Guest and this method isn't guest-accessible" (i.e. your session
// died server-side). The only reliable way to tell them apart from the
// response alone is the literal wording its guest-rejection branch always
// includes ("Login to access") — a real per-doctype PermissionError (a
// logged-in user without access to a specific project/record) uses different
// wording and must NOT redirect. A 401 from the bridge (session.Middleware's
// own unambiguous "no valid session" response) is always this case too.
let _redirectingToLogin = false;

function _isPublicRoute() {
  const p = window.location.pathname;
  return p.startsWith("/share/") || p.startsWith("/intake/") || p === "/login";
}

function _looksLikeSessionExpired(status, data) {
  if (status !== 401 && status !== 403) return false;
  const text = typeof data === "string" ? data : JSON.stringify(data || {});
  // gateway_guard.py's verify_gateway_request() ALSO throws AuthenticationError
  // (401) when a request reaches Frappe without going through bp-gateway at
  // all — e.g. the Vite dev server (localhost:8090) proxying straight to
  // Frappe, bypassing the gateway entirely. That's a routing/config problem,
  // not "you're logged out" — you can be fully authenticated and still hit
  // this. Redirecting to login for it is actively wrong: login succeeds, the
  // very next gated call 401s again for the same non-auth reason, straight
  // back to login (a real loop this exact check caused once already).
  if (text.includes("come through the bp-gateway")) return false;
  if (status === 401) return true;
  // 403: only Frappe's is_whitelisted() guest-rejection wording — a real
  // per-doctype PermissionError (logged in, just lacks access to this
  // record) uses different wording and must NOT redirect.
  return text.includes("Login to access");
}

/** Send the browser to Frappe's login page, preserving the current path so
 *  login returns the user where they were. No-ops on public/share/intake
 *  routes (Guest is the expected, normal state there) and if a redirect is
 *  already in flight — many concurrent API calls can all detect the same
 *  expired session at once, and only one navigation should happen. */
function _redirectToLogin() {
  if (_redirectingToLogin || _isPublicRoute()) return;
  _redirectingToLogin = true;
  const redirectTo = window.location.pathname + window.location.search;
  window.location.href = `/login?redirect-to=${encodeURIComponent(redirectTo)}`;
}

// Call any whitelisted method by full dotted path (not just the board module).
//
// TOPOLOGY ROUTING:
//   • Self-hosted (same-origin): the SPA is served from the gateway's origin,
//     so fetch('/api/method/...') hits the gateway's /api/ chain automatically.
//     The sid cookie flows and the gateway proxies + caches + rate-limits.
//   • Frappe Cloud (cross-origin): the SPA is on Frappe Cloud, the gateway is
//     on another host. We route ALL API calls through the bridge's proxy so
//     the gateway is the mandatory passage for every request.
const MINT_BRIDGE_TOKEN_METHOD = "batch_projects.api.session.mint_bridge_token";

async function callPath(fullMethod, params = {}) {
  // Cross-origin: route through the bridge proxy.
  // The bridge proxies /api/method/* to Frappe with HMAC-signed headers.
  if (bridgeIsCrossOrigin()) {
    // Components mount (and fire their own onMounted API calls) in Vue's
    // child-before-parent order, which means e.g. Sidebar's notification-count
    // fetch runs BEFORE App.vue's onMounted even calls bootstrapBridge() —
    // _gatewayJWT is guaranteed still null at that point, not just "usually".
    // Falling through to the same-origin fetch below in that state used to
    // 403 (gateway_guard rejects anything that didn't come through the
    // bridge); wait for bootstrap to actually settle instead. mint_bridge_token
    // is exempt: it's what bootstrapBridge itself calls to GET a bearer, pre-JWT
    // by definition — waiting on it here would deadlock bootstrap on itself.
    if (!_gatewayJWT && fullMethod !== MINT_BRIDGE_TOKEN_METHOD) {
      await _bridgeReady;
    }
    if (_gatewayJWT) {
      return bridgeProxyCall(fullMethod, params);
    }
    if (fullMethod !== MINT_BRIDGE_TOKEN_METHOD) {
      // Bootstrap settled (or was never started on this page) with no JWT —
      // cross-origin mode has no other legal path to Frappe.
      throw new Error("Bridge session not ready — please retry.");
    }
  }

  // Same-origin: the gateway IS the origin — fetch goes through it automatically.
  const res = await fetch(`/api/method/${fullMethod}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Frappe-CSRF-Token": window.csrf_token || "",
    },
    body: JSON.stringify(params),
  });

  const data = await res.json().catch(() => ({}));

  if (_looksLikeSessionExpired(res.status, data)) {
    _redirectToLogin();
    throw new Error("Session expired — redirecting to login.");
  }

  // Premium gate: backend raised BPUpgradeRequired.
  if (data.exc_type === "BPUpgradeRequired" ||
      (data.exc && data.exc.includes("BPUpgradeRequired"))) {
    let msg = "This feature requires a higher plan.";
    try {
      if (data._server_messages) {
        const first = JSON.parse(data._server_messages)[0];
        const inner = typeof first === "string" ? JSON.parse(first) : first;
        if (inner?.message) msg = inner.message;
      }
    } catch {}
    throw new UpgradeRequiredError(msg);
  }

  // Workspace admin turned the feature off: backend raised BPFeatureDisabled.
  if (data.exc_type === "BPFeatureDisabled" ||
      (data.exc && data.exc.includes("BPFeatureDisabled"))) {
    let msg = "This feature has been turned off for this workspace.";
    try {
      if (data._server_messages) {
        const first = JSON.parse(data._server_messages)[0];
        const inner = typeof first === "string" ? JSON.parse(first) : first;
        if (inner?.message) msg = inner.message;
      }
    } catch {}
    throw new FeatureDisabledError(msg);
  }

  // Frappe puts a clean "module.ExceptionClass: message" in data.exception.
  // data.exc is the full traceback, JSON-encoded a second time (so any
  // embedded unicode/newlines in the message show up as literal escape
  // sequences if regexed directly) — only fall back to it if exception is
  // somehow absent.
  const excSource = data.exception || data.exc;
  if (excSource) {
    const match = excSource.match(/frappe\.exceptions\.\w+: (.+)/);
    throw new Error(match ? match[1] : excSource);
  }

  if (!res.ok) {
    // Try to extract a human-readable message from Frappe's error response
    let msg = `API error: ${res.status}`;
    try {
      if (data._server_messages) {
        const parsed = JSON.parse(data._server_messages);
        const first = parsed[0];
        const inner = typeof first === 'string' ? JSON.parse(first) : first;
        if (inner?.message) msg = inner.message;
      } else if (data.message) {
        msg = typeof data.message === 'string' ? data.message : msg;
      }
    } catch {}
    throw new Error(msg);
  }

  return data.message;
}

// Board-module convenience wrapper (the vast majority of calls).
const call = (method, params = {}) => callPath(`${BASE}.${method}`, params);

/** Call a Frappe API method through the bridge's proxy (/api/method/...).
 *  Used on Frappe Cloud where the bridge is on a different origin — all
 *  API traffic must pass through the gateway so it can sign requests,
 *  enforce licensing, and cache. Sends the gateway JWT as bearer auth. */
async function bridgeProxyCall(fullMethod, params = {}) {
  const headers = {
    "Content-Type": "application/json",
    "X-Frappe-CSRF-Token": window.csrf_token || "",
  };
  if (_gatewayJWT) {
    headers["Authorization"] = `Bearer ${_gatewayJWT}`;
  }
  const res = await fetch(`${bridgeBase()}/api/method/${fullMethod}`, {
    method: "POST",
    headers,
    credentials: "include",
    body: JSON.stringify(params),
  });
  const data = await res.json().catch(() => ({}));
  if (_looksLikeSessionExpired(res.status, data)) {
    _redirectToLogin();
    throw new Error("Session expired — redirecting to login.");
  }
  if (data.exc_type === "BPUpgradeRequired") {
    throw new UpgradeRequiredError(data.message);
  }
  if (data.exc_type === "BPFeatureDisabled") {
    throw new FeatureDisabledError(data.message);
  }
  if (data.exception || data.exc) {
    const excSource = data.exception || data.exc;
    const match = excSource.match(/frappe\.exceptions\.\w+: (.+)/);
    throw new Error(match ? match[1] : excSource);
  }
  if (!res.ok) {
    throw new Error(data.message || `bridge proxy error: ${res.status}`);
  }
  return data.message;
}

// ─── BRIDGE (bp-gateway premium plane, /v1/*) ─────────────────────────────────
// Premium features live on the Go bridge, not Frappe. The bridge URL is wired
// ONCE per deployment and never touched again:
//   1. window.__BP_BRIDGE_URL__   (runtime global — set in index.html/config.js)
//   2. <meta name="bp-bridge-url" content="https://bridge.example.com">
//   3. "" → same-origin (self-host where the bridge also fronts the SPA)
//
// Same-origin (self-host fronted): the sid cookie flows automatically.
// Cross-origin (Frappe Cloud SPA → bridge on another host): see the token
// handoff TODO below — the httpOnly sid cookie can't cross domains, so a
// short-lived bearer issued by Frappe is required. Tracked, not yet built.
export function bridgeBase() {
  if (typeof window !== "undefined") {
    if (window.__BP_BRIDGE_URL__) return String(window.__BP_BRIDGE_URL__).replace(/\/$/, "");
    const meta = document.querySelector('meta[name="bp-bridge-url"]');
    if (meta?.content) return meta.content.replace(/\/$/, "");
  }
  return ""; // same-origin
}

/** Call a /v1/* endpoint on the bridge. Reuses the BPUpgradeRequired contract
 *  so a bridge-side gate throws the same UpgradeRequiredError as a Frappe gate. */
export async function bridgeCall(path, { method = "GET", body, token } = {}) {
  const headers = { "Content-Type": "application/json" };
  // Prefer an explicit token (the one-time bootstrap bearer); otherwise attach the
  // cached gateway session JWT — the cross-origin credential when the sid cookie
  // can't reach the bridge (Frappe Cloud). Same-origin still also sends the cookie.
  const bearer = token || _gatewayJWT;
  if (bearer) headers["Authorization"] = `Bearer ${bearer}`;
  const res = await fetch(`${bridgeBase()}/v1/${path.replace(/^\//, "")}`, {
    method,
    headers,
    credentials: "include", // sends sid same-origin; needs CORS allow-credentials cross-origin
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (_looksLikeSessionExpired(res.status, data)) {
    _redirectToLogin();
    throw new Error("Session expired — redirecting to login.");
  }
  if (res.status === 402 || data.exc_type === "BPUpgradeRequired") {
    throw new UpgradeRequiredError(data.message);
  }
  if (!res.ok) throw new Error(data.message || data.error || `bridge error: ${res.status}`);
  return data;
}

// ─── BILLING (via gateway proxy → bp-license) ────────────────────────────────

/** Fetch the plan catalog from bp-license via the gateway proxy. */
export const getPlans = () => bridgeCall("billing/plans");

/** Create a Dodo checkout session for the given tier and period.
 *  Returns { checkout_url, session_id }. Redirect the user to checkout_url. */
export const createCheckoutSession = (tier, period = "monthly", discountCode) =>
  bridgeCall("billing/checkout", {
    method: "POST",
    body: { tier, period, discount_code: discountCode || undefined },
  });

/** Get the authenticated user's active subscriptions. */
export const getMySubscriptions = () => bridgeCall("billing/subscriptions");

/** Get the Dodo customer portal URL (manage billing / payment methods). */
export const getBillingPortal = () =>
  bridgeCall("billing/portal", { method: "POST" });

// ─── BRIDGE SESSION BOOTSTRAP ─────────────────────────────────────────────────
// One post-login handshake with the bridge → entitlements + a gateway session JWT
// the SPA then carries on every bridge call. Works in both topologies:
//   • same-origin (self-host fronted): the sid cookie reaches the bridge directly.
//   • cross-origin (Frappe Cloud): the sid cookie can't cross origins, so we first
//     mint a short-lived bearer from Frappe (same-origin) and hand it to the bridge.

let _gatewayJWT = null;
export const getGatewayJWT = () => _gatewayJWT;
export const setGatewayJWT = (t) => { _gatewayJWT = t || null; };

// Resolved once bootstrapBridge() settles (success or failure) so callPath
// can safely await it instead of racing ahead — see callPath's cross-origin
// branch. Exists from module load (not created lazily inside
// bootstrapBridge itself) since Vue mounts children before parents: a
// component's own onMounted call can reach callPath before App.vue's
// onMounted has even called bootstrapBridge(). The timeout is a safety net
// for routes that never call bootstrapBridge at all (e.g. a guest landing
// on an allow-guest shell route) so such a call fails fast instead of
// hanging forever.
let _resolveBridgeReady;
const _bridgeReady = new Promise((resolve) => { _resolveBridgeReady = resolve; });
setTimeout(() => _resolveBridgeReady(), 8000);

/** True when the bridge runs on a different origin than the SPA (Frappe Cloud). */
function bridgeIsCrossOrigin() {
  const base = bridgeBase();
  if (!base) return false; // empty → same-origin
  try {
    return new URL(base, window.location.href).origin !== window.location.origin;
  } catch {
    return false;
  }
}

/** Mint the short-lived cross-origin bootstrap bearer from Frappe (same-origin). */
export const mintBridgeToken = () => callPath("batch_projects.api.session.mint_bridge_token");

// The gateway JWT is short-lived by design (session_ttl_seconds: 300 in
// prod config) and bootstrapBridge() used to only ever be called once, at
// mount. Any tab left open past that TTL had every subsequent call 401,
// which _looksLikeSessionExpired treats as "logged out" and bounces to
// /login — which then immediately bounces back since the underlying Frappe
// sid cookie was still fine, looking like a spontaneous page refresh every
// ~5 idle minutes. The bootstrap response already carries jwt_expires_in
// (handler.go) for exactly this; just act on it.
let _refreshTimer = null;
const REFRESH_SAFETY_MARGIN_SECS = 30;

/** Bootstrap the bridge session. Returns {user, entitlements, gateway_jwt, …}.
 *  Throws if the bridge is unreachable — it is the mandatory passage for ALL
 *  API calls (self-hosted via same-origin proxy; Frappe Cloud via cross-origin).
 *  Caches the gateway JWT for subsequent bridge calls and schedules a silent
 *  re-mint before it expires, so a tab left open never sees a hard 401. */
export async function bootstrapBridge() {
  try {
    let token;
    if (bridgeIsCrossOrigin()) {
      // Cross-origin (Frappe Cloud): sid cookie can't reach the bridge.
      // Mint a short-lived bearer from Frappe (same-origin, pre-bridge),
      // then hand it to the bridge for the bootstrap handshake.
      const minted = await mintBridgeToken();
      token = minted?.token;
      if (!token) {
        throw new Error("Bridge bootstrap token not issued — site may not be configured for the bridge.");
      }
    }
    // Same-origin: sid cookie flows to the bridge automatically (no bearer needed).
    const payload = await bridgeCall("session/bootstrap", { token });
    if (payload?.gateway_jwt) {
      setGatewayJWT(payload.gateway_jwt);
    } else {
      throw new Error("Bridge bootstrap failed — no gateway JWT returned.");
    }

    if (_refreshTimer) clearTimeout(_refreshTimer);
    const ttlSecs = Number(payload?.jwt_expires_in) || 300;
    const delayMs = Math.max(ttlSecs - REFRESH_SAFETY_MARGIN_SECS, REFRESH_SAFETY_MARGIN_SECS) * 1000;
    _refreshTimer = setTimeout(() => {
      bootstrapBridge().catch((e) => console.warn("[BP] silent JWT refresh failed:", e));
    }, delayMs);

    return payload;
  } finally {
    // Unblock any callPath() call that's waiting on _bridgeReady, whether
    // bootstrap just succeeded (JWT set — they'll proceed) or failed (JWT
    // still null — they'll throw the clear "not ready" error instead of
    // silently 403ing against Frappe directly).
    _resolveBridgeReady();
  }
}

/** Tear down the bridge session (called on logout). */
export async function bridgeLogout() {
  if (_refreshTimer) { clearTimeout(_refreshTimer); _refreshTimer = null; }
  try { await bridgeCall("session/logout", { method: "POST" }); } catch { /* best-effort */ }
  setGatewayJWT(null);
}

// ─── ENTITLEMENTS (monetization) ──────────────────────────────────────────────

export const getEntitlements = () => callPath("batch_projects.entitlements.get_entitlements");

// Entitlements straight from the bridge (authoritative tier/packs/features).
// Prefer this when the bridge is wired; falls back to the Frappe mirror above.
export const getBridgeEntitlements = () => bridgeCall("premium/entitlements");

// Persist that this user has seen/skipped/completed onboarding, so
// App.vue's trigger stops re-firing on reload.
export const dismissOnboarding = () => callPath("batch_projects.entitlements.dismiss_onboarding");
export const dismissNudge = (nudge_id) => callPath("batch_projects.entitlements.dismiss_nudge", { nudge_id });

// Who's online right now (Team+, same gate as realtime) — {users: [email, ...]}.
export const getPresence = () => bridgeCall("presence");

// ─── WORKSPACE SETTINGS (org-wide, one record for the whole site) ──
// Members get feature flags only; workspace admins get the full record.

const WORKSPACE_SETTINGS_BASE = "batch_projects.api.workspace_settings";
const callWorkspaceSettings = (method, params = {}) =>
  callPath(`${WORKSPACE_SETTINGS_BASE}.${method}`, params);

export const getWorkspaceSettings = () => callWorkspaceSettings("get_workspace_settings");
export const updateWorkspaceSettings = (params) =>
  callWorkspaceSettings("update_workspace_settings", params);

// ─── BP WORKFLOW (automation canvas) ──────────────────────────────

const WORKFLOWS_BASE = "batch_projects.api.workflows";
const callWorkflows = (method, params = {}) => callPath(`${WORKFLOWS_BASE}.${method}`, params);

export const listWorkflows = (project) => callWorkflows("list_workflows", { project });
export const getWorkflow = (name) => callWorkflows("get_workflow", { name });
export const saveWorkflow = (params) => callWorkflows("save_workflow", params);
export const deleteWorkflow = (name) => callWorkflows("delete_workflow", { name });
export const testWorkflow = (name, task = null) => callWorkflows("test_workflow", { name, task });
export const getWorkflowRuns = (workflow, since = null, limit = 20) =>
  callWorkflows("get_workflow_runs", { workflow, since, limit });
export const convertRuleToWorkflow = (rule) => callWorkflows("convert_rule_to_workflow", { rule });
export const getNodeRegistry = () => callPath("batch_projects.api.automation.get_node_registry");

// ─── BP WEBHOOK TOKEN (trigger.webhook's full lifecycle) ──────

const AUTOMATION_BASE = "batch_projects.api.automation";
const callAutomation = (method, params = {}) => callPath(`${AUTOMATION_BASE}.${method}`, params);

export const createWebhookToken = (params) => callAutomation("create_webhook_token", params);
export const listWebhookTokens = (project = null) => callAutomation("list_webhook_tokens", { project });
export const revokeWebhookToken = (name) => callAutomation("revoke_webhook_token", { name });

// ─── BP INTEGRATION CREDENTIAL ────────────────────────────────────

const CREDENTIALS_BASE = "batch_projects.api.credentials";
const callCredentials = (method, params = {}) => callPath(`${CREDENTIALS_BASE}.${method}`, params);

export const listCredentials = (project) => callCredentials("list_credentials", { project });
export const createCredential = (params) => callCredentials("create_credential", params);
export const deleteCredential = (name) => callCredentials("delete_credential", { name });
export const getOauthProviders = () => callCredentials("get_oauth_providers");
export const getOauthAuthorizeUrl = (provider, ownerProject) =>
  callCredentials("get_oauth_authorize_url", { provider, owner_project: ownerProject });

// ─── SPRINT ANALYTICS (agile metrics) ──────────────────────────────

const ANALYTICS_BASE = "batch_projects.api.sprint_analytics";
const callAnalytics = (method, params = {}) => callPath(`${ANALYTICS_BASE}.${method}`, params);

export const getSprintHealth = (sprint) => callAnalytics("get_sprint_health", { sprint });

// ─── NOTIFICATION TEMPLATES + RULES ───────────────────────────────

const NOTIF_ADMIN_BASE = "batch_projects.api.notifications_admin";
const callNotifAdmin = (method, params = {}) => callPath(`${NOTIF_ADMIN_BASE}.${method}`, params);

export const getNotificationTemplates = () => callNotifAdmin("get_notification_templates");
export const updateNotificationTemplate = (event_key, subject, body, enabled) =>
  callNotifAdmin("update_notification_template", { event_key, subject, body, enabled });
export const previewNotificationTemplate = (event_key, subject, body) =>
  callNotifAdmin("preview_notification_template", { event_key, subject, body });

export const getNotificationRules = () => callNotifAdmin("get_notification_rules");
export const createNotificationRule = (params) => callNotifAdmin("create_notification_rule", params);
export const updateNotificationRule = (name, params) =>
  callNotifAdmin("update_notification_rule", { name, ...params });
export const deleteNotificationRule = (name) => callNotifAdmin("delete_notification_rule", { name });

// ─── AUTOMATION RULES (premium — Team tier+) ───────────────────────────────────

export const getAutomationOptions = (project = null) => call("get_automation_options", { project });
export const getAutomationRules = (project = null) => call("get_automation_rules", { project });
export const getAutomationRuns = ({ project = null, rule = null, limit = 40 } = {}) =>
  call("get_automation_runs", { project, rule, limit });
export const createAutomationRule = (params) => call("create_automation_rule", params);
export const updateAutomationRule = (params) => call("update_automation_rule", params);
export const toggleAutomationRule = (rule, is_active) =>
  call("toggle_automation_rule", { rule, is_active: is_active ? 1 : 0 });
export const deleteAutomationRule = (rule) => call("delete_automation_rule", { rule });
export const duplicateAutomationRule = (rule) => call("duplicate_automation_rule", { rule });

// ─── TASK TEMPLATES (premium — Team tier+; listing is free) ───────────────────

const TEMPLATES_BASE = "batch_projects.api.task_templates";
const callTemplates = (method, params = {}) => callPath(`${TEMPLATES_BASE}.${method}`, params);

export const listTaskTemplates = (project) => callTemplates("list_task_templates", { project });
export const saveTaskAsTemplate = (task, template_name) =>
  callTemplates("save_task_as_template", { task, template_name });
export const createTaskTemplate = (params) => callTemplates("create_task_template", params);
export const updateTaskTemplate = (params) => callTemplates("update_task_template", params);
export const deleteTaskTemplate = (template) => callTemplates("delete_task_template", { template });
export const createTaskFromTemplate = (template, overrides) =>
  callTemplates("create_task_from_template", { template, overrides });

// ─── PROJECT TEMPLATES (premium Team tier+; listing is free) ───────

const PROJECT_TEMPLATES_BASE = "batch_projects.api.project_templates";
const callProjectTemplates = (method, params = {}) => callPath(`${PROJECT_TEMPLATES_BASE}.${method}`, params);

export const listProjectTemplates = () => callProjectTemplates("list_project_templates");
export const getProjectTemplate = (template) => callProjectTemplates("get_project_template", { template });
export const saveProjectAsTemplate = (params) => callProjectTemplates("save_project_as_template", params);
export const updateProjectTemplate = (params) => callProjectTemplates("update_project_template", params);
export const deleteProjectTemplate = (template) => callProjectTemplates("delete_project_template", { template });
export const createProjectFromTemplate = (params) => callProjectTemplates("create_project_from_template", params);

// ─── ERP MONEY SPINE ──────────────────────────────────────────────
// Linking is free-tier plumbing; get_project_money is gated (Business tier).

const ERP_LINK_BASE = "batch_projects.api.erp_link";
const callErpLink = (method, params = {}) => callPath(`${ERP_LINK_BASE}.${method}`, params);

export const linkErpnextProject = (project, erpnext_project) =>
  callErpLink("link_erpnext_project", { project, erpnext_project });
export const createAndLinkErpnextProject = (project) =>
  callErpLink("create_and_link_erpnext_project", { project });
export const unlinkErpnextProject = (project) =>
  callErpLink("unlink_erpnext_project", { project });
export const searchErpnextProjects = (txt) =>
  callErpLink("search_erpnext_projects", { txt });
export const getProjectMoney = (project, period) =>
  callErpLink("get_project_money", { project, period });
export const generateInvoice = (project, period) =>
  callErpLink("generate_invoice", { project, period });
export const generateExpenseInvoice = (project) =>
  callErpLink("generate_expense_invoice", { project });
export const getErpDocSummary = (project, doctype, name) =>
  callErpLink("get_erp_doc_summary", { project, doctype, name });
export const submitTimesheet = (project, timesheet) =>
  callErpLink("submit_timesheet", { project, timesheet });
export const getErpDoctypeFields = (doctype) =>
  callErpLink("get_erp_doctype_fields", { doctype });
export const searchNonStockItems = (txt) =>
  callErpLink("search_non_stock_items", { txt });
export const createPurchaseOrderFromTask = (task, supplier, items) =>
  callErpLink("create_purchase_order_from_task", { task, supplier, items });

// ─── NOTES (project-level, team-visible) ────────────────────────

const NOTES_BASE = "batch_projects.api.notes";
const callNotes = (method, params = {}) => callPath(`${NOTES_BASE}.${method}`, params);

export const listNotes = (project) => callNotes("list_notes", { project });
export const createNote = (project, title, content, pinned) =>
  callNotes("create_note", { project, title, content, pinned });
export const updateNote = (name, params) => callNotes("update_note", { name, ...params });
export const deleteNote = (name) => callNotes("delete_note", { name });

// ─── DRAWINGS (Excalidraw whiteboard, Team+ tier) ───────────────

const DRAWINGS_BASE = "batch_projects.api.drawings";
const callDrawings = (method, params = {}) => callPath(`${DRAWINGS_BASE}.${method}`, params);

export const listDrawings = (project) => callDrawings("list_drawings", { project });
export const getDrawing = (name) => callDrawings("get_drawing", { name });
export const createDrawing = (project, title) => callDrawings("create_drawing", { project, title });
export const saveDrawing = (name, params) => callDrawings("save_drawing", { name, ...params });
export const deleteDrawing = (name) => callDrawings("delete_drawing", { name });

// ─── CUSTOM FIELD LIBRARY (workspace-level field library) ──────────────────
// Definition CRUD is workspace-admin-only; attach/detach is project-Admin;
// get_project_fields is Viewer+ (per-field view_role further strips server-side).

const CUSTOM_FIELDS_BASE = "batch_projects.api.custom_fields";
const callCustomFields = (method, params = {}) => callPath(`${CUSTOM_FIELDS_BASE}.${method}`, params);

export const listLibraryFields = () => callCustomFields("list_library_fields");
export const listAttachableFields = () => callCustomFields("list_attachable_fields");
export const createLibraryField = (params) => callCustomFields("create_field", params);
export const updateLibraryField = (name, params) => callCustomFields("update_field", { name, ...params });
export const deleteLibraryField = (name) => callCustomFields("delete_field", { name });
export const attachFieldToProject = (project, custom_field, required = 0) =>
  callCustomFields("attach_field_to_project", { project, custom_field, required });
export const detachFieldFromProject = (project, custom_field) =>
  callCustomFields("detach_field_from_project", { project, custom_field });
export const getProjectFields = (project, scope = "tasks") =>
  callCustomFields("get_project_fields", { project, scope });
export const searchFieldLinkOptions = (project, field, txt = "") =>
  callCustomFields("search_field_link_options", { project, field, txt });

export const updateProjectCustomFieldValues = (project, values) =>
  call("update_project_custom_field_values", { project, values: JSON.stringify(values) });

// ─── TASK TIMER ────────────────────────────────────────────────────

const TIMERS_BASE = "batch_projects.api.timers";
const callTimers = (method, params = {}) => callPath(`${TIMERS_BASE}.${method}`, params);

export const getActiveTimer = () => callTimers("get_active_timer");
export const startTimer = (task) => callTimers("start_timer", { task });
export const stopTimer = () => callTimers("stop_timer");

// ─── SAVED REPORTS (custom report builder, persisted in BP Report) ────────────

export const getReportTasks = (params) => call("get_report_tasks", params);
export const getSavedReports = () => call("get_saved_reports");
export const getSavedReport = (report) => call("get_saved_report", { report });
export const saveReport = (params) => call("save_report", params);
export const deleteSavedReport = (report) => call("delete_saved_report", { report });
export const getMilestoneReport = (milestone) => call("get_milestone_report", { milestone });
export const getProjectBudgetSummary = (project) => call("get_project_budget_summary", { project });

// ─── PROJECTS ────────────────────────────────────────────────────────────────

export const getProjects = () => call("get_projects");

export const getProject = (project) => call("get_project", { project });

export const createProject = (params) => call("create_project", params);

// ─── PROJECT SETTINGS ────────────────────────────────────────────────────────

export const getWorkflowTemplates = () => call("get_workflow_templates");

// Single source of truth for project templates (statuses, issue types, views).
// Backed by setup/project_templates.py — use this to replace the duplicated
// frontend constants in constants/project-templates.js et al.
export const getProjectTemplates = () => call("get_project_templates");

// ─── GANTT / SCHEDULE AXIS ───────────────────────────────────────────────────
// Tasks + dependency edges + status colors for the Gantt timeline.
export const getGantt = (project) => call("get_gantt", { project });

export const updateProjectWorkflow = (project, workflow_states) =>
  call("update_project_workflow", {
    project,
    workflow_states: JSON.stringify(workflow_states),
  });

export const updateProjectIssueTypes = (project, issue_types) =>
  call("update_project_issue_types", {
    project,
    issue_types: JSON.stringify(issue_types),
  });

export const updateProjectLabels = (project, labels) =>
  call("update_project_labels", {
    project,
    labels: JSON.stringify(labels),
  });

export const updateProjectMembers = (project, members) =>
  call("update_project_members", {
    project,
    members: JSON.stringify(members),
  });

// ─── BOARD ───────────────────────────────────────────────────────────────────

export const getBoard = (project, showChildTasks = false) =>
  call("get_board", { project, show_child_issues: showChildTasks });

// Never cached (unlike get_board), safe to call once per project switch.
export const getMyCapabilities = (project) => call("get_my_capabilities", { project });

export const updateTaskStatus = (task, status, board_order, force = false) =>
  call("update_task_status", { issue: task, status, board_order, force });

// Drag-and-drop move: place `task` between `prev`/`next` neighbour tasks
// (names, or null at column ends), optionally changing status.
export const moveTask = (task, status, prev = null, next = null, force = false) =>
  call("move_task", { issue: task, status, prev, next, force });

// ─── QUERY ENGINE ────────────────────────────────────────────────────────────

/**
 * Unified task query. Used by Board, ListView, Sprint view, Saved Views.
 *
 * @param {string} project
 * @param {object} filters  — { status, assignee, priority, labels, epic,
 *                             sprint, task_type, parent_task, custom_fields,
 *                             due_before, due_after, created_after, search }
 * @param {string} group_by — 'status' | 'priority' | 'assignee' | 'epic' | 'task_type'
 * @param {string} sort_by
 * @param {string} sort_order — 'asc' | 'desc'
 * @param {number} limit
 * @param {number} offset
 */
export const queryTasks = (
  project,
  filters = {},
  group_by = null,
  sort_by = "creation",
  sort_order = "asc",
  limit = null,
  offset = 0,
) =>
  call("query_tasks", {
    project,
    filters: JSON.stringify(filters),
    group_by,
    sort_by,
    sort_order,
    limit,
    offset,
  });

// ─── TASKS ───────────────────────────────────────────────────────────────────

export const getTask = (task) => call("get_task", { issue: task });

export const createTask = (params) => {
  const payload = { ...params };
  // Ensure JSON fields are stringified if passed as objects
  if (
    payload.custom_field_values &&
    typeof payload.custom_field_values === "object"
  ) {
    payload.custom_field_values = JSON.stringify(payload.custom_field_values);
  }
  if (payload.labels && Array.isArray(payload.labels)) {
    payload.labels = JSON.stringify(payload.labels);
  }
  if (payload.assignees && Array.isArray(payload.assignees)) {
    payload.assignees = JSON.stringify(payload.assignees);
  }
  return call("create_task", payload);
};

export const updateTask = (task, fields, force = false) =>
  call("update_task", { issue: task, fields: JSON.stringify(fields), force });

export const deleteTask = (task) => call("delete_task", { issue: task });

export const duplicateTask = (task) => call("duplicate_task", { issue: task });

export const moveTaskToProject = (task, targetProject) =>
  call("move_task_to_project", { issue: task, target_project: targetProject });

export const searchTasks = (query, project, exclude) =>
  call("search_tasks", { query, project, exclude });

// Cross-project task search (connector — links tasks across boards)
export const searchTasksGlobal = (query, exclude) =>
  call("search_tasks_global", { query, exclude });

// ─── COMMENTS ────────────────────────────────────────────────────────────────

export const addComment = (task, comment_text) =>
  call("add_comment", { issue: task, comment_text });

export const editComment = (activity, comment_text) =>
  call("edit_comment", { activity, comment_text });

export const deleteComment = (activity) =>
  call("delete_comment", { activity });

// ─── EPICS ───────────────────────────────────────────────────────────────────

export const getEpics = (project) => call("get_epics", { project });
export const createEpic = (project, data = {}) => call("create_epic", { project, ...data });
export const updateEpic = (epic, fields) => call("update_epic", { epic, fields });
export const deleteEpic = (epic) => call("delete_epic", { epic });

// ─── GOALS / OKRs ───────────────────────────────────────────────────────────
const GOALS_BASE = "batch_projects.api.goals";
const callGoals = (method, params = {}) => callPath(`${GOALS_BASE}.${method}`, params);

export const listGoals = () => callGoals("list_goals");
export const getGoal = (goal) => callGoals("get_goal", { goal });
export const createGoal = (params) => callGoals("create_goal", params);
export const updateGoal = (goal, fields) => callGoals("update_goal", { goal, fields });
export const deleteGoal = (goal) => callGoals("delete_goal", { goal });
export const linkEpicToGoal = (goal, epic) => callGoals("link_epic_to_goal", { goal, epic });
export const unlinkEpicFromGoal = (goal, epic) => callGoals("unlink_epic_from_goal", { goal, epic });

// ─── SAVED VIEWS ─────────────────────────────────────────────────────────────

export const getViews = (project) => call("get_views", { project });
export const saveView = (project, view_name, config, view_type = "board", is_default = 0) =>
  call("save_view", { project, view_name, config, view_type, is_default });
export const updateView = (view, data = {}) => call("update_view", { view, ...data });
export const deleteView = (view) => call("delete_view", { view });
export const setViewSubscription = (view, subscribed = 1, frequency = "Weekly") =>
  call("set_view_subscription", { view, subscribed, frequency });

// ─── SPRINTS ─────────────────────────────────────────────────────────────────

export const getSprints = (project) => call("get_sprints", { project });

export const getSprintCapacity = (sprint) => call("get_sprint_capacity", { sprint });

export const getStandup = (sprint, entryDate) => call("get_standup", { sprint, entry_date: entryDate });
export const saveStandup = (sprint, fields) => call("save_standup", { sprint, ...fields });

export const createSprint = (
  project,
  sprint_name,
  goal,
  start_date,
  end_date,
) =>
  call("create_sprint", { project, sprint_name, goal, start_date, end_date });

export const updateSprint = (sprint, fields) =>
  call("update_sprint", { sprint, ...fields });

export const startSprint = (sprint) => call("start_sprint", { sprint });

export const completeSprint = (sprint, move_incomplete_to) =>
  call("complete_sprint", { sprint, move_incomplete_to });

export const deleteSprint = (sprint) => call("delete_sprint", { sprint });

export const getBacklog = (project) => call("get_backlog", { project });

export const moveTaskToSprint = (task, sprint) =>
  call("move_task_to_sprint", { issue: task, sprint });

// ─── DASHBOARD ───────────────────────────────────────────────────────────────

export const getDashboard = () => call("get_dashboard");

// ─── MEMBERS ─────────────────────────────────────────────────────────────────

export const getMembers = (project) => call("get_members", { project });

// ─── INVITATIONS ─────────────────────────────────────────────────────────────
const INV = "batch_projects.api.invitations";

export const inviteMember = (project, email, role = "Member") =>
  callPath(`${INV}.invite_member`, { project, email, role });

export const listInvitations = (project, includeResolved = 0) =>
  callPath(`${INV}.list_invitations`, { project, include_resolved: includeResolved });

export const revokeInvitation = (name) =>
  callPath(`${INV}.revoke_invitation`, { name });

export const resendInvitation = (name) =>
  callPath(`${INV}.resend_invitation`, { name });

export const getInvitation = (token) =>
  callPath(`${INV}.get_invitation`, { token });

export const acceptInvitation = (token) =>
  callPath(`${INV}.accept_invitation`, { token });

export const signupAndAccept = (token, password, fullName) =>
  callPath(`${INV}.signup_and_accept`, { token, password, full_name: fullName });

// ─── SHARE LINKS (view-only public links — premium, Team tier+) ────────────────
const SHARE = "batch_projects.api.sharing";

export const createShareLink = (params) =>
  callPath(`${SHARE}.create_share_link`, params);

export const listShareLinks = (project, scope) =>
  callPath(`${SHARE}.list_share_links`, { project, scope });

export const revokeShareLink = (name) =>
  callPath(`${SHARE}.revoke_share_link`, { name });

// Public read — token is the credential (no auth required).
export const getShared = (token) =>
  callPath(`${SHARE}.get_shared`, { token });

// Public write — the one narrow exception to "share links are read-only".
// Requires the link's own access_level to be "comment" (enforced server-side).
export const addGuestComment = (token, comment_text, guest_name) =>
  callPath(`${SHARE}.add_guest_comment`, { token, comment_text, guest_name });

export const updateSharedTask = (token, task, fields) =>
  callPath(`${SHARE}.update_shared_task`, { token, task, fields });

// ─── TASK LINKS ──────────────────────────────────────────────────────────────

export const addTaskLink = (task, linked_task, link_type, dep_type = "FS", lag_days = 0) =>
  call("add_task_link", { issue: task, linked_task, link_type, dep_type, lag_days });

export const removeTaskLink = (task, linked_task, link_type) =>
  call("remove_task_link", { issue: task, linked_task, link_type });

// ─── ERP REFERENCES ──────────────────────────────────────────────────────────

export const getAllowedDoctypes = (project) => call("get_allowed_doctypes", { project });

export const searchErpDocuments = (doctype, query, project) =>
  call("search_erp_documents", { doctype, query, project });

export const getErpDocumentLabel = (doctype, name) =>
  call("get_erp_document_label", { doctype, name });

// Read-scoped field metadata (condition builders — trigger.doc_event) —
// wider doctype whitelist than getErpDoctypeFields above, which is scoped to
// the "Update ERPNext Document" WRITE boundary. Same row shape either way.
export const getErpDoctypeFieldsReadonly = (doctype) =>
  call("get_erp_doctype_fields_readonly", { doctype });

export const addReference = (task, ref_doctype, ref_name, two_way = 0) =>
  call("add_reference", { issue: task, ref_doctype, ref_name, two_way });

export const removeReference = (task, reference_name, ref_doctype = null, ref_name = null) =>
  call("remove_reference", { issue: task, reference_name: reference_name || null, ref_doctype, ref_name });

// project is optional — passing it lets the backend strip Currency-typed
// fields for a caller without view_money on that project.
export const getMirrorSchema = (project) => call("get_mirror_schema", { project });

export const getMirrorValues = (doctype, names, project) =>
  call("get_mirror_values", { doctype, names: JSON.stringify(names), project });

// ─── ATTACHMENTS ─────────────────────────────────────────────────────────────

export const deleteAttachment = (file_name) =>
  call("delete_attachment", { file_name });

/**
 * Upload a file attachment to a BP Task via Frappe's native upload endpoint.
 * Returns the File doc.
 */
export async function uploadAttachment(
  file,
  doctype,
  docname,
  isPrivate = false,
) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("attached_to_doctype", doctype);
  formData.append("attached_to_name", docname);
  formData.append("is_private", isPrivate ? "1" : "0");
  formData.append("doctype", doctype);
  formData.append("docname", docname);

  const res = await fetch("/api/method/upload_file", {
    method: "POST",
    headers: { "X-Frappe-CSRF-Token": window.csrf_token || "" },
    body: formData,
  });
  if (!res.ok) throw new Error("Upload failed");
  const data = await res.json();
  if (data.exc) throw new Error(data.exc);
  return data.message;
}

// ─── MY TASKS ────────────────────────────────────────────────────────────────

export const getMyTasks = (params = {}) =>
  call("get_my_tasks", {
    status_filter: params.statusFilter || "open",
    project:       params.project   || null,
    priority:      params.priority  || null,
    group_by:      params.groupBy   || "project",
    sort_by:       params.sortBy    || "due_date",
    sort_order:    params.sortOrder || "asc",
    limit:         params.limit     || 200,
    offset:        params.offset    || 0,
  });

// ─── NOTIFICATIONS ───────────────────────────────────────────────────────────

export const getNotifications = (limit = 30, offset = 0, unread_only = false, on_date = null) =>
  call("get_notifications", { limit, offset, unread_only: unread_only ? 1 : 0, on_date });

export const markNotificationRead = (notification) =>
  call("mark_notification_read", { notification });

export const markNotificationUnread = (notification) =>
  call("mark_notification_unread", { notification });

export const markAllNotificationsRead = () =>
  call("mark_all_notifications_read", {});

export const getNotificationCount = () =>
  call("get_notification_count", {});

export const getViewPrefs = (project, view = "list") =>
  call("get_view_prefs", { project, view });
export const saveViewPrefs = (project, prefs, view = "list") =>
  call("save_view_prefs", { project, prefs, view });

export const getNotificationPreferences = () =>
  call("get_notification_preferences", {});
export const updateNotificationPreferences = (preferences) =>
  call("update_notification_preferences", { preferences });
export const getMutedItems = () => call("get_muted_items", {});
export const setMute = ({ task = null, project = null, muted = 1 } = {}) =>
  call("set_mute", { task, project, muted });

export const watchTask = (task) => call("watch_task", { task });
export const unwatchTask = (task) => call("unwatch_task", { task });
export const getTaskWatchers = (task) => call("get_task_watchers", { task });

// ─── PROJECT GENERAL SETTINGS ────────────────────────────────────────────────

export const updateProjectGeneral = (project, fields) =>
  call("update_project_general", { project, ...fields });

// ─── TEAMS ───────────────────────────────────────────────────────────────────

export const getTeams = () => call("get_teams");

export const getTeam = (team) => call("get_team", { team });

export const createTeam = (params) => call("create_team", params);

export const updateTeam = (team, fields) =>
  call("update_team", { team, ...fields });

export const updateTeamMembers = (team, members) =>
  call("update_team_members", { team, members: JSON.stringify(members) });

export const assignProjectToTeam = (project, team) =>
  call("assign_project_to_team", { project, team });

export const archiveTeam = (team) => call("archive_team", { team });


export const getErpNextDepartments = () => call("get_erpnext_departments");

export const getTeamVelocity = (team, last_n_sprints = 5) =>
  call("get_team_velocity", { team, last_n_sprints });

export const getTeamDashboard = (team) =>
  call("get_team_dashboard", { team });

export const updateTeamLinks = (team, links) =>
  call("update_team_links", { team, links: JSON.stringify(links) });

// ─── WORKLOAD ─────────────────────────────────────────────────────────────────

/** Forward-looking workload: allocated hours per member per week.
 *  weeks: 2 | 4 | 6 — defaults to 4
 *  team: BP Team name (optional)
 */
export const getWorkload = (weeks = 4, team = null) =>
  call("get_workload", { weeks, team });

// ─── UTILIZATION ─────────────────────────────────────────────────────────────

/** Backward-looking utilization from ERPNext Timesheets.
 *  period: 'last_7_days' | 'last_30_days' | 'last_90_days' | 'month:YYYY-MM'
 *  team: BP Team name (optional)
 */
export const getUtilization = (period = "last_30_days", team = null) =>
  call("get_utilization", { period, team });

// ─── PEOPLE ───────────────────────────────────────────────────────────────────

/** All project members with designation, active projects, this-week allocation,
 *  and last-30-day utilization.
 */
export const getPeople = () => call("get_people");

// ─── PROJECT FILES ────────────────────────────────────────────────────────────

/** All files attached to tasks in a project, with task context. */
export const getProjectFiles = (project) =>
  call("get_project_files", { project });

// ─── TIMESHEETS ───────────────────────────────────────────────────────────────

export const getTimesheets = (period = "last_30_days", team = null) =>
  call("get_timesheets", { period, team });

// ─── MARGIN REPORT ────────────────────────────────────────────────────────────

export const getMarginReport = (period = "last_30_days") =>
  call("get_margin_report", { period });

// Per-project delivery analytics: status breakdown, throughput, cycle time, velocity.
// Pass from_date/to_date (ISO strings) to override the period enum with a custom range.
export const getReports = (project, period = "last_30_days", fromDate = null, toDate = null) =>
  call("get_reports", { project, period, from_date: fromDate || undefined, to_date: toDate || undefined });

// Sprint completion analysis: committed vs added vs completed vs spillover.
export const getSprintReport = (project, sprintName) =>
  call("get_sprint_report", { project, sprint_name: sprintName });

// Cross-project delivery rollup for the Portfolio view.
export const getPortfolio = () => call("get_portfolio");

// Dashboard widget engine: group a metric by a dimension, scoped to a project or all.
export const getWidgetData = (config) => call("get_widget_data", { config: JSON.stringify(config) });

// BQL GROUP BY with client-supplied WHERE filters (respects sprint/status/priority conditions).
export const queryBqlGroupBy = (scope, filters, groupBy, metric = "count") =>
  call("query_bql_group_by", {
    scope: scope || "all",
    filters_json: JSON.stringify(filters || {}),
    group_by: groupBy,
    metric,
  });

// ─── WORKSPACE SUMMARY ────────────────────────────────────────────────────────

export const getWorkspaceSummary = () => call("get_workspace_summary");

// ─── MILESTONES ───────────────────────────────────────────────────────────────

export const getMilestones = (project = null) =>
  call("get_milestones", project ? { project } : {});

export const createMilestone = (project, title, due_date = null, description = null) =>
  call("create_milestone", { project, title, due_date, description });

export const updateMilestone = (name, fields) =>
  call("update_milestone", { name, fields });

export const deleteMilestone = (name) =>
  call("delete_milestone", { name });

// Must call through the real module path, not `call()` (the
// batch_projects.api.board namespace) — board.py only re-exports a
// thin alias to erp_link.generate_milestone_invoice. bp-gateway's MethodGate
// (the Go-side tier enforcement — see internal/license/license.go's
// urlToFeature table) matches on the REAL module path
// (batch_projects.api.erp_link.generate_milestone_invoice, gated
// billing_writeback/Business), not board's alias — so calling it through
// board silently skipped the Go-layer gate entirely (Python's own
// require_feature still caught it, but that's the patchable layer, not the
// enforcement boundary this app's own docs describe). Calling the real
// module path directly closes that gap.
export const generateMilestoneInvoice = (milestone) =>
  callErpLink("generate_milestone_invoice", { milestone });

// ─── RISKS ────────────────────────────────────────────────────────────────────

export const getRisks = (project = null) =>
  call("get_risks", project ? { project } : {});

export const createRisk = (project, title, severity = "medium", owner_user = null, description = null) =>
  call("create_risk", { project, title, severity, owner_user, description });

export const updateRisk = (name, fields) =>
  call("update_risk", { name, fields });

export const deleteRisk = (name) =>
  call("delete_risk", { name });

// ─── TEAM CAPACITY HEATMAP ────────────────────────────────────────────────────

export const getTeamCapacityHeatmap = (team = null) =>
  call("get_team_capacity_heatmap", team ? { team } : {});

// ─── TRIAGE / INBOX ───────────────────────────────────────────────────────────

export const getTriageQueue = (project) =>
  call("get_triage_queue", project ? { project } : {});

export const markTriaged = (task) =>
  call("mark_triaged", { task });

// ─── APPROVALS ────────────────────────────────────────────────────────────────

export const requestApproval = (issue, approver) =>
  call("request_approval", { issue, approver });

export const approveTask = (issue) =>
  call("approve_task", { issue });

export const rejectTask = (issue, reason) =>
  call("reject_task", { issue, reason });

// ─── SLA ──────────────────────────────────────────────────────────────────────

export const getSlaPolicies = (project) =>
  call("get_sla_policies", { project });

export const createSlaPolicy = (params) =>
  call("create_sla_policy", params);

export const getSlaBreaches = (params) =>
  call("get_sla_breaches", params);

// ─── INTAKE FORMS ─────────────────────────────────────────────────────────────
// Must call through the real module path, not `call()` (board.py's
// namespace) — that only re-exports thin aliases to api.forms.*, and the real
// module bp-gateway's MethodGate table actually gates on (`intake_forms`,
// Team tier). Calling board's alias meant that gate never matched, same
// class of bug as generateMilestoneInvoice above. Calling the real module
// path directly closes it; board.py's aliases have been removed.

const FORMS_BASE = "batch_projects.api.forms";
const callForms = (method, params = {}) => callPath(`${FORMS_BASE}.${method}`, params);

export const listIntakeForms = (project) =>
  callForms("list_intake_forms", { project });

export const getIntakeFormDetail = (form) =>
  callForms("get_intake_form_detail", { form });

export const createIntakeForm = (project, formTitle, fieldsJson, taskType, defaultStatus) =>
  callForms("create_intake_form", { project, form_title: formTitle, fields_json: fieldsJson, task_type: taskType, default_status: defaultStatus });

export const updateIntakeForm = (form, fields) =>
  callForms("update_intake_form", { form, fields });

export const deleteIntakeForm = (form) =>
  callForms("delete_intake_form", { form });

export const getPublicForm = (form) =>
  callForms("get_public_form", { form });

export const submitIntakeForm = (form, values) =>
  callForms("submit_intake_form", { form, values });

// ─── CHECKLIST ────────────────────────────────────────────────────────────────

export const getChecklist = (task) =>
  call("get_checklist", { task });

export const addChecklistItem = (task, text) =>
  call("add_checklist_item", { task, text });

export const updateChecklistItem = (task, itemId, text) =>
  call("update_checklist_item", { task, item_id: itemId, text });

export const toggleChecklistItem = (task, itemId) =>
  call("toggle_checklist_item", { task, item_id: itemId });

export const removeChecklistItem = (task, itemId) =>
  call("remove_checklist_item", { task, item_id: itemId });

// ─── WBS / PROJECT HIERARCHY ──────────────────────────────────────────────────

export const getProjectTree = () =>
  call("get_project_tree");

export const setParentProject = (project, parent_project) =>
  call("set_parent_project", { project, parent_project });
