<template>
  <div class="max-w-xl mx-auto px-6 py-12 space-y-5">
    <div class="mb-8">
      <h1 class="text-xl font-semibold text-foreground mb-2">Create your first project</h1>
      <p class="text-sm text-muted">You can add more detail after setup.</p>
    </div>

    <!-- Project name -->
    <Input
      label="Project name"
      isRequired
      :modelValue="modelValue.name"
      @update:modelValue="onNameInput"
      placeholder="e.g. Company Website"
      size="sm"
    />

    <!-- Project key -->
    <div>
      <div class="flex items-center gap-1 mb-1.5">
        <label class="text-[13px] font-medium leading-none text-foreground">
          Key <span class="text-danger">*</span>
        </label>
        <span v-if="autoKey" class="px-1 py-0.5 text-[10px] bg-default text-muted rounded-sm">auto</span>
      </div>
      <Input
        :modelValue="modelValue.key"
        @focus="autoKey = false"
        @update:modelValue="onKeyInput"
        placeholder="CWEB"
        maxlength="6"
        size="sm"
        :fullWidth="false"
        class="w-32 font-mono uppercase"
      />
      <p v-if="modelValue.key" class="mt-1 text-xs text-muted">
        {{ taskWord }} prefix: <span class="font-mono font-medium text-foreground">{{ modelValue.key }}-1</span>
      </p>
    </div>

    <!-- Project type -->
    <div>
      <label class="block text-xs font-semibold text-muted uppercase tracking-wide mb-2">Project type</label>
      <div class="grid grid-cols-4 gap-2">
        <button
          v-for="t in PROJECT_TYPES"
          :key="t.id"
          type="button"
          @click="updateField('type', t.id)"
          :class="[
            'flex flex-col items-center gap-1 px-2 py-2.5 rounded-md border-2 text-center transition-all',
            modelValue.type === t.id
              ? 'bg-overlay border-accent shadow-xs'
              : 'bg-surface-secondary border-border hover:bg-surface-hover',
          ]"
        >
          <component :is="t.icon" :size="16" :stroke-width="1.5"
            :class="modelValue.type === t.id ? 'text-accent' : 'text-muted'" />
          <span class="text-xs font-semibold" :class="modelValue.type === t.id ? 'text-foreground' : 'text-muted'">{{ t.label }}</span>
        </button>
      </div>
    </div>

    <!-- a billable type (from the type picker above, or from
         Step 3's template pre-selecting one) has no home for a client
         without this: create_project throws "Client is required for
         billable projects" if it's ever sent a billable type with none. -->
    <BillingFields
      v-if="modelValue.type !== 'internal'"
      :type="modelValue.type"
      :modelValue="modelValue.billing"
      @update:modelValue="v => updateField('billing', v)"
    />
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { PROJECT_TYPES } from '@/constants/project-types'
import { getTaskWord } from '@/constants/project-templates'
import BillingFields from '@/components/create-project/BillingFields.vue'
import { Input } from '@/ui'

const props = defineProps({
  modelValue: { type: Object, required: true },
  template:   { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue'])

const autoKey = ref(true)
const taskWord = computed(() => getTaskWord(props.template))

function updateField(field, value) {
  emit('update:modelValue', { ...props.modelValue, [field]: value })
}

function onNameInput(name) {
  updateField('name', name)
  if (!autoKey.value) return
  const words = name.trim().split(/\s+/).filter(Boolean)
  if (!words.length) { updateField('key', ''); return }
  const key = words.length === 1
    ? words[0].substring(0, 5).toUpperCase().replace(/[^A-Z0-9]/g, '')
    : words.map(w => w[0]).join('').toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 6)
  updateField('key', key)
}

function onKeyInput(val) {
  updateField('key', val.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 6))
}
</script>
