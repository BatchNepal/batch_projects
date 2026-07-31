import { ref } from 'vue'
import { MONEY_DRAWER_DOCTYPES } from '@/constants/erp-doctypes'

// the ONE reference→doc opener. Doctypes the Money drawer can
// summarize open in-app; everything else falls back to the raw /app link.
// Shared by TaskDetail, TaskCard, Backlog, MyTasks, Gantt so the
// MONEY_DRAWER_DOCTYPES check exists in exactly one place.
export function useErpDocOpener() {
  const moneyDrawerOpen    = ref(false)
  const moneyDrawerDoctype = ref('')
  const moneyDrawerName    = ref('')

  function openErpDoc(doctype, name) {
    if (MONEY_DRAWER_DOCTYPES.has(doctype)) {
      moneyDrawerDoctype.value = doctype
      moneyDrawerName.value = name
      moneyDrawerOpen.value = true
    } else {
      window.open(`/app/${doctype.toLowerCase().replace(/ /g, '-')}/${encodeURIComponent(name)}`, '_blank', 'noopener')
    }
  }

  return { moneyDrawerOpen, moneyDrawerDoctype, moneyDrawerName, openErpDoc }
}
