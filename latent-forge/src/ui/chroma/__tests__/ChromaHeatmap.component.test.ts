// @vitest-environment jsdom
import { cleanup, fireEvent, render } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ChromaResult } from "../../../lib/chroma/chromaClient.svelte";
import { consonanceColor } from "../../../lib/chroma/consonanceColor";
import { matchFrame } from "../../../lib/chroma/match";
import { HELP } from "../../../lib/help/strings";
import ChromaHeatmap from "../ChromaHeatmap.svelte";

type Call = { kind: "call"; name: string; args: unknown[] } | { kind: "set"; name: string; value: unknown };

function fakeContext() {
  const calls: Call[] = [];
  const ctx: Record<string, unknown> = {};
  for (const m of ["fillRect", "strokeRect", "beginPath", "moveTo", "lineTo", "stroke", "fillText", "clearRect", "setTransform"]) {
    ctx[m] = (...args: unknown[]) => { calls.push({ kind: "call", name: m, args }); };
  }
  for (const p of ["fillStyle", "strokeStyle", "lineWidth", "globalAlpha", "font", "textAlign", "textBaseline"]) {
    let v: unknown;
    Object.defineProperty(ctx, p, {
      get: () => v,
      set: (nv: unknown) => { v = nv; calls.push({ kind: "set", name: p, value: nv }); },
    });
  }
  return { ctx: ctx as unknown as CanvasRenderingContext2D, calls };
}

/** One clip whose only energy is C: bin 2 of band 0, and class 0 of the fold. */
function res(T: number): ChromaResult {
  const bands = new Float32Array(3 * 128 * T);
  const fold12 = new Float32Array(12 * T);
  for (let t = 0; t < T; t++) {
    bands[(0 * 128 + 2) * T + t] = 1;
    fold12[0 * T + t] = 1;
  }
  return { frames: T, fps: 10.7666015625, bands, fold12, T };
}

const TARGET = Float32Array.from([1, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0]);

beforeEach(() => {
  // jsdom lays nothing out, so fitChromaCanvas would bail on w <= 0.
  Object.defineProperty(HTMLCanvasElement.prototype, "clientWidth", { configurable: true, get: () => 400 });
  Object.defineProperty(HTMLCanvasElement.prototype, "clientHeight", { configurable: true, get: () => 131 });
});

afterEach(() => {
  delete (HTMLCanvasElement.prototype as unknown as Record<string, unknown>).clientWidth;
  delete (HTMLCanvasElement.prototype as unknown as Record<string, unknown>).clientHeight;
  vi.restoreAllMocks();
  cleanup();
});

describe("ChromaHeatmap's DOM contract", () => {
  it("carries M1 T14's own id, HELP.chromaHeatmap (v3 line 344)", () => {
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(fakeContext().ctx);
    const { getByTestId } = render(ChromaHeatmap, {
      props: { view: "global", win: { from: 0, to: 4 }, result: res(4), target: TARGET },
    });
    expect(getByTestId("chroma-heatmap").getAttribute("data-help")).toBe(HELP.chromaHeatmap);
  });

  it("says so in the DOM when there is nothing to draw, never with fillText", () => {
    const fake = fakeContext();
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(fake.ctx);
    const { getByText } = render(ChromaHeatmap, {
      props: { view: "global", win: { from: 0, to: 1 }, result: null, target: TARGET },
    });
    // Findable by text == a real DOM node. A fillText label never can be (M4).
    expect(getByText("no chroma yet")).toBeTruthy();
    expect(fake.calls.some((c) => c.kind === "call" && c.name === "fillText")).toBe(false);
  });
});

