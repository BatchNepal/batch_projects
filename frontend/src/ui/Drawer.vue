<template>
  <Teleport to="body">
    <Transition name="drfade">
      <div v-if="open" class="bp-overlay fixed inset-0 z-modal" style="background:var(--backdrop)" @click="isDismissable && emit('update:open', false)" />
    </Transition>
    <Transition :name="placement === 'left' ? 'drslide-left' : 'drslide-right'">
      <div
        v-if="open"
        :class="cn(
          'bp-overlay fixed z-modal top-0 bottom-0 bg-overlay shadow-overlay flex flex-col overflow-hidden outline-none',
          placement === 'left' ? 'left-0' : 'right-0',
          SIZE[size] ?? SIZE.md,
          $attrs.class,
        )"
        @click.stop
      >
        <slot />
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { watch, onBeforeUnmount } from 'vue'
import { cn } from '@/lib/utils'

defineOptions({ inheritAttrs: false })

const props = defineProps({
  open:          { type: Boolean, default: false },
  placement:     { type: String,  default: 'right' }, // right | left
  size:          { type: String,  default: 'md' },    // sm | md | lg | xl
  isDismissable: { type: Boolean, default: true },
})
const emit = defineEmits(['update:open'])

const SIZE = { sm: 'w-80', md: 'w-[420px] max-w-[90vw]', lg: 'w-[540px] max-w-[90vw]', xl: 'w-[680px] max-w-[95vw]' }

function onKey(e) { if (e.key === 'Escape' && props.open) emit('update:open', false) }
watch(() => props.open, (v) => {
  document.body.style.overflow = v ? 'hidden' : ''
  v ? document.addEventListener('keydown', onKey) : document.removeEventListener('keydown', onKey)
})
onBeforeUnmount(() => { document.body.style.overflow = ''; document.removeEventListener('keydown', onKey) })
</script>

<style scoped>
.drfade-enter-active { transition: opacity var(--duration-base) var(--ease-out); }
.drfade-leave-active { transition: opacity var(--duration-fast) var(--ease-in); }
.drfade-enter-from, .drfade-leave-to { opacity: 0; }

.drslide-right-enter-active { transition: transform var(--duration-modal) var(--ease-smooth); }
.drslide-right-leave-active { transition: transform var(--duration-base) var(--ease-in); }
.drslide-right-enter-from, .drslide-right-leave-to { transform: translateX(100%); }

.drslide-left-enter-active { transition: transform var(--duration-modal) var(--ease-smooth); }
.drslide-left-leave-active { transition: transform var(--duration-base) var(--ease-in); }
.drslide-left-enter-from, .drslide-left-leave-to { transform: translateX(-100%); }
</style>
