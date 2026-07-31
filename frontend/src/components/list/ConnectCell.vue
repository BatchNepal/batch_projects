<template>
  <FieldDropdown width="w-72" :close-on-select="false">
    <template #trigger>
      <button class="cc-trigger" :title="doctype ? `Link ${doctype}` : 'Link ERPNext documents'">
        <template v-if="shown.length">
          <!-- Scoped column: icon + label (or count). Generic: per-doctype summary chips. -->
          <template v-if="doctype">
            <span class="cc-chip" :title="shown.map(r => r.ref_label || r.ref_name).join(', ')">
              <component :is="dtIcon(doctype)" :size="12" :stroke-width="2" class="cc-chip-ic"/>
              {{ shown.length === 1 ? trimLabel(shown[0]) : shown.length + ' linked' }}
            </span>
          </template>
          <template v-else>
            <span v-for="g in summary.slice(0, 2)" :key="g.doctype" class="cc-chip"
              :title="g.items.map(r => r.ref_label || r.ref_name).join(', ')">
              <component :is="dtIcon(g.doctype)" :size="12" :stroke-width="2" class="cc-chip-ic"/>
              {{ g.abbr }}<template v-if="g.n > 1"> ×{{ g.n }}</template>
            </span>
            <span v-if="summary.length > 2" class="cc-more">+{{ summary.length - 2 }}</span>
          </template>
        </template>
        <span v-else class="cc-empty">
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/></svg>
          Connect
        </span>
      </button>
    </template>

    <div class="cc-panel" @click.stop>
      <div v-if="!doctype" class="cc-row">
        <select v-model="activeDoctype" class="hui-field cc-select">
          <option v-for="d in ERP_DOCTYPES" :key="d.name" :value="d.name">{{ d.name }}</option>
        </select>
      </div>

      <input
        v-model="q"
        class="hui-field cc-search"
        :placeholder="`Search ${activeDoctype}s…`"
        @input="onSearch"
      />

      <div class="cc-results">
        <div v-if="searching" class="cc-note">Searching…</div>
        <template v-else-if="results.length">
          <button v-for="r in results" :key="r.name" class="cc-result" @click="add(r)">
            <span class="cc-result-label">{{ r.label || r.name }}</span>
            <span class="cc-result-name">{{ r.name }}</span>
          </button>
        </template>
        <div v-else-if="q" class="cc-note">No {{ activeDoctype }} found.</div>
        <div v-else class="cc-note">Type to search {{ activeDoctype }}s.</div>
      </div>

      <template v-if="shown.length">
        <div class="cc-sep" />
        <p class="cc-hdr">Linked</p>
        <div v-for="r in shown" :key="r.name || r.ref_name" class="cc-linked">
          <span class="cc-linked-label">
            {{ r.ref_label || r.ref_name }}
            <span class="cc-linked-id">{{ r.ref_name }}</span>
          </span>
          <button v-if="openDoc" class="cc-x cc-open" title="Open" @click="openDoc(r.ref_doctype, r.ref_name)">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path stroke-linecap="round" stroke-linejoin="round" d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6m4-3h6m0 0v6m0-6L10 14"/></svg>
          </button>
          <a v-else class="cc-x cc-open" :href="refUrl(r)" target="_blank" rel="noopener" title="Open in ERPNext">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path stroke-linecap="round" stroke-linejoin="round" d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6m4-3h6m0 0v6m0-6L10 14"/></svg>
          </a>
          <button class="cc-x" title="Unlink" @click="remove(r)">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>
          </button>
        </div>
      </template>
    </div>
  </FieldDropdown>
</template>

<script setup>
import { ref, computed } from 'vue'
import { toast } from 'vue-sonner'
import FieldDropdown from '@/components/FieldDropdown.vue'
import { searchErpDocuments, addReference, removeReference } from '@/utils/api'
import { ERP_DOCTYPES } from '@/constants/erp-doctypes'

const props = defineProps({
  issue:   { type: Object, required: true },
  // When set, the cell is scoped to one doctype (erp:<Doctype> columns).
  doctype: { type: String, default: null },
  // Two-way: linking also leaves a backlink comment on the ERP document.
  twoWay:  { type: Boolean, default: false },
  // Parent-provided (doctype, name) opener — routes linked docs through the
  // Money drawer instead of the raw /app anchor fallback.
  openDoc: { type: Function, default: null },
})

const activeDoctype = ref(props.doctype || ERP_DOCTYPES[0].name)
const q         = ref('')
const results   = ref([])
const searching = ref(false)
let timer = null

