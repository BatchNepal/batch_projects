<template>
  <div :class="cn('flex flex-col gap-1.5', fullWidth ? 'w-full' : 'w-fit', $attrs.class)">
    <label v-if="label" :for="id" :class="cn('text-[13px] font-medium leading-none', isInvalid ? 'text-danger' : 'text-foreground')">
      {{ label }}<span v-if="isRequired" class="text-danger ml-0.5" aria-hidden="true">*</span>
    </label>

    <div :class="wrapperCls">
      <textarea
        :id="id"
        v-bind="inputAttrs"
        :value="modelValue"
        :placeholder="placeholder"
        :disabled="isDisabled"
        :readonly="isReadOnly"
        :rows="rows"
        class="flex-1 min-w-0 bg-transparent outline-none text-sm text-foreground placeholder:text-[var(--field-placeholder)] px-2.5 py-2 resize-none w-full disabled:cursor-not-allowed leading-normal"
        @input="emit('update:modelValue', $event.target.value)"
        @focus="focused = true"
        @blur="focused = false"
      />
    </div>

    <p v-if="isInvalid && errorMessage" class="text-[12px] text-danger leading-snug">{{ errorMessage }}</p>
    <p v-else-if="description" class="text-[12px] text-muted leading-snug">{{ description }}</p>
  </div>
</template>

<script setup>
import { ref, computed, useAttrs, useId } from 'vue'
import { cn } from '@/lib/utils'

defineOptions({ inheritAttrs: false })

const props = defineProps({
  modelValue:   { default: '' },
  label:        { type: String,  default: '' },
  description:  { type: String,  default: '' },
  errorMessage: { type: String,  default: '' },
  placeholder:  { type: String,  default: '' },
  rows:         { type: Number,  default: 3 },
  isDisabled:   { type: Boolean, default: false },
  isRequired:   { type: Boolean, default: false },
  isReadOnly:   { type: Boolean, default: false },
  isInvalid:    { type: Boolean, default: false },
  fullWidth:    { type: Boolean, default: true },
})

const emit = defineEmits(['update:modelValue'])
const attrs   = useAttrs()
const focused = ref(false)
const id      = useId()

const inputAttrs = computed(() => { const { class: _, ...r } = attrs; return r })

const wrapperCls = computed(() => cn(
  'hui-field flex w-full',
  props.isInvalid && 'is-invalid',
  props.isDisabled && 'opacity-45 pointer-events-none',
))
</script>
