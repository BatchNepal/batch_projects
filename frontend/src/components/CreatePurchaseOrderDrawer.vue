<template>
  <Drawer :open="modelValue" @update:open="close" size="md" placement="right">
    <DrawerHeader @close="close">
      <div class="min-w-0">
        <span class="text-[14px] font-semibold text-foreground">Create Purchase Order</span>
        <p class="text-[12px] text-muted truncate mt-0.5">{{ taskTitle }}</p>
      </div>
    </DrawerHeader>

    <DrawerBody>
      <div class="flex flex-col gap-4">
        <!-- Supplier picker — same async search-list pattern as the
             unlinked-project search in ProjectMoney.vue -->
        <div class="flex flex-col gap-1.5">
          <label class="text-[13px] font-medium text-foreground">Supplier</label>
          <div v-if="supplier" class="cpo-selected">
            <span class="truncate">{{ supplierLabel }}</span>
            <button type="button" class="cpo-clear" @click="clearSupplier">
              <X class="size-3.5" />
            </button>
          </div>
          <template v-else>
            <Input v-model="supplierQ" placeholder="Search suppliers…" isClearable @update:modelValue="onSupplierSearch">
              <template #startContent><Search class="size-3.5 text-muted" /></template>
            </Input>
            <div v-if="supplierResults.length" class="cpo-results">
              <button v-for="r in supplierResults" :key="r.name" type="button" class="cpo-result-row" @click="pickSupplier(r)">
                {{ r.label }}
              </button>
            </div>
          </template>
        </div>

        <!-- Item rows -->
        <div class="flex flex-col gap-2">
          <label class="text-[13px] font-medium text-foreground">Items</label>
          <div v-for="(row, i) in items" :key="row.key" class="cpo-item-row">
            <div class="flex-1 min-w-0">
              <div v-if="row.item_code" class="cpo-selected">
                <span class="truncate">{{ row.item_name }} <span class="text-muted font-mono text-[11px]">{{ row.item_code }}</span></span>
                <button type="button" class="cpo-clear" @click="clearItem(i)"><X class="size-3.5" /></button>
              </div>
              <template v-else>
                <Input v-model="row.q" size="sm" placeholder="Search items…" @update:modelValue="(v) => onItemSearch(i, v)">
                  <template #startContent><Search class="size-3.5 text-muted" /></template>
                </Input>
                <div v-if="row.results && row.results.length" class="cpo-results">
                  <button v-for="r in row.results" :key="r.item_code" type="button" class="cpo-result-row" @click="pickItem(i, r)">
                    {{ r.item_name }} <span class="text-muted font-mono text-[11px] ml-1">{{ r.item_code }}</span>
                  </button>
                </div>
              </template>
            </div>
            <Input v-model="row.qty" type="number" size="sm" placeholder="Qty" class="cpo-qty" />
            <Input v-model="row.rate" type="number" size="sm" placeholder="Rate" class="cpo-rate" />
            <button type="button" class="cpo-remove" :disabled="items.length === 1" @click="removeRow(i)">
              <Trash2 class="size-3.5" />
            </button>
          </div>
          <button type="button" class="cpo-add-row" @click="addRow">
            <Plus class="size-3.5" /> Add item
          </button>
        </div>

        <div class="cpo-total">
          <span class="text-[12.5px] text-muted">Estimated total</span>
          <span class="text-[13px] font-semibold text-foreground tabular-nums">{{ fmtTotal }}</span>
        </div>
      </div>
    </DrawerBody>

    <DrawerFooter>
      <Button size="sm" variant="ghost" @click="close">Cancel</Button>
      <Button size="sm" color="primary" :isDisabled="!canSubmit" :isLoading="creating" @click="submit">
        Create Purchase Order
      </Button>
    </DrawerFooter>
  </Drawer>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { debounce } from 'lodash'
import { toast } from 'vue-sonner'
import { Drawer, DrawerHeader, DrawerBody, DrawerFooter, Input, Button } from '@/ui'
import { Search, X, Plus, Trash2 } from 'lucide-vue-next'
import { searchErpDocuments, searchNonStockItems, createPurchaseOrderFromTask } from '@/utils/api'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  task:       { type: String,  required: true },
  taskTitle:  { type: String,  default: '' },
})
const emit = defineEmits(['update:modelValue', 'created'])

let rowKey = 0
function blankRow() {
  return { key: rowKey++, q: '', results: [], item_code: '', item_name: '', qty: '1', rate: '0' }
}

const supplier       = ref('')
const supplierLabel  = ref('')
const supplierQ      = ref('')
const supplierResults = ref([])
const items   = ref([blankRow()])
const creating = ref(false)

const onSupplierSearch = debounce(async () => {
  if (!supplierQ.value) { supplierResults.value = []; return }
  try { supplierResults.value = await searchErpDocuments('Supplier', supplierQ.value) }
  catch (e) { supplierResults.value = [] }
}, 250)

