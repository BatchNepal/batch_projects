<template>
  <Teleport to="body">
    <Transition name="ctx">
      <div
        v-if="issue"
        ref="menuEl"
        class="ctx-root bp-overlay"
        :style="menuStyle"
        @click.stop
        @mousedown.stop
      >
        <!-- Open -->
        <button class="ctx-item" @click="act('open')">
          <svg class="ctx-icon" width="13" height="13" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/></svg>
          Open issue
          <span class="ctx-hint">↵</span>
        </button>

        <div class="ctx-sep"/>

        <!-- Status flyout -->
        <div class="ctx-flyout-wrap" @mouseenter="openFly = 'status'" @mouseleave="openFly = null">
          <button class="ctx-item ctx-item--has-fly">
            Status
            <span class="ctx-fly-val">{{ issue.status }}</span>
            <svg class="ctx-chevron" width="10" height="10" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/></svg>
          </button>
          <div v-if="openFly === 'status'" class="ctx-fly" :style="flyStyle">
            <div class="ctx-fly-label">Move to status</div>
            <button
              v-for="s in store.workflowStates" :key="s.name"
              class="ctx-item ctx-item--option"
              :class="{ 'ctx-item--active': issue.status === s.name }"
              @click="update('status', s.name)"
            >
              <span class="ctx-status-dot" :style="{ background: s.color }"/>
              {{ s.name }}
              <svg v-if="issue.status === s.name" class="ctx-check" width="10" height="10" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>
            </button>
          </div>
        </div>

        <!-- Priority flyout -->
        <div class="ctx-flyout-wrap" @mouseenter="openFly = 'priority'" @mouseleave="openFly = null">
          <button class="ctx-item ctx-item--has-fly">
            Priority
            <span class="ctx-fly-val">{{ issue.priority || 'None' }}</span>
            <svg class="ctx-chevron" width="10" height="10" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/></svg>
          </button>
          <div v-if="openFly === 'priority'" class="ctx-fly" :style="flyStyle">
            <div class="ctx-fly-label">Set priority</div>
            <button
              v-for="p in PRIORITIES" :key="p.value"
              class="ctx-item ctx-item--option"
              :class="{ 'ctx-item--active': issue.priority === p.value }"
              @click="update('priority', p.value)"
            >
              <PriorityIcon :priority="p.value"/>
              <span class="text-muted">{{ p.label }}</span>
              <svg v-if="issue.priority === p.value" class="ctx-check" width="10" height="10" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>
            </button>
          </div>
        </div>

        <!-- Assignee flyout -->
        <div v-if="store.projectMembers?.length" class="ctx-flyout-wrap" @mouseenter="openFly = 'assignee'" @mouseleave="openFly = null">
          <button class="ctx-item ctx-item--has-fly">
            Assignees
            <span class="ctx-fly-val">
              {{ issue.assignees?.length ? issue.assignees[0].full_name?.split(' ')[0] + (issue.assignees.length > 1 ? ` +${issue.assignees.length-1}` : '') : 'None' }}
            </span>
            <svg class="ctx-chevron" width="10" height="10" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/></svg>
          </button>
          <div v-if="openFly === 'assignee'" class="ctx-fly ctx-fly--wide" :style="flyStyle">
            <div class="ctx-fly-label">Assign to</div>
            <div class="ctx-search-wrap">
              <input v-model="assigneeQ" class="ctx-search" placeholder="Search…" @click.stop @keydown.stop/>
            </div>
            <button @click="update('assignees', [])" class="ctx-item ctx-item--option" :class="{ 'ctx-item--active': !issue.assignees?.length }">
              <span class="ctx-av-empty"/>Unassigned
            </button>
            <button
              v-for="m in filteredMembers" :key="m.user"
              class="ctx-item ctx-item--option"
              :class="{ 'ctx-item--active': isAssigned(m.user) }"
              @click="toggleAssignee(m)"
            >
              <span class="ctx-av" :style="{ background: avatarColor(m.user) }">{{ ini(m.full_name) }}</span>
              <span class="flex-1 truncate">{{ m.full_name }}</span>
              <svg v-if="isAssigned(m.user)" class="ctx-check" width="10" height="10" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>
            </button>
          </div>
        </div>

        <!-- Move to (project) flyout -->
        <div v-if="otherProjects.length" class="ctx-flyout-wrap" @mouseenter="openFly = 'move'" @mouseleave="openFly = null">
          <button class="ctx-item ctx-item--has-fly">
            Move to
            <svg class="ctx-chevron" width="10" height="10" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/></svg>
          </button>
          <div v-if="openFly === 'move'" class="ctx-fly ctx-fly--wide" :style="flyStyle">
            <div class="ctx-fly-label">Move to project</div>
            <div class="ctx-search-wrap">
              <input v-model="moveQ" class="ctx-search" placeholder="Search projects…" @click.stop @keydown.stop/>
            </div>
            <button
              v-for="p in filteredProjects" :key="p.name"
              class="ctx-item ctx-item--option"
              :disabled="moving"
              @click="moveToProject(p)"
            >
              <ProjectAvatar :theme="p.theme" :seed="p.key" size="xs" />
              <span class="flex-1 truncate">{{ p.project_name }}</span>
              <span class="ctx-dep-sub">{{ p.key }}</span>
            </button>
            <p v-if="!filteredProjects.length" class="ctx-fly-label" style="text-transform:none;letter-spacing:normal;padding:6px 11px;">No matches</p>
          </div>
        </div>

        <!-- Dependencies flyout (Gantt passes the edges touching this task) -->
        <div v-if="deps?.length" class="ctx-flyout-wrap" @mouseenter="openFly = 'deps'" @mouseleave="openFly = null">
          <button class="ctx-item ctx-item--has-fly">
            Dependencies
            <span class="ctx-fly-val">{{ deps.length }}</span>
            <svg class="ctx-chevron" width="10" height="10" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/></svg>
          </button>
          <div v-if="openFly === 'deps'" class="ctx-fly ctx-fly--wide" :style="flyStyle">
            <div class="ctx-fly-label">Remove dependency</div>
            <button
              v-for="d in deps" :key="d.from + '→' + d.to"
              class="ctx-item ctx-item--option"
              @click="$emit('remove-dep', d); $emit('close')"
            >
              <svg class="ctx-icon" width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>
              <span class="flex-1 truncate">{{ d.label }}</span>
              <span class="ctx-dep-sub">{{ d.sub }}</span>
            </button>
          </div>
        </div>

        <div class="ctx-sep"/>

        <!-- Remove from timeline (Gantt only): clears both dates -->
        <button v-if="showTimeline && (issue.start_date || issue.due_date)" class="ctx-item" @click="$emit('clear-dates', issue.name); $emit('close')">
          <svg class="ctx-icon" width="13" height="13" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M8 2v3M16 2v3M3.5 9h17M21 8.5V17a4 4 0 01-4 4H7a4 4 0 01-4-4V8.5a4 4 0 014-4h10a4 4 0 014 4zM10 13l4 4m0-4l-4 4"/></svg>
          Remove from timeline
        </button>

        <!-- Copy key -->
        <button class="ctx-item" @click="act('copy-key')">
          <svg class="ctx-icon" width="13" height="13" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>
          Copy issue key
          <span class="ctx-hint">{{ issue.task_key }}</span>
        </button>

        <!-- Copy name -->
        <button class="ctx-item" @click="act('copy-name')">
          <svg class="ctx-icon" width="13" height="13" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>
          Copy name
        </button>

        <!-- Copy task link -->
        <button class="ctx-item" @click="act('copy-link')">
          <svg class="ctx-icon" width="13" height="13" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M13.828 10.172a4 4 0 010 5.656l-3 3a4 4 0 01-5.656-5.656l1.5-1.5M10.172 13.828a4 4 0 010-5.656l3-3a4 4 0 015.656 5.656l-1.5 1.5"/></svg>
          Copy task link
        </button>

        <!-- Add subitem -->
        <button class="ctx-item" @click="act('add-subitem')">
          <svg class="ctx-icon" width="13" height="13" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/></svg>
          Add subitem
        </button>

        <!-- Duplicate -->
        <button class="ctx-item" @click="act('duplicate')">
          <svg class="ctx-icon" width="13" height="13" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>
          Duplicate
        </button>

        <!-- Save as template -->
        <button class="ctx-item" @click="act('save-template')">
          <svg class="ctx-icon" width="13" height="13" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 3H5a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-4M18 2l4 4-11 11H7v-4L18 2z"/></svg>
          Save as template…
        </button>

        <div class="ctx-sep"/>

        <!-- Delete -->
        <button class="ctx-item ctx-item--danger" @click="act('delete')">
          <svg class="ctx-icon" width="13" height="13" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
          Delete
        </button>

      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useProjectStore } from '@/stores/project'
