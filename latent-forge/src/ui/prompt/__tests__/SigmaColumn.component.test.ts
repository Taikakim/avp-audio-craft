// @vitest-environment jsdom
import { cleanup, render } from "@testing-library/svelte";
import { tick } from "svelte";
import {
  afterEach, beforeEach, describe, expect, it, vi,
} from "vitest";
import { BASE_DEFAULTS, cloneRenderSettings } from "../../../lib/forge/defaults";
import type { RenderSettings, Target } from "../../../lib/forge/types";
import { SCHEDULE_DEBOUNCE_MS, scheduleClient } from "../../../lib/sampling/scheduleClient.svelte";
import { settings } from "../../../lib/stores/settings.svelte";
import SigmaColumn from "../SigmaColumn.svelte";

const CLIP: Target = { kind: "clip", id: "c1" };

function fakeSource() {
  const clips: Record<string, RenderSettings> = { c1: cloneRenderSettings(BASE_DEFAULTS) };
  return { clips, clipSettings: (id: string) => clips[id] ?? null, overlapSettings: () => null };
}

let src: ReturnType<typeof fakeSource>;
let fetchMock: ReturnType<typeof vi.fn>;

// Task 4's client calls /schedule itself, so the seam is `fetch`. `forgeApi` is not involved.
function scheduleResponse(steps: number): Response {
  return new Response(
    JSON.stringify({
      ok: true, sigmas: [1, 0.5, 0], steps, duration: 30, sigma_max: 1.0,
      dist_shift: "model", latent_len: 322,
    }),
    { status: 200, headers: { "content-type": "application/json" } },
  );
}

function sentBody(i: number): Record<string, unknown> {
  const [, init] = fetchMock.mock.calls[i] as [string, RequestInit];
  return JSON.parse(String(init.body)) as Record<string, unknown>;
}

beforeEach(() => {
  vi.useFakeTimers();
  src = fakeSource();
  settings.attach(src);
  fetchMock = vi.fn(async () => scheduleResponse(src.clips.c1.steps));
  vi.stubGlobal("fetch", fetchMock);
  // `scheduleClient` is a module singleton (Task 4), so its $state survives an unmount.
  scheduleClient.result = null;
  scheduleClient.error = null;
  // SigmaGraph.svelte draws to a real canvas; jsdom has no 2D context, so stub it the
  // same way Task 7's own test does, purely so mounting does not throw.
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({
    save: () => {}, restore: () => {}, beginPath: () => {}, moveTo: () => {}, lineTo: () => {},
    stroke: () => {}, fill: () => {}, fillRect: () => {}, setTransform: () => {},
    setLineDash: () => {}, scale: () => {}, measureText: () => ({ width: 0 }), fillText: () => {},
  } as unknown as CanvasRenderingContext2D);
});
afterEach(() => {
  settings.detach();
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  vi.useRealTimers();
});

// Every test below uses a LENGTH of its own. The client's cache is keyed on the whole request
// and lives on the singleton, so two tests that built the same request would make the second
// one a silent cache hit that never touches fetch at all.
describe("SigmaColumn builds and sends the ScheduleRequest (spec 4.5 item 3, 5.3)", () => {
  it("sends the target's steps, schedule and sampler_type with the given length as duration", async () => {
    src.clips.c1.steps = 40;
    render(SigmaColumn, { props: { target: CLIP, length: 30, a2a: null } });
    await vi.advanceTimersByTimeAsync(SCHEDULE_DEBOUNCE_MS);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect((fetchMock.mock.calls[0] as [string, RequestInit])[0]).toBe("/schedule");
    expect(sentBody(0)).toMatchObject({
      steps: 40, duration: 30, sampler_type: src.clips.c1.sampler_type,
    });
  });

  it("sends 1.0 as sigma_max for a fresh generate (a2a null)", async () => {
    render(SigmaColumn, { props: { target: CLIP, length: 31, a2a: null } });
    await vi.advanceTimersByTimeAsync(SCHEDULE_DEBOUNCE_MS);
    expect(sentBody(0)).toMatchObject({ sigma_max: 1.0 });
  });

  it("sends the clip's NOISE, capped at 1, as sigma_max on an A2A target", async () => {
    render(SigmaColumn, { props: { target: CLIP, length: 32, a2a: { on: true, noise: 0.4 } } });
    await vi.advanceTimersByTimeAsync(SCHEDULE_DEBOUNCE_MS);
    expect(sentBody(0)).toMatchObject({ sigma_max: 0.4 });
  });

  it("sends no request at all when NOISE floors sigma max below the chartable range", async () => {
    render(SigmaColumn, { props: { target: CLIP, length: 33, a2a: { on: true, noise: 0 } } });
    await vi.advanceTimersByTimeAsync(SCHEDULE_DEBOUNCE_MS);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("re-requests with the new duration when length changes", async () => {
    const { rerender } = render(SigmaColumn, { props: { target: CLIP, length: 34, a2a: null } });
    await vi.advanceTimersByTimeAsync(SCHEDULE_DEBOUNCE_MS);
    fetchMock.mockClear();
    await rerender({ target: CLIP, length: 60, a2a: null });
    await vi.advanceTimersByTimeAsync(SCHEDULE_DEBOUNCE_MS);
    expect(sentBody(0)).toMatchObject({ duration: 60 });
  });

  it("shows the client's error as the graph's note, in the DOM", async () => {
    fetchMock.mockRejectedValue(new Error("render server unreachable"));
    const { container } = render(SigmaColumn, { props: { target: CLIP, length: 35, a2a: null } });
    // No findByText here: it polls on real timers, and this suite runs on fake ones.
    await vi.advanceTimersByTimeAsync(SCHEDULE_DEBOUNCE_MS);
    await tick();
    expect(container.querySelector("[data-graph-error]")?.textContent)
      .toBe("render server unreachable");
  });

  it("shows the LatCH slot legend, or an em dash when a slot is absent", () => {
    const { getByTestId } = render(SigmaColumn, {
      props: {
        target: CLIP, length: 36, a2a: null,
        slots: [{ head: "beat_grid", kind: "value", value: 0.5, weight: 1, start_pct: 0, end_pct: 1 }],
      },
    });
    expect(getByTestId("sigma-slot-0").textContent).toBe("beat_grid");
    expect(getByTestId("sigma-slot-1").textContent).toBe("—");
  });
});
