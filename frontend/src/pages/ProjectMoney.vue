<template>
  <div class="pm-root">
    <!-- Entitlements haven't resolved yet (cold page load/refresh races the
         async bootstrap in App.vue) — wait rather than flashing the lock
         banner for a paid tier that just hasn't loaded its plan yet. -->
    <div v-if="!ent.loaded" class="grid grid-cols-4 gap-3 mb-6">
      <Skeleton v-for="i in 4" :key="i" class="h-[104px] rounded-lg" />
    </div>

    <!-- Locked (below Business tier) — always reachable, never blocked at the tab -->
    <div v-else-if="!unlocked" class="pm-lock-banner">
      <span class="pm-lock-icon"><Icon :icon="Lock" class="size-5 text-primary" /></span>
      <div class="min-w-0 flex-1">
        <p class="text-[14px] font-semibold text-foreground">See real revenue, cost and margin — on top of your own ERPNext</p>
        <p class="text-[13px] text-muted mt-1 leading-relaxed">
          Every invoice, timesheet and sales order this project touches, rolled up and
          three clicks from the real document. Available on the
          <span class="font-semibold text-foreground">{{ requiredPlan }}</span> plan and above.
        </p>
        <div class="flex items-center gap-2 mt-3">
          <Button size="sm" color="primary" @click="goUpgrade">
            <Icon :icon="Sparkles" class="size-3.5 mr-1" /> Upgrade to {{ requiredPlan }}
          </Button>
          <span class="text-[12px] text-muted">You're on the {{ ent.tierLabel }} plan</span>
        </div>
      </div>
    </div>

    <template v-else>
      <!-- Loading -->
      <div v-if="loading" class="grid grid-cols-4 gap-3 mb-6">
        <Skeleton v-for="i in 4" :key="i" class="h-[104px] rounded-lg" />
      </div>

      <!-- Unlinked: hero CTA to pick or create the ERPNext Project -->
      <div v-else-if="money && !money.linked" class="pm-unlinked">
        <span class="pm-lock-icon"><Icon :icon="Link2" class="size-5 text-primary" /></span>
        <div class="min-w-0 flex-1">
          <p class="text-[14px] font-semibold text-foreground">Link this project to ERPNext</p>
          <p class="text-[13px] text-muted mt-1 leading-relaxed">
            Money numbers come from your real ERPNext invoices, timesheets and sales
            orders — link an existing ERPNext Project or create one from this BP Project.
          </p>

          <div class="mt-4 max-w-sm">
            <Input v-model="searchQ" placeholder="Search ERPNext Projects…" isClearable @update:modelValue="onSearch">
              <template #startContent><Icon :icon="Search" class="size-3.5 text-muted" /></template>
            </Input>
            <div v-if="searchResults.length" class="mt-2 rounded-lg border border-border divide-y divide-border overflow-hidden">
              <button
                v-for="r in searchResults" :key="r.name"
                class="w-full flex items-center justify-between gap-3 px-3 py-2 text-left hover:bg-default transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                :disabled="r.already_linked"
                @click="pickProject(r)"
              >
                <span class="min-w-0">
                  <span class="block text-[13px] font-medium text-foreground truncate">{{ r.project_name }}</span>
                  <span class="block text-[11.5px] text-muted truncate">{{ r.name }}<template v-if="r.customer"> · {{ r.customer }}</template></span>
                </span>
                <span v-if="r.already_linked" class="text-[11px] text-muted shrink-0">Already linked</span>
              </button>
            </div>
          </div>

          <div class="flex items-center gap-2 mt-4">
            <Button size="sm" color="primary" :isLoading="linking" @click="doCreateAndLink">
              <Icon :icon="Plus" class="size-3.5 mr-1" /> Create ERPNext Project
            </Button>
          </div>
        </div>
      </div>

      <!-- Linked: the real money tab -->
      <template v-else-if="money">
        <!-- Linked project header -->
        <div class="pm-linked-header">
          <div class="flex items-center gap-2 min-w-0">
            <Icon :icon="Link2" class="size-4 text-success shrink-0" />
            <span class="text-[12.5px] text-muted shrink-0">Linked to</span>
            <span class="text-[13px] font-semibold text-foreground font-mono truncate">{{ money.erpnext_project }}</span>
          </div>
          <Button variant="ghost" size="sm" color="danger" :isLoading="unlinking" @click="doUnlink">
            Unlink
          </Button>
        </div>

        <div class="grid grid-cols-4 gap-3 mb-6">
          <KpiTile label="Revenue" :value="fmtCurrency(money.revenue.total)" :subline="periodLabel" />
          <KpiTile label="Cost" :value="fmtCurrency(costTotal)" :subline="`${money.labour.hours}h labour + materials + expenses`" />
          <KpiTile label="Margin" :value="fmtCurrency(money.margin)" :subline="marginPctLabel" />
          <KpiTile label="Unbilled" :value="fmtCurrency(money.labour.unbilled_value)" :subline="`${money.labour.unbilled_hours}h not yet invoiced`" />
        </div>

        <!-- Draft timesheets: logged (usually by the timer) but not yet submitted,
             so invisible to every number above -->
        <div v-if="money.labour.draft_hours" class="pm-note pm-note-draft">
          <Icon :icon="Hourglass" class="size-3.5 shrink-0" />
          <span class="text-[12.5px]">
            <span class="font-semibold tabular-nums">{{ money.labour.draft_hours }}h</span>
            awaiting submission — draft timesheets don't count above until submitted in ERPNext.
          </span>
          <span class="ml-auto flex items-center gap-2 flex-wrap justify-end shrink-0">
            <button v-for="r in money.labour.draft_rows" :key="r.timesheet" type="button"
              class="pm-note-link" @click="openDrawer('Timesheet', r.timesheet)">
              {{ r.timesheet }} <ChevronRight class="size-3 inline" />
            </button>
          </span>
        </div>

        <!-- No hourly rate: timer hours will land with a 0 billing value -->
        <div v-if="showRateNudge" class="pm-note pm-note-rate">
          <Icon :icon="AlertTriangle" class="size-3.5 shrink-0" />
          <span class="text-[12.5px]">
            No hourly rate set — tracked time lands on timesheets worth
            <span class="font-semibold tabular-nums">{{ fmtCurrency(0) }}</span>.
          </span>
          <RouterLink :to="{ name: 'ProjectSettings', params: { key: projectKey, tab: 'billing' } }"
            class="pm-note-link ml-auto shrink-0">
            Set hourly rate
          </RouterLink>
        </div>

        <div v-if="money.budget.amount" class="pm-budget-row">
          <span class="text-[12.5px] text-muted">Budget</span>
          <div class="pm-budget-bar">
            <div class="pm-budget-fill" :class="(money.budget.burn_pct || 0) > 100 ? 'pm-over' : (money.budget.burn_pct || 0) > 85 ? 'pm-watch' : ''"
                 :style="{ width: Math.min(money.budget.burn_pct || 0, 100) + '%' }" />
          </div>
          <span class="text-[12.5px] text-foreground tabular-nums">{{ money.budget.burn_pct ?? 0 }}% of {{ fmtCurrency(money.budget.amount) }}</span>
        </div>

        <Accordion class="pm-sections">
          <!-- Revenue rows -->
          <AccordionItem>
            <template #title>
              <span class="pm-sec-title">Revenue <span class="pm-sec-count">{{ money.revenue.rows.length }}</span></span>
            </template>
            <div v-if="money.revenue.rows.length" class="pm-rows">
              <button v-for="r in money.revenue.rows" :key="r.name" type="button" class="pm-row"
                @click="openDrawer('Sales Invoice', r.name)">
                <span class="pm-row-name">{{ r.name }}</span>
                <span class="pm-row-date">{{ r.date }}</span>
                <Chip size="sm" :color="statusColor(r.status)">{{ r.status }}</Chip>
                <span class="pm-row-amt">{{ fmtCurrency(r.grand_total) }}</span>
                <span v-if="r.outstanding" class="pm-row-sub">{{ fmtCurrency(r.outstanding) }} outstanding</span>
                <ChevronRight class="size-3 text-muted shrink-0" />
              </button>
            </div>
            <p v-else class="pm-empty">No Sales Invoices in this period.</p>
          </AccordionItem>

          <!-- Materials / Purchase Invoices -->
          <AccordionItem>
            <template #title>
              <span class="pm-sec-title">Materials <span class="pm-sec-count">{{ money.materials.rows.length }}</span></span>
            </template>
            <div v-if="money.materials.rows.length" class="pm-rows">
              <button v-for="r in money.materials.rows" :key="r.name" type="button" class="pm-row"
                @click="openDrawer('Purchase Invoice', r.name)">
                <span class="pm-row-name">{{ r.name }}</span>
                <span class="pm-row-date">{{ r.date }}</span>
                <Chip size="sm" :color="statusColor(r.status)">{{ r.status }}</Chip>
                <span class="pm-row-amt">{{ fmtCurrency(r.grand_total) }}</span>
                <ChevronRight class="size-3 text-muted shrink-0" />
              </button>
            </div>
            <p v-else class="pm-empty">No Purchase Invoices in this period.</p>
          </AccordionItem>

          <!-- Expenses -->
          <AccordionItem>
            <template #title>
              <span class="pm-sec-title">Expenses <span class="pm-sec-count">{{ money.expenses.rows.length }}</span></span>
            </template>
            <div v-if="money.expenses.rows.length" class="pm-rows">
              <button v-for="r in money.expenses.rows" :key="r.name" type="button" class="pm-row"
                @click="openDrawer('Expense Claim', r.name)">
                <span class="pm-row-name">{{ r.name }}</span>
                <span class="pm-row-date">{{ r.date }}</span>
                <Chip size="sm" :color="statusColor(r.status)">{{ r.status }}</Chip>
                <span class="pm-row-amt">{{ fmtCurrency(r.amount) }}</span>
                <ChevronRight class="size-3 text-muted shrink-0" />
              </button>
            </div>
            <p v-else class="pm-empty">No Expense Claims in this period.</p>
            <div v-if="money.expenses.unbilled_count" class="flex items-center justify-between gap-4 py-1" style="margin-top:8px">
              <p class="text-[13px] text-muted leading-relaxed max-w-md">
                {{ money.expenses.unbilled_count }} billable expense line(s), not yet on an invoice —
                worth {{ fmtCurrency(money.expenses.unbilled_value) }} at cost/markup.
              </p>
              <Button size="sm" color="primary"
                :isDisabled="invoicingExpenses"
                @click="onGenerateExpenseInvoice">
                <Icon :icon="Receipt" class="size-3.5 mr-1" />
                {{ invoicingExpenses ? 'Generating…' : 'Generate Expense Invoice' }}
              </Button>
            </div>
          </AccordionItem>

          <!-- Sales Orders -->
          <AccordionItem>
            <template #title>
              <span class="pm-sec-title">Sales Orders <span class="pm-sec-count">{{ money.sales_orders.length }}</span></span>
            </template>
            <div v-if="money.sales_orders.length" class="pm-rows">
              <button v-for="r in money.sales_orders" :key="r.name" type="button" class="pm-row"
                @click="openDrawer('Sales Order', r.name)">
                <span class="pm-row-name">{{ r.name }}</span>
                <Chip size="sm" :color="statusColor(r.status)">{{ r.status }}</Chip>
                <span class="pm-row-amt">{{ fmtCurrency(r.grand_total) }}</span>
                <span class="pm-row-sub">{{ r.per_billed || 0 }}% billed</span>
                <ChevronRight class="size-3 text-muted shrink-0" />
              </button>
            </div>
            <p v-else class="pm-empty">No Sales Orders against this project.</p>
          </AccordionItem>

          <!-- Unbilled — the nag -->
          <AccordionItem>
            <template #title>
              <span class="pm-sec-title">Unbilled <span class="pm-sec-count">{{ money.labour.unbilled_hours }}h</span></span>
            </template>
            <div class="flex items-center justify-between gap-4 py-1">
              <p class="text-[13px] text-muted leading-relaxed max-w-md">
                {{ money.labour.unbilled_hours }} billable hour(s) logged, not yet on an invoice —
                worth {{ fmtCurrency(money.labour.unbilled_value) }} at current rates.
              </p>
              <Button size="sm" color="primary"
                :isDisabled="!money.labour.unbilled_hours || invoicing"
                @click="onGenerateInvoice">
                <Icon :icon="Receipt" class="size-3.5 mr-1" />
                {{ invoicing ? 'Generating…' : 'Generate Invoice' }}
              </Button>
            </div>
          </AccordionItem>

          <!-- Per-task cost breakdown — actual is period-scoped,
               same window as everything above; committed is deliberately
               all-time (open POs right now), so it's labelled distinctly
               rather than implying they share a window. -->
          <AccordionItem>
            <template #title>
              <span class="pm-sec-title">By Task <span class="pm-sec-count">{{ money.by_task.rows.length }}</span></span>
            </template>
            <div v-if="money.by_task.rows.length" class="pm-task-list">
              <div v-for="t in money.by_task.rows" :key="t.task" class="pm-task-row">
                <div class="pm-task-head">
                  <span class="pm-task-key">{{ t.task_key || (t.task === '__untasked__' ? '—' : t.task) }}</span>
                  <span class="pm-task-title">{{ t.title }}</span>
                  <span class="pm-task-figure">{{ fmtCurrency(t.actual.total) }} <span class="pm-task-figure-label">actual</span></span>
                  <span class="pm-task-figure pm-task-committed">{{ fmtCurrency(t.committed.total) }} <span class="pm-task-figure-label">committed (open POs, current)</span></span>
                </div>
                <div v-if="t.committed.rows.length" class="pm-rows pm-task-po-rows">
                  <button v-for="po in t.committed.rows" :key="po.purchase_order" type="button" class="pm-row"
                    @click="openDrawer('Purchase Order', po.purchase_order)">
                    <span class="pm-row-name">{{ po.purchase_order }}</span>
                    <Chip size="sm" :color="statusColor(po.status)">{{ po.status }}</Chip>
                    <span class="pm-row-amt">{{ fmtCurrency(po.amount) }}</span>
                    <ChevronRight class="size-3 text-muted shrink-0" />
                  </button>
                </div>
              </div>
            </div>
            <p v-else class="pm-empty">No task-attributed spend yet.</p>
          </AccordionItem>
        </Accordion>
      </template>
    </template>

    <MoneyDrawer v-model:open="drawerOpen" :project="projectName" :doctype="drawerDoctype" :name="drawerName"
      @submitted="load" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { debounce } from 'lodash'
