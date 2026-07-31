<template>
  <div class="flex flex-col h-app bg-background font-sans text-foreground">
    <!-- Toolbar -->
    <header class="flex items-center justify-between px-4 py-2.5 border-b border-border bg-surface shrink-0">
      <div class="flex items-center gap-3 min-w-0">
        <button type="button" class="text-muted hover:text-foreground transition-colors" @click="goBack">
          <ArrowLeft :size="16" :stroke-width="1.75" />
        </button>
        <div class="w-px h-4 bg-border" />
        <div class="min-w-0">
          <div class="flex items-center gap-2">
            <input
              v-model="title"
              class="text-sm font-medium text-foreground bg-transparent outline-none min-w-0 truncate focus:bg-surface-secondary rounded px-1.5 -mx-1.5 py-0.5"
              placeholder="Untitled workflow"
            />
            <span class="text-[11px] font-medium uppercase tracking-wider text-muted px-1.5 py-0.5 rounded bg-surface-tertiary shrink-0">
              {{ scope }}
            </span>
          </div>
          <!-- A4: "surface last_run_at/last_run_status under the workflow title" -->
          <p v-if="lastRunAt" class="text-[11px] text-muted px-1.5 -mx-1.5 mt-0.5">
            Last run
            <span :class="lastRunStatus === 'Failed' ? 'text-danger' : 'text-success'">{{ lastRunStatus }}</span>
            {{ fmtLastRun(lastRunAt) }}
          </p>
        </div>
      </div>

      <Tabs
        v-model="viewMode" variant="segment"
        :tabs="[{ value: 'editor', label: 'Editor' }, { value: 'executions', label: 'Executions' }]"
      />

      <div class="flex items-center gap-2 shrink-0">
        <IconButton size="sm" variant="light" aria-label="Undo" :is-disabled="!undoStack.length" @click="undo">
          <Icon :icon="Undo2" class="size-4" />
        </IconButton>
        <IconButton size="sm" variant="light" aria-label="Redo" :is-disabled="!redoStack.length" @click="redo">
          <Icon :icon="Redo2" class="size-4" />
        </IconButton>
        <div class="w-px h-4 bg-border" />
        <span class="text-xs" :class="isDirty ? 'text-warning' : 'text-muted'">
          {{ isDirty ? 'Unsaved changes' : saveState }}
        </span>
        <div class="flex items-center gap-1.5">
          <Switch v-model="isActive" size="sm" />
          <span class="text-xs text-muted">{{ isActive ? 'Active' : 'Paused' }}</span>
        </div>
        <Tooltip v-if="!automationOptions.gateway_engine" placement="bottom">
          <template #trigger>
            <Button variant="outline" size="sm" is-disabled>Test workflow</Button>
          </template>
          Requires the gateway automation engine.
        </Tooltip>
        <Button v-else variant="outline" size="sm" :is-disabled="!workflowName || !isActive" @click="openTestModal">
          Test workflow
        </Button>
        <Button color="accent" variant="solid" size="sm" @click="save">Save</Button>
      </div>
    </header>

    <div v-if="viewMode === 'executions'" class="flex flex-1 min-h-0">
      <ExecutionsView ref="executionsViewRef" :workflow-name="workflowName" :nodes="nodes" @view-run="onViewRun" />
    </div>

    <div v-else class="flex flex-1 min-h-0">
      <!-- Node palette -->
      <aside class="w-56 border-r border-border bg-surface shrink-0 overflow-y-auto py-3">
        <div v-for="group in paletteGroups" :key="group.category" class="mb-4">
          <p class="px-3 mb-1.5 text-[11px] font-medium uppercase tracking-wider text-muted">{{ group.label }}</p>
          <button
            v-for="item in group.items"
            :key="item.type"
            type="button"
            draggable="true"
            class="w-full flex items-center gap-2 px-3 py-1.5 text-left hover:bg-surface-hover transition-colors cursor-grab active:cursor-grabbing"
            @click="addFromPalette(item)"
            @dragstart="onPaletteDragStart($event, item)"
          >
            <span class="flex items-center justify-center size-6 rounded-md bg-surface-tertiary shrink-0">
              <Icon :icon="item.icon" :size="13" :stroke-width="1.75" class="text-muted" />
            </span>
            <span class="text-xs text-foreground truncate">{{ item.label }}</span>
          </button>
        </div>
      </aside>

      <!-- Canvas -->
      <div class="flex-1 min-w-0 relative" @dragover.prevent @drop.prevent="onCanvasDrop">
        <VueFlow
          id="automation-canvas"
          v-model:nodes="nodes"
          v-model:edges="edges"
          :node-types="nodeTypes"
          :default-edge-options="{ type: 'smoothstep' }"
          :min-zoom="0.25"
          :max-zoom="1.5"
          fit-view-on-init
          class="wf-canvas"
          @connect="onConnect"
          @node-click="onNodeClick"
          @node-drag-start="pushHistory"
          @node-context-menu="onNodeContextMenu"
          @edge-context-menu="onEdgeContextMenu"
          @pane-context-menu="onPaneContextMenu"
        >
          <Background pattern-color="var(--wf-dot-color)" :gap="20" :size="2.75" />
          <Controls position="bottom-left" />
          <MiniMap
            position="bottom-right" pannable zoomable
            node-color="color-mix(in oklch, var(--foreground) 14%, var(--surface))"
            node-stroke-color="transparent"
            :node-border-radius="4"
            mask-color="color-mix(in oklch, var(--surface) 80%, transparent)"
            mask-stroke-color="var(--accent)"
            :mask-stroke-width="1.5"
          />
        </VueFlow>
      </div>
    </div>

    <CredentialPickerModal
      :open="credentialPicker.open"
      :model-value="credentialPicker.current"
      :default-type="credentialPicker.defaultType"
      @update:open="credentialPicker.open = $event"
      @select="onCredentialSelected"
    />

    <NodeConfigPanel
      :open="configPanel.open"
      :node="configPanel.node"
      :options="automationOptions"
      :scope="scope"
      :project="project"
      @update:open="configPanel.open = $event"
      @save="onSaveNodeConfig"
      @delete="onDeleteNode"
    />

    <CanvasContextMenu
      :open="contextMenu.open"
      :x="contextMenu.x"
      :y="contextMenu.y"
      :items="contextMenu.items"
      @update:open="contextMenu.open = $event"
    />

    <TestWorkflowModal
      :open="testModal.open"
      :scope="scope"
      :project="project"
      @update:open="testModal.open = $event"
      @select="onTestTaskSelected"
    />
  </div>
