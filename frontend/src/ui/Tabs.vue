<template>
  <div :class="cn('flex flex-col', $attrs.class)">
    <div :class="cn('flex items-center gap-0.5', variant === 'underline' ? 'border-b border-separator' : 'bg-default rounded-md p-0.5 w-fit')">
      <button
        v-for="tab in tabs"
        :key="tab.value"
        type="button"
        :disabled="tab.disabled"
        :class="cn(
          'tab relative text-sm font-medium outline-none transition-colors duration-90',
          'disabled:opacity-40 disabled:pointer-events-none',
          variant === 'underline'
            ? cn('px-3 h-8', modelValue === tab.value ? 'text-foreground' : 'text-muted hover:text-foreground')
            : cn('px-3 h-7 rounded-[5px]', modelValue === tab.value ? 'bg-surface text-foreground shadow-xs' : 'text-muted hover:text-foreground'),
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
import { cn } from '@/lib/utils'
const props = defineProps({
  modelValue: { default: '' },
  tabs:       { type: Array, default: () => [] }, // [{ value, label, icon?, disabled? }]
  variant:    { type: String, default: 'underline' }, // underline | segment
})
const emit = defineEmits(['update:modelValue'])
</script>

<style scoped>
.tab { transition: background-color var(--duration-fast) var(--ease-out), color var(--duration-fast) var(--ease-out); }
</style>
