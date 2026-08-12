<template>
<Teleport to="body">
<div class="jv-root">
  <div class="jv-backdrop" @click="store.closeTaskDetail()"/>

  <div class="jv-panel">

    <!-- ═══ HEADER BAR ═══ -->
    <header class="jv-header">
      <div class="jv-crumb">
        <LayoutGrid class="size-3 shrink-0 text-muted" />
        <span class="jv-crumb-project">Manage Task</span>
        <span class="jv-crumb-sep">/</span>
        <span v-if="issue" class="jv-crumb-key">{{ issue.task_key }}</span>
      </div>
      <div class="jv-header-actions">
        <Transition name="jv-fade">
          <span v-if="saveState !== 'idle'" class="jv-autosave" :class="`jv-save-${saveState}`">
            <Loader2 v-if="saveState === 'saving'" class="jv-spin size-2.5" />
            {{ saveState === 'saving' ? 'Saving…' : saveState === 'saved' ? 'Saved' : 'Failed' }}
          </span>
        </Transition>
        <!-- Eye/EyeOff is the right semantic (watch = visibility, kept
             distinct from Bell = notifications/mute in the More menu below)
             — Jira uses the same pairing. What actually read wrong was
             SIZE: EyeOff's diagonal slash fills its box far more than a
             glyph like X or the three dots beside it, so identical size-3.5
             looked visually heavier. Dropped one step to match their
             apparent weight, not their nominal box. -->
        <button class="jv-hbtn jv-watch-btn" :class="{ active: watching }" @click="toggleWatch" :title="watching ? 'Stop watching' : 'Watch this issue'">
          <component :is="watching ? Eye : EyeOff" class="size-3" />
        </button>
        <!-- Real people, not a count in a box — who's actually looking at
             this task right now, stacked like Assignee's own avatar stack
             above. Real photo when the user has one (jv-av-img), the usual
             hashed initials otherwise — same fallback rule as everywhere
             else in this file, no longer initials-only like the dropdown
             list below used to be either. No presence dot IN the stack: a
             6px dot at an avatar's own bottom-right corner sits exactly
             where the NEXT overlapping avatar paints on top of it, so
             anything but the last avatar would show a clipped dot — real,
             accurate presence stays one click away in the roomy dropdown
             list, which has no overlap to clip it. Click opens that list. -->
        <FieldDropdown v-if="watcherCount" ref="watcherRef" @open="loadWatchers" align="right" width="w-52">
          <template #trigger>
            <button class="jv-watch-stack-btn" :title="`${watcherCount} watching`">
              <span v-if="headerWatchers.length" class="jv-av-stack">
                <span v-for="w in headerWatchers" :key="w.user" class="jv-av jv-av-xs jv-av-stacked"
                  :class="{ 'jv-av-img': w.user_image }"
                  :style="w.user_image ? {} : { background: aColor(w.user) }">
                  <img v-if="w.user_image" :src="w.user_image" :alt="w.full_name" class="jv-av-photo" />
                  <template v-else>{{ ini(w.full_name) }}</template>
                </span>
              </span>
              <!-- Only ever the OVERFLOW, never the raw total — a bare "4"
                   next to 3 avatars already told you nothing the avatars
                   didn't; "+1" tells you there's someone NOT pictured. -->
              <span v-if="watcherOverflow > 0" class="jv-watch-count">+{{ watcherOverflow }}</span>
            </button>
          </template>
          <div v-if="watchersLoading" class="px-3 py-2 text-sm text-muted">Loading…</div>
          <template v-else-if="watcherList">
            <div v-if="watcherList.length">
              <div v-for="w in watcherList" :key="w.user" class="flex items-center gap-2.5 px-3 py-1.5">
                <span class="relative shrink-0">
                  <span class="jv-av jv-av-xs" :class="{ 'jv-av-img': w.user_image }"
                    :style="w.user_image ? {} : { background: aColor(w.user) }">
                    <img v-if="w.user_image" :src="w.user_image" :alt="w.full_name" class="jv-av-photo" />
                    <template v-else>{{ ini(w.full_name) }}</template>
                  </span>
                  <span v-if="isOnline(w.user)" class="jv-presence-dot" title="Online" />
                </span>
                <span class="text-sm text-foreground truncate">{{ w.full_name }}</span>
                <span v-if="isOnline(w.user)" class="text-xs text-success-soft-foreground ml-auto shrink-0">Online</span>
              </div>
            </div>
            <div v-else class="px-3 py-2 text-sm text-muted">No watchers</div>
          </template>
        </FieldDropdown>
        <FieldDropdown ref="moreRef" align="right" width="w-44">
          <template #trigger>
            <button class="jv-hbtn" title="More actions">
              <MoreHorizontal class="size-3.5" />
            </button>
          </template>
          <DropdownItem @click="doDuplicate(); moreRef?.close()">
            <Copy class="w-3.5 h-3.5 shrink-0" />Duplicate
          </DropdownItem>
          <DropdownItem @click="shareOpen = true; moreRef?.close()">
            <Share2 class="w-3.5 h-3.5 shrink-0" />Share task…
          </DropdownItem>
          <DropdownItem @click="toggleMute(); moreRef?.close()">
            <component :is="muted ? Bell : BellOff" class="w-3.5 h-3.5 shrink-0" />{{ muted ? 'Unmute notifications' : 'Mute notifications' }}
          </DropdownItem>
          <DropdownItem danger @click="handleDelete">
            <Trash2 class="w-3.5 h-3.5 shrink-0" />Delete
          </DropdownItem>
        </FieldDropdown>
        <button class="jv-hbtn" @click="store.closeTaskDetail()" title="Close">
          <X class="size-3.5" />
        </button>
      </div>
    </header>
 
    <!-- Loading -->
    <div v-if="!issue" class="jv-loading">
      <div class="jv-loader"/><span>Loading…</span>
    </div>

    <!-- ═══ TWO-COLUMN BODY ═══ -->
    <div v-else class="jv-body">

      <!-- ─── LEFT: MAIN CONTENT ─── -->
      <div class="jv-main">

        <!-- Hero card: title + action bar -->
        <div class="jv-hero">
        <div class="jv-title-block">
          <h1 ref="titleEl" contenteditable spellcheck="false" class="jv-title"
            @blur="saveTitle" @keydown.enter.prevent="titleEl?.blur()" @keydown.escape="titleEl?.blur()">{{ issue.title }}</h1>
        </div>

        <!-- Action bar (transition buttons) -->
        <div class="jv-action-bar">
          <button class="jv-action-btn" @click="focusComposer">
            <MessageCircle class="size-3" />
            Comment
          </button>
          <button class="jv-action-btn" @click="showAddSub = true">
            <ClipboardList class="size-3" />
            Child issue
          </button>
          <button class="jv-action-btn" @click="showAddLink = true">
            <Link2 class="size-3" />
            Link issue
          </button>
        </div>
        </div><!-- /jv-hero -->

        <!-- Description -->
        <div class="jv-section">
          <div class="jv-section-title">Description</div>
          <div class="jv-desc-wrap" @click="startDescEdit">
            <div v-if="!descEditing && !issue.description" class="jv-desc-placeholder">Add a description…</div>
            <div v-else-if="!descEditing" class="jv-desc-preview" v-html="issue.description"/>
            <div v-else @click.stop>
              <RichTextEditor :modelValue="descDraft" placeholder="Add a description…" min-height="100px" @update:modelValue="descDraft = $event" autofocus/>
              <div class="jv-desc-actions">
                <button class="jv-btn-save" @click.stop="saveDescription">
                  <span v-if="descSaving" class="jv-desc-spinner"/>
                  Done
                </button>
                <button class="jv-btn-cancel" @click.stop="cancelDescription">Cancel</button>
              </div>
            </div>
          </div>
        </div>

        <!-- Checklist -->
        <div class="jv-section">
          <div class="flex items-center justify-between">

            <div class="jv-section-title">
              Checklist
              <span v-if="checklistItems.length" class="jv-section-count">{{ checklistDone }}/{{ checklistItems.length }}</span>
              <div v-if="checklistItems.length" class="jv-mini-progress"><div class="jv-mini-fill" :style="{ width: checklistPct + '%' }"/></div>
            </div>
           <div class="jv-cl-add">
              <button class="jv-cl-add-btn" @click="addCheck">
                <Plus class="size-3" />
              </button>
            </div>
          </div>
          <div class="jv-checklist">
            <div v-for="item in checklistItems" :key="item.id" class="jv-cl-row">
              <button class="jv-cl-check" :class="{ done: item.done }" @click="toggleCheck(item)">
                <Check v-if="item.done" class="size-2.5 text-white" :stroke-width="3.5" />
              </button>
              <input
                :ref="el => setChecklistInputRef(item.id, el)"
                class="jv-cl-text"
                :class="{ done: item.done }"
                :value="item.text"
                @blur="(e) => onChecklistBlur(item, e.target.value)"
                @keydown.enter="(e) => e.target.blur()"
                @keydown.delete="(e) => { if (!e.target.value) removeCheck(item); }"
              />
              <button class="jv-cl-del" @click="removeCheck(item)">
                <X class="size-3" />
              </button>
            </div>
             <div v-if="!checklistItems.length" class="jv-cl-add">
              <button class="jv-cl-add-btn" @click="addCheck">
                <Plus class="size-3" />
                Add Checklist Item
              </button>
            </div>
          </div>
        </div>

        <!-- Attachments (capability off = hide outright) -->
        <div v-if="canViewFiles" class="jv-section">
          <div class="jv-section-title">Attachments</div>
          <TaskAttachments
            :modelValue="attachments"
            :issue-name="issue?.name"
            @update:modelValue="v => { if (store.selectedTask) store.selectedTask.attachments = v }"
          />
        </div>

        <!-- Child Issues / Subtasks -->
        <div class="jv-section">
          <div class="flex items-center justify-between">
            <div class="jv-section-title">
              SUBTASKS
              <span v-if="subtasks.length" class="jv-section-count">{{ doneCount }}/{{ subtasks.length }}</span>
              <div v-if="subtasks.length" class="jv-mini-progress"><div class="jv-mini-fill" :style="{ width: progressPct + '%' }"/></div>
            </div>
            <div v-if="!subtasks.length" class="jv-sub-empty">
             <button v-if="!showAddSub" class="jv-add-child-btn" @click="showAddSub=true">
            <Plus class="size-2.5" />
          </button>
          </div>
          </div>

          <div v-if="subtasks.length" class="jv-subtasks">
            <div v-for="st in subtasks" :key="st.name" class="jv-subtask">
              <button class="jv-st-check" :class="{ done: isCompleted(st.status) }" @click.stop="toggleSubtask(st)">
                <Check v-if="isCompleted(st.status)" class="size-2 text-white" :stroke-width="3.5" />
              </button>
              <span class="jv-st-type" :style="{ background: st.task_type ? taskTypeColor : 'var(--accent)' }">{{ (st.task_type || 'T').charAt(0) }}</span>
              <span class="jv-st-key">{{ st.task_key }}</span>
              <span class="jv-st-title" :class="{ done: isCompleted(st.status) }">{{ st.title }}</span>
              <div class="jv-st-meta">
                <div class="jv-st-pill-wrap">
                  <FieldDropdown width="w-32">
                    <template #trigger>
                      <button class="jv-st-pill">
                        <PriorityIcon v-if="st.priority" :priority="st.priority"/>
                        <span v-else style="color:var(--muted)">—</span>
                      </button>
                    </template>
                    <DropdownItem v-for="p in PRIORITIES" :key="p.value" :active="st.priority===p.value" @click="updateSubtask(st,'priority',p.value)"><PriorityIcon :priority="p.value"/><span class="text-foreground">{{ p.label }}</span></DropdownItem>
                  </FieldDropdown>
                </div>
                <div class="jv-st-pill-wrap">
                  <FieldDropdown width="w-36">
                    <template #trigger>
                      <button class="jv-st-pill">
                        <span class="jv-st-status" :style="{ background: wfColor(st.status)+'1A', color: wfColor(st.status) }">{{ st.status }}</span>
                      </button>
                    </template>
                    <DropdownItem v-for="s in store.workflowStates" :key="s.name" :active="st.status===s.name" @click="updateSubtask(st,'status',s.name)"><span class="w-2 h-2 rounded-sm shrink-0" :style="{ background: s.color }"/>{{ s.name }}</DropdownItem>
                  </FieldDropdown>
                </div>
                <div class="jv-st-pill-wrap">
                  <FieldDropdown width="w-44" :close-on-select="false">
                    <template #trigger>
                      <button class="jv-st-pill">
                        <template v-if="st.assignees?.length">
                          <span v-for="a in st.assignees.slice(0,2)" :key="a.user" class="jv-av jv-av-xs" :style="{ background: aColor(a.user) }">{{ ini(a.full_name) }}</span>
                        </template>
                        <UserRound v-else class="size-2.5 text-muted" />
                      </button>
                    </template>
                    <template #search>
                      <div class="jv-dd-search"><input v-model="stAssigneeQ" autofocus placeholder="Search…" class="jv-dd-input"/></div>
                    </template>
                    <DropdownItem @click="updateSubtask(st,'assignees',[])"><div class="jv-av-empty"/>Unassigned</DropdownItem>
                    <div class="jv-dd-sep"/>
                    <DropdownItem v-for="m in filteredMembersSt" :key="m.user" :active="st.assignees?.some(a=>a.user===m.user)" @click="toggleStAssignee(st,m)">
                      <span class="jv-av jv-av-sm" :style="{ background: aColor(m.user) }">{{ ini(m.full_name) }}</span><span class="flex-1 truncate">{{ m.full_name }}</span>
                    </DropdownItem>
                  </FieldDropdown>
                </div>
              </div>
            </div>
          </div>

          <!-- Add child issue inline -->
          <div v-if="showAddSub" class="jv-add-row">
            <span class="jv-type-badge" :style="{ background: taskTypeColor }">{{ (store.taskTypes?.[0]?.name || 'T').charAt(0) }}</span>
            <input v-model="newSubTitle" class="jv-add-input" placeholder="What needs to be done?" autofocus @keydown.enter="addSubtask" @keydown.escape="showAddSub = false; newSubTitle = ''"/>
            <div class="jv-st-pill-wrap">
              <FieldDropdown width="w-32">
                <template #trigger>
                  <button class="jv-add-chip"><PriorityIcon :priority="newSubPriority"/><span style="font-size:var(--text-xs)" class="text-foreground">{{ newSubPriority }}</span></button>
                </template>
                <DropdownItem v-for="p in PRIORITIES" :key="p.value" :active="newSubPriority===p.value" @click="newSubPriority=p.value"><PriorityIcon :priority="p.value"/><span class="text-foreground">{{ p.label }}</span></DropdownItem>
              </FieldDropdown>
            </div>
            <button class="jv-btn-save" @click="addSubtask" :disabled="!newSubTitle.trim()">
              <svg stroke="currentColor" fill="currentColor" 
              stroke-width="0" viewBox="0 0 20 20" aria-hidden="true" 
              height="16px" width="16px" 
              xmlns="http://www.w3.org/2000/svg"><path fill-rule="evenodd" d="M16.25 3a.75.75 0 0 0-.75.75v7.5H4.56l1.97-1.97a.75.75 0 0 0-1.06-1.06l-3.25 3.25a.75.75 0 0 0 0 1.06l3.25 3.25a.75.75 0 0 0 1.06-1.06l-1.97-1.97h11.69A.75.75 0 0 0 17 12V3.75a.75.75 0 0 0-.75-.75Z" clip-rule="evenodd"></path></svg>
            </button>
            <button class="jv-btn-cancel" @click="showAddSub=false;newSubTitle=''">
              <svg stroke="currentColor" fill="none" 
              stroke-width="0" viewBox="0 0 15 15" 
              height="15px" width="15px" 
              xmlns="http://www.w3.org/2000/svg"><path d="M10.9688 3.21871C11.1933 2.99416 11.5567 2.99416 11.7813 3.21871C12.0056 3.44328 12.0057 3.80673 11.7813 4.03121L8.31251 7.49996L11.7813 10.9687L11.8555 11.0586C12.0026 11.2817 11.9777 11.5848 11.7813 11.7812C11.5849 11.9776 11.2818 12.0026 11.0586 11.8554L10.9688 11.7812L7.50001 8.31246L4.03126 11.7812C3.80677 12.0057 3.44332 12.0056 3.21876 11.7812C2.99421 11.5567 2.99421 11.1933 3.21876 10.9687L6.68751 7.49996L3.21876 4.03121L3.14454 3.94137C2.99723 3.71819 3.0223 3.41517 3.21876 3.21871C3.41522 3.02225 3.71823 2.99719 3.94141 3.14449L4.03126 3.21871L7.50001 6.68746L10.9688 3.21871Z" fill="currentColor"></path></svg>
            </button>
          </div>

          <button v-if="!showAddSub && !subtasks.length" class="jv-add-child-btn" @click="showAddSub=true">
            <Plus class="size-2.5" />
            Add Subtasks
          </button>
        </div>

        <!-- Linked Tasks -->
        <div v-if="links.length || showAddLink" class="jv-section">
          <div class="jv-section-title">Linked {{ taskWord.toLowerCase() }}s</div>

          <div v-if="showAddLink" class="jv-add-row jv-add-row--link">
            <div class="jv-st-pill-wrap">
              <FieldDropdown width="w-40">
                <template #trigger>
                  <button class="jv-add-chip">{{ newLinkType }}<ChevronDown class="size-2" /></button>
                </template>
                <DropdownItem class="capitalize" v-for="lt in LINK_TYPES" :key="lt" :active="newLinkType===lt" @click="newLinkType=lt">{{ lt }}</DropdownItem>
              </FieldDropdown>
            </div>
            <div class="jv-link-search">
              <Search class="size-3 shrink-0 text-muted" />
              <input v-model="linkQ" @input="searchLink" :placeholder="`Search ${taskWord.toLowerCase()}s…`" class="jv-dd-input"/>
            </div>
            <button class="jv-btn-cancel" @click="showAddLink=false;linkQ='';linkResults=[]">Cancel</button>
            <div v-if="linkResults.length" class="jv-link-results">
              <div v-for="r in linkResults" :key="r.name" class="jv-link-result" @click="confirmLink(r)">
                <span class="jv-st-key">{{ r.task_key }}</span>
                <span class="flex-1 truncate" style="font-size:var(--text-sm);color:var(--foreground)">{{ r.title }}</span>
                <span class="jv-st-status" :style="{ background: wfColor(r.status)+'1A', color: wfColor(r.status) }">{{ r.status }}</span>
              </div>
            </div>
          </div>

          <template v-if="links.length">
            <div v-for="(group, type) in groupedLinks" :key="type">
              <div class="jv-link-type">{{ type }}</div>
              <div v-for="lk in group" :key="lk.linked_task" class="jv-link-row">
                <Link2 class="size-3 shrink-0 text-primary-400" />
                <span class="jv-st-key">{{ lk.linked_task_key }}</span>
                <span class="flex-1 truncate" style="font-size:var(--text-sm);color:var(--foreground)">{{ lk.linked_task_title }}</span>
                <span v-if="lk.linked_task_status" class="jv-st-status" :style="{ background: wfColor(lk.linked_task_status)+'1A', color: wfColor(lk.linked_task_status) }">{{ lk.linked_task_status }}</span>
                <button class="jv-remove-btn" @click="deleteLink(lk)" title="Remove">
                  <X class="size-2" />
                </button>
              </div>
            </div>
          </template>
          <div v-else-if="!showAddLink" class="jv-linked-empty">
            <span>No linked {{ taskWord.toLowerCase() }}s.</span>
            <button class="jv-add-link-btn" @click="showAddLink=true">Link a {{ taskWord.toLowerCase() }}</button>
          </div>
        </div>

        <!-- ERPNext References -->
        <div class="jv-section">
          <div class="jv-section-title">
            <span>References</span>
            <button class="jv-section-add-btn" @click="showAddRef = !showAddRef" title="Add reference">
              <Plus class="size-2.5" />
            </button>
          </div>

          <!-- Add reference row -->
          <div v-if="showAddRef" class="jv-ref-add-row">
            <div class="jv-ref-selects">
              <select v-model="refDoctype" class="jv-ref-select" @change="refQuery=''; refResults=[]">
                <option value="">Select doctype…</option>
                <option v-for="dt in allowedDoctypes" :key="dt" :value="dt">{{ dt }}</option>
              </select>
              <div v-if="refDoctype" class="jv-ref-search-wrap">
                <Search class="size-3 shrink-0 text-muted" />
                <input
                  v-model="refQuery"
                  class="jv-dd-input"
                  :placeholder="`Search ${refDoctype}…`"
                  @input="debouncedRefSearch"
                />
              </div>
            </div>
            <div v-if="refResults.length" class="jv-ref-results">
              <div
                v-for="r in refResults" :key="r.name"
                class="jv-ref-result"
                @click="addRef(r)"
              >
                <span class="jv-ref-doctype-badge">{{ r.doctype.split(' ').map(w=>w[0]).join('') }}</span>
                <span class="jv-ref-result-name">{{ r.name }}</span>
                <span v-if="r.label !== r.name" class="jv-ref-result-label">{{ r.label }}</span>
              </div>
            </div>
            <button class="jv-btn-cancel w-fit" @click="showAddRef=false; refQuery=''; refResults=[]">Cancel</button>
          </div>

          <!-- References list -->
          <div v-if="issueRefs.length" class="jv-refs-list">
            <div v-for="ref in issueRefs" :key="ref.name" class="jv-ref-row">
              <span class="jv-ref-doctype-badge">{{ ref.ref_doctype.split(' ').map(w=>w[0]).join('') }}</span>
              <div class="jv-ref-info">
                <span class="jv-ref-doctype-label">{{ ref.ref_doctype }}</span>
                <ReferencePreviewCard :doctype="ref.ref_doctype" :name="ref.ref_name" :project="issue.project">
                  <template #trigger>
                    <button
                      type="button"
                      class="jv-ref-link"
                      @click="openErpDoc(ref.ref_doctype, ref.ref_name)"
                    >
                      {{ ref.ref_name }}
                      <span v-if="ref.ref_label !== ref.ref_name" class="jv-ref-sublabel">· {{ ref.ref_label }}</span>
                      <ExternalLink class="size-2.5 shrink-0" />
                    </button>
                  </template>
                </ReferencePreviewCard>
              </div>
              <button class="jv-remove-btn" @click="removeRef(ref)" title="Remove">
                <X class="size-2" />
              </button>
            </div>
          </div>
          <div v-else-if="!showAddRef" class="jv-linked-empty">
            <span>No references yet.</span>
            <button class="jv-add-link-btn" @click="showAddRef=true">Add reference</button>
          </div>
        </div>

        <!-- Activity -->
        <div class="jv-section jv-section--activity">
          <div class="jv-section-title">Activity</div>
          <div class="jv-tabs">
            <button v-for="t in tabs" :key="t.id" class="jv-tab" :class="{ active: activeTab===t.id }" @click="activeTab=t.id">
              {{ t.label }}
              <span v-if="t.count != null" class="jv-tab-n">{{ t.count }}</span>
            </button>
          </div>

          <!-- Comments -->
          <div v-if="activeTab==='comments'">
            <div class="jv-compose">
              <span class="jv-me-av">{{ myInitials }}</span>
              <div class="jv-composer" :class="{ focused: commentFocused }">
                <MentionInput
                  ref="composerEl"
                  v-model="newComment"
                  :members="store.projectMembers || []"
                  placeholder="Add a comment… (@ to mention, ⌘↵ to submit)"
                  @focus="commentFocused = true"
                  @blur="commentFocused = !!newComment"
                  @submit="postComment"
                />
                <Transition name="jv-slide">
                  <div v-if="commentFocused||newComment" class="jv-composer-bar">
                    <span class="jv-hint">⌘↵ to submit</span>
                    <button @click="commentFocused=false;newComment=''" class="jv-btn-cancel">Discard</button>
                    <button @click="postComment" :disabled="!newComment.trim()" class="jv-btn-save">Save</button>
                  </div>
                </Transition>
              </div>
            </div>
            <div v-if="comments.length" class="jv-comments">
              <div v-for="c in comments" :key="c.name" class="jv-comment" :class="{ 'jv-comment--editing': editingComment === c.name }">
                <span class="jv-av jv-av-comment" :style="{ background: aColor(c.user) }">{{ (c.user === 'Guest' && c.guest_name ? c.guest_name : c.user)?.charAt(0)?.toUpperCase()||'?' }}</span>
                <div class="flex-1 min-w-0">
                  <div class="jv-comment-meta">
                    <span class="jv-comment-name">{{ c.user === 'Guest' && c.guest_name ? `${c.guest_name} (via share link)` : shortUser(c.user) }}</span>
                    <span class="jv-comment-time">{{ fmtRel(c.creation) }}</span>
                    <!-- Edit / Delete actions (only for comment author or admins) -->
                    <div v-if="c.user === currentUser || isProjectAdmin" class="jv-comment-actions">
                      <button class="jv-comment-action" title="Edit" @click.stop="startEditComment(c)">
                        <svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/></svg>
                      </button>
                      <button class="jv-comment-action jv-comment-action--delete" title="Delete" @click.stop="deleteCommentConfirm(c)">
                        <svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/></svg>
                      </button>
                    </div>
                  </div>
                  <!-- Normal view -->
                  <template v-if="editingComment !== c.name">
                    <div class="jv-comment-body" v-html="renderComment(c.comment_text)" @click="onCommentMentionClick"/>
                  </template>
                  <!-- Edit mode -->
                  <template v-else>
                    <div class="jv-composer jv-comment-edit-box">
                      <MentionInput
                        v-model="editCommentText"
                        :members="store.projectMembers || []"
                        placeholder="Edit comment…"
                        @submit="saveEditComment(c)"
                      />
                    </div>
                    <div class="jv-composer-bar">
                      <span class="jv-hint">⌘↵ to save</span>
                      <button @click="cancelEditComment" class="jv-btn-cancel">Cancel</button>
                      <button @click="saveEditComment(c)" :disabled="!editCommentText.trim()" class="jv-btn-save">Save</button>
                    </div>
                  </template>
                </div>
              </div>
            </div>
            <div v-else class="jv-no-comments">No comments yet. Be the first to add a comment.</div>
          </div>

          <!-- History -->
          <div v-if="activeTab==='history'">
            <div v-if="!history.length" class="jv-no-comments">No activity recorded yet.</div>
            <div v-else>
              <div v-for="(grp, date) in groupedHistory" :key="date">
                <div class="jv-hist-date">{{ date }}</div>
                <div v-for="a in grp" :key="a.name" class="jv-hist-row">
                  <div class="jv-hist-dot"/>
                  <p class="jv-hist-text"><strong>{{ shortUser(a.user) }}</strong> {{ activityText(a) }}</p>
                  <span class="jv-hist-time">{{ fmtRel(a.creation) }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

      </div><!-- /jv-main -->

      <!-- ─── RIGHT: SIDEBAR ─── -->
      <aside class="jv-sidebar">

        <!-- STATUS -->
        <div class="jv-sb-field jv-sb-field--status">
          <div class="jv-sb-label">Status</div>
          <div class="jv-sb-val"><div class="jv-sb-pill-wrap">
          <FieldDropdown>
            <template #trigger>
              <button class="jv-sb-inline-btn right-btn">
                <div class="jv-sb-inline-btn-content">
                  <span class="jv-sb-dot" :style="{ background: statusColor }"/>
                  <span>{{ issue.status }}</span>
                </div>
                <svg class="jv-sb-inline-btn-chevron" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7"/></svg>
              </button>
            </template>
            <DropdownItem v-for="s in store.workflowStates" :key="s.name" :active="issue.status===s.name" @click="setField('status',s.name)">
              <span class="w-2 h-2 rounded-sm shrink-0" :style="{ background: s.color }"/>{{ s.name }}
            </DropdownItem>
            <!-- Workflow config is BP Admin-only server-side (update_project_workflow
                 requires "BP Admin") — hidden for everyone else, including a
                 non-member viewing this task only via the task-assignee override
                 (store.myRole is null for them, never 'Admin'), so this never
                 dangles an action that would just 403. -->
            <template v-if="store.myRole === 'Admin'">
              <div class="jv-dd-sep"/>
              <template v-if="!showNewStatus">
                <div @click.stop="showNewStatus=true">
                  <DropdownItem>
                    <Plus class="size-2.5" /><span style="color:var(--muted)">Create status</span>
                  </DropdownItem>
                </div>
              </template>
              <template v-else>
                <div class="jv-inline-create" @click.stop>
                  <input v-model="newStatusName" class="jv-ic-input" placeholder="Status name" autofocus @keydown.enter.prevent="createStatus" @keydown.escape="showNewStatus=false"/>
                  <div class="jv-ic-colors">
                    <button v-for="c in STATUS_COLORS" :key="c" class="jv-ic-swatch" :class="{ active: newStatusColor===c }" :style="{ background: c }" @click.stop="newStatusColor=c"/>
                  </div>
                  <div class="jv-ic-row">
                    <select v-model="newStatusCategory" class="jv-ic-select">
                      <option value="unstarted">Unstarted</option>
                      <option value="started">Started</option>
                      <option value="completed">Completed</option>
                      <option value="cancelled">Cancelled</option>
                    </select>
                    <button class="jv-ic-save" :disabled="!newStatusName.trim()" @click.stop="createStatus">Add</button>
                  </div>
                </div>
              </template>
              <div class="jv-dd-sep"/>
              <DropdownItem @click="goToSettings('workflow')">
                <span style="color:var(--muted)">Manage workflow…</span>
              </DropdownItem>
            </template>
          </FieldDropdown>
          </div></div>
        </div>

        <div class="jv-sb-sep"/>

        <!-- PRIORITY -->
        <div class="jv-sb-field">
          <div class="jv-sb-label">Priority</div>
          <div class="jv-sb-val"><div class="jv-sb-pill-wrap">
          <FieldDropdown>
            <template #trigger>
              <button class="jv-sb-inline-btn">
                <div class="jv-sb-inline-btn-content">
                  <PriorityIcon :priority="issue.priority"/>
                  <span :class="issue.priority ? '' : 'jv-sb-unset'">{{ issue.priority || 'None' }}</span>
                </div>
                <svg class="jv-sb-inline-btn-chevron" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7"/></svg>
              </button>
            </template>
            <DropdownItem v-for="p in PRIORITIES" :key="p.value" :active="issue.priority===p.value" @click="setField('priority',p.value)">
              <PriorityIcon :priority="p.value"/><span class="text-foreground">{{ p.label }}</span>
            </DropdownItem>
          </FieldDropdown>
          </div></div>
        </div>

        <div class="jv-sb-sep"/>

        <!-- ASSIGNEE -->
        <div class="jv-sb-field">
          <div class="jv-sb-label">Assignee</div>
          <div class="jv-sb-val"><div class="jv-sb-pill-wrap">
          <FieldDropdown ref="assigneeDropdownRef" :close-on-select="false">
            <template #trigger>
              <button class="jv-sb-inline-btn">
                <div class="jv-sb-inline-btn-content">
                  <template v-if="issue.assignees?.length">
                    <div class="jv-av-stack">
                      <span v-for="(a, i) in issue.assignees.slice(0, 3)" :key="a.user" class="jv-av jv-av-sm jv-av-stacked" :style="{ background: aColor(a.user), zIndex: 3 - i }">{{ ini(a.full_name) }}</span>
                    </div>
                    <span class="jv-av-trigger-label">{{ issue.assignees[0].full_name?.split(' ')[0] }}<span v-if="issue.assignees.length > 1" class="jv-av-extra">+{{ issue.assignees.length - 1 }}</span></span>
                  </template>
                  <span v-else class="jv-sb-unset">Unassigned</span>
                </div>
                <svg class="jv-sb-inline-btn-chevron" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7"/></svg>
              </button>
            </template>
            <template #search>
              <div class="jv-dd-search"><input v-model="assigneeQ" autofocus placeholder="Search members…" class="jv-dd-input"/></div>
            </template>
            <DropdownItem @click="setField('assignees',[])"><div class="jv-av-empty"/>Unassigned</DropdownItem>
            <div class="jv-dd-sep"/>
            <DropdownItem v-for="m in filteredMembers" :key="m.user" :active="isAssigned(m.user)" @click="toggleAssignee(m)">
              <span class="jv-av jv-av-sm" :style="{ background: aColor(m.user) }">{{ ini(m.full_name) }}</span>
              <span class="flex-1 truncate">{{ m.full_name }}</span>
            </DropdownItem>
            <p v-if="!filteredMembers.length" class="jv-dd-empty">No members</p>
          </FieldDropdown>
          </div></div>
        </div>
          <hr class="my-3"/>
        <!-- TEAM -->
        <div class="jv-sb-field">
          <div class="jv-sb-label">Team</div>
          <div class="jv-sb-val"><div class="jv-sb-pill-wrap">
          <FieldDropdown>
            <template #trigger>
              <button class="jv-sb-inline-btn">
                <div class="jv-sb-inline-btn-content">
                  <template v-if="selectedTeam">
                    <span class="jv-team-dot" :style="{ background: selectedTeam.team_color }"/>
                    <span>{{ selectedTeam.team_name }}</span>
                  </template>
                  <span v-else class="jv-sb-unset">No team</span>
                </div>
                <svg class="jv-sb-inline-btn-chevron" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7"/></svg>
              </button>
            </template>
            <DropdownItem :active="!issue.team" @click="setField('team', null)">No team</DropdownItem>
            <DropdownItem v-for="t in store.teams" :key="t.name" :active="issue.team === t.name" @click="setField('team', t.name)">
              <span class="jv-team-dot" :style="{ background: t.team_color }"/>{{ t.team_name }}
            </DropdownItem>
            <p v-if="!store.teams.length" class="jv-dd-empty">No teams yet</p>
            <div class="jv-dd-sep"/>
            <DropdownItem @click="router.push('/workspace/teams')">
              <span style="color:var(--muted)">Manage teams…</span>
            </DropdownItem>
          </FieldDropdown>
          </div></div>
        </div>

        <!-- APPROVAL -->
        <div class="jv-sb-field mt-3" v-if="issue.approval_status && issue.approval_status !== 'Approval Not Required'">
          <div class="jv-sb-label">Approval</div>
          <!-- Read-only state uses the same .jv-sb-static row every other
               non-editable field uses (Reporter), so the rail keeps one
               34px rhythm instead of this row free-styling its own height. -->
          <div class="jv-sb-val border rounded-md shadow-sm">
            <div class="jv-sb-static">
              <span class="jv-sb-chip" :class="approvalChipClass">{{ issue.approval_status }}</span>
              <span v-if="issue.approver" class="jv-sb-sub font-medium text-gray-800" :title="issue.approver">
                {{ issue.approver_name || shortUser(issue.approver) }}
              </span>
            </div>
            <div v-if="issue.approval_status === 'Pending' && issue.approver === store.currentUser?.user"
                 class="jv-sb-actions">
              <button class="jv-sb-action jv-sb-action--ok" @click="doApprove">Approve</button>
              <button class="jv-sb-action jv-sb-action--no" @click="showRejectInput = true">Reject</button>
            </div>
            <div v-if="showRejectInput" class="jv-sb-actions">
              <input v-model="rejectReason" class="jv-sb-input" placeholder="Reason…" @keydown.enter="doReject" />
              <button class="jv-sb-action" @click="showRejectInput = false">Cancel</button>
            </div>
          </div>
        </div>
        <div v-else-if="store.hasCapability('bp_manager')" class="jv-sb-field">
          <div class="jv-sb-label">Approval</div>
          <!-- Requesting approval is an ACTION, so it gets the interactive
               affordance (.jv-sb-inline-btn) the other editable fields have,
               not bare muted text that reads as a disabled placeholder. -->
          <div class="jv-sb-val">
            <button v-if="!showApproverSelect" class="jv-sb-inline-btn" @click="showApproverSelect = true">
              <div class="jv-sb-inline-btn-content">
                <span class="jv-sb-unset">Request approval…</span>
              </div>
              <svg class="jv-sb-inline-btn-chevron" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7"/></svg>
            </button>
            <template v-else>
              <select v-model="selectedApprover" class="jv-sb-select">
                <option value="">Select approver…</option>
                <option v-for="m in store.projectMembers" :key="m.user" :value="m.user">{{ m.full_name }}</option>
              </select>
              <div class="jv-sb-actions">
                <button class="jv-sb-action jv-sb-action--ok" :disabled="!selectedApprover" @click="doRequestApproval">Send</button>
                <button class="jv-sb-action" @click="showApproverSelect = false">Cancel</button>
              </div>
            </template>
          </div>
        </div>

        <!-- RESOLUTION (only once the task is in a completed status) -->
        <div v-if="isCompleted(issue.status)" class="jv-sb-field">
          <div class="jv-sb-label">Resolution</div>
          <div class="jv-sb-val right-btn"><div class="jv-sb-pill-wrap">
          <FieldDropdown>
            <template #trigger>
              <button class="jv-sb-inline-btn">
                <div class="jv-sb-inline-btn-content">
                  <span :class="issue.resolution ? '' : 'jv-sb-unset'">{{ issue.resolution || 'Done' }}</span>
                </div>
                <svg class="jv-sb-inline-btn-chevron" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7"/></svg>
              </button>
            </template>
            <DropdownItem v-for="r in RESOLUTIONS" :key="r" :active="(issue.resolution||'Done')===r" @click="setField('resolution', r)">
              <span class="text-foreground">{{ r }}</span>
            </DropdownItem>
          </FieldDropdown>
          </div></div>
        </div>

        <!-- TASK TYPE -->
        <div class="jv-sb-field">
          <div class="jv-sb-label">Task Type</div>
          <div class="jv-sb-val"><div class="jv-sb-pill-wrap">
          <FieldDropdown>
            <template #trigger>
              <button class="jv-sb-inline-btn">
                <div class="jv-sb-inline-btn-content">
                  <span class="jv-type-badge" :style="{ background: taskTypeColor }">{{ issue.task_type?.charAt(0) }}</span>
                  <span :class="issue.task_type ? '' : 'jv-sb-unset'">{{ issue.task_type || 'None' }}</span>
                </div>
                <svg class="jv-sb-inline-btn-chevron" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7"/></svg>
              </button>
            </template>
            <DropdownItem v-for="t in store.taskTypes" :key="t.name" :active="issue.task_type===t.name" @click="setField('task_type',t.name)">
              <span class="jv-type-badge" :style="{ background: t.color }">{{ t.name.charAt(0) }}</span>{{ t.name }}
            </DropdownItem>
            <!-- update_project_issue_types requires BP Admin server-side — same
                 rationale as the workflow dropdown above. -->
            <template v-if="store.myRole === 'Admin'">
              <div class="jv-dd-sep"/>
              <template v-if="!showNewType">
                <div @click.stop="showNewType=true">
                  <DropdownItem>
                    <Plus class="size-2.5" /><span style="color:var(--muted)">Create task type</span>
                  </DropdownItem>
                </div>
              </template>
              <template v-else>
                <div class="jv-inline-create" @click.stop>
                  <input v-model="newTypeName" class="jv-ic-input" placeholder="Type name" autofocus @keydown.enter.prevent="createTaskType" @keydown.escape="showNewType=false"/>
                  <div class="jv-ic-colors">
                    <button v-for="c in STATUS_COLORS" :key="c" class="jv-ic-swatch" :class="{ active: newTypeColor===c }" :style="{ background: c }" @click.stop="newTypeColor=c"/>
                  </div>
                  <div class="jv-ic-row">
                    <button class="jv-ic-save" :disabled="!newTypeName.trim()" @click.stop="createTaskType">Add</button>
                  </div>
                </div>
              </template>
              <div class="jv-dd-sep"/>
              <DropdownItem @click="goToSettings('types')">
                <span style="color:var(--muted)">Manage task types…</span>
              </DropdownItem>
            </template>
          </FieldDropdown>
          </div></div>
        </div>

        <!-- SPRINT -->
        <div v-if="store.sprints?.length" class="jv-sb-field">
          <div class="jv-sb-label">Sprint</div>
          <div class="jv-sb-val"><div class="jv-sb-pill-wrap">
          <FieldDropdown>
            <template #trigger>
              <button class="jv-sb-inline-btn">
                <div class="jv-sb-inline-btn-content">
                  <Zap class="size-3 shrink-0" :style="{ color: issue.sprint ? 'var(--warning)' : 'var(--muted)' }" />
                  <span :class="issue.sprint ? '' : 'jv-sb-unset'">{{ issue.sprint ? sprintLabel(issue.sprint) : 'None' }}</span>
                </div>
                <svg class="jv-sb-inline-btn-chevron" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7"/></svg>
              </button>
            </template>
            <DropdownItem :active="!issue.sprint" @click="setField('sprint',null)"><span style="color:var(--muted)">No sprint</span></DropdownItem>
            <div class="jv-dd-sep"/>
            <DropdownItem v-for="s in store.activeSprints" :key="s.name" :active="issue.sprint===s.name" @click="setField('sprint',s.name)">{{ s.sprint_name }}</DropdownItem>
          </FieldDropdown>
          </div></div>
        </div>

        <!-- EPIC (read-only) -->
        <div v-if="issue.epic || issue.epic_title" class="jv-sb-field">
          <div class="jv-sb-label">Epic</div>
          <div class="jv-sb-static">
            <span v-if="issue.epic_title" class="jv-epic-tag" :style="{ background: `color-mix(in oklab, ${issue.epic_color || 'var(--accent)'} 10%, transparent)`, color: issue.epic_color || 'var(--accent)', borderColor: `color-mix(in oklab, ${issue.epic_color || 'var(--accent)'} 19%, transparent)` }">{{ issue.epic_title }}</span>
            <span v-else class="jv-sb-unset">None</span>
          </div>
        </div>

        <!-- REPORTER (read-only) -->
        <div class="jv-sb-field">
          <div class="jv-sb-label">Reporter</div>
          <div class="jv-sb-static border py-1 rounded-md shadow-sm">
            <template v-if="issue.reporter_name || issue.reporter || issue.owner">
              <span class="jv-av jv-av-sm" :style="{ background: aColor(issue.reporter || issue.owner || '') }">{{ ini(issue.reporter_name || shortUser(issue.reporter || issue.owner || '')) }}</span>
              <span style="font-size:var(--text-base);color:var(--foreground)">{{ issue.reporter_name || shortUser(issue.reporter || issue.owner || '') }}</span>
            </template>
            <span v-else class="jv-sb-unset">—</span>
          </div>
        </div>

        <div class="jv-sb-sep"/>

        <!-- START DATE -->
        <div class="jv-sb-field">
          <div class="jv-sb-label">Start date</div>
          <div class="jv-sb-val jv-sb-val--date border rounded-md shadow-sm">
            <DatePicker :modelValue="issue.start_date||null" placeholder="None" @update:modelValue="val=>setField('start_date',val||null)"/>
          </div>
        </div>

        <!-- DUE DATE -->
        <div class="jv-sb-field" :class="{ 'jv-overdue': isOverdue }">
          <div class="jv-sb-label" :class="{ 'jv-lbl-danger': isOverdue }">Due date</div>
          <div class="jv-sb-val jv-sb-val--date border rounded-md shadow-sm">
            <DatePicker :modelValue="issue.due_date||null" placeholder="None" @update:modelValue="val=>setField('due_date',val||null)"/>
          </div>
        </div>

        <!-- REPEATS -->
        <div class="jv-sb-sep"/>
        <div class="jv-sb-field">
          <div class="jv-sb-label">Repeats</div>
          <div class="jv-sb-val">
            <Switch :modelValue="!!issue.is_recurring" @update:modelValue="val => setField('is_recurring', val ? 1 : 0)"/>
          </div>
        </div>
        <template v-if="issue.is_recurring">
          <div class="jv-sb-field">
            <div class="jv-sb-label">Frequency</div>
            <div class="jv-sb-val">
              <FieldDropdown width="w-36">
                <template #trigger>
                  <span class="text-sm text-foreground">{{ issue.recurrence_frequency || 'Choose…' }}</span>
                </template>
                <DropdownItem v-for="f in ['Daily','Weekly','Biweekly','Monthly']" :key="f" @click="setField('recurrence_frequency', f)">
                  {{ f }}
                </DropdownItem>
              </FieldDropdown>
            </div>
          </div>
          <div class="jv-sb-field">
            <div class="jv-sb-label">Repeat until</div>
            <div class="jv-sb-val jv-sb-val--date">
              <DatePicker :modelValue="issue.recurrence_end_date||null" placeholder="Optional" @update:modelValue="val=>setField('recurrence_end_date',val||null)"/>
            </div>
          </div>
        </template>

        <!-- TIME & BILLING -->
        <template v-if="store.currentProject?.project_type !== 'internal'">
          <div class="jv-sb-sep"/>
          <div class="jv-sb-field">
            <div class="jv-sb-label">Est. hours</div>
            <div class="jv-sb-val border rounded-md shadow-sm">
              <input type="number" min="0" step="0.5" class="jv-hrs-input"
                :value="issue.estimated_hours || ''"
                placeholder="—"
                @change="e => setField('estimated_hours', parseFloat(e.target.value) || null)" />
            </div>
          </div>
          <div v-if="issue.actual_hours" class="jv-sb-field">
            <div class="jv-sb-label">Actual hours</div>
            <div class="jv-sb-static border rounded-md shadow-sm" style="font-size:var(--text-base);color:var(--foreground)">{{ issue.actual_hours }}h</div>
          </div>
          <div class="jv-sb-field">
            <div class="jv-sb-label" style="display:flex;align-items:center;gap:6px">
              Timer
              <span v-if="!timerEnabled"
                class="inline-flex items-center gap-1 text-xs font-semibold px-1 py-0.5 rounded
                       bg-[var(--surface-secondary)] text-muted uppercase tracking-wider">
                {{ ent.requiredPlanFor('time_tracking') }}
              </span>
            </div>
            <div class="jv-sb-val">
              <button v-if="!isTimerOnThisTask" class="jv-timer-btn"
                :disabled="!timerEnabled || timerBusy" @click="onStartTimer">
                <Play class="size-3" /> Start
              </button>
              <div v-else class="jv-timer-running">
                <button class="jv-timer-stop" :disabled="timerBusy" @click="onStopTimer">
                  <Square class="size-2.5" />
                </button>
                <span class="jv-timer-elapsed">{{ timerElapsedLabel }}</span>
              </div>
            </div>
          </div>
          <div v-if="timerEnabled" class="jv-sb-field">
            <div class="jv-sb-label" style="display:flex;align-items:center;justify-content:space-between">
              <span>Time log{{ timeEntries.length ? ` (${timeEntries.length})` : '' }}</span>
              <button class="jv-timelog-toggle" @click="timeLogOpen = !timeLogOpen">
                {{ timeLogOpen ? 'Hide' : (timeEntries.length ? 'Show' : 'Log time') }}
              </button>
            </div>
            <div v-if="timeLogOpen" class="jv-sb-val" style="display:block">
              <div class="jv-timelog-add">
                <input type="number" min="0" step="0.25" class="jv-hrs-input" v-model="newLogHours"
                  placeholder="Hours" @keydown.enter="submitManualLog" />
                <DatePicker v-model="newLogDate" placeholder="Today" style="width:120px" />
                <button class="jv-timer-btn" :disabled="!newLogHours || timeLogBusy" @click="submitManualLog">
                  <Plus class="size-3" /> Add
                </button>
              </div>
              <div v-if="timeEntries.length" class="jv-timelog-list">
                <div v-for="row in timeEntries" :key="row.name" class="jv-timelog-row">
                  <span class="jv-timelog-date">{{ fmtDate(row.from_time) }}</span>
                  <template v-if="editingLog === row.name">
                    <input type="number" min="0" step="0.25" class="jv-hrs-input jv-timelog-edit"
                      v-model="editingHours" @keydown.enter="saveEditLog(row)" @blur="saveEditLog(row)" autofocus />
                  </template>
                  <button v-else class="jv-timelog-hours" :disabled="!row.editable"
                    :title="row.editable ? 'Click to edit' : 'Submitted — read only'"
                    @click="row.editable && startEditLog(row)">{{ row.hours }}h</button>
                  <button v-if="row.editable" class="jv-timelog-del" title="Delete entry" @click="removeTimeEntry(row)">
                    <Trash2 class="size-3" />
                  </button>
                </div>
              </div>
            </div>
          </div>
          <div class="jv-sb-field">
            <div class="jv-sb-label">Billable</div>
            <div class="jv-sb-val">
              <button class="jv-toggle" :class="{ active: issue.billable }" @click="setField('billable', issue.billable ? 0 : 1)">
                <span class="jv-toggle-thumb"/>
              </button>
            </div>
          </div>
        </template>

        <!-- LABELS -->
        <div v-if="store.projectLabels?.length" class="jv-sb-field">
          <div class="jv-sb-label">Labels</div>
          <div class="jv-labels-wrap">
            <span v-for="lbl in issueLabels" :key="lbl" class="jv-lbl-tag" :style="getLabelStyle(lbl)">{{ lbl }}</span>
            <FieldDropdown width="w-44" :close-on-select="false">
              <template #trigger>
                <button class="jv-add-label-btn">
                  <Plus class="size-2.5" />{{ (issue.labels || []).length ? '' : 'Add' }}
                </button>
              </template>
              <DropdownItem v-for="l in store.projectLabels" :key="l.id || l.label" :active="issueLabels.includes(l.label)" @click="toggleLabel(l.label)">
                <span class="jv-lbl-dot" :style="{ background: l.color }"/>{{ l.label }}
              </DropdownItem>
              <!-- update_project_labels requires BP Admin server-side — same
                   rationale as the workflow/task-type dropdowns above. -->
              <template v-if="store.myRole === 'Admin'">
                <div class="jv-dd-sep"/>
                <template v-if="!showNewLabel">
                  <DropdownItem @click="showNewLabel=true"><Plus class="size-2.5"/><span style="color:var(--muted)">Create label</span></DropdownItem>
                </template>
                <template v-else>
                  <div class="jv-inline-create" @click.stop>
                    <input v-model="newLabelName" class="jv-ic-input" placeholder="Label name" autofocus @keydown.enter.prevent="createLabel" @keydown.escape="showNewLabel=false"/>
                    <div class="jv-ic-colors">
                      <button v-for="c in LABEL_COLORS" :key="c" class="jv-ic-swatch" :class="{ active: newLabelColor===c }" :style="{ background: c }" @click.stop="newLabelColor=c"/>
                    </div>
                    <div class="jv-ic-row">
                      <button class="jv-ic-save" :disabled="!newLabelName.trim()" @click.stop="createLabel">Add</button>
                    </div>
                  </div>
                </template>
                <div class="jv-dd-sep"/>
                <DropdownItem @click="goToSettings('labels')">
                  <span style="color:var(--muted)">Manage labels…</span>
                </DropdownItem>
              </template>
            </FieldDropdown>
          </div>
        </div>

        <!-- CUSTOM FIELDS -->
        <template v-if="activeCustomFields.length">
          <div class="jv-sb-sep"/>
          <div v-for="field in activeCustomFields" :key="field.id" class="jv-sb-field">
            <div class="jv-sb-label">
              {{ field.label }}<span v-if="field.required" style="color:var(--danger);margin-left:2px">*</span>
              <span v-if="markerColor(field)" class="inline-block size-1.5 rounded-full ml-1.5 align-middle"
                :style="{ background: markerColor(field) }" />
            </div>
            <CustomFieldInput :field="field" :modelValue="customValues[field.id]??null" :members="store.projectMembers||[]" :project-name="store.currentProject?.name" :show-label="false" :disabled="field.can_edit===false" @update:modelValue="val=>saveCustomField(field.id,val)"/>
          </div>
        </template>

        <!-- ERP links -->
        <template v-if="issue.sales_order||issue.timesheet_detail||canCreatePO">
          <div class="jv-sb-sep"/>
          <div v-if="issue.sales_order" class="jv-sb-field">
            <div class="jv-sb-label">Sales Order</div>
            <div class="jv-sb-static"><span class="jv-erp-link">{{ issue.sales_order }}</span></div>
          </div>
          <!-- Task-driven procurement — Manager+ only, and only
               once the project is linked to an ERPNext Project. -->
          <div v-if="canCreatePO" class="jv-sb-field">
            <button type="button" class="jv-erp-create-po" @click="poDrawerOpen = true">
              <ShoppingCart class="size-3.5" /> Create Purchase Order
            </button>
          </div>
        </template>

        <!-- Footer: timestamps -->
        <div class="jv-sb-footer">
          <span v-if="issue.creation">Created {{ fmtDate(issue.creation) }}</span>
          <span v-if="issue.modified">Updated {{ fmtDate(issue.modified) }}</span>
        </div>

      </aside><!-- /sidebar -->

    </div><!-- /jv-body -->
  </div><!-- /panel -->
</div>
</Teleport>

<ShareDialog v-if="issue" v-model="shareOpen" :project="issue.project" :task="issue.name" :task-title="issue.title" />

<CreatePurchaseOrderDrawer v-if="issue" v-model="poDrawerOpen" :task="issue.name" :task-title="issue.title"
  @created="onPoCreated" />
<MoneyDrawer v-model:open="moneyDrawerOpen" :project="issue?.project" doctype="Purchase Order" :name="moneyDrawerPo" />
<MoneyDrawer v-model:open="refDrawerOpen" :project="issue?.project" :doctype="refDrawerDoctype" :name="refDrawerName" />

</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { debounce } from 'lodash'
import { LayoutGrid, MoreHorizontal, Copy, Trash2, X, ChevronDown, MessageCircle, ClipboardList, Link2, Check, UserRound, Plus, Search, ExternalLink, Zap, Loader2, Bell, BellOff, Eye, EyeOff, Share2, Play, Square, ShoppingCart } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import ShareDialog from '@/components/ShareDialog.vue'
import CreatePurchaseOrderDrawer from '@/components/CreatePurchaseOrderDrawer.vue'
import MoneyDrawer from '@/components/MoneyDrawer.vue'
import { useProjectStore } from '@/stores/project'
import { useTimerStore } from '@/stores/timer'
import { useEntitlementsStore } from '@/stores/entitlements'
import { usePresence } from '@/composables/usePresence'
import { updateTask, addComment, editComment, deleteComment, createTask, addTaskLink, removeTaskLink, searchTasks, updateProjectWorkflow, updateProjectLabels, updateProjectIssueTypes, getAllowedDoctypes, searchErpDocuments, addReference, removeReference, getMutedItems, setMute, watchTask, unwatchTask, getTaskWatchers, duplicateTask, requestApproval, approveTask, rejectTask, getChecklist, addChecklistItem, updateChecklistItem, toggleChecklistItem, removeChecklistItem, logTime, listTimeEntries, updateTimeEntry, deleteTimeEntry } from '@/utils/api'
import { getActiveFields, resolveMarkerColor } from '@/utils/customFields.js'
import { PRIORITIES, avatarColor, initials } from '@/utils/constants.js'
const RESOLUTIONS = ['Done', "Won't Do", 'Duplicate', 'Cannot Reproduce', 'Obsolete']
import DatePicker from '@/components/DatePicker.vue'
import RichTextEditor from '@/components/RichTextEditor.vue'
import PriorityIcon from '@/components/PriorityIcon.vue'
import FieldDropdown from '@/components/FieldDropdown.vue'
import DropdownItem from '@/components/DropdownItem.vue'
import Switch from '@/ui/Switch.vue'
import CustomFieldInput   from '@/components/CustomFieldInput.vue'
import TaskAttachments   from '@/components/TaskAttachments.vue'
import MentionInput      from '@/components/MentionInput.vue'
import ReferencePreviewCard from '@/components/ReferencePreviewCard.vue'
import { useErpDocOpener } from '@/composables/useErpDocOpener.js'
import { getTaskWord } from '@/constants/project-templates'
import { confirmDialog } from '@/composables/useConfirmDialog'

defineEmits(['close'])
const store = useProjectStore()
const router = useRouter()
const { isOnline, stop: stopPresence } = usePresence()
const ent = useEntitlementsStore()

function goToSettings(tab) {
  const key = store.currentProject?.key
  if (key) router.push(`/workspace/${key}/settings/${tab}`)
}
const issue = computed(() => store.selectedTask)
const taskWord = computed(() => getTaskWord(store.currentProject?.template_used))

// ── Task timer ──────────────────────────────────────────────────
const timerStore = useTimerStore()
const timerBusy = ref(false)
const timerNow = ref(Date.now())
let timerTick = null
onMounted(() => {
  if (!timerStore.loaded) timerStore.refresh()
  if (!store.teams.length) store.fetchTeams()
  timerTick = setInterval(() => { timerNow.value = Date.now() }, 1000)
})
onUnmounted(() => { if (timerTick) clearInterval(timerTick); stopPresence() })

const timerEnabled = computed(() => ent.can('time_tracking'))
const isTimerOnThisTask = computed(() => timerStore.active?.task === issue.value?.name)
const timerElapsedLabel = computed(() => {
  if (!isTimerOnThisTask.value) return ''
  const started = new Date(timerStore.active.started_at).getTime()
  const secs = Math.max(0, Math.floor((timerNow.value - started) / 1000))
  const h = Math.floor(secs / 3600)
  const m = Math.floor((secs % 3600) / 60)
  const s = secs % 60
  const mm = String(m).padStart(2, '0')
  const ss = String(s).padStart(2, '0')
  return h > 0 ? `${h}:${mm}:${ss}` : `${m}:${ss}`
})

async function onStartTimer() {
  if (timerBusy.value || !issue.value) return
  timerBusy.value = true
  try {
    const res = await timerStore.start(issue.value.name)
    if (res.stopped_previous) {
      toast.info(`Stopped the timer on ${res.stopped_previous.task_key} — logged ${res.stopped_previous.elapsed_hours}h`)
    }
  } catch (e) {
    toast.error(e.message || 'Failed to start timer')
  } finally {
    timerBusy.value = false
  }
}

async function onStopTimer() {
  if (timerBusy.value) return
  timerBusy.value = true
  try {
    const res = await timerStore.stop()
    toast.success(res.logged ? `Logged ${res.elapsed_hours}h to today's timesheet` : 'Timer stopped')
  } catch (e) {
    toast.error(e.message || 'Failed to stop timer')
  } finally {
    timerBusy.value = false
  }
}

// ── Time log — manual entry + correction of already-logged rows ──────
// There was previously no way to fix a mistaken/forgotten timer entry from
// the app at all (audit 03 §C1); this panel is the fix.
const timeEntries = ref([])
const timeLogOpen = ref(false)
const timeLogBusy = ref(false)
const newLogHours = ref('')
const newLogDate = ref(null)
const editingLog = ref(null)   // name of the row currently being edited
const editingHours = ref('')

async function loadTimeEntries() {
  if (!issue.value?.name) return
  try {
    timeEntries.value = await listTimeEntries(issue.value.name)
  } catch (e) {
    console.error('Failed to load time entries:', e)
  }
}
watch(() => issue.value?.name, (n) => { timeEntries.value = []; timeLogOpen.value = false; if (n) loadTimeEntries() }, { immediate: true })

async function submitManualLog() {
  const hours = parseFloat(newLogHours.value)
  if (!hours || hours <= 0 || timeLogBusy.value) return
  timeLogBusy.value = true
  try {
    await logTime(issue.value.name, hours, newLogDate.value || null)
    newLogHours.value = ''
    newLogDate.value = null
    toast.success(`Logged ${hours}h`)
    await Promise.all([loadTimeEntries(), store.refreshTaskDetail?.()])
  } catch (e) {
    toast.error(e.message || 'Failed to log time')
  } finally {
    timeLogBusy.value = false
  }
}

function startEditLog(row) {
  editingLog.value = row.name
  editingHours.value = row.hours
}

// Bound to both @keydown.enter and @blur on the same input — removing the
// input on Enter (editingLog = null) fires a native blur, which would
// otherwise re-invoke this and send two concurrent saves of the same edit
// (observed live: the second lands mid-flight and the doc's `modified`
// timestamp has already moved, throwing TimestampMismatchError). Guard
// synchronously, before any await, so the second call is a no-op.
let savingLog = null
async function saveEditLog(row) {
  if (savingLog === row.name) return
  const hours = parseFloat(editingHours.value)
  editingLog.value = null
  if (!hours || hours <= 0 || hours === row.hours) return
  savingLog = row.name
  try {
    await updateTimeEntry(row.name, hours)
    toast.success('Time entry updated')
    await Promise.all([loadTimeEntries(), store.refreshTaskDetail?.()])
  } catch (e) {
    toast.error(e.message || 'Failed to update time entry')
  } finally {
    savingLog = null
  }
}

async function removeTimeEntry(row) {
  if (!await confirmDialog(`Delete this ${row.hours}h entry?`, { danger: true })) return
  try {
    await deleteTimeEntry(row.name)
    toast.success('Time entry deleted')
    await Promise.all([loadTimeEntries(), store.refreshTaskDetail?.()])
  } catch (e) {
    toast.error(e.message || 'Failed to delete time entry')
  }
}

// Programmatic assignee-picker open, for the global `A` keyboard shortcut.
const assigneeDropdownRef = ref(null)
function openAssigneePicker() {
  assigneeDropdownRef.value?.open()
}
defineExpose({ openAssigneePicker })

// Per-issue notification mute
const muted = ref(false)
watch(() => issue.value?.name, async (name) => {
  muted.value = false
  if (!name) return
  try {
    const m = await getMutedItems()
    muted.value = (m.tasks || []).includes(name)
  } catch {}
}, { immediate: true })

async function toggleMute() {
  const name = issue.value?.name
  if (!name) return
  const next = !muted.value
  muted.value = next
  try { await setMute({ task: name, muted: next ? 1 : 0 }) }
  catch { muted.value = !next }
}

// Per-issue watch (follow) — initialised from get_task's watching/watcher_count
const watching = computed(() => !!issue.value?.watching)
const watcherCount = computed(() => issue.value?.watcher_count || 0)
// Declared here, not down by loadChecklist() where they read most naturally
// (see that function's own comment for what checklistSeq is for) — this
// codebase's known TDZ footgun: the immediate:true watch a few lines below
// calls loadChecklist() SYNCHRONOUSLY during setup(), which is before a
// `const`/`let` further down the file has executed, throwing "Cannot access
// before initialization". Hoisting the two bindings the function closes over
// above the watch is enough; the function declaration itself is hoisted by
// JS regardless of where it's written.
const checklistItems = ref([])
let checklistSeq = 0
async function toggleWatch() {
  const t = issue.value
  if (!t?.name) return
  const next = !t.watching
  t.watching = next
  t.watcher_count = (t.watcher_count || 0) + (next ? 1 : -1)
  try { next ? await watchTask(t.name) : await unwatchTask(t.name) }
  catch { t.watching = !next; t.watcher_count = (t.watcher_count || 0) + (next ? -1 : 1) }
}

// Watcher list popover — lazy-fetched once per open, cached per task.
// TaskDetail is a single reused instance (App.vue mounts it with no :key),
// so switching to a different task (e.g. via a subtask/linked-task click)
// updates `issue` in place without unmounting this component — the cache
// must be reset on that transition or a later task shows a stale list.
const watcherRef      = ref(null)
const watcherList     = ref(null)
const watchersLoading = ref(false)
const watchersLoaded  = ref(false)

// { immediate: true } is load-bearing, not decoration — App.vue mounts
// TaskDetail with `v-if="store.showTaskDetail && store.selectedTask"`, so by
// the time this component's setup() runs, `issue.value.name` is ALREADY the
// real task (selectedTask only goes non-null once get_task has resolved).
// A non-immediate watch establishes ITS baseline at that same already-
// populated value, so the undefined -> name transition it's listening for
// already happened before the watcher existed to see it — the callback
// never fires on a task's first open, only on a later same-drawer subtask
// hop where .name genuinely changes again. That silently broke loadChecklist
// on every first open (nobody noticed on tasks with empty checklists) and
// would have broken the new eager watcher load below the same way.
watch(() => issue.value?.name, () => {
  watcherList.value = null
  watchersLoaded.value = false
  loadChecklist()
  // Eager, not lazy: the header now shows real stacked avatars (not just a
  // count), so the list has to exist before the dropdown is ever opened.
  // loadWatchers' own guard keeps this a no-op once cached.
  if (watcherCount.value) loadWatchers()
}, { immediate: true })

async function loadWatchers() {
  if (watchersLoaded.value || watchersLoading.value) return
  watchersLoading.value = true
  try {
    const res = await getTaskWatchers(issue.value.name)
    watcherList.value = res.watchers || []
    watchersLoaded.value = true
  } catch {
    watcherList.value = []
  } finally {
    watchersLoading.value = false
  }
}
// First 3 for the header stack — same cap the Assignee stack above uses.
const headerWatchers = computed(() => (watcherList.value || []).slice(0, 3))
// 0 (not just falsy) until watcherList genuinely resolves — otherwise the
// brief window before the eager load lands would show "+4" instead of the
// real avatars for a moment, since headerWatchers.length is 0 that whole time.
const watcherOverflow = computed(() => watcherList.value ? Math.max(0, watcherCount.value - headerWatchers.value.length) : 0)

const titleEl    = ref(null)
const composerEl = ref(null)

function getLabelStyle(labelName) {
  const lbl = (store.projectLabels || []).find(l => l.label === labelName)
  if (!lbl) return {}
  return { background: lbl.color + '18', color: lbl.color, borderColor: lbl.color + '40' }
}

async function createStatus() {
  if (!newStatusName.value.trim() || !issue.value) return
  const newState = { name: newStatusName.value.trim(), color: newStatusColor.value, category: newStatusCategory.value }
  const updated  = [...(store.workflowStates || []), newState]
  try {
    await updateProjectWorkflow(store.currentProject.name, updated)
    store.currentProject.workflow_states = updated
    // Apply the new status to current issue
    await setField('status', newState.name)
    showNewStatus.value = false
    newStatusName.value = ''
  } catch { toast.error('Failed to create status') }
}

async function createTaskType() {
  if (!newTypeName.value.trim() || !issue.value) return
  const newType = { name: newTypeName.value.trim(), color: newTypeColor.value }
  const updated = [...(store.taskTypes || []), newType]
  try {
    await updateProjectIssueTypes(store.currentProject.name, updated)
    store.currentProject.issue_types = updated
    await setField('task_type', newType.name)
    showNewType.value = false
    newTypeName.value = ''
  } catch { toast.error('Failed to create task type') }
}

async function createLabel() {
  if (!newLabelName.value.trim()) return
  const newLbl = { id: 'lbl_' + Math.random().toString(36).slice(2, 10), label: newLabelName.value.trim(), color: newLabelColor.value }
  const updated = [...(store.projectLabels || []), newLbl]
  try {
    await updateProjectLabels(store.currentProject.name, updated)
    store.currentProject.labels = updated
    // Toggle the new label onto this issue
    await toggleLabel(newLbl.label)
    showNewLabel.value = false
    newLabelName.value = ''
  } catch { toast.error('Failed to create label') }
}

async function toggleLabel(labelName) {
  const current = [...issueLabels.value]
  const idx = current.indexOf(labelName)
  if (idx >= 0) current.splice(idx, 1)
  else current.push(labelName)
  await setField('labels', current)
}


function focusComposer() {
  commentFocused.value = true
  nextTick(() => composerEl.value?.focus())
}
const moreRef    = ref(null)
const shareOpen  = ref(false)
const saveState  = ref('idle')
let   saveTimer  = null

const descEditing    = ref(false)
const activeTab      = ref('comments')
const assigneeQ      = ref('')
const stAssigneeQ    = ref('')
const showAddSub     = ref(false)
const newSubTitle    = ref('')
const newSubPriority = ref('Medium')
const showAddLink    = ref(false)
const newLinkType    = ref('relates to')
const linkQ          = ref('')
const linkResults    = ref([])

// ERPNext references
const showAddRef     = ref(false)
const refDoctype     = ref('')
const refQuery       = ref('')
const refResults     = ref([])
const allowedDoctypes = ref([])

// On-spot creation
const showNewStatus   = ref(false)
const newStatusName   = ref('')
const newStatusColor  = ref('#3b82f6')
const newStatusCategory = ref('unstarted')
const showNewLabel    = ref(false)
const newLabelName    = ref('')
const newLabelColor   = ref('#0B6BCB')
const showNewType     = ref(false)
const newTypeName     = ref('')
const newTypeColor    = ref('#3b82f6')

const STATUS_COLORS = ['#94a3b8','#3b82f6','#f59e0b','#22c55e','#ef4444','#8b5cf6','#ec4899','#06b6d4','#f97316']
const LABEL_COLORS  = ['#0B6BCB','#1F7A1F','#C41C1C','#FF8B00','#6554C0','#00B8D9','#FF5630','#36B37E','#FFAB00']
const newComment     = ref('')
const commentFocused = ref(false)
const editingComment = ref(null)   // activity name being edited
const editCommentText = ref('')

// ─── @mention display rendering (composer behaviour lives in MentionInput.vue) ──
function _escapeHtml(s) {
  return (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}
function renderComment(text) {
  // escape, then turn @[Name](uid) tokens into clickable blue mention chips + newlines
  let html = _escapeHtml(text)
  html = html.replace(/@\[([^\]]+)\]\(([^)]+)\)/g,
    (_, name, uid) => `<span class="jv-mention" role="button" tabindex="0" data-uid="${_escapeHtml(uid)}" data-name="${_escapeHtml(name)}" title="${_escapeHtml(uid)}">@${_escapeHtml(name)}</span>`)
  return html.replace(/\n/g, '<br>')
}

