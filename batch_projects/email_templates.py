"""Premium email templates for batch_projects notifications.

Design language — quiet, typographic, product-notification style
────────────────────────────────────
• White card on a soft grey page; one 3px coloured top-rule encodes the
  notification type without words.
• Monospace breadcrumb header reads like it was sent by the *company* running
  the instance (dynamic brand), with a small "powered by batch_projects" credit
  in the footer — never a hard-coded vendor name.
• Issue title is the hero; an actor row (coloured initials avatar + sentence)
  states who did what; threaded context (status pills, comment quote, change
  table) is indented to the avatar gutter, giving every block one rhythm.
• One neutral ramp (#101828 → #98A2B3) and one semantic pill palette shared by
  every template, so "Done / Blocked / In Review" mean the same colour everywhere.
• Aggregate emails (digest / weekly / report) reuse a single stats-panel atom.
• Table-based, inline styles only, Outlook-safe. Subjects front-load the action.
"""

import frappe


# ─── PALETTE ──────────────────────────────────────────────────────────────────

_PAGE_BG   = "#F8F9FA"
_CARD_BG   = "#FFFFFF"
_BORDER    = "#E4E7EC"
_DIVIDER   = "#F2F4F7"
_FILL      = "#F2F4F7"
_INK       = "#101828"   # headings
_BODY      = "#344054"   # body text
_SECOND    = "#475467"   # secondary text
_MUTED     = "#667085"   # meta / labels
_FAINT     = "#98A2B3"   # faint / credit

_SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif"
_MONO = "ui-monospace,SFMono-Regular,'SF Mono',Menlo,Monaco,Consolas,monospace"

# 3px top-rule + key colour per notification type
_ACCENT = {
    "Assignment":    "#175CD3",
    "Unassigned":    "#667085",
    "Mention":       "#B54708",
    "Comment":       "#475467",
    "Status Change": "#027A48",
    "Unblocked":     "#027A48",
    "Task Deleted":  "#667085",
    "Finance":       "#027A48",
    "Update":        "#5925DC",
    "Due Soon":      "#B54708",
    "Overdue":       "#B42318",
    "Sprint":        "#0E7090",
    "Summary":       "#0E7090",
    "Digest":        "#101828",
    "Approval Requested": "#B54708",
    "Approval Decided":   "#027A48",
    "Role Changed":       "#175CD3",
    "Automation":         "#5925DC",
    "Automation Failed":  "#B42318",
    "Timer Reminder":     "#B54708",
}

# Shared semantic pill palette: kind -> (background, foreground)
_PILL = {
    "neutral": ("#F2F4F7", "#344054"),
    "blue":    ("#EFF8FF", "#175CD3"),
    "green":   ("#ECFDF3", "#027A48"),
    "amber":   ("#FFFAEB", "#B54708"),
    "red":     ("#FEF3F2", "#B42318"),
    "violet":  ("#F4F3FF", "#5925DC"),
    "cyan":    ("#ECFDFF", "#0E7090"),
}

_PRIORITY_COLOR = {
    "Low":      "#667085",
    "Medium":   "#0E7090",
    "High":     "#B54708",
    "Urgent":   "#B42318",
    "Critical": "#B42318",
}

# Deterministic coloured avatars keyed off the actor's name
_AVATAR = [
    ("#EFF8FF", "#175CD3"), ("#ECFDF3", "#027A48"), ("#FFFAEB", "#B54708"),
    ("#FEF3F2", "#B42318"), ("#F4F3FF", "#5925DC"), ("#ECFDFF", "#0E7090"),
    ("#FDF2FA", "#C11574"),
]

_FIELD_LABEL = {
    "priority":     "Priority",
    "due_date":     "Due date",
    "title":        "Title",
    "task_type":    "Type",
    "labels":       "Labels",
    "story_points": "Points",
    "resolution":   "Resolution",
    "start_date":   "Start date",
    "description":  "Description",
}


def _e(v) -> str:
    """HTML-escape; returns '' for None."""
    return frappe.utils.escape_html(str(v)) if v is not None else ""


def _brand_name() -> str:
    """The identity the email should appear to come from — the company / site
    running this instance, *not* the vendor. Falls back gracefully so the header
    never renders 'None'."""
    for getter in (
        lambda: frappe.defaults.get_global_default("company"),
        lambda: frappe.db.get_single_value("Website Settings", "app_name"),
        lambda: frappe.local.site,
    ):
        try:
            v = getter()
            if v:
                return str(v)
        except Exception:
            continue
    return "Projects"


