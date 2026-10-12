import { describe, expect, it, vi } from "vitest";
import { chainIsIdle, chainRequest, fetchLatchHeads, type LatchHeadInfo } from "../latch";
import { CHAIN_DEFAULTS } from "../../forge/defaults";
import type { LaneChain } from "../../forge/types";

function clone(c: LaneChain): LaneChain {
  return JSON.parse(JSON.stringify(c)) as LaneChain;
}

// The two real heads from docs/latent-forge/contract/fixtures/handmade-info.json (M1 plan:2374-2393),
// restated field-for-field so the test fixture and the shipped fixture cannot silently diverge.
const RMS_BASS: LatchHeadInfo = {
  name: "rms_energy_bass", family: "medium", default_gain: 512.0,
  health: "ok", supports_kinds: ["constant", "ramp_up", "ramp_down", "beat_grid"],
  slider_min: -35.2, slider_max: -0.13, value_default: -12.0,
};
const CHROMA_OTHER: LatchHeadInfo = {
  name: "chroma_other", family: "chroma", default_gain: 2048.0,
  health: "ok", supports_kinds: ["constant"],
  slider_min: 0.0, slider_max: 1.0, value_default: 0.5,
};
const HEADS: Record<string, LatchHeadInfo> = { rms_energy_bass: RMS_BASS, chroma_other: CHROMA_OTHER };

// M8's CHAIN_DEFAULTS keys (M8 plan lines 265-270). parse_chain's _merge 400s on any other key.
const CHAIN_KEYS = ["bungee_on", "film", "film_on", "hparams", "latch_on", "lora", "lora_on", "semitones", "slots"];

