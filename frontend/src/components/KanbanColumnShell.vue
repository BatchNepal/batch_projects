<template>
  <div
    v-if="collapsed"
    class="group flex flex-col items-center w-12 shrink-0 bg-background-secondary rounded-xl py-4 self-stretch cursor-pointer select-none hover:bg-default transition-colors duration-200 border border-transparent hover:border-border-secondary"
    @click="$emit('update:collapsed', false)"
    :title="`${title} (${count})`"
  >
    <button
      class="mb-4 opacity-0 group-hover:opacity-100 transition-opacity text-muted hover:text-muted"
    >
      <ChevronRight class="size-3.5" />
    </button>
    <span
      class="text-xs font-semibold text-muted uppercase tracking-[0.15em]"
      style="writing-mode: vertical-rl; transform: rotate(180deg)"
    >
      {{ title }}
    </span>
    <span
      class="mt-3 text-xs font-bold text-muted bg-overlay border border-border shadow-sm rounded-full w-5 h-5 flex items-center justify-center"
    >
      {{ count }}
    </span>
  </div>

  <div
    v-else
    class="flex flex-col w-[330px] shrink-0 rounded-sm p-2.5 self-stretch border transition-colors duration-150"
    :class="dragOver ? 'bg-accent-soft border-accent' : 'bg-background-secondary border-border'"
  >
    <div class="flex items-center justify-between mb-2.5 px-1.5 pb-2.5 pt-1 group">
      <div class="flex items-center gap-2.5">
        <div class="flex items-center gap-2">
          <span v-if="color" class="inline-block size-2 rounded-full shrink-0" :style="{ background: color }" />
          <p class="text-base font-semibold text-foreground uppercase">
            {{ title }}
          </p>
        </div>

        <Transition name="kc-count" mode="out-in">
          <span
            :key="count"
            class="text-xs font-medium text-muted px-2 py-0.5 rounded-full bg-default min-w-[20px] text-center"
          >
            {{ count }}
          </span>
        </Transition>
      </div>
      <div
        class="flex items-center gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity"
      >
        <slot name="header-actions" />
        <button
          v-if="collapsible"
          class="opacity-0 group-hover:opacity-100 transition-opacity w-5 h-5 flex items-center justify-center rounded-md text-muted hover:text-foreground hover:bg-default -ml-1"
          @click.stop="$emit('update:collapsed', true)"
          title="Collapse column"
        >
          <ChevronLeft class="size-3" />
        </button>
      </div>
    </div>

    <slot />
  </div>
</template>

<script setup>
import { ChevronRight, ChevronLeft } from 'lucide-vue-next'

// Presentational-only "column canvas" chrome — the panel/border/dot+count
// header shared by the real per-project board (KanbanColumn.vue) and any
// dashboard widget that wants to look like a genuine kanban column
// (KanbanWidget.vue). Drag/drop, card rendering and data all stay with the
// caller; this component owns none of it.
defineProps({
  title: { type: String, required: true },
  count: { type: Number, default: 0 },
  color: { type: String, default: null },
  collapsed: { type: Boolean, default: false },
  collapsible: { type: Boolean, default: true },
  dragOver: { type: Boolean, default: false },
})
defineEmits(['update:collapsed'])
</script>

<style scoped>
.kc-count-enter-active,
.kc-count-leave-active { transition: opacity 0.12s ease, transform 0.12s ease; }
.kc-count-enter-from { opacity: 0; transform: translateY(4px) scale(0.85); }
.kc-count-leave-to   { opacity: 0; transform: translateY(-4px) scale(0.85); }
</style>
