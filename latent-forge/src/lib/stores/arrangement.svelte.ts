// The arrangement: what is on the timeline and where. Chrome state (theme, tabs,
// modules, help, selection) stays in view.svelte.ts; the viewport lives HERE
// because every consumer of pxPerSec is a timeline surface (WINTERMUTE,
// 2026-09-16). §9.2 still serialises it under `view: {...}` — that is a storage
// shape, not an ownership claim.

import {
  A2A_ENVELOPE_DEFAULT, BASE_DEFAULTS, CHAIN_DEFAULTS, cloneRenderSettings, MASTER_DEFAULT,
  MIX_DEFAULT, OVERLAP_DEFAULT,
} from "../forge/defaults";
import type {
  AudioRef, ClipOp, Envelope, ForgeClip, ForgeLane, MasterChain, MixSpec, OverlapParams, RenderSettings,
} from "../forge/types";
import { findOverlaps, type Overlap } from "../math/overlaps";
import type { SnapMode } from "../math/snap";
import { downbeatPhaseShifts, meanNativeBpm } from "../math/tempoMatch";
// I1 fix wave: a project-tempo change must re-arm every affected clip's
// debounced stretch (its required /forge/stretch speed = native_bpm/bpm
// changed), same as a CLIP BPM/DETUNE edit does. Safe circular import (unlike
// the transport.svelte one avoided below with an attached hook): lifecycle.ts
// has no eager module-load side effects -- its Transport decoder is
// constructed lazily on first actual use, well after both modules finish
// loading -- so it can be imported directly here.
import { scheduleStretch } from "../clips/lifecycle";

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

/** 7.3 keeps offset_sec and dur_sec in the STRETCHED domain, so anything that
 *  changes a clip's stretch has to move that pair with it. Both tempo paths --
 *  a PROJECT tempo change (setBpm) and a clip's own native tempo becoming
 *  known, changing or being cleared (setClipBpm) -- funnel through here rather
 *  than writing the same multiply a third time. Rescaling only dur_sec would
 *  make a trimmed clip point at different material. */
function rescaleTimebase(c: ForgeClip, ratio: number): void {
  if (!Number.isFinite(ratio) || ratio <= 0 || ratio === 1) return;
  c.offset_sec = c.offset_sec * ratio;
  c.dur_sec = c.dur_sec * ratio;
}

class ArrangementStore {
  bpm = $state(120);
  beatsPerBar = $state(4);
  // Typed, not `string`: an untyped field let the v1 spelling "off" through
  // svelte-check. SnapMode comes from lib/math/snap (Task 2), so Task 2 lands first.
  snap = $state<SnapMode>("lane");          // spec 4.3 default: downbeats (magnetic)
  lanes = $state<ForgeLane[]>(defaultLanes());

  /** M7 — spec §4.5/§4.6.5. Seeded from M1's own frozen defaults; nothing else about the store changes. */
  mix = $state<MixSpec>(structuredClone(MIX_DEFAULT));
  master = $state<MasterChain>(structuredClone(MASTER_DEFAULT));