describe("ChromaHeatmap draws the view it is given (spec §5.4)", () => {
  it("fills the background, the 12 reference cells, and one cell per lit row", () => {
    const fake = fakeContext();
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(fake.ctx);
    render(ChromaHeatmap, {
      props: { view: "global", win: { from: 0, to: 4 }, result: res(4), target: TARGET },
    });
    const fills = fake.calls.filter((c) => c.kind === "call" && c.name === "fillRect").length;
    // 1 background + 12 reference cells + 4 frames x 1 class above CELL_FLOOR
    expect(fills).toBe(1 + 12 + 4);
  });

  it("reads a band view out of that band's own 128 rows", () => {
    const fake = fakeContext();
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(fake.ctx);
    render(ChromaHeatmap, {
      props: { view: "bass", win: { from: 0, to: 4 }, result: res(4), target: TARGET },
    });
    const fills = fake.calls.filter((c) => c.kind === "call" && c.name === "fillRect").length;
    // only bin 2 of band 0 is above CELL_FLOOR in this fixture
    expect(fills).toBe(1 + 12 + 4);
  });

  it("colours a cell from the ramp, and never assigns the empty string", () => {
    const fake = fakeContext();
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(fake.ctx);
    render(ChromaHeatmap, {
      props: { view: "global", win: { from: 0, to: 4 }, result: res(4), target: TARGET },
    });
    const styles = fake.calls
      .filter((c) => c.kind === "set" && c.name === "fillStyle")
      .map((c) => (c as { value: unknown }).value);
    // NOT consonanceColor(1, 1). TARGET is [1,0,0,0,1,0,0,1,0,0,0,0] (classes
    // 0, 4, 7) and each frame's fold12 column is [1,0,...], so with matchFrame's
    // DIRECTED distance (frame class 0 against target classes 0, 4 and 7: the
    // distances are ((0-0)%12+12)%12=0, ((0-4)%12+12)%12=8 and
    // ((0-7)%12+12)%12=5) the frame's match is num/den =
    // (W[0] + W[8] + W[5]) / 3 = (1.0 + 0.66 + 0.82) / 3 = 0.8266..., not 1.
    // Compute the expectation rather than assuming a saturated frame.
    const frameMatch = matchFrame(Float32Array.from([1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]), TARGET);
    expect(styles).toContain(consonanceColor(1, frameMatch));
    expect(styles).not.toContain("");
  });
});

describe("ChromaHeatmap's middle-drag gesture (v3 331: up/down zooms, left/right scrolls)", () => {
  it("reports a narrower window when the middle button is dragged upward", async () => {
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(fakeContext().ctx);
    let seen: { from: number; to: number } | null = null;
    const { getByTestId } = render(ChromaHeatmap, {
      props: {
        view: "global", win: { from: 0, to: 96 }, result: res(96), target: TARGET,
        onwin: (w: { from: number; to: number }) => { seen = w; },
      },
    });
    const canvas = getByTestId("chroma-heatmap");
    vi.spyOn(canvas, "getBoundingClientRect").mockReturnValue({
      left: 0, top: 0, width: 400, height: 131, right: 400, bottom: 131, x: 0, y: 0, toJSON: () => ({}),
    });
    await fireEvent.pointerDown(canvas, { button: 1, clientX: 200, clientY: 60, pointerId: 1 });
    await fireEvent.pointerMove(canvas, { clientX: 200, clientY: 10, pointerId: 1 });
    expect(seen).not.toBe(null);
    expect(seen!.to - seen!.from).toBeLessThan(96);
  });

  it("recomputes from the drag's start each move, so reversing the pointer returns exactly to the start window", async () => {
    // A regression test for compounding: if each move zoomed the CURRENT
    // window instead of re-deriving from drag.startWin, ending back at the
    // pointer's start position would not generally restore the start window
    // once a step in between has been clamped -- and even short of a clamp,
    // compounding two inverse multiplicative factors is not exactly identity
    // in floating point the way "recompute from a fixed start" is.
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(fakeContext().ctx);
    let seen: { from: number; to: number } | null = null;
    const START = { from: 0, to: 96 };
    const { getByTestId } = render(ChromaHeatmap, {
      props: {
        view: "global", win: START, result: res(96), target: TARGET,
        onwin: (w: { from: number; to: number }) => { seen = w; },
      },
    });
    const canvas = getByTestId("chroma-heatmap");
    vi.spyOn(canvas, "getBoundingClientRect").mockReturnValue({
      left: 0, top: 0, width: 400, height: 131, right: 400, bottom: 131, x: 0, y: 0, toJSON: () => ({}),
    });
    await fireEvent.pointerDown(canvas, { button: 1, clientX: 200, clientY: 60, pointerId: 1 });
    await fireEvent.pointerMove(canvas, { clientX: 260, clientY: 10, pointerId: 1 }); // zoom in + scroll
    await fireEvent.pointerMove(canvas, { clientX: 200, clientY: 60, pointerId: 1 }); // back to the start point
    expect(seen).toEqual(START);
  });

  it("ignores a plain left-drag, which belongs to hover (Task 10)", async () => {
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(fakeContext().ctx);
    let seen: { from: number; to: number } | null = null;
    const { getByTestId } = render(ChromaHeatmap, {
      props: {
        view: "global", win: { from: 0, to: 96 }, result: res(96), target: TARGET,
        onwin: (w: { from: number; to: number }) => { seen = w; },
      },
    });
    const canvas = getByTestId("chroma-heatmap");
    await fireEvent.pointerDown(canvas, { button: 0, clientX: 200, clientY: 60, pointerId: 1 });
    await fireEvent.pointerMove(canvas, { clientX: 200, clientY: 10, pointerId: 1 });
    expect(seen).toBe(null);
  });
});
