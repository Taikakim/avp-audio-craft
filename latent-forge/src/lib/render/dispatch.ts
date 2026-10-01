// Spec §7.1's table, as a pure function. The twin of Writer A's renderBlock: the component reads
// the stores and hands the world in, so every row of the table is a one-line test and none of them
// needs a mounted component or a mocked fetch.
//
// The division of labour with renderBlock: renderBlock answers "may this run, and if not, what do I
// tell the operator" and owns every user-facing refusal. renderRequest answers "what exactly goes
// on the wire" and THROWS on a state renderBlock would already have refused -- a PayloadError here
// means the caller skipped the gate, which is a bug, not an operator mistake.

import type {
  AudioRef, ClipOp, ForgeClip, ForgeLane, JobOp, OverlapParams, RenderSettings, Target,
} from "../forge/types";
import { targetKey } from "../forge/guards";
import type { LatchHeadInfo } from "../chains/latch";
import type { RenderKind, SubmitRequest } from "./jobs.svelte";
import { a2aClipPayload, generatePayload, inpaintPayload, opPayload, PayloadError } from "./payloads";

export type { ClipOp } from "../forge/types";

/** M1's MIXDOWN copy on the other render control, so both say the same sentence. */
export const PREVIEW_RENDER_IDLE_LABEL = "▸ RENDER";

/** §6.8's default context each side of an inpaint region. M9 has no UI for it; when one lands it
 *  reads from here. Exported rather than component-local because Task 9's `dispatchWorld.ts`
 *  imports it — a `const` inside `PreviewContainer.svelte` is not importable. */
export const PAD_SEC = 8;

/** `stepsLeft` may legitimately be 0 (Fact 5: a commit with no sampling passes, decode, bend), so
 *  `?? 0` is for the null case only and the 0 is printed, never swallowed. */
export function renderLabel(busy: boolean, stepsLeft: number | null): string {
  if (!busy) return PREVIEW_RENDER_IDLE_LABEL;
  return `SAMPLING · ${stepsLeft ?? 0} steps left`;
}

/** Derived overlap, M5 T1's shape. */
export interface DispatchOverlap {
  key: string;
  lane: 0 | 1 | 2 | 3;
  start_sec: number;
  end_sec: number;
  a_id: string;
  b_id: string;
}

export interface DispatchWorld {
  /** `settings.current(target)` -- the TARGET's own copy (§7.2), the session defaults for `none`. */
  settings: RenderSettings;
  /** `settings.effectiveCfg(target)` -- 1.0 under POST (§5.3), which must not overwrite the field
   *  the operator is editing. */
  cfgScale: number;
  clip: ForgeClip | null;
  /** The CLIP's lane (§7.1 row 2: "using its lane's chain"), not `view.activeLane`. */
  lane: ForgeLane | null;
  heads: Record<string, LatchHeadInfo>;
  ckptPath: string | null;
  overlap: DispatchOverlap | null;
  overlapParams: OverlapParams | null;
  clipById: (id: string) => ForgeClip | null;
  /** The prompt-ARC string for `longform`. */
  arcPrompt: string;
  bendOps: unknown[];
  /** §6.8's context each side; default 8. */
  padSec: number;
}

const KIND_OF: Record<string, RenderKind> = {
  generate: "gen", decode: "gen", longform: "gen", bend: "gen",
  a2a_clip: "a2a", inpaint: "inpaint", commit: "mix",
};

export function kindOf(op: JobOp): RenderKind {
  return KIND_OF[op] ?? "gen";
}

function latentSourceOf(audio: AudioRef): { cropId?: string; latentPath?: string } {
  // renderBlock's own rule (`hasLatent`): the clip's latent IS its crop ref. A clip whose audio is
  // anything else has no latent to decode or bend, which renderBlock already refuses.
  return audio.kind === "crop" ? { cropId: audio.crop_id } : {};
}

function clipRequest(clip: ForgeClip, w: DispatchWorld): SubmitRequest {
  const key = targetKey({ kind: "clip", id: clip.id });

  // §7.1 row 2 wins over row 3: A2A on is a2a_clip whatever the OP select says.
  if (clip.a2a?.on) {
    return {
      op: "a2a_clip",
      kind: "a2a",
      sourceClipId: clip.id,
      targetKey: key,
      payload: a2aClipPayload({
        audio: clip.audio,
        render: w.settings,
        a2a: { on: true, noise: clip.a2a.noise, envelope: clip.a2a.envelope ?? null },
        chain: w.lane?.chain ?? null,
        heads: w.heads,
        ckptPath: w.ckptPath,
        cfgScale: w.cfgScale,
      }),
    };
  }

  const op: ClipOp | null = clip.op;
  if (op === null) {
    // renderBlock returns "turn A2A on or choose an op" for exactly this state; reaching here means
    // the gate was skipped.
    throw new PayloadError("turn A2A on or choose an op");
  }

  const payload =
    op === "generate"
      ? generatePayload(w.settings, w.cfgScale)
      : opPayload(op, {
          ...latentSourceOf(clip.audio),
          ops: w.bendOps,
          seed: w.settings.seed,
          arc: w.arcPrompt,
          steps: w.settings.steps,
          cfgScale: w.cfgScale,
          durationSec: w.settings.duration_sec,
        });

  return { op, kind: "gen", sourceClipId: clip.id, targetKey: key, payload };
}

function overlapRequest(w: DispatchWorld): SubmitRequest {
  const o = w.overlap;
  const params = w.overlapParams;
  if (!o || !params) throw new PayloadError("the overlap is gone");
  const a = w.clipById(o.a_id);
  const b = w.clipById(o.b_id);
  if (!a || !b) throw new PayloadError("the overlap is gone");

  // start/offset/dur are TIMELINE (stretched-domain) seconds, and run_inpaint_preview does not
  // stretch (commit's S2 does). So send the stretched file the timeline already plays; the raw
  // source would be sliced at the wrong place, tempo and pitch (review 2026-10-01).
  const side = (c: ForgeClip) => ({
    audio: c.previewAudio ?? c.audio, start_sec: c.start_sec, offset_sec: c.offset_sec, dur_sec: c.dur_sec,
  });

  return {
    op: "inpaint",
    kind: "inpaint",
    // §7.1 row 4 lands in "preview container + history" with no REPLACE CLIP: an inpaint is made
    // from two clips, so there is no single clip to replace.
    sourceClipId: null,
    targetKey: targetKey({ kind: "overlap", key: o.key }),
    payload: inpaintPayload({
      a: side(a),
      b: side(b),
      region: { start_sec: o.start_sec, end_sec: o.end_sec },
      params,
      padSec: w.padSec,
      cfgScale: w.cfgScale,
    }),
  };
}

/**
 * The §7.1 table. Throws `PayloadError` on a state `renderBlock` would already have refused, or a
 * payload field outside the server's range (Writer A's builders name the field).
 */
export function renderRequest(target: Target, w: DispatchWorld): SubmitRequest {
  if (target.kind === "overlap") return overlapRequest(w);
  if (target.kind === "clip") {
    if (!w.clip) throw new PayloadError("the selected clip is gone");
    return clipRequest(w.clip, w);
  }
  // §7.1 row 1: session-default settings, LENGTH as `duration`.
  return {
    op: "generate",
    kind: "gen",
    sourceClipId: null,
    targetKey: targetKey({ kind: "none" }),
    payload: generatePayload(w.settings, w.cfgScale),
  };
}
