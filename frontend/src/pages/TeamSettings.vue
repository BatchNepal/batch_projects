<template>
  <div class="ts-root">
    <div v-if="loading" class="ts-loading">
      <div class="ts-spinner"/> Loading…
    </div>

    <template v-else-if="team">
      <!-- Header -->
      <header class="ts-header">
        <div class="ts-header-left">
          <div class="ts-team-dot" :style="{ background: draft.team_color || 'var(--accent)' }">
            {{ draft.team_icon || draft.team_name?.slice(0,2).toUpperCase() }}
          </div>
          <div>
            <h1 class="ts-title">{{ draft.team_name }}</h1>
            <p class="ts-subtitle">Team Settings</p>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <Transition name="ts-toast">
            <span v-if="saving" class="ts-saving">
              <div class="ts-spinner-sm"/> Saving…
            </span>
          </Transition>
          <button class="ts-close-btn" @click="$router.push(`/workspace/team/${team.team_key}/board`)">
            <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>
            Close
          </button>
        </div>
      </header>

      <div class="ts-body">
        <!-- Tab rail -->
        <nav class="ts-tabs">
          <button v-for="tab in TABS" :key="tab.id" class="ts-tab" :class="{ active: activeTab === tab.id }" @click="activeTab = tab.id">
            {{ tab.label }}
          </button>
        </nav>

        <div class="ts-content">

          <!-- ── GENERAL ── -->
          <div v-if="activeTab === 'general'" class="ts-section">
            <div class="ts-card">
              <div class="ts-card-head"><h2 class="ts-card-title">Identity</h2></div>

              <div class="ts-row">
                <div class="ts-row-label"><span class="ts-label">Team name</span></div>
                <div class="ts-row-ctrl">
                  <input v-model="draft.team_name" class="ts-input" placeholder="Engineering" @blur="save"/>
                </div>
              </div>
              <div class="ts-row">
                <div class="ts-row-label"><span class="ts-label">Team key</span><span class="ts-sublabel">Used in URLs (e.g. ENG)</span></div>
                <div class="ts-row-ctrl">
                  <input v-model="draft.team_key" class="ts-input ts-input--mono ts-input--sm" maxlength="6"
                    placeholder="ENG" @input="draft.team_key = draft.team_key.toUpperCase()" @blur="save"/>
                </div>
              </div>
              <div class="ts-row">
                <div class="ts-row-label"><span class="ts-label">Colour & Icon</span></div>
                <div class="ts-row-ctrl ts-row-ctrl--inline">
                  <div class="ts-color-wrap">
                    <div class="ts-color-swatch" :style="{ background: draft.team_color || 'var(--accent)' }"/>
                    <input type="color" v-model="draft.team_color" class="ts-color-hidden" @change="save"/>
                  </div>
                  <input v-model="draft.team_icon" class="ts-input ts-input--icon" placeholder="🚀" @blur="save"/>
                  <div class="ts-identity-preview" :style="{ background: draft.team_color || 'var(--accent)' }">
                    {{ draft.team_icon || draft.team_name?.slice(0,2).toUpperCase() }}
                  </div>
                </div>
              </div>
              <div class="ts-row ts-row--top">
                <div class="ts-row-label"><span class="ts-label">Description</span></div>
                <div class="ts-row-ctrl">
                  <textarea v-model="draft.description" class="ts-input ts-input--textarea" rows="3" @blur="save"/>
                </div>
              </div>
              <div class="ts-row">
                <div class="ts-row-label"><span class="ts-label">Team lead</span></div>
                <div class="ts-row-ctrl">
                  <FieldDropdown width="w-64">
                    <template #trigger>
                      <button class="ts-select">
                        <span v-if="draft.lead" class="ts-av" :style="{ background: avatarColor(draft.lead) }">{{ initials(leadName) }}</span>
                        <span v-else class="ts-av ts-av--empty">👤</span>
                        <span :style="{ color: draft.lead ? 'var(--foreground)' : 'var(--muted)' }">{{ leadName || 'No lead' }}</span>
                      </button>
                    </template>
                    <DropdownItem @click="draft.lead = null; save()"><span style="color:var(--muted)">No lead</span></DropdownItem>
                    <div style="height:1px;background:var(--border);margin:3px 0"/>
                    <DropdownItem v-for="u in allUsers" :key="u.user" :active="draft.lead === u.user" @click="draft.lead = u.user; save()">
                      <span class="ts-av" :style="{ background: avatarColor(u.user) }">{{ initials(u.full_name) }}</span>
                      {{ u.full_name }}
                    </DropdownItem>
                  </FieldDropdown>
                </div>
              </div>
              <div class="ts-row">
                <div class="ts-row-label"><span class="ts-label">Department</span><span class="ts-sublabel">ERPNext Department sync</span></div>
                <div class="ts-row-ctrl">
                  <FieldDropdown width="w-64">
                    <template #trigger>
                      <button class="ts-select">
                        <span :style="{ color: draft.department ? 'var(--foreground)' : 'var(--muted)' }">
                          {{ draft.department || 'No department' }}
                        </span>
                      </button>
                    </template>
                    <DropdownItem @click="draft.department = null; save()"><span style="color:var(--muted)">No department</span></DropdownItem>
                    <div style="height:1px;background:var(--border);margin:3px 0"/>
                    <DropdownItem v-for="d in departments" :key="d.name" :active="draft.department === d.name" @click="draft.department = d.name; save()">
                      {{ d.department_name || d.name }}
                    </DropdownItem>
                  </FieldDropdown>
                </div>
              </div>
              <div class="ts-row">
                <div class="ts-row-label"><span class="ts-label">Sprint capacity</span><span class="ts-sublabel">Default hours per sprint</span></div>
                <div class="ts-row-ctrl">
                  <input v-model.number="draft.capacity_hours_per_sprint" type="number" min="0" class="ts-input ts-input--sm" @blur="save"/>
                </div>
              </div>
            </div>

            <!-- Danger zone -->
            <div class="ts-card">
              <div class="ts-card-head"><h2 class="ts-card-title">Danger zone</h2></div>
              <div class="ts-row">
                <div class="ts-row-label">
                  <span class="ts-label">Archive team</span>
                  <span class="ts-sublabel">Hidden from listings and unlinked from its projects. Data is preserved.</span>
                </div>
                <div class="ts-row-ctrl">
                  <button class="ts-btn-danger-sm" @click="archiveTeamConfirm">Archive team</button>
                </div>
              </div>
            </div>
          </div>

          <!-- ── MEMBERS ── -->
          <div v-if="activeTab === 'members'" class="ts-section">
            <!-- Add member row -->
            <div class="ts-add-row">
              <FieldDropdown width="w-64">
                <template #trigger>
                  <button class="ts-select-btn">
                    <span :style="{ color: newMember ? 'var(--foreground)' : 'var(--muted)' }">
                      {{ newMember ? getMemberName(newMember) : 'Select user…' }}
                    </span>
                  </button>
                </template>
                <template #search>
                  <div class="ts-dd-search"><input v-model="memberQ" autofocus placeholder="Search…" class="ts-dd-input"/></div>
                </template>
                <DropdownItem v-for="u in availableUsers" :key="u.user" @click="newMember = u.user">
                  <span class="ts-av" :style="{ background: avatarColor(u.user) }">{{ initials(u.full_name) }}</span>
                  {{ u.full_name }}
                </DropdownItem>
              </FieldDropdown>
              <FieldDropdown width="w-36">
                <template #trigger>
                  <button class="ts-select-btn">{{ newRole }}</button>
                </template>
                <DropdownItem v-for="r in ROLES" :key="r" :active="newRole === r" @click="newRole = r">{{ r }}</DropdownItem>
              </FieldDropdown>
              <input v-model.number="newCapacity" type="number" min="0" class="ts-input ts-input--sm" placeholder="Capacity hrs" style="width:120px"/>
              <button class="ts-btn-primary" :disabled="!newMember" @click="addMember">Add member</button>
            </div>

            <!-- Members table -->
            <div class="ts-table">
              <div class="ts-table-head">
                <span class="ts-th" style="flex:1">Member</span>
                <span class="ts-th" style="width:110px">Role</span>
                <span class="ts-th" style="width:110px">Capacity (hrs)</span>
                <span class="ts-th" style="width:50px"/>
              </div>
              <div v-for="m in members" :key="m.user" class="ts-table-row">
                <div class="ts-td" style="flex:1;display:flex;align-items:center;gap:10px">
                  <span class="ts-av" :style="{ background: avatarColor(m.user) }">{{ initials(m.full_name) }}</span>
                  <div>
                    <p style="font-size:var(--text-base);font-weight:500;color:var(--foreground)">{{ m.full_name }}</p>
                    <p style="font-size:var(--text-xs);color:var(--muted)">{{ m.user }}</p>
                  </div>
                </div>
                <div class="ts-td" style="width:110px">
                  <FieldDropdown width="w-36">
                    <template #trigger>
                      <button class="ts-role-btn">
                        <span class="ts-role-badge" :class="`ts-role-${m.role?.toLowerCase()}`">{{ m.role }}</span>
                      </button>
                    </template>
                    <DropdownItem v-for="r in ROLES" :key="r" :active="m.role === r" @click="updateMemberRole(m, r)">{{ r }}</DropdownItem>
                  </FieldDropdown>
                </div>
                <div class="ts-td" style="width:110px">
                  <input type="number" min="0" :value="m.capacity_hours_per_sprint" class="ts-input ts-input--sm" style="width:80px"
                    @change="e => updateMemberCapacity(m, e.target.value)"/>
                </div>
                <div class="ts-td" style="width:50px;display:flex;justify-content:flex-end">
                  <button class="ts-remove-btn" @click="removeMember(m)">
                    <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
                  </button>
                </div>
              </div>
              <div v-if="!members.length" class="ts-empty">No members yet.</div>
            </div>
          </div>

          <!-- ── PROJECTS ── -->
          <div v-if="activeTab === 'projects'" class="ts-section">
            <div class="ts-card">
              <div class="ts-card-head">
                <h2 class="ts-card-title">Projects in this team</h2>
                <p class="ts-card-desc">Assign or remove projects from this team.</p>
              </div>
              <!-- All projects -->
              <div v-for="p in allProjects" :key="p.name" class="ts-proj-row">
                <ProjectAvatar :theme="p.theme" :seed="p.key" size="xs" />
                <span class="ts-proj-name">{{ p.project_name }}</span>
                <span class="ts-proj-key">{{ p.key }}</span>
                <div style="flex:1"/>
                <button v-if="p.team === team.name" class="ts-btn-danger-sm" @click="unassignProject(p)">Remove</button>
                <button v-else class="ts-btn-ghost-sm" @click="assignProject(p)">Add to team</button>
              </div>
              <div v-if="!allProjects.length" class="ts-empty">No active projects.</div>
            </div>
          </div>

        </div>
      </div>

      <!-- Toast -->
      <Transition name="ts-toast">
        <div v-if="toast.show" class="ts-toast" :class="`ts-toast-${toast.type}`">{{ toast.message }}</div>
      </Transition>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useProjectStore } from '@/stores/project'
