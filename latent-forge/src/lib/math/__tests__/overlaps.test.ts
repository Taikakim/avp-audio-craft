import { describe, expect, it } from "vitest";
import type { ForgeClip } from "../../forge/types";
import { findOverlaps, overlapLabel } from "../overlaps";

function clip(over: Partial<ForgeClip>): ForgeClip {
  return {
    id: "c", lane: 0, start_sec: 0, offset_sec: 0, dur_sec: 4, loop: false,
    audio: { kind: "upload", sha256: "x" }, native_bpm: null, detune_cents: 0,
    downbeats_sec: [], render: {} as never, a2a: null, latentState: "none", history: [],
    ...over,
  } as ForgeClip;
}

describe("findOverlaps (v3 1601-1611, ported verbatim from Task 1's derived overlaps)", () => {
  it("finds one overlap between two clips in the same lane", () => {
    const a = clip({ id: "a", lane: 0, start_sec: 0, dur_sec: 8 });
    const b = clip({ id: "b", lane: 0, start_sec: 6, dur_sec: 8 });
    const out = findOverlaps([a, b]);
    expect(out).toHaveLength(1);
    expect(out[0]).toMatchObject({ lane: 0, start_sec: 6, end_sec: 8, a_id: "a", b_id: "b" });
    expect(out[0].key).toBe("a-b");
  });

  it("does not pair clips in different lanes", () => {
    const a = clip({ id: "a", lane: 0, start_sec: 0, dur_sec: 8 });
    const b = clip({ id: "b", lane: 1, start_sec: 6, dur_sec: 8 });
    expect(findOverlaps([a, b])).toEqual([]);
  });

  it("is empty when clips in a lane do not touch", () => {
    const a = clip({ id: "a", lane: 0, start_sec: 0, dur_sec: 4 });
    const b = clip({ id: "b", lane: 0, start_sec: 10, dur_sec: 4 });
    expect(findOverlaps([a, b])).toEqual([]);
  });

  it("finds every adjacent pair when three clips chain together", () => {
    const a = clip({ id: "a", lane: 0, start_sec: 0, dur_sec: 6 });
    const b = clip({ id: "b", lane: 0, start_sec: 4, dur_sec: 6 });
    const c = clip({ id: "c", lane: 0, start_sec: 8, dur_sec: 6 });
    const out = findOverlaps([a, b, c]);
    expect(out.map((o) => o.key)).toEqual(["a-b", "b-c"]);
  });

  it("finds a non-adjacent pair too (ALL pairs per lane, not just index-adjacent " +
     "ones) -- a clip spanning two later, mutually non-overlapping clips finds BOTH", () => {
    // a spans the whole lane (0-20s) and genuinely overlaps both b (2-4s) and
    // c (10-12s); b and c do not overlap each other. The scan is over every
    // (i,j) pair with i<j in start-sorted order, not just adjacent indices --
    // Task 1 deliberately widened it past the legacy drawing's adjacency-only
    // `_overlaps()` for exactly this case (see arrangement.svelte.ts's own
    // comment and its "finds a non-adjacent pair" test) -- so (a,c) IS found
    // here, verified against that store code, not reverted to the old bug.
    const a = clip({ id: "a", lane: 0, start_sec: 0, dur_sec: 20 });
    const b = clip({ id: "b", lane: 0, start_sec: 2, dur_sec: 2 });
    const c = clip({ id: "c", lane: 0, start_sec: 10, dur_sec: 2 });
    const out = findOverlaps([a, b, c]);
    expect(out.map((o) => o.key)).toEqual(["a-b", "a-c"]);
  });
});

describe("overlapLabel (spec 4.3: purple 'INPAINT n.nn bar' label)", () => {
  it("converts the span to bars at the project meter", () => {
    // 120 BPM 4/4: bar = 2s. A 3s span is 1.5 bars.
    expect(overlapLabel(6, 9, 120, 4)).toBe("INPAINT 1.50 bar");
  });

  it("follows a 3/4 meter", () => {
    // 120 BPM 3/4: bar = 1.5s. A 3s span is 2 bars.
    expect(overlapLabel(0, 3, 120, 3)).toBe("INPAINT 2.00 bar");
  });
});