def _status_kind(label: str) -> str:
    """Map a free-text status to a shared pill colour kind."""
    s = (label or "").lower()
    if any(w in s for w in ("done", "complete", "closed", "resolved", "shipped")):
        return "green"
    if any(w in s for w in ("review", "qa", "verify", "testing")):
        return "blue"
    if any(w in s for w in ("block", "stuck", "hold", "cancel")):
        return "red"
    if any(w in s for w in ("progress", "doing", "active")):
        return "blue"
    return "neutral"


# ─── SUBJECT LINES ────────────────────────────────────────────────────────────

def notification_subject(ntype: str, actor_name: str, task_key: str, task_title: str, **extras) -> str:
    """Return a tight, front-loaded subject line — action first."""
    title = task_title or "a task"
    actor = actor_name or "Someone"
    key   = f"[{task_key}] " if task_key else ""
    if ntype == "Assignment":
        return f"{key}{actor} assigned you to {title}"
    if ntype == "Unassigned":
        return f"{key}{actor} unassigned you from {title}"
    if ntype == "Comment":
        return f"{key}{actor} commented on {title}"
    if ntype == "Mention":
        return f"{key}{actor} mentioned you"
    if ntype == "Status Change":
        f, t = extras.get("from_status"), extras.get("to_status")
        if f and t:
            return f"{key}{f} → {t}"
        return f"{key}Status changed on {title}"
    if ntype == "Update":
        return f"{key}{actor} updated {title}"
    if ntype == "Due Soon":
        return f"{key}Due soon: {title}"
    if ntype == "Overdue":
        return f"{key}OVERDUE: {title}"
    if ntype == "Sprint":
        return f"Sprint update · {extras.get('project_name', 'Projects')}"
    if ntype == "Unblocked":
        return f"{key}Unblocked: {title}"
    if ntype == "Task Deleted":
        return f"{key}Deleted: {title}"
    if ntype == "Finance":
        return f"{extras.get('project_name') or 'Project'} · {title}"
    if ntype == "Approval Requested":
        return f"{key}{actor} requested your approval"
    if ntype == "Approval Decided":
        decision = extras.get("to_status") or "decided"
        return f"{key}{decision}: {title}"
    if ntype == "Role Changed":
        return f"{actor} gave you access to a project"
    if ntype == "Automation":
        return f"{key}Automation update on {title}"
    if ntype == "Automation Failed":
        return f"Automation failed — action needed"
    if ntype == "Timer Reminder":
        return f"{key}Timer still running on {title}"
    return f"{key}{title}"


# ─── BASE SHELL ───────────────────────────────────────────────────────────────

def _shell(breadcrumb_html: str, body_html: str, footer_html: str, accent: str = "#175CD3") -> str:
    """Outer card: 3px type top-rule + breadcrumb + body, muted footer outside."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Projects</title>
<!--[if mso]><noscript><xml><o:OfficeDocumentSettings><o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml></noscript><![endif]-->
</head>
<body style="margin:0;padding:0;background:{_PAGE_BG};-webkit-font-smoothing:antialiased;mso-line-height-rule:exactly;">

<table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%"
       style="background:{_PAGE_BG};min-width:320px;">
<tr><td style="padding:40px 16px;" align="center">

  <table role="presentation" cellspacing="0" cellpadding="0" border="0"
         style="width:100%;max-width:600px;background:{_CARD_BG};border-radius:6px;
                border:1px solid {_BORDER};overflow:hidden;
                box-shadow:0 1px 2px rgba(16,24,40,0.04);">

    <!-- type top-rule -->
    <tr><td style="height:3px;line-height:3px;font-size:0;background:{accent};">&nbsp;</td></tr>

    <!-- breadcrumb + body -->
    <tr>
      <td style="font-family:{_SANS};">
        {breadcrumb_html}{body_html}
      </td>
    </tr>

  </table>

  <!-- footer (outside the card) -->
  <table role="presentation" cellspacing="0" cellpadding="0" border="0"
         style="width:100%;max-width:600px;text-align:left;">
    <tr>
      <td style="padding:18px 4px 0;font-family:{_SANS};">
        {footer_html}
      </td>
    </tr>
  </table>

</td></tr>
</table>
</body>
</html>"""


# ─── ATOMS ────────────────────────────────────────────────────────────────────

