/**
 * useOverlay — Zero-dependency overlay primitive for HeroUI Vue port.
 * Replaces reka-ui's Dialog/Popover/Tooltip/Dropdown primitives.
 *
 * Provides: Teleport, focus trap, Escape-to-close, click-outside,
 *           body scroll lock, trigger positioning.
 */
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick, readonly } from 'vue'

const FOCUSABLE = 'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'

export function useOverlay(options = {}) {
  const {
    initialOpen = false,
    dismissable = true,         // close on outside click
    closeOnEscape = true,
    trapFocus = true,
    lockScroll = true,          // body scroll lock for modals/drawers
    teleport = true,
    teleportTo = 'body',
    onOpen,
    onClose,
  } = options

  const open = ref(initialOpen)
  const triggerEl = ref(null)
  const overlayEl = ref(null)

  // ── Open / Close ──────────────────────────────────────────────────────────

  let restoreFocusEl = null
  let previousActiveElement = null

  function show() {
    if (open.value) return
    previousActiveElement = document.activeElement
    restoreFocusEl = document.activeElement
    open.value = true
    if (lockScroll) document.body.style.overflow = 'hidden'
    onOpen?.()
    nextTick(() => {
      if (trapFocus && overlayEl.value) trapFocusIn(overlayEl.value)
    })
  }

  function hide() {
    if (!open.value) return
    open.value = false
    if (lockScroll) document.body.style.overflow = ''
    onClose?.()
    if (restoreFocusEl) {
      nextTick(() => restoreFocusEl?.focus?.())
      restoreFocusEl = null
    }
  }

  function toggle() { open.value ? hide() : show() }

  // ── Focus trap ────────────────────────────────────────────────────────────

  function trapFocusIn(container) {
    const focusable = [...container.querySelectorAll(FOCUSABLE)]
    if (!focusable.length) return
    const first = focusable[0]
    const last = focusable[focusable.length - 1]
    first.focus?.()

    container.addEventListener('keydown', function trap(e) {
      if (e.key !== 'Tab') return
      if (e.shiftKey) {
        if (document.activeElement === first) { e.preventDefault(); last.focus?.() }
      } else {
        if (document.activeElement === last) { e.preventDefault(); first.focus?.() }
      }
    }, { once: false })
  }

  // ── Global keyboard / click handlers ──────────────────────────────────────

  function onKeydown(e) {
    if (e.key === 'Escape' && closeOnEscape && open.value) {
      e.stopPropagation()
      hide()
    }
  }

  function onOutsideClick(e) {
    if (!open.value || !dismissable) return
    // Only close if click is outside both trigger and overlay
    const target = e.target
    if (overlayEl.value && overlayEl.value.contains(target)) return
    if (triggerEl.value && triggerEl.value.contains(target)) return
    // Also check if click is inside a portal-rendered teleport target
    hide()
  }

  // ── Lifecycle ─────────────────────────────────────────────────────────────

  onMounted(() => {
    document.addEventListener('keydown', onKeydown, true)
    // Use pointerdown (not click) so it fires before the click that might re-open
    document.addEventListener('pointerdown', onOutsideClick, true)
  })

  onBeforeUnmount(() => {
    document.removeEventListener('keydown', onKeydown, true)
    document.removeEventListener('pointerdown', onOutsideClick, true)
    if (lockScroll) document.body.style.overflow = ''
  })

  // ── Return ────────────────────────────────────────────────────────────────

  return {
    open: readonly(open),
    triggerEl,
    overlayEl,
    show,
    hide,
    toggle,
  }
}

/**
 * useFloating — Lightweight anchor positioning.
 * Positions a floating element relative to a trigger element.
 */
export function useFloating(triggerRef, floatingRef, options = {}) {
  const {
    placement = 'bottom-start',
    offset = 4,
    matchWidth = false,
    maxHeight = null,
  } = options

  const floatingStyle = ref({})

  function updatePosition() {
    if (!triggerRef.value || !floatingRef.value) return
    const trigger = triggerRef.value.getBoundingClientRect()
    const floating = floatingRef.value.getBoundingClientRect()

    const [side, align = 'center'] = placement.split('-')
    const viewW = window.innerWidth
    const viewH = window.innerHeight
    const gap = offset

    let top = 0, left = 0

    // Vertical
    if (side === 'bottom') {
      top = trigger.bottom + gap
      if (top + floating.height > viewH - 8) top = trigger.top - floating.height - gap
    } else if (side === 'top') {
      top = trigger.top - floating.height - gap
      if (top < 8) top = trigger.bottom + gap
    } else {
      top = trigger.top + (trigger.height - floating.height) / 2
    }

    // Horizontal
    if (align === 'start') {
      left = trigger.left
    } else if (align === 'end') {
      left = trigger.right - floating.width
    } else {
      left = trigger.left + (trigger.width - floating.width) / 2
    }

    // Keep in viewport
    if (left + floating.width > viewW - 8) left = viewW - floating.width - 8
    if (left < 8) left = 8
    if (top < 8) top = 8

    floatingStyle.value = {
      position: 'fixed',
      top: `${top}px`,
      left: `${left}px`,
      zIndex: 100,
      ...(matchWidth ? { minWidth: `${trigger.width}px` } : {}),
      ...(maxHeight ? { maxHeight: `${maxHeight}px` } : {}),
    }
  }

  return { floatingStyle, updatePosition }
}
