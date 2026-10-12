// @vitest-environment jsdom
import { cleanup, fireEvent, render } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { statsClient } from "../../../lib/stats/statsClient.svelte";
import { xcorrColor } from "../../../lib/stats/xcorrColor";
import XcorrPanel from "../XcorrPanel.svelte";

type Call = { kind: "call"; name: string; args: unknown[] } | { kind: "set"; name: string; value: unknown };

function fakeContext() {
  const calls: Call[] = [];
  const ctx: Record<string, unknown> = {};
  const methods = ["fillRect", "strokeRect", "beginPath", "moveTo", "lineTo", "stroke", "fillText", "clearRect", "setTransform"];
  for (const m of methods) {
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

function noopCtx(): CanvasRenderingContext2D {
  const noop = () => {};
  return {
    fillRect: noop, strokeRect: noop, beginPath: noop, moveTo: noop, lineTo: noop,
    stroke: noop, fillText: noop, clearRect: noop, setTransform: noop,
    fillStyle: "", strokeStyle: "", lineWidth: 1, globalAlpha: 1, font: "", textAlign: "left", textBaseline: "top",
  } as unknown as CanvasRenderingContext2D;
}

beforeEach(() => {
  // Every draw effect bails out via fitPanelCanvas's w<=0/h<=0 guard (M1 T13)
  // unless the canvas reports a real size -- jsdom never lays anything out,
  // so this is stubbed on the prototype, before mount, for every test.
  Object.defineProperty(HTMLCanvasElement.prototype, "clientWidth", { configurable: true, get: () => 300 });
  Object.defineProperty(HTMLCanvasElement.prototype, "clientHeight", { configurable: true, get: () => 300 });
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(noopCtx());
});

afterEach(() => {
  delete (HTMLCanvasElement.prototype as unknown as Record<string, unknown>).clientWidth;
  delete (HTMLCanvasElement.prototype as unknown as Record<string, unknown>).clientHeight;
  vi.restoreAllMocks();
  statsClient.dispose();
  cleanup();
});

describe("XcorrPanel before any analysis", () => {
  it("shows M1's empty-state text", () => {
    const { getByText } = render(XcorrPanel);
    expect(getByText("no analysis yet — choose lanes and press ANALYSE")).toBeTruthy();
  });
});

describe("XcorrPanel while a request is pending", () => {
  it("shows an analysing message instead of the empty-state text", () => {
    statsClient.pending = true;
    const { getByText, queryByText } = render(XcorrPanel);
    expect(getByText("analysing…")).toBeTruthy();
    expect(queryByText("no analysis yet — choose lanes and press ANALYSE")).toBeNull();
  });
});

describe("XcorrPanel on a server error (spec §9.7)", () => {
  it("shows a one-line error message", () => {
    statsClient.error = "no crops selected";
    const { getByTestId } = render(XcorrPanel);
    expect(getByTestId("xcorr-error").textContent).toBe("no crops selected");
  });
});

describe("XcorrPanel with a result: draws the diverging ramp (spec §4.4)", () => {
  it("fills exactly n*n cells, each from xcorrColor's own value", () => {
    const fake = fakeContext();
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(fake.ctx);
    statsClient.result = {
      n_frames: 10, n: 2,
      xcorr: Float32Array.from([-1, 0, 0.5, 1]),
      timeseries: [], features_available: [],
    };
    render(XcorrPanel);
    const fillRectCalls = fake.calls.filter((c) => c.kind === "call" && c.name === "fillRect");
    expect(fillRectCalls).toHaveLength(4);
    const fillStyleSets = fake.calls
      .filter((c) => c.kind === "set" && c.name === "fillStyle")
      .map((c) => (c as { value: unknown }).value);
    expect(fillStyleSets).toContain(xcorrColor(-1));
    expect(fillStyleSets).toContain(xcorrColor(1));
  });
});

describe("XcorrPanel with a result: hover reads out (row, col) and value (spec §4.4)", () => {
  it("reports the cell under the pointer and clears it on mouseleave", async () => {
    statsClient.result = {
      n_frames: 10, n: 2,
      xcorr: Float32Array.from([-1, 0, 0.5, 1]),
      timeseries: [], features_available: [],
    };
    const { container, getByTestId, queryByTestId } = render(XcorrPanel);
    const canvas = container.querySelector("canvas")!;
    vi.spyOn(canvas, "getBoundingClientRect").mockReturnValue({
      left: 0, top: 0, width: 300, height: 300, right: 300, bottom: 300, x: 0, y: 0, toJSON: () => ({}),
    });

    // cell = xcorrCellSize(min(300, 300), 2) = 150
    await fireEvent.mouseMove(canvas, { clientX: 10, clientY: 10 });
    expect(getByTestId("xcorr-hover").textContent).toBe("row 0 · col 0 · -1.000");

    await fireEvent.mouseMove(canvas, { clientX: 160, clientY: 10 });
    expect(getByTestId("xcorr-hover").textContent).toBe("row 0 · col 1 · 0.000");

    await fireEvent.mouseLeave(canvas);
    expect(queryByTestId("xcorr-hover")).toBeNull();
  });
});
