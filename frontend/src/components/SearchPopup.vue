<template>
<Teleport to="body">
<Transition name="sp-fade">
<div v-if="open" class="sp-root">
  <div class="sp-backdrop" @click="close"/>

  <div class="sp-panel">
    <!-- Search input -->
    <div class="sp-input-row">
      <svg class="sp-icon" width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
        <circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/>
      </svg>
      <input
        ref="inputEl"
        v-model="query"
        class="sp-input"
        placeholder="Search tasks or run a command…"
        @keydown.escape="close"
        @keydown.down.prevent="moveDown"
        @keydown.up.prevent="moveUp"
        @keydown.enter.prevent="confirmSelected"
      />
      <span class="sp-esc-hint">esc</span>
    </div>

    <!-- Filter chips -->
    <div v-if="activeFilters.length || query" class="sp-filter-row">
      <span
        v-for="f in activeFilters" :key="f.key"
        class="sp-chip"
        :style="{ background: f.color + '18', color: f.color, borderColor: f.color + '40' }"
      >
        {{ f.label }}: <strong>{{ f.value }}</strong>
        <button class="sp-chip-x" @click="removeFilter(f.key)">×</button>
      </span>

      <!-- Syntax hints -->
      <span v-if="syntaxHint" class="sp-syntax-hint">{{ syntaxHint }}</span>
    </div>

    <!-- Commands (Cmd+K palette) -->
    <div v-if="matchedCommands.length" class="sp-cmd-section">
      <p class="sp-section-label">Commands</p>
      <div
        v-for="(c, i) in matchedCommands" :key="c.id"
        class="sp-cmd"
        :class="{ 'sp-cmd--active': selectedIdx === i }"
        @mouseenter="selectedIdx = i"
        @click="c.run()"
      >
        <span class="sp-cmd-ic">
          <svg width="13" height="13" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M13 7l5 5-5 5M6 7l5 5-5 5"/></svg>
        </span>
        <span class="sp-cmd-label">{{ c.label }}</span>
      </div>
    </div>

    <!-- Quick filters -->
    <div v-if="!query && !activeFilters.length" class="sp-quick-row">
      <span class="sp-quick-label">Quick filters</span>
      <button class="sp-quick-btn" @click="applyFilter('assignee', myName, 'var(--accent)')">
        <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/></svg>
        My tasks
      </button>
      <button class="sp-quick-btn" @click="applyFilter('priority', 'Highest', '#EF4444')">
        Highest priority
      </button>
      <button class="sp-quick-btn" @click="applyFilter('priority', 'High', '#F97316')">
        High priority
      </button>
      <button v-if="store.activeSprints?.length" class="sp-quick-btn" @click="applyFilter('sprint', store.activeSprints[0]?.sprint_name, '#00B8D9')">
        Current sprint
      </button>
    </div>

    <!-- Syntax guide -->
    <div v-if="showSyntaxGuide && !query" class="sp-syntax-guide">
      <p class="sp-sg-title">Search syntax</p>
      <div class="sp-sg-grid">
        <span class="sp-sg-code">assignee:me</span><span class="sp-sg-desc">Tasks assigned to you</span>
        <span class="sp-sg-code">priority:High</span><span class="sp-sg-desc">By priority level</span>
        <span class="sp-sg-code">status:Done</span><span class="sp-sg-desc">By workflow status</span>
        <span class="sp-sg-code">type:Bug</span><span class="sp-sg-desc">By task type</span>
        <span class="sp-sg-code">label:frontend</span><span class="sp-sg-desc">By label</span>
        <span class="sp-sg-code">sprint:active</span><span class="sp-sg-desc">Current sprint tasks</span>
      </div>
    </div>

    <!-- Divider -->
    <div v-if="results.length || loading || query" class="sp-divider"/>

    <!-- Loading -->
    <div v-if="loading" class="sp-loading">
      <div class="sp-spinner"/>Searching…
    </div>

    <!-- Results -->
    <div v-else-if="results.length" class="sp-results" ref="resultsEl">
      <p class="sp-section-label">Tasks</p>
      <div
        v-for="(r, i) in results" :key="r.name"
        class="sp-result"
        :class="{ 'sp-result--active': selectedIdx === matchedCommands.length + i }"
        @mouseenter="selectedIdx = matchedCommands.length + i"
        @click="openTask(r)"
      >
        <span class="sp-r-type" :style="{ background: taskTypeColor(r.task_type) }">{{ r.task_type?.charAt(0) || 'T' }}</span>
        <span class="sp-r-key">{{ r.task_key }}</span>
        <span class="sp-r-title">{{ r.title }}</span>
        <span class="sp-r-status" :style="{ background: wfColor(r.status) + '1A', color: wfColor(r.status) }">{{ r.status }}</span>
        <span v-if="r.priority" class="sp-r-priority">
          <PriorityIcon :priority="r.priority"/>
        </span>
      </div>
    </div>

    <!-- No results -->
    <div v-else-if="query && !loading" class="sp-empty">
      <svg width="32" height="32" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5" style="color:var(--border);margin-bottom:8px"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>
      <p>No tasks found for <strong>"{{ query }}"</strong></p>
      <p class="sp-empty-sub">Try different keywords or use <span class="sp-sg-code-inline">syntax:filters</span></p>
    </div>

    <!-- Footer -->
    <div class="sp-footer">
      <span class="sp-footer-hint">
        <kbd>↑↓</kbd> navigate
        <kbd>↵</kbd> open
        <kbd>esc</kbd> close
      </span>
      <button class="sp-syntax-toggle" @click="showSyntaxGuide = !showSyntaxGuide">
        <svg width="11" height="11" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/></svg>
        {{ showSyntaxGuide ? 'Hide' : 'Search syntax' }}
      </button>
    </div>
  </div>
