<template>
  <div class="w-row" :class="{ 'w-row-has-solo': !!solo }" @click="$emit('click')">
    <!-- Solo, left — one big visual pulled out of the text flow entirely and
         sized to most of the row's height, so a thumbnail/avatar/icon reads
         as the row's anchor instead of another inline chip. -->
    <SoloItem v-if="solo && solo.position !== 'right'" :item="solo" />

    <div class="w-row-main">
      <!-- Row 1: the headline — always shown in full, at primary size. No
           truncation-into-badge here: a long title just ellipsis-truncates
           via plain CSS. This row's whole point is to be the one thing you
           can always read at a glance. -->
      <div v-if="line1.length" class="w-row-line w-row-line1">
        <RowItem v-for="(it, i) in line1" :key="i" :item="it" primary />
      </div>

      <!-- Row 2: secondary/meta — smaller text, and THIS is where real
           width-measured overflow collapses extra items into a "+N" badge
           (hover for the rest). -->
      <div v-if="line2.length || dateLabel" class="w-row-line w-row-line2">
        <div ref="line2El" class="w-row-line2-items">
          <template v-for="(it, i) in line2" :key="i">
            <RowItem v-if="i < visible2" :item="it" />
          </template>
          <OverflowButton v-if="line2.length > visible2" :items="line2.slice(visible2)" />
        </div>
        <span v-if="dateLabel" class="w-row-date" :class="dateClass">{{ dateLabel }}</span>
      </div>
    </div>

    <!-- Solo, right — same block, pinned to the far corner instead. -->
    <SoloItem v-if="solo && solo.position === 'right'" :item="solo" />
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount, h } from 'vue'
import { Avatar, ProjectAvatar } from '@/ui'

// Two-tier row + optional solo anchor.
//   solo   — one block (image, icon, avatar, project tile, assignee stack, or
//            even a text field) rendered large and vertically centred on
//            either edge, spanning most of the row height.
//   line1  — the full, un-truncated headline.
//   line2  — smaller secondary meta; truncates into a "+N" badge once it
//            genuinely doesn't fit (measured, not guessed).
// Which line something sits on decides its weight — not a per-field toggle —
// while which FIELDS go where stays entirely up to the person configuring it.
const props = defineProps({
  line1: { type: Array, default: () => [] }, // [{ kind: 'text'|'avatar-*'|'avatars', ... }]
  line2: { type: Array, default: () => [] },
  date:  { type: String, default: null },
  solo:  { type: Object, default: null },    // { ...block, position: 'left'|'right' }
})
defineEmits(['click'])

const GAP = 6        // .w-row-line2-items column-gap, kept in sync with the CSS below
const BADGE_W = 32   // reserve for the "+N" pill when it will actually appear

// Exact fit measurement — no fudge factor. The container is flex:1/min-width:0
// so its clientWidth is the real space left after the date column, and each
// child's own rendered width is read directly rather than estimated from
// character counts.
function useOverflow(itemsRef) {
  const el = ref(null)
  const visible = ref(Infinity) // optimistic: show everything until measured
  function measure() {
    const row = el.value
    if (!row) return
    const kids = [...row.children].filter((c) => !c.classList.contains('w-row-overflow-btn'))
    if (!kids.length) { visible.value = Infinity; return }
    const avail = row.clientWidth
    if (!avail) return
    const widths = kids.map((k) => k.getBoundingClientRect().width)
    const totalAll = widths.reduce((a, b) => a + b, 0) + GAP * (widths.length - 1)
    if (totalAll <= avail) { visible.value = Infinity; return }
    // Doesn't fit: re-fit against a budget that leaves room for the badge.
    const budget = avail - BADGE_W - GAP
    let used = 0, count = 0
    for (const w of widths) {
      const next = used + (count ? GAP : 0) + w
      if (count > 0 && next > budget) break
      used = next
      count++
    }
    visible.value = Math.max(1, count) // never hide everything
  }
  let ro
  onMounted(() => {
    nextTick(measure)
    ro = new ResizeObserver(() => nextTick(measure))
    if (el.value) ro.observe(el.value)
  })
  onBeforeUnmount(() => ro?.disconnect())
  watch(itemsRef, () => nextTick(measure), { deep: true })
  return { el, visible }
}
const { el: line2El, visible: visible2 } = useOverflow(() => props.line2)

const TEXT_COLOR = {
  default: 'var(--muted)',
  accent: 'var(--accent-soft-foreground)',
  success: 'var(--success-soft-foreground)',
  warning: 'var(--warning-soft-foreground)',
  danger: 'var(--danger-soft-foreground)',
}
const FILL_BG = {
  default: 'var(--default)',
  accent: 'var(--accent-soft)',
  success: 'var(--success-soft)',
  warning: 'var(--warning-soft)',
  danger: 'var(--danger-soft)',
}
function textColor(c) { return TEXT_COLOR[c] || c || TEXT_COLOR.default }