def _breadcrumb(parts: list) -> str:
    """Monospace uppercase context trail — leads with the dynamic brand."""
    sep = '&nbsp;&rsaquo;&nbsp;'
    trail = sep.join(_e(p) for p in parts if p)
    return (
        f'<div style="padding:22px 24px 0;">'
        f'<span style="font-family:{_MONO};font-size:11px;font-weight:600;'
        f'color:{_MUTED};text-transform:uppercase;letter-spacing:0.04em;">{trail}</span>'
        f'</div>'
    )


def _title(text: str) -> str:
    return (
        f'<div style="padding:8px 24px 0;">'
        f'<div style="font-size:19px;font-weight:600;line-height:1.4;'
        f'color:{_INK};letter-spacing:-0.2px;">{_e(text or "(no title)")}</div></div>'
    )


def _avatar(name: str) -> str:
    initials = "".join(w[0] for w in (name or "?").split()[:2]).upper() or "?"
    bg, fg = _AVATAR[sum(map(ord, name or "?")) % len(_AVATAR)]
    return (
        f'<table role="presentation" cellspacing="0" cellpadding="0" border="0">'
        f'<tr><td align="center" valign="middle" '
        f'style="width:32px;height:32px;background:{bg};border-radius:4px;'
        f'font-size:12px;font-weight:600;color:{fg};">{_e(initials)}</td></tr></table>'
    )


def _actor(name: str, action_html: str) -> str:
    """Coloured initials avatar + 'Name [did something]' sentence."""
    return (
        f'<div style="padding:18px 24px 0;">'
        f'<table role="presentation" cellspacing="0" cellpadding="0" border="0">'
        f'<tr>'
        f'<td width="32" valign="middle" style="padding-right:12px;">{_avatar(name)}</td>'
        f'<td valign="middle" style="font-size:14px;line-height:1.45;color:{_SECOND};">'
        f'<strong style="color:{_INK};font-weight:600;">{_e(name)}</strong>&nbsp;{action_html}</td>'
        f'</tr></table></div>'
    )


def _lead(html: str) -> str:
    """Avatar-less lead sentence (due/overdue/generic)."""
    return (
        f'<div style="padding:18px 24px 0;">'
        f'<p style="margin:0;font-size:14px;line-height:1.5;color:{_SECOND};">{html}</p></div>'
    )


def _pill(label: str, kind: str = "neutral") -> str:
    bg, fg = _PILL.get(kind, _PILL["neutral"])
    return (
        f'<span style="display:inline-block;background:{bg};color:{fg};'
        f'font-family:{_MONO};font-size:11px;font-weight:700;padding:3px 8px;'
        f'border-radius:4px;text-transform:uppercase;letter-spacing:0.02em;'
        f'vertical-align:middle;">{_e(label)}</span>'
    )


def _transition(from_label: str, to_label: str) -> str:
    return (
        f'<div style="padding:14px 24px 0 56px;">'
        f'{_pill(from_label, _status_kind(from_label))}'
        f'<span style="padding:0 8px;color:{_FAINT};font-size:13px;vertical-align:middle;">&rarr;</span>'
        f'{_pill(to_label, _status_kind(to_label))}</div>'
    )


def _quote(text: str) -> str:
    if not text:
        return ""
    t = text.strip()
    preview = t[:280]
    ell = "&thinsp;…" if len(t) > 280 else ""
    return (
        f'<div style="padding:14px 24px 0 56px;">'
        f'<div style="border-left:2px solid {_BORDER};padding-left:12px;'
        f'font-size:14px;line-height:1.6;color:{_BODY};">{_e(preview)}{ell}</div></div>'
    )


def _meta(items: list) -> str:
    """Small label+value chips. items = [(label, value, color)]"""
    cells = "".join(
        f'<td style="padding-right:22px;white-space:nowrap;vertical-align:middle;">'
        f'<span style="font-size:11px;color:{_MUTED};">{_e(lbl)}&thinsp;</span>'
        f'<span style="font-size:12px;font-weight:600;color:{col};">{_e(val)}</span></td>'
        for lbl, val, col in items if val
    )
    if not cells:
        return ""
    return (
        f'<div style="padding:14px 24px 0 56px;">'
        f'<table role="presentation" cellspacing="0" cellpadding="0" border="0">'
        f'<tr>{cells}</tr></table></div>'
    )


