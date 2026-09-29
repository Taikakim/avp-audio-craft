import { describe, expect, it } from "vitest";
import { isAudioRef, isEnvelope, isLatentRef, isProgress, targetKey } from "../guards";

describe("AudioRef guard accepts exactly the five kinds of spec §6.1", () => {
  it("accepts each valid kind", () => {
    expect(isAudioRef({ kind: "upload", sha256: "a".repeat(64) })).toBe(true);
    expect(isAudioRef({ kind: "render", job_id: "forge-20260916-120000-1", file: "out_00.wav" })).toBe(true);
    expect(isAudioRef({ kind: "crop", crop_id: "000412" })).toBe(true);
    expect(isAudioRef({ kind: "file", root: "uploads", rel: "a/b.wav" })).toBe(true);
    expect(isAudioRef({ kind: "path", path: "/SERVER/out/x.wav" })).toBe(true);
  });

  it("rejects a file ref that escapes its root", () => {
    expect(isAudioRef({ kind: "file", root: "uploads", rel: "../etc/passwd" })).toBe(false);
  });

  it("rejects unknown kinds and missing fields", () => {
    expect(isAudioRef({ kind: "latent", path: "/x" })).toBe(false);
    expect(isAudioRef({ kind: "crop" })).toBe(false);
    expect(isAudioRef(null)).toBe(false);
    expect(isAudioRef("crop")).toBe(false);
  });
});

describe("LatentRef guard", () => {
  it("accepts crop, path and a nested audio ref", () => {
    expect(isLatentRef({ kind: "crop", crop_id: "000412" })).toBe(true);
    expect(isLatentRef({ kind: "path", path: "/SERVER/out/x.z0.npy" })).toBe(true);
    expect(isLatentRef({ kind: "audio", audio: { kind: "crop", crop_id: "000412" } })).toBe(true);
  });

  it("rejects an audio ref whose payload is not an AudioRef", () => {
    expect(isLatentRef({ kind: "audio", audio: { kind: "nope" } })).toBe(false);
  });
});

describe("Envelope guard enforces the spec §5.2 shape", () => {
  it("accepts 4 points in 0..1 and 3 curves in -1..1", () => {
    expect(isEnvelope({ points: [0, 0.35, 0.7, 1], curves: [0, 0, 0] })).toBe(true);
    expect(isEnvelope({ points: [0.4, 0.4, 0.4, 0.4], curves: [-1, 0.5, 1] })).toBe(true);
  });

  it("rejects wrong arity and out-of-range values", () => {
    expect(isEnvelope({ points: [0, 1, 1], curves: [0, 0, 0] })).toBe(false);
    expect(isEnvelope({ points: [0, 0, 0, 1.2], curves: [0, 0, 0] })).toBe(false);
    expect(isEnvelope({ points: [0, 0, 0, 1], curves: [0, 0, 2] })).toBe(false);
  });
});

describe("Progress guard", () => {
  it("accepts a full progress record", () => {
    expect(
      isProgress({
        job_id: "forge-20260916-120000-1", op: "commit",
        stage: "ENCODE audio → latent", stage_index: 3, stage_count: 9,   // 1-based, 0 = not started
        step: 4, steps: 24, steps_left_total: 44, steps_total: 48,
      }),
    ).toBe(true);
  });

  it("rejects a partial one", () => {
    expect(isProgress({ job_id: "x", op: "commit", stage: "S1" })).toBe(false);
  });
});

describe("targetKey is stable and distinguishes the three target kinds", () => {
  it("names each kind", () => {
    expect(targetKey({ kind: "none" })).toBe("session");
    expect(targetKey({ kind: "clip", id: "clip_a" })).toBe("clip:clip_a");
    expect(targetKey({ kind: "overlap", key: "clip_a-clip_b" })).toBe("overlap:clip_a-clip_b");
  });
});
