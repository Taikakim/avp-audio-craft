// Peak extraction and canvas drawing for clip waveforms.
//
// The whole point of the audio-domain preview is seeing whether onsets and
// downbeats line up before committing a latent op, and you cannot see that on
// a flat rectangle. Peaks are min/max per pixel column, computed once per
// (buffer, resolution) and cached -- recomputing on every zoom tick of a
// 45-second stereo buffer is ~4M samples of needless work per frame.

export interface Peaks {
  /** Interleaved [min0, max0, min1, max1, ...] in -1..1, one pair per column. */
  data: Float32Array;
  columns: number;
}

const cache = new Map<string, Peaks>();

function key(url: string, columns: number, fromSec: number, toSec: number): string {
  return `${url}@${columns}:${fromSec.toFixed(3)}-${toSec.toFixed(3)}`;
}

/**
 * Reduce a span of an AudioBuffer to `columns` min/max pairs, mixing channels
 * down. The span matters for trimmed clips: a clip showing 4s out of a 45s
 * render must draw those 4s, not a squashed 45. Columns are capped: past a few
 * thousand there is nothing left to see and the cache starts costing memory.
 */
export function computePeaks(buffer: AudioBuffer, columns: number, fromSec = 0, toSec = Infinity): Peaks {
  const cols = Math.max(1, Math.min(4096, Math.floor(columns)));
  const data = new Float32Array(cols * 2);
  const chans: Float32Array[] = [];
  for (let c = 0; c < buffer.numberOfChannels; c++) chans.push(buffer.getChannelData(c));

  const first = Math.max(0, Math.floor(fromSec * buffer.sampleRate));
  const last = Math.min(buffer.length, Math.ceil(Math.min(toSec, buffer.duration) * buffer.sampleRate));
  const span = Math.max(1, last - first);
  const samplesPerCol = span / cols;

  for (let i = 0; i < cols; i++) {
    const start = first + Math.floor(i * samplesPerCol);
    const end = Math.min(last, first + Math.floor((i + 1) * samplesPerCol));
    let lo = 0;
    let hi = 0;
    for (let s = start; s < end; s++) {
      let v = 0;
      for (let c = 0; c < chans.length; c++) v += chans[c][s];
      v /= chans.length || 1;
      if (v < lo) lo = v;
      if (v > hi) hi = v;
    }
    data[i * 2] = lo;
    data[i * 2 + 1] = hi;
  }
  return { data, columns: cols };
}

export function peaksFor(
  url: string,
  buffer: AudioBuffer,
  columns: number,
  fromSec = 0,
  toSec = Infinity,
): Peaks {
  const clampedTo = Math.min(toSec, buffer.duration);
  const k = key(url, columns, fromSec, clampedTo);
  const hit = cache.get(k);
  if (hit) return hit;
  const peaks = computePeaks(buffer, columns, fromSec, clampedTo);
  cache.set(k, peaks);
  return peaks;
}

export function invalidatePeaks(url: string) {
  for (const k of [...cache.keys()]) if (k.startsWith(`${url}@`)) cache.delete(k);
}

/**
 * Draw peaks filling the canvas. Handles devicePixelRatio so the waveform is
 * crisp on a HiDPI screen instead of a blurry 2x upscale.
 */
export function drawPeaks(
  canvas: HTMLCanvasElement,
  peaks: Peaks,
  color: string,
  opts: { background?: string } = {},
) {
  const dpr = window.devicePixelRatio || 1;
  const cssW = canvas.clientWidth;
  const cssH = canvas.clientHeight;
  if (cssW <= 0 || cssH <= 0) return;
  if (canvas.width !== Math.round(cssW * dpr) || canvas.height !== Math.round(cssH * dpr)) {
    canvas.width = Math.round(cssW * dpr);
    canvas.height = Math.round(cssH * dpr);
  }
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, cssW, cssH);
  if (opts.background) {
    ctx.fillStyle = opts.background;
    ctx.fillRect(0, 0, cssW, cssH);
  }

  const mid = cssH / 2;
  const scale = cssH / 2;
  ctx.fillStyle = color;
  // One rect per pixel column; cheaper and sharper than a stroked path.
  for (let x = 0; x < cssW; x++) {
    const i = Math.min(peaks.columns - 1, Math.floor((x / cssW) * peaks.columns));
    const lo = peaks.data[i * 2];
    const hi = peaks.data[i * 2 + 1];
    const yTop = mid - hi * scale;
    const h = Math.max(1, (hi - lo) * scale);
    ctx.fillRect(x, yTop, 1, h);
  }
  // Centre line, so a near-silent clip still reads as a clip.
  ctx.globalAlpha = 0.35;
  ctx.fillRect(0, mid, cssW, 1);
  ctx.globalAlpha = 1;
}

/**
 * Mix a set of positioned buffers into one buffer, for the master strip.
 * OfflineAudioContext does the summing properly (including sample-rate
 * conversion) instead of us hand-rolling an adder that drifts.
 */
export async function mixdownToBuffer(
  parts: { buffer: AudioBuffer; startSec: number; gain: number }[],
  sampleRate: number,
): Promise<AudioBuffer | null> {
  const audible = parts.filter((p) => p.gain > 0 && p.buffer.length > 0);
  if (!audible.length) return null;
  const totalSec = Math.max(...audible.map((p) => p.startSec + p.buffer.duration));
  if (!Number.isFinite(totalSec) || totalSec <= 0) return null;
  const ctx = new OfflineAudioContext(2, Math.ceil(totalSec * sampleRate), sampleRate);
  for (const part of audible) {
    const src = ctx.createBufferSource();
    src.buffer = part.buffer;
    const g = ctx.createGain();
    g.gain.value = part.gain;
    src.connect(g).connect(ctx.destination);
    src.start(Math.max(0, part.startSec));
  }
  return ctx.startRendering();
}

/** Peak sample value, for a clipping indicator on the master strip. */
export function peakLevel(buffer: AudioBuffer): number {
  let peak = 0;
  for (let c = 0; c < buffer.numberOfChannels; c++) {
    const d = buffer.getChannelData(c);
    for (let i = 0; i < d.length; i += 16) {
      // Stride of 16 -- a true peak scan of a 45s stereo buffer is 4M reads and
      // this only drives a warning badge, not the audio.
      const v = Math.abs(d[i]);
      if (v > peak) peak = v;
    }
  }
  return peak;
}
