<!--
  MentionInput.vue — comment box with inline @mention chips.
  - v-model is the stored string using @[Display Name](user_id) tokens
    (the format batch_projects' backend parses for notifications).
  - contenteditable so mentions render as blue chips while composing/editing.
  - Robust Range-based @ detection (works regardless of caret anchor type).
  - Suggestion menu is Teleported to <body> so no ancestor overflow clips it.
-->
<template>
  <div class="mi-wrap">
    <div
      ref="editable"
      class="mi-input"
      contenteditable="true"
      role="textbox"
      :data-placeholder="placeholder"
      @input="onInput"
      @keydown="onKeydown"
      @focus="$emit('focus')"
      @blur="onBlur"
    />
    <Teleport to="body">
      <div v-if="open && items.length" class="mi-menu" :style="menuStyle">
        <button
          v-for="(m, i) in items"
          :key="m.user"
          type="button"
          class="mi-opt"
          :class="{ active: i === idx }"
          @mousedown.prevent="select(m)"
        >
          <span class="mi-av">{{ initials(m.full_name || m.user) }}</span>
          <span class="mi-name">{{ m.full_name || m.user }}</span>
          <span class="mi-sub">{{ (m.user || '').split('@')[0] }}</span>
        </button>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, nextTick } from 'vue'

const props = defineProps({
  modelValue:  { type: String, default: '' },
  members:     { type: Array,  default: () => [] },
  placeholder: { type: String, default: 'Add a comment… (@ to mention)' },
})
const emit = defineEmits(['update:modelValue', 'submit', 'focus', 'blur'])

const editable  = ref(null)
const open      = ref(false)
const query     = ref('')
const idx       = ref(0)
const menuStyle = ref({})

function initials(name) {
  return (name || '?').split(/[\s@.]+/).filter(Boolean).slice(0, 2).map(w => w[0]).join('').toUpperCase()
}

const items = ref([])
function refreshItems() {
  const q = query.value.toLowerCase()
  items.value = (props.members || [])
    .filter(m => !q || (m.full_name || m.user || '').toLowerCase().includes(q))
    .slice(0, 6)
  if (idx.value >= items.value.length) idx.value = 0
}

function updateMenuPos() {
  const el = editable.value
  if (!el) return
  const r = el.getBoundingClientRect()
  menuStyle.value = {
    position: 'fixed',
    left: `${Math.round(r.left)}px`,
    bottom: `${Math.round(window.innerHeight - r.top + 6)}px`,
    zIndex: 9999,
  }
}

// ── token serialize / deserialize ──────────────────────────────────────────
function makeChip(name, uid) {
  const span = document.createElement('span')
  span.className = 'mi-chip'
  span.contentEditable = 'false'
  span.dataset.name = name
  span.dataset.uid = uid
  span.textContent = '@' + name
  return span
}

function serialize() {
  const root = editable.value
  if (!root) return ''
  let out = ''
  root.childNodes.forEach(node => {
    if (node.nodeType === Node.TEXT_NODE) out += node.textContent
    else if (node.nodeName === 'BR') out += '\n'
    else if (node.classList?.contains('mi-chip')) out += `@[${node.dataset.name}](${node.dataset.uid})`
    else out += node.textContent || ''
  })
  return out.replace(/ /g, ' ')
}

const TOKEN = /@\[([^\]]+)\]\(([^)]+)\)/g
function render(value) {
  const root = editable.value
  if (!root) return
  root.innerHTML = ''
  const str = value || ''
  let last = 0, m
  TOKEN.lastIndex = 0
  while ((m = TOKEN.exec(str)) !== null) {
    if (m.index > last) root.appendChild(document.createTextNode(str.slice(last, m.index)))
    root.appendChild(makeChip(m[1], m[2]))
    last = TOKEN.lastIndex
  }
  if (last < str.length) root.appendChild(document.createTextNode(str.slice(last)))
}

watch(() => props.modelValue, (val) => { if (val !== serialize()) render(val) })
onMounted(() => render(props.modelValue))

function emitValue() { emit('update:modelValue', serialize()) }

