// Envelope geometry and sampling (spec §5.2), ported verbatim from the
// handoff's `_envelope` (v3 lines 1583-1596). `sampleEnvelope` is implemented
// IDENTICALLY in Python on the server -- do not "simplify" this file without
// re-recording docs/latent-forge/contract/vectors/envelope.json and checking
// both sides still agree.

import type { Envelope } from "../forge/types";

export const ENVELOPE_VIEW_W = 400;
export const ENVELOPE_VIEW_H = 100;
/** Node x positions across the 400-wide viewBox: 0, 1/3, 2/3, 1 of the width. */
export const ENVELOPE_XS = [0, 133.33, 266.67, 400] as const;

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v));
}

/**
 * Round away float64 ULP noise from chord-midpoint arithmetic (e.g.
 * `(266.67 + 400) / 2` prints as `333.33500000000004`, not `333.335`) without
 * touching real sub-micro precision -- the viewBox is 400 units wide, so
 * 1e-6 is far below anything visually or numerically meaningful here.
 */
function clean(v: number): number {
  return Math.round(v * 1e6) / 1e6;
}

/** v (0..1) -> SVG y in the 0..100 viewBox. Spec §5.2: y(v) = 90 - 80v. */
export function envelopeY(v: number): number {
  return 90 - v * 80;
}

export interface EnvelopeNode {
  x: number;
  y: number;
}

export interface EnvelopeSegment {
  x1: number;
  y1: number;
  cx: number;
  cy: number;
  x2: number;
  y2: number;
}

export interface EnvelopeGeometry {
  nodes: EnvelopeNode[];
  segments: EnvelopeSegment[];
  /** The single visible quadratic path, built exactly as `_envelope` builds `d`. */
  pathD: string;
}

/**
 * SVG node positions and the three segments' Bezier control points (spec
 * §5.2). The control point of segment i is the CHORD MIDPOINT of
 * (x_i,y_i)-(x_{i+1},y_{i+1}), offset vertically by `-curves[i]*60`.
 */
export function envelopeGeometry(env: Envelope): EnvelopeGeometry {
  const xs = ENVELOPE_XS;
  const ys = env.points.map(envelopeY);
  const nodes: EnvelopeNode[] = xs.map((x, i) => ({ x, y: ys[i] }));

  const segments: EnvelopeSegment[] = [];
  let d = `M ${xs[0]},${ys[0]} `;
  for (let i = 0; i < 3; i++) {
    const x1 = xs[i];
    const y1 = ys[i];
    const x2 = xs[i + 1];
    const y2 = ys[i + 1];
    const cx = clean((x1 + x2) / 2);
    const cy = clean((y1 + y2) / 2 - env.curves[i] * 60);
    segments.push({ x1, y1, cx, cy, x2, y2 });
    d += `Q ${cx},${cy} ${x2},${y2} `;
  }
  return { nodes, segments, pathD: d };
}

/**
 * Sample the envelope at n evenly-spaced frames (spec §5.2). For frame k,
 * x = k/(n-1) (0 if n=1); segment i = min(2, floor(3x)); local s = 3x - i.
 * Because the control point's x is the chord midpoint, x(s) is linear, so
 * y(s) = (1-s)^2*yi + 2s(1-s)*yc + s^2*yn, and v = clamp((90-y)/80, 0, 1).
 *
 * Implemented identically in Python on the server -- the shared vectors
 * under docs/latent-forge/contract/vectors/envelope.json are the contract.
 */
export function sampleEnvelope(env: Envelope, n: number): Float32Array {
  const out = new Float32Array(Math.max(0, n));
  for (let k = 0; k < n; k++) {
    const x = n === 1 ? 0 : k / (n - 1);
    const i = Math.min(2, Math.floor(3 * x));
    const s = 3 * x - i;
    const yi = envelopeY(env.points[i]);
    const yn = envelopeY(env.points[i + 1]);
    const yc = (yi + yn) / 2 - env.curves[i] * 60;
    const y = (1 - s) * (1 - s) * yi + 2 * s * (1 - s) * yc + s * s * yn;
    out[k] = clamp((90 - y) / 80, 0, 1);
  }
  return out;
}

/** Node drag (spec §5.2): v = clamp((90 - (clientY-top)/height*100)/80, 0, 1). */
export function nodeDragValue(clientY: number, top: number, height: number): number {
  const pct = ((clientY - top) / height) * 100;
  return clamp((90 - pct) / 80, 0, 1);
}

/** Segment drag (spec §5.2): c = clamp(c_start + (startY-clientY)/60, -1, 1). */
export function segmentDragValue(cStart: number, startY: number, clientY: number): number {
  return clamp(cStart + (startY - clientY) / 60, -1, 1);
}
