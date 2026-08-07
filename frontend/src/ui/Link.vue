<template>
  <component
    :is="to ? RouterLink : 'a'"
    v-bind="linkProps"
    :class="cn(
      'inline-flex items-center gap-1 transition-colors duration-fast rounded-sm',
      'focus-visible:outline-none focus-visible:shadow-focus',
      SIZE[size],
      COLOR[color] ?? COLOR.accent,
      underline === 'always' && 'underline underline-offset-2',
      underline === 'hover'  && 'hover:underline underline-offset-2',
      isBlock    && 'flex w-full',
      isDisabled && 'opacity-45 pointer-events-none',
      $attrs.class,
    )"
    v-bind_extra="{ ...$attrs, class: undefined }"
  >
    <slot />
    <svg v-if="isExternal" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="shrink-0 opacity-70" aria-hidden="true">
      <path d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/>
    </svg>
  </component>
</template>

<script setup>
import { computed, useAttrs } from 'vue'
import { RouterLink } from 'vue-router'
import { cn } from '@/lib/utils'

defineOptions({ inheritAttrs: false })

const props = defineProps({
  href:       { type: String,  default: undefined },
  to:         { default: undefined },
  color:      { type: String,  default: 'accent' }, // accent | foreground | success | warning | danger
  size:       { type: String,  default: 'md' },
  underline:  { type: String,  default: 'hover' },  // none | hover | always
  isExternal: { type: Boolean, default: false },
  isBlock:    { type: Boolean, default: false },
  isDisabled: { type: Boolean, default: false },
})

const attrs = useAttrs()

const linkProps = computed(() => {
  if (props.to) return { to: props.to }
  return { href: props.href, target: props.isExternal ? '_blank' : undefined, rel: props.isExternal ? 'noopener noreferrer' : undefined }
})

const SIZE  = { sm: 'text-xs', md: 'text-sm', lg: 'text-base' }
const COLOR = {
  accent:     'text-accent hover:text-accent-hover',
  foreground: 'text-foreground hover:text-muted',
  success:    'text-success hover:text-success-hover',
  warning:    'text-warning hover:text-warning-hover',
  danger:     'text-danger hover:text-danger-hover',
}
</script>
