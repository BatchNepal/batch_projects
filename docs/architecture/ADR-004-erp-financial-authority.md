# ADR-004: ERPNext financial authority

Status: Accepted

## Context

BatchProjects provides project financial views and workflow conveniences while ERPNext is the accounting system of record. Reimplementing accounting state inside BatchProjects would create reconciliation and compliance risk.

## Decision

ERPNext remains authoritative for accounting documents and posting state: Timesheets, Expense Claims, Purchase Orders/Invoices, Sales Invoices, Payment Entries, GL impact, taxes, currency conversion records, and document lifecycle.

BatchProjects may orchestrate creation of drafts, attach project/task dimensions, compute operational previews, and present project-centric rollups. Those views must derive from or reconcile to ERPNext records rather than maintain an independent ledger.

Financial values are treated as typed quantities. Amount plus currency, rate plus currency basis, and hours plus billing semantics travel together. Zero, null, and missing values are not interchangeable. Invalid or unresolved FX fails explicitly rather than substituting a plausible-looking number.

Billing operations must define draft, submit, cancel, return/credit, amendment, partial billing, multi-project attribution, and idempotency behaviour before being considered complete.

## Consequences

- BatchProjects does not create shadow invoice/payment truth.
- Financial previews must be explainable from underlying ERPNext rows.
- Lifecycle hooks/reconciliation must handle reversals, not only creation/submit happy paths.
- Multi-project billing must preserve per-project attribution even when ERPNext requires a header-level workaround.
- Billing correctness failures are release-blocking regardless of premium tier.

## Alternatives considered

### Maintain a separate BatchProjects billing ledger

Rejected because it duplicates ERPNext accounting state and creates inevitable drift.

### Silently default unresolved currency conversion

Rejected because a visible failure is recoverable; a confidently wrong invoice or margin figure is not.
