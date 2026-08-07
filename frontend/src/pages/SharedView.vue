<template>
  <div class="min-h-full bg-background flex flex-col">

    <!-- Top bar -->
    <header class="shrink-0 bg-surface border-b border-border">
      <div class="max-w-[1600px] mx-auto w-full px-5 h-14 flex items-center justify-between gap-4">
        <div class="flex items-center gap-2.5 min-w-0">
          <ProjectAvatar v-if="data?.project" :theme="data.project.theme" :seed="data.project.key" size="md" />
          <div class="min-w-0">
            <p class="text-[14px] font-semibold text-foreground truncate leading-tight">
              {{ data?.project?.project_name || 'Shared view' }}
            </p>
            <p class="text-[11px] text-muted leading-tight">{{ scopeLabel }}</p>
          </div>
        </div>
        <span class="shrink-0 inline-flex items-center gap-1.5 h-7 px-2.5 rounded-full bg-default text-[11.5px] font-medium text-muted">
          <template v-if="data?.access_level === 'comment'">
            <MessageSquare class="size-3.5" /> Can comment
          </template>
          <template v-else>
            <Eye class="size-3.5" /> View only
          </template>
        </span>
      </div>
    </header>

    <!-- Loading -->
    <div v-if="loading" class="flex-1 flex items-center justify-center">
      <Spinner class="w-6 h-6 text-primary" />
    </div>

    <!-- Error (invalid / revoked / expired) -->
    <div v-else-if="error" class="flex-1 flex items-center justify-center p-6">
      <div class="text-center max-w-sm">
        <div class="size-12 rounded-2xl bg-default flex items-center justify-center mx-auto mb-4">
          <LinkOff class="size-6 text-muted" />
        </div>
        <h1 class="text-[16px] font-semibold text-foreground">{{ error }}</h1>
        <p class="text-[13px] text-muted mt-1.5">
          Ask whoever shared this link to send you a new one.
        </p>
      </div>
    </div>

    <!-- Content -->
    <main v-else class="flex-1 overflow-auto">
      <div class="max-w-[1600px] mx-auto w-full p-5">

        <!-- BOARD / PROJECT scope → read-only kanban -->
        <template v-if="data.scope !== 'task'">
          <p v-if="data.project?.description" class="text-[13px] text-muted mb-4 max-w-2xl">
            {{ data.project.description }}
          </p>
          <div class="flex gap-3 overflow-x-auto pb-4">
            <div v-for="col in data.workflow_states" :key="col.name"
                 class="shrink-0 w-[300px] bg-surface-secondary rounded-sm flex flex-col">
              <div class="flex items-center gap-2 px-3.5 py-3">
                <span class="w-2.5 h-2.5 rounded-full shrink-0" :style="{ background: col.color || 'var(--muted)' }" />
                <span class="text-[13px] font-semibold text-foreground">{{ col.name }}</span>
                <span class="text-[12px] text-muted">{{ (data.board[col.name] || []).length }}</span>
              </div>
              <div class="px-2.5 pb-2.5 space-y-2 overflow-y-auto">
                <div v-for="t in (data.board[col.name] || [])" :key="t.name"
                     class="bg-surface rounded-[7px] border border-border p-3">
                  <div class="flex items-center gap-1.5 mb-1.5">
                    <span class="text-[11px] font-mono text-muted">{{ t.task_key }}</span>
                    <PriorityDot :priority="t.priority" />
                  </div>
                  <p class="text-[13px] text-foreground leading-snug">{{ t.title }}</p>
                  <div v-if="t.labels?.length || t.assignees?.length" class="flex items-center justify-between mt-2.5 gap-2">
                    <div class="flex flex-wrap gap-1 min-w-0">
                      <span v-for="l in t.labels?.slice(0,2)" :key="l.label || l"
                            class="inline-flex items-center gap-1 px-1.5 h-5 rounded text-[10.5px] font-medium bg-default text-muted">
                        <span v-if="l.color" class="w-1.5 h-1.5 rounded-full" :style="{ background: l.color }" />
                        {{ l.label || l }}
                      </span>
                    </div>
                    <div class="flex -space-x-1.5 shrink-0">
                      <span v-for="a in t.assignees?.slice(0,3)" :key="a.user"
                            class="w-5 h-5 rounded-full ring-2 ring-surface flex items-center justify-center text-[9px] font-semibold text-white"
                            :style="{ background: avatarColor(a.user) }" :title="a.full_name">
                        {{ initials(a.full_name) }}
                      </span>
                    </div>
                  </div>
                </div>
                <p v-if="!(data.board[col.name] || []).length" class="text-[12px] text-muted text-center py-4">No tasks</p>
              </div>
            </div>
          </div>
        </template>

        <!-- TASK scope → read-only task -->
        <template v-else>
          <div class="max-w-2xl mx-auto bg-surface rounded-lg border border-border overflow-hidden">
            <div class="p-6">
              <div class="flex items-center gap-2 mb-3">
                <span class="text-[12px] font-mono text-muted">{{ data.task.task_key }}</span>
                <span class="inline-flex items-center gap-1.5 h-6 px-2 rounded-md text-[12px] font-medium text-white"
                      :style="{ background: data.task.status_color }">{{ data.task.status }}</span>
                <PriorityDot :priority="data.task.priority" />
              </div>
              <h1 class="text-[20px] font-semibold text-foreground leading-snug">{{ data.task.title }}</h1>

              <div v-if="data.task.assignees?.length || data.task.due_date" class="flex items-center gap-5 mt-4">
                <div v-if="data.task.assignees?.length" class="flex items-center gap-2">
                  <span class="text-[12px] text-muted">Assignees</span>
                  <div class="flex -space-x-1.5">
                    <span v-for="a in data.task.assignees" :key="a.user"
                          class="w-6 h-6 rounded-full ring-2 ring-surface flex items-center justify-center text-[10px] font-semibold text-white"
                          :style="{ background: avatarColor(a.user) }" :title="a.full_name">{{ initials(a.full_name) }}</span>
                  </div>
                </div>
                <div v-if="data.task.due_date" class="flex items-center gap-1.5 text-[12px] text-muted">
                  <Calendar class="size-3.5" /> Due {{ fmtDate(data.task.due_date) }}
                </div>
              </div>

              <div v-if="data.task.description" class="prose prose-sm max-w-none mt-5 text-[13.5px] text-foreground leading-relaxed"
                   v-html="data.task.description" />

              <!-- Guest edit controls (access_level === 'edit') -->
              <div v-if="data.access_level === 'edit'" class="border-t border-border mt-5 pt-5">
                <p class="text-[12px] font-semibold text-muted uppercase tracking-wider mb-3">Edit task</p>
                <div class="space-y-3">
                  <div>
                    <label class="text-[12px] text-muted">Status</label>
                    <select v-model="editStatus" class="hui-field w-full mt-1 py-1.5 px-2.5 text-[13px] rounded-md">
                      <option v-for="s in data.task.workflow_states" :key="s" :value="s">{{ s }}</option>
                    </select>
                  </div>
                  <div>
                    <label class="text-[12px] text-muted">Priority</label>
                    <select v-model="editPriority" class="hui-field w-full mt-1 py-1.5 px-2.5 text-[13px] rounded-md">
                      <option v-for="p in PRIORITIES" :key="p.value" :value="p.value">{{ p.label }}</option>
                    </select>
                  </div>
                  <div>
                    <label class="text-[12px] text-muted">Description</label>
                    <textarea v-model="editDescription" rows="4"
                      class="hui-field w-full mt-1 py-2 px-3 text-[13px] text-foreground rounded-md"
                      placeholder="Update description…" />
                  </div>
                  <div class="flex items-center justify-between gap-2">
                    <p v-if="editError" class="text-[11.5px] text-danger">{{ editError }}</p>
                    <span v-else />
                    <Button size="sm" color="primary" :isLoading="saving" @click="submitEdit">
                      Save changes
                    </Button>
                  </div>
                </div>
              </div>
            </div>

            <div v-if="data.task.subtasks?.length" class="border-t border-border px-6 py-4">
              <p class="text-[12px] font-semibold text-muted uppercase tracking-wider mb-2">Subtasks</p>
              <div class="space-y-1.5">
                <div v-for="s in data.task.subtasks" :key="s.name" class="flex items-center gap-2.5">
                  <span class="w-2 h-2 rounded-full shrink-0" :style="{ background: s.status_color }" />
                  <span class="text-[12px] font-mono text-muted">{{ s.task_key }}</span>
                  <span class="text-[13px] text-foreground truncate">{{ s.title }}</span>
                </div>
              </div>
            </div>

            <div v-if="data.access_level === 'comment' || data.task.comments?.length"
                 class="border-t border-border px-6 py-4">
              <p class="text-[12px] font-semibold text-muted uppercase tracking-wider mb-3">Comments</p>

              <div v-if="data.task.comments?.length" class="space-y-3 mb-4">
                <div v-for="c in data.task.comments" :key="c.name" class="text-[13px]">
                  <div class="flex items-center gap-1.5 flex-wrap">
                    <span class="font-semibold text-foreground">
                      {{ c.user === 'Guest' ? (c.guest_name || 'Guest') : (c.full_name || c.user) }}
                    </span>
                    <span v-if="c.user === 'Guest'" class="text-[11px] text-muted">(via share link)</span>
                    <span class="text-[11px] text-muted">· {{ fmtDateTime(c.creation) }}</span>
                  </div>
                  <p class="text-foreground leading-relaxed mt-0.5 whitespace-pre-wrap">{{ c.comment_text }}</p>
                </div>
              </div>
              <p v-else class="text-[12px] text-muted mb-4">No comments yet.</p>

              <div v-if="data.access_level === 'comment'" class="space-y-2">
                <Input v-model="guestName" placeholder="Your name" size="sm" class="max-w-[200px]" />
                <textarea
                  v-model="commentText"
                  rows="3"
                  placeholder="Write a comment…"
                  class="hui-field w-full py-2 px-3 text-[13px] text-foreground placeholder:text-[var(--field-placeholder)]"
                />
                <div class="flex items-center justify-between gap-2">
                  <p v-if="postError" class="text-[11.5px] text-danger">{{ postError }}</p>
                  <span v-else />
                  <Button size="sm" color="primary" :disabled="!commentText.trim() || posting"
                          :isLoading="posting" @click="submitComment">
                    Post comment
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </template>
      </div>
    </main>

    <!-- Brand footer -->
    <footer class="shrink-0 py-3 text-center">
      <span class="text-[11px] text-muted">Shared with <span class="font-semibold text-foreground">BatchProjects</span></span>
    </footer>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, h } from 'vue'
