// Adapter from the arrangement's ForgeClip/ForgeLane to what Transport plays.
// Kept pure and separate from the store so it is testable without an
// AudioContext: everything here is string/number mapping, no side effects.

import { forgeApi } from "../forge/api";
import type { ForgeClip, ForgeLane } from "../forge/types";
import type { PlaybackClip, PlaybackLane } from "../audio/transport";

export function toPlaybackClips(clips: ForgeClip[]): PlaybackClip[] {
  return clips.map((c) => ({
    id: c.id,
    laneIndex: c.lane,
    startSec: c.start_sec,
    durationSec: c.dur_sec,
    offsetSec: c.offset_sec,
    // /forge/audio serves any AudioRef directly (spec 6.3) -- no upload/analyze
    // round trip needed just to hear it. I2 fix wave: prefer the debounced
    // /forge/stretch result (lib/clips/lifecycle.ts) once one exists -- it is
    // the clip resampled to the project's tempo/detune; the raw `audio` ref is
    // only exactly right when the clip has never needed stretching.
    previewUrl: forgeApi.audioUrl(c.previewAudio ?? c.audio),
  }));
}

export function toPlaybackLanes(lanes: ForgeLane[]): PlaybackLane[] {
  return lanes.map((l) => ({ index: l.index, muted: l.muted, solo: l.solo, gain: l.gain }));
}

/**
 * Spec 4.3's LOOP region toggle: once the playhead reaches the region's end,
 * where should it jump back to? Null means "nowhere" -- either looping is
 * off, the playhead has not reached the end yet, or the region is degenerate.
 */
export function loopWrap(
  sec: number,
  loopOn: boolean,
  loopStartSec: number,
  loopEndSec: number,
): number | null {
  if (!loopOn || loopEndSec <= loopStartSec) return null;
  return sec >= loopEndSec ? loopStartSec : null;
}

/** §9.6's MIXDOWN source. The commit already applied every lane's mute, solo and gain, so replaying
 *  the arrangement's lane state over the finished file would apply them a second time. */
export const MIX_PLAYBACK_LANES: PlaybackLane[] = [{ index: 0, muted: false, solo: false, gain: 1 }];

export function mixPlaybackClips(url: string | null, durSec: number): PlaybackClip[] {
  if (url === null) return [];
  return [{
    id: "mixdown",
    laneIndex: 0,
    startSec: 0,
    durationSec: Math.max(0, durSec),
    offsetSec: 0,
    previewUrl: url,
  }];
}