import { PRIORITIES, PRIORITY_MAP } from '@/utils/constants.js'
import PriorityIcon from '@/components/PriorityIcon.vue'
import ProjectAvatar from '@/ui/ProjectAvatar.vue'
import { toast } from 'vue-sonner'
import * as api from '@/utils/api.js'
import { UpgradeRequiredError } from '@/utils/api'

const props = defineProps({
  issue: { type: Object, default: null },
  x:     { type: Number, default: 0 },
  y:     { type: Number, default: 0 },
  deps:  { type: Array, default: null },          // [{from, to, label, sub}]
  showTimeline: { type: Boolean, default: false },
})
const emit = defineEmits(['close', 'remove-dep', 'clear-dates', 'deleted'])

const store     = useProjectStore()
const router    = useRouter()
const menuEl    = ref(null)
const menuStyle = ref({})
const flyStyle  = ref({ top: '0' })
const openFly   = ref(null)
const assigneeQ = ref('')
const moveQ  = ref('')
const moving = ref(false)

watch(() => [props.issue, props.x, props.y], async () => {
  if (!props.issue) return
  assigneeQ.value = ''
  moveQ.value     = ''
  openFly.value   = null
  await nextTick()
  if (!menuEl.value) return
  const vw = window.innerWidth, vh = window.innerHeight
  const w  = menuEl.value.offsetWidth  || 200
  const h  = menuEl.value.offsetHeight || 220
  const x  = props.x + w > vw - 8 ? props.x - w : props.x
  const y  = props.y + h > vh - 8 ? props.y - h : props.y
  menuStyle.value = { top: `${Math.max(8, y)}px`, left: `${Math.max(8, x)}px` }
  // Flyout appears to the right; check if enough space
  const flyRight = props.x + w + 180
  flyStyle.value = { left: flyRight > vw - 8 ? '-182px' : '100%', top: '-4px' }
}, { immediate: true })

