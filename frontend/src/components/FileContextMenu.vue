<template>
  <Teleport to="body">
    <div v-if="file" ref="menuEl" class="bp-overlay fc-menu" :style="menuStyle" role="menu">
      <button class="fc-item" role="menuitem" @click="$emit('rename', file)">
        <Pencil :size="13" :stroke-width="1.75" /> Rename
      </button>
      <a class="fc-item" role="menuitem" :href="file.file_url" target="_blank" download @click="$emit('close')">
        <Download :size="13" :stroke-width="1.75" /> Download
      </a>
      <div class="fc-sep" />
      <button class="fc-item fc-item--danger" role="menuitem" @click="$emit('delete', file)">
        <Trash2 :size="13" :stroke-width="1.75" /> Delete
      </button>
    </div>
  </Teleport>
</template>

<script setup>
// Cursor-positioned right-click menu for a file card/row — same teleport +
// viewport-clamped fixed-position technique as TaskContextMenu.vue, just
// with the 3 actions a file needs instead of a full task's ~15.
import { ref, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { Pencil, Download, Trash2 } from 'lucide-vue-next'

const props = defineProps({
  file: { type: Object, default: null }, // the file row, or null when closed
  x:    { type: Number, default: 0 },
  y:    { type: Number, default: 0 },
})
const emit = defineEmits(['rename', 'delete', 'close'])

const menuEl = ref(null)
const menuStyle = ref({})

watch(() => [props.file, props.x, props.y], async () => {
  if (!props.file) return
  await nextTick()
  if (!menuEl.value) return
  const vw = window.innerWidth, vh = window.innerHeight
  const w = menuEl.value.offsetWidth || 160
  const h = menuEl.value.offsetHeight || 120
  const x = props.x + w > vw - 8 ? props.x - w : props.x
  const y = props.y + h > vh - 8 ? props.y - h : props.y
  menuStyle.value = { top: `${Math.max(8, y)}px`, left: `${Math.max(8, x)}px` }
}, { immediate: true })

function onPD(e) {
  if (!props.file) return
  if (menuEl.value?.contains(e.target)) return
  emit('close')
}
function onKey(e) { if (e.key === 'Escape' && props.file) emit('close') }
onMounted(() => {
  document.addEventListener('pointerdown', onPD, true)
  document.addEventListener('keydown', onKey)
})
onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', onPD, true)
  document.removeEventListener('keydown', onKey)
})
</script>

<style scoped>
.fc-menu {
  position: fixed;
  z-index: var(--z-dropdown);
  min-width: 160px;
  padding: 4px;
  background: var(--overlay);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--overlay-shadow);
}
.fc-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  height: 30px;
  padding: 0 8px;
  border-radius: var(--radius-sm);
  font-size: 12.5px;
  font-weight: 500;
  color: var(--foreground);
  text-align: left;
  cursor: pointer;
  transition: background-color var(--duration-fast) var(--ease-out);
}
.fc-item:hover { background: var(--surface-hover); }
.fc-item--danger { color: var(--danger); }
.fc-item--danger:hover { background: var(--danger-soft); }
.fc-sep { height: 1px; margin: 4px 6px; background: var(--separator); }
</style>
