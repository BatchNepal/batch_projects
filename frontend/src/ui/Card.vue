<template>
  <component
    :is="isPressable ? 'button' : 'div'"
    :class="cn(
      'card relative flex flex-col overflow-hidden',
      VARIANT[variant] ?? VARIANT.default,
      shadow && variant !== 'transparent' && 'shadow-surface',
      bordered && 'border border-border',
      isPressable && 'cursor-pointer outline-none focus-visible:shadow-focus active:scale-[0.99]',
      fullWidth && 'w-full',
      $attrs.class,
    )"
    v-bind="{ ...$attrs, class: undefined }"
    @click="isPressable ? emit('press', $event) : undefined"
  >
    <div v-if="$slots.header || title || description" :class="cn('flex flex-col gap-0.5', noPadding ? '' : 'px-4 pt-4 pb-1')">
      <slot name="header">
        <p v-if="title"       class="text-sm font-semibold text-foreground leading-snug">{{ title }}</p>
        <p v-if="description" class="text-sm text-muted leading-snug">{{ description }}</p>
      </slot>
    </div>

    <div :class="cn('flex flex-1 flex-col', noPadding ? '' : 'px-4', !$slots.header && !title && !description && !noPadding && 'pt-4', !$slots.footer && !noPadding && 'pb-4')">
      <slot />
    </div>

    <div v-if="$slots.footer" :class="cn('flex items-center', noPadding ? '' : 'px-4 pb-4')">
      <slot name="footer" />
    </div>
  </component>
</template>

<script setup>
import { cn } from '@/lib/utils'
defineOptions({ inheritAttrs: false })

const props = defineProps({
  title:       { type: String,  default: '' },
  description: { type: String,  default: '' },
  variant:     { type: String,  default: 'default' },  // default | secondary | tertiary | transparent
  shadow:      { type: Boolean, default: true },
  bordered:    { type: Boolean, default: false },
  noPadding:   { type: Boolean, default: false },
  isPressable: { type: Boolean, default: false },
  fullWidth:   { type: Boolean, default: false },
})
const emit = defineEmits(['press'])

const VARIANT = {
  default:     'bg-surface rounded-lg',
  secondary:   'bg-surface-secondary rounded-lg',
  tertiary:    'bg-surface-tertiary rounded-lg',
  transparent: 'bg-transparent',
}
</script>

<style scoped>
.card {
  transition: transform var(--duration-base) var(--ease-smooth), box-shadow var(--duration-base) var(--ease-out);
}
button.card:active { transition: transform var(--duration-instant) ease-out; }
</style>
