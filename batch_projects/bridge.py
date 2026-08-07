"""Frappe → bp-gateway client (the scheduler/automation side-car).

The Go agent owns durable timers (recurring automations, SLA timers, deferred
actions) because Frappe's synchronous workers can't. When a user saves a
scheduled rule we *register* a job with the agent; when the rule's time comes
the agent calls back into ``batch_projects.api.automation.run_scheduled_event``
and Frappe does the transactional work. This module is only the outbound
registration half.

Config (site_config.json / env, never hard-coded):
    bp_bridge_url               e.g. "http://127.0.0.1:8001" — used here AND
                                 injected into every page as
                                 window.__BP_BRIDGE_URL__ for the browser's
                                 own /v1/* calls (see api/gateway.py).
    bp_bridge_internal_url      optional override, THIS module only. Exists
                                 because a browser and this backend process
                                 don't always reach the gateway at the same
                                 address — e.g. a docker-compose dev topology
                                 where the gateway sits behind a Caddy
                                 container only reachable from the host at
                                 127.0.0.1:8080, but that address is the
                                 *backend container's own loopback* from in
                                 here (confirmed live 2026-08-05:
                                 publish_event()/publish_realtime_event() were
                                 silently failing — connection refused — for
                                 exactly this reason, even though the same
                                 URL works fine for the browser). Falls back
                                 to bp_bridge_url when unset, so every normal
                                 single-address deployment (self-hosted
                                 install.sh, Frappe Cloud) is unaffected.
    bp_scheduler_ingest_token   shared token == gateway scheduler.ingest_token

If either is unset the functions are no-ops (dev without a bridge still saves
rules cleanly) — registration just won't happen, logged once at debug.
"""

import frappe
import json
import requests

_TIMEOUT = 5  # seconds — registration is a fast control-plane call
_EVENT_TIMEOUT = 2  # seconds — event publish is on the mutation hot-path


def _config():
    url = (
        frappe.conf.get("bp_bridge_internal_url")
        or frappe.conf.get("bp_bridge_url")
        or ""
    ).rstrip("/")
    token = frappe.conf.get("bp_scheduler_ingest_token") or ""
    return url, token


def is_configured() -> bool:
    url, token = _config()
    return bool(url and token)


def register_scheduled_job(
    *,
    kind: str,
    event: str,
    payload: dict,
    run_at: int | None = None,
    delay_seconds: int | None = None,
    interval_seconds: int = 0,
    max_retry: int = 0,
) -> str | None:
    """Register (or re-register) a job with the agent. Returns the bridge job id.

    Never raises into the caller's save — a bridge that is down must not block
    editing a rule. On failure it logs and returns None; the caller can decide
    whether to warn the user.
    """
    url, token = _config()
    if not (url and token):
        frappe.logger("bp.bridge").debug("bridge not configured — skipping job register")
        return None

    body: dict = {
        "kind": kind,
        "event": event,
        "payload": payload,
        "interval_seconds": interval_seconds,
    }
    if run_at is not None:
        body["run_at"] = run_at
    if delay_seconds is not None:
        body["delay_seconds"] = delay_seconds
    if max_retry:
        body["max_retry"] = max_retry

    try:
        resp = requests.post(
            f"{url}/v1/scheduler/jobs",
            data=json.dumps(body),
            headers={
                "Content-Type": "application/json",
                "X-BP-Service-Token": token,
            },
            timeout=_TIMEOUT,
        )
    except requests.RequestException as e:
        frappe.log_error(f"bridge register failed: {e}", "bp.bridge")
        return None

    if resp.status_code >= 300:
        frappe.log_error(
            f"bridge register {resp.status_code}: {resp.text[:300]}", "bp.bridge"
        )
        return None
    try:
        return resp.json().get("id")
    except ValueError:
        return None


def publish_event(payload: dict) -> bool:
    """Publish an automation event to the gateway's ingest endpoint.

    Fire-and-forget: this runs on the mutation hot-path (called from
    events.emit()), so a down or unconfigured bridge must never slow down or
    fail the caller's save. Any failure is logged, not raised.
    """
    url, token = _config()
    if not (url and token):
        frappe.logger("bp.bridge").debug("bridge not configured — skipping event publish")
        return False

    try:
        resp = requests.post(
            f"{url}/v1/events",
            data=json.dumps(payload),
            headers={
                "Content-Type": "application/json",
                "X-BP-Service-Token": token,
            },
            timeout=_EVENT_TIMEOUT,
        )
    except requests.RequestException as e:
        frappe.logger("bp.bridge").warning(f"event publish failed: {e}")
        return False

    if resp.status_code >= 300:
        frappe.logger("bp.bridge").warning(
            f"event publish {resp.status_code}: {resp.text[:200]}"
        )
        return False
    return True


