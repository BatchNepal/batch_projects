<template>
  <Modal :open="true" size="lg" @update:open="$emit('close')">
    <ModalHeader @close="$emit('close')">
      <h2 class="text-base font-semibold">Notification preferences</h2>
    </ModalHeader>

    <ModalBody class="space-y-3">
      <div v-if="loading" class="flex items-center justify-center py-8">
        <Loader2 class="size-5 animate-spin text-muted" />
      </div>

      <template v-else>
        <p class="text-sm text-muted">
          Channels are independent — keep in-app on while turning email off, or vice-versa.
        </p>

        <!-- ── In-app channel ─────────────────────────────────────── -->
        <section class="rounded-xl border border-border bg-surface shadow-sm">
          <div class="flex items-center gap-3 px-4 py-3.5">
            <span class="size-8 rounded-lg grid place-items-center bg-accent-soft text-accent-soft-foreground shrink-0">
              <Bell class="size-4" />
            </span>
            <div class="flex-1 min-w-0">
              <p class="text-sm font-semibold text-foreground leading-snug">In-app</p>
              <p class="text-[13px] text-muted leading-snug">Inbox bell + live updates inside BatchProjects</p>
            </div>
            <Switch :is-selected="!!prefs.inapp_enabled" @update:is-selected="toggle('inapp_enabled')" />
          </div>
        </section>

        <!-- ── Desktop push channel ───────────────────────────────── -->
        <section class="rounded-xl border border-border bg-surface shadow-sm">
          <div class="flex items-center gap-3 px-4 py-3.5">
            <span class="size-8 rounded-lg grid place-items-center bg-accent-soft text-accent-soft-foreground shrink-0">
              <MonitorSmartphone class="size-4" />
            </span>
            <div class="flex-1 min-w-0">
              <p class="text-sm font-semibold text-foreground leading-snug">Desktop push</p>
              <p class="text-[13px] text-muted leading-snug">Native notifications via ERPDesktop — instant even when this tab is closed</p>
            </div>
            <Switch :is-selected="!!prefs.desktop_enabled" @update:is-selected="toggle('desktop_enabled')" />
          </div>
        </section>

        <!-- ── Email channel ──────────────────────────────────────── -->
        <section class="rounded-xl border border-border bg-surface shadow-sm">
          <div class="flex items-center gap-3 px-4 py-3.5" :class="prefs.email_enabled && 'border-b border-separator'">
            <span class="size-8 rounded-lg grid place-items-center bg-accent-soft text-accent-soft-foreground shrink-0">
              <Mail class="size-4" />
            </span>
            <div class="flex-1 min-w-0">
              <p class="text-sm font-semibold text-foreground leading-snug">Email</p>
              <p class="text-[13px] text-muted leading-snug">Delivered to your inbox</p>
            </div>
            <Switch :is-selected="!!prefs.email_enabled" @update:is-selected="toggle('email_enabled')" />
          </div>

          <!-- Children only when the channel is on — no confusing dimmed toggles. -->
          <div v-if="prefs.email_enabled" class="px-4 py-4 space-y-5">
            <div>
              <p class="text-[11px] font-semibold uppercase tracking-wide text-muted mb-3">Notify me about</p>
              <div class="space-y-3">
                <PrefRow label="Assigned to you" description="When someone assigns a task to you" :value="prefs.email_assignment" @toggle="toggle('email_assignment')" />
                <PrefRow label="Comments" description="When someone comments on a task you're watching" :value="prefs.email_comment" @toggle="toggle('email_comment')" />
                <PrefRow label="Mentions" description="When someone @mentions you in a comment" :value="prefs.email_mention" @toggle="toggle('email_mention')" />
                <PrefRow label="Status changes" description="When a task you're watching changes status" :value="prefs.email_status_change" @toggle="toggle('email_status_change')" />
                <PrefRow label="Due date reminders" description="Daily reminder for tasks due soon or overdue" :value="prefs.email_due_reminder" @toggle="toggle('email_due_reminder')" />
              </div>
            </div>
            <div class="border-t border-separator" />
            <div>
              <p class="text-[11px] font-semibold uppercase tracking-wide text-muted mb-3">Digests</p>
              <div class="space-y-3">
                <PrefRow label="Daily digest" description="Morning summary of your open and overdue tasks" :value="prefs.email_digest" @toggle="toggle('email_digest')" />
                <PrefRow label="Weekly project summary" description="Mondays: project progress for leads and managers" :value="prefs.email_weekly_summary" @toggle="toggle('email_weekly_summary')" />
              </div>
            </div>
          </div>
          <div v-else class="px-4 py-3 text-[13px] text-muted">
            Email notifications are off. Turn this on to choose which emails you receive.
          </div>
        </section>
      </template>
    </ModalBody>

    <ModalFooter>
      <div class="flex items-center justify-between w-full">
        <p v-if="saved" class="text-[12px] text-success">Preferences saved.</p>
        <span v-else />
        <Button variant="solid" color="primary" size="sm" :isLoading="saving" @click="save">Save</Button>
      </div>
    </ModalFooter>
  </Modal>
</template>

<script setup>
import { ref, reactive, onMounted, defineComponent, h } from 'vue'
import { Loader2, Bell, Mail, MonitorSmartphone } from 'lucide-vue-next'
import { Modal, ModalHeader, ModalBody, ModalFooter, Button, Switch } from '@/ui'
import { getNotificationPreferences, updateNotificationPreferences } from '@/utils/api'

defineEmits(['close'])

const loading = ref(true)
const saving  = ref(false)
const saved   = ref(false)

const prefs = reactive({
  inapp_enabled:       1,
  desktop_enabled:     1,
  email_enabled:       1,
  email_assignment:    1,
  email_comment:       1,
  email_mention:       1,
  email_status_change: 1,
  email_due_reminder:  1,
  email_digest:        1,
  email_weekly_summary:1,
})

onMounted(async () => {
  try {
    const data = await getNotificationPreferences()
    Object.assign(prefs, data)
  } catch {}
  loading.value = false
})

function toggle(key) {
  prefs[key] = prefs[key] ? 0 : 1
  saved.value = false
}

async function save() {
  saving.value = true
  saved.value  = false
  try {
    const result = await updateNotificationPreferences({ ...prefs })
    Object.assign(prefs, result)
    saved.value = true
    setTimeout(() => { saved.value = false }, 3000)
  } catch {}
  saving.value = false
}

const PrefRow = defineComponent({
  props: ['label', 'description', 'value'],
  emits: ['toggle'],
  setup(props, { emit }) {
    return () =>
      h('div', { class: 'flex items-start justify-between gap-4' }, [
        h('div', { class: 'flex-1 min-w-0' }, [
          h('p', { class: 'text-sm text-foreground font-medium leading-snug' }, props.label),
          props.description
            ? h('p', { class: 'text-[13px] text-muted leading-snug mt-0.5' }, props.description)
            : null,
        ]),
        h(Switch, {
          isSelected: !!props.value,
          'onUpdate:isSelected': () => emit('toggle'),
        }),
      ])
  },
})
</script>
