import { describe, expect, it } from "vitest";
import { BLEND_IDEAS, blendIdea, loraWire } from "../registry";

const CURVE = Array.from({ length: 24 }, (_, i) => (i < 12 ? 1 : 0.5));

describe("blend registry", () => {
  it("has amount and direction, in that order", () => {
    expect(BLEND_IDEAS.map((b) => b.id)).toEqual(["amount", "direction"]);
  });
  it("amount is true interpolation with the base, direction is the stock per-block strength", () => {
    expect(blendIdea("amount").toWire(CURVE)).toEqual({ block_strengths: CURVE, blend: "interp" });
    expect(blendIdea("direction").toWire(CURVE)).toEqual({ block_strengths: CURVE });
  });
  it("copies the curve (the wire never aliases the live $state array)", () => {
    const w = blendIdea("amount").toWire(CURVE);
    expect(w.block_strengths).not.toBe(CURVE);
  });
  it("direction's help warns about the DoRA zero jump", () => {
    expect(blendIdea("direction").help).toContain("exact 0");
  });
});

describe("loraWire", () => {
  it("is today's lora object when there is no blend or it is off", () => {
    expect(loraWire({ ckpt_path: "/a", slot: 2, strength: 0.7 })).toEqual({ ckpt_path: "/a", slot: null, strength: 0.7 });
    expect(loraWire({ ckpt_path: "/a", slot: 2, strength: 0.7, blend: { on: false, mode: "amount", curve: CURVE } }))
      .toEqual({ ckpt_path: "/a", slot: null, strength: 0.7 });
  });
  it("sends strength 1 and the curve when blending (the curve IS the strength)", () => {
    expect(loraWire({ ckpt_path: "/a", slot: 2, strength: 0.7, blend: { on: true, mode: "amount", curve: CURVE } }))
      .toEqual({ ckpt_path: "/a", slot: null, strength: 1, block_strengths: CURVE, blend: "interp" });
  });
});
