<template>
  <div class="flex flex-col items-center justify-center h-full gap-3 text-[--muted]">
    <svg class="w-6 h-6 animate-spin" fill="none" viewBox="0 0 24 24">
      <circle class="opacity-20" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3"/>
      <path class="opacity-80" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
    </svg>
    <span class="text-sm">Opening reports…</span>
  </div>
</template>

<script setup>
/**
 * Legacy per-project Reports route. The project-level Reports tab has been
 * removed in favour of the unified Reports hub, where reports are scoped by
 * project / milestone / period. Anyone landing here (old bookmark) is sent to
 * the hub.
 */
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
onMounted(() => router.replace('/workspace/reports/dashboard'))
</script>