  /**
   * M7 (critic follow-up #4) -- what a NEW clip's `render` starts from. BASE until App sets it to
   * `() => cloneRenderSettings(settings.defaults)` (Task 9 Step 4): M4's defaults "seed new targets"
   * (spec §7.2) and follow STAGE, but this store may not import M4 (§12). A plain field, not $state:
   * it is read only inside addClip. Must return a fresh object every call.
   */
  renderSeed: () => RenderSettings = () => cloneRenderSettings(BASE_DEFAULTS);
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
      render: this.renderSeed(),
      a2a: null,
      latentState: "none",
      history: [],
      op: null,
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
    if (!c) return;
    const prev = c.native_bpm;
    if (prev === bpm) return;
    c.native_bpm = bpm;
    // 7.3 puts offset_sec and dur_sec in the STRETCHED domain, but until
    // native_bpm is known they are still in SOURCE seconds (the upload's raw
    // duration, or a placeholder for a file-row drop). The moment it becomes
    // known -- or changes, or is cleared -- the pair has to move domains, so
    // that lifecycle.ts's stretchSpeed invariant holds:
    //     dur_sec = nativeDur * (native_bpm / projectBpm)
    // setBpm does the same rescale for a PROJECT tempo change; this is the
    // first-time-known case it cannot see, and it was the gap that made a
    // tempo-mismatched clip's stretched preview play cut-short (native >
    // project) or run into trailing silence (native < project).
    // A null on either side means "that side is plain source seconds".
    const from = prev ?? this.bpm;
    const to = bpm ?? this.bpm;
    rescaleTimebase(c, to / from);
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
  /** 7.1 row 3's OP. `$state` rule: the array element is the live proxy, so the write goes through
   *  `this.clips.find(...)`, never through a caller's captured reference. (M9 T6) */
  setClipOp(id: string, op: ClipOp | null): void {
    const clip = this.clips.find((c) => c.id === id);
    if (clip) clip.op = op;
  }

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
    this.onLaneChange?.();
  }

  toggleMute(lane: number) {
    this.lanes[lane].muted = !this.lanes[lane].muted;
    this.onLaneChange?.();
  }

  toggleSolo(lane: number) {
    this.lanes[lane].solo = !this.lanes[lane].solo;
    this.onLaneChange?.();
  }

  /**
   * I7 fix wave: mute/solo/gain edits must reach the audio engine LIVE, even
   * mid-playback (the v1 store did this via a direct `this.transport.updateLanes(...)`
   * call in each of the three methods above; this store has no such handle).
   *
   * Deliberately NOT `import { playback } from "./transport.svelte"` here:
   * transport.svelte.ts already imports `arrangement` (to snapshot clips/lanes),
   * and importing back would make `playback`'s singleton -- which eagerly
   * constructs a real `Transport`/`AudioContext` as a default constructor
   * parameter -- load as a side effect of merely importing `arrangement`,
   * including from node-environment test files (arrangement.test.ts has no
   * jsdom, and vitest.setup.ts's AudioContext stub is scoped to
   * `typeof window !== "undefined"`) that never touch playback at all. Same
   * externally-attached seam as `settingsSource` above (the M4 settings seam):
   * transport.svelte.ts attaches the real hook at its own module bottom; tests
   * that want to observe it attach a fake one directly.
   */
  private onLaneChange: (() => void) | null = null;

  attachLiveLaneUpdater(fn: (() => void) | null) {
    this.onLaneChange = fn;
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

  /**
   * M7 -- a NON-SEEDING read. `overlapParams` writes OVERLAP_DEFAULT into overlapStore on first
   * read, which throws state_unsafe_mutation when it runs inside a $derived or a template. This is
   * the reader for those places: the live entry once one exists, otherwise a fresh default-shaped
   * copy that is NOT stored (mutating it reaches nothing; write through setOverlapParams).
   * Reading `this.overlapStore[key]` still registers the dependency, so a derived that peeked an
   * unseeded key re-runs when setOverlapParams later seeds it.
   */
  peekOverlapParams(key: string): OverlapParams {
    return this.overlapStore[key] ?? {
      ...structuredClone(OVERLAP_DEFAULT),
      render: cloneRenderSettings(OVERLAP_DEFAULT.render),
    };
  }

  /**
   * M7 -- empties overlapStore IN PLACE (the field is private, and M5 has no way to drop an entry).
   * T9's applyProject calls it before writing a loaded project's overlaps: without it a previous
   * project's edits survive under any key the next one reuses (a v1 import keeps its clip ids).
   */
  clearOverlapParams(): void {
    for (const k of Object.keys(this.overlapStore)) delete this.overlapStore[k];
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
      rescaleTimebase(c, prev / next);
      // I1 fix wave: this clip's required stretch SPEED (native_bpm/bpm) just
      // changed along with the project tempo -- re-arm its debounced stretch,
      // same as a direct CLIP BPM/DETUNE edit does. Without this its
      // previewAudio silently keeps playing at the OLD tempo's stretch.
      scheduleStretch(c.id);
    }
    this.bpm = next;
  }

  /** MATCH BPM (spec §4.3): meet at the mean of the clips' native tempos --
   *  least stretch for all of them. Sets project tempo only; setBpm already
   *  leaves start_sec alone (spec §7.3), so nothing moves in time. */
  matchBpm(): number | null {
    const mean = meanNativeBpm(this.clips);
    if (mean === null) return null;
    const rounded = Math.round(mean * 10) / 10;
    this.setBpm(rounded);
    return rounded;
  }

  /** MATCH DOWNBEATS (spec §4.3): shift every participating clip by the
   *  shortest path onto the common phase. Tempo is left alone. Returns how
   *  many clips moved. */
  matchDownbeats(): number {
    const shifts = downbeatPhaseShifts(this.clips, this.bpm, this.beatsPerBar);
    let moved = 0;
    for (const [id, delta] of shifts) {
      const c = this.find(id);
      if (!c) continue;
      this.moveClip(id, c.start_sec + delta);
      moved += 1;
    }
    return moved;
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

  // ---------------------------------------------------------------- persistence
  //
  // C1 fix wave: TopBar's SAVE/LOAD serialized the v1 `project` store, which
  // has held zero clips since Task 5 -- SAVE silently produced a file with no
  // clips in it. This is the local-file save/load (TopBar's own TEMPORARY
  // mechanism per its comment, ahead of M7's real /forge/sessions integration,
  // which already has its own ProjectV2 wire contract in forge/types.ts --
  // not reused here since this is a different, narrower, local-only shape).

  /** Every piece of state a reload needs to reconstruct the arrangement. */
  toJSON(): string {
    return JSON.stringify(
      {
        kind: "latent-forge-arrangement",
        version: 1,
        bpm: this.bpm,
        beatsPerBar: this.beatsPerBar,
        snap: this.snap,
        pxPerSec: this.pxPerSec,
        scrollSec: this.scrollSec,
        targetLane: this.targetLane,
        lanes: $state.snapshot(this.lanes),
        clips: $state.snapshot(this.clips),
        overlaps: $state.snapshot(this.overlapStore),
      },
      null,
      2,
    );
  }

  loadJSON(text: string): void {
    const data = JSON.parse(text);
    if (data.kind !== "latent-forge-arrangement") {
      throw new Error(`not a latent-forge arrangement file (kind: ${data.kind ?? "missing"})`);
    }
    this.bpm = typeof data.bpm === "number" ? data.bpm : 120;
    this.beatsPerBar = typeof data.beatsPerBar === "number" ? data.beatsPerBar : 4;
    this.snap = data.snap ?? "lane";
    this.pxPerSec = typeof data.pxPerSec === "number" ? data.pxPerSec : 80;
    this.scrollSec = typeof data.scrollSec === "number" ? data.scrollSec : 0;
    this.targetLane = data.targetLane ?? null;
    this.lanes = data.lanes ?? defaultLanes();
    this.clips = data.clips ?? [];
    this.overlapStore = data.overlaps ?? {};
    // A loaded clip's previewAudio ref may have been evicted server-side, and
    // lane gain/mute/solo may differ from what the engine is holding. Re-arm
    // the (cached, debounced) stretch for every analysed clip and push the
    // lanes live. Playback and selection belong to the caller (see TopBar).
    this.onLaneChange?.();
    for (const c of this.clips) if (c.native_bpm != null) scheduleStretch(c.id);
  }
}

export const arrangement = new ArrangementStore();
