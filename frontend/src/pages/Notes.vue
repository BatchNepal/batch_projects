<template>
  <div class="min-h-full bg-background">
    <div class="px-6 sm:px-8 py-6">

      <!-- Header -->
      <div class="flex items-center justify-between gap-4 mb-6">
        <div>
          <h1 class="text-[17px] font-semibold text-foreground tracking-[-0.01em]">Notes</h1>
          <p class="text-[13px] text-muted mt-1">Shared notes for this project — no digging through tasks.</p>
        </div>
        <Button v-if="canCreate" variant="solid" color="primary" size="sm" @click="openCreate">
          <Icon :icon="Plus" class="size-3.5 mr-1" /> New note
        </Button>
      </div>

      <!-- Loading -->
      <div v-if="loading" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5 gap-3">
        <Skeleton v-for="i in 6" :key="i" class="h-[132px] rounded-[10px]" />
      </div>

      <!-- Workspace admin turned Notes off (tab is already hidden in nav; this
           only fires on a direct URL hit or a race with entitlements load) -->
      <div v-else-if="ent.loaded && !ent.canWorkspace('notes')" class="bg-surface rounded-[10px]">
        <EmptyState :icon="Lock" title="Notes are turned off"
          description="A workspace admin turned this feature off. Ask them to re-enable it in Workspace Settings." />
      </div>

      <!-- Empty -->
      <div v-else-if="!notes.length" class="bg-surface rounded-[10px]">
        <EmptyState :icon="NotebookText" title="No notes yet"
          description="Capture a decision or bit of context here instead of burying it in a task.">
          <template v-if="canCreate" #action>
            <Button size="sm" color="primary" @click="openCreate">New note</Button>
          </template>
        </EmptyState>
      </div>

      <template v-else>
        <!-- Pinned strip -->
        <div v-if="pinnedNotes.length" class="mb-6">
          <p class="text-[11px] font-semibold uppercase tracking-wider text-muted mb-2">Pinned</p>
          <div class="flex gap-3 overflow-x-auto pb-1">
            <NoteCard v-for="n in pinnedNotes" :key="n.name" :note="n" compact @open="openNote(n)" />
          </div>
        </div>

        <!-- Card list -->
        <div>
          <p v-if="pinnedNotes.length" class="text-[11px] font-semibold uppercase tracking-wider text-muted mb-2">All notes</p>
          <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5 gap-3">
            <NoteCard v-for="n in unpinnedNotes" :key="n.name" :note="n" @open="openNote(n)" />
          </div>
        </div>
      </template>
    </div>

    <!-- Editor / viewer drawer -->
    <Drawer :open="drawerOpen" @update:open="closeDrawer" size="lg">
      <DrawerHeader @close="closeDrawer">
        <span class="text-[14px] font-semibold text-foreground">
          {{ editing ? (canEditCurrent ? 'Edit note' : 'Note') : 'New note' }}
        </span>
      </DrawerHeader>

      <DrawerBody class="space-y-4">
        <Input v-if="canEditCurrent" v-model="draft.title" size="md" placeholder="Untitled note" />
        <p v-else class="text-[16px] font-semibold text-foreground">{{ draft.title || 'Untitled note' }}</p>

        <RichTextEditor v-if="canEditCurrent" v-model="draft.content"
          placeholder="Write something the team should know…" min-height="240px" always-toolbar />
        <div v-else class="note-preview" v-html="draft.content || '<p class=\'text-muted\'>Nothing here yet.</p>'" />

        <div v-if="editing" class="flex items-center gap-1.5 text-[12px] text-muted pt-1 border-t border-separator">
          <Avatar :name="editing.owner_name" size="xs" />
          {{ editing.owner_name }} · {{ fmtDate(editing.modified) }}
        </div>
      </DrawerBody>

      <DrawerFooter class="justify-between">
        <div class="flex items-center gap-3">
          <template v-if="canEditCurrent">
            <button type="button" class="flex items-center gap-1.5 text-[12.5px] text-muted hover:text-foreground transition-colors"
              @click="draft.pinned = draft.pinned ? 0 : 1">
              <Icon :icon="draft.pinned ? Pin : PinOff" :size="14" :class="draft.pinned ? 'text-primary' : ''" />
              {{ draft.pinned ? 'Pinned' : 'Pin note' }}
            </button>
          </template>
          <Button v-if="editing && canEditCurrent" variant="light" color="danger" size="sm"
            :isLoading="deleting" @click="removeNote">
            Delete
          </Button>
        </div>
        <div class="flex items-center gap-2">
          <Button variant="bordered" color="default" size="sm" @click="closeDrawer">
            {{ canEditCurrent ? 'Cancel' : 'Close' }}
          </Button>
          <Button v-if="canEditCurrent" variant="solid" color="primary" size="sm" :isLoading="saving" @click="saveNote">
            Save
          </Button>
        </div>
      </DrawerFooter>
    </Drawer>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch, defineComponent, h } from 'vue'
