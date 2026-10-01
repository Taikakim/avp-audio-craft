import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { HELP } from "../strings";

const SOURCE = fileURLToPath(new URL("../strings.ts", import.meta.url));

describe("the extractor captured the whole drawing", () => {
  it("has the 80 handoff strings plus the 14 new controls (fix wave 2026-09-29 added 7 more; M7 T2 added 13)", () => {
    expect(Object.keys(HELP)).toHaveLength(114);
  });

  it("has no empty string", () => {
    for (const [id, text] of Object.entries(HELP)) {
      expect(text.length, `HELP.${id} is empty`).toBeGreaterThan(10);
    }
  });
});

describe("strings taken verbatim from the drawing", () => {
  it("keeps PROJECT BPM", () => {
    expect(HELP.projectBpm).toBe(
      "Project tempo. Every clip is stretched from its native BPM to this, and the grid is drawn from it. Safe value: MATCH BPM sets it to the mean of the loaded clips, which is the least stretch for all of them. Drag to scale; hold shift for 1/100th detail.",
    );
  });

  it("keeps SNAP", () => {
    expect(HELP.snapMode).toBe(
      "Snap resolution for dragging clips. DOWNBEATS is magnetic — a dragged clip's downbeats jump to another clip's within 5px, and dragging further pulls them free again. CLIP EDGES snaps to the start or end of any clip.",
    );
  });

  it("keeps MATCH BPM", () => {
    expect(HELP.matchBpm).toBe(
      "Least-work tempo match: the clips meet at their mean native BPM, so each is stretched as little as possible. Does not move anything in time.",
    );
  });

  it("keeps the ruler", () => {
    expect(HELP.ruler).toBe(
      "Ruler: bars and beats, seconds, and latent frames at 10.767 Hz. Click to locate the playhead. Middle-click and drag to zoom (up/down) and scroll (left/right) at once.",
    );
  });

  it("keeps SEED and RND", () => {
    expect(HELP.seed).toBe(
      "RNG seed for the initial noise. Same seed, same settings, same result. Safe value: any integer, or RND for a fresh one — there is no wrong seed.",
    );
    expect(HELP.seedRandom).toBe("New random seed.");
  });

  it("keeps LATENT NORMALISE", () => {
    expect(HELP.latentNormalise).toBe(
      "Renormalises the mixed latent to the distribution the decoder expects. Mixing two latents shrinks their norm, so leaving this off tends to give a quiet, dull decode. Safe value: on.",
    );
  });

  it("keeps the LatCH slot START % window note", () => {
    expect(HELP.latchStartPct).toBe(
      "Window start as a fraction of the step schedule. Each slot gets its own colour and its own lane on the sigma graph; hatching marks where the window overlaps the CFG-active region.",
    );
  });

  it("keeps the mix-order note", () => {
    expect(HELP.mixOrder).toBe(
      "slerp is defined pairwise, so a 4-way mix runs as a tree of pairwise slerps. WEIGHTED 4-WAY mixes all four lanes at once but is lerp-only.",
    );
  });
});

