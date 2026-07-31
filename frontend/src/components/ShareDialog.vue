<template>
  <Teleport to="body">
    <Transition name="sd-bg">
      <div
        v-if="modelValue"
        class="fixed inset-0 z-50 flex items-center justify-center p-4 bp-overlay"
        style="background:rgba(0,0,0,0.28)"
        @mousedown.self="close"
      >
        <Transition name="sd-modal" appear>
          <div
            v-if="modelValue"
            class="bg-surface rounded-2xl w-full max-w-md overflow-hidden shadow-overlay"
          >
            <!-- Header -->
            <div class="flex items-center justify-between px-5 py-4">
              <div class="flex items-center gap-2.5">
                <div class="size-7 rounded-lg bg-accent-soft flex items-center justify-center">
                  <Share2 class="size-3.5 text-primary" />
                </div>
                <span class="text-[14px] font-semibold text-foreground">
                  {{ isTask ? 'Share task' : 'Share' }}
                </span>
              </div>
              <button
                class="size-7 flex items-center justify-center rounded-md text-muted hover:bg-default hover:text-foreground transition-colors"
                @click="close"
              >
                <X class="size-4" />
              </button>
            </div>

            <!-- Scope tabs (hidden in single-task mode) -->
            <div v-if="!isTask" class="px-5">
              <div class="inline-flex p-0.5 rounded-lg bg-default">
                <button
                  v-for="t in TABS" :key="t.value"
                  class="px-3 h-7 rounded-md text-[12.5px] font-medium transition-colors"
                  :class="scope === t.value ? 'bg-surface text-foreground shadow-xs' : 'text-muted hover:text-foreground'"
                  @click="setScope(t.value)"
                >{{ t.label }}</button>
              </div>
            </div>

            <p class="px-5 pt-3 text-[12px] text-muted leading-relaxed">
              {{ scopeDescription }}
            </p>

            <!-- Body -->
            <div class="px-5 py-4">

              <!-- Gated: needs Team+ -->
              <div v-if="!canShare" class="rounded-xl bg-default p-4 text-center">
                <Lock class="size-5 text-muted mx-auto mb-2" />
                <p class="text-[13px] font-medium text-foreground">
                  Public links are a {{ requiredPlan }} feature
                </p>
                <p class="text-[12px] text-muted mt-1 mb-3">
                  Share read-only views with clients and stakeholders who don't have an account.
                </p>
                <Button size="sm" color="primary" @click="goUpgrade">Upgrade to {{ requiredPlan }}</Button>
              </div>

              <template v-else>
                <!-- Existing live links -->
                <div v-if="loading" class="flex justify-center py-6">
                  <Spinner class="w-5 h-5 text-primary" />
                </div>

                <div v-else-if="links.length" class="space-y-2 mb-3">
                  <div
                    v-for="l in links" :key="l.name"
                    class="rounded-xl border border-border p-2.5"
                    :class="l.expired ? 'opacity-60' : ''"
                  >
                    <div class="flex items-center gap-2">
                      <div class="flex-1 min-w-0 flex items-center gap-1.5 h-8 px-2.5 rounded-lg bg-default">
                        <LinkIcon class="size-3.5 text-muted shrink-0" />
                        <span class="text-[12px] text-foreground truncate font-mono">{{ l.url }}</span>
                        <span v-if="l.access_level && l.access_level !== 'view'" class="text-[10px] font-semibold px-1.5 py-0.5 rounded-full shrink-0"
                          :class="l.access_level === 'edit' ? 'bg-accent-soft text-accent' : 'bg-default text-muted'"
                        >{{ l.access_level === 'edit' ? 'Edit' : 'Comment' }}</span>
                      </div>
                      <button
                        class="shrink-0 h-8 px-3 inline-flex items-center gap-1.5 rounded-lg text-[12px] font-medium transition-colors"
                        :class="copiedName === l.name ? 'bg-success-soft text-success' : 'bg-primary text-white hover:bg-primary-hover'"
                        @click="copy(l)"
                      >
                        <Check v-if="copiedName === l.name" class="size-3.5" />
                        <Copy v-else class="size-3.5" />
                        {{ copiedName === l.name ? 'Copied' : 'Copy' }}
                      </button>
                    </div>
                    <div class="flex items-center justify-between mt-2 px-0.5">
                      <span class="text-[11px] text-muted">
                        <template v-if="l.expired">Expired</template>
                        <template v-else-if="l.expires_on">Expires {{ fmtDate(l.expires_on) }}</template>
                        <template v-else>No expiry</template>
                        <span v-if="l.access_count"> · {{ l.access_count }} view{{ l.access_count === 1 ? '' : 's' }}</span>
                      </span>
                      <button class="text-[11px] text-muted hover:text-danger transition-colors" @click="revoke(l)">
                        Revoke
                      </button>
                    </div>
                  </div>
                </div>

                <p v-else-if="!loading" class="text-[12px] text-muted text-center py-4">
                  No active link yet. Create one below.
                </p>

                <!-- Create -->
                <div class="flex items-center gap-2 pt-1">
                  <Select v-model="accessLevel" size="sm" class="w-28">
                    <SelectItem value="view">View only</SelectItem>
                    <SelectItem v-if="isTask" value="comment">Comment</SelectItem>
                    <SelectItem v-if="isTask" value="edit">Can edit</SelectItem>
                  </Select>
                  <Select v-model="expiry" size="sm" class="w-28">
                    <SelectItem v-for="o in EXPIRY_OPTIONS" :key="o.value" :value="o.value">{{ o.label }}</SelectItem>
                  </Select>
                  <Button size="sm" color="primary" class="flex-1" :isLoading="creating" @click="create">
                    Create link
                  </Button>
                </div>
              </template>
            </div>
          </div>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Share2, X, Copy, Check, Lock, Link as LinkIcon } from 'lucide-vue-next'
