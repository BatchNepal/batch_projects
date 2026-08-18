# ADR-001: Open-core capability boundary

Status: Accepted

## Context

BatchProjects is an AGPL Frappe application with an optional proprietary Gateway. The Community application must remain useful and trustworthy on its own, while paid capability must not rely solely on removable frontend or Python conditionals.

## Decision

Community owns durable project-management data, core task/project workflows, and ERPNext integration required for a coherent self-hosted product.

A capability is appropriate for Gateway ownership when its defensible value is execution, coordination, computation, realtime delivery, scheduling, integration brokering, metered infrastructure, or enterprise control. In those cases the public app may contain schemas, configuration UI, and explicit contracts, but the valuable execution should occur in Gateway where practical.

Correctness, authorization, data integrity, upgrade safety, and security are never premium features.

Entitlement checks in public code are usability and defence-in-depth controls; they are not considered the sole commercial boundary for a capability whose implementation can reasonably live in Gateway.

## Consequences

- Community must not be intentionally crippled to force conversion.
- Premium functionality requires an explicit app/Gateway contract.
- Paid execution paths must fail clearly when Gateway is unavailable or incompatible.
- Product planning must decide Community/Gateway ownership before implementation rather than scattering ad-hoc tier checks through code.

## Alternatives considered

### Gate complete public implementations with `require_feature()` only

Rejected as the primary protection. A self-hosting operator can modify AGPL Python/JavaScript.

### Keep the entire application proprietary

Rejected because Community adoption, Frappe ecosystem distribution, inspectability, and partner confidence are strategic product requirements.
