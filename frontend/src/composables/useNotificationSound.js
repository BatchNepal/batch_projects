// Shared mute flag (Sidebar.vue plays the ping, NotifPrefsModal.vue toggles
// it) plus a Web-Audio-synthesized two-tone chime — no binary asset to bundle,
// no license to track, and it themes trivially (same ping in light/dark).
import { ref } from 'vue'

const STORAGE_KEY = 'bp_notification_sound_muted'
const muted = ref(localStorage.getItem(STORAGE_KEY) === '1')
let audioCtx = null

export function useNotificationSoundMuted() {
  return muted
}

export function setSoundMuted(value) {
  muted.value = !!value
  localStorage.setItem(STORAGE_KEY, muted.value ? '1' : '0')
}

export function playNotificationPing() {
  if (muted.value) return
  try {
    audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)()
    const ctx = audioCtx
    if (ctx.state === 'suspended') ctx.resume()

    const now = ctx.currentTime
    const gain = ctx.createGain()
    gain.gain.setValueAtTime(0, now)
    gain.gain.linearRampToValueAtTime(0.16, now + 0.01)
    gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.35)
    gain.connect(ctx.destination)

    // Two quick ascending notes (Slack/Jira-style ping), not a single beep.
    const notes = [
      { freq: 880,    at: 0 },
      { freq: 1318.5, at: 0.08 },
    ]
    for (const { freq, at } of notes) {
      const osc = ctx.createOscillator()
      osc.type = 'sine'
      osc.frequency.setValueAtTime(freq, now + at)
      osc.connect(gain)
      osc.start(now + at)
      osc.stop(now + 0.35)
    }
  } catch (e) {
    // Web Audio unsupported/blocked by the browser — a silent ping is a fine fallback.
  }
}
