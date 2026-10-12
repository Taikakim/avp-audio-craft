import { describe, expect, it } from "vitest";
import { xcorrColor, XCORR_NEG, XCORR_POS, XCORR_ZERO } from "../xcorrColor";

function oklch(t: { l: number; c: number; h: number }): string {
  return `oklch(${t.l.toFixed(2)}% ${t.c.toFixed(3)} ${t.h.toFixed(1)})`;
}

describe("xcorrColor builds its own oklch() string, never a getComputedStyle read (HANDOUT.md)", () => {
  it("is neutral -- near-zero chroma -- at zero", () => {
    expect(xcorrColor(0)).toBe(oklch(XCORR_ZERO));
  });

  it("reaches the negative pole at -1", () => {
    expect(xcorrColor(-1)).toBe(oklch(XCORR_NEG));
  });

  it("reaches the positive pole at +1", () => {
    expect(xcorrColor(1)).toBe(oklch(XCORR_POS));
  });

  it("differs in hue between the two poles, not only lightness", () => {
    expect(XCORR_NEG.h).not.toBe(XCORR_POS.h);
    expect(xcorrColor(-1)).not.toBe(xcorrColor(1));
  });

  it("clamps outside -1..1 to the nearest pole", () => {
    expect(xcorrColor(5)).toBe(xcorrColor(1));
    expect(xcorrColor(-5)).toBe(xcorrColor(-1));
  });

  it("treats a non-finite value as zero rather than throwing or emitting NaN", () => {
    expect(xcorrColor(Number.NaN)).toBe(xcorrColor(0));
  });

  it("returns a literal oklch() string, never a var() reference to a custom property", () => {
    expect(xcorrColor(0.3).startsWith("oklch(")).toBe(true);
    expect(xcorrColor(0.3)).not.toContain("var(");
  });
});
