import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useProjectStore } from '@/stores/project'
import { toast } from 'vue-sonner'
import { createProject, inviteMember, updateWorkspaceSettings } from '@/utils/api'
import { WORKFLOW_PRESETS } from '@/constants/workflow-presets'
import { ISSUE_TYPES } from '@/constants/issue-types'
import { TEMPLATES } from '@/constants/project-templates'

const TOTAL_STEPS = 4

const DEFAULT_FORM = () => ({
  // timezone/currency/weeklyHours were collected here and
  // never read anywhere (BP Workspace Settings has no matching fields);
  // removed rather than inventing new persisted schema. `name` stays: it's
  // the step's own canProceed gate.
  workspace: {
    name: '',
  },
  invites: [],
  defaults: {
    template: 'kanban',
    issueTypes: ['Task', 'Bug', 'Story'],
  },
  firstProject: {
    name: '',
    key: '',
    type: 'internal',
    billing: {
      client: '', clientName: '', hourlyRate: '', budgetHours: '',
      totalBudget: '', currency: 'INR', retainerHours: '',
      overageRate: '', retainerStartMonth: '',
    },
  },
})

export function useOrgOnboarding({ onComplete } = {}) {
  const router = useRouter()
  const store = useProjectStore()
  const step = ref(1)
  const form = ref(DEFAULT_FORM())
  const saving = ref(false)

  // Step 3's template pick used to only drive the LOCAL
  // workflow-state preview; project_type came from Step 4's disconnected
  // default ('internal'), so a "Client delivery" pick silently produced an
  // internal, non-billable project. Same sync pattern useCreateProject.js's
  // own template watcher already uses for the main create-project flow.
  const billingRequired = computed(() => form.value.firstProject.type !== 'internal')

  watch(() => form.value.defaults.template, (templateId) => {
    const tpl = TEMPLATES.find(t => t.id === templateId)
    form.value.firstProject.type = tpl?.defaultProjectType || 'internal'
  })

  const canProceed = computed(() => {
    if (step.value === 1) return !!form.value.workspace.name.trim()
    if (step.value === 2) return true
    if (step.value === 3) return true
    if (step.value === 4) {
      if (!form.value.firstProject.name.trim() || !form.value.firstProject.key.trim()) return false
      if (billingRequired.value && !form.value.firstProject.billing.client) return false
      return true
    }
    return true
  })

  function next() {
    if (!canProceed.value || step.value >= TOTAL_STEPS) return
    step.value++
  }

  function back() {
    if (step.value > 1) step.value--
  }

  async function submit() {
    if (!canProceed.value || saving.value) return
    saving.value = true
    try {
      // The workspace name collected in step 1
      // (and gating that step's canProceed) must actually be sent here —
      // silently discarding a value the user was required to enter is the
      // same class of bug as the invites/timezone fields above. Best-effort:
      // brand_name is a Team-plan+ field (require_feature("custom_branding")
      // in update_workspace_settings), and onboarding runs before any paid
      // plan exists on a fresh install — a starter-tier BPUpgradeRequired
      // here must not break the primary "create my workspace" flow.
      const workspaceName = form.value.workspace.name.trim()
      if (workspaceName) {
        try {
          await updateWorkspaceSettings({ brand_name: workspaceName })
        } catch {
          // Starter tier (the common case) or a permission edge case —
          // silently skip; the workspace still gets created either way.
        }
      }

      const { name, key, type, billing } = form.value.firstProject
      const template = form.value.defaults.template || 'kanban'
      const workflowStates = WORKFLOW_PRESETS[template] || WORKFLOW_PRESETS.kanban
      const issueTypeObjs = form.value.defaults.issueTypes.map(typeName => {
        const found = ISSUE_TYPES.find(t => t.name === typeName)
        return { name: typeName, color: found?.color || '#0B6BCB', icon: found?.icon || 'CheckSquare' }
      })

      const created = await createProject({
        project_name:    name.trim(),
        key:             key.trim(),
        project_type:    type || 'internal',
        client:          billingRequired.value ? (billing.client || null) : null,
        budget_amount:   billing.totalBudget || null,
        hourly_rate:     billing.hourlyRate || null,
        retainer_hours:  billing.retainerHours || null,
        currency:        billing.currency || null,
        workflow_states: JSON.stringify(workflowStates),
        issue_types:     JSON.stringify(issueTypeObjs),
        custom_fields:   JSON.stringify([]),
      })

      // invites collected in step 2 were built into the form
      // but never sent; a new user could add teammates all the way through
      // setup and not one invite would go out. Best-effort per invite so a
      // single bad address doesn't sink the ones that would have worked.
      const invites = form.value.invites
      if (invites.length) {
        const results = await Promise.allSettled(
          invites.map(inv => inviteMember(created.name, inv.email, inv.role))
        )
        const failed = results.filter(r => r.status === 'rejected').length
        if (failed) {
          toast.warning(`${failed} of ${invites.length} invites failed to send`, {
            description: 'You can retry from Settings → Members.',
          })
        }
      }

      await store.fetchProjects()
      toast.success('Workspace ready', { description: `${key.trim()} · ${name.trim()}` })
      router.push(`/workspace/${key.trim()}/board`)
      onComplete?.()
    } catch (e) {
      toast.error('Setup failed', { description: String(e.message || e) })
    } finally {
      saving.value = false
    }
  }

  function skip() {
    onComplete?.()
  }

  return {
    step,
    totalSteps: TOTAL_STEPS,
    form,
    saving,
    canProceed,
    billingRequired,
    next,
    back,
    submit,
    skip,
  }
}
