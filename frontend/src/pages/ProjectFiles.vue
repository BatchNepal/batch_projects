<template>
  <div class="min-h-full bg-[var(--background)] font-sans text-[var(--foreground)]">

    <!-- ── Toolbar ───────────────────────────────────────────────────── -->
    <div class="sticky top-0 z-10 flex flex-wrap items-center gap-2 px-6 py-3 bg-overlay border-b border-border">

      <!-- Search -->
      <div class="relative">
        <Search :size="14" class="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted pointer-events-none" />
        <input
          v-model="search"
          type="text"
          placeholder="Search files…"
          class="h-8 w-52 pl-8 pr-3 text-[13px] bg-surface-secondary border border-border rounded-md focus:outline-none focus:shadow-focus focus:bg-overlay transition-colors"
        />
      </div>

      <!-- Type filter pills -->
      <div class="flex items-center gap-0.5 p-0.5 bg-surface-secondary border border-border rounded-md">
        <button
          v-for="f in TYPE_FILTERS"
          :key="f.value"
          type="button"
          :class="[
            'px-2.5 h-6 text-[12px] font-medium rounded transition-[background-color,color]',
            typeFilter === f.value
              ? 'bg-overlay text-foreground shadow-sm'
              : 'text-muted hover:text-muted'
          ]"
          @click="typeFilter = f.value"
        >{{ f.label }}</button>
      </div>

      <div class="flex-1" />

      <!-- Count -->
      <span v-if="!loading" class="text-[12px] text-muted tabular-nums">
        {{ filteredFiles.length }} {{ filteredFiles.length === 1 ? 'file' : 'files' }}
      </span>

      <!-- Upload -->
      <input ref="fileInputEl" type="file" multiple class="hidden" @change="onFilePicked" />
      <Button size="sm" color="primary" :isLoading="uploading" @click="fileInputEl?.click()">
        <template #startContent><Icon :icon="UploadIcon" :size="13" /></template>
        Upload
      </Button>

      <!-- Group by task toggle -->
      <button
        type="button"
        :class="[
          'flex items-center gap-1.5 px-2.5 h-8 text-[12px] font-medium rounded-md border transition-[background-color,color,border-color]',
          groupByTask
            ? 'bg-accent-soft text-accent-soft-foreground'
            : 'border-border bg-overlay text-muted hover:text-foreground hover:border-border-secondary'
        ]"
        @click="groupByTask = !groupByTask"
      >
        <Layers :size="13" :stroke-width="2" />
        By task
      </button>

      <!-- View toggle -->
      <div class="flex items-center p-0.5 bg-surface-secondary border border-border rounded-md">
        <button
          type="button"
          :class="[
            'w-7 h-6 flex items-center justify-center rounded transition-[background-color,color]',
            viewMode === 'grid' ? 'bg-overlay shadow-sm text-foreground' : 'text-muted hover:text-muted'
          ]"
          @click="viewMode = 'grid'"
          title="Grid"
        ><LayoutGrid :size="13" :stroke-width="2" /></button>
        <button
          type="button"
          :class="[
            'w-7 h-6 flex items-center justify-center rounded transition-[background-color,color]',
            viewMode === 'list' ? 'bg-overlay shadow-sm text-foreground' : 'text-muted hover:text-muted'
          ]"
          @click="viewMode = 'list'"
          title="List"
        ><List :size="13" :stroke-width="2" /></button>
      </div>
    </div>

    <!-- ── Content ───────────────────────────────────────────────────── -->
    <!-- Drag-and-drop target spans the whole content area, not just the
         empty state — dropping a file onto an already-populated grid must
         work exactly like dropping onto an empty one. dragCounter (not a
         plain boolean) is required: child elements firing their own
         dragenter/dragleave as the pointer crosses card boundaries would
         otherwise flicker isDraggingOver off mid-drag. -->
    <div
      class="px-6 py-5 relative"
      @dragenter.prevent="onDragEnter"
      @dragover.prevent
      @dragleave.prevent="onDragLeave"
      @drop.prevent="onDrop"
    >
      <div v-if="isDraggingOver" class="fp-drop-overlay">
        <div class="fp-drop-card">
          <UploadIcon :size="22" :stroke-width="1.5" />
          <p>Drop to upload to this project</p>
        </div>
      </div>

      <!-- Loading -->
      <div v-if="loading" class="flex items-center justify-center py-24">
        <div class="w-6 h-6 rounded-full border-2 border-accent border-t-transparent animate-spin" />
      </div>

      <!-- Empty -->
      <div v-else-if="!filteredFiles.length" class="bg-overlay rounded-lg border border-border">
        <EmptyState
          :icon="search || typeFilter !== 'all' ? SearchX : Paperclip"
          :title="search || typeFilter !== 'all' ? 'No files match' : 'No files yet'"
          :description="search || typeFilter !== 'all' ? 'Drag and drop files here, or use Upload.' : 'Files uploaded here or attached to tasks in this project will appear here.'"
        />
      </div>

      <!-- File groups (flat = 1 group with task_name null; grouped = per task) -->
      <template v-else>
        <div
          v-for="(group, gi) in displayGroups"
          :key="group.task_name || '__flat__'"
          :class="gi > 0 ? 'mt-6' : ''"
        >
          <!-- Group header (only shown in group-by-task mode). The
               task_name-less bucket is files uploaded to the project
               directly — it used to render NO header at all (v-if
               silently skipped it), so those files appeared to belong to
               whichever group happened to render right before them. -->
          <div v-if="groupByTask" class="flex items-center gap-2 mb-3 px-0.5">
            <button
              v-if="group.task_name"
              class="text-[13px] font-semibold text-foreground hover:text-accent transition-colors"
              @click="openTask(group.task_name)"
            >{{ group.task_title }}</button>
            <span v-else class="text-[13px] font-semibold text-foreground">Project files</span>
            <span class="text-[11px] text-muted font-normal">
              {{ group.files.length }} {{ group.files.length === 1 ? 'file' : 'files' }}
            </span>
          </div>

          <!-- ── GRID ─────────────────────────────────────────────────── -->
          <div
            v-if="viewMode === 'grid'"
            class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3"
          >
            <div
              v-for="f in group.files"
              :key="f.name"
              class="group relative bg-overlay rounded-lg border border-border overflow-hidden hover:border-border-secondary hover:shadow-md transition-[border-color,box-shadow] cursor-pointer select-none"
              @click="openPreview(f)"
              @contextmenu.prevent="openContextMenu(f, $event)"
            >
              <!-- Thumbnail area -->
              <div class="aspect-[4/3] bg-surface-secondary flex items-center justify-center overflow-hidden relative">
                <img
                  v-if="isImage(f.file_name)"
                  :src="f.file_url"
                  :alt="f.file_name"
                  class="w-full h-full object-cover"
                  @error="onImgError"
                />
                <div
                  v-else
                  class="w-14 h-14 rounded-xl flex items-center justify-center text-[13px] font-bold"
                  :style="fileIconStyle(f.file_name)"
                >{{ fileIconLabel(f.file_name) }}</div>
              </div>

              <!-- Hover overlay: download button -->
              <div class="absolute top-0 right-0 p-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
                <a
                  :href="f.file_url"
                  target="_blank"
                  download
                  class="w-7 h-7 flex items-center justify-center rounded-md bg-overlay/90 backdrop-blur-sm text-muted hover:text-foreground shadow-sm border border-border"
                  @click.stop
                ><Download :size="12" :stroke-width="2" /></a>
              </div>

              <!-- Info -->
              <div class="px-2.5 py-2 border-t border-separator">
                <p class="text-[12px] font-medium text-foreground truncate leading-snug" :title="f.file_name">
                  {{ f.file_name }}
                </p>
                <p
                  v-if="!groupByTask"
                  class="text-[10.5px] text-muted mt-0.5 truncate"
                  :title="f.task_title || 'Project file'"
                >{{ f.task_title || 'Project file' }}</p>
                <p class="text-[10.5px] text-muted mt-0.5 tabular-nums">{{ fmtSize(f.file_size) }}</p>
              </div>
            </div>
          </div>

          <!-- ── LIST ─────────────────────────────────────────────────── -->
          <div v-else class="bg-overlay rounded-lg border border-border overflow-hidden">
            <table class="w-full border-collapse text-sm">
              <thead>
                <tr class="border-b border-separator bg-surface-secondary">
                  <th class="text-left px-5 py-3 text-[11px] font-semibold uppercase tracking-wider text-muted">File</th>
                  <th v-if="!groupByTask" class="text-left px-4 py-3 text-[11px] font-semibold uppercase tracking-wider text-muted">Task</th>
                  <th class="text-left px-4 py-3 text-[11px] font-semibold uppercase tracking-wider text-muted hidden md:table-cell">Uploaded by</th>
                  <th class="text-right px-4 py-3 text-[11px] font-semibold uppercase tracking-wider text-muted">Size</th>
                  <th class="text-right px-5 py-3 text-[11px] font-semibold uppercase tracking-wider text-muted hidden sm:table-cell">Date</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="f in group.files"
                  :key="f.name"
                  class="border-b border-separator last:border-0 hover:bg-surface-secondary transition-colors cursor-pointer"
                  @click="openPreview(f)"
                  @contextmenu.prevent="openContextMenu(f, $event)"
                >
                  <!-- Icon + name -->
                  <td class="px-5 py-3">
                    <div class="flex items-center gap-2.5">
                      <div
                        class="w-7 h-7 rounded-md flex items-center justify-center text-[9px] font-bold shrink-0"
                        :style="fileIconStyle(f.file_name)"
                      >{{ fileIconLabel(f.file_name) }}</div>
                      <span class="text-[13px] font-medium text-foreground truncate max-w-[200px]" :title="f.file_name">
                        {{ f.file_name }}
                      </span>
                    </div>
                  </td>

                  <!-- Task (hidden in group mode) -->
                  <td v-if="!groupByTask" class="px-4 py-3">
                    <button
                      v-if="f.task_name"
                      class="text-[12px] text-muted hover:text-accent transition-colors truncate max-w-[180px] text-left block"
                      @click.stop="openTask(f.task_name)"
                    >{{ f.task_title }}</button>
                    <span v-else class="text-[12px] text-muted truncate max-w-[180px] block">Project file</span>
                  </td>

                  <!-- Uploaded by -->
                  <td class="px-4 py-3 hidden md:table-cell">
                    <span class="text-[12px] text-muted">{{ f.uploaded_by_name }}</span>
                  </td>

                  <!-- Size -->
                  <td class="px-4 py-3 text-right">
                    <span class="text-[12px] text-muted tabular-nums">{{ fmtSize(f.file_size) }}</span>
                  </td>

                  <!-- Date -->
                  <td class="px-5 py-3 text-right hidden sm:table-cell">
                    <span class="text-[12px] text-muted tabular-nums">{{ fmtDate(f.creation) }}</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </template>

    </div>

    <!-- ── Lightbox ──────────────────────────────────────────────────── -->
    <Teleport to="body">
      <Transition name="lb">
        <div
          v-if="preview"
          class="fixed inset-0 z-[70] bg-black/70 flex items-center justify-center p-4"
          @mousedown.self="closePreview"
        >
          <div class="relative bg-overlay rounded-xl shadow-overlay overflow-hidden w-full max-w-4xl max-h-[90vh] flex flex-col">

            <!-- Lightbox header -->
            <div class="flex items-center gap-3 px-4 py-3 border-b border-separator shrink-0">
              <div
                class="w-8 h-8 rounded-lg flex items-center justify-center text-[10px] font-bold shrink-0"
                :style="fileIconStyle(preview.file_name)"
              >{{ fileIconLabel(preview.file_name) }}</div>
              <div class="flex-1 min-w-0">
                <p class="text-[13px] font-semibold text-foreground truncate leading-none">{{ preview.file_name }}</p>
                <p class="text-[11px] text-muted mt-0.5 leading-none">
                  {{ fmtSize(preview.file_size) }}
                  <span v-if="preview.task_title"> ·
                    <button class="hover:text-muted transition-colors" @click="openTask(preview.task_name)">
                      {{ preview.task_title }}
                    </button>
                  </span>
                </p>
              </div>
              <a
                :href="preview.file_url"
                target="_blank"
                download
                class="flex items-center gap-1.5 px-3 h-7 text-[12px] font-medium bg-surface-secondary hover:bg-surface-hover text-muted rounded-md transition-colors"
              >
                <Download :size="12" :stroke-width="2" />
                Download
              </a>
              <button
                class="w-7 h-7 flex items-center justify-center rounded-md text-muted hover:bg-surface-hover transition-colors"
                @click="closePreview"
              ><X :size="15" :stroke-width="1.75" /></button>
            </div>

            <!-- Lightbox body -->
            <div class="flex-1 overflow-auto flex items-center justify-center bg-surface-secondary p-4 min-h-0">
              <!-- Image -->
              <img
                v-if="isImage(preview.file_name)"
                :src="preview.file_url"
                :alt="preview.file_name"
                class="max-w-full object-contain rounded-lg shadow-sm"
                style="max-height: 70vh"
                @error="onImgError"
              />
              <!-- Video -->
              <video
                v-else-if="isVideo(preview.file_name)"
                :src="preview.file_url"
                controls
                class="max-w-full rounded-lg shadow-sm"
                style="max-height: 70vh"
              />
              <!-- PDF -->
              <iframe
                v-else-if="isPdf(preview.file_name)"
                :src="preview.file_url"
                class="w-full rounded-lg border border-border"
                style="height: 65vh"
                frameborder="0"
              />
              <!-- No preview fallback -->
              <div v-else class="flex flex-col items-center gap-4 py-16">
                <div
                  class="w-20 h-20 rounded-2xl flex items-center justify-center text-xl font-bold"
                  :style="fileIconStyle(preview.file_name)"
                >{{ fileIconLabel(preview.file_name) }}</div>
                <p class="text-[13px] text-muted">No preview available for this file type</p>
                <a
                  :href="preview.file_url"
                  target="_blank"
                  download
                  class="flex items-center gap-2 px-4 h-9 text-[13px] font-medium bg-foreground hover:opacity-90 text-white rounded-lg transition-colors"
                ><Download :size="14" :stroke-width="2" /> Download file</a>
              </div>
            </div>

          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- ── Right-click context menu ──────────────────────────────────── -->
    <FileContextMenu
      :file="ctxFile" :x="ctxPos.x" :y="ctxPos.y"
      @close="ctxFile = null"
      @rename="onRename"
      @delete="onDelete"
    />

  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useProjectStore } from '@/stores/project'
