<template>
  <div class="flex flex-col min-h-full">

    <!-- Free trial banner — register()'s no-payment 60-day Business trial.
         Informational, not urgent: no countdown-panic styling, no CTA to
         upgrade before it "runs out" — it just says what's true and that
         nothing breaks or gets deleted when it ends. -->
    <div v-if="ent.isTrial" class="border-b px-8 py-3" style="background: var(--accent-soft); border-color: var(--border);">
      <div class="max-w-6xl mx-auto w-full flex items-center gap-2.5 text-[13px]" style="color: var(--accent-soft-foreground);">
        <Sparkles class="size-4 shrink-0" :stroke-width="2" />
        <span>
          You're on a free <strong>Business</strong> trial —
          <strong class="tabular-nums">{{ ent.trialDaysRemaining }}</strong>
          day{{ ent.trialDaysRemaining === 1 ? '' : 's' }} left, no card required.
          When it ends you'll move to the free Starter plan automatically — nothing is deleted.
        </span>
      </div>
    </div>

    <!-- ─── ACCOUNT HEADER — who you are billed as, not a marketing pitch ─── -->
    <section class="border-b" style="border-color: var(--border);">
      <div class="px-8 py-6 max-w-6xl mx-auto w-full">
        <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <h1 class="text-[20px] font-bold tracking-tight" style="color: var(--foreground);">Billing &amp; Plan</h1>
            <p class="text-[13px] mt-1" style="color: var(--muted);">Manage your workspace's subscription, seats, and invoices.</p>
          </div>
          <button type="button" :disabled="portalBusy" @click="openPortal"
            class="inline-flex items-center gap-2 px-4 py-2 rounded-md text-[13px] font-medium transition-colors shrink-0 disabled:opacity-60"
            style="background: var(--surface-secondary); color: var(--foreground); border: 1px solid var(--border);"
          >
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.75">
              <path stroke-linecap="round" stroke-linejoin="round" d="M2.25 8.25h19.5M2.25 9h19.5m-16.5 5.25h6m-6 2.25h3m-9-11.25h18a1.5 1.5 0 011.5 1.5v10.5a1.5 1.5 0 01-1.5 1.5h-18a1.5 1.5 0 01-1.5-1.5V6a1.5 1.5 0 011.5-1.5z" />
            </svg>
            {{ portalBusy ? 'Opening…' : 'Invoices & payment method' }}
          </button>
        </div>

        <!-- Current plan summary -->
        <div class="mt-6 rounded-lg p-5" style="background: var(--surface); border: 1px solid var(--border);">
          <div class="flex flex-wrap items-center gap-x-8 gap-y-4">
            <div>
              <p class="text-[11px] font-medium uppercase tracking-wider" style="color: var(--muted);">Current plan</p>
              <div class="flex items-center gap-2 mt-1">
                <span class="text-[16px] font-semibold" style="color: var(--foreground);">{{ ent.tierLabel }}</span>
                <span v-if="statusNote" class="text-[11px] font-medium px-2 py-0.5 rounded-full"
                  :style="{ background: statusTone.bg, color: statusTone.fg }">{{ statusNote }}</span>
              </div>
            </div>
            <div v-if="renewalLabel">
              <p class="text-[11px] font-medium uppercase tracking-wider" style="color: var(--muted);">{{ activeSub?.status === 'trialing' ? 'Trial ends' : 'Renews' }}</p>
              <p class="text-[13px] mt-1 tabular-nums" style="color: var(--foreground);">{{ renewalLabel }}</p>
            </div>
            <div v-if="ent.seatsTotal">
              <p class="text-[11px] font-medium uppercase tracking-wider" style="color: var(--muted);">Seats</p>
              <p class="text-[13px] mt-1 tabular-nums" :style="{ color: ent.isAtCapacity ? 'var(--danger)' : 'var(--foreground)' }">
                {{ ent.seatsUsed }} / {{ ent.seatsTotal }} used
              </p>
            </div>
            <div class="ml-auto" v-if="ent.tier !== 'starter'">
              <RouterLink to="/workspace/settings" class="text-[12.5px]" style="color: var(--accent);">Workspace settings →</RouterLink>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Loading state -->
    <div v-if="loading" class="flex flex-col items-center justify-center py-24 max-w-5xl mx-auto w-full">
      <div class="size-6 rounded-full animate-spin" style="border: 2px solid var(--border); border-top-color: var(--accent);" />
      <p class="text-[13px] mt-4" style="color: var(--muted);">Loading plans…</p>
    </div>

    <!-- Error state -->
    <div v-else-if="error" class="flex flex-col items-center justify-center py-24 max-w-5xl mx-auto w-full">
      <div class="w-12 h-12 rounded-full flex items-center justify-center mb-4" style="background: var(--danger-soft);">
        <svg class="w-5 h-5" style="color: var(--danger);" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
        </svg>
      </div>
      <p class="text-[14px]" style="color: var(--muted);">Plan details temporarily unavailable.</p>
      <p class="text-[12px] mt-1" style="color: var(--muted);">Check your connection and try again.</p>
      <button @click="loadPlans"
        class="mt-5 px-5 py-2 rounded-md text-[13px] font-medium transition-colors"
        style="background: var(--accent); color: var(--accent-foreground);"
      >Try again</button>
    </div>

    <template v-else>

    <!-- ─── CHANGE PLAN ─── -->
    <div class="px-8 pt-10 pb-4 max-w-6xl mx-auto w-full">
      <div class="flex flex-wrap items-end justify-between gap-4 mb-6">
        <div>
          <h2 class="text-[16px] font-bold" style="color: var(--foreground);">Change your plan</h2>
          <p class="text-[13px] mt-0.5" style="color: var(--muted);">Flat per-workspace pricing — no per-user math.</p>
        </div>
        <!-- Billing toggle -->
        <div class="inline-flex items-center gap-3 p-1 rounded-lg" style="background: var(--surface-secondary);">
          <button
            v-for="opt in billingOptions"
            :key="opt.value"
            @click="billing = opt.value"
            class="relative px-4 py-2 text-[13px] font-medium rounded-md transition-colors duration-150"
            :class="billing === opt.value
              ? 'shadow-sm' : 'hover:opacity-70'"
            :style="billing === opt.value
              ? 'background: var(--surface); color: var(--foreground);'
              : 'background: transparent; color: var(--muted);'"
          >
            {{ opt.label }}
            <span v-if="opt.value === 'yearly' && annualSavingsLabel"
              class="ml-1.5 text-[10px] font-semibold px-1.5 py-0.5 rounded-full"
              :style="billing === opt.value
                ? 'background: var(--accent-soft); color: var(--accent-soft-foreground);'
                : 'background: var(--surface); color: var(--muted);'"
            >{{ annualSavingsLabel }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- ─── PAID PLAN CARDS ─── -->
    <div class="px-8 pb-8 max-w-6xl mx-auto w-full">
      <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
        <PlanCard
          v-for="plan in paidPlans"
          :key="plan.id"
          :plan="plan"
          :billing="billing"
          :region="region"
          :current="currentPlan"
          :checkoutBusy="checkoutBusy"
          @select="selectPlan(plan)"
        />
      </div>
    </div>

    <!-- ─── COMMUNITY + ENTERPRISE ─── -->
    <div class="px-8 pb-12 max-w-6xl mx-auto w-full">
      <div class="grid grid-cols-1 md:grid-cols-2 gap-6">

        <!-- Community (Free) -->
        <template v-if="starterPlan">
          <div class="flex flex-col rounded-lg p-7 relative transition-shadow duration-200 hover:shadow-md"
            style="background: var(--surface); border: 1px solid var(--border);">
            <div class="flex items-center gap-3 mb-4">
              <div class="w-9 h-9 rounded-md flex items-center justify-center"
                style="background: var(--accent-soft); color: var(--accent-soft-foreground);">
                <svg class="w-[18px] h-[18px]" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
                </svg>
              </div>
              <div>
                <h3 class="text-[16px] font-semibold" style="color: var(--foreground);">{{ starterPlan.name }}</h3>
                <p class="text-[12px]" style="color: var(--muted);">{{ starterPlan.tagline }}</p>
              </div>
            </div>
            <div class="mb-5">
              <span class="text-[28px] font-bold" style="color: var(--foreground);">Free</span>
              <span class="text-[12px] ml-1" style="color: var(--muted);">{{ starterPlan.per }}</span>
            </div>
            <ul class="space-y-2.5 mb-6 flex-1">
              <li v-for="l in starterPlan.limits" :key="l"
                class="flex items-start gap-2.5 text-[13px]" style="color: var(--foreground);">
                <svg class="w-4 h-4 shrink-0 mt-0.5" style="color: var(--success);" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                </svg>
                {{ l }}
              </li>
            </ul>
            <button type="button" :disabled="currentPlan === 'starter'"
              class="w-full py-2.5 rounded-md text-[13px] font-medium transition-colors"
              :class="currentPlan === 'starter' ? 'cursor-default' : ''"
              :style="currentPlan === 'starter'
                ? 'background: var(--surface-secondary); color: var(--muted); border: 1px solid var(--border);'
                : 'background: transparent; color: var(--foreground); border: 1px solid var(--border); cursor: pointer;'"
            >{{ currentPlan === 'starter' ? 'Current plan' : 'Downgrade to Community' }}</button>
          </div>
        </template>

        <!-- Enterprise — driven by the real "enterprise" plan record (is_contact:true),
             never an invented price. -->
        <div v-if="enterprisePlan" class="flex flex-col rounded-lg p-7 relative transition-shadow duration-200 hover:shadow-md"
          style="background: var(--surface); border: 1px solid var(--border);">
          <div class="flex items-center gap-3 mb-4">
            <div class="w-9 h-9 rounded-md flex items-center justify-center"
              style="background: var(--accent-soft); color: var(--accent-soft-foreground);">
              <svg class="w-[18px] h-[18px]" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M3.75 21h16.5M4.5 3h15M5.25 3v18m13.5-18v18M9 6.75h1.5m-1.5 3h1.5m-1.5 3h1.5m3-6H15m-1.5 3H15m-1.5 3H15M9 21v-3.375c0-.621.504-1.125 1.125-1.125h3.75c.621 0 1.125.504 1.125 1.125V21" />
              </svg>
            </div>
            <div>
              <h3 class="text-[16px] font-semibold" style="color: var(--foreground);">{{ enterprisePlan.name }}</h3>
              <p class="text-[12px]" style="color: var(--muted);">{{ enterprisePlan.tagline }}</p>
            </div>
          </div>
          <div class="mb-5">
            <span class="text-[28px] font-bold" style="color: var(--foreground);">Custom</span>
            <span class="text-[12px] ml-1" style="color: var(--muted);">pricing — contact us</span>
          </div>
          <ul class="space-y-2.5 mb-6 flex-1">
            <li v-for="l in enterprisePlan.limits" :key="l"
              class="flex items-start gap-2.5 text-[13px]" style="color: var(--foreground);">
              <svg class="w-4 h-4 shrink-0 mt-0.5" style="color: var(--success);" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                <path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5" />
              </svg>
              {{ l }}
            </li>
            <li class="pt-2 mt-2" style="border-top: 1px solid var(--border);">
              <span class="text-[11px] font-medium uppercase tracking-wider" style="color: var(--muted);">Everything in Business, plus:</span>
            </li>
            <li v-for="feat in enterprisePlan.features?.slice(1)" :key="feat"
              class="flex items-start gap-2.5 text-[13px]" style="color: var(--foreground);">
              <svg class="w-4 h-4 shrink-0 mt-0.5" style="color: var(--accent-soft-foreground);" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                <path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5" />
              </svg>
              {{ feat }}
            </li>
          </ul>
          <button type="button" @click="contactSales"
            class="w-full py-2.5 rounded-md text-[13px] font-medium transition-colors hover:opacity-90"
            style="background: var(--accent); color: var(--accent-foreground);"
          >Contact sales</button>
        </div>
      </div>
    </div>

    <!-- ─── FEATURE COMPARISON — grouped by category, not one flat list ─── -->
    <div class="px-8 pb-12 max-w-6xl mx-auto w-full">
      <div class="text-center mb-8">
        <h2 class="text-[18px] font-bold" style="color: var(--foreground);">Compare plans in detail</h2>
        <p class="text-[13px] mt-1" style="color: var(--muted);">Every plan includes core collaboration features. Premium capabilities unlock at higher tiers.</p>
      </div>
      <div class="rounded-lg overflow-hidden"
        style="background: var(--surface); border: 1px solid var(--border);">
        <div class="overflow-x-auto">
          <table class="w-full text-[13px]" style="border-collapse: separate; border-spacing: 0;">
            <thead>
              <tr>
                <th class="text-left px-5 py-3.5 font-semibold sticky left-0 z-10 min-w-[200px]"
                  style="color: var(--foreground); background: var(--surface); border-bottom: 1px solid var(--border);">
                  Feature
                </th>
                <th v-for="col in planColumns" :key="col.tier"
                  class="text-center px-4 py-3.5 font-semibold min-w-[110px]"
                  style="color: var(--foreground); background: var(--surface); border-bottom: 1px solid var(--border);">
                  <div>{{ col.name }}</div>
                  <div class="text-[11px] font-normal mt-0.5" style="color: var(--muted);">{{ col.seats }}</div>
                </th>
              </tr>
            </thead>
            <tbody>
              <template v-for="group in featureGroups" :key="group.category">
                <tr>
                  <td :colspan="planColumns.length + 1" class="px-5 py-2 text-[11px] font-semibold uppercase tracking-wider"
                    style="color: var(--muted); background: var(--surface-secondary);">
                    {{ group.category }}
                  </td>
                </tr>
                <tr v-for="(row, ri) in group.rows" :key="row.label"
                  class="transition-colors"
                  :style="rowStyle(ri)">
                  <td class="px-5 py-3 text-[13px] sticky left-0 z-10"
                    :style="cellStyle(ri)">
                    {{ row.label }}
                  </td>
                  <td v-for="col in planColumns" :key="col.tier"
                    class="px-4 py-3 text-center">
                    <span v-if="typeof row[col.tier] === 'boolean'">
                      <svg v-if="row[col.tier]" class="w-[18px] h-[18px] mx-auto" style="color: var(--success);" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                      </svg>
                      <svg v-else class="w-[18px] h-[18px] mx-auto" style="color: var(--muted);" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M18 12H6" />
                      </svg>
                    </span>
                    <span v-else class="text-[12px]" style="color: var(--muted);">{{ row[col.tier] }}</span>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- ─── FAQ ─── -->
    <div class="px-8 pb-16 max-w-3xl mx-auto w-full">
      <h2 class="text-[18px] font-bold text-center mb-8" style="color: var(--foreground);">Common questions</h2>
      <div class="rounded-lg overflow-hidden" style="background: var(--surface); border: 1px solid var(--border);">
        <div class="divide-y" style="border-color: var(--border);">
          <div v-for="(faq, fi) in FAQS" :key="fi">
            <button
              type="button"
              class="w-full flex items-center justify-between gap-4 px-6 py-[18px] text-[13px] font-medium cursor-pointer transition-colors text-left"
              style="color: var(--foreground);"
              @click="toggleFaq(fi)"
            >
              {{ faq.q }}
              <svg class="w-4 h-4 shrink-0 transition-transform duration-200" :style="{ color: 'var(--muted)', transform: openFaqs.has(fi) ? 'rotate(180deg)' : 'rotate(0deg)' }" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
            </button>
            <div class="grid transition-[grid-template-rows] duration-200 ease-out" :style="{ gridTemplateRows: openFaqs.has(fi) ? '1fr' : '0fr' }">
              <div class="overflow-hidden">
                <p class="px-6 pb-[18px] text-[13px] leading-relaxed" style="color: var(--muted);">{{ faq.a }}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
      <p class="text-[12px] text-center mt-6" style="color: var(--muted);">
        Questions? <a href="mailto:sales@batcherp.com" style="color: var(--accent); text-decoration: underline;">Contact support</a>
      </p>
    </div>

    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, defineComponent, h } from 'vue'
