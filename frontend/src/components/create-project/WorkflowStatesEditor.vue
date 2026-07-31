<template>
  <div class="space-y-1">
    <draggable
      v-model="states"
      item-key="name"
      handle=".drag-handle"
      ghost-class="opacity-40"
      animation="150"
      @end="emitUpdate"
    >
      <template #item="{ element, index }">
        <div class="flex items-center gap-2 px-3 py-2 bg-overlay border border-border rounded-md group hover:border-border-secondary transition-colors mb-1 shadow-sm">
          <!-- Drag handle -->
          <button type="button" class="drag-handle cursor-grab text-muted hover:text-muted transition-colors shrink-0">
            <svg width="10" height="14" viewBox="0 0 10 14" fill="currentColor">
              <circle cx="3" cy="3" r="1.5"/><circle cx="7" cy="3" r="1.5"/>
              <circle cx="3" cy="7" r="1.5"/><circle cx="7" cy="7" r="1.5"/>
              <circle cx="3" cy="11" r="1.5"/><circle cx="7" cy="11" r="1.5"/>
            </svg>
          </button>

          <!-- Color dot -->
          <button
            type="button"
            @click="cycleColor(index)"
            class="w-4 h-4 rounded-full shrink-0 border-[3px] border-white shadow-sm hover:scale-110 transition-transform"
            :style="{ backgroundColor: element.color }"
          />

          <!-- Name input -->
          <input
            v-model="states[index].name"
            class="flex-1 text-sm font-medium text-foreground bg-transparent outline-none border-none focus:bg-surface-secondary rounded px-1.5 py-1 -mx-1.5 transition-colors"
            placeholder="Status name…"
            @input="emitUpdate"
          />

          <!-- Category select -->
          <div class="w-32 shrink-0">
            <Select
              v-model="states[index].category"
              size="sm"
              @update:modelValue="emitUpdate"
              :class="getCategoryClasses(element.category)"
              class="border-0 shadow-none"
            >
              <SelectItem value="unstarted" label="Unstarted">
                 <div class="flex items-center gap-1.5 text-muted"><span class="w-2 h-2 rounded-full bg-muted"></span>Unstarted</div>
              </SelectItem>
              <SelectItem value="started" label="Started">
                 <div class="flex items-center gap-1.5 text-accent"><span class="w-2 h-2 rounded-full bg-accent"></span>Started</div>
              </SelectItem>
              <SelectItem value="completed" label="Completed">
                 <div class="flex items-center gap-1.5 text-success"><span class="w-2 h-2 rounded-full bg-success"></span>Completed</div>
              </SelectItem>
              <SelectItem value="cancelled" label="Cancelled">
                 <div class="flex items-center gap-1.5 text-danger"><span class="w-2 h-2 rounded-full bg-danger"></span>Cancelled</div>
              </SelectItem>
            </Select>
          </div>

          <!-- Remove -->
          <button
            v-if="states.length > 1"
            type="button"
            @click="removeState(index)"
            class="opacity-0 group-hover:opacity-100 p-1.5 rounded-md text-muted hover:text-danger hover:bg-danger-soft transition-colors shrink-0 ml-1"
          >
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
            </svg>
          </button>
        </div>
      </template>
    </draggable>

    <button
      type="button"
      @click="addState"
      class="flex items-center gap-1.5 text-xs font-semibold text-muted hover:text-foreground bg-surface-secondary hover:bg-default border border-transparent hover:border-border transition-colors px-3 py-2 rounded-md mt-2"
    >
      <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="3">
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/>
      </svg>
      Add status
    </button>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import draggable from 'vuedraggable'
import { STATUS_COLOR_PALETTE } from '@/constants/workflow-presets'
import Select from '@/ui/Select.vue'
import SelectItem from '@/ui/SelectItem.vue'

const props = defineProps({
  modelValue: { type: Array, required: true },
})
const emit = defineEmits(['update:modelValue'])

const states = ref(props.modelValue.map(s => ({ ...s })))

let _emitting = false
watch(() => props.modelValue, (v) => {
  if (_emitting) return
  states.value = v.map(s => ({ ...s }))
}, { deep: true })

function emitUpdate() {
  _emitting = true
  emit('update:modelValue', states.value.map(s => ({ ...s })))
  Promise.resolve().then(() => { _emitting = false })
}

function cycleColor(idx) {
  const current = states.value[idx].color
  const i = STATUS_COLOR_PALETTE.indexOf(current)
  states.value[idx].color = STATUS_COLOR_PALETTE[(i + 1) % STATUS_COLOR_PALETTE.length]
  emitUpdate()
}

function addState() {
  states.value.push({ name: '', color: '#10b981', category: 'started' })
  emitUpdate()
}

function removeState(idx) {
  if (states.value.length > 1) {
    states.value.splice(idx, 1)
    emitUpdate()
  }
}

function getCategoryClasses(category) {
  switch (category) {
    case 'started': return '[&>button]:bg-accent-soft [&>button]:!text-accent-soft-foreground font-semibold'
    case 'completed': return '[&>button]:bg-success-soft [&>button]:!text-success-soft-foreground font-semibold'
    case 'cancelled': return '[&>button]:bg-danger-soft [&>button]:!text-danger-soft-foreground font-semibold'
    default: return '[&>button]:bg-default [&>button]:!text-foreground font-semibold'
  }
}
</script>