import { getProjectFiles, uploadProjectFile, renameProjectFile, deleteProjectFile } from '@/utils/api'
import { confirmDialog, promptDialog } from '@/composables/useConfirmDialog'
import { Button, Icon } from '@/ui'
import EmptyState from '@/ui/EmptyState.vue'
import FileContextMenu from '@/components/FileContextMenu.vue'
import { toast } from 'vue-sonner'
import { Paperclip, LayoutGrid, List, Search, X, Download, Layers, SearchX, Upload as UploadIcon } from 'lucide-vue-next'

const route = useRoute()
const store = useProjectStore()

// ── State ─────────────────────────────────────────────────────────────
const loading     = ref(false)
const allFiles    = ref([])
const search      = ref('')
const viewMode    = ref('grid')
const typeFilter  = ref('all')
const groupByTask = ref(false)
const preview     = ref(null)
const projectName = ref(null) // BP Project docname (not the :key route param)

const TYPE_FILTERS = [
  { value: 'all',       label: 'All'    },
  { value: 'images',    label: 'Images' },
  { value: 'docs',      label: 'Docs'   },
  { value: 'video',     label: 'Video'  },
  { value: 'other',     label: 'Other'  },
]

// ── File type helpers ─────────────────────────────────────────────────
const IMAGE_EXT = new Set(['jpg','jpeg','png','gif','webp','svg','bmp','avif','ico','tiff'])
const VIDEO_EXT = new Set(['mp4','webm','mov','avi','mkv'])
const DOC_EXT   = new Set(['pdf','doc','docx','xls','xlsx','csv','ppt','pptx','txt','md','rtf'])