import { useProjectStore } from '@/stores/project'
import { useEntitlementsStore } from '@/stores/entitlements'
import { getProjectMoney, generateInvoice, generateExpenseInvoice, searchErpnextProjects, linkErpnextProject, createAndLinkErpnextProject, unlinkErpnextProject, UpgradeRequiredError } from '@/utils/api'
import { toast } from 'vue-sonner'
import { Button, Chip, Skeleton, KpiTile, Accordion, AccordionItem, Input, Icon } from '@/ui'
import { Lock, Sparkles, Link2, Search, Plus, ChevronRight, Receipt, Hourglass, AlertTriangle } from 'lucide-vue-next'
import MoneyDrawer from '@/components/MoneyDrawer.vue'

const route  = useRoute()
const router = useRouter()
const store  = useProjectStore()
const ent    = useEntitlementsStore()

const unlocked    = computed(() => ent.can('profitability'))
const requiredPlan = computed(() => ent.requiredPlanFor('profitability'))

const projectKey  = computed(() => route.params.key)
const projectName = computed(() =>
  store.currentProject?.name ||
  store.projects.find(p => p.key === projectKey.value)?.name ||
  projectKey.value
)

const loading = ref(true)
const money   = ref(null)

// projectName falls back to the raw route key (e.g. "FWD") when neither
// store.currentProject nor store.projects is populated yet — true on a
// direct navigation or a page refresh straight to /workspace/:key/money,
// since (unlike Board) this page never itself loads the project. BP
// Project is autonamed field:project_name, so that fallback is never a
// valid docname and get_project_money 404s. Mirrors ProjectSettings.vue's
// same bootstrap-on-mount fix.
async function ensureProjectLoaded() {
  if (store.currentProject?.key === projectKey.value) return
  if (!store.projects.length) await store.fetchProjects()
  const proj = store.projects.find(p => p.key === projectKey.value)
  if (proj) await store.fetchBoard(proj.name)
}

