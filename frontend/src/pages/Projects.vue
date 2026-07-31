<template>
  <div class="max-w-4xl mx-auto px-6 py-8">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-foreground">Projects</h1>
      <Button v-if="store.projects.length" color="primary" size="sm" @click="$router.push(`/workspace/new-project`)">
        New project
      </Button>
    </div>

    <!-- Loading: card skeletons mirror the project rows -->
    <div v-if="store.loading" class="space-y-3">
      <div v-for="r in 4" :key="'sk' + r"
        class="flex items-center gap-4 bg-overlay border rounded-lg px-5 py-4">
        <Skeleton class="w-10 h-10 rounded-lg shrink-0" />
        <div class="flex-1 min-w-0 space-y-2">
          <Skeleton class="h-3" :style="{ width: (30 + (r % 3) * 14) + '%' }" />
          <Skeleton class="h-2.5" :style="{ width: (18 + (r % 4) * 8) + '%' }" />
        </div>
        <Skeleton class="h-5 w-14 rounded-full shrink-0" />
      </div>
    </div>

    <div v-else class="space-y-3">
      <router-link v-for="p in store.projects" :key="p.name" :to="store.projectLanding(p)"
        class="flex items-center gap-4 bg-overlay border border-border rounded-lg px-5 py-4 hover:shadow-md transition-shadow">
        <div
          class="w-10 h-10 rounded-lg bg-brand flex items-center justify-center text-white font-bold text-sm shrink-0">
          {{ p.key }}
        </div>
        <div class="flex-1 min-w-0">
          <div class="font-semibold text-foreground">{{ p.project_name }}</div>
          <div class="text-sm text-muted">
            {{ p.open_count }} open tasks · {{ p.issue_count }} total
          </div>
        </div>
        <span :class="p.status === 'Active' ? 'bg-success-soft text-success-soft-foreground' : 'bg-default text-muted'"
          class="px-2 py-0.5 text-xs font-medium rounded-full">
          {{ p.status }}
        </span>
      </router-link>

      <EmptyState
        v-if="!store.projects.length"
        :icon="FolderPlus"
        title="No projects yet"
        description="Create your first project to start tracking work."
      >
        <Button color="primary" size="sm" @click="$router.push(`/workspace/new-project`)">
          Create project
        </Button>
      </EmptyState>
    </div>
  </div>
</template>

<script setup>
import { onMounted } from "vue";
import { FolderPlus } from "lucide-vue-next";
import { Button, Skeleton, EmptyState } from "@/ui";
import { useProjectStore } from "@/stores/project";

const store = useProjectStore();
onMounted(() => store.fetchProjects());
</script>
