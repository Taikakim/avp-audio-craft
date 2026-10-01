// @vitest-environment jsdom
import { render } from "@testing-library/svelte";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { arrangement } from "../../../lib/stores/arrangement.svelte";
import { history } from "../../../lib/render/history.svelte";
import { jobs } from "../../../lib/render/jobs.svelte";
import * as mixdownModule from "../../../lib/render/mixdown.svelte";
import MixdownSlot from "../MixdownSlot.svelte";

const REF = { kind: "upload", sha256: "a".repeat(64) } as const;

function mixEntry() {
  return { job_id: "mix-1", forge_job_id: "forge-1", file: "mix.wav", label: "MIX 12:00:00", kind: "mix" as const, dur_sec: 40, source_clip_id: null, created: 1 };
}

beforeEach(() => {
  arrangement.clips.splice(0, arrangement.clips.length);
  history.clear();
  jobs.active = null;
  jobs.gpuBusyOther = null;
  vi.restoreAllMocks();
});

describe("MixdownSlot, wired (spec §4.2, §7.1)", () => {
  it("reads ▸ MIXDOWN idle and SAMPLING · N steps left while a commit runs", async () => {
    const { getByTestId, rerender } = render(MixdownSlot, { props: { busy: false, stepsLeft: null } });
    expect(getByTestId("mixdown-button").textContent?.trim()).toBe("▸ MIXDOWN");
    await rerender({ busy: true, stepsLeft: 44 });
    expect(getByTestId("mixdown-button").textContent?.trim()).toBe("SAMPLING · 44 steps left");
  });

  it("is disabled with the block reason as its title on an empty arrangement", () => {
    const { getByTestId } = render(MixdownSlot, { props: {} });
    const button = getByTestId("mixdown-button") as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    expect(button.title).toBe("nothing to commit — the arrangement has no clips");
  });

  it("runs the shared commit action on click once there is something to commit", async () => {
    arrangement.addClip({ lane: 0, startSec: 0, durSec: 8, audio: REF, nativeBpm: 120 });
    const run = vi.spyOn(mixdownModule, "runMixdown").mockResolvedValue(undefined);
    const { getByTestId } = render(MixdownSlot, { props: {} });
    (getByTestId("mixdown-button") as HTMLButtonElement).click();
    expect(run).toHaveBeenCalledTimes(1);
  });

  it("is draggable only with a mix in the slot, and drags the render AudioRef", () => {
    const { getByTestId, rerender } = render(MixdownSlot, { props: {} });
    const canvas = getByTestId("mixdown-canvas") as HTMLCanvasElement;
    expect(canvas.draggable).toBe(false);
    history.add(mixEntry());
    return rerender({}).then(() => {
      expect(canvas.draggable).toBe(true);
      const data: Record<string, string> = {};
      canvas.dispatchEvent(Object.assign(new Event("dragstart", { bubbles: true }), {
        dataTransfer: { setData: (k: string, v: string) => { data[k] = v; }, effectAllowed: "" },
      }));
      expect(JSON.parse(data["application/x-forge-ref"])).toEqual({ kind: "render", job_id: "mix-1", file: "mix.wav" });
    });
  });

  it("play and the canvas stay disabled until a mix exists", async () => {
    const { getByTestId, rerender } = render(MixdownSlot, { props: {} });
    expect((getByTestId("mixdown-play") as HTMLButtonElement).disabled).toBe(true);
    history.add(mixEntry());
    await rerender({});
    expect((getByTestId("mixdown-play") as HTMLButtonElement).disabled).toBe(false);
  });
});
