// Reactive project state (Svelte 5 runes). One store, imported as a
// singleton -- the studio is a single-document app, there's no multi-project
// switching yet.

import { api, ApiError, type InfoResponse, type StatusResponse } from "./api";
import { Transport } from "./transport";
import {
  DEFAULT_RENDER_PARAMS,
  defaultLanes,
  nextId,
  toLatentOffset,
  type Clip,
  type Lane,
  type LaneId,
} from "./types";

class ProjectStore {
  lanes = $state<Lane[]>(defaultLanes());
  clips = $state<Clip[]>([]);
  selectedClipId = $state<string | null>(null);
  playheadSec = $state(0);
  playing = $state(false);

  serverInfo = $state<InfoResponse | null>(null);
  serverStatus = $state<StatusResponse | null>(null);
  serverError = $state<string | null>(null);

  availableCrops = $state<string[]>([]);

  readonly transport = new Transport();
  private rafHandle: number | null = null;
  private statusPoll: ReturnType<typeof setInterval> | null = null;

  constructor() {
    this.transport.onEnded = () => {
      this.playing = false;
      this.stopPlayheadLoop();
    };
  }

  get selectedClip(): Clip | undefined {
    return this.clips.find((c) => c.id === this.selectedClipId);
  }

  // ---------------------------------------------------------------- server

  async connect() {
    try {
      const [info, status, crops] = await Promise.all([api.info(), api.status(), api.crops()]);
      this.serverInfo = info;
      this.serverStatus = status;
      this.availableCrops = crops;
      this.serverError = null;
    } catch (e) {
      this.serverError = e instanceof Error ? e.message : String(e);
    }
    if (!this.statusPoll) {
      this.statusPoll = setInterval(async () => {
        try {
          this.serverStatus = await api.status();
          this.serverError = null;
        } catch (e) {
          this.serverError = e instanceof Error ? e.message : String(e);
        }
      }, 3000);
    }
  }

  disconnect() {
    if (this.statusPoll) {
      clearInterval(this.statusPoll);
      this.statusPoll = null;
    }
  }

  // ---------------------------------------------------------------- clips

  addClipFromFile(file: File, laneId: LaneId, startSec: number, durationSec: number): Clip {
    const url = URL.createObjectURL(file);
    const clip: Clip = {
      id: nextId("clip"),
      laneId,
      startSec,
      durationSec,
      source: { kind: "audio-file", name: file.name, url },
      latentState: "none",
      previewUrl: url,
      render: { ...DEFAULT_RENDER_PARAMS },
    };
    this.clips.push(clip);
    return clip;
  }

  /** Drop a server-known latent crop onto the timeline. Preview comes from
   * GET /decode?crop_id=... (a fresh chunked decode, not cached) until the
   * clip is moved -- see PLAN_CORRECTIONS §5b and types.ts's LatentState doc. */
  async addClipFromCrop(cropId: string, laneId: LaneId, startSec: number): Promise<Clip> {
    const meta = await api.cropMeta(cropId);
    const durationSec = (meta.end_sample - meta.start_sample) / 44100;
    const clip: Clip = {
      id: nextId("clip"),
      laneId,
      startSec,
      durationSec,
      source: { kind: "crop", cropId },
      latentState: "valid",
      encodedAt: toLatentOffset(startSec),
      previewUrl: api.decodePreviewUrl(cropId),
      render: { ...DEFAULT_RENDER_PARAMS },
    };
    this.clips.push(clip);
    return clip;
  }

  removeClip(id: string) {
    const clip = this.clips.find((c) => c.id === id);
    if (clip?.previewUrl) this.transport.invalidate(clip.previewUrl);
    this.clips = this.clips.filter((c) => c.id !== id);
    if (this.selectedClipId === id) this.selectedClipId = null;
  }

  selectClip(id: string | null) {
    this.selectedClipId = id;
  }

