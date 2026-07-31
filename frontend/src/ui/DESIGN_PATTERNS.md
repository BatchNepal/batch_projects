# Design Patterns

Component visual language: **HeroUI React** (see `src/ui/`).
Page layout, information density, and data hierarchy: **Linear / Jira / Wrike**.

These notes capture the structural patterns to apply when building or rebuilding pages.
They are layout decisions, not component implementations.

---

## MetricRow

Horizontal strip of key metrics. Each metric is a vertical pair: uppercase label above a large number.

- Label: `text-[11px] font-medium uppercase tracking-wider text-gray-500`
- Value: `text-2xl font-semibold text-gray-900 tabular-nums` (`tabular-nums` prevents jiggle when values update)
- Gap between metrics: `48px` (`gap-12`)
- No icon backgrounds, no pastel tiles, no rounded squares behind icons — just text
- Optional `sub` line below the value: `text-[11px] text-gray-400`

**Use instead of:** 4-up icon-tile dashboard cards. Those waste vertical space and add visual noise.
**Use on:** Summary page top section, Team home, Dashboard.

---

## StatusPill

Column header label for board views and status indicators everywhere.

- Structure: `[6px colored dot] [UPPERCASE LABEL] [optional count chip]`
- Dot: `w-1.5 h-1.5 rounded-full` in the status color
- Label: `text-[11px] font-medium uppercase tracking-wider text-gray-700`
- Count chip: `min-w-[1rem] h-4 px-1 rounded-full text-[10px] font-medium text-gray-600 bg-gray-100 tabular-nums`
- Colors: gray (todo/default), blue (in progress), green (done), red (blocked), orange (pending), purple (review)

**Use on:** Board column headers, status rows in Summary, status cells in DataTable.

---

## PriorityIndicator

14×14px SVG signal-bar icon. Three bars of increasing height, colored by priority level.

Bar positions (viewBox 0 0 14 14):

- Bar 1: `x=0 y=9 width=3 height=5`
- Bar 2: `x=5 y=6 width=3 height=8`
- Bar 3: `x=10 y=3 width=3 height=11`

Priority palette — **high and urgent must be visually distinct at 14px**:

- `none`:   `['#e4e4e7', '#f4f4f5', '#f4f4f5']` — barely visible, recedes from the eye
- `low`:    `['#60a5fa', '#e4e4e7', '#f4f4f5']` — blue bar 1 only
- `medium`: `['#f97316', '#f97316', '#e4e4e7']` — orange bars 1–2
- `high`:   `['#f97316', '#f97316', '#f97316']` — orange all 3 (needs attention soon)
- `urgent`: `['#ef4444', '#ef4444', '#ef4444']` — red all 3 + circle dot at `cx=11.5 cy=1.5 r=1.5` above bar 3

The dot on urgent is the critical differentiator — without it, high and urgent look the same.

**Use on:** Task cards, DataTable rows, task detail header, Backlog list rows.

---

## EmptyState

Centered empty state for columns, lists, and pages.

- Icon: 32px Lucide icon in `text-gray-300` — communicates category, not decoration
- Title: `text-sm font-medium text-gray-900`
- Description: `text-xs text-gray-500 max-w-[220px] leading-relaxed`
- Action: optional slot below description, typically a secondary or ghost Button
- Container: `min-height: 120px`, centered with `flex-col items-center justify-center`

**Use instead of:** bare text like "No issues found" or "Nothing here yet."
**Use on:** Empty board columns, empty list views, empty backlog, zero-state pages.

---

## DataTable

Compact tabular data. Power-user density — rows at 36px, not the spacious 48px Notion default.

- Row height: `h-9` (36px) on `<tr>`, `align-middle` on `<td>`
- Header: `text-[11px] font-medium uppercase tracking-wider text-gray-500`, no background fill, `border-b border-gray-200`
- Body rows: `bg-white border-b border-gray-100 hover:bg-gray-50 transition-colors duration-75`
- Cell padding: `px-3`
- Skeleton loading: `loading` prop renders N rows (default 6) of `animate-pulse bg-gray-100 h-2.5 rounded` bars at deterministic-varying widths so columns look proportional

Column definition: `{ key: string, label: string, width?: string }`
Cell slot: `` `#cell-{key}` `` receives `{ row, col, value }`

**Use on:** Summary recent activity, Backlog issue list, List view, any tabular output.

---

## FilterChip

Filter bar pill. 28px height, minimal — label only, no left icon.

