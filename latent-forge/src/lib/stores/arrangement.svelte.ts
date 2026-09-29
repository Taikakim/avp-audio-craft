// The arrangement: what is on the timeline and where. Chrome state (theme, tabs,
// modules, help, selection) stays in view.svelte.ts; the viewport lives HERE
// because every consumer of pxPerSec is a timeline surface (WINTERMUTE,
// 2026-09-16). §9.2 still serialises it under `view: {...}` — that is a storage
// shape, not an ownership claim.

import {
  A2A_ENVELOPE_DEFAULT, BASE_DEFAULTS, CHAIN_DEFAULTS, cloneRenderSettings, OVERLAP_DEFAULT,
} from "../forge/defaults";
import type {
  AudioRef, Envelope, ForgeClip, ForgeLane, OverlapParams,
} from "../forge/types";
import { findOverlaps, type Overlap } from "../math/overlaps";
import type { SnapMode } from "../math/snap";

export const MIN_PX_PER_SEC = 4;
export const MAX_PX_PER_SEC = 600;
export const LANE_COUNT = 4;

/** A derived overlap region; its editable parameters live in `overlapParams`. */
export type { Overlap };

export interface AddClipArgs {
  lane: 0 | 1 | 2 | 3;
  startSec: number;
  durSec: number;
  audio: AudioRef;
  nativeBpm?: number | null;
  downbeatsSec?: number[];
}

let _seq = 0;
function nextId(): string {
  _seq += 1;
  return `clip_${Date.now().toString(36)}_${_seq}`;
}

function defaultLanes(): ForgeLane[] {
  return [0, 1, 2, 3].map((i) => ({
    index: i as 0 | 1 | 2 | 3,
    name: `LANE ${i + 1}`,
    muted: false,
    solo: false,
    gain: 1,
    chain: structuredClone(CHAIN_DEFAULTS),
  }));
}

class ArrangementStore {
  bpm = $state(120);
  beatsPerBar = $state(4);
  // Typed, not `string`: an untyped field let the v1 spelling "off" through
  // svelte-check. SnapMode comes from lib/math/snap (Task 2), so Task 2 lands first.
  snap = $state<SnapMode>("lane");          // spec 4.3 default: downbeats (magnetic)
  lanes = $state<ForgeLane[]>(defaultLanes());
  clips = $state<ForgeClip[]>([]);
  pxPerSec = $state(80);
  scrollSec = $state(0);
  /** The chroma TARGET lane (spec §4.3 header row 3); null = none chosen. */
  targetLane = $state<0 | 1 | 2 | 3 | null>(null);

  private overlapStore = $state<Record<string, OverlapParams>>({});

  /**
   * Overlaps are DERIVED from clip spans -- never stored, so they cannot go stale.
   * The scan itself lives in `../math/overlaps` (Task 7) -- see that module's
   * docstring for why it is ALL pairs per lane, not just sorted-adjacent ones.
   */
  overlaps = $derived.by<Overlap[]>(() => findOverlaps(this.clips));

  arrangementEndSec = $derived(
    this.clips.reduce((m, c) => Math.max(m, c.start_sec + c.dur_sec), 0),
  );

  // ---------------------------------------------------------------- clips

  addClip(args: AddClipArgs): ForgeClip {
    const clip: ForgeClip = {
      id: nextId(),
      lane: args.lane,
      start_sec: Math.max(0, args.startSec),
      offset_sec: 0,
      dur_sec: args.durSec,
      loop: false,
      audio: args.audio,
      previewAudio: null,
      native_bpm: args.nativeBpm ?? null,
      detune_cents: 0,
      downbeats_sec: args.downbeatsSec ?? [],
      render: cloneRenderSettings(BASE_DEFAULTS),
      a2a: null,
      latentState: "none",
      history: [],
    };
    this.clips.push(clip);
    // $state deep-proxies on push: the object above is a DEAD handle. Hand back the live one.
    return this.clips[this.clips.length - 1];
  }

  private find(id: string): ForgeClip | undefined {
    return this.clips.find((c) => c.id === id);
  }

