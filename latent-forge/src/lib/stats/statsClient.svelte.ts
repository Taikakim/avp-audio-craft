// The statistics data layer (spec §6.5): the two /forge/stats and
// /forge/dataset_scalars calls, decoded on arrival so no component ever sees
// base64 or a raw quantised byte. XcorrPanel and TimeSeriesPanel are separate
// components reading the same analysis, so this is a singleton -- there is
// exactly one "current" stats result and one "current" scalars result for the
// whole statistics view, matching the single ANALYSE action that produces
// them (spec §4.4).
//
// Two traps, both paid for elsewhere in this project (M1 T5's forgeApi.pollJob):
//  1. An "abort" listener added after its signal already fired never runs, so
//     every abort path here checks `signal.aborted` before registering one.
//  2. This is a SINGLETON: its cache outlives any one component's mount. A
//     test that does not vary its input or call dispose() between cases will
//     silently read the previous test's result -- see statsClient.test.ts's
//     last describe block, which exists to make that failure mode visible.
//
// requestStats and requestScalars are independent: /forge/dataset_scalars
// does not take latents or depend on ANALYSE at all (spec §6.5), so the XY
// panel can refresh on its own X/Y select change while a stats analysis is
// still running. Each gets its own AbortController/in-flight promise rather
// than sharing one -- calling one must never supersede the other.

import { forgeApi, ForgeApiError } from "../forge/api";
import type { LatentRef } from "../forge/types";
import { decodeBase64, dequantiseXcorr } from "./decode";

export interface StatsRequest {
  latents: LatentRef[];
  features: string[];
  max_frames?: number;   // spec §6.5 default 20000
  max_points?: number;   // spec §6.5 default 2000
}

export interface StatsResult {
  n_frames: number;
  /** Dequantised in place on arrival (byte/255*2-1); components never see base64. */
  xcorr: Float32Array;
  /** xcorr's side length: xcorr.length === n*n, cell(r, c) = xcorr[r*n + c]. */
  n: number;
  timeseries: { index: number; feature: string; fps: number; values: (number | null)[] }[];
  features_available: string[];
}

export interface DatasetScalars {
  fields: string[];
  points: { crop_id: string; x: number; y: number; label: string }[];
}

/**
 * `signal`-aware wrapper around a promise `forgeApi` itself cannot cancel
 * (none of its methods take an AbortSignal -- only `pollJob`'s own retry loop
 * does). This makes `requestStats`/`requestScalars` settle promptly on
 * supersession or `dispose()` even though the underlying fetch keeps running
 * in the background; its eventual result is simply discarded (see the
 * `signal.aborted` guards below).
 */
function raceAbort<T>(promise: Promise<T>, signal: AbortSignal): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    // Check FIRST: an "abort" listener registered after the signal already
    // fired never runs, so a signal that is already aborted must reject here
    // directly rather than via the listener below.
    if (signal.aborted) {
      reject(new DOMException("stats request superseded", "AbortError"));
      return;
    }
    const onAbort = () => reject(new DOMException("stats request superseded", "AbortError"));
    signal.addEventListener("abort", onAbort, { once: true });
    promise.then(
      (v) => { signal.removeEventListener("abort", onAbort); resolve(v); },
      (e) => { signal.removeEventListener("abort", onAbort); reject(e); },
    );
  });
}

function errorMessage(err: unknown): string {
  return err instanceof ForgeApiError ? err.message : String(err);
}

export class StatsClient {
  result = $state<StatsResult | null>(null);
  pending = $state(false);
  error = $state<string | null>(null);

  scalars = $state<DatasetScalars | null>(null);
  scalarsPending = $state(false);
  scalarsError = $state<string | null>(null);

  #statsController: AbortController | null = null;
  #statsInFlight: Promise<void> | null = null;
  #scalarsController: AbortController | null = null;
  #scalarsInFlight: Promise<void> | null = null;

  /** POST /forge/stats, decoded xcorr on arrival. Superseded by the next call. */
  requestStats(req: StatsRequest): Promise<void> {
    this.#statsController?.abort();
    const controller = new AbortController();
    this.#statsController = controller;
    this.pending = true;
    this.error = null;

    const run = (async () => {
      try {
        const res = await raceAbort(
          forgeApi.stats(req.latents, req.features, req.max_frames, req.max_points),
          controller.signal,
        );
        if (controller.signal.aborted) return; // superseded while in flight
        const n = res.xcorr.shape[0];
        const xcorr = dequantiseXcorr(decodeBase64(res.xcorr.data_b64), n);
        this.result = {
          n_frames: res.n_frames,
          xcorr,
          n,
          timeseries: res.timeseries,
          features_available: res.features_available,
        };
      } catch (err) {
        if (controller.signal.aborted) return;
        this.error = errorMessage(err);
      } finally {
        if (this.#statsController === controller) {
          this.pending = false;
          this.#statsController = null;
        }
      }
    })();
    this.#statsInFlight = run;
    return run;
  }

  /** GET /forge/dataset_scalars. Independent of requestStats (see the header comment). */
  requestScalars(x: string, y: string): Promise<void> {
    this.#scalarsController?.abort();
    const controller = new AbortController();
    this.#scalarsController = controller;
    this.scalarsPending = true;
    this.scalarsError = null;

    const run = (async () => {
      try {
        const res = await raceAbort(forgeApi.datasetScalars(x, y), controller.signal);
        if (controller.signal.aborted) return;
        this.scalars = { fields: res.fields, points: res.points };
      } catch (err) {
        if (controller.signal.aborted) return;
        this.scalarsError = errorMessage(err);
      } finally {
        if (this.#scalarsController === controller) {
          this.scalarsPending = false;
          this.#scalarsController = null;
        }
      }
    })();
    this.#scalarsInFlight = run;
    return run;
  }

  /** Await whatever is currently in flight; used by tests and by a caller
   *  that wants both calls settled before reading `result`/`scalars`. */
  async flush(): Promise<void> {
    const inFlight = [this.#statsInFlight, this.#scalarsInFlight].filter(
      (p): p is Promise<void> => p !== null,
    );
    await Promise.all(inFlight);
  }

  /** Aborts anything in flight and clears every field. Required before every
   *  test that reuses the exported singleton (see the header comment) and by
   *  a real caller leaving the statistics view for a clean slate. */
  dispose(): void {
    this.#statsController?.abort();
    this.#scalarsController?.abort();
    this.#statsController = null;
    this.#scalarsController = null;
    this.#statsInFlight = null;
    this.#scalarsInFlight = null;
    this.result = null;
    this.pending = false;
    this.error = null;
    this.scalars = null;
    this.scalarsPending = false;
    this.scalarsError = null;
  }
}

/** One client for the whole statistics view: XcorrPanel and TimeSeriesPanel
 *  both read `.result`, XYPanel reads `.scalars`, StatisticsView drives both
 *  from a single ANALYSE action (spec §4.4). */
export const statsClient = new StatsClient();
