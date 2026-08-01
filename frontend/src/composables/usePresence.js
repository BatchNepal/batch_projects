import { ref } from 'vue'
import { getPresence, UpgradeRequiredError } from '@/utils/api'

/**
 * Who's online right now, Messenger-dot style — not a hard session list,
 * just "heartbeated within the last ~45s" (see bp-gateway's
 * internal/realtime Presence handler). Module-level singleton: every
 * importer shares one poller/one Set instead of each mounting its own.
 */
const onlineUsers = ref(new Set())
const POLL_MS = 20000

let pollTimer = null
let refCount = 0

async function refresh() {
  try {
    const res = await getPresence()
    onlineUsers.value = new Set(res?.users || [])
  } catch (e) {
    if (e instanceof UpgradeRequiredError) {
      // Presence is a paid (Team+) gate on the gateway — a 402 here is
      // permanent, not transient, so polling every 20s forever just spams
      // the console for the tab's whole lifetime. Stop; a fresh mount
      // (refCount 0→1, e.g. full page load) gets one more attempt.
      if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
      return
    }
    // Transient failure — keep the last-known set rather than flashing
    // everyone offline.
  }
}

export function usePresence() {
  refCount++
  if (refCount === 1) {
    refresh()
    pollTimer = setInterval(refresh, POLL_MS)
  }

  function stop() {
    refCount = Math.max(0, refCount - 1)
    if (refCount === 0 && pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }

  const isOnline = (email) => !!email && onlineUsers.value.has(email)

  return { onlineUsers, isOnline, refresh, stop }
}