</div>
</Transition>
</Teleport>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { debounce } from 'lodash'
import { useProjectStore } from '@/stores/project'
import { searchTasks } from '@/utils/api.js'
import PriorityIcon from '@/components/PriorityIcon.vue'

const props = defineProps({ modelValue: { type: Boolean, default: false } })
const emit  = defineEmits(['update:modelValue'])

const store     = useProjectStore()
const router    = useRouter()
const route     = useRoute()
const inputEl   = ref(null)
const resultsEl = ref(null)
const open      = computed(() => props.modelValue)

const query          = ref('')
const results        = ref([])
const loading        = ref(false)
const selectedIdx    = ref(0)
const showSyntaxGuide = ref(false)
const filters        = ref({}) // { assignee, priority, status, type, label, sprint }

function close() { emit('update:modelValue', false) }

const myName = computed(() => window?.frappe?.session?.user_fullname || 'Me')

// ── Syntax parsing ────────────────────────────────────────────────────────
const SYNTAX_KEYS = ['assignee', 'priority', 'status', 'type', 'label', 'sprint']

const parsedQuery = computed(() => {
  let q = query.value
  const parsed = {}
  for (const key of SYNTAX_KEYS) {
    const match = q.match(new RegExp(`\\b${key}:([\\w\\-]+|"[^"]*")`, 'i'))
    if (match) {
      parsed[key] = match[1].replace(/^"|"$/g, '')
      q = q.replace(match[0], '').trim()
    }
  }
  return { text: q, filters: parsed }
})

const activeFilters = computed(() => {
  const all = { ...filters.value, ...parsedQuery.value.filters }
  const COLOR = { assignee:'#0052CC', priority:'#F97316', status:'#00875A', type:'#6554C0', label:'#00B8D9', sprint:'#FF8B00' }
  return Object.entries(all)
    .filter(([,v]) => v)
    .map(([k, v]) => ({ key: k, label: k, value: v, color: COLOR[k] || 'var(--muted)' }))
})

const syntaxHint = computed(() => {
  const q = query.value
  for (const key of SYNTAX_KEYS) {
    if (q.endsWith(key + ':')) return `Type a value after ${key}:`
  }
  return null
})

function applyFilter(key, value, color) {
  filters.value[key] = value
  inputEl.value?.focus()
  doSearch()
}

function removeFilter(key) {
  delete filters.value[key]
  // Also remove from query string
  query.value = query.value.replace(new RegExp(`\\b${key}:[\\w\\-]+`, 'i'), '').trim()
  doSearch()
}

