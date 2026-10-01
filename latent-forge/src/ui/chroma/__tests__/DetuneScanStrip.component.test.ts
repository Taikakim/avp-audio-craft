// @vitest-environment jsdom
import { cleanup, fireEvent, render } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ChromaResult } from "../../../lib/chroma/chromaClient.svelte";
import type { ForgeClip } from "../../../lib/forge/types";
import { HELP } from "../../../lib/help/strings";
import { arrangement } from "../../../lib/stores/arrangement.svelte";
import DetuneScanStrip from "../DetuneScanStrip.svelte";

type Call = { kind: "call"; name: string; args: unknown[] } | { kind: "set"; name: string; value: unknown };

function fakeContext() {
  const calls: Call[] = [];
  const ctx: Record<string, unknown> = {};
  for (const m of ["fillRect", "beginPath", "moveTo", "lineTo", "stroke", "fill", "closePath", "clearRect", "setTransform", "setLineDash"]) {
    ctx[m] = (...args: unknown[]) => { calls.push({ kind: "call", name: m, args }); };
  }
  for (const p of ["fillStyle", "strokeStyle", "lineWidth", "globalAlpha"]) {
    let v: unknown;
    Object.defineProperty(ctx, p, {
      get: () => v,
      set: (nv: unknown) => { v = nv; calls.push({ kind: "set", name: p, value: nv }); },
    });
  }
  return { ctx: ctx as unknown as CanvasRenderingContext2D, calls };
}

/** A clip whose chroma is pure C; the target is pure C#, so the peak is at +100¢. */
function result(T: number): ChromaResult {
  const fold12 = new Float32Array(12 * T);
  for (let t = 0; t < T; t++) fold12[0 * T + t] = 1;
  return { frames: T, fps: 10.7666015625, bands: new Float32Array(3 * 128 * T), fold12, T };
}

const TARGET = Float32Array.from([0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]);

let clip: ForgeClip;

beforeEach(() => {
  for (const c of [...arrangement.clips]) arrangement.removeClip(c.id);
  clip = arrangement.addClip({ lane: 0, startSec: 0, durSec: 4, audio: { kind: "crop", crop_id: "000412" } });
  Object.defineProperty(HTMLCanvasElement.prototype, "clientWidth", { configurable: true, get: () => 500 });
  Object.defineProperty(HTMLCanvasElement.prototype, "clientHeight", { configurable: true, get: () => 30 });
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(fakeContext().ctx);
});

afterEach(() => {
  delete (HTMLCanvasElement.prototype as unknown as Record<string, unknown>).clientWidth;
  delete (HTMLCanvasElement.prototype as unknown as Record<string, unknown>).clientHeight;
  vi.restoreAllMocks();
  for (const c of [...arrangement.clips]) arrangement.removeClip(c.id);
  cleanup();
});

function rect(canvas: HTMLElement) {
  vi.spyOn(canvas, "getBoundingClientRect").mockReturnValue({
    left: 0, top: 0, width: 500, height: 30, right: 500, bottom: 30, x: 0, y: 0, toJSON: () => ({}),
  });
}

describe("DetuneScanStrip's DOM contract", () => {
  it("carries all three of M1 T14's own ids (v3 332, 335, 336)", () => {
    const { getByTestId } = render(DetuneScanStrip, {
      props: { clip, result: result(12), target: TARGET, criterion: "highest" },
    });
    expect(getByTestId("chroma-scan-strip").getAttribute("data-help")).toBe(HELP.chromaDetuneScan);
    expect(getByTestId("chroma-best-criterion").getAttribute("data-help")).toBe(HELP.chromaBestCriterion);
    expect(getByTestId("chroma-best").getAttribute("data-help")).toBe(HELP.chromaBest);
  });

  it("is the drawing's 500 x 30 canvas", () => {
    const { getByTestId } = render(DetuneScanStrip, {
      props: { clip, result: result(12), target: TARGET, criterion: "highest" },
    });
    const canvas = getByTestId("chroma-scan-strip") as HTMLCanvasElement;
    expect(canvas.getAttribute("width")).toBe("500");
    expect(canvas.getAttribute("height")).toBe("30");
  });

  it("says so honestly when there is no clip to scan", () => {
    const { getByTestId } = render(DetuneScanStrip, {
      props: { clip: null, result: null, target: TARGET, criterion: "highest" },
    });
    expect(getByTestId("chroma-scan-label").textContent).toBe("detune scan · no clip");
  });
});

