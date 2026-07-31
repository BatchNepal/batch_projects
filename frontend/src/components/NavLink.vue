<template>
  <div @click="router.push(to)" :class="[
    'flex items-center gap-2 rounded-md cursor-pointer transition-all duration-100 select-none group',
    collapsed ? 'justify-center p-2' : 'px-2 py-[6px]',
    isActive
      ? 'bg-overlay shadow-sm border border-border text-foreground'
      : 'text-muted hover:bg-surface-secondary hover:text-muted hover:border hover:border-border hover:shadow-sm border border-transparent'
  ]" :title="collapsed ? label : undefined">
    <!-- Inline icons per type -->
    <template v-if="icon">
      <svg v-if="icon === 'home'" class="w-[15px] h-[15px] shrink-0" fill="none" stroke="currentColor"
        viewBox="0 0 24 24" stroke-width="1.75">
        <path stroke-linecap="round" stroke-linejoin="round"
          d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
      </svg>
      <svg v-else-if="icon === 'tasks'" class="w-[15px] h-[15px] shrink-0" fill="none" stroke="currentColor"
        viewBox="0 0 24 24" stroke-width="1.75">
        <path stroke-linecap="round" stroke-linejoin="round"
          d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
      </svg>
      <svg v-else-if="icon === 'bell'" class="w-[15px] h-[15px] shrink-0" fill="none" stroke="currentColor"
        viewBox="0 0 24 24" stroke-width="1.75">
        <path stroke-linecap="round" stroke-linejoin="round"
          d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
      </svg>
    </template>

    <!-- Project color avatar -->
    <div v-else-if="avatar" :style="{ backgroundColor: avatarBg }"
      class="w-[18px] h-[18px] rounded-[4px] flex items-center justify-center text-white text-[9px] font-bold shrink-0">
      {{
        avatar }}</div>

    <template v-if="!collapsed">
      <span class="flex-1 text-[13px] truncate">{{ label }}</span>
      <span v-if="badge"
        class="text-[10px] bg-border text-muted rounded-full px-1.5 min-w-[18px] text-center leading-snug">{{ badge
        }}</span>
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const props = defineProps({
  to: String,
  icon: String,
  label: String,
  collapsed: Boolean,
  avatar: String,
  avatarBg: String,
  badge: [String, Number],
  exact: Boolean,
})

const route = useRoute()
const router = useRouter()

const isActive = computed(() => {
  if (props.exact || props.to === '/workspace') return route.path === props.to
  return route.path.startsWith(props.to)
})
</script>