import { toast } from 'vue-sonner'
import { Sparkles } from 'lucide-vue-next'
import { useEntitlementsStore } from '@/stores/entitlements'
import { createCheckoutSession, getPlans, getMySubscriptions, getBillingPortal } from '@/utils/api'

const ent = useEntitlementsStore()
const region = ref('global')
const billing = ref('monthly')
// Computed, not a snapshot ref — `ent.tier` starts as "starter" and updates
// asynchronously once the entitlements store hydrates (same class of race
// condition Goals.vue also had to guard against). A plain `ref(ent.tier)` captured
// at setup time would permanently show "Community" as current even for a
// paid workspace whose entitlements just hadn't loaded yet.
const currentPlan = computed(() => ent.tier || 'starter')
const plans = ref([])
const checkoutBusy = ref('')
const portalBusy = ref(false)

const billingOptions = [
  { value: 'monthly', label: 'Monthly' },
  { value: 'yearly',  label: 'Annual' },
]

const loading = ref(true)
const error = ref(false)

// ── Current subscription (renewal date, status) — real data, already
// wired end to end, just never called from any page before this one. ──
const subscriptions = ref([])
const activeSub = computed(() =>
  subscriptions.value.find(s => s.status === 'active' || s.status === 'trialing')
    || subscriptions.value.find(s => s.status === 'on_hold')
    || null
)
const renewalLabel = computed(() => {
  const end = activeSub.value?.current_period_end
  if (!end) return ''
  const d = new Date(end)
  if (isNaN(d)) return ''
  return d.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
})
const statusNote = computed(() => {
  const s = activeSub.value?.status
  if (s === 'trialing') return 'Trial'
  if (s === 'on_hold') return 'Payment issue'
  return ''
})
const statusTone = computed(() => {
  const s = activeSub.value?.status
  if (s === 'on_hold') return { bg: 'var(--warning-soft)', fg: 'var(--warning-soft-foreground)' }
  return { bg: 'var(--accent-soft)', fg: 'var(--accent-soft-foreground)' }
})

