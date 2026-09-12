// Reactive project state (Svelte 5 runes). One store, imported as a
// singleton -- the studio is a single-document app, there's no multi-project
// switching yet.

import {
  api,
  ApiError,
  type CkptEntry,
  type InfoResponse,
  type JobResponse,
  type StatusResponse,
} from "./api";
import { circularMeanPhase, meanBpm, secPerBar, shortestPhaseDelta, type Meter, type SnapMode, DEFAULT_METER, snapSec } from "./musictime";
import { Transport } from "./transport";
import { invalidatePeaks, mixdownToBuffer, peakLevel } from "./waveform";
import {
  DEFAULT_RENDER_PARAMS,
  defaultLanes,
  nextId,
  toLatentOffset,
  type Clip,
  type Lane,
  type LaneId,
  type RenderOp,
} from "./types";

/** What a clip is missing before its chosen op can run. null = ready. */
export interface RenderBlock {
  reason: string;
  hint: string;
}

class ProjectStore {
  lanes = $state<Lane[]>(defaultLanes());
  clips = $state<Clip[]>([]);
  selectedClipId = $state<string | null>(null);
  playheadSec = $state(0);
  playing = $state(false);

  // --- view state
  meter = $state<Meter>({ ...DEFAULT_METER });
  snap = $state<SnapMode>("bar");
  pxPerSec = $state(80);

  // --- server state
  serverInfo = $state<InfoResponse | null>(null);
  serverStatus = $state<StatusResponse | null>(null);
  serverError = $state<string | null>(null);
  availableCrops = $state<string[]>([]);
  ckpts = $state<CkptEntry[]>([]);
  presets = $state<string[]>([]);

  // --- master strip
  masterPeakLevel = $state(0);
  masterBuffer = $state<AudioBuffer | null>(null);
  masterStale = $state(true);

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

  get arrangementEndSec(): number {
    return this.clips.reduce((m, c) => Math.max(m, c.startSec + c.durationSec), 0);
  }

  // ---------------------------------------------------------------- server

