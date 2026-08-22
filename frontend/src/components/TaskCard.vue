<
<template>
  <div
    :data-issue="issue.name"
    draggable="true"
    @dragstart.stop="onDragStart"
    @dragend.stop="onDragEnd"
    @click.stop="$emit('click')"
    @contextmenu.prevent="onContextMenu"
    :class="[
      'group relative bg-overlay rounded-[5px] mb-2.5 py-4 px-3.5 cursor-grab active:cursor-grabbing select-none',
      'shadow-sm border-[1px] border-gray-200',
      'hover:border-border-secondary',
      'transition-[box-shadow,border-color,opacity,transform] duration-150 ease-[cubic-bezier(0.25,0.1,0.25,1)]',
      isDragging ? 'opacity-60 scale-[0.97] rotate-1' : ''
    ]"
  >
  
    <!-- Title -->
    <h3
      class="text-md flex space-x-2 text-foreground font-semibold leading-snug tracking-tight line-clamp-2"
    >
      <!-- Task type icon (smaller, more subtle) -->
          
            <span>
              {{ issue.title }}
            </span>
    </h3>
    <p
      v-html="issue.description"
      class="text-sm mt-1 line-clamp-2 font-medium text-gray-500 leading-snug tracking-tight mb-3"
    ></p>

    <!-- ERP references + billable -->
    <div v-if="erpBadges.length || isBillable || issue.blocked_reason" class="flex items-center gap-1.5 mb-2 flex-wrap">
      <button
        v-for="g in erpBadges" :key="g.doctype"
        class="tc-erp-badge"
        :title="g.items.map(r => r.ref_label || r.ref_name).join(', ')"
        @click.stop="$emit('open-erp-doc', g.items[0].ref_doctype, g.items[0].ref_name)"
      >{{ g.abbr }}<template v-if="g.n > 1">×{{ g.n }}</template></button>
      <span v-if="isBillable" class="tc-billable-badge" :title="`${issue.estimated_hours}h billable`">$</span>
      <span v-if="issue.blocked_reason" class="tc-blocked-badge" :title="blockedMeta">
        <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.3 2.65a1.73 1.73 0 001.23 1.67L10.4 19.5a1.73 1.73 0 001.62 0l6.48-2.43a1.73 1.73 0 001.22-1.67V8.44a1.73 1.73 0 00-1.22-1.67l-6.48-2.43a1.73 1.73 0 00-1.62 0L3.94 6.77A1.73 1.73 0 002.7 8.44v6.96zM12 15.75h.008v.008H12v-.008z"/>
        </svg>
      </span>
      <button
        v-for="chip in mirrorChips" :key="chip.key"
        class="tc-mirror-chip"
        :title="`${chip.label}: ${chip.text}`"
        @click.stop="$emit('open-erp-doc', chip.doctype, chip.name)"
      >{{ chip.label }}: {{ chip.text }}</button>
    </div>

    <div class=" mb-3">
             <!-- Meta row: Due date + Progress -->
      <div
        v-if="issue.due_date || issue.sub_tasks?.length"
        class="flex items-center gap-3"
      >
        <!-- Due date pill -->
        <span
          v-if="issue.due_date"
          :class="[
            'inline-flex items-center gap-1 px-2 py-0.5 rounded-xs text-xs font-semibold',
            isOverdue
              ? ' text-danger-soft-foreground bg-danger-soft border border-danger'
              : isDueSoon
              ? ' text-warning-soft-foreground bg-warning-soft border border-warning'
              : ' text-muted bg-default border border-border'
          ]"
        >
          <svg
            v-if="isOverdue"
            class="w-3 h-3"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            stroke-width="2.5"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"
            />
          </svg>
          <svg
            v-else-if="isDueSoon"
            class="w-3 h-3"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            stroke-width="2.5"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          <svg
            v-else
            class="w-3 h-3"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            stroke-width="2"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5"
            />
          </svg>
          {{ formatDate(issue.due_date) }}
        </span>

        <!-- Subtask progress (linear bar instead of ring — scans faster) -->
        <div
          v-if="issue.sub_tasks?.length"
          class="flex items-center gap-1.5 flex-1 min-w-0"
        >
          <div class="h-1.5 flex-1 bg-default rounded-full overflow-hidden">
            <div
              class="h-full bg-success rounded-full transition-[width] duration-500 ease-out"
              :style="{ width: `${progressPct}%` }"
            />
          </div>
          <span
            class="text-xs font-semibold tabular-nums"
            :class="progressPct === 100 ? 'text-success-soft-foreground' : 'text-muted'"
          >
            {{ completedSubtasks }}/{{ issue.sub_tasks.length }}
          </span>
        </div>
      </div>

      
    </div>

    <!-- Bottom row -->
    <div class="flex items-center pr-2 justify-between">
      <!-- Left: Priority + Status hint -->

      <!-- Labels (chips) -->
      <div>
        <div class="flex items-start justify-between gap-2">
          <div class="flex items-center gap-1.5 min-w-0">
              <span
              class="w-3 h-3 rounded flex items-center justify-center shrink-0"
              :style="{ backgroundColor: taskTypeColor }"
              :title="issue.task_type"
            >
              <svg
                class="w-2.5 h-2.5 text-white"
                fill="currentColor"
                viewBox="0 0 10 10"
              >
                <circle v-if="isBug" cx="5" cy="5" r="4" />
                <g v-else-if="isSubtask">
                  <rect x="1" y="2" width="8" height="1.5" rx="0.5" />
                  <rect x="1" y="4.8" width="5" height="1.5" rx="0.5" />
                  <rect x="1" y="7.5" width="3" height="1.5" rx="0.5" />
                </g>
                <rect v-else x="1.5" y="1.5" width="7" height="7" rx="1.5" />
              </svg>
            </span> 
            <span
              class="text-xs pt-[1px] font-semibold text-muted tracking-tight uppercase truncate"
            >
              {{ issue.name }}
            </span>
          </div>
          <!-- Meta row: Due date + Progress -->
      
        </div>
      </div>
      <div class="flex items-center space-x-2">
        <div class="flex items-center gap-2">
          <PriorityIcon :priority="issue.priority" />
          <!-- Optional status dot if not completed -->
        </div>
        <!-- Right: Avatars -->
        <div class="flex items-center gap-1.5">
          <div class="flex -space-x-2">
            <Avatar
              v-for="a in (issue.assignees || []).slice(0, 3)"
              :key="a.user"
              :name="a.full_name"
              size="xs"
              class="ring-2 ring-white shrink-0"
            />
            <div
              v-if="(issue.assignees || []).length > 3"
              class="w-6 h-6 rounded-full bg-default flex items-center justify-center text-muted text-micro font-bold ring-2 ring-white shrink-0"
            >
              +{{ issue.assignees.length - 3 }}
            </div>
          </div>
        </div>
        
      </div>
    </div>

    <!-- Drag handle indicator (visible on hover) -->
    <div
      class="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity text-muted"
    >
      <svg class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 16 16">
        <circle cx="5" cy="4" r="1.2" />
        <circle cx="11" cy="4" r="1.2" />
        <circle cx="5" cy="8" r="1.2" />
        <circle cx="11" cy="8" r="1.2" />
        <circle cx="5" cy="12" r="1.2" />
        <circle cx="11" cy="12" r="1.2" />
      </svg>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useProjectStore } from '@/stores/project'