async function load() {
  if (!unlocked.value) { loading.value = false; return }
  loading.value = true
  try {
    await ensureProjectLoaded()
    money.value = await getProjectMoney(projectName.value, 'last_30_days')
  } catch (e) {
    if (!(e instanceof UpgradeRequiredError)) {
      toast.error("Couldn't load project money", { description: String(e.message || e) })
    }
  } finally {
    loading.value = false
  }
}
onMounted(load)
// unlocked/ent.loaded: a cold page load races App.vue's async entitlements
// bootstrap — load() bails out while unlocked is still (falsely) false, and
// nothing re-fires it once entitlements actually resolve without this.
watch([projectName, unlocked, () => ent.loaded], load)

const periodLabel = computed(() => money.value ? `${money.value.from_date} → ${money.value.to_date}` : '')
const costTotal   = computed(() => money.value ? money.value.labour.cost + money.value.materials.total + money.value.expenses.total : 0)
// Only nag about the rate where it's actually settable (the settings billing
// tab hides Hourly rate for fixed-budget projects) and actually zero.
const showRateNudge = computed(() =>
  money.value?.linked &&
  !money.value.hourly_rate &&
  ['tm', 'retainer'].includes(money.value.project_type)
)
const marginPctLabel = computed(() => {
  if (!money.value || !money.value.revenue.total) return 'No revenue yet'
  return `${Math.round((money.value.margin / money.value.revenue.total) * 100)}% margin`
})

