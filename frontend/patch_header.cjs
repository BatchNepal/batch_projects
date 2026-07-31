const fs = require('fs');
let content = fs.readFileSync('/home/frappe/batcherp/apps/batch_projects/frontend/src/components/ProjectHeader.vue', 'utf8');

// Replace rounded-[8px] overrides with rounded-md
content = content.replace(/trigger-class="rounded-\[8px\]"/g, 'trigger-class="rounded-md"');

// Modify the Label filter HeroSelect block to use built-in search and use plain store.projectLabels
// Wait, replacing lines might be tricky. Let's find the exact block

let oldLabelSelect = `          <!-- Label filter -->
          <HeroSelect
            v-if="store.projectLabels?.length"
            v-model="store.boardViewState.filterLabel"
            :options="filteredLabels.map(l => ({ value: l.label, label: l.label, color: l.color }))"
            width="max-w-max"
            popoverWidth="w-44 mt-1"
            align="right"
            :is-on="!!store.boardViewState.filterLabel"
            trigger-class="rounded-[8px]"
            trigger-size-class="h-[30px] px-[10px]"
            chevron-size-class="h-[9px] w-[9px] min-w-[9px]"
            clearable
          >
            <template #trigger>
              <div class="flex items-center gap-[5px] text-[12px]">
                <span
                  v-if="store.boardViewState.filterLabel"
                  class="w-2 h-2 rounded-full shrink-0"
                  :style="{ background: store.projectLabels.find(l=>l.label===store.boardViewState.filterLabel)?.color || '#6B7280' }"
                />
                <Tag v-else :size="12" :stroke-width="1.75" class="shrink-0 opacity-50" />
                <span class="truncate max-w-[80px]">
                  {{ store.boardViewState.filterLabel || 'Label' }}
                </span>
              </div>
            </template>
            <template #search>
              <div class="flex items-center gap-2 px-3 py-2 border-b border-gray-100">
                <Search :size="11" :stroke-width="2" class="text-gray-400 shrink-0" />
                <input v-model="labelSearchQ" autofocus placeholder="Search labels…" class="flex-1 text-[12.5px] bg-transparent border-none outline-none text-gray-800 placeholder:text-gray-400" @click.stop />
              </div>
            </template>
            <template #option="{ option }">
              <div class="flex items-center gap-2">
                <span class="ph-dd-dot" :style="{ background: option.color }"/>
                {{ option.label }}
              </div>
            </template>
          </HeroSelect>`;

content = content.replace(oldLabelSelect, `          <!-- Label filter -->
          <HeroSelect
            v-if="store.projectLabels?.length"
            v-model="store.boardViewState.filterLabel"
            :options="store.projectLabels.map(l => ({ value: l.label, label: l.label, color: l.color }))"
            width="max-w-max"
            popoverWidth="w-44 mt-1"
            align="right"
            :is-on="!!store.boardViewState.filterLabel"
            trigger-class="rounded-md"
            trigger-size-class="h-[30px] px-[10px]"
            chevron-size-class="h-[9px] w-[9px] min-w-[9px]"
            clearable
          >
            <template #trigger>
              <div class="flex items-center gap-[5px] text-[12px]">
                <span
                  v-if="store.boardViewState.filterLabel"
                  class="w-2 h-2 rounded-full shrink-0"
                  :style="{ background: store.projectLabels.find(l=>l.label===store.boardViewState.filterLabel)?.color || '#6B7280' }"
                />
                <Tag v-else :size="12" :stroke-width="1.75" class="shrink-0 opacity-50" />
                <span class="truncate max-w-[80px]">
                  {{ store.boardViewState.filterLabel || 'Label' }}
                </span>
              </div>
            </template>
            <template #option="{ option }">
              <div class="flex items-center gap-2">
                <span class="ph-dd-dot" :style="{ background: option.color }"/>
                {{ option.label }}
              </div>
            </template>
          </HeroSelect>`);

// Now remove the labelSearchQ completely
content = content.replace("const labelSearchQ = ref('')", "");
content = content.replace(/const filteredLabels = computed\(\(\) => \{[\s\S]*?\}\)/, "");

fs.writeFileSync('/home/frappe/batcherp/apps/batch_projects/frontend/src/components/ProjectHeader.vue', content);
console.log("Updated ProjectHeader.vue");

