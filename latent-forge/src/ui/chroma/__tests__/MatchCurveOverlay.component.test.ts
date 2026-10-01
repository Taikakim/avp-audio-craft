// @vitest-environment jsdom
import { cleanup, render } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ChromaResult } from "../../../lib/chroma/chromaClient.svelte";
import { HELP } from "../../../lib/help/strings";
import MatchCurveOverlay from "../MatchCurveOverlay.svelte";

type Call = { kind: "call"; name: string; args: unknown[] } | { kind: "set"; name: string; value: unknown };

function fakeContext() {
  const calls: Call[] = [];
  const ctx: Record<string, unknown> = {};
  for (const m of ["fillRect", "strokeRect", "beginPath", "moveTo", "lineTo", "stroke", "fill", "fillText", "clearRect", "setTransform", "closePath", "setLineDash"]) {
    ctx[m] = (...args: unknown[]) => { calls.push({ kind: "call", name: m, args }); };
  }
  for (const p of ["fillStyle", "strokeStyle", "lineWidth", "globalAlpha", "font", "textBaseline"]) {
    let v: unknown;
    Object.defineProperty(ctx, p, {
      get: () => v,
      set: (nv: unknown) => { v = nv; calls.push({ kind: "set", name: p, value: nv }); },
    });
  }
  return { ctx: ctx as unknown as CanvasRenderingContext2D, calls };
}

function result(T: number): ChromaResult {
  const fold12 = new Float32Array(12 * T);
  for (let t = 0; t < T; t++) fold12[0 * T + t] = 1;
  return { frames: T, fps: 10.7666015625, bands: new Float32Array(3 * 128 * T), fold12, T };
}

const TARGET = Float32Array.from([1, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0]);

beforeEach(() => {
  Object.defineProperty(HTMLCanvasElement.prototype, "clientWidth", { configurable: true, get: () => 400 });
  Object.defineProperty(HTMLCanvasElement.prototype, "clientHeight", { configurable: true, get: () => 129 });
});

afterEach(() => {
  delete (HTMLCanvasElement.prototype as unknown as Record<string, unknown>).clientWidth;
  delete (HTMLCanvasElement.prototype as unknown as Record<string, unknown>).clientHeight;
  vi.restoreAllMocks();
  cleanup();
});

describe("MatchCurveOverlay", () => {
  it("carries HELP.chromaMatchCurve (v3 line 346)", () => {
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(fakeContext().ctx);
    const { getByTestId } = render(MatchCurveOverlay, {
      props: { result: result(8), target: TARGET, win: { from: 0, to: 8 } },
    });
    expect(getByTestId("chroma-match-curve").getAttribute("data-help")).toBe(HELP.chromaMatchCurve);
  });

  it("plots one point per visible frame", () => {
    const fake = fakeContext();
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(fake.ctx);
    render(MatchCurveOverlay, {
      props: { result: result(96), target: TARGET, win: { from: 10, to: 20 } },
    });
    const moves = fake.calls.filter((c) => c.kind === "call" && c.name === "moveTo").length;
    const lines = fake.calls.filter((c) => c.kind === "call" && c.name === "lineTo").length;
    // three dashed anchor lines (1 moveTo + 1 lineTo each) + the curve itself,
    // which is 1 moveTo + 9 lineTo for a 10-frame window.
    expect(moves).toBe(3 + 1);
    expect(lines).toBe(3 + 9);
  });

  it("draws the three anchor reference lines even before any frame is scored", () => {
    const fake = fakeContext();
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(fake.ctx);
    render(MatchCurveOverlay, {
      props: { result: null, target: TARGET, win: { from: 0, to: 8 } },
    });
    expect(fake.calls.filter((c) => c.kind === "call" && c.name === "setLineDash").length).toBeGreaterThan(0);
    expect(fake.calls.filter((c) => c.kind === "call" && c.name === "moveTo").length).toBe(3);
  });

  it("clears rather than fills its background, so the heatmap shows through", () => {
    const fake = fakeContext();
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(fake.ctx);
    render(MatchCurveOverlay, {
      props: { result: result(8), target: TARGET, win: { from: 0, to: 8 } },
    });
    expect(fake.calls.some((c) => c.kind === "call" && c.name === "fillRect")).toBe(false);
  });
});
