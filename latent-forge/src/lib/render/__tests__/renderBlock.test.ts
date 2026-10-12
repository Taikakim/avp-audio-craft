import { describe, expect, it } from "vitest";
import { BASE_DEFAULTS, cloneRenderSettings } from "../../forge/defaults";
import type { ForgeClip, RenderSettings, Target } from "../../forge/types";
import { CAP_SEC } from "../payloads";
import { renderBlock, type RenderBlockState } from "../renderBlock";

const CROP = { kind: "crop", crop_id: "000412" } as const;
const UPLOAD = { kind: "upload", sha256: "a".repeat(64) } as const;

function clip(patch: Partial<ForgeClip> = {}): ForgeClip {
  return {
    id: "c1", lane: 0, start_sec: 0, offset_sec: 0, dur_sec: 8, loop: false, audio: UPLOAD,
    native_bpm: 120, detune_cents: 0, downbeats_sec: [], render: cloneRenderSettings(BASE_DEFAULTS),
    a2a: null, latentState: "none", history: [], ...patch,
  } as ForgeClip;
}

function state(patch: Partial<RenderBlockState> = {}): RenderBlockState {
  return {
    busy: false, gpuBusyOther: null,
    settings: { ...cloneRenderSettings(BASE_DEFAULTS), prompt: "dub", duration_sec: 45 } as RenderSettings,
    clip: null, clipOp: null, arcPrompt: "", bendOpCount: 0,
    overlapSpanSec: 4, padSec: 8, ...patch,
  };
}

const NONE: Target = { kind: "none" };
const CLIP: Target = { kind: "clip", id: "c1" };
const OVERLAP: Target = { kind: "overlap", key: "a-b" };

describe("renderBlock -- §9.7's blocked-target reasons, extended to M9's ops", () => {
  it("blocks everything while a job runs (§7.1)", () => {
    expect(renderBlock(NONE, state({ busy: true }))).toBe("a render is already running");
  });

  it("reports a GPU held by another job first, in §9.7's exact words", () => {
    expect(renderBlock(NONE, state({ busy: true, gpuBusyOther: "dash-77" }))).toBe("GPU busy — dash-77");
  });

  it("nothing selected: needs a prompt, then nothing", () => {
    expect(renderBlock(NONE, state({ settings: { ...state().settings, prompt: "  " } })))
      .toBe("needs a prompt — /generate requires a non-empty prompt.");
    expect(renderBlock(NONE, state())).toBeNull();
  });

  it("nothing selected: refuses a LENGTH over the 184 s cap", () => {
    const over = { ...state().settings, duration_sec: CAP_SEC + 1 };
    expect(renderBlock(NONE, state({ settings: over }))).toMatch(/184/);
  });

  it("clip with A2A on is never blocked for a prompt -- a2a_clip needs no prompt", () => {
    const c = clip({ a2a: { on: true, noise: 0.4, envelope: null } as unknown as ForgeClip["a2a"] });
    expect(renderBlock(CLIP, state({ clip: c, settings: { ...state().settings, prompt: "" } }))).toBeNull();
  });

  it("clip with A2A off and no op shows §7.1's own hint", () => {
    expect(renderBlock(CLIP, state({ clip: clip(), clipOp: null })))
      .toBe("turn A2A on or choose an op");
  });

  it("clip + decode needs a latent: a crop ref passes, an upload does not", () => {
    expect(renderBlock(CLIP, state({ clip: clip({ audio: CROP }), clipOp: "decode" }))).toBeNull();
    expect(renderBlock(CLIP, state({ clip: clip({ audio: UPLOAD }), clipOp: "decode" })))
      .toBe("no latent to decode — /decode takes crop_id or latent_path.");
  });

  it("clip + bend needs a latent AND at least one op", () => {
    expect(renderBlock(CLIP, state({ clip: clip({ audio: CROP }), clipOp: "bend", bendOpCount: 0 })))
      .toMatch(/no bend ops/);
    expect(renderBlock(CLIP, state({ clip: clip({ audio: CROP }), clipOp: "bend", bendOpCount: 2 }))).toBeNull();
  });

  it("clip + longform needs the arc, not the plain prompt", () => {
    expect(renderBlock(CLIP, state({ clip: clip(), clipOp: "longform", arcPrompt: "" })))
      .toMatch(/arc/);
    expect(renderBlock(CLIP, state({ clip: clip(), clipOp: "longform", arcPrompt: "0:pad|45:bass" }))).toBeNull();
  });

  it("clip + generate still needs a prompt", () => {
    expect(renderBlock(CLIP, state({ clip: clip(), clipOp: "generate", settings: { ...state().settings, prompt: "" } })))
      .toMatch(/needs a prompt/);
  });

  it("overlap: passes normally, refuses a padded span over the cap", () => {
    expect(renderBlock(OVERLAP, state())).toBeNull();
    expect(renderBlock(OVERLAP, state({ overlapSpanSec: 180, padSec: 8 }))).toMatch(/184/);
  });
});
