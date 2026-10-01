import { describe, expect, it } from "vitest";
import { CHAIN_DEFAULTS, MASTER_DEFAULT, MIX_DEFAULT } from "../../forge/defaults";
import { buildSignalPath, type SignalPathInput } from "../signalPath";

function baseInput(): SignalPathInput {
  return {
    lanes: [0, 1, 2, 3].map((i) => ({ index: i as 0 | 1 | 2 | 3, chain: structuredClone(CHAIN_DEFAULTS) })),
    clips: [],
    overlapCount: 0,
    mix: structuredClone(MIX_DEFAULT),
    master: structuredClone(MASTER_DEFAULT),
  };
}

describe("buildSignalPath — the nine §8.1 stages, in order", () => {
  it("returns exactly the nine spec labels, numbered 1-9", () => {
    const stages = buildSignalPath(baseInput());
    expect(stages.map((s) => s.label)).toEqual([
      "DECODE latent → audio", "BUNGEE stretch / pitch", "ENCODE audio → latent",
      "LANE CHAINS", "A2A RE-NOISE", "INPAINT OVERLAPS", "MIX", "MASTER CHAIN",
      "DECODE latent → audio",
    ]);
    expect(stages.map((s) => s.n)).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9]);
  });

  it("with no clips and nothing on, dims every stage except MASTER CHAIN (norm_on defaults true)", () => {
    const stages = buildSignalPath(baseInput());
    expect(stages[0].lit).toBe(false); // S1 DECODE: no crop-ref clips
    expect(stages[1].lit).toBe(false); // S2 BUNGEE
    expect(stages[2].lit).toBe(false); // S3 ENCODE: no clips
    expect(stages[3].lit).toBe(false); // S4 LANE CHAINS
    expect(stages[4].lit).toBe(false); // S5 A2A
    expect(stages[5].lit).toBe(false); // S6 INPAINT OVERLAPS
    expect(stages[6].lit).toBe(false); // S7 MIX: nothing to mix
    expect(stages[7].lit).toBe(true);  // S8 MASTER CHAIN: MASTER_DEFAULT.norm_on is true
    expect(stages[8].lit).toBe(false); // S9 DECODE: nothing to decode
  });

  it("lights S1 DECODE when a clip's audio is a crop ref", () => {
    const input = baseInput();
    input.clips = [{ lane: 0, isCropAudio: true, needsStretch: false, a2aOn: false }];
    expect(buildSignalPath(input)[0].lit).toBe(true);
  });

  it("lights S2 BUNGEE from either a lane's bungee_on or a clip needing stretch", () => {
    const byChain = baseInput();
    byChain.lanes[0].chain.bungee_on = true;
    expect(buildSignalPath(byChain)[1].lit).toBe(true);

    const byStretch = baseInput();
    byStretch.clips = [{ lane: 0, isCropAudio: false, needsStretch: true, a2aOn: false }];
    expect(buildSignalPath(byStretch)[1].lit).toBe(true);
  });

  it("lights S4 LANE CHAINS when any lane has an active feature, and notes idle lanes exactly (spec's own string)", () => {
    const input = baseInput();
    input.lanes[0].chain.latch_on = true;
    // no A2A clip in lane 0 -> idle
    const stages = buildSignalPath(input);
    expect(stages[3].lit).toBe(true);
    expect(stages[3].note).toBe("chain idle — no A2A clip in lane");
  });

  it("clears S4's idle note once the active lane has an A2A clip", () => {
    const input = baseInput();
    input.lanes[0].chain.latch_on = true;
    input.clips = [{ lane: 0, isCropAudio: false, needsStretch: false, a2aOn: true }];
    expect(buildSignalPath(input)[3].note).toBe("");
  });

  it("lights S5 A2A RE-NOISE exactly when some clip has A2A on", () => {
    const input = baseInput();
    input.clips = [{ lane: 2, isCropAudio: false, needsStretch: false, a2aOn: true }];
    expect(buildSignalPath(input)[4].lit).toBe(true);
  });

  it("lights S6 INPAINT OVERLAPS exactly when overlapCount > 0", () => {
    const input = baseInput();
    input.overlapCount = 1;
    expect(buildSignalPath(input)[5].lit).toBe(true);
  });

  it("S7 MIX's note names the current order using the drawing's own option text", () => {
    const tree = baseInput();
    expect(buildSignalPath(tree)[6].note).toBe("(1+2) + (3+4)");
    const cascade = baseInput(); cascade.mix.order = "cascade";
    expect(buildSignalPath(cascade)[6].note).toBe("((1+2)+3)+4");
    const quad = baseInput(); quad.mix.order = "quad";
    expect(buildSignalPath(quad)[6].note).toBe("weighted 4-way (lerp only)");
  });

  it("lights S8 MASTER CHAIN when either latch_on or norm_on is set (norm_on defaults true)", () => {
    const input = baseInput(); // MASTER_DEFAULT.norm_on === true
    expect(buildSignalPath(input)[7].lit).toBe(true);
    const bothOff = baseInput();
    bothOff.master = { ...bothOff.master, latch_on: false, norm_on: false };
    expect(buildSignalPath(bothOff)[7].lit).toBe(false);
  });
});