describe("the fourteen strings spec §9.4 requires rewritten, plus the fix-wave reconciliation", () => {
  it("rewrites all of them away from the handoff wording", () => {
    const rewritten = [
      "steps", "cfg", "modelStagePost", "modelStageBase", "sampler", "scheduleShape",
      "sigmaMin", "sigmaMax", "a2aNoise", "length", "latchWeight", "latchRho",
      "latchMu", "latchTargetKind",
    ] as const;
    for (const id of rewritten) {
      expect(HELP[id].length, `HELP.${id} missing`).toBeGreaterThan(40);
    }
  });

  it("STEPS quotes this build's defaults, not the v/eps ones", () => {
    expect(HELP.steps).toContain("8 for POST");
    expect(HELP.steps).toContain("24 for BASE");
    expect(HELP.steps).not.toContain("100 for v/eps models");
  });

  it("CFG says POST ignores it and states the 0-64 range", () => {
    expect(HELP.cfg).toContain("POST ignores it");
    expect(HELP.cfg).toContain("0–64");
  });

  it("LENGTH states the 184 s cap and drops the 6 min 20 s ceiling", () => {
    expect(HELP.length).toContain("184 s");
    expect(HELP.length).not.toContain("6 min 20 s");
  });

  it("SAMPLER offers rectified-flow samplers only and names the LatCH forcing", () => {
    expect(HELP.sampler).toContain("pingpong");
    expect(HELP.sampler).toContain("forces euler");
    expect(HELP.sampler).not.toContain("k-diffusion set");
  });

  it("A2A NOISE states the 0-1 range and drops the 0.1-100 v/eps scale", () => {
    expect(HELP.a2aNoise).toContain("0–1");
    expect(HELP.a2aNoise).not.toContain("0.1–100");
  });

  it("the target-kind list drops chroma_major / chroma_minor", () => {
    expect(HELP.latchTargetKind).toContain("beat_grid");
    expect(HELP.latchTargetKind).toContain("not offered here");
  });

  it("SHAPE names MODEL as the default and the array-upload rule", () => {
    expect(HELP.scheduleShape).toContain("MODEL is the checkpoint's own schedule");
    expect(HELP.scheduleShape).toContain("explicit sigma array");
  });

  it("keeps every rewritten original in a handoff comment beside it", () => {
    const src = readFileSync(SOURCE, "utf8");
    // 14 from spec §9.4 + 1 more (`model`) reconciled in the 2026-09-29 fix wave, see below.
    expect(src.match(/\/\/ handoff: "/g) ?? []).toHaveLength(15);
    expect(src).toContain(
      '// handoff: "Number of denoising steps. More steps cost time and give diminishing returns. Safe value: 100 for v/eps models, 50 for rectified_flow, 8 for rf_denoiser. Drag to scale; hold shift for 1/100th detail."',
    );
  });

  it("MODEL was reconciled to TopBar's live text (fix wave 2026-09-29, finding #4)", () => {
    // Task 14's extractor and TopBar.svelte's inline data-help had already drifted -- TopBar's
    // was more likely what users actually saw, so it won and is now what the drawing's raw text
    // gets rewritten to. Confirms the drift-added sentence is present and it's still marked as
    // a rewrite (handoff comment retained above it in strings.ts).
    expect(HELP.model).toContain("The first four entries are backbones");
  });
});

describe("new controls this build has and the drawing did not", () => {
  it("covers transport, DARK, FiLM TARGET, OP and PREVIEW/MIXDOWN", () => {
    for (const id of [
      "transportPlay", "transportStop", "transportLoop", "darkToggle",
      "filmTarget", "opSelect", "previewMixdownToggle",
    ] as const) {
      expect(HELP[id].length, `HELP.${id} missing`).toBeGreaterThan(20);
    }
    expect(HELP.transportPlay).toContain("Space");
  });

  it("DARK was reconciled to TopBar's live text (fix wave 2026-09-29, finding #4)", () => {
    // Was "Dark theme. It re-maps lightness ... remembered in this browser." (generated) vs
    // "Light or dark ground. ... kept in this browser." (TopBar's live inline literal) -- fully
    // different wording, not just a drifted sentence. TopBar's live text won, same rationale as
    // MODEL above.
    expect(HELP.darkToggle).toContain("kept in this browser");
    expect(HELP.darkToggle).toContain("the ruler and the sigma graph follow it too");
  });

  it("covers the 7 controls the fix wave found with no HELP entry at all (MixdownSlot x2, PreviewContainer x5)", () => {
    for (const id of [
      "mixdownCommit", "mixdownWave", "previewRender", "previewHistory",
      "previewDragToLane", "previewUseSettings", "previewReplaceClip",
    ] as const) {
      expect(HELP[id].length, `HELP.${id} missing`).toBeGreaterThan(20);
    }
  });
});
