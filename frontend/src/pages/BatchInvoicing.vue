<template>
  <div class="bi">
    <header class="bi-head">
      <div class="min-w-0">
        <h1 class="bi-title">Batch invoicing</h1>
        <p class="bi-sub">Bundle several projects for one client into a single invoice. Each line stays tagged to its own project.</p>
      </div>
      <Button variant="light" size="sm" :isLoading="loading" @click="load">
        <template #startContent><Icon :icon="RefreshCw" :size="13" /></template>Refresh
      </Button>
    </header>

    <div v-if="loading && !clients.length" class="bi-body">
      <Skeleton v-for="i in 3" :key="i" class="h-24 w-full rounded-lg mb-3" />
    </div>

    <div v-else-if="error" class="bi-body">
      <div class="bi-error">{{ error }}</div>
    </div>

    <EmptyState
      v-else-if="!clients.length"
      :icon="ReceiptText"
      title="Nothing to invoice"
      description="Unbilled billable hours on linked projects show up here. Hours on tasks awaiting or refused approval are held back."
      class="bi-body"
    />

    <div v-else class="bi-body">
      <section v-for="c in clients" :key="c.client" class="bi-card">
        <div class="bi-card-head">
          <div class="min-w-0">
            <p class="bi-client">{{ c.client }}</p>
            <p class="bi-meta">
              {{ c.projects.length }} project{{ c.projects.length === 1 ? '' : 's' }}
              · <span class="tnum">{{ c.total_hours }}</span> h unbilled
            </p>
          </div>
          <div class="bi-card-actions">
            <span class="bi-total tnum">{{ fmtMoney(selectedAmount(c), currencyOf(c)) }}</span>
            <Button
              size="sm" color="primary"
              :isDisabled="!selectedCount(c) || busy === c.client || mixedSelected(c)"
              :isLoading="busy === c.client"
              @click="openConfirm(c)"
            >Create invoice</Button>
          </div>
        </div>

        <!-- A batch must be one currency; warn before they select a mix
             rather than letting the backend refuse after the fact. -->
        <p v-if="mixedSelected(c)" class="bi-warn">
          Selected projects are priced in different currencies ({{ selectedCurrencies(c).join(', ') }}).
          One invoice can only be in one currency — narrow the selection.
        </p>

        <table class="bi-table">
          <thead>
            <tr>
              <th class="w-8">
                <Checkbox
                  :isSelected="allSelected(c)"
                  :isIndeterminate="selectedCount(c) > 0 && !allSelected(c)"
                  @update:isSelected="v => toggleAll(c, v)"
                />
              </th>
              <th>Project</th>
              <th class="ta-r">Hours</th>
              <th class="ta-r">Amount</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="p in c.projects" :key="p.bp_project"
              class="bi-row" :class="{ 'is-on': isSelected(p) }"
              @click="toggle(p)"
            >
              <td @click.stop>
                <Checkbox :isSelected="isSelected(p)" @update:isSelected="() => toggle(p)" />
              </td>
              <td class="bi-pname">
                {{ p.project_name }}
                <span v-if="p.currency" class="bi-cur">{{ p.currency }}</span>
              </td>
              <td class="ta-r tnum">{{ p.hours }}</td>
              <td class="ta-r tnum">{{ fmtMoney(p.amount, p.currency) }}</td>
            </tr>
          </tbody>
        </table>
      </section>
    </div>

    <!-- confirm + payment-first overrides -->
    <Modal :open="confirm.open" @update:open="v => (confirm.open = v)">
      <ModalHeader>Create invoice</ModalHeader>
      <ModalBody>
        <p class="bi-confirm-line">
          <strong>{{ confirm.client }}</strong> —
          {{ confirm.projects.length }} project{{ confirm.projects.length === 1 ? '' : 's' }},
          <span class="tnum">{{ fmtMoney(confirm.amount, confirm.currency) }}</span>
        </p>
        <ul class="bi-confirm-list">
          <li v-for="p in confirm.projects" :key="p.bp_project">
            {{ p.project_name }}<span class="tnum">{{ fmtMoney(p.amount, p.currency) }}</span>
          </li>
        </ul>

        <details class="bi-adv">
          <summary>Payment already received?</summary>
          <p class="bi-adv-help">
            For wire/prepaid clients the invoice must match what actually landed.
            Set the exact amount and rate — nothing is guessed, and it refuses rather
            than create a mismatched invoice.
          </p>
          <div class="bi-adv-grid">
            <Input v-model="confirm.overrideAmount" label="Exact amount" placeholder="Optional" />
            <Input v-model="confirm.overrideCurrency" label="Currency" :placeholder="confirm.currency || 'Optional'" />
            <Input v-model="confirm.overrideRate" label="Conversion rate" placeholder="Optional" />
          </div>
        </details>

        <p v-if="confirm.error" class="bi-error mt-3">{{ confirm.error }}</p>
      </ModalBody>
      <ModalFooter>
        <Button variant="bordered" @click="confirm.open = false">Cancel</Button>
        <Button color="primary" :isLoading="confirm.busy" @click="doCreate">Create draft invoice</Button>
      </ModalFooter>
    </Modal>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { RefreshCw, ReceiptText } from 'lucide-vue-next'