- Height: `h-7` (28px)
- Padding: `px-2` (8px)
- Inactive: `bg-white border border-gray-200 text-gray-600 hover:bg-gray-50`
- Active: `bg-gray-100 border-gray-200 text-gray-900` — shows value inline as `"Priority: High"`
- Right icon: `ChevronDown` at 12px — omit with `hasMenu: false` for toggle-style filters
- No icon on the left

**Use on:** ProjectHeader filter row (Priority, Type, Label, Group, Sort), any toolbar filter strip.

---

## SectionCard

Dashboard section wrapper. White card with hover shadow.

- Background: `bg-white`
- Border: `border border-gray-200`
- Radius: `rounded-lg` (8px)
- Shadow: none at rest, `shadow-sm` on hover — `transition-shadow duration-150`
- Header: `px-4 py-3 border-b border-gray-100` — title (`text-sm font-semibold text-gray-900`) + optional subtitle (`text-xs text-gray-500`)
- "View all" link: right-aligned, primary accent color, renders as `<RouterLink>` when `to` prop is given (no full reload)
- Content: `p-4` slot

**Use on:** Summary page sections (Recent Activity, Progress, Open Issues), Dashboard widgets.

---

## ViewTabs

Text-only tab strip for page-level view switching.

- Tab height: `h-8` (32px)
- Tab padding: `px-4` (16px horizontal)
- Inactive: `text-gray-600 hover:text-gray-900`
- Active: `text-gray-900` + `absolute bottom-0 h-0.5 bg-gray-900` underline (2px, full tab width)
- Container: `border-b border-gray-200`
- No icons inside tabs — label text only

**Use on:** Summary/Board/List/Backlog switcher in ProjectHeader (currently a custom segment pill — ViewTabs is the simpler replacement).

---

## Layout Density Rule

Default to **Linear/Plane density**, not Notion density.

- Rows at 36px, not 48px
- Section padding at 16px, not 24px
- Gap between sections at 24px (`gap-6`), not 32px
- Font sizes: 11px for meta labels, 13px for body, 15px for section titles, never go above `text-lg` on a data page

Power users skim rows quickly. Casual users tolerate density when hierarchy is clear. Extra whitespace makes data pages feel like landing pages.

---

## Component Decision Trees

How to pick the right prop combination from `src/ui/`. Import everything from `'@/ui'`.

---

### Button

Full API: `variant` × `color` × `size` × `isIconOnly` × `isLoading` × `isDisabled` × `fullWidth`.

**Default** (`variant="solid" color="default"`) renders a neutral gray button — **not** a primary CTA. To get the blue primary button you must set `color="primary"`.

| Situation | Usage |
|---|---|
| Primary CTA — the main action on a page or modal | `variant="solid" color="primary"` |
| Secondary / Cancel alongside a primary CTA | `variant="bordered" color="default"` |
| Destructive — confirmed delete / remove / archive | `variant="solid" color="danger"` |
| Destructive — one step before confirmation dialog | `variant="bordered" color="danger"` |
| Tertiary toolbar action — no strong visual weight needed | `variant="light" color="default"` |
| Ghost / outline that fills on hover — toggle states | `variant="ghost" color="primary"` (or matching color) |
| Flat tint — filter tag, category action, subtle CTA | `variant="flat" color="primary"` |
| Floating / elevated CTA | `variant="shadow" color="primary"` |
| Icon-only in a toolbar | `isIconOnly` + `variant="light" color="default"` + `size="sm"` |
| Icon-only primary action | `isIconOnly` + `variant="solid" color="primary"` + `size="md"` |
| Async operation — show spinner | `:isLoading="true"` — Spinner renders automatically, no extra code |
| Full-width (modal footer, form submit) | `fullWidth` |

**Size guide:** `size="sm"` (h-8, 32px) for toolbars and dense rows — `size="md"` (h-10, 40px) for standard buttons — `size="lg"` (h-12, 48px) for landing-page-scale CTAs.

**`as` prop:** Render as a different element without losing styling. `as="a"` for external links, `as="RouterLink"` for SPA navigation, `as="div"` if needed for nesting inside other interactive elements.

Slots: `startContent` and `endContent` for leading/trailing icons at the correct spacing. Default slot is the label text.

---

### Input

Full API: `size` × `type` × `isClearable` × `isDisabled` × `isReadOnly` × `isRequired` × `isInvalid` + `label` + `placeholder` + `description` + `errorMessage`.