import { avatarColor, initials } from '@/utils/constants.js'
import * as api from '@/utils/api.js'
import FieldDropdown from '@/components/FieldDropdown.vue'
import DropdownItem  from '@/components/DropdownItem.vue'
import ProjectAvatar from '@/ui/ProjectAvatar.vue'
import { confirmDialog } from '@/composables/useConfirmDialog'

const route  = useRoute()
const router = useRouter()
const store  = useProjectStore()
const teamKey = computed(() => route.params.key)

const loading    = ref(true)
const saving     = ref(false)
const activeTab  = ref('general')
const team       = ref(null)
const members    = ref([])
const allUsers   = ref([])
const departments = ref([])
const allProjects = ref([])

const draft      = ref({})
const newMember  = ref(null)
const newRole    = ref('Member')
const newCapacity = ref(40)
const memberQ    = ref('')

const toast = ref({ show: false, type: 'success', message: '' })
let toastTimer = null

const TABS  = [
  { id: 'general',  label: 'General'  },
  { id: 'members',  label: 'Members'  },
  { id: 'projects', label: 'Projects' },
]
const ROLES = ['Admin', 'Manager', 'Member', 'Viewer']

const leadName = computed(() =>
  draft.value.lead ? (allUsers.value.find(u => u.user === draft.value.lead)?.full_name || draft.value.lead) : ''
)