// ── Move to project ──────────────────────────────────────────────────────
const otherProjects = computed(() =>
  (store.projects || []).filter(p => p.name !== (props.issue?.project || store.currentProject?.name))
)
const filteredProjects = computed(() => {
  const q = moveQ.value.trim().toLowerCase()
  if (!q) return otherProjects.value
  return otherProjects.value.filter(p =>
    p.project_name?.toLowerCase().includes(q) || p.key?.toLowerCase().includes(q)
  )
})
async function moveToProject(target) {
  if (!props.issue || moving.value) return
  moving.value = true
  const oldKey = props.issue.task_key
  try {
    const res = await api.moveTaskToProject(props.issue.name, target.name)
    toast.success(`Moved ${oldKey} → ${res.task_key} in ${target.project_name}`)
    store.refreshBoard()
    emit('deleted', props.issue.name) // task no longer belongs to the current project's view
  } catch (e) {
    toast.error(e.message || 'Failed to move task')
  } finally {
    moving.value = false
    emit('close')
  }
}

const currentAssignees = computed(() => props.issue?.assignees || [])
const filteredMembers  = computed(() => {
  const q = assigneeQ.value.toLowerCase()
  return (store.projectMembers || []).filter(m =>
    !q || m.full_name?.toLowerCase().includes(q)
  ).slice(0, 8)
})