// Click a mention in a posted comment → drop that person into the composer
function onCommentMentionClick(e) {
  const el = e.target.closest?.('.jv-mention')
  if (!el || !el.dataset.uid) return
  const token = `@[${el.dataset.name}](${el.dataset.uid})`
  const cur = newComment.value || ''
  newComment.value = (cur && !/\s$/.test(cur) ? cur + ' ' : cur) + token + ' '
  commentFocused.value = true
  nextTick(() => composerEl.value?.focus())
}

const LINK_TYPES = ['blocks','is blocked by','clones','is cloned by','duplicates','relates to']

// ── Checklist ─────────────────────────────────────────────────────────────────
// Rewritten after a live audit found four compounding bugs:
//
// 1. Response-race: every mutation blindly did `checklistItems.value =
//    r.items`. The backend's reload-mutate-save (board.py _save_checklist)
//    guarantees the LAST-ISSUED request's response reflects the fully merged
//    state — but HTTP responses don't always arrive in request order, so a
//    slower response to an EARLIER click could land after a faster one and
//    stomp it, silently reverting a toggle the user had already made.
//    `checklistSeq` fixes this: only the response to the most-recently-
//    issued mutation is ever applied.
// 2. Ghost blank rows: blur always saved whatever text was present,
//    including empty. "Add item" -> click away without typing left a
//    permanent invisible row that still counted in the N/total denominator.
// 3. Backspace-to-delete checked the STALE `item.text` (the last-saved
//    value) instead of the input's live DOM value, so it only worked on a
//    row that had never been edited.
// 4. No optimistic toggle — checking a box waited a full round trip before
//    flipping, and no focus landed in a freshly-added row, so every "Add
//    item" click required a second click to start typing.
const checklistInputs = new Map() // item.id -> <input> element, for post-add focus
function setChecklistInputRef(id, el) {
  if (el) checklistInputs.set(id, el)
  else checklistInputs.delete(id)
}