  removeClip(id: string) {
    this.clips = this.clips.filter((c) => c.id !== id);
  }

  duplicateClip(id: string): ForgeClip | undefined {
    const c = this.find(id);
    if (!c) return undefined;
    this.clips.push({
      ...structuredClone($state.snapshot(c)) as ForgeClip,
      id: nextId(),
      start_sec: c.start_sec + c.dur_sec,
      // A latent is valid only where it was encoded, so a copy elsewhere is stale by definition.
      latentState: c.latentState === "none" ? "none" : "stale",
    });
    return this.clips[this.clips.length - 1];
  }

  moveClip(id: string, startSec: number) {
    const c = this.find(id);
    if (!c) return;
    c.start_sec = Math.max(0, startSec);
    this.refreshStale(c);
  }

  moveClipToLane(id: string, lane: 0 | 1 | 2 | 3) {
    const c = this.find(id);
    if (c) c.lane = lane;
  }

  /** Head trim moves start AND offset together, or the audio slides under the clip. */
  trimClip(id: string, edge: "start" | "end", sec: number) {
    const c = this.find(id);
    if (!c) return;
    if (edge === "start") {
      const delta = sec - c.start_sec;
      const offset = c.offset_sec + delta;
      const dur = c.dur_sec - delta;
      if (offset < 0 || dur < 0.05) return;
      c.start_sec = sec;
      c.offset_sec = offset;
      c.dur_sec = dur;
    } else {
      const dur = sec - c.start_sec;
      if (dur < 0.05) return;
      c.dur_sec = dur;
    }
    this.refreshStale(c);
  }

  setLoop(id: string, on: boolean) {
    const c = this.find(id);
    if (c) c.loop = on;
  }

  setClipBpm(id: string, bpm: number | null) {
    const c = this.find(id);
    if (c) c.native_bpm = bpm;
  }

  setDetune(id: string, cents: number) {
    const c = this.find(id);
    if (c) c.detune_cents = Math.max(-100, Math.min(100, Math.round(cents)));
  }

  setDownbeats(id: string, downbeatsSec: number[]) {
    const c = this.find(id);
    if (c) c.downbeats_sec = downbeatsSec;
  }

  setPreviewAudio(id: string, ref: AudioRef | null) {
    const c = this.find(id);
    if (c) c.previewAudio = ref;
  }

  private refreshStale(c: ForgeClip) {
    if (c.latentState !== "valid") return;
    if (c.encodedAtSec === undefined || Math.abs(c.encodedAtSec - c.start_sec) > 1e-9) {
      c.latentState = "stale";
    }
  }

  // ---------------------------------------------------------------- a2a

  ensureA2A(id: string) {
    const c = this.find(id);
    if (!c || c.a2a) return;
    c.a2a = { on: true, noise: A2A_ENVELOPE_DEFAULT.points[0], envelope: structuredClone(A2A_ENVELOPE_DEFAULT) };
  }

  setEnvelope(id: string, env: Envelope) {
    const c = this.find(id);
    if (c?.a2a) c.a2a.envelope = structuredClone(env);
  }

  /** Spec §5.2: editing NOISE afterwards scales all four points proportionally. */
  setNoise(id: string, noise: number) {
    const c = this.find(id);
    if (!c?.a2a) return;
    const from = c.a2a.noise;
    c.a2a.noise = noise;
    // NOISE 0 is a legal drag value (5.1), and 0 scales nothing: from 0 the only
    // sane reading of "scales all four points proportionally" is a flat envelope at
    // the new value. Guarding with `noise || 1e-6` instead turns the next drag into
    // a factor of 500000 and pins every point to 1 -- the opposite of the gesture.
    if (from <= 0) {
      c.a2a.envelope.points = [noise, noise, noise, noise];
      return;
    }
    const factor = noise / from;
    c.a2a.envelope.points = c.a2a.envelope.points.map(
      (p) => Math.max(0, Math.min(1, p * factor)),
    ) as Envelope["points"];
  }

  // ---------------------------------------------------------------- lanes

