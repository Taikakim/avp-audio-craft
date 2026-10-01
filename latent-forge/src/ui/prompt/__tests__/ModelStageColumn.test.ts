// @vitest-environment jsdom
import { cleanup, fireEvent, render, waitFor } from "@testing-library/svelte";
import { tick } from "svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { forgeApi } from "../../../lib/forge/api";
import { BASE_DEFAULTS, cloneRenderSettings } from "../../../lib/forge/defaults";
import type { RenderSettings, Target } from "../../../lib/forge/types";
import { FLAT_PLATEAU_NOTE, POST_CFG_NOTE } from "../../../lib/sampling/scheduleRules";
import { settings, STAGE_BACKBONE } from "../../../lib/stores/settings.svelte";
import ModelStageColumn from "../ModelStageColumn.svelte";

const CLIP: Target = { kind: "clip", id: "c1" };

function fakeSource() {
  const clips: Record<string, RenderSettings> = { c1: cloneRenderSettings(BASE_DEFAULTS) };
  clips.c1.seed = 42; // BASE_DEFAULTS.seed is -1, a server-resolve sentinel outside RANGES.seed
  return { clips, clipSettings: (id: string) => clips[id] ?? null, overlapSettings: () => null };
}

let src: ReturnType<typeof fakeSource>;
beforeEach(() => {
  src = fakeSource();
  settings.attach(src);
  settings.setStage("BASE");
});
afterEach(() => {
  settings.detach();
  settings.stageLocked = false;
  settings.stageRebuilding = false;
  cleanup();
  vi.restoreAllMocks();
});

