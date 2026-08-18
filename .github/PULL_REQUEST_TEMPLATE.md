## Summary

<!-- What problem does this solve and why is this change needed? -->

Closes #

## Change type

- [ ] Bug fix
- [ ] Feature
- [ ] Security hardening
- [ ] Refactor / technical debt
- [ ] Migration / schema
- [ ] Documentation / developer experience

## Risk assessment

**Risk:** Low / Medium / High / Critical

Affected areas:

- [ ] Frappe schema / DocTypes
- [ ] Permissions / tenancy / identity
- [ ] ERPNext integration
- [ ] Billing / accounting / money
- [ ] Gateway / premium boundary
- [ ] Automation / integrations
- [ ] Frontend / UX
- [ ] Migration / upgrade path
- [ ] Public API / compatibility

## Behaviour and invariants

<!-- State the externally visible behaviour and the invariants that must remain true. For financial or permission changes, be explicit. -->

## Data and migration impact

<!-- Schema changes, patches, backfills, fixtures, fresh-install behaviour, or "None". -->

## Security impact

<!-- Authn/authz, tenant isolation, secrets, outbound network access, or "None". -->

## Financial impact

<!-- Money, rates, FX, timesheets, expenses, procurement, invoices, payment lifecycle, or "None". -->

## Testing

<!-- Exact automated and manual checks performed. Include failure-path testing where relevant. -->

- [ ] Regression test added or existing coverage proves the changed behaviour
- [ ] Relevant tests pass locally
- [ ] CI passes
- [ ] Fresh install / migrate considered when schema or setup changed
- [ ] Failure and rollback behaviour considered

## Compatibility

- ERPNext/Frappe target: `version-__`
- BatchProjects compatibility impact: None / describe
- Gateway compatibility impact: None / describe

## UI evidence

<!-- Required for visible UI changes: screenshots or recording, including empty/loading/error states where relevant. -->

## Rollback

<!-- How can this change be safely reverted? Note irreversible data migrations explicitly. -->

## Frontend build

- [ ] If `frontend/src/` changed, I ran `yarn build` and committed `batch_projects/public/frontend/`
- [ ] Not applicable

## Final review

- [ ] Scope is limited to this issue; unrelated cleanup is excluded
- [ ] Documentation / ADRs updated when architecture or public behaviour changed
- [ ] No secrets, credentials, customer data, or private planning material are included
