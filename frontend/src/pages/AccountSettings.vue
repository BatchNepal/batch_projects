<template>
  <div class="flex flex-col min-h-full bg-background">
    <!-- Page header -->
    <div class="px-8 pt-8 pb-6 border-b border-border">
      <h1 class="text-xl font-semibold text-foreground">Account settings</h1>
      <p class="text-[13px] text-muted mt-1">Manage your profile and notification preferences.</p>
    </div>

    <div class="flex flex-col gap-8 px-8 py-8 max-w-2xl">

      <!-- Profile -->
      <section>
        <h2 class="text-[13px] font-semibold text-foreground mb-4">Profile</h2>
        <div class="bg-surface shadow-surface rounded-lg p-5 space-y-4">
          <div class="flex items-center gap-4">
            <div class="w-12 h-12 rounded-full bg-accent-soft flex items-center justify-center text-accent text-lg font-semibold shrink-0 ring-1 ring-border">
              {{ userInitials }}
            </div>
            <div class="min-w-0">
              <p class="text-[14px] font-semibold text-foreground truncate">{{ userName }}</p>
              <p class="text-[12px] text-muted truncate">{{ userEmail }}</p>
            </div>
          </div>
          <div class="pt-2 border-t border-border">
            <a
              :href="`/app/user/${encodeURIComponent(userEmail)}`"
              target="_blank"
              class="inline-flex items-center gap-1.5 text-[13px] text-primary hover:underline"
            >
              Edit profile in Frappe
              <ExternalLink class="size-3" />
            </a>
          </div>
        </div>
      </section>

      <!-- Appearance -->
      <section>
        <h2 class="text-[13px] font-semibold text-foreground mb-4">Appearance</h2>
        <div class="bg-surface shadow-surface rounded-lg p-5">
          <div class="flex items-start justify-between gap-6">
            <div class="min-w-0">
              <p class="text-[13px] font-medium text-foreground">Interface density</p>
              <p class="text-[12px] text-muted mt-0.5 leading-relaxed">
                Comfortable enlarges the whole interface. Compact is denser — more on screen.
              </p>
            </div>
            <div class="shrink-0 inline-flex p-0.5 rounded-lg bg-default">
              <button
                v-for="opt in DENSITY_OPTIONS" :key="opt.value"
                type="button"
                class="px-3 h-7 rounded-[6px] text-[13px] font-medium transition-colors duration-90 ease-out"
                :class="density === opt.value
                  ? 'bg-surface text-foreground shadow-xs'
                  : 'text-muted hover:text-foreground'"
                @click="setDensity(opt.value)">
                {{ opt.label }}
              </button>
            </div>
          </div>
        </div>
      </section>

      <!-- Notification preferences -->
      <section>
        <h2 class="text-[13px] font-semibold text-foreground mb-4">Notifications</h2>
        <div class="bg-surface shadow-surface rounded-lg divide-y divide-border">

          <div v-if="loadingPrefs" class="flex justify-center py-8">
            <Loader2 class="size-5 animate-spin text-muted" />
          </div>

          <template v-else>
            <!-- In-app -->
            <div class="px-5 py-4">
              <p class="text-[12px] font-semibold uppercase tracking-wider text-muted mb-3">In-app</p>
              <PrefRow
                label="In-app notifications"
                description="Show a badge and inbox entries for activity on your tasks."
                :value="prefs.inapp_enabled"
                @toggle="toggle('inapp_enabled')"
              />
            </div>

            <!-- Desktop push -->
            <div class="px-5 py-4">
              <p class="text-[12px] font-semibold uppercase tracking-wider text-muted mb-3">Desktop push</p>
              <PrefRow
                label="Desktop push notifications"
                description="Native OS notifications via ERPDesktop — delivered instantly even when this tab is closed."
                :value="prefs.desktop_enabled"
                @toggle="toggle('desktop_enabled')"
              />
            </div>

            <!-- Email master -->
            <div class="px-5 py-4">
              <div class="flex items-center justify-between mb-3">
                <p class="text-[12px] font-semibold uppercase tracking-wider text-muted">Email</p>
                <Switch :model-value="!!prefs.email_enabled" @update:model-value="toggle('email_enabled')" />
              </div>
              <div class="space-y-3" :class="!prefs.email_enabled && 'opacity-40 pointer-events-none'">
                <PrefRow
                  label="Assignments"
                  description="When someone assigns a task to you."
                  :value="prefs.email_assignment"
                  @toggle="toggle('email_assignment')"
                />
                <PrefRow
                  label="Comments"
                  description="When someone comments on a task you're watching."
                  :value="prefs.email_comment"
                  @toggle="toggle('email_comment')"
                />
                <PrefRow
                  label="Mentions"
                  description="When someone @mentions you."
                  :value="prefs.email_mention"
                  @toggle="toggle('email_mention')"
                />
                <PrefRow
                  label="Status changes"
                  description="When a task you're watching moves to a new status."
                  :value="prefs.email_status_change"
                  @toggle="toggle('email_status_change')"
                />
                <PrefRow
                  label="Due date reminders"
                  description="Daily alert for tasks due within 2 days or already overdue."
                  :value="prefs.email_due_reminder"
                  @toggle="toggle('email_due_reminder')"
                />
              </div>
            </div>

            <!-- Digests -->
            <div class="px-5 py-4">
              <p class="text-[12px] font-semibold uppercase tracking-wider text-muted mb-3">Digests</p>
              <div class="space-y-3" :class="!prefs.email_enabled && 'opacity-40 pointer-events-none'">
                <PrefRow
                  label="Daily digest"
                  description="Morning summary of your open and overdue tasks."
                  :value="prefs.email_digest"
                  @toggle="toggle('email_digest')"
                />
                <PrefRow
                  label="Weekly project summary"
                  description="Sent Mondays to project leads and managers."
                  :value="prefs.email_weekly_summary"
                  @toggle="toggle('email_weekly_summary')"
                />
              </div>
            </div>
          </template>
        </div>

        <div class="flex items-center gap-3 mt-4">
          <Button variant="solid" color="primary" size="sm" :isLoading="savingPrefs" @click="savePrefs">
            Save preferences
          </Button>
          <span v-if="prefsSaved" class="text-[12px] text-success">Saved.</span>
        </div>
      </section>

      <!-- Muted items -->
      <section>
        <h2 class="text-[13px] font-semibold text-foreground mb-1">Muted items</h2>
        <p class="text-[13px] text-muted mb-4">
          Items you muted won't send notifications regardless of your settings above.
          Unmute from the task or project context menu.
        </p>
        <div v-if="loadingMutes" class="text-[13px] text-muted">Loading…</div>
        <div v-else-if="!muted.tasks.length && !muted.projects.length" class="text-[13px] text-muted">
          No muted items.
        </div>
        <div v-else class="bg-surface shadow-surface rounded-lg divide-y divide-border">
          <div
            v-for="task in muted.tasks"
            :key="'t-' + task"
            class="flex items-center justify-between px-4 py-3 text-[13px]"
          >
            <span class="font-mono text-muted">{{ task }}</span>
            <button
              class="text-[12px] text-muted hover:text-foreground transition-colors"
              @click="unmute({ task })"
            >
              Unmute
            </button>
          </div>
          <div
            v-for="proj in muted.projects"
            :key="'p-' + proj"
            class="flex items-center justify-between px-4 py-3 text-[13px]"
          >
            <span class="text-foreground">{{ projectLabel(proj) }}</span>
            <button
              class="text-[12px] text-muted hover:text-foreground transition-colors"
              @click="unmute({ project: proj })"
            >
              Unmute
            </button>
          </div>
        </div>
      </section>

    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, defineComponent, h } from 'vue'
