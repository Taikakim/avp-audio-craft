import { describe, expect, it } from "vitest";
import { BASE_DEFAULTS, CHAIN_DEFAULTS, MASTER_DEFAULT, MIX_DEFAULT } from "../defaults";
import { convertProjectV1 } from "../convertProjectV1";

function v1Base() {
  return {
    version: 1,
    meter: { bpm: 128, beatsPerBar: 4 },
    snap: "beat",
    pxPerSec: 90,
    lanes: [
      { id: "drums", label: "Drums", color: "var(--purple)", muted: false, solo: false, gain: 1 },
      { id: "bass", label: "Bass", color: "var(--green)", muted: true, solo: false, gain: 0.8 },
      { id: "other", label: "Other", color: "var(--accent)", muted: false, solo: false, gain: 1 },
      { id: "vocals", label: "Vocals", color: "var(--neutral-lane)", muted: false, solo: true, gain: 1 },
    ],
    clips: [] as unknown[],
  };
}

describe("lanes: drums/bass/other/vocals -> LANE 1..4 (spec 867-869)", () => {
  it("maps ids to indices 0-3 and names LANE n, keeping mute/solo/gain, seeding CHAIN_DEFAULTS", () => {
    const out = convertProjectV1(v1Base());
    expect(out.lanes.map((l) => l.index)).toEqual([0, 1, 2, 3]);
    expect(out.lanes.map((l) => l.name)).toEqual(["LANE 1", "LANE 2", "LANE 3", "LANE 4"]);
    expect(out.lanes[1].muted).toBe(true);
    expect(out.lanes[1].gain).toBe(0.8);
    expect(out.lanes[3].solo).toBe(true);
    for (const lane of out.lanes) expect(lane.chain).toEqual(CHAIN_DEFAULTS);
  });
});

describe("snap: off -> free, digits or 1/n pass through as 1/n (M5's own table cites bare digits; the real v1 SnapMode, musictime.ts:52, already spells 1/8 -- both are handled)", () => {
  it("off -> free", () => {
    expect(convertProjectV1({ ...v1Base(), snap: "off" }).snap).toBe("free");
  });
  it("1/8 (the real v1 spelling) passes through unchanged", () => {
    expect(convertProjectV1({ ...v1Base(), snap: "1/8" }).snap).toBe("1/8");
  });
  it("a bare-digit spelling, if ever encountered, still maps to 1/n", () => {
    expect(convertProjectV1({ ...v1Base(), snap: "16" }).snap).toBe("1/16");
  });
  it("bar/beat/edge pass through unchanged", () => {
    expect(convertProjectV1({ ...v1Base(), snap: "edge" }).snap).toBe("edge");
  });
  it("an unrecognised value falls back to the arrangement store's own default, lane", () => {
    expect(convertProjectV1({ ...v1Base(), snap: "nonsense" }).snap).toBe("lane");
  });
});

