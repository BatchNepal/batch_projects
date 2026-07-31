/**
 * useGlobalShortcuts — single-key (no modifier) shortcut layer.
 *
 * Mounted once in the app shell (App.vue), not per-page. Keys are ignored
 * while focus is in an input/textarea/select/contenteditable, or while the
 * caller reports a blocking overlay is open (search palette, create-task
 * composer, onboarding, the cheat sheet itself, public routes) — the open
 * TaskDetail drawer is deliberately NOT blocking, since `A` targets it.
 */
import { onMounted, onBeforeUnmount } from 'vue'

const EDITABLE_TAGS = new Set(['INPUT', 'TEXTAREA', 'SELECT'])

function isEditableTarget(el) {
  if (!el) return false
  if (EDITABLE_TAGS.has(el.tagName)) return true
  if (el.isContentEditable) return true
  return !!el.closest?.('[contenteditable="true"]')
}

export function useGlobalShortcuts({ onCreate, onAssign, onCheatSheet, isBlocked } = {}) {
  function onKeydown(e) {
    if (e.defaultPrevented) return
    if (e.metaKey || e.ctrlKey || e.altKey) return // single-key only — Cmd+K etc. live elsewhere
    if (isEditableTarget(e.target)) return
    if (isBlocked?.()) return

    if (e.key === '?') {
      e.preventDefault()
      onCheatSheet?.()
      return
    }
    if (e.key.length !== 1) return // ignore Shift/Tab/arrows/etc.

    const key = e.key.toLowerCase()
    if (key === 'c') {
      e.preventDefault()
      onCreate?.()
    } else if (key === 'a') {
      e.preventDefault()
      onAssign?.()
    }
  }

  onMounted(() => document.addEventListener('keydown', onKeydown))
  onBeforeUnmount(() => document.removeEventListener('keydown', onKeydown))
}
