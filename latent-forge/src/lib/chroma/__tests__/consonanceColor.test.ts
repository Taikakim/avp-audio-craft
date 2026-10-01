import { describe, expect, it } from "vitest";
import {
  CELL_C_BASE,
  CELL_C_SPAN,
  CELL_L_SPAN,
  CELL_L_TOP,
  CONSONANT_HUE,
  DISSONANT_HUE,
  LEGEND_C,
  LEGEND_L,
  LEGEND_STOPS,
  TARGET_ROW_HUE,
  consonanceColor,
  consonanceHue,
  legendColor,
  targetRowColor,
} from "../consonanceColor";

describe("consonanceHue (v3 _drawChroma 1186: hue = 60 + (1 - match) * 200)", () => {
  it("is the consonant hue at a perfect match and the dissonant hue at zero", () => {
    expect(consonanceHue(1)).toBe(CONSONANT_HUE);
    expect(consonanceHue(0)).toBe(DISSONANT_HUE);
    expect(DISSONANT_HUE - CONSONANT_HUE).toBe(200);
  });

  it("clamps outside 0..1 rather than running off the hue circle", () => {
    expect(consonanceHue(-3)).toBe(DISSONANT_HUE);
    expect(consonanceHue(9)).toBe(CONSONANT_HUE);
    expect(consonanceHue(Number.NaN)).toBe(DISSONANT_HUE);
  });
});

describe("consonanceColor builds its own oklch() string (HANDOUT.md ramp exception)", () => {
  it("never reads a token: the string is assembled from the named constants", () => {
    expect(consonanceColor(0, 1)).toBe(
      `oklch(${CELL_L_TOP.toFixed(2)}% ${CELL_C_BASE.toFixed(3)} ${CONSONANT_HUE.toFixed(1)})`,
    );
  });

  it("darkens and saturates with the cell's own value", () => {
    expect(consonanceColor(1, 1)).toBe(
      `oklch(${(CELL_L_TOP - CELL_L_SPAN).toFixed(2)}% ${(CELL_C_BASE + CELL_C_SPAN).toFixed(3)} ${CONSONANT_HUE.toFixed(1)})`,
    );
  });

  it("moves hue with the FRAME's match and lightness with the CELL's value", () => {
    expect(consonanceColor(0.5, 0)).not.toBe(consonanceColor(0.5, 1));
    expect(consonanceColor(0.5, 0.5)).toBe("oklch(70.00% 0.115 160.0)");
  });
});

describe("targetRowColor (the reference row across the top, v3 1178)", () => {
  it("uses its own purple hue, so the target never reads as a score", () => {
    expect(targetRowColor(1)).toContain(`${TARGET_ROW_HUE.toFixed(1)})`);
    expect(targetRowColor(0)).toContain(`${TARGET_ROW_HUE.toFixed(1)})`);
    expect(targetRowColor(1)).not.toBe(consonanceColor(1, 1));
  });
});

describe("legendColor (the gradient strip's nine stops, v3 2025-2028)", () => {
  it("walks the same hue axis as the cells, at one fixed lightness and chroma", () => {
    expect(legendColor(0)).toBe(
      `oklch(${LEGEND_L.toFixed(2)}% ${LEGEND_C.toFixed(3)} ${DISSONANT_HUE.toFixed(1)})`,
    );
    expect(legendColor(1)).toBe(
      `oklch(${LEGEND_L.toFixed(2)}% ${LEGEND_C.toFixed(3)} ${CONSONANT_HUE.toFixed(1)})`,
    );
  });

  it("is nine distinct stops wide, as the drawing draws it", () => {
    expect(LEGEND_STOPS).toBe(9);
    const stops = Array.from({ length: LEGEND_STOPS }, (_, i) => legendColor(i / (LEGEND_STOPS - 1)));
    expect(new Set(stops).size).toBe(LEGEND_STOPS);
  });
});
