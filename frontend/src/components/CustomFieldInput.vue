<template>
  <div class="cf-field" :class="{ 'cf-field--error': error, 'cf-field--inline': inline }">

    <!-- Label (hidden in inline mode) -->
    <label v-if="!inline && showLabel" class="cf-label">
      {{ field.label }}
      <span v-if="field.required" class="cf-required">*</span>
    </label>

    <!-- ── TEXT ── -->
    <input
      v-if="field.type === 'text'"
      type="text"
      class="cf-input"
      :value="modelValue"
      :placeholder="field.placeholder || ''"
      :disabled="disabled"
      @input="emit('update:modelValue', $event.target.value || null)"
      @blur="handleBlur"
    />

    <!-- ── TEXTAREA ── -->
    <textarea
      v-else-if="field.type === 'textarea'"
      class="cf-input cf-textarea"
      :value="modelValue"
      :placeholder="field.placeholder || ''"
      :disabled="disabled"
      rows="3"
      @input="emit('update:modelValue', $event.target.value || null)"
      @blur="handleBlur"
    />

    <!-- ── NUMBER ── -->
    <div v-else-if="field.type === 'number'" class="cf-number-wrap">
      <span v-if="field.unit" class="cf-unit">{{ field.unit }}</span>
      <input
        type="number"
        class="cf-input"
        :class="{ 'cf-input--with-unit': field.unit }"
        :value="modelValue"
        :placeholder="field.placeholder || '0'"
        :min="field.min ?? undefined"
        :max="field.max ?? undefined"
        :disabled="disabled"
        @input="emit('update:modelValue', $event.target.value === '' ? null : Number($event.target.value))"
        @blur="handleBlur"
      />
    </div>

    <!-- ── DATE ── -->
    <input
      v-else-if="field.type === 'date'"
      type="date"
      class="cf-input cf-date"
      :value="modelValue"
      :disabled="disabled"
      @change="emit('update:modelValue', $event.target.value || null)"
      @blur="handleBlur"
    />

    <!-- ── SELECT ── -->
    <div v-else-if="field.type === 'select'" class="cf-select-wrap">
      <select
        class="cf-input cf-select"
        :value="modelValue"
        :disabled="disabled"
        @change="emit('update:modelValue', $event.target.value || null)"
        @blur="handleBlur"
      >
        <option value="">{{ field.placeholder || 'Select…' }}</option>
        <option
          v-for="opt in field.options ?? []"
          :key="opt.id"
          :value="opt.id"
        >{{ opt.label }}</option>
      </select>
      <ChevronDown class="cf-select-icon" :size="14" />
    </div>

    <!-- ── MULTISELECT ── -->
    <div v-else-if="field.type === 'multiselect'" class="cf-multi">
      <!-- Selected chips -->
      <div v-if="selectedOptions.length" class="cf-chips">
        <span
          v-for="opt in selectedOptions"
          :key="opt.id"
          class="cf-chip"
        >
          {{ opt.label }}
          <button
            v-if="!disabled"
            class="cf-chip-remove"
            type="button"
            @click="removeOption(opt.id)"
          >
            <X :size="10" />
          </button>
        </span>
      </div>

      <!-- Dropdown -->
      <div v-if="!disabled" class="cf-multi-dropdown" ref="multiDropdownRef">
        <button
          type="button"
          class="cf-multi-trigger"
          @click="multiOpen = !multiOpen"
        >
          <Plus :size="12" />
          <span>{{ selectedOptions.length ? 'Add' : (field.placeholder || 'Select…') }}</span>
        </button>

        <div v-if="multiOpen" class="cf-dropdown-panel">
          <button
            v-for="opt in unselectedOptions"
            :key="opt.id"
            type="button"
            class="cf-dropdown-item"
            @click="addOption(opt.id)"
          >
            {{ opt.label }}
          </button>
          <div v-if="unselectedOptions.length === 0" class="cf-dropdown-empty">
            All options selected
          </div>
        </div>
      </div>

      <!-- Read-only display -->
      <span v-else-if="!selectedOptions.length" class="cf-empty">—</span>
    </div>

    <!-- ── CHECKBOX ── -->
    <label v-else-if="field.type === 'checkbox'" class="cf-checkbox-label">
      <input
        type="checkbox"
        class="cf-checkbox"
        :checked="!!modelValue"
        :disabled="disabled"
        @change="emit('update:modelValue', $event.target.checked)"
      />
      <span class="cf-checkbox-text">{{ modelValue ? 'Yes' : 'No' }}</span>
    </label>

    <!-- ── USER (Employee) ── -->
    <div v-else-if="field.type === 'user'" class="cf-user-wrap">
      <select
        class="cf-input cf-select"
        :value="modelValue"
        :disabled="disabled"
        @change="emit('update:modelValue', $event.target.value || null)"
        @blur="handleBlur"
      >
        <option value="">{{ field.placeholder || 'Select person…' }}</option>
        <option
          v-for="member in members"
          :key="member.user"
          :value="member.user"
        >{{ member.full_name }}</option>
      </select>
      <ChevronDown class="cf-select-icon" :size="14" />
    </div>

    <!-- ── URL ── -->
    <div v-else-if="field.type === 'url'" class="cf-url-wrap">
      <input
        type="url"
        class="cf-input cf-url"
        :value="modelValue"
        :placeholder="field.placeholder || 'https://…'"
        :disabled="disabled"
        @input="emit('update:modelValue', $event.target.value || null)"
        @blur="handleBlur"
      />
      <a
        v-if="modelValue"
        :href="modelValue"
        target="_blank"
        rel="noopener noreferrer"
        class="cf-url-open"
        tabindex="-1"
      >
        <ExternalLink :size="13" />
      </a>
    </div>

    <!-- ── CURRENCY / PERCENT (number variants with affix) ──
         Currency's ₹ is a PREFIX, percent's % is a SUFFIX — they need room
         reserved on opposite sides. Both used to get the same
         cf-input--with-unit (padding-LEFT only), so percent's "0" sat flush
         against the input's left edge with nothing reserving room for the %
         on the right — see cf-input--with-suffix below for the fix. -->
    <div v-else-if="field.type === 'currency' || field.type === 'percent'" class="cf-number-wrap">
      <span v-if="field.type === 'currency'" class="cf-unit">{{ field.unit || '₹' }}</span>
      <input
        type="number" class="cf-input"
        :class="field.type === 'currency' ? 'cf-input--with-unit' : 'cf-input--with-suffix'"
        :value="modelValue" :placeholder="field.type === 'percent' ? '0' : '0.00'"
        :min="field.type === 'percent' ? 0 : undefined" :max="field.type === 'percent' ? 100 : undefined"
        :disabled="disabled"
        @input="emit('update:modelValue', $event.target.value === '' ? null : Number($event.target.value))"
        @blur="handleBlur"
      />
      <span v-if="field.type === 'percent'" class="cf-unit cf-unit--suffix">%</span>
    </div>

    <!-- ── RATING (1–5 stars) ── -->
    <div v-else-if="field.type === 'rating'" class="cf-rating">
      <button v-for="n in 5" :key="n" type="button" class="cf-star" :disabled="disabled"
        @click="emit('update:modelValue', modelValue === n ? null : n); handleBlur()">
        <Star :size="16" :fill="n <= (modelValue || 0) ? 'currentColor' : 'none'"
          :class="n <= (modelValue || 0) ? 'cf-star--on' : 'cf-star--off'" />
      </button>
    </div>

    <!-- ── EMAIL / PHONE ── -->
    <div v-else-if="field.type === 'email' || field.type === 'phone'" class="cf-url-wrap">
      <input
        :type="field.type === 'email' ? 'email' : 'tel'" class="cf-input cf-url"
        :value="modelValue"
        :placeholder="field.placeholder || (field.type === 'email' ? 'name@company.com' : '+1 555 000 0000')"
        :disabled="disabled"
        @input="emit('update:modelValue', $event.target.value || null)"
        @blur="handleBlur"
      />
      <a v-if="modelValue" :href="(field.type === 'email' ? 'mailto:' : 'tel:') + modelValue"
        class="cf-url-open" tabindex="-1">
        <component :is="field.type === 'email' ? Mail : Phone" :size="13" />
      </a>
    </div>

    <!-- ── LINK (ERPNext linked record) ── -->
    <div v-else-if="field.type === 'link'" class="cf-link-wrap" ref="linkDropdownRef">
      <div v-if="modelValue && modelValue.name" class="cf-link-chip">
        <span class="cf-link-chip-label">{{ modelValue.label || modelValue.name }}</span>
        <a v-if="linkDoctype" :href="linkRefUrl" target="_blank" rel="noopener noreferrer"
          class="cf-link-open" tabindex="-1">
          <ExternalLink :size="12" />
        </a>
        <button v-if="!disabled" type="button" class="cf-link-clear" @click="clearLink">
          <X :size="11" />
        </button>
      </div>
      <template v-else-if="!disabled">
        <input
          type="text"
          class="cf-input"
          v-model="linkQuery"
          :placeholder="field.placeholder || 'Search…'"
          @focus="linkOpen = true; runLinkSearch()"
          @input="onLinkQueryInput"
        />
        <div v-if="linkOpen" class="cf-dropdown-panel cf-link-panel">
          <div v-if="linkLoading" class="cf-dropdown-empty">Searching…</div>
          <template v-else>
            <button v-for="opt in linkResults" :key="opt.name" type="button" class="cf-dropdown-item"
              @click="selectLink(opt)">
              {{ opt.label }}
            </button>
            <div v-if="!linkResults.length" class="cf-dropdown-empty">No matches</div>
          </template>
        </div>
      </template>
      <span v-else class="cf-empty">—</span>
    </div>

    <!-- Error message -->
    <p v-if="error" class="cf-error">{{ error }}</p>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { ChevronDown, X, Plus, ExternalLink, Star, Mail, Phone } from 'lucide-vue-next'