function fmtCurrency(v) {
  try {
    // Exact money on the deep-dive surface: the KPI must match the invoice it
    // drills into to the last paisa (602.45 ≠ 602). Round figures still show
    // clean (500, not 500.00). MarginReport's K/M abbreviation is a different,
    // deliberate choice for portfolio scanning — don't "unify" them.
    return new Intl.NumberFormat(undefined, { style: 'currency', currency: money.value?.currency || 'USD', minimumFractionDigits: 0, maximumFractionDigits: 2 }).format(Number(v || 0))
  } catch (e) {
    return Number(v || 0).toLocaleString(undefined, { maximumFractionDigits: 2 })
  }
}

const STATUS_COLOR = {
  paid: 'success', completed: 'success', closed: 'success',
  overdue: 'danger', unpaid: 'warning', 'partly paid': 'warning', 'to bill': 'warning',
  draft: 'default', cancelled: 'default', 'on hold': 'default',
}
function statusColor(status) { return STATUS_COLOR[(status || '').toLowerCase()] || 'default' }

function erpUrl(doctype, name) { return `/app/${doctype}/${encodeURIComponent(name)}` }

// Money drawer — every deep-link below opens the in-app read-only
// drawer instead of a new ERPNext tab; the raw URL lives one click further
// in, as the drawer's own "Open in ERPNext ↗" escape hatch.
const drawerOpen    = ref(false)
const drawerDoctype = ref('')
const drawerName    = ref('')
function openDrawer(doctype, name) {
  drawerDoctype.value = doctype
  drawerName.value = name
  drawerOpen.value = true
}

