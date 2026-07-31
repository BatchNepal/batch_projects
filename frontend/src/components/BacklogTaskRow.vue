<template>
  <div
    class="bl-issue-row"
    :class="{ 'bl-issue-row--muted': muted }"
    :style="{ gridTemplateColumns: gridTemplate }"
    draggable="true"
    @dragstart="$emit('dragstart', $event, issue)"
    @click="store.openTaskDetail(issue.name)"
    @contextmenu.prevent="$emit('contextmenu', $event, issue)"
  >
    <div class="bl-cell bl-cell--drag"><svg width="10" height="10" fill="currentColor" viewBox="0 0 20 20"><path d="M7 2a2 2 0 10.001 4.001A2 2 0 007 2zm0 6a2 2 0 10.001 4.001A2 2 0 007 6zm0 6a2 2 0 10.001 4.001A2 2 0 007 12zM13 2a2 2 0 10.001 4.001A2 2 0 0013 2zm0 6a2 2 0 10.001 4.001A2 2 0 0013 6zm0 6a2 2 0 10.001 4.001A2 2 0 0013 12z"/></svg></div>
    <div class="bl-cell bl-cell--key"><span class="bl-issue-key">{{ issue.task_key }}</span></div>
    <div class="bl-cell bl-cell--type"><span class="bl-issue-type" :style="{ background: store.taskTypeMap?.[issue.task_type]?.color || 'var(--accent)' }">{{ (issue.task_type || 'T').charAt(0) }}</span></div>

    <!-- Title cell — the one flexible track; internal content truncates as a unit. -->
    <div class="bl-cell bl-cell--title bl-cell--border">
      <span class="bl-issue-title">{{ issue.title }}</span>
      <template v-if="issueLabels(issue).length">
        <span v-for="lbl in issueLabels(issue).slice(0,2)" :key="lbl" class="bl-lbl-chip" :style="labelStyle(lbl)">{{ lbl }}</span>
      </template>
      <button v-for="g in erpBadges(issue)" :key="g.doctype" class="bl-erp-badge" :title="g.items.map(r => r.ref_label || r.ref_name).join(', ')" @click.stop="openErpDoc(g.items[0].ref_doctype, g.items[0].ref_name)">{{ g.abbr }}<template v-if="g.n > 1">×{{ g.n }}</template></button>
      <span v-if="issue.billable && issue.estimated_hours" class="bl-billable-badge" title="Billable">$</span>
      <button v-for="chip in mirrorChips(issue)" :key="chip.key" class="bl-mirror-chip" :title="`${chip.label}: ${chip.text}`" @click.stop="openErpDoc(chip.doctype, chip.name)">{{ chip.label }}: {{ chip.text }}</button>
    </div>

    <div v-if="columns.epic" class="bl-cell bl-cell--border" :title="issue.epic_title || ''">
      <span class="bl-col-text">{{ issue.epic_title || '—' }}</span>
    </div>
    <div v-if="columns.points" class="bl-cell bl-cell--border bl-cell--num">
      <input
        type="number" min="0" class="bl-col-input" title="Story points (estimated)"
        :value="issue.story_points || ''" placeholder="—"
        @change="saveField('story_points', $event)" @click.stop
      />
    </div>
    <div v-if="columns.actualPoints" class="bl-cell bl-cell--border bl-cell--num">
      <input
        type="number" min="0" class="bl-col-input" title="Actual points"
        :value="issue.actual_points || ''" placeholder="—"
        @change="saveField('actual_points', $event)" @click.stop
      />
    </div>
    <div v-if="columns.unplanned" class="bl-cell bl-cell--border bl-cell--num">
      <button
        type="button"
        class="bl-col-check-btn"
        title="Unplanned — added after the sprint started"
        @click.stop="toggleUnplanned"
      >
        <span class="bl-col-check" :class="{ 'bl-col-check--on': issue.is_unplanned }">
          <svg v-if="issue.is_unplanned" width="9" height="9" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="3.5"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>
        </span>
      </button>
    </div>

    <div class="bl-cell bl-cell--border bl-cell--num"><PriorityIcon :priority="issue.priority" /></div>
    <div class="bl-cell bl-cell--border">
      <span class="bl-issue-status" :style="statusStyle(issue.status)">{{ issue.status }}</span>
    </div>
    <div class="bl-cell bl-issue-assignees">
      <span v-for="a in (issue.assignees || []).slice(0, 2)" :key="a.user" class="bl-av" :style="{ background: avatarColor(a.user) }" :title="a.full_name">{{ initials(a.full_name) }}</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useProjectStore } from '@/stores/project'
import { avatarColor, initials } from '@/utils/constants.js'
import { updateTask } from '@/utils/api.js'
import { blGridTemplate } from '@/utils/backlogGrid.js'
import PriorityIcon from '@/components/PriorityIcon.vue'

const props = defineProps({
  issue:       { type: Object, required: true },
  muted:       { type: Boolean, default: false },
  columns:     { type: Object, default: () => ({}) }, // {points, actualPoints, unplanned, epic}
  mirrorChips: { type: Function, default: () => [] },
  openErpDoc:  { type: Function, required: true },
})
defineEmits(['dragstart', 'contextmenu'])

const store = useProjectStore()
const gridTemplate = computed(() => blGridTemplate(props.columns))

