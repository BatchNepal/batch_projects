<template>
  <Drawer :open="open" @update:open="$emit('update:open', $event)" size="lg" placement="right">
    <DrawerHeader @close="$emit('update:open', false)">
      <div class="flex items-center gap-2 min-w-0 flex-wrap">
        <Chip size="sm" variant="soft">{{ doctype }}</Chip>
        <span class="font-semibold text-[13px] text-foreground truncate">{{ data?.title || name }}</span>
        <a :href="erpUrl" target="_blank" rel="noopener noreferrer" class="dq-erp-link ml-auto">
          Open in ERPNext <Icon :icon="ExternalLink" :size="12" />
        </a>
      </div>
    </DrawerHeader>

    <DrawerBody class="p-0">
      <div v-if="loading" class="p-5 space-y-3">
        <Skeleton class="h-4 w-2/3 rounded" />
        <Skeleton class="h-24 rounded-lg" />
        <Skeleton class="h-16 rounded-lg" />
      </div>

      <div v-else-if="error" class="flex flex-col items-center justify-center text-center py-16 px-5">
        <span class="size-10 rounded-lg bg-[var(--surface-secondary)] flex items-center justify-center mb-3">
          <Icon :icon="FileX" :size="18" class="text-muted" />
        </span>
        <p class="text-[13px] font-medium text-foreground">Can't open this record</p>
        <p class="text-[12.5px] text-muted mt-1 max-w-xs">{{ error }}</p>
      </div>

      <div v-else-if="data" class="p-5">
        <div class="dq-field-grid">
          <div v-for="f in data.fields" :key="f.fieldname" class="dq-field">
            <span class="dq-field-label">{{ f.label }}</span>
            <span class="dq-field-value">{{ fmtValue(f) }}</span>
          </div>
        </div>
      </div>
    </DrawerBody>
  </Drawer>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { ExternalLink, FileX } from 'lucide-vue-next'
import { Drawer, DrawerHeader, DrawerBody, Chip, Icon, Skeleton } from '@/ui'
import { getWidgetSourceDocQuickview, UpgradeRequiredError } from '@/utils/api'

// Generic, read-only "what is this record" panel for any non-BP-Task
// widget-source doctype (Lead, Opportunity, CRM Lead, CRM Deal, ...).
// BP Task rows never route here — they open the real TaskDetail sidebar.
// Modeled on MoneyDrawer.vue's chrome (Drawer + field-grid) so it reads as
// the same family of ERP-doc panels, not a new visual language.
const props = defineProps({
  open: { type: Boolean, default: false },
  doctype: { type: String, default: '' },
  name: { type: String, default: '' },
})
defineEmits(['update:open'])

const loading = ref(false)
const error = ref('')
const data = ref(null)

const erpUrl = computed(() => `/app/${props.doctype.toLowerCase().replace(/ /g, '-')}/${encodeURIComponent(props.name)}`)

function fmtValue(f) {
  const v = f.value
  if (v === null || v === undefined || v === '') return '—'
  if (f.fieldtype === 'Check') return v ? 'Yes' : 'No'
  if (f.fieldtype === 'Currency') {
    try { return new Intl.NumberFormat(undefined, { style: 'currency', currency: 'USD', maximumFractionDigits: 2 }).format(Number(v)) }
    catch { return v }
  }
  if (f.fieldtype === 'Percent') return `${Math.round(v)}%`
  if (f.fieldtype === 'Date' || f.fieldtype === 'Datetime') {
    try { return new Date(v).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }) }
    catch { return v }
  }
  return v
}

async function load() {
  if (!props.doctype || !props.name) return
  loading.value = true
  error.value = ''
  data.value = null
  try {
    data.value = await getWidgetSourceDocQuickview(props.doctype, props.name)
  } catch (e) {
    error.value = e instanceof UpgradeRequiredError
      ? 'Available on any paid plan.'
      : (e.message || 'Something went wrong loading this record.')
  } finally {
    loading.value = false
  }
}

watch(() => [props.open, props.doctype, props.name], ([isOpen]) => { if (isOpen) load() }, { immediate: true })
</script>

<style scoped>
.dq-field-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px 20px; }
.dq-field { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
.dq-field-label { font-size: 11px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: 0.02em; }
.dq-field-value { font-size: 13px; font-weight: 500; color: var(--foreground); overflow-wrap: break-word; }
.dq-erp-link {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: 12px; font-weight: 600; color: var(--accent);
  text-decoration: none; white-space: nowrap;
}
.dq-erp-link:hover { text-decoration: underline; }
</style>
