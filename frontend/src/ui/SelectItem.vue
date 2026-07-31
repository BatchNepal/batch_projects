<template>
  <div
    role="option"
    :aria-selected="isSelected"
    :aria-disabled="isDisabled || undefined"
    :tabindex="isDisabled ? -1 : 0"
    :class="cn(
      'sel-item relative flex items-center gap-2 px-2.5 rounded-[5px] cursor-pointer select-none',
      'text-foreground outline-none',
      'hover:bg-default focus-visible:bg-default',
      isSelected && 'font-medium',
      isDisabled && 'opacity-45 cursor-not-allowed pointer-events-none',
      ITEM_SIZE[ctx?.size?.value ?? 'md'],
    )"
    @click="handleSelect"
    @keydown.enter.prevent="handleSelect"
    @keydown.space.prevent="handleSelect"
  >
    <span class="flex-1 truncate text-start">
      <slot />
    </span>
    <svg
      v-if="isSelected"
      class="shrink-0 text-foreground"
      width="12" height="12" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" stroke-width="2.5"
      stroke-linecap="round" stroke-linejoin="round"
    ><path d="M5 13l4 4L19 7"/></svg>
  </div>
</template>

<script setup>
import { inject, computed, onMounted, onBeforeUnmount, useSlots } from 'vue'
import { cn } from '@/lib/utils'

// HeroUI list-box-item: min-h-9 rows at standard size, press scale(0.98)
const ITEM_SIZE = {
  sm: 'min-h-[30px] py-1 text-[13px]',
  md: 'min-h-[32px] py-1.5 text-sm',
  lg: 'min-h-9 py-2 text-sm',
}

const props = defineProps({
  value:      { required: true },
  isDisabled: { type: Boolean, default: false },
})

const slots = useSlots()
const ctx = inject('select-ctx', null)

const isSelected = computed(() => ctx?.modelValue.value === props.value)

function getLabel() {
  // Extract text content from the default slot
  const vnode = slots.default?.()[0]
  if (!vnode) return String(props.value)
  if (typeof vnode.children === 'string') return vnode.children.trim()
  return vnode.el?.textContent?.trim() || String(props.value)
}

onMounted(()       => ctx?.register(props.value, getLabel()))
onBeforeUnmount(() => ctx?.unregister(props.value))

function handleSelect() {
  if (props.isDisabled) return
  ctx?.onSelect(props.value)
}
</script>

<style scoped>
.sel-item {
  transition: background-color var(--duration-fast) var(--ease-out), transform 250ms var(--ease-smooth);
}
.sel-item:active { transform: scale(0.98); transition: transform 40ms ease-out; }
</style>
