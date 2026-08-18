# Issue taxonomy

Use a small, composable label system. Labels describe independent dimensions instead of becoming a second backlog.

## Type

- `type:bug` — incorrect behaviour
- `type:feature` — new user-facing capability
- `type:security` — non-sensitive security hardening
- `type:tech-debt` — maintainability/debt reduction
- `type:refactor` — structural change intended to preserve behaviour
- `type:docs` — documentation only

## Area

- `area:work`
- `area:frontend`
- `area:erp`
- `area:billing`
- `area:permissions`
- `area:gateway`
- `area:automation`
- `area:integrations`
- `area:resources`
- `area:reporting`
- `area:migrations`
- `area:ci`

## Priority

- `priority:P0` — release-blocking security, data, financial, tenant, install/upgrade, or outage risk
- `priority:P1` — major correctness/reliability issue
- `priority:P2` — important planned work
- `priority:P3` — minor improvement/polish

## Risk

- `risk:critical`
- `risk:high`
- `risk:normal`

Risk is about the consequence of getting the change wrong; priority is about when it must be addressed.

## Workflow labels

Prefer GitHub Project fields for normal workflow state. Use labels only for exceptional states such as `blocked` or `needs-design` when project automation cannot express them.

## Rules

- Do not create labels for individual releases, people, customers, or one-off initiatives.
- Do not encode multiple dimensions in one label (`high-priority-billing-bug`).
- A typical triaged issue should have one type, one primary area, one priority, and a risk label when the change is unusually sensitive.
- Security vulnerability disclosures do not become public labelled issues until coordinated disclosure permits it.
