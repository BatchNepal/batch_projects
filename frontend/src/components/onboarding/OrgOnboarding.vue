<template>
  <div class="bp-overlay fixed inset-0 z-modal bg-background flex flex-col overflow-hidden">

    <!-- Top bar -->
    <div class="flex items-center justify-between px-8 py-4 border-b border-border bg-overlay shrink-0">
      <div class="flex items-center gap-2">
        <div class="w-7 h-7 rounded-md overflow-hidden flex items-center justify-center shrink-0">
          <img :src="'/assets/batch_projects/images/bp-logo-new.svg'" class="w-full h-full object-cover" alt="" />
        </div>
        <span class="text-sm font-semibold text-foreground">BatchProjects</span>
      </div>

      <!-- Step indicators. Bare dots told you there were four steps but never
           what they were, and this is the same wizard shape CreateProjectFlow
           already renders with numbered, labelled, back-navigable steps —
           two different progress idioms for the same job. Matched to that one.
           Labels collapse on narrow screens, numbers always remain. -->
      <nav class="flex items-center gap-2" aria-label="Setup progress">
        <template v-for="i in totalSteps" :key="i">
          <button
            type="button"
            class="ob-step flex items-center gap-1.5"
            :disabled="i >= step"
            :aria-current="i === step ? 'step' : undefined"
            :aria-label="`Step ${i}: ${stepLabels[i - 1]}`"
            @click="i < step && goTo(i)"
          >
            <span
              class="ob-step-num w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold shrink-0"
              :class="i === step ? 'bg-accent text-accent-foreground'
                    : i < step ? 'bg-accent-soft text-accent-soft-foreground'
                    : 'bg-default text-muted'"
            >
              <Check v-if="i < step" :size="11" :stroke-width="3" />
              <template v-else>{{ i }}</template>
            </span>
            <span
              class="text-sm font-medium hidden sm:inline"
              :class="i === step ? 'text-foreground' : 'text-muted'"
            >{{ stepLabels[i - 1] }}</span>
          </button>
          <span
            v-if="i < totalSteps"
            class="w-4 h-px shrink-0"
            :class="i < step ? 'bg-accent-soft-hover' : 'bg-border'"
          />
        </template>
      </nav>

      <Button variant="light" color="default" size="sm" @click="skip">
        Skip setup for now
      </Button>
    </div>

    <!-- Step content.
         The inner min-h-full flex centres each step optically. Without it the
         content was pinned to the top of a full-height scroll area, so step 1
         — a heading and a single input — sat above roughly 800px of empty
         white on a 1000px viewport. That's the first screen a new customer
         ever sees. Taller steps (3 and 4) exceed the container and simply
         scroll as before; `items-center` only takes effect while the content
         is shorter than the viewport. -->
    <div class="flex-1 overflow-y-auto">
      <!-- No items-center: children must stay full-width so each step's own
           `max-w-xl mx-auto` keeps doing the horizontal centring. -->
      <div class="min-h-full flex flex-col justify-center">
      <Transition name="step" mode="out-in">
        <OnboardingStep1Identity
          v-if="step === 1"
          key="step1"
          v-model="form.workspace"
        />
        <OnboardingStep2Invite
          v-else-if="step === 2"
          key="step2"
          v-model="form.invites"
        />
        <OnboardingStep3Defaults
          v-else-if="step === 3"
          key="step3"
          v-model="form.defaults"
        />
        <OnboardingStep4FirstProject
          v-else-if="step === 4"
          key="step4"
          v-model="form.firstProject"
          :template="form.defaults.template"
        />
      </Transition>
      </div>
    </div>

    <!-- Bottom nav -->
    <div class="shrink-0 bg-overlay border-t border-border px-8 py-4 flex items-center justify-between">
      <Button v-if="step > 1" variant="bordered" color="default" size="sm" @click="back">
        <template #startContent><ArrowLeft class="size-3.5" /></template>
        Back
      </Button>
      <div v-else />

      <div class="flex items-center gap-3">
        <Button
          v-if="step < totalSteps"
          variant="light" color="default" size="sm"
          @click="next"
        >
          Skip this step
        </Button>

        <Button
          v-if="step < totalSteps"
          color="primary" size="sm"
          :isDisabled="!canProceed"
          @click="next"
        >
          Next
          <template #endContent><ArrowRight class="size-3.5" /></template>
        </Button>

        <Button
          v-if="step === totalSteps"
          color="primary" size="sm"
          :isDisabled="!canProceed"
          :isLoading="saving"
          @click="submit"
        >
          {{ saving ? 'Setting up…' : 'Create project →' }}
        </Button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ArrowLeft, ArrowRight, Check } from 'lucide-vue-next'
import { Button } from '@/ui'
import OnboardingStep1Identity from './OnboardingStep1Identity.vue'
import OnboardingStep2Invite from './OnboardingStep2Invite.vue'
import OnboardingStep3Defaults from './OnboardingStep3Defaults.vue'
import OnboardingStep4FirstProject from './OnboardingStep4FirstProject.vue'
import { useOrgOnboarding } from '@/composables/useOrgOnboarding'

const emit = defineEmits(['close'])

const { step, totalSteps, form, saving, canProceed, next, back, submit, skip } = useOrgOnboarding({
  onComplete: () => emit('close'),
})

// Mirrors the step components' own headings, in order.
const stepLabels = ['Workspace', 'Team', 'Defaults', 'First project']

// Backward only — jumping forward would skip validation that `next()` runs.
function goTo(i) {
  if (i < step.value) step.value = i
}
</script>

<style scoped>
/* 0.1s was fast enough to read as a flicker rather than a transition;
   CreateProjectFlow's equivalent runs at 180ms. Matched. */
.step-enter-active, .step-leave-active {
  transition: opacity 180ms var(--ease-out), transform 180ms var(--ease-out);
}
.step-enter-from { opacity: 0; transform: translateX(16px); }
.step-leave-to   { opacity: 0; transform: translateX(-16px); }

/* Completed steps are clickable (go back); the current and future ones
   aren't. Only paint transitions — the old dots used `transition-all`, which
   animated the width change too. */
.ob-step:disabled { cursor: default; }
.ob-step:not(:disabled) { cursor: pointer; }
.ob-step-num {
  transition: background-color 180ms var(--ease-out), color 180ms var(--ease-out);
}
@media (hover: hover) {
  .ob-step:not(:disabled):hover .ob-step-num { background: var(--accent-soft-hover); }
}

@media (prefers-reduced-motion: reduce) {
  .step-enter-active, .step-leave-active, .ob-step-num { transition: none; }
}
</style>
