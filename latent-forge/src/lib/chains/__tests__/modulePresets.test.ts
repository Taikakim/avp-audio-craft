import { describe, expect, it } from "vitest";
import { CHAIN_DEFAULTS } from "../../forge/defaults";
import type { LaneChain } from "../../forge/types";
import { applyModulePreset, durableChain, MODULE_PRESET_FIELDS, modulePresetPayload } from "../modulePresets";

function clone(c: LaneChain): LaneChain {
  return JSON.parse(JSON.stringify(c)) as LaneChain;
}

describe("module presets (spec 9.3: module level = that module's settings object)", () => {
  it("each level's payload is exactly its own fields, *_on flag included -- and never a resident slot index", () => {
    const chain = clone(CHAIN_DEFAULTS);
    chain.film_on = true;
    chain.semitones = -5;
    chain.lora = { ckpt_path: "/SERVER/a.safetensors", slot: 2, strength: 1 };   // slot 2 is only true NOW
    expect(Object.keys(modulePresetPayload(chain, "latch")).sort()).toEqual(["hparams", "latch_on", "slots"]);
    expect(modulePresetPayload(chain, "film")).toEqual({ film_on: true, film: CHAIN_DEFAULTS.film });
    // ckpt_path is the durable identity; slot is a transient /slots resolution (critic pass 2 #14)
    expect(modulePresetPayload(chain, "lora")).toEqual({ lora_on: false, lora: { ckpt_path: "/SERVER/a.safetensors", slot: null, strength: 1 } });
    expect(durableChain(chain).lora.slot).toBeNull();
    expect(chain.lora.slot).toBe(2);   // the live chain keeps its resolution
    expect(modulePresetPayload(chain, "bungee")).toEqual({ bungee_on: false, semitones: -5 });
    expect(MODULE_PRESET_FIELDS.bungee).toEqual(["bungee_on", "semitones"]);
  });

  it("the payload is a deep copy -- editing the chain afterwards does not change a saved payload", () => {
    const chain = clone(CHAIN_DEFAULTS);
    const payload = modulePresetPayload(chain, "latch") as Pick<LaneChain, "hparams">;
    chain.hparams.rho = 9;
    expect(payload.hparams.rho).toBe(CHAIN_DEFAULTS.hparams.rho);
  });

  it("recall writes only that level's fields, in place, and ignores anything else in the payload", () => {
    const chain = clone(CHAIN_DEFAULTS);
    const before = chain;
    applyModulePreset(chain, "bungee", { bungee_on: true, semitones: 7, latch_on: true, film_on: true });
    expect(chain).toBe(before);                 // same object -- the $state proxy rule
    expect(chain.bungee_on).toBe(true);
    expect(chain.semitones).toBe(7);
    expect(chain.latch_on).toBe(false);         // not bungee's field: untouched
    expect(chain.film_on).toBe(false);
  });
});