function isAssigned(user) { return currentAssignees.value.some(a => a.user === user) }

const AVATAR_COLORS = ['#0052CC','#00875A','#DE350B','#FF991F','#00B8D9','#6554C0']
function avatarColor(key) {
  let h = 0
  for (let i = 0; i < (key||'').length; i++) h = key.charCodeAt(i) + ((h << 5) - h)
  return AVATAR_COLORS[Math.abs(h) % AVATAR_COLORS.length]
}
function ini(name) {
  if (!name) return '?'
  return name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2)
}

async function update(field, value) {
  if (!props.issue) return
  props.issue[field] = value
  openFly.value = null
  try { await store.updateTaskField(props.issue.name, field, value) }
  catch { toast.error('Failed to update') }
}

async function toggleAssignee(m) {
  if (!props.issue) return
  const cur = [...currentAssignees.value]
  const idx = cur.findIndex(a => a.user === m.user)
  const next = idx >= 0 ? cur.filter(a => a.user !== m.user)
                        : [...cur, { user: m.user, full_name: m.full_name }]
  props.issue.assignees = next
  try { await store.updateTaskField(props.issue.name, 'assignees', next) }
  catch { toast.error('Failed') }
}

function act(action) {
  if (action === 'open') { store.openTaskDetail(props.issue.name); emit('close') }
  else if (action === 'copy-key') {
    navigator.clipboard?.writeText(props.issue.task_key)
    toast.success(`Copied ${props.issue.task_key}`)
    emit('close')
  } else if (action === 'copy-name') {
    navigator.clipboard?.writeText(props.issue.title || '')
    toast.success('Copied task name')
    emit('close')
  } else if (action === 'copy-link') {
    const projectKey = store.projects.find(p => p.name === props.issue.project)?.key
      || store.currentProject?.key
    const url = projectKey
      ? `${window.location.origin}/workspace/${projectKey}/board?task=${props.issue.task_key}`
      : window.location.href
    navigator.clipboard?.writeText(url)
    toast.success('Copied task link')
    emit('close')
  } else if (action === 'add-subitem') {
    store.createTaskDefaults = {
      parent_task: props.issue.name,
      parent_task_key: props.issue.task_key,
    }
    store.showCreateTask = true
    emit('close')
  } else if (action === 'delete') {
    if (!confirm(`Delete "${props.issue.title}"?`)) return
    const name = props.issue.name
    api.deleteTask(name)
      .then(() => { store.refreshBoard(); store.issueCreatedCount++ ; toast.success('Deleted'); emit('deleted', name) })
      .catch(() => toast.error('Failed to delete'))
    emit('close')
  } else if (action === 'save-template') {
    const name = window.prompt('Template name', props.issue.title)
    emit('close')
    if (!name || !name.trim()) return
    api.saveTaskAsTemplate(props.issue.name, name.trim())
      .then(() => toast.success('Saved as template'))
      .catch(handleErr)
  } else if (action === 'duplicate') {
    const name = props.issue.name
    api.duplicateTask(name)
      .then(() => { store.refreshBoard(); store.issueCreatedCount++ ; toast.success('Duplicated') })
      .catch(() => toast.error('Failed to duplicate'))
    emit('close')
  }
}

function handleErr(e) {
  if (e instanceof UpgradeRequiredError) {
    toast.error(e.message, {
      action: {
        label: 'Upgrade',
        onClick: () => router.push({ name: 'Pricing' }).catch(() => { window.location.hash = '#/pricing' }),
      },
    })
  } else {
    toast.error(e.message || 'Something went wrong')
  }
}

function onOutside(e) {
  if (!props.issue || menuEl.value?.contains(e.target)) return
  emit('close')
}
function onKey(e) {
  if (e.key === 'Escape') emit('close')
  if (e.key === 'Enter' && props.issue) act('open')
}

onMounted(() => {
  document.addEventListener('mousedown', onOutside, true)
  document.addEventListener('keydown', onKey, true)
})
onUnmounted(() => {
  document.removeEventListener('mousedown', onOutside, true)
  document.removeEventListener('keydown', onKey, true)
})
</script>