</template>

<script setup>
import { ref, markRaw, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { MiniMap } from '@vue-flow/minimap'
import { ArrowLeft, Key, Pencil, Copy, Trash2, Undo2, Redo2 } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/controls/dist/style.css'
import '@vue-flow/minimap/dist/style.css'

import Button from '@/ui/Button.vue'
import IconButton from '@/ui/IconButton.vue'
import Icon from '@/ui/Icon.vue'
import Switch from '@/ui/Switch.vue'
import Tabs from '@/ui/Tabs.vue'
import Tooltip from '@/ui/Tooltip.vue'
import WorkflowNode from '@/components/automation-canvas/WorkflowNode.vue'
import WorkflowSubNode from '@/components/automation-canvas/WorkflowSubNode.vue'
import AddNodeButton from '@/components/automation-canvas/AddNodeButton.vue'
import CredentialPickerModal from '@/components/automation-canvas/CredentialPickerModal.vue'
import NodeConfigPanel from '@/components/automation-canvas/NodeConfigPanel.vue'
import CanvasContextMenu from '@/components/automation-canvas/CanvasContextMenu.vue'
import TestWorkflowModal from '@/components/automation-canvas/TestWorkflowModal.vue'
import ExecutionsView from '@/components/automation-canvas/ExecutionsView.vue'
import {
  ensureNodeRegistryLoaded, toCanvasNode, toStoredNode, paletteGroups as buildPaletteGroups, switchOutputPorts,
} from '@/constants/automation-node-registry'
import { getWorkflow, saveWorkflow, getAutomationOptions, testWorkflow, getWorkflowRuns } from '@/utils/api'

const props = defineProps({ workflowId: { type: String, default: null } })
const router = useRouter()
const route = useRoute()
const goBack = () => router.back()

const workflowName = ref(props.workflowId)
const title = ref('Untitled workflow')
// A brand-new workflow (no workflowId) started from a project's own
// Automations tab arrives with ?project=<name> and defaults to
// scope='project' scoped to it; started from Workspace Settings (no query
// param) it defaults to 'workspace', unchanged from before. An EXISTING
// workflow's scope/project always come from the loaded doc — see load().
const scope = ref(route.query.project ? 'project' : 'workspace')
const project = ref(route.query.project || null)
const saveState = ref('')
const loading = ref(true)
const paletteGroups = ref([])
// A3: Active/Paused — a brand-new (unsaved) workflow defaults Active, same
// as save_workflow's own is_active=1 default. A4: Editor/Executions
// segmented toggle + the run this workflow last actually made, shown under
// the title (get_workflow's own last_run_at/last_run_status — set once
// somewhere actually runs, not something the canvas invents).
const isActive = ref(true)
const viewMode = ref('editor')
const lastRunAt = ref(null)
const lastRunStatus = ref(null)
function fmtLastRun(dt) {
  try { return new Date(dt).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) }
  catch { return dt }
}
// get_automation_options(project) — real statuses/members/labels/priorities/
// etc. NodeConfigPanel's fields resolve `options_source` against this
// instead of hardcoding a second copy. Fetched once per load(); re-fetched
// if an existing workflow's own project differs from the route-query guess
// (see load() below).
const automationOptions = ref({})
async function loadAutomationOptions() {
  try {
    automationOptions.value = await getAutomationOptions(project.value)
  } catch {
    // Viewer without admin rights on a workspace-scope workflow, or similar
    // — leave options empty rather than block the canvas from rendering;
    // Combobox fields just show no suggestions (still usable via allow-create).
    automationOptions.value = {}
  }
}

