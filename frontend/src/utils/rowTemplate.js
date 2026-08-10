// Resolves a Column widget's row_template (see RowDesignerModal.vue) + one
// real record into the ordered item lists WidgetRow.vue renders — the SAME
// function powers the designer's live preview and ColumnWidget.vue's real
// rendering, so "what you configured" and "what you get" can never drift
// into two hand-maintained copies.
//
// Which FIELDS go where is entirely up to you — an ordered list per line,
// drag anything anywhere, no cap. Which ROW you put something in decides
// its weight: line1 is the full headline (never truncated —
// WidgetRow just lets long text ellipsis), line2 is smaller secondary meta
// that collapses into a "+N" badge once it doesn't fit. The one fieldtype-
// driven (not position-driven) exception: a Date/Datetime field always
// renders in the dedicated date slot regardless of which line/position it
// was dropped on, because "Today"/"Tomorrow" formatting and right-alignment
// are a FORMAT concern, not a layout opinion.
//
// row_template shape:
//   { line1: [block, ...], line2: [block, ...], solo: block | null }
//   block, one of:
//     { kind: 'field', field, color, bg }
//       color / bg are the SAME shape, independently set:
//         null | { mode: 'flat', value: '#hex' }
//              | { mode: 'value_map', map: { rawValue: '#hex' }, fallback: '#hex' | null }
//       `color` paints the text, `bg` paints behind it. bg unset (the
//       default) stays fully transparent, so the neutral-chrome default is
//       never overridden unless someone deliberately picks a background —
//       and a status can be, say, dark green text on a pale green pill
//       because the two are separate choices rather than one derived from
//       the other. value_map's fallback covers any value NOT in map (a
//       status added after this was configured), checked after an exact hit.
//     { kind: 'avatar', source, field }
//       source: 'identity'   -> the doctype's own photo field (Frappe's
//                                meta.image_field — Customer/Lead/Contact/
//                                Supplier/Employee/Item all have one), or a
//                                hashed-color avatar from the record's own
//                                title if the doctype has none / it's unset
//                                (no field needed on the block itself)
//               'project'    -> BP Task's own project tile (Task rows only)
//               'assignees'  -> avatar stack (Task rows only — the only
//                                doctype this app renders multi-assignee for)
//               'field'      -> `field` names a real doctype field: an
//                                Attach Image/Image field renders the image
//                                directly, a Link field renders a hashed
//                                avatar keyed by that field's raw value
//   solo: any single field/avatar block (icon, image, avatar, project tile,
//     assignee stack, a text field — genuinely any kind, not avatar-only),
//     pulled out of line1/line2 to render as one big, row-height visual
//     beside the two-line text stack. `{ ...block, position:
//     'left' | 'right' }` — 'left' (the default) sits before the text
//     stack in reading order, 'right' pins it to the far corner instead.
export function resolveRowProps(template, record, ctx) {
  if (!template || (!template.line1?.length && !template.line2?.length && !template.solo)) return null

  let date = null
  function resolveBlock(blk) {
    if (blk.kind === 'avatar') return resolveAvatarBlock(blk, record, ctx)
    if (blk.kind !== 'field' || !blk.field) return null
    const raw = record?.[blk.field]
    const meta = ctx.fieldMeta(blk.field)
    if (meta?.fieldtype === 'Date' || meta?.fieldtype === 'Datetime') {
      if (raw) date = raw
      return null
    }
    if (raw == null || raw === '') return null
    const key = isUserLike(raw) ? (raw.full_name || raw.user) : raw
    return {
      kind: 'text',
      text: formatValue(raw, meta),
      color: resolveColor(blk.color, key),
      bg: resolveColor(blk.bg, key, null),
    }
  }
  function resolveLine(blocks) {
    return (blocks || []).map(resolveBlock).filter(Boolean)
  }

  const line1 = resolveLine(template.line1)
  const line2 = resolveLine(template.line2)
  const solo = template.solo ? resolveBlock(template.solo) : null
  if (solo) solo.position = template.solo.position === 'right' ? 'right' : 'left'

  // Nothing resolved to real content (e.g. every field was empty on this
  // particular record) — the caller's own fallback title keeps the row from
  // rendering completely blank.
  if (!line1.length && !line2.length && !solo) {
    line1.push({ kind: 'text', text: ctx.fallbackTitle(record), color: 'default' })
  }

  return { line1, line2, date, solo }
}

