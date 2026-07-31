<template>
  <div class="space-y-4">
    <!-- Client type-ahead -->
    <div class="relative">
      <Input
        v-model="customerQuery"
        label="Client"
        :isRequired="true"
        :placeholder="modelValue.clientName || 'Search customers…'"
        size="sm"
        variant="bordered"
        @update:modelValue="onCustomerInput"
        @focus="showDropdown = true"
        @blur="onBlur"
      />
      <ul
        v-if="showDropdown && customers.length"
        class="absolute z-dropdown left-0 right-0 mt-1.5 bg-overlay rounded-lg shadow-overlay max-h-52 overflow-y-auto p-1"
      >
        <li
          v-for="c in customers"
          :key="c.name"
          @mousedown.prevent="selectCustomer(c)"
          class="px-2.5 py-2 rounded-[5px] text-sm cursor-pointer hover:bg-default flex flex-col gap-0.5 transition-colors"
        >
          <span class="font-medium text-foreground">{{ c.label }}</span>
          <span class="text-xs text-muted">{{ c.name }}</span>
        </li>
      </ul>
      <p v-if="showDropdown && customerQuery && !customers.length && !searching" class="mt-1.5 text-xs text-muted">
        No customers found.
      </p>
    </div>

    <!-- T&M fields -->
    <template v-if="type === 'tm'">
      <div class="grid grid-cols-2 gap-3 items-end">
        <Input :model-value="modelValue.hourlyRate" label="Hourly rate" placeholder="0.00" type="number" size="sm" variant="bordered" @update:modelValue="update('hourlyRate', $event)">
          <template #startContent><span class="text-xs text-muted">{{ modelValue.currency }}</span></template>
        </Input>
        <Input :model-value="modelValue.budgetHours" label="Budget hours (cap)" placeholder="Optional" type="number" size="sm" variant="bordered" @update:modelValue="update('budgetHours', $event)" />
      </div>
    </template>

    <!-- Fixed price fields -->
    <template v-if="type === 'fixed'">
      <div class="grid grid-cols-2 gap-3 items-end ">
        <Input :model-value="modelValue.totalBudget" label="Total budget" :isRequired="true" placeholder="0.00" type="number" size="sm" variant="bordered" @update:modelValue="update('totalBudget', $event)">
          <template #startContent><span class="text-xs text-muted">{{ modelValue.currency }}</span></template>
        </Input>
        <div class="relative">
          <label class="bp-bf-label">Currency</label>
          <input
            v-model="curQuery"
            :placeholder="modelValue.currency || 'Search…'"
            spellcheck="false"
            class="hui-field w-full h-8 px-3 text-sm outline-none uppercase font-medium text-foreground placeholder:text-[var(--field-placeholder)]"
            @focus="curOpen = true; curQuery = ''"
            @blur="onCurBlur"
            @input="curOpen = true"
          />
          <ul v-if="curOpen" class="absolute z-dropdown left-0 right-0 mt-1.5 bg-overlay rounded-lg shadow-overlay max-h-52 overflow-y-auto p-1">
            <li v-for="c in filteredCurrencies" :key="c.code" @mousedown.prevent="selectCurrency(c)"
                class="px-2.5 py-1.5 rounded-[5px] text-sm cursor-pointer hover:bg-default flex items-center justify-between gap-3 transition-colors">
              <span class="font-semibold text-foreground">{{ c.code }}</span>
              <span class="text-xs text-muted truncate">{{ c.name }}</span>
            </li>
            <li v-if="!filteredCurrencies.length" class="px-2.5 py-2 text-xs text-muted">No match.</li>
          </ul>
        </div>
      </div>
    </template>

    <!-- Retainer fields -->
    <template v-if="type === 'retainer'">
      <div class="grid grid-cols-2 gap-3 items-end">
        <Input :model-value="modelValue.retainerHours" label="Monthly hours included" placeholder="e.g. 40" type="number" size="sm" variant="bordered" @update:modelValue="update('retainerHours', $event)" />
        <Input :model-value="modelValue.overageRate" label="Overage rate" placeholder="0.00" type="number" size="sm" variant="bordered" @update:modelValue="update('overageRate', $event)">
          <template #startContent><span class="text-xs text-muted">{{ modelValue.currency }}</span></template>
        </Input>
      </div>
      <div class="grid grid-cols-2 gap-3 items-end">
        <div>
          <label class="bp-bf-label">Start month</label>
          <Select :model-value="startMonth" @update:model-value="setMonth" size="sm" :fullWidth="true">
            <SelectItem v-for="mo in MONTHS" :key="mo.v" :value="mo.v">{{ mo.l }}</SelectItem>
          </Select>
        </div>
        <div>
          <label class="bp-bf-label">Year</label>
          <Select :model-value="startYear" @update:model-value="setYear" size="sm" :fullWidth="true">
            <SelectItem v-for="y in YEARS" :key="y" :value="String(y)">{{ y }}</SelectItem>
          </Select>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import Input from '@/ui/Input.vue'
