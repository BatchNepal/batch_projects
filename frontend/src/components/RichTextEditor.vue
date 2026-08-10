<template>
  <div class="rte-wrap" :class="{ 'rte-focused': isFocused, 'rte-editing': isEditing }">
    <!-- Toolbar — only shown when editing or always if alwaysToolbar prop -->
    <div v-if="editor && (isEditing || alwaysToolbar)" class="rte-toolbar">
      <!-- Text style group -->
      <div class="rte-group">
        <TB @click="editor.chain().focus().toggleBold().run()" :on="editor.isActive('bold')" title="Bold"><b>B</b></TB>
        <TB @click="editor.chain().focus().toggleItalic().run()" :on="editor.isActive('italic')" title="Italic"><i>I</i></TB>
        <TB @click="editor.chain().focus().toggleStrike().run()" :on="editor.isActive('strike')" title="Strikethrough"><s>S</s></TB>
        <TB @click="editor.chain().focus().toggleCode().run()" :on="editor.isActive('code')" title="Inline code">
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M10 20l4-16M7 7l-4 4 4 4M17 7l4 4-4 4"/></svg>
        </TB>
      </div>
      <div class="rte-sep"/>
      <!-- Heading group -->
      <div class="rte-group">
        <TB @click="editor.chain().focus().toggleHeading({level:1}).run()" :on="editor.isActive('heading',{level:1})" title="Heading 1">H₁</TB>
        <TB @click="editor.chain().focus().toggleHeading({level:2}).run()" :on="editor.isActive('heading',{level:2})" title="Heading 2">H₂</TB>
        <TB @click="editor.chain().focus().toggleHeading({level:3}).run()" :on="editor.isActive('heading',{level:3})" title="Heading 3">H₃</TB>
      </div>
      <div class="rte-sep"/>
      <!-- List group -->
      <div class="rte-group">
        <TB @click="editor.chain().focus().toggleBulletList().run()" :on="editor.isActive('bulletList')" title="Bullet list">
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/></svg>
        </TB>
        <TB @click="editor.chain().focus().toggleOrderedList().run()" :on="editor.isActive('orderedList')" title="Numbered list">
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M10 6h11M10 12h11M10 18h11M4 6h.01M4 12h.01M4 18h.01"/></svg>
        </TB>
        <TB @click="editor.chain().focus().toggleTaskList().run()" :on="editor.isActive('taskList')" title="Task list">
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><rect x="3" y="5" width="4" height="4" rx="0.5"/><path d="M11 7h10"/><rect x="3" y="13" width="4" height="4" rx="0.5"/><path d="M11 15h10"/></svg>
        </TB>
        <TB @click="editor.chain().focus().toggleBlockquote().run()" :on="editor.isActive('blockquote')" title="Blockquote">
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"/></svg>
        </TB>
        <TB @click="editor.chain().focus().toggleCodeBlock().run()" :on="editor.isActive('codeBlock')" title="Code block">
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"/></svg>
        </TB>
      </div>
      <div class="rte-sep"/>
      <!-- History -->
      <div class="rte-group">
        <TB @click="editor.chain().focus().undo().run()" :disabled="!editor.can().undo()" title="Undo">
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M3 10h10a8 8 0 018 8v2M3 10l6 6M3 10l6-6"/></svg>
        </TB>
        <TB @click="editor.chain().focus().redo().run()" :disabled="!editor.can().redo()" title="Redo">
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M21 10H11a8 8 0 00-8 8v2M21 10l-6 6M21 10l-6-6"/></svg>
        </TB>
      </div>
    </div>

    <!-- Content area -->
    <div class="rte-body" @click="editor?.commands.focus()">
      <EditorContent :editor="editor" class="rte-content"/>
    </div>

    <!-- Save/Cancel — shown when editing and showSaveBar is true -->
    <div v-if="isEditing && showSaveBar" class="rte-footer">
      <button @click="handleSave" class="rte-btn-save">Save</button>
      <button @click="handleCancel" class="rte-btn-cancel">Cancel</button>
    </div>
  </div>
</template>

<script setup>
import { useEditor, EditorContent } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import Placeholder from '@tiptap/extension-placeholder'
import TaskList from '@tiptap/extension-task-list'
import TaskItem from '@tiptap/extension-task-item'
import { ref, watch, h, defineComponent, onBeforeUnmount } from 'vue'

