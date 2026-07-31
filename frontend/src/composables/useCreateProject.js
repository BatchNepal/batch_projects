import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useProjectStore } from '@/stores/project'
import { toast } from 'vue-sonner'
import { createProject, createProjectFromTemplate } from '@/utils/api'
import { WORKFLOW_PRESETS } from '@/constants/workflow-presets'
import { TEMPLATE_ISSUE_TYPES, ISSUE_TYPES, ISSUE_TYPE_POOLS } from '@/constants/issue-types'
import { TEMPLATES } from '@/constants/project-templates'
import { PROJECT_COLOR_SWATCHES } from '@/constants/project-types'
import { PROJECT_THEME_KEYS } from '@/constants/project-themes'

// a user (BP Project Template) selection is stored in
// form.template as "user:<name>", same field the built-in gallery already
// keys off, so the rest of the wizard (selection highlight, preview) needs
// no parallel state. isUserTemplate()/userTemplateName() are the only two
// places that need to know the difference.
const USER_PREFIX = 'user:'
export function isUserTemplateId(id) { return typeof id === 'string' && id.startsWith(USER_PREFIX) }
export function userTemplateName(id) { return isUserTemplateId(id) ? id.slice(USER_PREFIX.length) : null }

const DEFAULT_FORM = () => ({
  template: 'blank',
  name: '',
  key: '',
  lead: '',
  leadName: '',
  icon: 'Folder',
  color: PROJECT_COLOR_SWATCHES[0],
  theme: PROJECT_THEME_KEYS[0],
  visibility: 'workspace',
  type: 'internal',
  billing: {
    client: '',
    clientName: '',
    hourlyRate: '',
    budgetHours: '',
    totalBudget: '',
    currency: 'INR',
    retainerHours: '',
    overageRate: '',
    retainerStartMonth: '',
  },
  startDate: new Date().toISOString().slice(0, 10),
  endDate: '',
  description: '',
  workflowStates: [...(WORKFLOW_PRESETS.blank)],
  issueTypes: ['Task'],
  issueTypePool: [...ISSUE_TYPE_POOLS.General],
})

