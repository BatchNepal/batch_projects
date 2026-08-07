<template>
  <div class="hw">
    <div class="hw-text">
      <p class="hw-title">{{ widget.title || 'Untitled section' }}</p>
      <p v-if="widget.description" class="hw-desc">{{ widget.description }}</p>
    </div>
    <a v-if="widget.link_url" :href="widget.link_url" target="_blank" rel="noopener noreferrer" class="hw-link">
      {{ widget.link_label || 'View' }}
      <Icon :icon="ExternalLink" :size="12" />
    </a>
  </div>
</template>

<script setup>
import { ExternalLink } from 'lucide-vue-next'
import { Icon } from '@/ui'

// Plain section divider — no data, no fetch — for organizing a dashboard
// into visual blocks ("Q4 Pipeline" above a row of CRM widgets, etc.).
defineProps({
  widget: { type: Object, required: true }, // { title, description, link_url, link_label }
})
</script>

<style scoped>
/* align-items was center — on a grid box taller than the text (the common
   case), that centers the title in leftover space regardless of the
   widget's own padding value, so a 0px/borderless padding still LOOKED
   padded (the gap was never padding, it was centering). flex-start makes
   the visible gap always equal to the actual padding, honestly — shrink
   padding to 0 and the title sits flush against the top edge. */
/* height was 100% — that fills the WHOLE grid box regardless of content, so
   with content pinned flex-start, every pixel of unused height still
   collected below it, between the text and the padding-bottom boundary.
   That leftover was never padding either, and no padding-bottom value could
   ever reach it. auto lets .hw be exactly as tall as its own content, so
   padding-bottom now measures from the text's real bottom edge, not from
   wherever the grid box happens to end. */
.hw { height: auto; display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.hw-text { min-width: 0; }
.hw-title { font-size: 16px; font-weight: 600; color: var(--foreground); letter-spacing: -0.01em; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.hw-desc { font-size: 12.5px; color: var(--muted); margin-top: 3px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.hw-link {
  display: inline-flex; align-items: center; gap: 4px; flex-shrink: 0;
  font-size: 12px; font-weight: 600; color: var(--accent); text-decoration: none;
}
.hw-link:hover { text-decoration: underline; }
</style>
