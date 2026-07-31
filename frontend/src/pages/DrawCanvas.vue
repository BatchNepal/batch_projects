<template>
  <div class="h-full flex flex-col overflow-hidden bg-background">

    <!-- Top bar -->
    <header class="shrink-0 h-12 flex items-center justify-between gap-3 px-4 bg-surface border-b border-separator">
      <div class="flex items-center gap-2 min-w-0 flex-1">
        <button type="button"
          class="flex items-center justify-center w-7 h-7 rounded-md text-muted hover:bg-[var(--surface-hover)] hover:text-foreground transition-colors shrink-0"
          @click="router.push(`/workspace/${route.params.key}/draw`)" title="Back to drawings">
          <Icon :icon="ArrowLeft" class="size-4" />
        </button>
        <Input v-if="canEdit" v-model="titleDraft" size="sm" class="max-w-[260px]" placeholder="Untitled drawing"
          @blur="saveTitleIfChanged" @keydown.enter="$event.target.blur()" />
        <span v-else class="text-[13.5px] font-medium text-foreground truncate">{{ titleDraft || 'Untitled drawing' }}</span>
      </div>

      <div class="flex items-center gap-3 shrink-0">
        <Transition name="fade">
          <span v-if="saving" key="saving" class="flex items-center gap-1.5 text-[12px] text-muted">
            <Spinner size="sm" /> Saving…
          </span>
          <span v-else-if="staleWarning" key="stale" class="flex items-center gap-1.5 text-[12px] text-warning">
            <Icon :icon="TriangleAlert" class="size-3.5" /> Overwrote a newer change
          </span>
          <span v-else-if="savedFlash" key="saved" class="flex items-center gap-1.5 text-[12px] text-[var(--success-soft-foreground)]">
            <Icon :icon="Check" class="size-3.5" /> Saved
          </span>
        </Transition>
        <Button v-if="canDelete" variant="light" color="danger" size="sm" :isLoading="deleting" @click="removeDrawing">
          Delete
        </Button>
      </div>
    </header>

    <!-- Canvas -->
    <div class="flex-1 min-h-0 relative overflow-hidden">
      <div v-if="loading" class="absolute inset-0 flex items-center justify-center">
        <Spinner size="md" />
      </div>
      <div v-else-if="error" class="absolute inset-0 flex items-center justify-center">
        <EmptyState :icon="AlertCircle" title="Can't open this drawing" :description="error" />
      </div>
      <ExcalidrawHost v-else :key="drawingId" :initial-data="initialData" :view-mode-enabled="!canEdit"
        @change="onChange" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { debounce } from 'lodash'
import { useProjectStore } from '@/stores/project'
import { Button, Input, Icon, Spinner, EmptyState } from '@/ui'
import { ArrowLeft, Check, TriangleAlert, AlertCircle } from 'lucide-vue-next'
import ExcalidrawHost from '@/components/ExcalidrawHost.vue'
import {
  getDrawing, saveDrawing, deleteDrawing, getMembers,
  FeatureDisabledError, UpgradeRequiredError,
} from '@/utils/api'

const route  = useRoute()
const router = useRouter()
const store  = useProjectStore()

const drawingId = computed(() => route.params.drawingId)
const sessionUser = window?.frappe?.session?.user || ''

const loading = ref(true)
const error   = ref('')
const canEdit   = ref(false)
const canDelete = ref(false)
const deleting   = ref(false)
const initialData = ref(null)
const titleDraft   = ref('')
let loadedModified = null
let savedTitle = ''
let skippedFirstChange = false // Excalidraw fires onChange once on mount with no real edit yet

async function loadRole(projectName) {
  try {
    const res = await getMembers(projectName)
    canDelete.value = !!res.can_manage
    canEdit.value = canDelete.value || (res.members || []).some(
      m => m.user === sessionUser && ['Member', 'Manager', 'Admin'].includes(m.role)
    )
  } catch { canEdit.value = false; canDelete.value = false }
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    if (!store.projects.length) await store.fetchProjects()
    const proj = store.projects.find(p => p.key === route.params.key)
    if (proj) await loadRole(proj.name)

    const doc = await getDrawing(drawingId.value)
    titleDraft.value = doc.title || ''
    savedTitle = doc.title || ''
    loadedModified = doc.modified
    let parsed = null
    try { parsed = doc.scene_json ? JSON.parse(doc.scene_json) : null } catch { parsed = null }
    initialData.value = parsed || { elements: [], appState: {} }
    skippedFirstChange = false
  } catch (e) {
    if (e instanceof FeatureDisabledError) error.value = e.message
    else if (e instanceof UpgradeRequiredError) error.value = e.message
    else error.value = e.message || "This drawing doesn't exist or you don't have access to it."
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(drawingId, load)

// ── Autosave ─────────────────────────────────────────────────────────────────
const saving       = ref(false)
const savedFlash    = ref(false)
const staleWarning  = ref(false)
let savedFlashTimer = null
let staleTimer       = null
let latestScene       = null

const doSave = debounce(async () => {
  if (!canEdit.value || latestScene == null) return
  saving.value = true
  try {
    const res = await saveDrawing(drawingId.value, {
      scene_json: latestScene, base_modified: loadedModified,
    })
    loadedModified = res.modified
    if (res.stale) {
      staleWarning.value = true
      clearTimeout(staleTimer)
      staleTimer = setTimeout(() => { staleWarning.value = false }, 4000)
    } else {
      savedFlash.value = true
      clearTimeout(savedFlashTimer)
      savedFlashTimer = setTimeout(() => { savedFlash.value = false }, 2000)
    }
  } catch (e) {
    console.error('saveDrawing error', e)
  } finally {
    saving.value = false
  }
}, 2000)

function onChange(elements, appState, files) {
  if (!canEdit.value || loading.value) return
  if (!skippedFirstChange) { skippedFirstChange = true; return }
  latestScene = JSON.stringify({
    elements,
    appState: { viewBackgroundColor: appState.viewBackgroundColor },
    files,
  })
  doSave()
}

async function saveTitleIfChanged() {
  if (!canEdit.value || titleDraft.value === savedTitle) return
  try {
    const res = await saveDrawing(drawingId.value, { title: titleDraft.value, base_modified: loadedModified })
    loadedModified = res.modified
    savedTitle = res.title
  } catch (e) {
    console.error('save title error', e)
  }
}

async function removeDrawing() {
  if (!confirm(`Delete "${titleDraft.value || 'this drawing'}"? This can't be undone.`)) return
  deleting.value = true
  try {
    await deleteDrawing(drawingId.value)
    router.push(`/workspace/${route.params.key}/draw`)
  } catch (e) {
    console.error('deleteDrawing error', e)
  } finally {
    deleting.value = false
  }
}

onBeforeUnmount(() => {
  // flush, not cancel — cancel() would silently discard up to 2s of strokes
  // when the user navigates away right after drawing.
  doSave.flush()
  clearTimeout(savedFlashTimer)
  clearTimeout(staleTimer)
})
</script>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.15s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
