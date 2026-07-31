// Shared ApexCharts theme for batch_projects Reports.
// App-like rendering, no fuzzy drop-shadows, sharp gridlines

export const PALETTE = [
  "var(--accent)",
  "var(--success)",
  "var(--warning)",
  "var(--danger)",
  "#06b6d4", // cyan-500 — supplementary categorical color, no token equivalent
  "#8b5cf6", // purple-500
  "#14b8a6", // teal-500
  "#f97316", // orange-500
  "#0ea5e9", // sky-500
];

const FONT = 'var(--font-sans, Inter)';
const AXIS = "var(--muted)";
const GRID = "var(--border)";

// Deep-merge helper so wrappers can override any base option.
function merge(base, over) {
  const out = Array.isArray(base) ? [...base] : { ...base };
  for (const k in over) {
    const v = over[k];
    out[k] =
      v && typeof v === "object" && !Array.isArray(v) && typeof out[k] === "object"
        ? merge(out[k] || {}, v)
        : v;
  }
  return out;
}

// Base options every wrapper starts from.
export function baseOptions(over = {}) {
  const base = {
    chart: {
      fontFamily: FONT,
      toolbar: { show: false },
      zoom: { enabled: false },
      animations: { enabled: true, easing: "easeinout", speed: 300 },
      dropShadow: { enabled: false },
      redrawOnParentResize: true,
      redrawOnWindowResize: true,
      parentHeightOffset: 0,
      offsetX: 0,
      offsetY: 0,
    },
    colors: PALETTE,
    // Flat fills — explicitly solid so no gradient ever creeps in.
    fill: { type: "solid", opacity: 1 },
    dataLabels: { enabled: false },
    grid: {
      borderColor: GRID,
      strokeDashArray: 0,
      xaxis: { lines: { show: false } },
      yaxis: { lines: { show: true } },
      padding: { top: 0, right: 4, bottom: 0, left: 4 },
    },
    stroke: { lineCap: "round", width: 2 },
    xaxis: {
      axisBorder: { show: false },
      axisTicks: { show: false },
      labels: {
        style: { colors: AXIS, fontSize: "11px", fontWeight: 500, fontFamily: FONT },
        rotate: -28,
        rotateAlways: false,
        hideOverlappingLabels: true,
        trim: true,
        maxHeight: 64,
      },
      tickPlacement: "on",
      crosshairs: { show: false },
    },
    yaxis: {
      labels: {
        style: { colors: AXIS, fontSize: "11px", fontWeight: 500, fontFamily: FONT },
        formatter: (v) => fmtNum(v),
      },
      axisBorder: { show: false },
      axisTicks: { show: false },
    },
    legend: {
      fontSize: "12px",
      fontWeight: 500,
      fontFamily: FONT,
      labels: { colors: "var(--foreground)" },
      markers: { width: 8, height: 8, radius: 2 },
      itemMargin: { horizontal: 8, vertical: 2 },
    },
    tooltip: {
      theme: "light",
      style: { fontSize: "12px", fontFamily: FONT },
      marker: { show: false },
    },
    states: {
      hover: { filter: { type: "lighten", value: 0.06 } },
      active: { filter: { type: "none" } },
    },
  };
  return merge(base, over);
}

// Compact number formatter shared with widget labels.
export function fmtNum(n) {
  n = +n || 0;
  if (Math.abs(n) >= 1e6) return (n / 1e6).toFixed(1) + "M";
  if (Math.abs(n) >= 1e3) return (n / 1e3).toFixed(1) + "k";
  return Number.isInteger(n) ? String(n) : n.toFixed(1);
}

// Pull per-item colors when provided, else fall back to the palette.
export function itemColors(items = []) {
  return items.map((it, i) => it.color || PALETTE[i % PALETTE.length]);
}