async function loadSubscriptions() {
  try {
    const data = await getMySubscriptions()
    if (Array.isArray(data)) subscriptions.value = data
  } catch (e) {
    // Non-fatal — the page still works without renewal-date context.
    console.error('[Billing] failed to load subscriptions:', e)
  }
}

async function openPortal() {
  portalBusy.value = true
  try {
    const res = await getBillingPortal()
    if (res.portal_url) window.open(res.portal_url, '_blank')
    else toast.error(res.detail || 'No billing portal available yet')
  } catch (e) {
    toast.error(e.message || 'Could not open the billing portal')
  } finally {
    portalBusy.value = false
  }
}

function normalizePlan(p) {
  const monthly = p.price_monthly || 0
  const yearly = p.price_yearly
  return {
    id: p.id || p.tier,
    name: p.display_name || p.name,
    tagline: p.tagline || '',
    price: {
      global: monthly,
      monthly,
      yearly,
    },
    priceYearly: {
      global: yearly,
      monthly: yearly,
      yearly,
    },
    per: p.per || '/workspace / month',
    highlight: p.is_popular === true,
    limits: p.limits || p.features || [],
    seats: p.max_users,
    features: p.features || [],
    feature_flags: p.feature_flags || {},
    is_contact: p.is_contact === true,
    tier: p.tier,
  }
}

