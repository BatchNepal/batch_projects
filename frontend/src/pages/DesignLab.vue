<template>
  <div class="lab-root">
    <header class="lab-head">
      <h1>Design Lab</h1>
      <p>The same "Create project" form, four design languages — values pulled from each system's released tokens. Pick the law.</p>
    </header>

    <section class="mb-10">
      <p class="text-[13px] font-semibold text-foreground mb-1">Split menu button — action + arrow pill, HeroUI card popover</p>
      <p class="text-[12px] text-muted mb-4">Depth from fill + shadow + press physics, not borders.</p>
      <div class="flex items-center gap-4 flex-wrap">
        <SplitMenuButton label="New project" :icon="Plus" :options="smbOptions" @action="smbLog('primary action')" @select="o => smbLog(o.label)" />
        <span class="text-[12px] text-muted">{{ smbLast }}</span>
      </div>
    </section>

    <div class="lab-grid">

      <!-- ════ JIRA — Atlassian DS, 2025 visual refresh ════
           tokens fetched from @atlaskit/tokens: input bg #F8F8F8 (whitens on
           hover), text #1E2125 / #505258, brand #1558BC -->
      <section class="lab-cell" style="background:#FFFFFF">
        <div class="lab-tag">Jira · Atlassian (2025 refresh)</div>

        <div class="f-jira">
          <h2 class="j-title">Add project details</h2>
          <p class="j-sub">You can change these details anytime in your project settings.</p>

          <div class="j-field">
            <label class="j-label">Name<span class="j-req"> *</span></label>
            <input class="j-input" v-model="jira.name" placeholder="Try a team name, project goal, milestone..." />
          </div>

          <div class="j-row">
            <div class="j-field" style="flex:0 0 110px">
              <label class="j-label">Key<span class="j-req"> *</span></label>
              <input class="j-input j-key" v-model="jira.key" />
            </div>
            <div class="j-field" style="flex:1">
              <label class="j-label">Template</label>
              <div class="j-selwrap">
                <select class="j-input j-select" v-model="jira.template">
                  <option>Kanban</option><option>Scrum</option><option>Bug tracking</option>
                </select>
                <svg class="j-chev" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6"/></svg>
              </div>
            </div>
          </div>

          <div class="j-field">
            <label class="j-label">Access</label>
            <div class="j-selwrap">
              <select class="j-input j-select" v-model="jira.access">
                <option>Open — anyone in the workspace</option>
                <option>Private — members only</option>
              </select>
              <svg class="j-chev" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6"/></svg>
            </div>
          </div>

          <div class="j-footer">
            <button class="j-btn j-btn--subtle">Cancel</button>
            <button class="j-btn j-btn--primary">Next</button>
          </div>
        </div>

        <ul class="lab-traits">
          <li>Gray-filled inputs #F8F8F8 → turn WHITE on hover</li>
          <li>Focus = 2px blue border swap, no ring/shadow</li>
          <li>11px bold uppercase-ish labels, dense</li>
          <li>4px radius, 32px compact buttons, brand #1558BC</li>
          <li>Zero shadows anywhere</li>
        </ul>
      </section>

      <!-- ════ MONDAY.COM — values verified from open-source Vibe ════
           radius-small 4px everywhere, 1px #C3C6D4, hover border #323338,
           focus #0073EA, Figtree -->
      <section class="lab-cell" style="background:#FFFFFF">
        <div class="lab-tag">monday.com · Vibe (exact)</div>

        <div class="f-monday">
          <h2 class="m-title">Create board</h2>

          <div class="m-field">
            <label class="m-label">Board name</label>
            <input class="m-input" v-model="monday.name" placeholder="New Board" />
          </div>

          <div class="m-field">
            <label class="m-label">Privacy</label>
            <div class="m-radios">
              <label class="m-radio" :class="{ on: monday.privacy === 'main' }">
                <input type="radio" value="main" v-model="monday.privacy" /><span class="m-dot" />
                Main <em>— visible to everyone</em>
              </label>
              <label class="m-radio" :class="{ on: monday.privacy === 'private' }">
                <input type="radio" value="private" v-model="monday.privacy" /><span class="m-dot" />
                Private
              </label>
            </div>
          </div>

          <div class="m-field">
            <label class="m-label">Select what you're managing in this board</label>
            <div class="m-chips">
              <button v-for="c in ['Items','Clients','Projects','Tasks']" :key="c"
                class="m-chip" :class="{ on: monday.manage === c }" @click="monday.manage = c">{{ c }}</button>
            </div>
          </div>

          <div class="m-footer">
            <button class="m-btn m-btn--ghost">Cancel</button>
            <button class="m-btn m-btn--primary">Create Board</button>
          </div>
        </div>

        <ul class="lab-traits">
          <li>4px radius on EVERYTHING (verified: --border-radius-small)</li>
          <li>1px #C3C6D4 → hover darkens to TEXT color #323338</li>
          <li>Focus = 1px #0073EA, nothing else</li>
          <li>40px fields / 32px buttons, airy 24px gaps</li>
          <li>Figtree, regular-weight labels</li>
        </ul>
      </section>

      <!-- ════ ASANA ════
           warm greige, huge borderless name, in-product CTAs are BLUE
           #4573D2 (coral is brand, not buttons) -->
      <section class="lab-cell" style="background:#F9F8F8">
        <div class="lab-tag">Asana</div>

        <div class="f-asana">
          <h2 class="a-title">New project</h2>

          <div class="a-field">
            <input class="a-bigname" v-model="asana.name" placeholder="Project name" />
          </div>

          <div class="a-row">
            <div class="a-field" style="flex:1">
              <label class="a-label">Team</label>
              <select class="a-input" v-model="asana.team">
                <option>Engineering</option><option>Design</option><option>Marketing</option>
              </select>
            </div>
            <div class="a-field" style="flex:1">
              <label class="a-label">Privacy</label>
              <select class="a-input" v-model="asana.privacy">
                <option>Shared with team</option><option>Private to members</option>
              </select>
            </div>
          </div>

          <div class="a-field">
            <label class="a-label">Default view</label>
            <div class="a-views">
              <button v-for="v in ['List','Board','Timeline','Calendar']" :key="v"
                class="a-view" :class="{ on: asana.view === v }" @click="asana.view = v">{{ v }}</button>
            </div>
          </div>

          <div class="a-footer">
            <button class="a-btn a-btn--secondary">Cancel</button>
            <button class="a-btn a-btn--primary">Create project</button>
          </div>
        </div>

        <ul class="lab-traits">
          <li>Warm greige canvas #F9F8F8, near-black #1E1F21 text</li>
          <li>Huge borderless name — border appears on hover</li>
          <li>1px #CFCBCB, 6px radius, focus darkens to charcoal</li>
          <li>CTA is BLUE #4573D2 (coral = brand only)</li>
          <li>36px controls, soft single shadow on the dialog</li>
        </ul>
      </section>

      <!-- ════ HEROUI (heroui.com v2 look) ════
           flat FILLED fields #F4F4F5 (no border, no shadow), 12px radius,
           40px heights, primary #006FEE, card 14px + layered shadow-medium -->
      <section class="lab-cell" style="background:#FFFFFF">
        <div class="lab-tag">HeroUI (heroui.com)</div>

        <div class="f-hero">
          <h2 class="h-title">Create project</h2>
          <p class="h-sub">Flat filled fields — the heroui.com signature.</p>

          <div class="h-field">
            <label class="h-label">Project name</label>
            <input class="h-input" v-model="hero.name" placeholder="e.g. Website Redesign" />
          </div>

          <div class="h-row">
            <div class="h-field" style="flex:0 0 110px">
              <label class="h-label">Key</label>
              <input class="h-input h-key" v-model="hero.key" />
            </div>
            <div class="h-field" style="flex:1">
              <label class="h-label">Template</label>
              <div class="h-selwrap">
                <select class="h-input h-select" v-model="hero.template">
                  <option>Kanban</option><option>Scrum</option><option>Client delivery</option>
                </select>
                <svg class="h-chev" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6"/></svg>
              </div>
            </div>
          </div>

          <div class="h-field">
            <label class="h-label">Visibility</label>
            <div class="h-selwrap">
              <select class="h-input h-select" v-model="hero.visibility">
                <option>Workspace</option><option>Private</option>
              </select>
              <svg class="h-chev" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6"/></svg>
            </div>
          </div>

          <div class="h-footer">
            <button class="h-btn h-btn--ghost">Cancel</button>
            <button class="h-btn h-btn--primary">Create project</button>
          </div>
        </div>

        <ul class="lab-traits">
          <li>Fields = flat gray FILL #F4F4F5, no border, no shadow</li>
          <li>Hover deepens fill #E4E4E7; ring only on keyboard focus</li>
          <li>12px field/button radius (not pills!), 40px heights</li>
          <li>Primary #006FEE, hover = 90% opacity, press scale .97</li>
          <li>Card: 14px radius + layered shadow-medium</li>
        </ul>
      </section>

    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { SplitMenuButton } from '@/ui'
