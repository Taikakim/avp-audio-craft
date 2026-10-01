// Spec §9.7: "Blocked targets use the existing `renderBlock` reasons, extended to the new ops."
// The existing ones are v1's (sa3-studio/src/lib/store.svelte.ts:351-388) -- {reason, hint} pairs.
// §9.7's surface is ONE line, so reason and hint are joined with the em dash v1's own renderClip
// used: `${blocked.reason} — ${blocked.hint}`.
//
// PURE, and it imports no store: Writer B's ▸ RENDER (M9 T6) and this task's inline error both
// call it, and the two were written in parallel. The caller reads the stores and hands the world
// in, which is also what makes every branch here a one-line test.
//
// a2a_track and a2a_mix are deliberately absent: both need a server-side `audio_path` and there is
// no upload-to-path route (v1's own hint says so), and §7.1's OP column lists only
// generate/decode/longform/bend. See open question A3.

import type { ClipOp, ForgeClip, RenderSettings, Target } from "../forge/types";
import { CAP_SEC } from "./payloads";

export type { ClipOp } from "../forge/types";

export interface RenderBlockState {
  /** jobs.busy -- §7.1: "While any job runs, every render control is disabled". */
  busy: boolean;
  /** jobs.gpuBusyOther -- §9.7's `GPU busy — <job_id>`. */
  gpuBusyOther: string | null;
  /** The TARGET's own settings (§7.2), not the session defaults, unless the target is `none`. */
  settings: RenderSettings;
  /** The selected clip, when the target is a clip. */
  clip: ForgeClip | null;
  /** The clip's OP when A2A is off. null = it has neither (§7.1's disabled row). */
  clipOp: ClipOp | null;
  /** The prompt-ARC string for `longform` (server:1366 reads it as req["schedule"]). */
  arcPrompt: string;
  /** How many bend ops are configured. */
  bendOpCount: number;
  /** The overlap's own length in seconds, when the target is an overlap. */
  overlapSpanSec: number;
  /** The inpaint context each side (spec §6.8, default 8.0). */
  padSec: number;
}

const CAP_LINE = `over the 184 s cap — forge passes are capped at 184 s locally (T<2048).`;

/** v1's rule, unchanged: a latent exists if the clip's own audio is a crop ref. M9 has no
 *  `latentPath` on ForgeClip, so the crop ref is the whole of it (open question A3). */
function hasLatent(clip: ForgeClip): boolean {
  return clip.audio.kind === "crop";
}

function generateBlock(s: RenderSettings): string | null {
  if (!s.prompt.trim()) return "needs a prompt — /generate requires a non-empty prompt.";
  if (!(s.duration_sec > 0) || s.duration_sec > CAP_SEC) return `LENGTH is ${CAP_LINE}`;
  return null;
}

export function renderBlock(target: Target, state: RenderBlockState): string | null {
  // §9.7 puts the GPU line on RENDER itself, so it outranks the generic busy line -- an operator
  // needs to know it is someone else's job, not theirs.
  if (state.gpuBusyOther !== null) return `GPU busy — ${state.gpuBusyOther}`;
  if (state.busy) return "a render is already running";

  if (target.kind === "overlap") {
    const span = state.overlapSpanSec + 2 * state.padSec;
    if (!(state.overlapSpanSec > 0)) return "the overlap has no length";
    if (span > CAP_SEC) return `the padded inpaint span is ${CAP_LINE}`;
    return null;
  }

  if (target.kind === "none") return generateBlock(state.settings);

  const clip = state.clip;
  if (clip === null) return "the selected clip is gone";
  // §7.1 row 2: A2A on wins, and a2a_clip needs no prompt -- the source audio is the prompt.
  if (clip.a2a?.on) return null;
  // §7.1 row 3's own words, quoted: "disabled with the hint `turn A2A on or choose an op`".
  if (state.clipOp === null) return "turn A2A on or choose an op";

  switch (state.clipOp) {
    case "generate":
      return generateBlock(state.settings);
    case "decode":
      return hasLatent(clip) ? null : "no latent to decode — /decode takes crop_id or latent_path.";
    case "bend":
      if (!hasLatent(clip)) return "no latent to bend — /bend takes crop_id or latent_path.";
      return state.bendOpCount > 0
        ? null
        : "no bend ops — add at least one op: channel_roll, quantize, segment_shuffle…";
    case "longform":
      return state.arcPrompt.trim()
        ? null
        : "needs a prompt arc — arc grammar, e.g. 0:opening pad|45:driving bass.";
  }
}
