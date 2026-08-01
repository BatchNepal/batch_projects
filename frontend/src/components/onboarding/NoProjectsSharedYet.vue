<template>
  <div class="fixed inset-0 z-[400] bg-background flex flex-col overflow-hidden bp-overlay">
    <!-- Top bar — same shell as OrgOnboarding, no step indicators (one screen only) -->
    <div class="flex items-center justify-between px-8 py-4 border-b border-border bg-overlay shrink-0">
      <div class="flex items-center gap-2">
        <div class="w-7 h-7 rounded-md overflow-hidden flex items-center justify-center shrink-0">
          <img :src="'/assets/batch_projects/images/bp-logo-new.svg'" class="w-full h-full object-cover" alt="" />
        </div>
        <span class="text-sm font-semibold text-foreground">BatchProjects</span>
      </div>
      <Button variant="light" color="default" size="sm" @click="$emit('close')">
        Continue to workspace
      </Button>
    </div>

    <div class="flex-1 flex items-center justify-center">
      <div class="flex flex-col items-center text-center max-w-[360px] px-6">
        <MailboxIcon class="text-muted mb-4 shrink-0" style="width:32px;height:32px;stroke-width:1.5" />
        <p class="text-sm font-semibold text-foreground">You're in — nothing shared with you yet</p>
        <p class="text-xs text-muted mt-1.5 leading-relaxed">
          Your workspace already has projects, but none have been shared with your account.
          Ask a project admin to add you as a member, or check back after they do.
        </p>
        <div class="flex items-center gap-2 mt-5">
          <Button variant="bordered" color="default" size="sm" :isLoading="refreshing" @click="refresh">
            Check again
          </Button>
          <Button color="primary" size="sm" @click="$emit('close')">
            Continue to workspace
          </Button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { Mailbox as MailboxIcon } from 'lucide-vue-next'
import { Button } from '@/ui'
import { useProjectStore } from '@/stores/project'

const emit = defineEmits(['close'])
const store = useProjectStore()
const refreshing = ref(false)

async function refresh() {
  refreshing.value = true
  try {
    await store.fetchProjects()
    if (store.projects.length > 0) emit('close')
  } finally {
    refreshing.value = false
  }
}
</script>