import { Plus, FilePlus, LayoutGrid, Sparkles } from 'lucide-vue-next'
const smbLast = ref('')
function smbLog(x){ smbLast.value = 'Picked: ' + x }
const smbOptions = [
  { label: 'Blank project', desc: 'Start from scratch.',        icon: FilePlus,  color: '#64748B' },
  { label: 'From template',  desc: 'Pick a preset workflow.',    icon: LayoutGrid, color: '#2684FF' },
  { label: 'AI setup',       desc: 'Describe it, we scaffold.',  icon: Sparkles,  color: '#8B5CF6' },
]

const jira   = reactive({ name: '', key: 'WEB', template: 'Kanban', access: 'Open — anyone in the workspace' })
const monday = reactive({ name: '', privacy: 'main', manage: 'Projects' })
const asana  = reactive({ name: '', team: 'Engineering', privacy: 'Shared with team', view: 'Board' })
const hero   = reactive({ name: '', key: 'WEB', template: 'Kanban', visibility: 'Workspace' })
</script>

<style scoped>
/* ════════ Lab chrome ════════ */
.lab-root { min-height: 100%; overflow-y: auto; background: var(--background); padding: 40px 32px 64px; }
.lab-head h1 { font-size: 22px; font-weight: 700; color: var(--foreground); }
.lab-head p  { font-size: 13px; color: var(--muted); margin-top: 4px; }
.lab-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-top: 28px; max-width: 1200px; }
.lab-cell { border-radius: 16px; padding: 28px; box-shadow: var(--surface-shadow); position: relative; display: flex; flex-direction: column; }
.lab-tag {
  position: absolute; top: -10px; left: 20px; font-size: 11px; font-weight: 700;
  letter-spacing: .04em; padding: 3px 10px; border-radius: 99px;
  background: var(--foreground); color: var(--surface);
}
.lab-traits { margin-top: auto; padding-top: 20px; display: flex; flex-direction: column; gap: 3px; }
.lab-traits li { font-size: 11px; color: var(--muted); list-style: none; }
.lab-traits li::before { content: '— '; }

