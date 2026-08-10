<template>
  <IconButton
    variant="outline" size="sm"
    :color="store.activeViewId ? 'accent' : 'default'"
    :class="{ 'ph-icon-btn-on': open }"
    title="Saved views"
    @click="toggleOpen"
  >
    <ListTodo :size="15" :stroke-width="1.75" />
  </IconButton>

  <Drawer :open="open" @update:open="open = $event" size="sm" placement="right">
    <DrawerHeader class="border-b" @close="open = false">
      <h2 class="text-sm font-semibold">Saved views</h2>
    </DrawerHeader>

    <DrawerBody class="p-2">
      <EmptyState
        v-if="!store.savedViews.length"
        :icon="ListTodo"
        title="No saved views yet"
        description="Save the current filters, grouping, and sort as a reusable view."
      />
      <div
        v-for="v in store.savedViews" :key="v.id"
        class="group flex items-center gap-1 rounded-md hover:bg-default"
      >
        <button
          class="flex-1 flex items-center gap-2 px-2.5 py-2 text-sm text-left min-w-0"
          :class="store.activeViewId === v.id ? 'text-accent font-medium' : 'text-foreground'"
          @click="applyAndClose(v)"
        >
          <Check v-if="store.activeViewId === v.id" :size="13" class="shrink-0" />
          <span v-else class="w-[13px] shrink-0" />
          <span class="truncate">{{ v.name }}</span>
          <span v-if="v.is_default" class="text-micro font-semibold uppercase tracking-wide bg-warning-soft text-warning-soft-foreground px-1 py-0.5 rounded shrink-0">Default</span>
          <Mail v-if="v.subscribed" :size="11" class="text-success shrink-0" :title="`Subscribed (${v.subscription_frequency})`" />
        </button>
        <div class="flex items-center gap-0.5 pr-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
          <IconButton size="xs" variant="ghost" :class="{ 'text-warning': v.is_default }" title="Set as default" @click.stop="toggleDefault(v)">
            <Star :size="13" :fill="v.is_default ? 'currentColor' : 'none'" />
          </IconButton>
          <IconButton size="xs" variant="ghost" :class="{ 'text-success': v.subscribed }" :title="v.subscribed ? 'Unsubscribe email' : 'Subscribe (weekly email)'" @click.stop="toggleSubscribe(v)">
            <Mail :size="13" />
          </IconButton>
          <IconButton size="xs" variant="ghost" title="Rename" @click.stop="renameView(v)">
            <Pencil :size="13" />
          </IconButton>
          <IconButton size="xs" variant="ghost" color="danger" title="Delete" @click.stop="onDeleteView(v)">
            <Trash2 :size="13" />
          </IconButton>
        </div>
      </div>
    </DrawerBody>

    <DrawerFooter class="justify-end">
      <Button size="sm" :variant="hasAnyState ? 'soft' : 'outline'" :color="hasAnyState ? 'accent' : 'default'" @click="showSaveView = true; open = false">
        <template #startContent><Bookmark :size="13" :fill="hasAnyState ? 'currentColor' : 'none'" /></template>
        Save current view{{ hasAnyState ? '' : '…' }}
      </Button>
    </DrawerFooter>
  </Drawer>

  <SaveViewModal
    v-model="showSaveView"
    :view-type="isBoard ? 'board' : 'list'"
    :group-by="store.boardGroupBy"
    :sort-by="store.boardSortBy"
    :sprint-filter="store.boardSprintFilter"
    :filters="store.boardViewState"
    @save="onSaveView"
  />
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import { ListTodo, ChevronDown, Check, Star, Mail, Pencil, Trash2, Bookmark } from 'lucide-vue-next'
import { Button, IconButton, EmptyState, Drawer, DrawerHeader, DrawerBody, DrawerFooter } from '@/ui'
import SaveViewModal from '@/components/SaveViewModal.vue'
import { useProjectStore } from '@/stores/project'
import { toast } from 'vue-sonner'
import { updateView, setViewSubscription } from '@/utils/api'
import { promptDialog } from '@/composables/useConfirmDialog'

const props = defineProps({
  isBoard: { type: Boolean, default: false },
  hasFilters: { type: Boolean, default: false },
})

const route = useRoute()
const store = useProjectStore()
const projectKey = computed(() => route.params.key)

const open        = ref(false)
const showSaveView = ref(false)

const activeViewName = computed(() =>
  store.savedViews.find(v => v.id === store.activeViewId)?.name || 'Views'
)

const hasAnyState = computed(() =>
  props.hasFilters ||
  store.boardGroupBy !== 'status' ||
  store.boardSortBy  !== 'board_order' ||
  store.boardSprintFilter !== 'all'
)

async function toggleOpen() {
  open.value = true
  await store.loadSavedViews(projectKey.value)
}

function applyAndClose(v) {
  store.applyView(v)
  open.value = false
}

async function toggleDefault(v) {
  try {
    await updateView(v.id, { is_default: v.is_default ? 0 : 1 })
    await store.loadSavedViews(projectKey.value)
  } catch (e) { toast.error(e.message || 'Could not update view') }
}

async function toggleSubscribe(v) {
  try {
    const r = await setViewSubscription(v.id, v.subscribed ? 0 : 1, v.subscription_frequency || 'Weekly')
    await store.loadSavedViews(projectKey.value)
    toast.success(r.subscribed ? `Subscribed — ${r.subscription_frequency.toLowerCase()} email` : 'Unsubscribed')
  } catch (e) { toast.error(e.message || 'Could not update subscription') }
}

async function renameView(v) {
  const name = await promptDialog({ title: 'Rename view', inputLabel: 'View name', defaultValue: v.name })
  if (!name || name.trim() === v.name) return
  try {
    await updateView(v.id, { view_name: name.trim() })
    await store.loadSavedViews(projectKey.value)
  } catch (e) { toast.error(e.message || 'Could not rename view') }
}

async function onDeleteView(v) {
  await store.removeView(v.id, projectKey.value)
  toast.success('View deleted')
}

async function onSaveView(name) {
  await store.saveCurrentView(name, projectKey.value, props.isBoard ? 'board' : 'list')
  toast.success('View saved', { description: name })
}
</script>

<style scoped>
.ph-icon-btn-on { background: var(--surface-secondary); color: var(--foreground); }
</style>