import { ExternalLink, Loader2 } from 'lucide-vue-next'
import { Button, Switch } from '@/ui'
import {
  getNotificationPreferences,
  updateNotificationPreferences,
  getMutedItems,
  setMute,
} from '@/utils/api'
import { useProjectStore } from '@/stores/project'
import { useDensity } from '@/composables/useDensity'

const store = useProjectStore()

// Appearance — interface density
const { density, setDensity } = useDensity()
const DENSITY_OPTIONS = [
  { value: 'comfortable', label: 'Comfortable' },
  { value: 'compact',     label: 'Compact' },
]

const userName = computed(
  () => store.currentUser?.fullname || store.currentUser?.user
        || window?.frappe?.session?.user_fullname || window?.frappe?.session?.user || 'User'
)
const userEmail = computed(() => store.currentUser?.user || window?.frappe?.session?.user || '')
const userInitials = computed(() =>
  userName.value.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2)
)

function projectLabel(name) {
  return store.projects.find(p => p.name === name)?.project_name || name
}

// ── Preferences ──────────────────────────────────────────────────────────
const loadingPrefs = ref(true)
const savingPrefs  = ref(false)
const prefsSaved   = ref(false)

const prefs = reactive({
  inapp_enabled:        1,
  desktop_enabled:      1,
  email_enabled:        1,
  email_assignment:     1,
  email_comment:        1,
  email_mention:        1,
  email_status_change:  1,
  email_due_reminder:   1,
  email_digest:         1,
  email_weekly_summary: 1,
})

onMounted(async () => {
  try {
    const data = await getNotificationPreferences()
    Object.assign(prefs, data)
  } catch {}
  loadingPrefs.value = false

  try {
    const data = await getMutedItems()
    Object.assign(muted, data)
  } catch {}
  loadingMutes.value = false

  if (!store.projects.length) store.fetchProjects().catch(() => {})
})

function toggle(key) {
  prefs[key] = prefs[key] ? 0 : 1
  prefsSaved.value = false
}

async function savePrefs() {
  savingPrefs.value = true
  prefsSaved.value  = false
  try {
    const result = await updateNotificationPreferences({ ...prefs })
    Object.assign(prefs, result)
    prefsSaved.value = true
    setTimeout(() => { prefsSaved.value = false }, 3000)
  } catch {}
  savingPrefs.value = false
}

// ── Muted items ───────────────────────────────────────────────────────────
const loadingMutes = ref(true)
const muted = reactive({ tasks: [], projects: [] })

async function unmute({ task = null, project = null }) {
  try {
    await setMute({ task, project, muted: 0 })
    if (task)    muted.tasks    = muted.tasks.filter(t => t !== task)
    if (project) muted.projects = muted.projects.filter(p => p !== project)
  } catch {}
}

// ── PrefRow sub-component ─────────────────────────────────────────────────
const PrefRow = defineComponent({
  props: ['label', 'description', 'value'],
  emits: ['toggle'],
  setup(props, { emit }) {
    return () =>
      h('div', { class: 'flex items-start justify-between gap-4' }, [
        h('div', { class: 'flex-1' }, [
          h('p', { class: 'text-[13px] text-foreground' }, props.label),
          props.description
            ? h('p', { class: 'text-[12px] text-muted mt-0.5' }, props.description)
            : null,
        ]),
        h(Switch, {
          modelValue: !!props.value,
          'onUpdate:modelValue': () => emit('toggle'),
        }),
      ])
  },
})
</script>
