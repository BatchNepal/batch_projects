<template>
  <div
    :class="cn(
      'wf-node group relative flex items-center gap-2.5 rounded-lg border bg-surface px-3 py-2.5 min-w-[180px] transition-colors',
      status === 'error' ? 'border-danger shadow-[0_0_0_3px_var(--danger-soft)]'
        : selected ? 'border-accent shadow-focus' : 'border-border shadow-surface hover:border-border-hover',
    )"
    :title="status === 'error' && data.errorMessage ? data.errorMessage : undefined"
    :style="cardMinHeight ? { minHeight: cardMinHeight + 'px' } : undefined"
  >
    <Handle
      v-if="showTargetHandle"
      type="target"
      :position="Position.Left"
      class="wf-handle"
    />

    <span
      :class="cn('flex items-center justify-center shrink-0 rounded-md size-8', iconBg)"
      :style="iconBg === 'wf-icon-custom' ? { background: accentSoft, color: accentColor } : undefined"
    >
      <Icon :icon="icon" :size="16" :stroke-width="1.75" />
    </span>

    <div class="flex flex-col min-w-0 flex-1">
      <p class="text-sm font-medium text-foreground leading-snug truncate">{{ label }}</p>
      <p v-if="subtitle" class="text-xs text-muted leading-snug truncate">{{ subtitle }}</p>
    </div>

    <span
      v-if="status && status !== 'idle'"
      :class="cn('absolute -top-1.5 -right-1.5 flex items-center justify-center size-4 rounded-full ring-2 ring-[var(--surface)]', STATUS_DOT[status])"
    >
      <Loader2 v-if="status === 'running'" :size="10" class="animate-spin text-white" :stroke-width="3" />
      <Check v-else-if="status === 'success'" :size="10" class="text-white" :stroke-width="3" />
      <X v-else-if="status === 'error'" :size="10" class="text-white" :stroke-width="3" />
    </span>

    <!-- Multi-port (true/false, and now logic.switch's N+1 cases) case:
         handles are spread evenly between 12px-from-top and 12px-from-bottom
         rather than stacked together at center-right — a straight smoothstep
         wire out of any dot travels at that dot's own height, so a label
         placed clear of the wire's lane never gets cut through by it (the
         earlier centered-and-adjacent layout put the label directly in the
         wire's rightward exit lane — live-verified, not a hypothetical).
         Labels alternate above/below their own dot (even index above, odd
         below) rather than all stacking on one side, which is what breaks
         down past 2 ports — this generalizes the original true/false
         placement (i===0 above, i===1 below) to N ports; cardMinHeight below
         gives them enough vertical room to not collide with 3+ ports. -->
    <template v-for="(port, i) in outputPorts" :key="port.id">
      <Handle
        :id="port.id"
        type="source"
        :position="Position.Right"
        :style="outputPorts.length > 1 ? { top: portTop(i, outputPorts.length) } : undefined"
        class="wf-handle"
      />
      <span
        v-if="outputPorts.length > 1 && port.label"
        :class="cn(
          'absolute right-[-6px] z-10 text-[10px] font-medium px-1.5 py-px rounded-full whitespace-nowrap translate-x-1/2',
          i % 2 === 0 ? '-translate-y-full' : '',
          PORT_BADGE[port.tone] ?? PORT_BADGE.default,
        )"
        :style="{ top: `calc(${portTop(i, outputPorts.length)} + ${i % 2 === 0 ? '-8px' : '8px'})` }"
      >{{ port.label }}</span>
    </template>
    <Handle v-if="outputPorts.length === 0 && !isTerminal" type="source" :position="Position.Right" class="wf-handle" />

    <template v-for="port in subPorts" :key="port.id">
      <Handle
        :id="port.id"
        type="source"
        :position="Position.Bottom"
        :style="{ left: port.left }"
        class="wf-handle wf-handle-sub"
      />
    </template>
    <div v-if="subPorts.length" class="absolute left-0 right-0 -bottom-5 flex justify-around px-4">
      <button
        v-for="port in subPorts"
        :key="port.id"
        type="button"
        class="text-[10px] font-medium bg-surface px-1 rounded hover:underline"
        :class="attachedCredentialLabel(port) ? 'text-accent' : 'text-muted'"
        @click.stop="data.onAttachCredential?.(id, port.id)"
      >{{ attachedCredentialLabel(port) ?? port.label }}<span v-if="port.required && !attachedCredentialLabel(port)" class="text-danger">*</span></button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'
import { Check, X, Loader2 } from 'lucide-vue-next'
import Icon from '@/ui/Icon.vue'
import { cn } from '@/lib/utils'

