# Architecture Decision Records

Architecture Decision Records (ADRs) capture durable decisions whose rationale must survive individual contributors and private planning documents.

Use an ADR when a change affects one or more of:

- authentication, authorization, or tenant boundaries;
- Community vs proprietary Gateway ownership;
- ERPNext data/accounting authority;
- financial semantics or lifecycle;
- compatibility/versioning contracts;
- transaction boundaries or irreversible migrations;
- infrastructure assumptions that constrain supported deployments.

## Status

Each ADR uses one of: Proposed, Accepted, Superseded, Deprecated.

## Format

1. Context
2. Decision
3. Consequences
4. Alternatives considered

ADRs document decisions, not implementation diaries. If a decision changes, add a new ADR and mark the old one Superseded rather than silently rewriting history.

## Current records

- ADR-001: Open-core capability boundary
- ADR-002: Gateway identity and trust boundary
- ADR-003: Authorization model
- ADR-004: ERPNext financial authority
