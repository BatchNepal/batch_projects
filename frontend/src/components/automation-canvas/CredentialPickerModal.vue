<template>
  <Modal :open="open" size="sm" @update:open="emit('update:open', $event)">
    <ModalHeader title="Attach a credential" subtitle="Never inlined in the workflow's own config — stored encrypted, referenced by name only." />
    <ModalBody>
      <div v-if="credentials.length" class="flex flex-col gap-1 mb-4">
        <div v-for="c in credentials" :key="c.name" class="flex items-center gap-1">
          <button
            type="button"
            :class="cn(
              'flex-1 min-w-0 flex items-center gap-2.5 px-2.5 py-2 rounded-md text-left transition-colors',
              selected === c.name ? 'bg-accent-soft' : 'hover:bg-surface-hover',
            )"
            @click="selected = c.name"
          >
            <span class="flex items-center justify-center size-7 rounded-md bg-surface-tertiary shrink-0">
              <Icon :icon="Key" :size="14" class="text-muted" />
            </span>
            <span class="min-w-0 flex-1">
              <p class="text-sm text-foreground truncate">{{ c.label }}</p>
              <p class="text-xs text-muted truncate">{{ c.credential_type }}</p>
            </span>
            <Check v-if="selected === c.name" :size="15" class="text-accent shrink-0" />
          </button>
          <IconButton size="sm" variant="ghost" @click="onDelete(c)">
            <Icon :icon="Trash2" :size="14" class="text-muted" />
          </IconButton>
        </div>
      </div>
      <p v-else class="text-xs text-muted mb-4">No credentials yet — create one below.</p>

      <div class="border-t border-border pt-3 flex flex-col gap-2.5">
        <p class="text-xs font-medium text-muted uppercase tracking-wider">New credential</p>
        <Input v-model="newLabel" label="Label" placeholder="Billing webhook token" size="sm" />
        <Select v-model="newType" label="Type" size="sm">
          <SelectItem value="bearer_token">Bearer token</SelectItem>
          <SelectItem value="api_key">API key</SelectItem>
          <SelectItem value="basic_auth">Basic auth</SelectItem>
          <SelectItem value="custom_header">Custom header</SelectItem>
          <SelectItem value="webhook_url">Webhook URL (Slack/Discord/Teams/Google Chat)</SelectItem>
          <SelectItem value="bot_token">Bot token (Telegram)</SelectItem>
        </Select>
        <Input v-model="newValue" label="Value" type="password" placeholder="Never shown again after saving" size="sm" />
        <p v-if="createError" class="text-xs text-danger">{{ createError }}</p>
        <Button size="sm" variant="outline" :is-disabled="!newLabel || !newValue" :is-loading="creating" @click="onCreate">
          Create &amp; use
        </Button>
      </div>
    </ModalBody>
    <ModalFooter>
      <Button variant="ghost" size="sm" @click="emit('update:open', false)">Cancel</Button>
      <Button color="accent" size="sm" :is-disabled="!selected" @click="onConfirm">Attach</Button>
    </ModalFooter>
  </Modal>
</template>

<script setup>
import { ref, watch } from 'vue'
import { Key, Check, Trash2 } from 'lucide-vue-next'
import Modal from '@/ui/Modal.vue'
import ModalHeader from '@/ui/ModalHeader.vue'
import ModalBody from '@/ui/ModalBody.vue'
import ModalFooter from '@/ui/ModalFooter.vue'
import Input from '@/ui/Input.vue'
import Select from '@/ui/Select.vue'
import SelectItem from '@/ui/SelectItem.vue'
import Button from '@/ui/Button.vue'
import Icon from '@/ui/Icon.vue'
import IconButton from '@/ui/IconButton.vue'
import { cn } from '@/lib/utils'
import { listCredentials, createCredential, deleteCredential } from '@/utils/api'

const props = defineProps({
  open: { type: Boolean, default: false },
  modelValue: { type: String, default: null },
  defaultType: { type: String, default: 'bearer_token' },
})
const emit = defineEmits(['update:open', 'select'])

const credentials = ref([])
const selected = ref(props.modelValue)
const newLabel = ref('')
const newType = ref(props.defaultType)
const newValue = ref('')
const creating = ref(false)

async function load() {
  credentials.value = await listCredentials()
  selected.value = props.modelValue
  newType.value = props.defaultType
}
watch(() => props.open, (v) => { if (v) load() })

const createError = ref('')
async function onCreate() {
  creating.value = true
  createError.value = ''
  try {
    const res = await createCredential({ label: newLabel.value, credential_type: newType.value, value: newValue.value })
    credentials.value.unshift({ name: res.name, label: res.label, credential_type: res.credential_type })
    selected.value = res.name
    newLabel.value = ''; newValue.value = ''
  } catch (err) {
    // Was previously silently swallowed — a permission error (non-admin
    // trying to create a credential) left the form sitting there with zero
    // feedback. Found via live-verify testing, not a hypothetical.
    createError.value = err?.message || 'Could not create credential.'
  } finally {
    creating.value = false
  }
}

async function onDelete(c) {
  if (!window.confirm(`Delete credential "${c.label}"? Any automation node using it will fail until reattached.`)) return
  await deleteCredential(c.name)
  credentials.value = credentials.value.filter(x => x.name !== c.name)
  if (selected.value === c.name) selected.value = null
}

function onConfirm() {
  const c = credentials.value.find((c) => c.name === selected.value)
  emit('select', { name: selected.value, label: c?.label })
  emit('update:open', false)
}
</script>
