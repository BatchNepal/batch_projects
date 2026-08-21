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
import { bridgeBase, getGatewayJWT, onGatewayJWTChange } from "./api";

let _es = null;
let _reconnectTimer = null;
let _reconnectDelay = 1000;
const MAX_RECONNECT_DELAY = 30000;
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
  // ProjectStore historically used comment.added as its generic "comments for
  // this open task changed; refetch detail" signal. Backend now emits the
  // precise lifecycle names comment.updated/comment.deleted. Preserve those
  // semantics for future listeners while adapting the existing store through
  // one compatibility projection instead of duplicating comment mutation
  // handling across every component.
  const delivered =
    payload?.event === "comment.updated" || payload?.event === "comment.deleted"
      ? { ...payload, comment_event: payload.event, event: "comment.added" }
      : payload;

  for (const handler of _handlers) {
    try {
      handler(delivered);
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
    _reconnectDelay = 1000;
    _consecutiveInstantFails = 0;
  };

  es.onerror = () => {
    if (es.readyState === EventSource.CLOSED) {
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

// api.js's bootstrapBridge() silently re-mints the gateway JWT ~30s before
// it expires (REFRESH_SAFETY_MARGIN_SECS), but that alone doesn't help an
// already-open EventSource — native EventSource has no way to swap its
// query-string token mid-connection, so without this the connection just
// sits on its old, soon-to-expire token until the server eventually cuts
// it off. Confirmed live: every ~5 minutes the connection died (the
// chunked response cut short), the browser retried the same now-expired
// token once or twice (a stray 401 in the console each time), and only
// then did onerror's readyState===CLOSED path reconnect with a fresh one
// — a real gap where any event published during that window was silently
// missed, on top of the console noise. Proactively swapping the moment a
// fresh token lands removes both.
onGatewayJWTChange((token) => {
  if (!_es || _es.readyState !== EventSource.OPEN || !token) return;
  teardownRealtime();
  connectRealtime();
});