import { resolveOptionLabel } from '@/utils/customFields.js'
import { searchFieldLinkOptions } from '@/utils/api.js'

// ─── Props ────────────────────────────────────────────────────────────────────

const props = defineProps({
  /**
   * Field schema object from BP Project.custom_fields
   * { id, label, type, required, options, placeholder, min, max, unit, ... }
   */
  field: {
    type: Object,
    required: true,
  },

  /**
   * Current value. Type depends on field.type:
   * text/textarea/url: string | null
   * number: number | null
   * date: "YYYY-MM-DD" | null
   * select: optionId string | null
   * multiselect: optionId[] | []
   * checkbox: boolean
   * user: Employee docname string | null
   */
  modelValue: {
    default: null,
  },

  /** List of users for user fields: [{user, full_name}] */
  members: {
    type: Array,
    default: () => [],
  },

  /** Current project name — required for 'link'-type fields, since the
   *  search endpoint is project-scoped (binds the field to the project the
   *  value is being edited in). Unused by every other field type. */
  projectName: {
    type: String,
    default: null,
  },

  /** Disable editing */
  disabled: {
    type: Boolean,
    default: false,
  },

  /** Hide the label (used inside TaskDetail metadata row) */
  inline: {
    type: Boolean,
    default: false,
  },

  /** Show label above input. Default true. */
  showLabel: {
    type: Boolean,
    default: true,
  },

  /** External error message (from validateAllFields) */
  error: {
    type: String,
    default: null,
  },
})