function issueLabels(issue) {
  const raw = issue.labels
  if (!raw) return []
  if (Array.isArray(raw)) return raw
  try { return JSON.parse(raw) } catch { return [] }
}
function labelStyle(labelName) {
  const lbl = (store.projectLabels || []).find(l => l.label === labelName)
  if (!lbl) return { background: 'var(--surface-secondary)', color: 'var(--muted)', borderColor: 'var(--border)' }
  return { background: lbl.color + '18', color: lbl.color, borderColor: lbl.color + '40' }
}
function statusStyle(status) {
  const color = store.workflowStateMap?.[status]?.color || 'var(--muted)'
  return { background: color + '1A', color, borderColor: color + '40' }
}
function erpBadges(issue) {
  const m = {}
  for (const r of (issue.references || [])) (m[r.ref_doctype] ||= []).push(r)
  return Object.entries(m).map(([doctype, items]) => ({
    doctype, items, n: items.length,
    abbr: doctype.split(' ').map(w => w[0]).join('').toUpperCase(),
  }))
}

async function saveField(field, e) {
  // 0, never null — actual_points/story_points columns are NOT NULL in the
  // DB (no bare-empty state), so clearing the input means "0", not "unset".
  const next = e.target.value === '' ? 0 : Number(e.target.value)
  const prev = props.issue[field]
  if (next === prev) return
  props.issue[field] = next
  try { await updateTask(props.issue.name, { [field]: next }) }
  catch { props.issue[field] = prev }
}

async function toggleUnplanned() {
  const next = props.issue.is_unplanned ? 0 : 1
  const prev = props.issue.is_unplanned
  props.issue.is_unplanned = next
  try { await updateTask(props.issue.name, { is_unplanned: next }) }
  catch { props.issue.is_unplanned = prev }
}
</script>

<style scoped>
.bl-issue-row {
  display: grid; align-items: center; column-gap: 0;
  padding: 0 14px; height: 38px; border-bottom: 1px solid var(--separator);
  cursor: pointer; transition: background .08s;
}
.bl-issue-row:hover { background: var(--background); }
.bl-issue-row:last-child { border-bottom: none; }
.bl-issue-row--muted:hover { background: var(--background); }

.bl-cell { display: flex; align-items: center; gap: 6px; height: 100%; min-width: 0; padding: 0 8px; }
.bl-cell:first-child { padding-left: 0; }
.bl-cell--border { border-right: 1px solid var(--separator); }
.bl-cell--num { justify-content: center; }
.bl-cell--title { overflow: hidden; }

.bl-cell--drag { color: var(--muted); cursor: grab; flex-shrink: 0; opacity: 0; transition: opacity .1s; }
.bl-issue-row:hover .bl-cell--drag { opacity: 1; }

.bl-issue-key { font-size: 10.5px; font-weight: 700; color: var(--muted); font-family: monospace; white-space: nowrap; }
.bl-issue-type { width: 15px; height: 15px; border-radius: 2px; flex-shrink: 0; display: inline-flex; align-items: center; justify-content: center; color: var(--accent-foreground); font-size: 7.5px; font-weight: 700; }
.bl-issue-title { font-size: 13px; color: var(--foreground); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex-shrink: 1; min-width: 24px; }
.bl-lbl-chip { flex-shrink: 0; padding: 1px 6px; border: 1px solid; border-radius: 3px; font-size: 10.5px; font-weight: 600; white-space: nowrap; }
.bl-erp-badge { flex-shrink: 0; height: 16px; padding: 0 5px; font-size: 9.5px; font-weight: 700; letter-spacing: .02em; color: var(--accent-soft-foreground); background: var(--accent-soft); border: none; border-radius: 3px; cursor: pointer; }
.bl-billable-badge { flex-shrink: 0; display: inline-flex; align-items: center; justify-content: center; width: 16px; height: 16px; font-size: 9.5px; font-weight: 800; color: var(--success-soft-foreground); background: var(--success-soft); border-radius: 3px; }
.bl-mirror-chip { flex-shrink: 0; max-width: 130px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; height: 16px; padding: 0 6px; font-size: 9.5px; font-weight: 600; color: var(--muted); background: var(--surface-secondary); border: none; border-radius: 3px; cursor: pointer; }
.bl-issue-status { flex-shrink: 0; padding: 2px 7px; font-size: 10.5px; font-weight: 700; text-transform: uppercase; letter-spacing: .04em; border: 1px solid; border-radius: 3px; white-space: nowrap; }
.bl-issue-assignees { display: flex; flex-shrink: 0; justify-content: flex-end; }
.bl-av { width: 20px; height: 20px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; color: var(--accent-foreground); font-size: 7.5px; font-weight: 700; margin-left: -4px; border: 1.5px solid var(--surface); flex-shrink: 0; }
.bl-issue-assignees .bl-av:first-child { margin-left: 0; }

/* Sprint column catalog — per-task cells, widths driven by the shared grid template */
.bl-col-text { font-size: 12px; color: var(--muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.bl-col-input {
  width: 100%; height: 22px; text-align: center;
  font-size: 12px; font-family: inherit; color: var(--foreground);
  background: none; border: 1px solid transparent; border-radius: 4px;
  font-variant-numeric: tabular-nums; transition: border-color .1s, background .1s;
}
.bl-col-input:hover { border-color: var(--border); background: var(--surface-secondary); }
.bl-col-input:focus { outline: none; border-color: var(--accent); background: var(--surface); }
.bl-col-input::placeholder { color: var(--muted); }
/* Chrome/Safari number-input spinners — cramped this narrow, drop them */
.bl-col-input::-webkit-outer-spin-button, .bl-col-input::-webkit-inner-spin-button { -webkit-appearance: none; margin: 0; }
.bl-col-check-btn { background: none; border: none; padding: 0; cursor: pointer; display: flex; align-items: center; justify-content: center; }
.bl-col-check {
  width: 14px; height: 14px; border-radius: 3px; flex-shrink: 0;
  border: 1px solid var(--border-secondary); display: flex; align-items: center; justify-content: center;
  color: var(--accent-foreground); transition: background-color .1s, border-color .1s;
}
.bl-col-check--on { background: var(--accent); border-color: var(--accent); }
</style>
