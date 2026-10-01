// The chroma target (spec §5.4). Two sources, one 12-class Float32Array out,
// so nothing downstream ever has to know which mode is on.
//
// lane mode: the TARGET LANE's clips' folds, summed over frames and
//   max-normalised (Task 4's targetProfile). The lane lives on the ARRANGEMENT
//   store as `arrangement.targetLane: 0|1|2|3|null` (M5 T1), NOT as a flag on
//   ForgeLane -- M1 T3's ForgeLane has no such field.
// set mode: twelve piano-key toggles, which a chord symbol can fill in.
//
// Why a second ChromaClient. Task 2's `chromaClient` singleton holds ONE
// current result, which is the selected clip's -- the heatmap, the curve, the
// scan strip and the score label all read it. Lane mode needs a DIFFERENT
// clip's analysis (often several), so asking through the singleton would
// clobber the pane's own view. This store therefore owns its own instance of
// the same class, with its own per-AudioRef cache, and the two never collide.
// The cost is honest: one round trip per target-lane clip, once.

import { fold12Columns, NOTE_NAMES } from "./bins";
import { ChromaClient } from "./chromaClient.svelte";
import { type ChromaTargetMode, parseChord, setProfile, targetProfile } from "./target";
import type { AudioRef, ForgeClip } from "../forge/types";

export const NO_TARGET_LANE_LABEL = "no TARGET lane";
export const EMPTY_KEYS_LABEL = "no classes selected";

/** The lane button's own label: the drawing's `LANE n`, 1-based (v3 2047). */
export function laneTargetLabel(lane: 0 | 1 | 2 | 3 | null): string {
  return lane === null ? NO_TARGET_LANE_LABEL : `LANE ${lane + 1}`;
}

export function keysLabel(keys: readonly boolean[]): string {
  const on = NOTE_NAMES.filter((_, p) => keys[p]);
  return on.length ? on.join(" ") : EMPTY_KEYS_LABEL;
}

/**
 * The audio to analyse for each clip in the TARGET lane. §5.4 computes chroma
 * on the STRETCHED preview "so it matches what the timeline plays", and
 * previewAudio is in-memory only (M1's Normative table), so an unstretched
 * clip falls back to its source ref rather than being skipped.
 */
export function laneTargetRefs(clips: readonly ForgeClip[], lane: 0 | 1 | 2 | 3 | null): AudioRef[] {
  if (lane === null) return [];
  return clips.filter((c) => c.lane === lane).map((c) => c.previewAudio ?? c.audio);
}

const ZERO = new Float32Array(12);

export class ChromaTargetStore {
  mode = $state<ChromaTargetMode>("lane");
  keys = $state<boolean[]>(new Array(12).fill(false));
  chordText = $state("");
  /** false only for text that is neither empty nor a chord this app knows. */
  chordOk = $state(true);
  laneProfile = $state<Float32Array | null>(null);
  laneClipCount = $state(0);
  pending = $state(false);
  error = $state<string | null>(null);

  #client = new ChromaClient();
  #run = 0;

  /** The one thing everything downstream reads. */
  profile = $derived<Float32Array>(
    this.mode === "set" ? setProfile(this.keys) : (this.laneProfile ?? ZERO),
  );

  setMode(m: ChromaTargetMode): void {
    this.mode = m;
  }

  toggleKey(p: number): void {
    if (p < 0 || p > 11) return;
    this.keys[p] = !this.keys[p];
  }

  /**
   * Typing into the chord field. parseChord never throws and returns null for
   * half-finished text, which is the NORMAL case while someone types -- so
   * null leaves the key row exactly as it was and only marks the field.
   */
  setChordText(text: string): void {
    this.chordText = text;
    const trimmed = text.trim();
    if (trimmed === "") {
      this.chordOk = true;
      return;
    }
    const keys = parseChord(trimmed);
    if (!keys) {
      this.chordOk = false;
      return;
    }
    this.chordOk = true;
    this.keys = keys;
    this.mode = "set";
  }

  /**
   * Analyse every clip in the TARGET lane and fold them into one profile.
   * Sequential on purpose: the results are summed anyway, and a burst of
   * parallel /forge/chroma calls on one CPU server buys nothing.
   */
  async loadLane(refs: readonly AudioRef[]): Promise<void> {
    const run = ++this.#run;
    this.error = null;
    this.laneClipCount = refs.length;
    if (refs.length === 0) {
      this.laneProfile = null;
      this.pending = false;
      return;
    }
    this.pending = true;
    const frames: Float32Array[] = [];
    for (const ref of refs) {
      await this.#client.request(ref);
      await this.#client.flush();
      if (run !== this.#run) return; // a newer load superseded this one
      if (this.#client.error) {
        this.error = this.#client.error;
        this.laneProfile = null;
        this.pending = false;
        return;
      }
      const res = this.#client.result;
      if (res) frames.push(...fold12Columns(res.fold12, res.T));
    }
    this.laneProfile = targetProfile(frames);
    this.pending = false;
  }

  dispose(): void {
    this.#run += 1;
    this.#client.dispose();
    this.mode = "lane";
    this.keys = new Array(12).fill(false);
    this.chordText = "";
    this.chordOk = true;
    this.laneProfile = null;
    this.laneClipCount = 0;
    this.pending = false;
    this.error = null;
  }
}

/** One target for the whole CHROMA tab. */
export const chromaTarget = new ChromaTargetStore();
