// @vitest-environment jsdom
import { cleanup, fireEvent, render } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { BASE_DEFAULTS, SCHEDULE_DEFAULT, cloneRenderSettings } from "../../../lib/forge/defaults";
import type { RenderSettings, Target } from "../../../lib/forge/types";
import { progressAtStep } from "../../../lib/sampling/cfgInterval";
import { scheduleClient } from "../../../lib/sampling/scheduleClient.svelte";
import { settings } from "../../../lib/stores/settings.svelte";
import { view } from "../../../lib/stores/view.svelte";
import AdvancedSampling from "../AdvancedSampling.svelte";

const CLIP: Target = { kind: "clip", id: "c1" };

// sigma0 = 1, four steps: progress at each index is 0, 0.4, 0.7, 0.9, 1
const SIGMAS = [1, 0.6, 0.3, 0.1, 0];

function fakeSource() {
  const clips: Record<string, RenderSettings> = { c1: cloneRenderSettings(BASE_DEFAULTS) };
  return { clips, clipSettings: (id: string) => clips[id] ?? null, overlapSettings: () => null };
}

/**
 * This module never requests a schedule -- Task 10's SigmaColumn does -- so a test that needs
 * the STEPS unit drives the shared singleton directly, through the same public API the column
 * uses. `flush()` is Task 4's own test seam: it skips the debounce.
 */
async function seedSchedule(): Promise<void> {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(
    JSON.stringify({
      ok: true, sigmas: SIGMAS, steps: 4, duration: 30, sigma_max: 1,
      dist_shift: "model", latent_len: 322,
    }),
    { status: 200, headers: { "content-type": "application/json" } },
  )));
  scheduleClient.request({
    steps: 4, duration: 30, sigma_max: 1, sampler_type: "euler", schedule: { ...SCHEDULE_DEFAULT },
  });
  await scheduleClient.flush();
}

let src: ReturnType<typeof fakeSource>;
beforeEach(() => {
  src = fakeSource();
  settings.attach(src);
  view.selection = CLIP;
  // `scheduleClient` is a module singleton, so a result seeded by one test would otherwise
  // still be there for the next one.
  scheduleClient.result = null;
  scheduleClient.error = null;
});
afterEach(() => {
  settings.detach();
  cleanup();
  vi.unstubAllGlobals();
});

