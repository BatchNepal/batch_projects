<template>
  <div class="min-h-full bg-background flex flex-col">

    <!-- Top bar -->
    <header class="shrink-0 bg-surface border-b border-border">
      <div class="max-w-[600px] mx-auto w-full px-5 h-14 flex items-center justify-between gap-4">
        <div class="flex items-center gap-2.5 min-w-0">
          <div class="w-7 h-7 rounded-lg flex items-center justify-center text-white text-[11px] font-bold shrink-0"
               :style="{ background: 'var(--accent)' }">
            <FormInput class="size-4" />
          </div>
          <div class="min-w-0">
            <p class="text-[14px] font-semibold text-foreground truncate leading-tight">
              {{ form?.form_title || 'Intake Form' }}
            </p>
            <p v-if="form?.project" class="text-[11px] text-muted leading-tight">{{ form.project }}</p>
          </div>
        </div>
      </div>
    </header>

    <!-- Loading -->
    <div v-if="loading" class="flex-1 flex items-center justify-center">
      <Spinner class="w-6 h-6 text-primary" />
    </div>

    <!-- Error -->
    <div v-else-if="error" class="flex-1 flex items-center justify-center p-6">
      <div class="text-center max-w-sm">
        <div class="size-12 rounded-2xl bg-default flex items-center justify-center mx-auto mb-4">
          <AlertCircle class="size-6 text-muted" />
        </div>
        <h1 class="text-[16px] font-semibold text-foreground">{{ error }}</h1>
        <p class="text-[13px] text-muted mt-1.5">
          This form may have been deactivated or the link is invalid.
        </p>
      </div>
    </div>

    <!-- Success -->
    <div v-else-if="submitted" class="flex-1 flex items-center justify-center p-6">
      <div class="text-center max-w-sm">
        <div class="size-12 rounded-2xl bg-success-soft flex items-center justify-center mx-auto mb-4">
          <CheckCircle2 class="size-6 text-success" />
        </div>
        <h1 class="text-[16px] font-semibold text-foreground">Form submitted</h1>
        <p class="text-[13px] text-muted mt-1.5">
          Thank you! Your submission has been received.
        </p>
      </div>
    </div>

    <!-- Form -->
    <main v-else class="flex-1 overflow-auto">
      <div class="max-w-[600px] mx-auto w-full p-6">
        <div class="bg-surface rounded-lg border border-border p-6">
          <div class="space-y-4">
            <div v-for="(field, i) in form.fields" :key="i">
              <label class="text-[13px] font-medium text-foreground mb-1 block">
                {{ field.label }}
                <span v-if="field.required" class="text-danger">*</span>
              </label>

              <Input v-if="field.type === 'text' || field.type === 'email'"
                v-model="values[i]" :type="field.type" :placeholder="field.label"
                size="sm" class="w-full" />

              <textarea v-else-if="field.type === 'textarea'"
                v-model="values[i]" :placeholder="field.label"
                class="w-full h-24 px-3 py-2 text-[13px] rounded-lg border border-border bg-surface resize-none outline-none focus:border-accent" />

              <Select v-else-if="field.type === 'select'"
                v-model="values[i]" size="sm" class="w-full">
                <SelectItem value="">{{ field.label }}</SelectItem>
                <SelectItem v-for="opt in field.options || []" :key="opt" :value="opt">{{ opt }}</SelectItem>
              </Select>

              <Input v-else
                v-model="values[i]" :placeholder="field.label"
                size="sm" class="w-full" />
            </div>

            <div class="pt-2">
              <Button size="sm" color="primary" full-width
                :isLoading="submitting" :disabled="!isValid"
                @click="doSubmit">
                Submit
              </Button>
            </div>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { Button, Input, Select, SelectItem, Spinner } from '@/ui'
import { FormInput, AlertCircle, CheckCircle2 } from 'lucide-vue-next'
import * as api from '@/utils/api'

const route = useRoute()
const form = ref(null)
const loading = ref(true)
const error = ref(null)
const submitting = ref(false)
const submitted = ref(false)
const values = ref([])

const isValid = computed(() => {
  if (!form.value?.fields) return false
  return form.value.fields.every((f, i) => {
    if (f.required) return values.value[i]?.trim()
    return true
  })
})

onMounted(async () => {
  const token = route.params.token
  if (!token) { error.value = 'Invalid form link.'; loading.value = false; return }
  try {
    const data = await api.call('batch_projects.api.forms.get_public_form', { form: token })
    form.value = data
    values.value = data.fields.map(() => '')
  } catch (e) {
    error.value = e.messages?.[0] || 'Form not found.'
  } finally {
    loading.value = false
  }
})

async function doSubmit() {
  const token = route.params.token
  if (!token || submitting.value) return
  submitting.value = true
  try {
    const payload = {}
    form.value.fields.forEach((f, i) => {
      if (values.value[i]?.trim()) payload[f.label] = values.value[i].trim()
    })
    await api.call('batch_projects.api.forms.submit_intake_form', {
      form: token,
      values: JSON.stringify(payload),
    })
    submitted.value = true
  } catch (e) {
    // Error is shown via toast from the api wrapper
  } finally {
    submitting.value = false
  }
}
</script>
