# Setting up the BatchProjects Gateway

Premium BatchProjects capabilities — real-time collaboration, workflow
automation, push notifications, subscription management, and others — are
delivered by a dedicated backend service, the **Gateway**. It runs
alongside ERPNext rather than inside it, as its own three-service Docker
Compose stack. This page covers installing it. Organizations using the
Community edition can skip this entirely — BatchProjects runs standalone
without the Gateway.

## Topology

The Gateway can run on the **same infrastructure as ERPNext** or on
**separate infrastructure**. The installer figures this out for you — by
inference from your ERPNext URL, or by asking — but it can also be pinned
explicitly with `--topology`:

| `--topology` value | When | Notes |
|---|---|---|
| `cloud` | ERPNext is on Frappe Cloud | Always separate infrastructure — Frappe Cloud doesn't host arbitrary services. Every value the Gateway needs is available directly from the Frappe Cloud dashboard, no shell access required. |
| `same-vps` | ERPNext runs on this same server | The installer detects whether ERPNext is Dockerized or a bare bench and configures networking accordingly (see `--network` below), confirming what it found before writing anything. |
| `remote` | ERPNext is self-hosted on a different server | Same flow as Frappe Cloud from the installer's point of view — it just needs the URL. |

Omit `--topology` entirely and the installer infers it from `--frappe` (or,
with no `--frappe` either, detects a local Frappe instance or asks via a
short menu) — always with a confirmation, never silently.

In every case, the Gateway is reachable at its own domain (or an
automatically generated one — see below), since the browser communicates
with it directly over HTTPS as a distinct origin.

## Installing

No license key is required to begin; installations activate automatically
on a free 60-day Business-plan trial (no card required), reverting to the
free Community plan afterward with nothing deleted. Upgrade at any time
from BatchProjects' own Billing page.

### Recommended: interactive

```bash
curl -fsSL https://get.batchprojects.com/install.sh | bash
```

With no flags, the installer walks you through everything, in order:
installing Docker if it's missing, confirming the topology it infers (or a
short menu if it can't infer one), your ERPNext URL, a Frappe API key/secret
(with a pointer to where to generate one), your domain (blank for a free
auto-provisioned one), and a final summary to confirm before anything is
written. The license/trial step itself never prompts — it just happens.

### Unattended / scripted

For CI, provisioning scripts, or anywhere a terminal isn't available:

```bash
curl -fsSL https://get.batchprojects.com/install.sh | bash -s -- \
  --yes --topology cloud \
  --frappe https://yoursite.example.com --site yoursite.example.com \
  --domain gateway.yoursite.com \
  --api-key KKKK --api-secret SSSS
```

`--yes` accepts every inferred default instead of prompting — combine it
with enough flags that nothing is left for the installer to ask about, or
it will fail outright rather than hang waiting on a terminal that isn't
there.

Secrets can be supplied via environment instead of flags, to keep them out
of shell history and the process table: `BP_LICENSE_KEY`,
`BP_FRAPPE_API_KEY`, `BP_FRAPPE_API_SECRET`.

Organizations with an existing paid license key supply it directly to
activate that tier immediately instead of starting a trial:

```bash
curl -fsSL https://get.batchprojects.com/install.sh | bash -s -- \
  --key BP-XXXX-XXXX-XXXX \
  --frappe https://yourcompany.com \
  --domain gateway.yourcompany.com
```

`deploy/setup.sh` in this folder runs the identical installer as a local
script, with the same options and behavior.

### What the installer does

1. Verify Docker is present, offering to install it if not.
2. Resolve the topology (see above) and, when co-located with ERPNext,
   detect whether it's Docker or a bare bench.
3. Detect the installed BatchProjects version and automatically select
   the matching Gateway release.
4. Activate the deployment — automatically on a free 60-day Business
   trial if no license key was supplied, or by validating the supplied
   key — and generate the Gateway's configuration.
5. Start the Gateway behind an automatically provisioned TLS endpoint.
6. Display four configuration values required by ERPNext (see below) —
   this step is not automatic and should not be skipped. Trial
   installations also receive a license key at this point; retain it for
   future reinstalls or support requests.

## Deployment flags reference

Most installs never need any of these — the installer infers sensible
defaults for all of them. They exist for layouts the defaults don't fit.