def _change_table(changes: list) -> str:
    """Old (strikethrough) → new table for task.updated emails."""
    rows = ""
    for c in changes:
        field  = c.get("field", "")
        from_v = c.get("from")
        to_v   = c.get("to")

        if field.startswith("cf:"):
            label = field[3:].replace("_", " ").title()
        else:
            label = _FIELD_LABEL.get(field, field.replace("_", " ").title())

        if field == "description":
            value_html = f'<em style="color:{_MUTED};font-size:12px;">description updated</em>'
        elif field == "priority":
            t_col = _PRIORITY_COLOR.get(str(to_v), _INK) if to_v else _INK
            old = (f'<span style="text-decoration:line-through;color:{_FAINT};'
                   f'font-size:12px;">{_e(from_v)}</span>&thinsp;→&thinsp;') if from_v else ""
            value_html = f'{old}<span style="font-weight:600;color:{t_col};font-size:13px;">{_e(to_v)}</span>'
        else:
            if isinstance(from_v, list) or isinstance(to_v, list):
                fs = ", ".join(str(x) for x in (from_v or [])) or "—"
                ts = ", ".join(str(x) for x in (to_v or [])) or "—"
            else:
                fs = str(from_v) if from_v not in (None, "") else "—"
                ts = str(to_v) if to_v not in (None, "") else "—"
            value_html = (f'<span style="text-decoration:line-through;color:{_FAINT};font-size:12px;">{_e(fs)}</span>'
                          f'&thinsp;→&thinsp;<span style="font-weight:600;color:{_INK};font-size:13px;">{_e(ts)}</span>')

        rows += (
            f'<tr>'
            f'<td style="padding:5px 14px 5px 0;font-size:11px;color:{_MUTED};'
            f'white-space:nowrap;vertical-align:top;width:82px;">{_e(label)}</td>'
            f'<td style="padding:5px 0;vertical-align:top;">{value_html}</td></tr>'
        )

    if not rows:
        return ""
    return (
        f'<div style="padding:14px 24px 0 56px;">'
        f'<table role="presentation" cellspacing="0" cellpadding="0" border="0" '
        f'style="border-collapse:collapse;">{rows}</table></div>'
    )


def _cta(primary: tuple, secondary: tuple = None, left: int = 24, primary_bg: str = "#101828") -> str:
    purl, plabel = primary
    html = (
        f'<a href="{purl}" target="_blank" rel="noopener" '
        f'style="display:inline-block;background:{primary_bg};color:#ffffff;'
        f'text-decoration:none;font-size:13px;font-weight:600;padding:9px 16px;'
        f'border-radius:6px;letter-spacing:0.01em;">{_e(plabel)}</a>'
    )
    if secondary:
        surl, slabel = secondary
        html += (
            f'<a href="{surl}" target="_blank" rel="noopener" '
            f'style="display:inline-block;margin-left:8px;color:{_SECOND};'
            f'text-decoration:none;font-size:13px;font-weight:600;padding:9px 14px;'
            f'border-radius:6px;border:1px solid #D0D5DD;">{_e(slabel)}</a>'
        )
    return f'<div style="padding:22px 24px 26px {left}px;">{html}</div>'


def _footer(reason_html: str, manage_url: str, manage_label: str = "Manage notifications") -> str:
    return (
        f'<div style="font-size:12px;color:{_MUTED};line-height:1.6;">{reason_html}&ensp;'
        f'<a href="{manage_url}" style="color:{_MUTED};text-decoration:underline;">{_e(manage_label)}</a></div>'
        f'<div style="margin-top:6px;font-size:11px;color:{_FAINT};">'
        f'Sent by {_e(_brand_name())}&nbsp;&middot;&nbsp;powered by batch_projects</div>'
    )


# ─── PER-TYPE NOTIFICATION BUILDERS ──────────────────────────────────────────

