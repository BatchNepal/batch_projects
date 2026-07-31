<template>
  <Teleport to="body">
    <div class="ct-backdrop" @click.self="$emit('close')">
      <div class="ct-modal">

        <!-- Header -->
        <div class="ct-header">
          <div class="ct-header-left">
            <div class="ct-logo">BP</div>
            <span class="ct-header-title">Create team</span>
          </div>
          <button class="ct-close" @click="$emit('close')">
            <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>
          </button>
        </div>

        <!-- Body -->
        <div class="ct-body">

          <!-- Preview -->
          <div class="ct-preview-row">
            <div class="ct-preview-dot" :style="{ background: form.color }">
              <span v-if="form.icon">{{ form.icon }}</span>
              <span v-else class="ct-preview-initials">{{ previewInitials }}</span>
            </div>
            <div class="ct-preview-text">
              <p class="ct-preview-name">{{ form.name || 'Team name' }}</p>
              <p class="ct-preview-key">{{ form.key || 'KEY' }}</p>
            </div>
          </div>

          <!-- Team name -->
          <div class="ct-field">
            <label class="ct-label">Team name <span class="ct-req">*</span></label>
            <input
              ref="nameInput"
              v-model="form.name"
              class="ct-input"
              placeholder="e.g. Engineering, Operations"
              @input="autoKey"
            />
          </div>

          <!-- Key -->
          <div class="ct-field">
            <label class="ct-label">Team key <span class="ct-sublabel">· Used in URLs</span></label>
            <input
              v-model="form.key"
              class="ct-input ct-input--mono"
              maxlength="6"
              placeholder="ENG"
              @input="form.key = form.key.toUpperCase().replace(/[^A-Z0-9]/g, '')"
            />
          </div>

          <!-- Color + Icon row -->
          <div class="ct-field">
            <label class="ct-label">Colour & icon</label>
            <div class="ct-color-row">
              <!-- Color swatches -->
              <div class="ct-swatches">
                <button
                  v-for="c in COLORS" :key="c"
                  class="ct-swatch"
                  :style="{ background: c }"
                  :class="{ active: form.color === c }"
                  @click="form.color = c"
                />
                <!-- Custom color -->
                <div class="ct-custom-color">
                  <div class="ct-swatch ct-swatch--custom" :style="{ background: form.color }">
                    <svg width="10" height="10" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"/></svg>
                  </div>
                  <input type="color" v-model="form.color" class="ct-color-hidden"/>
                </div>
              </div>
              <!-- Emoji -->
              <div class="ct-icon-wrap">
                <input
                  v-model="form.icon"
                  class="ct-input ct-input--icon"
                  placeholder="🚀"
                  maxlength="2"
                />
                <span class="ct-icon-hint">optional emoji</span>
              </div>
            </div>
          </div>

          <!-- Department (optional) -->
          <div class="ct-field">
            <label class="ct-label">ERPNext Department <span class="ct-sublabel">· optional</span></label>
            <FieldDropdown width="w-full">
              <template #trigger>
                <button class="ct-select">
                  <span :style="{ color: form.department ? 'var(--foreground)' : 'var(--muted)' }">
                    {{ form.department || 'Link to department…' }}
                  </span>
                  <svg class="ct-select-caret" width="11" height="11" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7"/></svg>
                </button>
              </template>
              <DropdownItem @click="form.department = null"><span style="color:var(--muted)">None</span></DropdownItem>
              <div style="height:1px;background:var(--border);margin:3px 0"/>
              <DropdownItem v-for="d in departments" :key="d.name" :active="form.department === d.name" @click="form.department = d.name">
                {{ d.department_name || d.name }}
              </DropdownItem>
            </FieldDropdown>
          </div>

        </div>

        <!-- Footer -->
        <div class="ct-footer">
          <button class="ct-btn-ghost" @click="$emit('close')">Cancel</button>
          <button
            class="ct-btn-primary"
            :disabled="!form.name.trim() || !form.key.trim() || creating"
            @click="submit"
          >
            <div v-if="creating" class="ct-spinner"/>
            Create team
          </button>
        </div>

      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import * as api from '@/utils/api.js'