function resolveAvatarBlock(blk, record, ctx) {
  if (blk.source === 'identity') {
    // The doctype's own photo (Customer/Lead/Contact/Supplier/Employee/Item
    // all have one — see get_widget_source_fields' is_identity_image tag)
    // beats a hashed-initials avatar whenever the record actually has one
    // set; falls through to the hash avatar for doctypes with no photo
    // field, or a record that hasn't set one.
    const image = ctx.identityImageField ? record?.[ctx.identityImageField] : null
    if (image) return { kind: 'avatar-image', image, name: ctx.fallbackTitle(record) }
    return { kind: 'avatar-hash', name: ctx.fallbackTitle(record) }
  }
  if (blk.source === 'project') return ctx.projectAvatar ? ctx.projectAvatar(record) : null
  if (blk.source === 'assignees') return { kind: 'avatars', people: ctx.assignees ? ctx.assignees(record) : [] }
  if (blk.source === 'field' && blk.field) {
    const raw = record?.[blk.field]
    if (!raw) return null
    // Some Link-to-User fields (owner, notably — see get_doctype_column_data)
    // arrive pre-resolved as {user, full_name, user_image} for exactly this
    // avatar use case, not a bare username string — schema metadata alone
    // (Link field) can't tell you that, so check the actual shape.
    if (isUserLike(raw)) {
      const name = raw.full_name || raw.user || ''
      return raw.user_image ? { kind: 'avatar-image', image: raw.user_image, name } : { kind: 'avatar-hash', name }
    }
    const meta = ctx.fieldMeta(blk.field)
    if (meta?.fieldtype === 'Attach Image' || meta?.fieldtype === 'Image') {
      return { kind: 'avatar-image', image: raw, name: ctx.fallbackTitle(record) }
    }
    return { kind: 'avatar-hash', name: String(raw) }
  }
  return null
}

// A resolved {user, full_name, user_image} object — see resolveAvatarBlock's
// own comment. Guards String(raw) from ever producing "[object Object]".
function isUserLike(v) {
  return !!v && typeof v === 'object' && !Array.isArray(v) && ('full_name' in v || 'user' in v)
}

function formatValue(raw, meta) {
  if (isUserLike(raw)) return raw.full_name || raw.user || ''
  if (meta?.fieldtype === 'Check') return raw === 1 || raw === '1' ? 'Yes' : 'No'
  return String(raw)
}

function resolveColor(color, rawValue, fallback = 'default') {
  if (!color) return fallback
  if (color.mode === 'flat') return color.value || fallback
  if (color.mode === 'value_map') {
    return color.map?.[String(rawValue)] || color.fallback || fallback
  }
  return fallback
}

// Every fieldname a template actually references, so the caller can ask the
// backend to SELECT them. Without this the designer could offer any field
// while the query returned only its own hardcoded handful, and the block
// rendered blank with no error anywhere (see get_column_widget_data's
// extra_fields).
// `identityImageField` — the doctype's own designated photo field (Frappe's
// meta.image_field, see get_widget_source_fields), if the template uses a
// 'identity' avatar block anywhere. That block never names a field itself
// (it's "whatever this record's own identity is"), so without this the
// backend would never SELECT the photo column and resolveAvatarBlock's
// identity branch would have nothing to fall through to but the hashed
// avatar, even on a doctype that has a real photo.
export function templateFieldNames(template, identityImageField) {
  if (!template) return []
  const out = new Set()
  let usesIdentity = false
  const visit = (blk) => {
    if (!blk) return
    if (blk.field) out.add(blk.field)
    if (blk.kind === 'avatar' && blk.source === 'identity') usesIdentity = true
  }
  ;(template.line1 || []).forEach(visit)
  ;(template.line2 || []).forEach(visit)
  visit(template.solo)
  if (usesIdentity && identityImageField) out.add(identityImageField)
  return [...out]
}

// Every doctype field this app is ever likely to point a row block at, in
// one flat list a block can reference by fieldname — used by the designer
// to resolve a field's fieldtype/options for the color-mode decision
// (Select/fixed-options fields get an auto-populated per-value map; free-
// text fields get a single flat color) without a second lookup structure.
export function fieldMetaLookup(fields) {
  const byName = {}
  for (const f of fields || []) byName[f.fieldname] = f
  return (fieldname) => byName[fieldname] || null
}
