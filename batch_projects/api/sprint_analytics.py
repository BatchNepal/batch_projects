"""
batch_projects/api/sprint_analytics.py
──────────────────────────────────────
Whitelisted endpoints for sprint/agile analytics.

Every endpoint:
  1. Verifies the request came through bp-gateway (gateway_guard)
  2. Checks project-level permissions via access.require()
  3. Reads from Redis cache when available (cache.py)
  4. Computes fresh analytics on cache miss (analytics.py)
  5. Writes to cache with TTL
  6. Returns clean JSON

Cache strategy: analytics data has a longer TTL than board data (120s vs 60s)
because burndown/velocity/cycle-time don't change as frequently as task drags
and reorders. The cache is invalidated when tasks in the sprint are mutated
(via the existing events.emit → invalidate_project pipeline).
"""

import frappe
import json

from batch_projects.api.board import _check_permission, _require_system_user
from batch_projects import analytics
from batch_projects.cache import get as cache_get, set as cache_set, VIEW_SPRINTS

ANALYTICS_TTL = 120  # seconds — longer than board TTL, analytics change slower


def _cache_key(kind: str, entity: str) -> str:
    return f"bp:v1:analytics:{kind}:{entity}"


# ─────────────────────────────────────────────────────────────────────────────
# SPRINT HEALTH — the main entry point for the sprint detail page
# ─────────────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_sprint_health(sprint):
    """Full sprint analytics: burndown + burnup + velocity + cycle time + status counts.

    GET /api/method/batch_projects.api.sprint_analytics.get_sprint_health?sprint=SPRINT-0001
    """
    from batch_projects.gateway_guard import verify_gateway_request
    verify_gateway_request()

    sprint_doc = frappe.get_doc("BP Sprint", sprint)
    project = sprint_doc.project

    if project:
        _check_permission(project, "BP Viewer")
    else:
        _require_system_user()

    # Check cache
    ck = _cache_key("sprint_health", sprint)
    cached = cache_get("analytics", ck)
    if cached is not None:
        return cached

    data = analytics.compute_sprint_health(sprint)
    cache_set("analytics", ck, data)
    return data


# ─────────────────────────────────────────────────────────────────────────────
# CACHE INVALIDATION HOOK — called from events.py when a sprint is mutated
# ─────────────────────────────────────────────────────────────────────────────

def invalidate_sprint_cache(sprint: str, project: str = None):
    """Drop all analytics cache for a sprint. Called by events.emit on sprint
    mutations (task created/updated/deleted/moved within the sprint)."""
    try:
        # Direct Redis key deletion since analytics keys are finer-grained
        # than the standard VIEW_SPRINTS key.
        frappe.cache().delete_value(_cache_key("sprint_health", sprint))
    except Exception:
        pass
