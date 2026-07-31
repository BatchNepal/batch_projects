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
  console.log("[BP] realtime connecting:", url.replace(/token=[^&]+/, "token=***"));

  const es = new EventSource(url);
  _es = es;

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
  };

  es.onerror = () => {
    // A dropped connection auto-retries via the browser's native EventSource
    // reconnect. A hard close (readyState CLOSED — e.g. a 401/402 from an
    // expired/ungated token, which the browser treats as fatal and does NOT
    // auto-retry) needs a manual reconnect with backoff, re-reading the
    // token in case it rotated since we last connected.
    if (es.readyState === EventSource.CLOSED) {
      teardownRealtime();
      _reconnectTimer = setTimeout(connectRealtime, _reconnectDelay);
      _reconnectDelay = Math.min(_reconnectDelay * 2, MAX_RECONNECT_DELAY);
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