describe("AdvancedSampling (spec 4.6 item 4, 5.3)", () => {
  it("offers the current objective's samplers with the target's own value selected", () => {
    src.clips.c1.sampler_type = "rk4";
    const { getByTestId } = render(AdvancedSampling);
    expect((getByTestId("adv-sampler") as HTMLSelectElement).value).toBe("rk4");
  });

  it("disables and relabels the sampler when the given latch forces Euler", () => {
    const { getByTestId } = render(AdvancedSampling, {
      props: {
        latch: {
          latch_on: true,
          slots: [{ head: "onsets", kind: "value", value: 0.5, weight: 1, start_pct: 0, end_pct: 1 }],
        },
      },
    });
    const select = getByTestId("adv-sampler") as HTMLSelectElement;
    expect(select.disabled).toBe(true);
    expect(select.value).toBe("euler");
    expect(select.options[0].textContent).toBe("euler (forced by LatCH)");
  });

  it("writes a chosen shape through settings.patchSchedule", async () => {
    const { getByTestId } = render(AdvancedSampling);
    await fireEvent.change(getByTestId("adv-shape"), { target: { value: "geometric" } });
    expect(src.clips.c1.schedule.shape).toBe("geometric");
  });

  it("greys lambda min/max and shows the note unless the shape is logsnr", async () => {
    const first = render(AdvancedSampling);
    expect((first.getByTestId("adv-lam-min") as HTMLInputElement).disabled).toBe(true);
    expect((first.getByTestId("adv-lam-max") as HTMLInputElement).disabled).toBe(true);
    expect(first.getByTestId("adv-lam-note")).toBeTruthy();
    await fireEvent.change(first.getByTestId("adv-shape"), { target: { value: "logsnr" } });
    expect(src.clips.c1.schedule.shape).toBe("logsnr");
    first.unmount();
    // Fresh render for the second half: this fixture's clips are plain objects, so the change
    // above is not reactive here (M5's real source is $state, where it is).
    const second = render(AdvancedSampling);
    expect((second.getByTestId("adv-lam-min") as HTMLInputElement).disabled).toBe(false);
    expect((second.getByTestId("adv-lam-max") as HTMLInputElement).disabled).toBe(false);
    expect(second.queryByTestId("adv-lam-note")).toBeNull();
  });

  it("shows sigma max read-only at 1.00 with no A2A clip", () => {
    const { getByLabelText } = render(AdvancedSampling);
    const field = getByLabelText("σ MAX") as HTMLInputElement;
    expect(field.value).toBe("1.00");
    expect(field.readOnly).toBe(true);
  });

  it("mirrors the clip's own NOISE when A2A is on", () => {
    const { getByLabelText } = render(AdvancedSampling, { props: { a2a: { on: true, noise: 0.4 } } });
    expect((getByLabelText("σ MAX") as HTMLInputElement).value).toBe("0.40");
  });

  it("writes rho, sigma min, plateaus and tilt through settings.patchSchedule", async () => {
    const { getByTestId } = render(AdvancedSampling);
    await fireEvent.change(getByTestId("adv-rho"), { target: { value: "3" } });
    await fireEvent.change(getByTestId("adv-sigma-min"), { target: { value: "0.05" } });
    await fireEvent.change(getByTestId("adv-plateaus"), { target: { value: "10" } });
    await fireEvent.change(getByTestId("adv-tilt"), { target: { value: "0.4" } });
    expect(src.clips.c1.schedule.rho).toBe(3);
    expect(src.clips.c1.schedule.sigma_min).toBe(0.05);
    expect(src.clips.c1.schedule.plateaus).toBe(10);
    expect(src.clips.c1.schedule.tilt).toBe(0.4);
  });

  it("writes CFG rescale through settings.patch, not patchSchedule", async () => {
    const { getByTestId } = render(AdvancedSampling);
    await fireEvent.change(getByTestId("adv-rescale"), { target: { value: "0.3" } });
    expect(src.clips.c1.scale_phi).toBe(0.3);
  });

  it("writes the CFG interval bounds through settings.patch as progress, never as a step", async () => {
    const { getByTestId } = render(AdvancedSampling);
    await fireEvent.change(getByTestId("adv-cfg-lo"), { target: { value: "0.2" } });
    await fireEvent.change(getByTestId("adv-cfg-hi"), { target: { value: "0.9" } });
    expect(src.clips.c1.cfg_interval_progress).toEqual([0.2, 0.9]);
  });

  it("disables the UNIT toggle until a schedule arrives, and says why", () => {
    const { getByTestId } = render(AdvancedSampling);
    const toggle = getByTestId("adv-cfg-unit") as HTMLButtonElement;
    expect(toggle.disabled).toBe(true);
    expect(toggle.title).toBe("the step index needs a schedule from the server");
    expect(toggle.textContent).toBe("PROGRESS");
  });

  it("toggling the CFG unit changes only the displayed label, never the stored progress", async () => {
    await seedSchedule();
    const { getByTestId } = render(AdvancedSampling);
    const before = [...src.clips.c1.cfg_interval_progress];
    await fireEvent.click(getByTestId("adv-cfg-unit"));
    expect(src.clips.c1.cfg_interval_progress).toEqual(before);
    expect(getByTestId("adv-cfg-unit").textContent).toBe("STEPS");
    await fireEvent.click(getByTestId("adv-cfg-unit"));
    expect(getByTestId("adv-cfg-unit").textContent).toBe("PROGRESS");
  });

  it("in the STEPS unit shows the crossing step index and still stores progress, never the step", async () => {
    await seedSchedule();
    settings.patch(CLIP, { cfg_interval_progress: [0.5, 1] });
    const { getByTestId } = render(AdvancedSampling);
    await fireEvent.click(getByTestId("adv-cfg-unit"));
    // progress 0.5 first reaches at index 2 of SIGMAS, and 1 at the last index
    expect((getByTestId("adv-cfg-lo") as HTMLInputElement).value).toBe("2");
    expect((getByTestId("adv-cfg-hi") as HTMLInputElement).value).toBe("4");
    // typing a step index writes the progress that step sits at -- NOT 3
    await fireEvent.change(getByTestId("adv-cfg-lo"), { target: { value: "3" } });
    expect(src.clips.c1.cfg_interval_progress[0]).toBeCloseTo(progressAtStep(SIGMAS, 3));
    expect(src.clips.c1.cfg_interval_progress[0]).not.toBe(3);
  });

  it("renders a validation error inline under the offending field", async () => {
    settings.patchSchedule(CLIP, { rho: 999 });
    const { getByTestId } = render(AdvancedSampling);
    expect(getByTestId("adv-issue-rho").textContent).toContain("rho must be between");
  });
});