const normalizedPlans = computed(() => plans.value.map(normalizePlan))
const starterPlan = computed(() => normalizedPlans.value.find(p => p.id === 'starter'))
const enterprisePlan = computed(() => normalizedPlans.value.find(p => p.id === 'enterprise'))
const paidPlans = computed(() => normalizedPlans.value.filter(p => p.id !== 'starter' && p.id !== 'enterprise'))

// Real, computed from the loaded catalog — never a guessed/borrowed percentage.
const annualSavingsLabel = computed(() => {
  const p = paidPlans.value.find(p => p.price.monthly > 0 && p.price.yearly > 0)
  if (!p) return ''
  const pct = Math.round((1 - p.price.yearly / (p.price.monthly * 12)) * 100)
  return pct > 0 ? `SAVE ${pct}%` : ''
})

const TIER_ORDER = ['starter', 'growth', 'pro', 'business', 'enterprise']
const planColumns = computed(() => {
  const byTier = {}
  for (const p of normalizedPlans.value) byTier[p.tier] = p
  return TIER_ORDER
    .map(tier => {
      const p = byTier[tier]
      if (!p) return null
      return {
        tier: p.tier,
        name: p.name,
        seats: p.seats == null ? 'Unlimited' : String(p.seats),
        featureFlags: p.feature_flags || {},
      }
    })
    .filter(Boolean)
})

