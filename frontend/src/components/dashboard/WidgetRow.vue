<template>
  <div class="w-row" @click="$emit('click')">
    <div class="w-row-main">
      <p class="w-row-title">{{ title }}</p>
      <div v-if="chips.length || avatars.length" class="w-row-meta">
        <Chip v-for="(c, i) in chips" :key="i" size="sm" variant="flat" :color="c.color" :title="c.title">{{ c.text }}</Chip>
        <div v-if="avatars.length" class="w-row-avatars">
          <Avatar v-for="a in avatars.slice(0, 3)" :key="a.full_name" :name="a.full_name" :src="a.user_image" size="xs" class="ring-2 ring-white shrink-0" />
          <div v-if="avatars.length > 3" class="w-row-avatar-overflow">+{{ avatars.length - 3 }}</div>
        </div>
      </div>
    </div>
    <span v-if="dateLabel" class="w-row-date" :class="dateClass">{{ dateLabel }}</span>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Chip, Avatar } from '@/ui'

// Flat row layout: title left, chips + avatar(s) second line, date
// right-aligned (absent entirely when no date is configured — no
// card border/shadow between rows, a hairline separator only (see
// .w-row + .w-row scoped rule). Shared by ColumnWidget.vue's BP Task and
// generic-doctype paths alike.
const props = defineProps({
  title: { type: String, required: true },
  chips: { type: Array, default: () => [] },       // [{ text, color, title }]
  avatars: { type: Array, default: () => [] },     // [{ full_name, user_image }]
  date: { type: String, default: null },           // ISO date/datetime or null
})
defineEmits(['click'])

function isOverdue(d) {
  const due = new Date(d); due.setHours(0, 0, 0, 0)
  const today = new Date(); today.setHours(0, 0, 0, 0)
  return due < today
}
function isDueSoon(d) {
  if (isOverdue(d)) return false
  const due = new Date(d); due.setHours(0, 0, 0, 0)
  const today = new Date(); today.setHours(0, 0, 0, 0)
  const diff = Math.round((due - today) / 86400000)
  return diff >= 0 && diff <= 2
}
const dateClass = computed(() => {
  if (!props.date) return ''
  if (isOverdue(props.date)) return 'w-row-date-overdue'
  if (isDueSoon(props.date)) return 'w-row-date-soon'
  return 'w-row-date-normal'
})
const dateLabel = computed(() => {
  if (!props.date) return ''
  const d = new Date(props.date)
  const today = new Date(); today.setHours(0, 0, 0, 0)
  const cmp = new Date(d); cmp.setHours(0, 0, 0, 0)
  const diff = Math.round((cmp - today) / 86400000)
  if (diff === 0) return 'Today'
  if (diff === 1) return 'Tomorrow'
  if (diff === -1) return 'Yesterday'
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
})
</script>

<style scoped>
.w-row {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
  padding: 10px 4px; cursor: pointer; border-bottom: 1px solid var(--border-secondary);
  transition: background-color .12s;
}
.w-row:last-child { border-bottom: none; }
.w-row:hover { background: var(--surface-secondary); }
.w-row-main { min-width: 0; flex: 1; }
.w-row-title { font-size: 13px; font-weight: 600; color: var(--foreground); line-height: 1.35; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.w-row-meta { display: flex; align-items: center; gap: 6px; margin-top: 4px; flex-wrap: wrap; }
.w-row-avatars { display: flex; align-items: center; margin-left: 2px; }
.w-row-avatars > * + * { margin-left: -6px; }
.w-row-avatar-overflow { width: 20px; height: 20px; border-radius: 999px; background: var(--default); display: flex; align-items: center; justify-content: center; color: var(--muted); font-size: 9px; font-weight: 700; box-shadow: 0 0 0 2px white; flex-shrink: 0; margin-left: -6px; }

.w-row-date { flex-shrink: 0; font-size: 11px; font-weight: 600; white-space: nowrap; }
.w-row-date-overdue { color: var(--danger); }
.w-row-date-soon { color: var(--warning-soft-foreground); }
.w-row-date-normal { color: var(--muted); }
</style>
