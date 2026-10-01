// The chroma data layer (spec §6.3, §5.4): POST /forge/chroma, decoded on
// arrival so no component ever sees base64 or a raw quantised byte.
//
// THE QUANTISATION IS NOT UNIFORM. §6.3 dequantises every byte as
// byte/255*scale, but `bands` carries THREE scales -- one per band, applied to
// that band's own 128*T slice of the C-order stream -- while `fold12` carries
// exactly one for the whole array. Using scale[0] everywhere mis-scales two
// thirds of the data and looks entirely plausible on screen.
//
// Singleton: the heatmap, the match curve, the scan strip and the clip score
// label are separate components reading the same analysis of the same clip.
// It also keeps a per-AudioRef cache. The server caches on the audio file's
// sha256, but the pane re-reads on every selection change and a cache miss
// still costs a round trip, so the decoded result is kept here too.
//
// Two traps, both paid for elsewhere in this project:
//  1. An "abort" listener added after its signal has already fired never runs,
//     so every abort path checks `signal.aborted` FIRST. Without it the
//     promise never settles and the test hangs green.
//  2. A singleton's cache outlives a component unmount -- and a test file.
//     Every test must vary its input or call dispose().

import { forgeApi, ForgeApiError } from "../forge/api";
import type { AudioRef } from "../forge/types";
import { decodeBase64, dequantiseScaled } from "../stats/decode";
import { BANDS, BINS_PER_BAND } from "./bins";

export interface ChromaResult {
  /** T, the number of latent frames the server analysed. */
  frames: number;
  /** 10.7666015625 = 44100/4096 (spec §6.3). */
  fps: number;
  /** 3*128*T, C order: value(band, bin, frame) = bands[(band*128 + bin)*T + frame]. */
  bands: Float32Array;
  /** 12*T, C order: value(class, frame) = fold12[class*T + frame]. */
  fold12: Float32Array;
  /** Same as `frames`; named T because every geometry expression uses it that way. */
  T: number;
}

export class ChromaShapeError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ChromaShapeError";
  }
}

type ChromaResponse = {
  ok: true;
  frames: number;
  fps: number;
  bands: { shape: [number, number, number]; scale: [number, number, number]; data_b64: string };
  fold12: { shape: [number, number]; scale: number; data_b64: string };
};

/**
 * A stable cache key for any AudioRef (spec §6.1's five kinds). Built from the
 * fields rather than JSON.stringify, whose output depends on the order the
 * caller happened to write the object literal in.
 */
export function chromaRefKey(ref: AudioRef): string {
  switch (ref.kind) {
    case "upload": return `upload:${ref.sha256}`;
    case "render": return `render:${ref.job_id}:${ref.file}`;
    case "crop":   return `crop:${ref.crop_id}`;
    case "file":   return `file:${ref.root}:${ref.rel}`;
    case "path":   return `path:${ref.path}`;
  }
}

function decodeChroma(res: ChromaResponse): ChromaResult {
  const T = res.frames;
  const [nBands, nBins, tBands] = res.bands.shape;
  const [nClasses, tFold] = res.fold12.shape;
  if (nBands !== BANDS || nBins !== BINS_PER_BAND || tBands !== T || nClasses !== 12 || tFold !== T) {
    throw new ChromaShapeError(
      `chroma: expected bands [3,128,${T}] and fold12 [12,${T}], got [${res.bands.shape}] and [${res.fold12.shape}]`,
    );
  }

  const bandBytes = decodeBase64(res.bands.data_b64);
  const per = BINS_PER_BAND * T;
  if (bandBytes.length !== BANDS * per) {
    throw new ChromaShapeError(
      `chroma: expected ${BANDS * per} bytes for bands [3,128,${T}], got ${bandBytes.length}`,
    );
  }
  // One scale per band, each applied to that band's own slice. dequantiseScaled
  // is M10 T1's -- built there for exactly this reuse.
  const bands = new Float32Array(BANDS * per);
  for (let b = 0; b < BANDS; b++) {
    bands.set(dequantiseScaled(bandBytes.subarray(b * per, (b + 1) * per), res.bands.scale[b]), b * per);
  }

  const foldBytes = decodeBase64(res.fold12.data_b64);
  if (foldBytes.length !== 12 * T) {
    throw new ChromaShapeError(
      `chroma: expected ${12 * T} bytes for fold12 [12,${T}], got ${foldBytes.length}`,
    );
  }
  const fold12 = dequantiseScaled(foldBytes, res.fold12.scale);

  return { frames: T, fps: res.fps, bands, fold12, T };
}