const TIER_RANK = { starter: 0, growth: 1, pro: 1, team: 1, business: 2, enterprise: 3, dev: 99 }

// Grouped by category (matches every competitor's pattern — a flat 27-row
// list is unscannable). ERP & Finance gets its own section deliberately:
const FEATURE_GROUPS = [
  {
    category: 'Core project management',
    rows: [
      { label: 'Members',                   gate: null, format: 'count' },
      { label: 'Board, List & Gantt views',  gate: null, format: 'bool' },
      { label: 'Sprints & Backlog',          gate: null, format: 'bool' },
      { label: 'Custom fields',              gate: null, format: 'bool' },
      { label: 'Saved views',                gate: null, format: 'bool' },
      { label: 'Workload & Utilization',     gate: null, format: 'bool' },
    ],
  },
  {
    category: 'Collaboration & automation',
    rows: [
      { label: 'Automations',                gate: 'automations' },
      { label: 'Webhooks',                   gate: 'webhooks' },
      { label: 'Realtime live updates',      gate: 'realtime' },
      { label: 'Draw (whiteboard)',          gate: 'draw' },
      { label: 'Share links',                gate: 'share_links' },
      { label: 'Notification rules',         gate: 'notification_rules' },
      { label: 'Automation scheduler',       gate: 'scheduler' },
    ],
  },
  {
    category: 'Forms & templates',
    rows: [
      { label: 'Task & project templates',   gate: 'templates' },
      { label: 'Public intake forms',        gate: 'intake_forms' },
    ],
  },
  {
    category: 'ERP & finance',
    rows: [
      { label: 'ERPNext integration',        gate: 'integrations' },
      { label: 'Timesheets',                 gate: 'time_tracking' },
      { label: 'Margin report',              gate: 'profitability' },
      { label: 'ERPNext invoice write-back', gate: 'billing_writeback' },
    ],
  },
  {
    category: 'Insights & reporting',
    rows: [
      { label: 'Portfolio view',             gate: 'portfolio' },
      { label: 'Goals / OKRs',                gate: 'goals' },
      { label: 'Dashboard builder',          gate: 'dashboards' },
      { label: 'Exports (XLSX/PDF)',         gate: 'exports' },
    ],
  },
  {
    category: 'Enterprise & security',
    rows: [
      { label: 'API access',                 gate: 'api' },
      { label: 'SSO / SAML',                 gate: 'sso' },
      { label: 'Audit log',                  gate: 'audit_log' },
      { label: 'SLA guarantee',              gate: 'sso' },
    ],
  },
]

