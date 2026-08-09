import { ref } from 'vue'
import { MONEY_DRAWER_DOCTYPES } from '@/constants/erp-doctypes'
import { ensureErpDocAccess } from '@/utils/api'

// the ONE reference→doc opener. Doctypes the Money drawer can
// summarize open in-app; everything else falls back to the raw /app link.
// Shared by TaskDetail, TaskCard, Backlog, MyTasks, Gantt so the
// MONEY_DRAWER_DOCTYPES check exists in exactly one place.
export function useErpDocOpener() {
  const moneyDrawerOpen    = ref(false)
  const moneyDrawerDoctype = ref('')
  const moneyDrawerName    = ref('')

  async function openErpDoc(doctype, name) {
    if (MONEY_DRAWER_DOCTYPES.has(doctype)) {
      moneyDrawerDoctype.value = doctype
      moneyDrawerName.value = name
      moneyDrawerOpen.value = true
      return
    }
    // SPA members hold zero ERPNext DocPerm by design — a raw desk link 403s
    // unless the backend first grants a per-document share (tenancy-checked
    // against this doc's own BP Project references). Open the tab from the
    // click handler first (avoids popup-blocker issues on the async gap),
    // then navigate it once access is confirmed.
    const win = window.open('', '_blank', 'noopener')
    try {
      await ensureErpDocAccess(doctype, name)
      if (win) win.location = `/app/${doctype.toLowerCase().replace(/ /g, '-')}/${encodeURIComponent(name)}`
    } catch (e) {
      if (win) win.close()
      throw e
    }
  }

  return { moneyDrawerOpen, moneyDrawerDoctype, moneyDrawerName, openErpDoc }
}
