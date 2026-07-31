/**
 * useGanttScale — the ONE date↔px source of truth for the Gantt (Phase
 * 7B-XL doctrine point 4). Everything else on the chart (bar left/width,
 * day-grid cells, today line, arrows) derives its geometry by calling
 * xOf()/dateOf() here rather than doing its own dayW math.
 *
 * Two distinct zoom paths, deliberately different:
 *  - setPreset()/fitToRange(): NOT pointer-tracked, so they animate dayW
 *    over ~120ms (rAF, ease-out) — this is where easing belongs.
 *  - zoomAboutPointer(): IS pointer-tracked (live wheel/pinch), so dayW
 *    and the compensating scrollLeft are set synchronously, every event,
 *    with no transition — an eased trailing animation here is exactly the
 *    "laggy-floaty" feel the doctrine rejects.
 */
import { ref, computed } from 'vue'

export const MIN_DAYW = 3
export const MAX_DAYW = 120
const DAY_MS = 86400000
const ANIM_MS = 120

export const ZOOM_PRESETS = {
  day: 34, week: 16, month: 6, quarter: 3,
}

export function useGanttScale(initialDayW = 32) {
  const dayW = ref(initialDayW)
  let raf = null

  function _stopAnim() {
    if (raf) { cancelAnimationFrame(raf); raf = null }
  }

  /** Animate dayW to `target` over ANIM_MS, calling onFrame after each step
   *  (so the caller can keep e.g. a fixed anchor date under a fixed point). */
  function _animateTo(target, onFrame) {
    _stopAnim()
    const clamped = Math.max(MIN_DAYW, Math.min(MAX_DAYW, target))
    const start = dayW.value
    if (Math.abs(clamped - start) < 0.01) { onFrame?.(); return }
    const t0 = performance.now()
    function tick(now) {
      const t = Math.min(1, (now - t0) / ANIM_MS)
      const eased = 1 - Math.pow(1 - t, 3) // ease-out cubic
      dayW.value = start + (clamped - start) * eased
      onFrame?.()
      raf = t < 1 ? requestAnimationFrame(tick) : null
    }
    raf = requestAnimationFrame(tick)
  }

  function setDayW(v) {
    _stopAnim()
    dayW.value = Math.max(MIN_DAYW, Math.min(MAX_DAYW, v))
  }

  /** date -> px offset from rangeStart, at the current dayW. */
  function xOf(date, rangeStart) {
    return Math.round((date - rangeStart) / DAY_MS) * dayW.value
  }
  /** px offset from rangeStart -> the date under it, at the current dayW. */
  function dateOf(px, rangeStart) {
    return new Date(rangeStart.getTime() + (px / dayW.value) * DAY_MS)
  }

  const activeGrain = computed(() =>
    dayW.value >= 24 ? 'day' : dayW.value >= 11 ? 'week' : dayW.value >= 5 ? 'month' : 'quarter'
  )

  /** Named zoom step (Day/Week/Month/Quarter toolbar segment) — animated,
   *  anchored on whatever's currently at the viewport's horizontal center. */
  function setPreset(name, { scrollEl, leftW, rangeStart } = {}) {
    const target = ZOOM_PRESETS[name]
    if (target == null) return
    _zoomAnimatedAbout(target, scrollEl, leftW, rangeStart, 0.5)
  }

  /** Fit the whole `totalDays` span into the current viewport width. */
  function fitToRange(scrollEl, leftW, totalDays, padPx = 8) {
    if (!scrollEl || !totalDays) return
    const avail = scrollEl.clientWidth - leftW - padPx
    if (avail <= 0) return
    _zoomAnimatedAbout(avail / totalDays, scrollEl, leftW, null, 0.5, () => { scrollEl.scrollLeft = 0 })
  }

  /** Animated zoom that keeps the date at `anchorFrac` (0=left edge of
   *  viewport, 0.5=center, 1=right edge) visually stationary. */
  function _zoomAnimatedAbout(target, scrollEl, leftW, rangeStart, anchorFrac, onDone) {
    const _pollDone = () => {
      if (!onDone) return
      const check = () => { if (!raf) onDone(); else requestAnimationFrame(check) }
      requestAnimationFrame(check)
    }
    if (!scrollEl || !rangeStart) {
      // No anchor to hold (fitToRange passes rangeStart=null) — still honor
      // onDone, it carries the post-zoom scroll reset.
      _animateTo(target)
      _pollDone()
      return
    }
    // clientWidth = LAYOUT px; rect.width would be VISUAL px under the app's
    // html{zoom:var(--ui-zoom)} density scaling — mixing them drifts the
    // anchor ~8% per screenful in comfortable density.
    const viewportTimelineW = scrollEl.clientWidth - leftW
    // Anchor measured from the container's left edge, INCLUDING the sticky
    // label column: frac 0.5 must be the visual center of the timeline
    // region (leftW + half the timeline viewport), not half the timeline
    // width from the container edge — that point sits leftW/2 off-center.
    const anchorFromLeft = leftW + viewportTimelineW * anchorFrac
    const anchorPxInTimeline = scrollEl.scrollLeft - leftW + anchorFromLeft
    const anchorDate = dateOf(Math.max(0, anchorPxInTimeline), rangeStart)
    _animateTo(target, () => {
      const newAnchorPxInTimeline = xOf(anchorDate, rangeStart)
      scrollEl.scrollLeft = newAnchorPxInTimeline + leftW - anchorFromLeft
    })
    _pollDone()
  }

  /** Continuous ctrl+wheel / pinch zoom — synchronous, no easing, so the
   *  date under the cursor never visibly drifts mid-gesture. */
  function zoomAboutPointer(scrollEl, leftW, clientX, deltaY, rangeStart) {
    _stopAnim()
    const rect = scrollEl.getBoundingClientRect()
    // Visual px → layout px: the app density-zooms <html>, so client coords
    // are scaled while scrollLeft/SVG/offset coords are not. The measured
    // ratio IS the accumulated zoom.
    const sc = scrollEl.offsetWidth ? rect.width / scrollEl.offsetWidth : 1
    // Clamp into the timeline region: a ctrl+wheel with the cursor over the
    // sticky label column would otherwise anchor to a date hidden UNDER the
    // labels and the zoom would appear to drift.
    const pointerXInViewport = Math.max(leftW, (clientX - rect.left) / sc)
    const pointerXInTimeline = scrollEl.scrollLeft - leftW + pointerXInViewport
    const anchorDate = dateOf(Math.max(0, pointerXInTimeline), rangeStart)

    const factor = Math.pow(1.0015, -deltaY)
    dayW.value = Math.max(MIN_DAYW, Math.min(MAX_DAYW, dayW.value * factor))

    const newPointerXInTimeline = xOf(anchorDate, rangeStart)
    scrollEl.scrollLeft = newPointerXInTimeline + leftW - pointerXInViewport
  }

  return {
    dayW, setDayW, setPreset, fitToRange, zoomAboutPointer,
    xOf, dateOf, activeGrain,
  }
}