def build_notification_email(
    ntype: str,
    actor_name: str,
    task_key: str,
    task_title: str,
    message: str,
    url: str,
    manage_url: str,
    comment_text: str = None,
    changes: list = None,
    priority: str = None,
    due_date=None,
    from_status: str = None,
    to_status: str = None,
) -> str:
    """Return a complete HTML email string for one notification event."""
    accent = _ACCENT.get(ntype, _MUTED)
    brand  = _brand_name()
    crumb  = _breadcrumb([brand, task_key]) if task_key else _breadcrumb([brand])

    # ── Assignment ────────────────────────────────────────────────────────────
    if ntype == "Assignment":
        meta = []
        if priority:
            meta.append(("Priority", priority, _PRIORITY_COLOR.get(priority, _INK)))
        if due_date:
            meta.append(("Due", str(due_date), _INK))
        body = (
            _title(task_title)
            + _actor(actor_name, "assigned this to you")
            + _meta(meta)
            + _cta((url, "View task"), left=56)
        )
        foot = _footer("You were assigned to this task.", manage_url)

    # ── Unassigned ────────────────────────────────────────────────────────────
    elif ntype == "Unassigned":
        body = (
            _title(task_title)
            + _actor(actor_name, "unassigned you from this task")
            + _cta((url, "View task"), left=56)
        )
        foot = _footer("You were removed from this task.", manage_url)

    # ── Mention ───────────────────────────────────────────────────────────────
    elif ntype == "Mention":
        body = (
            _title(task_title)
            + _actor(actor_name, f'<strong style="color:{accent};">@mentioned</strong> you')
            + _quote(comment_text)
            + _cta((url, "View mention"), (url, "Open task"), left=56)
        )
        foot = _footer("You were mentioned in this task.", manage_url)

    # ── Comment ───────────────────────────────────────────────────────────────
    elif ntype == "Comment":
        body = (
            _title(task_title)
            + _actor(actor_name, "left a comment")
            + _quote(comment_text)
            + _cta((url, "Reply to comment"), (url, "Open task"), left=56)
        )
        foot = _footer("You're watching this task.", manage_url)

    # ── Status Change ─────────────────────────────────────────────────────────
    elif ntype == "Status Change":
        if from_status and to_status:
            body = (
                _title(task_title)
                + _actor(actor_name, "changed the status")
                + _transition(from_status, to_status)
                + _cta((url, "View task"), left=56)
            )
        else:
            body = (
                _title(task_title)
                + _actor(actor_name, "changed the status")
                + _cta((url, "View task"), left=56)
            )
        foot = _footer("You're watching this task.", manage_url)

    # ── Update (field changes) ────────────────────────────────────────────────
    elif ntype == "Update":
        _NOTABLE = {"priority", "due_date", "title", "task_type",
                    "labels", "story_points", "description"}
        notable = [c for c in (changes or []) if c.get("field") in _NOTABLE]
        if len(notable) == 1:
            fl = _FIELD_LABEL.get(notable[0].get("field", ""), "a field").lower()
            action = f'updated <strong style="color:{_INK};">{_e(fl)}</strong>'
        else:
            action = "updated this task"
        body = (
            _title(task_title)
            + _actor(actor_name, action)
            + _change_table(notable)
            + _cta((url, "View task"), left=56)
        )
        foot = _footer("You're watching this task.", manage_url)

    # ── Due Soon ──────────────────────────────────────────────────────────────
    elif ntype == "Due Soon":
        due_str = (f'<span style="color:{accent};font-weight:600;">{_e(str(due_date))}</span>'
                   if due_date else f'<span style="color:{accent};font-weight:600;">soon</span>')
        body = (
            _title(task_title)
            + _lead(f'This task is due {due_str}.')
            + _cta((url, "View task"), left=24)
        )
        foot = _footer("You're assigned to or watching this task.", manage_url)

    # ── Overdue ───────────────────────────────────────────────────────────────
    elif ntype == "Overdue":
        body = (
            _title(task_title)
            + _lead(f'This task is <strong style="color:{accent};">overdue</strong>.')
            + _cta((url, "View task"), left=24, primary_bg=accent)
        )
        foot = _footer("You're assigned to or watching this task.", manage_url)

    # ── Sprint ────────────────────────────────────────────────────────────────
    elif ntype == "Sprint":
        body = (
            _lead(f'<strong style="color:{_INK};">{_e(actor_name)}</strong>&nbsp;{_e(message)}')
            + _cta((url, "View board"), left=24, primary_bg=accent)
        )
        foot = _footer("You're a member of this project.", manage_url)

    # ── Approval Requested ───────────────────────────────────────────────────
    elif ntype == "Approval Requested":
        body = (
            _title(task_title)
            + _actor(actor_name, f'<strong style="color:{accent};">requested your approval</strong> on this task')
            + _cta((url, "Review & decide"), left=56, primary_bg=accent)
        )
        foot = _footer("You were named as the approver on this task.", manage_url)

    # ── Approval Decided ─────────────────────────────────────────────────────
    elif ntype == "Approval Decided":
        if from_status and to_status:
            body = (
                _title(task_title)
                + _actor(actor_name, "decided the approval")
                + _transition(from_status, to_status)
                + _cta((url, "View task"), left=56)
            )
        else:
            body = (
                _title(task_title)
                + _actor(actor_name, "decided the approval")
                + _cta((url, "View task"), left=56)
            )
        foot = _footer("You're watching this task.", manage_url)

    # ── Unblocked (every blocker on this task is now done) ──────────────────
    elif ntype == "Unblocked":
        body = (
            _title(task_title)
            + _lead(_e(message))
            + _pill("Ready to start", "green")
            + _cta((url, "Open task"), left=24, primary_bg=accent)
        )
        foot = _footer("You're assigned to or watching this task.", manage_url)

    # ── Task Deleted (a task you followed was removed) ──────────────────────
    elif ntype == "Task Deleted":
        body = (
            _title(task_title)
            + _lead(_e(message))
            + _cta((url, "Open project"), left=24, primary_bg=accent)
        )
        foot = _footer("You were assigned to or watching this task.", manage_url)

    # ── Finance (erp.* money events) ────────────────────────────────────────
    elif ntype == "Finance":
        body = (
            _title(task_title)
            + _lead(_e(message))
            + (_pill(task_key, "green") if task_key else "")
            + _cta((url, "Open project"), left=24, primary_bg=accent)
        )
        foot = _footer("You manage this project's money.", manage_url)

    # ── Role Changed (added to / re-roled on a project) ─────────────────────
    elif ntype == "Role Changed":
        role_line = (
            _transition(from_status, to_status) if from_status
            else _meta([("Role", to_status or "", accent)])
        )
        body = (
            _lead(f'<strong style="color:{_INK};">{_e(actor_name)}</strong>&nbsp;gave you access to this project.')
            + role_line
            + _cta((url, "Open project"), left=24, primary_bg=accent)
        )
        foot = _footer("Your project access changed.", manage_url)

    # ── Automation ────────────────────────────────────────────────────────────
    elif ntype == "Automation":
        if task_title:
            body = (
                _title(task_title)
                + _lead(_e(message))
                + _cta((url, "View task"), left=24, primary_bg=accent)
            )
        else:
            body = _lead(_e(message)) + _cta((url, "View project"), left=24, primary_bg=accent)
        foot = _footer("An automation rule in this project ran an action.", manage_url)

    # ── Automation Failed ────────────────────────────────────────────────────
    elif ntype == "Automation Failed":
        body = (
            _lead(f'<strong style="color:{accent};">{_e(message)}</strong>')
            + _cta((url, "Check run history"), left=24, primary_bg=accent)
        )
        foot = _footer("You own this automation rule.", manage_url)

    # ── Timer Reminder ───────────────────────────────────────────────────────
    elif ntype == "Timer Reminder":
        body = (
            _title(task_title)
            + _lead(_e(message))
            + _cta((url, "Open task"), left=24, primary_bg=accent)
        )
        foot = _footer("You have a timer running on this task.", manage_url)

    # ── Generic fallback ──────────────────────────────────────────────────────
    else:
        body = _lead(_e(message)) + _cta((url, "Open task"), left=24)
        foot = _footer("You have a new notification.", manage_url)

    return _shell(crumb, body, foot, accent)


