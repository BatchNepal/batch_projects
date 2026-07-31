<template>
  <div class="w-full overflow-x-auto">
    <table class="w-full border-collapse">
      <thead>
        <tr>
          <th
            v-for="col in columns"
            :key="col.key"
            :style="col.width ? { width: col.width } : {}"
            class="px-3 py-2 text-left text-xs font-medium text-muted border-b border-border bg-background tracking-wide uppercase"
            :class="col.sortable ? 'cursor-pointer select-none hover:text-foreground transition-colors' : ''"
            @click="col.sortable && $emit('sort', col.key)"
          >
            <span class="inline-flex items-center gap-1">
              {{ col.label }}
              <svg v-if="col.sortable && sortKey === col.key" class="size-3 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <path stroke-linecap="round" stroke-linejoin="round" :d="sortDir === 'asc' ? 'M18 15l-6-6-6 6' : 'M6 9l6 6 6-6'" />
              </svg>
            </span>
          </th>
        </tr>
      </thead>
      <tbody>
        <template v-if="loading">
          <tr v-for="n in skeletonCount" :key="`sk-${n}`" class="border-b border-separator">
            <td v-for="(col, ci) in columns" :key="col.key" class="px-3 py-2 align-middle">
              <div class="h-2.5 rounded-sm bg-default" :style="{ width: W[(n * 3 + ci) % W.length] }" />
            </td>
          </tr>
        </template>
        <template v-else>
          <tr
            v-for="(row, i) in rows"
            :key="row.id ?? row.name ?? i"
            class="border-b border-separator last:border-b-0 hover:bg-background-secondary transition-colors duration-90"
            :class="onRowClick && 'cursor-pointer'"
            @click="onRowClick?.(row)"
          >
            <td v-for="col in columns" :key="col.key" class="px-3 py-2 text-sm text-foreground align-middle">
              <slot :name="`cell-${col.key}`" :row="row" :col="col" :value="row[col.key]">
                {{ row[col.key] ?? '—' }}
              </slot>
            </td>
          </tr>
        </template>
      </tbody>
    </table>

    <div v-if="!loading && !rows?.length">
      <slot name="empty">
        <p class="text-xs text-muted text-center py-8">No results</p>
      </slot>
    </div>
  </div>
</template>

<script setup>
defineProps({
  columns:       { type: Array,    required: true },
  rows:          { type: Array,    default: () => [] },
  loading:       { type: Boolean,  default: false },
  skeletonCount: { type: Number,   default: 6 },
  onRowClick:    { type: Function, default: null },
  sortKey:       { type: String,   default: '' },
  sortDir:       { type: String,   default: 'asc' },
})
defineEmits(['sort'])

const W = ['62%', '78%', '45%', '68%', '54%', '82%', '38%', '71%']
</script>