function loadChecklist() {
  if (!issue.value?.name) { checklistItems.value = []; return }
  const mySeq = ++checklistSeq
  getChecklist(issue.value.name).then(r => {
    if (mySeq !== checklistSeq) return
    checklistItems.value = r.items || []
  }).catch(() => {})
}

const checklistDone = computed(() => checklistItems.value.filter(i => i.done).length)
const checklistPct  = computed(() => checklistItems.value.length ? Math.round(checklistDone.value / checklistItems.value.length * 100) : 0)

function addCheck() {
  if (!issue.value?.name) return
  const mySeq = ++checklistSeq
  const previousIds = new Set(checklistItems.value.map(i => i.id))
  addChecklistItem(issue.value.name, '').then(r => {
    if (mySeq !== checklistSeq) return
    checklistItems.value = r.items || []
    // The new row is whichever id wasn't there before — focus it so typing
    // can start immediately, matching "add item" feel.
    const added = checklistItems.value.find(i => !previousIds.has(i.id))
    if (added) nextTick(() => checklistInputs.get(added.id)?.focus())
  }).catch(() => {})
}
function toggleCheck(item) {
  if (!issue.value?.name) return
  // Optimistic: flip immediately so the click feels instant, reconcile (or
  // revert, on error) once the server responds.
  const prevDone = item.done
  item.done = !prevDone
  const mySeq = ++checklistSeq
  toggleChecklistItem(issue.value.name, item.id).then(r => {
    if (mySeq !== checklistSeq) return
    checklistItems.value = r.items || []
  }).catch(() => { item.done = prevDone })
}
function onChecklistBlur(item, rawText) {
  const text = (rawText || '').trim()
  // Empty on blur = discard, never persist a blank row — whether it's a
  // freshly-added item nobody typed into, or an existing one cleared out.
  if (!text) { removeCheck(item); return }
  if (text === item.text) return // unchanged — skip the network round trip
  updateCheck(item, text)
}
function updateCheck(item, text) {
  if (!issue.value?.name) return
  const mySeq = ++checklistSeq
  updateChecklistItem(issue.value.name, item.id, text).then(r => {
    if (mySeq !== checklistSeq) return
    checklistItems.value = r.items || []
  }).catch(() => {})
}
function removeCheck(item) {
  if (!issue.value?.name) return
  const mySeq = ++checklistSeq
  removeChecklistItem(issue.value.name, item.id).then(r => {
    if (mySeq !== checklistSeq) return
    checklistItems.value = r.items || []
  }).catch(() => {})
}

