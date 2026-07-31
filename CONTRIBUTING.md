# Contributing to BatchProjects

Thanks for looking at this. A few things to know before you send a PR.

## How contributions land

This repo is **PR-only** — there's no direct push to `version-15` (the
default branch), including for maintainers. The flow:

1. Fork, branch off `version-15`.
2. Open a PR. Fill in the template — what changed and why, not just what.
3. CI has to pass (see below).
4. A maintainer reviews, may ask for changes, then merges.

By submitting a PR you agree your contribution is licensed under this
project's license (AGPL-3.0-only, see [`LICENSE`](LICENSE)).

## Branch model

Branches are named `version-NN`, matching the ERPNext major version they
target — `version-15` today, following the same convention used by
[HRMS](https://github.com/frappe/hrms), Payments, Shipping, and other Frappe
community apps. Open PRs against the branch matching the ERPNext version
you're testing on. See [`deploy/README.md`](deploy/README.md) for the full
compatibility story (this app's version, the optional gateway add-on's
version, and ERPNext's version are three separate things that don't move in
lockstep).

## Dev setup

This is a standard Frappe app plus a Vue 3 / Vite SPA.

```bash
# Inside an existing bench
bench get-app https://github.com/BatchNepal/batch_projects --branch version-15
bench --site yoursite.local install-app batch_projects

# Frontend
cd apps/batch_projects/frontend
NODE_ENV=development yarn install --production=false
yarn dev      # dev server with hot reload
yarn build    # production build → ../batch_projects/public/frontend
```

`bench build` does **not** rebuild this SPA (it's a separate Vite project,
not part of Frappe's own asset pipeline) — always run `yarn build` after
frontend changes, before committing.

## The dist-drift check

`public/frontend/assets/` (the built SPA) is committed to the repo — this is
deliberate, so `bench get-app` + `bench install-app` works with zero Node
dependency for anyone consuming the app normally. CI enforces that committed
output actually matches source: it runs `yarn build` and diffs the result
against what you committed. **If you touch anything under `frontend/src/`,
run `yarn build` and commit the resulting changes in `public/frontend/` in
the same PR**, or CI will fail.

## Code style

- Python: match the existing style in the file you're editing. No new
  formatter/linter config without discussing it first.
- Vue/frontend: use the existing `@/ui` component kit, don't hand-roll CSS
  or introduce a second component library. If you're touching UI, a
  screenshot in the PR description speeds up review a lot.
- Keep changes scoped to what the PR is about. Unrelated cleanup makes
  review slower, not faster — send it as a separate PR.

## Reporting bugs vs. security issues

Regular bugs: open a GitHub issue with repro steps.
Security vulnerabilities: **do not** open a public issue — see
[`SECURITY.md`](SECURITY.md).

## Code of Conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md).
