<template>
  <div class="bg-overlay border border-border rounded-lg transition-shadow duration-150 hover:shadow-sm">
    <div v-if="title || $slots.trailing" class="flex items-start justify-between px-4 py-3 border-b border-separator">
      <div class="min-w-0">
        <h3 v-if="title" class="text-sm font-semibold text-foreground leading-snug">{{ title }}</h3>
        <p v-if="subtitle" class="text-xs text-muted mt-0.5 leading-snug">{{ subtitle }}</p>
      </div>
      <div v-if="$slots.trailing || to || viewAllHref || viewAllLabel" class="shrink-0 ml-4 mt-px">
        <slot name="trailing">
          <RouterLink
            v-if="to"
            :to="to"
            class="text-xs text-primary hover:underline whitespace-nowrap"
          >
            {{ viewAllLabel || 'View all →' }}
          </RouterLink>
          <a
            v-else-if="viewAllHref"
            :href="viewAllHref"
            class="text-xs text-primary hover:underline whitespace-nowrap"
          >
            {{ viewAllLabel || 'View all →' }}
          </a>
          <button
            v-else-if="viewAllLabel"
            type="button"
            class="text-xs text-primary hover:underline whitespace-nowrap cursor-pointer bg-transparent border-none p-0"
            @click="emit('view-all')"
          >
            {{ viewAllLabel }}
          </button>
        </slot>
      </div>
    </div>
    <div class="p-4">
      <slot />
    </div>
  </div>
</template>

<script setup>
import { RouterLink } from 'vue-router'

defineProps({
  title:        { type: String, default: '' },
  subtitle:     { type: String, default: '' },
  to:           { default: null },
  viewAllHref:  { type: String, default: '' },
  viewAllLabel: { type: String, default: '' },
})
const emit = defineEmits(['view-all'])
</script>