import PriorityIcon from '@/components/PriorityIcon.vue'
import { Avatar } from '@/ui'

const props = defineProps({
  issue: { type: Object, required: true },
  index: { type: Number, default: 0 },
  mirrorChips: { type: Array, default: () => [] }
})
const emit = defineEmits(['click', 'dragstart', 'context-menu', 'open-erp-doc'])

const store = useProjectStore()
const isDragging = ref(false)

const issueTypeConfig = computed(
  () => store.taskTypeMap?.[props.issue.task_type] || null
)
const taskTypeColor = computed(() => issueTypeConfig.value?.color || 'var(--accent)')
const isBug = computed(() => props.issue.task_type?.toLowerCase() === 'bug')
const isSubtask = computed(() =>
  props.issue.task_type?.toLowerCase().includes('sub')
)

const statusColor = computed(() => {
  const state = store.workflowStateMap?.[props.issue.status]
  return state?.color || 'var(--muted)'
})

const completedSubtasks = computed(() => {
  if (!props.issue.sub_tasks?.length) return 0
  return props.issue.sub_tasks.filter(
    st => store.workflowStateMap?.[st.status]?.category === 'completed'
  ).length
})

const issueLabels = computed(() => {
  const raw = props.issue.labels
  if (!raw) return []
  if (Array.isArray(raw)) return raw
  try {
    return JSON.parse(raw)
  } catch {
    return []
  }
})

const erpBadges = computed(() => {
  const m = {}
  for (const r of (props.issue.references || [])) (m[r.ref_doctype] ||= []).push(r)
  return Object.entries(m).map(([doctype, items]) => ({
    doctype, items, n: items.length,
    abbr: doctype.split(' ').map(w => w[0]).join('').toUpperCase(),
  }))
})
const isBillable = computed(() => !!(props.issue.billable && props.issue.estimated_hours))

const blockedMeta = computed(() => {
  if (!props.issue.blocked_reason) return ''
  const since = props.issue.blocked_since ? ` since ${new Date(props.issue.blocked_since).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}` : ''
  return `${props.issue.blocked_reason}${since}`
})

