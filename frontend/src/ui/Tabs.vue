<template>
  <div :class="cn('flex flex-col', $attrs.class)">
    <div
      role="tablist"
      :aria-label="ariaLabel || undefined"
      :class="cn('flex items-center gap-0.5', variant === 'underline' ? 'border-b border-separator' : 'bg-default rounded-md p-0.5 w-fit')"
      @keydown="onKeydown"
    >
      <button
        v-for="tab in tabs"
        :key="tab.value"
        ref="tabEls"
        type="button"
        role="tab"
        :id="`${uid}-tab-${tab.value}`"
        :aria-selected="modelValue === tab.value"
        :aria-controls="`${uid}-panel-${tab.value}`"
        :aria-disabled="tab.disabled || undefined"
        :disabled="tab.disabled"
        :tabindex="modelValue === tab.value ? 0 : -1"
        :class="cn(
          'tab relative text-sm font-medium transition-colors duration-fast',
          'disabled:opacity-40 disabled:pointer-events-none',
          variant === 'underline'
            ? cn('px-3 h-8', modelValue === tab.value ? 'text-foreground' : 'text-muted hover:text-foreground')
            : cn('px-3 h-7 rounded-sm', modelValue === tab.value ? 'bg-surface text-foreground shadow-xs' : 'text-muted hover:text-foreground'),
        )"
        @click="emit('update:modelValue', tab.value)"
      >
        <component v-if="tab.icon" :is="tab.icon" class="inline-block mr-1.5 -mt-px" style="width:13px;height:13px" />
        {{ tab.label }}
        <span v-if="variant === 'underline' && modelValue === tab.value" class="absolute bottom-0 left-0 right-0 h-[2px] bg-accent rounded-full" />
      </button>
    </div>
    <slot />
  </div>
</template>

<script setup>
import { ref, nextTick, useId } from 'vue'
import { cn } from '@/lib/utils'
const props = defineProps({
  modelValue: { default: '' },
  tabs:       { type: Array, default: () => [] }, // [{ value, label, icon?, disabled? }]
  variant:    { type: String, default: 'underline' }, // underline | segment
  ariaLabel:  { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue'])

// Stable per-instance prefix so tab/panel ids can't collide when two Tabs
// render on the same screen (Reports and Dashboards both do).
const uid = useId()
const tabEls = ref([])

/* WAI-ARIA tabs pattern. Previously these were plain <button>s in a <div>:
   no roles, so a screen reader announced "button" with no notion of a tab set,
   selected state, or which panel it controls — and every tab was a separate
   tab stop, so keyboarding past a 6-tab bar took six presses.

   Roving tabindex fixes both: exactly ONE tab is in the tab order (the
   selected one) and Left/Right move between them, Home/End jump to the ends.
   Disabled tabs are skipped rather than trapping the cursor. */
function onKeydown(e) {
  const keys = ['ArrowRight', 'ArrowLeft', 'Home', 'End']
  if (!keys.includes(e.key)) return
  const enabled = props.tabs.filter(t => !t.disabled)
  if (!enabled.length) return
  e.preventDefault()

  const cur = enabled.findIndex(t => t.value === props.modelValue)
  let next
  if (e.key === 'Home') next = 0
  else if (e.key === 'End') next = enabled.length - 1
  // Wraps, per the ARIA pattern — reaching the end and continuing returns
  // to the start rather than dead-ending.
  else if (e.key === 'ArrowRight') next = (cur + 1) % enabled.length
  else next = (cur - 1 + enabled.length) % enabled.length

  const target = enabled[next]
  emit('update:modelValue', target.value)
  // Focus must follow selection or the roving tabindex strands the user on a
  // button that just became tabindex="-1".
  nextTick(() => {
    const i = props.tabs.findIndex(t => t.value === target.value)
    tabEls.value[i]?.focus()
  })
}
</script>

<style scoped>
.tab { transition: background-color var(--duration-fast) var(--ease-out), color var(--duration-fast) var(--ease-out); }
</style>
