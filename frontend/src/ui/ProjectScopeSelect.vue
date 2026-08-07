<template>
  <!-- Trigger button -->
  <div ref="triggerRef" class="relative" @click.stop>
    <button
      type="button"
      class="heroui-select inline-flex items-center gap-1.5 h-6 pl-2.5 pr-2 rounded-md bg-default hover:bg-[--surface-hover] text-[--foreground] text-xs font-medium outline-none transition-[background-color,box-shadow] cursor-pointer focus-visible:ring-2 focus-visible:ring-[--accent]/25"
      :class="{ 'border-[--accent] ring-2 ring-[--accent]/20': open }"
      @click="toggle"
    >
      <span class="truncate max-w-[160px]">{{ label }}</span>
      <svg class="w-3 h-3 text-[--muted] shrink-0 transition-transform" :class="open ? 'rotate-180' : ''" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5">
        <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7"/>
      </svg>
    </button>

    <!-- Dropdown panel -->
    <Teleport to="body">
      <Transition name="pss-pop">
        <div
          v-if="open"
          ref="panelRef"
          :style="panelStyle"
          class="bp-overlay fixed z-dropdown bg-overlay border border-border shadow-popover rounded-lg w-[240px] py-1 outline-none"
          @click.stop
        >
          <!-- All projects shortcut -->
          <button
            type="button"
            class="w-full flex items-center gap-2 px-3 py-1.5 text-[13px] font-medium text-foreground hover:bg-default transition-colors cursor-pointer"
            @click="selectAll"
          >
            <span class="w-4 h-4 rounded border border-border-secondary flex items-center justify-center shrink-0"
              :class="isAll ? 'bg-primary border-primary' : 'bg-overlay'">
              <svg v-if="isAll" class="w-2.5 h-2.5 text-white" fill="none" viewBox="0 0 12 12" stroke="currentColor" stroke-width="2.5">
                <path stroke-linecap="round" stroke-linejoin="round" d="M2 6l3 3 5-5"/>
              </svg>
            </span>
            All projects
          </button>

          <div class="h-px bg-border mx-2 my-1" />

          <!-- Per-project checkboxes -->
          <div class="max-h-[220px] overflow-y-auto">
            <button
              v-for="p in projects"
              :key="p.name"
              type="button"
              class="w-full flex items-center gap-2 px-3 py-1.5 text-[13px] text-foreground hover:bg-default transition-colors cursor-pointer"
              @click="toggleProject(p.name)"
            >
              <span class="w-4 h-4 rounded border border-border-secondary flex items-center justify-center shrink-0"
                :class="isSelected(p.name) ? 'bg-primary border-primary' : 'bg-overlay'">
                <svg v-if="isSelected(p.name)" class="w-2.5 h-2.5 text-white" fill="none" viewBox="0 0 12 12" stroke="currentColor" stroke-width="2.5">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M2 6l3 3 5-5"/>
                </svg>
              </span>
              <span class="truncate flex-1 text-left">{{ p.project_name }}</span>
            </button>
          </div>

          <!-- Confirm footer when multi-select differs -->
          <template v-if="!isAll && selectedCount > 0">
            <div class="h-px bg-border mx-2 mt-1" />
            <div class="px-3 py-2 flex items-center justify-between">
              <span class="text-[11px] text-[--muted]">{{ selectedCount }} selected</span>
              <button
                type="button"
                class="text-[12px] font-semibold text-primary hover:opacity-80 cursor-pointer"
                @click="open = false"
              >Apply</button>
            </div>
          </template>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'

const props = defineProps({
  // modelValue: 'all' | string (single project name) | string[] (multi)
  modelValue: { default: 'all' },
  projects: { type: Array, default: () => [] }, // [{ name, project_name }]
  // When used inside a widget configure panel, show an "Inherit" option
  allowInherit: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])

// ── normalise value ───────────────────────────────────────────────
const selected = computed(() => {
  const v = props.modelValue
  if (!v || v === 'all') return 'all'
  if (v === 'inherit') return 'inherit'
  if (Array.isArray(v)) return v
  return v // single string
})

