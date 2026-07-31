import { ref } from 'vue'

/**
 * Interface density (UI scale). Persisted per browser in localStorage and
 * applied as a `data-density` attribute on <html>, which index.css turns into
 * a root `zoom`. Default is "comfortable" (roomier) — "compact" is the original
 * dense baseline for power users.
 */
const KEY = 'bp_density'
const VALID = ['comfortable', 'compact']

const stored = localStorage.getItem(KEY)
const density = ref(VALID.includes(stored) ? stored : 'comfortable')

function apply(d) {
  document.documentElement.dataset.density = d
}

/** Call once, as early as possible, to avoid a flash of the wrong scale. */
export function initDensity() {
  apply(density.value)
}

export function useDensity() {
  function setDensity(d) {
    if (!VALID.includes(d) || d === density.value) return
    density.value = d
    localStorage.setItem(KEY, d)
    apply(d)
  }
  return { density, setDensity }
}