// Credential picker — WorkflowNode calls data.onAttachCredential(nodeId,
// portId) on click (not a bubbled Vue event: Vue Flow doesn't forward
// custom events from arbitrary node components to the parent, so a
// data-callback is the reliable wiring here, not @attach-credential).
//
// A sub_port's `field` (see toCanvasNode) says where the credential
// reference lives in config: integration.http_request's `auth` is a
// {type,credential,credentialLabel} union (it also allows "none"); the
// messaging presets' `credential` is a flat string with a companion
// `credential_label` — see automation.py's registry comment for why. These
// two helpers are the ONE place that distinction is resolved, so the
// picker/materializer/click-handler below don't each special-case node types.
function credentialRef(node, field) {
  const cfg = node?.data?.config ?? {}
  if (field === 'auth') {
    return cfg.auth?.credential ? { credential: cfg.auth.credential, label: cfg.auth.credentialLabel } : null
  }
  return cfg[field] ? { credential: cfg[field], label: cfg[`${field}_label`] } : null
}
function applyCredentialRef(node, field, name, label) {
  if (field === 'auth') {
    node.data.config = { ...node.data.config, auth: { type: 'credential', credential: name, credentialLabel: label } }
  } else {
    node.data.config = { ...node.data.config, [field]: name, [`${field}_label`]: label }
  }
}
// Default credential_type for the picker's "New credential" form, so
// attaching to a Slack node doesn't start on "Bearer token" by mistake.
const CREDENTIAL_TYPE_BY_NODE_TYPE = {
  'integration.slack': 'webhook_url', 'integration.discord': 'webhook_url',
  'integration.teams': 'webhook_url', 'integration.googlechat': 'webhook_url',
  'integration.telegram': 'bot_token',
}
const credentialPicker = ref({ open: false, nodeId: null, portId: null, field: 'auth', current: null, defaultType: 'bearer_token' })
function onAttachCredential(nodeId, portId) {
  const node = nodes.value.find((n) => n.id === nodeId)
  const port = (node?.data?.subPorts ?? []).find((p) => p.id === portId)
  const field = port?.field ?? 'auth'
  credentialPicker.value = {
    open: true, nodeId, portId, field,
    current: credentialRef(node, field)?.credential ?? null,
    defaultType: CREDENTIAL_TYPE_BY_NODE_TYPE[node?.data?.typeKey] ?? 'bearer_token',
  }
}
function onCredentialSelected({ name, label }) {
  const { nodeId, portId, field } = credentialPicker.value
  const node = nodes.value.find((n) => n.id === nodeId)
  if (!node) return
  applyCredentialRef(node, field, name, label)
  // Materialize the visual sub-node + dashed edge now that a real
  // credential is attached (previously just an empty labeled slot).
  // Same id scheme the illustrative starter example uses (n3 + 'cred' port
  // -> 'n3-cred') — a real pick REPLACES that placeholder sub-node instead
  // of leaving a second, overlapping one behind (found via live-verify: the
  // starter's hardcoded 'n3-cred'/'e-cred' didn't match this generated id,
  // so both existed at once).
  const subId = `${nodeId}-${portId}`
  nodes.value = nodes.value.filter((n) => n.id !== subId)
  nodes.value.push({
    id: subId, type: 'subnode',
    position: { x: node.position.x + 30, y: node.position.y + 150 },
    data: { label, icon: Key },
  })
  edges.value = edges.value.filter((e) => e.id !== `e-${subId}`)
  edges.value.push({
    id: `e-${subId}`, source: nodeId, sourceHandle: portId, target: subId,
    type: 'smoothstep', style: { strokeDasharray: '4 3' },
  })
}