// A generic, registry-driven node card — one component renders every node
// TYPE (trigger/logic/action/integration) rather than one Vue component per
// type, same "declarative, not hardcoded per node" principle the node
// registry itself follows (see WORKPLAN-PHASE24 02-NODE-LIBRARY.md §3).
const props = defineProps({
  id:       { type: String, required: true },
  data:     { type: Object, required: true }, // { label, subtitle, icon, category, outputPorts, subPorts, status, accentColor }
  selected: { type: Boolean, default: false },
})
function attachedCredentialLabel(port) {
  if (port.id !== 'cred') return null
  if ((port.field ?? 'auth') === 'auth') return props.data.config?.auth?.credentialLabel ?? null
  return props.data.config?.[`${port.field}_label`] ?? null
}

const label    = computed(() => props.data.label)
const subtitle = computed(() => props.data.subtitle)
const icon     = computed(() => props.data.icon)
const status   = computed(() => props.data.status)
// A single-output node (action/integration) whose Settings tab has
// on_error="error_branch" needs somewhere to actually route the error
// case — bp_workflow.py's own validator already requires a real edge off
// a sourceHandle:'error' port for that mode, so the port must exist before
// a user can wire it. Registry-driven multi-port nodes (logic.if's
// true/false) are untouched — this only kicks in when the base registry
// gives zero named ports. The first (unlabeled) entry keeps `id: undefined`
// so existing/new normal edges (which never set sourceHandle) keep
// resolving to it via Vue Flow's own "no handleId -> bounds[0]" fallback.
const outputPorts = computed(() => {
  const base = props.data.outputPorts ?? []
  if (base.length === 0 && props.data.onError === 'error_branch') {
    return [{ id: undefined, label: '', tone: 'default' }, { id: 'error', label: 'error', tone: 'error' }]
  }
  return base
})
const subPorts     = computed(() => props.data.subPorts ?? [])
const isTerminal   = computed(() => props.data.isTerminal ?? false)

// Evenly spread port i of n between 12px-from-top and 12px-from-bottom.
// At n=2 this reduces to exactly the original hardcoded values (0 and 1 ->
// 12px / calc(100% - 12px)), so logic.if's existing look is unchanged.
function portTop(i, n) {
  const frac = n <= 1 ? 0 : i / (n - 1)
  return `calc(12px + (100% - 24px) * ${frac})`
}
// logic.switch can have up to 6 ports (5 cases + default) — the default
// compact card (~44px tall) has no room to spread that many dots/labels
// without overlap, so grow the card's min-height once there are more than
// 2 outputs. 2-port nodes (logic.if) are untouched, keeping their existing
// compact size.
//
// The 56px-per-gap figure isn't arbitrary: adjacent ports alternate their
// label above/below the dot, so the TIGHTEST case is two labels pointing at
// EACH OTHER from neighboring dots (dot i's label going down, dot i+1's
// label going up) — each needs ~26px clearance (8px offset + ~18px badge
// height) from its own dot, so the two dots need >=52px between them or
// the labels collide. Live-verified this exact collision at 22px/port
// before bumping it — "L don" from an overlapped "blocked"/"done" pair.
const cardMinHeight = computed(() => {
  const n = outputPorts.value.length
  return n > 2 ? Math.max(64, 24 + (n - 1) * 56) : undefined
})
const showTargetHandle = computed(() => props.data.category !== 'trigger')

const accentColor = computed(() => props.data.accentColor ?? 'var(--accent)')
const accentSoft  = computed(() => props.data.accentSoft ?? 'var(--accent-soft)')

// Category -> icon chip treatment. Triggers get the app's accent; everything
// else uses a neutral chip so ONLY the trigger (and any custom-accented
// integration node, e.g. a specific third-party brand color) draws the eye —
// "chrome whispers, data sings" from this app's own design law, applied to
// node chrome vs a node's actual distinguishing icon.
const iconBg = computed(() => {
  if (props.data.accentColor) return 'wf-icon-custom'
  return {
    trigger: 'bg-accent-soft text-accent-soft-foreground',
    logic: 'bg-warning-soft text-warning-soft-foreground',
    action: 'bg-surface-tertiary text-foreground',
    integration: 'bg-success-soft text-success-soft-foreground',
  }[props.data.category] ?? 'bg-surface-tertiary text-foreground'
})

const STATUS_DOT = {
  running: 'bg-accent',
  success: 'bg-success',
  error: 'bg-danger',
}
const PORT_BADGE = {
  true: 'bg-success-soft text-success-soft-foreground',
  false: 'bg-danger-soft text-danger-soft-foreground',
  error: 'bg-danger-soft text-danger-soft-foreground',
  default: 'bg-surface-tertiary text-muted',
}
</script>

<style scoped>
.wf-node { box-shadow: var(--shadow-sm); }
:deep(.wf-handle) {
  width: 8px;
  height: 8px;
  background: var(--surface);
  border: 1.5px solid var(--border-hover, var(--border));
}
:deep(.wf-handle:hover) { border-color: var(--accent); }
:deep(.wf-handle-sub) { background: var(--muted-tertiary); }
</style>
