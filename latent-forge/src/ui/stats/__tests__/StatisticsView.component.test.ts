// @vitest-environment jsdom
import { cleanup, fireEvent, render } from "@testing-library/svelte";
import { tick } from "svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { statsClient } from "../../../lib/stats/statsClient.svelte";
import { view } from "../../../lib/stores/view.svelte";
import type { LaneSel } from "../statsHeader";
import StatisticsView from "../StatisticsView.svelte";

function noopCtx(): CanvasRenderingContext2D {
  const noop = () => {};
  return {
    fillRect: noop, strokeRect: noop, beginPath: noop, moveTo: noop, lineTo: noop, stroke: noop,
    fillText: noop, arc: noop, fill: noop, clearRect: noop, setTransform: noop,
    fillStyle: "", strokeStyle: "", lineWidth: 1, globalAlpha: 1, font: "", textAlign: "left", textBaseline: "top",
  } as unknown as CanvasRenderingContext2D;
}

beforeEach(() => {
  Object.defineProperty(HTMLCanvasElement.prototype, "clientWidth", { configurable: true, get: () => 300 });
  Object.defineProperty(HTMLCanvasElement.prototype, "clientHeight", { configurable: true, get: () => 220 });
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(noopCtx());
  vi.spyOn(statsClient, "requestScalars").mockResolvedValue(undefined);
  vi.spyOn(statsClient, "requestStats").mockResolvedValue(undefined);
});

afterEach(() => {
  delete (HTMLCanvasElement.prototype as unknown as Record<string, unknown>).clientWidth;
  delete (HTMLCanvasElement.prototype as unknown as Record<string, unknown>).clientHeight;
  vi.restoreAllMocks();
  statsClient.dispose();
  view.clearLog();
  cleanup();
});

describe("StatisticsView composes the header and three panels (spec §4.4)", () => {
  it("renders the stats-view region, the header, and all three panels", () => {
    const { container, getByTestId } = render(StatisticsView);
    expect(container.querySelector('[data-region="stats-view"]')).toBeTruthy();
    expect(getByTestId("stats-analyse")).toBeTruthy();
    expect(container.querySelectorAll("[data-stats-panel]")).toHaveLength(3);
  });
});

describe("ANALYSE resolves the current selection through laneLatents, never an arrangement import", () => {
  it("requests exactly the latents laneLatents returns for the selected lane, plus the fixed feature list", async () => {
    const laneLatents = vi.fn((sel: LaneSel) => (sel === 2 ? [{ kind: "crop" as const, crop_id: "000412" }] : []));
    const { container } = render(StatisticsView, { props: { laneLatents } });
    await fireEvent.click(container.querySelector('[data-stats-lane="2"]')!);
    await fireEvent.click(container.querySelector('[data-testid="stats-analyse"]')!);
    expect(laneLatents).toHaveBeenLastCalledWith(2);
    expect(statsClient.requestStats).toHaveBeenCalledWith({
      latents: [{ kind: "crop", crop_id: "000412" }],
      features: ["rms", "onset_strength", "spectral_centroid"],
    });
  });

  it("defaults laneLatents to 'nothing selected' when the caller supplies none", async () => {
    const { container } = render(StatisticsView);
    await fireEvent.click(container.querySelector('[data-testid="stats-analyse"]')!);
    expect(statsClient.requestStats).toHaveBeenCalledWith({
      latents: [], features: ["rms", "onset_strength", "spectral_centroid"],
    });
  });
});

describe("a server error puts a red line in TERMINAL (spec §9.7)", () => {
  it("appends an error-level log line when statsClient.error is set", async () => {
    render(StatisticsView);
    statsClient.error = "no crops selected";
    await tick();
    const lines = view.logLines.filter((l) => l.level === "error");
    expect(lines.some((l) => l.text.includes("no crops selected"))).toBe(true);
  });

  it("appends its own line for a dataset_scalars error, independent of the stats error", async () => {
    render(StatisticsView);
    statsClient.scalarsError = "unknown field";
    await tick();
    const lines = view.logLines.filter((l) => l.level === "error");
    expect(lines.some((l) => l.text.includes("unknown field"))).toBe(true);
  });
});
