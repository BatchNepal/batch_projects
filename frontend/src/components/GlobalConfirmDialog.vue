<template>
  <Teleport to="body">
    <Transition name="gcd-fade">
      <div v-if="dialogState.open" class="fixed inset-0 z-modal" style="background:var(--backdrop)" @click="onBackdrop" />
    </Transition>
    <Transition name="gcd-zoom">
      <div v-if="dialogState.open" class="fixed inset-0 z-modal flex items-center justify-center p-4 pointer-events-none">
        <div
          ref="dialogEl"
          role="alertdialog" aria-modal="true"
          :aria-labelledby="dialogState.title ? 'gcd-title' : undefined"
          aria-describedby="gcd-message"
          class="relative pointer-events-auto bg-overlay shadow-overlay rounded-[12px] w-full max-w-sm p-5 flex flex-col gap-4 outline-none"
          @click.stop
        >
          <div class="flex flex-col gap-1">
            <h2 v-if="dialogState.title" id="gcd-title" class="text-[14px] font-semibold text-foreground">{{ dialogState.title }}</h2>
            <p id="gcd-message" class="text-[13px] text-muted leading-relaxed whitespace-pre-line">{{ dialogState.message }}</p>
          </div>

          <Input
            v-if="dialogState.kind === 'prompt'"
            ref="inputEl"
            v-model="dialogState.inputValue"
            :label="dialogState.inputLabel"
            :placeholder="dialogState.placeholder"
            size="sm"
            @keydown.enter="onConfirm"
          />

          <div class="flex items-center justify-end gap-2">
            <Button v-if="dialogState.kind !== 'alert'" variant="bordered" color="default" size="sm" @click="onCancel">
              {{ dialogState.cancelLabel }}
            </Button>
            <Button :color="dialogState.danger ? 'danger' : 'primary'" size="sm" @click="onConfirm">
              {{ dialogState.confirmLabel }}
            </Button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
// Single global instance, mounted once in App.vue — see useConfirmDialog.js
// for why this replaces window.confirm/prompt/alert app-wide.
import { ref, watch, nextTick, onBeforeUnmount } from 'vue'
import { Button, Input } from '@/ui'
import { dialogState, resolveDialog } from '@/composables/useConfirmDialog'

const inputEl = ref(null)

function onConfirm() {
  resolveDialog(dialogState.kind === 'prompt' ? dialogState.inputValue : true)
}
function onCancel() {
  resolveDialog(dialogState.kind === 'prompt' ? null : false)
}
// Backdrop click on an alert() replacement dismisses it (nothing to
// cancel); on confirm/prompt it's the same as Cancel, not Confirm — a
// stray click outside must never silently confirm a destructive action.
function onBackdrop() {
  dialogState.kind === 'alert' ? resolveDialog(undefined) : onCancel()
}

function onKey(e) {
  if (e.key !== 'Escape' || !dialogState.open) return
  onCancel()
}
watch(() => dialogState.open, (v) => {
  document.body.style.overflow = v ? 'hidden' : ''
  if (v) {
    document.addEventListener('keydown', onKey)
    // Prompt gets the text field focused+selected (matches native prompt());
    // confirm/alert focus the confirm button so Enter/Space acts on it
    // without requiring a Tab first.
    nextTick(() => {
      if (dialogState.kind === 'prompt') inputEl.value?.$el?.querySelector('input')?.select()
    })
  } else {
    document.removeEventListener('keydown', onKey)
  }
})
onBeforeUnmount(() => { document.body.style.overflow = ''; document.removeEventListener('keydown', onKey) })
</script>

<style scoped>
.gcd-fade-enter-active { transition: opacity var(--duration-base) var(--ease-out); }
.gcd-fade-leave-active { transition: opacity var(--duration-fast) var(--ease-in); }
.gcd-fade-enter-from, .gcd-fade-leave-to { opacity: 0; }
.gcd-zoom-enter-active { transition: opacity var(--duration-modal) var(--ease-out), transform var(--duration-modal) var(--ease-smooth); }
.gcd-zoom-leave-active { transition: opacity var(--duration-base) var(--ease-in), transform var(--duration-base) var(--ease-in); }
.gcd-zoom-enter-from   { opacity: 0; transform: scale(0.95); }
.gcd-zoom-leave-to     { opacity: 0; transform: scale(0.95); }
</style>
