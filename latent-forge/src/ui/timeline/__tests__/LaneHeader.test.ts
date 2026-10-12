// @vitest-environment jsdom
//
// I1 fix wave: LaneHeader's drop-to-add-clip-at-playhead used to call
// `arrangement.addClip` directly, bypassing lib/clips/lifecycle.ts's
// upload/analyze/stretch pipeline entirely (Task 10, built and tested, never
// actually wired in) -- a dropped clip's native_bpm/downbeats_sec stayed
// permanently empty. This exercises the real drop handler, through the real
// component, and asserts /forge/analyze is actually called and its result
// lands on the clip -- not just that a clip with a placeholder shape appears.
import { cleanup, render } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { arrangement } from "../../../lib/stores/arrangement.svelte";
import { CHAIN_DEFAULTS } from "../../../lib/forge/defaults";
import type { ForgeLane } from "../../../lib/forge/types";
import LaneHeader from "../LaneHeader.svelte";

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json" } });
}

function lane(index: 0 | 1 | 2 | 3): ForgeLane {
  return { index, name: `LANE ${index + 1}`, muted: false, solo: false, gain: 1, chain: structuredClone(CHAIN_DEFAULTS) };
}

function reset() {
  for (const c of [...arrangement.clips]) arrangement.removeClip(c.id);
}

beforeEach(reset);
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  reset();
});

describe("dropping a ref onto a lane's header slot", () => {
  it("routes through lifecycle.ts: calls /forge/analyze and fills native_bpm/downbeats_sec", async () => {
    const fetchMock = vi.fn(async (url: string) => {
      if (url === "/forge/analyze") {
        return jsonResponse({
          ok: true, bpm: 140, bpm_candidates: [], beats_sec: [], downbeats_sec: [0.2, 1.2],
          duration_sec: 4, source: "librosa",
        });
      }
      throw new Error(`unexpected fetch ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const { getByRole } = render(LaneHeader, { props: { lane: lane(0) } });
    const slot = getByRole("group", { name: /drop target/i });

    const ref = { kind: "crop", crop_id: "abc123" };
    const event = new Event("drop", { bubbles: true, cancelable: true });
    Object.defineProperty(event, "dataTransfer", {
      value: { getData: () => JSON.stringify(ref) },
    });
    slot.dispatchEvent(event);

    // The drop handler is async (it awaits lifecycle's addClip); let its
    // microtasks resolve.
    await new Promise((r) => setTimeout(r, 0));
    await new Promise((r) => setTimeout(r, 0));

    expect(fetchMock).toHaveBeenCalledWith("/forge/analyze", expect.objectContaining({ method: "POST" }));
    expect(arrangement.clips).toHaveLength(1);
    expect(arrangement.clips[0].native_bpm).toBe(140);
    expect(arrangement.clips[0].downbeats_sec).toEqual([0.2, 1.2]);
  });
});
