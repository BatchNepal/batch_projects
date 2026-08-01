<template>
  <div class="fixed inset-0 z-[400] bg-background flex flex-col overflow-hidden">

    <!-- Top bar -->
    <div class="flex items-center justify-between px-8 py-4 border-b border-border bg-overlay shrink-0">
      <div class="flex items-center gap-2">
        <div class="w-7 h-7 rounded-md overflow-hidden flex items-center justify-center shrink-0">
          <img :src="'/assets/batch_projects/images/bp-logo-new.svg'" class="w-full h-full object-cover" alt="" />
        </div>
        <span class="text-sm font-semibold text-foreground">BatchProjects</span>
      </div>

      <!-- Step indicators -->
      <div class="flex items-center gap-1.5">
        <div
          v-for="i in totalSteps"
          :key="i"
          :class="[
            'h-1.5 rounded-full transition-all duration-300',
            i === step ? 'w-6 bg-accent' : i < step ? 'w-4 bg-accent' : 'w-4 bg-default',
          ]"
        />
      </div>

      <Button variant="light" color="default" size="sm" @click="skip">
        Skip setup for now
      </Button>
    </div>

    <!-- Step content -->
    <div class="flex-1 overflow-y-auto">
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
import { ArrowLeft, ArrowRight } from 'lucide-vue-next'
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
</script>

<style scoped>
.step-enter-active, .step-leave-active { transition: opacity 0.1s ease, transform 0.1s ease; }
.step-enter-from { opacity: 0; transform: translateX(16px); }
.step-leave-to   { opacity: 0; transform: translateX(-16px); }
</style>