  /** Move a clip on the timeline. Audio-domain placement is unconstrained
   * (ORIENTATION.md §3 -- the 92.9ms latent frame does NOT quantise this).
   * A latent-backed clip that moves away from where it was encoded goes
   * `stale`: its preview audio is still valid to *listen* to, but a RENDER
   * is required before that position's latent can be trusted. */
  moveClip(id: string, newStartSec: number) {
    const clip = this.clips.find((c) => c.id === id);
    if (!clip) return;
    clip.startSec = Math.max(0, newStartSec);
    if (clip.latentState === "valid" && clip.encodedAt) {
      const stillAtEncodedOffset =
        toLatentOffset(clip.startSec).frame === clip.encodedAt.frame &&
        toLatentOffset(clip.startSec).residualSamples === clip.encodedAt.residualSamples;
      if (!stillAtEncodedOffset) clip.latentState = "stale";
    }
  }

  moveClipToLane(id: string, laneId: LaneId) {
    const clip = this.clips.find((c) => c.id === id);
    if (clip) clip.laneId = laneId;
  }

  // ---------------------------------------------------------------- render

  /** RENDER commits: runs the real server-side op for one clip and swaps its
   * preview audio for the committed result. This is the ONLY path that talks
   * to /generate or /decode -- everything else in the app stays audio-domain. */
  async renderClip(id: string): Promise<void> {
    const clip = this.clips.find((c) => c.id === id);
    if (!clip) return;
    clip.pendingJobId = "pending";
    const oldPreview = clip.previewUrl;
    try {
      const hasPrompt = clip.render.prompt.trim().length > 0;
      const job = hasPrompt
        ? await api.generate({
            prompt: clip.render.prompt,
            negative_prompt: clip.render.negativePrompt,
            duration: clip.durationSec,
            steps: clip.render.steps,
            cfg_scale: clip.render.cfgScale,
            seed: clip.render.seed,
            sampler_type: clip.render.samplerType,
          })
        : clip.source.kind === "crop"
          ? await api.decodeJob({ crop_id: clip.source.cropId })
          : (() => {
              throw new Error("clip has no prompt and no source crop -- nothing to render");
            })();

      clip.pendingJobId = job.job_id;
      if (job.urls.length) {
        clip.previewUrl = job.urls[0];
        clip.source = { kind: "render", jobId: job.job_id, filename: job.urls[0].split("/").pop()! };
      }
      clip.latentState = job.latents.length ? "valid" : clip.latentState;
      clip.encodedAt = toLatentOffset(clip.startSec);
      if (oldPreview) this.transport.invalidate(oldPreview);
      await this.transport.preload(clip.previewUrl!);
    } catch (e) {
      this.serverError = e instanceof ApiError ? e.message : e instanceof Error ? e.message : String(e);
      throw e;
    } finally {
      clip.pendingJobId = undefined;
    }
  }

  // ---------------------------------------------------------------- transport

  async play() {
    await this.transport.play(this.clips, this.lanes, this.playheadSec);
    this.playing = true;
    this.startPlayheadLoop();
  }

  pause() {
    this.transport.pause();
    this.playing = false;
    this.playheadSec = this.transport.currentTimeSec;
    this.stopPlayheadLoop();
  }

  stop() {
    this.transport.stop();
    this.playing = false;
    this.playheadSec = 0;
    this.stopPlayheadLoop();
  }

  async seek(sec: number) {
    this.playheadSec = Math.max(0, sec);
    if (this.playing) await this.transport.seek(this.playheadSec, this.clips, this.lanes);
  }

  setLaneGain(laneId: LaneId, gain: number) {
    const lane = this.lanes.find((l) => l.id === laneId);
    if (!lane) return;
    lane.gain = gain;
    this.transport.updateLanes(this.lanes);
  }

  toggleMute(laneId: LaneId) {
    const lane = this.lanes.find((l) => l.id === laneId);
    if (!lane) return;
    lane.muted = !lane.muted;
    this.transport.updateLanes(this.lanes);
  }

  toggleSolo(laneId: LaneId) {
    const lane = this.lanes.find((l) => l.id === laneId);
    if (!lane) return;
    lane.solo = !lane.solo;
    this.transport.updateLanes(this.lanes);
  }

  private startPlayheadLoop() {
    const tick = () => {
      if (!this.playing) return;
      this.playheadSec = this.transport.currentTimeSec;
      this.rafHandle = requestAnimationFrame(tick);
    };
    this.rafHandle = requestAnimationFrame(tick);
  }

  private stopPlayheadLoop() {
    if (this.rafHandle !== null) {
      cancelAnimationFrame(this.rafHandle);
      this.rafHandle = null;
    }
  }
}

export const project = new ProjectStore();
