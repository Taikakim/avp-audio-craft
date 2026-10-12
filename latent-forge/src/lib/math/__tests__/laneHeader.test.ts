import { describe, expect, it } from "vitest";
import type { ForgeClip } from "../../forge/types";
import { bpmTargetClip, laneCountLabel, parseForgeRefPayload } from "../laneHeader";

function clip(over: Partial<ForgeClip>): ForgeClip {
  return {
    id: "c", lane: 0, start_sec: 0, offset_sec: 0, dur_sec: 4, loop: false,
    audio: { kind: "upload", sha256: "abc" }, native_bpm: null, detune_cents: 0,
    downbeats_sec: [], render: {} as never, a2a: null, latentState: "none", history: [],
    ...over,
  } as ForgeClip;
}

describe("laneCountLabel (spec 4.3: 'N clips · latent/audio')", () => {
  it("reads empty with nothing in the lane", () => {
    expect(laneCountLabel([])).toBe("empty lane");
  });

  it("splits by whether a clip is latent-backed", () => {
    const clips = [
      clip({ id: "a", audio: { kind: "crop", crop_id: "1" } }),
      clip({ id: "b", audio: { kind: "upload", sha256: "x" } }),
      clip({ id: "c", audio: { kind: "upload", sha256: "y" }, latentState: "stale" }),
    ];
    expect(laneCountLabel(clips)).toBe("3 clips · 2 latent 1 audio");
  });

  it("uses the singular for exactly one clip", () => {
    expect(laneCountLabel([clip({ id: "a" })])).toBe("1 clip · 1 audio");
  });

  it("omits a zero-count part", () => {
    const clips = [clip({ id: "a", audio: { kind: "crop", crop_id: "1" } })];
    expect(laneCountLabel(clips)).toBe("1 clip · 1 latent");
  });
});

describe("bpmTargetClip (v3 1660-1678: selected clip in this lane, else the lane's first)", () => {
  const inLane = [clip({ id: "a", lane: 2 }), clip({ id: "b", lane: 2 })];

  it("prefers the selection when it is in this lane", () => {
    expect(bpmTargetClip(inLane, inLane[1], 2)?.id).toBe("b");
  });

  it("falls back to the first clip when the selection is in another lane", () => {
    const elsewhere = clip({ id: "z", lane: 0 });
    expect(bpmTargetClip(inLane, elsewhere, 2)?.id).toBe("a");
  });

  it("falls back to the first clip when nothing is selected", () => {
    expect(bpmTargetClip(inLane, undefined, 2)?.id).toBe("a");
  });

  it("is null for an empty lane", () => {
    expect(bpmTargetClip([], undefined, 3)).toBeNull();
  });
});

describe("parseForgeRefPayload (M1 T15's application/x-forge-ref, spec 6.1)", () => {
  it("accepts a ref that validates as an AudioRef", () => {
    expect(parseForgeRefPayload('{"kind":"crop","crop_id":"000412"}')).toEqual({ kind: "crop", crop_id: "000412" });
  });

  it("rejects malformed JSON without throwing", () => {
    expect(parseForgeRefPayload("{not json")).toBeNull();
  });

  it("rejects a ref shape that isAudioRef refuses", () => {
    expect(parseForgeRefPayload('{"kind":"unknown"}')).toBeNull();
  });
});