function resolveCell(def, col, fg) {
  if (def.format === 'count') return col.seats
  if (!def.gate) return true
  const minTier = fg[def.gate]
  if (minTier) return (TIER_RANK[col.tier] || 0) >= (TIER_RANK[minTier] || 0)
  if (col.featureFlags[def.gate] !== undefined) return col.featureFlags[def.gate]
  return false
}

const featureGroups = computed(() => {
  const cols = planColumns.value
  if (!cols.length) return []
  const fg = ent.featureMinTier || {}
  return FEATURE_GROUPS.map(group => ({
    category: group.category,
    rows: group.rows.map(def => {
      const row = { label: def.label }
      for (const col of cols) row[col.tier] = resolveCell(def, col, fg)
      return row
    }),
  }))
})

async function loadPlans() {
  loading.value = true
  error.value = false
  try {
    const data = await getPlans()
    if (Array.isArray(data) && data.length) {
      plans.value = data
      return
    }
    throw new Error('Empty plans response')
  } catch (e) {
    if (window.location.hostname === 'localhost') {
      try {
        const res = await fetch('/plans.json')
        if (res.ok) {
          const data = await res.json()
          if (Array.isArray(data) && data.length) {
            plans.value = data
            return
          }
        }
      } catch (_) { /* fall through */ }
    }
    console.error('[Billing] failed to load plans:', e)
    error.value = true
    plans.value = []
  } finally {
    loading.value = false
  }
}

function rowStyle(ri) {
  return ri % 2 !== 0 ? { background: 'color-mix(in oklab, var(--accent) 2%, transparent)' } : {}
}
function cellStyle(ri) {
  return {
    color: 'var(--foreground)',
    background: ri % 2 === 0 ? 'var(--surface)' : 'color-mix(in oklab, var(--accent) 2%, transparent)',
  }
}

onMounted(() => {
  loadPlans()
  loadSubscriptions()
})

