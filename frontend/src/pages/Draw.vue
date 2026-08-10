<template>
  <div class="min-h-full bg-background">
    <div class="px-6 sm:px-8 py-6">

      <!-- Header -->
      <div class="flex items-center justify-between gap-4 mb-6">
        <div>
          <h1 class="text-xl font-semibold text-foreground tracking-[-0.01em]">Draw</h1>
          <p class="text-base text-muted mt-1">Whiteboards for this project — sketch it before you spec it.</p>
        </div>
        <Button v-if="canCreate && unlocked && ent.canWorkspace('draw')" variant="solid" color="primary" size="sm"
          :isLoading="creating" @click="openNewDrawing">
          <Icon :icon="Plus" class="size-3.5 mr-1" /> New drawing
        </Button>
      </div>

      <!-- Entitlements haven't resolved yet — wait rather than flash the wrong banner -->
      <div v-if="!ent.loaded || loading" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5 gap-3">
        <Skeleton v-for="i in 6" :key="i" class="h-[132px] rounded-[10px]" />
      </div>

      <!-- Workspace admin turned Draw off -->
      <div v-else-if="!ent.canWorkspace('draw')" class="bg-surface rounded-[10px]">
        <EmptyState :icon="Lock" title="Draw is turned off"
          description="A workspace admin turned this feature off. Ask them to re-enable it in Workspace Settings." />
      </div>

      <!-- Locked (below Team tier) — always reachable, never blocked at the tab -->
      <div v-else-if="!unlocked" class="flex items-start gap-4 p-5 rounded-[10px] border border-[var(--border-secondary)]"
        style="background: color-mix(in oklab, var(--primary) 5%, transparent)">
        <span class="w-10 h-10 rounded-[8px] shrink-0 flex items-center justify-center bg-overlay border border-border shadow-xs">
          <Icon :icon="Lock" class="size-5 text-primary" />
        </span>
        <div class="min-w-0 flex-1">
          <p class="text-md font-semibold text-foreground">Sketch it out with the whole team</p>
          <p class="text-base text-muted mt-1 leading-relaxed">
            A shared Excalidraw whiteboard per project — wireframes, flows, quick diagrams.
            Available on the <span class="font-semibold text-foreground">{{ requiredPlan }}</span> plan and above.
          </p>
          <div class="flex items-center gap-2 mt-3">
            <Button size="sm" color="primary" @click="goUpgrade">
              <Icon :icon="Sparkles" class="size-3.5 mr-1" /> Upgrade to {{ requiredPlan }}
            </Button>
            <span class="text-sm text-muted">You're on the {{ ent.tierLabel }} plan</span>
          </div>
        </div>
      </div>

      <!-- Empty -->
      <div v-else-if="!drawings.length" class="bg-surface rounded-[10px]">
        <EmptyState :icon="PenTool" title="No drawings yet"
          description="Start a whiteboard for wireframes, flows, or a quick diagram the whole team can see.">
          <template v-if="canCreate" #action>
            <Button size="sm" color="primary" :isLoading="creating" @click="openNewDrawing">New drawing</Button>
          </template>
        </EmptyState>
      </div>

      <!-- Card grid -->
      <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5 gap-3">
        <RouterLink
          v-for="d in drawings" :key="d.name"
          :to="`/workspace/${route.params.key}/draw/${d.name}`"
          class="group bg-surface shadow-surface rounded-[10px] p-4 hover:bg-[var(--surface-hover)] transition-colors duration-150 block"
        >
          <div class="h-[72px] rounded-[6px] bg-[var(--surface-secondary)] flex items-center justify-center mb-3">
            <Icon :icon="PenTool" :size="20" class="text-muted" />
          </div>
          <p class="text-base font-semibold text-foreground truncate">{{ d.title || 'Untitled drawing' }}</p>
          <div class="flex items-center gap-1.5 mt-2">
            <Avatar :name="d.owner_name" size="xs" />
            <span class="text-xs text-muted truncate">{{ d.owner_name }} · {{ fmtDate(d.modified) }}</span>
          </div>
        </RouterLink>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { useProjectStore } from '@/stores/project'
import { useEntitlementsStore } from '@/stores/entitlements'
import { Button, Icon, Skeleton, EmptyState, Avatar } from '@/ui'
import { Plus, Lock, PenTool, Sparkles } from 'lucide-vue-next'
import { listDrawings, createDrawing, getMembers, FeatureDisabledError, UpgradeRequiredError } from '@/utils/api'

const route  = useRoute()
const router = useRouter()
const store  = useProjectStore()
const ent    = useEntitlementsStore()

const unlocked     = computed(() => ent.can('draw'))
const requiredPlan = computed(() => ent.requiredPlanFor('draw'))
function goUpgrade() {
  router.push({ name: 'Pricing' }).catch(() => { window.location.hash = '#/pricing' })
}

const sessionUser = window?.frappe?.session?.user || ''
const project = computed(() => store.projects.find(p => p.key === route.params.key))
const canCreate = ref(false)

async function loadRole() {
  if (!project.value) return
  try {
    const res = await getMembers(project.value.name)
    canCreate.value = !!res.can_manage || (res.members || []).some(
      m => m.user === sessionUser && ['Member', 'Manager', 'Admin'].includes(m.role)
    )
  } catch { canCreate.value = false }
}

// ── Load ─────────────────────────────────────────────────────────────────────
const loading   = ref(true)
const drawings  = ref([])

async function load() {
  if (!project.value || !unlocked.value || !ent.canWorkspace('draw')) { loading.value = false; return }
  loading.value = true
  try {
    const [drawingsRes] = await Promise.all([listDrawings(project.value.name), loadRole()])
    drawings.value = drawingsRes
  } catch (e) {
    if (!(e instanceof FeatureDisabledError) && !(e instanceof UpgradeRequiredError)) console.error('listDrawings error', e)
    drawings.value = []
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  if (!store.projects.length) { try { await store.fetchProjects() } catch {} }
  await load()
})
// Cold load races App.vue's async entitlements bootstrap — re-run once it resolves.
watch([() => route.params.key, unlocked, () => ent.loaded], load)

// ── Create ───────────────────────────────────────────────────────────────────
const creating = ref(false)
async function openNewDrawing() {
  if (!project.value) return
  creating.value = true
  try {
    const created = await createDrawing(project.value.name, 'Untitled drawing')
    router.push(`/workspace/${route.params.key}/draw/${created.name}`)
  } catch (e) {
    console.error('createDrawing error', e)
  } finally {
    creating.value = false
  }
}

function fmtDate(d) {
  if (!d) return ''
  const dt = new Date(d)
  const diff = Math.floor((Date.now() - dt.getTime()) / 1000)
  if (diff < 60) return 'just now'
  if (diff < 3600) return Math.floor(diff / 60) + 'm ago'
  if (diff < 86400) return Math.floor(diff / 3600) + 'h ago'
  if (diff < 86400 * 7) return Math.floor(diff / 86400) + 'd ago'
  return dt.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })
}
</script>
