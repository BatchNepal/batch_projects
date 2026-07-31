"""
batch_projects/rank.py
──────────────────────
Manual board ordering without renumbering the whole column on every drag.

Each task carries a `board_rank`: a zero-padded integer string (so MySQL's
lexicographic ordering matches numeric ordering). Inserting between two
neighbours stores the midpoint of their ranks — a single-row write. The wide
STEP (65536) leaves room for thousands of inserts before two neighbours sit
one apart; only then does the column get rebalanced (rare).

This replaces the old behaviour where a drag set `board_order` to a raw index
without shifting siblings, producing colliding orders broken only by creation
date.
"""

import contextlib

import frappe

STEP = 1 << 16          # 65536 — gap between freshly-spaced ranks
WIDTH = 12              # zero-pad width; fits ranks up to ~10^12


def fmt(n: int) -> str:
    return str(int(n)).zfill(WIDTH)


def parse(rank: str | None) -> int:
    try:
        return int(rank) if rank else 0
    except (ValueError, TypeError):
        return 0


def rank_between(prev: str | None, nxt: str | None):
    """Rank string strictly between prev and nxt, or None if there's no room
    (caller should rebalance and retry). Open ends: prev=None -> top,
    nxt=None -> bottom (append)."""
    if prev and nxt:
        a, b = parse(prev), parse(nxt)
        if b - a > 1:
            return fmt((a + b) // 2)
        return None                      # adjacent — needs rebalance
    if prev and not nxt:                 # append after last
        return fmt(parse(prev) + STEP)
    if nxt and not prev:                 # insert before first
        b = parse(nxt)
        if b > 1:
            return fmt(b // 2)
        return None                      # no headroom below — rebalance
    return fmt(STEP)                     # empty column


def end_rank(project: str, status: str) -> str:
    """Rank that appends to the end of a (project, status) column."""
    last = frappe.db.get_value(
        "BP Task", {"project": project, "status": status},
        "board_rank", order_by="board_rank desc")
    return rank_between(last, None) if last else fmt(STEP)


@contextlib.contextmanager
def column_lock(project: str, status: str, timeout: int = 5):
    """Serializes rank_between/rebalance_column calls for one (project,
    status) column across concurrent requests — a MySQL named
    lock (session-scoped advisory lock, not a row lock), so it works
    uniformly even when prev/next are None (column start/end — nothing to
    lock a row on in that case).

    Without this, two concurrent drags into the same gap (two users, or two
    browser tabs) both read the same neighbour ranks, both compute the
    identical midpoint, and both write it — a silent duplicate-rank
    collision, not a crash, so it never surfaced as an error. Found by
    reading the code under a concurrency lens, not from a bug report."""
    name = f"bp_rank:{project}:{status}"
    got = frappe.db.sql("SELECT GET_LOCK(%s, %s)", (name, timeout))[0][0]
    if not got:
        frappe.throw(
            "This board column is busy — try the move again.",
            frappe.ValidationError,
        )
    try:
        yield
    finally:
        frappe.db.sql("SELECT RELEASE_LOCK(%s)", (name,))


def rebalance_column(project: str, status: str):
    """Re-space every task in a column evenly. Cheap and rare."""
    names = frappe.get_all(
        "BP Task", filters={"project": project, "status": status},
        order_by="board_rank asc, creation asc", pluck="name")
    for i, name in enumerate(names, start=1):
        frappe.db.set_value("BP Task", name, "board_rank", fmt(i * STEP),
                            update_modified=False)
