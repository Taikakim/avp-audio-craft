import { describe, expect, it } from "vitest";
import { decodeBase64, dequantiseScaled, dequantiseXcorr, XcorrShapeError } from "../decode";

describe("decodeBase64 turns a base64 string into raw bytes", () => {
  it("decodes a small ASCII payload", () => {
    const bytes = decodeBase64(btoa("hi"));
    expect(Array.from(bytes)).toEqual([104, 105]);
  });

  it("returns an empty array for an empty string", () => {
    const bytes = decodeBase64("");
    expect(bytes).toBeInstanceOf(Uint8Array);
    expect(bytes.length).toBe(0);
  });
});

describe("dequantiseXcorr dequantises byte/255*2-1 in row-major C order (spec §6.5)", () => {
  it("throws a named error when the byte count does not match an n x n matrix", () => {
    expect(() => dequantiseXcorr(new Uint8Array(3), 2)).toThrow(XcorrShapeError);
    expect(() => dequantiseXcorr(new Uint8Array(3), 2)).toThrow(/expected 4 bytes/);
  });

  it("maps the endpoints: 0 -> -1, 255 -> +1", () => {
    expect(dequantiseXcorr(new Uint8Array([0]), 1)[0]).toBe(-1);
    expect(dequantiseXcorr(new Uint8Array([255]), 1)[0]).toBe(1);
  });

  it("pins the exact float32 value for byte 128, not a hand-rounded 0.00392", () => {
    const out = dequantiseXcorr(new Uint8Array([128]), 1);
    const expected = Math.fround((128 / 255) * 2 - 1);
    expect(out[0]).toBe(expected);
    expect(out[0]).toBeCloseTo(0.003921568627451, 6);
  });

  it("reads row-major C order: cell(r, c) = out[r*n + c]", () => {
    const n = 2;
    // row 0: [0, 85], row 1: [170, 255]
    const bytes = new Uint8Array([0, 85, 170, 255]);
    const out = dequantiseXcorr(bytes, n);
    const cell = (r: number, c: number) => out[r * n + c];
    expect(cell(0, 0)).toBe(Math.fround((0 / 255) * 2 - 1));
    expect(cell(0, 1)).toBe(Math.fround((85 / 255) * 2 - 1));
    expect(cell(1, 0)).toBe(Math.fround((170 / 255) * 2 - 1));
    expect(cell(1, 1)).toBe(Math.fround((255 / 255) * 2 - 1));
  });
});

describe("dequantiseScaled dequantises byte/255*scale for a given band scale (spec §6.3)", () => {
  it("scales the endpoints and an interior byte by the given scale", () => {
    const out = dequantiseScaled(new Uint8Array([0, 128, 255]), 2.5);
    expect(out[0]).toBe(0);
    expect(out[1]).toBe(Math.fround((128 / 255) * 2.5));
    expect(out[2]).toBe(Math.fround((255 / 255) * 2.5));
  });

  it("returns an empty array for empty bytes, matching decodeBase64('')", () => {
    const out = dequantiseScaled(decodeBase64(""), 1.0);
    expect(out.length).toBe(0);
  });
});
