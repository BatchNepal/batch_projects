# Deploying BatchProjects

Two independent components make up a BatchProjects deployment, depending
on which features you need:

1. **BatchProjects** — the Community-edition Frappe application and Vue
   interface. Installed with a standard `bench get-app`, and works
   anywhere Frappe does: self-hosted (Docker or bare bench) or on Frappe
   Cloud. See the [root README](../README.md#quick-start). Starting from
   nothing? [`docker-compose.selfhost.yml`](docker-compose.selfhost.yml)
   provisions ERPNext and BatchProjects together.
2. **The Gateway** (optional) — real-time collaboration, workflow
   automation, and the other capabilities described in
   [`gateway-setup.md`](gateway-setup.md). Every install activates
   automatically on a free 60-day Business-plan trial (no card required),
   reverting to the free tier afterward with nothing deleted or blocked
   beyond normal free-tier gating — a paid plan is only needed to keep the
   trial's features past day 60. Runs as its own compact Docker Compose
   stack on infrastructure you control, independent of how ERPNext itself
   is hosted.

Organizations using the Community edition only need step 1 — the Gateway
is entirely optional.

## Compatibility

BatchProjects, the Gateway, and ERPNext core each version independently.
Compatibility between them is managed as follows:

| Relationship | Mechanism | How it's enforced |
|---|---|---|
| **BatchProjects ⨯ ERPNext/Frappe core** | A dedicated git branch per ERPNext release line — `version-15` targets ERPNext v15, with `version-16` following the same pattern once ERPNext v16 ships. | Selected at install time (`bench get-app --branch version-15`). |
| **BatchProjects ⨯ Gateway** | Semantic version ranges. Each Gateway release declares the BatchProjects version range it supports; the installer detects the running BatchProjects version and automatically resolves the newest compatible Gateway release from a signed compatibility manifest. | Fully automatic, both at install time and on every subsequent Gateway restart. |
| **Gateway ⨯ ERPNext/Frappe core** | The same branch convention as the first row, applied to the Gateway's own release channel. | Determined by which Gateway release channel is in use. |

In practice, an organization selects the `version-NN` branch that matches
its ERPNext installation; everything downstream — which Gateway release
is installed and kept current — is resolved automatically. A Gateway
release that is incompatible with the installed BatchProjects version
will refuse to start rather than operate in an unsupported state.

## Deployment scenarios

| Environment | BatchProjects | Gateway |
|---|---|---|
| Self-hosted, Docker | `bench get-app` inside the bench container | Co-located or on separate infrastructure — the installer detects the topology and confirms before writing configuration |
| Self-hosted, bare bench | `bench get-app`, no containerization | Deployed via its own Docker Compose stack, whether co-located or separate |
| Frappe Cloud | Standard Frappe Cloud application install | Always deployed on separate infrastructure, since Frappe Cloud does not host arbitrary services. Every configuration value the Gateway requires is available directly from the Frappe Cloud dashboard — no shell access is needed. |

## Domain requirements

The Gateway installer provisions a working HTTPS endpoint automatically if
no domain is supplied — a subdomain of `erpnext-nepal.com` named after the
ERPNext site, one per instance, with DNS managed automatically on your
behalf. A dedicated domain or subdomain is fully supported and recommended
for any production deployment.
