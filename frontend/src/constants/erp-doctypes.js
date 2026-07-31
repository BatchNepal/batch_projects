import {
  ShoppingCart, Receipt, Briefcase, HandCoins, UserSquare2, Truck, FileText, Package,
} from 'lucide-vue-next'

// Doctypes the Money drawer can summarize (must stay within erp_link.py
// _DOC_SPECS) — cells referencing these open the in-app drawer; everything
// else falls back to the raw /app link.
export const MONEY_DRAWER_DOCTYPES = new Set([
  'Sales Invoice', 'Purchase Invoice', 'Sales Order', 'Purchase Order', 'Timesheet', 'Expense Claim',
])

// Doctypes offered for Connect columns (must stay within the backend's
// allowed reference doctypes in api/board.py).
export const ERP_DOCTYPES = [
  { name: 'Sales Order',      icon: ShoppingCart, hint: 'Confirmed customer orders' },
  { name: 'Sales Invoice',    icon: Receipt,      hint: 'Billing & payment status' },
  { name: 'Purchase Order',   icon: Briefcase,    hint: 'Orders to suppliers' },
  { name: 'Purchase Invoice', icon: HandCoins,    hint: 'Supplier bills' },
  { name: 'Customer',         icon: UserSquare2,  hint: 'The client record' },
  { name: 'Supplier',         icon: Truck,        hint: 'Vendor record' },
  { name: 'Quotation',        icon: FileText,     hint: 'Offers sent to customers' },
  { name: 'Stock Entry',      icon: Package,      hint: 'Material movements' },
]
