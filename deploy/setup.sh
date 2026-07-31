#!/usr/bin/env bash
# Thin wrapper around the gateway installer, for discoverability — so
# someone browsing this repo's deploy/ folder finds it without needing to
# know about get.batchprojects.com or the separate (private) bp-gateway
# repo directly. Always fetches whatever's current; kept as a wrapper
# rather than a copy specifically so it can never drift/go stale.
#
# See gateway-setup.md in this folder for the full guide.
set -euo pipefail
curl -fsSL https://get.batchprojects.com/install.sh | bash -s -- "$@"
