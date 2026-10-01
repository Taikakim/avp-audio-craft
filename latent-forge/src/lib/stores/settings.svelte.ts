import { BASE_DEFAULTS, POST_DEFAULTS, cloneRenderSettings } from "../forge/defaults";
import type { RenderSettings, ScheduleSpec, Target } from "../forge/types";

export type ModelStage = "POST" | "BASE";
export type Objective = "rf_denoiser" | "rectified_flow";
export type SettingsScope = "session" | "clip" | "overlap";

/** Spec 5.3: POST = backbone `medium` (adversarially post-trained), BASE = `medium-base`. */
export const STAGE_BACKBONE: Record<ModelStage, string> = {
  POST: "medium",
  BASE: "medium-base",
};

export const STAGE_OBJECTIVE: Record<ModelStage, Objective> = {
  POST: "rf_denoiser",
  BASE: "rectified_flow",
};

/**
 * The fields a stage switch overwrites in `session.defaults`.
 *
 * Spec 5.3 says entering POST "loads the POST defaults into the session-default
 * settings", and then lists only sampling values: steps 8, sampler pingpong,
 * shape logsnr, lam [-6.2, 2.0], rho 1, CFG off. Taking the sentence literally
 * would also overwrite the prompt the user just typed, which no reading of the
 * drawing supports -- MODEL STAGE sits in the same column as STEPS and CFG, not
 * in the prompt column. So the switch is scoped to exactly the three fields 5.3
 * names, and `prompt`, `negative_prompt`, `seed`, `apg_scale`,
 * `cfg_interval_progress` and `scale_phi` survive it.
 *
 * `cfg_scale` is NOT here either. 5.3 says POST sends it as 1.0, not that it
 * stores 1.0 -- `effectiveCfg` does the substitution on the wire, so the value
 * the user set in BASE is still there when they come back. Overwriting it would
 * destroy that value for the `{kind: "none"}` target, which is every target
 * until an arrangement exists.
 */
export const STAGE_FIELDS = ["steps", "sampler_type", "schedule"] as const satisfies
  readonly (keyof RenderSettings)[];

/**
 * How this store reaches settings it does not own.
 *
 * Spec 7.2 puts `render` on the clip and inside each overlap's params, and 9.2
 * serialises them there. M5 owns the arrangement and registers itself through
 * `attach`. Returning `null` means "I have no such target", which resolves to
 * the session defaults rather than inventing an object.
 */
export interface TargetSettingsSource {
  clipSettings(id: string): RenderSettings | null;
  overlapSettings(key: string): RenderSettings | null;
}

function stageDefaults(stage: ModelStage): RenderSettings {
  return cloneRenderSettings(stage === "POST" ? POST_DEFAULTS : BASE_DEFAULTS);
}

/**
 * Typed field copy. `(x as Record<string, unknown>)[k] = ...` does not compile:
 * TS2352, "index signature for type 'string' is missing in type
 * 'RenderSettings'". The generic keeps each assignment checked field by field,
 * which is also what stops STAGE_FIELDS from silently drifting off the type.
 */
function copyFields(into: RenderSettings, from: RenderSettings): void {
  for (const k of STAGE_FIELDS) assign(into, from, k);
}

function assign<K extends keyof RenderSettings>(
  into: RenderSettings,
  from: RenderSettings,
  k: K,
): void {
  into[k] = from[k];
}

export class SettingsStore {
  /** Seeds new targets (spec 7.2) and is what an unselected pane edits. */
  defaults = $state<RenderSettings>(cloneRenderSettings(BASE_DEFAULTS));

  /** Session-level, not per target (spec 10 X4): switching rebuilds the model. */
  stage = $state<ModelStage>("BASE");

  /** Set from `/info`; displayed by the top bar, carried in the project JSON (9.2). */
  ckptPath = $state<string | null>(null);

  /**
   * Set while something else owns the session-level stage: M7's SessionController holds it for
   * the whole of a session load or IMPORT (M7 plan, Task 9). While it is set, T9's MODEL STAGE
   * offers no switch, so a rebuild can never finish mid-load and `setStage` over the defaults the
   * load just applied (reconcile pass 2026-09-25; M7 Open questions 32).
   */
  stageLocked = $state(false);

  /** True while T9's own POST/BASE rebuild is in flight. M7 refuses to START a load meanwhile, so a
   *  stage switch and a session load never overlap in either order. */
  stageRebuilding = $state(false);

  #source: TargetSettingsSource | null = null;

  attach(source: TargetSettingsSource): void {
    this.#source = source;
  }

  detach(): void {
    this.#source = null;
  }

  get objective(): Objective {
    return STAGE_OBJECTIVE[this.stage];
  }

  get backboneId(): string {
    return STAGE_BACKBONE[this.stage];
  }

  /** Spec 5.3: "CFG disabled (cfg_scale sent as 1.0, fields greyed)". */
  get cfgDisabled(): boolean {
    return this.stage === "POST";
  }

  scope(t: Target): SettingsScope {
    if (t.kind === "clip" && this.#source?.clipSettings(t.id)) return "clip";
    if (t.kind === "overlap" && this.#source?.overlapSettings(t.key)) return "overlap";
    return "session";
  }

  /**
   * The settings object this target reads. It is the OWNER's object, not a copy,
   * so a caller that mutates it in place is editing the right thing -- and the
   * $state proxy rule means a captured copy would not be reactive anyway.
   */
  current(t: Target): RenderSettings {
    if (t.kind === "clip") return this.#source?.clipSettings(t.id) ?? this.defaults;
    if (t.kind === "overlap") return this.#source?.overlapSettings(t.key) ?? this.defaults;
    return this.defaults;
  }

  /** Same object as `current`; the separate name marks a write at the call site. */
  editable(t: Target): RenderSettings {
    return this.current(t);
  }

  patch(t: Target, p: Partial<RenderSettings>): void {
    Object.assign(this.editable(t), p);
  }

  patchSchedule(t: Target, p: Partial<ScheduleSpec>): void {
    Object.assign(this.editable(t).schedule, p);
  }

  /** Restores the current stage's sampling fields; the prompt and seed stay. */
  resetSampling(t: Target): void {
    copyFields(this.editable(t), stageDefaults(this.stage));
  }

  /**
   * Does NOT call the server. The component confirms the rebuild and calls
   * `forgeApi.setBackbone` first; this only moves the client-side state, so a
   * failed rebuild leaves the store on the stage that is actually loaded.
   */
  setStage(stage: ModelStage): void {
    this.stage = stage;
    copyFields(this.defaults, stageDefaults(stage));
  }

  /** What actually goes on the wire. Spec 5.3: guidance is distilled into POST. */
  effectiveCfg(t: Target): number {
    return this.cfgDisabled ? 1.0 : this.current(t).cfg_scale;
  }
}

export const settings = new SettingsStore();
