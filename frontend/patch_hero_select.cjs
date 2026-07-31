const fs = require('fs');
let content = fs.readFileSync('/home/frappe/batcherp/apps/batch_projects/frontend/src/components/HeroSelect.vue', 'utf8');

// 1. Update rounded-xl to rounded-md in popover
content = content.replace("transform rounded-xl bg-white", "transform rounded-md bg-white");

// 2. Update rounded-lg to rounded-md in list item
content = content.replace("justify-between rounded-lg px-2", "justify-between rounded-md px-2");

// 3. Add search bar after search slot if searchable
content = content.replace(
    "<slot name=\"search\"></slot>",
    `<slot name="search"></slot>
      <div v-if="searchable && !hasSearchSlot" class="flex items-center gap-2 px-2 py-1.5 border-b border-gray-100 mb-1">
        <svg class="w-3.5 h-3.5 text-gray-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        <input 
          ref="searchInputRef"
          v-model="searchQuery" 
          placeholder="Search..." 
          class="flex-1 text-[12.5px] bg-transparent border-none outline-none text-gray-800 placeholder:text-gray-400" 
          @click.stop 
          @keydown.space.stop
        />
      </div>`
);

// 4. Update props
content = content.replace(
    "emptyText: String",
    "emptyText: String,\n  searchable: { type: Boolean, default: true }"
);

// 5. Update script logic
content = content.replace(
    "const containerRef = ref(null)",
    "const containerRef = ref(null)\nconst searchQuery = ref('')\nconst searchInputRef = ref(null)\nconst hasSearchSlot = computed(() => !!slots.search)"
);

content = content.replace(
    "const listOptions = computed(() => props.options || [])",
    `const listOptions = computed(() => {
  let opts = props.options || []
  if (props.searchable && searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    opts = opts.filter(o => o.label?.toLowerCase().includes(q) || String(o.value).toLowerCase().includes(q))
  }
  return opts
})`
);

content = content.replace(
    "isOpen.value = !isOpen.value",
    `isOpen.value = !isOpen.value\n  if (isOpen.value && props.searchable && !hasSearchSlot.value) {\n    setTimeout(() => { if (searchInputRef.value) searchInputRef.value.focus() }, 50)\n  } else if (!isOpen.value) {\n    searchQuery.value = ''\n  }`
);

content = content.replace(
    "function close() {\n  isOpen.value = false\n}",
    "function close() {\n  isOpen.value = false\n  searchQuery.value = ''\n}"
);

fs.writeFileSync('/home/frappe/batcherp/apps/batch_projects/frontend/src/components/HeroSelect.vue', content);
console.log("Updated HeroSelect.vue");