import { useRoute } from 'vue-router'
import { Eye, Calendar, Link2Off as LinkOff, MessageSquare } from 'lucide-vue-next'
import { getShared, addGuestComment, updateSharedTask } from '@/utils/api'
import Spinner from '@/ui/Spinner.vue'
import { Input, Button, ProjectAvatar } from '@/ui'
import { PRIORITIES } from '@/utils/constants.js'

const route = useRoute()
const loading = ref(true)
const error = ref('')
const data = ref(null)

const GUEST_NAME_KEY = 'bp_guest_comment_name'
const guestName = ref(sessionStorage.getItem(GUEST_NAME_KEY) || '')
const commentText = ref('')
const posting = ref(false)
const postError = ref('')

async function submitComment() {
  const text = commentText.value.trim()
  if (!text || posting.value) return
  posting.value = true
  postError.value = ''
  try {
    sessionStorage.setItem(GUEST_NAME_KEY, guestName.value.trim())
    const res = await addGuestComment(route.params.token, text, guestName.value.trim())
    data.value.task.comments = data.value.task.comments || []
    data.value.task.comments.push({
      name: res.activity,
      user: 'Guest',
      guest_name: res.guest_name,
      comment_text: text,
      creation: res.creation,
    })
    commentText.value = ''
  } catch (e) {
    postError.value = e.message || "Couldn't post comment."
  } finally {
    posting.value = false
  }
}

