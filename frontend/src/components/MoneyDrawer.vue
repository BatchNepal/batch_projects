<template>
  <Drawer :open="open" @update:open="$emit('update:open', $event)" size="lg" placement="right">
    <DrawerHeader @close="$emit('update:open', false)">
      <div class="flex items-center gap-2 min-w-0 flex-wrap">
        <button v-if="stack.length" type="button" class="md-back" title="Back" @click="goBack">
          <Icon :icon="ChevronLeft" class="size-4" />
        </button>
        <Chip size="sm" variant="soft">{{ current.doctype }}</Chip>
        <span class="font-mono text-[13px] font-semibold text-foreground truncate">{{ current.name }}</span>
        <Chip v-if="summary?.status" size="sm" :color="statusColor(summary.status)">{{ summary.status }}</Chip>
        <a :href="erpUrl" target="_blank" rel="noopener noreferrer" class="md-erp-link ml-auto">
          Open in ERPNext <ExternalLink class="size-3 inline" />
        </a>
      </div>
    </DrawerHeader>

    <DrawerBody class="p-0">
      <!-- Loading -->
      <div v-if="loading" class="p-5 space-y-3">
        <Skeleton class="h-4 w-2/3 rounded" />
        <Skeleton class="h-24 rounded-lg" />
        <Skeleton class="h-32 rounded-lg" />
      </div>

      <!-- Denied / missing — same friendly empty state either way, never a raw traceback -->
      <div v-else-if="error" class="flex flex-col items-center justify-center text-center py-16 px-5">
        <span class="size-10 rounded-lg bg-[var(--surface-secondary)] flex items-center justify-center mb-3">
          <Icon :icon="FileX" class="size-5 text-muted" />
        </span>
        <p class="text-[13px] font-medium text-foreground">Can't open this document</p>
        <p class="text-[12.5px] text-muted mt-1 max-w-xs">{{ error }}</p>
      </div>

      <div v-else-if="summary" class="p-5">
        <div class="md-field-grid">
          <div v-for="f in fields" :key="f.key" class="md-field">
            <span class="md-field-label">{{ f.label }}</span>
            <span class="md-field-value">{{ f.value }}</span>
          </div>
        </div>

        <div class="mt-6">
          <p class="md-section-label">{{ isTimesheet ? 'Time logs' : 'Items' }}</p>
          <DataTable :columns="columns" :rows="children">
            <template #cell-item_name="{ row }">
              <span class="text-[13px]">{{ row.item_name }}</span>
              <span v-if="row.description && row.description !== row.item_name" class="block text-[11.5px] text-muted mt-0.5">
                {{ row.description }}
              </span>
            </template>
            <template #cell-task="{ row }">
              <span v-if="row.task_key" class="text-[12px] whitespace-nowrap">
                <span class="font-mono font-semibold text-accent">{{ row.task_key }}</span>
                <span class="text-muted"> — {{ row.task_title }}</span>
              </span>
              <span v-else class="text-muted">—</span>
            </template>
            <template #cell-from_time="{ value }">{{ fmtDateTime(value) }}</template>
            <template #cell-to_time="{ value }">{{ fmtDateTime(value) }}</template>
            <template #cell-hours="{ value }">{{ Number(value || 0).toFixed(2) }}h</template>
            <template #cell-is_billable="{ value }">
              <Chip size="sm" variant="soft" :color="value ? 'success' : 'default'">{{ value ? 'Yes' : 'No' }}</Chip>
            </template>
            <template #cell-billing_amount="{ value }">{{ fmtMoney(value) }}</template>
            <template #cell-rate="{ value }">{{ fmtMoney(value) }}</template>
            <template #cell-amount="{ value }">{{ fmtMoney(value) }}</template>
            <template #cell-billed_amt="{ value }">{{ fmtMoney(value) }}</template>
            <template #cell-committed="{ row }">{{ fmtMoney((row.amount || 0) - (row.billed_amt || 0) - (row.rate || 0) * (row.returned_qty || 0)) }}</template>
            <template #empty>
              <p class="text-[12.5px] text-muted text-center py-8">
                {{ isTimesheet ? 'No time logs on this timesheet.' : 'No line items.' }}
              </p>
            </template>
          </DataTable>
        </div>

        <!-- The hours behind a generated invoice — each opens its Timesheet
             through the same gated endpoint (non-transitive by design).
             Section renders whenever the backend curates the key (Sales
             Invoice), with an explicit empty state: an invisible section
             reads as "feature missing", not "no data". -->
        <div v-if="summary.timesheets" class="mt-6">
          <p class="md-section-label">Timesheets</p>
          <div v-if="summary.timesheets.length" class="md-ts-list">
            <button v-for="t in summary.timesheets" :key="t.timesheet" type="button"
              class="md-ts-row" @click="navigate('Timesheet', t.timesheet)">
              <span class="font-mono text-[12.5px] font-semibold text-accent">{{ t.timesheet }}</span>
              <span class="text-[12px] text-muted">{{ t.hours }}h</span>
              <span class="ml-auto text-[12.5px] font-medium text-foreground tabular-nums">{{ fmtMoney(t.amount) }}</span>
              <ChevronRight class="size-3 text-muted shrink-0" />
            </button>
          </div>
          <div v-else class="md-ts-list">
            <p class="text-[12.5px] text-muted text-center py-6 m-0 w-full">
              No timesheets — this invoice wasn't billed from tracked hours.
            </p>
          </div>
        </div>
      </div>
    </DrawerBody>

    <DrawerFooter v-if="canSubmit">
      <Button size="sm" color="primary" :isLoading="submitting" @click="onSubmit">
        <Icon :icon="Check" class="size-3.5 mr-1" /> Submit Timesheet
      </Button>
    </DrawerFooter>
  </Drawer>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { toast } from 'vue-sonner'
