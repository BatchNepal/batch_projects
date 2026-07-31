<template>
  <Modal :open="open" @update:open="onToggle" size="md">
    <div class="p-5 w-full">
      <h3 class="text-[15px] font-semibold text-foreground leading-tight mb-0.5">Daily standup</h3>
      <p class="text-[12.5px] text-muted mb-4">{{ sprintName }} — {{ today }}</p>

      <div v-if="loading" class="py-8 flex items-center justify-center">
        <Spinner size="sm" />
      </div>

      <template v-else>
        <!-- Your own entry — editable -->
        <div class="standup-card standup-card--mine">
          <p class="standup-card-label">Your update</p>
          <div class="standup-field">
            <label>Yesterday</label>
            <textarea v-model="form.yesterday" rows="2" placeholder="What did you work on?" />
          </div>
          <div class="standup-field">
            <label>Today</label>
            <textarea v-model="form.today" rows="2" placeholder="What are you working on?" />
          </div>
          <div class="standup-field">
            <label>Blockers</label>
            <textarea v-model="form.blockers" rows="2" placeholder="Anything in your way?" />
          </div>
          <div class="flex justify-end mt-2">
            <Button size="sm" color="primary" :isLoading="saving" @click="save">
              {{ mineExists ? 'Update' : 'Post' }}
            </Button>
          </div>
        </div>

        <!-- Everyone else's entries for today -->
        <div v-if="others.length" class="mt-5 space-y-3">
          <p class="standup-card-label">Team</p>
          <div v-for="e in others" :key="e.user" class="standup-card">
            <div class="flex items-center gap-2 mb-2">
              <span class="standup-av" :style="{ background: avatarColor(e.user) }">{{ initials(e.full_name) }}</span>
              <span class="text-[12.5px] font-semibold text-foreground">{{ e.full_name }}</span>
            </div>
            <div class="space-y-1.5 text-[12.5px] text-muted pl-1">
              <p v-if="e.yesterday"><span class="standup-tag">Yesterday</span> {{ e.yesterday }}</p>
              <p v-if="e.today"><span class="standup-tag">Today</span> {{ e.today }}</p>
              <p v-if="e.blockers" class="text-danger"><span class="standup-tag standup-tag--danger">Blockers</span> {{ e.blockers }}</p>
              <p v-if="!e.yesterday && !e.today && !e.blockers" class="italic">No update yet.</p>
            </div>
          </div>
        </div>
      </template>
    </div>
  </Modal>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { toast } from 'vue-sonner'
import Modal from '@/ui/Modal.vue'
import Spinner from '@/ui/Spinner.vue'
import { Button } from '@/ui'
import { getStandup, saveStandup } from '@/utils/api'
import { avatarColor, initials } from '@/utils/constants.js'

const props = defineProps({
  open:       { type: Boolean, default: false },
  sprint:     { type: String, default: null },
  sprintName: { type: String, default: '' },
})
const emit = defineEmits(['update:open'])
function onToggle(v) { emit('update:open', v) }

const loading = ref(false)
const saving  = ref(false)
const entries = ref([])
const mineExists = ref(false)
const today = new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'short', day: 'numeric' })
const form = reactive({ yesterday: '', today: '', blockers: '' })

const others = computed(() => entries.value.filter(e => !e.__isMine))

watch(() => [props.open, props.sprint], async ([isOpen, sprint]) => {
  if (!isOpen || !sprint) return
  loading.value = true
  form.yesterday = ''; form.today = ''; form.blockers = ''
  mineExists.value = false
  try {
    const res = await getStandup(sprint)
    entries.value = (res.entries || []).map(e => ({ ...e, __isMine: res.mine && e.name === res.mine.name }))
    if (res.mine) {
      mineExists.value = true
      form.yesterday = res.mine.yesterday || ''
      form.today = res.mine.today || ''
      form.blockers = res.mine.blockers || ''
    }
  } finally {
    loading.value = false
  }
}, { immediate: true })

async function save() {
  saving.value = true
  try {
    await saveStandup(props.sprint, { yesterday: form.yesterday, today: form.today, blockers: form.blockers })
    toast.success(mineExists.value ? 'Standup updated' : 'Standup posted')
    mineExists.value = true
    emit('update:open', false)
  } catch (e) {
    toast.error(e.message || 'Failed to save standup')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.standup-card {
  border: 1px solid var(--separator); border-radius: 8px; padding: 12px;
}
.standup-card--mine { background: var(--accent-soft); border-color: transparent; }
.standup-card-label {
  font-size: 10px; font-weight: 700; color: var(--muted);
  text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 8px;
}
.standup-field { margin-bottom: 8px; }
.standup-field:last-of-type { margin-bottom: 0; }
.standup-field label {
  display: block; font-size: 11px; font-weight: 600; color: var(--muted); margin-bottom: 3px;
}
.standup-field textarea {
  width: 100%; font-size: 12.5px; font-family: inherit; color: var(--foreground);
  background: var(--surface); border: 1px solid var(--field-border); border-radius: 6px;
  padding: 6px 8px; resize: none; outline: none; transition: border-color .1s;
}
.standup-field textarea:focus { border-color: var(--accent); }
.standup-field textarea::placeholder { color: var(--field-placeholder); }
.standup-av {
  width: 22px; height: 22px; border-radius: 50%; flex-shrink: 0;
  display: inline-flex; align-items: center; justify-content: center;
  color: var(--accent-foreground); font-size: 8.5px; font-weight: 700;
}
.standup-tag {
  display: inline-block; font-size: 10px; font-weight: 700; color: var(--muted);
  text-transform: uppercase; letter-spacing: 0.03em; margin-right: 4px;
}
.standup-tag--danger { color: var(--danger); }
</style>