describe("ModelStageColumn (spec 4.5 item 2)", () => {
  it("shows the target's steps, cfg, seed and the given length", () => {
    const { getByTestId } = render(ModelStageColumn, {
      props: { target: CLIP, length: 30, onLength: () => {} },
    });
    expect((getByTestId("stage-steps") as HTMLInputElement).value).toBe("24");
    expect((getByTestId("stage-cfg") as HTMLInputElement).value).toBe("6");
    expect((getByTestId("stage-seed") as HTMLInputElement).value).toBe("42");
    expect((getByTestId("stage-length") as HTMLInputElement).value).toBe("30");
  });

  it("highlights whichever stage the store is on, and shows no pending confirm until asked", async () => {
    // `beforeEach` sets the stage explicitly (the `settings` singleton is shared across
    // files), so this cannot assert the store's DEFAULT -- Task 1's own suite already pins
    // that. What it proves instead is the thing this component owns: the lit button follows
    // `settings.stage`, in both directions.
    const { getByTestId, queryByTestId } = render(ModelStageColumn, {
      props: { target: CLIP, length: 30, onLength: () => {} },
    });
    expect(getByTestId("stage-base").className).toContain("on");
    expect(getByTestId("stage-post").className).not.toContain("on");
    expect(queryByTestId("stage-confirm")).toBeNull();
    settings.setStage("POST");
    await tick();
    expect(getByTestId("stage-post").className).toContain("on");
    expect(getByTestId("stage-base").className).not.toContain("on");
    expect(queryByTestId("stage-confirm")).toBeNull();
  });

  it("typing a new STEPS value writes it through settings.patch", async () => {
    const { getByTestId } = render(ModelStageColumn, {
      props: { target: CLIP, length: 30, onLength: () => {} },
    });
    await fireEvent.change(getByTestId("stage-steps"), { target: { value: "40" } });
    expect(src.clips.c1.steps).toBe(40);
  });

  it("disables CFG and shows the POST note only while the stage is POST", async () => {
    const { getByTestId, queryByTestId } = render(ModelStageColumn, {
      props: { target: CLIP, length: 30, onLength: () => {} },
    });
    expect((getByTestId("stage-cfg") as HTMLInputElement).disabled).toBe(false);
    expect(queryByTestId("cfg-note")).toBeNull();
    settings.setStage("POST");
    await tick();
    expect((getByTestId("stage-cfg") as HTMLInputElement).disabled).toBe(true);
    expect(getByTestId("cfg-note").textContent).toBe(POST_CFG_NOTE);
  });

  it("typing a new CFG value writes it through settings.patch while BASE", async () => {
    const { getByTestId } = render(ModelStageColumn, {
      props: { target: CLIP, length: 30, onLength: () => {} },
    });
    await fireEvent.change(getByTestId("stage-cfg"), { target: { value: "9.5" } });
    expect(src.clips.c1.cfg_scale).toBe(9.5);
  });

  it("shows the flat-plateau note only when the schedule is flat on an ODE sampler", async () => {
    const first = render(ModelStageColumn, {
      props: { target: CLIP, length: 30, onLength: () => {} },
    });
    expect(first.queryByTestId("flat-warn")).toBeNull();
    first.unmount();
    // Re-render rather than await a tick: this fixture's clips are plain objects, so an in-place
    // patch is not reactive here (M5's real source is $state, where it is). What is under test is
    // the component's rule, which is the same either way.
    settings.patch(CLIP, { sampler_type: "euler" });
    settings.patchSchedule(CLIP, { stepped: true, tilt: 0 });
    const second = render(ModelStageColumn, {
      props: { target: CLIP, length: 30, onLength: () => {} },
    });
    expect(second.getByTestId("flat-warn").textContent).toBe(FLAT_PLATEAU_NOTE);
  });

  it("typing a new SEED value writes it through settings.patch", async () => {
    const { getByTestId } = render(ModelStageColumn, {
      props: { target: CLIP, length: 30, onLength: () => {} },
    });
    await fireEvent.change(getByTestId("stage-seed"), { target: { value: "777" } });
    expect(src.clips.c1.seed).toBe(777);
  });

  it("clicking RND writes a fresh in-range seed", async () => {
    const { getByTestId } = render(ModelStageColumn, {
      props: { target: CLIP, length: 30, onLength: () => {} },
    });
    await fireEvent.click(getByTestId("stage-seed-rnd"));
    expect(Number.isInteger(src.clips.c1.seed)).toBe(true);
    expect(src.clips.c1.seed).toBeGreaterThanOrEqual(0);
    expect(src.clips.c1.seed).toBeLessThanOrEqual(999999);
  });

  it("changing LENGTH calls onLength, never settings.patch", async () => {
    const onLength = vi.fn();
    // RenderSettings DOES have duration_sec, so this assertion is load-bearing:
    // the column must delegate to onLength and leave the store write to the tab
    // (Task 10), which is the single owner. Watching the store's own write path
    // is what pins that -- an assertion on the settings object would not.
    const patch = vi.spyOn(settings, "patch");
    const { getByTestId } = render(ModelStageColumn, {
      props: { target: CLIP, length: 30, onLength },
    });
    await fireEvent.change(getByTestId("stage-length"), { target: { value: "60" } });
    expect(onLength).toHaveBeenCalledWith(60);
    expect(patch).not.toHaveBeenCalled();
  });

  it("clicking the inactive stage button shows the inline confirm; CONTINUE rebuilds then switches stage", async () => {
    const setBackbone = vi.spyOn(forgeApi, "setBackbone").mockResolvedValue({
      ok: true, active: "medium", objective: "rf_denoiser", rebuild_sec: 9.4, warnings: [],
    });
    const { getByTestId } = render(ModelStageColumn, {
      props: { target: CLIP, length: 30, onLength: () => {} },
    });
    await fireEvent.click(getByTestId("stage-post"));
    expect(getByTestId("stage-confirm").textContent).toContain("rebuilds the model — continue?");
    expect(settings.stage).toBe("BASE"); // unchanged until CONTINUE resolves
    await fireEvent.click(getByTestId("stage-confirm-continue"));
    await waitFor(() => expect(settings.stage).toBe("POST"));
    expect(setBackbone).toHaveBeenCalledWith(STAGE_BACKBONE.POST);
  });

  it("CANCEL leaves the stage untouched and calls neither API", async () => {
    const setBackbone = vi.spyOn(forgeApi, "setBackbone");
    const { getByTestId, queryByTestId } = render(ModelStageColumn, {
      props: { target: CLIP, length: 30, onLength: () => {} },
    });
    await fireEvent.click(getByTestId("stage-post"));
    await fireEvent.click(getByTestId("stage-confirm-cancel"));
    expect(queryByTestId("stage-confirm")).toBeNull();
    expect(settings.stage).toBe("BASE");
    expect(setBackbone).not.toHaveBeenCalled();
  });

  it("a failed rebuild shows the error and leaves the stage on the one actually loaded", async () => {
    vi.spyOn(forgeApi, "setBackbone").mockRejectedValue(new Error("render server unreachable"));
    const { getByTestId } = render(ModelStageColumn, {
      props: { target: CLIP, length: 30, onLength: () => {} },
    });
    await fireEvent.click(getByTestId("stage-post"));
    await fireEvent.click(getByTestId("stage-confirm-continue"));
    await waitFor(() => expect(getByTestId("stage-error").textContent).toBe("render server unreachable"));
    expect(settings.stage).toBe("BASE");
  });

  it("offers no switch while settings.stageLocked, and flags stageRebuilding while its own rebuild runs", async () => {
    // M7's SessionController holds stageLocked for a whole session load and refuses to START one
    // while stageRebuilding is set, so a rebuild can never setStage over a load's defaults
    // (reconcile pass 2026-09-25; M7 Open questions 32).
    let finish!: () => void;
    type Rebuilt = Awaited<ReturnType<typeof forgeApi.setBackbone>>;
    const setBackbone = vi.spyOn(forgeApi, "setBackbone").mockReturnValue(new Promise<Rebuilt>((resolve) => {
      finish = () => resolve({ ok: true, active: "medium", objective: "rf_denoiser", rebuild_sec: 9.4, warnings: [] });
    }));
    const { getByTestId, queryByTestId } = render(ModelStageColumn, {
      props: { target: CLIP, length: 30, onLength: () => {} },
    });
    settings.stageLocked = true;
    await tick();
    expect((getByTestId("stage-post") as HTMLButtonElement).disabled).toBe(true);
    await fireEvent.click(getByTestId("stage-post"));
    expect(queryByTestId("stage-confirm")).toBeNull();   // clickStage refuses too, disabled or not
    settings.stageLocked = false;
    await tick();
    await fireEvent.click(getByTestId("stage-post"));
    await fireEvent.click(getByTestId("stage-confirm-continue"));
    expect(settings.stageRebuilding).toBe(true);
    expect(setBackbone).toHaveBeenCalledTimes(1);
    finish();
    await waitFor(() => expect(settings.stage).toBe("POST"));
    expect(settings.stageRebuilding).toBe(false);
  });
});
