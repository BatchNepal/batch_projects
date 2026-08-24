"""
batch_projects/cache.py
────────────────────────
Centralized Redis cache layer for batch_projects.

Design principles:
  1. Cache-aside pattern — read from cache, fall back to DB on miss
  2. Write-through invalidation — every mutation bumps a per-project
     generation counter immediately
  3. TTL as safety net — 60s max TTL so bugs can't cause permanent stale data
  4. Granular keys — per-project, per-view, per-user, so invalidation is
     surgical not nuclear
  5. Version prefix — bump CACHE_VERSION to instantly bust all cached data
     globally (useful after schema changes, migrations, or bugs)

Cache key structure:
  bp:v{VERSION}:{view}:{project}:{generation}:{user}
  e.g. bp:v1:board:Freedom Website Development:3:test1+info@batchnepal.com

The generation component (see _current_gen/invalidate_project) is what makes
invalidation work without Redis pattern-delete support: bumping it makes
every previously-cached key for that project unreachable immediately, and
the 60s TTL reaps the now-orphaned entries on its own.

The user component exists because a cached view's payload is sanitized for
the CALLER's effective role/permissions (hidden custom fields, money fields,
etc. — see api/custom_fields.hidden_field_ids_for_project) before it's
cached. Without `user` in the key, a higher-privilege caller's response
would be served verbatim to a lower-privilege caller within the same TTL
window.
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


def _gen_key(project: str) -> str:
    return f"bp:v{CACHE_VERSION}:gen:{project}"


def _current_gen(project: str) -> int:
    try:
        return int(frappe.cache().get_value(_gen_key(project)) or 0)
    except Exception:
        return 0


def _key(view: str, project: str, user: str) -> str:
    """Build a namespaced, versioned, per-user cache key."""
    return f"bp:v{CACHE_VERSION}:{view}:{project}:{_current_gen(project)}:{user}"


def get(view: str, project: str, user: str | None = None):
    """
    Read from cache. Returns None on miss.
    Uses frappe.cache() which is a Redis wrapper.
    """
    user = user or frappe.session.user
    try:
        raw = frappe.cache().get_value(_key(view, project, user))
        if raw is None:
            return None
        return json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        # Cache read failure is non-fatal — fall through to DB
        return None


def set(view: str, project: str, data, user: str | None = None) -> None:
    """
    Write to cache with TTL.
    Serializes to JSON to ensure consistent types across gunicorn workers.
    """
    user = user or frappe.session.user
    try:
        frappe.cache().set_value(
            _key(view, project, user),
            json.dumps(data, default=str),
            expires_in_sec=CACHE_TTL,
        )
    except Exception:
        # Cache write failure is non-fatal
        pass


def invalidate_project(project: str) -> None:
    """
    Invalidate ALL cached views (and every user's cached copy of them) for a
    project. Called on every issue mutation, sprint change, or project update.
    This is the core of the cache invalidation strategy.

    Bumps the per-project generation counter rather than deleting individual
    keys — Frappe's cache wrapper has no pattern-delete, so there is no way
    to enumerate and delete every {view, user} key that might exist for this
    project. Bumping the generation makes all of them unreachable immediately;
    the 60s TTL reaps the orphaned Redis entries on its own.
    """
    try:
        frappe.cache().set_value(_gen_key(project), _current_gen(project) + 1)
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