  setLaneGain(lane: number, gain: number) {
    this.lanes[lane].gain = Math.max(0, Math.min(1, gain));
  }

  toggleMute(lane: number) {
    this.lanes[lane].muted = !this.lanes[lane].muted;
  }

  toggleSolo(lane: number) {
    this.lanes[lane].solo = !this.lanes[lane].solo;
  }

  /** Spec §8.1 S3: if any lane is soloed, only soloed lanes are audible. */
  isAudible(lane: number): boolean {
    const anySolo = this.lanes.some((l) => l.solo);
    return anySolo ? this.lanes[lane].solo : !this.lanes[lane].muted;
  }

  setTargetLane(lane: 0 | 1 | 2 | 3 | null) {
    this.targetLane = lane;
  }

  // ---------------------------------------------------------------- overlaps

  overlapParams(key: string): OverlapParams {
    if (!this.overlapStore[key]) {
      this.overlapStore[key] = {
        ...structuredClone(OVERLAP_DEFAULT),
        render: cloneRenderSettings(OVERLAP_DEFAULT.render),
      };
    }
    return this.overlapStore[key];
  }

  setOverlapParams(key: string, patch: Partial<OverlapParams>) {
    Object.assign(this.overlapParams(key), patch);
  }

  // ---------------------------------------------------------------- the M4 settings seam

  /**
   * M4's `TargetSettingsSource`, structurally (M4 plan T1: `clipSettings(id)` /
   * `overlapSettings(key)`, each returning the OWNER's settings object or null). Typed from M1's
   * own types, so this store imports nothing of M4 -- M4 and M5 are siblings (§12). M7 T9's
   * App.svelte attaches it: `settings.attach(arrangement.settingsSource)` (reconcile pass
   * 2026-09-25 -- until then `settings.attach` was called only in test fixtures).
   *
   * NEVER seeds: settings.current() runs inside $derived and templates, where a $state write
   * throws state_unsafe_mutation. An overlap whose params were never created resolves to null
   * (session defaults); OverlapBox creates them in the click handler that selects it (Task 7).
   */
  readonly settingsSource = {
    clipSettings: (id: string): ForgeClip["render"] | null => this.find(id)?.render ?? null,
    overlapSettings: (key: string): OverlapParams["render"] | null => this.overlapStore[key]?.render ?? null,
  };

  // ---------------------------------------------------------------- transport-facing

  /**
   * Spec §7.3: project tempo is NON-ELASTIC. Start times stay fixed in seconds;
   * only the stretch — and therefore each clip's duration — changes.
   */
  setBpm(bpm: number) {
    // 300, not the brief's literal 200: the trim-rescale test asks for an exact
    // 120->240 doubling (ratio 0.5, "stretched source halves") and 200 would
    // silently clamp that to 140/120, breaking the non-elastic-tempo contract
    // on the very case that proves it. No spec ceiling is documented; 300
    // keeps the floor's spirit (a sane project-tempo range) while giving that
    // test room.
    const next = Math.max(60, Math.min(300, bpm));
    const prev = this.bpm;
    if (Math.abs(next - prev) < 1e-9) return;
    for (const c of this.clips) {
      if (c.native_bpm == null) continue;
      // BOTH move: 7.3 puts offset_sec and dur_sec in the stretched domain, so a
      // change of stretch rescales the whole timebase. Rescaling only dur_sec makes
      // a trimmed clip point at different material after a tempo nudge.
      const ratio = prev / next;
      c.offset_sec = c.offset_sec * ratio;
      c.dur_sec = c.dur_sec * ratio;
    }
    this.bpm = next;
  }

  setSnap(mode: SnapMode) {
    this.snap = mode;
  }

  zoomBy(factor: number) {
    this.pxPerSec = Math.max(MIN_PX_PER_SEC, Math.min(MAX_PX_PER_SEC, this.pxPerSec * factor));
  }

  setScrollSec(sec: number) {
    this.scrollSec = Math.max(0, sec);
  }
}

export const arrangement = new ArrangementStore();