// ── Guest task edit state ─────────────────────────────────────────────────
const saving = ref(false)
const editError = ref('')
const editStatus = ref('')
const editPriority = ref('')
const editDescription = ref('')

// Seed edit fields from loaded task data
function seedEditFields() {
  if (data.value?.task) {
    editStatus.value = data.value.task.status || ''
    editPriority.value = data.value.task.priority || 'Medium'
    editDescription.value = data.value.task.description || ''
  }
}

async function submitEdit() {
  if (saving.value) return
  saving.value = true
  editError.value = ''
  try {
    const fields = {
      status: editStatus.value,
      priority: editPriority.value,
      description: editDescription.value,
    }
    await updateSharedTask(route.params.token, data.value.task.name, fields)
    // Update local display
    if (data.value.task) {
      data.value.task.status = editStatus.value
      data.value.task.priority = editPriority.value
      data.value.task.description = editDescription.value
    }
  } catch (e) {
    editError.value = e.message || 'Failed to save changes.'
  } finally {
    saving.value = false
  }
}

const scopeLabel = computed(() => {
  const s = data.value?.scope
  if (s === 'task') return 'Shared task · read-only'
  if (s === 'project') return 'Shared project · read-only'
  return 'Shared board · read-only'
})

onMounted(async () => {
  try {
    data.value = await getShared(route.params.token)
    seedEditFields()
  } catch (e) {
    error.value = e.message || 'This link is invalid.'
  } finally {
    loading.value = false
  }
})

const COLORS = ['#225DFB','#7C3AED','#059669','#DC2626','#D97706','#0891B2','#BE185D','#9333EA']
function avatarColor(seed) {
  const k = seed || ''
  let hsh = 0
  for (let i = 0; i < k.length; i++) hsh = k.charCodeAt(i) + ((hsh << 5) - hsh)
  return COLORS[Math.abs(hsh) % COLORS.length]
}
function initials(name) {
  return (name || '?').split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2)
}
function fmtDate(s) {
  try { return new Date(s).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) }
  catch { return s }
}
function fmtDateTime(s) {
  try { return new Date(s).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) }
  catch { return s }
}

// Tiny inline priority dot (avoids pulling the editable PriorityIcon).
const PRIORITY_COLOR = { Urgent: '#DC2626', High: '#EA580C', Medium: '#D97706', Low: '#0891B2', Lowest: '#9CA3AF' }
const PriorityDot = (props) => h('span', {
  class: 'inline-block w-2 h-2 rounded-full shrink-0',
  style: { background: PRIORITY_COLOR[props.priority] || 'var(--muted)' },
  title: props.priority || '',
})
PriorityDot.props = ['priority']
</script>