// ── Search ─────────────────────────────────────────────────────────────────
const doSearch = debounce(async () => {
  const { text, filters: syntaxFilters } = parsedQuery.value
  const allFilters = { ...filters.value, ...syntaxFilters }
  if (!text && !Object.values(allFilters).some(Boolean)) {
    results.value = []
    return
  }
  loading.value = true
  selectedIdx.value = 0
  try {
    results.value = await searchTasks(
      text,
      store.currentProject?.name,
      null
    )
    // Client-side filter by syntax filters
    if (Object.keys(allFilters).length) {
      results.value = results.value.filter(r => {
        if (allFilters.priority && r.priority !== allFilters.priority) return false
        if (allFilters.status && r.status !== allFilters.status) return false
        if (allFilters.type && r.task_type !== allFilters.type) return false
        if (allFilters.label && !(r.labels || []).includes(allFilters.label)) return false
        if (allFilters.assignee) {
          const val = allFilters.assignee.toLowerCase()
          const me = val === 'me' || val === myName.value.toLowerCase().split(' ')[0]
          if (me) {
            const myUser = window?.frappe?.session?.user
            if (!r.assignees?.some(a => a.user === myUser || a.full_name?.toLowerCase().includes(val))) return false
          } else {
            if (!r.assignees?.some(a => a.full_name?.toLowerCase().includes(val))) return false
          }
        }
        return true
      })
    }
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}, 250)

watch(query, doSearch)

// ── Commands (Cmd+K palette) ─────────────────────────────────────────────────
const VIEW_LABEL = { summary:'Summary', board:'Board', list:'List', backlog:'Backlog', gantt:'Timeline', reports:'Reports', notes:'Notes', draw:'Draw' }
const projectKey = computed(() => route.params.key)

const commands = computed(() => {
  const k = projectKey.value
  const cmds = [{ id:'new-task', label:'Create task', kw:'new add issue', run:() => { store.showCreateTask = true; close() } }]
  if (k) {
    const views = store.currentProject?.enabled_views || ['summary', 'board', 'list']
    for (const v of views) {
      if (VIEW_LABEL[v]) cmds.push({ id:'view-'+v, label:'Go to '+VIEW_LABEL[v], kw:'view open '+v, run:() => { router.push(`/workspace/${k}/${v}`); close() } })
    }
    cmds.push({ id:'settings', label:'Project settings', kw:'config', run:() => { router.push(`/workspace/${k}/settings`); close() } })
  }
  cmds.push({ id:'my-tasks', label:'Go to My Tasks', kw:'assigned', run:() => { router.push('/workspace/my-tasks'); close() } })
  cmds.push({ id:'all-projects', label:'Go to All Projects', kw:'switch', run:() => { router.push('/workspace/all'); close() } })
  cmds.push({ id:'reports', label:'Go to Reports', kw:'analytics insights', run:() => { router.push('/workspace/reports'); close() } })
  return cmds
})

const matchedCommands = computed(() => {
  // Suppress commands while a syntax filter is active (pure issue search).
  if (Object.keys(filters.value).length || Object.keys(parsedQuery.value.filters).length) return []
  const t = (parsedQuery.value.text || '').trim().toLowerCase()
  const list = t ? commands.value.filter(c => c.label.toLowerCase().includes(t) || c.kw.includes(t)) : commands.value
  return list.slice(0, 7)
})

// Unified, keyboard-navigable list: commands first, then issue results.
const navItems = computed(() => [
  ...matchedCommands.value.map(c => ({ kind:'cmd', cmd:c })),
  ...results.value.map(r => ({ kind:'task', task:r })),
])

// ── Keyboard navigation ────────────────────────────────────────────────────
function moveDown() {
  if (navItems.value.length) selectedIdx.value = Math.min(selectedIdx.value + 1, navItems.value.length - 1)
}
function moveUp() {
  selectedIdx.value = Math.max(selectedIdx.value - 1, 0)
}
function confirmSelected() {
  const item = navItems.value[selectedIdx.value]
  if (!item) return
  if (item.kind === 'cmd') item.cmd.run()
  else openTask(item.task)
}

function openTask(r) {
  store.openTaskDetail(r.name)
  close()
}

// ── Colors ─────────────────────────────────────────────────────────────────
function taskTypeColor(t) { return store.taskTypeMap?.[t]?.color || 'var(--accent)' }
function wfColor(s) { return store.workflowStateMap?.[s]?.color || 'var(--muted)' }

// ── Lifecycle ──────────────────────────────────────────────────────────────
watch(open, async (v) => {
  if (v) {
    query.value = ''
    results.value = []
    filters.value = {}
    selectedIdx.value = 0
    showSyntaxGuide.value = false
    await nextTick()
    inputEl.value?.focus()
  }
})

function onKeydown(e) {
  if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
    e.preventDefault()
    if (open.value) close()
    else emit('update:modelValue', true)
  }
}

