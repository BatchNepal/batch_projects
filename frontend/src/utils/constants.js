/**
 * Shared constants — single source of truth for hardcoded values.
 * Priority and Status categories match the ERPNext DocType exactly.
 */

// Must match bp_issue.json Select options exactly
export const PRIORITIES = [
  { value: "Highest", label: "Highest", color: "#EF4444", textClass: "text-red-500"    },
  { value: "High",    label: "High",    color: "#F97316", textClass: "text-orange-500" },
  { value: "Medium",  label: "Medium",  color: "#F59E0B", textClass: "text-amber-500"  },
  { value: "Low",     label: "Low",     color: "#60A5FA", textClass: "text-blue-400"   },
  { value: "Lowest",  label: "Lowest",  color: "#94A3B8", textClass: "text-slate-400"  },
];

export const PRIORITY_MAP = Object.fromEntries(
  PRIORITIES.map((p) => [p.value, p]),
);

// Atlassian-aligned avatar palette — richer than defaults
export const AVATAR_COLORS = [
  "#1D4ED8", // blue-700
  "#047857", // emerald-700
  "#B91C1C", // red-700
  "#B45309", // amber-700
  "#0369A1", // sky-700
  "#6D28D9", // violet-700
  "#7C3AED", // purple-600 (Atlassian purple)
  "#0E7490", // cyan-700
  "#BE185D", // pink-700
  "#065F46", // emerald-800
];

export function avatarColor(key) {
  if (!key) return AVATAR_COLORS[0];
  let h = 0;
  for (let i = 0; i < key.length; i++) h = key.charCodeAt(i) + ((h << 5) - h);
  return AVATAR_COLORS[Math.abs(h) % AVATAR_COLORS.length];
}

export function initials(name) {
  if (!name) return "?";
  return name
    .split(" ")
    .map((w) => w[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);
}