const availableUsers = computed(() => {
  const existing = new Set(members.value.map(m => m.user))
  const q = memberQ.value.toLowerCase()
  return allUsers.value.filter(u => !existing.has(u.user) && (!q || u.full_name.toLowerCase().includes(q) || u.user.toLowerCase().includes(q)))
})

function getMemberName(user) {
  return allUsers.value.find(u => u.user === user)?.full_name || user
}

async function save() {
  if (!team.value) return
  saving.value = true
  try {
    await api.updateTeam(team.value.name, draft.value)
    // Refresh team in store
    await store.fetchTeams()
    showToast('Saved')
  } catch (e) {
    showToast(e.message || 'Failed to save', 'error')
  } finally { saving.value = false }
}

async function addMember() {
  if (!newMember.value) return
  const u = allUsers.value.find(u => u.user === newMember.value)
  if (!u) return
  members.value.push({ user: u.user, full_name: u.full_name, role: newRole.value, capacity_hours_per_sprint: newCapacity.value })
  await saveMembers()
  newMember.value = null; newRole.value = 'Member'; newCapacity.value = 40; memberQ.value = ''
}

async function removeMember(m) {
  if (!await confirmDialog(`Remove ${m.full_name || m.user}?`, { danger: true })) return
  members.value = members.value.filter(x => x.user !== m.user)
  await saveMembers()
}