import FieldDropdown from '@/components/FieldDropdown.vue'
import DropdownItem  from '@/components/DropdownItem.vue'

const emit = defineEmits(['close', 'created'])

const nameInput = ref(null)
const creating  = ref(false)
const departments = ref([])

const COLORS = [
  '#225DFB', '#7C3AED', '#059669', '#DC2626',
  '#D97706', '#0891B2', '#BE185D', '#0E7490',
  '#16A34A', '#9333EA', '#EA580C', '#2563EB',
]

const form = ref({
  name:       '',
  key:        '',
  color:      '#225DFB',
  icon:       '',
  department: null,
})

const previewInitials = computed(() => {
  if (!form.value.name) return 'T'
  const words = form.value.name.trim().split(/\s+/)
  if (words.length >= 2) return (words[0][0] + words[1][0]).toUpperCase()
  return form.value.name.slice(0, 2).toUpperCase()
})

function autoKey() {
  const words = form.value.name.trim().split(/\s+/).filter(Boolean)
  if (words.length >= 2) {
    form.value.key = words.slice(0, 4).map(w => w[0]).join('').toUpperCase()
  } else if (words.length === 1) {
    form.value.key = words[0].slice(0, 4).toUpperCase().replace(/[^A-Z0-9]/g, '')
  }
}

async function submit() {
  if (!form.value.name.trim() || !form.value.key.trim() || creating.value) return
  creating.value = true
  try {
    const team = await api.createTeam({
      team_name:  form.value.name.trim(),
      team_key:   form.value.key.trim(),
      team_color: form.value.color,
      team_icon:  form.value.icon || '',
      department: form.value.department || '',
    })
    emit('created', team)
  } catch (e) {
    alert(e.message || 'Failed to create team')
  } finally {
    creating.value = false
  }
}

onMounted(async () => {
  await nextTick()
  nameInput.value?.focus()
  try {
    departments.value = await api.getErpNextDepartments()
  } catch {}
})
</script>

<style scoped>
.ct-backdrop {
  position: fixed; inset: 0; z-index: 1000;
  background: rgba(9,30,66,.55);
  display: flex; align-items: center; justify-content: center;
  padding: 20px;
}

.ct-modal {
  background: var(--surface); border-radius: 10px;
  width: 460px; max-width: 100%;
  box-shadow: 0 20px 60px rgba(9,30,66,.25);
  display: flex; flex-direction: column;
  overflow: hidden;
}

/* Header */
.ct-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 20px; border-bottom: 1px solid var(--border);
}
.ct-header-left { display: flex; align-items: center; gap: 10px; }
.ct-logo {
  width: 26px; height: 26px; border-radius: 5px; background: var(--accent);
  display: flex; align-items: center; justify-content: center;
  color: var(--accent-foreground); font-size: 9px; font-weight: 800;
}
.ct-header-title { font-size: 14px; font-weight: 700; color: var(--foreground); }
.ct-close {
  display: flex; align-items: center; justify-content: center;
  width: 28px; height: 28px; border: none; background: none;
  color: var(--muted); border-radius: 4px; cursor: pointer; transition: background .1s;
}
.ct-close:hover { background: var(--surface-secondary); color: var(--foreground); }

/* Body */
.ct-body { padding: 20px; display: flex; flex-direction: column; gap: 18px; }

/* Preview */
.ct-preview-row {
  display: flex; align-items: center; gap: 14px;
  padding: 14px 16px; background: var(--surface-secondary);
  border-radius: 8px;
}
.ct-preview-dot {
  width: 44px; height: 44px; border-radius: 10px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  font-size: 20px; transition: background .2s;
  box-shadow: 0 2px 8px rgba(0,0,0,.15);
}
.ct-preview-initials { color: var(--accent-foreground); font-size: 14px; font-weight: 800; }
.ct-preview-name { font-size: 15px; font-weight: 700; color: var(--foreground); }
.ct-preview-key { font-size: 11px; font-family: monospace; color: var(--muted); margin-top: 1px; }

