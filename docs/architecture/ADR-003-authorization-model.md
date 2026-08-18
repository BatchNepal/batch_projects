# ADR-003: Authorization model

Status: Accepted

## Context

BatchProjects has its own project roles and visibility model while also surfacing selected ERPNext data. BatchProjects users may intentionally lack broad native ERPNext roles, so authorization cannot be reduced to one framework-level permission check.

## Decision

BatchProjects data is authorized by project/workspace membership, role, capability, and tenant/project scope on the server. The frontend may hide unavailable actions but is never the security boundary.

ERPNext documents surfaced through BatchProjects require both an intentional BatchProjects workflow boundary and appropriate document/tenant validation. Generic ERP dashboard sources must additionally respect native ERPNext read/write permission unless a narrowly-scoped BatchProjects operation explicitly performs an authorized write on the user's behalf.

For scoped ERP documents, a foreign document and a nonexistent document should normally produce the same denial where distinguishing them would leak tenancy information.

Authorization logic should be centralized and reused. New endpoints must not invent a parallel interpretation of project access.

## Consequences

- Every mutation needs a server-side access check.
- Dynamic data surfaces require source, field, and operator allowlisting.
- Negative permission tests are required for sensitive paths.
- `ignore_permissions=True` is acceptable only after an explicit upstream authorization boundary is established and documented; it is never a convenience flag.
- ReBAC may optimize/push down scope, but must not silently broaden Frappe's fallback permissions.

## Alternatives considered

### Give every BatchProjects user broad ERPNext roles

Rejected because it unnecessarily exposes ERPNext modules and records unrelated to the project workspace.

### Rely on frontend visibility

Rejected because browser code is user-controlled and cannot enforce authorization.
