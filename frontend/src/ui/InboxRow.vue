<template>
  <div
    :class="[
      'group relative flex items-center gap-3 px-4 h-14 border-b border-separator last:border-b-0 cursor-pointer transition-colors',
      item.unread ? 'bg-accent/[0.035] hover:bg-accent/[0.06]' : 'hover:bg-foreground/[0.04]',
    ]"
    @click="emit('click', item)"
  >
    <!-- Actor avatar, with a type badge (mention/assigned/review) overlaid on the corner -->
    <div class="relative shrink-0">
      <Avatar :name="item.actor || item.actorInitial || '?'" :color="item.actorColor" size="md" />
      <span
        class="absolute -bottom-0.5 -right-0.5 flex items-center justify-center size-4 rounded-full bg-overlay ring-2 ring-overlay"
        :class="TYPE_META[item.type]?.tint ?? TYPE_META.review.tint"
      >
        <component :is="TYPE_META[item.type]?.icon ?? TYPE_META.review.icon" :size="10" :stroke-width="2.5" />
      </span>
    </div>

    <!-- Body -->
    <p class="flex-1 text-sm text-muted truncate">
      <span :class="['text-foreground', item.unread ? 'font-semibold' : 'font-medium']">{{ item.actor }}</span>
      {{ ' ' + item.action + ' ' }}
      <span class="italic text-muted">{{ item.context }}</span>
    </p>

    <!-- Time -->
    <span class="shrink-0 text-xs text-muted tabular-nums">{{ item.time }}</span>

    <!-- Unread dot, right-aligned like a mail client's read-state marker -->
    <span v-if="item.unread" class="shrink-0 size-1.5 rounded-full bg-accent"></span>

    <!-- Mark as read (only shown when there's something to do) -->
    <button v-if="item.unread" type="button"
      class="shrink-0 p-1 rounded text-muted hover:text-success hover:bg-surface-secondary transition-colors opacity-0 group-hover:opacity-100"
      title="Mark as read"
      @click.stop="emit('menu', item)">
      <svg class="size-4" fill="none" stroke="currentColor" stroke-width="2.2" viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><path d="M5 13l4 4L19 7"/></svg>
    </button>
  </div>
</template>

<script setup>
import { AtSign, UserCheck, Eye } from 'lucide-vue-next'
import Avatar from './Avatar.vue'

defineProps({
  item: { type: Object, required: true },
  // item shape: { id, actor, actorInitial, actorColor, action, context, time, unread, type, task, project }
})
const emit = defineEmits(['click', 'menu'])

// One glance should tell you WHY something is in your inbox, not just THAT
// it is — a mention, an assignment, and a status/review update read
// identically today (same dot, same layout). Icon + tint per type gives
// each row a distinct silhouette, same idea as Attio's per-record-type
// iconography in its Calls/Activity lists.
const TYPE_META = {
  mention:  { icon: AtSign,    tint: 'text-accent' },
  assigned: { icon: UserCheck, tint: 'text-warning' },
  review:   { icon: Eye,       tint: 'text-info' },
}
</script>