describe("chainRequest — the chain object M8's parse_chain takes (W 2026-09-25)", () => {
  it("sends exactly the chain's nine keys and two slots for an untouched chain, FILM gain 1.75", () => {
    const req = chainRequest(clone(CHAIN_DEFAULTS), HEADS);
    expect(Object.keys(req).sort()).toEqual(CHAIN_KEYS);
    expect(req.slots).toHaveLength(2);
    expect(Object.keys(req.hparams).sort()).toEqual(["gamma", "log_norms", "mu", "n_iter", "rho"]);
    expect(req.film).toEqual({ ckpt: null, gain: 1.75, value: 4.0 });   // the server's own default
    expect(req).toEqual(CHAIN_DEFAULTS);                                 // nothing else changed
  });

  it("sends the chain even while latch_on is false -- the server ignores the slots then", () => {
    const chain = clone(CHAIN_DEFAULTS);
    chain.slots[0] = { head: "rms_energy_bass", kind: "constant", value: -10, weight: 2, start_pct: 0, end_pct: 0.6 };
    const req = chainRequest(chain, HEADS);
    expect(req.latch_on).toBe(false);
    expect(req.slots[0]).toEqual(chain.slots[0]);
  });

  it("keeps an inactive slot in place -- head none or weight 0 is sent, never dropped (one slot is a 400)", () => {
    const chain = clone(CHAIN_DEFAULTS);
    chain.latch_on = true;
    chain.slots[0] = { head: "none", kind: "constant", value: 0, weight: 1, start_pct: 0, end_pct: 0.6 };
    chain.slots[1] = { head: "rms_energy_bass", kind: "constant", value: -10, weight: 0, start_pct: 0, end_pct: 0.6 };
    const req = chainRequest(chain, HEADS);
    expect(req.slots).toHaveLength(2);
    expect(req.slots.map((s) => s.head)).toEqual(["none", "rms_energy_bass"]);
    expect(req.slots[1].weight).toBe(0);   // the server drops it; the client does not
  });

  it("sends rho/mu as the 0..30 multipliers the sliders hold -- no gain is computed client-side", () => {
    // Hand-check: with weight 2 on rms_energy_bass (default_gain 512) the OLD client sent
    // rho = 2 * (512 * 2) = 2048, which parse_chain's 0..30 range check refuses. The server now
    // computes gain_0 = 512 * 2 = 1024 and rho = 2 * 1024 = 2048 itself (M8 chain_to_request; its
    // own test_chain_latch_gains pins the same arithmetic at rho 1.0 -> 1024, mu 0.5 -> 512).
    const chain = clone(CHAIN_DEFAULTS);
    chain.latch_on = true;
    chain.slots[0] = { head: "rms_energy_bass", kind: "constant", value: -10, weight: 2, start_pct: 0, end_pct: 0.6 };
    chain.hparams = { rho: 2, mu: 3, gamma: 0.5, n_iter: 5, log_norms: true };
    const req = chainRequest(chain, HEADS);
    expect(req.hparams).toEqual({ rho: 2, mu: 3, gamma: 0.5, n_iter: 5, log_norms: true });
    expect(req.slots[0]).toEqual({ head: "rms_energy_bass", kind: "constant", value: -10, weight: 2, start_pct: 0, end_pct: 0.6 });
    expect(JSON.stringify(req)).not.toContain('"gain":1024');
    expect(req.slots[0]).not.toHaveProperty("gain");
    expect(req).not.toHaveProperty("rho");   // nested under hparams only
  });

  it("rewrites a head the registry does not list to none, in place -- both slots stay (the server 400s on it)", () => {
    // M8 plan lines 377-379: chain_to_request raises `unknown LatCH head` for a name it does not
    // know with weight > 0, so sending it would fail the whole job.
    const chain = clone(CHAIN_DEFAULTS);
    chain.latch_on = true;
    chain.slots[0] = { head: "deleted_head", kind: "constant", value: 0, weight: 3, start_pct: 0, end_pct: 0.6 };
    chain.slots[1] = { head: "chroma_other", kind: "constant", value: 0.5, weight: 1, start_pct: 0, end_pct: 0.6 };
    const req = chainRequest(chain, HEADS);
    expect(req.slots.map((s) => s.head)).toEqual(["none", "chroma_other"]);
    expect(JSON.stringify(req)).not.toContain("deleted_head");
    expect(req.slots[0].weight).toBe(3);                // only the head changes
    expect(chain.slots[0].head).toBe("deleted_head");   // and the live chain is not touched
  });

  it("never sends start_pct > end_pct: crossed sliders go out as end_pct = start_pct, even with LatCH off (W 2026-09-25; critic follow-up #5)", () => {
    const chain = clone(CHAIN_DEFAULTS);   // latch_on false, head none: parse_chain still checks the order
    expect(chain.latch_on).toBe(false);
    chain.slots[1] = { head: "none", kind: "constant", value: 0, weight: 1, start_pct: 0.8, end_pct: 0.3 };
    const req = chainRequest(chain, HEADS);
    expect(req.slots[1].start_pct).toBe(0.8);                // the handle the user dragged is kept
    expect(req.slots[1].end_pct).toBe(0.8);                  // end = max(start, end)
    expect(req.slots[0]).toEqual(CHAIN_DEFAULTS.slots[0]);   // an ordered slot is sent as it is
    expect(chain.slots[1].end_pct).toBe(0.3);                // and the live chain is not touched
  });

  it("writes lora.slot null and keeps ckpt_path -- the path is the durable identity (Open questions 25)", () => {
    const chain = clone(CHAIN_DEFAULTS);
    chain.lora_on = true;
    chain.lora = { ckpt_path: "/SERVER/lora/x.ckpt", slot: 3, strength: 0.8 };
    expect(chainRequest(chain, HEADS).lora).toEqual({ ckpt_path: "/SERVER/lora/x.ckpt", slot: null, strength: 0.8 });
    expect(chain.lora.slot).toBe(3);
  });

  it("returns plain data: editing the request never reaches the chain, and it survives structuredClone", () => {
    const chain = clone(CHAIN_DEFAULTS);
    const req = chainRequest(chain, HEADS);
    req.slots[0].weight = 9;
    req.hparams.rho = 9;
    req.film.gain = 0;
    expect(chain.slots[0].weight).toBe(1);
    expect(chain.hparams.rho).toBe(1);
    expect(chain.film.gain).toBe(1.75);
    expect(() => structuredClone(req)).not.toThrow();
  });

  it("drops any key the chain type does not declare (parse_chain's _merge 400s on unknown fields)", () => {
    const chain = clone(CHAIN_DEFAULTS) as LaneChain & { stray?: number };
    chain.stray = 1;
    (chain.slots[0] as unknown as Record<string, unknown>).gain = 512;
    (chain.film as unknown as Record<string, unknown>).target = 4;
    const req = chainRequest(chain, HEADS);
    expect(Object.keys(req).sort()).toEqual(CHAIN_KEYS);
    expect(Object.keys(req.slots[0]).sort()).toEqual(["end_pct", "head", "kind", "start_pct", "value", "weight"]);
    expect(Object.keys(req.film).sort()).toEqual(["ckpt", "gain", "value"]);
  });
});

