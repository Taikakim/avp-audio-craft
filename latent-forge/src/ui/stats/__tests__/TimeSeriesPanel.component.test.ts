// @vitest-environment jsdom
import { cleanup, render } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { statsClient } from "../../../lib/stats/statsClient.svelte";
import TimeSeriesPanel from "../TimeSeriesPanel.svelte";

function noopCtx(): CanvasRenderingContext2D {
  const noop = () => {};
  return {
    fillRect: noop, beginPath: noop, moveTo: noop, lineTo: noop, stroke: noop,
    fillText: noop, clearRect: noop, setTransform: noop,
    fillStyle: "", strokeStyle: "", lineWidth: 1, globalAlpha: 1, font: "", textAlign: "left", textBaseline: "top",
  } as unknown as CanvasRenderingContext2D;
}

beforeEach(() => {
  Object.defineProperty(HTMLCanvasElement.prototype, "clientWidth", { configurable: true, get: () => 300 });
  Object.defineProperty(HTMLCanvasElement.prototype, "clientHeight", { configurable: true, get: () => 220 });
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(noopCtx());
});

afterEach(() => {
  delete (HTMLCanvasElement.prototype as unknown as Record<string, unknown>).clientWidth;
  delete (HTMLCanvasElement.prototype as unknown as Record<string, unknown>).clientHeight;
  vi.restoreAllMocks();
  statsClient.dispose();
  cleanup();
});

describe("TimeSeriesPanel before any analysis", () => {
  it("shows M1's empty-state text", () => {
    const { getByText } = render(TimeSeriesPanel);
    expect(getByText("no analysis yet — choose lanes and press ANALYSE")).toBeTruthy();
  });

  it("offers the three computed-feature defaults before a result arrives", () => {
    const { container } = render(TimeSeriesPanel);
    const opts = Array.from(container.querySelector("select")!.querySelectorAll("option")).map((o) => o.textContent);
    expect(opts).toEqual(["rms", "onset_strength", "spectral_centroid"]);
  });
});

describe("TimeSeriesPanel while a request is pending", () => {
  it("shows an analysing message", () => {
    statsClient.pending = true;
    const { getByText } = render(TimeSeriesPanel);
    expect(getByText("analysing…")).toBeTruthy();
  });
});

describe("TimeSeriesPanel on a server error (spec §9.7)", () => {
  it("shows a one-line error message", () => {
    statsClient.error = "job failed";
    const { getByTestId } = render(TimeSeriesPanel);
    expect(getByTestId("timeseries-error").textContent).toBe("job failed");
  });
});

describe("TimeSeriesPanel offers every feature the server reports (spec §4.4)", () => {
  it("replaces the default list with features_available once a result has arrived", () => {
    statsClient.result = {
      n_frames: 100, n: 0, xcorr: new Float32Array(0),
      timeseries: [{ index: 0, feature: "rms", fps: 10.77, values: [0.1, 0.2] }],
      features_available: ["rms", "chroma_ts"],
    };
    const { container } = render(TimeSeriesPanel);
    const opts = Array.from(container.querySelector("select")!.querySelectorAll("option")).map((o) => o.textContent);
    expect(opts).toEqual(["rms", "chroma_ts"]);
  });
});

describe("TimeSeriesPanel with a result", () => {
  it("shows a no-data message when the selected feature (rms, the default) matches no series in the result", () => {
    statsClient.result = {
      n_frames: 100, n: 0, xcorr: new Float32Array(0),
      timeseries: [{ index: 0, feature: "onset_strength", fps: 10.77, values: [0.1] }],
      features_available: ["onset_strength"],
    };
    const { getByText } = render(TimeSeriesPanel);
    expect(getByText("no data for this feature")).toBeTruthy();
  });

  it("lists one legend entry per clip, labelled from the indexLabels prop", () => {
    statsClient.result = {
      n_frames: 100, n: 0, xcorr: new Float32Array(0),
      timeseries: [
        { index: 0, feature: "rms", fps: 10.77, values: [0.1, 0.2] },
        { index: 1, feature: "rms", fps: 10.77, values: [0.3, null] },
      ],
      features_available: ["rms"],
    };
    const { getByTestId } = render(TimeSeriesPanel, { props: { indexLabels: ["LANE 1 · clip_a", "LANE 2 · clip_b"] } });
    const items = Array.from(getByTestId("timeseries-legend").querySelectorAll("li")).map((li) => li.textContent);
    expect(items).toEqual(["LANE 1 · clip_a", "LANE 2 · clip_b"]);
  });

  it("falls back to 'series <index>' when no label is supplied for that index", () => {
    statsClient.result = {
      n_frames: 50, n: 0, xcorr: new Float32Array(0),
      timeseries: [{ index: 2, feature: "rms", fps: 10.77, values: [1] }],
      features_available: ["rms"],
    };
    const { getByTestId } = render(TimeSeriesPanel);
    expect(getByTestId("timeseries-legend").textContent).toBe("series 2");
  });

  it("renders without throwing when a series is all-null (a feature the latent lacks, spec §6.5)", () => {
    statsClient.result = {
      n_frames: 50, n: 0, xcorr: new Float32Array(0),
      timeseries: [{ index: 0, feature: "rms", fps: 10.77, values: [null, null, null] }],
      features_available: ["rms"],
    };
    expect(() => render(TimeSeriesPanel)).not.toThrow();
  });
});