// ─── Emits ────────────────────────────────────────────────────────────────────

const emit = defineEmits(['update:modelValue', 'blur'])

// ─── Multiselect state ────────────────────────────────────────────────────────

const multiOpen = ref(false)
const multiDropdownRef = ref(null)

const currentIds = computed(() => {
  if (!Array.isArray(props.modelValue)) return []
  return props.modelValue
})

const selectedOptions = computed(() => {
  return (props.field.options ?? []).filter(o => currentIds.value.includes(o.id))
})

const unselectedOptions = computed(() => {
  return (props.field.options ?? []).filter(o => !currentIds.value.includes(o.id))
})

function addOption(optId) {
  emit('update:modelValue', [...currentIds.value, optId])
  multiOpen.value = false
}

function removeOption(optId) {
  emit('update:modelValue', currentIds.value.filter(id => id !== optId))
}

// Close multiselect / link dropdowns on outside click
function handleOutsideClick(e) {
  if (multiDropdownRef.value && !multiDropdownRef.value.contains(e.target)) {
    multiOpen.value = false
  }
  if (linkDropdownRef.value && !linkDropdownRef.value.contains(e.target)) {
    linkOpen.value = false
  }
}

onMounted(() => document.addEventListener('mousedown', handleOutsideClick))
onBeforeUnmount(() => {
  document.removeEventListener('mousedown', handleOutsideClick)
  clearTimeout(linkDebounceTimer)
})

