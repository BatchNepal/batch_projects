<template>
  <Teleport to="body">
    <Transition name="sv-bg">
      <div
        v-if="modelValue"
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
        style="background:rgba(0,0,0,0.28)"
        @mousedown.self="$emit('update:modelValue', false)"
      >
        <Transition name="sv-modal" appear>
          <div
            v-if="modelValue"
            class="bg-overlay rounded-xl w-full max-w-sm overflow-hidden"
            style="box-shadow:0 8px 32px rgba(0,0,0,0.12),0 2px 8px rgba(0,0,0,0.08),0 0 0 1px rgba(0,0,0,0.06)"
          >
            <!-- Header -->
            <div class="flex items-center justify-between px-5 py-4">
              <div class="flex items-center gap-2.5">
                <div class="size-7 rounded-lg bg-accent-soft flex items-center justify-center">
                  <Bookmark class="size-3.5 text-accent" />
                </div>
                <span class="text-md font-semibold text-foreground">Save current view</span>
              </div>
              <button
                class="size-7 flex items-center justify-center rounded-md text-muted hover:bg-surface-secondary hover:text-muted transition-colors"
                @click="$emit('update:modelValue', false)"
              >
                <X class="size-4" />
              </button>
            </div>

            <div class="h-px bg-border mx-5" />

            <!-- Body -->
            <div class="px-5 py-4 space-y-3.5">
              <div>
                <label class="block text-xs font-semibold text-muted uppercase tracking-wider mb-1.5">View name</label>
                <input
                  ref="inputRef"
                  v-model="name"
                  class="w-full h-9 px-3 text-base text-foreground bg-[var(--surface-secondary)] border border-transparent rounded-lg outline-none transition-all
                    hover:bg-[var(--surface-secondary)] focus:bg-overlay focus:border-border-secondary focus:ring-2 focus:ring-accent-soft"
                  placeholder="e.g. My open bugs, Sprint 3 work…"
                  maxlength="60"
                  @keydown.enter.prevent="save"
                  @keydown.escape.prevent="$emit('update:modelValue', false)"
                />
              </div>

              <div>
                <p class="text-xs font-semibold text-muted uppercase tracking-wider mb-2">Saving</p>
                <div class="flex flex-wrap gap-1.5">
                  <span class="sv-pill sv-pill-blue">
                    <LayoutGrid class="size-3" />{{ viewTypeLabel }}
                  </span>
                  <span class="sv-pill" :class="groupBy !== 'status' ? 'sv-pill-violet' : 'sv-pill-gray'">
                    <SlidersHorizontal class="size-3" />Group: {{ groupBy }}
                  </span>
                  <span v-if="sortBy !== 'board_order'" class="sv-pill sv-pill-violet">
                    <ArrowUpDown class="size-3" />Sort: {{ sortLabel }}
                  </span>
                  <span v-if="sprintFilter === 'active_sprint'" class="sv-pill sv-pill-emerald">
                    <Play class="size-3" />Active sprint
                  </span>
                  <span v-if="filters.filterAssignee" class="sv-pill sv-pill-gray">👤 {{ filters.filterAssignee.split(' ')[0] }}</span>
                  <span v-if="filters.filterPriority" class="sv-pill sv-pill-gray">⚑ {{ filters.filterPriority }}</span>
                  <span v-if="filters.filterType"     class="sv-pill sv-pill-gray">◈ {{ filters.filterType }}</span>
                  <span v-if="filters.filterLabel"    class="sv-pill sv-pill-gray">🏷 {{ filters.filterLabel }}</span>
                </div>
              </div>
            </div>

            <!-- Footer -->
            <div class="flex items-center justify-end gap-2 px-5 pb-4">
              <button
                class="h-8 px-4 text-base font-medium text-muted rounded-full border border-border bg-overlay hover:bg-surface-secondary transition-colors"
                @click="$emit('update:modelValue', false)"
              >
                Cancel
              </button>
              <button
                :disabled="!name.trim()"
                class="h-8 px-4 text-base font-semibold text-white bg-accent rounded-full hover:bg-accent-hover active:scale-[0.97] transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                @click="save"
              >
                Save view
              </button>
            </div>
          </div>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { Bookmark, X, LayoutGrid, SlidersHorizontal, ArrowUpDown, Play } from 'lucide-vue-next'

const props = defineProps({
  modelValue: Boolean,
  viewType:     { type: String, default: 'board' },
  groupBy:      { type: String, default: 'status' },
  sortBy:       { type: String, default: 'board_order' },
  sprintFilter: { type: String, default: 'all' },
  filters:      { type: Object, default: () => ({}) },
})
const emit = defineEmits(['update:modelValue', 'save'])

const name     = ref('')
const inputRef = ref(null)

const viewTypeLabel = computed(() => props.viewType === 'list' ? 'List view' : 'Board view')

const SORT_LABELS = {
  board_order: 'Manual', priority: 'Priority', due_date: 'Due date',
  title: 'Title', creation: 'Created',
}
const sortLabel = computed(() => SORT_LABELS[props.sortBy] || props.sortBy)

watch(() => props.modelValue, (v) => {
  if (v) {
    name.value = ''
    nextTick(() => inputRef.value?.focus())
  }
})

function save() {
  if (!name.value.trim()) return
  emit('save', name.value.trim())
  emit('update:modelValue', false)
}
</script>

<style scoped>
.sv-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  font-size:var(--text-sm);
  font-weight: 600;
  white-space: nowrap;
}
.sv-pill-blue    { background: var(--accent-soft); color: var(--accent-soft-foreground); }
.sv-pill-violet  { background: #F5F3FF; color: #7C3AED; }
.sv-pill-emerald { background: var(--success-soft); color: var(--success-soft-foreground); }
.sv-pill-gray    { background: var(--surface-secondary); color: var(--muted); }

.sv-bg-enter-active, .sv-bg-leave-active { transition: opacity 0.15s ease; }
.sv-bg-enter-from, .sv-bg-leave-to { opacity: 0; }

.sv-modal-enter-active { transition: opacity 0.15s ease, transform 0.15s cubic-bezier(0.16,1,0.3,1); }
.sv-modal-leave-active { transition: opacity 0.1s ease; }
.sv-modal-enter-from   { opacity: 0; transform: scale(0.96) translateY(6px); }
.sv-modal-leave-to     { opacity: 0; }
</style>
