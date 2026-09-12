// Web Audio playback engine for the timeline.
//
// "THE TIMELINE IS AUDIO" (ORIENTATION.md §3): every clip -- whether it started
// life as an imported audio file, a decoded latent crop, or a committed
// RENDER's output -- has a `previewUrl` that resolves to playable audio, and
// that is ALL this engine ever schedules. It never touches a latent directly;
// that stays server-side, behind RENDER.
//
// Multi-clip, multi-lane scheduling via native AudioBufferSourceNodes rather
// than <audio> elements: <audio> can't be sample-accurately scheduled to start
// at an arbitrary future AudioContext time, which is required once more than
// one clip can overlap on a lane or clips must line up across lanes.

import type { Clip, Lane, LaneId } from "./types";

interface ScheduledSource {
  node: AudioBufferSourceNode;
  clipId: string;
}

export class Transport {
  readonly ctx: AudioContext;
  private masterGain: GainNode;
  private laneGains = new Map<LaneId, GainNode>();
  private bufferCache = new Map<string, AudioBuffer>(); // keyed by previewUrl
  private inFlight = new Map<string, Promise<AudioBuffer>>();
  private scheduled: ScheduledSource[] = [];
  private endTimer: ReturnType<typeof setTimeout> | null = null;
  private playStartedAtCtxTime = 0; // ctx.currentTime when playback began
  private playStartedAtTimelineSec = 0; // timeline position that corresponds to it
  private _playing = false;

  onEnded?: () => void;

  constructor() {
    this.ctx = new AudioContext();
    this.masterGain = this.ctx.createGain();
    this.masterGain.connect(this.ctx.destination);
  }

  private laneGain(laneId: LaneId): GainNode {
    let g = this.laneGains.get(laneId);
    if (!g) {
      g = this.ctx.createGain();
      g.connect(this.masterGain);
      this.laneGains.set(laneId, g);
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

  private applyLaneGain(lane: Lane, anySolo: boolean) {
    const g = this.laneGain(lane.id);
    const audible = anySolo ? lane.solo : !lane.muted;
    g.gain.setValueAtTime(audible ? lane.gain : 0, this.ctx.currentTime);
  }

  /** Update lane gain/mute/solo live, without restarting playback. */
  updateLanes(lanes: Lane[]) {
    const anySolo = lanes.some((l) => l.solo);
    for (const lane of lanes) this.applyLaneGain(lane, anySolo);
  }

  /**
   * Start playback from `fromSec` on the timeline. Preloads any clip buffers
   * not already cached, then schedules every clip that overlaps
   * [fromSec, +inf) to start at its correct offset into the AudioContext
   * clock. Clips already in progress at `fromSec` start mid-buffer.
   */
  async play(clips: Clip[], lanes: Lane[], fromSec: number) {
    this.stop();
    if (this.ctx.state === "suspended") await this.ctx.resume();

    const withPreview = clips.filter((c): c is Clip & { previewUrl: string } => !!c.previewUrl);
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
      const lane = lanes.find((l) => l.id === clip.laneId);
      node.connect(lane ? this.laneGain(lane.id) : this.masterGain);

      const offsetIntoClip = Math.max(0, fromSec - clip.startSec);
      const whenToStart = ctxStart + Math.max(0, clip.startSec - fromSec);
      const durationRemaining = clip.durationSec - offsetIntoClip;
      node.start(whenToStart, offsetIntoClip, durationRemaining);
      this.scheduled.push({ node, clipId: clip.id });
      latestEnd = Math.max(latestEnd, clipEnd);
    }

    this.playStartedAtCtxTime = ctxStart;
    this.playStartedAtTimelineSec = fromSec;
    this._playing = true;

    // Fire onEnded once the last-scheduled clip finishes, so the UI can stop
    // the playhead instead of free-running past the arrangement.
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
  async seek(sec: number, clips: Clip[], lanes: Lane[]) {
    const wasPlaying = this._playing;
    this.stop();
    this.playStartedAtTimelineSec = Math.max(0, sec);
    if (wasPlaying) await this.play(clips, lanes, this.playStartedAtTimelineSec);
  }
}