describe("chainIsIdle (spec §5.5, §8.1 S4 — the exact SIGNAL PATH string)", () => {
  it("is false when no feature is on, regardless of an A2A clip", () => {
    expect(chainIsIdle(clone(CHAIN_DEFAULTS), false)).toBe(false);
    expect(chainIsIdle(clone(CHAIN_DEFAULTS), true)).toBe(false);
  });

  it("is true when latch_on is on and the lane has no A2A clip", () => {
    const chain = clone(CHAIN_DEFAULTS);
    chain.latch_on = true;
    expect(chainIsIdle(chain, false)).toBe(true);
  });

  it("is false when latch_on is on and the lane DOES have an A2A clip", () => {
    const chain = clone(CHAIN_DEFAULTS);
    chain.latch_on = true;
    expect(chainIsIdle(chain, true)).toBe(false);
  });

  it("treats FiLM, LoRA and Bungee as equally 'active' — any one of the four, not just LatCH", () => {
    const film = clone(CHAIN_DEFAULTS); film.film_on = true;
    const lora = clone(CHAIN_DEFAULTS); lora.lora_on = true;
    const bungee = clone(CHAIN_DEFAULTS); bungee.bungee_on = true;
    expect(chainIsIdle(film, false)).toBe(true);
    expect(chainIsIdle(lora, false)).toBe(true);
    expect(chainIsIdle(bungee, false)).toBe(true);
  });
});

describe("fetchLatchHeads", () => {
  it("keys the /info.latch_heads array by head name", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({
      ok: true,
      latch_heads: [
        { name: "rms_energy_bass", family: "medium", default_gain: 512.0, health: "ok",
          supports_kinds: ["constant"], slider_min: -35.2, slider_max: -0.13, value_default: -12.0 },
      ],
    }))));
    const heads = await fetchLatchHeads();
    expect(Object.keys(heads)).toEqual(["rms_energy_bass"]);
    expect(heads.rms_energy_bass.default_gain).toBe(512.0);
  });

  it("returns an empty record rather than throwing when latch_heads is missing", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ ok: true }))));
    await expect(fetchLatchHeads()).resolves.toEqual({});
  });
});

describe("chainRequest — a ramp's explicit start (value_from)", () => {
  function withSlot(slot: Partial<LaneChain["slots"][0]>): LaneChain {
    const chain = clone(CHAIN_DEFAULTS);
    chain.slots[0] = { head: "rms_energy_bass", kind: "ramp_up", value: -12, weight: 1, start_pct: 0, end_pct: 0.6, ...slot };
    return chain;
  }

  it("sends value_from for a ramp that has one", () => {
    const req = chainRequest(withSlot({ value_from: -30 }), HEADS);
    expect(req.slots[0]).toEqual({ head: "rms_energy_bass", kind: "ramp_up", value: -12, weight: 1, start_pct: 0, end_pct: 0.6, value_from: -30 });
  });

  it("leaves it off for a ramp without one, so an older server still accepts the chain", () => {
    expect("value_from" in chainRequest(withSlot({}), HEADS).slots[0]).toBe(false);
    expect("value_from" in chainRequest(withSlot({ value_from: null }), HEADS).slots[0]).toBe(false);
  });

  it("leaves it off for every kind that is not a ramp, even if a stale value_from is still on the slot", () => {
    for (const kind of ["constant", "beat_grid"]) {
      expect("value_from" in chainRequest(withSlot({ kind, value_from: -30 }), HEADS).slots[0]).toBe(false);
    }
  });

  it("still rewrites an unlisted head to none on a ramp that has a start", () => {
    const req = chainRequest(withSlot({ head: "ghost_head", value_from: -30 }), HEADS);
    expect(req.slots[0].head).toBe("none");
  });
});
