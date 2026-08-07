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
        <!-- Who else has this drawing open right now — 
             avatar row with a live-presence dot. Only OTHER people show
             here; your own presence is implicit (you're looking at it). -->
        <div v-if="presentUsers.length" class="flex items-center -space-x-1.5">
          <div v-for="p in presentUsers.slice(0, 4)" :key="p.user" class="relative" :title="p.full_name">
            <Avatar :name="p.full_name" size="sm" class="ring-2 ring-[var(--surface)]" />
            <span class="dc-presence-dot" />
          </div>
          <span v-if="presentUsers.length > 4" class="dc-presence-overflow">+{{ presentUsers.length - 4 }}</span>
        </div>
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
      <ExcalidrawHost v-else ref="hostRef" :key="drawingId" :initial-data="initialData" :view-mode-enabled="!canEdit"
        @change="onChange" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { debounce } from 'lodash'
import { useProjectStore } from '@/stores/project'
import { Button, Input, Icon, Spinner, EmptyState, Avatar } from '@/ui'
import { ArrowLeft, Check, TriangleAlert, AlertCircle } from 'lucide-vue-next'
import ExcalidrawHost from '@/components/ExcalidrawHost.vue'
import { reconcileElements, CaptureUpdateAction } from '@excalidraw/excalidraw'
import {
  getDrawing, saveDrawing, deleteDrawing, getMembers,
  broadcastDrawingChange, broadcastDrawingPresence,
  FeatureDisabledError, UpgradeRequiredError,
} from '@/utils/api'
import { confirmDialog } from '@/composables/useConfirmDialog'
import { onRealtimeEvent } from '@/utils/realtime'

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

async function loadAndJoin() {
  stopRealtimeCollab() // leaving whatever drawing (if any) we were just on
  await load()
  if (!error.value) startRealtimeCollab()
}
onMounted(loadAndJoin)
watch(drawingId, loadAndJoin)

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
  // A remotely-applied update triggers this same onChange as a side effect
  // of updateScene() — must not re-save/re-broadcast the data we just
  // received (see applyRemoteElements / the applyingRemote flag above).
  if (applyingRemote) return
  latestScene = JSON.stringify({
    elements,
    appState: { viewBackgroundColor: appState.viewBackgroundColor },
    files,
  })
  doSave()
  // Live sync: a separate, faster debounce than the 2s autosave above — the
  // whole point is that other viewers see strokes appear quickly, not only
  // once the durable save lands.
  broadcastChange(JSON.stringify(elements))
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

// ── Live collaboration ──────────────────────────────────────────────────────
// Two independent signals, both ephemeral (see api/drawings.py's broadcast_
// only endpoints — nothing here is durable; saveDrawing above remains the
// only write to the actual BP Drawing doc):
//   1. Presence — who else has this drawing open (the avatar row in the
//      header). A client that vanishes without a clean unmount just ages out
//      of PRESENCE_STALE_MS — same posture as composables/usePresence.js's
//      existing workspace-wide online-dot heartbeat.
//   2. Scene sync — every local edit is pushed (debounced, separately and
//      faster than the 2s save) so everyone else's canvas updates live
//      instead of only on next reload; incoming pushes are merged via
//      Excalidraw's own reconcileElements (version-based, the same utility
//      their official collaboration example uses) so two people editing at
//      once don't stomp each other.
const hostRef      = ref(null)
const presentUsers = ref([]) // [{ user, full_name, lastSeen }], others only
const PRESENCE_HEARTBEAT_MS = 20000
const PRESENCE_STALE_MS     = 45000
let presenceHeartbeatTimer = null
let presenceSweepTimer     = null

// Set while applying a REMOTELY-received scene into Excalidraw — its own
// onChange fires as a side effect of updateScene(), and without this guard
// that would immediately re-save and re-broadcast the exact data we just
// received, in a wasteful (harmless but pointless) echo loop.
let applyingRemote = false

function upsertPresence(user, full_name) {
  if (!user || user === sessionUser) return
  const row = presentUsers.value.find(p => p.user === user)
  if (row) { row.full_name = full_name; row.lastSeen = Date.now() }
  else presentUsers.value.push({ user, full_name, lastSeen: Date.now() })
}
function removePresence(user) {
  presentUsers.value = presentUsers.value.filter(p => p.user !== user)
}
function sweepStalePresence() {
  const cutoff = Date.now() - PRESENCE_STALE_MS
  presentUsers.value = presentUsers.value.filter(p => p.lastSeen >= cutoff)
}

function pingPresence(leaving = false) {
  if (!drawingId.value) return
  broadcastDrawingPresence(drawingId.value, leaving).catch(() => {}) // best-effort
}

const broadcastChange = debounce((elementsJson) => {
  if (!drawingId.value) return
  broadcastDrawingChange(drawingId.value, elementsJson).catch(() => {}) // best-effort
}, 400)

function applyRemoteElements(elements) {
  const api = hostRef.value?.getApi?.()
  if (!api) return
  const local = api.getSceneElementsIncludingDeleted()
  const reconciled = reconcileElements(local, elements, api.getAppState())
  applyingRemote = true
  api.updateScene({ elements: reconciled, captureUpdate: CaptureUpdateAction.NEVER })
  // Reset on next tick — onChange fires synchronously off updateScene, so by
  // the time this line runs the guarded onChange call has already happened.
  Promise.resolve().then(() => { applyingRemote = false })
}

let stopRealtimeListener = null
function startRealtimeCollab() {
  stopRealtimeListener = onRealtimeEvent((payload) => {
    if (payload?.drawing !== drawingId.value || payload?.user === sessionUser) return

    if (payload.event === 'drawing.presence') {
      if (payload.leaving) removePresence(payload.user)
      else upsertPresence(payload.user, payload.full_name)
      return
    }
    if (payload.event === 'drawing.changed') {
      try {
        const scene = JSON.parse(payload.elements_json)
        const elements = Array.isArray(scene) ? scene : scene?.elements
        if (Array.isArray(elements)) applyRemoteElements(elements)
      } catch (e) {
        console.error('drawing.changed parse error', e)
      }
    }
  })

  pingPresence()
  presenceHeartbeatTimer = setInterval(() => pingPresence(), PRESENCE_HEARTBEAT_MS)
  presenceSweepTimer = setInterval(sweepStalePresence, PRESENCE_HEARTBEAT_MS)
}
function stopRealtimeCollab() {
  stopRealtimeListener?.()
  stopRealtimeListener = null
  if (presenceHeartbeatTimer) { clearInterval(presenceHeartbeatTimer); presenceHeartbeatTimer = null }
  if (presenceSweepTimer) { clearInterval(presenceSweepTimer); presenceSweepTimer = null }
  pingPresence(true) // best-effort "I'm leaving" — a clean unmount's fast path;
                      // an unclean one (closed tab) just relies on the 45s age-out
  presentUsers.value = []
}

async function removeDrawing() {
  if (!await confirmDialog(`Delete "${titleDraft.value || 'this drawing'}"? This can't be undone.`, { danger: true })) return
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
  stopRealtimeCollab()
})
</script>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.15s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

.dc-presence-dot {
  position: absolute;
  right: -1px;
  bottom: -1px;
  width: 8px;
  height: 8px;
  border-radius: var(--radius-full);
  background: var(--success);
  border: 1.5px solid var(--surface);
}
.dc-presence-overflow {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: var(--radius-full);
  background: var(--default);
  color: var(--muted);
  font-size: 9px;
  font-weight: 500;
  box-shadow: 0 0 0 2px var(--surface);
}
</style>