// Data accessors
const subtasks = computed(() => issue.value?.subtasks || [])
const links    = computed(() => issue.value?.links    || [])
const activity = computed(() => [...(issue.value?.activity||[])].sort((a,b)=>new Date(a.creation)-new Date(b.creation)))
const comments = computed(() => activity.value.filter(a=>a.action_type==='Comment'))
const history  = computed(() => activity.value.filter(a=>a.action_type!=='Comment'))

// Custom fields
const activeCustomFields = computed(() => getActiveFields(store.currentProject?.custom_fields||[]))
const issueLabels = computed(() => {
  const raw = issue.value?.labels
  if (!raw) return []
  if (Array.isArray(raw)) return raw
  try { return JSON.parse(raw) } catch { return [] }
})
const customValues = computed(() => {
  const raw = issue.value?.custom_field_values
  if (!raw) return {}
  try { return typeof raw==='string'?JSON.parse(raw):(raw||{}) } catch { return {} }
})
function markerColor(field) { return resolveMarkerColor(field, customValues.value[field.id]) }
async function saveCustomField(fieldId, value) {
  if (!issue.value) return
  const updated = { ...customValues.value, [fieldId]: value }
  if (store.selectedTask) store.selectedTask.custom_field_values = updated
  setSaving()
  try { await updateTask(issue.value.name,{custom_field_values:updated}); setSaved() }
  catch(e) { setError(); console.error('CF:',e) }
}

