<template>
  <nav aria-label="Breadcrumb" :class="cn('flex', $attrs.class)" v-bind="{ ...$attrs, class: undefined }">
    <ol :class="cn('flex flex-wrap items-center gap-1', SIZE[size])">
      <li v-for="(item, idx) in visibleItems" :key="idx" class="flex items-center gap-1">
        <span v-if="idx > 0" class="text-muted select-none" aria-hidden="true">
          <slot name="separator">{{ separator }}</slot>
        </span>
        <span v-if="item.__ellipsis" class="text-muted px-1">…</span>
        <span v-else-if="idx === visibleItems.length - 1" aria-current="page" class="font-medium text-foreground truncate max-w-[180px]">{{ item.label }}</span>
        <RouterLink v-else-if="item.to" :to="item.to" class="text-muted hover:text-foreground transition-colors truncate max-w-[120px]">{{ item.label }}</RouterLink>
        <a v-else-if="item.href" :href="item.href" class="text-muted hover:text-foreground transition-colors truncate max-w-[120px]">{{ item.label }}</a>
        <span v-else class="text-muted truncate max-w-[120px]">{{ item.label }}</span>
      </li>
    </ol>
  </nav>
</template>

<script setup>
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { cn } from '@/lib/utils'

defineOptions({ inheritAttrs: false })

const props = defineProps({
  items:     { type: Array,  required: true },
  separator: { type: String, default: '/' },
  maxItems:  { type: Number, default: 0 },
  size:      { type: String, default: 'md' },
})

const SIZE = { sm: 'text-xs', md: 'text-sm', lg: 'text-base' }

const visibleItems = computed(() => {
  const list = props.items
  if (!props.maxItems || list.length <= props.maxItems) return list
  const keep = Math.max(1, props.maxItems - 2)
  return [list[0], { __ellipsis: true }, ...list.slice(list.length - keep)]
})
</script>