const shown = computed(() => {
  const refs = props.issue.references || []
  return props.doctype ? refs.filter(r => r.ref_doctype === props.doctype) : refs
})

const summary = computed(() => {
  const m = {}
  for (const r of shown.value) (m[r.ref_doctype] ||= []).push(r)
  return Object.entries(m).map(([doctype, items]) => ({
    doctype, items, n: items.length,
    abbr: doctype.split(' ').map(w => w[0]).join('').toUpperCase(),
  }))
})
function dtIcon(dt) { return ERP_DOCTYPES.find(d => d.name === dt)?.icon || null }
function trimLabel(r) {
  const l = r.ref_label || r.ref_name
  return l.length > 16 ? l.slice(0, 15) + '…' : l
}
function refUrl(r) {
  return r.ref_url || `/app/${r.ref_doctype.toLowerCase().replace(/ /g, '-')}/${encodeURIComponent(r.ref_name)}`
}

function onSearch() {
  clearTimeout(timer)
  const query = q.value.trim()
  if (!query) { results.value = []; return }
  searching.value = true
  timer = setTimeout(async () => {
    try {
      results.value = await searchErpDocuments(activeDoctype.value, query, props.issue.project) || []
    } catch { results.value = [] }
    finally { searching.value = false }
  }, 250)
}

async function add(r) {
  try {
    const refreshed = await addReference(props.issue.name, activeDoctype.value, r.name, props.twoWay ? 1 : 0)
    if (Array.isArray(refreshed)) props.issue.references = refreshed
    q.value = ''; results.value = []
  } catch (e) {
    toast.error("Couldn't link document", { description: String(e.message || e) })
  }
}

async function remove(r) {
  const prev = props.issue.references
  props.issue.references = prev.filter(x => x !== r)
  try {
    await removeReference(props.issue.name, r.name || null, r.ref_doctype, r.ref_name)
  } catch (e) {
    props.issue.references = prev
    toast.error("Couldn't unlink", { description: String(e.message || e) })
  }
}
</script>

<style scoped>
.cc-trigger{display:inline-flex;align-items:center;gap:4px;min-height:26px;max-width:100%;padding:0 4px;background:none;border:none;cursor:pointer;font-family:inherit}
.cc-chip{display:inline-flex;align-items:center;gap:5px;height:22px;padding:0 8px;font-size:11.5px;font-weight:600;color:var(--accent-soft-foreground);background:var(--accent-soft);border-radius:var(--radius-md);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.cc-chip-ic{flex-shrink:0;opacity:.8}
.cc-linked-id{display:block;font-size:10.5px;color:var(--muted);font-family:var(--font-mono)}
.cc-more{font-size:11px;color:var(--muted)}
.cc-empty{display:inline-flex;align-items:center;gap:5px;font-size:12px;color:var(--muted);opacity:0;transition:opacity .12s}
:global(.lv-row:hover) .cc-empty{opacity:1}
.cc-panel{padding:8px;min-width:260px}
.cc-row{margin-bottom:6px}
.cc-select{width:100%;height:30px;font-size:12.5px;padding:0 8px;font-family:inherit;color:var(--foreground);cursor:pointer}
.cc-search{width:100%;height:30px;font-size:12.5px;padding:0 8px;font-family:inherit;color:var(--foreground);outline:none}
.cc-results{max-height:160px;overflow-y:auto;margin-top:6px}
.cc-result{display:flex;flex-direction:column;align-items:flex-start;gap:1px;width:100%;text-align:left;padding:5px 8px;border:none;background:none;border-radius:5px;cursor:pointer;font-family:inherit}
.cc-result:hover{background:var(--default)}
.cc-result-label{font-size:12.5px;font-weight:500;color:var(--foreground)}
.cc-result-name{font-size:11px;color:var(--muted);font-family:var(--font-mono)}
.cc-note{font-size:12px;color:var(--muted);padding:8px;text-align:center}
.cc-sep{height:1px;background:var(--separator);margin:8px 0 6px}
.cc-hdr{font-size:10.5px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;margin:0 0 4px;padding:0 2px}
.cc-linked{display:flex;align-items:center;gap:6px;padding:3px 4px;border-radius:5px}
.cc-linked:hover{background:var(--surface-secondary)}
.cc-linked-label{flex:1;font-size:12.5px;color:var(--foreground);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.cc-x{display:inline-flex;align-items:center;justify-content:center;width:18px;height:18px;border:none;background:none;border-radius:4px;color:var(--muted);cursor:pointer}
.cc-x:hover{background:var(--danger-soft);color:var(--danger)}
.cc-open:hover{background:var(--surface-secondary);color:var(--foreground)}
</style>