function goUpgrade() {
  router.push({ name: 'Pricing' }).catch(() => { window.location.hash = '#/pricing' })
}

// ── Unlinked state: search-and-link / create-and-link ─────────────────────
const searchQ = ref('')
const searchResults = ref([])
const linking = ref(false)
const unlinking = ref(false)

const onSearch = debounce(async () => {
  if (!searchQ.value) { searchResults.value = []; return }
  try {
    searchResults.value = await searchErpnextProjects(searchQ.value)
  } catch (e) {
    searchResults.value = []
  }
}, 250)

async function pickProject(r) {
  if (r.already_linked || linking.value) return
  linking.value = true
  try {
    await linkErpnextProject(projectName.value, r.name)
    toast.success(`Linked to ${r.name}`)
    searchQ.value = ''
    searchResults.value = []
    await load()
  } catch (e) {
    toast.error(e.message || 'Failed to link project')
  } finally {
    linking.value = false
  }
}

async function doCreateAndLink() {
  if (linking.value) return
  linking.value = true
  try {
    const res = await createAndLinkErpnextProject(projectName.value)
    toast.success(`Created and linked ${res.erpnext_project}`)
    await load()
  } catch (e) {
    toast.error(e.message || 'Failed to create ERPNext Project')
  } finally {
    linking.value = false
  }
}

