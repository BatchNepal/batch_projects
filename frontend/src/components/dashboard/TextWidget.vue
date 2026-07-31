<template>
  <div class="tw">
    <div v-if="!editing" class="tw-view" @dblclick="startEdit">
      <p v-if="widget.title" class="tw-title">{{ widget.title }}</p>
      <div v-if="text" class="tw-body">{{ text }}</div>
      <div v-else class="tw-placeholder">Double-click to add a note…</div>
    </div>
    <div v-else class="tw-edit">
      <textarea
        ref="area"
        v-model="draft"
        class="tw-area"
        placeholder="Write a note, annotation or description…"
        @keydown.esc="cancelEdit"
        @keydown.ctrl.enter.prevent="saveEdit"
        @keydown.meta.enter.prevent="saveEdit"
      />
      <div class="tw-edit-foot">
        <span class="tw-hint">Ctrl+Enter to save · Esc to cancel</span>
        <div class="flex gap-1">
          <button class="tw-btn tw-btn-ghost" @click="cancelEdit">Cancel</button>
          <button class="tw-btn tw-btn-primary" @click="saveEdit">Save</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick } from 'vue'

const props = defineProps({
  widget: { type: Object, required: true },
})

const emit = defineEmits(['text-change'])

const editing = ref(false)
const draft   = ref('')
const area    = ref(null)

const text = computed(() => props.widget.text || '')

async function startEdit() {
  draft.value = text.value
  editing.value = true
  await nextTick()
  area.value?.focus()
}

function saveEdit() {
  emit('text-change', draft.value)
  editing.value = false
}

function cancelEdit() {
  editing.value = false
}
</script>

<style scoped>
.tw { height: 100%; display: flex; flex-direction: column; }

.tw-view {
  flex: 1; min-height: 0; overflow-y: auto;
  padding: 2px 0;
  cursor: default;
}
.tw-view:hover .tw-placeholder { opacity: 0.7; }

.tw-title { font-size: 13px; font-weight: 600; color: var(--foreground); margin-bottom: 8px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tw-body { font-size: 13px; color: var(--foreground); line-height: 1.7; white-space: pre-wrap; word-break: break-word; }
.tw-placeholder { font-size: 13px; color: var(--border); line-height: 1.7; user-select: none; }

.tw-edit { flex: 1; min-height: 0; display: flex; flex-direction: column; border: 1px solid var(--accent); border-radius: 8px; overflow: hidden; background: var(--surface-secondary); }
.tw-area {
  flex: 1; min-height: 0; resize: none; outline: none; border: none;
  padding: 10px 12px; font-size: 13px; color: var(--foreground); background: transparent;
  line-height: 1.7; font-family: inherit;
}
.tw-edit-foot { flex-shrink: 0; display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 6px 10px; border-top: 1px solid var(--border); background: var(--surface-secondary); }
.tw-hint { font-size: 11px; color: var(--muted); }
.tw-btn { height: 26px; padding: 0 12px; border-radius: 6px; font-size: 12px; font-weight: 600; border: 1px solid transparent; cursor: pointer; transition: all .12s; }
.tw-btn-ghost   { background: transparent; color: var(--muted); border-color: var(--border); }
.tw-btn-ghost:hover { background: var(--surface-secondary); }
.tw-btn-primary { background: var(--accent); color: var(--accent-foreground); }
.tw-btn-primary:hover { opacity: .88; }
</style>