import { Drawer, DrawerHeader, DrawerBody, DrawerFooter, Chip, Button, Icon, Skeleton, DataTable } from '@/ui'
import { ExternalLink, FileX, Check, ChevronLeft, ChevronRight } from 'lucide-vue-next'
import { getErpDocSummary, submitTimesheet, UpgradeRequiredError } from '@/utils/api'

const props = defineProps({
  open:    { type: Boolean, default: false },
  project: { type: String,  default: '' },
  doctype: { type: String,  default: '' },
  name:    { type: String,  default: '' },
})
const emit = defineEmits(['update:open', 'submitted'])

const loading    = ref(false)
const error      = ref('')
const summary    = ref(null)
const submitting = ref(false)

// In-drawer navigation: opening a linked doc (e.g. an SI's backing
// Timesheet) swaps the target and re-fetches through the same gated
// endpoint — access is never inherited from the current doc. `stack`
// remembers where we came from so Back works.
const current = ref({ doctype: props.doctype, name: props.name })
const stack   = ref([])

function navigate(doctype, name) {
  stack.value.push({ ...current.value })
  current.value = { doctype, name }
  load()
}
function goBack() {
  const prev = stack.value.pop()
  if (prev) { current.value = prev; load() }
}

const ERP_ROUTE = {
  'Sales Invoice':    'sales-invoice',
  'Purchase Invoice': 'purchase-invoice',
  'Sales Order':       'sales-order',
  'Purchase Order':    'purchase-order',
  'Timesheet':         'timesheet',
}
// The escape hatch, per the scope contract — everything this drawer doesn't
// curate (taxes, addresses, attachments, comments, …) lives one click away.
const erpUrl = computed(() =>
  `/app/${ERP_ROUTE[current.value.doctype] || current.value.doctype.toLowerCase()}/${encodeURIComponent(current.value.name)}`
)

const isTimesheet = computed(() => current.value.doctype === 'Timesheet')
const canSubmit    = computed(() => isTimesheet.value && summary.value?.docstatus === 0)

const STATUS_COLOR = {
  paid: 'success', completed: 'success', closed: 'success', submitted: 'success',
  overdue: 'danger', unpaid: 'warning', 'partly paid': 'warning', 'to bill': 'warning',
  draft: 'default', cancelled: 'default', 'on hold': 'default',
}
function statusColor(status) { return STATUS_COLOR[(status || '').toLowerCase()] || 'default' }

// Field grid: every curated header field except the ones already shown in
// the header chip row / rendered as the items-or-time_logs table below.
// Iteration order follows the backend's own curated field order (erp_link.
// _DOC_SPECS) — no separate ordering table to keep in sync.
const SKIP_KEYS = new Set(['doctype', 'name', 'status', 'docstatus', 'items', 'time_logs', 'timesheets'])
const FIELD_LABELS = {
  posting_date: 'Posting date', due_date: 'Due date', customer: 'Customer',
  supplier: 'Supplier', currency: 'Currency', grand_total: 'Grand total',
  outstanding_amount: 'Outstanding', transaction_date: 'Date',
  delivery_date: 'Delivery date', per_billed: '% Billed', per_delivered: '% Delivered',
  employee: 'Employee', employee_name: 'Employee name', start_date: 'Start date',
  end_date: 'End date', total_hours: 'Total hours', per_received: '% Received',
}
const CURRENCY_KEYS = new Set(['grand_total', 'outstanding_amount'])
const PERCENT_KEYS  = new Set(['per_billed', 'per_delivered', 'per_received'])
const HOURS_KEYS    = new Set(['total_hours'])

const fields = computed(() => {
  if (!summary.value) return []
  return Object.keys(summary.value)
    .filter((k) => !SKIP_KEYS.has(k))
    .map((k) => ({ key: k, label: FIELD_LABELS[k] || k, value: fmtValue(k, summary.value[k]) }))
})

