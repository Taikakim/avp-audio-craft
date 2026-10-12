// @vitest-environment jsdom
import { cleanup, render } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { sigmaGraphGeometry } from "../../../lib/sampling/sigmaGraph";
import type { SigmaGraphInput } from "../../../lib/sampling/sigmaGraph";
import SigmaGraph from "../SigmaGraph.svelte";

type Call = { kind: "call"; name: string; args: unknown[] } | { kind: "set"; name: string; value: unknown };

function fakeContext() {
  const calls: Call[] = [];
  const ctx: Record<string, unknown> = {};
  const methods = [
    "fillRect", "beginPath", "moveTo", "lineTo", "stroke", "fillText", "save", "restore",
    "clip", "rect", "setLineDash", "setTransform",
  ];
  for (const m of methods) {
    ctx[m] = (...args: unknown[]) => {
      calls.push({ kind: "call", name: m, args });
    };
  }
  ctx.measureText = (text: string) => {
    calls.push({ kind: "call", name: "measureText", args: [text] });
    return { width: text.length * 6 };
  };
  for (const p of ["fillStyle", "strokeStyle", "lineWidth", "globalAlpha"]) {
    let v: unknown;
    Object.defineProperty(ctx, p, {
      get: () => v,
      set: (nv: unknown) => {
        v = nv;
        calls.push({ kind: "set", name: p, value: nv });
      },
    });
  }
  return { ctx: ctx as unknown as CanvasRenderingContext2D, calls };
}

/**
 * The tokens the component reads, set INLINE on an ancestor of the canvas. Measured against
 * real jsdom (M4_CRITIC_FINDINGS.md, "Probe: how jsdom resolves custom properties"): a value
 * set inline on the element or on any ancestor comes back out of getComputedStyle exactly as
 * written, and inherits down. **Do not "fix" this into a `<style>` block** — a `:root` rule goes
 * through jsdom's CSS parser and comes back reformatted (`oklch(90% 0.012 240)` returns as
 * `oklch(90%0.012 240)`, the space after the percent eaten), so every assertion below would
 * fail for a reason that has nothing to do with this component. Values are deliberately
 * unlike the real theme's, so a test can only pass by actually reading the property.
 */
const TOKENS: Record<string, string> = {
  "--panel2": "oklch(11% 0.1 1)",
  "--turq-strong": "oklch(22% 0.2 2)",
  "--slot1": "oklch(33% 0.3 3)",
  "--slot2": "oklch(44% 0.4 4)",
  "--warm": "oklch(55% 0.5 5)",
  "--text-dim": "oklch(66% 0.6 6)",
  "--text": "oklch(77% 0.7 7)",
};

let fake: ReturnType<typeof fakeContext>;
beforeEach(() => {
  fake = fakeContext();
  // render() mounts into a container under document.body, so the canvas inherits these.
  for (const [k, v] of Object.entries(TOKENS)) document.body.style.setProperty(k, v);
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(fake.ctx as never);
  // jsdom 25.0.1 (the lockfile's) returns custom properties from getComputedStyle only for the
  // element that declares them -- it does not inherit them to descendants, which every real
  // browser does and which the component relies on. Walk up the ancestors for `--*` reads so the
  // test sees what a browser would; every other property goes through jsdom untouched.
  const realGcs = window.getComputedStyle.bind(window);
  vi.spyOn(window, "getComputedStyle").mockImplementation((el: Element, pseudo?: string | null) => {
    const cs = realGcs(el, pseudo);
    return new Proxy(cs, {
      get(target, prop) {
        if (prop === "getPropertyValue") {
          return (name: string) => {
            if (!name.startsWith("--")) return target.getPropertyValue(name);
            for (let n: Element | null = el; n; n = n.parentElement) {
              const v = realGcs(n).getPropertyValue(name);
              if (v) return v;
            }
            return "";
          };
        }
        const v = Reflect.get(target, prop);
        return typeof v === "function" ? v.bind(target) : v;
      },
    });
  });
});
afterEach(() => {
  for (const k of Object.keys(TOKENS)) document.body.style.removeProperty(k);
  vi.restoreAllMocks();
  cleanup();
});

const SIGMAS = [1, 0.6, 0.3, 0.1, 0];

function input(over: Partial<SigmaGraphInput> = {}): SigmaGraphInput {
  return {
    sigmas: SIGMAS, steps: 4, cfgLo: 0, cfgHi: 1, stepped: false, scalePhi: 0,
    slots: [], width: 100, height: 118, ...over,
  };
}