describe("clips: crop and render sources convert; empty and audio-file are dropped unless v1 recorded a serverPath", () => {
  it("a crop clip converts with defaults filled into render", () => {
    const out = convertProjectV1({
      ...v1Base(),
      clips: [{
        id: "clip_1", laneId: "bass", startSec: 4, durationSec: 8, offsetSec: 0,
        source: { kind: "crop", cropId: "000412" }, latentState: "valid",
        bpm: 140, downbeatSec: 0.3,
        render: { op: "decode", prompt: "warm pad", negativePrompt: "vocals", steps: 30, cfgScale: 5, seed: 7, noiseLevel: 0.4 },
      }],
    });
    expect(out.clips).toHaveLength(1);
    const c = out.clips[0];
    expect(c.lane).toBe(1);
    expect(c.audio).toEqual({ kind: "crop", crop_id: "000412" });
    expect(c.start_sec).toBe(4);
    expect(c.dur_sec).toBe(8);
    expect(c.native_bpm).toBe(140);
    expect(c.downbeats_sec).toEqual([0.3]);
    expect(c.detune_cents).toBe(0);
    expect(c.loop).toBe(false);
    expect(c.a2a).toBeNull();
    expect(c.history).toEqual([]);
    expect(c.render.prompt).toBe("warm pad");
    expect(c.render.negative_prompt).toBe("vocals");
    expect(c.render.steps).toBe(30);
    expect(c.render.cfg_scale).toBe(5);
    expect(c.render.seed).toBe(7);
    // fields v1 never had stay at BASE_DEFAULTS
    expect(c.render.schedule).toEqual(BASE_DEFAULTS.schedule);
    expect(c.render.duration_sec).toBe(8);   // filled from the clip's own duration
  });

  it("a render-sourced clip converts jobId/filename to job_id/file", () => {
    const out = convertProjectV1({
      ...v1Base(),
      clips: [{
        id: "clip_2", laneId: "drums", startSec: 0, durationSec: 5, offsetSec: 0,
        source: { kind: "render", jobId: "forge-1", filename: "out_00.wav" }, latentState: "none",
        render: { op: "generate", prompt: "kick", steps: 24, cfgScale: 6, seed: -1, noiseLevel: 0.4 },
      }],
    });
    expect(out.clips[0].audio).toEqual({ kind: "render", job_id: "forge-1", file: "out_00.wav" });
  });

  it("drops empty and audio-file clips with no serverPath, since v1 itself never durably saved their audio", () => {
    const out = convertProjectV1({
      ...v1Base(),
      clips: [
        { id: "e", laneId: "drums", startSec: 0, durationSec: 4, offsetSec: 0, source: { kind: "empty" }, latentState: "none", render: { op: "generate", prompt: "", steps: 24, cfgScale: 6, seed: -1, noiseLevel: 0.4 } },
        { id: "f", laneId: "drums", startSec: 4, durationSec: 4, offsetSec: 0, source: { kind: "audio-file", name: "x.wav", url: "blob:x" }, latentState: "none", render: { op: "generate", prompt: "", steps: 24, cfgScale: 6, seed: -1, noiseLevel: 0.4 } },
      ],
    });
    expect(out.clips).toHaveLength(0);
  });

  it("keeps an audio-file clip whose v1 serverPath says where the server has its audio, as a path ref", () => {
    const out = convertProjectV1({
      ...v1Base(),
      clips: [{
        id: "g", laneId: "other", startSec: 2, durationSec: 4, offsetSec: 0,
        source: { kind: "audio-file", name: "take.wav", url: "blob:y" },
        serverPath: "/SERVER/renders/take.wav",   // types.ts:150-158 -- a job's file, or typed in
        latentState: "none", render: { op: "generate", prompt: "", steps: 24, cfgScale: 6, seed: -1, noiseLevel: 0.4 },
      }],
    });
    expect(out.clips).toHaveLength(1);
    expect(out.clips[0].audio).toEqual({ kind: "path", path: "/SERVER/renders/take.wav" });
    expect(out.clips[0].lane).toBe(2);
    expect(JSON.stringify(out)).not.toContain("blob:");
  });
});

describe("a v1 file with no mix/master/chain data converts to the defaults per lane, never throws (brief's own rule, generalised)", () => {
  it("fills mix, master and every lane's chain from the M1 defaults", () => {
    const out = convertProjectV1(v1Base());
    expect(out.mix).toEqual(MIX_DEFAULT);
    expect(out.master).toEqual(MASTER_DEFAULT);
  });

  it("never throws on missing lanes/clips or a garbage top level, and fills every ProjectV2 field", () => {
    expect(() => convertProjectV1({})).not.toThrow();
    expect(() => convertProjectV1(null)).not.toThrow();
    expect(() => convertProjectV1("not an object")).not.toThrow();
    const out = convertProjectV1({});
    expect(out.version).toBe(2);
    expect(out.lanes).toHaveLength(4);
    expect(out.clips).toEqual([]);
    expect(out.overlaps).toEqual({});
    expect(out.renders).toEqual([]);
    expect(out.mixdown).toBeNull();
    expect(out.preview).toBeNull();
    expect(out.ui).toEqual({ bottomTab: "prompt", modules: ["files", "lane-chain"], sideOpen: true, terminal: "pane" });
  });
});

describe("previewAudio is never read from v1 (spec 9.2, M5's Normative table)", () => {
  it("ignores a v1 clip's previewUrl entirely: the required ForgeClip.previewAudio is always null", () => {
    const out = convertProjectV1({
      ...v1Base(),
      clips: [{
        id: "clip_3", laneId: "drums", startSec: 0, durationSec: 4, offsetSec: 0,
        source: { kind: "crop", cropId: "000900" }, latentState: "valid",
        previewUrl: "http://example/preview.wav",
        render: { op: "decode", prompt: "", steps: 24, cfgScale: 6, seed: -1, noiseLevel: 0.4 },
      }],
    });
    // ForgeClip.previewAudio is a REQUIRED field (M5 T10: `AudioRef | null`), so "never written"
    // means null, not absent -- the v1 previewUrl must not leak into it or anywhere else.
    expect(out.clips[0].previewAudio).toBeNull();
    expect(JSON.stringify(out)).not.toContain("preview.wav");
  });
});
