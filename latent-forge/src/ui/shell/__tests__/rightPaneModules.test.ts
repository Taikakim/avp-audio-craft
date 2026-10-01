// @vitest-environment jsdom
import { cleanup, render, waitFor } from "@testing-library/svelte";
import { tick } from "svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CHAIN_DEFAULTS } from "../../../lib/forge/defaults";
import { arrangement } from "../../../lib/stores/arrangement.svelte";
import { settings } from "../../../lib/stores/settings.svelte";
import { view } from "../../../lib/stores/view.svelte";
import RightPaneModules from "../RightPaneModules.svelte";

// The REAL ModuleShell. Its lit dot is pinned by M1 T9 since the reconcile pass of 2026-09-25:
// [data-module-dot=<id>] carrying data-lit="true"|"false" (Open questions 27). The probe this suite
// used to mock ModuleShell with, because no plan pinned that markup, is gone.
const lit = (container: HTMLElement, id: string) =>
  container.querySelector(`[data-module-dot="${id}"]`)!.getAttribute("data-lit");

const RMS_BASS = { name: "rms_energy_bass", family: "medium", default_gain: 512, health: "ok",
  supports_kinds: ["constant"], slider_min: -35.2, slider_max: -0.13, value_default: -12 };

beforeEach(() => {
  // Every module body fetches on mount (FILES, LANE CHAIN, MASTER CHAIN), and so does this file's
  // own head list; answer all of them with one valid body so nothing rejects on jsdom's relative URLs.
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({
    ok: true, roots: [], files: [], names: [], latch_heads: [RMS_BASS], models: [], slots: [],
  }))));
  arrangement.clips.splice(0, arrangement.clips.length);
});

afterEach(() => {
  cleanup();
  view.clearSelection();
  view.closeModule("overlap");
  view.closeModule("advanced-sampling");
  arrangement.clips.splice(0, arrangement.clips.length);
  for (const lane of arrangement.lanes) lane.chain = structuredClone(CHAIN_DEFAULTS);
  vi.unstubAllGlobals();
});

describe("RightPaneModules after M7 T9", () => {
  it("lights LANE CHAIN's dot from the active lane's live chain, and relights on an in-place edit", async () => {
    view.setActiveLane(0);
    const { container } = render(RightPaneModules);
    expect(lit(container, "lane-chain")).toBe("false");
    arrangement.lanes[0].chain.latch_on = true;   // in place -- Global Constraint #1
    await tick();
    expect(lit(container, "lane-chain")).toBe("true");
    expect(lit(container, "master-chain")).toBe("false");
  });

  it("renders a never-edited overlap's module without seeding it (no state_unsafe_mutation from the lit snapshot or the body)", () => {
    arrangement.addClip({ lane: 0, startSec: 0, durSec: 10, audio: { kind: "crop", crop_id: "A" } });
    arrangement.addClip({ lane: 0, startSec: 6, durSec: 10, audio: { kind: "crop", crop_id: "B" } });
    const [ov] = arrangement.overlaps;
    view.select({ kind: "overlap", key: ov.key });
    view.openModule("overlap");   // mount OverlapInpaint's body too, not just the shell
    const { container, getByTestId } = render(RightPaneModules);
    expect(container.querySelector('[data-module="overlap"]')).not.toBeNull();
    expect(getByTestId("inpaint-overlap-button")).toBeTruthy();
    // still unseeded: two peeks are two different objects (Task 3's own contract)
    expect(arrangement.peekOverlapParams(ov.key)).not.toBe(arrangement.peekOverlapParams(ov.key));
  });

  it("hands ADVANCED SAMPLING only registry-known LatCH slots, so a deleted head does not force Euler", async () => {
    // M4's activeSlots counts any non-"none", non-zero-weight head; chainRequest (T1) sends a head
    // /info does not list as "none" (the server 400s on it). Passing it through would show "euler
    // (forced by LatCH)" for a request that sends no active LatCH slot at all (critic pass 2 #8).
    view.setActiveLane(0);
    const chain = arrangement.lanes[0].chain;
    chain.latch_on = true;
    chain.slots[0] = { head: "deleted_head", kind: "constant", value: 0, weight: 1, start_pct: 0, end_pct: 0.6 };
    view.openModule("advanced-sampling");
    const { findByTestId } = render(RightPaneModules);
    const sampler = (await findByTestId("adv-sampler")) as HTMLSelectElement;   // M4's own testid
    expect(sampler.disabled).toBe(false);
    chain.slots[0].head = "rms_energy_bass";   // a head the registry lists: now it really forces Euler
    await waitFor(() => expect(sampler.disabled).toBe(true));
  });

  it("wires M4 to M5: a selected clip's OWN render lights ADVANCED SAMPLING, and its A2A NOISE reaches σ MAX (reconcile pass, OQ 19/20)", async () => {
    settings.attach(arrangement.settingsSource);   // App.svelte does this once at startup (Step 4)
    try {
      const clip = arrangement.addClip({ lane: 0, startSec: 0, durSec: 4, audio: { kind: "crop", crop_id: "A" } });
      arrangement.ensureA2A(clip.id);
      arrangement.setNoise(clip.id, 0.4);
      view.select({ kind: "clip", id: clip.id });
      view.openModule("advanced-sampling");
      const { container, findByLabelText } = render(RightPaneModules);
      expect(lit(container, "advanced-sampling")).toBe("false");
      // M4 T11: σ MAX mirrors the selected A2A clip's NOISE -- only if `a2a` reaches the module.
      expect(((await findByLabelText("σ MAX")) as HTMLInputElement).value).toBe("0.40");
      const before = settings.defaults.steps;
      clip.render.steps = 40;                      // the CLIP's settings, in place, not session.defaults
      await tick();
      expect(lit(container, "advanced-sampling")).toBe("true");
      expect(settings.defaults.steps).toBe(before);
    } finally {
      settings.detach();
    }
  });
});
