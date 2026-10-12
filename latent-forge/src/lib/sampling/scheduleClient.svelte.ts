import { ForgeApiError } from "../forge/api";
import { SCHEDULE_DEFAULT } from "../forge/defaults";
import type { ScheduleSpec } from "../forge/types";

/** Spec 5.3's graph is debounced 150ms so a drag does not fire one request per frame. */
export const SCHEDULE_DEBOUNCE_MS = 150;

export interface ScheduleRequest {
  steps: number;
  duration: number;
  sigma_max: number;
  sampler_type: string | null;
  schedule: ScheduleSpec;
}

/**
 * `shape` and `warnings` are optional because today's server
 * (explorer_render_server.py:1009-1060) reads only steps/duration/sigma_max/dist_shift and
 * never echoes either one. M1 T5 types them as required on the wire; this is the client's own,
 * more honest shape until M3 lands.
 */
export interface ScheduleResult {
  sigmas: number[];
  steps: number;
  duration: number;
  sigma_max: number;
  dist_shift: string | number;
  latent_len: number;
  shape?: string;
  warnings?: string[];
}

/**
 * A value-based cache key, not object identity. The nested `schedule` object's own keys are
 * sorted too, so two ScheduleSpec literals built with the same values in a different property
 * order still hash the same -- callers construct these objects in more than one place across
 * this milestone and nothing should force them to agree on field order to hit the cache.
 */
export function scheduleKey(req: ScheduleRequest): string {
  const sortedSchedule = Object.fromEntries(
    Object.entries(req.schedule).sort(([a], [b]) => a.localeCompare(b)),
  );
  return JSON.stringify({
    steps: req.steps,
    duration: req.duration,
    sigma_max: req.sigma_max,
    sampler_type: req.sampler_type,
    schedule: sortedSchedule,
  });
}

/** Spec 5.3: "the sigma sequence must be non-increasing." Equal neighbours are fine (a flat
 * plateau); only a step back UP is a violation. */
export function isNonIncreasing(sigmas: number[]): boolean {
  for (let i = 1; i < sigmas.length; i++) {
    if (sigmas[i] > sigmas[i - 1]) return false;
  }
  return true;
}

const SCHEDULE_FIELDS = Object.keys(SCHEDULE_DEFAULT) as (keyof ScheduleSpec)[];

/**
 * Whether a spec is byte-for-byte M1 T4's SCHEDULE_DEFAULT. Keyed off the default object's own
 * keys rather than a hand-written field list, so a ScheduleSpec field added later is compared
 * without anyone remembering to come back here. `staleShape` needs the WHOLE spec, not just
 * `shape`: today's route ignores the entire `schedule` block, so ρ, STEPPED, PLATEAUS and TILT
 * changed at shape "model" chart exactly the same curve as the untouched default does.
 */
export function scheduleIsDefault(spec: ScheduleSpec): boolean {
  return SCHEDULE_FIELDS.every((k) => spec[k] === SCHEDULE_DEFAULT[k]);
}

class AbortedError extends Error {}

/**
 * M4's own call to /schedule. NOT `forgeApi.schedule`: M1's frozen client takes one parameter
 * (no AbortSignal), has no `duration` in its body type, and declares a return type that claims
 * `shape`/`warnings` the route does not send while omitting the five it does. Spec 6 freezes
 * only `/forge/*` and asks for the pre-existing routes the client "calls directly" -- /schedule
 * among them -- to live "in their own client module so the frozen and unfrozen surfaces stay
 * distinguishable". This file is that module, so the call lives here. Module-local on purpose:
 * `ScheduleClient` is the only caller, and nothing outside this file should reach the route.
 */
async function postSchedule(req: ScheduleRequest, signal: AbortSignal): Promise<ScheduleResult> {
  const res = await fetch("/schedule", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(req),
    signal,
  });
  // Parse tolerantly for the same reason M1's own client does: a dead proxy answers with HTML
  // or with nothing, and a raw JSON parse error tells the operator nothing.
  const body = (await res.json().catch(() => null)) as (ScheduleResult & { error?: string }) | null;
  if (body === null) {
    throw new ForgeApiError(res.status, "render server unreachable (non-JSON response from /schedule)");
  }
  // The route answers a validation failure with {"error": "..."} and no `ok` key
  // (explorer_render_server.py:1024-1031), so the status is what decides.
  if (!res.ok) throw new ForgeApiError(res.status, body.error ?? `request failed (${res.status})`);
  return body;
}

/**
 * Races the real call against the signal itself, checking `signal.aborted` BEFORE adding the
 * listener. An abort fired earlier in the same tick (a superseded request, or dispose()) has
 * already dispatched its one 'abort' event by the time some code gets around to listening for
 * it; a listener added after that point never runs and the promise it was meant to settle hangs
 * forever. This exact bug was found and fixed in M1's own abortable client.
 */
