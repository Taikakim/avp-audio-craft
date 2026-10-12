import { describe, expect, it } from "vitest";
import { clipLabel, overlapInfoLine } from "../overlapLabel";
import type { ForgeClip } from "../types";

function clip(over: Partial<ForgeClip> & { audio: ForgeClip["audio"] }): ForgeClip {
  return {
    id: "clip_x", lane: 0, start_sec: 0, offset_sec: 0, dur_sec: 4, loop: false,
    native_bpm: null, detune_cents: 0, downbeats_sec: [], latentState: "none", history: [],
    a2a: null, previewAudio: null, op: null,   // required on ForgeClip since M5 T10 (in-memory only)
    render: {} as ForgeClip["render"],
    ...over,
  };
}

describe("clipLabel picks a readable name per AudioRef kind (spec §6.1)", () => {
  it("crop -> the crop id", () => {
    expect(clipLabel(clip({ audio: { kind: "crop", crop_id: "000412" } }))).toBe("000412");
  });
  it("render -> the file", () => {
    expect(clipLabel(clip({ audio: { kind: "render", job_id: "forge-1", file: "out_00.wav" } }))).toBe("out_00.wav");
  });
  it("file -> the last path segment of rel", () => {
    expect(clipLabel(clip({ audio: { kind: "file", root: "crops", rel: "a/b/kick.wav" } }))).toBe("kick.wav");
  });
  it("path -> the last path segment", () => {
    expect(clipLabel(clip({ audio: { kind: "path", path: "/SERVER/out/x.wav" } }))).toBe("x.wav");
  });
  it("upload -> the first 8 chars of the sha256", () => {
    expect(clipLabel(clip({ audio: { kind: "upload", sha256: "a".repeat(64) } }))).toBe("aaaaaaaa");
  });
  it("undefined clip -> a fixed placeholder, never throws", () => {
    expect(clipLabel(undefined)).toBe("?");
  });
});

describe("overlapInfoLine (spec §4.6.1: which overlap, its two clip names)", () => {
  it("names the lane, both clips and the mask window in seconds", () => {
    const a = clip({ id: "clip_a", audio: { kind: "crop", crop_id: "000100" } });
    const b = clip({ id: "clip_b", audio: { kind: "crop", crop_id: "000200" } });
    const line = overlapInfoLine({ lane: 1, start_sec: 10, end_sec: 12.5 }, a, b);
    expect(line).toBe("lane 2 · 000100 → 000200 · mask 10.00–12.50 s");
  });

  it("falls back to the placeholder name when a clip cannot be found", () => {
    const line = overlapInfoLine({ lane: 0, start_sec: 0, end_sec: 1 }, undefined, undefined);
    expect(line).toBe("lane 1 · ? → ? · mask 0.00–1.00 s");
  });
});