import Select from '@/ui/Select.vue'
import SelectItem from '@/ui/SelectItem.vue'
import { searchErpDocuments } from '@/utils/api.js'

const props = defineProps({
  modelValue: { type: Object, required: true },
  type:       { type: String, required: true },
})
const emit = defineEmits(['update:modelValue'])

const CURRENCIES = [
  { code: 'INR', name: 'Indian Rupee' },
  { code: 'USD', name: 'US Dollar' },
  { code: 'EUR', name: 'Euro' },
  { code: 'GBP', name: 'British Pound' },
  { code: 'NPR', name: 'Nepalese Rupee' },
  { code: 'AUD', name: 'Australian Dollar' },
  { code: 'CAD', name: 'Canadian Dollar' },
  { code: 'SGD', name: 'Singapore Dollar' },
  { code: 'AED', name: 'UAE Dirham' },
  { code: 'JPY', name: 'Japanese Yen' },
  { code: 'CNY', name: 'Chinese Yuan' },
  { code: 'SAR', name: 'Saudi Riyal' },
  { code: 'ZAR', name: 'South African Rand' },
  { code: 'BDT', name: 'Bangladeshi Taka' },
  { code: 'LKR', name: 'Sri Lankan Rupee' },
]

// Searchable currency combobox
const curOpen = ref(false)
const curQuery = ref(props.modelValue.currency || 'INR')
const filteredCurrencies = computed(() => {
  const q = curQuery.value.trim().toLowerCase()
  if (!q) return CURRENCIES
  return CURRENCIES.filter(c => c.code.toLowerCase().includes(q) || c.name.toLowerCase().includes(q))
})
function selectCurrency(c) {
  update('currency', c.code)
  curQuery.value = c.code
  curOpen.value = false
}
function onCurBlur() {
  setTimeout(() => { curOpen.value = false; curQuery.value = props.modelValue.currency || 'INR' }, 150)
}
const MONTHS = [
  { v: '01', l: 'January' }, { v: '02', l: 'February' }, { v: '03', l: 'March' },
  { v: '04', l: 'April' }, { v: '05', l: 'May' }, { v: '06', l: 'June' },
  { v: '07', l: 'July' }, { v: '08', l: 'August' }, { v: '09', l: 'September' },
  { v: '10', l: 'October' }, { v: '11', l: 'November' }, { v: '12', l: 'December' },
]
const thisYear = new Date().getFullYear()
const YEARS = [thisYear - 1, thisYear, thisYear + 1, thisYear + 2, thisYear + 3]

// retainerStartMonth is stored as 'YYYY-MM'
const startYear = computed(() => (props.modelValue.retainerStartMonth || '').split('-')[0] || '')
const startMonth = computed(() => (props.modelValue.retainerStartMonth || '').split('-')[1] || '')
function setMonth(m) {
  const y = startYear.value || String(thisYear)
  update('retainerStartMonth', `${y}-${m}`)
}
function setYear(y) {
  const m = startMonth.value || '01'
  update('retainerStartMonth', `${y}-${m}`)
}

const customerQuery = ref(props.modelValue.clientName || '')
const customers = ref([])
const showDropdown = ref(false)
const searching = ref(false)
let timer = null

function update(field, value) {
  emit('update:modelValue', { ...props.modelValue, [field]: value })
}

function onCustomerInput() {
  clearTimeout(timer)
  const q = customerQuery.value.trim()
  if (!q) { customers.value = []; return }
  searching.value = true
  timer = setTimeout(async () => {
    try {
      // Goes through the whitelisted BP endpoint (frappe.get_all, perm-bypassing)
      // so project creators without direct Customer read still get results.
      customers.value = await searchErpDocuments('Customer', q)
    } catch {
      customers.value = []
    } finally {
      searching.value = false
    }
  }, 200)
}

function selectCustomer(c) {
  customerQuery.value = c.label
  showDropdown.value = false
  emit('update:modelValue', { ...props.modelValue, client: c.name, clientName: c.label })
}

function onBlur() {
  setTimeout(() => { showDropdown.value = false }, 150)
}
</script>

<style scoped>
.bp-bf-label { display: block; font-size: var(--text-sm); font-weight: var(--font-semibold); color: var(--foreground); margin-bottom: 6px; }
</style>
