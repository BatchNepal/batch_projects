<template>
  <slot name="trigger" :open="open" :show="show" :hide="hide" />
  <Teleport to="body">
    <Transition name="adfade">
      <div v-if="open" class="fixed inset-0 z-modal" style="background:var(--backdrop)" @click="hide" />
    </Transition>
    <Transition name="adzoom">
      <div v-if="open" class="fixed inset-0 z-modal flex items-center justify-center p-4 pointer-events-none">
        <div class="relative pointer-events-auto bg-overlay shadow-overlay rounded-xl w-full max-w-sm p-5 flex flex-col gap-4 outline-none" @click.stop>
          <slot />
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, watch, onBeforeUnmount } from 'vue'

const open = ref(false)
function show() { open.value = true }
function hide() { open.value = false }
defineExpose({ open, show, hide })

function onKey(e) { if (e.key === 'Escape' && open.value) hide() }
watch(open, (v) => {
  document.body.style.overflow = v ? 'hidden' : ''
  v ? document.addEventListener('keydown', onKey) : document.removeEventListener('keydown', onKey)
})
onBeforeUnmount(() => { document.body.style.overflow = ''; document.removeEventListener('keydown', onKey) })
</script>

<style scoped>
.adfade-enter-active { transition: opacity var(--duration-base) var(--ease-out); }
.adfade-leave-active { transition: opacity var(--duration-fast) var(--ease-in); }
.adfade-enter-from, .adfade-leave-to { opacity: 0; }
.adzoom-enter-active { transition: opacity var(--duration-modal) var(--ease-out), transform var(--duration-modal) var(--ease-smooth); }
.adzoom-leave-active { transition: opacity var(--duration-base) var(--ease-in), transform var(--duration-base) var(--ease-in); }
.adzoom-enter-from   { opacity: 0; transform: scale(0.95); }
.adzoom-leave-to     { opacity: 0; transform: scale(0.95); }
</style>
