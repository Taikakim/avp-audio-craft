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
import { AUDIO_SOURCE_TIMELINE, registerAudioSource, takeAudio } from "../audio/soloBus";
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
    // 4.5: preview and timeline transports are independent AND mutually exclusive. pause() (not
    // stop()) on this side: the requirement is that they never sound together, and stop() would also
    // rewind the operator's playhead to 0 on every audition (M9 T7, open question 2).
    registerAudioSource(AUDIO_SOURCE_TIMELINE, () => this.pause());
  }

  private snapshotClips() {
    return toPlaybackClips(arrangement.clips);
  }

  private snapshotLanes() {
    return toPlaybackLanes(arrangement.lanes);
  }

  async play() {
    if (this.playing) return;
    takeAudio(AUDIO_SOURCE_TIMELINE);           // 4.5: starting one stops the other
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

  /** I7 fix wave: push a live mute/solo/gain edit to the engine immediately,
   *  even mid-playback. Called via arrangement's externally-attached
   *  `attachLiveLaneUpdater` hook (see arrangement.svelte.ts for why that is
   *  a hook rather than this module being imported the other way around). */
  updateLiveLanes() {
    this.engine.updateLanes(this.snapshotLanes());
  }
}

export const playback = new PlaybackStore();
// I7 fix wave: the v1 store called `this.transport.updateLanes(...)` directly
// from within toggleMute/toggleSolo/setLaneGain; this store's split into two
// singletons means arrangement cannot import playback back (see the long
// comment on arrangement's `onLaneChange` field), so this module attaches
// itself as the live-update hook instead, once, here.
arrangement.attachLiveLaneUpdater(() => playback.updateLiveLanes());