// Colors
const statusColor    = computed(() => store.workflowStateMap?.[issue.value?.status]?.color|| 'var(--muted)')
const taskTypeColor = computed(() => store.taskTypeMap?.[issue.value?.task_type]?.color|| 'var(--accent)')
const selectedTeam   = computed(() => store.teams.find(t => t.name === issue.value?.team) || null)
// Approval state is data, so it reads as a soft chip off the semantic ramp
// (composition law §1) — not raw palette steps, which ignored dark theme.
const approvalChipClass = computed(() => ({
  Pending:  'jv-sb-chip--warn',
  Approved: 'jv-sb-chip--ok',
  Rejected: 'jv-sb-chip--no',
}[issue.value?.approval_status] || ''))
const aColor = avatarColor
const ini    = initials
function wfColor(s) { return store.workflowStateMap?.[s]?.color|| 'var(--muted)' }
function sprintLabel(n) { return store.sprints?.find(s=>s.name===n)?.sprint_name||n }
const isOverdue = computed(() => { const d=issue.value?.due_date; return d&&new Date(d+'T00:00:00')<new Date()&&!isCompleted(issue.value?.status) })
function isCompleted(s) { return store.workflowStateMap?.[s]?.category==='completed' }

// Assignees
const filteredMembers     = computed(() => { const q=assigneeQ.value.toLowerCase(); return (store.projectMembers||[]).filter(m=>!q||m.full_name?.toLowerCase().includes(q)) })
function isAssigned(user) { return (issue.value?.assignees||[]).some(a=>a.user===user) }
async function toggleAssignee(m) {
  const user=m.user, cur=issue.value?.assignees||[]
  const updated=isAssigned(user)?cur.filter(a=>a.user!==user):[...cur,{user,full_name:m.full_name}]
  if(store.selectedTask) store.selectedTask.assignees=updated
  try { await store.updateTaskField(issue.value.name, 'assignees', updated) } catch(e){ console.error(e) }
}

// ── Approval ─────────────────────────────────────────────────────────────────
const showApproverSelect = ref(false)
const selectedApprover   = ref('')
const showRejectInput    = ref(false)
const rejectReason       = ref('')

async function doRequestApproval() {
  if (!selectedApprover.value || !issue.value) return
  try {
    await requestApproval(issue.value.name, selectedApprover.value)
    issue.value.approval_status = 'Pending'
    issue.value.approver = selectedApprover.value
    showApproverSelect.value = false
    selectedApprover.value = ''
    toast.success('Approval requested')
  } catch (e) { toast.error(e.message || 'Failed') }
}
async function doApprove() {
  if (!issue.value) return
  try {
    await approveTask(issue.value.name)
    issue.value.approval_status = 'Approved'
    toast.success('Task approved')
  } catch (e) { toast.error(e.message || 'Failed') }
}
async function doReject() {
  if (!issue.value) return
  try {
    await rejectTask(issue.value.name, rejectReason.value || undefined)
    issue.value.approval_status = 'Rejected'
    showRejectInput.value = false
    rejectReason.value = ''
    toast.success('Task rejected')
  } catch (e) { toast.error(e.message || 'Failed') }
}

// Save
function setSaving(){ saveState.value='saving'; if(saveTimer) clearTimeout(saveTimer) }
function setSaved() { saveState.value='saved';  saveTimer=setTimeout(()=>{ saveState.value='idle' },2000) }
function setError() { saveState.value='error';  saveTimer=setTimeout(()=>{ saveState.value='idle' },3000) }
async function setField(field, value) {
  if (!issue.value) return
  if (field !== 'description' && issue.value[field] === value) return
  setSaving()
  try {
    // Route through the store (board + backlog + detail update in-memory). The
    // dependency-block guard lives in the store/backend, so it fires here too
    // and surfaces via the global confirm modal.
    const res = await store.updateTaskField(issue.value.name, field, value)
    setSaved()
    if (!res?.blocked && field === 'status' && isCompleted(value)) triggerCelebration()
  } catch(e) {
    console.error(e); setError()
    toast.error(e.message || 'Failed to save')
  }
}

// ── Celebration ───────────────────────────────────────────────────────────────
const showCelebration = ref(false)
function triggerCelebration() {
  showCelebration.value = true
  setTimeout(() => { showCelebration.value = false }, 2800)
}
async function saveTitle(e) { const t=e.target.innerText.trim(); if(t&&t!==issue.value?.title) await setField('title',t) }
const descDraft   = ref('')
const descSaving  = ref(false)
function startDescEdit() {
  if (descEditing.value) return
  descDraft.value = issue.value?.description || ''
  descEditing.value = true
}
async function saveDescription() {
  if (!issue.value || descSaving.value) return
  const val = descDraft.value
  // No-op if unchanged
  if (val === (issue.value.description || '')) { descEditing.value = false; return }
  descSaving.value = true
  setSaving()
  try {
    // Route through store.updateTaskField so board + backlog + detail
    // are all patched in-memory — no stale data after closing TaskDetail
    await store.updateTaskField(issue.value.name, 'description', val)
    setSaved()
    descEditing.value = false
  } catch(e) {
    setError()
  } finally {
    descSaving.value = false
  }
}
function cancelDescription() {
  descDraft.value = issue.value?.description || ''
  descEditing.value = false
}

// Subtasks
const doneCount   = computed(()=>subtasks.value.filter(st=>isCompleted(st.status)).length)
const progressPct = computed(()=>subtasks.value.length?Math.round(doneCount.value/subtasks.value.length*100):0)
const filteredMembersSt = computed(()=>{ const q=stAssigneeQ.value.toLowerCase(); return (store.projectMembers||[]).filter(m=>!q||m.full_name?.toLowerCase().includes(q)) })
async function addSubtask() {
  if(!newSubTitle.value.trim()) return
  await createTask({project:store.currentProject.name,title:newSubTitle.value.trim(),task_type:store.taskTypes?.[0]?.name||'Task',parent_task:issue.value.name,priority:newSubPriority.value,status:store.workflowStates?.[0]?.name||'To Do',assignees:[]})
  newSubTitle.value=''; showAddSub.value=false; await store.refreshTaskDetail?.()
}
async function toggleSubtask(st) {
  const done=store.workflowStates?.find(s=>s.category==='completed')?.name||'Done'
  const todo=store.workflowStates?.find(s=>s.category==='unstarted')?.name||'To Do'
  await updateTask(st.name,{status:isCompleted(st.status)?todo:done})
  // Update optimistically in the subtask list
  if (store.selectedTask?.subtasks) {
    const idx = store.selectedTask.subtasks.findIndex(s => s.name === st.name)
    if (idx !== -1) store.selectedTask.subtasks[idx].status = isCompleted(st.status) ? todo : done
  }
  // Refresh TaskDetail data without the null→loading flash
  await store.refreshTaskDetail?.()
}
async function updateSubtask(st,field,value) {
  if(store.selectedTask?.subtasks){const idx=store.selectedTask.subtasks.findIndex(s=>s.name===st.name); if(idx!==-1) store.selectedTask.subtasks[idx][field]=value}
  try{await updateTask(st.name,{[field]:value})}catch(e){await store.refreshTaskDetail?.()}
}
async function toggleStAssignee(st,m) {
  const cur=st.assignees||[], already=cur.some(a=>a.user===m.user)
  const updated=already?cur.filter(a=>a.user!==m.user):[...cur,{user:m.user,full_name:m.full_name}]
  await updateSubtask(st,'assignees',updated)
}

// Links
const issueRefs    = computed(() => issue.value?.references || [])
const attachments  = computed({
  get: () => issue.value?.attachments || [],
  set: (v) => { if (store.selectedTask) store.selectedTask.attachments = v }
})

const groupedLinks = computed(()=>{ const g={}; for(const lk of links.value){if(!g[lk.link_type])g[lk.link_type]=[]; g[lk.link_type].push(lk)} return g })
const searchLink = debounce(async()=>{ if(!linkQ.value.trim()){linkResults.value=[];return} try{linkResults.value=await searchTasks(linkQ.value,store.currentProject?.name,issue.value?.name)}catch(e){} },300)
// Keep the dialog open on failure — closing it and clearing the query reads as
// success, so a swallowed error here looked exactly like a created link.
async function confirmLink(r) { try{await addTaskLink(issue.value.name,r.name,newLinkType.value);showAddLink.value=false;linkQ.value='';linkResults.value=[];await store.refreshTaskDetail?.()}catch(e){toast.error(e.message||'Could not link that task')} }
// ERPNext reference functions
async function loadAllowedDoctypes() {
  if (allowedDoctypes.value.length) return
  try { allowedDoctypes.value = await getAllowedDoctypes(store.currentProject?.name) } catch {}
}

const debouncedRefSearch = debounce(async () => {
  if (!refDoctype.value || !refQuery.value.trim()) { refResults.value = []; return }
  try { refResults.value = await searchErpDocuments(refDoctype.value, refQuery.value, store.currentProject?.name) } catch {}
}, 300)

watch(showAddRef, (v) => { if (v) loadAllowedDoctypes() })

async function addRef(r) {
  if (!issue.value) return
  try {
    const updated = await addReference(issue.value.name, r.doctype, r.name)
    if (store.selectedTask) store.selectedTask.references = updated
    showAddRef.value = false
    refQuery.value = ''
    refResults.value = []
    refDoctype.value = ''
  } catch (e) { toast.error('Failed to add reference') }
}

async function removeRef(ref) {
  if (!issue.value) return
  try {
    await removeReference(issue.value.name, ref.name)
    if (store.selectedTask) {
      store.selectedTask.references = store.selectedTask.references.filter(r => r.name !== ref.name)
    }
  } catch (e) { toast.error('Failed to remove reference') }
}

async function deleteLink(lk) { try{await removeTaskLink(issue.value.name,lk.linked_task,lk.link_type);await store.refreshTaskDetail?.()}catch(e){toast.error(e.message||'Could not remove that link')} }

// Current user info
const currentUser   = computed(() => window?.frappe?.session?.user || '')
const isProjectAdmin = computed(() => {
  const role = store.currentProject?.members?.find(m => m.user === currentUser.value)?.role
  return role === 'Admin' || role === 'Manager' || store.isAdmin
})

// ── Task-driven procurement ──────────────────────────────────────
// Cosmetic gate mirroring the backend's real bar (require_feature
// "integrations" + access.require Manager+ + view_money) — the
// endpoint enforces all three regardless of what this hides.
const canCreatePO = computed(() =>
  isProjectAdmin.value && ent.can('integrations') && store.hasCapability('view_money') &&
  !!store.currentProject?.erpnext_project
)
// Files section in the task drawer.
const canViewFiles = computed(() => store.hasCapability('view_files'))
const poDrawerOpen    = ref(false)
const moneyDrawerOpen = ref(false)
const moneyDrawerPo   = ref('')
function onPoCreated(poName) {
  moneyDrawerPo.value = poName
  moneyDrawerOpen.value = true
}

// reference-list opener — must use the same pattern ListView.vue uses for
// this, not a raw <a>. Separate drawer instance from the PO-creation
// one above, which is hardcoded to a single doctype.
const { moneyDrawerOpen: refDrawerOpen, moneyDrawerDoctype: refDrawerDoctype,
  moneyDrawerName: refDrawerName, openErpDoc } = useErpDocOpener()

// Comments
async function postComment() {
  if(!newComment.value.trim()) return
  // The draft is only cleared after a successful post, so an error here leaves
  // the text in the box to retry — but the user still has to be told it failed.
  try{await addComment(issue.value.name,newComment.value);newComment.value='';commentFocused.value=false;await store.refreshTaskDetail?.()}catch(e){toast.error(e.message||'Comment not posted')}
}

function startEditComment(c) {
  editingComment.value = c.name
  editCommentText.value = c.comment_text || ''
}

function cancelEditComment() {
  editingComment.value = null
  editCommentText.value = ''
}

async function saveEditComment(c) {
  if (!editCommentText.value.trim()) return
  try {
    await editComment(c.name, editCommentText.value)
    // Update locally without full refresh
    if (issue.value?.activity) {
      const idx = issue.value.activity.findIndex(a => a.name === c.name)
      if (idx >= 0) issue.value.activity[idx].comment_text = editCommentText.value
    }
    cancelEditComment()
  } catch(e) { console.error('Edit comment failed:', e) }
}

async function deleteCommentConfirm(c) {
  if (!await confirmDialog('Delete this comment?', { danger: true })) return
  try {
    await deleteComment(c.name)
    // Remove locally without full refresh
    if (issue.value?.activity) {
      const idx = issue.value.activity.findIndex(a => a.name === c.name)
      if (idx >= 0) issue.value.activity.splice(idx, 1)
    }
  } catch(e) { console.error('Delete comment failed:', e) }
}

