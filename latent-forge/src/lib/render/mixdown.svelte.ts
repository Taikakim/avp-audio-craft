// The `commit` action, shared by BOTH ▸ MIXDOWN buttons (spec §7.1: the MIX tab's row reads "same
// as the row above"). One module so the two cannot drift: same payload, same block reasons, same
// label, same HELP id.

import { fetchLatchHeads, type LatchHeadInfo } from "../chains/latch";
import type { RenderSettings } from "../forge/types";
import { signalKeyOf, type CommitStage, type SignalPathClip, type SignalPathInput } from "../mix/signalPath";
import { arrangement } from "../stores/arrangement.svelte";
import { settings } from "../stores/settings.svelte";
import { commitPayload, PayloadError } from "./payloads";
import { jobs } from "./jobs.svelte";
import { masterSource } from "./masterSource.svelte";

/**
 * The ONE builder of the signal-path input -- MixSignalPath.svelte renders from it and runMixdown
 * stamps a commit's stages with signalKeyOf() of it, so the key a commit is stamped with and the
 * key the component compares against can never disagree (M9 T4 Step 5).
 */
export function signalInputNow(): SignalPathInput {
  const clips: SignalPathClip[] = arrangement.clips.map((c) => ({
    lane: c.lane,
    isCropAudio: c.audio.kind === "crop",
    needsStretch: (c.native_bpm !== null && c.native_bpm !== arrangement.bpm) || c.detune_cents !== 0,
    a2aOn: c.a2a?.on ?? false,
  }));
  return {
    lanes: arrangement.lanes.map((l) => ({ index: l.index, chain: l.chain })),
    clips,
    overlapCount: arrangement.overlaps.length,
    mix: arrangement.mix,
    master: arrangement.master,
  };
}

/** The signal key of the arrangement the in-flight commit was built from (set in runMixdown). */
let pendingKey: string | null = null;

// Spec 6.9: a commit's result carries `meta.stages` ([{label, on, note, seconds}]). Captured with
// the signal key of the arrangement it described, so mergeSignalPath can tell when it has gone stale.
jobs.onDone = (rec) => {
  if (rec.op !== "commit") return;
  // Pressing MIXDOWN is the operator asking to hear the mixdown: show the result they just made.
  // (Before this, the MASTER pane stayed on PREVIEW and read "no mix yet" after a good commit.)
  masterSource.set("mixdown");
  const raw = (rec.result?.meta as { stages?: unknown } | undefined)?.stages;
  if (!Array.isArray(raw)) return;
  mixdown.acceptStages(raw as CommitStage[], pendingKey);
};

/** §9.7's inline error is keyed by target; a commit has no clip or overlap, so it gets its own. */
export const MIXDOWN_TARGET_KEY = "mixdown";

class MixdownStore {
  /** The last commit's meta.stages, or null. */
  stages = $state<CommitStage[] | null>(null);
  /** The signalKeyOf() of the arrangement those stages describe. */
  key = $state<string | null>(null);

  /** Overridable in tests; /info is fetched once per commit, not cached across a backbone switch. */
  heads(): Promise<Record<string, LatchHeadInfo>> {
    return fetchLatchHeads();
  }

  acceptStages(stages: CommitStage[], key: string | null = this.key): void {
    this.stages = stages;
    this.key = key;
  }

  reset(): void {
    this.stages = null;
    this.key = null;
  }
}

export const mixdown = new MixdownStore();

/**
 * Why MIXDOWN is disabled, in the words the button shows. The empty-arrangement sentence is
 * validate_commit's own (M8 plan:1452-1453, `raise ForgeError(400, "nothing to commit — the
 * arrangement has no clips")`) so the operator reads the same text whichever side caught it.
 */
export function mixdownBlock(): string | null {
  if (jobs.gpuBusyOther !== null) return `GPU busy — ${jobs.gpuBusyOther}`;
  if (jobs.active !== null) return "a render is already running";
  if (arrangement.clips.length === 0) return "nothing to commit — the arrangement has no clips";
  return null;
}

/** §4.5 LENGTH does not apply to a commit: the arrangement's own end is the length (§6.9's
 *  top-level duration_sec), floored at one second so an empty-ish arrangement is not 0. */
function commitDuration(): number {
  return Math.max(1, arrangement.arrangementEndSec);
}

export async function runMixdown(): Promise<void> {
  const blocked = mixdownBlock();
  if (blocked !== null) {
    jobs.lastError = { targetKey: MIXDOWN_TARGET_KEY, message: blocked };
    return;
  }
  let payload: Record<string, unknown>;
  try {
    const heads = await mixdown.heads();
    payload = commitPayload({
      bpm: arrangement.bpm,
      durationSec: commitDuration(),
      defaults: settings.defaults,
      lanes: arrangement.lanes,
      clips: arrangement.clips,
      overlaps: arrangement.overlaps,
      overlapParamsOf: (key) => arrangement.peekOverlapParams(key),
      mix: arrangement.mix,
      master: arrangement.master,
      decodeLanes: false,
      heads,
      // Spec §5.3: guidance is distilled into POST, so cfg goes on the wire as 1.0 there --
      // without mutating any target's own cfg_scale.
      cfgOf: (s: RenderSettings) => (settings.cfgDisabled ? 1.0 : s.cfg_scale),
    });
  } catch (e) {
    // A PayloadError is a refusal we can explain; anything else is a bug and is surfaced the same
    // way rather than thrown into a click handler where nothing would catch it.
    jobs.lastError = {
      targetKey: MIXDOWN_TARGET_KEY,
      message: e instanceof PayloadError || e instanceof Error ? e.message : String(e),
    };
    return;
  }
  pendingKey = signalKeyOf(signalInputNow());
  await jobs.submit({ op: "commit", payload, kind: "mix", sourceClipId: null, targetKey: MIXDOWN_TARGET_KEY });
}
