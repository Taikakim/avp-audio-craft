import { describe, expect, it } from "vitest";
import { BASE_DEFAULTS, cloneRenderSettings, MASTER_DEFAULT, MIX_DEFAULT, OVERLAP_DEFAULT, POST_DEFAULTS } from "../../forge/defaults";
import { arrangement } from "../arrangement.svelte";

describe("arrangement.renderSeed (critic follow-up #4)", () => {
  it("seeds a new clip's render from the hook -- BASE until App sets it, a fresh copy per clip", () => {
    const REF = { kind: "crop" as const, crop_id: "seed" };
    const before = arrangement.renderSeed;
    try {
      const base = arrangement.addClip({ lane: 0, startSec: 0, durSec: 4, audio: REF });
      expect(base.render).toEqual(BASE_DEFAULTS);                        // M5's behaviour, unchanged by default
      arrangement.renderSeed = () => cloneRenderSettings(POST_DEFAULTS);   // what App's settings.defaults is under POST
      const a = arrangement.addClip({ lane: 0, startSec: 8, durSec: 4, audio: REF });
      const b = arrangement.addClip({ lane: 1, startSec: 0, durSec: 4, audio: REF });
      expect(a.render).toEqual(POST_DEFAULTS);
      expect(a.render.schedule).not.toBe(b.render.schedule);            // never a shared object
      expect(base.render).toEqual(BASE_DEFAULTS);                        // an existing clip is not re-seeded
    } finally {
      arrangement.renderSeed = before;
      arrangement.clips.splice(0, arrangement.clips.length);
    }
  });
});

describe("arrangement.mix / .master (M7 T3)", () => {
  it("are seeded from M1's frozen defaults, as copies rather than the constants themselves", () => {
    expect(arrangement.mix).toEqual(MIX_DEFAULT);
    expect(arrangement.master).toEqual(MASTER_DEFAULT);
    arrangement.master.noise = 99;
    expect(MASTER_DEFAULT.noise).toBe(0.25);
    arrangement.master.noise = 0.25;
  });
});

describe("arrangement.peekOverlapParams (non-seeding; Global Constraint #8)", () => {
  it("returns an unstored default-shaped copy until the key is seeded, then the live entry", () => {
    const key = "peek-a-peek-b";
    const first = arrangement.peekOverlapParams(key);
    expect(first.steps).toBe(OVERLAP_DEFAULT.steps);
    expect(first.chroma_xfade).toBe(OVERLAP_DEFAULT.chroma_xfade);
    // not stored: two peeks are two different objects, and mutating one reaches nothing
    expect(arrangement.peekOverlapParams(key)).not.toBe(first);
    first.steps = 99;
    expect(arrangement.peekOverlapParams(key).steps).toBe(OVERLAP_DEFAULT.steps);
    // once a write seeds it, peek hands back the SAME live entry overlapParams does
    arrangement.setOverlapParams(key, { steps: 40 });
    expect(arrangement.peekOverlapParams(key)).toBe(arrangement.overlapParams(key));
    expect(arrangement.peekOverlapParams(key).steps).toBe(40);
  });

  it("clearOverlapParams drops every seeded entry, in place, so peek is back to an unstored default", () => {
    const key = "clear-a-clear-b";
    arrangement.setOverlapParams(key, { steps: 40 });
    expect(arrangement.peekOverlapParams(key)).toBe(arrangement.peekOverlapParams(key)); // seeded: one live object
    arrangement.clearOverlapParams();
    expect(arrangement.peekOverlapParams(key).steps).toBe(OVERLAP_DEFAULT.steps);
    expect(arrangement.peekOverlapParams(key)).not.toBe(arrangement.peekOverlapParams(key)); // unstored again
  });
});
