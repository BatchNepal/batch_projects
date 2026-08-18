# Definition of Done

A change is done when the behaviour is complete, reviewable, and safe to operate—not merely when the happy path works on one developer machine.

## Required for every non-trivial change

- Acceptance criteria are satisfied.
- Relevant automated tests exist and pass.
- CI passes.
- Error and empty states are handled where applicable.
- Public behaviour/API changes are documented.
- No unrelated changes are bundled into the PR.
- No secrets, customer data, or private planning material are committed.

## Additional gates by risk

### Permissions / tenancy / identity

- Server-side authorization is enforced; UI hiding is never the authority.
- Negative tests prove a lower-privileged or foreign-project user is denied.
- Service identities are narrowly scoped and cannot silently become the acting business user.
- Failure is fail-closed where trust cannot be established.

### Billing / accounting / money

- Values have explicit units/currency semantics.
- `0`, `NULL`, and missing values are intentionally distinct where meaningful.
- Draft/submit/cancel/return/amend lifecycle is defined.
- Duplicate execution is prevented or safely idempotent.
- ERPNext remains the accounting source of truth; no shadow ledger is introduced.
- Multi-project and multi-currency cases are tested where supported.

### Schema / migrations

- Fresh install works.
- Upgrade from the previous supported release works.
- Patch/backfill is idempotent or safely one-shot by design.
- Existing user data is preserved or migration impact is explicitly documented.
- Recovery/rollback path is understood before merge.

### Gateway / premium boundary

- Premium enforcement is not solely an editable frontend/Python conditional when the protected capability can live in Gateway.
- App/Gateway contract is version-compatible and fails clearly when incompatible.
- Direct-to-Frappe bypass is considered.
- Secrets and privileged service calls use a machine-authenticated boundary.

### UI

- Existing `@/ui` components and design tokens are used unless an ADR/design-system change justifies otherwise.
- Loading, error, empty, disabled, and permission-denied states are coherent.
- Keyboard/focus behaviour is preserved for interactive changes.
- Screenshots or recording are attached to the PR for visible changes.

## Release readiness

An issue may be development-complete while still waiting for release. `Done` means merged and accepted; release tracking remains separate so supported branches and shipped versions stay auditable.
