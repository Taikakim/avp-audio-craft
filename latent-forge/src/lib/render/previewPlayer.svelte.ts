// The preview container's own transport (spec §4.5). NOT M5's `playback`: that one plays the
// arrangement, and §4.5 requires these two to be independent and mutually exclusive.
//
// There is no "play one buffer" engine method to write. M5's Transport already plays a list of
// PlaybackClips, and the preview IS a one-element list -- so currentTimeSec, onEnded, pause, seek,
// scrub and stopScrub all arrive for free and the two transports behave identically.

import { Transport, type PlaybackEngine } from "../audio/transport";
import { AUDIO_SOURCE_PREVIEW, registerAudioSource, takeAudio } from "../audio/soloBus";

const PREVIEW_LANE = { index: 0, muted: false, solo: false, gain: 1 };

export class PreviewPlayerStore {
  playing = $state(false);
  playheadSec = $state(0);
  durationSec = $state(0);
  url = $state<string | null>(null);

  /** `undefined` = not tried yet, `null` = this environment has no Web Audio. M5's own lazy-decoder
   *  pattern: a module-level `new Transport()` would throw at IMPORT time under jsdom and take the
   *  whole graph with it. */
  #engine: PlaybackEngine | null | undefined;

  constructor() {
    registerAudioSource(AUDIO_SOURCE_PREVIEW, () => this.stop());
  }

  /** Test seam, and the one M10 would use to share an engine. */
  useEngine(engine: PlaybackEngine | null): void {
    this.#engine = engine;
    if (engine) engine.onEnded = () => { this.playing = false; };
  }

  engine(): PlaybackEngine | null {
    if (this.#engine === undefined) {
      try {
        const t = new Transport();
        t.onEnded = () => { this.playing = false; };
        this.#engine = t;
      } catch {
        this.#engine = null;
      }
    }
    return this.#engine;
  }

  /** A new previewed render: audio only (§10 X15). Rewinds, because it is different audio. */
  load(url: string, durSec: number): void {
    if (this.url === url) return;
    this.stop();
    this.url = url;
    this.durationSec = durSec;
    this.playheadSec = 0;
  }

  #clips() {
    return [{
      id: "preview", laneIndex: 0, startSec: 0,
      durationSec: this.durationSec, offsetSec: 0, previewUrl: this.url,
    }];
  }

  async play(): Promise<void> {
    const engine = this.engine();
    if (!engine || this.url === null || this.playing) return;
    // §4.5: starting one stops the other. Before the engine starts, so the two never overlap even
    // for the length of an await.
    takeAudio(AUDIO_SOURCE_PREVIEW);
    await engine.play(this.#clips(), [PREVIEW_LANE], this.playheadSec);
    this.playing = true;
  }

  stop(): void {
    const engine = this.#engine;
    if (!engine) return;
    engine.stop();
    engine.stopScrub();
    this.playing = false;
  }

  async toggle(): Promise<void> {
    if (this.playing) this.stop();
    else await this.play();
  }

  async seek(sec: number): Promise<void> {
    const clamped = Math.max(0, Math.min(sec, this.durationSec));
    this.playheadSec = clamped;
    const engine = this.engine();
    if (engine && this.playing) await engine.seek(clamped, this.#clips(), [PREVIEW_LANE]);
  }

  /** Click/drag on the waveform (§4.5). Audible scrub, same gesture as M5's Alt+drag on a clip. */
  async scrubAt(sec: number): Promise<void> {
    await this.seek(sec);
    const engine = this.engine();
    if (!engine || this.url === null || this.playing) return;
    takeAudio(AUDIO_SOURCE_PREVIEW);
    engine.scrub(await engine.preload(this.url), this.playheadSec);
  }

  /** Pulled by the container's rAF loop while playing, exactly as M5's Ruler drives `syncPlayhead`. */
  syncPlayhead(): void {
    const engine = this.#engine;
    if (!engine || !this.playing) return;
    this.playheadSec = engine.currentTimeSec;
  }
}

export const previewPlayer = new PreviewPlayerStore();