async function updateMemberRole(m, role) {
  m.role = role
  await saveMembers()
}

async function updateMemberCapacity(m, val) {
  m.capacity_hours_per_sprint = Number(val) || 0
  await saveMembers()
}

async function saveMembers() {
  try {
    await api.updateTeamMembers(team.value.name, members.value)
    showToast('Members updated')
  } catch (e) { showToast('Failed', 'error') }
}

async function assignProject(p) {
  try {
    await api.assignProjectToTeam(p.name, team.value.name)
    p.team = team.value.name
    showToast(`${p.project_name} added to team`)
    await store.fetchTeams()
  } catch (e) { showToast(e.message || 'Failed to assign project', 'error') }
}

async function unassignProject(p) {
  if (!await confirmDialog(`Remove ${p.project_name} from this team?`, { danger: true })) return
  try {
    await api.assignProjectToTeam(p.name, '')
    p.team = null
    showToast(`${p.project_name} removed`)
    await store.fetchTeams()
  } catch (e) { showToast(e.message || 'Failed to remove project', 'error') }
}

async function archiveTeamConfirm() {
  if (!await confirmDialog(`Archive "${team.value.team_name}"? It will be hidden and unlinked from its projects. Data is preserved.`, { danger: true })) return
  try {
    await api.archiveTeam(team.value.name)
    await store.fetchTeams()
    router.push('/workspace/teams')
  } catch (e) { showToast(e.message || 'Failed to archive team', 'error') }
}

function showToast(message, type = 'success') {
  if (toastTimer) clearTimeout(toastTimer)
  toast.value = { show: true, type, message }
  toastTimer = setTimeout(() => { toast.value.show = false }, 2500)
}