/* Fields */
.ct-field { display: flex; flex-direction: column; gap: 6px; }
.ct-label { font-size: 12.5px; font-weight: 600; color: var(--foreground); }
.ct-sublabel { font-size: 11.5px; font-weight: 400; color: var(--muted); }
.ct-req { color: var(--danger); }

.ct-input {
  height: 36px; padding: 0 11px;
  font-size: 13.5px; font-family: inherit; color: var(--foreground);
  background: var(--surface-secondary); border: 1.5px solid var(--border);
  border-radius: 5px; outline: none;
  transition: background .1s, border-color .1s, box-shadow .1s;
}
.ct-input:focus { background: var(--surface); border-color: var(--accent); box-shadow: 0 0 0 3px rgba(76,154,255,.12); }
.ct-input::placeholder { color: var(--muted); }
.ct-input--mono { font-family: monospace; font-size: 13px; letter-spacing: .06em; text-transform: uppercase; width: 110px; }
.ct-input--icon { width: 60px; text-align: center; font-size: 22px; padding: 0 6px; }

/* Color row */
.ct-color-row { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
.ct-swatches { display: flex; gap: 6px; flex-wrap: wrap; }
.ct-swatch {
  width: 24px; height: 24px; border-radius: 6px; cursor: pointer;
  border: 2px solid transparent; transition: transform .1s, border-color .1s;
  flex-shrink: 0;
}
.ct-swatch:hover { transform: scale(1.15); }
.ct-swatch.active { border-color: var(--accent-foreground); box-shadow: 0 0 0 2px currentColor; }
.ct-swatch--custom { display: flex; align-items: center; justify-content: center; color: rgba(255,255,255,.8); }
.ct-custom-color { position: relative; }
.ct-color-hidden { position: absolute; inset: 0; opacity: 0; cursor: pointer; width: 100%; height: 100%; }
.ct-icon-wrap { display: flex; align-items: center; gap: 8px; }
.ct-icon-hint { font-size: 11.5px; color: var(--muted); }

/* Select */
.ct-select {
  display: flex; align-items: center; justify-content: space-between;
  width: 100%; height: 36px; padding: 0 11px;
  font-size: 13.5px; font-family: inherit;
  background: var(--surface-secondary); border: 1.5px solid var(--border);
  border-radius: 5px; cursor: pointer; outline: none;
  transition: border-color .1s, background .1s;
}
.ct-select:hover { border-color: var(--border-secondary); background: var(--surface-secondary); }
.ct-select-caret { color: var(--muted); flex-shrink: 0; }

/* Footer */
.ct-footer {
  display: flex; justify-content: flex-end; gap: 8px;
  padding: 14px 20px; border-top: 1px solid var(--border);
  background: var(--surface-secondary);
}
.ct-btn-ghost {
  height: 34px; padding: 0 14px;
  font-size: 13px; font-weight: 600; font-family: inherit;
  color: var(--foreground); background: var(--surface); border: 1px solid var(--border);
  border-radius: 5px; cursor: pointer; transition: background .1s;
}
.ct-btn-ghost:hover { background: var(--surface-secondary); }
.ct-btn-primary {
  display: inline-flex; align-items: center; gap: 7px;
  height: 34px; padding: 0 16px;
  font-size: 13px; font-weight: 700; font-family: inherit;
  color: var(--accent-foreground); background: var(--accent); border: none;
  border-radius: 5px; cursor: pointer; transition: background .1s;
}
.ct-btn-primary:hover { background: var(--accent-hover); }
.ct-btn-primary:disabled { opacity: .5; cursor: not-allowed; }
.ct-spinner {
  width: 13px; height: 13px; border-radius: 50%;
  border: 2px solid rgba(255,255,255,.3); border-top-color: var(--accent-foreground);
  animation: ct-spin .7s linear infinite;
}
@keyframes ct-spin { to { transform: rotate(360deg) } }
</style>