// Manual wire connection — Vue Flow's autoConnect defaults to false, so
// without this handler a drag between two handles shows the preview line
// but never actually creates a persisted edge on release. Found via direct
// user testing: "connection...doesnot work" was this exact gap, not a CSS
// issue.
function onConnect(connection) {
  pushHistory()
  edges.value.push({
    id: `e-${connection.source}-${connection.sourceHandle ?? 'o'}-${connection.target}-${Date.now()}`,
    source: connection.source,
    sourceHandle: connection.sourceHandle,
    target: connection.target,
    targetHandle: connection.targetHandle,
  })
}

// Node config panel — the other confirmed-missing piece: clicking a node
// did nothing (only the credential sub-port chip had a click handler).
// subnode/addButton are UI scaffolding, not real graph nodes — skip those.
const configPanel = ref({ open: false, node: null })
function onNodeClick({ node }) {
  if (node.type !== 'workflow') return
  configPanel.value = { open: true, node }
}
function onSaveNodeConfig({ nodeId, label, config, retry, onError, disabled }) {
  const node = nodes.value.find((n) => n.id === nodeId)
  if (!node) return
  pushHistory()
  node.data.label = label
  node.data.config = config
  node.data.retry = retry
  node.data.onError = onError
  node.data.disabled = disabled
  if (node.data.typeKey === 'logic.switch') {
    // Port count just changed with the cases[] list — re-derive it (same
    // helper toCanvasNode uses on load) and drop any edge wired to a case
    // handle that no longer exists, so a shrunk case list doesn't leave a
    // dangling wire pointing at nothing.
    node.data.outputPorts = switchOutputPorts(config.cases)
    const validHandles = new Set(node.data.outputPorts.map((p) => p.id))
    edges.value = edges.value.filter((e) => e.source !== nodeId || !e.sourceHandle || validHandles.has(e.sourceHandle))
  }
}
function onDeleteNode(nodeId) {
  pushHistory()
  nodes.value = nodes.value.filter((n) => n.id !== nodeId)
  edges.value = edges.value.filter((e) => e.source !== nodeId && e.target !== nodeId)
}
function duplicateNode(node) {
  pushHistory()
  const id = `n${seq++}`
  nodes.value.push(makeNode({
    id, type: node.data.typeKey, label: `${node.data.label} copy`,
    position: { x: node.position.x + 40, y: node.position.y + 40 },
    config: JSON.parse(JSON.stringify(node.data.config ?? {})),
  }))
}

// Right-click context menu — node/edge/pane, mirroring the same three
// surfaces a click can land on. screenToFlowCoordinate needs the SAME id
// on <VueFlow> and useVueFlow() — called from this parent (not a Vue Flow
// descendant), it silently connects to a disconnected phantom store
// otherwise (see the id="automation-canvas" match below).
const { screenToFlowCoordinate } = useVueFlow('automation-canvas')
const contextMenu = ref({ open: false, x: 0, y: 0, items: [] })