async function load() {
  loading.value = true
  try {
    if (!store.teams.length) await store.fetchTeams()
    const t = store.teams.find(t => t.team_key === teamKey.value)
    if (!t) { loading.value = false; return }

    const [teamData, depts, projects] = await Promise.all([
      api.getTeam(t.name),
      api.getErpNextDepartments(),
      api.getProjects(),
    ])

    team.value    = teamData
    members.value = teamData.members || []
    departments.value = depts || []
    allProjects.value = projects || []

    // Flatten all system users from store
    allUsers.value = store.projectMembers.length
      ? store.projectMembers
      : (teamData.members || [])

    // If store has users from board, use those
    if (store.boardData?.members?.length) {
      allUsers.value = store.boardData.members
    }

    draft.value = {
      team_name:   teamData.team_name,
      team_key:    teamData.team_key,
      team_color:  teamData.team_color || 'var(--accent)',
      team_icon:   teamData.team_icon || '',
      description: teamData.description || '',
      lead:        teamData.lead || null,
      department:  teamData.department || null,
      company:     teamData.company || '',
      capacity_hours_per_sprint: teamData.capacity_hours_per_sprint || 80,
      default_workflow_template: teamData.default_workflow_template || 'general',
    }
  } finally { loading.value = false }
}

onMounted(load)
watch(teamKey, load)
</script>

<style scoped>
.ts-root { height:100vh; display:flex; flex-direction:column; background:var(--surface-secondary); font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; font-size:var(--text-md); color:var(--foreground); }
.ts-loading { display:flex; align-items:center; justify-content:center; height:200px; gap:10px; color:var(--muted); }
.ts-spinner { width:16px; height:16px; border-radius:50%; border:2.5px solid var(--border); border-top-color:var(--accent); animation:ts-spin .7s linear infinite; }
.ts-spinner-sm { width:12px; height:12px; border:2px solid rgba(255,255,255,.3); border-top-color:var(--accent-foreground); border-radius:50%; animation:ts-spin .7s linear infinite; display:inline-block; }
@keyframes ts-spin { to { transform:rotate(360deg) } }

/* Header */
.ts-header { display:flex; align-items:center; justify-content:space-between; height:52px; padding:0 24px; background:var(--surface); border-bottom:1px solid var(--border); flex-shrink:0; }
.ts-header-left { display:flex; align-items:center; gap:12px; }
.ts-team-dot { width:32px; height:32px; border-radius:4px; display:flex; align-items:center; justify-content:center; color:var(--accent-foreground); font-size:var(--text-xs); font-weight:700; }
.ts-title { font-size:var(--text-md); font-weight:700; color:var(--foreground); }
.ts-subtitle { font-size:var(--text-xs); color:var(--muted); }
.ts-saving { display:inline-flex; align-items:center; gap:5px; font-size:var(--text-sm); color:var(--muted); }
.ts-close-btn { display:inline-flex; align-items:center; gap:5px; height:30px; padding:0 12px; font-size:var(--text-sm); font-weight:500; font-family:inherit; color:var(--muted); background:none; border:1px solid var(--border); border-radius:var(--radius-md); cursor:pointer; transition:background .15s ease; }
.ts-close-btn:hover { background:var(--surface-secondary); }

/* Body */
.ts-body { display:flex; flex:1; min-height:0; }
.ts-tabs { width:160px; flex-shrink:0; background:var(--surface); border-right:1px solid var(--border); padding:16px 8px; display:flex; flex-direction:column; gap:2px; }
.ts-tab { display:flex; align-items:center; height:34px; padding:0 10px; font-size:var(--text-base); font-weight:500; font-family:inherit; color:var(--foreground); background:none; border:none; border-radius:var(--radius-md); cursor:pointer; text-align:left; transition:background .15s ease, color .15s ease; }
.ts-tab:hover { background:var(--surface-secondary); }
.ts-tab.active { background:var(--surface-secondary); color:var(--foreground); font-weight:700; }
.ts-content { flex:1; overflow-y:auto; padding:24px 28px; }

