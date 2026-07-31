// Shared column-track definition for the Backlog spreadsheet-style table.
// BacklogTaskRow (data rows) and BacklogColumnBar (header/footer) MUST both
// build their `grid-template-columns` from this same function — that's what
// keeps header labels, row cells, and footer aggregates pixel-aligned
// regardless of per-row content (title length, badge count, status text).
const BASE = ['26px', '68px', '26px', 'minmax(0,1fr)'] // drag | key | type | title+meta
const TAIL = ['36px', '116px', '64px']                  // priority | status | assignees

export function blGridTemplate(columns) {
  const cols = [...BASE]
  if (columns.epic) cols.push('110px')
  if (columns.points) cols.push('64px')
  if (columns.actualPoints) cols.push('64px')
  if (columns.unplanned) cols.push('60px')
  cols.push(...TAIL)
  return cols.join(' ')
}
