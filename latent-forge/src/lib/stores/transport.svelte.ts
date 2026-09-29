// Playhead and transport state. Separate from arrangement.svelte.ts (Task 1)
// because play/pause/where-the-playhead-is is runtime state, not committed
// arrangement data -- Task 1's Interfaces line has no playhead field, and it
// shouldn't: two different concerns, two stores.
//
// The engine is injected (defaults to a real Transport) so this store is
// testable without an AudioContext, which jsdom does not provide. It owns no
// timer: Ruler.svelte runs a requestAnimationFrame loop that calls
// `syncPlayhead()` every frame while mounted, so this file has nothing that
// needs `vi.useFakeTimers()` gymnastics to test.

import { toPlaybackClips, toPlaybackLanes, loopWrap } from "../math/playback";
import { Transport, type PlaybackEngine } from "../audio/transport";
import { arrangement } from "./arrangement.svelte";

export class PlaybackStore {
  playheadSec = $state(0);
  playing = $state(false);
  loopOn = $state(false);
  loopStartSec = $state(0);
  loopEndSec = $state(0);

  constructor(private engine: PlaybackEngine = new Transport()) {
    this.engine.onEnded = () => {
      this.playing = false;
    };
  }

  private snapshotClips() {
    return toPlaybackClips(arrangement.clips);
  }

  private snapshotLanes() {
    return toPlaybackLanes(arrangement.lanes);
  }

  async play() {
    if (this.playing) return;
    await this.engine.play(this.snapshotClips(), this.snapshotLanes(), this.playheadSec);
    this.playing = true;
  }

  pause() {
    if (!this.playing) return;
    this.playheadSec = this.engine.currentTimeSec;
    this.engine.pause();
    this.playing = false;
  }

  stop() {
    this.engine.stop();
    this.playing = false;
    this.playheadSec = this.loopOn ? this.loopStartSec : 0;
  }

  async togglePlay() {
    if (this.playing) this.pause();
    else await this.play();
  }

  async seek(sec: number) {
    const clamped = Math.max(0, sec);
    this.playheadSec = clamped;
    if (this.playing) {
      await this.engine.seek(clamped, this.snapshotClips(), this.snapshotLanes());
    }
  }

  toggleLoop() {
    this.loopOn = !this.loopOn;
  }

  /** Bounds are ordered regardless of which edge the caller dragged. */
  setLoopRegion(startSec: number, endSec: number) {
    this.loopStartSec = Math.max(0, Math.min(startSec, endSec));
    this.loopEndSec = Math.max(startSec, endSec);
  }

  /** Pull the engine's clock into the reactive playhead; called once per animation frame. */
  syncPlayhead() {
    if (!this.playing) return;
    this.playheadSec = this.engine.currentTimeSec;
    const wrap = loopWrap(this.playheadSec, this.loopOn, this.loopStartSec, this.loopEndSec);
    if (wrap !== null) void this.seek(wrap);
  }

  preload(url: string) {
    return this.engine.preload(url);
  }

  async scrubClip(url: string, atSec: number) {
    const buffer = await this.engine.preload(url);
    this.engine.scrub(buffer, atSec);
  }

  stopScrub() {
    this.engine.stopScrub();
  }
}

export const playback = new PlaybackStore();
