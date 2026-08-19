# BatchProjects Engineering Workflow

This document defines how changes are planned, implemented, reviewed, and released.
It applies to maintainers and external contributors.

## Principles

1. Production branches are changed through pull requests, never casual direct pushes.
2. Every non-trivial change has a traceable issue or equivalent design context.
3. Correctness, authorization, financial integrity, migration safety, and compatibility are product requirements, not cleanup work.
4. Small reviewable changes are preferred to broad mixed-purpose refactors.
5. Public Community code and proprietary Gateway capabilities have an explicit architectural boundary.

## Work lifecycle

`Backlog -> Needs design -> Ready -> In progress -> In review -> Ready for release -> Done`

Critical incidents may move directly to In progress, but still require an issue, regression coverage, and PR review before merge.

## Issue classes

- Bug: reproducible incorrect behaviour.
- Regression: behaviour that worked in a prior supported version and no longer does.
- Feature: new user-visible capability or material workflow improvement.
- Engineering: architecture, technical debt, migration, CI, reliability, performance, or developer experience.
- Security hardening: planned non-sensitive security work. Undisclosed vulnerabilities follow SECURITY.md and are never filed publicly.

## Priority

- P0: security, data corruption, financial correctness, tenant isolation, upgrade/install breakage, or a release-blocking outage.
- P1: major workflow correctness/reliability issue with no acceptable long-term workaround.
- P2: important product or engineering improvement.
- P3: minor improvement, polish, or opportunistic cleanup.

Priority is independent of type. A refactor can be P0 if it is required to remove a live safety risk; a feature can be P3.

## Branches

For the v15 line:

`short-lived branch -> develop-15 -> tested release PR -> version-15`

- `develop-15` is the integration branch. Normal fixes, features, engineering work, dependency updates, and release preparation start from and merge back into it.
- `version-15` is the stable/default release branch. It receives only explicitly tested release candidates and minimal production hotfixes.
- Short-lived implementation branches should describe one concern and are deleted after merge.
- A production hotfix starts from `version-15`, lands there through a reviewed PR, and is immediately forward-ported to `develop-15` through a second reviewed PR. Stable-only fixes are release drift and must be reconciled.
- Dependabot version-update PRs target `develop-15`. GitHub security-update PRs target the default branch (`version-15`) and therefore follow the hotfix/forward-port path.
- Force-pushing or rewriting either long-lived branch is not part of the normal release process.

Short-lived implementation branches should describe intent, for example:

- `fix/381-zero-billing-hours`
- `sec/417-gateway-ssrf`
- `feat/402-resource-calendar`
- `refactor/455-board-service`
- `chore/470-ci-frappe-tests`

Delete short-lived branches after merge.

## Pull requests

A pull request must explain why the change exists, its risk, compatibility impact, tests, migration impact, and rollback path. The diff is not the design document.

Keep one concern per PR where practical. Do not mix unrelated formatting, dead-code cleanup, dependency upgrades, and product behaviour into one change.

High-risk changes require especially explicit evidence:

- Billing/accounting: amount units, currency, lifecycle, idempotency, and ERPNext source-of-truth behaviour.
- Permissions/security: authenticated identity, tenant/project boundary, failure mode, and negative tests.
- Schema/migrations: fresh install, upgrade, idempotency, rollback/recovery, and existing-data preservation.
- Gateway contracts: supported app/gateway version range and fail-closed behaviour.

## Review

Reviewers evaluate behaviour and risk, not just syntax.

A reviewer should be able to answer:

- What invariant is this change protecting or introducing?
- Can a lower-privileged user bypass the intended boundary?
- Can the operation partially commit or be executed twice?
- Can an upgrade leave an existing site inconsistent?
- Can Community/Gateway behaviour drift across versions?
- Is the failure visible and recoverable?

CODEOWNERS identifies the current accountable maintainer for sensitive paths. Ownership should be split into real GitHub teams only when those teams exist.

## Merge policy

Preferred merge method: squash for ordinary feature/fix branches so the supported branch stays readable. Preserve separate commits only when their history is intentionally useful and independently valid.

Do not merge with failing required checks. Do not bypass protections for convenience. Emergency bypasses, when repository administrators must use one, require a follow-up issue explaining the incident and restoring normal controls.

## Releases

A release is a product event, not only a tag.

For v15, release preparation happens on `develop-15`. The exact release candidate must be identified and verified before a PR promotes it to `version-15`. Do not use `version-15` as a second integration branch, and do not assume independently accumulated commits are safe to combine without proving the release-candidate tree.

Before release:

- target issues are closed or explicitly deferred;
- required CI is green;
- schema migrations are tested;
- public compatibility statements are current;
- CHANGELOG is updated;
- security-sensitive changes are reviewed;
- the exact artifact/revision being released is identified;
- meaningful stable-only drift has been forward-ported or deliberately reconciled;
- the exact release-candidate tree has passed migration, targeted high-risk regressions, and release smoke verification.

Patch releases contain compatible fixes. Minor releases may add backwards-compatible capability. Breaking application/Gateway requirements must be explicit in release notes and compatibility metadata.

## Architecture decisions

Decisions that affect trust boundaries, data ownership, financial semantics, compatibility, or public/proprietary separation belong in `docs/architecture/` as ADRs. Code comments may link to an ADR, but architecture must not depend on private planning documents that are absent from the repository.