  async connect() {
    try {
      const [info, status] = await Promise.all([api.info(), api.status()]);
      this.serverInfo = info;
      this.serverStatus = status;
      this.serverError = null;
    } catch (e) {
      this.serverError = e instanceof Error ? e.message : String(e);
    }
    // Crops/ckpts/presets are best-effort: a server can be up and healthy with
    // no player latent_dir configured, and that must not read as "offline".
    void api.crops().then((c) => (this.availableCrops = c)).catch(() => {});
    void api.presets().then((p) => (this.presets = p.presets)).catch(() => {});
    void api.ckpts().then((c) => (this.ckpts = c.ckpts ?? [])).catch(() => {});

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

  get logTail(): string[] {
    return this.serverStatus?.log_tail ?? [];
  }

  // ---------------------------------------------------------------- clips

  addClipFromFile(file: File, laneId: LaneId, startSec: number, durationSec: number): Clip {
    const url = URL.createObjectURL(file);
    const clip: Clip = {
      id: nextId("clip"),
      laneId,
      startSec: Math.max(0, startSec),
      durationSec,
      offsetSec: 0,
      source: { kind: "audio-file", name: file.name, url },
      latentState: "none",
      previewUrl: url,
      render: { ...DEFAULT_RENDER_PARAMS },
    };
    this.clips.push(clip);
    this.markMasterStale();
    return clip;
  }

  /** Drop a server-known latent crop onto the timeline. Preview comes from
   * GET /decode?crop_id=... (a fresh chunked decode, not cached). */
  async addClipFromCrop(cropId: string, laneId: LaneId, startSec: number): Promise<Clip> {
    let durationSec = 45;
    try {
      const meta = await api.cropMeta(cropId);
      durationSec = (meta.end_sample - meta.start_sample) / 44100;
    } catch {
      // No sidecar, or no latent_dir configured -- fall back to a nominal
      // length; the real one lands when the preview buffer decodes.
    }
    const clip: Clip = {
      id: nextId("clip"),
      laneId,
      startSec: Math.max(0, startSec),
      durationSec,
      offsetSec: 0,
      source: { kind: "crop", cropId },
      latentState: "valid",
      encodedAt: toLatentOffset(startSec),
      previewUrl: api.decodePreviewUrl(cropId),
      render: { ...DEFAULT_RENDER_PARAMS, op: "decode" },
    };
    this.clips.push(clip);
    this.markMasterStale();
    return clip;
  }

  /** Correct a clip's length once its audio has actually decoded. */
  setClipDurationFromBuffer(id: string, bufferDurationSec: number) {
    const clip = this.clips.find((c) => c.id === id);
    if (!clip) return;
    const usable = Math.max(0.01, bufferDurationSec - clip.offsetSec);
    if (Math.abs(clip.durationSec - usable) > 0.01) {
      clip.durationSec = usable;
      this.markMasterStale();
    }
  }

  removeClip(id: string) {
    const clip = this.clips.find((c) => c.id === id);
    if (clip?.previewUrl) {
      this.transport.invalidate(clip.previewUrl);
      invalidatePeaks(clip.previewUrl);
    }
    this.clips = this.clips.filter((c) => c.id !== id);
    if (this.selectedClipId === id) this.selectedClipId = null;
    this.markMasterStale();
  }

  duplicateClip(id: string) {
    const clip = this.clips.find((c) => c.id === id);
    if (!clip) return;
    const copy: Clip = {
      ...clip,
      id: nextId("clip"),
      startSec: clip.startSec + clip.durationSec,
      render: { ...clip.render },
      // A latent is only valid where it was encoded, so a copy at a new offset
      // is stale by definition.
      latentState: clip.latentState === "none" ? "none" : "stale",
      pendingJobId: undefined,
    };
    this.clips.push(copy);
    this.selectedClipId = copy.id;
    this.markMasterStale();
  }

  selectClip(id: string | null) {
    this.selectedClipId = id;
  }

  /** Every other clip's start and end, for edge snapping. */
  edgesExcept(clipId: string): number[] {
    const out: number[] = [0];
    for (const c of this.clips) {
      if (c.id === clipId) continue;
      out.push(c.startSec, c.startSec + c.durationSec);
    }
    return out;
  }

  /** Move a clip on the timeline. Audio-domain placement is unconstrained
   * (ORIENTATION.md §3 -- the 92.9ms latent frame does NOT quantise this).
   * A latent-backed clip that moves away from where it was encoded goes
   * `stale`: its preview audio is still valid to listen to, but a RENDER is
   * required before that position's latent can be trusted. */
  moveClip(id: string, newStartSec: number, applySnap = true) {
    const clip = this.clips.find((c) => c.id === id);
    if (!clip) return;
    const target = applySnap
      ? snapSec(newStartSec, this.snap, this.meter, this.edgesExcept(id))
      : Math.max(0, newStartSec);
    if (Math.abs(target - clip.startSec) < 1e-9) return;
    clip.startSec = target;
    this.refreshLatentState(clip);
    this.markMasterStale();
  }

  moveClipToLane(id: string, laneId: LaneId) {
    const clip = this.clips.find((c) => c.id === id);
    if (clip && clip.laneId !== laneId) {
      clip.laneId = laneId;
      this.markMasterStale();
    }
  }

  /** Trim from the head (moves start and offset together) or the tail. */
  trimClip(id: string, edge: "start" | "end", newSec: number) {
    const clip = this.clips.find((c) => c.id === id);
    if (!clip) return;
    const snapped = snapSec(newSec, this.snap, this.meter, this.edgesExcept(id));
    if (edge === "start") {
      const delta = snapped - clip.startSec;
      const newOffset = clip.offsetSec + delta;
      const newDuration = clip.durationSec - delta;
      if (newOffset < 0 || newDuration < 0.05) return;
      clip.startSec = snapped;
      clip.offsetSec = newOffset;
      clip.durationSec = newDuration;
    } else {
      const newDuration = snapped - clip.startSec;
      if (newDuration < 0.05) return;
      clip.durationSec = newDuration;
    }
    this.refreshLatentState(clip);
    this.markMasterStale();
  }

  private refreshLatentState(clip: Clip) {
    if (clip.latentState !== "valid" || !clip.encodedAt) return;
    const now = toLatentOffset(clip.startSec);
    const same = now.frame === clip.encodedAt.frame && now.residualSamples === clip.encodedAt.residualSamples;
    if (!same) clip.latentState = "stale";
  }

  // ------------------------------------------------------- tempo / alignment

  /** MATCH BPM: meet at the mean of the clips' native tempos -- least stretch
   * for all of them. Sets the project tempo only; nothing moves in time. Does
   * NOT itself stretch anything: no time-stretch exists client-side, and the
   * server's stretch lives in the a2a/mix path, so this is the honest half. */
  matchBpm(): number | null {
    const mean = meanBpm(this.clips.map((c) => c.bpm ?? NaN));
    if (mean === null) return null;
    this.meter = { ...this.meter, bpm: Math.round(mean * 10) / 10 };
    return this.meter.bpm;
  }

  /** MATCH DOWNBEATS: shift every clip by the shortest path so its downbeat
   * lands on the common phase (the circular mean). Tempo is left alone. Only
   * clips with a known downbeat participate. */
  matchDownbeats(): number {
    const bar = secPerBar(this.meter);
    const participating = this.clips.filter((c) => c.downbeatSec !== undefined);
    if (participating.length < 2) return 0;
    const phaseOf = (c: Clip) => (((c.startSec + (c.downbeatSec ?? 0)) / bar) % 1 + 1) % 1;
    const mean = circularMeanPhase(participating.map(phaseOf));
    if (mean === null) return 0;
    let moved = 0;
    for (const clip of participating) {
      const delta = shortestPhaseDelta(phaseOf(clip), mean) * bar;
      if (Math.abs(delta) < 1e-6) continue;
      clip.startSec = Math.max(0, clip.startSec + delta);
      this.refreshLatentState(clip);
      moved += 1;
    }
    if (moved) this.markMasterStale();
    return moved;
  }

  // ---------------------------------------------------------------- render

  /**
   * Why this clip's chosen op cannot run yet, or null if it can.
   *
   * This is where the app stays honest: /a2a_track and /a2a_mix resolve
   * `audio_path` with require_path() ON THE SERVER and there is no upload
   * route, so a clip imported from the browser's file picker genuinely cannot
   * be a2a'd until the server can see that file. Rather than let the button
   * fail with a 500, say so up front.
   */
  renderBlock(clip: Clip): RenderBlock | null {
    const r = clip.render;
    switch (r.op) {
      case "generate":
        return r.prompt.trim()
          ? null
          : { reason: "needs a prompt", hint: "/generate requires a non-empty prompt." };
      case "decode":
        if (clip.source.kind === "crop" || clip.latentPath) return null;
        return {
          reason: "no latent to decode",
          hint: "Drop a crop from the library, or run a generate first — /decode takes crop_id or latent_path.",
        };
      case "a2a_track":
        if (!clip.serverPath)
          return {
            reason: "no server-side audio path",
            hint: "/a2a_track resolves audio_path on the server and there is no upload route. Decode or generate this clip first (a job's output path is server-side), or paste the path by hand.",
          };
        return r.prompt.trim() ? null : { reason: "needs a prompt", hint: "/a2a_track requires a prompt." };
      case "a2a_mix":
        if (!clip.serverPath) return { reason: "no server-side A path", hint: "The A side must exist on the server." };
        if (!r.mixBPath?.trim()) return { reason: "no B path", hint: "/a2a_mix needs b_path — a second server-side file." };
        return r.promptRegion?.trim()
          ? null
          : { reason: "needs a region prompt", hint: "/a2a_mix requires prompt_region for the transition." };
      case "longform":
        return r.schedule?.trim()
          ? null
          : { reason: "needs a schedule", hint: "Arc grammar, e.g. 0:opening pad|45:driving bass." };
      case "bend":
        if (!(clip.source.kind === "crop" || clip.latentPath))
          return { reason: "no latent to bend", hint: "/bend takes crop_id or latent_path." };
        return r.bendOps?.length
          ? null
          : { reason: "no bend ops", hint: "Add at least one op — channel_roll, quantize, segment_shuffle…" };
    }
  }

  /** RENDER commits: runs the real server-side op for one clip and swaps its
   * preview audio for the committed result. This is the ONLY path that talks
   * to the job endpoints -- everything else in the app stays audio-domain. */
  async renderClip(id: string): Promise<void> {
    const clip = this.clips.find((c) => c.id === id);
    if (!clip) return;
    const blocked = this.renderBlock(clip);
    if (blocked) throw new Error(`${blocked.reason} — ${blocked.hint}`);

    clip.pendingJobId = "pending";
    const oldPreview = clip.previewUrl;
    try {
      const job = await this.dispatch(clip);
      clip.pendingJobId = job.job_id;
      if (job.urls.length) {
        clip.previewUrl = job.urls[0];
        clip.source = { kind: "render", jobId: job.job_id, filename: job.urls[0].split("/").pop()! };
      }
      // build_response's `files` are ABSOLUTE SERVER PATHS -- this is what
      // makes a rendered clip a2a-able on the next pass.
      if (job.files.length) clip.serverPath = job.files[0];
      if (job.latents.length) {
        clip.latentPath = job.latents[0];
        clip.latentState = "valid";
      }
      clip.encodedAt = toLatentOffset(clip.startSec);
      clip.lastRenderNote =
        `${clip.render.op} · ${job.timings.total_sec}s` +
        (job.seed !== null ? ` · seed ${job.seed}` : "") +
        (job.warnings.length ? ` · ${job.warnings.length} warning(s)` : "");
      if (oldPreview && oldPreview !== clip.previewUrl) {
        this.transport.invalidate(oldPreview);
        invalidatePeaks(oldPreview);
      }
      if (clip.previewUrl) {
        const buf = await this.transport.preload(clip.previewUrl);
        this.setClipDurationFromBuffer(clip.id, buf.duration);
      }
      this.markMasterStale();
    } catch (e) {
      this.serverError = e instanceof ApiError ? e.message : e instanceof Error ? e.message : String(e);
      throw e;
    } finally {
      clip.pendingJobId = undefined;
    }
  }

  private dispatch(clip: Clip): Promise<JobResponse> {
    const r = clip.render;
    const common = { steps: r.steps, cfg_scale: r.cfgScale, seed: r.seed };
    switch (r.op) {
      case "generate":
        return api.generate({
          ...common,
          prompt: r.prompt,
          negative_prompt: r.negativePrompt || undefined,
          duration: clip.durationSec,
          sampler_type: r.samplerType || undefined,
        });
      case "decode":
        return api.decodeJob(
          clip.source.kind === "crop" ? { crop_id: clip.source.cropId } : { latent_path: clip.latentPath! },
        );
      case "a2a_track":
        return api.a2aTrack({
          ...common,
          audio_path: clip.serverPath!,
          prompt: r.prompt,
          noise_level: r.noiseLevel,
          apg_scale: r.apgScale,
        });
      case "a2a_mix":
        return api.a2aMix({
          ...common,
          a_path: clip.serverPath!,
          b_path: r.mixBPath!,
          prompt_region: r.promptRegion!,
          noise_level: r.noiseLevel,
        });
      case "longform":
        return api.longform({
          ...common,
          schedule: r.schedule!,
          duration: clip.durationSec,
          audio_path: clip.serverPath,
          window_sec: r.windowSec,
          overlap_sec: r.overlapSec,
          xfade_sec: r.xfadeSec,
          noise_level: r.noiseLevel,
        });
      case "bend":
        return api.bend({
          ops: r.bendOps!,
          seed: r.seed,
          ...(clip.source.kind === "crop" ? { crop_id: clip.source.cropId } : { latent_path: clip.latentPath! }),
        });
    }
  }

  setRenderOp(id: string, op: RenderOp) {
    const clip = this.clips.find((c) => c.id === id);
    if (!clip) return;
    clip.render.op = op;
    if (op === "bend" && !clip.render.bendOps?.length) {
      clip.render.bendOps = [{ op: "channel_roll", k: 16, shift: 32 }];
    }
  }

  // ---------------------------------------------------------------- master

  markMasterStale() {
    this.masterStale = true;
  }

  /** Render the arrangement offline to get a real master waveform. Audio-domain
   * only: this is the preview mix, explicitly NOT the eventual output. */
  async renderMasterPreview(): Promise<void> {
    const anySolo = this.lanes.some((l) => l.solo);
    const parts: { buffer: AudioBuffer; startSec: number; gain: number }[] = [];
    for (const clip of this.clips) {
      if (!clip.previewUrl) continue;
      const lane = this.lanes.find((l) => l.id === clip.laneId);
      const audible = lane ? (anySolo ? lane.solo : !lane.muted) : true;
      if (!audible) continue;
      try {
        const buf = await this.transport.preload(clip.previewUrl);
        parts.push({ buffer: buf, startSec: clip.startSec, gain: lane?.gain ?? 1 });
      } catch {
        // A clip whose audio can't be fetched just doesn't appear in the
        // master preview; the timeline still shows it.
      }
    }
    const mixed = await mixdownToBuffer(parts, this.transport.ctx.sampleRate);
    this.masterBuffer = mixed;
    this.masterPeakLevel = mixed ? peakLevel(mixed) : 0;
    this.masterStale = false;
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

  async togglePlay() {
    if (this.playing) this.pause();
    else await this.play();
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
    this.markMasterStale();
  }

  toggleMute(laneId: LaneId) {
    const lane = this.lanes.find((l) => l.id === laneId);
    if (!lane) return;
    lane.muted = !lane.muted;
    this.transport.updateLanes(this.lanes);
    this.markMasterStale();
  }

  toggleSolo(laneId: LaneId) {
    const lane = this.lanes.find((l) => l.id === laneId);
    if (!lane) return;
    lane.solo = !lane.solo;
    this.transport.updateLanes(this.lanes);
    this.markMasterStale();
  }

  zoomBy(factor: number) {
    this.pxPerSec = Math.max(4, Math.min(600, this.pxPerSec * factor));
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

  // ---------------------------------------------------------------- persistence

  /**
   * Serialise the arrangement. Clips imported from the browser's file picker
   * are backed by blob: URLs that die with the page, so they are saved WITHOUT
   * a preview and flagged on load -- honest beats a project that silently
   * loads with missing audio.
   */
  toJSON(): string {
    return JSON.stringify(
      {
        version: 1,
        meter: this.meter,
        snap: this.snap,
        pxPerSec: this.pxPerSec,
        lanes: this.lanes,
        clips: this.clips.map((c) => ({
          ...c,
          previewUrl: c.source.kind === "audio-file" ? undefined : c.previewUrl,
          pendingJobId: undefined,
        })),
      },
      null,
      2,
    );
  }

  loadJSON(text: string): { relinkNeeded: number } {
    const data = JSON.parse(text);
    if (data.version !== 1) throw new Error(`unsupported project version ${data.version}`);
    this.transport.stop();
    this.meter = data.meter ?? { ...DEFAULT_METER };
    this.snap = data.snap ?? "bar";
    this.pxPerSec = data.pxPerSec ?? 80;
    this.lanes = data.lanes ?? defaultLanes();
    this.clips = (data.clips ?? []).map((c: Clip) => ({
      ...c,
      // A crop-backed clip can always rebuild its preview URL; a local file cannot.
      previewUrl: c.previewUrl ?? (c.source.kind === "crop" ? api.decodePreviewUrl(c.source.cropId) : undefined),
      render: { ...DEFAULT_RENDER_PARAMS, ...c.render },
    }));
    this.selectedClipId = null;
    this.playheadSec = 0;
    this.markMasterStale();
    return { relinkNeeded: this.clips.filter((c) => !c.previewUrl).length };
  }
}

export const project = new ProjectStore();

// Dev-only handle so the arrangement can be driven from the browser console
// (adding clips, checking transport state) without a render server running.
if (import.meta.env.DEV) {
  (window as unknown as { __sa3: ProjectStore }).__sa3 = project;
}