| Situation | Usage |
|---|---|
| Standard form field | Global flat standard (default). `bg-gray-100` at rest, `bg-white ring-2 ring-[#1e96eb]/40` on focus. No borders. |
| Error state | `:isInvalid="true" errorMessage="Field is required"` — turns white + red ring |
| Leading icon (search, user, etc.) | `startContent` slot: `<Icon :icon="Search" />` at 16px |
| Trailing content (units, actions) | `endContent` slot |
| Disabled / read-only | `:isDisabled` or `:isReadOnly` — use read-only for display-mode fields that might become editable |

**Size guide:** Same as Button — `sm` for dense rows, `md` for forms, `lg` for prominent standalone fields (e.g. project name on create screen).

Do NOT use `color` or `variant` prop for Input, the canonical flat design is the only one. For per-field errors, use `isInvalid` instead.

---

### Select / SelectItem / SelectSection

Full API: `size` × `labelPlacement` × `selectionMode` × `isDisabled` × `isRequired` × `isInvalid`. Children: `<SelectItem>` and optionally `<SelectSection>`.

```vue
<!-- Standard single select -->
<Select v-model="val" label="Status">
  <SelectItem value="todo">Todo</SelectItem>
  <SelectItem value="in-progress">In Progress</SelectItem>
  <SelectItem value="done">Done</SelectItem>
</Select>

<!-- Multi-select with chips (assignees, labels) -->
<Select v-model="vals" selectionMode="multiple" label="Assignees">
  <SelectItem v-for="u in users" :key="u.id" :value="u.id">{{ u.name }}</SelectItem>
</Select>

<!-- Grouped options -->
<Select v-model="val" label="Priority">
  <SelectSection label="Active">
    <SelectItem value="urgent">Urgent</SelectItem>
    <SelectItem value="high">High</SelectItem>
  </SelectSection>
  <SelectSection label="Passive">
    <SelectItem value="low">Low</SelectItem>
    <SelectItem value="none">None</SelectItem>
  </SelectSection>
</Select>
```

| Situation | Usage |
|---|---|
| Standard form dropdown | Global flat standard (default), `labelPlacement="outside"` (default) |
| Floating label (dense forms, inside card) | `labelPlacement="inside"` — label floats above value when focused/filled |
| Label to the left of field | `labelPlacement="outside-left"` — for horizontal form layouts |
| Multi-value (tags, labels, assignees) | `selectionMode="multiple"` — selected items render as removable chips |
| Error state | `:isInvalid="true" errorMessage="..."` |

---

### Textarea

Full API: `rows` × `isDisabled` × `isReadOnly` × `isRequired` × `isInvalid` + `label` + `placeholder` + `description` + `errorMessage`.

No `size`, `variant` or `color` prop. Height is controlled by `rows`. Uses Global flat standard by default.

| Situation | Usage |
|---|---|
| Comments, task description, notes | Global flat standard (default), `rows=3` |
| Longer content (project description, acceptance criteria) | `:rows="5"` |
| Error state | `:isInvalid="true" errorMessage="..."` |

---

### Other components in `src/ui/`

| Component | When to use |
|---|---|
| `Avatar` | User/member display everywhere. Already used in TaskCard, ProjectHeader. Props: `name` (generates initials), `src` (image URL), `size`. |
| `Chip` | Status tags, label badges inline with text. Smaller and more inline than Button. |
| `Checkbox` | Boolean form fields. `:isSelected` + `@update:isSelected`. |
| `Switch` | Toggle settings. Prefer over Checkbox for on/off system preferences. |
| `Modal` + `ModalHeader` + `ModalBody` + `ModalFooter` | All dialogs. Never use browser `alert()`/`confirm()`. `ModalFooter` slots: `startContent` (secondary actions left) and `endContent` (primary CTA right). |
| `Tooltip` | Hover explanation for icon-only buttons, truncated text. Keep tooltip text under 80 chars. |
| `Accordion` / `AccordionItem` | Collapsible sections in settings and detail panels. |
| `Divider` | Horizontal rule between sections. Prefer `border-t border-gray-100` in tight layouts. |
| `Icon` | Lucide icon wrapper with 16px / 1.5px stroke defaults. `<Icon :icon="Search" />` or override: `<Icon :icon="Plus" :size="18" />`. |
| `IconButton` | Icon-only button shorthand. Equivalent to `Button` with `isIconOnly`. |
| `Spinner` | Loading state. Already used in Board.vue. |

---

### Primitives not yet in `src/ui/` — build before Summary rebuild