<style scoped>
.ctx-root {
  position: fixed; z-index: 99999;
  width: 210px;
  background: var(--overlay);
  border: 1px solid var(--border);
  border-radius: 4px;
  box-shadow: var(--overlay-shadow);
  padding: 3px 0;
}
.ctx-sep { height: 1px; background: var(--surface-secondary); margin: 3px 0; }

.ctx-item {
  display: flex; align-items: center; gap: 7px;
  width: 100%; padding: 6px 11px;
  font-size: 13px; font-weight: 500; font-family: inherit;
  color: var(--foreground); background: none; border: none;
  cursor: pointer; text-align: left;
  transition: background .08s; white-space: nowrap;
}
.ctx-item:hover { background: var(--surface-secondary); }
.ctx-item:disabled { opacity: 0.5; cursor: not-allowed; }
.ctx-item:disabled:hover { background: none; }
.ctx-item--option { font-size: 12.5px; padding: 5px 11px; }
.ctx-item--active { color: var(--accent); }
.ctx-item--danger { color: var(--danger); }
.ctx-item--danger:hover { background: var(--danger-soft); }
.ctx-item--danger .ctx-icon { color: var(--danger); }
.ctx-item--has-fly { justify-content: flex-start; }

.ctx-icon  { color: var(--muted); flex-shrink: 0; }
.ctx-hint  { margin-left: auto; font-size: 10.5px; color: var(--muted); }
.ctx-check { margin-left: auto; color: var(--accent); flex-shrink: 0; }
.ctx-chevron { margin-left: auto; color: var(--muted); flex-shrink: 0; }

.ctx-fly-val {
  margin-left: auto; font-size: 11px; color: var(--muted);
  font-weight: 400; white-space: nowrap; max-width: 70px;
  overflow: hidden; text-overflow: ellipsis;
}

/* Flyout container */
.ctx-flyout-wrap { position: relative; }
.ctx-fly {
  position: absolute;
  top: 0; left: 100%;
  width: 180px;
  background: var(--overlay);
  border: 1px solid var(--border);
  border-radius: 4px;
  box-shadow: var(--overlay-shadow);
  padding: 3px 0; z-index: 10;
}
.ctx-fly--wide { width: 200px; }
.ctx-fly-label {
  font-size: 10px; font-weight: 700; color: var(--muted);
  text-transform: uppercase; letter-spacing: 0.08em;
  padding: 5px 11px 3px;
}
.ctx-status-dot { width: 8px; height: 8px; border-radius: 2px; flex-shrink: 0; }
.ctx-dep-sub { margin-left: auto; padding-left: 8px; font-size: 10.5px; color: var(--muted); white-space: nowrap; flex-shrink: 0; }
.ctx-type-badge { width: 15px; height: 15px; border-radius: 3px; flex-shrink: 0; display:inline-flex;align-items:center;justify-content:center;color:var(--accent-foreground);font-size:8px;font-weight:700; }
.ctx-av { width: 19px; height: 19px; border-radius: 50%; flex-shrink:0; display:inline-flex;align-items:center;justify-content:center;color:var(--accent-foreground);font-size:7.5px;font-weight:700; }
.ctx-av-empty { width: 19px; height: 19px; border-radius: 50%; background: var(--surface-secondary); flex-shrink:0; }
.ctx-search-wrap { padding: 4px 8px 3px; }
.ctx-search { width:100%; font-size:12px; font-family:inherit; background:var(--surface-secondary); border:1px solid var(--border); border-radius:3px; outline:none; padding:3px 7px; color:var(--foreground); }
.ctx-search:focus { background:var(--surface); border-color:var(--accent); }
.ctx-search::placeholder { color:var(--muted); }

/* Animation */
.ctx-enter-active { transition: opacity .1s ease, transform .1s cubic-bezier(0.16,1,0.3,1); }
.ctx-leave-active { transition: opacity .07s ease; }
.ctx-enter-from  { opacity: 0; transform: scale(0.97) translateY(-3px); }
.ctx-leave-to    { opacity: 0; }
</style>