// `bg` and `color` are set independently, so a background may arrive with no
// explicit text colour. Rather than leaving unreadable default-grey on a
// dark pill, derive a readable text colour from the background's real
// relative luminance — a pale yellow gets near-black, a deep indigo gets
// white. An explicit text colour always wins over this.
function hexLuminance(hex) {
  const m = /^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(hex || '')
  if (!m) return null
  const [r, g, b] = [1, 2, 3].map((i) => {
    const v = parseInt(m[i], 16) / 255
    return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}
function autoTextOn(bg) {
  const lum = hexLuminance(bg)
  if (lum === null) return TEXT_COLOR[bg] || TEXT_COLOR.default
  return lum > 0.55 ? 'rgba(0,0,0,.82)' : '#fff'
}
// No bg -> transparent, exactly as before. A bg with no explicit text colour
// -> auto-contrast. Both set -> both honoured verbatim.
function itemStyle(it) {
  const hasBg = !!it.bg
  const explicitColor = it.color && it.color !== 'default'
  const style = {}
  if (hasBg) style.background = FILL_BG[it.bg] || it.bg
  style.color = explicitColor ? textColor(it.color) : (hasBg ? autoTextOn(it.bg) : TEXT_COLOR.default)
  return style
}

function renderVisual(it, big) {
  if (it.kind === 'avatar-image') {
    return h('img', { class: big ? 'w-row-solo-img' : 'w-row-img', src: it.image, alt: it.name || '' })
  }
  if (it.kind === 'avatar-project') {
    return h(ProjectAvatar, { theme: it.theme, seed: it.seed, size: big ? 'lg' : 'xs', class: 'shrink-0', title: it.label })
  }
  if (it.kind === 'avatar-hash') {
    return h(Avatar, { name: it.name, size: big ? 'lg' : 'xs', radius: big ? 'md' : 'sm', class: 'shrink-0' })
  }
  if (it.kind === 'avatars') {
    const people = it.people || []
    const shown = big ? 2 : 3
    return h('div', { class: big ? 'w-row-solo-avatars' : 'w-row-avatars' },
      [
        ...people.slice(0, shown).map((a, i) => h(Avatar, {
          key: a.full_name || a.user || i,
          name: a.full_name || a.user, src: a.user_image,
          size: big ? 'md' : 'xs', class: 'ring-2 ring-white shrink-0',
        })),
        people.length > shown
          ? h('div', { class: big ? 'w-row-solo-avatar-overflow' : 'w-row-avatar-overflow' }, `+${people.length - shown}`)
          : null,
      ])
  }
  return null
}

const RowItem = {
  props: { item: { type: Object, required: true }, primary: { type: Boolean, default: false } },
  render() {
    const it = this.item
    const visual = renderVisual(it, false)
    if (visual) return visual
    // text — line position (primary prop) decides weight; a background is
    // opt-in per field and only then does the chip become a pill.
    return h('span', {
      class: [this.primary ? 'w-row-title' : 'w-row-chip', it.bg ? 'w-row-filled' : null],
      style: this.primary && !it.bg && !(it.color && it.color !== 'default') ? {} : itemStyle(it),
      title: it.text,
    }, it.text)
  },
}

const SoloItem = {
  props: { item: { type: Object, required: true } },
  render() {
    const it = this.item
    const visual = renderVisual(it, true)
    return h('div', { class: 'w-row-solo' }, [
      visual || h('span', {
        class: ['w-row-solo-text', it.bg ? 'w-row-filled' : null],
        style: itemStyle(it),
        title: it.text,
      }, it.text),
    ])
  },
}

const OverflowButton = {
  props: { items: { type: Array, required: true } },
  data() { return { open: false } },
  render() {
    return h('span', { class: 'w-row-overflow-btn', onMouseenter: () => (this.open = true), onMouseleave: () => (this.open = false) }, [
      h('button', { type: 'button', class: 'w-row-overflow-trigger' }, `+${this.items.length}`),
      this.open ? h('div', { class: 'w-row-overflow-pop' },
        this.items.map((it, i) => h(RowItem, { key: i, item: it, class: 'w-row-overflow-item' }))
      ) : null,
    ])
  },
}

function startOfDay(d) { const x = new Date(d); x.setHours(0, 0, 0, 0); return x }
function dayDiff(d) {
  const due = startOfDay(d)
  if (isNaN(due)) return null
  return Math.round((due - startOfDay(new Date())) / 86400000)
}
const dateClass = computed(() => {
  const diff = props.date ? dayDiff(props.date) : null
  if (diff === null) return ''
  if (diff < 0) return 'w-row-date-overdue'
  if (diff <= 2) return 'w-row-date-soon'
  return 'w-row-date-normal'
})
const dateLabel = computed(() => {
  if (!props.date) return ''
  const d = new Date(props.date)
  if (isNaN(d)) return ''
  const diff = dayDiff(props.date)
  if (diff === 0) return 'Today'
  if (diff === 1) return 'Tomorrow'
  if (diff === -1) return 'Yesterday'
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
})
</script>

<style scoped>
.w-row {
  display: flex; align-items: center; gap: 10px;
  padding: 10px; cursor: pointer; border-bottom: 1px solid var(--border);
  transition: background-color .12s;
}
.w-row:last-child { border-bottom: none; }
.w-row:hover { background: var(--surface-secondary); }

.w-row-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 3px; }

.w-row-line { display: flex; align-items: center; gap: 6px; min-width: 0; flex-wrap: nowrap; overflow: hidden; }
.w-row-line2 { justify-content: space-between; gap: 8px; }
.w-row-line2-items { display: flex; align-items: center; gap: 6px; min-width: 0; flex: 1; overflow: hidden; }

.w-row-title { flex: 0 1 auto; min-width: 0; font-size: 14px; font-weight: 500; color: var(--foreground); line-height: 1.35; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.w-row-chip { flex-shrink: 0; font-size: 11px; font-weight: 600; line-height: 1.5; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 150px; }
/* Opt-in filled treatment — only ever applied when explicitly turned on. */
.w-row-filled { padding: 1px 7px; border-radius: 999px; }

.w-row-img { width: 18px; height: 18px; border-radius: var(--radius-sm); object-fit: cover; flex-shrink: 0; }
.w-row-avatars { display: flex; align-items: center; flex-shrink: 0; }
.w-row-avatars > * + * { margin-left: -6px; }
.w-row-avatar-overflow { width: 20px; height: 20px; border-radius: 999px; background: var(--default); display: flex; align-items: center; justify-content: center; color: var(--muted); font-size: 9px; font-weight: 700; box-shadow: 0 0 0 2px var(--surface); flex-shrink: 0; margin-left: -6px; }

/* ── Solo anchor ──────────────────────────────────────────────────────────
   38px against a ~58px row: deliberately more than half the row height, so
   it reads as the row's primary visual rather than an oversized inline chip.
   Self-centred and never shrinks, so the text stack beside it keeps a stable
   baseline no matter how tall its own two lines end up. */
.w-row-solo {
  flex-shrink: 0; align-self: center;
  width: 38px; height: 38px;
  display: flex; align-items: center; justify-content: center;
  overflow: hidden;
}
.w-row-solo-img { width: 38px; height: 38px; border-radius: var(--radius-md); object-fit: cover; }
.w-row-solo :deep(.size-10), .w-row-solo :deep(.size-9) { width: 38px; height: 38px; }
.w-row-solo-text {
  font-size: 12px; font-weight: 700; line-height: 1.2; text-align: center;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 100%;
}
.w-row-solo-avatars { display: flex; align-items: center; }
.w-row-solo-avatars > * + * { margin-left: -8px; }
.w-row-solo-avatar-overflow { width: 30px; height: 30px; border-radius: 999px; background: var(--default); display: flex; align-items: center; justify-content: center; color: var(--muted); font-size: 10px; font-weight: 700; box-shadow: 0 0 0 2px var(--surface); flex-shrink: 0; margin-left: -8px; }

.w-row-overflow-btn { position: relative; flex-shrink: 0; display: inline-flex; }
.w-row-overflow-trigger {
  display: flex; align-items: center; justify-content: center;
  height: 17px; padding: 0 6px; border-radius: 999px;
  font-size: 10px; font-weight: 700; color: var(--muted);
  background: var(--default); border: none; cursor: pointer;
}
.w-row-overflow-trigger:hover { color: var(--foreground); background: var(--surface-secondary); }
.w-row-overflow-pop {
  position: absolute; bottom: calc(100% + 5px); left: 0; z-index: 20;
  display: flex; flex-direction: column; align-items: flex-start; gap: 5px; padding: 7px 9px;
  border-radius: var(--radius-md); background: var(--overlay); box-shadow: var(--shadow-overlay);
  border: 1px solid var(--border); white-space: nowrap;
}
.w-row-overflow-item { max-width: 240px !important; }

.w-row-date { flex-shrink: 0; font-size: 11px; font-weight: 600; white-space: nowrap; }
.w-row-date-overdue { color: var(--danger); }
.w-row-date-soon { color: var(--warning-soft-foreground); }
.w-row-date-normal { color: var(--muted); }
</style>
