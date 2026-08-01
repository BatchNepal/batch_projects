// Single, always-on realtime connection to bp-gateway's browser plane
// (GET /v1/realtime/subscribe, internal/realtime on the Go side). Replaces
// the old per-project socket.io-client connection in stores/project.js and
// Sidebar.vue's separate window.frappe.realtime listener — both talked
// straight to Frappe's own socket.io, bypassing the gateway entirely.
//
// Connected once at App.vue mount (not reopened per project switch); any
// number of listeners can subscribe via onRealtimeEvent(handler) and get
// every bp_event this connection receives — project.js still filters by
// currentProject itself (_applyRealtimeEvent already does this), so this
// module doesn't need to know about "current project" at all.
//
// Auth: native EventSource can't set an Authorization header, so the
// gateway-issued JWT (api.js's getGatewayJWT(), set by bootstrapBridge())
// goes in a ?token= query param — a route added specifically for this on
// the gateway side (session.go resolve()), scoped to this one endpoint.
import { bridgeBase, getGatewayJWT } from "./api";

let _es = null;
let _reconnectTimer = null;
let _reconnectDelay = 1000;
const MAX_RECONNECT_DELAY = 30000;
// Once a connection has failed several times in a row *immediately* (see
// _connectStartedAt below), treat it as a standing gate rather than a
// network blip — e.g. bp-gateway's 402 when the tenant's plan doesn't
// include the "realtime" feature (Team+ only, internal/realtime.go). That
// gate doesn't lift on its own, so retrying every ~30s forever just spams
// the console for the lifetime of the tab. Back off to a slow poll instead.
const HARD_GATE_RECONNECT_DELAY = 5 * 60 * 1000;
const HARD_GATE_THRESHOLD = 3;
let _consecutiveInstantFails = 0;
let _connectStartedAt = 0;
const _handlers = new Set();

/** Register a handler for every bp_event received. Returns an unsubscribe fn. */
export function onRealtimeEvent(handler) {
  _handlers.add(handler);
  return () => _handlers.delete(handler);
}

function _dispatch(payload) {
  for (const handler of _handlers) {
    try {
      handler(payload);
    } catch (e) {
      console.error("[BP] realtime handler error:", e);
    }
  }
}

/** Open the connection (no-op if already open/connecting). Call once, after
 *  bootstrapBridge() has resolved so a gateway JWT exists. */
export function connectRealtime() {
  if (_es) return;
  const token = getGatewayJWT();
  if (!token) {
    console.warn("[BP] realtime: no gateway session yet, not connecting");
    return;
  }

  const url = `${bridgeBase()}/v1/realtime/subscribe?token=${encodeURIComponent(token)}`;
  const suspectHardGate = _consecutiveInstantFails >= HARD_GATE_THRESHOLD;
  if (!suspectHardGate) {
    console.log("[BP] realtime connecting:", url.replace(/token=[^&]+/, "token=***"));
  }

  const es = new EventSource(url);
  _es = es;
  _connectStartedAt = Date.now();

  es.addEventListener("bp_event", (e) => {
    try {
      _dispatch(JSON.parse(e.data));
    } catch (err) {
      console.warn("[BP] realtime: unparseable event", err);
    }
  });

  es.onopen = () => {
    console.log("[BP] realtime connected");
    _reconnectDelay = 1000; // reset backoff on a clean connect
    _consecutiveInstantFails = 0;
  };

  es.onerror = () => {
    // A dropped connection auto-retries via the browser's native EventSource
    // reconnect. A hard close (readyState CLOSED — e.g. a 401/402 from an
    // expired/ungated token, which the browser treats as fatal and does NOT
    // auto-retry) needs a manual reconnect with backoff, re-reading the
    // token in case it rotated since we last connected.
    if (es.readyState === EventSource.CLOSED) {
      // EventSource never exposes the failed response's status to JS, so
      // fall back to timing: a rejection like a 402 entitlement gate closes
      // near-instantly, while a genuine network drop closes after the
      // connection has been live for a while.
      const failedFast = Date.now() - _connectStartedAt < 2000;
      teardownRealtime();
      if (failedFast) {
        _consecutiveInstantFails++;
      } else {
        _consecutiveInstantFails = 0;
        _reconnectDelay = 1000;
      }
      _reconnectDelay = _consecutiveInstantFails >= HARD_GATE_THRESHOLD
        ? HARD_GATE_RECONNECT_DELAY
        : Math.min(_reconnectDelay * 2, MAX_RECONNECT_DELAY);
      _reconnectTimer = setTimeout(connectRealtime, _reconnectDelay);
    }
  };
}

export function teardownRealtime() {
  if (_reconnectTimer) {
    clearTimeout(_reconnectTimer);
    _reconnectTimer = null;
  }
  if (_es) {
    try {
      _es.close();
    } catch (e) {
      /* already closed */
    }
    _es = null;
  }
}

export function isRealtimeConnected() {
  return _es?.readyState === EventSource.OPEN;
}
