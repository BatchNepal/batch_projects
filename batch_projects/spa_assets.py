import json
import os

import frappe

_manifest_cache = {}


def get_spa_entry():
    """Resolve the SPA's actual (content-hashed) entry filenames from Vite's
    build manifest, for the www/workspace.html and www/batch-projects.html
    templates.

    Previously the entry had a fixed name ("index.js") with a manually
    appended ?v=<mtime> query for cache-busting. Rollup's own chunk-to-chunk
    imports back into the entry (which happen for any code shared between
    App.vue and a lazy-loaded route — routine, not a misconfiguration) always
    use the bare output filename, which never matched the query-stringed URL
    the HTML used. The browser treated those as two different modules and
    ran the entry's top-level side effects (app mount, bootstrapBridge,
    connectRealtime, every boot-time API call) a second time. Content-hashing
    the entry like every other chunk makes all references resolve to the
    same URL, so there's nothing left to mismatch.
    """
    manifest_path = frappe.get_app_path(
        "batch_projects", "public", "frontend", ".vite", "manifest.json"
    )
    try:
        mtime = os.path.getmtime(manifest_path)
    except OSError:
        return {"js": "assets/index.js", "css": "assets/index.css"}

    cached = _manifest_cache.get(manifest_path)
    if cached and cached[0] == mtime:
        return cached[1]

    with open(manifest_path) as f:
        manifest = json.load(f)

    entry = manifest.get("index.html") or next(
        (v for v in manifest.values() if v.get("isEntry")), None
    )
    result = {
        "js": entry["file"],
        "css": (entry.get("css") or ["assets/index.css"])[0],
    } if entry else {"js": "assets/index.js", "css": "assets/index.css"}

    _manifest_cache[manifest_path] = (mtime, result)
    return result
