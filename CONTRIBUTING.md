# Contributing to BatchProjects

BatchProjects is maintained as production software for the ERPNext ecosystem. Contributions are welcome, but changes must be reviewable, testable, and safe to operate.

## Before you start

- Use the structured GitHub issue forms for bugs, regressions, features, and engineering work.
- Security vulnerabilities are **never** reported through public issues; follow [`SECURITY.md`](SECURITY.md).
- Read [`docs/engineering/DEVELOPMENT_WORKFLOW.md`](docs/engineering/DEVELOPMENT_WORKFLOW.md) and [`docs/engineering/DEFINITION_OF_DONE.md`](docs/engineering/DEFINITION_OF_DONE.md) before non-trivial changes.
- Architecture decisions that affect trust boundaries, money, compatibility, migrations, or Community/Gateway ownership belong in [`docs/architecture/`](docs/architecture/).

## How changes land

Supported release branches are PR-only by policy. The expected flow is:

1. Start from the matching `version-NN` branch.
2. Create a short-lived branch for one concern.
3. Implement the smallest coherent change.
4. Add or update regression coverage.
5. Run the relevant checks locally.
6. Open a pull request and complete the full PR template.
7. Address review and CI findings.
8. Merge only after required checks and review are satisfied.

Do not bundle unrelated cleanup into a product change. Smaller PRs are easier to reason about, safer to revert, and produce more useful repository history.

By submitting a PR you agree your contribution is licensed under this project's license (AGPL-3.0-only, see [`LICENSE`](LICENSE)).

## Branch model

Branches are named `version-NN`, matching the ERPNext/Frappe major version they target. Open PRs against the release line you actually tested.

Short-lived implementation branches should describe intent, for example:

- `fix/381-zero-billing-hours`
- `sec/417-gateway-ssrf`
- `feat/402-resource-calendar`
- `refactor/455-board-service`
- `chore/470-ci-frappe-tests`

See [`deploy/README.md`](deploy/README.md) for BatchProjects/Gateway/ERPNext compatibility.

## Development setup

BatchProjects is a Frappe app plus a Vue 3 / Vite SPA.

```bash
# Inside an existing bench
bench get-app https://github.com/BatchNepal/batch_projects --branch version-15
bench --site yoursite.local install-app batch_projects

# Frontend
cd apps/batch_projects/frontend
NODE_ENV=development yarn install --production=false
yarn dev
yarn build
```

`bench build` does **not** rebuild the standalone Vite SPA. After frontend source changes, run `yarn build` and commit the resulting `batch_projects/public/frontend/` output in the same PR.

## Testing expectations

At minimum, test the behaviour you changed and its failure path. Higher-risk areas require stronger evidence:

- permissions/tenancy: prove denied access as well as allowed access;
- billing/accounting: test zero/null semantics, currency, lifecycle, and duplicate execution where relevant;
- migrations/schema: test fresh install and upgrade behaviour;
- Gateway contracts: test incompatible/missing Gateway behaviour and fail-closed enforcement;
- UI: cover loading, empty, error, permission, and disabled states where the change affects them.

Frappe integration tests can be run with `bench run-tests --app batch_projects` or a narrower module while developing.

## Frontend conventions

Use the existing `@/ui` component kit and token system. Do not add a second component library or introduce page-local visual conventions when an existing primitive covers the interaction. Visible UI changes should include screenshots or a short recording in the PR.

## Code and architecture conventions

- Prefer domain-focused modules over adding unrelated responsibilities to large API modules.
- Low-level helpers should not decide transaction boundaries unless that ownership is intentional and documented.
- `ignore_permissions=True` requires an explicit, server-side authorization boundary before it is used.
- Financial logic must preserve value units and ERPNext's role as accounting source of truth.
- Premium capability should follow [`ADR-001`](docs/architecture/ADR-001-open-core-boundary.md); a removable public-code conditional is not sufficient protection for valuable executable capability that can live in Gateway.
- Do not reference private/non-shipped planning files as the sole explanation for public architecture.

## Pull request review

The reviewer is expected to understand why the change exists, what invariant it affects, what can fail, and how it is tested. The PR template intentionally asks for security, financial, migration, compatibility, and rollback impact so those questions are answered before merge instead of after an incident.

## Code of Conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md).
