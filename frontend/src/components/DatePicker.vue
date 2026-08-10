<template>
  <Popover :open="open" padding="" @update:open="open = $event">
    <template #trigger="{ open: popoverOpen }">
      <slot name="trigger" :open="popoverOpen" :display="displayDate">
        <button
          style="-webkit-tap-highlight-color: transparent; outline: none !important;"
          :class="[
            'hui-field group flex w-full h-9 items-center justify-between px-3 select-none cursor-pointer',
            popoverOpen && 'is-active',
            modelValue ? 'text-foreground font-medium' : 'text-[var(--field-placeholder)]'
          ]"
        >
          <div class="flex flex-1 items-center text-base">
            <span class="tracking-tight">{{ displayDate || placeholder }}</span>
          </div>
          <div class="flex items-center gap-1.5 shrink-0 ml-auto pointer-events-none">
            <div v-if="modelValue" @click.stop.prevent="clearDate" style="-webkit-tap-highlight-color: transparent; outline: none !important;" class="pointer-events-auto p-0.5 rounded-md text-[var(--field-placeholder)] bg-transparent hover:text-danger hover:bg-danger-soft transition-colors opacity-0 group-hover:opacity-100" title="Clear">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5">
                <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
              </svg>
            </div>
            <span class="flex items-center justify-center text-[var(--field-placeholder)] group-hover:text-foreground transition-colors">
              <svg aria-hidden="true" aria-label="Calendar icon" fill="none" height="1em" role="presentation" viewBox="0 0 13 14" width="1em" xmlns="http://www.w3.org/2000/svg" class="text-xl"><path clip-rule="evenodd" d="M3.75 4.5A.75.75 0 0 1 3 3.75v-.748a1.5 1.5 0 0 0-1.5 1.5v1h10v-1a1.5 1.5 0 0 0-1.5-1.5v.75a.75.75 0 1 1-1.5 0v-.75h-4v.747a.75.75 0 0 1-.75.75ZM8.5 1.501h-4V.75a.75.75 0 0 0-1.5 0v.752a3 3 0 0 0-3 3v6a3 3 0 0 0 3 3h7a3 3 0 0 0 3-3v-6a3 3 0 0 0-3-3v-.75a.75.75 0 0 0-1.5 0v.75Zm-7 5.5v3.5a1.5 1.5 0 0 0 1.5 1.5h7a1.5 1.5 0 0 0 1.5-1.5v-3.5h-10Z" fill="currentColor" fill-rule="evenodd"></path></svg>
            </span>
          </div>
        </button>
      </slot>
    </template>

    <div
      class="w-[264px] h-[285px] p-3 bg-overlay border border-border shadow-lg rounded-lg overflow-hidden flex flex-col"
      style="font-family: 'Inter', sans-serif;"
    >
      <!-- Header -->
      <header class="flex items-center justify-between px-1 pb-3 shrink-0">
        <button @click="showYearPicker = !showYearPicker" style="-webkit-tap-highlight-color: transparent; outline: none !important;" class="flex items-center gap-1.5 bg-transparent hover:bg-surface-secondary rounded-lg px-2 py-1 -ml-1 transition-colors focus-visible:ring-2 focus-visible:ring-accent select-none">
          <span class="text-base font-semibold text-[var(--foreground)]">{{ monthName }} {{ currentYear }}</span>
          <span class="inline-flex w-[14px] h-[14px] items-center justify-center text-[var(--accent)] transition-transform duration-200" :class="{ 'rotate-90': showYearPicker }">
            <svg aria-hidden="true" fill="none" height="1em" role="presentation" viewBox="0 0 16 16" width="1em" xmlns="http://www.w3.org/2000/svg"><path clip-rule="evenodd" d="M5.47 2.97a.75.75 0 0 1 1.06 0l4.5 4.5a.75.75 0 0 1 0 1.06l-4.5 4.5a.75.75 0 1 1-1.06-1.06L9.44 8 5.47 4.03a.75.75 0 0 1 0-1.06Z" fill="currentColor" fill-rule="evenodd"></path></svg>
          </span>
        </button>
        
        <div class="flex items-center gap-1" :class="{ 'pointer-events-none opacity-0': showYearPicker }">
          <button @click="prevMonth" style="-webkit-tap-highlight-color: transparent; outline: none !important;" class="flex w-7 h-7 items-center justify-center bg-transparent rounded-full text-[var(--accent)] hover:bg-surface-secondary hover:text-[var(--accent)] transition-all focus-visible:ring-2 focus-visible:ring-accent active:scale-95 duration-150 transform-gpu cursor-pointer select-none">
            <svg aria-hidden="true" fill="none" height="16" viewBox="0 0 16 16" width="16" xmlns="http://www.w3.org/2000/svg" class="w-4 h-4"><path clip-rule="evenodd" d="M10.53 2.97a.75.75 0 0 1 0 1.06L6.56 8l3.97 3.97a.75.75 0 1 1-1.06 1.06l-4.5-4.5a.75.75 0 0 1 0-1.06l4.5-4.5a.75.75 0 0 1 1.06 0" fill="currentColor" fill-rule="evenodd"></path></svg>
          </button>
          <button @click="nextMonth" style="-webkit-tap-highlight-color: transparent; outline: none !important;" class="flex w-7 h-7 items-center justify-center bg-transparent rounded-full text-[var(--accent)] hover:bg-surface-secondary hover:text-[var(--accent)] transition-all focus-visible:ring-2 focus-visible:ring-accent active:scale-95 duration-150 transform-gpu cursor-pointer select-none">
            <svg aria-hidden="true" fill="none" height="16" viewBox="0 0 16 16" width="16" xmlns="http://www.w3.org/2000/svg" class="w-4 h-4"><path clip-rule="evenodd" d="M5.47 2.97a.75.75 0 0 1 1.06 0l4.5 4.5a.75.75 0 0 1 0 1.06l-4.5 4.5a.75.75 0 1 1-1.06-1.06L9.44 8 5.47 4.03a.75.75 0 0 1 0-1.06Z" fill="currentColor" fill-rule="evenodd"></path></svg>
          </button>
        </div>
      </header>

      <!-- Grid (Calendar) -->
      <table v-if="!showYearPicker" class="w-full h-full table-fixed border-collapse" cellpadding="0">
        <thead>
          <tr>
            <th v-for="d in ['M','T','W','T','F','S','S']" :key="d" class="h-7 align-middle text-center text-xs font-medium text-[var(--muted)] uppercase select-none cursor-default">
              {{ d }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(week, wIndex) in calendarWeeks" :key="wIndex">
            <td v-for="dayObj in week" :key="dayObj.date" class="h-8 p-0 text-center align-middle">
              <button 
                @click="selectDate(dayObj)"
                style="-webkit-tap-highlight-color: transparent; outline: none !important;"
                :class="[
                  'relative flex w-[30px] h-[30px] mx-auto items-center justify-center rounded-full text-center text-base font-medium transition-all duration-150 cursor-pointer transform-gpu p-0 border-none select-none',
                  'focus-visible:z-10 focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1',
                  dayObj.selected 
                    ? (dayObj.isOutsideMonth ? 'bg-surface-secondary text-[var(--accent)]' : 'bg-[var(--accent)] text-white shadow-sm shadow-accent/20')
                    : dayObj.isOutsideMonth 
                      ? 'text-muted opacity-50 bg-transparent hover:bg-surface-secondary' 
                      : dayObj.isToday
                        ? 'text-[var(--accent)] bg-transparent hover:bg-surface-secondary font-semibold'
                        : 'text-[var(--foreground)] bg-transparent hover:bg-surface-secondary hover:text-[var(--foreground)]',
                  !dayObj.selected ? 'active:scale-95 active:bg-surface-hover' : 'active:scale-95'
                ]"
              >
                {{ dayObj.dayNum }}
                <span v-if="dayObj.isToday" class="absolute bottom-1 left-1/2 w-[3px] h-[3px] -translate-x-1/2 rounded-[min(32px,1.25rem)]" :class="dayObj.selected ? (dayObj.isOutsideMonth ? 'bg-[var(--accent)]' : 'bg-overlay') : 'bg-[var(--accent)]'"></span>
              </button>
            </td>
          </tr>
        </tbody>
      </table>

      <!-- Year Picker -->
      <div v-else class="grid grid-cols-4 gap-1 flex-1 overflow-y-auto pr-1" style="scrollbar-width: none;">
        <button 
          v-for="y in Array.from({length: 200}, (_, i) => 1900 + i)" :key="y"
          @click="selectYear(y)"
          :ref="el => { if (y === viewYear) activeYearRef = el }"
          style="-webkit-tap-highlight-color: transparent; outline: none !important;"
          :class="[
            'flex h-8 w-full items-center justify-center rounded-full text-base font-medium transition-colors cursor-pointer focus-visible:ring-2 focus-visible:ring-accent select-none',
            y === viewYear 
              ? 'bg-[var(--accent)] text-white shadow-sm shadow-accent/20' 
              : 'text-[var(--foreground)] bg-transparent hover:bg-surface-secondary hover:text-[var(--foreground)]',
            !isNaN(y) && y !== viewYear ? 'active:scale-95 active:bg-surface-hover' : ''
          ]"
        >
          {{ y }}
        </button>
      </div>

    </div>
  </Popover>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import Popover from '@/ui/Popover.vue'