async function selectPlan(plan) {
  if (plan.id === currentPlan.value || plan.id === 'starter') return
  checkoutBusy.value = plan.id
  try {
    const res = await createCheckoutSession(plan.id, billing.value)
    if (res.checkout_url) {
      window.location.href = res.checkout_url
    } else {
      toast.error('Could not create checkout session')
    }
  } catch (e) {
    toast.error(e.message || 'Checkout failed')
  } finally {
    checkoutBusy.value = ''
  }
}

function contactSales() {
  window.open('mailto:sales@batcherp.com?subject=Enterprise plan inquiry', '_blank')
}

// First question open by default — an animated grid-rows accordion instead
// of native <details>, which has no transition at all.
const openFaqs = ref(new Set([0]))
function toggleFaq(i) {
  const next = new Set(openFaqs.value)
  next.has(i) ? next.delete(i) : next.add(i)
  openFaqs.value = next
}

const FAQS = [
  {
    q: 'What counts as a "member"?',
    a: 'Any enabled System User who is a member of at least one project or team. Guests and disabled users don\'t count toward your seat limit.',
  },
  {
    q: 'What happens when I hit my seat limit?',
    a: 'Adding another member is blocked until you upgrade to a plan with more seats. Existing members keep working normally.',
  },
  {
    q: 'Is pricing per user or per workspace?',
    a: 'Per workspace. One flat price covers up to the listed number of members — no per-seat math or hidden fees.',
  },
  {
    q: 'All features included at every tier?',
    a: 'Most features are available on every plan. Enterprise-grade capabilities like SSO, audit log, and SLA guarantees are Enterprise-only. See the feature comparison table above for exactly what\'s included at each tier.',
  },
  {
    q: 'Can I switch plans at any time?',
    a: 'Yes. Upgrades take effect immediately. Downgrades apply at the next billing cycle.',
  },
  {
    q: 'What happens to my data if I downgrade?',
    a: 'Nothing is deleted. Premium-only views like Goals, Portfolio, and Dashboards are hidden until you upgrade again, but the underlying data stays exactly as it was.',
  },
  {
    q: 'Where do I find my invoices or update my payment method?',
    a: 'Click "Invoices & payment method" above — it opens your secure billing portal (hosted by our payment processor) with your full invoice history, receipts, and card details.',
  },
]

