// useConfirmDialog — promise-based replacement for window.confirm/prompt/alert.
//
// The app had 25+ call sites across 18 files using the browser's native
// confirm()/prompt()/alert() — the top-middle OS-chrome popup that can't be
// styled, doesn't match the app's theme (including dark mode), and blocks the
// entire JS thread while open. One singleton state object (below) + one
// <GlobalConfirmDialog/> mounted once in App.vue replaces all of them with a
// themed AlertDialog, while keeping each call site's shape nearly identical:
//   if (!confirm('Delete this?')) return         ->  if (!await confirmDialog('Delete this?')) return
//   const name = prompt('Name', current)         ->  const name = await promptDialog({ message: 'Name', defaultValue: current })
//   alert(e.message)                              ->  alertDialog(e.message)
import { reactive } from 'vue'

export const dialogState = reactive({
  open: false,
  kind: 'confirm', // 'confirm' | 'prompt' | 'alert'
  title: '',
  message: '',
  confirmLabel: 'Confirm',
  cancelLabel: 'Cancel',
  danger: false,
  inputValue: '',
  inputLabel: '',
  placeholder: '',
  _resolve: null,
})

function open(kind, opts) {
  // A second dialog requested while one is open would silently orphan the
  // first caller's promise (it would never resolve) — resolve it as
  // cancelled/null first so nothing hangs forever.
  if (dialogState.open && dialogState._resolve) {
    dialogState._resolve(kind === 'prompt' ? null : false)
  }
  return new Promise((resolve) => {
    Object.assign(dialogState, {
      open: true,
      kind,
      title: opts.title || '',
      message: opts.message || '',
      confirmLabel: opts.confirmLabel || (kind === 'alert' ? 'OK' : 'Confirm'),
      cancelLabel: opts.cancelLabel || 'Cancel',
      danger: !!opts.danger,
      inputValue: opts.defaultValue || '',
      inputLabel: opts.inputLabel || '',
      placeholder: opts.placeholder || '',
      _resolve: resolve,
    })
  })
}

/** Replaces `confirm(message)`. Resolves true/false. */
export function confirmDialog(message, opts = {}) {
  return open('confirm', { message, ...opts })
}

/** Replaces `window.prompt(message, defaultValue)`. Resolves the entered
 * string, or null if cancelled (same contract as native prompt). */
export function promptDialog(opts = {}) {
  return open('prompt', opts)
}

/** Replaces `alert(message)`. Resolves once dismissed — awaitable for
 * callers that want to sequence after it, but firing-and-forgetting is fine
 * too (matches alert()'s original "just show it" usage). */
export function alertDialog(message, opts = {}) {
  return open('alert', { message, ...opts })
}

export function resolveDialog(value) {
  const resolve = dialogState._resolve
  dialogState.open = false
  dialogState._resolve = null
  resolve?.(value)
}