import {
  Button, Icon, Skeleton, EmptyState, Checkbox, Input,
  Modal, ModalHeader, ModalBody, ModalFooter,
} from '@/ui'
import { getBatchInvoiceCandidates, generateInvoice } from '@/utils/api'
import { toast } from 'vue-sonner'

const clients = ref([])
const loading = ref(false)
const error = ref('')
const busy = ref('')
const picked = reactive({})     // bp_project -> true

async function load() {
  loading.value = true
  error.value = ''
  try {
    clients.value = await getBatchInvoiceCandidates() || []
    // Default to everything selected: the common case is "bill it all".
    for (const c of clients.value) for (const p of c.projects) picked[p.bp_project] = true
  } catch (e) {
    error.value = e?.message || 'Could not load invoiceable work.'
    clients.value = []
  } finally {
    loading.value = false
  }
}
onMounted(load)

function isSelected(p) { return !!picked[p.bp_project] }
function toggle(p) { picked[p.bp_project] = !picked[p.bp_project] }
function selectedOf(c) { return c.projects.filter(isSelected) }
function selectedCount(c) { return selectedOf(c).length }
function allSelected(c) { return c.projects.length > 0 && selectedCount(c) === c.projects.length }
function toggleAll(c, v) { for (const p of c.projects) picked[p.bp_project] = !!v }
function selectedAmount(c) { return round2(selectedOf(c).reduce((s, p) => s + p.amount, 0)) }
function selectedCurrencies(c) {
  return [...new Set(selectedOf(c).map(p => p.currency).filter(Boolean))].sort()
}
function mixedSelected(c) { return selectedCurrencies(c).length > 1 }
function currencyOf(c) { return selectedCurrencies(c)[0] || c.currencies?.[0] || '' }