These are documented above as layout patterns but not yet implemented as components. Build them in `src/ui/` using HeroUI visual tokens (primary blue, neutral palette, existing typography scale) before rebuilding ProjectSummary:

- `MetricRow` — horizontal metric strip
- `SectionCard` — white card wrapper with header + hover shadow
- `StatusPill` — dot + uppercase label + count chip
- `FilterChip` — 28px filter bar pill
- `ViewTabs` — tab strip with underline indicator
- `PriorityIndicator` — 14px SVG signal-bar icon
- `DataTable` — compact 36px-row table with skeleton loading
- `EmptyState` — centered 120px empty state

They should feel like they came from the same design system as Button and Select — same corner radii, same color tokens, same typography scale. Not the stark Linear aesthetic from the deleted `src/components/ui/` experiment.

---

### Note on `src/components/ui/` (shadcn primitives)

Complex primitives that `src/ui/` doesn't yet provide (Popover, Dialog, Command palette) live in `src/components/ui/` from shadcn-vue. Currently used by: `DatePicker.vue` (Popover), `CommandDialog.vue` (Dialog). Use them as-is. When `src/ui/` adds equivalents, migrate. Do not duplicate.

---

## Never-Do Rules

These were identified from evaluating earlier implementations against the Linear/Plane reference:

1. **No pastel icon background tiles on metric cards.** No `bg-green-100` rounded squares with an icon inside. Icons stand alone or are omitted.
2. **No charts with fewer than 3 data points.** Show a number or a simple list instead. A bar chart with 1–2 bars is noise.
3. **No decorative icons.** Every icon must carry information. If you can remove it without losing meaning, remove it.
4. **No left icon inside FilterChip labels.** Label + optional value text + chevron on right. Nothing on the left.
5. **No full-page-reload navigation in SPA context.** `<RouterLink>` over `<a href>` for internal links.
6. **No uniform skeleton bars.** Vary widths per column so skeleton looks like real proportional data.
7. **No tracking-wider on anything except uppercase labels.** Body text, headings, counts — no letter-spacing.

---

## The Composition Law (2026-07-12)

Why apps look "Bootstrap" despite good components: it's never the atoms, it's the
decisions BETWEEN them. These rules are binding for every screen. The reference
implementation is the Gantt toolbar (`pages/Gantt.vue`) — copy its recipe.

### 1. Color allocation
The chrome whispers, the data sings. Saturated color exists ONLY on user data
(status, bars, avatars, labels, charts). Chrome uses neutrals + exactly one
interaction accent (`var(--accent)`). Never tint chrome: no colored toolbar
buttons, no colored section headers, no accent borders as decoration.

### 2. The metric scale — the ONLY values that exist
- **Control heights:** 28 (toolbars/dense) · 32 (forms) · 40 (primary CTA, rare)
- **Radii:** 6 (controls) · 10 (cards/frames/overlays) · 999 (chips + avatars ONLY)
  · 4 (data-viz shapes: gantt bars, chart marks)
- **Gaps/padding steps:** 4 · 8 · 12 · 16 · 24 (page gutters stay 20/24 as shipped)
- **Text:** 11 uppercase labels · 12.5 secondary · 13 body · 14 section titles ·
  16+ page titles only. Weights 400/500/600 — 600 for anything structural.
  Numbers ALWAYS `tabular-nums`.

### 3. Separation language
Background shifts and whitespace FIRST. Borders are permitted in exactly three
places: one hairline under a sticky header, around text inputs, table row
hairlines. NEVER around buttons, toolbars, or segmented controls — if a bg
shift can separate it, a border may not.

### 4. Buttons & controls
- Default chrome button = **ghost**: transparent, `var(--muted)` text, hover =
  `var(--surface-hover)` bg + `var(--foreground)` text. No border, no shadow.
- Exactly ONE filled primary button per view.
- Segmented control = filled track (`var(--surface-secondary)`, 2px padding,
  radius 8) with the active segment lifted (`var(--surface)` + `--shadow-xs`).
  No borders, no divider lines between segments.

### 5. Shadows
Reserved for genuine elevation: popovers, drawers, drag ghosts, and hover-lift
on *clickable cards / draggable bars*. Never on static cards, never on buttons,
never as decoration. (No Bootstrap `box-shadow: 0 .125rem .25rem` haze.)

### 6. States & motion
Hover = background tint, never a color flip. 120–150ms ease on enter/leave
states ONLY — never transition a property that tracks the pointer (see the
Gantt smoothness doctrine in WORKPLAN 7B-XL). Consistent focus rings. Skeletons
over spinners.