export function useCreateProject({ onSuccess } = {}) {
  const router = useRouter()
  const store = useProjectStore()

  const saving = ref(false)
  const keyAutoMode = ref(true)
  const keyError = ref('')
  const form = ref(DEFAULT_FORM())

  watch(() => form.value.template, (templateId) => {
    // A user template's own shape (workflow_states/issue_types) is applied
    // by the caller (CreateProjectFlow.vue), which has the fetched list —
    // this composable only knows the built-in 11.
    if (isUserTemplateId(templateId)) return
    const tpl = TEMPLATES.find(t => t.id === templateId)
    const category = tpl?.category || 'General'
    form.value.workflowStates = [...(WORKFLOW_PRESETS[templateId] || WORKFLOW_PRESETS.blank)]
    form.value.issueTypePool = [...(ISSUE_TYPE_POOLS[category] || ISSUE_TYPE_POOLS.General)]
    form.value.issueTypes = [...(TEMPLATE_ISSUE_TYPES[templateId] || ['Task'])]
    if (tpl?.defaultProjectType) form.value.type = tpl.defaultProjectType
    else if (templateId === 'blank' || templateId === 'simple' || templateId === 'kanban') form.value.type = 'internal'
  })

  function onNameInput() {
    if (!keyAutoMode.value) return
    const words = form.value.name.trim().split(/\s+/).filter(Boolean)
    if (!words.length) { form.value.key = ''; return }
    if (words.length === 1) {
      form.value.key = words[0].substring(0, 5).toUpperCase().replace(/[^A-Z0-9]/g, '')
    } else {
      form.value.key = words.map(w => w[0]).join('').toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 6)
    }
    keyError.value = ''
  }

  function onKeyFocus() {
    keyAutoMode.value = false
  }

  function onKeyInput() {
    form.value.key = form.value.key.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 6)
    keyError.value = ''
  }

  function onKeyBlur() {
    const k = form.value.key
    if (!k) return
    if (k.length < 2) { keyError.value = 'Key must be at least 2 characters.'; return }
    if (store.projects.some(p => p.key === k)) {
      keyError.value = `Key "${k}" is already in use. Choose another.`
    }
  }

  const billingRequired = computed(() => form.value.type !== 'internal')

  const canCreate = computed(() => {
    if (!form.value.name.trim()) return false
    if (!form.value.key.trim() || form.value.key.length < 2) return false
    if (keyError.value) return false
    if (billingRequired.value && !form.value.billing.client) return false
    if (form.value.type === 'fixed' && !form.value.billing.totalBudget) return false
    return true
  })

  const missingFields = computed(() => {
    const m = []
    if (!form.value.name.trim()) m.push('Project name')
    if (!form.value.key.trim() || form.value.key.length < 2) m.push('Project key (2–6 chars)')
    if (billingRequired.value && !form.value.billing.client) m.push('Client')
    if (form.value.type === 'fixed' && !form.value.billing.totalBudget) m.push('Total budget')
    return m
  })

  async function submit() {
    if (!canCreate.value || saving.value) return
    saving.value = true
    try {
      // a user template's shape (states/types/labels/custom
      // fields/tasks/automations) is expanded entirely server-side; the
      // wizard only supplies what create_project_from_template actually
      // accepts (name/key/start_date/client). Icon/color/lead/description/
      // visibility overrides from this form don't apply on this path — the
      // template's own snapshot wins, same as the built-in gallery's
      // workflow/issue-type fields do today.
      if (isUserTemplateId(form.value.template)) {
        const created = await createProjectFromTemplate({
          template: userTemplateName(form.value.template),
          project_name: form.value.name.trim(),
          key: form.value.key.trim(),
          start_date: form.value.startDate || null,
          client: billingRequired.value ? (form.value.billing.client || null) : null,
          // Billing values the user sees in BillingFields travel with the
          // create — server treats them as overrides of the template's
          // snapshot defaults, so nothing typed here is silently discarded.
          budget_amount: form.value.billing.totalBudget || null,
          hourly_rate: form.value.billing.hourlyRate || null,
          retainer_hours: form.value.billing.retainerHours || null,
          currency: form.value.billing.currency || null,
        })
        await store.fetchProjects()
        toast.success('Project created from template', {
          description: `${created.key} · ${form.value.name.trim()}`,
        })
        router.push(`/workspace/${created.key}/board`)
        onSuccess?.()
        return
      }

      const issueTypeObjs = form.value.issueTypes.map(name => {
        const found = ISSUE_TYPES.find(t => t.name === name)
        return { name, color: found?.color || '#0B6BCB', icon: found?.icon || 'CheckSquare' }
      })
      const payload = {
        project_name:    form.value.name.trim(),
        key:             form.value.key.trim(),
        description:     form.value.description || '',
        project_lead:    form.value.lead || null,
        project_color:   form.value.color,
        project_icon:    form.value.icon,
        theme:           form.value.theme,
        visibility:      form.value.visibility,
        project_type:    form.value.type,
        client:          form.value.billing.client || null,
        budget_amount:   form.value.billing.totalBudget || null,
        hourly_rate:     form.value.billing.hourlyRate || null,
        retainer_hours:  form.value.billing.retainerHours || null,
        currency:        form.value.billing.currency,
        start_date:      form.value.startDate || null,
        target_end_date: form.value.endDate || null,
        workflow_states: JSON.stringify(form.value.workflowStates),
        issue_types:     JSON.stringify(issueTypeObjs),
        custom_fields:   JSON.stringify([]),
        template_used:   form.value.template,
      }
      await createProject(payload)
      await store.fetchProjects()
      toast.success('Project created', {
        description: `${form.value.key} · ${form.value.name.trim()}`,
      })
      router.push(`/workspace/${form.value.key}/board`)
      onSuccess?.()
    } catch (e) {
      console.error(e)
      const msg = String(e.message || e)
      if (msg.toLowerCase().includes('key') || msg.toLowerCase().includes('duplicate')) {
        keyError.value = 'This key is already taken.'
      } else {
        toast.error("Couldn't create project", {
          description: msg,
          action: { label: 'Retry', onClick: submit },
        })
      }
    } finally {
      saving.value = false
    }
  }

  function reset() {
    form.value = DEFAULT_FORM()
    keyAutoMode.value = true
    keyError.value = ''
    saving.value = false
  }

  return {
    form,
    saving,
    keyAutoMode,
    keyError,
    canCreate,
    missingFields,
    billingRequired,
    onNameInput,
    onKeyFocus,
    onKeyInput,
    onKeyBlur,
    submit,
    reset,
  }
}