/* Cards */
.ts-section { max-width:700px; display:flex; flex-direction:column; gap:20px; }
.ts-card { box-shadow: var(--surface-shadow); border-radius:16px; background:var(--surface); overflow:hidden; }
.ts-card-head { padding:14px 22px 12px; border-bottom:1px solid var(--surface-secondary); background:var(--background); }
.ts-card-title { font-size:var(--text-base); font-weight:700; color:var(--foreground); margin:0 0 2px; }
.ts-card-desc  { font-size:var(--text-sm); color:var(--muted); margin:0; }

.ts-row { display:grid; grid-template-columns:200px 1fr; align-items:center; gap:20px; padding:13px 22px; border-bottom:1px solid var(--surface-secondary); }
.ts-row:last-child { border-bottom:none; }
.ts-row--top { align-items:flex-start; }
.ts-row-label { display:flex; flex-direction:column; gap:2px; }
.ts-label    { font-size:var(--text-base); font-weight:600; color:var(--foreground); }
.ts-sublabel { font-size:var(--text-sm); color:var(--muted); }
.ts-row-ctrl { display:flex; flex-direction:column; }
.ts-row-ctrl--inline { flex-direction:row; align-items:center; gap:10px; }

.ts-input { width:100%; height:34px; padding:0 10px; font-size:var(--text-base); font-family:inherit; color:var(--foreground); background:var(--surface-secondary); border:1.5px solid var(--border); border-radius:4px; outline:none; transition:background .1s, border-color .1s; }
.ts-input:focus { background:var(--surface); border-color:var(--accent); box-shadow:0 0 0 3px rgba(76,154,255,.12); }
.ts-input--mono { width:110px; font-family:monospace; text-transform:uppercase; }
.ts-input--sm { width:80px; }
.ts-input--textarea { height:auto; min-height:76px; padding:9px 10px; resize:vertical; }
.ts-input--icon { width:60px; text-align:center; font-size:var(--text-3xl); }

.ts-color-wrap { position:relative; width:34px; height:34px; flex-shrink:0; }
.ts-color-swatch { width:34px; height:34px; border-radius:4px; border:1.5px solid var(--border); pointer-events:none; }
.ts-color-hidden { position:absolute; inset:0; opacity:0; cursor:pointer; width:100%; height:100%; }
.ts-identity-preview { width:36px; height:36px; border-radius:6px; flex-shrink:0; display:flex; align-items:center; justify-content:center; color:var(--accent-foreground); font-size:var(--text-base); font-weight:700; }

.ts-select { display:inline-flex; align-items:center; gap:8px; height:36px; padding:0 10px; min-width:200px; font-size:var(--text-base); font-family:inherit; color:var(--foreground); background:var(--surface-secondary); border:1.5px solid var(--border); border-radius:4px; cursor:pointer; }
.ts-select:hover { border-color:var(--border-secondary); }
.ts-av { width:24px; height:24px; border-radius:50%; display:inline-flex; align-items:center; justify-content:center; color:var(--accent-foreground); font-size:var(--text-micro); font-weight:700; flex-shrink:0; }
.ts-av--empty { background:var(--surface-secondary) !important; color:var(--muted); }