// ─── Link (ERPNext linked record) state ──────────────────────────────────────

const linkQuery = ref('')
const linkResults = ref([])
const linkOpen = ref(false)
const linkLoading = ref(false)
const linkDropdownRef = ref(null)
let linkDebounceTimer = null

const linkDoctype = computed(() => {
  const opts = props.field.options
  return (opts && !Array.isArray(opts) && opts.link_doctype) || null
})
const linkRefUrl = computed(() => {
  if (!linkDoctype.value || !props.modelValue?.name) return '#'
  return `/app/${linkDoctype.value.toLowerCase().replace(/ /g, '-')}/${props.modelValue.name}`
})

function onLinkQueryInput() {
  clearTimeout(linkDebounceTimer)
  linkDebounceTimer = setTimeout(runLinkSearch, 250)
}

async function runLinkSearch() {
  if (!props.projectName) return
  linkLoading.value = true
  try {
    linkResults.value = await searchFieldLinkOptions(props.projectName, props.field.id, linkQuery.value)
  } catch {
    linkResults.value = []
  } finally {
    linkLoading.value = false
  }
}

function selectLink(opt) {
  emit('update:modelValue', { name: opt.name, label: opt.label })
  linkOpen.value = false
  linkQuery.value = ''
  handleBlur()
}

function clearLink() {
  emit('update:modelValue', null)
  linkQuery.value = ''
  linkResults.value = []
  handleBlur()
}

// ─── Blur ─────────────────────────────────────────────────────────────────────

function handleBlur() {
  emit('blur', props.field.id)
}
</script>

<style scoped>
/* ── Base ── */
.cf-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.cf-field--inline {
  flex-direction: row;
  align-items: center;
  gap: 8px;
}

/* ── Label ── */
.cf-label {
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
  color: var(--muted);
  line-height: 1.4;
  user-select: none;
}

.cf-required {
  color: var(--danger);
  margin-left: 2px;
}

/* ── Shared input base ── */
.cf-input {
  width: 100%;
  height: var(--input-height-md);
  padding: var(--input-padding);
  font-size: var(--text-sm);
  font-family: var(--font-sans);
  color: var(--foreground);
  background: var(--surface-secondary);
  /* Was `border: var(--field-border)` — --field-border is a COLOR only
     (#abacb1), and the border shorthand resets any sub-property it doesn't
     set to its initial value, which for border-style is `none`. So this
     never actually drew a border, anywhere this component is used, not
     just in the task detail rail — matching .hui-field's real recipe
     (index.css) below. */
  border: var(--field-border-width) solid var(--field-border);
  border-radius: var(--input-radius);
  outline: none;
  transition: border-color var(--transition-base), box-shadow var(--transition-base);
  line-height: 1.4;
  -webkit-appearance: none;
}

.cf-input:focus {
  border-color: var(--accent);
  box-shadow: var(--shadow-focus);
  background: var(--surface);
}

.cf-input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  background: var(--surface-secondary);
}

.cf-field--error .cf-input {
  border-color: var(--danger-soft-hover);
}

.cf-field--error .cf-input:focus {
  box-shadow: var(--shadow-focus-danger);
}

/* ── Textarea ── */
.cf-textarea {
  height: auto;
  padding: 8px 12px;
  resize: vertical;
  min-height: 72px;
}

/* ── Number with unit ── */
.cf-number-wrap {
  position: relative;
  display: flex;
  align-items: center;
}

.cf-unit {
  position: absolute;
  left: 10px;
  font-size: var(--text-sm);
  color: var(--muted);
  pointer-events: none;
  z-index: 1;
}

/* A suffix sits on the RIGHT, not left:10px like every prefix unit —
   .cf-unit--suffix used to only adjust margin, never move to the other
   side, so % rendered on top of whatever digit happened to be there. */
.cf-unit--suffix {
  left: auto;
  right: 10px;
}

.cf-input--with-unit {
  padding-left: 28px;
}

/* Mirror of the above, for a suffix — reserves room on the right instead. */
.cf-input--with-suffix {
  padding-right: 28px;
}

/* ── Date ── */
.cf-date {
  cursor: pointer;
}

/* ── Select ── */
.cf-select-wrap {
  position: relative;
}

.cf-select {
  appearance: none;
  -webkit-appearance: none;
  padding-right: 28px;
  cursor: pointer;
  background: var(--surface-secondary);
}