# ─── PHASE 16 — CUSTOM TEMPLATE SHELL ─────────────────────────────────────────
# Same "why you got this" footer text as each build_notification_email branch
# above — a custom (BP Notification Template) override replaces the message
# CONTENT, not this reasoning, so it stays consistent whichever path rendered
# the email.
_FOOTER_REASON = {
    "Assignment":     "You were assigned to this task.",
    "Unassigned":     "You were removed from this task.",
    "Mention":        "You were mentioned in this task.",
    "Comment":        "You're watching this task.",
    "Status Change":  "You're watching this task.",
    "Update":         "You're watching this task.",
    "Due Soon":       "You're assigned to or watching this task.",
    "Overdue":        "You're assigned to or watching this task.",
    "Sprint":         "You're a member of this project.",
    "Unblocked":      "You're assigned to or watching this task.",
    "Task Deleted":   "You were assigned to or watching this task.",
    "Finance":        "You manage this project's money.",
    "Approval Requested": "You were named as the approver on this task.",
    "Approval Decided":   "You're watching this task.",
    "Role Changed":       "Your project access changed.",
    "Automation":         "An automation rule in this project ran an action.",
    "Automation Failed":  "You own this automation rule.",
    "Timer Reminder":     "You have a timer running on this task.",
}


def build_custom_notification_email(ntype: str, task_key: str, body_html: str, manage_url: str) -> str:
    """Wrap an admin-authored (BP Notification Template) body in the
    SAME shell/breadcrumb/footer chrome build_notification_email uses, so a
    custom template overrides message content — not brand chrome."""
    accent = _ACCENT.get(ntype, _MUTED)
    crumb = _breadcrumb([_brand_name(), task_key]) if task_key else _breadcrumb([_brand_name()])
    foot = _footer(_FOOTER_REASON.get(ntype, "You have a new notification."), manage_url)
    return _shell(crumb, body_html, foot, accent)