function tokenSets(name: string): unknown[] {
  return fake.calls.filter((c) => c.kind === "set" && c.name === name).map((c) => (c as { value: unknown }).value);
}

function argsOf(name: string): unknown[][] {
  return fake.calls
    .filter((c) => c.kind === "call" && c.name === name)
    .map((c) => (c as { args: unknown[] }).args);
}

/**
 * The moveTo/lineTo pairs of the ONE path stroked in `color`, from that strokeStyle set up to
 * the `stroke` that closes it. Both the sigma and the progress curve emit lineTo calls, so a
 * flat list of every lineTo cannot tell a component that swapped them apart from one that did
 * not; slicing by colour can.
 */
function pathStrokedIn(color: string): unknown[][] {
  const start = fake.calls.findIndex(
    (c) => c.kind === "set" && c.name === "strokeStyle" && c.value === color,
  );
  if (start < 0) return [];
  const end = fake.calls.findIndex((c, i) => i > start && c.kind === "call" && c.name === "stroke");
  return fake.calls
    .slice(start, end < 0 ? undefined : end)
    .filter((c) => c.kind === "call" && (c.name === "moveTo" || c.name === "lineTo"))
    .map((c) => (c as { args: unknown[] }).args);
}

describe("SigmaGraph, a full render", () => {
  it("carries the data-help attribute and a stable test id", () => {
    const { getByTestId } = render(SigmaGraph, {
      props: { input: input(), note: null, pending: false, error: null },
    });
    expect(getByTestId("sigma-graph").getAttribute("data-help")).toBeTruthy();
  });

  it("fills the ground with the resolved --panel2 before anything else", () => {
    render(SigmaGraph, { props: { input: input(), note: null, pending: false, error: null } });
    const fillStyles = tokenSets("fillStyle");
    expect(fillStyles[0]).toBe(TOKENS["--panel2"]);
    const firstFillRectIndex = fake.calls.findIndex((c) => c.kind === "call" && c.name === "fillRect");
    const firstStrokeIndex = fake.calls.findIndex((c) => c.kind === "call" && c.name === "stroke");
    expect(firstFillRectIndex).toBeGreaterThanOrEqual(0);
    expect(firstStrokeIndex).toBeGreaterThan(firstFillRectIndex);
  });

  it("fills the CFG band with --turq-strong and strokes its two edges in the same colour", () => {
    render(SigmaGraph, { props: { input: input(), note: null, pending: false, error: null } });
    expect(tokenSets("fillStyle")).toContain(TOKENS["--turq-strong"]);
    expect(tokenSets("strokeStyle")).toContain(TOKENS["--turq-strong"]);
  });

  it("strokes the sigma curve in --text and the progress curve in --turq-strong, dashed", () => {
    render(SigmaGraph, { props: { input: input(), note: null, pending: false, error: null } });
    expect(tokenSets("strokeStyle")).toContain(TOKENS["--text"]);
    const dashCalls = fake.calls.filter((c) => c.kind === "call" && c.name === "setLineDash");
    expect(dashCalls.length).toBeGreaterThan(0);
  });

  it("draws the tick marks and both labels in --text-dim", () => {
    render(SigmaGraph, { props: { input: input(), note: null, pending: false, error: null } });
    expect(tokenSets("fillStyle")).toContain(TOKENS["--text-dim"]);
    const textCalls = fake.calls.filter((c) => c.kind === "call" && c.name === "fillText");
    expect(textCalls.some((c) => (c as { args: unknown[] }).args[0] === "sigma + progress")).toBe(true);
    expect(textCalls.some((c) => (c as { args: unknown[] }).args[0] === "4")).toBe(true);
  });

  it("scales the backing store by devicePixelRatio through setTransform", () => {
    const dprSpy = vi.spyOn(window, "devicePixelRatio", "get").mockReturnValue(2);
    render(SigmaGraph, { props: { input: input(), note: null, pending: false, error: null } });
    const transform = fake.calls.find((c) => c.kind === "call" && c.name === "setTransform") as
      { args: unknown[] } | undefined;
    expect(transform?.args).toEqual([2, 0, 0, 2, 0, 0]);
    dprSpy.mockRestore();
  });
});

describe("SigmaGraph with an active LatCH slot", () => {
  it("fills the slot lane with --slot1 for index 0 and --slot2 for index 1", () => {
    render(SigmaGraph, {
      props: {
        input: input({
          cfgLo: 0.5, cfgHi: 1,
          slots: [
            { head: "onsets", kind: "value", value: 0.5, weight: 1, start_pct: 0.2, end_pct: 0.6 },
            { head: "beat_grid", kind: "value", value: 0.5, weight: 1, start_pct: 0, end_pct: 0.1 },
          ],
        }),
        note: null, pending: false, error: null,
      },
    });
    const fillStyles = tokenSets("fillStyle");
    expect(fillStyles).toContain(TOKENS["--slot1"]);
    expect(fillStyles).toContain(TOKENS["--slot2"]);
  });
});