function round2(n) { return Math.round((n + Number.EPSILON) * 100) / 100 }
function fmtMoney(n, cur) {
  const v = round2(n || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  return cur ? `${v} ${cur}` : v
}

const confirm = reactive({
  open: false, client: '', projects: [], amount: 0, currency: '',
  overrideAmount: '', overrideCurrency: '', overrideRate: '',
  busy: false, error: '',
})

function openConfirm(c) {
  const sel = selectedOf(c)
  Object.assign(confirm, {
    open: true, client: c.client, projects: sel,
    amount: selectedAmount(c), currency: currencyOf(c),
    overrideAmount: '', overrideCurrency: '', overrideRate: '',
    busy: false, error: '',
  })
}

async function doCreate() {
  confirm.busy = true
  confirm.error = ''
  busy.value = confirm.client
  try {
    const res = await generateInvoice(
      confirm.projects.map(p => p.bp_project),
      null,
      {
        amount: confirm.overrideAmount || undefined,
        currency: confirm.overrideCurrency || undefined,
        conversion_rate: confirm.overrideRate || undefined,
      },
    )
    confirm.open = false
    toast.success(`Draft ${res.sales_invoice} created`, { description: fmtMoney(res.grand_total, res.currency) })
    await load()
  } catch (e) {
    // The backend refuses rather than creating a wrong invoice (currency
    // mismatch, unresolved rate, amount assertion) — surface it verbatim,
    // those messages are written to be actionable.
    confirm.error = e?.message || 'Could not create the invoice.'
  } finally {
    confirm.busy = false
    busy.value = ''
  }
}
</script>

<style scoped>
.bi { display: flex; flex-direction: column; height: 100%; overflow: hidden; background: var(--surface); }

.bi-head {
  flex-shrink: 0; display: flex; align-items: flex-start; justify-content: space-between;
  gap: 16px; padding: 16px 20px 12px; border-bottom: 1px solid var(--border);
}
.bi-title { font-size:var(--text-xl); font-weight: 600; color: var(--foreground); letter-spacing: -0.01em; }
.bi-sub { font-size:var(--text-sm); color: var(--muted); margin-top: 2px; max-width: 62ch; }

.bi-body { flex: 1; min-height: 0; overflow-y: auto; padding: 16px 20px 24px; }

.bi-card { border: 1px solid var(--border); border-radius: 10px; background: var(--surface); margin-bottom: 12px; overflow: hidden; }
.bi-card-head { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 12px 14px; }
.bi-client { font-size:var(--text-md); font-weight: 600; color: var(--foreground); }
.bi-meta { font-size:var(--text-sm); color: var(--muted); margin-top: 2px; }
.bi-card-actions { display: flex; align-items: center; gap: 12px; flex-shrink: 0; }
.bi-total { font-size:var(--text-md); font-weight: 600; color: var(--foreground); }

.bi-warn {
  margin: 0 14px 10px; padding: 8px 10px; border-radius: 6px;
  background: var(--warning-soft); color: var(--warning-soft-foreground); font-size:var(--text-sm);
}

.bi-table { width: 100%; border-collapse: collapse; }
.bi-table th {
  text-align: left; font-size:var(--text-xs); font-weight: 500; text-transform: uppercase;
  letter-spacing: 0.04em; color: var(--muted); padding: 6px 14px;
  border-bottom: 1px solid var(--border);
}
.bi-row { height: 36px; cursor: pointer; }
.bi-row td { padding: 0 14px; font-size:var(--text-base); color: var(--foreground); border-bottom: 1px solid var(--border); vertical-align: middle; }
.bi-row:last-child td { border-bottom: none; }
.bi-row:hover { background: var(--surface-hover); }
.bi-row.is-on { background: var(--surface-secondary); }
.bi-pname { font-weight: 500; }
.bi-cur { font-size:var(--text-xs); color: var(--muted); margin-left: 6px; }

.ta-r { text-align: right; }
.tnum { font-variant-numeric: tabular-nums; }

.bi-error {
  padding: 10px 12px; border-radius: 6px; font-size:var(--text-sm);
  background: var(--danger-soft); color: var(--danger-soft-foreground);
}
.mt-3 { margin-top: 12px; }

.bi-confirm-line { font-size:var(--text-base); color: var(--foreground); }
.bi-confirm-list { margin: 10px 0 0; padding: 0; list-style: none; }
.bi-confirm-list li {
  display: flex; justify-content: space-between; gap: 12px;
  font-size:var(--text-sm); color: var(--muted); padding: 3px 0;
}

.bi-adv { margin-top: 16px; border-top: 1px solid var(--border); padding-top: 12px; }
.bi-adv summary { font-size:var(--text-sm); font-weight: 500; color: var(--foreground); cursor: pointer; }
.bi-adv-help { font-size:var(--text-sm); color: var(--muted); margin: 6px 0 10px; line-height: 1.5; }
.bi-adv-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }

@media (max-width: 720px) {
  .bi-card-head { flex-direction: column; align-items: stretch; }
  .bi-card-actions { justify-content: space-between; }
  .bi-adv-grid { grid-template-columns: 1fr; }
}
</style>
