import { describe, expect, it } from "vitest";
import { frameAt, LATENT_FPS, secPerBar } from "../../musictime";

describe("vitest harness reaches the existing pure modules", () => {
  it("knows the latent frame rate", () => {
    expect(LATENT_FPS).toBeCloseTo(10.7666015625, 9);
  });

  it("computes the latent frame of a timeline second", () => {
    expect(frameAt(0)).toBe(0);
    expect(frameAt(1)).toBe(10);
    expect(frameAt(92.8 / 1000)).toBe(0);
  });

  it("computes a bar length from the meter", () => {
    expect(secPerBar({ bpm: 120, beatsPerBar: 4 })).toBeCloseTo(2, 12);
  });
});
