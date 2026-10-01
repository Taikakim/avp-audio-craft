import { describe, expect, it } from "vitest";
import { MIX_PLAYBACK_LANES, mixPlaybackClips } from "../playback";

const URL = "/forge/audio?ref=%7B%22kind%22%3A%22render%22%7D";

describe("mixPlaybackClips — one file, from zero, over one audible lane", () => {
  it("is a single clip starting at 0 with no offset", () => {
    expect(mixPlaybackClips(URL, 96)).toEqual([
      { id: "mixdown", laneIndex: 0, startSec: 0, durationSec: 96, offsetSec: 0, previewUrl: URL },
    ]);
  });

  it("is empty without a url — the engine would silently skip it anyway", () => {
    expect(mixPlaybackClips(null, 96)).toEqual([]);
  });

  it("floors a missing or zero duration at 0 rather than emitting a negative clip", () => {
    expect(mixPlaybackClips(URL, 0)[0].durationSec).toBe(0);
    expect(mixPlaybackClips(URL, -5)[0].durationSec).toBe(0);
  });

  it("plays over a synthetic lane, so a muted or un-soloed lane 0 cannot silence the mix", () => {
    expect(MIX_PLAYBACK_LANES).toEqual([{ index: 0, muted: false, solo: false, gain: 1 }]);
  });
});
