<template>
  <div class="shrink-0 flex items-center justify-between gap-3 px-5 py-4 border-b border-separator">
    <div class="min-w-0 flex-1">
      <slot />
    </div>
    <slot name="actions">
      <button
        class="flex items-center justify-center rounded-md text-muted hover:bg-default hover:text-foreground transition-colors outline-none focus-visible:shadow-focus"
        style="width:28px;height:28px"
        @click="$emit('close')"
        aria-label="Close"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M18 6L6 18M6 6l12 12"/>
        </svg>
      </button>
    </slot>
  </div>
</template>
<script setup>
defineEmits(['close'])
</script>
