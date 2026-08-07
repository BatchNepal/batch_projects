<template>
  <div class="smb" ref="rootEl">
    <!-- Primary action — rounded-full on the OUTER (left) edge -->
    <button type="button" class="smb-main" :disabled="disabled" @click="emit('action')">
      <component v-if="icon" :is="icon" class="smb-main-ic" :size="15" :stroke-width="2" />
      <span>{{ label }}</span>
    </button>

    <!-- Hairline split -->
    <span class="smb-split" aria-hidden="true" />

    <!-- Caret — rounded-full on the OUTER (right) edge -->
    <button type="button" class="smb-caret" :class="{ open }" :disabled="disabled"
      :aria-expanded="open" aria-haspopup="menu" @click="open = !open">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
        stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6" /></svg>
    </button>

    <!-- Floating HeroUI card of options -->
    <Teleport to="body">
      <Transition name="smb-pop">
        <div v-if="open" ref="panelEl" class="smb-panel" :style="pos" role="menu" @click.stop>
          <button
            v-for="(opt, i) in options" :key="i"
            type="button" class="smb-opt" role="menuitem"
            @click="choose(opt)">
            <span class="smb-opt-ic" :style="opt.color ? { background: opt.color + '1F', color: opt.color } : {}">
              <component :is="opt.icon" :size="16" :stroke-width="1.85" />
            </span>
            <span class="smb-opt-text">
              <span class="smb-opt-label">{{ opt.label }}</span>
              <span v-if="opt.desc" class="smb-opt-desc">{{ opt.desc }}</span>
            </span>
          </button>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'

const props = defineProps({
  label:    { type: String, default: 'Action' },
  icon:     { type: [Object, Function], default: null },
  // [{ label, desc?, icon, color?, value? }]
  options:  { type: Array, default: () => [] },
  align:    { type: String, default: 'end' }, // start | end
  disabled: { type: Boolean, default: false },
})
const emit = defineEmits(['action', 'select'])

const open    = ref(false)
const rootEl  = ref(null)
const panelEl = ref(null)
const pos     = ref({})

function reposition() {
  requestAnimationFrame(() => {
    if (!rootEl.value || !panelEl.value) return
    const t = rootEl.value.getBoundingClientRect()
    const p = panelEl.value.getBoundingClientRect()
    const gap = 8
    let top  = t.bottom + gap
    let left = props.align === 'end' ? t.right - p.width : t.left
    if (top + p.height > window.innerHeight - 8) top = t.top - p.height - gap
    left = Math.max(8, Math.min(left, window.innerWidth - p.width - 8))
    pos.value = { top: top + 'px', left: left + 'px', minWidth: t.width + 'px' }
  })
}
function choose(opt) {
  open.value = false
  emit('select', opt)
  opt.onSelect?.(opt)
}
function onDocDown(e) {
  if (!open.value) return
  if (rootEl.value?.contains(e.target) || panelEl.value?.contains(e.target)) return
  open.value = false
}
watch(open, v => { if (v) nextTick(reposition) })
onMounted(() => {
  document.addEventListener('pointerdown', onDocDown, true)
  window.addEventListener('scroll', reposition, true)
  window.addEventListener('resize', reposition)
})
onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', onDocDown, true)
  window.removeEventListener('scroll', reposition, true)
  window.removeEventListener('resize', reposition)
})
</script>

<style scoped>
/* Split pill — depth from fill + press physics, NOT borders. */
.smb { display: inline-flex; align-items: stretch; height: 36px; isolation: isolate; }

.smb-main, .smb-caret {
  display: inline-flex; align-items: center; gap: 7px;
  background: var(--accent); color: var(--accent-foreground);
  border: none; cursor: pointer; font-family: inherit; font-size: 13px; font-weight: 600;
  transition: background-color var(--duration-fast) var(--ease-out), transform var(--duration-base) var(--ease-smooth);
  -webkit-tap-highlight-color: transparent; outline: none;
}
.smb-main  { padding: 0 16px 0 18px; border-radius: 999px 0 0 999px; }
.smb-caret { padding: 0 12px; border-radius: 0 999px 999px 0; }
.smb-main-ic { margin-left: -2px; }

.smb-split { width: 1px; background: color-mix(in oklab, var(--accent-foreground) 28%, transparent); z-index: 1; }

@media (hover: hover) {
  .smb-main:hover, .smb-caret:hover { background: var(--accent-hover); }
}
.smb-main:active  { transform: scale(0.97); }
.smb-caret:active { transform: scale(0.95); }
.smb-caret svg { transition: transform var(--duration-base) var(--ease-smooth); }
.smb-caret.open svg { transform: rotate(180deg); }
.smb-main:disabled, .smb-caret:disabled { opacity: 0.5; pointer-events: none; }
.smb-main:focus-visible, .smb-caret:focus-visible {
  box-shadow: 0 0 0 2px var(--surface), 0 0 0 4px var(--focus);
}

/* Floating card — overlay shadow carries the depth; no border box */
.smb-panel {
  position: fixed; z-index: var(--z-popover, 1110);
  background: var(--overlay); border-radius: var(--radius-lg);
  box-shadow: var(--overlay-shadow); padding: 6px; max-width: 320px;
}
.smb-opt {
  display: flex; align-items: center; gap: 11px; width: 100%; text-align: left;
  padding: 8px 10px; border: none; background: none; border-radius: var(--radius-md);
  cursor: pointer; font-family: inherit; transition: background-color var(--duration-fast) var(--ease-out);
}
.smb-opt:hover { background: var(--surface-secondary); }
.smb-opt:active { transform: scale(0.985); }
.smb-opt-ic {
  display: grid; place-items: center; width: 32px; height: 32px; flex-shrink: 0;
  border-radius: var(--radius-md); background: var(--surface-secondary); color: var(--muted);
}
.smb-opt-text { display: flex; flex-direction: column; min-width: 0; }
.smb-opt-label { font-size: 13px; font-weight: 500; color: var(--foreground); }
.smb-opt-desc  { font-size: 11.5px; color: var(--muted); line-height: 1.35; }

.smb-pop-enter-active { transition: opacity var(--duration-fast) var(--ease-out), transform var(--duration-fast) var(--ease-smooth); transform-origin: top right; }
.smb-pop-leave-active { transition: opacity var(--duration-fast) var(--ease-in), transform var(--duration-fast) var(--ease-in); }
.smb-pop-enter-from, .smb-pop-leave-to { opacity: 0; transform: scale(0.95) translateY(-4px); }
</style>