const PlanCard = defineComponent({
  props: ['plan', 'billing', 'region', 'current', 'checkoutBusy'],
  emits: ['select'],
  setup(props, { emit }) {
    const isCurrent = computed(() => props.plan.id === props.current)
    const isBusy = computed(() => props.checkoutBusy === props.plan.id)
    const isYearly = computed(() => props.billing === 'yearly')

    // The Annual toggle shows the real annual total (price.yearly), not the
    // monthly number with a caption bolted on — was showing the same figure
    // regardless of the toggle before this fix.
    const price = computed(() => {
      const p = props.plan
      if (!p.price) return 0
      return isYearly.value ? (p.price.yearly || 0) : (p.price.monthly || 0)
    })
    const periodSuffix = computed(() => isYearly.value ? '/workspace / year' : '/workspace / month')

    const currency = computed(() => '$')

    const btnText = computed(() => {
      if (isCurrent.value) return 'Current plan'
      if (isBusy.value) return 'Redirecting…'
      if (price.value === 0) return 'Get started'
      return `Upgrade to ${props.plan.name}`
    })

    return () => {
      const p = props.plan
      return h('div', {
        class: [
          'flex flex-col rounded-lg p-7 relative transition-shadow duration-200',
          isCurrent.value
            ? 'ring-2'
            : p.highlight
              ? 'hover:shadow-lg'
              : 'hover:shadow-md',
        ].join(' '),
        style: {
          background: isCurrent.value
            ? 'color-mix(in oklab, var(--accent-soft) 60%, var(--surface))'
            : 'var(--surface)',
          border: isCurrent.value
            ? '1px solid color-mix(in oklab, var(--accent) 40%, transparent)'
            : p.highlight
              ? '1px solid color-mix(in oklab, var(--accent) 30%, transparent)'
              : '1px solid var(--border)',
        },
      }, [
        // Badge row
        h('div', { class: 'flex items-center justify-between mb-5' }, [
          p.highlight && !isCurrent.value
            ? h('span', {
                class: 'text-[10px] font-semibold px-2.5 py-0.5 rounded-full',
                style: {
                  background: 'var(--accent)',
                  color: 'var(--accent-foreground)',
                },
              }, 'Most popular')
            : h('span'),
          isCurrent.value
            ? h('span', {
                class: 'text-[10px] font-semibold px-2.5 py-0.5 rounded-full',
                style: {
                  background: 'color-mix(in oklab, var(--accent) 12%, transparent)',
                  color: 'var(--accent-soft-foreground)',
                },
              }, 'Current plan')
            : h('span'),
        ]),

        // Price
        h('div', { class: 'mb-5' }, [
          h('h3', {
            class: 'text-[18px] font-bold',
            style: { color: 'var(--foreground)' },
          }, p.name),
          h('p', {
            class: 'text-[12px] mt-0.5',
            style: { color: 'var(--muted)' },
          }, p.tagline),
          h('div', { class: 'mt-4 flex items-baseline gap-1' }, [
            price.value === 0
              ? h('span', {
                  class: 'text-[28px] font-bold',
                  style: { color: 'var(--foreground)' },
                }, 'Free')
              : [
                  h('span', {
                    class: 'text-[28px] font-bold',
                    style: { color: 'var(--foreground)' },
                  }, currency.value),
                  h('span', {
                    class: 'text-[28px] font-bold leading-none',
                    style: { color: 'var(--foreground)' },
                  }, price.value.toLocaleString()),
                  h('span', {
                    class: 'text-[12px] ml-1',
                    style: { color: 'var(--muted)' },
                  }, periodSuffix.value),
                ],
          ]),
        ]),

        // Feature highlights list
        h('ul', { class: 'space-y-2.5 mb-6 flex-1' }, (p.limits || []).map(l =>
          h('li', {
            class: 'flex items-start gap-2.5 text-[13px]',
            style: { color: 'var(--foreground)' },
          }, [
            h('span', {
              class: 'w-4 h-4 shrink-0 mt-0.5 flex items-center justify-center text-[12px] font-bold rounded-full',
              style: { color: 'var(--success)', background: 'color-mix(in oklab, var(--success) 12%, transparent)' },
            }, '✓'),
            h('span', l),
          ])
        )),

        // Features breakdown — explicit delta framing, same pattern every
        // competitor's plan card uses ("Everything in X, plus:").
        (p.features && p.features.length > 0) && h('div', {
          class: 'mb-6 pt-4',
          style: { borderTop: '1px solid var(--border)' },
        }, [
          h('p', {
            class: 'text-[11px] font-medium uppercase tracking-wider mb-2',
            style: { color: 'var(--muted)' },
          }, p.features[0] && /^everything in/i.test(p.features[0]) ? p.features[0] + ':' : 'Includes:'),
          ...p.features.slice(1, 5).map(f =>
            h('p', {
              class: 'text-[12px] leading-relaxed',
              style: { color: 'var(--muted)' },
            }, `— ${f}`)
          ),
        ]),

        // CTA
        h('button', {
          class: [
            'w-full py-2.5 rounded-md text-[13px] font-medium transition-colors flex items-center justify-center gap-2',
          ].join(' '),
          disabled: isCurrent.value || isBusy.value,
          style: isCurrent.value
            ? { background: 'var(--surface-secondary)', color: 'var(--muted)', border: '1px solid var(--border)', cursor: 'default' }
            : p.highlight
              ? { background: 'var(--accent)', color: 'var(--accent-foreground)', border: 'none', cursor: 'pointer' }
              : { background: 'transparent', color: 'var(--foreground)', border: '1px solid var(--border)', cursor: 'pointer' },
          onClick: () => !isCurrent.value && !isBusy.value && emit('select'),
          onMouseover: function(e) {
            if (!isCurrent.value && !p.highlight) {
              e.target.style.background = 'var(--surface-hover)';
            }
          },
          onMouseout: function(e) {
            if (!isCurrent.value && !p.highlight) {
              e.target.style.background = 'transparent';
            }
          },
        }, [
          btnText.value,
          isBusy.value && h('span', {
            class: 'animate-spin size-3.5 rounded-full',
            style: { border: '2px solid currentColor', borderTopColor: 'transparent' },
          }),
        ]),
      ])
    }
  },
})
</script>