function ext(name) { return (name || '').split('.').pop()?.toLowerCase() || '' }
function isImage(name) { return IMAGE_EXT.has(ext(name)) }
function isVideo(name) { return VIDEO_EXT.has(ext(name)) }
function isPdf(name)   { return ext(name) === 'pdf' }

// ── Filtering ─────────────────────────────────────────────────────────
const filteredFiles = computed(() => {
  let files = allFiles.value

  if (typeFilter.value === 'images') files = files.filter(f => isImage(f.file_name))
  else if (typeFilter.value === 'docs')  files = files.filter(f => DOC_EXT.has(ext(f.file_name)))
  else if (typeFilter.value === 'video') files = files.filter(f => isVideo(f.file_name))
  else if (typeFilter.value === 'other') files = files.filter(f =>
    !isImage(f.file_name) && !DOC_EXT.has(ext(f.file_name)) && !isVideo(f.file_name)
  )

  if (search.value.trim()) {
    const q = search.value.toLowerCase()
    files = files.filter(f =>
      f.file_name.toLowerCase().includes(q) ||
      (f.task_title || '').toLowerCase().includes(q) ||
      (f.uploaded_by_name || '').toLowerCase().includes(q)
    )
  }

  return files
})

// ── Group by task ─────────────────────────────────────────────────────
const groupedFiles = computed(() => {
  const map = {}
  for (const f of filteredFiles.value) {
    const k = f.task_name || '__none__'
    if (!map[k]) map[k] = { task_name: f.task_name, task_title: f.task_title, files: [] }
    map[k].files.push(f)
  }
  return Object.values(map).sort((a, b) =>
    (a.task_title || '').localeCompare(b.task_title || '')
  )
})

