// Project theme avatars — complete pre-rendered tiles (bold color fill +
// illustrated character, baked as one image) supplied directly by design,
// matching Jira's real avatar language. Each project gets a distinct,
// memorable identity instead of a plain color dot — see the Dashboard
// "Project Health" cards. Assigned round-robin at project creation; stored
// on BP Project as `theme` (falls back to a hash-of-key pick for projects
// created before this existed, so nothing shows blank).
import koalaBlue    from '@/bp-icons/koala-blue.png'
import koalaGreen   from '@/bp-icons/koala-green.png'
import koalaRed     from '@/bp-icons/koala-red.png'
import notesOrange  from '@/bp-icons/notes-orange.png'
import notesPurple  from '@/bp-icons/notes.png'
import treasureGray from '@/bp-icons/treasure-gray.png'
import treasureSand from '@/bp-icons/treasure-sand.png'
import whiteboard   from '@/bp-icons/whiteboard.png'
import yetiBlue      from '@/bp-icons/yeti-blue.png'
import yetiGreen     from '@/bp-icons/yeti-green.png'

export const PROJECT_THEMES = {
  koalaBlue:    { label: 'Koala (blue)',    icon: koalaBlue },
  koalaGreen:   { label: 'Koala (green)',   icon: koalaGreen },
  koalaRed:     { label: 'Koala (red)',     icon: koalaRed },
  notesOrange:  { label: 'Sticky notes (orange)', icon: notesOrange },
  notesPurple:  { label: 'Sticky notes (purple)', icon: notesPurple },
  treasureGray: { label: 'Treasure chest (gray)', icon: treasureGray },
  treasureSand: { label: 'Treasure chest (sand)', icon: treasureSand },
  whiteboard:   { label: 'Whiteboard',      icon: whiteboard },
  yetiBlue:     { label: 'Yeti (blue)',     icon: yetiBlue },
  yetiGreen:    { label: 'Yeti (green)',    icon: yetiGreen },
}

export const PROJECT_THEME_KEYS = Object.keys(PROJECT_THEMES)

/** Deterministic fallback for projects created before `theme` existed —
 *  same key always resolves to the same theme, so it doesn't reshuffle
 *  on every render, but doesn't require a migration either. */
export function resolveProjectTheme(theme, fallbackSeed) {
  if (theme && PROJECT_THEMES[theme]) return PROJECT_THEMES[theme]
  let h = 0
  for (const ch of (fallbackSeed || '')) h = ch.charCodeAt(0) + ((h << 5) - h)
  return PROJECT_THEMES[PROJECT_THEME_KEYS[Math.abs(h) % PROJECT_THEME_KEYS.length]]
}
