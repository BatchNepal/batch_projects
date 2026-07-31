<template>
  <div class="thp" ref="rootEl">
    <button type="button" class="thp-tile" :class="{ open }" title="Project avatar" @click="open = !open">
      <ProjectAvatar :theme="theme" size="lg" />
    </button>

    <Transition name="thp-pop">
      <div v-if="open" class="thp-panel">
        <p class="thp-label">Choose an avatar</p>
        <div class="thp-grid">
          <button
            v-for="key in PROJECT_THEME_KEYS" :key="key"
            type="button"
            class="thp-item" :class="{ on: theme === key }"
            :title="PROJECT_THEMES[key].label"
            @click="pick(key)"
          >
            <img :src="PROJECT_THEMES[key].icon" :alt="PROJECT_THEMES[key].label" class="w-full h-full object-cover rounded-[6px]" />
          </button>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { ProjectAvatar } from '@/ui'
import { PROJECT_THEMES, PROJECT_THEME_KEYS } from '@/constants/project-themes'

defineProps({
  theme: { type: String, default: '' },
})
const emit = defineEmits(['update:theme'])

const open = ref(false)
const rootEl = ref(null)

function pick(key) {
  emit('update:theme', key)
  open.value = false
}

function onDocClick(e) {
  if (open.value && rootEl.value && !rootEl.value.contains(e.target)) open.value = false
}
onMounted(() => document.addEventListener('mousedown', onDocClick))
onUnmounted(() => document.removeEventListener('mousedown', onDocClick))
</script>

<style scoped>
.thp { position: relative; display: inline-block; }

.thp-tile {
  border-radius: 10px; cursor: pointer; display: block; overflow: hidden;
  transition: transform 250ms var(--ease-smooth), box-shadow 150ms var(--ease-out);
}
.thp-tile:hover { transform: translateY(-1px); }
.thp-tile:active { transform: scale(0.96); transition: transform 40ms ease-out; }
.thp-tile.open { box-shadow: 0 0 0 2px var(--focus); }

.thp-panel {
  position: absolute; top: calc(100% + 8px); left: 0; z-index: 50; width: 220px;
  background: var(--overlay); border-radius: 8px;
  box-shadow: var(--overlay-shadow);
  padding: 12px;
}
.thp-label { font-size: 12px; font-weight: 500; color: var(--muted); margin: 0 0 8px; }

.thp-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 6px; }
.thp-item {
  aspect-ratio: 1; border-radius: 8px; padding: 2px; cursor: pointer;
  border: 1.5px solid transparent; transition: border-color 0.1s, transform 0.1s;
}
.thp-item:hover { transform: scale(1.05); }
.thp-item.on { border-color: var(--accent); }

.thp-pop-enter-active, .thp-pop-leave-active { transition: opacity .14s ease, transform .14s ease; transform-origin: top left; }
.thp-pop-enter-from, .thp-pop-leave-to { opacity: 0; transform: scale(.97) translateY(-3px); }
</style>