describe("SigmaGraph, rescale line", () => {
  it("draws the dotted rescale line in --warm only when scale_phi > 0", () => {
    render(SigmaGraph, {
      props: { input: input({ scalePhi: 0.3 }), note: null, pending: false, error: null },
    });
    expect(tokenSets("strokeStyle")).toContain(TOKENS["--warm"]);
  });

  it("draws no rescale line when scale_phi is 0", () => {
    render(SigmaGraph, {
      props: { input: input({ scalePhi: 0 }), note: null, pending: false, error: null },
    });
    expect(tokenSets("strokeStyle")).not.toContain(TOKENS["--warm"]);
  });
});

describe("SigmaGraph strokes Task 6's geometry, not its own", () => {
  it("draws the sigma curve through sigmaGraphGeometry's own first and last sigmaPath points", () => {
    const inp = input();
    render(SigmaGraph, { props: { input: inp, note: null, pending: false, error: null } });
    // Same input the component was handed, so a component that strokes an empty path, or
    // strokes the progress curve where the sigma curve belongs, cannot pass this.
    const g = sigmaGraphGeometry(inp);
    const first = g.sigmaPath[0];
    const last = g.sigmaPath[g.sigmaPath.length - 1];
    const path = pathStrokedIn(TOKENS["--text"]);
    expect(path.length).toBe(g.sigmaPath.length); // the opening moveTo plus one lineTo each
    expect(path[0]).toEqual([first.x, first.y]); // the moveTo that opens the path
    expect(argsOf("lineTo")).toContainEqual([last.x, last.y]);
    expect(path[path.length - 1]).toEqual([last.x, last.y]);
  });

  it("fills the CFG band at exactly the rectangle sigmaGraphGeometry computed", () => {
    const inp = input({ cfgLo: 0.5, cfgHi: 0.9 });
    render(SigmaGraph, { props: { input: inp, note: null, pending: false, error: null } });
    const g = sigmaGraphGeometry(inp);
    expect(argsOf("fillRect")).toContainEqual([
      g.cfgBand.x0, 0, g.cfgBand.x1 - g.cfgBand.x0, g.plotHeight,
    ]);
  });
});

describe("SigmaGraph, pending dims the curve", () => {
  it("sets globalAlpha below 1 while pending, and back to 1 for the background", () => {
    render(SigmaGraph, { props: { input: input(), note: null, pending: true, error: null } });
    const alphas = tokenSets("globalAlpha") as number[];
    expect(alphas).toContain(1);
    expect(alphas.some((a) => a > 0 && a < 1)).toBe(true);
  });
});

describe("SigmaGraph, note and error", () => {
  // Both are DOM siblings of the canvas, never fillText: Task 10 looks the note up with
  // Testing Library, and text painted into a canvas is invisible to every DOM query there is.
  it("renders the note as a DOM sibling of the canvas when there is no error", () => {
    const { container, getByText } = render(SigmaGraph, {
      props: { input: input(), note: "schedule shape is charted from M3 onward", pending: false, error: null },
    });
    expect(getByText("schedule shape is charted from M3 onward")).toBeTruthy();
    expect(container.querySelector("[data-graph-note]")?.textContent)
      .toBe("schedule shape is charted from M3 onward");
    expect(container.querySelector("[data-graph-error]")).toBeNull();
  });

  it("renders the error instead of the note when both are set", () => {
    const { container } = render(SigmaGraph, {
      props: { input: input(), note: "a note", pending: false, error: "schedule is not non-increasing" },
    });
    expect(container.querySelector("[data-graph-error]")?.textContent)
      .toBe("schedule is not non-increasing");
    expect(container.querySelector("[data-graph-note]")).toBeNull();
  });

  it("renders only the background and the note when input is null", () => {
    const { container } = render(SigmaGraph, {
      props: { input: null, note: "computing schedule…", pending: true, error: null },
    });
    expect(container.querySelector("[data-graph-note]")?.textContent).toBe("computing schedule…");
    expect(container.querySelector('canvas[data-canvas="sigma"]')).toBeTruthy();
    expect(fake.calls.some((c) => c.kind === "call" && c.name === "stroke")).toBe(false);
  });
});