# ─── SHARED STATS PANEL ───────────────────────────────────────────────────────

def _stat_panel(stats: list) -> str:
    """Centered stat cells with dividers. stats = [(num, label, color)]"""
    n = len(stats) or 1
    cells = ""
    for i, (num, label, color) in enumerate(stats):
        border = "" if i == n - 1 else f"border-right:1px solid #EAECF0;"
        cells += (
            f'<td style="text-align:center;padding:16px 12px;{border}width:{100 // n}%;">'
            f'<div style="font-size:24px;font-weight:700;color:{color};line-height:1;">{_e(num)}</div>'
            f'<div style="font-size:10px;font-weight:600;color:{_MUTED};margin-top:5px;'
            f'text-transform:uppercase;letter-spacing:0.06em;">{_e(label)}</div></td>'
        )
    return (
        f'<table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" '
        f'style="background:#F9FAFB;border:1px solid #EAECF0;border-radius:8px;'
        f'border-collapse:separate;">{cells and f"<tr>{cells}</tr>"}</table>'
    )


# ─── DIGEST EMAIL ─────────────────────────────────────────────────────────────

def _task_row(t: dict, base_url: str) -> str:
    key   = frappe.db.get_value("BP Project", t.get("project"), "key") if t.get("project") else ""
    turl  = (f"{base_url}/workspace/{key}/board?task={t.get('task_key', '')}" if key else base_url)
    tkey  = t.get("task_key") or ""
    title = t.get("title") or ""
    due   = t.get("due_date")
    due_html = (f'<span style="font-size:11px;color:{_FAINT};">&thinsp;· due {_e(str(due))}</span>'
                if due else "")
    return (
        f'<tr><td style="padding:7px 0;border-bottom:1px solid {_DIVIDER};">'
        f'<a href="{turl}" style="text-decoration:none;">'
        f'<span style="font-family:{_MONO};font-size:11px;font-weight:600;'
        f'color:{_FAINT};margin-right:9px;">{_e(tkey)}</span>'
        f'<span style="font-size:13px;color:{_INK};font-weight:500;">{_e(title)}</span>'
        f'</a>{due_html}</td></tr>'
    )


def _task_section(title: str, tasks: list, color: str, base_url: str, limit: int = 8) -> str:
    if not tasks:
        return ""
    rows = "".join(_task_row(t, base_url) for t in tasks[:limit])
    extra = (f'<tr><td style="padding:6px 0;font-size:12px;color:{_FAINT};">'
             f'+{len(tasks) - limit} more</td></tr>') if len(tasks) > limit else ""
    return (
        f'<div style="margin-bottom:22px;">'
        f'<div style="font-size:10.5px;font-weight:700;color:{color};'
        f'letter-spacing:0.07em;text-transform:uppercase;margin-bottom:8px;">'
        f'{_e(title)}&thinsp;({len(tasks)})</div>'
        f'<table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">'
        f'{rows}{extra}</table></div>'
    )


