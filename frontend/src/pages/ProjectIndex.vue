<template>
  <div class="flex items-center justify-center h-full">
    <Spinner class="w-5 h-5 text-primary-400" />
  </div>
</template>

<script setup>
// Resolves /workspace/:key → the project's configured default view.
// Lives as a component (not a router redirect) because the project list may
// not be loaded yet on a cold/direct navigation, and we need to await it.
import { onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useProjectStore } from '@/stores/project'
import Spinner from '@/ui/Spinner.vue'

const route  = useRoute()
const router = useRouter()
const store  = useProjectStore()

onMounted(async () => {
  const key = route.params.key
  if (!store.projects.length) {
    try { await store.fetchProjects() } catch {}
  }
  const p = store.projects.find(p => p.key === key)
  let view = p?.default_view || 'summary'
  // Guard: never land on a view the project doesn't expose.
  const enabled = Array.isArray(p?.enabled_views) ? p.enabled_views : []
  if (view !== 'summary' && view !== 'files' && enabled.length && !enabled.includes(view)) {
    view = 'summary'
  }
  router.replace(`/workspace/${key}/${view}`)
})
</script>
