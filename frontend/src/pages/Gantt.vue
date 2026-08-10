<template>
  <div class="gt-root">
    <!-- ── Toolbar ── -->
    <div class="gt-toolbar">
      <div class="gt-tb-left">
        <span class="gt-tb-title">Timeline</span>
        <span class="gt-tb-count" v-if="!loading">{{ datedTasks.length }} scheduled<template v-if="undatedTasks.length"> · {{ undatedTasks.length }} unscheduled</template></span>
      </div>
      <div class="gt-tb-right" v-if="!loading && datedTasks.length">
        <div class="gt-seg" title="Color bars by">
          <button v-for="m in COLOR_MODES" :key="m.v" class="gt-seg-btn" :class="{ on: colorMode === m.v }" @click="colorMode = m.v">{{ m.l }}</button>
        </div>
        <button class="gt-tb-btn" :class="{ on: showCritical }" title="Highlight the chain of tasks with zero slack — any slip there slips the whole project"
                @click="showCritical = !showCritical">Critical path</button>
        <button class="gt-tb-btn" @click="autoFit">Fit</button>
        <button class="gt-tb-btn" @click="scrollToToday">Today</button>
        <div class="gt-seg" title="Timeline scale">
          <button v-for="g in GRANULARITY" :key="g.v" class="gt-seg-btn" :class="{ on: activeGrain === g.v }" @click="setGrain(g.v)">{{ g.l }}</button>
        </div>
      </div>
    </div>

    <!-- ── Loading ── -->
    <div v-if="loading" class="gt-state">
      <div class="gt-spinner"/>
    </div>

    <!-- ── Empty ── -->
    <div v-else-if="!datedTasks.length" class="gt-state">
      <div class="gt-empty">
        <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4"><path stroke-linecap="round" stroke-linejoin="round" d="M4 6h10M4 12h14M4 18h7"/></svg>
        <p class="gt-empty-t">Nothing scheduled yet</p>
        <p class="gt-empty-s">Give tasks a start and due date to see them on the timeline.</p>
      </div>
    </div>

    <!-- ── Chart ── -->
    <div v-else class="gt-scroll" ref="scrollEl"
         :class="{ panning: isPanning, 'space-pan': spaceHeld }"
         @scroll="onScroll" @wheel="onWheel"
         @pointerdown="onPanStart" @click.capture="onClickCapture">
      <div class="gt-grid" :style="{ width: (LEFT_W + timelineW) + 'px' }">

        <!-- Header -->
        <div class="gt-head" :style="{ height: HEAD_H + 'px' }">
          <div class="gt-corner" :style="{ width: LEFT_W + 'px' }">Task</div>
          <div class="gt-head-time" :style="{ width: timelineW + 'px' }">
            <div class="gt-months">
              <div v-for="m in months" :key="m.key" class="gt-month" :style="{ left: m.x + 'px', width: m.w + 'px' }">
                <span>{{ m.label }}</span>
              </div>
            </div>
            <div class="gt-daystrip" v-if="showDayGrid">
              <div v-for="d in days" :key="d.key"
                   class="gt-day" :class="{ 'is-weekend': d.weekend, 'is-today': d.isToday }"
                   :style="{ left: d.x + 'px', width: dayW + 'px' }">
                <span v-if="dayW >= 22">{{ d.dom }}</span>
              </div>
            </div>
            <!-- triangle cap at the header edge,
                 the line itself continues in the body overlay -->
            <div v-if="todayX !== null" class="gt-today-cap" :style="{ left: todayX + 'px' }"/>
          </div>
        </div>

        <!-- Body -->
        <div class="gt-rows" :style="{ height: rows.length * ROW_H + 'px' }">
          <!-- Row labels + backgrounds (virtualized: viewport ± buffer) -->
          <div v-for="vr in visibleRows" :key="vr.row.name"
               class="gt-row" :class="{ 'is-group': vr.row.rowType === 'group' }"
               :style="{ top: vr.idx * ROW_H + 'px', height: ROW_H + 'px' }"
               @mouseenter="hoverRow = vr.row.name" @mouseleave="hoverRow = null">
            <!-- Group header -->
            <div v-if="vr.row.rowType === 'group'" class="gt-label gt-glabel" :style="{ width: LEFT_W + 'px' }" @click="toggleGroup(vr.row.key)">
              <svg class="gt-chevron" :class="{ collapsed: vr.row.collapsed }" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/></svg>
              <span class="gt-gdot" :style="{ background: vr.row.color }"/>
              <span class="gt-gname">{{ vr.row.label }}</span>
              <span class="gt-gcount">{{ vr.row.count }}</span>
              <span class="gt-gdate">{{ vr.row.dateLabel }}</span>
            </div>
            <!-- Task -->
            <div v-else class="gt-label" :style="{ width: LEFT_W + 'px' }"
                 :class="{ hov: hoverRow === vr.row.name }" @click="open(vr.row)"
                 @contextmenu.prevent="onCtx($event, vr.row)">
              <span class="gt-label-indent"/>
              <span class="gt-key">{{ vr.row.task_key }}</span>
              <span class="gt-name">{{ vr.row.title }}</span>
              <button
                v-for="g in erpBadges(vr.row)" :key="g.doctype"
                class="gt-erp-badge"
                :title="g.items.map(r => r.ref_label || r.ref_name).join(', ')"
                @click.stop="openErpDoc(g.items[0].ref_doctype, g.items[0].ref_name)"
              >{{ g.abbr }}<template v-if="g.n > 1">×{{ g.n }}</template></button>
              <span v-if="vr.row.billable && vr.row.estimated_hours" class="gt-billable-badge" title="Billable">$</span>
              <span class="gt-date">{{ vr.row.dateLabel }}</span>
            </div>
            <div class="gt-rowtrack" :class="{ hov: hoverRow === vr.row.name }"/>
          </div>

          <!-- Timeline overlay (weekends, today, arrows, bars) -->
          <div class="gt-overlay" ref="overlayEl" :style="{ left: LEFT_W + 'px', width: timelineW + 'px', height: rows.length * ROW_H + 'px' }">
            <div v-for="d in weekendDays" :key="'w' + d.key" class="gt-wkcol" :style="{ left: d.x + 'px', width: dayW + 'px' }"/>
            <div v-if="todayX !== null" class="gt-todayline" :style="{ left: todayX + 'px' }"/>

            <div v-for="mk in milestoneMarkers" :key="'ms' + mk.name"
                 class="gt-msline" :class="{ done: mk.done, overdue: mk.overdue }"
                 :style="{ left: mk.x + 'px' }">
              <span class="gt-msdiamond" :title="mk.title + (mk.dateLabel ? ' · ' + mk.dateLabel : '')"/>
            </div>

            <svg class="gt-arrows" :width="timelineW" :height="rows.length * ROW_H">
              <defs>
                <marker id="gt-arrow" markerWidth="7" markerHeight="7" refX="5.5" refY="3" orient="auto">
                  <path d="M0,0 L6,3 L0,6 Z" fill="var(--muted)"/>
                </marker>
              </defs>
              <path v-for="(a, ai) in arrows" :key="ai" :d="a.d"
                    marker-end="url(#gt-arrow)" class="gt-arrow"
                    :class="{ crit: a.crit, dimmed: a.dimmed }"
                    @click="onWireClick(a)">
                <title>{{ a.title }} — click to remove</title>
              </path>
              <!-- elastic preview wire while drawing a dependency (XL-C) -->
              <path v-if="linkPreview" :d="linkPreview.d" class="gt-linkpreview"/>
            </svg>

            <template v-for="vr in visibleRows" :key="'b' + vr.row.name">
              <!-- Group summary bar (bracket spanning children) -->
              <div v-if="vr.row.rowType === 'group' && vr.row.hasSpan" class="gt-groupbar" :style="groupBarStyle(vr.row, vr.idx)"/>
              <!-- Task bar -->
              <div v-else-if="vr.row.bar" class="gt-bar"
                   :class="{ done: vr.row.done, milestone: vr.row.bar.milestone, hov: hoverRow === vr.row.name, 'link-target': linkTargetName === vr.row.name, dragging: dragLive?.name === vr.row.name, crit: criticalInfo?.tasks.has(vr.row.name), dim: criticalInfo && !criticalInfo.tasks.has(vr.row.name) }"
                   :style="barStyle(vr.row, vr.idx)"
                   :data-name="vr.row.name"
                   @pointerdown="onBarDown($event, vr.row, 'move')"
                   @mouseenter="hoverRow = vr.row.name" @mouseleave="hoverRow = null"
                   @click="open(vr.row)"
                   @contextmenu.prevent="onCtx($event, vr.row)">
                <template v-if="vr.row.bar.milestone">
                  <span class="gt-diamond" :style="{ background: barColor(vr.row) }"/>
                  <span class="gt-bar-out">{{ vr.row.title }}</span>
                </template>
                <template v-else>
                  <span class="gt-bar-fill" :style="{ background: barColor(vr.row) }"/>
                  <span v-if="vr.row.progress != null" class="gt-bar-prog" :style="{ width: vr.row.progress + '%' }"/>

                  <!-- Connection dots: drag from an edge dot onto another bar
                       to draw a real "blocks" dependency (XL-C). -->
                  <span class="gt-dot gt-dot-l" title="Drag to another task: it must finish before this starts"
                        @pointerdown="onLinkStart($event, vr.row, 'left')"/>
                  <span class="gt-dot gt-dot-r" title="Drag to another task: this must finish before it starts"
                        @pointerdown="onLinkStart($event, vr.row, 'right')"/>

                  <!-- Resize grips (XL-B): grab an end to change start/due date -->
                  <span class="gt-rsz gt-rsz-l" @pointerdown.stop="onBarDown($event, vr.row, 'resize-l')"/>
                  <span class="gt-rsz gt-rsz-r" @pointerdown.stop="onBarDown($event, vr.row, 'resize-r')"/>

                  <!-- Avatar sits INSIDE the bar at the left,
                       label next to it; below the width threshold both move
                       outside-right instead. -->
                  <template v-if="vr.row.bar.w >= 64">
                    <span v-if="vr.row.assignees?.length" class="gt-bar-avs-inline">
                      <span v-for="(a, ai) in vr.row.assignees.slice(0, 3)" :key="a.user" class="gt-bar-av"
                            :style="{ background: a.image ? 'var(--surface)' : avatarColor(a.user), boxShadow: '0 0 0 1.5px ' + barColor(vr.row), marginLeft: ai > 0 ? '-6px' : '0' }"
                            :title="a.name">
                        <img v-if="a.image" class="gt-av-img" :src="avatarSrc(a.image)" :alt="a.name"/>
                        <template v-else>{{ initials(a.name) }}</template>
                      </span>
                      <span v-if="vr.row.assignees.length > 3" class="gt-bar-av gt-bar-more" :style="{ boxShadow: '0 0 0 1.5px ' + barColor(vr.row) }">+{{ vr.row.assignees.length - 3 }}</span>
                    </span>
                    <span class="gt-bar-in">{{ vr.row.title }}</span>
                    <span v-if="vr.row.done" class="gt-bar-check">✓</span>
                  </template>
                  <template v-else>
                    <span v-if="vr.row.assignees?.length && vr.row.bar.w >= 36" class="gt-bar-avs">
                      <span v-for="(a, ai) in vr.row.assignees.slice(0, 3)" :key="a.user" class="gt-bar-av"
                            :style="{ background: a.image ? 'var(--surface)' : avatarColor(a.user), boxShadow: '0 0 0 1.5px ' + barColor(vr.row), marginLeft: ai > 0 ? '-6px' : '0' }"
                            :title="a.name">
                        <img v-if="a.image" class="gt-av-img" :src="avatarSrc(a.image)" :alt="a.name"/>
                        <template v-else>{{ initials(a.name) }}</template>
                      </span>
                      <span v-if="vr.row.assignees.length > 3" class="gt-bar-av gt-bar-more" :style="{ boxShadow: '0 0 0 1.5px ' + barColor(vr.row) }">+{{ vr.row.assignees.length - 3 }}</span>
                    </span>
                    <span class="gt-bar-out">{{ vr.row.title }}</span>
                  </template>
                </template>
              </div>
            </template>

            <!-- XL-B snap ghost + floating date chip: the bar itself follows
                 the hand un-snapped; this shows where it will land. -->
            <div v-if="dragGhost" class="gt-ghost"
                 :style="{ left: dragGhost.left + 'px', top: dragGhost.top + 'px', width: dragGhost.w + 'px', height: (ROW_H - BAR_PAD * 2) + 'px' }"/>
            <div v-if="dragGhost" class="gt-dragchip"
                 :style="{ left: dragGhost.left + 'px', top: (dragGhost.top - 26) + 'px' }">{{ dragGhost.label }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Right-click actions — the same menu Board/List use (status, priority,
         assignees, copy key, template, delete), plus the Gantt-only entries:
         a Dependencies flyout and "Remove from timeline". -->
    <TaskContextMenu
      v-if="ctxTask" :issue="ctxTask" :x="ctxX" :y="ctxY"
      :deps="ctxDeps" show-timeline
      @close="ctxTask = null"
      @remove-dep="onCtxRemoveDep"
      @clear-dates="onCtxClearDates"
      @deleted="onCtxDeleted"
    />
    <MoneyDrawer v-model:open="moneyDrawerOpen" :project="projectName" :doctype="moneyDrawerDoctype" :name="moneyDrawerName" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { useProjectStore } from '@/stores/project'
import { getGantt, getMilestones, addTaskLink, removeTaskLink, updateTask } from '@/utils/api'
import { initials, avatarColor } from '@/utils/constants.js'
import { toast } from 'vue-sonner'
import { useGanttScale } from '@/composables/useGanttScale'
import TaskContextMenu from '@/components/TaskContextMenu.vue'
import MoneyDrawer from '@/components/MoneyDrawer.vue'
import { useErpDocOpener } from '@/composables/useErpDocOpener.js'
import { confirmDialog } from '@/composables/useConfirmDialog'

const route = useRoute()
const store = useProjectStore()
const { moneyDrawerOpen, moneyDrawerDoctype, moneyDrawerName, openErpDoc } = useErpDocOpener()

// same doctype-grouping shape as ListView's ConnectCell summary.
function erpBadges(task) {
  const m = {}
  for (const r of (task.references || [])) (m[r.ref_doctype] ||= []).push(r)
  return Object.entries(m).map(([doctype, items]) => ({
    doctype, items, n: items.length,
    abbr: doctype.split(' ').map(w => w[0]).join('').toUpperCase(),
  }))
}

// ── Layout constants ──────────────────────────────────────────────────────────
const LEFT_W = 318
const ROW_H = 46
const HEAD_H = 56
const BAR_PAD = 9          // vertical inset of bar within a row (bar height = ROW_H - 2*BAR_PAD)
const ROW_BUFFER = 10      // virtualization: rows rendered beyond the viewport edge
const DAY_BUFFER = 10      // windowed time grid: day-cells rendered beyond the viewport edge

// Single date↔px source of truth — dayW,
// zoom presets, Fit and cursor-anchored wheel zoom all live here.
const { dayW, setPreset: scaleSetPreset, fitToRange: scaleFitToRange,
        zoomAboutPointer, xOf: scaleXOf, activeGrain } = useGanttScale(32)

// Day / Week / Month / Quarter view selector.
const GRANULARITY = [
  { v: 'day', l: 'Day' },
  { v: 'week', l: 'Week' },
  { v: 'month', l: 'Month' },
  { v: 'quarter', l: 'Quarter' },
]
function setGrain(g) {
  scaleSetPreset(g, { scrollEl: scrollEl.value, leftW: LEFT_W, rangeStart: range.value?.start })
}
function autoFit() {
  if (!scrollEl.value || !range.value) return
  scaleFitToRange(scrollEl.value, LEFT_W, range.value.totalDays)
}

// Ctrl+wheel / pinch — zoom about the cursor's date, doctrine point 4.
// A plain wheel (no modifier) falls through to normal scroll untouched.
function onWheel(e) {
  if (!e.ctrlKey && !e.metaKey) return
  e.preventDefault()
  if (!scrollEl.value || !range.value) return
  if (barDragCtx || linkDrag.value) return // never rescale mid-drag
  zoomAboutPointer(scrollEl.value, LEFT_W, e.clientX, e.deltaY, range.value.start)
}

// ── Data ──────────────────────────────────────────────────────────────────────
const loading = ref(true)
const tasks = ref([])
const edges = ref([])
const milestones = ref([])
const scrollEl = ref(null)
const hoverRow = ref(null)
const collapsedGroups = ref(new Set())
function toggleGroup(key) {
  const s = new Set(collapsedGroups.value)
  s.has(key) ? s.delete(key) : s.add(key)
  collapsedGroups.value = s
}

const projectKey = computed(() => route.params.key)
const projectName = computed(() =>
  store.currentProject?.name ||
  store.projects.find(p => p.key === projectKey.value)?.name ||
  projectKey.value
)

async function load() {
  loading.value = true
  try {
    const [res, ms] = await Promise.all([
      getGantt(projectName.value),
      getMilestones(projectName.value).catch(() => []),
    ])
    tasks.value = res.tasks || []
    edges.value = res.edges || []
    milestones.value = Array.isArray(ms) ? ms : []
  } catch (e) {
    toast.error("Couldn't load timeline", { description: String(e.message || e) })
  } finally {
    loading.value = false
    await nextTick()
    measureViewport()
    scrollToToday(false)
  }
}

onMounted(load)
watch(projectName, load)

// Edits made in the TaskDetail drawer (opened by clicking a bar) must show
// on the chart instantly — the Gantt keeps its own get_gantt task list, so
// it subscribes to the store's single-field patch broadcast. Gantt-relevant
// fields patch in place; a status change also shifts color/done (that
// mapping lives server-side), so that one silently refetches.
async function _silentReload() {
  try {
    const res = await getGantt(projectName.value)
    tasks.value = res.tasks || []
    edges.value = res.edges || []
  } catch (e) { /* keep showing the current chart */ }
}
watch(() => store.taskPatch, (p) => {
  if (!p) return
  const t = tasks.value.find(x => x.name === p.name)
  if (!t) return
  if (p.field === 'status') { _silentReload(); return }
  if (p.field === 'assignees') {
    t.assignees = (p.value || []).map(a => ({
      user: a.user,
      name: a.name || a.full_name || a.user,
      full_name: a.full_name || a.name || a.user,  // context menu reads this shape
      image: a.image || a.user_image || null,
    }))
  } else if (['title', 'start_date', 'due_date', 'priority', 'epic', 'estimated_hours', 'actual_hours'].includes(p.field)) {
    t[p.field] = p.value
  } else {
    return
  }
  tasks.value = [...tasks.value]
})

// ── Viewport tracking (scroll position + size) — feeds both virtualization
// axes below and the wheel-zoom anchor math. ─────────────────────────────────
const scrollTop = ref(0)
const scrollLeftPx = ref(0)
const viewportW = ref(0)
const viewportH = ref(0)
// rAF-coalesced: scroll can fire several times per frame, and each reactive
// write re-runs the virtualization computeds — once per frame is all the
// windowing needs (the ±buffers absorb the one-frame lag).
let scrollRaf = null
function onScroll(e) {
  const el = e.target
  if (scrollRaf) return
  scrollRaf = requestAnimationFrame(() => {
    scrollRaf = null
    scrollTop.value = el.scrollTop
    scrollLeftPx.value = el.scrollLeft
  })
}
function measureViewport() {
  if (!scrollEl.value) return
  viewportW.value = scrollEl.value.clientWidth
  viewportH.value = scrollEl.value.clientHeight
}
let resizeObserver = null
onMounted(() => {
  measureViewport()
  if (window.ResizeObserver) {
    resizeObserver = new ResizeObserver(measureViewport)
    if (scrollEl.value) resizeObserver.observe(scrollEl.value)
  } else {
    window.addEventListener('resize', measureViewport)
  }
})
onBeforeUnmount(() => {
  if (scrollRaf) cancelAnimationFrame(scrollRaf)
  if (resizeObserver) resizeObserver.disconnect()
  else window.removeEventListener('resize', measureViewport)
})
// The scroll element itself only exists once data has loaded (v-else in the
// template) — re-attach the observer whenever it (re)appears.
watch(scrollEl, (el) => {
  if (!el) return
  measureViewport()
  if (resizeObserver) resizeObserver.observe(el)
})

// ── Pan: grab the chart like a hand (drawio/Figma/Miro) ──────────────────────
// Two entry points: dragging any empty timeline area pans directly, and
// holding Space arms the hand tool everywhere (even over bars/labels).
// Doctrine point 1: scroll positions are written directly per pointermove —
// no easing, nothing trails the hand.
const isPanning = ref(false)
const spaceHeld = ref(false)
let panMoved = false
let panStart = null

function _isInteractive(el) {
  return !!el?.closest?.('.gt-bar, .gt-label, .gt-glabel, .gt-msdiamond, .gt-arrow, button, a, input')
}
function onPanStart(e) {
  if (e.button !== 0) return
  if (!spaceHeld.value && _isInteractive(e.target)) return
  const el = scrollEl.value
  if (!el) return
  isPanning.value = true
  panMoved = false
  panStart = { x: e.clientX, y: e.clientY, left: el.scrollLeft, top: el.scrollTop }
  el.setPointerCapture?.(e.pointerId)
  window.addEventListener('pointermove', onPanMove)
  window.addEventListener('pointerup', onPanEnd, { once: true })
}
function onPanMove(e) {
  if (!panStart || !scrollEl.value) return
  const dx = e.clientX - panStart.x, dy = e.clientY - panStart.y
  if (!panMoved && Math.abs(dx) + Math.abs(dy) > 4) panMoved = true
  // visual px → layout px (density zoom), or the chart pans faster than the hand
  const sc = _zoomScale(scrollEl.value)
  scrollEl.value.scrollLeft = panStart.left - dx / sc
  scrollEl.value.scrollTop = panStart.top - dy / sc
}
function onPanEnd() {
  window.removeEventListener('pointermove', onPanMove)
  panStart = null
  isPanning.value = false
  // panMoved survives until the ghost click that follows pointerup has been
  // swallowed by onClickCapture — a drag must never read as a task click.
  setTimeout(() => { panMoved = false }, 0)
}
let suppressClick = false
function onClickCapture(e) {
  if (panMoved || suppressClick) { e.stopPropagation(); e.preventDefault() }
}

// ── XL-C: draw a dependency by dragging between bar edge dots ─────────────────
// Right dot → drop on a bar: this task BLOCKS that one (finish → start).
// Left dot  → drop on a bar: that task must finish first (this is blocked by it).
// The preview wire is an elastic bezier recomputed per pointermove; the drop
// calls the same add_task_link endpoint as the task drawer (cycle-guarded,
// permission-checked, reciprocal link mirrored server-side). Optimistic: the
// edge appears instantly and is rolled back with a toast if the server says no.
const linkDrag = ref(null)
const linkTargetName = ref(null)
const linkTargetHalf = ref('left')

// Pointer → SVG-local coordinates, MEASURED not derived — and CORRECTED for
// the app's density zoom. index.css puts `zoom: var(--ui-zoom)` on <html>
// (1.0833 in comfortable density): client coords are VISUAL px, while SVG
// and offset coords are LAYOUT px. rect.width / offsetWidth IS the
// accumulated zoom factor — divide it out, or every pointer measurement
// runs ~8% long, drifting further the further you drag (the documented
// "popup drift" trap from index.css, reborn in the Gantt).
const overlayEl = ref(null)
function _zoomScale(el) {
  return el && el.offsetWidth ? el.getBoundingClientRect().width / el.offsetWidth : 1
}
function _timelinePoint(e) {
  const el = overlayEl.value
  if (!el) return { x: 0, y: 0 }
  const r = el.getBoundingClientRect()
  const sc = el.offsetWidth ? r.width / el.offsetWidth : 1
  return { x: (e.clientX - r.left) / sc, y: (e.clientY - r.top) / sc }
}
function onLinkStart(e, row, end) {
  if (spaceHeld.value) return          // hand tool wins — let it bubble to pan
  if (e.button !== 0 || !row.bar) return
  e.stopPropagation()
  e.preventDefault()
  const i = rowIndex.value[row.name]
  const y = i * ROW_H + ROW_H / 2
  // Anchor at the CENTER OF THE DOT the hand actually grabbed (dots float
  // 14px off the bar; 9px wide → center sits 9.5px out from the edge),
  // not at the bar edge — a wire that starts 18px away from your fingers
  // reads as broken.
  const edgeX = end === 'right' ? row.bar.left + Math.max(dayW.value, row.bar.w - 3) : row.bar.left
  const x = edgeX + (end === 'right' ? 9.5 : -9.5)
  linkDrag.value = { from: row.name, end, x1: x, y1: y, cx: x, cy: y }
  window.addEventListener('pointermove', onLinkMove)
  window.addEventListener('pointerup', onLinkEnd, { once: true })
  window.addEventListener('keydown', onLinkEsc)
}
function onLinkMove(e) {
  if (!linkDrag.value || !scrollEl.value) return
  const p = _timelinePoint(e)
  linkDrag.value.cx = p.x
  linkDrag.value.cy = p.y
  const bar = document.elementFromPoint(e.clientX, e.clientY)?.closest?.('.gt-bar')
  const name = bar?.dataset?.name
  if (name && name !== linkDrag.value.from) {
    linkTargetName.value = name
    // Which END of the target the hand is over decides the dependency type
    // (both values visual px within the same element, so zoom cancels out).
    const r = bar.getBoundingClientRect()
    linkTargetHalf.value = (e.clientX - r.left) < r.width / 2 ? 'left' : 'right'
  } else {
    linkTargetName.value = null
  }
}
async function onLinkEnd() {
  window.removeEventListener('pointermove', onLinkMove)
  window.removeEventListener('keydown', onLinkEsc)
  const drag = linkDrag.value
  const target = linkTargetName.value
  linkDrag.value = null
  linkTargetName.value = null
  suppressClick = true
  setTimeout(() => { suppressClick = false }, 0)
  if (!drag || !target) return
  // Dependency type from (which end you grabbed) × (which half you dropped on):
  //   my FINISH → their left half  = FS (my finish gates their start)
  //   my FINISH → their right half = FF (my finish gates their finish)
  //   my START  → their right half = FS (their finish gates my start)
  //   my START  → their left half  = SS (their start gates my start)
  const half = linkTargetHalf.value
  let pred, succ, depType
  if (drag.end === 'right') { pred = drag.from; succ = target; depType = half === 'right' ? 'FF' : 'FS' }
  else { pred = target; succ = drag.from; depType = half === 'left' ? 'SS' : 'FS' }
  if (edges.value.some(x => x.from === pred && x.to === succ)) return
  // Instant local cycle check (mirror of the backend guard, which stays the
  // authority): reject before anything renders or hits the network — an
  // invalid wire should never even flash into existence.
  if (_wouldCycle(pred, succ)) {
    toast.error('That link would create a circular dependency.')
    return
  }
  const edge = { from: pred, to: succ, dep_type: depType, lag: 0 }
  edges.value = [...edges.value, edge]   // optimistic
  try {
    await addTaskLink(pred, succ, 'blocks', depType, 0)
  } catch (err) {
    edges.value = edges.value.filter(x => !(x.from === pred && x.to === succ))
    toast.error(err?.message || "Couldn't create the dependency")
  }
}
// Is `pred` already reachable FROM `succ` along blocking edges? Then adding
// pred→succ would close a loop. O(V+E) DFS over the in-memory graph.
function _wouldCycle(pred, succ) {
  const adj = {}
  for (const e of edges.value) (adj[e.from] ||= []).push(e.to)
  const stack = [succ]
  const seen = new Set()
  while (stack.length) {
    const n = stack.pop()
    if (n === pred) return true
    if (seen.has(n)) continue
    seen.add(n)
    for (const nx of adj[n] || []) stack.push(nx)
  }
  return false
}

function onLinkEsc(e) {
  if (e.key !== 'Escape' || !linkDrag.value) return
  window.removeEventListener('pointermove', onLinkMove)
  linkDrag.value = null
  linkTargetName.value = null
}
// ── XL-B: drag bars to move, grab edges to resize ─────────────────────────────
// The bar itself follows the hand UN-snapped (doctrine 5); the dashed ghost +
// floating date chip show the snapped day-grid landing spot. Wires read the
// live drag position from the same reactive source, so they stay glued to the
// moving bar in the same render flush (doctrine 2). Drop = optimistic date
// write + server save with rollback; every change lands on the undo stack
// (Ctrl+Z / Ctrl+Shift+Z).
const dragLive = ref(null)    // { name, leftPx, wPx } — raw pixels under the hand
const dragGhost = ref(null)   // snapped { left, w, top, label }
const undoStack = ref([])
const redoStack = ref([])
let barDragCtx = null

function onBarDown(e, row, mode) {
  if (spaceHeld.value || e.button !== 0 || !row.bar) return
  const win = windowOf(row)
  if (!win) return
  if (mode !== 'move') e.stopPropagation()
  barDragCtx = {
    name: row.name, mode,
    startPt: _timelinePoint(e),
    origLeft: row.bar.left,
    origW: row.bar.milestone ? dayW.value : Math.max(dayW.value, row.bar.w - 3),
    origStart: win[0], origEnd: win[1],
    rowIdx: rowIndex.value[row.name],
    hasStart: !!row.start_date, hasDue: !!row.due_date,
    started: false, snapStart: null, snapEnd: null,
  }
  window.addEventListener('pointermove', onBarMove)
  window.addEventListener('pointerup', onBarUp, { once: true })
  window.addEventListener('keydown', onBarEsc)
}

function onBarMove(e) {
  const c = barDragCtx
  if (!c) return
  const pt = _timelinePoint(e)
  const dx = pt.x - c.startPt.x
  if (!c.started) {
    // 4px threshold: a twitchy click must stay a click (open the task)
    if (Math.abs(dx) < 4 && Math.abs(pt.y - c.startPt.y) < 4) return
    c.started = true
  }
  let leftPx = c.origLeft, wPx = c.origW
  if (c.mode === 'move') leftPx = c.origLeft + dx
  else if (c.mode === 'resize-r') wPx = Math.max(dayW.value * 0.5, c.origW + dx)
  else { leftPx = c.origLeft + dx; wPx = Math.max(dayW.value * 0.5, c.origW - dx) }
  dragLive.value = { name: c.name, leftPx, wPx }

  const dDays = Math.round(dx / dayW.value)
  let s = new Date(c.origStart), en = new Date(c.origEnd)
  if (c.mode === 'move') { s.setDate(s.getDate() + dDays); en.setDate(en.getDate() + dDays) }
  else if (c.mode === 'resize-r') { en.setDate(en.getDate() + dDays); if (en < s) en = new Date(s) }
  else { s.setDate(s.getDate() + dDays); if (s > en) s = new Date(en) }
  c.snapStart = s; c.snapEnd = en
  const gl = xOf(s)
  dragGhost.value = {
    left: gl,
    w: Math.max(dayW.value, (diffDays(en, s) + 1) * dayW.value - 3),
    top: c.rowIdx * ROW_H + BAR_PAD,
    label: fmtRange(s, en),
  }
  _dragAutoScroll(e)
}

// Edge autoscroll (doctrine 7): dragging near the timeline edges scrolls it,
// faster the deeper into the zone the pointer sits.
function _dragAutoScroll(e) {
  const el = scrollEl.value
  if (!el) return
  const rect = el.getBoundingClientRect()
  const sc = _zoomScale(el)
  const px = (e.clientX - rect.left) / sc   // layout px within the container
  const M = 48
  if (px < LEFT_W + M) el.scrollLeft -= Math.ceil((LEFT_W + M - px) / 6)
  else if (px > el.clientWidth - M) el.scrollLeft += Math.ceil((px - (el.clientWidth - M)) / 6)
}

function onBarUp() {
  window.removeEventListener('pointermove', onBarMove)
  window.removeEventListener('keydown', onBarEsc)
  const c = barDragCtx
  barDragCtx = null
  dragLive.value = null
  dragGhost.value = null
  if (!c || !c.started) return           // plain click → open() proceeds
  suppressClick = true
  setTimeout(() => { suppressClick = false }, 0)
  const { snapStart: s, snapEnd: en } = c
  if (!s || (+s === +c.origStart && +en === +c.origEnd)) return
  undoStack.value.push({ name: c.name, hasStart: c.hasStart, hasDue: c.hasDue,
                         before: { s: c.origStart, e: c.origEnd }, after: { s, e: en } })
  redoStack.value = []
  _applyDates(c.name, c.hasStart, c.hasDue, s, en)
}

function onBarEsc(e) {
  if (e.key !== 'Escape' || !barDragCtx) return
  window.removeEventListener('pointermove', onBarMove)
  barDragCtx = null
  dragLive.value = null
  dragGhost.value = null
}

function _isoDay(d) { const p = n => String(n).padStart(2, '0'); return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}` }

async function _applyDates(name, hasStart, hasDue, s, en) {
  const t = tasks.value.find(x => x.name === name)
  if (!t) return
  // Only touch the date fields the task actually uses — a deadline-only task
  // (one date set) keeps being deadline-only when moved.
  const fields = {}
  if (hasStart) fields.start_date = _isoDay(s)
  if (hasDue) fields.due_date = _isoDay(en)
  if (!Object.keys(fields).length) return
  const prev = { start_date: t.start_date, due_date: t.due_date }
  Object.assign(t, fields)
  tasks.value = [...tasks.value]        // rows/arrows recompute from committed state
  try {
    await updateTask(name, fields)
  } catch (err) {
    Object.assign(t, prev)
    tasks.value = [...tasks.value]
    toast.error(err?.message || "Couldn't reschedule the task")
  }
}

function undoSchedule() {
  const u = undoStack.value.pop()
  if (!u) return
  redoStack.value.push(u)
  _applyDates(u.name, u.hasStart, u.hasDue, u.before.s, u.before.e)
}
function redoSchedule() {
  const r = redoStack.value.pop()
  if (!r) return
  undoStack.value.push(r)
  _applyDates(r.name, r.hasStart, r.hasDue, r.after.s, r.after.e)
}

// Remove a dependency — optimistic, rolled back with a toast on failure.
// Shared by the wire click and the context menu's Dependencies flyout.
async function _removeEdge(from, to) {
  const removed = edges.value.find(x => x.from === from && x.to === to)
  edges.value = edges.value.filter(x => !(x.from === from && x.to === to))
  try {
    await removeTaskLink(from, to, 'blocks')
  } catch (err) {
    if (removed) edges.value = [...edges.value, removed]
    toast.error(err?.message || "Couldn't remove the dependency")
  }
}
async function onWireClick(a) {
  if (!a.from || !a.to) return
  if (!await confirmDialog(`Remove dependency ${a.title}?`, { danger: true })) return
  await _removeEdge(a.from, a.to)
}

// ── Right-click context menu ──────────────────────────────────────────────────
// Reuses TaskContextMenu (Board/List) — its optimistic edits go through
// store.updateTaskField, whose taskPatch broadcast this page already
// subscribes to, so menu changes repaint the chart with no extra wiring.
const ctxTask = ref(null)
const ctxX = ref(0)
const ctxY = ref(0)

function onCtx(e, row) {
  if (row.rowType === 'group') return
  if (barDragCtx || linkDrag.value || isPanning.value) return
  const t = tasks.value.find(x => x.name === row.name)
  if (!t) return
  // The menu mutates issue.assignees in the {user, full_name} shape; the
  // gantt payload uses {user, name, image}. Carry both so neither breaks.
  t.assignees = (t.assignees || []).map(a => ({ ...a, full_name: a.full_name || a.name }))
  ctxTask.value = t
  ctxX.value = e.clientX
  ctxY.value = e.clientY
}

const ctxDeps = computed(() => {
  const t = ctxTask.value
  if (!t) return []
  const keyOf = n => tasks.value.find(x => x.name === n)?.task_key || n
  return edges.value
    .filter(e => e.from === t.name || e.to === t.name)
    .map(e => ({
      from: e.from, to: e.to,
      label: `${keyOf(e.from)} → ${keyOf(e.to)}`,
      sub: (e.dep_type || 'FS') + (e.lag ? ` ${e.lag > 0 ? '+' : ''}${e.lag}d` : ''),
    }))
})

function onCtxRemoveDep(d) { _removeEdge(d.from, d.to) }

// "Remove from timeline" — clears both dates (backend maps "" → NULL for
// Date fields). The bar disappears, so the toast carries its own Undo.
async function onCtxClearDates(name) {
  ctxTask.value = null
  const t = tasks.value.find(x => x.name === name)
  if (!t) return
  const prev = { start_date: t.start_date, due_date: t.due_date }
  t.start_date = null
  t.due_date = null
  tasks.value = [...tasks.value]
  try {
    await updateTask(name, { start_date: '', due_date: '' })
    toast.success('Removed from timeline', {
      action: {
        label: 'Undo',
        onClick: async () => {
          Object.assign(t, prev)
          tasks.value = [...tasks.value]
          try { await updateTask(name, { start_date: prev.start_date || '', due_date: prev.due_date || '' }) }
          catch (err) { toast.error(err?.message || "Couldn't restore the dates") }
        },
      },
    })
  } catch (err) {
    Object.assign(t, prev)
    tasks.value = [...tasks.value]
    toast.error(err?.message || "Couldn't update the task")
  }
}

// Delete cascades to subtasks server-side — refetch rather than guess locally.
function onCtxDeleted() { _silentReload() }

const linkPreview = computed(() => {
  const d = linkDrag.value
  if (!d) return null
  // Balanced node-editor cubic: leaves the source dot
  // horizontally, arrives at the cursor horizontally from the opposite
  // side — a proper S-bend for end-to-end connections. With pointer
  // coordinates now zoom-corrected (see _timelinePoint), the tip sits
  // EXACTLY on the cursor.
  const dir = d.end === 'right' ? 1 : -1
  const pull = Math.max(36, Math.min(160, Math.abs(d.cx - d.x1) * 0.5))
  return { d: `M${d.x1},${d.y1} C${d.x1 + dir * pull},${d.y1} ${d.cx - dir * pull},${d.cy} ${d.cx},${d.cy}` }
})
function _typing(t) {
  return t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT' ||
               t.tagName === 'BUTTON' || t.isContentEditable)
}
function onKeyDown(e) {
  if ((e.ctrlKey || e.metaKey) && e.code === 'KeyZ' && !_typing(e.target)) {
    e.preventDefault()
    e.shiftKey ? redoSchedule() : undoSchedule()
    return
  }
  if (e.code !== 'Space' || _typing(e.target)) return
  spaceHeld.value = true
  e.preventDefault() // space must arm the hand tool, not page-scroll the chart
}
function onKeyUp(e) { if (e.code === 'Space') spaceHeld.value = false }
onMounted(() => {
  window.addEventListener('keydown', onKeyDown)
  window.addEventListener('keyup', onKeyUp)
})
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeyDown)
  window.removeEventListener('keyup', onKeyUp)
  window.removeEventListener('pointermove', onPanMove)
  window.removeEventListener('pointermove', onLinkMove)
  window.removeEventListener('keydown', onLinkEsc)
})

// ── Date helpers ────────────────────────────────────────────────────────────────
const DAY = 86400000
function parseDay(s) { return s ? new Date(s + 'T00:00:00') : null }
function diffDays(a, b) { return Math.round((a - b) / DAY) }
const today = (() => { const d = new Date(); d.setHours(0, 0, 0, 0); return d })()

// task → its [start, end] window (fall back to whichever date exists)
function windowOf(t) {
  const s = parseDay(t.start_date) || parseDay(t.due_date)
  const e = parseDay(t.due_date) || parseDay(t.start_date)
  if (!s || !e) return null
  return e < s ? [e, s] : [s, e]
}

// Toolbar filters (shared boardViewState) apply here exactly as on Board/List
const filteredTasks = computed(() => {
  let list = tasks.value
  if (store.boardSprintFilter === 'active_sprint') {
    const active = store.sprints?.find(s => s.status === 'Active')
    if (active) list = list.filter(t => t.sprint === active.name)
  }
  const vs = store.boardViewState
  const q = vs.search?.toLowerCase()
  if (q) list = list.filter(t => t.title?.toLowerCase().includes(q) || t.task_key?.toLowerCase().includes(q))
  if (vs.filterAssignee) list = list.filter(t => (t.assignees || []).some(a => (a.name || a.full_name) === vs.filterAssignee))
  if (vs.filterPriority) list = list.filter(t => t.priority === vs.filterPriority)
  if (vs.filterType)     list = list.filter(t => t.task_type === vs.filterType)
  if (vs.filterLabel)    list = list.filter(t => {
    const lbls = Array.isArray(t.labels) ? t.labels : (() => { try { return JSON.parse(t.labels || '[]') } catch { return [] } })()
    return lbls.includes(vs.filterLabel)
  })
  return list
})

const datedTasks = computed(() => filteredTasks.value.filter(t => windowOf(t)))
const undatedTasks = computed(() => filteredTasks.value.filter(t => !windowOf(t)))

// ── Timeline range ──────────────────────────────────────────────────────────────
const range = computed(() => {
  const wins = datedTasks.value.map(windowOf)
  if (!wins.length) return null
  let min = wins[0][0], max = wins[0][1]
  for (const [s, e] of wins) { if (s < min) min = s; if (e > max) max = e }
  if (today < min) min = today
  if (today > max) max = today
  const start = new Date(min); start.setDate(start.getDate() - 3)
  const end = new Date(max); end.setDate(end.getDate() + 4)
  return { start, end, totalDays: diffDays(end, start) + 1 }
})

const timelineW = computed(() => range.value ? range.value.totalDays * dayW.value : 0)
// Thin wrapper over the composable so every existing call site (xOf(date))
// stays single-arg — the composable itself is the source of truth for the
// dayW math, this just supplies this page's current range anchor.
function xOf(date) { return range.value ? scaleXOf(date, range.value.start) : 0 }

// ── Day / month strips (day-cells windowed to the visible scroll region ± buffer;
// months stay unwindowed — there are only ever a handful) ─────────────────────
const visibleDayRange = computed(() => {
  if (!range.value) return { start: 0, end: 0 }
  const leftInTimeline = scrollLeftPx.value - LEFT_W
  const start = Math.max(0, Math.floor(leftInTimeline / dayW.value) - DAY_BUFFER)
  const end = Math.min(range.value.totalDays, Math.ceil((leftInTimeline + viewportW.value) / dayW.value) + DAY_BUFFER)
  return { start, end: Math.max(start, end) }
})
const days = computed(() => {
  if (!range.value) return []
  const { start, end } = visibleDayRange.value
  const out = []
  for (let i = start; i < end; i++) {
    const d = new Date(range.value.start); d.setDate(d.getDate() + i)
    const wd = d.getDay()
    out.push({
      key: i, x: i * dayW.value, dom: d.getDate(),
      weekend: wd === 0 || wd === 6,
      isToday: d.getTime() === today.getTime(),
    })
  }
  return out
})
// Day grid + weekend shading only read well when there's room; below this
// zoom they turn into gray noise, so we drop to a clean month-only view.
const showDayGrid = computed(() => dayW.value >= 13)
const weekendDays = computed(() => showDayGrid.value ? days.value.filter(d => d.weekend) : [])

const months = computed(() => {
  if (!range.value) return []
  const out = []
  const cur = new Date(range.value.start); cur.setDate(1)
  const MN = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
  while (cur <= range.value.end) {
    const monthStart = cur < range.value.start ? range.value.start : new Date(cur)
    const next = new Date(cur); next.setMonth(next.getMonth() + 1)
    const monthEnd = next > range.value.end ? range.value.end : new Date(next.getTime() - DAY)
    const x = xOf(monthStart)
    const w = (diffDays(monthEnd, monthStart) + 1) * dayW.value
    // Local-date key, NOT toISOString(): at UTC+05:45 local midnight July 1
    // is June 30 UTC, so ISO keys label months wrong AND collide (duplicate
    // v-for keys) for every timezone east of Greenwich.
    out.push({ key: `${cur.getFullYear()}-${cur.getMonth()}`, label: `${MN[cur.getMonth()]} ${cur.getFullYear()}`, x, w })
    cur.setMonth(cur.getMonth() + 1)
  }
  return out
})

const todayX = computed(() => {
  if (!range.value) return null
  if (today < range.value.start || today > range.value.end) return null
  return xOf(today) + dayW.value / 2
})

// BP Milestones rendered as vertical markers (status drives color)
const milestoneMarkers = computed(() => {
  if (!range.value) return []
  const out = []
  for (const m of milestones.value) {
    if (m.status === 'Cancelled') continue
    const d = parseDay(m.due_date)
    if (!d || d < range.value.start || d > range.value.end) continue
    out.push({
      name:      m.name,
      title:     m.title,
      dateLabel: d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
      x:         xOf(d) + dayW.value / 2,
      done:      m.status === 'Completed',
      overdue:   m.status === 'Open' && d < today,
    })
  }
  return out
})

// ── Rows (ordered: by start, then epic grouping kept implicit via epic dot) ──────
const epicColorMap = computed(() => {
  // store.epics may be an array OR an object map keyed by epic name.
  const src = store.epics
  const m = {}
  if (Array.isArray(src)) {
    for (const ep of src) { if (ep?.name) m[ep.name] = ep.color || ep.colour }
  } else if (src && typeof src === 'object') {
    for (const [key, ep] of Object.entries(src)) {
      const color = (ep && (ep.color || ep.colour)) || null
      m[key] = color
      if (ep?.name) m[ep.name] = color
    }
  }
  return m
})

const MONTHS_ABBR = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
function fmtRange(s, e) {
  if (!s) return ''
  const sm = MONTHS_ABBR[s.getMonth()], sd = s.getDate()
  if (!e || e.getTime() === s.getTime()) return `${sm} ${sd}`
  const em = MONTHS_ABBR[e.getMonth()], ed = e.getDate()
  return s.getMonth() === e.getMonth() ? `${sm} ${sd} – ${ed}` : `${sm} ${sd} – ${em} ${ed}`
}

function buildTaskRow(t, groupColor) {
  const win = windowOf(t)
  let bar = null
  if (win) {
    const [s, e] = win
    const span = diffDays(e, s) + 1
    // Diamond = deadline-style marker: exactly ONE date set (windowOf
    // mirrored it). A genuine 1-day task with both dates is a small BAR —
    // bars carry progress/avatars and will be resizable in XL-B; diamonds
    // can't be either.
    const deadlineOnly = !(t.start_date && t.due_date)
    bar = { left: xOf(s), w: span * dayW.value, milestone: deadlineOnly }
  }
  let progress = null
  if (t.estimated_hours > 0) progress = Math.max(0, Math.min(100, Math.round((t.actual_hours || 0) / t.estimated_hours * 100)))
  else if (t.done) progress = 100
  return {
    rowType: 'task', ...t, bar,
    depth: t.parent_task ? 1 : 0,
    dateLabel: win ? fmtRange(win[0], win[1]) : '',
    groupColor,
    progress,
  }
}

// Grouped, flat row list: group headers interleaved with their task rows.
const rows = computed(() => {
  if (!range.value) return []
  const all = [...datedTasks.value, ...undatedTasks.value]

  const groups = new Map()
  for (const t of all) {
    const key = t.epic || '__none__'
    if (!groups.has(key)) {
      groups.set(key, {
        key,
        label: t.epic ? (t.epic_title || t.epic) : 'No epic',
        color: t.epic ? (t.epic_color || GANTT_PALETTE[hashStr(t.epic) % GANTT_PALETTE.length]) : '#9FA6AD',
        tasks: [],
      })
    }
    groups.get(key).tasks.push(t)
  }

  const list = [...groups.values()]
  for (const g of list) {
    let min = null, max = null
    for (const t of g.tasks) {
      const w = windowOf(t)
      if (w) { if (min === null || w[0] < min) min = w[0]; if (max === null || w[1] > max) max = w[1] }
    }
    g.min = min; g.max = max
    g.tasks.sort((a, b) => {
      const wa = windowOf(a), wb = windowOf(b)
      if (wa && wb) return wa[0] - wb[0]
      return wa ? -1 : wb ? 1 : 0
    })
  }
  list.sort((a, b) => (a.min && b.min) ? a.min - b.min : a.min ? -1 : b.min ? 1 : 0)

  const flat = []
  const hideHeaders = list.length === 1 && list[0].key === '__none__'
  for (const g of list) {
    const isCollapsed = collapsedGroups.value.has(g.key)
    if (!hideHeaders) {
      flat.push({
        rowType: 'group', name: 'group:' + g.key, key: g.key, label: g.label,
        color: g.color, collapsed: isCollapsed, count: g.tasks.length,
        hasSpan: g.min !== null,
        gx: g.min !== null ? xOf(g.min) : 0,
        gw: (g.min !== null && g.max !== null) ? (diffDays(g.max, g.min) + 1) * dayW.value : 0,
        dateLabel: g.min !== null ? fmtRange(g.min, g.max) : '',
      })
    }
    if (hideHeaders || !isCollapsed) {
      for (const t of g.tasks) flat.push(buildTaskRow(t, g.color))
    }
  }
  return flat
})

const rowIndex = computed(() => {
  const m = {}
  rows.value.forEach((r, i) => { m[r.name] = i })
  return m
})

// Virtualization (doctrine: 500-task project at 60fps) — only rows within
// the vertical viewport ± ROW_BUFFER are ever mounted; both the label
// column and the timeline bars read from this same list, so they can never
// fall out of sync with each other.
const visibleRowRange = computed(() => {
  const topInRows = scrollTop.value - HEAD_H
  const start = Math.max(0, Math.floor(topInRows / ROW_H) - ROW_BUFFER)
  const end = Math.min(rows.value.length, Math.ceil((topInRows + viewportH.value) / ROW_H) + ROW_BUFFER)
  return { start, end: Math.max(start, end) }
})
const visibleRows = computed(() => {
  const { start, end } = visibleRowRange.value
  return rows.value.slice(start, end).map((row, k) => ({ row, idx: start + k }))
})

// ── Bar coloring ────────────────────────────────────────────────────────────
const COLOR_MODES = [
  { v: 'status', l: 'Status' },
  { v: 'epic', l: 'Epic' },
  { v: 'priority', l: 'Priority' },
]
const colorMode = ref('status')
// map) — vibrant, white-text-safe bar fills, one brand across the app.
const GANTT_PALETTE = ['#2684ff', '#36b37e', '#A25DDC', '#FDAB3D', '#E2445C', '#579BFC', '#037F4C', '#FF642E', '#7E3B8A', '#6b778c']
// Hot → cool by urgency, same family.
const PRIORITY_COLOR = { Highest: '#E2445C', High: '#FF642E', Medium: '#FDAB3D', Low: '#579BFC', Lowest: '#8A94A6' }
function hashStr(s) { let h = 0; for (let i = 0; i < (s || '').length; i++) h = (Math.imul(h, 31) + s.charCodeAt(i)) >>> 0; return h }
// Real profile photo when the account has one (same path normalization as
// People.vue), initials only as the fallback.
function avatarSrc(img) { return img.startsWith('/') || img.startsWith('http') ? img : '/files/' + img }
function barColor(t) {
  if (colorMode.value === 'epic') return t.epic ? GANTT_PALETTE[hashStr(t.epic) % GANTT_PALETTE.length] : '#9FA6AD'
  if (colorMode.value === 'priority') return PRIORITY_COLOR[t.priority] || 'var(--muted)'
  return t.color || 'var(--muted)'
}

function barStyle(r, i) {
  if (!r.bar) return {}
  // While this bar is being dragged, it renders at the live (un-snapped)
  // pointer position; arrows read the same source, same flush.
  const live = dragLive.value?.name === r.name ? dragLive.value : null
  if (r.bar.milestone) {
    const left = live ? live.leftPx : r.bar.left
    return { left: (left + dayW.value / 2 - 7) + 'px', top: (i * ROW_H + ROW_H / 2 - 7) + 'px' }
  }
  return {
    left: (live ? live.leftPx : r.bar.left) + 'px',
    top: (i * ROW_H + BAR_PAD) + 'px',
    width: (live ? live.wPx : Math.max(dayW.value, r.bar.w - 3)) + 'px',
    height: (ROW_H - BAR_PAD * 2) + 'px',
  }
}

function groupBarStyle(r, i) {
  return {
    left: r.gx + 'px',
    top: (i * ROW_H + ROW_H / 2 - 2) + 'px',
    width: Math.max(dayW.value, r.gw) + 'px',
    background: r.color,
  }
}

// ── Dependency arrows (finish-to-start, ROUNDED elbows) ─────────────────────────
// Orthogonal polyline → path with quarter-turn quadratic corners: the
// "smooth and flowing" wire look (vs hard right angles), radius clamped so
// short segments never overshoot.
function roundedPath(pts, r = 5) {
  let d = `M${pts[0][0]},${pts[0][1]}`
  for (let i = 1; i < pts.length - 1; i++) {
    const [x0, y0] = pts[i - 1], [x1, y1] = pts[i], [x2, y2] = pts[i + 1]
    const l1 = Math.hypot(x1 - x0, y1 - y0), l2 = Math.hypot(x2 - x1, y2 - y1)
    const rr = Math.min(r, l1 / 2, l2 / 2)
    const ux1 = Math.sign(x1 - x0), uy1 = Math.sign(y1 - y0)
    const ux2 = Math.sign(x2 - x1), uy2 = Math.sign(y2 - y1)
    d += ` L${x1 - ux1 * rr},${y1 - uy1 * rr} Q${x1},${y1} ${x1 + ux2 * rr},${y1 + uy2 * rr}`
  }
  const [xe, ye] = pts[pts.length - 1]
  return d + ` L${xe},${ye}`
}

// Generic orthogonal router: exit the source horizontally in exitDir, arrive
// at the target horizontally in entryDir; picks the clean 3-turn elbow when
// the approach direction works out, else routes around via a half-row jog.
function routeEdge(sx, sy, exitDir, ex, ey, entryDir) {
  const g = 11
  const x1 = sx + exitDir * g
  const x2 = ex - entryDir * g
  let pts
  if (sy === ey) {
    pts = [[sx, sy], [ex, ey]]
  } else if (Math.sign(ex - x1) === entryDir || ex === x1) {
    pts = [[sx, sy], [x1, sy], [x1, ey], [ex, ey]]
  } else {
    const midY = sy + (ey >= sy ? ROW_H / 2 : -ROW_H / 2)
    pts = [[sx, sy], [x1, sy], [x1, midY], [x2, midY], [x2, ey], [ex, ey]]
  }
  return roundedPath(pts)
}

const DEP_LABEL = { FS: 'finish → start', SS: 'start → start', FF: 'finish → finish' }

const arrows = computed(() => {
  const out = []
  const live = dragLive.value
  const crit = criticalInfo.value
  for (const e of edges.value) {
    const fi = rowIndex.value[e.from], ti = rowIndex.value[e.to]
    if (fi == null || ti == null) continue
    const fr = rows.value[fi], tr = rows.value[ti]
    if (!fr.bar || !tr.bar) continue
    const type = e.dep_type || 'FS'
    // Doctrine point 2: wires attach to the LIVE position of a dragged bar.
    const frLeft = live?.name === fr.name ? live.leftPx : fr.bar.left
    const frW = live?.name === fr.name ? live.wPx : Math.max(dayW.value, fr.bar.w - 3)
    const trLeft = live?.name === tr.name ? live.leftPx : tr.bar.left
    const trW = live?.name === tr.name ? live.wPx : Math.max(dayW.value, tr.bar.w - 3)

    // Anchor per dependency type: the wire leaves the predecessor's FINISH
    // (right) for FS/FF or START (left) for SS, and lands on the successor's
    // START (left) for FS/SS or FINISH (right) for FF.
    const sy = fi * ROW_H + ROW_H / 2
    const ey = ti * ROW_H + ROW_H / 2
    let sx, exitDir, ex, entryDir
    if (fr.bar.milestone) { sx = frLeft + dayW.value / 2 + (type === 'SS' ? -9 : 7); exitDir = type === 'SS' ? -1 : 1 }
    else if (type === 'SS') { sx = frLeft; exitDir = -1 }
    else { sx = frLeft + frW; exitDir = 1 }
    if (tr.bar.milestone) { ex = trLeft + dayW.value / 2 + (type === 'FF' ? 9 : -9); entryDir = type === 'FF' ? -1 : 1 }
    else if (type === 'FF') { ex = trLeft + trW + 2; entryDir = -1 }
    else { ex = trLeft - 2; entryDir = 1 }

    const lagStr = e.lag ? ` ${e.lag > 0 ? '+' : ''}${e.lag}d lag` : ''
    const key = e.from + '→' + e.to
    out.push({
      d: routeEdge(sx, sy, exitDir, ex, ey, entryDir),
      from: e.from,
      to: e.to,
      crit: !!crit?.edges.has(key),
      dimmed: !!crit && !crit.edges.has(key),
      title: `${fr.task_key || e.from} → ${tr.task_key || e.to} (${DEP_LABEL[type]}${lagStr})`,
    })
  }
  return out
})

// ── Critical Path Method (Gantt v2) ──────────────────────────────────────────
// Classic backward pass over the typed constraint graph, on the ACTUAL
// schedule: LF(task) starts at project end and tightens through each outgoing
// constraint (FS: pred.LF ≤ succ.LS − lag · SS: pred.LS ≤ succ.LS − lag ·
// FF: pred.LF ≤ succ.LF − lag). float = LF − F; float ≤ 0 ⇒ critical.
// Day numbers use an EXCLUSIVE finish (day after the last) so the ±1s of
// inclusive date spans can't leak into the math. O(V+E), cycles impossible
// (link creation guards them), computed only while the toggle is on.
const showCritical = ref(false)
const criticalInfo = computed(() => {
  if (!showCritical.value || !range.value) return null
  const nodes = {}
  for (const t of datedTasks.value) {
    const w = windowOf(t)
    if (!w) continue
    const S = diffDays(w[0], range.value.start)
    const F = diffDays(w[1], range.value.start) + 1
    nodes[t.name] = { S, F, LF: Infinity }
  }
  const es = edges.value.filter(e => nodes[e.from] && nodes[e.to])
  const adj = {}, indeg = {}
  for (const n in nodes) indeg[n] = 0
  for (const e of es) { (adj[e.from] ||= []).push(e); indeg[e.to]++ }
  const q = Object.keys(nodes).filter(n => !indeg[n])
  const topo = []
  while (q.length) {
    const n = q.shift()
    topo.push(n)
    for (const e of adj[n] || []) if (--indeg[e.to] === 0) q.push(e.to)
  }
  let projectEnd = -Infinity
  for (const n in nodes) projectEnd = Math.max(projectEnd, nodes[n].F)
  for (const n in nodes) nodes[n].LF = projectEnd
  for (let i = topo.length - 1; i >= 0; i--) {
    const p = nodes[topo[i]]
    for (const e of adj[topo[i]] || []) {
      const s = nodes[e.to]
      const lag = e.lag || 0
      const type = e.dep_type || 'FS'
      const sLS = s.LF - (s.F - s.S)
      const cap = type === 'FS' ? sLS - lag
        : type === 'SS' ? sLS - lag + (p.F - p.S)
        : s.LF - lag // FF
      if (cap < p.LF) p.LF = cap
    }
  }
  const tasks = new Set()
  for (const n in nodes) if (nodes[n].LF - nodes[n].F <= 0) tasks.add(n)
  const critEdges = new Set()
  for (const e of es) {
    if (!tasks.has(e.from) || !tasks.has(e.to)) continue
    const p = nodes[e.from], s = nodes[e.to]
    const lag = e.lag || 0
    const type = e.dep_type || 'FS'
    const slack = type === 'FS' ? s.S - (p.F + lag)
      : type === 'SS' ? s.S - (p.S + lag)
      : s.F - (p.F + lag)
    if (slack <= 0) critEdges.add(e.from + '→' + e.to)
  }
  return { tasks, edges: critEdges }
})

// ── Actions ──────────────────────────────────────────────────────────────────────
function open(r) { if (r?.name) store.openTaskDetail(r.name) }

function scrollToToday(smooth = true) {
  if (!scrollEl.value || todayX.value === null) return
  const target = LEFT_W + todayX.value - scrollEl.value.clientWidth / 2.4
  scrollEl.value.scrollTo({ left: Math.max(0, target), behavior: smooth ? 'smooth' : 'auto' })
}
</script>

<style scoped>
.gt-root { display: flex; flex-direction: column; height: 100%; min-height: 0; }

/* Toolbar */
.gt-toolbar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 20px; flex-shrink: 0;
}
.gt-tb-left { display: flex; align-items: baseline; gap: 10px; }
.gt-tb-title { font-size: var(--text-md); font-weight: var(--font-semibold); color: var(--foreground); letter-spacing: var(--tracking-snug); }
.gt-tb-count { font-size: var(--text-sm); color: var(--muted); }
.gt-tb-right { display: flex; align-items: center; gap: 8px; }
/* Composition Law reference implementation (see ui/DESIGN_PATTERNS.md):
   ghost buttons — no borders, no boxes; hover is a bg tint, never a color
   flip; segmented control = filled track with a lifted active segment. */
.gt-tb-btn {
  height: 28px; padding: 0 10px; border-radius: 6px; border: none;
  background: transparent; color: var(--muted); font-size: var(--text-sm);
  font-weight: var(--font-medium); cursor: pointer; transition: background .12s, color .12s;
}
.gt-tb-btn:hover { background: var(--surface-hover); color: var(--foreground); }
.gt-tb-btn.on { background: var(--surface-secondary); color: var(--foreground); font-weight: var(--font-semibold); }
.gt-seg { display: flex; align-items: center; gap: 2px; background: var(--surface-secondary); border-radius: 8px; padding: 2px; }
.gt-seg-btn { height: 24px; padding: 0 10px; border-radius: 6px; font-size: var(--text-sm); font-weight: var(--font-medium); color: var(--muted); background: transparent; cursor: pointer; transition: background .12s, color .12s; }
.gt-seg-btn:hover { color: var(--foreground); }
.gt-seg-btn.on { background: var(--surface); color: var(--foreground); font-weight: var(--font-semibold); box-shadow: var(--shadow-xs); }

/* States */
.gt-state { flex: 1; display: grid; place-items: center; }
.gt-spinner { width: 24px; height: 24px; border: 2.5px solid var(--border); border-top-color: var(--accent); border-radius: 50%; animation: gt-spin .7s linear infinite; }
@keyframes gt-spin { to { transform: rotate(360deg) } }
.gt-empty { text-align: center; color: var(--muted); max-width: 280px; }
.gt-empty svg { color: var(--border-secondary); margin-bottom: 12px; }
.gt-empty-t { font-size: var(--text-base); font-weight: var(--font-semibold); color: var(--muted); }
.gt-empty-s { font-size: var(--text-sm); color: var(--muted); margin-top: 4px; }

/* Scroll surface */
.gt-scroll {
  flex: 1; min-height: 0; overflow: auto; position: relative;
  margin: 0 20px 16px; border: 1px solid var(--border); border-radius: 10px;
  background: var(--surface);
  user-select: none; /* pan/link drags must never start a text selection */
}
/* Fill the container even when the timeline is narrower than the viewport
   (otherwise zoomed-out charts only cover the left "half page"). */
.gt-grid { position: relative; min-width: 100%; box-sizing: border-box; }

/* Header */
.gt-head { position: sticky; top: 0; z-index: 5; display: flex; background: var(--surface); border-bottom: 1px solid var(--border); }
.gt-corner {
  position: sticky; left: 0; z-index: 6; flex-shrink: 0;
  display: flex; align-items: flex-end; padding: 0 16px 9px;
  background: var(--surface); border-right: 1px solid var(--border);
  font-size: var(--text-xs); font-weight: var(--font-semibold); text-transform: uppercase;
  letter-spacing: .04em; color: var(--muted);
}
.gt-head-time { position: relative; flex-shrink: 0; }
.gt-months { position: absolute; inset: 0 0 auto 0; height: 28px; }
.gt-month { position: absolute; top: 0; height: 28px; display: flex; align-items: center; padding-left: 10px; box-sizing: border-box; }
.gt-month span { font-size: var(--text-sm); font-weight: var(--font-semibold); color: var(--foreground); letter-spacing: var(--tracking-snug); }
.gt-daystrip { position: absolute; left: 0; right: 0; top: 28px; bottom: 0; }
.gt-day { position: absolute; top: 0; bottom: 0; display: flex; align-items: center; justify-content: center; box-sizing: border-box; font-size: var(--text-xs); color: var(--muted); border-left: 1px solid color-mix(in srgb, var(--surface-secondary) 60%, transparent); }
.gt-day.is-weekend { color: var(--border-secondary); }
.gt-day.is-today { color: var(--accent); font-weight: var(--font-bold); }
/* today marker: circled date in the strip + triangle cap where
   the line meets the header. */
.gt-day.is-today span {
  min-width: 20px; height: 20px; display: inline-grid; place-items: center;
  padding: 0 3px; background: var(--accent); color: var(--accent-foreground);
  border-radius: 999px; font-weight: var(--font-semibold);
}
.gt-today-cap {
  position: absolute; bottom: -1px; transform: translateX(-50%); z-index: 2;
  width: 0; height: 0; pointer-events: none;
  border-left: 5px solid transparent; border-right: 5px solid transparent;
  border-top: 6px solid var(--accent);
}

/* Rows — absolutely positioned (top = idx*ROW_H) so virtualization can drop
   off-screen rows from the DOM without collapsing scroll height. */
.gt-rows { position: relative; }
.gt-row { position: absolute; left: 0; right: 0; display: flex; }
.gt-label {
  position: sticky; left: 0; z-index: 3; flex-shrink: 0; box-sizing: border-box;
  display: flex; align-items: center; gap: 7px; padding: 0 14px;
  background: var(--surface); border-right: 1px solid var(--border);
  border-bottom: 1px solid var(--surface-secondary); cursor: pointer;
}
.gt-label.hov { background: var(--surface-hover); }
.gt-label-indent { flex-shrink: 0; }
.gt-epic-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.gt-label-indent { width: 4px; flex-shrink: 0; }
.gt-key { font-size: var(--text-xs); font-weight: var(--font-semibold); color: var(--muted); font-family: var(--font-mono); flex-shrink: 0; }
.gt-name { flex: 1; min-width: 0; font-size: var(--text-sm); color: var(--foreground); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.gt-date { flex-shrink: 0; font-size: var(--text-xs); color: var(--muted); white-space: nowrap; padding-left: 6px; }
.gt-erp-badge { flex-shrink: 0; height: 16px; padding: 0 5px; font-size:var(--text-micro); font-weight: 700; letter-spacing: .02em; color: var(--accent-soft-foreground); background: var(--accent-soft); border: none; border-radius: 3px; cursor: pointer; }
.gt-billable-badge { flex-shrink: 0; display: inline-flex; align-items: center; justify-content: center; width: 16px; height: 16px; font-size:var(--text-micro); font-weight: 800; color: var(--success-soft-foreground); background: var(--success-soft); border-radius: 3px; }
.gt-rowtrack { flex: 1; box-sizing: border-box; border-bottom: 1px solid var(--surface-secondary); }
.gt-rowtrack.hov { background: color-mix(in srgb, var(--surface-secondary) 55%, transparent); }

/* Group header rows */
.gt-row.is-group .gt-rowtrack { background: var(--surface-hover); border-bottom-color: var(--border); }
.gt-glabel { background: var(--surface-hover); border-bottom-color: var(--border); cursor: pointer; gap: 7px; }
.gt-glabel:hover { background: var(--surface-secondary); }
.gt-chevron { color: var(--muted); flex-shrink: 0; transform: rotate(90deg); transition: transform .15s; }
.gt-chevron.collapsed { transform: rotate(0deg); }
.gt-gdot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.gt-gname { flex: 0 1 auto; min-width: 0; font-size: var(--text-sm); font-weight: var(--font-semibold); color: var(--foreground); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.gt-gcount { flex-shrink: 0; font-size:var(--text-xs); font-weight: var(--font-semibold); color: var(--muted); background: var(--surface-secondary); padding: 1px 7px; border-radius: 999px; font-variant-numeric: tabular-nums; }
.gt-gdate { margin-left: auto; flex-shrink: 0; font-size: var(--text-xs); color: var(--muted); white-space: nowrap; padding-left: 6px; }

/* Group summary bar — bracket with notched ends spanning children
   (Bryntum/dhtmlx cherry-pick), not a plain flat bar. */
.gt-groupbar { position: absolute; z-index: 2; height: 4px; border-radius: 1px; opacity: .95; pointer-events: none; }
.gt-groupbar::before, .gt-groupbar::after {
  content: ''; position: absolute; top: -3px; width: 2px; height: 10px;
  background: inherit; border-radius: 1px;
}
.gt-groupbar::before { left: 0; }
.gt-groupbar::after { right: 0; }

/* Timeline overlay */
.gt-overlay { position: absolute; top: 0; z-index: 1; pointer-events: none; }
/*faint grid: the canvas must read as whitespace, not gray haze */
.gt-wkcol { position: absolute; top: 0; bottom: 0; background: color-mix(in srgb, var(--surface-secondary) 30%, transparent); }
.gt-todayline {
  position: absolute; top: 0; bottom: 0; width: 2px; background: var(--accent);
  opacity: .6; box-shadow: 0 0 6px color-mix(in srgb, var(--accent) 45%, transparent);
}

/* Pan cursors: empty timeline reads as grabbable; Space arms the hand tool
   everywhere; while actually panning everything shows the closed hand. */
.gt-rowtrack { cursor: grab; }
.gt-scroll.space-pan, .gt-scroll.space-pan * { cursor: grab !important; }
.gt-scroll.panning, .gt-scroll.panning * { cursor: grabbing !important; }

.gt-msline { position: absolute; top: 0; bottom: 0; width: 0; border-left: 1px dashed var(--warning); opacity: .8; pointer-events: none; }
.gt-msline .gt-msdiamond { position: absolute; top: 3px; left: -4.5px; width: 8px; height: 8px; transform: rotate(45deg); background: var(--warning); border-radius: 1px; pointer-events: auto; cursor: default; }
.gt-msline.done { border-color: var(--success); opacity: .5; }
.gt-msline.done .gt-msdiamond { background: var(--success); }
.gt-msline.overdue { border-color: var(--danger); }
.gt-msline.overdue .gt-msdiamond { background: var(--danger); }
.gt-arrows { position: absolute; top: 0; left: 0; overflow: visible; }
/* Wires are interactive: hover lights the dependency and the <title> names
   it ("FWD-1 blocks FWD-2"). pointer-events re-enabled per-path (the parent
   overlay is pointer-events:none). */
.gt-arrow {
  fill: none; stroke: var(--muted); stroke-width: 1.5; opacity: .5;
  pointer-events: stroke; cursor: default;
  transition: opacity .12s, stroke .12s;
}
.gt-arrow:hover { stroke: var(--accent); opacity: 1; stroke-width: 2; }
/* Critical-path mode: the zero-slack chain in danger red, everything else recedes */
.gt-arrow.crit { stroke: var(--danger); stroke-width: 2; opacity: .95; }
.gt-arrow.dimmed { opacity: .12; }
.gt-bar.dim { opacity: .3; }
.gt-bar.crit { box-shadow: 0 0 0 2px var(--danger), 0 1px 2px rgba(11,13,14,.1); }

/* Bars —  rounded RECT, not a pill */
.gt-bar {
  position: absolute; z-index: 2; pointer-events: auto; cursor: pointer;
  border-radius: 4px; display: flex; align-items: center; overflow: visible;
  /* Doctrine point 1: the bar's transform belongs to XL-B's drag engine —
     never transition it, and never let hover own it. Lift = filter+shadow. */
  box-shadow: 0 1px 2px rgba(11,13,14,.1); transition: filter .12s, box-shadow .12s;
}
.gt-bar:hover, .gt-bar.hov { filter: brightness(1.07) saturate(1.05); box-shadow: 0 4px 10px rgba(11,13,14,.18); z-index: 3; }
.gt-bar-fill { position: absolute; inset: 0; border-radius: inherit; }
.gt-bar-prog { position: absolute; left: 0; top: 0; bottom: 0; background: rgba(11,13,14,.16); border-radius: 4px 0 0 4px; }

/* Connection dots — appear on bar hover at both edges; drag one onto
   another bar to draw a dependency. */
.gt-dot {
  position: absolute; top: 50%; width: 9px; height: 9px; z-index: 4;
  transform: translateY(-50%); border-radius: 50%;
  background: var(--surface); border: 2px solid var(--accent);
  opacity: 0; transition: opacity .15s, box-shadow .15s;
  cursor: crosshair; box-sizing: border-box;
}
/* Floating a few px OFF the bar — a connector affordance,
   not part of the rectangle. */
.gt-dot-l { left: -14px; }
.gt-dot-r { right: -14px; }
.gt-bar:hover .gt-dot, .gt-bar.hov .gt-dot { opacity: 1; }
.gt-dot:hover { box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 25%, transparent); }
/* Valid drop target while a wire is being drawn */
.gt-bar.link-target { outline: 2px solid var(--accent); outline-offset: 2px; filter: brightness(1.08); }
.gt-linkpreview {
  fill: none; stroke: var(--accent); stroke-width: 2; stroke-dasharray: 5 4;
  pointer-events: none; opacity: .9;
}

/* XL-B: resize grips (invisible zones, the cursor is the affordance),
   drag ghost + floating date chip, and the lifted dragging state. */
.gt-rsz { position: absolute; top: 0; bottom: 0; width: 9px; z-index: 3; cursor: ew-resize; }
.gt-rsz-l { left: -2px; }
.gt-rsz-r { right: -2px; }
.gt-bar.dragging { box-shadow: 0 6px 16px rgba(11,13,14,.26); z-index: 5; cursor: grabbing; opacity: .92; }
.gt-ghost {
  position: absolute; z-index: 1; border-radius: 4px; pointer-events: none;
  border: 1.5px dashed var(--accent);
  background: color-mix(in srgb, var(--accent) 8%, transparent);
}
.gt-dragchip {
  position: absolute; z-index: 6; pointer-events: none; white-space: nowrap;
  font-size:var(--text-xs); font-weight: var(--font-semibold); color: var(--accent-foreground);
  background: var(--accent); padding: 2px 8px; border-radius: 999px;
  box-shadow: var(--shadow-sm); font-variant-numeric: tabular-nums;
}
/* Done bars stay SOLID — fading half the chart to
   55% pastel is what made the canvas read washed-out. Done-ness is the ✓. */
.gt-bar-check {
  position: relative; z-index: 1; flex-shrink: 0; padding-right: 7px;
  color: var(--accent-foreground); font-size:var(--text-xs); font-weight: var(--font-bold);
  text-shadow: 0 1px 1.5px rgba(0,0,0,.25);
}
/* Label + avatars live inside the bar once there's room (see the
   w>=64 branch in the template) — flex children of .gt-bar, laid out over
   the absolutely-positioned fill/progress layers beneath them. */
.gt-bar-in {
  position: relative; z-index: 1; flex: 1; min-width: 0; padding: 0 11px;
  color: var(--accent-foreground); font-size: var(--text-sm); font-weight: var(--font-semibold);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  text-shadow: 0 1px 1.5px rgba(0,0,0,.22);
}
.gt-bar-avs-inline { position: relative; z-index: 2; display: flex; align-items: center; flex-shrink: 0; padding-left: 6px; padding-right: 2px; }
.gt-av-img { width: 100%; height: 100%; object-fit: cover; border-radius: 50%; display: block; }
.gt-bar-out {
  position: absolute; left: calc(100% + 8px); top: 50%; transform: translateY(-50%);
  font-size: var(--text-sm); color: var(--muted); white-space: nowrap; pointer-events: none;
}
.gt-bar-avs { position: absolute; right: 4px; top: 50%; transform: translateY(-50%); z-index: 2; display: flex; align-items: center; }
.gt-bar-av { width: 19px; height: 19px; border-radius: 50%; display: grid; place-items: center; color: var(--accent-foreground); font-size:var(--text-micro); font-weight: var(--font-bold); flex-shrink: 0; }
.gt-bar-more { background: var(--muted); }
.gt-bar.milestone { background: transparent !important; box-shadow: none; width: 14px; height: 14px; }
.gt-diamond { width: 12px; height: 12px; border-radius: 3px; transform: rotate(45deg); box-shadow: 0 1px 2px rgba(11,13,14,.2); }

/* Epic header rows (reserved for grouping) */
.gt-row.is-epic .gt-label { font-weight: var(--font-semibold); }
</style>
