// Shared formatting for BP mirror-column / reference-preview values —
// the display half of get_mirror_values (board.py). Used by
// ListView.vue's mirror columns and the reference hover-preview
// so both render the same doc's fields identically.

export function formatMirrorValue(val, fieldtype, rec) {
  if (val == null || val === '') return ''
  if (fieldtype === 'Currency') {
    try {
      return new Intl.NumberFormat(undefined, {
        style: 'currency', currency: rec?.currency || 'INR', maximumFractionDigits: 0,
      }).format(Number(val))
    } catch (e) {
      return Number(val).toLocaleString(undefined, { maximumFractionDigits: 0 })
    }
  }
  if (fieldtype === 'Percent') return Math.round(Number(val)) + '%'
  if (fieldtype === 'Date') {
    const d = new Date(val)
    return isNaN(d) ? String(val) : d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  }
  return String(val)
}
