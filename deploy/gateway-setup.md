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
**separate infrastructure**, depending on your environment:

- **Frappe Cloud**: always deployed on separate infrastructure, since
  Frappe Cloud does not host arbitrary services. Every configuration
  value the Gateway needs is available directly from the Frappe Cloud
  dashboard — no shell access required at any point.
- **Self-hosted, same server**: the installer detects whether ERPNext is
  running in Docker or as a bare bench and configures networking
  accordingly. It always shows what it detected and asks for confirmation
  before writing any configuration.
- **Self-hosted, separate server**: point the installer at your ERPNext
  URL, the same as the Frappe Cloud flow.

In every case, the Gateway is reachable at its own domain (or an
automatically generated one — see below), since the browser communicates
with it directly over HTTPS as a distinct origin.

## Installing

On the server where the Gateway will run — no license key is required to
begin; installations activate automatically on the Community plan, with
an upgrade available at any time from BatchProjects' own Billing page:

```bash
curl -fsSL https://get.batchprojects.com/install.sh | bash -s -- \
  --frappe https://yourcompany.com \
  --domain gateway.yourcompany.com
```

Organizations with an existing paid license key can supply it directly to
activate that tier immediately:

```bash
curl -fsSL https://get.batchprojects.com/install.sh | bash -s -- \
  --key BP-XXXX-XXXX-XXXX \
  --frappe https://yourcompany.com \
  --domain gateway.yourcompany.com
```

`deploy/setup.sh` in this folder runs the identical installer as a local
script, with the same options and behavior.

The installer requires:

- Your **ERPNext site URL** — prompted for if not supplied.
- A **domain or subdomain** pointed at this server, or none at all — the
  installer will generate a working one automatically (see below).

The installer will:

1. Verify Docker is present, offering to install it if not.
2. When co-located with ERPNext on the same server, detect whether it is
   running in Docker or as a bare bench, and confirm before proceeding.
3. Detect the installed BatchProjects version and automatically select
   the matching Gateway release.
4. Activate the deployment — automatically on the Community plan if no
   license key was supplied, or by validating the supplied key — and
   generate the Gateway's configuration.
5. Start the Gateway behind an automatically provisioned TLS endpoint.
6. Display three configuration values required by ERPNext (see below) —
   this step is not automatic and should not be skipped. Community-plan
   installations also receive a license key at this point; retain it for
   future reinstalls or support requests.

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
with the matching credentials to trust them. The installer displays three
key/value pairs on completion; where they are applied depends on how
ERPNext is hosted:

**Self-hosted, with shell access:**

```bash
bench --site <your-site> set-config bp_gateway_shared_secret "<value from installer>"
bench --site <your-site> set-config bp_bridge_bootstrap_secret "<value from installer>"
bench --site <your-site> set-config bp_scheduler_ingest_token "<value from installer>"
```

**Frappe Cloud:** open the site dashboard, navigate to **Settings → Site
Config**, add each of the three values, then select **Update
Configuration**. No shell access is required.

Until this step is complete, the Gateway operates normally, but ERPNext
is unable to verify that requests originated from it — premium features
that depend on this trust relationship will not function correctly.

## Updating

```bash
curl -fsSL https://get.batchprojects.com/install.sh | bash -s -- --update
```

Re-resolves the newest Gateway release compatible with the BatchProjects
version currently installed, applies it, and restarts the service.

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
