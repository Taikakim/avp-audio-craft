// @vitest-environment jsdom
import { cleanup, fireEvent, render } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { statsClient } from "../../../lib/stats/statsClient.svelte";
import XYPanel from "../XYPanel.svelte";

type Call = { kind: "call"; name: string; args: unknown[] } | { kind: "set"; name: string; value: unknown };

function fakeContext() {
  const calls: Call[] = [];
  const ctx: Record<string, unknown> = {};
  const methods = ["fillRect", "beginPath", "moveTo", "lineTo", "stroke", "fillText", "arc", "fill", "clearRect", "setTransform"];
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

/** Inline on an ancestor of the canvas comes back out of getComputedStyle
 *  exactly as written, and inherits down (HANDOUT.md's measured jsdom
 *  table) -- render() mounts under document.body, so setting these there
 *  gives panelColour a real, distinct value to read per token. */
const TOKENS: Record<string, string> = {
  "--border": "oklch(50% 0.02 10)",
  "--text-dim": "oklch(60% 0.02 20)",
  "--turq-strong": "oklch(70% 0.15 195)",
};

let fake: ReturnType<typeof fakeContext>;

beforeEach(() => {
  Object.defineProperty(HTMLCanvasElement.prototype, "clientWidth", { configurable: true, get: () => 300 });
  Object.defineProperty(HTMLCanvasElement.prototype, "clientHeight", { configurable: true, get: () => 300 });
  fake = fakeContext();
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(fake.ctx);
  for (const [k, v] of Object.entries(TOKENS)) document.body.style.setProperty(k, v);
  // requestScalars normally hits fetch; every test below drives statsClient's
  // state directly, so the request itself is a no-op here.
  vi.spyOn(statsClient, "requestScalars").mockResolvedValue(undefined);
});

afterEach(() => {
  delete (HTMLCanvasElement.prototype as unknown as Record<string, unknown>).clientWidth;
  delete (HTMLCanvasElement.prototype as unknown as Record<string, unknown>).clientHeight;
  for (const k of Object.keys(TOKENS)) document.body.style.removeProperty(k);
  vi.restoreAllMocks();
  statsClient.dispose();
  cleanup();
});

describe("XYPanel requests its own data independently of ANALYSE (spec §6.5)", () => {
  it("calls requestScalars with the default bpm/lufs pair on mount", () => {
    render(XYPanel);
    expect(statsClient.requestScalars).toHaveBeenCalledWith("bpm", "lufs");
  });

  it("re-requests when the X select changes", async () => {
    const { container } = render(XYPanel);
    const selects = container.querySelectorAll("select");
    await fireEvent.change(selects[0], { target: { value: "rel_pos" } });
    expect(statsClient.requestScalars).toHaveBeenLastCalledWith("rel_pos", "lufs");
  });
});

describe("XYPanel populates X/Y selects from the server's own fields, never a hard-coded list", () => {
  it("offers the default three before any response", () => {
    const { container } = render(XYPanel);
    const opts = Array.from(container.querySelectorAll("select")[0].querySelectorAll("option")).map((o) => o.textContent);
    expect(opts).toEqual(["bpm", "lufs", "rel_pos"]);
  });

  it("offers every field the server reports, once a response has arrived", () => {
    statsClient.scalars = { fields: ["bpm", "lufs", "rel_pos", "onset_density"], points: [] };
    const { container } = render(XYPanel);
    const opts = Array.from(container.querySelectorAll("select")[0].querySelectorAll("option")).map((o) => o.textContent);
    expect(opts).toEqual(["bpm", "lufs", "rel_pos", "onset_density"]);
  });
});

describe("XYPanel states", () => {
  it("shows a one-line error on a server error (spec §9.7)", () => {
    statsClient.scalarsError = "unknown field";
    const { getByTestId } = render(XYPanel);
    expect(getByTestId("xy-error").textContent).toBe("unknown field");
  });

  it("shows a loading message before the first response", () => {
    statsClient.scalarsPending = true;
    const { getByText } = render(XYPanel);
    expect(getByText("loading…")).toBeTruthy();
  });

  it("shows a no-data message when a response has zero points", () => {
    statsClient.scalars = { fields: ["bpm", "lufs", "rel_pos"], points: [] };
    const { getByText } = render(XYPanel);
    expect(getByText("no scalar data for this pair")).toBeTruthy();
  });

  it("drops a point that is null on either axis before plotting, without crashing", () => {
    statsClient.scalars = {
      fields: ["bpm", "lufs", "rel_pos"],
      points: [
        { crop_id: "a", x: 120, y: -14, label: "a" },
        { crop_id: "b", x: null as unknown as number, y: -10, label: "b" },
      ],
    };
    expect(() => render(XYPanel)).not.toThrow();
  });
});

describe("XYPanel highlighting (spec §4.4)", () => {
  it("highlights nothing when laneCropIds is not supplied", () => {
    statsClient.scalars = { fields: ["bpm", "lufs", "rel_pos"], points: [{ crop_id: "a", x: 1, y: 2, label: "a" }] };
    render(XYPanel);
    const fillStyleSets = fake.calls
      .filter((c) => c.kind === "set" && c.name === "fillStyle")
      .map((c) => (c as { value: unknown }).value);
    expect(fillStyleSets).not.toContain(TOKENS["--turq-strong"]);
  });

  it("draws the dim pass before the highlighted pass, one fill() per point in each", () => {
    statsClient.scalars = {
      fields: ["bpm", "lufs", "rel_pos"],
      points: [
        { crop_id: "a", x: 1, y: 2, label: "a" },
        { crop_id: "b", x: 3, y: 4, label: "b" },
      ],
    };
    render(XYPanel, { props: { laneCropIds: new Set(["b"]) } });
    const fillStyleSets = fake.calls
      .filter((c) => c.kind === "set" && c.name === "fillStyle")
      .map((c) => (c as { value: unknown }).value);
    const dimIndex = fillStyleSets.indexOf(TOKENS["--text-dim"]);
    const turqIndex = fillStyleSets.indexOf(TOKENS["--turq-strong"]);
    expect(dimIndex).toBeGreaterThanOrEqual(0);
    expect(turqIndex).toBeGreaterThan(dimIndex);
    expect(fake.calls.filter((c) => c.kind === "call" && c.name === "fill")).toHaveLength(2);
  });
});
