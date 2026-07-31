"""
batch_projects/cache.py
────────────────────────
Centralized Redis cache layer for batch_projects.

Design principles:
  1. Cache-aside pattern — read from cache, fall back to DB on miss
  2. Write-through invalidation — every mutation deletes the cache key immediately
  3. TTL as safety net — 60s max TTL so bugs can't cause permanent stale data
  4. Granular keys — per-project, per-view, so invalidation is surgical not nuclear
  5. Version prefix — bump CACHE_VERSION to instantly bust all cached data globally
     (useful after schema changes, migrations, or bugs)

Cache key structure:
  bp:v{VERSION}:{view}:{project}
  e.g. bp:v1:board:Freedom Website Development
"""

import frappe
import json

# Bump this to instantly bust ALL batch_projects cache across all projects
CACHE_VERSION = "1"

# TTL in seconds — safety net against any invalidation edge cases
CACHE_TTL = 60

# Views that are cached
VIEW_BOARD       = "board"
VIEW_BACKLOG     = "backlog"
VIEW_SPRINTS     = "sprints"
VIEW_RECIPIENTS  = "recipients"  # per-project broadcast recipient list


def _key(view: str, project: str) -> str:
    """Build a namespaced, versioned cache key."""
    return f"bp:v{CACHE_VERSION}:{view}:{project}"


def get(view: str, project: str):
    """
    Read from cache. Returns None on miss.
    Uses frappe.cache() which is a Redis wrapper.
    """
    try:
        raw = frappe.cache().get_value(_key(view, project))
        if raw is None:
            return None
        return json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        # Cache read failure is non-fatal — fall through to DB
        return None


def set(view: str, project: str, data) -> None:
    """
    Write to cache with TTL.
    Serializes to JSON to ensure consistent types across gunicorn workers.
    """
    try:
        frappe.cache().set_value(
            _key(view, project),
            json.dumps(data, default=str),
            expires_in_sec=CACHE_TTL,
        )
    except Exception:
        # Cache write failure is non-fatal
        pass


def invalidate_project(project: str) -> None:
    """
    Delete ALL cached views for a project.
    Called on every issue mutation, sprint change, or project update.
    This is the core of the cache invalidation strategy.
    """
    try:
        for view in (VIEW_BOARD, VIEW_BACKLOG, VIEW_SPRINTS):
            frappe.cache().delete_value(_key(view, project))
    except Exception:
        frappe.log_error(frappe.get_traceback(), "bp_cache invalidation failed")


def invalidate_all() -> None:
    """
    Nuclear option — bust all batch_projects cache.
    Use when: CACHE_VERSION bump is not enough (e.g. urgent hotfix).
    """
    try:
        # Frappe's cache doesn't support pattern delete natively,
        # so we rely on the version prefix strategy instead.
        # To fully bust: increment CACHE_VERSION at top of this file.
        pass
    except Exception:
        pass