/* Members table */
.ts-add-row { background:var(--surface); border:1px solid var(--border); border-radius:var(--radius-md); padding:14px 16px; margin-bottom:16px; display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
.ts-select-btn { display:inline-flex; align-items:center; gap:7px; height:30px; padding:0 10px; min-width:180px; font-size:var(--text-base); font-family:inherit; color:var(--foreground); background:var(--surface-secondary); border:1px solid var(--border); border-radius:var(--radius-md); cursor:pointer; }
.ts-select-btn:hover { border-color:var(--border-secondary); }
.ts-dd-search { padding:8px 11px; border-bottom:1px solid var(--border); }
.ts-dd-input { width:100%; font-size:var(--text-sm); font-family:inherit; border:none; outline:none; background:transparent; }
.ts-table { background:var(--surface); border:1px solid var(--border); border-radius:var(--radius-md); }
.ts-table-head { display:flex; align-items:center; background:var(--surface-secondary); border-bottom:1px solid var(--border); padding:0 16px; height:34px; }
.ts-th { font-size:var(--text-xs); font-weight:700; color:var(--muted); text-transform:uppercase; letter-spacing:.04em; }
.ts-table-row { display:flex; align-items:center; padding:0 16px; height:52px; border-bottom:1px solid var(--surface-secondary); }
.ts-table-row:last-child { border-bottom:none; }
.ts-td { display:flex; align-items:center; }
.ts-role-btn { border:none; background:none; cursor:pointer; padding:2px 0; }
.ts-role-badge { display:inline-flex; align-items:center; padding:2px 8px; border-radius:var(--radius-md); font-size:var(--text-xs); font-weight:700; text-transform:uppercase; }
.ts-role-admin   { background:var(--accent-soft); color:var(--accent); }
.ts-role-manager { background:var(--accent-soft); color:var(--accent-soft-foreground); }
.ts-role-member  { background:var(--success-soft); color:var(--success-soft-foreground); }
.ts-role-viewer  { background:var(--surface-secondary); color:var(--foreground); }
.ts-remove-btn { display:flex; align-items:center; justify-content:center; width:26px; height:26px; border:none; background:none; color:var(--muted); border-radius:var(--radius-md); cursor:pointer; transition:background .15s ease, color .15s ease; }
.ts-remove-btn:hover { background:var(--danger-soft); color:var(--danger-soft-foreground); }
.ts-empty { padding:28px; text-align:center; font-size:var(--text-base); color:var(--muted); }

/* Projects tab */
.ts-proj-row { display:flex; align-items:center; gap:10px; padding:12px 22px; border-bottom:1px solid var(--surface-secondary); }
.ts-proj-row:last-child { border-bottom:none; }
.ts-proj-name { font-size:var(--text-base); font-weight:500; color:var(--foreground); }
.ts-proj-key { font-size:var(--text-xs); font-family:monospace; color:var(--muted); background:var(--surface-secondary); padding:1px 5px; border-radius:2px; }

/* Buttons */
.ts-btn-primary { display:inline-flex; align-items:center; height:30px; padding:0 12px; font-size:var(--text-sm); font-weight:700; font-family:inherit; color:var(--accent-foreground); background:var(--accent); border:none; border-radius:var(--radius-md); cursor:pointer; }
.ts-btn-primary:hover { background:var(--accent-hover); }
.ts-btn-primary:disabled { opacity:.5; cursor:not-allowed; }
.ts-btn-ghost-sm { height:28px; padding:0 10px; font-size:var(--text-sm); font-weight:600; font-family:inherit; color:var(--foreground); background:var(--surface); border:1px solid var(--border); border-radius:var(--radius-md); cursor:pointer; }
.ts-btn-ghost-sm:hover { background:var(--surface-secondary); }
.ts-btn-danger-sm { height:28px; padding:0 10px; font-size:var(--text-sm); font-weight:600; font-family:inherit; color:var(--danger-soft-foreground); background:var(--surface); border:1px solid var(--danger); border-radius:var(--radius-md); cursor:pointer; }
.ts-btn-danger-sm:hover { background:var(--danger-soft); }

/* Toast */
.ts-toast { position:fixed; bottom:24px; left:50%; transform:translateX(-50%); display:inline-flex; align-items:center; gap:7px; padding:8px 16px; border-radius:4px; font-size:var(--text-base); font-weight:500; z-index:9999; white-space:nowrap; box-shadow:0 4px 12px rgba(9,30,66,.2); }
.ts-toast-success { background:var(--success); color:var(--accent-foreground); }
.ts-toast-error   { background:var(--danger-soft-foreground); color:var(--accent-foreground); }
.ts-toast-enter-active { transition:all .2s ease; }
.ts-toast-leave-active { transition:all .15s ease; }
.ts-toast-enter-from, .ts-toast-leave-to { opacity:0; transform:translateX(-50%) translateY(8px); }
</style>