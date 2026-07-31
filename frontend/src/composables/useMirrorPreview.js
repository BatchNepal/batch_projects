// Session cache + fetch for the reference hover-preview.
// Wraps the EXISTING getMirrorSchema()/getMirrorValues() wrappers (utils/api.js,
// backed by board.py's get_mirror_values) — no field logic duplicated
// here, just caching and a neutral-state contract for the UI.
//
// Module-level (not per-component) so the cache survives a TaskDetail drawer
// being closed and reopened for the same task, or hovering the same doc from
// a different task — cached per doc name for the session.
import { getMirrorSchema, getMirrorValues } from '@/utils/api'

// The schema can differ per project (Currency fields stripped for
// a caller without view_money on THAT project), so the cache key includes
// project — a schema fetched while viewing a project where money is hidden
// must never leak into a different project's hover-preview.
const schemaPromiseByProject = new Map() // project (or '') -> promise
const valueCache = new Map() // "project::doctype::name" -> resolved preview object
const pending = new Map()    // same key -> in-flight promise (de-dupe concurrent hovers)

function loadSchema(project) {
  const key = project || ''
  if (!schemaPromiseByProject.has(key)) {
    schemaPromiseByProject.set(key, getMirrorSchema(project).catch(() => ({})))
  }
  return schemaPromiseByProject.get(key)
}

/**
 * Resolve a hover-preview for one ERPNext document. Never throws — an
 * unmirrored doctype or a permission-denied document both resolve to a
 * neutral state object, so callers never need a try/catch + error toast.
 *
 * Per docs/TODO-CALLS.md's resilience principle ("never cache a failure as
 * truth"): a genuine row-level permission denial (the call succeeded, the
 * row just wasn't in the response — a stable fact) is cached for the
 * session. A caught exception (network blip, backend restart, or a
 * doctype-level permission error we can't distinguish from a transient one)
 * is NOT cached, so the next hover retries instead of being stuck showing
 * "No access" forever from a blip.
 */
export async function fetchMirrorPreview(doctype, name, project) {
  const key = `${project || ''}::${doctype}::${name}`
  if (valueCache.has(key)) return valueCache.get(key)
  if (pending.has(key)) return pending.get(key)

  const promise = (async () => {
    const schema = await loadSchema(project)
    const fields = schema?.[doctype]
    if (!fields || !fields.length) {
      return { result: { state: 'unmirrored', doctype, name }, cacheable: true }
    }
    try {
      const rows = await getMirrorValues(doctype, [name], project)
      const row = rows?.[name]
      if (!row) {
        return { result: { state: 'no-access', doctype, name }, cacheable: true } // genuinely filtered out
      }
      return { result: { state: 'ready', doctype, name, fields, row }, cacheable: true }
    } catch (e) {
      return { result: { state: 'no-access', doctype, name }, cacheable: false } // transient — don't trust it
    }
  })().then(({ result, cacheable }) => {
    if (cacheable) valueCache.set(key, result)
    return result
  })

  pending.set(key, promise)
  const result = await promise
  pending.delete(key)
  return result
}
