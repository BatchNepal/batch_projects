"""
batch_projects/api/sprint_analytics.py
──────────────────────────────────────
Whitelisted endpoints for sprint/agile analytics.

Every endpoint:
  1. Verifies the request came through bp-gateway (gateway_guard)
  2. Checks project-level permissions via access.require()
  3. Reads from Redis cache when available (cache.py)
  4. Computes fresh analytics on cache miss from live, non-trashed tasks
  5. Writes to cache with TTL
  6. Returns clean JSON
"""

import frappe

from batch_projects.api.board import _check_permission, _require_system_user
from batch_projects import analytics_live as analytics
from batch_projects.cache import get as cache_get, set as cache_set

ANALYTICS_TTL = 120


def _cache_key(kind: str, entity: str) -> str:
    return f"bp:v1:analytics:{kind}:{entity}"


@frappe.whitelist()
def get_sprint_health(sprint):
    """Full sprint analytics: burndown + burnup + velocity + cycle time + status counts."""
    from batch_projects.gateway_guard import verify_gateway_request
    verify_gateway_request()

    sprint_doc = frappe.get_doc("BP Sprint", sprint)
    project = sprint_doc.project

    if project:
        _check_permission(project, "BP Viewer")
    else:
        _require_system_user()

    cache_key = _cache_key("sprint_health", sprint)
    cached = cache_get("analytics", cache_key)
    if cached is not None:
        return cached

    data = analytics.compute_sprint_health(sprint)
    cache_set("analytics", cache_key, data)
    return data


def invalidate_sprint_cache(sprint: str, project: str = None):
    """Drop all analytics cache for a sprint after task/sprint mutations."""
    try:
        frappe.cache().delete_value(_cache_key("sprint_health", sprint))
    except Exception:
        pass