function fmtValue(key, value) {
  if (value === null || value === undefined || value === '') return '—'
  if (CURRENCY_KEYS.has(key)) return fmtMoney(value)
  if (PERCENT_KEYS.has(key)) return `${Math.round(value)}%`
  if (HOURS_KEYS.has(key)) return `${value}h`
  return value
}

function fmtMoney(v) {
  try {
    return new Intl.NumberFormat(undefined, {
      style: 'currency', currency: summary.value?.currency || 'USD',
      minimumFractionDigits: 0, maximumFractionDigits: 2,
    }).format(Number(v || 0))
  } catch (e) {
    return Number(v || 0).toLocaleString(undefined, { maximumFractionDigits: 2 })
  }
}

function fmtDateTime(v) {
  if (!v) return '—'
  try {
    return new Date(v).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
  } catch (e) {
    return String(v)
  }
}

const children = computed(() => summary.value ? (summary.value.items || summary.value.time_logs || []) : [])

// One "Item" column, not two — description only renders (as a second line,
// see #cell-item_name) when it actually differs from item_name. Every row
// generate_invoice creates sets both to the identical string; real
// ERPNext-authored PI/SO rows can legitimately have a distinct description.
const ITEM_COLUMNS = [
  { key: 'item_name', label: 'Item', width: '38%' },
  { key: 'qty',        label: 'Qty' },
  { key: 'uom',        label: 'UOM' },
  { key: 'rate',       label: 'Rate' },
  { key: 'amount',     label: 'Amount' },
]
const TIME_LOG_COLUMNS = [
  { key: 'task',            label: 'Task' },
  { key: 'activity_type',   label: 'Activity' },
  { key: 'from_time',       label: 'From' },
  { key: 'to_time',         label: 'To' },
  { key: 'hours',           label: 'Hours' },
  { key: 'is_billable',     label: 'Billable' },
  { key: 'billing_amount',  label: 'Amount' },
]
// Purchase Order rows carry billed_amt (doc currency, same as rate/amount) —
// an extra "Committed" column derived client-side (amount - billed_amt) so
// the drawer shows the per-line outstanding remainder, not just the order
// amount.
const PO_ITEM_COLUMNS = [
  ...ITEM_COLUMNS,
  { key: 'billed_amt', label: 'Billed' },
  { key: 'committed',  label: 'Committed' },
]
const isPurchaseOrder = computed(() => current.value.doctype === 'Purchase Order')
const columns = computed(() => {
  if (isTimesheet.value) return TIME_LOG_COLUMNS
  if (isPurchaseOrder.value) return PO_ITEM_COLUMNS
  return ITEM_COLUMNS
})

async function load() {
  if (!props.project || !current.value.doctype || !current.value.name) return
  loading.value = true
  error.value = ''
  summary.value = null
  try {
    summary.value = await getErpDocSummary(props.project, current.value.doctype, current.value.name)
  } catch (e) {
    error.value = e instanceof UpgradeRequiredError
      ? 'This requires the Business plan or higher.'
      : (e.message || 'Something went wrong loading this document.')
  } finally {
    loading.value = false
  }
}

watch(() => [props.open, props.doctype, props.name], ([isOpen]) => {
  if (isOpen) {
    current.value = { doctype: props.doctype, name: props.name }
    stack.value = []
    load()
  }
}, { immediate: true })

async function onSubmit() {
  if (submitting.value || !summary.value) return
  if (!confirm(`Submit ${summary.value.name}? This posts the hours to ERPNext and can't be undone from here.`)) return
  submitting.value = true
  try {
    summary.value = await submitTimesheet(props.project, current.value.name)
    toast.success('Timesheet submitted')
    emit('submitted')
  } catch (e) {
    toast.error(e.message || 'Failed to submit timesheet')
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.md-field-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px 20px; }
.md-field { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
.md-field-label { font-size: 11px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: 0.02em; }
.md-field-value { font-size: 13px; font-weight: 500; color: var(--foreground); overflow-wrap: break-word; }
.md-section-label { font-size: 11px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: 0.02em; margin-bottom: 8px; }
.md-erp-link {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: 12px; font-weight: 600; color: var(--accent);
  text-decoration: none; white-space: nowrap;
}
.md-erp-link:hover { text-decoration: underline; }

.md-back {
  width: 24px; height: 24px; border-radius: 6px; flex-shrink: 0;
  display: grid; place-items: center; color: var(--muted);
  background: transparent; transition: background .12s, color .12s;
}
.md-back:hover { background: var(--surface-secondary); color: var(--foreground); }

.md-ts-list { display: flex; flex-direction: column; border: 1px solid var(--border-secondary); border-radius: 8px; overflow: hidden; }
.md-ts-row {
  display: flex; align-items: center; gap: 10px;
  height: 38px; padding: 0 12px; text-align: left;
  background: transparent; transition: background .08s;
}
.md-ts-row + .md-ts-row { border-top: 1px solid var(--border-secondary); }
.md-ts-row:hover { background: var(--surface-secondary); }
</style>
