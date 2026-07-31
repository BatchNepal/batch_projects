<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="fixed inset-0 z-dropdown"
      @click="close"
      @contextmenu.prevent="close"
    />
    <div
      v-if="open"
      class="bp-overlay fixed z-dropdown overflow-hidden rounded-lg border border-border bg-overlay shadow-overlay p-1.5 outline-none"
      style="min-width: 190px; max-height: 70vh; overflow-y: auto"
      :style="{ left: clampedX + 'px', top: clampedY + 'px' }"
      @click.stop
      @contextmenu.stop.prevent
    >
      <template v-for="(item, i) in items" :key="i">
        <div v-if="item.heading" class="px-2 pt-2 pb-1 text-[11px] font-medium uppercase tracking-wider text-muted">{{ item.heading }}</div>
        <DropdownItem v-else :color="item.danger ? 'danger' : 'default'" @click="select(item)">
          <template v-if="item.icon" #startContent><Icon :icon="item.icon" class="size-3.5" /></template>
          {{ item.label }}
        </DropdownItem>
      </template>
      <p v-if="!items.length" class="px-2 py-1.5 text-xs text-muted italic">Nothing here</p>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, provide } from 'vue'
import DropdownItem from '@/ui/DropdownItem.vue'
import Icon from '@/ui/Icon.vue'

// A standalone, arbitrarily-positioned (right-click) menu — Dropdown.vue
// only anchors to a trigger slot, not a click coordinate, so this is a
// small sibling rather than a reuse. Same .bp-overlay counter-zoom +
// DropdownItem styling for visual consistency with the rest of the app.
const props = defineProps({
  open:  { type: Boolean, default: false },
  x:     { type: Number, default: 0 },
  y:     { type: Number, default: 0 },
  items: { type: Array, default: () => [] }, // { label, icon, danger, action } | { heading }
})
const emit = defineEmits(['update:open'])

function close() { emit('update:open', false) }
provide('dropdown-hide', close)

function select(item) {
  item.action?.()
  close()
}

// Keep the menu on-screen near viewport edges (right-clicking near the
// canvas's right/bottom edge would otherwise render it partly off-screen).
const clampedX = computed(() => Math.min(props.x, window.innerWidth - 210))
const clampedY = computed(() => Math.min(props.y, window.innerHeight - 40 - props.items.length * 32))
</script>
