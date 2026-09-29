// Where a dragged edge lands. Pure: the caller supplies the meter, the zoom and
// the things worth snapping to, so this never reaches into a store.

export type SnapMode = "bar" | "beat" | "1/8" | "1/16" | "1/32" | "lane" | "edge" | "free";

/** Spec 4.3, in the order the select shows them. `lane` is the default. */
export const SNAP_MODES: { value: SnapMode; label: string }[] = [
  { value: "bar", label: "bar" },
  { value: "beat", label: "beat" },
  { value: "1/8", label: "1/8" },
  { value: "1/16", label: "1/16" },
  { value: "1/32", label: "1/32" },
  { value: "lane", label: "downbeats (magnetic)" },
  { value: "edge", label: "clip edges" },
  { value: "free", label: "free" },
];

/** Spec 4.3: "a dragged clip's downbeats jump to another clip's within 5px". */
export const MAGNET_PX = 5;

export interface SnapContext {
  bpm: number;
  beatsPerBar: number;
  /** Current zoom. The 5 px magnet is a SCREEN distance, so it widens as you zoom out. */
  pxPerSec: number;
  /** Other clips' starts and ends, for `edge`. */
  edges: number[];
  /** Other lanes' downbeats, for `lane`. */
  magnets: number[];
}

export interface SnapResult {
  sec: number;
  snapped: boolean;
  /** The magnet it locked onto, for the UI's indicator; null when it did not snap. */
  to: number | null;
}

export function gridIntervalSec(mode: SnapMode, bpm: number, beatsPerBar: number): number | null {
  const beat = 60 / bpm;
  switch (mode) {
    case "bar": return beat * beatsPerBar;
    case "beat": return beat;
    case "1/8": return beat / 2;
    case "1/16": return beat / 4;
    case "1/32": return beat / 8;
    default: return null;            // lane, edge and free are not grids
  }
}

function nearest(sec: number, targets: number[], toleranceSec: number): number | null {
  let best: number | null = null;
  let bestDist = toleranceSec;
  for (const t of targets) {
    const d = Math.abs(t - sec);
    if (d <= bestDist) {
      best = t;
      bestDist = d;
    }
  }
  return best;
}

export function snapDelta(sec: number, mode: SnapMode, ctx: SnapContext): SnapResult {
  const clamped = Math.max(0, sec);
  if (mode === "free") return { sec: clamped, snapped: false, to: null };

  const interval = gridIntervalSec(mode, ctx.bpm, ctx.beatsPerBar);
  if (interval !== null) {
    return { sec: Math.max(0, Math.round(clamped / interval) * interval), snapped: true, to: null };
  }

  // Magnetic modes: a screen-distance tolerance, and dragging further pulls free.
  const toleranceSec = MAGNET_PX / Math.max(1e-6, ctx.pxPerSec);
  const targets = mode === "edge" ? ctx.edges : ctx.magnets;
  const hit = nearest(clamped, targets, toleranceSec);
  return hit === null
    ? { sec: clamped, snapped: false, to: null }
    : { sec: Math.max(0, hit), snapped: true, to: hit };
}

export function snapSec(sec: number, mode: SnapMode, ctx: SnapContext): number {
  return snapDelta(sec, mode, ctx).sec;
}