import { useRoute } from 'vue-router'
import { useProjectStore } from '@/stores/project'
import { useEntitlementsStore } from '@/stores/entitlements'
import {
  Button, Input, Icon, Skeleton, EmptyState, Avatar,
  Drawer, DrawerHeader, DrawerBody, DrawerFooter,
} from '@/ui'
import { Plus, Pin, PinOff, Lock, NotebookText } from 'lucide-vue-next'
import RichTextEditor from '@/components/RichTextEditor.vue'
import { listNotes, createNote, updateNote, deleteNote, getMembers, FeatureDisabledError } from '@/utils/api'
import { confirmDialog } from '@/composables/useConfirmDialog'

const route = useRoute()
const store = useProjectStore()
const ent   = useEntitlementsStore()

const sessionUser = window?.frappe?.session?.user || ''
// This client-side rank is a display/UI-gating hint only (which button to
// show) — the real enforcement is server-side in api/notes.py via access.py.
const ROLE_RANK = { Admin: 4, Manager: 3, Member: 2, Viewer: 1 }

const project = computed(() => store.projects.find(p => p.key === route.params.key))
const projectMembers = ref([])
const isManager = ref(false) // can_manage, straight from get_members — authoritative

const myRole = computed(() =>
  projectMembers.value.find(m => m.user === sessionUser)?.role
)
const canCreate = computed(() => isManager.value || (ROLE_RANK[myRole.value] || 0) >= ROLE_RANK.Member)

function canEditNote(note) {
  return !!note && (note.owner === sessionUser || isManager.value)
}

// ── Load ─────────────────────────────────────────────────────────────────────
const loading = ref(true)
const notes   = ref([])

async function load() {
  if (!project.value) return
  loading.value = true
  try {
    const [notesRes, membersRes] = await Promise.all([
      listNotes(project.value.name),
      getMembers(project.value.name).catch(() => null),
    ])
    notes.value = notesRes
    if (membersRes) {
      projectMembers.value = membersRes.members || []
      isManager.value = !!membersRes.can_manage
    }
  } catch (e) {
    if (!(e instanceof FeatureDisabledError)) console.error('listNotes error', e)
    notes.value = []
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  if (!store.projects.length) { try { await store.fetchProjects() } catch {} }
  await load()
})
watch(() => route.params.key, load)

const pinnedNotes   = computed(() => notes.value.filter(n => n.pinned))
const unpinnedNotes = computed(() => notes.value.filter(n => !n.pinned))

// ── Drawer ───────────────────────────────────────────────────────────────────
const drawerOpen = ref(false)
const editing    = ref(null) // note object, or null when creating
const saving     = ref(false)
const deleting   = ref(false)
const draft = reactive({ title: '', content: '', pinned: 0 })

const canEditCurrent = computed(() => !editing.value || canEditNote(editing.value))

function openCreate() {
  editing.value = null
  Object.assign(draft, { title: '', content: '', pinned: 0 })
  drawerOpen.value = true
}
function openNote(n) {
  editing.value = n
  Object.assign(draft, { title: n.title, content: n.content, pinned: n.pinned ? 1 : 0 })
  drawerOpen.value = true
}
function closeDrawer() {
  drawerOpen.value = false
  editing.value = null
}