function abortRejection(signal: AbortSignal): Promise<never> {
  return new Promise((_resolve, reject) => {
    if (signal.aborted) {
      reject(new AbortedError());
      return;
    }
    signal.addEventListener("abort", () => reject(new AbortedError()), { once: true });
  });
}

export class ScheduleClient {
  result = $state<ScheduleResult | null>(null);
  pending = $state(false);
  error = $state<string | null>(null);

  #cache = new Map<string, ScheduleResult>();
  #timer: ReturnType<typeof setTimeout> | null = null;
  #controller: AbortController | null = null;
  #lastReq: ScheduleRequest | null = null;
  #lastResultReq: ScheduleRequest | null = null;
  #inFlight: Promise<void> | null = null;
  #disposed = false;

  /** True exactly when the request behind the CURRENTLY SHOWN result asked for ANY non-default
   * ScheduleSpec and the response carried no `shape` -- the only signal available before M3
   * that the curve on screen is the model curve regardless of what was asked for. The whole
   * spec, not just `shape`: the route ignores the entire `schedule` block today, so a person
   * dragging rho or switching STEPPED on at shape "model" is looking at exactly as uncharted a
   * curve as someone who picked "geometric", and deserves the same note. */
  get staleShape(): boolean {
    if (!this.#lastResultReq || !this.result) return false;
    return !scheduleIsDefault(this.#lastResultReq.schedule) && this.result.shape === undefined;
  }

  request(req: ScheduleRequest): void {
    if (this.#disposed) return;
    this.#lastReq = req;
    if (this.#timer !== null) {
      clearTimeout(this.#timer);
      this.#timer = null;
    }
    const cached = this.#cache.get(scheduleKey(req));
    if (cached) {
      if (this.#controller) {
        this.#controller.abort();
        this.#controller = null;
      }
      this.result = cached;
      this.error = null;
      this.pending = false;
      this.#lastResultReq = req;
      return;
    }
    this.pending = true;
    this.#timer = setTimeout(() => {
      this.#timer = null;
      this.#inFlight = this.#run(req);
    }, SCHEDULE_DEBOUNCE_MS);
  }

  /** Test seam: bypasses the debounce and waits for the in-flight call to settle. */
  async flush(): Promise<void> {
    if (this.#timer !== null) {
      clearTimeout(this.#timer);
      this.#timer = null;
      if (this.#lastReq) this.#inFlight = this.#run(this.#lastReq);
    }
    if (this.#inFlight) await this.#inFlight;
  }

  dispose(): void {
    this.#disposed = true;
    if (this.#timer !== null) {
      clearTimeout(this.#timer);
      this.#timer = null;
    }
    if (this.#controller) {
      this.#controller.abort();
      this.#controller = null;
    }
    // Clears pending HERE rather than leaving it to #run's finally: nulling #controller
    // above makes that block's `this.#controller === controller` guard false, so the
    // in-flight run never clears the flag and a disposed client stays pending forever.
    this.pending = false;
  }

  async #run(req: ScheduleRequest): Promise<void> {
    if (this.#controller) this.#controller.abort();
    const controller = new AbortController();
    this.#controller = controller;
    this.pending = true;
    const apiPromise = postSchedule(req, controller.signal);
    apiPromise.catch(() => {}); // avoid an unhandled rejection when the abort race wins instead
    try {
      const result = await Promise.race([apiPromise, abortRejection(controller.signal)]);
      if (controller.signal.aborted) return;
      if (!isNonIncreasing(result.sigmas)) {
        this.error = "schedule sigmas are not non-increasing";
        this.result = null;
        this.#lastResultReq = req;
        return;
      }
      this.#cache.set(scheduleKey(req), result);
      this.result = result;
      this.error = null;
      this.#lastResultReq = req;
    } catch (e) {
      if (controller.signal.aborted || e instanceof AbortedError) return;
      // Any Error's own message, not just a ForgeApiError's: `String(e)` on a plain
      // Error yields "Error: render server unreachable", and the note the SIGMA column
      // shows is meant to read as the server's sentence, not as a stringified throw.
      this.error = e instanceof Error ? e.message : String(e);
    } finally {
      if (this.#controller === controller) {
        this.pending = false;
        this.#controller = null;
      }
    }
  }
}

/**
 * The milestone's one client, a module singleton exactly as `settings` and `view` are.
 * Task 10's SigmaColumn is the only thing that calls `request()` -- it is the component that
 * knows the target's steps, the tab's LENGTH and the A2A sigma max. Task 11's ADVANCED
 * SAMPLING only READS `scheduleClient.result?.sigmas` to render the CFG interval's STEPS unit;
 * a second client there would answer "which step does progress 0.7 reach" from a different
 * array than the graph drew, which is the one thing spec 5.3 forbids.
 */
export const scheduleClient = new ScheduleClient();