const isAll = computed(() => selected.value === 'all' || selected.value === 'inherit')

const selectedCount = computed(() => {
  if (isAll.value) return props.projects.length
  if (Array.isArray(selected.value)) return selected.value.length
  return 1
})

function isSelected(name) {
  if (isAll.value) return false
  if (Array.isArray(selected.value)) return selected.value.includes(name)
  return selected.value === name
}

function selectAll() {
  emit('update:modelValue', 'all')
}

function toggleProject(name) {
  const cur = selected.value
  let next
  if (isAll.value) {
    // switching from "all" to single
    next = [name]
  } else if (Array.isArray(cur)) {
    const idx = cur.indexOf(name)
    if (idx >= 0) {
      next = cur.filter(n => n !== name)
      if (next.length === 0) next = 'all'
    } else {
      next = [...cur, name]
      // if every project checked, normalise to "all"
      if (next.length === props.projects.length) next = 'all'
    }
  } else {
    // was single string
    if (cur === name) {
      next = 'all'
    } else {
      next = [cur, name]
    }
  }
  emit('update:modelValue', next)
}

// ── label ─────────────────────────────────────────────────────────
const label = computed(() => {
  const v = selected.value
  if (v === 'inherit') return 'Inherit'
  if (v === 'all' || !v) return 'All projects'
  if (Array.isArray(v)) {
    if (v.length === 0) return 'All projects'
    if (v.length === 1) {
      return props.projects.find(p => p.name === v[0])?.project_name || v[0]
    }
    return `${v.length} projects`
  }
  return props.projects.find(p => p.name === v)?.project_name || v
})

// ── positioning ──────────────────────────────────────────────────
const open = ref(false)
const triggerRef = ref(null)
const panelRef = ref(null)
const panelStyle = ref({})

function updatePos() {
  if (!triggerRef.value || !panelRef.value) return
  const t = triggerRef.value.getBoundingClientRect()
  const f = panelRef.value.getBoundingClientRect()
  const gap = 4
  let top = t.bottom + gap
  let left = t.left
  if (top + f.height > window.innerHeight - 8) top = t.top - f.height - gap
  if (left + f.width > window.innerWidth - 8) left = t.right - f.width
  left = Math.max(8, left)
  top = Math.max(8, top)
  panelStyle.value = { top: top + 'px', left: left + 'px' }
}

function toggle() { open.value ? close() : show() }
function show() { open.value = true; nextTick(updatePos) }
function close() { open.value = false }

function onPointerDown(e) {
  if (!open.value) return
  if (panelRef.value?.contains(e.target)) return
  if (triggerRef.value?.contains(e.target)) return
  close()
}
function onKeydown(e) { if (e.key === 'Escape') close() }

onMounted(() => {
  document.addEventListener('pointerdown', onPointerDown, true)
  document.addEventListener('keydown', onKeydown, true)
})
onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', onPointerDown, true)
  document.removeEventListener('keydown', onKeydown, true)
})

watch(open, v => {
  if (v) {
    window.addEventListener('scroll', updatePos, true)
    window.addEventListener('resize', updatePos)
  } else {
    window.removeEventListener('scroll', updatePos, true)
    window.removeEventListener('resize', updatePos)
  }
})
</script>

<style scoped>
.heroui-select {
  transition: background-color var(--duration-base) var(--ease-out), border-color var(--duration-base) var(--ease-out), box-shadow var(--duration-base) var(--ease-out);
}
.pss-pop-enter-active { transition: opacity var(--duration-fast) var(--ease-out), transform var(--duration-fast) var(--ease-smooth); }
.pss-pop-leave-active { transition: opacity var(--duration-fast) var(--ease-in), transform var(--duration-fast) var(--ease-in); }
.pss-pop-enter-from   { opacity: 0; transform: translateY(-4px) scale(0.97); }
.pss-pop-leave-to     { opacity: 0; transform: scale(0.97); }
</style>
