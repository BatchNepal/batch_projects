<template>
  <Teleport to="body">
    <div class="ct-backdrop" @click.self="$emit('close')">
      <div class="ct-modal">

        <!-- Header -->
        <div class="ct-header">
          <div class="ct-header-left">
            <div>
              <svg stroke="currentColor" fill="none" stroke-width="0" 
              viewBox="0 0 15 15" height="18px" width="18px" xmlns="http://www.w3.org/2000/svg"><path d="M5 8.90039C6.43913 8.90046 7.6804 9.15211 8.5752 9.75488C9.50225 10.3797 10 11.3432 10 12.6006C9.99965 12.8763 9.77567 13.1003 9.5 13.1006C9.22426 13.1004 9.00035 12.8763 9 12.6006C9.00002 11.643 8.64164 11.0053 8.0166 10.584C7.35911 10.1411 6.3499 9.90046 5 9.90039C3.65022 9.90044 2.6409 10.1412 1.9834 10.584C1.35846 11.0053 1 11.643 1 12.6006C0.999652 12.8763 0.775703 13.1003 0.5 13.1006C0.224252 13.1004 0.000348561 12.8763 0 12.6006C0 11.3434 0.49706 10.3797 1.42383 9.75488C2.31864 9.15205 3.56076 8.90044 5 8.90039ZM9.97461 8.90039C11.4139 8.9004 12.6549 9.15204 13.5498 9.75488C14.4771 10.3797 14.9746 11.343 14.9746 12.6006C14.9743 12.8764 14.7505 13.1006 14.4746 13.1006C14.1989 13.1004 13.975 12.8763 13.9746 12.6006C13.9746 11.6428 13.6165 11.0053 12.9912 10.584C12.4734 10.2352 11.7376 10.0138 10.7891 9.93457C10.5558 9.55417 10.2666 9.20728 9.91992 8.90137C9.93812 8.90129 9.95635 8.90039 9.97461 8.90039ZM5.00098 1.84961C6.74004 1.8502 8.15018 3.26085 8.15039 5C8.15018 6.73915 6.74004 8.14882 5.00098 8.14941C3.26141 8.14941 1.8508 6.73951 1.85059 5C1.8508 3.26048 3.26141 1.84961 5.00098 1.84961ZM9.97559 1.84961C11.7149 1.84994 13.1248 3.26069 13.125 5C13.1248 6.73931 11.7149 8.14908 9.97559 8.14941C9.45224 8.14941 8.95974 8.01975 8.52539 7.79395C8.73332 7.53194 8.91351 7.24709 9.05957 6.94238C9.33776 7.07372 9.64758 7.14941 9.97559 7.14941C11.1626 7.14908 12.1248 6.18703 12.125 5C12.1248 3.81297 11.1626 2.84994 9.97559 2.84961C9.64775 2.84961 9.33765 2.92435 9.05957 3.05566C8.91343 2.75109 8.73336 2.46598 8.52539 2.2041C8.95962 1.97833 9.45244 1.84961 9.97559 1.84961ZM5.00098 2.84961C3.81369 2.84961 2.8508 3.81277 2.85059 5C2.8508 6.18723 3.8137 7.14941 5.00098 7.14941C6.18775 7.14882 7.15018 6.18686 7.15039 5C7.15018 3.81313 6.18775 2.8502 5.00098 2.84961Z" fill="currentColor"></path></svg>
            </div>
            <div>
              <p class="ct-header-title">Create a new team</p>
             <p class="ct-header-subtitle">Required fields are marked with an asterisk*</p>
            </div>

          </div>
          <button class="ct-close" @click="$emit('close')">
            <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>
          </button>
        </div>

        <!-- Body -->
        <div class="ct-body">
           

          <!-- Team name -->
          <div class="ct-field">
            <label class="ct-label">Team Name <span class="ct-req">*</span></label>
            <input
              ref="nameInput"
              v-model="form.name"
              class="ct-input"
              placeholder="e.g. Engineering, Operations"
              @input="autoKey"
            />
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
                  <div class="ct-swatch ct-swatch--custom" :style="{ background: form.color, borderColor: form.color }">
                    <svg width="10" height="10" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"/></svg>
                  </div>
                  <input type="color" v-model="form.color" class="ct-color-hidden"/>
                </div>
              </div>
            </div>
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
            Create
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
import { alertDialog } from '@/composables/useConfirmDialog'

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
    alertDialog(e.message || 'Failed to create team')
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
  background: #050c1f75;
  display: flex; align-items: center; justify-content: center;
  padding: 20px;
}

