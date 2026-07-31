<!--
  LvCells — the single source of truth for List-view data cells.

  Renders the <td> for every visible column for one issue. Used identically by
  top-level rows AND subtask/child rows, in both grouped and ungrouped modes, so
  every cell is editable everywhere (no more read-only child rows). All the
  helpers/state come from the parent ListView via provide('lvCtx', …).
-->
<template>
  <td v-for="col in cols" :key="col.key"
      :class="['lv-td',{'lv-td-fill':col.key==='status'||col.key==='priority','lv-td-center':col.key==='due'||col.key==='timeline'}]"
      @click.stop>
    <template v-if="col.key==='status'">
      <FieldDropdown width="w-44">
        <template #trigger>
          <button class="lv-status-pill" :style="statusStyle(issue.status)">{{ issue.status }}</button>
        </template>
        <DropdownItem v-for="s in store.workflowStates" :key="s.name" :active="issue.status===s.name" @click="save(issue,'status',s.name)">
          <span class="lv-dot" :style="{background:s.color}"/>{{ s.name }}
        </DropdownItem>
      </FieldDropdown>
    </template>
    <template v-else-if="col.key==='priority'">
      <FieldDropdown width="w-36">
        <template #trigger>
          <button class="lv-status-pill" :style="priorityStyle(issue.priority)">{{ issue.priority||'—' }}</button>
        </template>
        <DropdownItem v-for="p in PRIORITIES" :key="p.value" :active="issue.priority===p.value" @click="save(issue,'priority',p.value)">
          <PriorityIcon :priority="p.value"/><span :style="{color:p.color}">{{ p.label }}</span>
        </DropdownItem>
      </FieldDropdown>
    </template>
    <template v-else-if="col.key==='type'">
      <FieldDropdown v-if="store.taskTypes?.length>1" width="w-40">
        <template #trigger>
          <button class="lv-field-btn">
            <span class="lv-type-badge" :style="{background:typeColor(issue.task_type)}">{{ (issue.task_type||'T').charAt(0) }}</span>
            <span>{{ issue.task_type||'—' }}</span>
          </button>
        </template>
        <DropdownItem v-for="t in store.taskTypes" :key="t.name" :active="issue.task_type===t.name" @click="save(issue,'task_type',t.name)">
          <span class="lv-type-badge" :style="{background:t.color}">{{ t.name.charAt(0) }}</span>{{ t.name }}
        </DropdownItem>
      </FieldDropdown>
      <span v-else class="lv-field-plain">
        <span class="lv-type-badge" :style="{background:typeColor(issue.task_type)}">{{ (issue.task_type||'T').charAt(0) }}</span>
        <span>{{ issue.task_type||'—' }}</span>
      </span>
    </template>
    <template v-else-if="col.key==='assignee'">
      <FieldDropdown width="w-52" :close-on-select="false">
        <template #trigger>
          <button class="lv-field-btn">
            <template v-if="issue.assignees?.length">
              <span style="display:inline-flex;align-items:center">
                <span v-for="(a,ai) in issue.assignees.slice(0,3)" :key="a.user"
                  class="lv-av" :style="{background:avatarColor(a.user),marginLeft:ai>0?'-5px':'0'}" :title="a.full_name">
                  {{ initials(a.full_name) }}
                </span>
              </span>
            </template>
            <span v-else class="lv-av-empty" title="Assign"/>
          </button>
        </template>
        <template #search><div class="lv-ddsearch"><input v-model="aQ" autofocus placeholder="Search…" class="lv-ddinput"/></div></template>
        <DropdownItem @click="save(issue,'assignees',[])"><span class="lv-av-empty"/>Unassigned</DropdownItem>
        <div class="lv-ddsep"/>
        <DropdownItem v-for="m in filteredMembers" :key="m.user" :active="hasA(issue,m.user)" @click="togA(issue,m)">
          <span class="lv-av" :style="{background:avatarColor(m.user)}">{{ initials(m.full_name) }}</span>
          <span class="flex-1 truncate">{{ m.full_name }}</span>
        </DropdownItem>
      </FieldDropdown>
    </template>
    <template v-else-if="col.key==='timeline'">
      <FieldDropdown width="w-64" :close-on-select="false">
        <template #trigger>
          <button class="lv-tl-pill" :class="{empty:!issue.start_date&&!issue.due_date}" :style="timelineStyle(issue)">
            {{ timelineLabel(issue) }}
          </button>
        </template>
        <div class="lv-tl-pop" @click.stop>
          <div class="lv-tl-row"><span class="lv-tl-lbl">Start</span><DatePicker :modelValue="issue.start_date||null" placeholder="None" @update:modelValue="v=>save(issue,'start_date',v||null)"/></div>
          <div class="lv-tl-row"><span class="lv-tl-lbl">Due</span><DatePicker :modelValue="issue.due_date||null" placeholder="None" @update:modelValue="v=>save(issue,'due_date',v||null)"/></div>
        </div>
      </FieldDropdown>
    </template>
    <template v-else-if="col.key==='due'">
      <div class="lv-date-td" :class="{overdue:isOverdue(issue),today:isDueToday(issue),soon:isDueSoon(issue)}">
        <DatePicker :modelValue="issue.due_date||null" placeholder="—" @update:modelValue="v=>save(issue,'due_date',v||null)"/>
      </div>
    </template>
    <template v-else-if="col.key==='blocked'">
      <BlockedCell :issue="issue"/>
    </template>
    <template v-else-if="col.key==='connected'">
      <ConnectCell :issue="issue"/>
    </template>
    <template v-else-if="col.key.startsWith('erp:')">
      <ConnectCell :issue="issue" :doctype="col.label" :two-way="erpTwoWay(col.label)"/>
    </template>
    <template v-else-if="col.key.startsWith('mirror:')">
      <template v-if="mirrorDisplay(issue, col).length">
        <span v-for="(v,vi) in mirrorDisplay(issue, col).slice(0,2)" :key="vi"
          class="lv-mirror-val" :class="{'lv-mirror-status': col.mirror && mirrorFieldMeta(col.mirror.doctype,col.mirror.field)?.fieldtype==='Status'}">
          {{ v.text }}
        </span>
        <span v-if="mirrorDisplay(issue, col).length>2" class="lv-lbl-more">+{{ mirrorDisplay(issue, col).length-2 }}</span>
      </template>
      <span v-else class="lv-unset">—</span>
    </template>
    <template v-else-if="col.key.startsWith('cf:')">
      <template v-if="col.cf.type==='select'">
        <FieldDropdown width="w-44">
          <template #trigger>
            <button class="lv-field-btn">
              <span v-if="cfValue(issue,col.cf)">{{ cfOptionLabel(col.cf, cfValue(issue,col.cf)) }}</span>
              <span v-else class="lv-unset">—</span>
            </button>
          </template>
          <DropdownItem :active="!cfValue(issue,col.cf)" @click="saveCf(issue,col.cf,null)">—</DropdownItem>
          <DropdownItem v-for="o in col.cf.options||[]" :key="o.id" :active="cfValue(issue,col.cf)===o.id" @click="saveCf(issue,col.cf,o.id)">{{ o.label }}</DropdownItem>
        </FieldDropdown>
      </template>
      <template v-else-if="col.cf.type==='multiselect'">
        <FieldDropdown width="w-48" :close-on-select="false">
          <template #trigger>
            <button class="lv-field-btn">
              <template v-if="cfMulti(issue,col.cf).length">
                <span v-for="id in cfMulti(issue,col.cf).slice(0,2)" :key="id" class="lv-cf-tag">{{ cfOptionLabel(col.cf,id) }}</span>
                <span v-if="cfMulti(issue,col.cf).length>2" class="lv-lbl-more">+{{ cfMulti(issue,col.cf).length-2 }}</span>
              </template>
              <span v-else class="lv-unset">—</span>
            </button>
          </template>
          <DropdownItem v-for="o in col.cf.options||[]" :key="o.id" :active="cfMulti(issue,col.cf).includes(o.id)" @click="cfMultiToggle(issue,col.cf,o.id)">{{ o.label }}</DropdownItem>
        </FieldDropdown>
      </template>
      <template v-else-if="col.cf.type==='date'">
        <div class="lv-date-td">
          <DatePicker :modelValue="cfValue(issue,col.cf)||null" placeholder="—" @update:modelValue="v=>saveCf(issue,col.cf,v||null)"/>
        </div>
      </template>
      <template v-else-if="col.cf.type==='number'">
        <input class="lv-pts-input" style="width:84px;text-align:left" type="number" :value="cfValue(issue,col.cf)??''" placeholder="—"
          @change="e=>saveCf(issue,col.cf,e.target.value===''?null:Number(e.target.value))" @click.stop/>
      </template>
      <template v-else>
        <input class="lv-cf-input" :value="cfValue(issue,col.cf)||''" placeholder="—"
          @change="e=>saveCf(issue,col.cf,e.target.value||null)" @click.stop/>
      </template>
    </template>
    <template v-else-if="col.key==='sprint'">
      <FieldDropdown width="w-48">
        <template #trigger>
          <button class="lv-field-btn">
            <span v-if="issue.sprint" class="lv-sprint-chip">{{ sprintName(issue.sprint) }}</span>
            <span v-else class="lv-unset">—</span>
          </button>
        </template>
        <DropdownItem :active="!issue.sprint" @click="save(issue,'sprint',null)">No sprint</DropdownItem>
        <DropdownItem v-for="s in (store.sprints||[])" :key="s.name" :active="issue.sprint===s.name" @click="save(issue,'sprint',s.name)">{{ s.sprint_name }}</DropdownItem>
        <p v-if="!(store.sprints||[]).length" class="lv-dd-empty">No sprints</p>
      </FieldDropdown>
    </template>
    <template v-else-if="col.key==='epic'">
      <FieldDropdown width="w-52">
        <template #trigger>
          <button class="lv-field-btn">
            <span v-if="issue.epic" class="lv-epic-chip">{{ epicName(issue.epic) }}</span>
            <span v-else class="lv-unset">—</span>
          </button>
        </template>
        <DropdownItem :active="!issue.epic" @click="save(issue,'epic',null)">No epic</DropdownItem>
        <DropdownItem v-for="e in epicOptions" :key="e.name" :active="issue.epic===e.name" @click="save(issue,'epic',e.name)">{{ e.title }}</DropdownItem>
        <p v-if="!epicOptions.length" class="lv-dd-empty">No epics</p>
      </FieldDropdown>
    </template>
    <template v-else-if="col.key==='points'">
      <input class="lv-pts-input" type="number" min="0"
        :value="issue.story_points||''" placeholder="—"
        @change="e=>save(issue,'story_points',e.target.value===''?null:Number(e.target.value))"
        @click.stop/>
    </template>
    <template v-else-if="col.key==='labels'">
      <FieldDropdown width="w-52" :close-on-select="false">
        <template #trigger>
          <button class="lv-field-btn">
            <span v-if="issueLabels(issue).length" class="lv-label-row">
              <span v-for="lbl in issueLabels(issue).slice(0,2)" :key="lbl" class="lv-lbl-chip" :style="labelStyle(lbl)">{{ lbl }}</span>
              <span v-if="issueLabels(issue).length>2" class="lv-lbl-more">+{{ issueLabels(issue).length-2 }}</span>
            </span>
            <span v-else class="lv-unset">—</span>
          </button>
        </template>
        <DropdownItem v-for="l in (store.projectLabels||[])" :key="l.label" :active="issueLabels(issue).includes(l.label)" @click="togLabel(issue,l.label)">
          <span class="lv-dot" :style="{background:l.color}"/>{{ l.label }}
        </DropdownItem>
        <p v-if="!(store.projectLabels||[]).length" class="lv-dd-empty">No labels defined</p>
      </FieldDropdown>
    </template>
  </td>
</template>

<script setup>
import { inject } from 'vue'
import FieldDropdown from '@/components/FieldDropdown.vue'
import DropdownItem  from '@/components/DropdownItem.vue'
import PriorityIcon  from '@/components/PriorityIcon.vue'
import DatePicker    from '@/components/DatePicker.vue'
import ConnectCell   from '@/components/list/ConnectCell.vue'
import BlockedCell   from '@/components/list/BlockedCell.vue'

defineProps({
  issue: { type: Object, required: true },
  cols:  { type: Array,  required: true },
})

// Everything below comes from ListView via provide('lvCtx', …). Returning refs
// from setup lets the template auto-unwrap them.
const ctx = inject('lvCtx')
const {
  store, PRIORITIES, aQ, filteredMembers, epicOptions,
  save, saveCf, cfMultiToggle, togA, togLabel, hasA,
  statusStyle, priorityStyle, typeColor, timelineStyle, timelineLabel, labelStyle,
  avatarColor, initials, sprintName, epicName,
  cfValue, cfMulti, cfOptionLabel, issueLabels,
  mirrorDisplay, mirrorFieldMeta, erpTwoWay, isOverdue, isDueToday, isDueSoon,
} = ctx
</script>
