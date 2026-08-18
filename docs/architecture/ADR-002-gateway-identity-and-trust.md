# ADR-002: Gateway identity and trust boundary

Status: Accepted

## Context

BatchProjects supports deployments where browser requests pass through bp-gateway before reaching Frappe. Gateway may use a privileged Frappe service account as a transport credential, but business authorization must still evaluate the real end user.

## Decision

The Gateway is the only trusted source of `X-BP-*` entitlement and acting-user headers. It strips caller-supplied values, injects validated claims, and signs the request with the shared Gateway/Frappe secret.

Frappe verifies the signature before applying Gateway identity. When a real acting user is asserted, application permission checks run as that user; the Gateway service account must never become the implicit business actor.

Machine-only internal APIs must authenticate the specific Gateway/service trust boundary. Broad human roles such as System Manager are not a substitute for service authentication when an endpoint returns secrets or performs privileged machine operations.

If asserted identity or authorization scope cannot be verified, sensitive operations fail closed.

## Consequences

- Direct-to-Frappe access to Gateway-dependent APIs must not bypass the trust boundary.
- New privileged service endpoints require explicit machine authentication and negative tests.
- Client-supplied `X-BP-*` headers are untrusted input.
- ReBAC/permission-resolution failure must not silently widen access.

## Alternatives considered

### Run all proxied calls as the Gateway service account

Rejected because it collapses user authorization into transport privilege and makes a proxy bug an application-wide privilege escalation.

### Trust an unsigned acting-user header

Rejected because any caller able to reach Frappe could impersonate another user.