.ct-modal {
  background: var(--surface); border-radius:9pt;
  width: 460px; max-width: 100%;
  box-shadow: 12px 20px 60px rgba(9,30,66,.25);
  display: flex; flex-direction: column;
  overflow: hidden;
}

/* Header */
.ct-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 20px;border-bottom: 1px solid var(--border);
}
.ct-header-left { display: flex; align-items: center; gap: 10px; }
.ct-logo {
  width: 26px; height: 26px; border-radius: 5px; background: var(--accent);
  display: flex; align-items: center; justify-content: center;
  color: var(--accent-foreground); font-size:var(--text-micro); font-weight: 800;
}
.ct-header-title { font-size:var(--text-md); font-weight: 600; color: var(--foreground); }
.ct-header-subtitle{
  font-size:var(--text-sm); font-weight: 400; color: var(--muted); margin-top: 1px;
}
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
  font-size:var(--text-3xl); transition: background .2s;
  box-shadow: 0 2px 8px rgba(0,0,0,.15);
}
.ct-preview-initials { color: var(--accent-foreground); font-size:var(--text-md); font-weight: 800; }
.ct-preview-name { font-size:var(--text-md); font-weight: 700; color: var(--foreground); }
.ct-preview-key { font-size:var(--text-xs); font-family: monospace; color: var(--muted); margin-top: 1px; }

/* Fields */
.ct-field { display: flex; flex-direction: column; gap: 6px; }
.ct-label { font-size:var(--text-sm); font-weight: 600; color: var(--subtle-text); }
.ct-sublabel { font-size:var(--text-sm); font-weight: 400; color: var(--muted); }
.ct-req { color: var(--danger); }

.ct-input {
  height: 36px; padding: 0 12px;
  font-size:var(--text-base); font-family: inherit; color: var(--foreground);
  background: var(--surface);
   border: 1px solid #d9dadc;
  border-radius: 5px; outline: none;
      transition: background-color .15s ease, border-color .15s ease, box-shadow .15s cubic-bezier(0, 0, .2, 1);
}
.ct-input:hover { background: #f3f3f4; border-color: var(--border-secondary); }

.ct-input:focus { background: var(--surface); border-color: var(--accent); 
    box-shadow: inset 0 0 0 1px #4688ec;
}
.ct-input::placeholder { color: var(--muted); }
.ct-input--mono { font-family: monospace; font-size:var(--text-base); letter-spacing: .06em; text-transform: uppercase; width: 110px; }
.ct-input--icon { width: 60px; text-align: center; font-size:var(--text-3xl); padding: 0 6px; }

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
.ct-icon-hint { font-size:var(--text-sm); color: var(--muted); }

/* Select */
.ct-select {
  display: flex; align-items: center; justify-content: space-between;
  width: 100%; height: 36px; padding: 0 11px;
  font-size:var(--text-base); font-family: inherit;
  background: var(--surface); border: 1.75px solid #d9dadc;
  border-radius: 5px; cursor: pointer; outline: none;
  transition: border-color .1s, background .1s;
}
.ct-select:hover { border-color: var(--border-secondary); background: var(--surface-secondary); }
.ct-select-caret { color: var(--muted); flex-shrink: 0; }

/* Footer */
.ct-footer {
  display: flex; justify-content: flex-end; gap: 8px;
  padding: 14px 20px; border-top: 1px solid var(--border);
}
.ct-btn-ghost {
  padding: 0 14px;
  font-size:var(--text-base); font-weight: 600; font-family: inherit;
  color: var(--foreground); background: var(--surface); border: 1px solid var(--border);
  border-radius: 5px; cursor: pointer; transition: background .1s;
}
.ct-btn-ghost:hover { background: var(--surface-secondary); }
.ct-btn-primary {
  padding: 4px 16px;
  font-size:var(--text-base); font-weight: 700; font-family: inherit;
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