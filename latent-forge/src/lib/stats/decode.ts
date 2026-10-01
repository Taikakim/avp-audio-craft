// Base64 + quantisation for the statistics contract (spec §6.5) and the
// chroma contract (spec §6.3), kept pure and separate from any fetch so
// vitest can pin exact dequantised numbers without a network mock. Two
// quantisation conventions coexist: xcorr's bytes dequantise as
// byte/255*2-1 (range -1..1, spec §6.5); the chroma bands' (spec §6.3)
// dequantise as byte/255*scale, one scale per band. Both start from the same
// base64 -> Uint8Array decode, so it lives here once rather than twice.

export class XcorrShapeError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "XcorrShapeError";
  }
}

/**
 * `atob`-based decode: works in the browser and under vitest (Node 18+'s
 * global `atob`) alike, with no dependency on Node's `Buffer`, which the
 * browser bundle must never pull in.
 */
export function decodeBase64(b64: string): Uint8Array {
  if (b64.length === 0) return new Uint8Array(0);
  const binary = atob(b64);
  const out = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) out[i] = binary.charCodeAt(i);
  return out;
}

/**
 * Dequantise the xcorr matrix (spec §6.5): `byte/255*2-1`, so the range is
 * -1..1, not 0..1. `bytes` is row-major C order: `cell(r, c) = out[r*n + c]`.
 * Throws when the byte count does not match an n x n matrix -- a caller
 * passing the wrong n is a programmer error, not a value to paper over.
 */
export function dequantiseXcorr(bytes: Uint8Array, n: number): Float32Array {
  if (bytes.length !== n * n) {
    throw new XcorrShapeError(
      `dequantiseXcorr: expected ${n * n} bytes for a ${n}x${n} matrix, got ${bytes.length}`,
    );
  }
  const out = new Float32Array(bytes.length);
  for (let i = 0; i < bytes.length; i++) out[i] = (bytes[i] / 255) * 2 - 1;
  return out;
}

/**
 * Dequantise a scaled band (spec §6.3's chroma bands: `byte/255*scale`, one
 * scale per band). M6 reuses this for the 3x128xT SAME chroma bands -- built
 * here because the base64 + quantisation split belongs with the rest of the
 * decode layer, not duplicated in the chroma tab.
 */
export function dequantiseScaled(bytes: Uint8Array, scale: number): Float32Array {
  const out = new Float32Array(bytes.length);
  for (let i = 0; i < bytes.length; i++) out[i] = (bytes[i] / 255) * scale;
  return out;
}