function onNodeContextMenu({ event, node }) {
  if (node.type !== 'workflow') return
  event.preventDefault()
  contextMenu.value = {
    open: true, x: event.clientX, y: event.clientY,
    items: [
      { label: 'Configure', icon: Pencil, action: () => { configPanel.value = { open: true, node } } },
      { label: 'Duplicate', icon: Copy, action: () => duplicateNode(node) },
      { label: 'Delete', icon: Trash2, danger: true, action: () => onDeleteNode(node.id) },
    ],
  }
}
function onEdgeContextMenu({ event, edge }) {
  event.preventDefault()
  contextMenu.value = {
    open: true, x: event.clientX, y: event.clientY,
    items: [
      { label: 'Delete connection', icon: Trash2, danger: true, action: () => {
        pushHistory()
        edges.value = edges.value.filter((e) => e.id !== edge.id)
      } },
    ],
  }
}
function onPaneContextMenu(event) {
  event.preventDefault()
  const flowPos = screenToFlowCoordinate({ x: event.clientX, y: event.clientY })
  const items = paletteGroups.value.flatMap((group) => [
    { heading: group.label },
    ...group.items.map((item) => ({
      label: item.label, icon: item.icon,
      action: () => addNodeAt(item.type, item.label, flowPos),
    })),
  ])
  contextMenu.value = { open: true, x: event.clientX, y: event.clientY, items }
}

// Drag-and-drop from the palette (WORKPLAN-PHASE25 A1) — the top complaint:
// dragging a palette item onto the canvas previously did nothing at all,
// no dragstart/drop wiring existed anywhere. HTML5 DnD, not Vue Flow's own
// node-drag (that's for repositioning EXISTING canvas nodes).
function onPaletteDragStart(event, item) {
  event.dataTransfer.setData('application/x-bp-node-type', item.type)
  event.dataTransfer.setData('application/x-bp-node-label', item.label)
  event.dataTransfer.effectAllowed = 'move'
}
function onCanvasDrop(event) {
  const type = event.dataTransfer.getData('application/x-bp-node-type')
  if (!type) return
  const label = event.dataTransfer.getData('application/x-bp-node-label')
  const flowPos = screenToFlowCoordinate({ x: event.clientX, y: event.clientY })
  addNodeAt(type, label, flowPos)
}

// Every node created through this wrapper (never toCanvasNode directly) gets
// the credential-attach callback wired in — one injection point instead of
// repeating it at every call site (loadStarterExample, load(), addFromPalette).
function makeNode(stored) {
  const n = toCanvasNode(stored)
  n.data.onAttachCredential = onAttachCredential
  return n
}

// markRaw — Vue Flow's node-types map holds component definitions, not
// reactive state; wrapping avoids Vue trying to make the component itself
// reactive (perf footgun with large component trees like this one).
const nodeTypes = {
  workflow: markRaw(WorkflowNode),
  subnode: markRaw(WorkflowSubNode),
  addButton: markRaw(AddNodeButton),
}

const nodes = ref([])
const edges = ref([])
const executionsViewRef = ref(null)