def publish_realtime_event(event: str, project: str, payload: dict) -> bool:
    """Publish a live-update event to the gateway's browser realtime plane
    (POST /v1/realtime/publish -> internal/realtime.Handler.Publish), which
    fans it out over SSE to every connected client whose visible-project set
    includes `project` (see gateway's realtime.go membership.sees).

    Was frappe.publish_realtime() — Frappe's own native socket.io/pub-sub
    mechanism, which this gateway's Subscribe() never consumed: two
    completely disconnected systems. Confirmed live (2026-08-05): a
    publish_realtime() broadcast never reached a connected SSE client with a
    valid session token, correct CORS, and a genuinely open stream — every
    realtime-dependent feature in the app (board live-refresh, drawing
    collaboration, notification badge) was silently non-functional in any
    topology where the gateway is a separate origin from Frappe. This is the
    fix: publish through the gateway's own plane instead.

    Deliberately NOT /v1/events (automation ingest) despite both ultimately
    feeding the same Redis stream — that endpoint also LPushes to the
    automation queue and gates on the "automations" feature; see
    realtime.go's Publish doc comment for why reusing it would be wrong for
    a plane that can fire many times a second under active use (drawing
    collaboration, live board updates).

    Fire-and-forget, same posture as publish_event: a down/unconfigured
    bridge must never slow down or fail the caller's save."""
    url, token = _config()
    if not (url and token):
        frappe.logger("bp.bridge").debug("bridge not configured — skipping realtime publish")
        return False

    body = {"event": event, "project": project or "", "payload": payload}
    try:
        resp = requests.post(
            f"{url}/v1/realtime/publish",
            data=json.dumps(body),
            headers={
                "Content-Type": "application/json",
                "X-BP-Service-Token": token,
            },
            timeout=_EVENT_TIMEOUT,
        )
    except requests.RequestException as e:
        frappe.logger("bp.bridge").warning(f"realtime publish failed: {e}")
        return False

    if resp.status_code >= 300:
        frappe.logger("bp.bridge").warning(
            f"realtime publish {resp.status_code}: {resp.text[:200]}"
        )
        return False
    return True


def publish_rebac_event(payload: dict) -> bool:
    """Publish a relationship-change edge (task assigned/unassigned, project
    role changed) to the gateway's ReBAC Redis sync endpoint.

    Deliberately a SEPARATE endpoint from publish_event()'s /v1/events —
    that one feeds automation.Engine.Ingest, which license-gates on the
    "automations" paid feature. Permission-sync correctness must never be
    tied to a paid tier, so this rides its own path, same bridge/token.

    Fire-and-forget on the mutation hot-path, same posture as publish_event:
    a down or unconfigured bridge must never slow down or fail the caller's
    save. The gateway is what enforces fail-closed on a stale/unreachable
    cache — this call failing silently is not itself a security hole."""
    url, token = _config()
    if not (url and token):
        frappe.logger("bp.bridge").debug("bridge not configured — skipping rebac sync")
        return False

    try:
        resp = requests.post(
            f"{url}/v1/rebac/sync",
            data=json.dumps(payload),
            headers={
                "Content-Type": "application/json",
                "X-BP-Service-Token": token,
            },
            timeout=_EVENT_TIMEOUT,
        )
    except requests.RequestException as e:
        frappe.logger("bp.bridge").warning(f"rebac sync publish failed: {e}")
        return False

    if resp.status_code >= 300:
        frappe.logger("bp.bridge").warning(
            f"rebac sync publish {resp.status_code}: {resp.text[:200]}"
        )
        return False
    return True


def cancel_scheduled_job(job_id: str) -> bool:
    """Cancel a previously registered job. Best-effort; never raises."""
    if not job_id:
        return False
    url, token = _config()
    if not (url and token):
        return False
    try:
        resp = requests.delete(
            f"{url}/v1/scheduler/jobs/{job_id}",
            headers={"X-BP-Service-Token": token},
            timeout=_TIMEOUT,
        )
        return resp.status_code < 300
    except requests.RequestException as e:
        frappe.log_error(f"bridge cancel failed: {e}", "bp.bridge")
        return False
