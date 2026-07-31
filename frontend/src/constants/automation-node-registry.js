// Fetches the node-type registry from the backend (batch_projects.api.
// automation.get_node_registry — WORKPLAN-PHASE24 02-NODE-LIBRARY.md) so
// this file is no longer a second, hand-maintained copy that can drift from
// the Python source of truth. Icon names come back as strings (JSON-safe);
// ICON_MAP resolves them to the actual Lucide component for rendering.
import {
  Zap, Clock, Webhook, GitBranch, Filter, Bell, CheckCircle2, Globe, Tag, Calendar, MessageSquare,
  MessageCircle, Send, Layers, Rows3, CircleDollarSign, MousePointerClick, Users, MessagesSquare,
} from 'lucide-vue-next'
import { getNodeRegistry } from '@/utils/api'

const ICON_MAP = {
  Zap, Clock, Webhook, GitBranch, Filter, Bell, CheckCircle2, Globe, Tag, Calendar, MessageSquare,
  MessageCircle, Send, Layers, Rows3, CircleDollarSign, MousePointerClick, Users, MessagesSquare,
}

let _registry = null
let _fetchPromise = null

// Call once (AutomationCanvas.vue does this in onMounted, before load()) —
// subsequent calls reuse the same in-flight/resolved promise, so multiple
// components mounting concurrently don't each fire their own request.
export async function ensureNodeRegistryLoaded() {
  if (_registry) return _registry
  if (!_fetchPromise) {
    _fetchPromise = getNodeRegistry().then((raw) => {
      _registry = raw
      return raw
    })
  }
  return _fetchPromise
}

export function nodeMeta(type) {
  const entry = _registry?.[type]
  if (!entry) {
    // Registry not loaded yet, or an unknown type (e.g. saved by a newer
    // build). Degrade to a generic placeholder rather than throwing —
    // a workflow with an unrecognized node type should still render.
    return { category: 'action', icon: CheckCircle2, label: type }
  }
  return { ...entry, icon: ICON_MAP[entry.icon] ?? CheckCircle2 }
}

// logic.switch's port count depends on how many `cases` the user has
// configured — unlike logic.if's fixed true/false, there is no static
// output_ports list for it in the registry (WORKPLAN-PHASE25 C5). Called
// both at node-creation/load time (toCanvasNode below) and again after every
// config Apply (AutomationCanvas.vue's onSaveNodeConfig), so the two never
// drift. Cap of 5 mirrors the backend's config_schema description.
export function switchOutputPorts(cases) {
  const list = (Array.isArray(cases) ? cases : []).slice(0, 5)
  return [
    ...list.map((c, i) => ({ id: `case-${i}`, label: c || `case ${i + 1}`, tone: 'default' })),
    { id: 'default', label: 'default', tone: 'default' },
  ]
}

// stored (backend/JSON-safe) node -> Vue Flow runtime node
export function toCanvasNode(stored) {
  const meta = nodeMeta(stored.type)
  const outputPorts = stored.type === 'logic.switch'
    ? switchOutputPorts(stored.config?.cases)
    : (meta.output_ports ?? []).map((p) => ({ id: p.id, label: p.label, tone: p.id }))
  return {
    id: stored.id,
    type: 'workflow',
    position: stored.position ?? { x: 0, y: 0 },
    selected: false,
    data: {
      label: stored.label ?? meta.label,
      subtitle: `${meta.category[0].toUpperCase()}${meta.category.slice(1)} · ${meta.label}`,
      icon: meta.icon,
      category: meta.category,
      outputPorts,
      // `field` says which config key holds the credential reference — 'auth'
      // (a {type,credential} union, integration.http_request's own shape) vs
      // a flat string field name (integration.slack/discord/telegram's
      // `credential`). Carried through so AutomationCanvas.vue/WorkflowNode.vue
      // don't have to special-case node types themselves — see
      // credentialRef()/applyCredentialRef() in AutomationCanvas.vue.
      subPorts: (meta.sub_ports ?? []).map((p) => ({ id: p.id, label: p.label, left: '50%', required: false, field: p.field ?? 'auth' })),
      status: stored.status ?? 'idle',
      config: stored.config ?? {},
      disabled: stored.disabled ?? false,
      retry: stored.retry ?? null,
      onError: stored.on_error ?? 'stop',
      typeKey: stored.type, // preserved verbatim so toStoredNode can round-trip it exactly
    },
  }
}

// Vue Flow runtime node -> stored (backend/JSON-safe) node — strips
// presentation-only fields (icon component refs, computed subtitle) that
// are re-derived from `type` on load, never persisted.
export function toStoredNode(canvasNode) {
  if (canvasNode.type !== 'workflow') return null // subnode/addButton are UI scaffolding, not persisted graph nodes
  const d = canvasNode.data
  return {
    id: canvasNode.id,
    type: d.typeKey,
    label: d.label,
    position: canvasNode.position,
    config: d.config ?? {},
    disabled: d.disabled ?? false,
    ...(d.retry ? { retry: d.retry } : {}),
    ...(d.onError && d.onError !== 'stop' ? { on_error: d.onError } : {}),
  }
}

// Palette grouping — category order/labels are a UI concern, not backend
// data, so this stays here; the actual node TYPES per category come from
// the loaded registry (paletteGroups() must be called after
// ensureNodeRegistryLoaded() resolves).
const CATEGORY_ORDER = [
  { category: 'trigger', label: 'Triggers' },
  { category: 'logic', label: 'Logic' },
  { category: 'action', label: 'Actions' },
  { category: 'integration', label: 'Integrations' },
]

export function paletteGroups() {
  if (!_registry) return []
  return CATEGORY_ORDER.map((g) => ({
    ...g,
    // hidden: true (e.g. integration.webhook_response — WORKPLAN-PHASE25 B3,
    // deferred wait_for_workflow) stays resolvable via nodeMeta() for any
    // already-saved workflow, just not offered as something NEW to place.
    items: Object.entries(_registry)
      .filter(([, meta]) => meta.category === g.category && !meta.hidden)
      .map(([type, meta]) => ({ type, ...nodeMeta(type) })),
  })).filter((g) => g.items.length > 0)
}
