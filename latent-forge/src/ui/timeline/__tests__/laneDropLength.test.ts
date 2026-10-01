// @vitest-environment jsdom
import { cleanup, fireEvent, render, waitFor } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { AudioRef } from "../../../lib/forge/types";
import { FORGE_DUR_MIME, FORGE_REF_MIME } from "../../../lib/math/laneHeader";
import { arrangement } from "../../../lib/stores/arrangement.svelte";
import LaneHeader from "../LaneHeader.svelte";

const REF: AudioRef = { kind: "render", job_id: "gen-7", file: "out_00.wav" };

function dropEvent(data: Record<string, string>) {
  return {
    preventDefault: () => {},
    dataTransfer: { getData: (t: string) => data[t] ?? "", files: [] },
  } as unknown as DragEvent;
}

function analyzeOk(bpm: number | null) {
  return vi.fn(async () => new Response(
    JSON.stringify({
      ok: true, bpm, bpm_candidates: [], beats_sec: [], downbeats_sec: bpm === null ? [] : [0.5],
      duration_sec: 96, source: "librosa",
    }),
    { status: 200, headers: { "content-type": "application/json" } },
  ));
}

beforeEach(() => {
  for (const c of [...arrangement.clips]) arrangement.removeClip(c.id);
  arrangement.setBpm(120);
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("a drop onto a lane gets the render's real length, not M5's four seconds", () => {
  it("lands a clip as long as the dragged render says it is", async () => {
    vi.stubGlobal("fetch", analyzeOk(null));
    const { container } = render(LaneHeader, { props: { lane: arrangement.lanes[0] } });
    const slot = container.querySelector(".header") as HTMLElement;

    await fireEvent(slot, Object.assign(new Event("drop", { bubbles: true }), dropEvent({
      [FORGE_REF_MIME]: JSON.stringify(REF), [FORGE_DUR_MIME]: "96",
    })));

    await waitFor(() => expect(arrangement.clips).toHaveLength(1));
    expect(arrangement.clips[0].dur_sec).toBe(96);
    expect(arrangement.clips[0].audio).toEqual(REF);
  });

  it("runs the analysis the old path skipped, so CLIP BPM is no longer blank", async () => {
    vi.stubGlobal("fetch", analyzeOk(96));
    const { container } = render(LaneHeader, { props: { lane: arrangement.lanes[0] } });
    const slot = container.querySelector(".header") as HTMLElement;

    await fireEvent(slot, Object.assign(new Event("drop", { bubbles: true }), dropEvent({
      [FORGE_REF_MIME]: JSON.stringify(REF), [FORGE_DUR_MIME]: "96",
    })));

    await waitFor(() => expect(arrangement.clips[0]?.native_bpm).toBe(96));
    expect(arrangement.clips[0].downbeats_sec).toEqual([0.5]);
  });

  it("decodes the audio for its length when the drag source did not know one (a FILES row)", async () => {
    vi.stubGlobal("fetch", analyzeOk(null));
    const { container } = render(LaneHeader, { props: { lane: arrangement.lanes[0] } });
    const slot = container.querySelector(".header") as HTMLElement;

    await fireEvent(slot, Object.assign(new Event("drop", { bubbles: true }), dropEvent({
      [FORGE_REF_MIME]: JSON.stringify({ kind: "crop", crop_id: "000412" }),
    })));

    // No AudioContext in vitest, so the decode path returns null and the documented floor applies.
    await waitFor(() => expect(arrangement.clips).toHaveLength(1));
    expect(arrangement.clips[0].dur_sec).toBe(4);
  });

  it("ignores a drop with no forge ref, exactly as M5 did", async () => {
    const { container } = render(LaneHeader, { props: { lane: arrangement.lanes[0] } });
    const slot = container.querySelector(".header") as HTMLElement;
    await fireEvent(slot, Object.assign(new Event("drop", { bubbles: true }), dropEvent({})));
    expect(arrangement.clips).toHaveLength(0);
  });
});