/* ════════ 1. JIRA — Atlassian 2025 refresh ════════ */
.f-jira { font-family: -apple-system, "Segoe UI", Roboto, sans-serif; color: #1E2125; max-width: 420px; }
.j-title { font-size: 20px; font-weight: 600; color: #1E2125; letter-spacing: -0.01em; }
.j-sub   { font-size: 14px; color: #505258; margin: 4px 0 20px; }
.j-field { margin-bottom: 14px; }
.j-row   { display: flex; gap: 12px; }
.j-label { display: block; font-size: 11px; font-weight: 700; color: #505258; margin-bottom: 4px; }
.j-req   { color: #AE2A19; }
.j-input {
  width: 100%; height: 36px; padding: 0 8px; font-size: 14px; color: #1E2125;
  background: #F8F8F8; border: 1px solid #F8F8F8; border-radius: 4px; outline: none;
  transition: background 150ms ease, border-color 150ms ease;
}
.j-input:hover  { background: #FFFFFF; border-color: #B7B9BE; }
.j-input:focus  { background: #FFFFFF; border-color: #4688EC; box-shadow: inset 0 0 0 1px #4688EC; }
.j-input::placeholder { color: #6B6E76; }
.j-key { text-transform: uppercase; font-weight: 600; }
.j-selwrap { position: relative; }
.j-select { appearance: none; cursor: pointer; padding-right: 28px; }
.j-chev { position: absolute; right: 6px; top: 50%; transform: translateY(-50%); color: #505258; pointer-events: none; }
.j-footer { display: flex; justify-content: flex-end; gap: 8px; margin-top: 22px; }
.j-btn {
  height: 32px; padding: 0 12px; font-size: 14px; font-weight: 500;
  border-radius: 4px; border: none; cursor: pointer; transition: background 120ms ease;
  font-family: inherit;
}
.j-btn--subtle  { background: transparent; color: #1E2125; }
.j-btn--subtle:hover  { background: #0B120E14; }
.j-btn--primary { background: #1558BC; color: #FFFFFF; }
.j-btn--primary:hover { background: #144794; }

/* ════════ 2. MONDAY.COM — exact Vibe values ════════ */
.f-monday { font-family: 'Figtree', 'Roboto', -apple-system, sans-serif; color: #323338; max-width: 440px; }
.m-title { font-size: 24px; font-weight: 500; color: #323338; margin-bottom: 24px; }
.m-field { margin-bottom: 24px; }
.m-label { display: block; font-size: 14px; font-weight: 400; color: #323338; margin-bottom: 8px; }
.m-input {
  width: 100%; height: 40px; padding: 8px 12px; font-size: 14px; color: #323338;
  background: #FFFFFF; border: 1px solid #C3C6D4; border-radius: 4px; outline: none;
  transition: border-color 150ms ease-in;
  font-family: inherit;
}
.m-input:hover { border-color: #323338; }
.m-input:focus { border-color: #0073EA; }
.m-input::placeholder { color: #676879; }
.m-radios { display: flex; gap: 24px; }
.m-radio  { display: flex; align-items: center; gap: 8px; font-size: 14px; cursor: pointer; }
.m-radio em { font-style: normal; color: #676879; font-size: 13px; }
.m-radio input { display: none; }
.m-dot {
  width: 16px; height: 16px; border-radius: 50%; border: 1px solid #C3C6D4;
  transition: border-color 100ms ease;
}
.m-radio.on .m-dot { border: 5px solid #0073EA; }
.m-chips { display: flex; gap: 8px; flex-wrap: wrap; }
.m-chip {
  height: 32px; padding: 0 12px; font-size: 14px; color: #323338; cursor: pointer;
  background: #FFFFFF; border: 1px solid #C3C6D4; border-radius: 4px;
  transition: all 150ms ease-in; font-family: inherit;
}
.m-chip:hover { border-color: #323338; }
.m-chip.on { background: #CCE5FF; border-color: #0073EA; color: #0073EA; }
.m-footer { display: flex; justify-content: flex-end; gap: 8px; margin-top: 28px; }
.m-btn {
  height: 32px; padding: 8px 16px; display: inline-flex; align-items: center;
  font-size: 14px; font-weight: 400; line-height: 1;
  border-radius: 4px; border: none; cursor: pointer; transition: background 150ms ease-in;
  font-family: inherit;
}
.m-btn--ghost { background: transparent; color: #323338; }
.m-btn--ghost:hover { background: #6768791A; }
.m-btn--primary { background: #0073EA; color: #FFFFFF; }
.m-btn--primary:hover { background: #0060B9; }

/* ════════ 3. ASANA ════════ */
.f-asana { font-family: -apple-system, "Helvetica Neue", sans-serif; color: #1E1F21; max-width: 440px;
  background: #FFFFFF; border-radius: 8px; padding: 24px; box-shadow: 0 1px 3px rgba(0,0,0,.06), 0 4px 12px rgba(0,0,0,.04); }
.a-title { font-size: 16px; font-weight: 500; color: #6D6E6F; margin-bottom: 12px; }
.a-field { margin-bottom: 20px; }
.a-row { display: flex; gap: 16px; }
.a-bigname {
  width: 100%; font-size: 24px; font-weight: 500; color: #1E1F21;
  border: 1px solid transparent; border-radius: 6px; padding: 8px 10px; margin-left: -10px;
  outline: none; background: transparent; transition: border-color 120ms ease;
  font-family: inherit;
}
.a-bigname:hover { border-color: #CFCBCB; }
.a-bigname:focus { border-color: #1E1F21; }
.a-bigname::placeholder { color: #A2A0A2; }
.a-label { display: block; font-size: 13px; color: #1E1F21; margin-bottom: 6px; }
.a-input {
  width: 100%; height: 36px; padding: 0 10px; font-size: 14px; color: #1E1F21;
  background: #FFFFFF; border: 1px solid #CFCBCB; border-radius: 6px; outline: none;
  transition: border-color 120ms ease; cursor: pointer; font-family: inherit;
}
.a-input:hover { border-color: #A2A0A2; }
.a-input:focus { border-color: #1E1F21; }
.a-views { display: flex; gap: 8px; }
.a-view {
  height: 32px; padding: 0 12px; font-size: 13px; color: #1E1F21; cursor: pointer;
  background: #FFFFFF; border: 1px solid #CFCBCB; border-radius: 6px;
  transition: all 120ms ease; font-family: inherit;
}
.a-view:hover { background: #F9F8F8; }
.a-view.on { border-color: #1E1F21; background: #F9F8F8; font-weight: 500; }
.a-footer { display: flex; justify-content: flex-end; gap: 8px; margin-top: 24px; }
.a-btn {
  height: 36px; padding: 0 12px; font-size: 14px; font-weight: 500;
  border-radius: 6px; cursor: pointer; transition: all 120ms ease; font-family: inherit;
}
.a-btn--secondary { background: #FFFFFF; color: #1E1F21; border: 1px solid #CFCBCB; }
.a-btn--secondary:hover { background: #F9F8F8; }
.a-btn--primary { background: #4573D2; color: #FFFFFF; border: none; }
.a-btn--primary:hover { background: #3C66BC; }

/* ════════ 4. HEROUI — heroui.com v2 language ════════
   Flat FILLED fields: bg default-100 #F4F4F5, no border, no shadow,
   radius-medium 12px, h-40. Hover default-200 #E4E4E7. Primary #006FEE.
   Card radius-large 14px + shadow-medium (exact NextUI value). */
.f-hero { font-family: inherit; color: #11181C; max-width: 420px;
  background: #FFFFFF; border-radius: 14px; padding: 24px;
  box-shadow: 0px 0px 15px 0px rgba(0,0,0,0.03), 0px 2px 30px 0px rgba(0,0,0,0.08), 0px 0px 1px 0px rgba(0,0,0,0.3); }
.h-title { font-size: 18px; font-weight: 600; color: #11181C; }
.h-sub { font-size: 13px; color: #71717A; margin: 2px 0 20px; }
.h-field { margin-bottom: 16px; }
.h-row { display: flex; gap: 12px; }
.h-label { display: block; font-size: 14px; font-weight: 500; color: #11181C; margin-bottom: 6px; }
.h-input {
  width: 100%; height: 40px; padding: 0 12px; font-size: 14px; color: #11181C;
  background: #F4F4F5; border: none; border-radius: 12px; outline: none;
  transition: background-color 150ms ease;
  font-family: inherit;
}
.h-input:hover { background: #E4E4E7; }
.h-input:focus-visible { outline: 2px solid #006FEE; outline-offset: 2px; }
.h-input::placeholder { color: #71717A; }
.h-key { text-transform: uppercase; font-weight: 600; }
.h-selwrap { position: relative; }
.h-select { appearance: none; cursor: pointer; padding-right: 32px; }
.h-chev { position: absolute; right: 10px; top: 50%; transform: translateY(-50%); color: #71717A; pointer-events: none; }
.h-footer { display: flex; justify-content: flex-end; gap: 10px; margin-top: 24px; }
.h-btn {
  height: 40px; padding: 0 16px; font-size: 14px; font-weight: 500;
  border-radius: 12px; border: none; cursor: pointer;
  transition: transform 250ms ease, opacity 150ms ease, background-color 150ms ease;
  font-family: inherit;
}
.h-btn:active { transform: scale(0.97); }
.h-btn--ghost { background: transparent; color: #11181C; }
.h-btn--ghost:hover { background: #F4F4F5; }
.h-btn--primary { background: #006FEE; color: #FFFFFF; }
.h-btn--primary:hover { opacity: 0.9; }

@media (max-width: 980px) { .lab-grid { grid-template-columns: 1fr; } }
</style>
