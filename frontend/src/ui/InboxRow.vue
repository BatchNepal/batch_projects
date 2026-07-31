<template>
  <div
    :class="[
      'group flex items-center gap-3 px-4 h-14 border-b border-separator last:border-b-0 cursor-pointer transition-colors border-l-2',
      item.unread ? 'border-l-accent hover:bg-surface-secondary' : 'border-l-transparent hover:bg-surface-secondary',
    ]"
    @click="emit('click', item)"
  >
    <!-- Unread dot -->
    <span class="shrink-0 size-1.5 rounded-full transition-colors"
      :class="item.unread ? 'bg-accent' : 'bg-transparent'"></span>

    <!-- Actor avatar -->
    <Avatar :name="item.actor || item.actorInitial || '?'" :color="item.actorColor" size="md" />

    <!-- Body -->
    <p class="flex-1 text-sm text-muted truncate">
      <span class="font-semibold text-foreground">{{ item.actor }}</span>
      {{ ' ' + item.action + ' ' }}
      <span class="italic text-muted">{{ item.context }}</span>
    </p>

    <!-- Time -->
    <span class="shrink-0 text-xs text-muted tabular-nums">{{ item.time }}</span>

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
import Avatar from './Avatar.vue'

defineProps({
  item: { type: Object, required: true },
  // item shape: { id, actor, actorInitial, actorColor, action, context, time, unread, type, task, project }
})
const emit = defineEmits(['click', 'menu'])
</script>