// Single loop source: either 1 flat group or per-task groups
const displayGroups = computed(() =>
  groupByTask.value
    ? groupedFiles.value
    : [{ task_name: null, task_title: null, files: filteredFiles.value }]
)

// ── Load ──────────────────────────────────────────────────────────────
async function load() {
  loading.value = true
  try {
    if (!store.projects.length) await store.fetchProjects()
    const proj = store.projects.find(p => p.key === route.params.key)
    if (!proj) return
    projectName.value = proj.name
    const res = await getProjectFiles(proj.name)
    allFiles.value = res || []
  } catch (e) {
    console.error('ProjectFiles load error', e)
  } finally {
    loading.value = false
  }
}

onMounted(load)

// ── Upload (button + drag-and-drop) ────────────────────────────────────
const fileInputEl   = ref(null)
const uploading      = ref(false)
const isDraggingOver = ref(false)
let dragCounter = 0 // see the drop-zone template comment: children re-firing
                     // dragenter/dragleave as the cursor crosses them would
                     // flicker a plain boolean; a depth counter doesn't.

async function uploadFiles(fileList) {
  const files = Array.from(fileList || [])
  if (!files.length || !projectName.value) return
  uploading.value = true
  let okCount = 0
  for (const file of files) {
    try {
      await uploadProjectFile(file, projectName.value)
      okCount++
    } catch (e) {
      toast.error(`Could not upload "${file.name}"`, { description: e.message })
    }
  }
  uploading.value = false
  if (okCount) toast.success(`${okCount} file${okCount === 1 ? '' : 's'} uploaded`)
  if (okCount) await load()
}

