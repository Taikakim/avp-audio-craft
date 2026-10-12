// @vitest-environment jsdom
// Critic follow-up #2: PromptSigmaTab sources TargetBar's clip props from M5's arrangement, so the
// A2A toggle M5 T12's Playwright gate clicks really turns A2A on.
import { cleanup, fireEvent, render } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { scheduleClient } from "../../../lib/sampling/scheduleClient.svelte";
import { arrangement } from "../../../lib/stores/arrangement.svelte";
import { view } from "../../../lib/stores/view.svelte";
import PromptSigmaTab from "../PromptSigmaTab.svelte";

beforeEach(() => {
  // SigmaColumn fetches /schedule and draws a canvas: the same seams as M4's PromptSigmaTab test.
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({
    ok: true, sigmas: [1, 0.5, 0], steps: 24, duration: 30, sigma_max: 1.0, dist_shift: "model", latent_len: 322,
  }), { status: 200, headers: { "content-type": "application/json" } })));
  scheduleClient.result = null;
  scheduleClient.error = null;
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({
    save: () => {}, restore: () => {}, beginPath: () => {}, moveTo: () => {}, lineTo: () => {},
    stroke: () => {}, fill: () => {}, fillRect: () => {}, setTransform: () => {},
    setLineDash: () => {}, scale: () => {}, measureText: () => ({ width: 0 }), fillText: () => {},
  } as unknown as CanvasRenderingContext2D);
});

afterEach(() => {
  cleanup();
  view.clearSelection();
  arrangement.clips.splice(0, arrangement.clips.length);
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("PromptSigmaTab after M7 T9: the target bar reads the selected clip (critic follow-up #2)", () => {
  it("the A2A toggle turns the SELECTED clip's A2A on and off through M5, and NOISE shows the clip's own", async () => {
    const c = arrangement.addClip({ lane: 2, startSec: 0, durSec: 4, audio: { kind: "crop", crop_id: "A" } });
    view.select({ kind: "clip", id: c.id });
    const { getByTestId } = render(PromptSigmaTab);   // propless, exactly as BottomPane mounts it
    const toggle = getByTestId("target-a2a-toggle");
    expect(toggle.textContent).toBe("A2A OFF");
    await fireEvent.click(toggle);
    expect(c.a2a?.on).toBe(true);                     // what MasterStrip's envelope overlay reads
    expect(getByTestId("target-a2a-toggle").textContent).toBe("A2A ON");
    expect((getByTestId("target-noise") as HTMLInputElement).value).toBe(String(c.a2a!.noise));
    await fireEvent.click(getByTestId("target-a2a-toggle"));
    expect(c.a2a?.on).toBe(false);                    // off again, envelope kept
    expect(c.a2a?.envelope).toBeTruthy();
  });
});