const props = defineProps({
  modelValue:    { type: String, default: '' },
  placeholder:   { type: String, default: 'Add a description...' },
  minHeight:     { type: String, default: '100px' },
  alwaysToolbar: { type: Boolean, default: false },
  showSaveBar:   { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'save', 'cancel'])

const isFocused = ref(false)
const isEditing = ref(props.alwaysToolbar)
let savedContent = props.modelValue

// Toolbar button
const TB = defineComponent({
  props: { on: Boolean, disabled: Boolean, title: String },
  setup(p, { slots }) {
    return () => h('button', {
      type: 'button',
      title: p.title,
      disabled: p.disabled,
      class: ['rte-tb', p.on ? 'rte-tb-on' : '', p.disabled ? 'rte-tb-disabled' : ''].join(' '),
    }, slots.default?.())
  }
})

const editor = useEditor({
  content: props.modelValue,
  extensions: [
    StarterKit,
    Placeholder.configure({ placeholder: props.placeholder }),
    TaskList.configure({ HTMLAttributes: { class: 'rte-tasklist' } }),
    TaskItem.configure({ nested: true }),
  ],
  editorProps: {
    attributes: {
      class: 'rte-inner focus:outline-none',
      style: `min-height:${props.minHeight}`,
    },
  },
  onFocus() {
    isFocused.value = true
    isEditing.value = true
    savedContent = editor.value?.getHTML() || ''
  },
  onBlur() {
    isFocused.value = false
  },
  onUpdate({ editor: e }) {
    emit('update:modelValue', e.getHTML())
  },
})

watch(() => props.modelValue, (val) => {
  if (editor.value && editor.value.getHTML() !== val) {
    editor.value.commands.setContent(val || '', false)
  }
})

function handleSave() {
  emit('save', editor.value?.getHTML())
  isEditing.value = false
}

function handleCancel() {
  editor.value?.commands.setContent(savedContent || '', false)
  emit('cancel')
  emit('update:modelValue', savedContent)
  isEditing.value = false
}

onBeforeUnmount(() => editor.value?.destroy())
</script>

<style>
/* ── Wrapper ── */
.rte-wrap {
  border: 1.5px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  transition: border-color 0.15s, box-shadow 0.15s;
  overflow: hidden;
}
.rte-wrap:hover {
  border-color: var(--muted);
}
.rte-wrap.rte-focused {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(11, 107, 203, 0.12);
}

/* ── Toolbar ── */
.rte-toolbar {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 5px 8px;
  border-bottom: 1px solid var(--surface-secondary);
  background: var(--surface-secondary);
  flex-wrap: wrap;
}
.rte-group { display: flex; align-items: center; gap: 1px; }
.rte-sep { width: 1px; height: 18px; background: var(--surface-secondary); margin: 0 3px; }

.rte-tb {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 26px;
  height: 26px;
  padding: 0 4px;
  border-radius: 4px;
  border: none;
  background: transparent;
  color: var(--muted);
  font-size:var(--text-sm);
  font-weight: 600;
  cursor: pointer;
  transition: all 0.1s;
  line-height: 1;
}
.rte-tb:hover { background: var(--surface-secondary); color: var(--foreground); }
.rte-tb.rte-tb-on { background: var(--accent-soft); color: var(--accent); }
.rte-tb.rte-tb-disabled { opacity: 0.35; cursor: not-allowed; pointer-events: none; }

/* ── Content body ── */
.rte-body {
  padding: 10px 14px;
  cursor: text;
}
.rte-inner {
  font-size:var(--text-base);
  color: var(--foreground);
  line-height: 1.65;
}

/* Placeholder */
.rte-inner p.is-editor-empty:first-child::before {
  content: attr(data-placeholder);
  color: var(--muted);
  pointer-events: none;
  float: left;
  height: 0;
}

/* Typography */
.rte-inner p { margin: 0 0 6px; }
.rte-inner p:last-child { margin-bottom: 0; }
.rte-inner strong { font-weight: 700; color: var(--foreground); }
.rte-inner em { font-style: italic; color: var(--foreground); }
.rte-inner s { text-decoration: line-through; color: var(--muted); }

.rte-inner h1 { font-size:var(--text-metric); font-weight: 700; color: var(--foreground); margin: 10px 0 6px; line-height: 1.3; }
.rte-inner h2 { font-size:var(--text-md); font-weight: 700; color: var(--foreground); margin: 8px 0 4px; }
.rte-inner h3 { font-size:var(--text-base); font-weight: 700; color: var(--foreground); margin: 6px 0 3px; }

.rte-inner ul { list-style: disc; padding-left: 20px; margin: 4px 0; }
.rte-inner ol { list-style: decimal; padding-left: 20px; margin: 4px 0; }
.rte-inner li { margin: 2px 0; }

.rte-inner blockquote {
  border-left: 3px solid var(--border);
  padding: 4px 12px;
  color: var(--muted);
  margin: 6px 0;
  background: var(--surface-secondary);
  border-radius: 0 4px 4px 0;
}

.rte-inner pre {
  background: var(--surface-secondary);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 10px 14px;
  font-size:var(--text-sm);
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  margin: 6px 0;
  overflow-x: auto;
  color: var(--foreground);
}
.rte-inner code {
  background: var(--surface-secondary);
  border: 1px solid var(--surface-secondary);
  border-radius: 3px;
  padding: 1px 5px;
  font-size:var(--text-sm);
  font-family: 'JetBrains Mono', monospace;
  color: var(--danger);
}

/* ── Footer (save/cancel bar) ── */
.rte-footer {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  border-top: 1px solid var(--surface-secondary);
  background: var(--surface-secondary);
}
.rte-btn-save {
  padding: 5px 16px;
  background: var(--accent);
  color: var(--accent-foreground);
  font-size:var(--text-sm);
  font-weight: 600;
  border-radius: 6px;
  border: none;
  cursor: pointer;
  transition: background 0.15s;
}
.rte-btn-save:hover { background: var(--accent-hover); }
.rte-btn-cancel {
  padding: 5px 12px;
  background: transparent;
  color: var(--muted);
  font-size:var(--text-sm);
  font-weight: 500;
  border-radius: 6px;
  border: none;
  cursor: pointer;
  transition: background 0.15s;
}
.rte-btn-cancel:hover { background: var(--surface-secondary); color: var(--foreground); }
</style>