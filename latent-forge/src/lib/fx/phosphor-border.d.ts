// Hand-written types for the verbatim-copied phosphor-border.js (spec §9.5: "copied verbatim …
// plus a .d.ts"). The .js is never edited, so the types live beside it. Every field below is
// read from that file's own DEFAULTS object; `sweepStart`/`sweepEnd` are deliberately ABSENT --
// they are the app's ramp endpoints, not module config, and set() would silently swallow them.

/** Each value is a list of `#rrggbb` strings the beam cycles through. */
export declare const PALETTES: {
  teal: string[];
  amber: string[];
  accent: string[];
  sparse: string[];
  c64: string[];
};

export interface PhosphorOptions {
  /** Border ring thickness in backing pixels; clamped to `ceil(height / 2)`. Changing it rebuilds the ring. */
  thickness?: number;
  linesPerColour?: number;
  /** 0..1 randomisation of the write interval. */
  jitter?: number;
  /** Seconds; the red-phosphor time constant, scaled 1.0 / 1.6 / 0.6 for R / G / B. */
  persistence?: number;
  chromaBleed?: number;
  /** Integer sub-steps per animation frame. */
  supersample?: number;
  /** Full raster sweeps per second. THE field the progress driver writes. */
  sweepHz?: number;
  gain?: number;
  spotSpread?: number;
  /** true = transparent where the phosphor is dark. Required for an overlay canvas. */
  alphaOut?: boolean;
  /** An ARRAY of hex strings -- e.g. PALETTES.teal, never the string "teal". */
  palette?: string[];
}

export interface PhosphorBorder {
  start(): void;
  stop(): void;
  /** Merges into the live config. Only `thickness` triggers a ring rebuild. */
  set(patch: PhosphorOptions): void;
  /** Sets canvas.width/height and rebuilds. */
  resize(width: number, height: number): void;
  /** Calls `this.stop()` -- keep the handle whole; a destructured `destroy` throws. */
  destroy(): void;
}

export declare function createPhosphorBorder(
  canvas: HTMLCanvasElement,
  options?: PhosphorOptions,
): PhosphorBorder;
