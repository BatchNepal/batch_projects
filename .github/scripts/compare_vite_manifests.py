#!/usr/bin/env python3
"""Compare Vite manifests while ignoring machine-specific node_modules prefixes.

Some package-manager/symlink layouts cause Vite to record an absolute path before
``node_modules/`` for third-party assets. That path is not part of the deployed
artifact contract and differs across developer/CI machines. Everything from
``node_modules/`` onward, plus every other manifest field, must still match.

Strip to the LAST ``node_modules/`` occurrence, not the first: some external
dependency-storage layouts nest the real node_modules under a path that itself
contains the literal substring ``node_modules/`` (e.g. a shared cache directory
named .../node_modules/<workspace>/.../node_modules/pkg), which would otherwise
leave a machine-specific prefix in the "normalized" path and cause a false
mismatch.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def normalize(value):
    if isinstance(value, dict):
        return {normalize_key(k): normalize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [normalize(v) for v in value]
    if isinstance(value, str):
        return normalize_path(value)
    return value


def normalize_key(value: str) -> str:
    return normalize_path(value)


def normalize_path(value: str) -> str:
    marker = "node_modules/"
    idx = value.rfind(marker)
    return value[idx:] if idx >= 0 else value


def load(path: str):
    return normalize(json.loads(Path(path).read_text(encoding="utf-8")))


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: compare_vite_manifests.py <committed> <generated>", file=sys.stderr)
        return 2

    committed = load(sys.argv[1])
    generated = load(sys.argv[2])
    if committed == generated:
        return 0

    print("::error::Vite manifest differs after normalizing machine-specific node_modules prefixes.")
    print("The committed frontend build is stale; run 'yarn build' in frontend/ and commit the result.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