def build_digest_email(user_name: str, due_today: list, overdue: list,
                       open_tasks: list, unread: int, base_url: str) -> str:
    import datetime
    h = datetime.datetime.now().hour
    greeting = "morning" if h < 12 else "afternoon" if h < 17 else "evening"
    date_label = frappe.utils.formatdate(frappe.utils.today(), "d MMMM yyyy")
    unread_note = (f'&ensp;·&ensp;<span style="color:{_FAINT};">{unread} unread</span>'
                   if unread else "")

    sections = (
        _task_section("Overdue",    overdue,    "#B42318", base_url)
        + _task_section("Due today",  due_today,  "#B54708", base_url)
        + _task_section("Your tasks", open_tasks, _MUTED,    base_url, limit=6)
    )
    my_tasks_url = f"{base_url}/workspace/my-tasks"
    manage_url   = f"{base_url}/workspace/account"

    crumb = _breadcrumb([_brand_name(), "Daily digest"])
    body = (
        f'<div style="padding:22px 24px 24px;">'
        f'<p style="margin:0 0 3px;font-size:12px;color:{_FAINT};">{_e(date_label)}{unread_note}</p>'
        f'<h2 style="margin:0 0 22px;font-size:20px;font-weight:700;color:{_INK};">'
        f'Good {greeting}, {_e(user_name)}</h2>'
        f'{sections}'
        f'<a href="{my_tasks_url}" target="_blank" '
        f'style="display:inline-block;background:{_INK};color:#ffffff;text-decoration:none;'
        f'font-size:13px;font-weight:600;padding:10px 20px;border-radius:6px;margin-top:4px;">'
        f'Open My Tasks&nbsp;&rsaquo;</a></div>'
    )
    foot = _footer("Your daily task digest.", manage_url, "Manage preferences")
    return _shell(crumb, body, foot, _ACCENT["Digest"])


# ─── WEEKLY PROJECT SUMMARY ───────────────────────────────────────────────────

def build_weekly_email(project_name: str, done: int, created: int,
                       open_count: int, overdue: int) -> str:
    crumb = _breadcrumb([_brand_name(), project_name, "Weekly"])
    body = (
        f'<div style="padding:22px 24px 24px;">'
        f'<p style="margin:0 0 3px;font-size:11px;color:{_FAINT};letter-spacing:0.07em;'
        f'text-transform:uppercase;">Weekly summary</p>'
        f'<h2 style="margin:0 0 20px;font-size:18px;font-weight:700;color:{_INK};">'
        f'{_e(project_name)}</h2>'
        + _stat_panel([
            (done,       "Completed", "#027A48"),
            (created,    "Created",   "#175CD3"),
            (open_count, "Open",      _SECOND),
            (overdue,    "Overdue",   "#B42318"),
        ])
        + f'</div>'
    )
    foot = _footer("Weekly project summary.",
                   frappe.utils.get_url("/workspace/account"), "Manage preferences")
    return _shell(crumb, body, foot, _ACCENT["Summary"])


# ─── SCHEDULED REPORT EMAIL ──────────────────────────────────────────────────

def build_report_email(report_name: str, scope: str, period: str,
                       status_breakdown: list, total: int,
                       created: int, completed: int, url: str) -> str:
    chips = "".join(
        f'<span style="display:inline-block;margin:3px 5px 3px 0;padding:3px 9px;'
        f'border-radius:20px;font-size:11px;font-weight:600;'
        f'background:{(s.get("color") or _MUTED)}1a;color:{(s.get("color") or _MUTED)};">'
        f'{_e(s.get("name", ""))}: {s.get("count", 0)}</span>'
        for s in (status_breakdown or [])[:8] if s.get("count")
    )

    crumb = _breadcrumb([_brand_name(), "Reports"])
    body = (
        f'<div style="padding:22px 24px 24px;">'
        f'<p style="margin:0 0 2px;font-size:11px;color:{_FAINT};letter-spacing:0.07em;'
        f'text-transform:uppercase;">Scheduled report</p>'
        f'<h2 style="margin:0 0 3px;font-size:18px;font-weight:700;color:{_INK};">'
        f'{_e(report_name)}</h2>'
        f'<p style="margin:0 0 18px;font-size:13px;color:{_MUTED};">'
        f'{_e(scope)}&ensp;·&ensp;{_e((period or "").replace("_", " "))}</p>'
        + _stat_panel([
            (total,     "Total",   "#175CD3"),
            (completed, "Done",    "#027A48"),
            (created,   "Created", "#0E7090"),
        ])
        + (f'<div style="margin:18px 0 0;">{chips}</div>' if chips else "")
        + f'<div style="margin-top:18px;">'
          f'<a href="{url}" target="_blank" '
          f'style="display:inline-block;background:{_INK};color:#ffffff;text-decoration:none;'
          f'font-size:13px;font-weight:600;padding:10px 20px;border-radius:6px;">'
          f'Open full report&nbsp;&rsaquo;</a></div>'
        + f'</div>'
    )
    foot = _footer("Scheduled report delivery.",
                   frappe.utils.get_url("/workspace/account"), "Manage preferences")
    return _shell(crumb, body, foot, _ACCENT["Summary"])