function onFilePicked(e) {
  uploadFiles(e.target.files)
  e.target.value = '' // same file picked twice in a row must still fire @change
}

function onDragEnter(e) {
  // Only real files, not e.g. a task card being dragged from the board in
  // another tab/window — dataTransfer.types is the one thing available
  // during dragenter (the actual File objects only exist at drop time).
  if (!e.dataTransfer?.types?.includes('Files')) return
  dragCounter++
  isDraggingOver.value = true
}
function onDragLeave() {
  dragCounter = Math.max(0, dragCounter - 1)
  if (dragCounter === 0) isDraggingOver.value = false
}
function onDrop(e) {
  dragCounter = 0
  isDraggingOver.value = false
  uploadFiles(e.dataTransfer?.files)
}

// ── Right-click context menu ────────────────────────────────────────────
const ctxFile = ref(null)
const ctxPos  = ref({ x: 0, y: 0 })
function openContextMenu(f, e) {
  ctxFile.value = f
  ctxPos.value = { x: e.clientX, y: e.clientY }
}

async function onRename(f) {
  ctxFile.value = null
  const newName = await promptDialog({
    title: 'Rename file', inputLabel: 'Name', defaultValue: f.file_name,
  })
  if (!newName || !newName.trim() || newName.trim() === f.file_name) return
  try {
    await renameProjectFile(f.name, newName.trim())
    toast.success('Renamed')
    await load()
  } catch (e) {
    toast.error('Could not rename file', { description: e.message })
  }
}

async function onDelete(f) {
  ctxFile.value = null
  if (!await confirmDialog(`Delete "${f.file_name}"? This can't be undone.`, { danger: true })) return
  try {
    await deleteProjectFile(f.name)
    toast.success('File deleted')
    await load()
  } catch (e) {
    toast.error('Could not delete file', { description: e.message })
  }
}

// ── Preview / lightbox ────────────────────────────────────────────────
function openPreview(f) { preview.value = f }
function closePreview()  { preview.value = null }

function openTask(taskName) {
  if (!taskName) return
  store.openTaskDetail(taskName)
  closePreview()
}

function onKeyDown(e) { if (e.key === 'Escape') closePreview() }
onMounted(() => document.addEventListener('keydown', onKeyDown))
onUnmounted(() => document.removeEventListener('keydown', onKeyDown))