/**
 * signal-aware wrapper around a promise forgeApi cannot itself cancel (none of
 * its methods takes an AbortSignal). The underlying fetch keeps running; its
 * result is discarded by the `signal.aborted` guards below.
 */
function raceAbort<T>(promise: Promise<T>, signal: AbortSignal): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    // Check FIRST -- a listener added after the signal fired never runs.
    if (signal.aborted) {
      reject(new DOMException("chroma request superseded", "AbortError"));
      return;
    }
    const onAbort = () => reject(new DOMException("chroma request superseded", "AbortError"));
    signal.addEventListener("abort", onAbort, { once: true });
    promise.then(
      (v) => { signal.removeEventListener("abort", onAbort); resolve(v); },
      (e) => { signal.removeEventListener("abort", onAbort); reject(e); },
    );
  });
}

function errorMessage(err: unknown): string {
  if (err instanceof ForgeApiError) return err.message;
  if (err instanceof ChromaShapeError) return err.message;
  return String(err);
}

export class ChromaClient {
  result = $state<ChromaResult | null>(null);
  pending = $state(false);
  error = $state<string | null>(null);

  #controller: AbortController | null = null;
  #inFlight: Promise<void> | null = null;
  #cache = new Map<string, ChromaResult>();

  /**
   * Analyse one clip's audio. §5.4: the caller passes the clip's STRETCHED
   * preview audio (`ForgeClip.previewAudio ?? ForgeClip.audio`), not the raw
   * source, so the chroma matches what the timeline plays.
   */
  request(audio: AudioRef): Promise<void> {
    const key = chromaRefKey(audio);
    const cached = this.#cache.get(key);
    if (cached) {
      this.#controller?.abort();       // a cache hit supersedes anything in flight
      this.#controller = null;
      this.result = cached;
      this.pending = false;
      this.error = null;
      return Promise.resolve();
    }

    this.#controller?.abort();
    const controller = new AbortController();
    this.#controller = controller;
    this.pending = true;
    this.error = null;

    const run = (async () => {
      try {
        const res = await raceAbort(forgeApi.chroma(audio), controller.signal);
        if (controller.signal.aborted) return;   // superseded while in flight
        const decoded = decodeChroma(res as ChromaResponse);
        this.#cache.set(key, decoded);
        this.result = decoded;
      } catch (err) {
        if (controller.signal.aborted) return;
        this.error = errorMessage(err);
      } finally {
        if (this.#controller === controller) {
          this.pending = false;
          this.#controller = null;
        }
      }
    })();
    this.#inFlight = run;
    return run;
  }

  /** Await whatever is in flight. Used by tests and by a caller that needs
   *  `result` settled before it reads it. */
  async flush(): Promise<void> {
    if (this.#inFlight) await this.#inFlight;
  }

  /** Abort anything in flight, clear every field AND the cache. Required
   *  between tests that reuse the singleton, and on leaving the tab. */
  dispose(): void {
    this.#controller?.abort();
    this.#controller = null;
    this.#inFlight = null;
    this.#cache.clear();
    this.result = null;
    this.pending = false;
    this.error = null;
  }
}

/** One client for the whole CHROMA tab (spec §4.5, §5.4). */
export const chromaClient = new ChromaClient();
