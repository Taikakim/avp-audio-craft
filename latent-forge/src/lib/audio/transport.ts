// Web Audio playback engine for the timeline.
//
// "THE TIMELINE IS AUDIO" (ORIENTATION.md §3): every clip's audio is resolved
// to a URL and scheduled as a plain buffer; nothing here ever touches a
// latent. Multi-clip, multi-lane scheduling via native AudioBufferSourceNodes
// rather than <audio> elements: <audio> can't be sample-accurately scheduled
// to start at an arbitrary future AudioContext time.
//
// Decoupled from any particular clip/lane model (M5 T3, 2026-09-17): this
// shipped importing the v1 app's `Clip`/`Lane` from "./types"; M5's
// ForgeClip/ForgeLane replaced that model, so the engine now speaks two small
// structural interfaces instead of a specific milestone's data shape.

export interface PlaybackClip {
  id: string;
  laneIndex: number;
  startSec: number;
  durationSec: number;
  offsetSec: number;
  previewUrl: string | null;
}

export interface PlaybackLane {
  index: number;
  muted: boolean;
  solo: boolean;
  gain: number;
}

/**
 * The public surface `lib/stores/transport.svelte.ts` depends on, so its
 * tests can inject a fake in place of a real AudioContext (jsdom has none).
 * `scrub`/`stopScrub` are declared here (Task 3) and given real bodies in
 * Task 6, so the interface never has to widen again once clip-audition lands.
 */
export interface PlaybackEngine {
  play(clips: PlaybackClip[], lanes: PlaybackLane[], fromSec: number): Promise<void>;
  pause(): void;
  stop(): void;
  seek(sec: number, clips: PlaybackClip[], lanes: PlaybackLane[]): Promise<void>;
  preload(url: string): Promise<AudioBuffer>;
  invalidate(url: string): void;
  scrub(buffer: AudioBuffer, atSec: number, windowSec?: number): void;
  stopScrub(): void;
  readonly currentTimeSec: number;
  readonly playing: boolean;
  onEnded?: () => void;
}

interface ScheduledSource {
  node: AudioBufferSourceNode;
  clipId: string;
}

export class Transport implements PlaybackEngine {
  readonly ctx: AudioContext;
  private masterGain: GainNode;
  private laneGains = new Map<number, GainNode>();
  private bufferCache = new Map<string, AudioBuffer>(); // keyed by previewUrl
  private inFlight = new Map<string, Promise<AudioBuffer>>();
  private scheduled: ScheduledSource[] = [];
  private endTimer: ReturnType<typeof setTimeout> | null = null;
  private scrubNode: AudioBufferSourceNode | null = null;
  private playStartedAtCtxTime = 0; // ctx.currentTime when playback began
  private playStartedAtTimelineSec = 0; // timeline position that corresponds to it
  private _playing = false;

  onEnded?: () => void;

  constructor() {
    this.ctx = new AudioContext();
    this.masterGain = this.ctx.createGain();
    this.masterGain.connect(this.ctx.destination);
  }

  private laneGain(laneIndex: number): GainNode {
    let g = this.laneGains.get(laneIndex);
    if (!g) {
      g = this.ctx.createGain();
      g.connect(this.masterGain);
      this.laneGains.set(laneIndex, g);
    }
    return g;
  }

  /** Fetch + decode a clip's preview audio, cached by URL. Safe to call repeatedly. */
  async preload(url: string): Promise<AudioBuffer> {
    const cached = this.bufferCache.get(url);
    if (cached) return cached;
    const inFlight = this.inFlight.get(url);
    if (inFlight) return inFlight;
    const p = (async () => {
      const res = await fetch(url);
      if (!res.ok) throw new Error(`fetch ${url} failed: ${res.status}`);
      const arr = await res.arrayBuffer();
      const buf = await this.ctx.decodeAudioData(arr);
      this.bufferCache.set(url, buf);
      this.inFlight.delete(url);
      return buf;
    })();
    this.inFlight.set(url, p);
    return p;
  }

  /** Drop a cached buffer -- call when a clip's previewUrl changes (re-render, re-encode). */
  invalidate(url: string) {
    this.bufferCache.delete(url);
  }

  get playing() {
    return this._playing;
  }

  /** Current playhead position in timeline seconds. */
  get currentTimeSec(): number {
    if (!this._playing) return this.playStartedAtTimelineSec;
    return this.playStartedAtTimelineSec + (this.ctx.currentTime - this.playStartedAtCtxTime);
  }

  private applyLaneGain(lane: PlaybackLane, anySolo: boolean) {
    const g = this.laneGain(lane.index);
    const audible = anySolo ? lane.solo : !lane.muted;
    g.gain.setValueAtTime(audible ? lane.gain : 0, this.ctx.currentTime);
  }