function pickSupplier(r) {
  supplier.value = r.name
  supplierLabel.value = r.label
  supplierQ.value = ''
  supplierResults.value = []
}
function clearSupplier() {
  supplier.value = ''
  supplierLabel.value = ''
}

function onItemSearch(i, v) {
  const row = items.value[i]
  row.q = v
  searchItemsDebounced(i)
}
const searchItemsDebounced = debounce(async (i) => {
  const row = items.value[i]
  if (!row || !row.q) { if (row) row.results = []; return }
  try { row.results = await searchNonStockItems(row.q) }
  catch (e) { row.results = [] }
}, 250)

function pickItem(i, r) {
  const row = items.value[i]
  row.item_code = r.item_code
  row.item_name = r.item_name
  row.q = ''
  row.results = []
}
function clearItem(i) {
  const row = items.value[i]
  row.item_code = ''
  row.item_name = ''
}
function addRow() { items.value.push(blankRow()) }
function removeRow(i) { if (items.value.length > 1) items.value.splice(i, 1) }

const canSubmit = computed(() =>
  !!supplier.value &&
  items.value.every(r => r.item_code && Number(r.qty) > 0)
)

const estimatedTotal = computed(() =>
  items.value.reduce((sum, r) => sum + (Number(r.qty) || 0) * (Number(r.rate) || 0), 0)
)
// Plain number, no currency symbol: this form has no currency context and
// inventing one (e.g. "$" on an NPR company) is the exact cosmetic-currency
// bug the money spine already fixed once — the real, labelled amount shows
// in the MoneyDrawer that opens on success.
function fmtNumber(v) {
  try { return new Intl.NumberFormat(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 2 }).format(v) }
  catch (e) { return String(v) }
}
const fmtTotal = computed(() => fmtNumber(estimatedTotal.value))

async function submit() {
  if (!canSubmit.value || creating.value) return
  creating.value = true
  try {
    const payload = items.value.map(r => ({ item_code: r.item_code, qty: Number(r.qty), rate: Number(r.rate) }))
    const res = await createPurchaseOrderFromTask(props.task, supplier.value, payload)
    toast.success(`Draft Purchase Order ${res.purchase_order} created`, {
      description: 'Review and submit it in ERPNext to make it committed spend.',
    })
    emit('created', res.purchase_order)
    close()
  } catch (e) {
    toast.error(e.message || 'Failed to create Purchase Order')
  } finally {
    creating.value = false
  }
}

function reset() {
  supplier.value = ''
  supplierLabel.value = ''
  supplierQ.value = ''
  supplierResults.value = []
  items.value = [blankRow()]
}
function close() { emit('update:modelValue', false) }

watch(() => props.modelValue, (v) => { if (v) reset() })
</script>

<style scoped>
.cpo-selected {
  display: flex; align-items: center; justify-content: space-between; gap: 8px;
  height: 36px; padding: 0 10px; border-radius: 8px;
  background: var(--surface-secondary); border: 1px solid var(--border-secondary);
  font-size: 12.5px; color: var(--foreground);
}
.cpo-clear { display: flex; align-items: center; color: var(--muted); background: none; border: none; cursor: pointer; flex-shrink: 0; }
.cpo-clear:hover { color: var(--foreground); }

.cpo-results {
  margin-top: 2px; border: 1px solid var(--border-secondary); border-radius: 8px;
  overflow: hidden; max-height: 160px; overflow-y: auto;
}
.cpo-result-row {
  display: block; width: 100%; text-align: left; padding: 7px 10px;
  font-size: 12.5px; color: var(--foreground); background: none; border: none; cursor: pointer;
}
.cpo-result-row + .cpo-result-row { border-top: 1px solid var(--border-secondary); }
.cpo-result-row:hover { background: var(--surface-secondary); }

.cpo-item-row { display: flex; align-items: flex-start; gap: 6px; }
.cpo-qty  { width: 68px; flex-shrink: 0; }
.cpo-rate { width: 84px; flex-shrink: 0; }
.cpo-remove {
  width: 36px; height: 36px; flex-shrink: 0; border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  color: var(--muted); background: none; border: 1px solid transparent; cursor: pointer;
}
.cpo-remove:hover:not(:disabled) { color: var(--danger); background: var(--surface-secondary); }
.cpo-remove:disabled { opacity: 0.35; cursor: not-allowed; }

.cpo-add-row {
  display: inline-flex; align-items: center; gap: 6px; align-self: flex-start;
  font-size: 12.5px; font-weight: 600; color: var(--accent);
  background: none; border: none; cursor: pointer; padding: 4px 2px;
}
.cpo-add-row:hover { text-decoration: underline; }

.cpo-total {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 12px; border-radius: 8px;
  background: var(--surface-secondary); border: 1px solid var(--border-secondary);
}
</style>