const props = defineProps({
  modelValue: { type: String, default: null }, // YYYY-MM-DD
  placeholder: { type: String, default: 'Select date' },
})

// "23 May" (adds year only when it differs from the current one)
const displayDate = computed(() => {
  if (!props.modelValue) return ''
  const [y, mo, d] = props.modelValue.split('-').map(Number)
  const dt = new Date(y, mo - 1, d)
  const base = dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  return y === new Date().getFullYear() ? base : `${base}, ${y}`
})
const emit = defineEmits(['update:modelValue'])

const open = ref(false)
const showYearPicker = ref(false)
const activeYearRef = ref(null)

const today = new Date()
const getInitDate = () => props.modelValue ? new Date(props.modelValue) : new Date()

const viewMonth = ref(getInitDate().getMonth())
const viewYear = ref(getInitDate().getFullYear())

const MONTHS = ['January','February','March','April','May','June','July','August','September','October','November','December']

const monthName = computed(() => MONTHS[viewMonth.value])
const currentYear = computed(() => viewYear.value)

watch(open, (isOpen) => {
  if (isOpen) {
    showYearPicker.value = false
    const d = getInitDate()
    viewMonth.value = d.getMonth()
    viewYear.value = d.getFullYear()
  }
})

watch(showYearPicker, async (val) => {
  if (val) {
    await nextTick()
    if (activeYearRef.value) {
      activeYearRef.value.scrollIntoView({ block: 'center', behavior: 'auto' })
    }
  }
})