// Hide broken image and show fallback icon sibling if it exists
function onImgError(e) {
  const img = e.target
  if (img) img.style.display = 'none'
  const fallback = img?.nextElementSibling
  if (fallback) fallback.style.display = 'flex'
}

// ── Icon helpers ──────────────────────────────────────────────────────
const EXT_MAP = {
  pdf:  { label: 'PDF',  bg: '#FFEBE6', color: '#BF2600' },
  doc:  { label: 'DOC',  bg: '#DEEBFF', color: '#0052CC' },
  docx: { label: 'DOC',  bg: '#DEEBFF', color: '#0052CC' },
  xls:  { label: 'XLS',  bg: '#E3FCEF', color: '#006644' },
  xlsx: { label: 'XLS',  bg: '#E3FCEF', color: '#006644' },
  csv:  { label: 'CSV',  bg: '#E3FCEF', color: '#006644' },
  ppt:  { label: 'PPT',  bg: '#FFEBE6', color: '#BF2600' },
  pptx: { label: 'PPT',  bg: '#FFEBE6', color: '#BF2600' },
  png:  { label: 'IMG',  bg: '#EAE6FF', color: '#403294' },
  jpg:  { label: 'IMG',  bg: '#EAE6FF', color: '#403294' },
  jpeg: { label: 'IMG',  bg: '#EAE6FF', color: '#403294' },
  gif:  { label: 'IMG',  bg: '#EAE6FF', color: '#403294' },
  svg:  { label: 'SVG',  bg: '#EAE6FF', color: '#403294' },
  webp: { label: 'IMG',  bg: '#EAE6FF', color: '#403294' },
  zip:  { label: 'ZIP',  bg: '#FFFAE6', color: '#7A5800' },
  rar:  { label: 'RAR',  bg: '#FFFAE6', color: '#7A5800' },
  mp4:  { label: 'VID',  bg: '#FFF0B3', color: '#7A5800' },
  webm: { label: 'VID',  bg: '#FFF0B3', color: '#7A5800' },
  mov:  { label: 'VID',  bg: '#FFF0B3', color: '#7A5800' },
  txt:  { label: 'TXT',  bg: '#F4F5F7', color: '#5E6C84' },
  md:   { label: 'MD',   bg: '#F4F5F7', color: '#5E6C84' },
  json: { label: 'JSON', bg: '#E3FCEF', color: '#006644' },
}

function fileIconLabel(name) {
  return EXT_MAP[ext(name)]?.label || ext(name).toUpperCase().slice(0, 4) || 'FILE'
}
function fileIconStyle(name) {
  const e = EXT_MAP[ext(name)]
  return e ? { background: e.bg, color: e.color } : { background: 'var(--surface-secondary)', color: 'var(--muted)' }
}

// ── Formatters ────────────────────────────────────────────────────────
function fmtSize(bytes) {
  if (!bytes) return ''
  if (bytes < 1024)            return bytes + ' B'
  if (bytes < 1024 * 1024)     return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 / 1024).toFixed(1) + ' MB'
}

function fmtDate(d) {
  if (!d) return ''
  const dt   = new Date(d)
  const now  = Date.now()
  const diff = Math.floor((now - dt.getTime()) / 1000)
  if (diff < 60)         return 'just now'
  if (diff < 3600)       return Math.floor(diff / 60) + 'm ago'
  if (diff < 86400)      return Math.floor(diff / 3600) + 'h ago'
  if (diff < 86400 * 7)  return Math.floor(diff / 86400) + 'd ago'
  return dt.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
}
</script>

<style scoped>
.lb-enter-active, .lb-leave-active { transition: opacity 0.15s ease; }
.lb-enter-from, .lb-leave-to { opacity: 0; }
.lb-enter-active > div, .lb-leave-active > div { transition: transform 0.18s cubic-bezier(0.32,0.72,0,1); }
.lb-enter-from > div, .lb-leave-to > div { transform: scale(0.96); }

.fp-drop-overlay {
  position: fixed;
  inset: 0;
  z-index: var(--z-overlay);
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--backdrop);
  pointer-events: none;
}
.fp-drop-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 32px 40px;
  border: 2px dashed var(--accent);
  border-radius: var(--radius-xl);
  background: var(--overlay);
  color: var(--accent);
  font-size: 13px;
  font-weight: 600;
  box-shadow: var(--overlay-shadow);
}
</style>