.cf-select-icon {
  position: absolute;
  right: 10px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--muted);
  pointer-events: none;
}

/* ── Multiselect ── */
.cf-multi {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.cf-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.cf-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: var(--chip-height);
  padding: var(--chip-padding);
  font-size: var(--chip-font-size);
  font-weight: var(--chip-font-weight);
  color: var(--accent);
  background: var(--accent-soft);
  border-radius: var(--chip-radius);
  border: 1px solid var(--accent-soft-hover);
  white-space: nowrap;
}

.cf-chip-remove {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  height: 14px;
  border: none;
  background: none;
  color: var(--accent);
  cursor: pointer;
  padding: 0;
  border-radius: 2px;
  transition: background var(--transition-fast), color var(--transition-fast);
}

.cf-chip-remove:hover {
  background: var(--accent-soft);
  color: var(--accent-hover);
}

.cf-multi-dropdown {
  position: relative;
  display: inline-block;
}

.cf-multi-trigger {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 24px;
  padding: 0 8px;
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
  color: var(--muted);
  background: transparent;
  border: 1px dashed var(--border-secondary);
  border-radius: var(--radius-xs);
  cursor: pointer;
  transition: all var(--transition-base);
}

.cf-multi-trigger:hover {
  border-color: var(--accent);
  color: var(--accent);
  background: var(--accent-soft);
}

.cf-dropdown-panel {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  min-width: 160px;
  background: var(--surface);
  border: var(--border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  z-index: var(--z-dropdown);
  overflow: hidden;
  padding: 4px;
}

.cf-dropdown-item {
  display: block;
  width: 100%;
  padding: 6px 10px;
  font-size: var(--text-sm);
  color: var(--foreground);
  background: none;
  border: none;
  border-radius: var(--radius-xs);
  text-align: left;
  cursor: pointer;
  transition: background var(--transition-fast);
}

.cf-dropdown-item:hover {
  background: var(--surface-secondary);
}

.cf-dropdown-empty {
  padding: 8px 10px;
  font-size: var(--text-xs);
  color: var(--muted);
  text-align: center;
}

/* ── Checkbox ── */
.cf-checkbox-label {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  user-select: none;
}

.cf-checkbox {
  width: 15px;
  height: 15px;
  accent-color: var(--accent);
  cursor: pointer;
}

.cf-checkbox-text {
  font-size: var(--text-sm);
  color: var(--foreground);
}

/* ── User ── */
.cf-user-wrap {
  position: relative;
}

/* ── URL ── */
.cf-url-wrap {
  position: relative;
  display: flex;
  align-items: center;
}

.cf-url {
  padding-right: 32px;
}

.cf-url-open {
  position: absolute;
  right: 10px;
  color: var(--muted);
  display: flex;
  align-items: center;
  transition: color var(--transition-base);
}

.cf-url-open:hover {
  color: var(--accent);
}

/* ── Error ── */
.cf-error {
  font-size: var(--text-xs);
  color: var(--danger);
  margin: 0;
  line-height: 1.4;
}

/* ── Empty state ── */
.cf-empty {
  font-size: var(--text-sm);
  color: var(--muted);
}
.cf-rating { display: inline-flex; align-items: center; gap: 2px; }
.cf-star { background: none; border: none; padding: 1px; cursor: pointer; line-height: 0; color: var(--warning); }
.cf-star--off { color: var(--border-secondary); }
.cf-star:disabled { cursor: default; }

/* ── Link (ERPNext linked record) ── */
.cf-link-wrap { position: relative; }
.cf-link-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: var(--chip-height);
  padding: var(--chip-padding);
  font-size: var(--chip-font-size);
  font-weight: var(--chip-font-weight);
  color: var(--accent);
  background: var(--accent-soft);
  border-radius: var(--chip-radius);
  border: 1px solid var(--accent-soft-hover);
  max-width: 100%;
}
.cf-link-chip-label { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cf-link-open, .cf-link-clear {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--accent);
  background: none;
  border: none;
  padding: 0;
  cursor: pointer;
  transition: color var(--transition-fast);
}
.cf-link-open:hover, .cf-link-clear:hover { color: var(--accent-hover); }
.cf-link-panel { width: 100%; max-height: 220px; overflow-y: auto; }
</style>