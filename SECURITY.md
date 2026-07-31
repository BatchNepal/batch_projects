# Security Policy

## Supported versions

Security fixes are backported to the most recent `version-NN` branch matching
a supported ERPNext major release (see the compatibility table in
[`deploy/README.md`](deploy/README.md)). Older `version-NN` branches receive
fixes on a best-effort basis only.

## Reporting a vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Email **info@batchnepal.com** with:

- A description of the vulnerability and its impact.
- Steps to reproduce (a minimal repro is enormously helpful).
- The BatchProjects version / branch you tested against.
- Whether the finding involves the gateway add-on (`bp-gateway`) or the
  core Frappe app — both are in scope, the gateway just isn't public source,
  so a code-level receipt isn't expected for it.

You should get an acknowledgement within a few business days. We'll work
with you on a disclosure timeline once the report is triaged — please give
us a reasonable window to ship a fix before any public disclosure.

## Scope

In scope: the `batch_projects` Frappe app (this repo), the self-host
`deploy/` tooling, and the `bp-gateway` add-on's *behavior* (even though its
source isn't public). Out of scope: vulnerabilities in ERPNext/Frappe core
itself — please report those upstream at
[frappe/frappe](https://github.com/frappe/frappe/security) or
[frappe/erpnext](https://github.com/frappe/erpnext/security).