function getLabelStyle (labelName) {
  const lbl = (store.projectLabels || []).find(l => l.label === labelName)
  if (!lbl)
    return { background: 'var(--surface-secondary)', color: 'var(--muted)', borderColor: 'var(--border)' }
  return {
    background: lbl.color + '14',
    color: lbl.color,
    borderColor: lbl.color + '30'
  }
}

const progressPct = computed(() =>
  props.issue.sub_tasks?.length
    ? Math.round((completedSubtasks.value / props.issue.sub_tasks.length) * 100)
    : 0
)

const isCompleted = computed(
  () => store.workflowStateMap?.[props.issue.status]?.category === 'completed'
)

const isOverdue = computed(() => {
  if (!props.issue.due_date || isCompleted.value) return false
  const due = new Date(props.issue.due_date)
  due.setHours(0, 0, 0, 0)
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return due < today
})

const isDueSoon = computed(() => {
  if (!props.issue.due_date || isOverdue.value || isCompleted.value)
    return false
  const due = new Date(props.issue.due_date)
  due.setHours(0, 0, 0, 0)
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const diff = Math.round((due - today) / 86400000)
  return diff >= 0 && diff <= 2
})

function formatDate (d) {
  const date = new Date(d)
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const cmp = new Date(date)
  cmp.setHours(0, 0, 0, 0)
  const diff = Math.round((cmp - today) / 86400000)
  if (diff === 0) return 'Today'
  if (diff === 1) return 'Tomorrow'
  if (diff === -1) return 'Yesterday'
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function onDragStart (e) {
  isDragging.value = true
  window.__dragIssue = {
    issue: props.issue,
    fromStatus: props.issue.status,
    fromIndex: props.index
  }
  e.dataTransfer.effectAllowed = 'move'

  // Cleaner ghost: use the element itself with a modifier class
  const el = e.currentTarget
  const rect = el.getBoundingClientRect()

  // Create a cleaner ghost image
  const ghost = el.cloneNode(true)
  ghost.classList.add('dragging-ghost')
  Object.assign(ghost.style, {
    position: 'fixed',
    top: `${rect.top}px`,
    left: `${rect.left}px`,
    width: `${rect.width}px`,
    opacity: '0.85',
    transform: 'rotate(2deg) scale(1.03)',
    boxShadow: 'var(--overlay-shadow)',
    pointerEvents: 'none',
    zIndex: '9999',
    transition: 'none'
  })

  document.body.appendChild(ghost)
  e.dataTransfer.setDragImage(ghost, e.offsetX, e.offsetY)

  // Remove after drag image is captured
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      if (ghost.parentNode) ghost.parentNode.removeChild(ghost)
    })
  })

  emit('dragstart', props.issue)
}

function onDragEnd () {
  isDragging.value = false
}

function onContextMenu (e) {
  emit('context-menu', { issue: props.issue, x: e.clientX, y: e.clientY })
}
</script>

<style scoped>
/* Optional: ensure ghost doesn't inherit hover states */
.dragging-ghost {
  filter: saturate(0.9);
}
/* Must use the shadow tokens, not a raw rgba(0,0,0,...) shadow —
   the shadow tokens use Brex's navy-grey tint, not flat black;
   see tokens.css. --card-shadow/--surface-shadow-hover already exist for
   exactly this. */
.tc-shadow {
  box-shadow: var(--card-shadow);
}
.tc-shadow:hover {
  box-shadow: var(--surface-shadow-hover);
}
.tc-erp-badge {
  display: inline-flex; align-items: center; height: 18px; padding: 0 6px;
  font-size:var(--text-xs); font-weight: 700; letter-spacing: .02em;
  color: var(--accent-soft-foreground); background: var(--accent-soft);
  border: none; border-radius: var(--radius-sm); cursor: pointer;
}
.tc-billable-badge {
  display: inline-flex; align-items: center; justify-content: center; width: 18px; height: 18px;
  font-size:var(--text-xs); font-weight: 800; color: var(--success-soft-foreground);
  background: var(--success-soft); border-radius: var(--radius-sm);
}
.tc-blocked-badge {
  display: inline-flex; align-items: center; justify-content: center; width: 18px; height: 18px;
  color: var(--warning-soft-foreground); background: var(--warning-soft);
  border-radius: var(--radius-sm);
}
.tc-mirror-chip {
  display: inline-flex; align-items: center; height: 18px; padding: 0 6px;
  font-size:var(--text-xs); font-weight: 600; color: var(--muted); background: var(--surface-secondary);
  border: none; border-radius: var(--radius-sm); cursor: pointer; max-width: 140px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
</style>
