<template>
  <div class="border-b border-separator last:border-b-0">
    <button
      type="button"
      class="flex items-center justify-between w-full py-2.5 px-1 text-sm font-medium text-foreground hover:bg-default rounded-md transition-colors duration-90 outline-none focus-visible:shadow-focus"
      @click="open = !open"
    >
      <slot name="title" />
      <svg
        class="shrink-0 text-muted transition-transform duration-180"
        :class="open ? 'rotate-180' : ''"
        width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"
      >
        <path d="M6 9l6 6 6-6"/>
      </svg>
    </button>
    <div v-if="open" class="overflow-hidden pb-3 px-1">
      <div class="text-sm text-muted leading-relaxed"><slot /></div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
const open = ref(false)
</script>
