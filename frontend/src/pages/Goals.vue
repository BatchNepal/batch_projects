<template>
  <div class="goals-root">
    <div class="goals-header">
      <h1 class="text-[20px] font-semibold text-foreground">Goals</h1>
      <Button v-if="ent.loaded && ent.can('goals')" size="sm" color="primary" @click="showCreate = true">
        <Plus class="size-3.5 mr-1" /> New Goal
      </Button>
    </div>

    <!-- Locked banner (only after entitlements hydrate — avoids false flash on cold nav) -->
    <div v-if="ent.loaded && !ent.can('goals')" class="goals-lock">
      <Lock class="size-5 text-primary" />
      <div>
        <p class="text-[14px] font-semibold text-foreground">Goals require the {{ ent.requiredPlanFor('goals') }} plan</p>
        <p class="text-[13px] text-muted mt-1">Align epics across projects with OKR-style goal tracking.</p>
      </div>
    </div>

    <!-- Loading -->
    <div v-else-if="loading" class="grid grid-cols-3 gap-4">
      <Skeleton v-for="i in 3" :key="i" class="h-[120px] rounded-lg" />
    </div>

    <!-- Goals list -->
    <div v-else class="goals-grid">
      <div v-for="g in goals" :key="g.name"
           class="goal-card" :style="{ borderLeftColor: g.color || '#6366f1' }">
        <div class="flex items-center gap-2 mb-2">
          <span class="text-[13px] font-semibold text-foreground truncate">{{ g.title }}</span>
          <span class="goal-status" :class="statusClass(g.status)">{{ g.status }}</span>
        </div>
        <div class="flex items-center gap-3 text-[11.5px] text-muted mb-3">
          <span v-if="g.start_date">{{ g.start_date }}</span>
          <span v-if="g.end_date">→ {{ g.end_date }}</span>
          <span v-if="g.owner">{{ g.owner }}</span>
        </div>
        <div class="mb-2">
          <div class="flex items-center justify-between text-[12px]">
            <span class="text-muted">Progress</span>
            <span class="font-semibold text-foreground">{{ g.progress }}%</span>
          </div>
          <div class="goal-bar">
            <div class="goal-bar-fill" :style="{ width: Math.min(g.progress, 100) + '%', background: g.color || '#6366f1' }" />
          </div>
        </div>
        <div v-if="g.linked_epics?.length" class="flex flex-wrap gap-1">
          <span v-for="e in g.linked_epics" :key="e" class="text-[11px] px-1.5 py-0.5 rounded bg-overlay text-muted font-mono">{{ e }}</span>
        </div>
        <p v-else class="text-[11px] text-muted">No epics linked</p>
      </div>
    </div>
    <!-- The "New Goal" button already lives in the
         page header above, so no action slot needed here. -->
    <EmptyState v-if="!loading && !goals.length" :icon="Target" title="No goals yet"
      description="Create one to start tracking OKRs across projects." />

    <!-- Create modal -->
    <Modal :open="showCreate" @update:open="v => !v && (showCreate = false)" size="sm" hideCloseButton>
      <ModalHeader class="px-5 pt-5">
        <p class="text-[15px] font-semibold text-foreground">New Goal</p>
      </ModalHeader>
      <ModalBody class="px-5 py-4 space-y-3">
        <Input v-model="newTitle" label="Title" placeholder="e.g. Q3 Revenue Growth" />
        <Input v-model="newColor" label="Color" placeholder="#6366f1" />
      </ModalBody>
      <ModalFooter class="px-5 pb-5 justify-end gap-2">
        <Button size="sm" variant="ghost" @click="showCreate=false">Cancel</Button>
        <Button size="sm" color="primary" :isLoading="creating" :disabled="!newTitle.trim()" @click="doCreate">Create</Button>
      </ModalFooter>
    </Modal>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { useEntitlementsStore } from '@/stores/entitlements'
import { listGoals, createGoal } from '@/utils/api'
import { toast } from 'vue-sonner'
import { Button, Skeleton, Input, EmptyState, Modal, ModalHeader, ModalBody, ModalFooter } from '@/ui'
import { Lock, Plus, Target } from 'lucide-vue-next'

const ent = useEntitlementsStore()
const loading = ref(true)
const goals = ref([])
const showCreate = ref(false)
const newTitle = ref('')
const newColor = ref('#6366f1')
const creating = ref(false)

function statusClass(s) {
  return {
    'On Track': 'goal-ok', 'At Risk': 'goal-warn', 'Off Track': 'goal-bad', 'Done': 'goal-done'
  }[s] || ''
}

async function load() {
  // Wait for entitlements bootstrap — on cold nav the store may not
  // have hydrated yet, and can('goals') would false-negative.
  if (!ent.loaded) {
    await new Promise(resolve => {
      const stop = watch(() => ent.loaded, v => { if (v) { stop(); resolve() } })
    })
  }
  if (!ent.can('goals')) { loading.value = false; return }
  loading.value = true
  try { goals.value = await listGoals() }
  catch (e) { toast.error(e.message || 'Failed to load goals') }
  finally { loading.value = false }
}

async function doCreate() {
  if (!newTitle.value.trim() || creating.value) return
  creating.value = true
  try {
    await createGoal({ title: newTitle.value.trim(), color: newColor.value || '#6366f1' })
    showCreate.value = false
    newTitle.value = ''
    toast.success('Goal created')
    await load()
  } catch (e) { toast.error(e.message || 'Failed') }
  finally { creating.value = false }
}

onMounted(load)
</script>

<style scoped>
.goals-root { padding: 24px 28px 40px; max-width: 960px; }
.goals-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; }
.goals-lock { display: flex; align-items: flex-start; gap: 16px; padding: 20px; border-radius: 10px; border: 1px solid var(--border-secondary); background: color-mix(in oklab, var(--primary) 5%, transparent); }
.goals-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }
.goal-card { background: var(--overlay); border: 1px solid var(--border-secondary); border-left: 3px solid; border-radius: 8px; padding: 16px; }
.goal-status { font-size: 11px; font-weight: 600; padding: 1px 7px; border-radius: 999px; }
.goal-ok { background: color-mix(in oklab, var(--success) 15%, transparent); color: var(--success); }
.goal-warn { background: color-mix(in oklab, var(--warning) 15%, transparent); color: var(--warning); }
.goal-bad { background: color-mix(in oklab, var(--danger) 15%, transparent); color: var(--danger); }
.goal-done { background: color-mix(in oklab, var(--accent) 15%, transparent); color: var(--accent); }
.goal-bar { height: 6px; border-radius: 999px; background: var(--surface-secondary); overflow: hidden; margin-top: 4px; }
.goal-bar-fill { height: 100%; border-radius: 999px; transition: width .3s; }
</style>
