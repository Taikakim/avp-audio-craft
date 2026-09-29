// Clip lifecycle (spec §7.3, §6.3): resolve an AudioRef, analyze for tempo
// and downbeats, stretch to the project's tempo/detune, warm the peak cache.
// Every step degrades honestly -- a clip that fails analysis still lands on
// the timeline with native_bpm: null, and a stretch failure never removes it
// or blocks its (un-stretched) audio from playing.

import { forgeApi, ForgeApiError } from "../forge/api";
import { arrangement } from "../stores/arrangement.svelte";
import { Transport } from "../audio/transport";
import type { AudioRef, ForgeClip } from "../forge/types";

const STRETCH_DEBOUNCE_MS = 400;

/** Client mirror of the server's stretch cache key (spec §6.3), minus the
 *  file sha256 -- the AudioRef itself already identifies the source audio
 *  (an upload ref carries its own sha256; a crop ref is a stable id). */
export function stretchCacheKey(ref: AudioRef, speed: number, semitones: number): string {
  return `${JSON.stringify(ref)}::${speed.toFixed(6)}::${semitones.toFixed(4)}`;
}

/** >1 = faster (spec §6.3 /forge/stretch). The same ratio T1's non-elastic
 *  duration rescaling implies: dur_sec = nativeDur * (native_bpm/projectBpm). */
export function stretchSpeed(nativeBpm: number, projectBpm: number): number {
  return projectBpm / nativeBpm;
}

// In-flight dedup only: an entry is removed as soon as its promise settles
// (success OR failure), never left cached indefinitely. Two reasons: (1) a
// failed request must not poison later callers with a stale rejection, and
// (2) a SUCCESSFUL result must not be reused forever either -- once a clip is
// removed from the timeline nothing should keep serving its cached analysis.
// Sequential (non-concurrent) reuse of an already-known result instead goes
// through `analyzedSibling`/`stretchedSibling` below, which read the live
// arrangement rather than a side cache -- that state already gets cleaned up
// by `removeClip`, so it can never go stale independently of the timeline.
const analyzeCache = new Map<string, Promise<{ bpm: number | null; downbeats_sec: number[] }>>();
const stretchCache = new Map<string, Promise<{ ref: AudioRef; duration_sec: number }>>();
const stretchTimers = new Map<string, ReturnType<typeof setTimeout>>();

/** Another LIVE clip already analyzed to the same AudioRef -- reuse its
 *  result instead of re-asking the server (spec §7.3 "cached"). Scoped to
 *  the live timeline, not a permanent cache: returns null once no clip using
 *  this ref remains, so the next clip added against it re-analyzes fresh. */
function analyzedSibling(ref: AudioRef, excludeId: string): { bpm: number | null; downbeats_sec: number[] } | null {
  const key = JSON.stringify(ref);
  const sibling = arrangement.clips.find(
    (c) => c.id !== excludeId && c.native_bpm != null && JSON.stringify(c.audio) === key,
  );
  return sibling ? { bpm: sibling.native_bpm, downbeats_sec: sibling.downbeats_sec } : null;
}

/** Another live clip already stretched to the exact same (ref, speed,
 *  semitones) -- reuse its previewAudio instead of re-asking the server. */
function stretchedSibling(targetKey: string, excludeId: string): AudioRef | null {
  for (const c of arrangement.clips) {
    if (c.id === excludeId || c.previewAudio == null || c.native_bpm == null) continue;
    const key = stretchCacheKey(c.audio, stretchSpeed(c.native_bpm, arrangement.bpm), c.detune_cents / 100);
    if (key === targetKey) return c.previewAudio;
  }
  return null;
}

/** Lazily built and never allowed to take the caller down with it: there is
 *  no Web Audio in the vitest environment (node, no jsdom AudioContext), and
 *  a browser that somehow lacks it should not lose the clip over a peak-cache
 *  warm-up. Real browsers, and Playwright, always have one. */
let _decoder: Transport | null | undefined;
function decoder(): Transport | null {
  if (_decoder === undefined) {
    try {
      _decoder = new Transport();
    } catch {
      _decoder = null;
    }
  }
  return _decoder;
}

export interface AddClipInput {
  lane: 0 | 1 | 2 | 3;
  startSec: number;
  /** An OS file drop: uploaded first (spec §7.3); its own duration is used. */
  file?: File;
  /** An already-known ref: preview container, MIXDOWN slot, FILES, history. */
  ref?: AudioRef;
  /** Required when `file` is not given -- the drag source already knows it. */
  durationSec?: number;
  /** Skip analysis when the caller already knows these (e.g. a duplicated clip). */
  nativeBpm?: number | null;
  downbeatsSec?: number[];
}

export interface AddClipOutcome {
  clip: ForgeClip;
  /** Set when analysis failed; the clip is on the timeline regardless. */
  analyzeError: ForgeApiError | null;
}

function asApiError(e: unknown): ForgeApiError {
  return e instanceof ForgeApiError ? e : new ForgeApiError(0, e instanceof Error ? e.message : String(e));
}

/** Adding a clip (spec §7.3): resolve ref (upload first for OS files) ->
 *  analyze unless already known -> schedule the debounced stretch -> peaks
 *  warm. */
