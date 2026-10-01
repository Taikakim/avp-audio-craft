// @vitest-environment jsdom
import { cleanup, fireEvent, render } from "@testing-library/svelte";
import {
  afterEach, beforeEach, describe, expect, it, vi,
} from "vitest";
import { BASE_DEFAULTS, LENGTH_CAP_SEC, cloneRenderSettings } from "../../../lib/forge/defaults";
import type { Target } from "../../../lib/forge/types";
import { scheduleClient } from "../../../lib/sampling/scheduleClient.svelte";
import { settings } from "../../../lib/stores/settings.svelte";
import { view } from "../../../lib/stores/view.svelte";
import PromptSigmaTab from "../PromptSigmaTab.svelte";

const NONE: Target = { kind: "none" };
const CLIP: Target = { kind: "clip", id: "c1" };

// Task 4's client calls /schedule with fetch, so that is the seam here too.
let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.useFakeTimers();
  fetchMock = vi.fn(async () => new Response(
    JSON.stringify({
      ok: true, sigmas: [1, 0.5, 0], steps: 24, duration: 30, sigma_max: 1.0,
      dist_shift: "model", latent_len: 322,
    }),
    { status: 200, headers: { "content-type": "application/json" } },
  ));
  vi.stubGlobal("fetch", fetchMock);
  scheduleClient.result = null; // a module singleton, so its $state outlives an unmount
  scheduleClient.error = null;
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({
    save: () => {}, restore: () => {}, beginPath: () => {}, moveTo: () => {}, lineTo: () => {},
    stroke: () => {}, fill: () => {}, fillRect: () => {}, setTransform: () => {},
    setLineDash: () => {}, scale: () => {}, measureText: () => ({ width: 0 }), fillText: () => {},
  } as unknown as CanvasRenderingContext2D);
  view.selection = NONE;
  // `settings` is a module singleton: a LENGTH written by one test must not reach the next.
  settings.defaults.duration_sec = BASE_DEFAULTS.duration_sec;
});
afterEach(() => {
  settings.detach();
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe("PromptSigmaTab assembles the three columns (spec 4.5)", () => {
  it("tags itself as the prompt tab body, and each column with its own data-col", () => {
    const { container } = render(PromptSigmaTab);
    expect(container.querySelector('[data-tab-body="prompt"]')).toBeTruthy();
    expect(container.querySelector('[data-col="prompt"]')).toBeTruthy();
    expect(container.querySelector('[data-col="model-stage"]')).toBeTruthy();
    expect(container.querySelector('[data-col="sigma"]')).toBeTruthy();
    expect(container.querySelector('canvas[data-canvas="sigma"]')).toBeTruthy();
  });

  it("reads the target from view.selection, not a prop", () => {
    view.selection = CLIP;
    const { getByTestId } = render(PromptSigmaTab, { props: { clipName: "kick loop" } });
    expect(getByTestId("target-name").textContent).toBe("kick loop");
  });

  it("passes the clip-shaped props straight through to the target bar", () => {
    view.selection = CLIP;
    const { getByTestId } = render(PromptSigmaTab, {
      props: { clipName: "kick loop", clipHasLatent: true, a2a: { on: false, noise: 0.4 }, op: "generate" },
    });
    expect(getByTestId("target-clip-row")).toBeTruthy();
  });

  it("owns LENGTH through settings.duration_sec and feeds the same number to the schedule request", async () => {
    const { getByTestId } = render(PromptSigmaTab);
    await fireEvent.change(getByTestId("stage-length"), { target: { value: "77" } });
    await vi.advanceTimersByTimeAsync(200);
    const bodies = fetchMock.mock.calls.map(
      (c) => JSON.parse(String((c as [string, RequestInit])[1].body)) as Record<string, unknown>,
    );
    expect(bodies).toContainEqual(expect.objectContaining({ duration: 77 }));
  });

  it("clamps a typed length to LENGTH_CAP_SEC", async () => {
    const { getByTestId } = render(PromptSigmaTab);
    await fireEvent.change(getByTestId("stage-length"), { target: { value: "9999" } });
    expect((getByTestId("stage-length") as HTMLInputElement).value).toBe(String(LENGTH_CAP_SEC));
    expect(settings.current(view.selection).duration_sec).toBe(LENGTH_CAP_SEC);
  });

  it("writes LENGTH to the selected target's settings, so it is per target not per tab", async () => {
    // Two clips that own their settings: with nothing attached every target resolves to the one
    // session-defaults object, and "per target" would be untestable.
    const clips = { c1: cloneRenderSettings(BASE_DEFAULTS), c2: cloneRenderSettings(BASE_DEFAULTS) };
    settings.attach({
      clipSettings: (id) => (clips as Record<string, typeof clips.c1>)[id] ?? null,
      overlapSettings: () => null,
    });
    view.selection = { kind: "clip", id: "c1" };
    const { getByTestId } = render(PromptSigmaTab);
    await fireEvent.change(getByTestId("stage-length"), { target: { value: "77" } });
    expect(settings.current({ kind: "clip", id: "c1" }).duration_sec).toBe(77);
    // A different target keeps its own -- the default, untouched.
    expect(settings.current({ kind: "clip", id: "c2" }).duration_sec).toBeCloseTo(47.556, 3);
  });
});
