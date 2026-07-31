<template>
  <div class="max-w-xl mx-auto px-6 py-12 space-y-6">
    <div class="mb-8">
      <h1 class="text-xl font-semibold text-foreground mb-2">Invite your team</h1>
      <p class="text-sm text-muted">Invitations will be sent by email. You can add more members later from Settings.</p>
    </div>

    <!-- Email input -->
    <div>
      <div class="flex gap-2 items-end">
        <Input
          v-model="emailInput"
          label="Email addresses"
          @keydown.enter.prevent="addEmail"
          @keydown.tab.prevent="addEmail"
          @paste.prevent="onPaste"
          placeholder="name@company.com, another@company.com"
          size="sm"
        />
        <Button variant="flat" color="default" size="sm" @click="addEmail">Add</Button>
      </div>
      <p class="mt-1 text-xs text-muted">Press Enter or Tab to add. Paste multiple emails separated by commas.</p>
    </div>

    <!-- Invite chips -->
    <div v-if="modelValue.length" class="space-y-2">
      <div
        v-for="(invite, i) in modelValue"
        :key="invite.email"
        class="flex items-center gap-3 px-3 py-2 bg-surface-secondary border border-border rounded-sm"
      >
        <div class="w-6 h-6 rounded-full bg-accent-soft flex items-center justify-center text-xs font-semibold text-accent-soft-foreground shrink-0">
          {{ invite.email[0].toUpperCase() }}
        </div>
        <span class="flex-1 text-sm text-foreground">{{ invite.email }}</span>
        <Select
          :modelValue="invite.role"
          @update:modelValue="updateRole(i, $event)"
          size="sm"
          :fullWidth="false"
        >
          <SelectItem value="Admin">Admin</SelectItem>
          <SelectItem value="Member">Member</SelectItem>
          <SelectItem value="Viewer">Viewer</SelectItem>
        </Select>
        <button type="button" @click="removeInvite(i)" class="text-muted hover:text-foreground transition-colors">
          <X class="size-3.5" />
        </button>
      </div>
    </div>

    <p v-else class="text-sm text-muted py-4 text-center">No invites added yet. This step is optional.</p>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { X } from 'lucide-vue-next'
import { Button, Input, Select, SelectItem } from '@/ui'

const props = defineProps({ modelValue: { type: Array, required: true } })
const emit = defineEmits(['update:modelValue'])

const emailInput = ref('')

function addEmail() {
  const emails = emailInput.value.split(/[\s,;]+/).map(e => e.trim().toLowerCase()).filter(e => e.includes('@'))
  if (!emails.length) return
  const next = [...props.modelValue]
  emails.forEach(email => {
    if (!next.find(i => i.email === email)) next.push({ email, role: 'Member' })
  })
  emit('update:modelValue', next)
  emailInput.value = ''
}

function onPaste(e) {
  emailInput.value = (e.clipboardData || window.clipboardData).getData('text')
  addEmail()
}

function removeInvite(idx) {
  const next = props.modelValue.filter((_, i) => i !== idx)
  emit('update:modelValue', next)
}

function updateRole(idx, role) {
  const next = props.modelValue.map((inv, i) => i === idx ? { ...inv, role } : inv)
  emit('update:modelValue', next)
}
</script>
