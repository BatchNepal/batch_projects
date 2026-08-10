/** @type {import('tailwindcss').Config} */

export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  darkMode: ["class", '[data-theme="dark"]'],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "-apple-system", "BlinkMacSystemFont", "sans-serif"],
        mono: ["JetBrains Mono", "Fira Code", "ui-monospace", "monospace"],
      },
      borderWidth: { DEFAULT: 'var(--border-width)' },
      /* Mirrors tokens.css --text-* exactly (see the law note there):
         11 · 12.5 · 13 · 14 · 16+. `sm` moved 12 -> 12.5 so Tailwind's
         text-sm and the design law's "secondary" step are the same thing
         instead of two sizes half a pixel apart. */
      fontSize: {
        xs:    ["0.6875rem",  { lineHeight: "1.2" }],
        sm:    ["0.78125rem", { lineHeight: "1.35" }],
        base:  ["0.8125rem", { lineHeight: "1.5" }],
        md:    ["0.875rem",  { lineHeight: "1.5" }],
        lg:    ["0.9375rem", { lineHeight: "1.5" }],
        xl:    ["1rem",      { lineHeight: "1.4" }],
        "2xl": ["1.125rem",  { lineHeight: "1.35" }],
        "3xl": ["1.25rem",   { lineHeight: "1.25" }],
        /* Closed data tiers — see tokens.css. */
        micro:  ["0.5625rem", { lineHeight: "1" }],
        metric: ["1.75rem",   { lineHeight: "1" }],
      },

      /* All colors reference CSS vars — OKLCH values live in tokens.css */
      colors: {
        accent: {
          DEFAULT:           "var(--accent)",
          foreground:        "var(--accent-foreground)",
          hover:             "var(--accent-hover)",
          soft:              "var(--accent-soft)",
          "soft-foreground": "var(--accent-soft-foreground)",
          "soft-hover":      "var(--accent-soft-hover)",
        },
        success: {
          DEFAULT:           "var(--success)",
          foreground:        "var(--success-foreground)",
          hover:             "var(--success-hover)",
          soft:              "var(--success-soft)",
          "soft-foreground": "var(--success-soft-foreground)",
          "soft-hover":      "var(--success-soft-hover)",
        },
        warning: {
          DEFAULT:           "var(--warning)",
          foreground:        "var(--warning-foreground)",
          hover:             "var(--warning-hover)",
          soft:              "var(--warning-soft)",
          "soft-foreground": "var(--warning-soft-foreground)",
          "soft-hover":      "var(--warning-soft-hover)",
        },
        danger: {
          DEFAULT:           "var(--danger)",
          foreground:        "var(--danger-foreground)",
          hover:             "var(--danger-hover)",
          soft:              "var(--danger-soft)",
          "soft-foreground": "var(--danger-soft-foreground)",
          "soft-hover":      "var(--danger-soft-hover)",
        },
        info: {
          DEFAULT:           "var(--info)",
          foreground:        "var(--info-foreground)",
          hover:             "var(--info-hover)",
          soft:              "var(--info-soft)",
          "soft-foreground": "var(--info-soft-foreground)",
          "soft-hover":      "var(--info-soft-hover)",
        },
        default: {
          DEFAULT:  "var(--default)",
          foreground:"var(--default-foreground)",
          hover:    "var(--default-hover)",
        },
        surface: {
          DEFAULT:   "var(--surface)",
          secondary: "var(--surface-secondary)",
          tertiary:  "var(--surface-tertiary)",
          hover:     "var(--surface-hover)",
        },
        overlay: {
          DEFAULT: "var(--overlay)",
        },
        background: {
          DEFAULT:   "var(--background)",
          secondary: "var(--background-secondary)",
          tertiary:  "var(--background-tertiary)",
        },
        foreground: {
          DEFAULT: "var(--foreground)",
        },
        muted: {
          DEFAULT: "var(--muted)",
        },
        border: {
          DEFAULT:   "var(--border)",
          secondary: "var(--border-secondary)",
          tertiary:  "var(--border-tertiary)",
        },
        separator: {
          DEFAULT: "var(--separator)",
        },
        /* Alias — legacy compat */
        primary: {
          DEFAULT:    "var(--accent)",
          foreground: "var(--accent-foreground)",
          hover:      "var(--accent-hover)",
          50:         "var(--accent-soft)",
          100:        "var(--accent-soft)",
        },
      },

      /* Bare `border`/`border-b`/`divide-*` resolve to tokens — never gray-200 */
      borderColor: {
        DEFAULT: "var(--border)",
      },
      divideColor: {
        DEFAULT: "var(--separator)",
      },

      borderRadius: {
        xs:    "2px",
        sm:    "4px",
        md:    "6px",
        lg:    "8px",
        xl:    "10px",
        "2xl": "14px",
        "3xl": "20px",
        full:  "9999px",
      },

      spacing: {
        0.5:  "2px",
        1:    "4px",
        1.5:  "6px",
        2:    "8px",
        2.5:  "10px",
        3:    "12px",
        3.5:  "14px",
        4:    "16px",
        5:    "20px",
        6:    "24px",
        7:    "28px",
        8:    "32px",
        9:    "36px",
        10:   "40px",
        11:   "44px",
        12:   "48px",
        14:   "56px",
        16:   "64px",
      },

      /* Every entry resolves through tokens.css so Tailwind's `shadow-*` and
         raw `var(--shadow-*)` can never drift apart again — they were hard-
         coded here as flat black with no dark-theme equivalent, while the
         token layer had a tuned, theme-aware ladder. See the SHADOW SCALE
         comment in tokens.css. */
      boxShadow: {
        none:          "none",
        xs:            "var(--shadow-xs)",
        sm:            "var(--shadow-sm)",
        md:            "var(--shadow-md)",
        lg:            "var(--shadow-lg)",
        xl:            "var(--shadow-xl)",
        surface:       "var(--surface-shadow)",
        "surface-sm":  "var(--surface-shadow-sm)",
        "surface-hover":"var(--surface-shadow-hover)",
        overlay:       "var(--overlay-shadow)",
        field:         "var(--field-shadow)",
        focus:         "var(--shadow-focus)",
        "focus-danger":"var(--shadow-focus-danger)",
        popover:       "var(--shadow-popover)",
      },

      keyframes: {
        "accordion-down": {
          from: { height: "0", opacity: "0" },
          to:   { height: "var(--accordion-content-height)", opacity: "1" },
        },
        "accordion-up": {
          from: { height: "var(--accordion-content-height)", opacity: "1" },
          to:   { height: "0", opacity: "0" },
        },
        skeleton:      { "100%": { transform: "translateX(200%)" } },
        "caret-blink": {
          "0%, 70%, 100%": { opacity: "1" },
          "20%, 50%":      { opacity: "0" },
        },
        "scale-in": {
          from: { opacity: "0", transform: "scale(0.96)" },
          to:   { opacity: "1", transform: "scale(1)" },
        },
        "scale-out": {
          from: { opacity: "1", transform: "scale(1)" },
          to:   { opacity: "0", transform: "scale(0.96)" },
        },
        "slide-in-right": {
          from: { transform: "translateX(100%)" },
          to:   { transform: "translateX(0)" },
        },
        "slide-out-right": {
          from: { transform: "translateX(0)" },
          to:   { transform: "translateX(100%)" },
        },
        "slide-up": {
          from: { opacity: "0", transform: "translateY(6px)" },
          to:   { opacity: "1", transform: "translateY(0)" },
        },
        "toast-in": {
          from: { opacity: "0", transform: "translateX(20px) scale(0.96)" },
          to:   { opacity: "1", transform: "translateX(0) scale(1)" },
        },
        "toast-out": {
          from: { opacity: "1", transform: "translateX(0) scale(1)" },
          to:   { opacity: "0", transform: "translateX(24px) scale(0.95)" },
        },
      },

      animation: {
        "accordion-down":  "accordion-down 0.16s ease-out",
        "accordion-up":    "accordion-up 0.14s ease-in",
        "skeleton":        "skeleton 2s linear infinite",
        "caret-blink":     "caret-blink 1.2s ease-out infinite",
        "scale-in":        "scale-in 0.14s cubic-bezier(0.32, 0.72, 0, 1)",
        "scale-out":       "scale-out 0.11s ease-in",
        "slide-in-right":  "slide-in-right 0.20s cubic-bezier(0.32, 0.72, 0, 1)",
        "slide-out-right": "slide-out-right 0.16s ease-in",
        "slide-up":        "slide-up 0.14s ease-out",
        "toast-in":        "toast-in 0.22s cubic-bezier(0.34, 1.56, 0.64, 1)",
        "toast-out":       "toast-out 0.16s cubic-bezier(0.4, 0, 1, 1) forwards",
      },

      /* Mirrors the motion scale in tokens.css — same values, so `duration-fast`
         and `var(--duration-fast)` are interchangeable. Retune in ONE place
         (tokens.css) and update here to match. */
      transitionDuration: {
        instant: "var(--duration-instant)",
        fast:    "var(--duration-fast)",
        base:    "var(--duration-base)",
        slow:    "var(--duration-slow)",
        slower:  "var(--duration-slower)",
        modal:   "var(--duration-modal)",
        enter:   "var(--duration-enter)",
        exit:    "var(--duration-exit)",
      },

      /* out/in/in-out deliberately OVERRIDE Tailwind's defaults so the utility
         `ease-out` and the token `var(--ease-out)` are the same curve — the kit
         mixed raw `ease-out` (Tailwind's cubic-bezier(0,0,.2,1) is close but
         `ease-in-out`/`linear` were not) with token easings on sibling
         elements. Enter decelerates, exit accelerates. */
      transitionTimingFunction: {
        out:         "var(--ease-out)",
        in:          "var(--ease-in)",
        "in-out":    "var(--ease-in-out)",
        smooth:      "var(--ease-smooth)",
        "out-fluid": "var(--ease-out-fluid)",
        "out-quart": "var(--ease-out-quart)",
        "out-expo":  "var(--ease-out-expo)",
        spring:      "var(--ease-spring)",
      },

      /* Layering law: content < sticky < overlay/drawer < modal < dropdown/
         popover < toast < tooltip. Dropdowns OUTRANK modals/overlays because
         they spawn from controls inside them (was 100 — rendered behind the
         z-[300] CreateProjectFlow page, hiding Select options). */
      zIndex: {
        sticky:   "200",
        overlay:  "300",
        modal:    "400",
        /* dropdowns/popovers spawn from controls inside ANY surface —
           including legacy hand-rolled modals at z-1000 (e.g. Backlog's
           sprint dialog, which swallowed DatePicker popups at 510) */
        dropdown: "1100",
        popover:  "1110",
        toast:    "1200",
        tooltip:  "1300",
      },
    },
  },

  plugins: [require("tailwindcss-animate")],
};