export async function addClip(input: AddClipInput): Promise<AddClipOutcome> {
  let ref: AudioRef;
  let durSec = input.durationSec ?? 0;

  if (input.file) {
    const up = await forgeApi.upload(input.file);
    ref = up.ref;
    durSec = up.duration_sec;
  } else if (input.ref) {
    ref = input.ref;
  } else {
    throw new Error("addClip needs a file or a ref");
  }

  const clip = arrangement.addClip({
    lane: input.lane,
    startSec: input.startSec,
    durSec,
    audio: ref,
    nativeBpm: input.nativeBpm ?? null,
    downbeatsSec: input.downbeatsSec ?? [],
  });

  let analyzeError: ForgeApiError | null = null;
  if (input.nativeBpm == null && input.downbeatsSec == null) {
    try {
      await ensureAnalysis(clip.id);
    } catch (e) {
      analyzeError = asApiError(e);
      // Honest degradation (spec §7.3): the clip stays, native_bpm stays null.
    }
  }

  scheduleStretch(clip.id);
  return { clip, analyzeError };
}

/** forgeApi.analyze fills native_bpm and downbeats_sec unless already known
 *  (spec §7.3). Cached while a LIVE sibling clip on the timeline already
 *  shares the same AudioRef -- not cached forever: once every clip using
 *  that ref has been removed, re-adding it (e.g. from FILES/history) pays a
 *  fresh round trip rather than serving a stale (or nonexistent) entry. */
export async function ensureAnalysis(clipId: string): Promise<void> {
  const clip = arrangement.clips.find((c) => c.id === clipId);
  if (!clip || clip.native_bpm != null) return;

  const sibling = analyzedSibling(clip.audio, clipId);
  if (sibling) {
    arrangement.setClipBpm(clipId, sibling.bpm);
    arrangement.setDownbeats(clipId, sibling.downbeats_sec);
    return;
  }

  const key = JSON.stringify(clip.audio);
  let pending = analyzeCache.get(key);
  if (!pending) {
    pending = forgeApi.analyze(clip.audio).then((r) => ({ bpm: r.bpm, downbeats_sec: r.downbeats_sec }));
    analyzeCache.set(key, pending);
    // .finally()'s own returned promise mirrors a rejection and nothing else
    // holds it, so swallow it there -- `await pending` below (and addClip's
    // try/catch) is what actually handles the failure.
    pending.finally(() => {
      if (analyzeCache.get(key) === pending) analyzeCache.delete(key);
    }).catch(() => {});
  }
  const result = await pending;

  const live = arrangement.clips.find((c) => c.id === clipId);
  if (!live) return; // removed while analysis was in flight
  arrangement.setClipBpm(live.id, result.bpm);
  arrangement.setDownbeats(live.id, result.downbeats_sec);
}

/** Debounced 400ms (spec §7.3); re-arms on every call for the same clip. */
export function scheduleStretch(clipId: string, onError?: (e: ForgeApiError) => void) {
  const existing = stretchTimers.get(clipId);
  if (existing) clearTimeout(existing);
  stretchTimers.set(
    clipId,
    setTimeout(() => {
      stretchTimers.delete(clipId);
      void runStretch(clipId, onError);
    }, STRETCH_DEBOUNCE_MS),
  );
}

async function runStretch(clipId: string, onError?: (e: ForgeApiError) => void): Promise<void> {
  const clip = arrangement.clips.find((c) => c.id === clipId);
  if (!clip || clip.native_bpm == null) return;

  const speed = stretchSpeed(clip.native_bpm, arrangement.bpm);
  const semitones = clip.detune_cents / 100;
  // Identity, per spec §6.3 -- the server would return the source ref unchanged anyway.
  if (Math.abs(speed - 1) < 5e-4 && Math.abs(semitones) < 1e-4) {
    arrangement.setPreviewAudio(clipId, null);
    return;
  }

  const key = stretchCacheKey(clip.audio, speed, semitones);

  const sibling = stretchedSibling(key, clipId);
  if (sibling) {
    arrangement.setPreviewAudio(clipId, sibling);
    await decoder()?.preload(forgeApi.audioUrl(sibling)); // best-effort
    return;
  }

  let pending = stretchCache.get(key);
  if (!pending) {
    pending = forgeApi.stretch(clip.audio, speed, semitones).then((r) => ({ ref: r.ref, duration_sec: r.duration_sec }));
    stretchCache.set(key, pending);
    pending.finally(() => {
      if (stretchCache.get(key) === pending) stretchCache.delete(key);
    }).catch(() => {});
  }

  try {
    const result = await pending;
    const live = arrangement.clips.find((c) => c.id === clipId);
    if (!live) return;
    arrangement.setPreviewAudio(live.id, result.ref);
    await decoder()?.preload(forgeApi.audioUrl(result.ref)); // warm the peak cache; best-effort
  } catch (e) {
    // A stretch failure must not remove the clip or block its original audio
    // (spec §7.3 "degrade honestly") -- playback just falls back to unstretched.
    onError?.(asApiError(e));
  }
}
