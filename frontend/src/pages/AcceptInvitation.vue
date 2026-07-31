<template>
  <div class="min-h-full flex items-center justify-center bg-background-secondary p-4">
    <div class="w-full max-w-[420px] bg-background rounded-xl border border-separator shadow-overlay p-8">
      <!-- Loading -->
      <div v-if="loading" class="flex flex-col items-center py-8">
        <Spinner />
        <p class="text-[13px] text-muted mt-3">Loading invitation…</p>
      </div>

      <!-- Invalid / resolved -->
      <div v-else-if="error" class="text-center py-4">
        <div class="size-12 rounded-full bg-danger-soft flex items-center justify-center mx-auto mb-4">
          <Icon :icon="AlertTriangle" :size="22" class="text-danger" />
        </div>
        <h1 class="text-[16px] font-semibold text-foreground">Invitation unavailable</h1>
        <p class="text-[13px] text-muted mt-2 leading-relaxed">{{ error }}</p>
        <Button class="mt-6" color="primary" variant="flat" @click="goWorkspace">Go to workspace</Button>
      </div>

      <!-- Active invitation -->
      <div v-else class="text-center py-2">
        <div class="size-12 rounded-full bg-accent-soft flex items-center justify-center mx-auto mb-4">
          <Icon :icon="Mail" :size="22" class="text-accent" />
        </div>
        <h1 class="text-[17px] font-semibold text-foreground tracking-[-0.01em]">
          You're invited to {{ invite.project_title }}
        </h1>
        <p class="text-[13px] text-muted mt-2">
          You'll join as <span class="font-medium text-foreground">{{ invite.role }}</span>.
        </p>

        <!-- accept: logged in, matches -->
        <template v-if="invite.needs === 'accept'">
          <Button class="mt-6 w-full" color="primary" :isLoading="busy" @click="accept">
            Accept invitation
          </Button>
          <p class="text-[11px] text-muted mt-3">Signed in as {{ invite.logged_in_as }}</p>
        </template>

        <!-- signup: brand-new guest sets a password inline -->
        <template v-else-if="invite.needs === 'signup'">
          <div class="mt-6 space-y-3 text-left">
            <Input v-model="fullName" size="md" label="Your name" placeholder="Jane Cooper" />
            <Input v-model="password" size="md" type="password" label="Create a password"
              placeholder="At least 8 characters" @keyup.enter="signup" />
            <p class="text-[11px] text-muted">Joining as {{ invite.email }}</p>
          </div>
          <Button class="mt-5 w-full" color="primary" :isLoading="busy"
            :isDisabled="!canSignup" @click="signup">
            Join {{ invite.project_title }}
          </Button>
        </template>

        <!-- login: existing account, not signed in -->
        <template v-else-if="invite.needs === 'login'">
          <Button class="mt-6 w-full" color="primary" @click="login">
            Log in to accept
          </Button>
          <p class="text-[11px] text-muted mt-3">Invitation for {{ invite.email }}</p>
        </template>

        <!-- mismatch: signed in as the wrong user -->
        <template v-else-if="invite.needs === 'mismatch'">
          <p class="text-[13px] text-muted mt-5 leading-relaxed">
            This invitation was sent to <span class="font-medium text-foreground">{{ invite.email }}</span>,
            but you're signed in as {{ invite.logged_in_as }}.
          </p>
          <Button class="mt-5 w-full" color="primary" variant="flat" @click="login">
            Switch account
          </Button>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getInvitation, acceptInvitation, signupAndAccept } from '@/utils/api.js'
import { Button, Spinner, Icon, Input } from '@/ui'
import { Mail, AlertTriangle } from 'lucide-vue-next'

const route  = useRoute()
const router = useRouter()
const token  = route.params.token

const loading  = ref(true)
const busy     = ref(false)
const error    = ref('')
const invite   = ref({})
const fullName = ref('')
const password = ref('')

const canSignup = computed(() => fullName.value.trim() && password.value.length >= 8)

onMounted(load)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const inv = await getInvitation(token)
    if (inv.status !== 'Pending') {
      error.value = inv.status === 'Accepted'
        ? 'This invitation has already been accepted.'
        : `This invitation is ${inv.status.toLowerCase()}.`
    } else {
      invite.value = inv
    }
  } catch (e) {
    error.value = e.message || 'This invitation link is invalid.'
  } finally {
    loading.value = false
  }
}

function goProject(res) {
  // Bare project URL → ProjectIndex resolves to the project's default view
  // (the store isn't populated yet right after accepting).
  if (res?.project_key) router.replace(`/workspace/${res.project_key}`)
  else router.replace('/workspace')
}

async function accept() {
  busy.value = true
  try {
    goProject(await acceptInvitation(token))
  } catch (e) {
    error.value = e.message || 'Could not accept this invitation.'
  } finally { busy.value = false }
}

async function signup() {
  if (!canSignup.value) return
  busy.value = true
  try {
    goProject(await signupAndAccept(token, password.value, fullName.value.trim()))
  } catch (e) {
    error.value = e.message || 'Could not complete signup.'
  } finally { busy.value = false }
}

function login() {
  const back = encodeURIComponent(`/workspace/invite/${token}`)
  window.location.href = `/login?redirect-to=${back}`
}

function goWorkspace() { router.replace('/workspace') }
</script>
