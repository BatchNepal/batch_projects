<template>
  <button v-if="timerStore.active" class="gti-pill" :disabled="busy" @click="onOpen">
    <span class="gti-dot" />
    <span class="gti-key">{{ timerStore.active.task_key }}</span>
    <span class="gti-elapsed">{{ elapsedLabel }}</span>
    <span class="gti-stop" @click.stop="onStop">
      <Square class="size-2.5" />
    </span>
  </button>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { toast } from 'vue-sonner'
import { Square } from 'lucide-vue-next'
import { useTimerStore } from '@/stores/timer'
import { useProjectStore } from '@/stores/project'

const timerStore = useTimerStore()
const store = useProjectStore()
const busy = ref(false)
const now = ref(Date.now())
let tick = null

onMounted(() => {
  if (!timerStore.loaded) timerStore.refresh()
  tick = setInterval(() => { now.value = Date.now() }, 1000)
})
onUnmounted(() => { if (tick) clearInterval(tick) })

const elapsedLabel = computed(() => {
  if (!timerStore.active) return ''
  const started = new Date(timerStore.active.started_at).getTime()
  const secs = Math.max(0, Math.floor((now.value - started) / 1000))
  const h = Math.floor(secs / 3600)
  const m = Math.floor((secs % 3600) / 60)
  const s = secs % 60
  const mm = String(m).padStart(2, '0')
  const ss = String(s).padStart(2, '0')
  return h > 0 ? `${h}:${mm}:${ss}` : `${m}:${ss}`
})

function onOpen() {
  if (timerStore.active) store.openTaskDetail(timerStore.active.task)
}

async function onStop() {
  if (busy.value) return
  busy.value = true
  try {
    const res = await timerStore.stop()
    toast.success(res.logged ? `Logged ${res.elapsed_hours}h to today's timesheet` : 'Timer stopped')
  } catch (e) {
    toast.error(e.message || 'Failed to stop timer')
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.gti-pill {
  display: inline-flex; align-items: center; gap: 7px;
  height: 28px; padding: 0 10px 0 8px;
  border-radius: 999px; border: 1px solid var(--border);
  background: var(--surface-secondary); cursor: pointer;
  transition: background 0.15s;
}
.gti-pill:hover:not(:disabled) { background: var(--surface-tertiary, var(--border)); }
.gti-pill:disabled { opacity: 0.7; cursor: default; }
.gti-dot {
  width: 7px; height: 7px; border-radius: 50%; background: var(--danger);
  animation: gti-pulse 1.6s ease-in-out infinite;
  flex-shrink: 0;
}
.gti-key { font-size:var(--text-sm); font-weight: 600; color: var(--foreground); }
.gti-elapsed { font-size:var(--text-sm); font-weight: 600; color: var(--muted); font-variant-numeric: tabular-nums; }
.gti-stop {
  display: inline-flex; align-items: center; justify-content: center;
  width: 18px; height: 18px; border-radius: 50%;
  background: var(--danger); color: var(--accent-foreground); margin-left: 2px; flex-shrink: 0;
}
@keyframes gti-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.35; }
}
</style>
