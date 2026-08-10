<template>
  <div :class="cn('flex flex-col gap-1.5', fullWidth ? 'w-full' : 'w-fit', $attrs.class)">
    <label v-if="label" :for="inputId" :class="labelCls">
      {{ label }}<span v-if="isRequired" class="text-danger ml-0.5" aria-hidden="true">*</span>
    </label>

    <div :class="wrapperCls">
      <span v-if="$slots.startContent" class="field-adorn left">
        <slot name="startContent" />
      </span>

      <input
        :id="inputId"
        v-bind="inputAttrs"
        :type="type"
        :value="modelValue"
        :placeholder="placeholder"
        :disabled="isDisabled"
        :readonly="isReadOnly"
        :required="isRequired"
        :class="inputCls"
        @input="emit('update:modelValue', $event.target.value)"
        @focus="focused = true"
        @blur="focused = false"
      />

      <button
        v-if="isClearable && modelValue"
        type="button"
        tabindex="-1"
        class="field-adorn right cursor-pointer text-muted hover:text-foreground transition-colors"
        @click="emit('update:modelValue', ''); emit('clear')"
        aria-label="Clear"
      >
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M18 6L6 18M6 6l12 12"/>
        </svg>
      </button>

      <span v-if="$slots.endContent" class="field-adorn right">
        <slot name="endContent" />
      </span>
    </div>

    <p v-if="isInvalid && errorMessage" class="text-sm text-danger leading-snug">{{ errorMessage }}</p>
    <p v-else-if="description" class="text-sm text-muted leading-snug">{{ description }}</p>
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
  type:         { type: String,  default: 'text' },
  size:         { type: String,  default: 'md' },      // sm | md | lg
  variant:      { type: String,  default: 'default' }, // default | filled
  isDisabled:   { type: Boolean, default: false },
  isRequired:   { type: Boolean, default: false },
  isReadOnly:   { type: Boolean, default: false },
  isClearable:  { type: Boolean, default: false },
  isInvalid:    { type: Boolean, default: false },
  fullWidth:    { type: Boolean, default: true },
})

const emit = defineEmits(['update:modelValue', 'clear'])
const attrs  = useAttrs()
const focused = ref(false)
const inputId = useId()

const inputAttrs = computed(() => {
  const { class: _, ...rest } = attrs
  return rest
})

// HeroUI v3 field heights (input.css: min-h-9 standard)
const HEIGHT = { sm: 'h-8', md: 'h-9', lg: 'h-10' }
const FONT   = { sm: 'text-base', md: 'text-sm', lg: 'text-sm' }

const wrapperCls = computed(() => cn(
  'hui-field flex items-center w-full',
  HEIGHT[props.size] ?? HEIGHT.md,
  props.isInvalid && 'is-invalid',
  props.isDisabled && 'opacity-45 pointer-events-none',
))

const inputCls = computed(() => cn(
  'flex-1 min-w-0 h-full bg-white outline-none px-3 rounded-[inherit]',
  'placeholder:text-[var(--field-placeholder)] text-foreground',
  FONT[props.size] ?? FONT.md,
  props.isReadOnly && 'cursor-default select-all',
))

const labelCls = computed(() => cn(
  'text-base font-medium leading-none',
  props.isInvalid ? 'text-danger' : 'text-foreground',
))
</script>

<style scoped>
.field-adorn {
  display: flex;
  align-items: center;
  flex-shrink: 0;
  color: var(--muted);
}
.field-adorn.left  { padding-left: 8px; }
.field-adorn.right { padding-right: 8px; }
.field-adorn > :deep(svg) {
  width: 14px;
  height: 14px;
  pointer-events: none;
}
</style>
