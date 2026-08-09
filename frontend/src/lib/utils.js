import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs) {
  return twMerge(clsx(inputs));
}

// Anti-flicker for skeleton-gated loads: a fetch that resolves in 40ms
// (warm cache, same-network dev) still shows its skeleton for a single
// frame before yanking it away — a flash, not a smooth load. Holds the
// resolved value back until `ms` has elapsed since the call started, but
// never delays a GENUINELY slow load by even one extra ms beyond that floor.
export async function withMinDuration(promise, ms = 300) {
  const started = Date.now()
  const result = await promise
  const remaining = ms - (Date.now() - started)
  if (remaining > 0) await new Promise((r) => setTimeout(r, remaining))
  return result
}

export function valueUpdater(updaterOrValue, ref) {
  ref.value =
    typeof updaterOrValue === "function"
      ? updaterOrValue(ref.value)
      : updaterOrValue;
}
