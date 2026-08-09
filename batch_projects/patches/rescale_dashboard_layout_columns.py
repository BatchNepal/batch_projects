"""DashboardView.vue's grid went from 12 columns to 48 (see stores/
dashboards.js' WIDGET_DEFAULTS comment) so resize/drag steps in ~10-15px
increments instead of ~110px ones. Every existing BP Dashboard.layout was
saved under the old 12-col scale — this multiplies each entry's x/w/minW by
4 (48/12) so widgets keep their exact rendered size and position under the
new column count. y/h/minH are row-height units, untouched by a column
rescale."""

import json

import frappe

COL_SCALE = 4


def execute():
    rows = frappe.get_all("BP Dashboard", filters={"layout": ["is", "set"]}, fields=["name", "layout"])
    migrated = 0
    skipped = 0
    for r in rows:
        try:
            layout = json.loads(r.layout) if isinstance(r.layout, str) else (r.layout or [])
        except (json.JSONDecodeError, TypeError):
            skipped += 1
            continue
        # Only a clean list-of-dicts is the current schema (see spa_assets.py /
        # DashboardView.vue's localLayout). A few dashboards on this box
        # predate that shape — an old save format that bundled
        # widgets/layout/scope together into ONE object inside this same
        # field, so json.loads(r.layout) here returns a dict, not a list.
        # Left untouched rather than guessed at; unrelated to this patch.
        if not isinstance(layout, list) or not layout or not all(isinstance(i, dict) for i in layout):
            skipped += 1
            continue
        for item in layout:
            item["x"] = (item.get("x") or 0) * COL_SCALE
            item["w"] = (item.get("w") or 0) * COL_SCALE
            if item.get("minW") is not None:
                item["minW"] = item["minW"] * COL_SCALE
        frappe.db.set_value("BP Dashboard", r.name, "layout", json.dumps(layout))
        migrated += 1
    frappe.db.commit()
    print(f"  Rescaled {migrated} dashboard layout(s) from 12-col to 48-col ({skipped} skipped — not the current layout-array shape)")