async function doUnlink() {
  if (unlinking.value) return
  if (!window.confirm('Unlink this ERPNext Project? This only clears the link — no data is deleted in either system.')) return
  unlinking.value = true
  try {
    await unlinkErpnextProject(projectName.value)
    toast.success('ERPNext Project unlinked')
    // Immediately transition to unlinked state, then refresh
    money.value = { linked: false, project: projectName.value }
    await load()
  } catch (e) {
    toast.error(e.message || 'Failed to unlink project')
  } finally {
    unlinking.value = false
  }
}

const invoicing = ref(false)

async function onGenerateInvoice() {
  if (invoicing.value) return
  invoicing.value = true
  try {
    const res = await generateInvoice(projectName.value)
    toast.success(`Draft Sales Invoice ${res.sales_invoice} created`, {
      description: `${res.hours_invoiced}h invoiced — review and submit it in ERPNext.`,
      action: { label: 'Open', onClick: () => window.open(erpUrl('sales-invoice', res.sales_invoice), '_blank') },
    })
    await load()
  } catch (e) {
    if (!(e instanceof UpgradeRequiredError)) {
      toast.error(e.message || 'Failed to generate invoice')
    }
  } finally {
    invoicing.value = false
  }
}

const invoicingExpenses = ref(false)

async function onGenerateExpenseInvoice() {
  if (invoicingExpenses.value) return
  invoicingExpenses.value = true
  try {
    const res = await generateExpenseInvoice(projectName.value)
    toast.success(`Draft Sales Invoice ${res.sales_invoice} created`, {
      description: `${res.expenses_invoiced} expense line(s) invoiced — review and submit it in ERPNext.`,
      action: { label: 'Open', onClick: () => window.open(erpUrl('sales-invoice', res.sales_invoice), '_blank') },
    })
    await load()
  } catch (e) {
    if (!(e instanceof UpgradeRequiredError)) {
      toast.error(e.message || 'Failed to generate invoice')
    }
  } finally {
    invoicingExpenses.value = false
  }
}
</script>

<style scoped>
.pm-root { padding: 20px 24px 40px; }

.pm-lock-banner, .pm-unlinked {
  display: flex; align-items: flex-start; gap: 16px;
  padding: 20px; border-radius: 10px;
  border: 1px solid var(--border-secondary);
  background: color-mix(in oklab, var(--primary) 5%, transparent);
}
.pm-lock-icon {
  width: 40px; height: 40px; border-radius: 8px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  background: var(--overlay); border: 1px solid var(--border); box-shadow: var(--shadow-xs);
}

