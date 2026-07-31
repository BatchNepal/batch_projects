<template>
  <div class="ia-root">

    <!-- File list -->
    <div v-if="files.length" class="ia-list">
      <div v-for="f in files" :key="f.name || f._id" class="ia-file">
        <div class="ia-file-icon" :class="iconClass(f.file_name)">
          {{ iconLabel(f.file_name) }}
        </div>
        <div class="ia-file-info">
          <a
            :href="f.file_url"
            target="_blank"
            rel="noopener noreferrer"
            class="ia-file-name"
          >{{ f.file_name }}</a>
          <span class="ia-file-meta">{{ fmtSize(f.file_size) }}</span>
        </div>
        <div class="ia-file-actions">
          <a :href="f.file_url" target="_blank" download class="ia-action-btn" title="Download">
            <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
            </svg>
          </a>
          <button
            v-if="!readonly"
            class="ia-action-btn ia-action-btn--danger"
            title="Remove"
            @click="remove(f)"
          >
            <svg width="11" height="11" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
            </svg>
          </button>
        </div>
        <!-- Upload progress -->
        <div v-if="f._uploading" class="ia-progress">
          <div class="ia-progress-bar" :style="{ width: (f._progress || 0) + '%' }"/>
        </div>
      </div>
    </div>

    <!-- Drop zone -->
    <div
      v-if="!readonly"
      class="ia-drop"
      :class="{
        'ia-drop--active': isDragging,
        'ia-drop--compact': files.length > 0,
      }"
      @dragenter.prevent="isDragging = true"
      @dragover.prevent="isDragging = true"
      @dragleave.prevent="isDragging = false"
      @drop.prevent="onDrop"
      @click="$refs.fileInput.click()"
    >
      <input
        ref="fileInput"
        type="file"
        multiple
        class="ia-hidden-input"
        @change="onFileInput"
      />

      <template v-if="!files.length || isDragging">
        <div class="ia-drop-icon">
          <svg width="22" height="22" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M9 13h6m-3-3v6m5 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
          </svg>
        </div>
        <p class="ia-drop-text">
          <span class="ia-drop-link">Click to attach</span> or drag and drop
        </p>
        <p class="ia-drop-hint">Any file up to 10MB</p>
      </template>
      <template v-else>
        <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/>
        </svg>
        <span class="ia-drop-link">Attach more files</span>
      </template>
    </div>

    <!-- Error -->
    <p v-if="error" class="ia-error">{{ error }}</p>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { uploadAttachment, deleteAttachment } from '@/utils/api.js'
import { toast } from 'vue-sonner'

