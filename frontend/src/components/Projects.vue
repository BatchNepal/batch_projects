<template>
  <section>
  <div class="max-w-4xl mx-auto px-6 py-8">
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-3xl font-bold text-foreground tracking-tight">All Projects</h1>
        <p class="text-base text-muted mt-0.5">{{ store.projects.length }} project{{ store.projects.length !== 1 ? 's' : '' }}</p>
      </div>
      <button @click="$router.push(`/workspace/new-project`)"
        class="flex items-center gap-2 px-4 py-2 bg-[var(--accent)] text-white text-base font-semibold rounded-lg hover:bg-accent-hover shadow-sm shadow-accent-soft transition-[background-color]">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/></svg>
        New Project
      </button>
    </div>

    <div v-if="store.loading" class="text-center py-12 text-muted">Loading...</div>

    <div v-else class="grid grid-cols-1 gap-3">
      <router-link
        v-for="p in store.projects" :key="p.name"
        :to="store.projectLanding(p)"
        class="flex items-center gap-4 bg-overlay border border-border rounded-lg px-5 py-4 hover:border-border-secondary hover:shadow-sm transition-[border-color,box-shadow] group"
      >
        <ProjectAvatar :theme="p.theme" :seed="p.key" size="lg" />

        <div class="flex-1 min-w-0">
          <div class="font-semibold text-md text-foreground">{{ p.project_name }}</div>
          <div class="text-sm text-muted mt-0.5">
            {{ p.open_count }} open · {{ p.issue_count }} total
          </div>
        </div>

        <span :class="p.status === 'Active' ? 'bg-success-soft text-success-soft-foreground' : 'bg-surface-secondary text-muted'"
          class="px-2.5 py-0.5 text-xs font-semibold rounded-full shrink-0">
          {{ p.status }}
        </span>

        <svg class="w-4 h-4 text-muted group-hover:text-muted transition-colors shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/>
        </svg>
      </router-link>

      <!-- Empty state -->
      <div v-if="!store.projects.length"
        class="flex flex-col items-center justify-center py-20 text-center">
        <div class="w-16 h-16 rounded-2xl bg-accent-soft flex items-center justify-center mb-4">
          <svg class="w-8 h-8 text-[var(--accent)]" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z"/>
          </svg>
        </div>
        <h3 class="text-xl font-semibold text-foreground mb-1">No projects yet</h3>
        <p class="text-base text-muted mb-6">Create your first project to get started.</p>
        <button @click="$router.push(`/workspace/new-project`)"
          class="flex items-center gap-2 px-5 py-2.5 bg-[var(--accent)] text-white text-base font-semibold rounded-xl hover:bg-accent-hover transition-colors">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/></svg>
          Create Project
        </button>
      </div>
    </div>
  </div>
  </section>
</template>

<script setup>
import { onMounted } from 'vue'
import { useProjectStore } from '@/stores/project'
import ProjectAvatar from '@/ui/ProjectAvatar.vue'

const store = useProjectStore()
onMounted(() => store.fetchProjects())
</script>