const calendarWeeks = computed(() => {
  const weeks = []
  const firstOfMonth = new Date(viewYear.value, viewMonth.value, 1)
  
  let startDay = firstOfMonth.getDay() 
  let leadingDays = startDay === 0 ? 6 : startDay - 1
  
  let currentDate = new Date(firstOfMonth)
  currentDate.setDate(currentDate.getDate() - leadingDays)
  
  for (let w = 0; w < 6; w++) {
    const week = []
    for (let d = 0; d < 7; d++) {
      const isOutsideMonth = currentDate.getMonth() !== viewMonth.value
      
      const y = currentDate.getFullYear()
      const m = currentDate.getMonth() + 1
      const date = currentDate.getDate()
      const dateStr = `${y}-${String(m).padStart(2, '0')}-${String(date).padStart(2, '0')}`
      
      const isToday = y === today.getFullYear() && (currentDate.getMonth()) === today.getMonth() && date === today.getDate()
      const isSelected = props.modelValue === dateStr
      
      week.push({
        date: dateStr,
        dayNum: date,
        isOutsideMonth,
        isToday,
        selected: isSelected,
      })
      currentDate.setDate(currentDate.getDate() + 1)
    }
    weeks.push(week)
  }
  
  if (weeks[5].every(d => d.isOutsideMonth)) {
    weeks.pop()
  }
  
  return weeks
})

function prevMonth() {
  if (viewMonth.value === 0) { viewMonth.value = 11; viewYear.value-- }
  else viewMonth.value--
}

function nextMonth() {
  if (viewMonth.value === 11) { viewMonth.value = 0; viewYear.value++ }
  else viewMonth.value++
}

function selectDate(dayObj) {
  emit('update:modelValue', dayObj.date)
  open.value = false
}

function clearDate() {
  emit('update:modelValue', null)
  open.value = false
}

function selectYear(y) {
  viewYear.value = y
  showYearPicker.value = false
}

function formatDisplay(val) {
  if (!val) return ''
  const [y, m, d] = val.split('-').map(Number)
  return new Date(y, m - 1, d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: y !== today.getFullYear() ? 'numeric' : undefined })
}
</script>