// History
const groupedHistory = computed(()=>{
  const g={},today=new Date(),yesterday=new Date(today-86400000)
  for(const a of history.value){
    const d=new Date(a.creation)
    const label=d.toDateString()===today.toDateString()?'Today':d.toDateString()===yesterday.toDateString()?'Yesterday':d.toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'})
    if(!g[label])g[label]=[]; g[label].push(a)
  }
  return g
})
const FIELD_LABELS = {
  priority:'priority', task_type:'type', title:'title', due_date:'due date',
  start_date:'start date', story_points:'story points', description:'description', labels:'labels',
}
function fieldLabel(a){ return FIELD_LABELS[a.field_name] || (a.field_name ? a.field_name.replace(/_/g,' ') : 'field') }
function activityText(a) {
  if(a.action_type==='Status Change') return `changed status to "${a.new_value}"`
  if(a.action_type==='Field Edit') {
    const f=fieldLabel(a)
    if(a.field_name==='description') return `updated the ${f}`
    if(a.old_value && a.new_value) return `changed ${f} from "${a.old_value}" to "${a.new_value}"`
    if(a.new_value) return `set ${f} to "${a.new_value}"`
    if(a.old_value) return `cleared ${f} (was "${a.old_value}")`
    return `updated ${f}`
  }
  if(a.action_type==='Assignment')    return a.old_value?`unassigned ${a.old_value}`:`assigned ${a.new_value}`
  if(a.action_type==='Created')       return 'created this issue'
  return a.action_type?.toLowerCase()||''
}
const tabs = computed(()=>[ {id:'comments',label:'Comments',count:comments.value.length}, {id:'history',label:'History',count:null} ])
const myInitials = computed(()=>{ const n=window?.frappe?.session?.user_fullname||'Me'; return n.split(' ').map(w=>w[0]).join('').toUpperCase().slice(0,2) })
function shortUser(u){return !u?'Unknown':u.includes('@')?u.split('@')[0]:u}
function fmtRel(d){
  if(!d)return''
  const m=Math.floor((Date.now()-new Date(d))/60000)
  if(m<1)return'just now'; if(m<60)return`${m}m ago`
  const h=Math.floor(m/60); if(h<24)return`${h}h ago`
  return new Date(d).toLocaleDateString('en-US',{month:'short',day:'numeric'})
}
function fmtDate(d){return d?new Date(d).toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'}):''}
async function handleDelete(){
  if(!await confirmDialog(`Move "${issue.value?.title}" to trash?`, { danger: true, confirmLabel: 'Move to trash' }))return
  try{await store.deleteCurrentIssue(issue.value.name); toast.success('Moved to trash')}catch(e){toast.error(e.message||'Could not move this to trash')}
}
async function doDuplicate(){
  if(!issue.value?.name)return
  try{
    await duplicateTask(issue.value.name)
    store.refreshBoard()
    toast.success('Task duplicated')
  }catch(e){toast.error(e.message||'Failed to duplicate')}
}
</script>

<style scoped>
/* ─── ROOT ─── */
.jv-root {
  font-family: 'DM Sans', -apple-system, BlinkMacSystemFont, sans-serif;
  font-size:var(--text-md);
  color: var(--foreground);
  -webkit-font-smoothing: antialiased;
}

/* ─── BACKDROP ─── */
.jv-backdrop {
  position: fixed; inset: 0;
  background: rgba(15, 20, 30, 0.35);
  animation: jv-bd 0.2s ease;
  z-index: 48 !important;
}
@keyframes jv-bd { from { opacity: 0 } }

/* ─── PANEL ─── */
.jv-panel {
  position: fixed;
  top: 0; right: 0; bottom: 0;
  z-index: 49 !important;
  width: 920px;
  max-width: 95vw;
  display: flex;
  flex-direction: column;
  background: var(--overlay);
  border-left: 1px solid var(--border);
  box-shadow: -4px 0 24px rgba(0,0,0,0.10), 0 0 0 1px rgba(0,0,0,0.04);
  animation: jv-in 0.2s ease;
}
@keyframes jv-in { from { transform: translateX(24px); opacity: 0 } }

/* ─── HEADER ─── */
.jv-header {
  display: flex; align-items: center; justify-content: space-between;
  height: 48px; padding: 0 16px;
  background: var(--overlay);
  border-bottom: 1px solid var(--surface-secondary);
  flex-shrink: 0;
  box-shadow: 0 1px 2px rgba(0,0,0,0.04);
}
.jv-crumb { display: flex; align-items: center; gap: 6px; min-width: 0; flex: 1; }
.jv-crumb-project { font-size:13px; font-weight: 600; color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 140px; padding-top:2px; }
.jv-crumb-sep { color: var(--border); font-size:var(--text-base); }
.jv-crumb-key { font-size:var(--text-sm); font-weight: 700; color: var(--muted); white-space: nowrap; padding: 1px 7px; border-radius: 4px; }
.jv-header-actions { display: flex; align-items: center; gap: 4px; flex-shrink: 0; }
.jv-watch-count { font-size:var(--text-xs); font-weight: 600; color: var(--muted); }
/* Ghost trigger, not a filled pill — the avatar stack itself is the visual
   weight here, same register as every other chrome control in this rail. */
.jv-watch-stack-btn {
  cursor: pointer; padding: 0 8px 0 4px; height: 28px; display: inline-flex;
  align-items: center; gap: 5px; border: none; background: none;
  border-radius: 6px; transition: background .1s;
}
.jv-watch-stack-btn:hover { background: var(--surface-secondary); }
.jv-watch-stack-btn:hover .jv-watch-count { color: var(--foreground); }
.jv-hbtn { display: flex; align-items: center; justify-content: center; width: 30px; height: 30px; border: none; background: none; cursor: pointer; color: var(--muted); border-radius: 6px; transition: background 0.1s, color 0.1s; }
.jv-hbtn:hover { background: var(--surface-secondary); color: var(--foreground); }
/* Declared AFTER .jv-hbtn deliberately — this button carries BOTH classes,
   and at equal specificity the later rule wins the tie regardless of which
   one "sounds" more specific. Was silently losing its own background to
   .jv-hbtn's `background: none` for exactly that reason. Rests on a grey
   chip like Mute/Watch toggles elsewhere in the app, not bare-icon
   transparent like Close/More beside it — this one holds a persistent
   on/off state, so it should read as a toggle at a glance, not only on
   hover. */
.jv-watch-btn { display: inline-flex; align-items: center; gap: 4px; width: auto; padding: 0 7px; background: var(--surface-secondary); }
.jv-watch-btn:hover { background: var(--default-hover); color: var(--foreground); }
.jv-watch-btn.active { color: var(--accent); background: var(--accent-soft); }
.jv-watch-btn.active:hover { background: var(--accent-soft-hover); }

.jv-autosave { display: inline-flex; align-items: center; gap: 4px; padding: 2px 8px; border-radius: 6px; font-size:var(--text-xs); font-weight: 500; }
.jv-save-saving { background: var(--surface-secondary); color: var(--muted); }
/* Were --success/--danger — the SATURATED variant, not the "-soft-foreground"
   one every other soft chip in this file pairs with its own -soft background
   (Approval, status chips). --success is lightness 0.73 in light theme,
   nearly the same lightness as the 12%-tint background it sat on top of —
   low contrast text on its own pill. */
.jv-save-saved  { background: var(--success-soft); color: var(--success-soft-foreground); }
.jv-save-error  { background: var(--danger-soft); color: var(--danger-soft-foreground); }
.jv-spin { animation: jv-spin 0.8s linear infinite; flex-shrink: 0; }
@keyframes jv-spin { to { transform: rotate(360deg) } }
.jv-fade-enter-active, .jv-fade-leave-active { transition: all 0.15s; }
.jv-fade-enter-from, .jv-fade-leave-to { opacity: 0; }

/* ─── LOADING ─── */
.jv-loading { flex: 1; display: flex; align-items: center; justify-content: center; gap: 10px; color: var(--muted); font-size:var(--text-base); }
.jv-loader  { width: 16px; height: 16px; border: 2px solid var(--border); border-top-color: var(--accent); border-radius: 50%; animation: jv-spin 0.8s linear infinite; }

/* ─── TWO-COLUMN LAYOUT ─── */
.jv-body {
  flex: 1; min-height: 0;
  display: grid;
  grid-template-columns: 1fr 288px;
  overflow: hidden;
}

/* ─── MAIN (left) ─── */
.jv-main {
  overflow-y: auto;
  padding: 0 0 48px;
  background: var(--overlay);
  border-right: 1px solid var(--border);
  scrollbar-width: thin; scrollbar-color: var(--border) transparent;
}

/* ─── HERO (title + action bar) ─── */
.jv-hero {
  padding: 20px 24px 0;
  border-bottom: 1px solid var(--surface-secondary);
}

/* Title block */
.jv-title-block { margin-bottom: 8px; }
.jv-type-badge { width: 16px; height: 16px; border-radius: 4px; display: inline-flex; align-items: center; justify-content: center; color: var(--accent-foreground); font-size:var(--text-micro); font-weight: 700; flex-shrink: 0; }
.jv-team-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.jv-st-type {
  width: 16px; height: 16px; border-radius: 4px;
  display: inline-flex; align-items: flex-start; justify-content: flex-start;
  padding: 2px 2px 0 2px;
  color: var(--accent-foreground) !important; font-size:var(--text-micro); font-weight: 800; flex-shrink: 0; line-height: 1;
}
.jv-type-label { font-size:var(--text-sm); font-weight: 600; color: var(--muted); letter-spacing: 0; }
.jv-parent-link { display: inline-flex; align-items: center; gap: 3px; font-size:var(--text-xs); font-weight: 600; color: var(--accent); margin-left: 8px; }
.jv-parent-link:hover { text-decoration: underline; cursor: pointer; }

.jv-title {
  font-size:var(--text-3xl);
   font-weight: 700;
   color: var(--foreground);
  letter-spacing: -0.015em;
   line-height: 1.35;
  outline: none; cursor: text;
  border-radius: 6px;
   padding: 6px 6px; 
   margin: 0 -4px;
  transition: background 0.3s;
}
.jv-title:hover { background: #f8f8f8; }
.jv-title:focus { background: var(--surface-secondary);  }

/* Action bar */
/* Law §3: a border may not do what whitespace can. The rule that used to sit
   above this bar just added a horizontal line to an already-busy panel. */
.jv-action-bar {
  display: flex; align-items: center; gap: 4px;
  flex-wrap: wrap;
  padding: 4px 0 16px;
  margin-top: 12px;
}

/* Status is DATA, so it keeps its colour — as a soft chip (tinted bg + full
   colour text), which needs no border to read as a control. */
.jv-transition-btn {
  display: inline-flex; align-items: center; gap: 5px;
  height: 28px; padding: 0 10px;
  font-size:var(--text-sm); font-weight: 600; font-family: inherit;
  border: none; border-radius: 6px; cursor: pointer;
  transition: filter 0.12s;
}
.jv-transition-btn:hover { filter: brightness(0.96); }

.right-btn :hover {
  background: var(--surface-hover);
  color: var(--foreground);
}

/* Law §4: chrome buttons are GHOST. These were filled + bordered, which is
   exactly the "Bootstrap toolbar" tell — four boxed buttons in a row. */
.jv-action-btn {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 6px 10px;
  border: 2px solid var(--border);
  font-size:var(--text-sm); font-weight: 500; font-family: inherit;
  color: #000000;
  border: 1px solid #e1e2e1 ; border-radius: 6px;
  cursor: pointer; transition: background 0.12s, color 0.12s;
}
.jv-action-btn:hover { background: var(--surface-hover); color: var(--foreground); }

/* Sections — separated by whitespace, not by a rule per section. */
.jv-section {
  padding: 16px 24px;
}
/* Law §2: uppercase labels are the 11px step. This and .jv-sb-label are a
   deliberate two-tier pair — content sections shout in uppercase/600, field
   labels stay sentence-case/500 — so they must NOT share a size. */
.jv-section-title {
  display: flex; align-items: center; gap: 8px;
  font-size: 14px; font-weight: 800; 
  color: #292a2e;
  text-transform: uppercase; letter-spacing: 0.05em;
  margin-bottom: 10px;
}
.jv-section-count { font-size:var(--text-sm); font-weight: 500; color: var(--muted); }
.jv-section-add-btn {
  display: flex; align-items: center; justify-content: center;
  width: 22px; height: 22px; border: none; background: none;
  color: var(--muted); cursor: pointer; border-radius: 6px;
  transition: background .1s, color .1s; margin-left: auto;
}
.jv-section-add-btn:hover { background: var(--surface-secondary); color: var(--foreground); }

/* Mini progress bar */
.jv-mini-progress { flex: 1; height: 3px; background: var(--surface-secondary); border-radius: 4px; overflow: hidden; margin-left: 4px; max-width: 80px; }
.jv-mini-fill { height: 100%; background: var(--success); border-radius: 4px; transition: width 0.3s; }

/* Hours input */
.jv-hrs-input { width: 72px; height: 26px; padding: 0 8px; font-size:var(--text-base); font-family: inherit; color: var(--foreground); background: var(--surface-secondary); border: 1px solid var(--border); border-radius: 6px; outline: none; transition: border-color 0.15s; }
.jv-hrs-input:focus { border-color: var(--accent); background: var(--surface); box-shadow: 0 0 0 3px rgba(11,107,203,0.08); }
.jv-hrs-input::placeholder { color: var(--muted); }

/* Billable toggle */
.jv-toggle { width: 32px; height: 18px; border-radius: 9px; background: var(--border); border: none; cursor: pointer; position: relative; transition: background 0.15s; flex-shrink: 0; }
.jv-toggle.active { background: var(--success); }
.jv-toggle-thumb { position: absolute; top: 2px; left: 2px; width: 14px; height: 14px; border-radius: 50%; background: var(--accent-foreground); box-shadow: 0 1px 3px rgba(0,0,0,0.2); transition: transform 0.15s; }
.jv-toggle.active .jv-toggle-thumb { transform: translateX(14px); }

/* Task timer */
.jv-timer-btn { display: inline-flex; align-items: center; gap: 5px; height: 26px; padding: 0 10px; font-size:var(--text-sm); font-weight: 600; color: var(--foreground); background: var(--surface-secondary); border: 1px solid var(--border); border-radius: 6px; cursor: pointer; transition: background 0.15s; }
.jv-timer-btn:hover:not(:disabled) { background: var(--surface-tertiary, var(--border)); }
.jv-timer-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.jv-timer-running { display: inline-flex; align-items: center; gap: 8px; }
.jv-timer-stop { display: inline-flex; align-items: center; justify-content: center; width: 22px; height: 22px; border-radius: 50%; background: var(--danger); color: var(--accent-foreground); border: none; cursor: pointer; flex-shrink: 0; }
.jv-timer-stop:disabled { opacity: 0.6; cursor: not-allowed; }
.jv-timer-elapsed { font-size:var(--text-base); font-weight: 600; color: var(--foreground); font-variant-numeric: tabular-nums; }

.jv-timelog-toggle { font-size: var(--text-xs); font-weight: 600; color: var(--accent); background: none; border: none; cursor: pointer; padding: 0; }
.jv-timelog-toggle:hover { text-decoration: underline; }
.jv-timelog-add { display: flex; align-items: center; gap: 6px; margin-top: 6px; }
.jv-timelog-list { display: flex; flex-direction: column; gap: 2px; margin-top: 8px; }
.jv-timelog-row { display: flex; align-items: center; gap: 8px; padding: 4px 0; }
.jv-timelog-date { font-size: var(--text-xs); color: var(--muted); flex: 1; }
.jv-timelog-hours { font-size: var(--text-sm); font-weight: 600; color: var(--foreground); background: none; border: none; cursor: pointer; padding: 2px 4px; border-radius: 4px; font-variant-numeric: tabular-nums; }
.jv-timelog-hours:hover:not(:disabled) { background: var(--surface-secondary); }
.jv-timelog-hours:disabled { cursor: default; color: var(--muted); }
.jv-timelog-edit { width: 60px; height: 22px; }
.jv-timelog-del { display: inline-flex; align-items: center; justify-content: center; width: 20px; height: 20px; border: none; background: none; color: var(--muted); cursor: pointer; border-radius: 4px; flex-shrink: 0; }
.jv-timelog-del:hover { color: var(--danger); background: var(--surface-secondary); }

/* Description */
.jv-desc-wrap {
  min-height: 36px; padding: 8px 10px;
  cursor: text; transition: background 0.1s;
  border-radius: 6px; margin: 0 -10px;
}
.jv-desc-wrap:hover { background: var(--surface-secondary); }
.jv-desc-wrap:has(.ql-editor) { background: transparent; cursor: default; padding: 0; margin: 0; }
.jv-desc-placeholder { font-size:var(--text-base); color: var(--muted); }
.jv-desc-preview { font-size:var(--text-base); color: var(--foreground); line-height: 1.65; }
.jv-desc-preview :deep(p) { margin: 0 0 8px; }
.jv-desc-preview :deep(p:last-child) { margin: 0; }
.jv-desc-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 10px; }
.jv-desc-spinner { display: inline-block; width: 10px; height: 10px; border-radius: 50%; border: 2px solid rgba(255,255,255,.3); border-top-color: var(--accent-foreground); animation: jv-spin .6s linear infinite; }
@keyframes jv-spin { to { transform: rotate(360deg); } }
.jv-btn-cancel { height: 28px; padding: 0 12px; font-size:var(--text-sm); font-weight: 600; font-family: inherit; color: var(--muted); background: none; border: 1.5px solid var(--border); border-radius: 8px; cursor: pointer; transition: background .1s; }
.jv-btn-cancel:hover { background: var(--surface-secondary); }

/* Subtasks */
.jv-subtasks { display: flex; flex-direction: column; gap: 2px; margin: 0; }

/* ── Checklist ── */
.jv-checklist { display: flex; flex-direction: column; gap: 1px; margin: 4px 0 0; }
.jv-cl-row { display: flex; align-items: center; gap: 6px; padding: 2px 0; }
.jv-cl-check { width: 16px; height: 16px; 
  border-radius: 3px; 
  border: 2px solid #e0e0e0;
   background: var(--surface); 
   display: flex;
    align-items: center; 
    justify-content: center;
     cursor: pointer;
      flex-shrink: 0;
       transition: all .12s;
       }
.jv-cl-check:hover { border-color: var(--accent); }
.jv-cl-check.done { background: var(--accent); border-color: var(--accent); }
.jv-cl-text { flex: 1; min-width: 0; border: none; background: transparent; font-size:var(--text-base); color: var(--foreground); outline: none; padding: 2px 0; }
.jv-cl-text:hover { border-bottom: 1px solid var(--border); }
.jv-cl-text:focus { border-bottom: 1px solid var(--accent); }
.jv-cl-text.done { text-decoration: line-through; color: var(--muted); }
.jv-cl-del { width: 20px; height: 20px; display: flex; align-items: center; justify-content: center; color: var(--muted); opacity: 0; cursor: pointer; border-radius: 3px; transition: opacity .1s; flex-shrink: 0; }
.jv-cl-row:hover .jv-cl-del { opacity: 1; }
.jv-cl-del:hover { color: var(--danger); background: var(--danger-soft); }
.jv-cl-add { margin-top: 4px; }
.jv-cl-add-btn { 
  display: inline-flex;
   align-items: center;
    gap: 4px;
     font-size:var(--text-sm);
     font-weight: 600;
      color: var(--muted);
       background: none;
         cursor: pointer;
          transition: color .1s;
           padding: 4px 8px;
            border-radius: 4px;
            border: 1px solid var(--border);
          box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05); 
           }
