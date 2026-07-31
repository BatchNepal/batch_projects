## Plan: User-Seat Licensing Enforcement

**TL;DR** — Enforce the new tiered pricing (Community 3, Growth 10, Pro 20, Business 50, Enterprise unlimited) by rebalancing tier defaults, wiring `assert_seat_available` to all member-insertion points, and adding frontend seat-limit UX. The seat-enforcement scaffolding **already exists** in `entitlements.py` — this plan covers the remaining gaps.

---

### Baseline — what's already built

| Layer | Status |
|---|---|
| License JWT `MaxUsers` claim | ✅ in `LicenseClaims.MaxUsers` |
| Go `Checker.MaxUsers()` accessor | ✅ on `license.Checker` |
| Proxy strips client `X-Bp-*` headers | ✅ anti-spoofing |
| Proxy injects `X-BP-Max-Users` | ✅ every proxied request gets it |
| Request HMAC signature (`X-BP-Gateway-Sig`) | ✅ `gateway_guard.py` verifies it |
| All batch_projects API methods verify gateway sig | ✅ via `_require_system_user()` / `_check_permission()` |
| `entitlements.py:current_max_users()` | ✅ reads header, cached fallback |
| `entitlements.py:count_active_seats()` | ✅ enabled System Users with ≥1 BP Project/Team Member |
| `entitlements.py:assert_seat_available()` | ✅ raises `BPUpgradeRequired` |
| `entitlements.py:assert_seats_available()` | ✅ bulk variant |
| Gateway bootstrap returns `max_users` | ✅ via `/v1/session/bootstrap` and `/v1/premium/entitlements` |
| SPA store receives `limits.max_users` | ✅ `entitlements.js` store |
| Backend emits `seats_used` in `get_entitlements()` | ✅ already in response (Phase 4 needs no backend changes) |

### Gaps to close

| Gap | Phase | Status |
|---|---|---|
| Tier defaults don't match new bands (starter=5, you want Community=3, Growth=10, etc.) | 1 | ✅ Done |
| `_TIER_DEFAULT_MAX_USERS` name suggests it's the live ladder when it's only the unlicensed fallback | 1 | ✅ Done |
| `current_max_users()` reads header without checking gateway sig was verified on this request | 1 | ✅ Done |
| `assert_seat_available` called from only 1 place (invitation accept) — missing from project creation, team creation, and the generic REST API | 2 | ✅ Done |
| No frontend display of seat consumption (backend already provides the data) | 4 | 🏗️ In progress |
| No self-serve upgrade flow when hard-blocked | 5 | ❌ Not started |

---

### Phase 1 — Rebalance tiers & harden header trust ✅

**A. Rename Python fallback table** (`entitlements.py`) ✅

```
_TIER_DEFAULT_MAX_USERS  →  _UNLICENSED_FALLBACK_MAX_USERS
```

Docstring added explaining this is ONLY the unlicensed fallback. Rebalanced values:
```python
_UNLICENSED_FALLBACK_MAX_USERS = {
    "starter": 3,      # Community
    "growth": 10,      # $29/mo
    "pro": 20,         # $59/mo
    "team": 25,        # legacy
    "business": 50,    # $149/mo
    "enterprise": 0,   # unlimited
    "dev": 0,          # unlimited
}
```

Added `"growth"` and `"pro"` to `_TIER_RANK` (rank 10 = unlocks all features) and `_TIER_LABEL`.

**B. Update Go defaults** (`license.go`) ✅

- `starterClaims().MaxUsers`: 5 → 3
- Added `growth`(10) and `pro`(10) to `tierRank` — same rank as team/business means all features unlocked
- Updated `tierLabel()`: starter→"Community", added growth→"Growth", pro→"Pro"
- Updated docstring: all paid plans unlock all features; only starter has feature gating

**C. Defense-in-depth: fail-closed on unauthenticated header** ✅

- `gateway_guard.py`: sets `frappe.local._bp_gateway_verified = True` after successful HMAC verification
- `entitlements.py:current_max_users()`: checks `getattr(frappe.local, '_bp_gateway_verified', False)` before trusting `X-BP-Max-Users` header; falls through to unlicensed cap if flag is false

**D. Seat counting docstring** — not changed yet (minor, non-functional).

---

### Phase 2 — Wire seat checks to all member-insertion points ✅

**Layer A — `doc_events` hook** ✅ Added to `hooks.py`:
```python
"BP Project Member": {
    "before_insert": "batch_projects.entitlements.before_member_insert",
},
"BP Team Member": {
    "before_insert": "batch_projects.entitlements.before_member_insert",
},
```

Handler in `entitlements.py`:
```python
def before_member_insert(doc, method):
    user = doc.get("user")
    if user:
        assert_seat_available(user)
```

**Layer B — Direct-SQL call sites** ✅

| Location | Change |
|---|---|
| `board.py:create_project` | Added `assert_seat_available(creator)` before the direct-SQL INSERT |
| `board.py:create_team` | Added `assert_seat_available(creator)` before `doc.append("members")` |

---

### Phase 3 — Gateway-side enforcement (deferred)

**Decision: skip for v1.** Reasoning:
- The doc_events hook + direct-SQL belt-and-suspenders cover every insertion path.
- The gateway already enforces: (a) license validity (checker.Middleware on expired/absent), (b) request authentication (HMAC signature).
- MethodGate was built as additional defense-in-depth (covers `/api/method/` and `/api/resource/` paths in Go).

Revisit if:
- Frappe is ever exposed directly without the gateway on production
- A bypass of the doc_events hook is found

---

### Phase 4 — Frontend seat-limit UX

**Note**: The backend already emits `seats_used` in `get_entitlements()` (entitlements.py:345). No backend changes needed for this phase — it's purely frontend wiring.