// Undo/redo (WORKPLAN-PHASE25 A6, SHOULD — deferred earlier this session,
// now built). Snapshots go through the SAME toStoredNode/makeNode round-
// trip load()/save() already use, deliberately NOT a raw deep-clone of the
// live Vue Flow node objects: those carry a resolved icon COMPONENT and an
// onAttachCredential FUNCTION in data (see makeNode) — neither survives
// JSON.stringify, and even a structural clone would drag along the
// registry-derived, re-derivable fields. addButton/subnode scaffolding is
// excluded from every snapshot on purpose: addButton only ever exists in
// the illustrative starter example (nothing a real user does creates one),
// and subnodes are fully re-derivable from config.auth.credential via
// materializeCredentialSubnodes, called again after every restore.
// Live-verified consequence, not a bug: a REAL attached credential's
// sub-node correctly survives undo/redo (materializeCredentialSubnodes
// regenerates it from config, which snapshotting does preserve); the
// starter example's two decorative "+"-button nodes and its illustrative
// n3 sub-node (config.auth.credential is null there — a placeholder, not a
// real attachment) do NOT come back after an undo, same as they never
// existed in a save/reload either. Cosmetic, starter-example-only, and
// already true of the rest of the canvas's scaffolding handling.
const undoStack = ref([])
const redoStack = ref([])
const MAX_HISTORY = 50
function snapshot() {
  const storedNodes = nodes.value.filter((n) => n.type === 'workflow').map(toStoredNode)
  const liveIds = new Set(storedNodes.map((n) => n.id))
  const storedEdges = edges.value
    .filter((e) => liveIds.has(e.source) && liveIds.has(e.target))
    .map((e) => ({ ...e }))
  return { nodes: storedNodes, edges: storedEdges, title: title.value }
}
function pushHistory() {
  undoStack.value.push(snapshot())
  if (undoStack.value.length > MAX_HISTORY) undoStack.value.shift()
  redoStack.value = [] // a new action invalidates whatever redo history existed
}
function restoreSnapshot(snap) {
  nodes.value = snap.nodes.map(makeNode)
  edges.value = snap.edges
  title.value = snap.title
  materializeCredentialSubnodes()
}
function undo() {
  if (!undoStack.value.length) return
  redoStack.value.push(snapshot())
  restoreSnapshot(undoStack.value.pop())
}
function redo() {
  if (!redoStack.value.length) return
  undoStack.value.push(snapshot())
  restoreSnapshot(redoStack.value.pop())
}
function isEditableTarget(el) {
  return el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.isContentEditable)
}
// Keyboard shortcuts stay off while a dialog is open — undoing the CANVAS
// while NodeConfigPanel/CredentialPickerModal has its own unsaved draft
// state would desync the two; native text-field undo already covers typing.
function onHistoryKeydown(e) {
  const mod = e.ctrlKey || e.metaKey
  if (!mod || e.key.toLowerCase() !== 'z') return
  if (isEditableTarget(document.activeElement)) return
  if (configPanel.value.open || credentialPicker.value.open) return
  e.preventDefault()
  if (e.shiftKey) redo()
  else undo()
}
onMounted(() => window.addEventListener('keydown', onHistoryKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', onHistoryKeydown))

// A fresh, unsaved workflow starts from this illustrative example (mirrors
// WORKPLAN-PHASE24 01-DATA-MODEL.md §2) rather than a blank canvas — gives a
// new user something concrete to edit instead of an empty page. The
// credential sub-node/edge and the "+" add-buttons are UI-only scaffolding
// (toStoredNode filters them out of what actually gets saved — see its own
// comment); a real credential-picker UI is a follow-up, not built yet.
function loadStarterExample() {
  nodes.value = [
    makeNode({ id: 'n1', type: 'trigger.task_event', label: 'When a task moves to Done', position: { x: 40, y: 160 }, config: { event: 'task.status_changed', to_status: 'Done' }, status: 'success' }),
    makeNode({ id: 'n2', type: 'logic.if', label: 'Is it billable?', position: { x: 340, y: 160 }, config: {}, status: 'success' }),
    makeNode({
      id: 'n3', type: 'integration.http_request', label: 'Notify billing webhook',
      position: { x: 660, y: 60 }, status: 'running',
      config: { auth: { type: 'credential', credential: null, credentialLabel: 'Billing Token' } },
    }),
    { id: 'n3-cred', type: 'subnode', position: { x: 690, y: 210 }, data: { label: 'Billing Token', icon: Key } },
    makeNode({ id: 'n4', type: 'action.notify', label: 'Notify assignee', position: { x: 660, y: 280 }, config: {} }),
    { id: 'n3-add', type: 'addButton', position: { x: 980, y: 88 }, data: {} },
    { id: 'n4-add', type: 'addButton', position: { x: 980, y: 300 }, data: {} },
  ]
  edges.value = [
    { id: 'e1', source: 'n1', target: 'n2' },
    { id: 'e2', source: 'n2', sourceHandle: 'true', target: 'n3' },
    { id: 'e3', source: 'n2', sourceHandle: 'false', target: 'n4' },
    { id: 'e-n3-cred', source: 'n3', sourceHandle: 'cred', target: 'n3-cred', type: 'smoothstep', style: { strokeDasharray: '4 3' } },
    { id: 'e4', source: 'n3', target: 'n3-add' },
    { id: 'e5', source: 'n4', target: 'n4-add' },
  ]
  title.value = 'Task billing webhook'
}

async function load() {
  loading.value = true
  try {
    await ensureNodeRegistryLoaded() // must resolve before toCanvasNode() can resolve icons/ports
    paletteGroups.value = buildPaletteGroups()
    if (!workflowName.value) {
      loadStarterExample()
      await loadAutomationOptions()
      return
    }
    const wf = await getWorkflow(workflowName.value)
    title.value = wf.title
    scope.value = wf.scope
    project.value = wf.project || null
    isActive.value = !!wf.is_active
    lastRunAt.value = wf.last_run_at || null
    lastRunStatus.value = wf.last_run_status || null
    nodes.value = wf.nodes.map(makeNode)
    edges.value = wf.edges
    materializeCredentialSubnodes()
    saveState.value = 'All changes saved'
    await loadAutomationOptions() // needs the real project.value resolved above
  } finally {
    loading.value = false
    isDirty.value = false
  }
}

// WORKPLAN-PHASE25 A6: a saved node's config.auth.credential previously
// round-tripped correctly (config is saved/loaded verbatim, credentialLabel
// included) but its visual sub-node + dashed edge — built once, live, by
// onCredentialSelected — never got recreated on reload, since subnodes are
// deliberately UI-only scaffolding toStoredNode filters out of what's
// saved. No extra fetch needed: credentialLabel already lives inside the
// reloaded config, this just replays the same materialization
// onCredentialSelected does for a fresh pick.
function materializeCredentialSubnodes() {
  for (const node of nodes.value) {
    if (node.type !== 'workflow') continue
    for (const port of node.data.subPorts ?? []) {
      const ref = credentialRef(node, port.field)
      if (!ref?.credential) continue
      const subId = `${node.id}-${port.id}`
      if (nodes.value.some((n) => n.id === subId)) continue
      nodes.value.push({
        id: subId, type: 'subnode',
        position: { x: node.position.x + 30, y: node.position.y + 150 },
        data: { label: ref.label || ref.credential, icon: Key },
      })
      edges.value.push({
        id: `e-${subId}`, source: node.id, sourceHandle: port.id, target: subId,
        type: 'smoothstep', style: { strokeDasharray: '4 3' },
      })
    }
  }
}
onMounted(load)
watch(() => props.workflowId, (id) => { workflowName.value = id; load() })

// Dirty tracking + unload guard (WORKPLAN-PHASE25 A6, SHOULD — kept small
// on purpose: autosave/undo-redo are real, separate features and half-
// building either was worse than just doing this one). The watcher fires
// during load() too (nodes/edges/title all get set there) — resetting
// isDirty at load()'s own end, after everything has settled, cancels that
// out without needing a separate suppress flag.
const isDirty = ref(false)
watch([nodes, edges, title, isActive], () => { isDirty.value = true }, { deep: true })
function onBeforeUnload(e) {
  if (!isDirty.value) return
  e.preventDefault()
  e.returnValue = ''
}
onMounted(() => window.addEventListener('beforeunload', onBeforeUnload))
onBeforeUnmount(() => window.removeEventListener('beforeunload', onBeforeUnload))

async function save() {
  saveState.value = 'Saving…'
  const storedNodes = nodes.value.map(toStoredNode).filter(Boolean)
  const storedEdges = edges.value.filter((e) =>
    storedNodes.some((n) => n.id === e.source) && storedNodes.some((n) => n.id === e.target))
  const res = await saveWorkflow({
    name: workflowName.value, title: title.value, scope: scope.value, project: project.value,
    nodes: storedNodes, edges: storedEdges, is_active: isActive.value ? 1 : 0,
  })
  workflowName.value = res.name
  saveState.value = 'Saved just now'
  isDirty.value = false
}

// A3: Test workflow — pick a task, fire the workflow's own trigger through
// the REAL pipeline (test_workflow does no dry-run — see its own docstring),
// then poll get_workflow_runs for the run that shows up AFTER we fired,
// painting each WorkflowNode's status as results stream in (WorkflowNode
// already renders data.status running/success/error — see toCanvasNode's
// stored.status field, this just mutates it live on the runtime nodes).
const testModal = ref({ open: false })
function openTestModal() {
  if (!workflowName.value) {
    toast.error('Save the workflow before testing it.')
    return
  }
  testModal.value = { open: true }
}
function resetNodeStatuses() {
  for (const n of nodes.value) {
    if (n.type === 'workflow') n.data.status = 'idle'
  }
}
function paintRunOnCanvas(run) {
  const byId = {}
  for (const n of run.nodes) byId[n.node_id] = n.status
  for (const n of nodes.value) {
    if (n.type !== 'workflow') continue
    const status = byId[n.id]
    if (!status) continue
    n.data.status = status === 'Failed' ? 'error' : status === 'Skipped' ? 'idle' : 'success'
  }
}
async function onTestTaskSelected(taskName) {
  testModal.value = { open: false }
  resetNodeStatuses()
  let res
  try {
    res = await testWorkflow(workflowName.value, taskName)
  } catch (e) {
    toast.error(e?.message || 'Could not fire the test event.')
    return
  }
  toast.info(`Test fired: ${res.event}`)

  // Fixed 1s x 10 poll, per spec — no attempt to predict Go's own
  // nanosecond run_id ahead of time (it doesn't exist until runWorkflow
  // generates it server-side); `since` isolates OUR run instead.
  for (let i = 0; i < 10; i++) {
    await new Promise((r) => setTimeout(r, 1000))
    let runs
    try {
      runs = await getWorkflowRuns(workflowName.value, res.fired_at)
    } catch {
      continue
    }
    if (!runs.length) continue
    const run = runs[0]
    paintRunOnCanvas(run)
    const nodeCount = (nodes.value.filter((n) => n.type === 'workflow')).length
    if (run.nodes.length >= nodeCount - 1 || i === 9) {
      // -1: the trigger node itself never gets its own run row (it already
      // fired — that's why we're here, same reasoning runWorkflow's own
      // comment gives for skipping it in the walk).
      toast[run.status === 'Failed' ? 'error' : 'success'](`Test run ${run.status.toLowerCase()}`)
      lastRunAt.value = run.started_at
      lastRunStatus.value = run.status
      return
    }
  }
  toast.warning('Test run is still in progress — check Executions shortly.')
}

// A4: clicking a run in ExecutionsView switches back to Editor with that
// run's per-node statuses painted — same paintRunOnCanvas Test workflow
// uses, one code path for "show me what a run looked like" either way it
// was triggered.
function onViewRun(run) {
  viewMode.value = 'editor'
  resetNodeStatuses()
  paintRunOnCanvas(run)
}
watch(viewMode, (v) => {
  if (v === 'executions') executionsViewRef.value?.load()
})

let seq = 100
// Shared by palette click, palette drag-drop, and the pane right-click menu
// — one place that actually creates a node, not three copies that could
// drift. `addFromPalette`'s old behavior always dropped every new node at
// the SAME hardcoded {x:340,y:420} (WORKPLAN-PHASE25 A1) — stacking node
// after node exactly on top of each other. Cascades from the last add
// instead; drag-drop and the context menu both pass a real cursor position.
let lastAddedPosition = { x: 340, y: 420 }
function addNodeAt(type, label, position) {
  pushHistory()
  const id = `n${seq++}`
  nodes.value.push(makeNode({ id, type, label, position, config: {} }))
  lastAddedPosition = position
  return id
}
function addFromPalette(item) {
  const position = { x: lastAddedPosition.x + 40, y: lastAddedPosition.y + 40 }
  addNodeAt(item.type, item.label, position)
}
</script>

<style>
.wf-canvas {
  /* Theme-adaptive dot grid — color-mix against --foreground so it stays
     visible (not --border's near-invisible 0.15 alpha, tuned for hairlines
     not a background pattern) while automatically flipping with dark mode. */
  --wf-dot-color: color-mix(in oklch, var(--foreground) 22%, transparent);
  background: var(--background);
  /* Root cause of the wire/handle misalignment, found via direct inspection
     of Vue Flow's own store (window.__vf.findNode('n1') — offsetWidth 226
     vs the SAME element's real getBoundingClientRect width 268, a ratio
     matching --ui-zoom exactly): Vue Flow's internal geometry math divides
     getBoundingClientRect measurements by ONLY its own pan/zoom transform,
     with zero awareness of the app's separate `zoom` on <html> (comfortable
     density, see index.css's INTERFACE DENSITY block). The two zooms
     compound in getBoundingClientRect but Vue Flow only undoes one of them,
     so every handle position it computes is off by the --ui-zoom factor —
     exactly the same class of bug index.css's .bp-overlay counter-zoom
     already exists to fix, applied here to a third-party canvas library
     instead of a popover. */
  zoom: calc(1 / var(--ui-zoom));
}
.vue-flow__minimap { border-radius: var(--radius-lg); overflow: hidden; box-shadow: var(--shadow-md); }
.vue-flow__controls { box-shadow: var(--shadow-md); border-radius: var(--radius-md); overflow: hidden; }
.vue-flow__controls-button {
  background: var(--surface);
  border-color: var(--border);
  fill: var(--foreground);
}
.vue-flow__controls-button:hover { background: var(--surface-hover); }
.vue-flow__edge-path { stroke: var(--muted-tertiary); stroke-width: 1.5; }
.vue-flow__edge.selected .vue-flow__edge-path { stroke: var(--accent); }
</style>