// ── @ detection (Range-based: robust to caret anchor being element or text) ──
function textBeforeCaret() {
  const sel = window.getSelection()
  if (!sel || !sel.rangeCount) return null
  const range = sel.getRangeAt(0)
  if (!range.collapsed) return null
  if (!editable.value.contains(range.endContainer)) return null
  const pre = range.cloneRange()
  pre.selectNodeContents(editable.value)
  pre.setEnd(range.endContainer, range.endOffset)
  return pre.toString()
}

function detect() {
  const before = textBeforeCaret()
  if (before == null) { open.value = false; return }
  const m = before.match(/(?:^|\s)@([\w.\-]*)$/)
  if (m) {
    query.value = m[1]
    refreshItems()
    if (items.value.length) { updateMenuPos(); open.value = true; idx.value = 0 }
    else open.value = false
  } else {
    open.value = false
  }
}

function onInput() {
  emitValue()
  detect()
}

function onKeydown(e) {
  if (open.value && items.value.length) {
    if (e.key === 'ArrowDown') { e.preventDefault(); idx.value = (idx.value + 1) % items.value.length; return }
    if (e.key === 'ArrowUp')   { e.preventDefault(); idx.value = (idx.value - 1 + items.value.length) % items.value.length; return }
    if (e.key === 'Enter' || e.key === 'Tab') { e.preventDefault(); select(items.value[idx.value]); return }
    if (e.key === 'Escape')    { e.preventDefault(); open.value = false; return }
  }
  if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); emit('submit') }
}

function select(member) {
  if (!member) { open.value = false; return }
  const sel = window.getSelection()
  if (!sel || !sel.rangeCount) { open.value = false; return }
  const range = sel.getRangeAt(0)
  const node = range.endContainer
  const off = range.endOffset
  const back = query.value.length + 1  // "@" + typed query

  if (node.nodeType === Node.TEXT_NODE && off >= back) {
    const del = document.createRange()
    del.setStart(node, off - back)
    del.setEnd(node, off)
    del.deleteContents()
    const chip = makeChip(member.full_name || member.user, member.user)
    const space = document.createTextNode(' ')
    del.insertNode(space)
    del.insertNode(chip)
    const after = document.createRange()
    after.setStartAfter(space)
    after.collapse(true)
    sel.removeAllRanges()
    sel.addRange(after)
  } else {
    // Fallback: append chip at the end
    const chip = makeChip(member.full_name || member.user, member.user)
    editable.value.appendChild(chip)
    editable.value.appendChild(document.createTextNode(' '))
  }
  open.value = false
  emitValue()
}

function onBlur() {
  setTimeout(() => { open.value = false }, 150)
  emit('blur')
}

function focus() { nextTick(() => editable.value?.focus()) }
function clear() { if (editable.value) { editable.value.innerHTML = ''; emitValue() } }
defineExpose({ focus, clear })
</script>

<style scoped>
.mi-wrap { position: relative; width: 100%; }
.mi-input {
  min-height: 56px; width: 100%; padding: 8px 10px;
  font-size: 13px; line-height: 1.7; color: var(--foreground); outline: none;
  white-space: pre-wrap; word-break: break-word; cursor: text;
}
.mi-input:empty::before { content: attr(data-placeholder); color: var(--muted); }
:deep(.mi-chip) {
  color: var(--accent); background: var(--accent-soft); border-radius: 4px;
  padding: 1px 5px; font-weight: 500; white-space: nowrap;
}
.mi-menu {
  min-width: 230px; max-height: 240px; overflow-y: auto;
  background: var(--overlay); border: 1px solid var(--border);
  border-radius: 8px; box-shadow: 0 8px 24px rgba(0,0,0,0.18); padding: 4px;
}
.mi-opt {
  display: flex; align-items: center; gap: 8px; width: 100%;
  padding: 6px 8px; border: none; background: none; cursor: pointer;
  border-radius: 6px; font-size: 13px; color: var(--foreground); text-align: left;
}
.mi-opt:hover, .mi-opt.active { background: var(--surface-secondary); }
.mi-av {
  display: inline-flex; align-items: center; justify-content: center;
  width: 22px; height: 22px; border-radius: 50%; background: var(--accent);
  color: var(--accent-foreground); font-size: 10px; font-weight: 600; flex-shrink: 0;
}
.mi-name { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.mi-sub { margin-left: auto; font-size: 11px; color: var(--muted); flex-shrink: 0; }
</style>