const props = defineProps({
  // Existing attachments from server: [{name, file_name, file_url, file_size}]
  modelValue: { type: Array, default: () => [] },
  // If provided, uploads go directly to this issue; otherwise buffered for submit
  issueName:  { type: String, default: null },
  readonly:   { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'queued'])

const isDragging = ref(false)
const error      = ref('')

// files = server attachments + pending uploads
const files = computed(() => props.modelValue)

// ── Upload ────────────────────────────────────────────────────────────────────
function onDrop(e) {
  isDragging.value = false
  handleFiles([...e.dataTransfer.files])
}
function onFileInput(e) {
  handleFiles([...e.target.files])
  e.target.value = ''
}

async function handleFiles(rawFiles) {
  error.value = ''
  const oversized = rawFiles.filter(f => f.size > 10 * 1024 * 1024)
  if (oversized.length) {
    error.value = `${oversized.map(f => f.name).join(', ')} exceeds 10MB limit.`
    return
  }

  for (const file of rawFiles) {
    if (props.issueName) {
      // Attached to existing issue — upload immediately
      const pending = {
        _id:        Math.random().toString(36).slice(2),
        file_name:  file.name,
        file_url:   '',
        file_size:  file.size,
        _uploading: true,
        _progress:  0,
      }
      emit('update:modelValue', [...props.modelValue, pending])

      try {
        const result = await uploadAttachment(file, 'BP Task', props.issueName)
        const updated = props.modelValue.map(f =>
          f._id === pending._id
            ? { name: result.name, file_name: result.file_name, file_url: result.file_url, file_size: result.file_size }
            : f
        )
        emit('update:modelValue', updated)
        toast.success(`${file.name} uploaded`)
      } catch (e) {
        emit('update:modelValue', props.modelValue.filter(f => f._id !== pending._id))
        toast.error(`Failed to upload ${file.name}`)
      }
    } else {
      // New issue — buffer the File object, emit for parent to upload after create
      emit('queued', file)
      // Show preview locally
      const preview = {
        _id:       Math.random().toString(36).slice(2),
        file_name: file.name,
        file_url:  URL.createObjectURL(file),
        file_size: file.size,
        _pending:  true,
        _file:     file,
      }
      emit('update:modelValue', [...props.modelValue, preview])
    }
  }
}

async function remove(f) {
  if (f._pending) {
    // Just remove from local list
    emit('update:modelValue', props.modelValue.filter(x => x._id !== f._id))
    return
  }
  try {
    await deleteAttachment(f.name)
    emit('update:modelValue', props.modelValue.filter(x => x.name !== f.name))
    toast.success('Removed')
  } catch { toast.error('Failed to remove attachment') }
}

// ── Helpers ───────────────────────────────────────────────────────────────────
const EXT_MAP = {
  pdf:  { label: 'PDF',  bg: '#FFEBE6', color: '#BF2600' },
  doc:  { label: 'DOC',  bg: '#DEEBFF', color: '#0052CC' },
  docx: { label: 'DOC',  bg: '#DEEBFF', color: '#0052CC' },
  xls:  { label: 'XLS',  bg: '#E3FCEF', color: '#006644' },
  xlsx: { label: 'XLS',  bg: '#E3FCEF', color: '#006644' },
  csv:  { label: 'CSV',  bg: '#E3FCEF', color: '#006644' },
  png:  { label: 'IMG',  bg: '#EAE6FF', color: '#403294' },
  jpg:  { label: 'IMG',  bg: '#EAE6FF', color: '#403294' },
  jpeg: { label: 'IMG',  bg: '#EAE6FF', color: '#403294' },
  gif:  { label: 'IMG',  bg: '#EAE6FF', color: '#403294' },
  svg:  { label: 'SVG',  bg: '#EAE6FF', color: '#403294' },
  zip:  { label: 'ZIP',  bg: '#FFFAE6', color: '#7A5800' },
  mp4:  { label: 'VID',  bg: '#FFF0B3', color: '#7A5800' },
  txt:  { label: 'TXT',  bg: 'var(--surface-secondary)', color: 'var(--muted)' },
}

function ext(name) { return (name || '').split('.').pop()?.toLowerCase() || '' }
function iconLabel(name) { return EXT_MAP[ext(name)]?.label || ext(name).toUpperCase().slice(0,3) || 'FILE' }
function iconClass(name) {
  const e = EXT_MAP[ext(name)]
  return e ? `ia-icon--custom` : ''
}
function iconStyle(name) {
  const e = EXT_MAP[ext(name)]
  return e ? { background: e.bg, color: e.color } : {}
}

function fmtSize(bytes) {
  if (!bytes) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}
</script>

<style scoped>
.ia-root { display: flex; flex-direction: column; gap: 8px; }

/* File list */
.ia-list { display: flex; flex-direction: column; gap: 4px; }
.ia-file {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 10px; border-radius: 8px;
  border: 1px solid var(--border); background: var(--surface-secondary);
  position: relative; overflow: hidden;
  transition: background .1s;
}
.ia-file:hover { background: var(--surface-secondary); }

.ia-file-icon {
  width: 32px; height: 32px; border-radius: 6px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  font-size: 9px; font-weight: 700; letter-spacing: 0.03em;
  background: var(--border); color: var(--muted);
}

.ia-file-info { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.ia-file-name {
  font-size: 13px; font-weight: 500; color: var(--foreground);
  text-decoration: none; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.ia-file-name:hover { color: var(--foreground); text-decoration: underline; }
.ia-file-meta { font-size: 12px; color: var(--muted); }

.ia-file-actions { display: flex; align-items: center; gap: 3px; flex-shrink: 0; }
.ia-action-btn {
  display: flex; align-items: center; justify-content: center;
  width: 28px; height: 28px; border: none; background: none;
  color: var(--muted); border-radius: 6px; cursor: pointer;
  text-decoration: none; transition: background .1s, color .1s;
}
.ia-action-btn:hover { background: var(--border); color: var(--foreground); }
.ia-action-btn--danger:hover { background: var(--danger-soft); color: var(--danger); }

.ia-progress {
  position: absolute; bottom: 0; left: 0; right: 0;
  height: 2px; background: var(--border);
}
.ia-progress-bar { height: 100%; background: var(--foreground); transition: width .2s; }

/* Drop zone */
.ia-drop {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 6px; padding: 22px 16px;
  border: 1px dashed var(--border); border-radius: 8px;
  background: var(--surface-secondary); cursor: pointer;
  transition: border-color .15s, background .15s;
  user-select: none;
}
.ia-drop:hover, .ia-drop--active {
  border-color: var(--muted); background: var(--surface-secondary);
}
.ia-drop--active { border-style: solid; }

.ia-drop--compact {
  flex-direction: row; padding: 12px 16px; gap: 8px;
  justify-content: flex-start;
}

.ia-drop-icon { color: var(--muted); }
.ia-drop--active .ia-drop-icon,
.ia-drop:hover .ia-drop-icon { color: var(--muted); }

.ia-drop-text { font-size: 13px; color: var(--muted); margin: 0; text-align: center; }
.ia-drop-hint { font-size: 12px; color: var(--muted); margin: 0; }
.ia-drop-link { color: var(--foreground); font-weight: 600; text-decoration: underline;}
.ia-drop:hover .ia-drop-link { color: var(--accent); }
.ia-drop--compact .ia-drop-link { font-size: 13px; }

.ia-hidden-input { display: none; }
.ia-error { font-size: 12px; color: var(--danger); margin: 0; }
</style>