  /** Update lane gain/mute/solo live, without restarting playback. */
  updateLanes(lanes: PlaybackLane[]) {
    const anySolo = lanes.some((l) => l.solo);
    for (const lane of lanes) this.applyLaneGain(lane, anySolo);
  }

  /**
   * Start playback from `fromSec` on the timeline. Preloads any clip buffers
   * not already cached, then schedules every clip that overlaps
   * [fromSec, +inf) to start at its correct offset into the AudioContext
   * clock. Clips already in progress at `fromSec` start mid-buffer.
   */
  async play(clips: PlaybackClip[], lanes: PlaybackLane[], fromSec: number) {
    this.stop();
    if (this.ctx.state === "suspended") await this.ctx.resume();

    const withPreview = clips.filter((c): c is PlaybackClip & { previewUrl: string } => !!c.previewUrl);
    await Promise.all(withPreview.map((c) => this.preload(c.previewUrl)));

    const anySolo = lanes.some((l) => l.solo);
    for (const lane of lanes) this.applyLaneGain(lane, anySolo);

    const ctxStart = this.ctx.currentTime + 0.05; // small lead-in so scheduling never races the clock
    let latestEnd = fromSec;

    for (const clip of withPreview) {
      const clipEnd = clip.startSec + clip.durationSec;
      if (clipEnd <= fromSec) continue; // fully in the past
      const buf = this.bufferCache.get(clip.previewUrl);
      if (!buf) continue; // decode failed silently upstream; skip rather than throw mid-transport

      const node = this.ctx.createBufferSource();
      node.buffer = buf;
      const lane = lanes.find((l) => l.index === clip.laneIndex);
      node.connect(lane ? this.laneGain(lane.index) : this.masterGain);

      const intoClip = Math.max(0, fromSec - clip.startSec);
      const offsetIntoBuffer = clip.offsetSec + intoClip;
      const whenToStart = ctxStart + Math.max(0, clip.startSec - fromSec);
      const durationRemaining = Math.min(
        clip.durationSec - intoClip,
        Math.max(0, buf.duration - offsetIntoBuffer),
      );
      if (durationRemaining <= 0) continue;
      node.start(whenToStart, offsetIntoBuffer, durationRemaining);
      this.scheduled.push({ node, clipId: clip.id });
      latestEnd = Math.max(latestEnd, clipEnd);
    }

    this.playStartedAtCtxTime = ctxStart;
    this.playStartedAtTimelineSec = fromSec;
    this._playing = true;

    const tailMs = Math.max(0, (latestEnd - fromSec) * 1000);
    this.endTimer = setTimeout(() => {
      this._playing = false;
      this.playStartedAtTimelineSec = latestEnd;
      this.endTimer = null;
      this.onEnded?.();
    }, tailMs + 60);
  }

  pause() {
    if (!this._playing) return;
    this.playStartedAtTimelineSec = this.currentTimeSec;
    this._playing = false;
    this.clearScheduled();
  }

  stop() {
    this.clearScheduled();
    this._playing = false;
  }

  private clearScheduled() {
    if (this.endTimer !== null) {
      clearTimeout(this.endTimer);
      this.endTimer = null;
    }
    for (const s of this.scheduled) {
      try {
        s.node.stop();
      } catch {
        // already stopped/ended -- fine
      }
    }
    this.scheduled = [];
  }

  /** Jump the playhead. If currently playing, restarts scheduling from the new position. */
  async seek(sec: number, clips: PlaybackClip[], lanes: PlaybackLane[]) {
    const wasPlaying = this._playing;
    this.stop();
    this.playStartedAtTimelineSec = Math.max(0, sec);
    if (wasPlaying) await this.play(clips, lanes, this.playStartedAtTimelineSec);
  }

  /**
   * Audition a short looping grain of `buffer` centred on `atSec` (Task 6:
   * Alt+drag scrub). Independent of the lane transport above -- it does not
   * touch `scheduled` or `_playing`, so scrubbing while stopped, or while the
   * arrangement plays, both just work.
   */
  scrub(buffer: AudioBuffer, atSec: number, windowSec = 0.15) {
    this.stopScrub();
    const half = windowSec / 2;
    const loopStart = Math.max(0, atSec - half);
    const loopEnd = Math.min(buffer.duration, atSec + half);
    if (loopEnd <= loopStart) return;
    const node = this.ctx.createBufferSource();
    node.buffer = buffer;
    node.loop = true;
    node.loopStart = loopStart;
    node.loopEnd = loopEnd;
    node.connect(this.masterGain);
    node.start(this.ctx.currentTime, loopStart);
    this.scrubNode = node;
  }

  stopScrub() {
    if (!this.scrubNode) return;
    try {
      this.scrubNode.stop();
    } catch {
      // already stopped -- fine
    }
    this.scrubNode = null;
  }
}