describe("clicking and dragging the strip sets detune (spec §5.4)", () => {
  it("writes through arrangement.setDetune, never by mutating the clip, and ADDS to what is there", async () => {
    // The axis is RELATIVE to the clip's current detune, because the fold
    // being scanned is the fold of already-stretched audio. x = 0 is therefore
    // "-100 ¢ FROM 20 ¢", i.e. -80 -- not -100.
    arrangement.setDetune(clip.id, 20);
    const spy = vi.spyOn(arrangement, "setDetune");
    const { getByTestId } = render(DetuneScanStrip, {
      props: { clip: arrangement.clips[0], result: result(12), target: TARGET, criterion: "highest" },
    });
    const canvas = getByTestId("chroma-scan-strip");
    rect(canvas);
    await fireEvent.pointerDown(canvas, { button: 0, clientX: 0, clientY: 15, pointerId: 1 });
    expect(spy).toHaveBeenCalledWith(clip.id, -80);
    expect(arrangement.clips[0].detune_cents).toBe(-80);
  });

  it("keeps following the pointer while the button is held, and stops after it is released", async () => {
    const { getByTestId } = render(DetuneScanStrip, {
      props: { clip, result: result(12), target: TARGET, criterion: "highest" },
    });
    const canvas = getByTestId("chroma-scan-strip");
    rect(canvas);
    // x = 250 is the strip's centre, i.e. 0 ¢ relative: the press alone leaves
    // the clip's 0 ¢ where it is. The move to the right edge is +100 from
    // there.
    await fireEvent.pointerDown(canvas, { button: 0, clientX: 250, clientY: 15, pointerId: 1 });
    expect(arrangement.clips[0].detune_cents).toBe(0);
    await fireEvent.pointerMove(canvas, { clientX: 500, clientY: 15, pointerId: 1 });
    expect(arrangement.clips[0].detune_cents).toBe(100);
    await fireEvent.pointerUp(canvas, { clientX: 500, clientY: 15, pointerId: 1 });
    await fireEvent.pointerMove(canvas, { clientX: 0, clientY: 15, pointerId: 1 });
    expect(arrangement.clips[0].detune_cents).toBe(100);
  });

  it("ignores a middle or right button, which are not the strip's gesture", async () => {
    const { getByTestId } = render(DetuneScanStrip, {
      props: { clip, result: result(12), target: TARGET, criterion: "highest" },
    });
    const canvas = getByTestId("chroma-scan-strip");
    rect(canvas);
    await fireEvent.pointerDown(canvas, { button: 1, clientX: 0, clientY: 15, pointerId: 1 });
    expect(arrangement.clips[0].detune_cents).toBe(0);
  });
});

describe("BEST and the criterion toggle (spec §5.4, v3 1919-1929)", () => {
  it("ADDS the argmax under the current criterion to the clip's own detune", async () => {
    arrangement.setDetune(clip.id, -20);
    const { getByTestId } = render(DetuneScanStrip, {
      props: { clip: arrangement.clips[0], result: result(12), target: TARGET, criterion: "highest" },
    });
    await fireEvent.click(getByTestId("chroma-best"));
    // A pure-C clip against a pure-C# target does NOT peak cleanly at +100.
    // `rotate` splits linearly, so at c cents the frame is {0: 1-c/100,
    // 1: c/100}; once 1-c/100 falls below the float32 threshold, class 0 drops
    // out entirely and the score is W[0] = 1.0 exactly. That happens at 96 and
    // at 100 -- a flat top -- and `bestDetune`'s strict `>` keeps the FIRST,
    // so BEST returns 96. (Against the float64 literal threshold it would be a
    // three-way tie from 92; the Math.fround fix in Task 3 is what moves the
    // first tied point to 96. The two are coupled -- do not change one alone.)
    //
    // And 96 is a step on a RELATIVE axis, so BEST adds it: -20 + 96 = 76.
    // The bare-assignment version returned 96 here and, pressed again, 96
    // again rather than converging -- which is the bug this pins.
    expect(arrangement.clips[0].detune_cents).toBe(76);
  });

  it("does nothing at all when there is no clip or no chroma yet", async () => {
    const { getByTestId } = render(DetuneScanStrip, {
      props: { clip, result: null, target: TARGET, criterion: "highest" },
    });
    await fireEvent.click(getByTestId("chroma-best"));
    expect(arrangement.clips[0].detune_cents).toBe(0);
  });

  it("reports the flipped criterion upward rather than owning it", async () => {
    let seen: string | null = null;
    const { getByTestId } = render(DetuneScanStrip, {
      props: {
        clip, result: result(12), target: TARGET, criterion: "highest",
        oncriterion: (c: string) => { seen = c; },
      },
    });
    expect(getByTestId("chroma-best-criterion").textContent).toBe("HIGHEST");
    await fireEvent.click(getByTestId("chroma-best-criterion"));
    expect(seen).toBe("steadiest");
  });
});

describe("the red mark at the clip's current detune (spec §5.4)", () => {
  it("strokes a line in the --red token at the CENTRE, because the axis is relative to it", () => {
    arrangement.setDetune(clip.id, 50);
    const fake = fakeContext();
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(fake.ctx);
    const { getByTestId } = render(DetuneScanStrip, {
      props: { clip: arrangement.clips[0], result: result(12), target: TARGET, criterion: "highest" },
    });
    expect(getByTestId("chroma-scan-strip")).toBeTruthy();
    // Find the mark by its colour and read the moveTo that follows it -- the
    // 0 ¢ GRID line is drawn at the same x, so a bare "some moveTo is at 250.5"
    // would pass even with no mark at all.
    const redAt = fake.calls.findIndex(
      (c) => c.kind === "set" && c.name === "strokeStyle" && c.value === "oklch(55% 0.20 25)",
    ); // chromaCanvas's --red fallback, copied from M1 T12's tokens.css
    expect(redAt).toBeGreaterThanOrEqual(0);
    const mark = fake.calls
      .slice(redAt)
      .find((c) => c.kind === "call" && c.name === "moveTo") as { args: number[] } | undefined;
    expect(mark).toBeTruthy();
    // 250.5, the strip's centre -- NOT xForCents(50) = 375.5. The clip's
    // detune is the axis ORIGIN, so the mark does not move when it changes.
    expect(mark!.args[0]).toBeCloseTo(250.5, 6);
  });
});