import { Button, Spinner, Select, SelectItem } from '@/ui'
import { useEntitlementsStore } from '@/stores/entitlements'
import { createShareLink, listShareLinks, revokeShareLink } from '@/utils/api'
import { toast } from 'vue-sonner'

const props = defineProps({
  modelValue: Boolean,
  project:    { type: String, required: true },   // project name
  // When set, the dialog is in single-task mode (no tabs).
  task:       { type: String, default: null },
  taskTitle:  { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue'])

const router = useRouter()
const ent = useEntitlementsStore()

const TABS = [
  { value: 'board',   label: 'Share board' },
  { value: 'project', label: 'Share project' },
]
const EXPIRY_OPTIONS = [
  { value: '0',  label: 'No expiry' },
  { value: '7',  label: 'Expires in 7 days' },
  { value: '30', label: 'Expires in 30 days' },
  { value: '90', label: 'Expires in 90 days' },
]

const isTask  = computed(() => !!props.task)
const scope       = ref('board')
const accessLevel = ref('view')
const expiry      = ref('0')
const links       = ref([])
const loading = ref(false)
const creating = ref(false)
const copiedName = ref(null)

const canShare = computed(() => ent.can('share_links'))
const requiredPlan = computed(() => ent.requiredPlanFor('share_links'))

const scopeDescription = computed(() => {
  if (isTask.value) {
    if (accessLevel.value === 'edit') return 'Anyone with this link can update status, priority, and description — no account needed.'
    if (accessLevel.value === 'comment') return 'Anyone with this link can view and leave comments — no account needed.'
    return 'Anyone with this link can view this task read-only — no account needed.'
  }
  if (scope.value === 'project') return 'A read-only link to the whole project. No account needed.'
  return 'A read-only link to this board. No account needed.'
})

function setScope(s) {
  if (scope.value === s) return
  scope.value = s
  load()
}

async function load() {
  if (!canShare.value) return
  loading.value = true
  try {
    links.value = await listShareLinks(props.project, isTask.value ? 'task' : scope.value)
    // In task mode, only show links for this specific task.
    if (isTask.value) links.value = links.value.filter(l => l.task === props.task)
  } catch (e) {
    console.error('listShareLinks', e)
    links.value = []
  } finally {
    loading.value = false
  }
}

async function create() {
  creating.value = true
  try {
    const params = {
      project: props.project,
      scope: isTask.value ? 'task' : scope.value,
      access_level: accessLevel.value,
      expires_in_days: expiry.value === '0' ? null : Number(expiry.value),
    }
    if (isTask.value) params.task = props.task
    await createShareLink(params)
    await load()
    const labels = { view: 'View-only', comment: 'Comment', edit: 'Editable' }
    toast.success(`${labels[accessLevel.value] || 'View-only'} link created`)
  } catch (e) {
    if (e.upgradeRequired) toast.error(e.message)
    else toast.error(e.message || 'Could not create link')
  } finally {
    creating.value = false
  }
}

async function copy(l) {
  try { await navigator.clipboard.writeText(l.url) } catch {}
  copiedName.value = l.name
  setTimeout(() => { if (copiedName.value === l.name) copiedName.value = null }, 1800)
}

async function revoke(l) {
  if (!confirm('Revoke this link? Anyone using it will lose access immediately.')) return
  try {
    await revokeShareLink(l.name)
    links.value = links.value.filter(x => x.name !== l.name)
    toast.success('Link revoked')
  } catch (e) { toast.error(e.message || 'Could not revoke') }
}

function fmtDate(s) {
  try { return new Date(s).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }) }
  catch { return s }
}

function goUpgrade() {
  close()
  router.push('/workspace/pricing')
}

function close() { emit('update:modelValue', false) }

watch(() => props.modelValue, (v) => {
  if (v) {
    scope.value = 'board'
    expiry.value = '0'
    copiedName.value = null
    load()
  }
})
</script>

<style scoped>
.sd-bg-enter-active, .sd-bg-leave-active { transition: opacity 0.15s ease; }
.sd-bg-enter-from, .sd-bg-leave-to { opacity: 0; }
.sd-modal-enter-active { transition: opacity 0.15s ease, transform 0.15s cubic-bezier(0.16,1,0.3,1); }
.sd-modal-leave-active { transition: opacity 0.1s ease; }
.sd-modal-enter-from   { opacity: 0; transform: scale(0.96) translateY(6px); }
.sd-modal-leave-to     { opacity: 0; }
</style>
