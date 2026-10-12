// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { CHROMA_TOKEN_FALLBACK, chromaColour, fitChromaCanvas } from "../chromaCanvas";

afterEach(() => {
  document.body.innerHTML = "";
  vi.restoreAllMocks();
});

describe("chromaColour (HANDOUT.md: in jsdom, seed tokens INLINE, never from a <style> block)", () => {
  it("returns an inline-seeded token exactly", () => {
    const el = document.createElement("div");
    el.style.setProperty("--border", "oklch(80% 0.014 240)");
    document.body.append(el);
    expect(chromaColour(el, "--border")).toBe("oklch(80% 0.014 240)");
  });

  it("falls back per token when the property is undefined, never to the empty string", () => {
    const el = document.createElement("div");
    document.body.append(el);
    // ctx.fillStyle = "" is a SILENT no-op that leaves the previous colour.
    expect(chromaColour(el, "--border")).toBe(CHROMA_TOKEN_FALLBACK["--border"]);
    expect(chromaColour(el, "--border")).not.toBe("");
  });

  it("still returns a visible colour for a token it has never heard of", () => {
    const el = document.createElement("div");
    document.body.append(el);
    expect(chromaColour(el, "--not-a-token").length).toBeGreaterThan(0);
  });
});

describe("fitChromaCanvas", () => {
  it("returns null for a zero-sized canvas rather than painting into nothing", () => {
    const canvas = document.createElement("canvas");
    document.body.append(canvas);
    expect(fitChromaCanvas(canvas)).toBe(null);
  });
});