onMounted(() => document.addEventListener('keydown', onKeydown))
onUnmounted(() => document.removeEventListener('keydown', onKeydown))
</script>

<style scoped>
.sp-root {
  position: fixed; inset: 0; z-index: 999;
  display: flex; align-items: flex-start; justify-content: center;
  padding-top: 80px;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  -webkit-font-smoothing: antialiased;
}
.sp-backdrop {
  position: fixed; inset: 0;
  background: rgba(9, 30, 66, 0.5);
}
.sp-panel {
  position: relative; z-index: 1;
  width: 640px; max-width: calc(100vw - 32px);
  background: var(--overlay);
  border-radius: 10px;
  box-shadow: 0 20px 60px rgba(9, 30, 66, 0.28), 0 4px 16px rgba(9, 30, 66, 0.12);
  overflow: hidden;
  display: flex; flex-direction: column;
}

/* Input row */
.sp-input-row {
  display: flex; align-items: center; gap: 10px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--surface-secondary);
}
.sp-icon { color: var(--muted); flex-shrink: 0; }
.sp-input {
  flex: 1; font-size: 15px; font-family: inherit;
  color: var(--foreground); background: none; border: none; outline: none;
}
.sp-input::placeholder { color: var(--muted); }
.sp-esc-hint {
  font-size: 10.5px; font-weight: 600; color: var(--muted);
  background: var(--surface-secondary); padding: 2px 6px; border-radius: 4px;
  border: 1px solid var(--border); letter-spacing: .03em;
  flex-shrink: 0;
}

/* Filter chips */
.sp-filter-row {
  display: flex; flex-wrap: wrap; align-items: center; gap: 5px;
  padding: 8px 16px;
  border-bottom: 1px solid var(--surface-secondary);
}
.sp-chip {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 2px 8px; border-radius: 4px;
  font-size: 11.5px; font-weight: 500;
  border: 1px solid transparent;
}
.sp-chip-x {
  border: none; background: none; cursor: pointer;
  font-size: 13px; line-height: 1; padding: 0; opacity: .7;
}
.sp-chip-x:hover { opacity: 1; }
.sp-syntax-hint { font-size: 11.5px; color: var(--muted); font-style: italic; }

/* Quick filters */
.sp-quick-row {
  display: flex; flex-wrap: wrap; align-items: center; gap: 6px;
  padding: 10px 16px;
  border-bottom: 1px solid var(--surface-secondary);
}
.sp-quick-label { font-size: 10.5px; font-weight: 700; color: var(--muted); text-transform: uppercase; letter-spacing: .05em; margin-right: 4px; }
.sp-quick-btn {
  display: inline-flex; align-items: center; gap: 5px;
  height: 24px; padding: 0 10px;
  font-size: 12px; font-weight: 500; font-family: inherit;
  color: var(--foreground); background: var(--surface-secondary);
  border: 1px solid var(--border); border-radius: 5px; cursor: pointer;
  transition: background .08s, border-color .08s;
}
.sp-quick-btn:hover { background: var(--surface-secondary); border-color: var(--border); }
.sp-quick-btn svg { color: var(--muted); }