async function saveNote() {
  if (!project.value) return
  saving.value = true
  try {
    if (editing.value) {
      const updated = await updateNote(editing.value.name, {
        title: draft.title, content: draft.content, pinned: draft.pinned,
      })
      const i = notes.value.findIndex(n => n.name === updated.name)
      if (i !== -1) notes.value[i] = updated
    } else {
      const created = await createNote(project.value.name, draft.title, draft.content, draft.pinned)
      notes.value.unshift(created)
    }
    closeDrawer()
  } catch (e) {
    console.error('saveNote error', e)
  } finally {
    saving.value = false
  }
}

async function removeNote() {
  if (!editing.value) return
  if (!await confirmDialog(`Delete "${editing.value.title || 'this note'}"? This can't be undone.`, { danger: true })) return
  deleting.value = true
  try {
    await deleteNote(editing.value.name)
    notes.value = notes.value.filter(n => n.name !== editing.value.name)
    closeDrawer()
  } catch (e) {
    console.error('deleteNote error', e)
  } finally {
    deleting.value = false
  }
}

// ── Formatters ────────────────────────────────────────────────────────────────
function stripHtml(html) {
  if (!html) return ''
  return html.replace(/<[^>]*>/g, ' ').replace(/&amp;/g, '&').replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/\s+/g, ' ').trim()
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

// ── NoteCard (local render-fn component, mirrors WorkspaceSettings FeatureRow) ─
const NoteCard = defineComponent({
  props: { note: { type: Object, required: true }, compact: { type: Boolean, default: false } },
  emits: ['open'],
  setup(props, { emit }) {
    return () => h('div', {
      class: [
        'group bg-surface shadow-surface rounded-[10px] p-4 cursor-pointer hover:bg-[var(--surface-hover)] transition-colors duration-150',
        props.compact ? 'shrink-0 w-[260px]' : '',
      ],
      onClick: () => emit('open'),
    }, [
      h('div', { class: 'flex items-start justify-between gap-2 mb-1.5' }, [
        h('p', { class: 'text-[13px] font-semibold text-foreground truncate' }, props.note.title || 'Untitled note'),
        props.note.pinned ? h(Icon, { icon: Pin, size: 13, class: 'text-primary shrink-0 mt-0.5' }) : null,
      ]),
      h('p', { class: 'text-[12px] text-muted line-clamp-3 leading-relaxed min-h-[3.15em]' }, stripHtml(props.note.content) || 'No content yet.'),
      h('div', { class: 'flex items-center gap-1.5 mt-3' }, [
        h(Avatar, { name: props.note.owner_name, size: 'xs' }),
        h('span', { class: 'text-[11px] text-muted truncate' }, `${props.note.owner_name} · ${fmtDate(props.note.modified)}`),
      ]),
    ])
  },
})
</script>

<style scoped>
.note-preview { font-size: 13.5px; color: var(--foreground); line-height: 1.65; }
.note-preview :deep(p) { margin: 0 0 10px; }
.note-preview :deep(p:last-child) { margin: 0; }
.note-preview :deep(h1) { font-size: 18px; font-weight: 600; margin: 0 0 10px; }
.note-preview :deep(h2) { font-size: 16px; font-weight: 600; margin: 0 0 8px; }
.note-preview :deep(h3) { font-size: 14px; font-weight: 600; margin: 0 0 8px; }
.note-preview :deep(ul), .note-preview :deep(ol) { margin: 0 0 10px; padding-left: 20px; }
.note-preview :deep(blockquote) { border-left: 2px solid var(--border); padding-left: 10px; color: var(--muted); margin: 0 0 10px; }
.note-preview :deep(code) { background: var(--surface-secondary); border-radius: 4px; padding: 1px 4px; font-size: 12.5px; }
.note-preview :deep(pre) { background: var(--surface-secondary); border-radius: 8px; padding: 10px 12px; overflow-x: auto; margin: 0 0 10px; }
</style>
