import { SAMPLERS_BY_OBJECTIVE } from "../forge/defaults";
import type { LatchSlot } from "../forge/types";
import type { Objective } from "../stores/settings.svelte";

/** Spec 5.3: the LatCH-guided sampler is Euler-only. */
export const LATCH_FORCED_SAMPLER = "euler";
export const LATCH_FORCED_LABEL = "euler (forced by LatCH)";

/** Just the part of a LaneChain this module reads, so M7 can hand it any shape. */
export interface LatchState {
  latch_on: boolean;
  slots: readonly LatchSlot[];
}

/**
 * A slot is active only if it could change the sample: the chain is on, it names
 * a head, and it carries weight. An inert slot must not force Euler -- the
 * drawing leaves both slots present at all times, so "slots.length > 0" would
 * force Euler permanently.
 *
 * The window is deliberately NOT part of this test. Spec 5.5 drops a slot only
 * for `head === "none"` or `weight === 0`, so a zero-width window still reaches
 * the server, which forces Euler and echoes a warning (5.3). Filtering on the
 * window here would have the client send `dpmpp` while reporting `forced: false`
 * and the server quietly sample with something else -- a disagreement about what
 * ran, which is the one thing this pane exists to prevent. The sigma graph may
 * still skip drawing a zero-width lane; that is a drawing question, not this one.
 */
export function activeSlots(l: LatchState): LatchSlot[] {
  if (!l.latch_on) return [];
  return l.slots.filter((s) => s.head !== "" && s.head !== "none" && s.weight !== 0);
}

export function isLatchActive(l: LatchState): boolean {
  return activeSlots(l).length > 0;
}

export interface SamplerChoice {
  value: string;
  label: string;
  options: readonly string[];
  disabled: boolean;
  forced: boolean;
}

/**
 * The sampler the request will carry, plus what the select should show.
 *
 * A requested sampler the objective does not offer falls back to the objective's
 * first option rather than being sent: switching POST/BASE changes the objective
 * under a stored `sampler_type`, and `dpmpp` on rf_denoiser is not a thing the
 * server can honour.
 */
export function resolveSampler(
  objective: Objective,
  requested: string | null,
  latch: LatchState,
): SamplerChoice {
  // M1 types the table as Record<string, string[]>, so the lookup is unchecked
  // and the array is shared and mutable -- copy it before handing it to a select.
  const options: readonly string[] = [...(SAMPLERS_BY_OBJECTIVE[objective] ?? [])];
  if (isLatchActive(latch)) {
    return {
      value: LATCH_FORCED_SAMPLER,
      label: LATCH_FORCED_LABEL,
      options,
      disabled: true,
      forced: true,
    };
  }
  const value = requested !== null && options.includes(requested) ? requested : options[0];
  return { value, label: value, options, disabled: false, forced: false };
}