| Flag | Values | What it's for |
|---|---|---|
| `--network` | `bridge` \| `host` \| `attach:NAME` | How the Gateway container reaches the network. `bridge` (default off same-VPS) is normal Docker networking. `host` (default *on* same-VPS) skips Docker's port-mapping layer entirely. `attach:NAME` joins Frappe's own Docker network directly by name — use this when Frappe itself runs in Docker on the same VPS, for a stable container-DNS dial target instead of host networking. |
| `--tls` | `caddy` \| `external` \| `traefik` \| `none` | How HTTPS gets terminated. `caddy` (default when 80/443 are free) is the Gateway's own bundled Caddy, fully automatic Let's Encrypt. `traefik` is chosen automatically when Traefik already owns 80/443 — labels are written automatically, no manual step. `external` is chosen automatically for any other reverse proxy already on 80/443 — the installer writes example config snippets under `reverse-proxy/` that you apply by hand. `none` disables TLS entirely; **development only**, never production. |
| `--reverse-proxy` | `nginx` \| `apache` \| `caddy` \| `traefik` \| `npm` \| `haproxy` \| `other` | What's already running on 80/443, if anything — normally auto-detected. Selects which config-snippet template gets written for the `external` TLS case. |
| `--gateway-port` | port number (default `8001`) | The local port the Gateway binds to. The installer auto-picks the next free port above 8001 on its own — only set this to pin a specific port for a reproducible/scripted deployment; if the pinned port is taken, install fails rather than silently relocating. |
| `--dial-url` | URL | Overrides where the Gateway *container* dials Frappe, separately from `--frappe` (the *public identity* used for the Host header and browser-facing links). The installer already picks the right default per topology (loopback for same-VPS/host networking, the Docker service name for `attach:`, the public URL itself otherwise) — set this explicitly only when none of those fit, e.g. a private VPN path or a non-default Frappe port. |
| `--site` | Frappe site name | Cosmetic only — feeds the manual `bench --site <name> set-config ...` fallback commands if automatic configuration isn't available. Re-derived from Frappe's own session info if omitted. |
| `--api-key` / `--api-secret` | credentials | **Required** (or prompted, or via `BP_FRAPPE_API_KEY`/`BP_FRAPPE_API_SECRET`). Live-validated against Frappe before the install proceeds at all, and used to attempt automatic Frappe-side configuration (see below). |
| `--tune-kernel` | flag, opt-in | Writes host-wide sysctl tuning (larger connection backlogs, BBR congestion control, a higher file-descriptor ceiling) for a Gateway fronting many concurrent connections at scale. Affects the *entire machine*, not just the Gateway container — skip this on a shared VPS running other services. |
| `--reconfigure` | flag | Re-asks every deployment question (topology, network, TLS, domain) from scratch on an existing install, keeping the same license. |
| `--no-color` | flag | Disable colored output. |

## No domain available?

Omitting `--domain` causes the license server to provision a working HTTPS
endpoint automatically — a subdomain named after your ERPNext site (for
example, `acmecorp.erpnext-nepal.com`), with its DNS record created and kept
pointed at this server automatically, including across a redeploy to new
infrastructure. TLS is provisioned against it exactly as it would be for a
dedicated domain. Each instance receives exactly one such subdomain,
reused on every subsequent activation rather than a new one each time. A
permanent domain can be attached at any later time with
`--update --domain your.domain.com`.

## Connecting the Gateway to ERPNext

The Gateway signs its requests to ERPNext, and ERPNext must be configured
with the matching credentials to trust them. The installer first attempts
this automatically over BatchProjects' own API, using the already-validated
`--api-key`/`--api-secret`; if that's unavailable (an older BatchProjects
version, for instance), it falls back to displaying four key/value pairs
for you to apply by hand — where depends on how ERPNext is hosted:

**Self-hosted, with shell access:**

```bash
bench --site <your-site> set-config bp_gateway_shared_secret   "<value from installer>"
bench --site <your-site> set-config bp_bridge_bootstrap_secret "<value from installer>"
bench --site <your-site> set-config bp_scheduler_ingest_token  "<value from installer>"
bench --site <your-site> set-config bp_bridge_url              "<value from installer>"
```

**Frappe Cloud:** open the site dashboard, navigate to **Settings → Site
Config**, add each of the four values, then select **Update
Configuration**. No shell access is required.

Until this step is complete, the Gateway operates normally, but ERPNext
is unable to verify that requests originated from it — premium features
that depend on this trust relationship will not function correctly. This
is especially visible for `bp_bridge_url` specifically: without it, the
workspace/board pages never learn where the Gateway is, so their `/v1/*`
calls (session bootstrap, realtime, files) fail outright rather than just
being unverified.

## Updating

```bash
curl -fsSL https://get.batchprojects.com/install.sh | bash -s -- --update
```

Re-resolves the newest Gateway release compatible with the BatchProjects
version currently installed, applies it, and restarts the service. Nothing
about topology, network, TLS, domain, or the license is touched — a pure
image-version bump.

## Other modes

| Mode | What it does | When to use it |
|---|---|---|
| `--repair` | Re-validates Frappe credentials, rewrites local config/compose/proxy files from what's already known, restarts. **No license-server contact at all.** | A stuck or corrupted local install that still has its `.env`/state intact — the one recovery path that never risks re-registering. |
| `--reattach --key <key>` | Re-runs the full install pipeline, including a real license-server call keyed on the license key you supply. | Local files (`gateway.yaml`, secrets) were lost, but you still have the license key — recovers configuration without issuing a new license. |
| `--uninstall` | Stops the Gateway and deletes `/opt/bp-gateway` — `.env`, `gateway.yaml`, `credentials.txt`, everything local. **Irreversible for local files, no backup taken.** Does **not** revoke the license server-side; contact support@batchnepal.com to release it. | Decommissioning an install entirely. |
| `--doctor` | Writes a redacted diagnostic bundle (`docker compose ps`, `.env`/`gateway.yaml` with secrets stripped, recent logs, a health check) to `/tmp/bp-gateway-doctor-<timestamp>.txt`. | Attach to a support request — designed to be safe to share. |

## Troubleshooting

- **Health check**: `https://<your-gateway-domain>/health` should return
  `{"status":"ok", ...}` with a version number.
- **Logs**: `docker compose -f /opt/bp-gateway/docker-compose.yml logs -f`
- **"Gateway version is incompatible" at startup**: the installed
  BatchProjects version has been upgraded past what the current Gateway
  release supports. Run the update command above.
- **DNS**: if TLS provisioning fails on a dedicated domain, confirm the
  DNS record actually resolves to this server before retrying. An
  auto-provisioned domain resolves within a few minutes of activation; if
  it doesn't, re-run the install command to retry provisioning.
- **Stuck or broken local config**: try `--repair` first (no license
  involved); `--doctor` produces a bundle worth attaching if you need to
  ask for help.