.jv-cl-add-btn:hover { color: var(--foreground); background: var(--surface-secondary); }
.jv-subtask {
  display: grid;
  grid-template-columns: 18px 16px 56px 1fr auto;
  align-items: center; gap: 6px;
  padding: 5px 8px; border-radius: 6px;
  transition: background 0.1s;
  background: var(--surface-secondary);
  border: 1px solid var(--surface-secondary);
  margin-bottom: 2px;
}
.jv-subtask:hover { background: var(--surface-secondary); }

.jv-st-check { width: 14px; height: 14px; border-radius: 4px; border: 2px solid var(--border); background: var(--surface); display: flex; align-items: center; justify-content: center; cursor: pointer; transition: all 0.1s; flex-shrink: 0; }
.jv-st-check:hover { border-color: var(--accent); }
.jv-st-check.done { background: var(--success); border-color: var(--success); }
.jv-st-key { font-size:var(--text-xs); font-weight: 700; color: var(--accent); white-space: nowrap; font-family: monospace; }
.jv-st-title { font-size:var(--text-base); color: var(--foreground); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.jv-st-title.done { text-decoration: line-through; color: var(--muted); }

/* Subtask pills — must be inline, force FieldDropdown internal divs */
.jv-st-meta { display: flex; align-items: center; gap: 2px; }
.jv-st-pill-wrap { display: inline-flex; align-items: center; flex-shrink: 0; }
.jv-st-pill-wrap :deep(.relative) { display: inline-flex !important; width: auto !important; }
.jv-st-pill-wrap :deep(.relative > div) { display: inline-flex !important; width: auto !important; }
.jv-st-pill {
  display: inline-flex; align-items: center; gap: 3px;
  padding: 2px 5px; border-radius: 4px; border: none;
  background: transparent; cursor: pointer; font-size:var(--text-xs);
  transition: background 0.1s;
}
.jv-st-pill:hover { background: var(--border); }
.jv-st-status { display: inline-flex; align-items: center; padding: 1px 6px; border-radius: 4px; font-size:var(--text-xs); font-weight: 700; white-space: nowrap; }

/* Add child issue row */
.jv-add-row {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  padding: 8px 8px; background: #fff;
  border: 1px solid var(--border);
  border-radius: 6px; margin: 8px 0 0;
}
.jv-add-row--link { background: #f8f8f8; }
.jv-add-row--link:hover { background: var(--surface-secondary); }
.jv-add-input { flex: 1; min-width: 160px; font-size:14px; font-weight:500; font-family: "Inter"; color: var(--foreground); background: transparent; border: none; outline: none; }
.jv-add-input::placeholder { color: var(--muted); }
.jv-add-child-btn { display: inline-flex; align-items: center; gap: 5px;  padding: 4px 10px; font-size:var(--text-sm); font-weight: 600; font-family: inherit; 
  color: var(--muted);
   background: #fff; border: 1px solid var(--border); border-radius: 6px; cursor: pointer; transition: background 0.1s; box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05); 
 }
.jv-add-child-btn:hover { background: #f8f8f8; color: black }
.jv-add-chip { display: inline-flex; align-items: center; gap: 4px; height: 30px; padding: 0 8px; font-size:var(--text-sm); font-weight: 500; font-family: inherit; color: var(--foreground); background: var(--surface); border: 1px solid var(--border); border-radius: 4px; cursor: pointer; transition: background 0.1s; white-space: nowrap; }
.jv-add-chip:hover { background: var(--surface-secondary); }

/* Linked issues */
.jv-link-type { font-size:var(--text-xs); font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; color: var(--muted); padding: 6px 0 3px; }
.jv-link-row { display: flex; align-items: center; gap: 7px; padding: 5px 8px; border-radius: 6px; border: 1px solid var(--surface-secondary); background: var(--surface-secondary); margin: 0 0 4px; transition: background 0.1s; }
.jv-link-row:hover { background: var(--surface-secondary); }
.jv-link-search { flex: 1; min-width: 200px; display: flex; align-items: center; gap: 7px; padding: 5px 9px; background: var(--surface); border: 1px solid var(--border); border-radius: 6px; }
.jv-link-search:focus-within { border-color: var(--muted); }
.jv-link-results { width: 100%; border: 1px solid var(--border); border-radius: 8px; overflow: hidden; background: var(--overlay); box-shadow: 0 12px 32px 0 rgba(0,0,0,.08), 0 0 0 1px rgba(0,0,0,.04); }
.jv-link-result { display: flex; align-items: center; gap: 7px; padding: 7px 10px; cursor: pointer; border-bottom: 1px solid var(--surface-secondary); transition: background 0.1s; }
.jv-link-result:last-child { border-bottom: none; }
.jv-link-result:hover { background: var(--surface-secondary); }
.jv-remove-btn { display: flex; align-items: center; justify-content: center; width: 18px; height: 18px; border: none; background: none; color: var(--muted); border-radius: 4px; cursor: pointer; opacity: 0; transition: all 0.1s; flex-shrink: 0; }
.jv-link-row:hover .jv-remove-btn, .jv-ref-row:hover .jv-remove-btn { opacity: 1; }
.jv-remove-btn:hover { background: var(--danger-soft); color: var(--danger); }

/* Tabs */
.jv-tabs { display: flex; border-bottom: 1px solid var(--surface-secondary); margin: 0; }
.jv-tab { display: inline-flex; align-items: center; gap: 5px; padding: 8px 0; margin-right: 20px; margin-bottom: -1px; font-size:var(--text-base); font-weight: 500; color: var(--muted); background: none; border: none; border-bottom: 2px solid transparent; cursor: pointer; transition: color 0.1s, border-color 0.1s; }
.jv-tab:hover { color: var(--foreground); }
.jv-tab.active { color: var(--foreground); border-bottom-color: var(--foreground); font-weight: 700; }
.jv-tab-n { font-size:var(--text-xs); font-weight: 700; padding: 1px 5px; border-radius: 10px; background: var(--surface-secondary); color: var(--muted); }
.jv-tab.active .jv-tab-n { background: var(--border); color: var(--foreground); }

/* Compose */
.jv-compose { display: flex; gap: 10px; padding: 12px 0 8px; }
.jv-me-av { width: 28px; height: 28px; border-radius: 50%; background: var(--foreground); color: var(--background); font-size:var(--text-micro); font-weight: 700; display: flex; align-items: center; justify-content: center; flex-shrink: 0; margin-top: 2px; }
.jv-composer { flex: 1; border: 1.5px solid var(--border); border-radius: 8px; overflow: hidden; background: var(--surface); transition: border-color 0.15s; }
.jv-composer.focused { border-color: var(--muted); box-shadow: 0 0 0 3px rgba(0,0,0,0.06); }
.jv-composer-ta { width: 100%; padding: 8px 12px; font-size:var(--text-base); font-family: inherit; color: var(--foreground); background: transparent; border: none; outline: none; resize: none; line-height: 1.6; }
.jv-composer-ta::placeholder { color: var(--muted); }
.jv-composer-bar { display: flex; align-items: center; justify-content: flex-end; gap: 8px; padding: 6px 10px; border-top: 1px solid var(--border); background: var(--surface-secondary); }
.jv-hint { font-size:var(--text-xs); color: var(--muted); margin-right: auto; }
.jv-slide-enter-active, .jv-slide-leave-active { transition: all 0.12s; max-height: 44px; overflow: hidden; }
.jv-slide-enter-from, .jv-slide-leave-to { opacity: 0; max-height: 0; }

/* Comments */
.jv-comments { display: flex; flex-direction: column; gap: 14px; padding: 0 0 8px; }
.jv-comment { display: flex; gap: 10px; }
.jv-comment-meta { display: flex; align-items: center; gap: 7px; margin-bottom: 4px; position: relative; }
.jv-comment-name { font-size:var(--text-base); font-weight: 700; color: var(--foreground); }
.jv-comment-time { font-size:var(--text-xs); color: var(--muted); }
.jv-comment-actions { display: flex; gap: 2px; margin-left: auto; opacity: 0; transition: opacity 0.12s; }
.jv-comment:hover .jv-comment-actions { opacity: 1; }
.jv-comment-action {
  display: inline-flex; align-items: center; justify-content: center;
  width: 22px; height: 22px; border-radius: 5px; border: none;
  background: transparent; color: var(--muted); cursor: pointer;
  transition: background 0.1s, color 0.1s;
}
.jv-comment-action:hover { background: var(--surface-secondary); color: var(--foreground); }
.jv-comment-action--delete:hover { background: var(--danger-soft); color: var(--danger); }
.jv-comment-body { background: var(--surface-secondary); border: 1px solid var(--border); border-radius: 8px; padding: 8px 12px; font-size:var(--text-base); line-height: 1.6; color: var(--foreground); }
.jv-mention { color: var(--accent); background: var(--accent-soft); border-radius: 4px; padding: 1px 5px; font-weight: 500; cursor: pointer; transition: background 0.12s; }
.jv-mention:hover { background: var(--accent-soft); }
.jv-composer { position: relative; }
.jv-mention-menu { position: absolute; left: 8px; bottom: calc(100% + 4px); z-index: 30; min-width: 200px; background: var(--overlay); border: 1px solid var(--border); border-radius: 8px; box-shadow: 0 8px 24px rgba(0,0,0,0.12); padding: 4px; }
.jv-mention-opt { display: flex; align-items: center; gap: 8px; width: 100%; padding: 6px 8px; border: none; background: none; cursor: pointer; border-radius: 6px; font-size:var(--text-base); color: var(--foreground); text-align: left; }
.jv-mention-opt:hover, .jv-mention-opt.active { background: var(--surface-secondary); }
.jv-mention-av { display: inline-flex; align-items: center; justify-content: center; width: 22px; height: 22px; border-radius: 50%; background: var(--accent); color: var(--accent-foreground); font-size:var(--text-xs); font-weight: 600; flex-shrink: 0; }
.jv-comment-edit-ta { width: 100%; margin-top: 4px; }
.jv-no-comments { font-size:var(--text-base); color: var(--muted); padding: 10px 0 4px; }

/* History */
.jv-hist-date { font-size:var(--text-xs); font-weight: 700; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; padding: 8px 0 4px; border-top: 1px solid var(--surface-secondary); margin-top: 4px; }
.jv-hist-date:first-child { border-top: none; margin-top: 0; }
.jv-hist-row { display: flex; align-items: center; gap: 8px; padding: 4px 6px; border-radius: 5px; }
.jv-hist-rows-end { padding-bottom: 8px; }
.jv-hist-row:hover { background: var(--surface-secondary); }
.jv-hist-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--border); border: 2px solid var(--border); flex-shrink: 0; }
.jv-hist-text { flex: 1; font-size:var(--text-sm); color: var(--foreground); }
.jv-hist-time { font-size:var(--text-xs); color: var(--muted); white-space: nowrap; flex-shrink: 0; }

/* ─── SIDEBAR ─── */
.jv-sidebar {
  background: var(--overlay);
  overflow-y: auto;
  padding: 0 0 32px;
  scrollbar-width: thin; scrollbar-color: var(--border) transparent;
  display: flex; flex-direction: column;
}

/* Field block — label above value */
.jv-sb-field { padding: 5px 16px; border: none; }
.jv-sb-field--status { padding-top: 12px; padding-bottom:6px; }
/* padding-left matches the value row's, so label and value sit on one edge. */
.jv-sb-label {
  font-size: 13px; font-weight: 600; color: black;
  margin-bottom: 4px; padding-left: 0px;
}
.jv-lbl-danger { color: var(--danger) !important; }

/* Value wrapper */
.jv-sb-val { display: flex; flex-direction: column;
  min-height: 32px;
}

.jv-sb-val :hover {
  background: #f8f8f8;
}

.jv-sb-val--date { display: flex; width: 100%; }

/* Pill wrap — forces FieldDropdown to full width */
.jv-sb-pill-wrap { display: block; width: 100%; }
.jv-sb-pill-wrap :hover {
  background-color: #f8f8f8;
}
.jv-sb-pill-wrap :deep(.relative) { display: block !important; width: 100% !important; }
.jv-sb-pill-wrap :deep(.relative > div) { display: block !important; width: 100% !important; }

/* Inline btn */
/* GHOST, not filled. Nine permanently-grey boxes stacked down the rail is
   the "stack of form controls" look; a polished rail shows values as text
   and reveals the control only under the pointer (law §4). Padding matches
   .jv-sb-label's so label and value share one left edge — with no fill,
   any indent difference reads as broken alignment. */
.jv-sb-inline-btn {
  display: flex; align-items: center; justify-content: space-between; gap: 8px;
  width: 100%; padding: 0 12px; height: 34px;
  font-size:var(--text-base); font-weight: 500; font-family: inherit;
  color: var(--foreground); background: transparent;
  border: 1px solid var(--border); border-radius: 6px; cursor: pointer;
  transition: background 0.12s; outline: none; text-align: left;
 box-shadow: 0 1px 1px 0 rgba(0, 0, 0, 0.05); 
}
/* Was identical to the resting background, so an interactive field gave no
   hover feedback at all. Law §6: hover = background tint. */
.jv-sb-inline-btn:hover { background: var(--secondary-new) !important; }
.jv-sb-inline-btn-content { display: flex; align-items: center; gap: 8px; flex: 1; min-width: 0; overflow: hidden; }
.jv-sb-inline-btn-chevron { width: 13px; height: 13px; flex-shrink: 0; opacity: 0.35; color: var(--muted); transition: opacity 0.15s; }
.jv-sb-inline-btn:hover .jv-sb-inline-btn-chevron { opacity: 0.7; }

/* Read-only rows share the editable row's metrics exactly, so the rail reads
   as one aligned list. Now that editable rows are transparent at rest too,
   these need no fill to stop looking ragged — they simply never light up. */
.jv-sb-static {
  min-height: 32px; padding: 0 8px;
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  cursor: default;
}
.jv-sb-unset { color: var(--muted); font-size:var(--text-base); }

/* Soft status chip — the ONE chip recipe for the rail (law §1: status colour
   is a soft chip, never a full fill). Semantic ramp only, so it themes. */
.jv-sb-chip {
  display: inline-flex; align-items: center;
  padding: 2px 8px; border-radius: 999px;
  font-size: var(--text-sm); font-weight: 600;
  background: var(--default); color: var(--muted);
}
.jv-sb-chip--warn { background: var(--warning-soft); color: var(--warning-soft-foreground); }
.jv-sb-chip--ok   { background: var(--success-soft); color: var(--success-soft-foreground); }
.jv-sb-chip--no   { background: var(--danger-soft);  color: var(--danger-soft-foreground); }
.jv-sb-sub { font-size: var(--text-sm); color: var(--accent); }

/* Row-level actions (Approve / Reject / Send / Cancel) — ghost by default
   per law §4; only the affirmative action carries colour. */
.jv-sb-actions { display: flex; align-items: center; gap: 4px; padding: 4px 8px 0; flex-wrap: wrap; }
.jv-sb-action {
  height: 26px; padding: 0 8px; border: none; border-radius: 6px;
  background: transparent; color: var(--muted); cursor: pointer;
  font-size: var(--text-sm); font-weight: 600; font-family: inherit;
  transition: background .12s, color .12s;
}
.jv-sb-action:hover { background: var(--surface-hover); color: var(--foreground); }
.jv-sb-action:disabled { opacity: .45; pointer-events: none; }
.jv-sb-action--ok:hover { background: var(--success-soft); color: var(--success-soft-foreground); }
.jv-sb-action--no:hover { background: var(--danger-soft);  color: var(--danger-soft-foreground); }

/* Inputs in the rail share the interactive field's 34px height + radius so
   an expanded row never changes the rail's vertical rhythm. */
.jv-sb-input, .jv-sb-select {
  width: 100%; height: 32px; padding: 0 8px;
  font-size: var(--text-base); font-family: inherit; color: var(--foreground);
  background: var(--surface); border: 1px solid var(--field-border);
  border-radius: 6px; outline: none;
}
.jv-sb-input:focus, .jv-sb-select:focus { border-color: var(--accent); box-shadow: var(--shadow-focus); }

/* .hui-field (DatePicker's trigger) is a BUTTON that opens a picker — same
   category as the Status/Assignee/Priority rows above, so it gets the same
   ghost-until-hover treatment those already use. Measured in the rail it
   shipped at 36px/white/bordered against the 32px/transparent buttons
   beside it — one more register in a column that already had three. */
.jv-sidebar :deep(.hui-field) {
  height: 32px; min-height: 32px; padding: 0 8px;
  background: transparent;
  border-color: transparent;
  box-shadow: none;
  transition: background .12s, border-color .12s;
}
.jv-sidebar :deep(.hui-field:hover) { background: var(--surface-hover); }
.jv-sidebar :deep(.hui-field:focus-within) {
  background: var(--surface);
  border-color: var(--accent);
  box-shadow: var(--shadow-focus);
}

/* .cf-input is a REAL field — a raw <input>/<select>/<textarea> you type or
   pick a value directly into, not a button that opens something else. The
   design law's Fields section is explicit that a field keeps its
   `--field-border` at rest ("white bg + 1px --field-border, hover darkens,
   focus = accent ring") — the ghost-button treatment above is for buttons,
   and applying it here made an editable field visually indistinguishable
   from empty space until you happened to hover it. Border stays visible
   always; only the fill goes ambient-until-hover, closer to the datepicker
   button beside it without erasing the one cue that says "type here". */
.jv-sidebar :deep(.cf-input) {
  height: 32px; min-height: 32px; padding: 0 8px;
  background: transparent;
  border-color: var(--field-border);
  box-shadow: none;
  transition: background .12s, border-color .12s;
}
.jv-sidebar :deep(.cf-input:hover) {
  background: var(--surface-hover);
  border-color: var(--field-border-hover);
}
.jv-sidebar :deep(.cf-input:focus) {
  background: var(--surface);
  border-color: var(--accent);
  box-shadow: var(--shadow-focus);
}
/* The blanket `padding: 0 8px` above is a plain shorthand, which beats
   CustomFieldInput.vue's own OWN type-specific padding at equal specificity
   by simply being declared later in that component's stylesheet — reachable
   here because .jv-sidebar's ancestor class makes every rule above it more
   specific than CustomFieldInput's scoped-only selectors. That silently ate
   the reserved space a select's chevron, a currency/percent field's ₹/%,
   and a url/email/phone field's action icon all depend on, so those started
   overlapping the value text — and a textarea's forced 32px/height clipped
   to one line. Restoring each variant's own padding/height here, same
   specificity tier, declared after so it wins the tie. */
.jv-sidebar :deep(.cf-textarea)          { height: auto; min-height: 72px; padding: 8px; }
.jv-sidebar :deep(.cf-select)            { padding-right: 28px; }
.jv-sidebar :deep(.cf-input--with-unit)  { padding-left: 28px; }
.jv-sidebar :deep(.cf-input--with-suffix){ padding-right: 28px; }
.jv-sidebar :deep(.cf-url)               { padding-right: 32px; }

/* Separator */
.jv-sb-sep { height: 1px; background: var(--surface-secondary); margin: 4px 0; }

/* Status dot */
.jv-sb-dot { width: 8px; height: 8px; border-radius: 2px; flex-shrink: 0; }

/* Avatars */
.jv-av-stack { display: flex; align-items: center; flex-shrink: 0; }
.jv-av-stacked { border: 1.5px solid var(--surface-secondary); margin-left: -5px; }
.jv-av-stacked:first-child { margin-left: 0; }
.jv-av-trigger-label { font-size:var(--text-base); color: var(--foreground); font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.jv-av-extra { font-size:var(--text-xs); color: var(--muted); font-weight: 400; margin-left: 2px; }

/* Epic tag */
.jv-epic-tag { display: inline-flex; align-items: center; padding: 2px 7px; border: 1px solid; border-radius: 6px; font-size:var(--text-sm); font-weight: 600; }

/* Overdue */
.jv-overdue .jv-sb-label { color: var(--danger); }

/* Footer timestamps */
.jv-sb-footer { font-size:var(--text-xs); color: var(--muted); display: flex; flex-direction: column; gap: 2px; padding: 12px 14px; margin-top: auto; border-top: 1px solid var(--surface-secondary); }

/* ERP link */
.jv-erp-link { font-size:var(--text-sm); font-weight: 600; color: var(--accent); cursor: pointer; }
.jv-erp-link:hover { text-decoration: underline; }

.jv-erp-create-po {
  display: inline-flex; align-items: center; gap: 6px;
  height: 30px; padding: 0 10px; border-radius: 7px;
  font-size:var(--text-sm); font-weight: 600; color: var(--accent);
  background: var(--surface-secondary); border: 1px solid var(--border-secondary);
  cursor: pointer; transition: background .1s;
}
.jv-erp-create-po:hover { background: var(--default-hover, var(--surface-secondary)); }

/* Avatar variants */
.jv-av { display: inline-flex; align-items: center; justify-content: center; color: var(--accent-foreground); font-weight: 700; border-radius: 50%; flex-shrink: 0; overflow: hidden; }
/* Real profile photo instead of hashed initials, when the user has one set
   — no background needed underneath since the photo covers the full circle. */
.jv-av-img { background: none; }
.jv-av-photo { width: 100%; height: 100%; object-fit: cover; border-radius: inherit; }
.jv-av-xs { width: 14px; height: 14px; font-size:var(--text-micro); border: 1px solid var(--surface-secondary); margin-left: -3px; }
.jv-presence-dot {
  position: absolute; bottom: -1px; right: -1px;
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--success); border: 1.5px solid var(--overlay);
}
.jv-av-xs:first-child { margin-left: 0; }
.jv-av-sm { width: 22px; height: 22px; font-size:var(--text-micro); }
.jv-av-comment { width: 24px; height: 24px; font-size:var(--text-micro); }
.jv-av-empty { width: 18px; height: 18px; border-radius: 50%; border: 2px dashed var(--border); flex-shrink: 0; }

/* Buttons */
.jv-btn-save {
  display: inline-flex; align-items: center;
  padding: 4px 6px;
  font-size:var(--text-sm); font-weight: 700; font-family: inherit;
  background: var(--accent); color: #fff;
  border: none; border-radius: 4px; cursor: pointer;
  transition: background 0.1s;
}
.jv-btn-save:hover { background: var(--accent-hover); }
.jv-btn-save:disabled { opacity: 0.5; cursor: not-allowed; }

.jv-btn-cancel {
  display: inline-flex; align-items: center;
  padding: 4px 6px;
  font-size:var(--text-sm); font-weight: 500; font-family: inherit;
  background: none; color: var(--foreground);
  border: 1px solid var(--border); border-radius: 4px; cursor: pointer;
  transition: background 0.1s;
}
.jv-btn-cancel:hover { background: var(--surface-secondary); }

/* DD helpers */
.jv-dd-search { padding: 8px 11px; border-bottom: 1px solid var(--border); }
.jv-dd-input  { width: 100%; font-size:var(--text-sm); font-family: inherit; color: var(--foreground); background: transparent; border: none; outline: none; }
.jv-dd-input::placeholder { color: var(--muted); }
.jv-dd-sep  { height: 1px; background: var(--border); margin: 3px 7px; }
.jv-dd-empty { padding: 8px 11px; font-size:var(--text-sm); color: var(--muted); }

/* Labels */
.jv-labels-wrap { display: flex; flex-wrap: wrap; gap: 4px; align-items: center; }
.jv-lbl-tag {
  display: inline-flex; align-items: center;
  padding: 2px 8px; border: 1px solid; border-radius: 6px;
  font-size:var(--text-sm); font-weight: 600; cursor: pointer;
  transition: opacity 0.1s;
}
.jv-lbl-tag:hover { opacity: 0.75; }
.jv-lbl-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.jv-add-label-btn {
  display: inline-flex; align-items: center; gap: 4px;
  height: 22px; padding: 0 7px;
  font-size:var(--text-sm); font-family: inherit; color: var(--muted);
  background: var(--surface-secondary); border: 1px dashed var(--border);
  border-radius: 6px; cursor: pointer;
  transition: background 0.1s, border-color 0.1s;
}
.jv-add-label-btn:hover { background: var(--surface-secondary); border-color: var(--muted); }


/* ── Celebration ── */
.jv-celebrate-overlay {
  position: absolute; inset: 0;
  display: flex; align-items: center; justify-content: center;
  pointer-events: none; z-index: 200;
  background: rgba(255,255,255,.0);
}
.jv-celebrate-inner {
  display: flex; flex-direction: column; align-items: center; gap: 8px;
  pointer-events: none;
}
.jv-celebrate-burst { position: relative; width: 80px; height: 80px; }
.jv-particle {
  position: absolute; top: 50%; left: 50%;
  width: 6px; height: 6px; border-radius: 50%;
  animation: jv-burst 0.7s cubic-bezier(0,.9,.57,1) forwards;
  opacity: 0;
}
@keyframes jv-burst {
  0%  { transform: translate(-50%,-50%) rotate(var(--angle)) translateY(0); opacity: 1; }
  80% { opacity: 1; }
  100%{ transform: translate(-50%,-50%) rotate(var(--angle)) translateY(calc(-1 * var(--dist))); opacity: 0; }
}
.jv-celebrate-icon { font-size:var(--text-metric); animation: jv-pop .4s cubic-bezier(0.34,1.56,0.64,1); }
@keyframes jv-pop { from{transform:scale(0);opacity:0} to{transform:scale(1);opacity:1} }
.jv-celebrate-msg {
  font-size:var(--text-base); font-weight: 700; color: var(--success);
  animation: jv-pop .4s .15s cubic-bezier(0.34,1.56,0.64,1) both;
}
.jv-celebrate-enter-active { transition: opacity .2s; }
.jv-celebrate-leave-active { transition: opacity .4s .8s; }
.jv-celebrate-enter-from, .jv-celebrate-leave-to { opacity: 0; }

/* Linked issues empty */
.jv-linked-empty {
  display: flex; align-items: center; gap: 8px;
  padding: 4px 0; font-size:13px; font-weight:500; color: var(--muted);
}
.jv-add-link-btn {
  font-size:13px; font-weight: 600; color: var(--accent); background: none;
  border: none; cursor: pointer; padding: 0; font-family: inherit;
}
.jv-add-link-btn:hover { text-decoration: underline; }


/* ── On-spot creation ── */
.jv-inline-create {
  padding: 8px 10px 10px;
  display: flex; flex-direction: column; gap: 6px;
}
.jv-ic-input {
  width: 100%; height: 28px; padding: 0 8px;
  font-size:var(--text-sm); font-family: inherit; color: var(--foreground);
  background: var(--surface-secondary); border: 1px solid var(--border);
  border-radius: 6px; outline: none;
  transition: border-color .1s, background .1s;
}
.jv-ic-input:focus { background: var(--surface); border-color: var(--muted); box-shadow: 0 0 0 2px rgba(0,0,0,0.06); }
.jv-ic-colors { display: flex; gap: 4px; flex-wrap: wrap; }
.jv-ic-swatch {
  width: 16px; height: 16px; border-radius: 50%;
  border: 2px solid transparent; cursor: pointer;
  transition: transform .1s, border-color .1s;
}
.jv-ic-swatch:hover { transform: scale(1.15); }
.jv-ic-swatch.active { border-color: var(--foreground); }
.jv-ic-row { display: flex; align-items: center; gap: 6px; }
.jv-ic-select {
  flex: 1; height: 26px; padding: 0 6px;
  font-size:var(--text-sm); font-family: inherit;
  background: var(--surface-secondary); border: 1px solid var(--border);
  border-radius: 6px; outline: none; cursor: pointer;
}
.jv-ic-save {
  height: 26px; padding: 0 10px;
  font-size:var(--text-sm); font-weight: 600; font-family: inherit;
  color: var(--accent-foreground); background: var(--accent); border: none;
  border-radius: 6px; cursor: pointer;
  transition: background .1s;
}
.jv-ic-save:hover { background: var(--accent-hover); }
.jv-ic-save:disabled { opacity: .45; cursor: not-allowed; }


/* ── ERPNext References ── */
.jv-ref-add-row {
  display: flex; flex-direction: column; gap: 8px;
  padding: 0 0 8px;
}
.jv-ref-selects { display: flex; flex-direction: column; gap: 6px; }
.jv-ref-select {
  height: 30px; padding: 0 8px;
  font-size:var(--text-sm); font-family: inherit; color: var(--foreground);
  background: var(--surface-secondary); border: 1px solid var(--border);
  border-radius: 6px; outline: none; cursor: pointer;
  transition: border-color .1s;
}
.jv-ref-select:focus { background: var(--surface); border-color: var(--accent); }
.jv-ref-search-wrap {
  display: flex; align-items: center; gap: 6px;
  padding: 0 8px; height: 30px;
  background: var(--surface-secondary); border: 1px solid var(--border);
  border-radius: 6px; transition: border-color .1s;
}
.jv-ref-search-wrap:focus-within { background: var(--surface); border-color: var(--accent); }
.jv-ref-results {
  border: 1px solid var(--border); border-radius: 8px;
  background: var(--overlay); overflow: hidden;
}
.jv-ref-result {
  display: flex; align-items: center; gap: 8px;
  padding: 7px 10px; cursor: pointer; font-size:var(--text-sm);
  transition: background .08s;
}
.jv-ref-result:hover { background: var(--surface-secondary); }
.jv-ref-result-name { font-weight: 600; color: var(--foreground); }
.jv-ref-result-label { color: var(--muted); font-size:var(--text-sm); flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.jv-refs-list { display: flex; flex-direction: column; gap: 4px; padding: 0 0 4px; }
.jv-ref-row {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 0; border-bottom: 1px solid var(--surface-secondary);
}
.jv-ref-row:last-child { border-bottom: none; }
.jv-ref-doctype-badge {
  width: 26px; height: 26px; border-radius: 6px; flex-shrink: 0;
  background: var(--accent-soft); color: var(--accent);
  display: flex; align-items: center; justify-content: center;
  font-size:var(--text-micro); font-weight: 800; letter-spacing: 0.02em;
}
.jv-ref-info { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 1px; }
.jv-ref-doctype-label { font-size:var(--text-xs); color: var(--muted); font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; }
.jv-ref-link {
  display: inline-flex; align-items: center; gap: 4px;
  font-size:var(--text-sm); font-weight: 600; color: var(--accent);
  text-decoration: none;
  background: none; border: none; padding: 0; margin: 0; cursor: pointer; font-family: inherit;
}
.jv-ref-link:hover { text-decoration: underline; }
.jv-ref-sublabel { color: var(--muted); font-weight: 400; font-size:var(--text-sm); }
.jv-section-add-btn {
  display: flex; align-items: center; justify-content: center;
  width: 20px; height: 20px; border: none; background: none;
  color: var(--muted); cursor: pointer; border-radius: 6px;
  transition: background .1s, color .1s;
}
.jv-section-add-btn:hover { background: var(--surface-secondary); color: var(--foreground); }

</style>

<!-- Global override: DatePicker popover must appear above the panel -->
<style>
[data-reka-popper-content-wrapper],
[data-radix-popper-content-wrapper] {
  z-index: 9999 !important;
}

/* ── Celebration ── */
.jv-celebrate-overlay {
  position: absolute; inset: 0;
  display: flex; align-items: center; justify-content: center;
  pointer-events: none; z-index: 200;
  background: rgba(255,255,255,.0);
}
.jv-celebrate-inner {
  display: flex; flex-direction: column; align-items: center; gap: 8px;
  pointer-events: none;
}
.jv-celebrate-burst { position: relative; width: 80px; height: 80px; }
.jv-particle {
  position: absolute; top: 50%; left: 50%;
  width: 6px; height: 6px; border-radius: 50%;
  animation: jv-burst 0.7s cubic-bezier(0,.9,.57,1) forwards;
  opacity: 0;
}
@keyframes jv-burst {
  0%  { transform: translate(-50%,-50%) rotate(var(--angle)) translateY(0); opacity: 1; }
  80% { opacity: 1; }
  100%{ transform: translate(-50%,-50%) rotate(var(--angle)) translateY(calc(-1 * var(--dist))); opacity: 0; }
}
.jv-celebrate-icon { font-size:var(--text-metric); animation: jv-pop .4s cubic-bezier(0.34,1.56,0.64,1); }
@keyframes jv-pop { from{transform:scale(0);opacity:0} to{transform:scale(1);opacity:1} }
.jv-celebrate-msg {
  font-size:var(--text-base); font-weight: 700; color: var(--success);
  animation: jv-pop .4s .15s cubic-bezier(0.34,1.56,0.64,1) both;
}
.jv-celebrate-enter-active { transition: opacity .2s; }
.jv-celebrate-leave-active { transition: opacity .4s .8s; }
.jv-celebrate-enter-from, .jv-celebrate-leave-to { opacity: 0; }

/* Linked issues empty */
.jv-linked-empty {
  display: flex; align-items: center; gap: 8px;
  padding: 4px 0; font-size:var(--text-sm); color: var(--muted);
}
.jv-add-link-btn {
  font-size:var(--text-sm); font-weight: 600; color: var(--accent); background: none;
  border: none; cursor: pointer; padding: 0; font-family: inherit;
}
.jv-add-link-btn:hover { text-decoration: underline; }

</style>