**Files**: `frontend/src/stores/entitlements.js`, people/team management components

1. **Entitlements store** — add:
   - `seatsUsed` (number, from existing `seats_used` field in bootstrap response)
   - `seatsTotal` (number, from existing `limits.max_users`)
   - `seatsRemaining` (computed: `seatsTotal === 0 ? Infinity : seatsTotal - seatsUsed`)
   - `isAtCapacity` (computed: `seatsRemaining <= 0`)

2. **People tab / Add Member dialog** — show:
   - `"3 of 3 seats used"` indicator next to the member count
   - When at capacity, add a banner: "Your plan covers {seats} seats. All are in use. [Upgrade]"
   - Disable the "Invite" / "Add" button with an upgrade CTA tooltip

3. **Team detail / Manage Members** — same treatment

4. **Optimistic pre-check**: Before the server call, check `isAtCapacity` locally. If true, show the upgrade prompt immediately — no round-trip needed. Server still enforces as backstop.

---

### Phase 5 — Self-serve upgrade flow

**Files**: `frontend/src/utils/api.js`, upgrade dialog component

1. **Error interceptor**: The SPA's API layer (`api.js`) already detects `BPUpgradeRequired` by `exc_type`. When the error is seat-related (message matches "seat limit" or "seats"), route to an upgrade dialog instead of a generic toast.

2. **Upgrade dialog**: "Your plan includes {seats} seats. Upgrade to add more people." with a "View Plans" button that takes them to the pricing page (or opens a contact-sales form for Enterprise).

3. **Post-upgrade**: When the license JWT is refreshed (higher `MaxUsers`), the next proxied request carries the new `X-BP-Max-Users`. No DB migration or manual intervention needed. The previously-blocked user can immediately add members.

---

### Header trust — full chain (for review)

```
Browser                          bp-gateway                          Frappe
  │                                  │                                  │
  │  POST /api/method/...            │                                  │
  │  (no X-Bp-* headers)             │                                  │
  │─────────────────────────────────>│                                  │
  │                                  │  1. Strip all X-Bp-* headers    │
  │                                  │     (anti-spoofing)              │
  │                                  │  2. Inject X-BP-Max-Users       │
  │                                  │     (from license JWT)          │
  │                                  │  3. HMAC-SHA256(method+path+ts) │
  │                                  │     → X-BP-Gateway-Sig          │
  │                                  │─────────────────────────────────>│
  │                                  │                                  │
  │                                  │  4. gateway_guard verifies sig  │
  │                                  │     → sets frappe.local flag    │
  │                                  │  5. Method runs, reads header   │
  │                                  │     (trusted because sig passed)│
```

**Threat: curl Frappe directly with spoofed header**
```
curl http://frappe:8000/api/method/... -H "X-BP-Max-Users: 999999"
  → gateway_guard rejects: no X-BP-Gateway-Sig, or wrong signature
  → reject before any header is read  🛡️
```

**Threat: curl Frappe directly on a non-batch_projects endpoint that calls `current_max_users()`**
```
curl http://frappe:8000/api/method/other_app.doSomething
  → gateway_guard skips (path doesn't start with batch_projects)
  → current_max_users() reads X-BP-Max-Users header from request
  → defense-in-depth check: frappe.local._bp_gateway_verified is False
  → fall through to _UNLICENSED_FALLBACK_MAX_USERS  🛡️
```

---

### Verification checklist

- [ ] Start with Community tier (max_users=3). Create a project → creator occupies seat 1.
- [ ] Invite 2 more members via invitations → succeed (seats 2-3).
- [ ] Try inviting a 4th member → `BPUpgradeRequired`, hard-blocked.
- [ ] Same for team membership: try adding 4th user to a team → blocked.
- [ ] Same via generic REST API to `BP Project Member` → doc_events hook catches it → blocked.
- [ ] Upgrade license JWT to Growth (max_users=10) → restart/reload → 4th user can now be added.
- [ ] Frontend shows "3 of 3 seats used" on Community, "10 seats" after upgrade.
- [ ] Dev mode (no license JWT, dev_mode=true) → `starterClaims()` with max_users=3.
- [ ] Direct curl to Frappe with spoofed `X-BP-Max-Users: 999999` on a batch_projects API → rejected by gateway_guard.
- [ ] Same on a non-batch_projects API → fallback cap used (fail-closed).

### Files touched

| File | Change | Status |
|---|---|---|
| `bp-gateway/internal/license/license.go` | `starterClaims().MaxUsers: 5→3`, added `growth`/`pro` to `tierRank`, updated `tierLabel` | ✅ Built |
| `batch_projects/entitlements.py` | `_TIER_DEFAULT_MAX_USERS` → `_UNLICENSED_FALLBACK_MAX_USERS` (3/10/20/50 caps), added `growth`/`pro` ranks + labels, fail-closed header guard, `before_member_insert` handler | ✅ Built |
| `batch_projects/gateway_guard.py` | Sets `frappe.local._bp_gateway_verified = True` after successful verification | ✅ Built |
| `batch_projects/hooks.py` | Added `doc_events` for BP Project Member and BP Team Member `before_insert` | ✅ Built |
| `batch_projects/api/board.py` | Added `assert_seat_available` in `create_project` and `create_team` | ✅ Built |
| `batch_projects/frontend/src/stores/entitlements.js` | Wire seatsUsed/seatsRemaining/isAtCapacity from existing bootstrap fields | ❌ Phase 4 |
| `batch_projects/frontend/src/utils/api.js` | Add seat-limit detection in `BPUpgradeRequired` handler | ❌ Phase 5 |
| People/team management Vue components | Seat consumption display, upgrade CTA, disabled button at capacity | ❌ Phase 4 |