/* Syntax guide */
.sp-syntax-guide {
  padding: 12px 16px;
  border-bottom: 1px solid var(--surface-secondary);
  background: var(--surface-secondary);
}
.sp-sg-title { font-size: 10.5px; font-weight: 700; color: var(--muted); text-transform: uppercase; letter-spacing: .05em; margin: 0 0 8px; }
.sp-sg-grid {
  display: grid; grid-template-columns: auto 1fr;
  gap: 4px 12px; align-items: center;
}
.sp-sg-code {
  font-size: 11.5px; font-family: 'SFMono-Regular', Consolas, monospace;
  color: var(--accent); background: var(--accent-soft); padding: 1px 6px; border-radius: 3px;
  white-space: nowrap;
}
.sp-sg-desc { font-size: 12px; color: var(--muted); }

/* Divider */
.sp-divider { height: 1px; background: var(--surface-secondary); }

/* Loading */
.sp-loading {
  display: flex; align-items: center; gap: 8px;
  padding: 16px; font-size: 13px; color: var(--muted);
}
.sp-spinner {
  width: 14px; height: 14px; border-radius: 50%;
  border: 2px solid var(--border); border-top-color: var(--accent);
  animation: sp-spin .6s linear infinite; flex-shrink: 0;
}
@keyframes sp-spin { to { transform: rotate(360deg) } }

/* Results */
.sp-section-label { font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); padding: 6px 14px 3px; margin: 0; }
.sp-cmd-section { padding-bottom: 4px; }
.sp-cmd {
  display: flex; align-items: center; gap: 9px;
  padding: 8px 14px; cursor: pointer;
  transition: background .08s;
}
.sp-cmd:hover, .sp-cmd--active { background: var(--surface-secondary); }
.sp-cmd-ic {
  width: 18px; height: 18px; border-radius: 4px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  color: var(--muted); background: var(--surface-secondary);
}
.sp-cmd--active .sp-cmd-ic { color: var(--accent); }
.sp-cmd-label { flex: 1; font-size: 13px; font-weight: 500; color: var(--foreground); }
.sp-results { max-height: 360px; overflow-y: auto; }
.sp-result {
  display: flex; align-items: center; gap: 8px;
  padding: 9px 14px; cursor: pointer;
  transition: background .08s;
}
.sp-result:hover, .sp-result--active { background: var(--surface-secondary); }
.sp-r-type {
  width: 16px; height: 16px; border-radius: 3px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  color: var(--accent-foreground); font-size: 8px; font-weight: 700;
}
.sp-r-key { font-size: 11px; font-weight: 700; color: var(--accent); font-family: monospace; white-space: nowrap; flex-shrink: 0; }
.sp-r-title { flex: 1; font-size: 13px; color: var(--foreground); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.sp-r-status {
  font-size: 10px; font-weight: 700; padding: 1px 7px; border-radius: 3px;
  flex-shrink: 0; white-space: nowrap; text-transform: uppercase; letter-spacing: .03em;
}
.sp-r-priority { flex-shrink: 0; }

/* Empty */
.sp-empty {
  display: flex; flex-direction: column; align-items: center;
  padding: 32px 16px; color: var(--muted); font-size: 13px; text-align: center;
}
.sp-empty p { margin: 0 0 4px; }
.sp-empty-sub { font-size: 12px; color: var(--muted); }
.sp-sg-code-inline { font-family: monospace; font-size: 11px; background: var(--surface-secondary); padding: 1px 5px; border-radius: 3px; color: var(--foreground); }

/* Footer */
.sp-footer {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 14px;
  border-top: 1px solid var(--surface-secondary);
  background: var(--surface-secondary);
}
.sp-footer-hint { display: flex; align-items: center; gap: 8px; font-size: 11.5px; color: var(--muted); }
.sp-footer-hint kbd {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 18px; height: 18px; padding: 0 4px;
  background: var(--surface-secondary); border: 1px solid var(--border); border-radius: 3px;
  font-size: 10px; font-family: inherit; color: var(--muted);
}
.sp-syntax-toggle {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: 11.5px; font-weight: 500; color: var(--accent);
  background: none; border: none; cursor: pointer; font-family: inherit;
  padding: 2px 4px; border-radius: 3px; transition: background .08s;
}
.sp-syntax-toggle:hover { background: var(--accent-soft); }

/* Transition */
.sp-fade-enter-active { transition: opacity .12s, transform .12s; }
.sp-fade-leave-active { transition: opacity .08s; }
.sp-fade-enter-from, .sp-fade-leave-to { opacity: 0; transform: translateY(-6px); }
</style>