.pm-linked-header {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
  margin-bottom: 16px; padding: 8px 14px;
  border: 1px solid var(--border-secondary); border-radius: 8px;
  pointer-events: none;
}
.pm-linked-header > * {
  pointer-events: auto;
}

.pm-note {
  display: flex; align-items: center; gap: 10px;
  margin-bottom: 12px; padding: 10px 14px;
  border: 1px solid var(--border-secondary); border-radius: 8px;
  color: var(--muted);
}
.pm-note-draft, .pm-note-rate {
  border-color: color-mix(in oklab, var(--warning) 35%, var(--border-secondary));
  background: color-mix(in oklab, var(--warning) 7%, transparent);
  color: var(--foreground);
}
.pm-note-link {
  background: none; border: none; padding: 0; font: inherit; cursor: pointer;
  font-size: 12px; font-weight: 600; color: var(--accent);
  text-decoration: none; white-space: nowrap;
}
.pm-note-link:hover { text-decoration: underline; }

.pm-budget-row {
  display: flex; align-items: center; gap: 10px;
  margin-bottom: 20px; padding: 10px 14px;
  border: 1px solid var(--border-secondary); border-radius: 8px;
}
.pm-budget-bar { flex: 1; height: 6px; border-radius: 999px; background: var(--surface-secondary); overflow: hidden; }
.pm-budget-fill { height: 100%; border-radius: 999px; background: var(--accent); transition: width .3s; }
.pm-budget-fill.pm-watch { background: var(--warning); }
.pm-budget-fill.pm-over  { background: var(--danger); }

.pm-sections { border: 1px solid var(--border-secondary); border-radius: 10px; padding: 4px 12px; }
.pm-sec-title { display: flex; align-items: center; gap: 8px; }
.pm-sec-count { font-size: 11px; font-weight: 600; color: var(--muted); background: var(--surface-secondary); padding: 1px 7px; border-radius: 999px; }

.pm-rows { display: flex; flex-direction: column; }
.pm-row {
  display: flex; align-items: center; gap: 12px; width: 100%;
  height: 36px; padding: 0 8px; border-radius: 6px;
  background: none; border: none; font: inherit; text-align: left; cursor: pointer;
  text-decoration: none; transition: background .08s;
}
.pm-row:hover { background: var(--surface-secondary); }
.pm-row-name { font-size: 12.5px; font-weight: 600; color: var(--accent); font-family: monospace; flex-shrink: 0; }
.pm-row-date { font-size: 12px; color: var(--muted); flex-shrink: 0; }
.pm-row-amt { font-size: 13px; font-weight: 600; color: var(--foreground); margin-left: auto; font-variant-numeric: tabular-nums; }
.pm-row-sub { font-size: 11.5px; color: var(--muted); flex-shrink: 0; }
.pm-empty { font-size: 12.5px; color: var(--muted); padding: 8px; }

.pm-task-list { display: flex; flex-direction: column; gap: 2px; }
.pm-task-row { padding: 6px 8px; border-radius: 6px; }
.pm-task-row + .pm-task-row { border-top: 1px solid var(--border-secondary); }
.pm-task-head { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.pm-task-key { font-size: 12px; font-weight: 600; color: var(--accent); font-family: monospace; flex-shrink: 0; }
.pm-task-title { font-size: 12.5px; color: var(--foreground); flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pm-task-figure { font-size: 12.5px; font-weight: 600; color: var(--foreground); font-variant-numeric: tabular-nums; display: flex; align-items: baseline; gap: 4px; flex-shrink: 0; }
.pm-task-figure-label { font-size: 10.5px; font-weight: 500; color: var(--muted); white-space: nowrap; }
.pm-task-committed { color: var(--warning); }
.pm-task-po-rows { margin-top: 2px; padding-left: 12px; }
</style>
