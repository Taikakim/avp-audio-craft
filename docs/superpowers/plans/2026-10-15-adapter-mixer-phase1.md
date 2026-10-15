# Adapter Mixer — Phase 1 (per-block blending for one adapter) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** In the Latent Forge, let the user draw a per-DiT-block curve for the lane's LoRA/DoRA (true blend with the base model, or stock direction scaling), as an optional ADVANCED FX that greys out the plain strength control.

**Architecture:** GHOST-NOTE's backend (SAO `5522423`) already applies per-block DoRA strength at runtime (`dora.block_strengths`, `dora.blend="interp"`, `_apply_block_profile` in `eval/explorer_render_server.py`). Phase 1 plumbs it end to end: the lane chain's `lora` object gains an optional `blend` state in the GUI, which a small registry turns into the two wire fields; the forge's `parse_chain` / `chain_to_request` validate and forward them into the `dora` request. A reusable curve module + SVG editor live in a new bottom tab, ADAPTER MIX. The server-side weight compositor of the spec starts in Phase 2 (spec §6.1 allows Phase 1 to use GHOST-NOTE's fields).

**Tech Stack:** Svelte 5 (runes) + TypeScript + vitest/@testing-library (latent-forge); Python 3.13 + pytest (eval/forge).

**Spec:** `docs/superpowers/specs/2026-10-15-adapter-mixer-design.md`

**Phase 1 scope (spec §7 item 1):** single adapter, `amount` / `direction`, the curve editor with all shapes and
transforms, the right-pane switch and greying, lora presets. NOT in Phase 1: the compositor, pairs, PARALLEL / CHAIN,
the expand toggle (attention / feed-forward), the `/mix/profile` underlay data (the editor already accepts an
`underlay` prop), patch bays, EXPORT, the experiment log.

## Global Constraints

- 24 DiT blocks, index 0..23. Curve values range **-0.5..1.5** (spec §3).
- With ADVANCED FX off (or no `blend` state), the job payload is **byte-identical** to today's (spec §1, §6).
- `blend` modes: `amount` = true weight interpolation with the base (`blend: "interp"`); `direction` = stock DoRA strength per block (no `blend` key) (spec §3).
- ADVANCED FX on greys out the right-pane SCALE control; the curve is the strength (spec §4.1). Wire strength is then 1.0 and `block_strengths` = the curve.
- The per-block profile only applies to an adapter named by checkpoint path, never a resident slot (`prepare_model` applies `_apply_block_profile` only on the `ckpt` path): a blended request sends `slot: null`.
- New blend ideas = one registry entry (spec §4.3).
- Ownership headers on new/edited scripts: `// Owner: WINTERMUTE (created 2026-10-15)` / `# Last edited: WINTERMUTE 2026-10-15 — <what>` (MASTER §4).
- Commit with `Misc/agent_commit.sh WINTERMUTE ...`, explicit paths only.

## Review Focus

1. **A resident-slot adapter with blending on** — the user picked an adapter that is loaded in a slot; the blend must still apply (client sends `slot: null` + `ckpt_path`; server 400s clearly if there is no path). Tests: Task 1 (`test_chain_blend_needs_ckpt_path`), Task 3 (`sends slot null when blending`).
2. **A saved session or preset from before this change** (no `blend` key) must load unchanged, and one with a malformed `blend` must be rejected, not half-applied. Tests: Task 2.
- 3. **Freehand draw jumping several columns in one pointer move** (fast drag) must fill every column between, not leave gaps. Test: Task 4 (`drawSegment fills skipped columns`).
- 4. **ADVANCED FX toggled on with LoRA off or no adapter chosen** — the tab must say what is missing instead of silently sending nothing. Test: Task 6.
- 5. **Switching lanes while the ADAPTER MIX tab is open** — the editor must show and edit the ACTIVE lane's curve, not the previous one. Test: Task 6.

---

### Task 1: Forge server — accept and forward `chain.lora.block_strengths` / `chain.lora.blend`

**Files:**
- Modify: `eval/forge/render_settings.py` (CHAIN_DEFAULTS, `parse_chain` lora block, `chain_to_request` lora block)
- Test: `eval/tests/test_forge_render_settings.py`

**Interfaces:**
- Consumes: GHOST-NOTE's `dora` fields read in `prepare_model` (`block_strengths`: list of 24 floats; `blend`: `"interp"` or absent).
- Produces: `parse_chain(obj)["lora"]` gains keys `block_strengths: list[float] | None`, `blend: "interp" | None`; `chain_to_request(...)["dora"]` carries them only when set.

- [ ] **Step 1: Write the failing tests** (append to `eval/tests/test_forge_render_settings.py`; the file's own `chain(**kw)` helper builds a chain dict)

```python
CURVE = [1.0] * 12 + [0.5] * 12


def test_chain_lora_blend_forwarded_only_when_set():
    plain = chain(latch_on=False, lora_on=True, lora={"ckpt_path": "/x.ckpt", "slot": None, "strength": 0.8})
    assert R.chain_to_request(R.parse_chain(plain), HEADS)["dora"] == {"ckpt_path": "/x.ckpt", "strength": 0.8}
    amt = chain(latch_on=False, lora_on=True,
                lora={"ckpt_path": "/x.ckpt", "slot": None, "strength": 1.0, "block_strengths": CURVE, "blend": "interp"})
    assert R.chain_to_request(R.parse_chain(amt), HEADS)["dora"] == {
        "ckpt_path": "/x.ckpt", "strength": 1.0, "block_strengths": CURVE, "blend": "interp"}
    direction = chain(latch_on=False, lora_on=True,
                      lora={"ckpt_path": "/x.ckpt", "slot": None, "strength": 1.0, "block_strengths": CURVE})
    assert R.chain_to_request(R.parse_chain(direction), HEADS)["dora"] == {
        "ckpt_path": "/x.ckpt", "strength": 1.0, "block_strengths": CURVE}


def test_chain_blend_needs_ckpt_path():
    c = chain(latch_on=False, lora_on=True,
              lora={"ckpt_path": None, "slot": 1, "strength": 1.0, "block_strengths": CURVE})
    with pytest.raises(ForgeError) as e:
        R.chain_to_request(R.parse_chain(c), HEADS)
    assert "checkpoint path" in str(e.value)


@pytest.mark.parametrize("bad", [
    {"block_strengths": [1.0] * 23},
    {"block_strengths": [1.0] * 23 + [2.0]},
    {"block_strengths": [1.0] * 23 + [float("nan")]},
    {"block_strengths": "flat"},
    {"blend": "lerp"},
])
def test_chain_blend_rejects(bad):
    lora = {"ckpt_path": "/x.ckpt", "slot": None, "strength": 1.0, "block_strengths": CURVE, **bad}
    with pytest.raises(ForgeError):
        R.parse_chain(chain(lora_on=True, lora=lora))
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd /home/kim/Projects/SAO && .venv/bin/python -m pytest eval/tests/test_forge_render_settings.py -q -k "blend"`
Expected: FAIL (`unknown chain.lora field(s): block_strengths`).

- [ ] **Step 3: Implement**

In `CHAIN_DEFAULTS` change the lora entry to:

```python
                  "lora_on": False, "lora": {"ckpt_path": None, "slot": None, "strength": 1.0,
                                             "block_strengths": None, "blend": None},
```

Add above `parse_chain`:

```python
N_BLOCKS = 24
BLOCK_MULT_RANGE = (-0.5, 1.5)
LORA_BLENDS = (None, "interp")


def _block_strengths(v):
    """Per-DiT-block strength multipliers (adapter mixer phase 1, W 2026-10-15): None or 24 finite numbers."""
    if v is None:
        return None
    if not isinstance(v, list) or len(v) != N_BLOCKS:
        raise ForgeError(400, f"lora.block_strengths must be a list of {N_BLOCKS} numbers")
    lo, hi = BLOCK_MULT_RANGE
    return [_num(x, lo, hi, f"lora.block_strengths[{i}]") for i, x in enumerate(v)]
```

Replace the `c["lora"] = {...}` assignment in `parse_chain` with:

```python
    if lora["blend"] not in LORA_BLENDS:
        raise ForgeError(400, f"lora.blend {lora['blend']!r} not in {LORA_BLENDS}")
    c["lora"] = {"ckpt_path": lora["ckpt_path"] or None,
                 "slot": None if lora["slot"] is None else _num(lora["slot"], 0, 63, "lora.slot", integer=True),
                 "strength": _num(lora["strength"], 0, 1, "lora.strength"),
                 "block_strengths": _block_strengths(lora["block_strengths"]),
                 "blend": lora["blend"]}
```

Replace the `if chain["lora_on"]:` block in `chain_to_request` with:

```python
    if chain["lora_on"]:
        lora = chain["lora"]
        if lora["block_strengths"] is not None:
            # The block profile is applied only to an adapter loaded by path (prepare_model), never a resident slot.
            if not lora["ckpt_path"]:
                raise ForgeError(400, "per-block LoRA blending needs the adapter's checkpoint path, not a resident slot")
            out["dora"] = {"ckpt_path": lora["ckpt_path"], "strength": lora["strength"],
                           "block_strengths": list(lora["block_strengths"])}
            if lora["blend"] is not None:
                out["dora"]["blend"] = lora["blend"]
        elif lora["slot"] is not None:
            out["dora"] = {"slot": lora["slot"], "strength": lora["strength"]}
        elif lora["ckpt_path"]:
            out["dora"] = {"ckpt_path": lora["ckpt_path"], "strength": lora["strength"]}
```

Add `# Last edited: WINTERMUTE 2026-10-15 — chain.lora block_strengths / blend (adapter mixer phase 1)` under the module docstring.

- [ ] **Step 4: Run the whole file**

Run: `cd /home/kim/Projects/SAO && .venv/bin/python -m pytest eval/tests/test_forge_render_settings.py -q`
Expected: all pass (the existing `test_chain_film_lora_and_off` still passes: unset fields add no keys).

- [ ] **Step 5: Commit**

```bash
cd /home/kim/Projects/SAO && git add eval/forge/render_settings.py eval/tests/test_forge_render_settings.py
Misc/agent_commit.sh WINTERMUTE -m "forge: chain.lora.block_strengths / blend forwarded to the dora request (adapter mixer phase 1)"
```

---

### Task 2: GUI data model — `LoraBlend` on the lane chain, saved and validated

**Files:**
- Modify: `latent-forge/src/lib/forge/types.ts` (LaneChain.lora)
- Modify: `latent-forge/src/lib/forge/projectSerializer.svelte.ts` (`isLaneChain`)
- Test: `latent-forge/src/lib/forge/__tests__/projectSerializer.test.ts`, `latent-forge/src/lib/chains/__tests__/modulePresets.test.ts`

**Interfaces:**
- Produces (types.ts):

```ts
/** Adapter mixer phase 1: how the lane's LoRA/DoRA acts per DiT block (spec 2026-10-15-adapter-mixer-design §3). */
export type BlendMode = "amount" | "direction";
export interface LoraBlend {
  /** ADVANCED FX on: the curve replaces SCALE. */
  on: boolean;
  mode: BlendMode;
  /** 24 values, -0.5..1.5, index = DiT block. */
  curve: number[];
}
```

and `lora: { ckpt_path: string | null; slot: number | null; strength: number; blend?: LoraBlend | null };`

- [ ] **Step 1: Write the failing tests**

Append to `projectSerializer.test.ts`:

```ts
describe("lane chain lora.blend (adapter mixer phase 1)", () => {
  const goodBlend = { on: true, mode: "amount", curve: Array(24).fill(1) };
  function projectWithBlend(blend: unknown) {
    arrangement.lanes[0].chain.lora = { ckpt_path: "/SERVER/a.safetensors", slot: null, strength: 1 };
    const p = JSON.parse(JSON.stringify(serializeProject({ name: "b" })));
    p.lanes[0].chain.lora.blend = blend;
    return p;
  }
  it("accepts a project without blend (sessions saved before this change)", () => {
    expect(() => validateProjectV2(projectWithBlend(undefined))).not.toThrow();
  });
  it("accepts null and a well-formed blend", () => {
    expect(() => validateProjectV2(projectWithBlend(null))).not.toThrow();
    expect(() => validateProjectV2(projectWithBlend(goodBlend))).not.toThrow();
  });
  it.each([
    ["wrong length", { ...goodBlend, curve: Array(23).fill(1) }],
    ["out of range", { ...goodBlend, curve: [...Array(23).fill(1), 2] }],
    ["unknown mode", { ...goodBlend, mode: "lerp" }],
    ["on not boolean", { ...goodBlend, on: "yes" }],
  ])("rejects a malformed blend: %s", (_label, blend) => {
    expect(() => validateProjectV2(projectWithBlend(blend))).toThrow();
  });
});
```

Append to `modulePresets.test.ts` (it already imports `modulePresetPayload`, `applyModulePreset`, `CHAIN_DEFAULTS`):

```ts
it("a lora module preset carries the blend curve and restores it", () => {
  const chain = structuredClone(CHAIN_DEFAULTS);
  chain.lora = { ckpt_path: "/a.ckpt", slot: 3, strength: 1,
                 blend: { on: true, mode: "amount", curve: Array.from({ length: 24 }, (_, i) => i / 23) } };
  const payload = modulePresetPayload(chain, "lora") as Record<string, unknown>;
  const target = structuredClone(CHAIN_DEFAULTS);
  applyModulePreset(target, "lora", payload);
  expect(target.lora.blend).toEqual(chain.lora.blend);
  expect(target.lora.slot).toBeNull();
});
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd /home/kim/Projects/SAO/latent-forge && npx vitest run src/lib/forge/__tests__/projectSerializer.test.ts src/lib/chains/__tests__/modulePresets.test.ts`
Expected: the "rejects a malformed blend" cases FAIL (validation accepts anything); TS may also flag `blend` on the lora literal.

- [ ] **Step 3: Implement**

Add the `BlendMode` / `LoraBlend` types above `LaneChain` in `types.ts` and extend `lora` as shown in Interfaces.

In `projectSerializer.svelte.ts` add next to the other validators:

```ts
const BLEND_MODES = ["amount", "direction"];

/** lora.blend (adapter mixer phase 1): absent / null, or {on, mode, curve[24] within -0.5..1.5}. */
function isLoraBlend(b: unknown): boolean {
  if (b === undefined || b === null) return true;
  if (!isObj(b) || !isBool(b.on) || typeof b.mode !== "string" || !BLEND_MODES.includes(b.mode)) return false;
  const c = b.curve;
  return Array.isArray(c) && c.length === 24 && c.every((v) => isNum(v) && v >= -0.5 && v <= 1.5);
}
```

and append `&& isLoraBlend(lora.blend)` to the `return` of `isLaneChain`.

- [ ] **Step 4: Run to verify they pass, plus the whole suite's type check**

Run: `cd /home/kim/Projects/SAO/latent-forge && npx vitest run src/lib/forge src/lib/chains && npm run check`
Expected: PASS; svelte-check 0 errors.

- [ ] **Step 5: Commit**

```bash
cd /home/kim/Projects/SAO && git add latent-forge/src/lib/forge/types.ts latent-forge/src/lib/forge/projectSerializer.svelte.ts latent-forge/src/lib/forge/__tests__/projectSerializer.test.ts latent-forge/src/lib/chains/__tests__/modulePresets.test.ts
Misc/agent_commit.sh WINTERMUTE -m "latent-forge: LoraBlend on the lane chain, validated and carried by lora presets"
```

---

### Task 3: Blend registry + wire mapping in `chainRequest`

**Files:**
- Create: `latent-forge/src/lib/blend/registry.ts`
- Modify: `latent-forge/src/lib/chains/latch.ts` (`ChainRequest.lora`, `chainRequest`)
- Test: `latent-forge/src/lib/blend/__tests__/registry.test.ts`, `latent-forge/src/lib/chains/__tests__/latch.test.ts`

**Interfaces:**
- Consumes: `LoraBlend`, `BlendMode` (Task 2).
- Produces:

```ts
export interface BlendWire { block_strengths: number[]; blend?: "interp" }
export interface BlendIdea { id: BlendMode; label: string; help: string; toWire(curve: number[]): BlendWire }
export const BLEND_IDEAS: readonly BlendIdea[];
export function blendIdea(id: BlendMode): BlendIdea;
export function loraWire(lora: LaneChain["lora"]): ChainRequest["lora"];
```

`ChainRequest["lora"]` becomes `{ ckpt_path: string | null; slot: null; strength: number; block_strengths?: number[]; blend?: "interp" }`.

- [ ] **Step 1: Write the failing tests**

`src/lib/blend/__tests__/registry.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { BLEND_IDEAS, blendIdea, loraWire } from "../registry";

const CURVE = Array.from({ length: 24 }, (_, i) => (i < 12 ? 1 : 0.5));

describe("blend registry", () => {
  it("has amount and direction, in that order", () => {
    expect(BLEND_IDEAS.map((b) => b.id)).toEqual(["amount", "direction"]);
  });
  it("amount is true interpolation with the base, direction is the stock per-block strength", () => {
    expect(blendIdea("amount").toWire(CURVE)).toEqual({ block_strengths: CURVE, blend: "interp" });
    expect(blendIdea("direction").toWire(CURVE)).toEqual({ block_strengths: CURVE });
  });
  it("copies the curve (the wire never aliases the live $state array)", () => {
    const w = blendIdea("amount").toWire(CURVE);
    expect(w.block_strengths).not.toBe(CURVE);
  });
});

describe("loraWire", () => {
  it("is today's lora object when there is no blend or it is off", () => {
    expect(loraWire({ ckpt_path: "/a", slot: 2, strength: 0.7 })).toEqual({ ckpt_path: "/a", slot: null, strength: 0.7 });
    expect(loraWire({ ckpt_path: "/a", slot: 2, strength: 0.7, blend: { on: false, mode: "amount", curve: CURVE } }))
      .toEqual({ ckpt_path: "/a", slot: null, strength: 0.7 });
  });
  it("sends strength 1 and the curve when blending (the curve IS the strength)", () => {
    expect(loraWire({ ckpt_path: "/a", slot: 2, strength: 0.7, blend: { on: true, mode: "amount", curve: CURVE } }))
      .toEqual({ ckpt_path: "/a", slot: null, strength: 1, block_strengths: CURVE, blend: "interp" });
  });
});
```

Append to `src/lib/chains/__tests__/latch.test.ts` (inside the existing `describe("chainRequest ...")` file scope):

```ts
describe("chainRequest — lora blend (adapter mixer phase 1)", () => {
  it("an untouched chain's lora is byte-identical to before", () => {
    const req = chainRequest(clone(CHAIN_DEFAULTS), HEADS);
    expect(req.lora).toEqual({ ckpt_path: null, slot: null, strength: 1.0 });
    expect(Object.keys(req.lora).sort()).toEqual(["ckpt_path", "slot", "strength"]);
  });
  it("sends slot null when blending", () => {
    const c = clone(CHAIN_DEFAULTS);
    c.lora = { ckpt_path: "/a.ckpt", slot: 1, strength: 0.4, blend: { on: true, mode: "direction", curve: Array(24).fill(0.5) } };
    expect(chainRequest(c, HEADS).lora).toEqual({ ckpt_path: "/a.ckpt", slot: null, strength: 1, block_strengths: Array(24).fill(0.5) });
  });
});
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd /home/kim/Projects/SAO/latent-forge && npx vitest run src/lib/blend src/lib/chains/__tests__/latch.test.ts`
Expected: FAIL (`Cannot find module '../registry'`).

- [ ] **Step 3: Implement** `src/lib/blend/registry.ts`:

```ts
// Owner: WINTERMUTE (created 2026-10-15)
// Blend ideas for the adapter mixer (spec docs/superpowers/specs/2026-10-15-adapter-mixer-design.md §3, §4.3).
// A new idea = one entry here (plus its own controls, Phase 2+). Each turns the UI's curve into the
// fields the server's `dora` request takes (GHOST-NOTE's _apply_block_profile, SAO 5522423).
import type { BlendMode, LaneChain } from "../forge/types";
import type { ChainRequest } from "../chains/latch";

export interface BlendWire { block_strengths: number[]; blend?: "interp" }
export interface BlendIdea { id: BlendMode; label: string; help: string; toWire(curve: number[]): BlendWire }

export const BLEND_IDEAS: readonly BlendIdea[] = [
  {
    id: "amount",
    label: "amount (blend with base)",
    help: "Per block, how much of the adapter's weight change is applied: 0 = base model, 1 = full adapter.",
    toWire: (curve) => ({ block_strengths: [...curve], blend: "interp" }),
  },
  {
    id: "direction",
    label: "direction (stock strength)",
    help: "Per block, the adapter's usual strength knob: scales the low-rank direction, the trained magnitude stays.",
    toWire: (curve) => ({ block_strengths: [...curve] }),
  },
];

export function blendIdea(id: BlendMode): BlendIdea {
  const idea = BLEND_IDEAS.find((b) => b.id === id);
  if (!idea) throw new Error(`unknown blend mode ${id}`);
  return idea;
}

/** The chain's lora object as the server takes it. No blend (or blend off) = exactly the pre-mixer shape. */
export function loraWire(lora: LaneChain["lora"]): ChainRequest["lora"] {
  const base = { ckpt_path: lora.ckpt_path, slot: null, strength: lora.strength } as ChainRequest["lora"];
  if (!lora.blend?.on) return base;
  return { ...base, strength: 1, ...blendIdea(lora.blend.mode).toWire(lora.blend.curve) };
}
```

In `latch.ts`: change the `lora` member of `ChainRequest` to
`lora: { ckpt_path: string | null; slot: null; strength: number; block_strengths?: number[]; blend?: "interp" };`,
add `import { loraWire } from "../blend/registry";`, and in `chainRequest` replace the `lora: { ckpt_path: ..., slot: null, strength: ... },` line with `lora: loraWire(chain.lora),`. Add `// Last edited: WINTERMUTE 2026-10-15 — lora via blend/registry loraWire (adapter mixer phase 1)` under the file's first comment line.

- [ ] **Step 4: Run to verify they pass**

Run: `cd /home/kim/Projects/SAO/latent-forge && npx vitest run src/lib/blend src/lib/chains && npm run check`
Expected: PASS, 0 type errors.

- [ ] **Step 5: Commit**

```bash
cd /home/kim/Projects/SAO && git add latent-forge/src/lib/blend latent-forge/src/lib/chains/latch.ts latent-forge/src/lib/chains/__tests__/latch.test.ts
Misc/agent_commit.sh WINTERMUTE -m "latent-forge: blend registry (amount / direction) and lora wire mapping"
```

---

### Task 4: Curve math — shapes, transforms, freehand segments

**Files:**
- Create: `latent-forge/src/lib/blend/curves.ts`
- Test: `latent-forge/src/lib/blend/__tests__/curves.test.ts`

**Interfaces:**
- Produces:

```ts
export const N_BLOCKS = 24;
export const CURVE_MIN = -0.5;
export const CURVE_MAX = 1.5;
export function clampValue(v: number): number;
export function flatCurve(v?: number): number[];
export interface CurveShape { id: string; label: string; make(): number[] }
export const CURVE_SHAPES: readonly CurveShape[];
export function soloCurve(block: number): number[];
export function invertCurve(c: number[]): number[];
export function smoothCurve(c: number[]): number[];
export function scaleCurve(c: number[], k: number): number[];
export function drawSegment(c: number[], i0: number, v0: number, i1: number, v1: number): number[];
export function isFlatOne(c: number[]): boolean;
```

- [ ] **Step 1: Write the failing tests** `src/lib/blend/__tests__/curves.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import {
  CURVE_MAX, CURVE_MIN, CURVE_SHAPES, N_BLOCKS, clampValue, drawSegment, flatCurve, invertCurve, isFlatOne,
  scaleCurve, smoothCurve, soloCurve,
} from "../curves";

describe("curve shapes", () => {
  it("every shape has 24 values inside the range", () => {
    for (const s of CURVE_SHAPES) {
      const c = s.make();
      expect(c, s.id).toHaveLength(N_BLOCKS);
      expect(c.every((v) => v >= CURVE_MIN && v <= CURVE_MAX), s.id).toBe(true);
    }
  });
  it("has the spec's shapes", () => {
    expect(CURVE_SHAPES.map((s) => s.id)).toEqual([
      "flat", "early_ramp_down", "late_ramp_down", "middle_bell", "ascending_exp", "descending_exp",
      "early_only", "last8_off", "alternating",
    ]);
  });
  it("early ramp-down falls 1 -> 0 and last-8-off zeroes blocks 16..23", () => {
    const r = CURVE_SHAPES.find((s) => s.id === "early_ramp_down")!.make();
    expect(r[0]).toBe(1); expect(r[23]).toBe(0);
    const l = CURVE_SHAPES.find((s) => s.id === "last8_off")!.make();
    expect(l.slice(0, 16).every((v) => v === 1) && l.slice(16).every((v) => v === 0)).toBe(true);
  });
  it("solo lights exactly one block", () => {
    const s = soloCurve(5);
    expect(s.filter((v) => v === 1)).toHaveLength(1);
    expect(s[5]).toBe(1);
  });
});

describe("transforms", () => {
  it("invert mirrors around 0.5 and clamps", () => {
    expect(invertCurve(flatCurve(1))).toEqual(flatCurve(0));
    expect(invertCurve(flatCurve(-0.5))[0]).toBe(CURVE_MAX);
  });
  it("scale clamps into the range", () => {
    expect(scaleCurve(flatCurve(1), 2)).toEqual(flatCurve(1.5));
  });
  it("smooth keeps length and averages neighbours", () => {
    const c = soloCurve(10);
    const s = smoothCurve(c);
    expect(s).toHaveLength(N_BLOCKS);
    expect(s[10]).toBeCloseTo(1 / 3);
    expect(s[9]).toBeCloseTo(1 / 3);
  });
  it("clampValue bounds", () => {
    expect(clampValue(9)).toBe(CURVE_MAX);
    expect(clampValue(-9)).toBe(CURVE_MIN);
  });
});

describe("drawSegment (freehand drag)", () => {
  it("fills skipped columns with a straight line", () => {
    const c = drawSegment(flatCurve(1), 2, 0, 6, 1);
    expect(c.slice(2, 7)).toEqual([0, 0.25, 0.5, 0.75, 1]);
    expect(c[1]).toBe(1);
    expect(c[7]).toBe(1);
  });
  it("works right-to-left and clamps", () => {
    const c = drawSegment(flatCurve(1), 6, 3, 2, -3);
    expect(c[6]).toBe(CURVE_MAX);
    expect(c[2]).toBe(CURVE_MIN);
  });
  it("does not mutate its input", () => {
    const base = flatCurve(1);
    drawSegment(base, 0, 0, 23, 0);
    expect(isFlatOne(base)).toBe(true);
  });
});
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd /home/kim/Projects/SAO/latent-forge && npx vitest run src/lib/blend/__tests__/curves.test.ts`
Expected: FAIL (`Cannot find module '../curves'`).

- [ ] **Step 3: Implement** `src/lib/blend/curves.ts`:

```ts
// Owner: WINTERMUTE (created 2026-10-15)
// Per-DiT-block curves for the adapter mixer (spec 2026-10-15-adapter-mixer-design §4.2). Pure: every
// function returns a new array, so a curve held in a $state proxy is replaced, never mutated in place.
export const N_BLOCKS = 24;
export const CURVE_MIN = -0.5;
export const CURVE_MAX = 1.5;

export function clampValue(v: number): number {
  return v < CURVE_MIN ? CURVE_MIN : v > CURVE_MAX ? CURVE_MAX : v;
}

const make = (f: (i: number) => number): number[] =>
  Array.from({ length: N_BLOCKS }, (_, i) => clampValue(Number(f(i).toFixed(6))));

export function flatCurve(v = 1): number[] {
  return make(() => v);
}

export interface CurveShape { id: string; label: string; make(): number[] }

const LAST = N_BLOCKS - 1;
const E3 = Math.exp(3) - 1;

export const CURVE_SHAPES: readonly CurveShape[] = [
  { id: "flat", label: "flat", make: () => flatCurve(1) },
  { id: "early_ramp_down", label: "early ramp down", make: () => make((i) => 1 - i / LAST) },
  { id: "late_ramp_down", label: "late ramp down", make: () => make((i) => (i < 12 ? 1 : 1 - (i - 11) / 12)) },
  { id: "middle_bell", label: "middle bell", make: () => make((i) => Math.exp(-(((i - LAST / 2) / 5) ** 2))) },
  { id: "ascending_exp", label: "ascending exp", make: () => make((i) => (Math.exp((3 * i) / LAST) - 1) / E3) },
  { id: "descending_exp", label: "descending exp", make: () => make((i) => (Math.exp((3 * (LAST - i)) / LAST) - 1) / E3) },
  { id: "early_only", label: "early only", make: () => make((i) => (i < 8 ? 1 : 0)) },
  { id: "last8_off", label: "last 8 off", make: () => make((i) => (i < 16 ? 1 : 0)) },
  { id: "alternating", label: "alternating", make: () => make((i) => (i % 2 === 0 ? 1 : 0)) },
];

export function soloCurve(block: number): number[] {
  return make((i) => (i === block ? 1 : 0));
}

export function invertCurve(c: number[]): number[] {
  return c.map((v) => clampValue(Number((1 - v).toFixed(6))));
}

export function scaleCurve(c: number[], k: number): number[] {
  return c.map((v) => clampValue(Number((v * k).toFixed(6))));
}

/** 3-tap moving average, edges replicated. */
export function smoothCurve(c: number[]): number[] {
  return c.map((v, i) => {
    const a = c[Math.max(0, i - 1)];
    const b = c[Math.min(c.length - 1, i + 1)];
    return clampValue(Number(((a + v + b) / 3).toFixed(6)));
  });
}

/** A freehand stroke from (i0, v0) to (i1, v1): every column between is set on the straight line. */
export function drawSegment(c: number[], i0: number, v0: number, i1: number, v1: number): number[] {
  const out = [...c];
  const lo = Math.max(0, Math.min(i0, i1));
  const hi = Math.min(N_BLOCKS - 1, Math.max(i0, i1));
  for (let i = lo; i <= hi; i++) {
    const t = i1 === i0 ? 1 : (i - i0) / (i1 - i0);
    out[i] = clampValue(Number((v0 + (v1 - v0) * t).toFixed(6)));
  }
  return out;
}

export function isFlatOne(c: number[]): boolean {
  return c.length === N_BLOCKS && c.every((v) => v === 1);
}
```

- [ ] **Step 4: Run to verify they pass**

Run: `cd /home/kim/Projects/SAO/latent-forge && npx vitest run src/lib/blend`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/kim/Projects/SAO && git add latent-forge/src/lib/blend/curves.ts latent-forge/src/lib/blend/__tests__/curves.test.ts
Misc/agent_commit.sh WINTERMUTE -m "latent-forge: per-block curve math (shapes, transforms, freehand segments)"
```

---

### Task 5: `CurveEditor.svelte` — the drawable 24-column graph

**Files:**
- Create: `latent-forge/src/ui/blend/CurveEditor.svelte`
- Test: `latent-forge/src/ui/blend/__tests__/CurveEditor.component.test.ts`

**Interfaces:**
- Consumes: `N_BLOCKS`, `CURVE_MIN`, `CURVE_MAX`, `clampValue`, `drawSegment` (Task 4).
- Produces: component props `{ values: number[]; onChange: (v: number[]) => void; underlay?: number[] | null; height?: number }`. Test ids: `curve-col-<i>` (one `rect` per block, `data-value` attribute), `curve-svg`, `curve-value-input`.

- [ ] **Step 1: Write the failing test** `src/ui/blend/__tests__/CurveEditor.component.test.ts`:

```ts
// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import CurveEditor from "../CurveEditor.svelte";
import { flatCurve } from "../../../lib/blend/curves";

afterEach(cleanup);

// jsdom may lack PointerEvent; MouseEvent carries clientX/clientY, which is all the editor reads.
if (!("PointerEvent" in window)) (window as unknown as Record<string, unknown>).PointerEvent = MouseEvent;

// jsdom has no layout: give the svg a fixed box so pointer x/y map to columns/values.
function box(el: Element, w = 240, h = 100) {
  el.getBoundingClientRect = () => ({ left: 0, top: 0, width: w, height: h, right: w, bottom: h, x: 0, y: 0, toJSON: () => ({}) });
}

describe("CurveEditor", () => {
  it("renders one column per DiT block with its value", () => {
    render(CurveEditor, { values: flatCurve(0.5), onChange: () => {} });
    expect(screen.getByTestId("curve-col-0").getAttribute("data-value")).toBe("0.5");
    expect(screen.getByTestId("curve-col-23")).toBeTruthy();
  });

  it("a drag from block 2 to block 6 rewrites every column between (no gaps)", async () => {
    const onChange = vi.fn();
    render(CurveEditor, { values: flatCurve(1), onChange });
    const svg = screen.getByTestId("curve-svg");
    box(svg);
    // 240 px / 24 blocks = 10 px per column; y 100 = value -0.5 (bottom), y 0 = 1.5 (top)
    await fireEvent.pointerDown(svg, { clientX: 25, clientY: 75, pointerId: 1 });   // block 2, value 0
    await fireEvent.pointerMove(svg, { clientX: 65, clientY: 25, pointerId: 1 });   // block 6, value 1
    await fireEvent.pointerUp(svg, { pointerId: 1 });
    const last = onChange.mock.calls.at(-1)![0] as number[];
    expect(last.slice(2, 7)).toEqual([0, 0.25, 0.5, 0.75, 1]);
  });

  it("double-click opens a typed value for that block", async () => {
    const onChange = vi.fn();
    render(CurveEditor, { values: flatCurve(1), onChange });
    await fireEvent.dblClick(screen.getByTestId("curve-col-4"));
    const input = screen.getByTestId("curve-value-input") as HTMLInputElement;
    await fireEvent.input(input, { target: { value: "0.3" } });
    await fireEvent.keyDown(input, { key: "Enter" });
    expect((onChange.mock.calls.at(-1)![0] as number[])[4]).toBe(0.3);
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd /home/kim/Projects/SAO/latent-forge && npx vitest run src/ui/blend`
Expected: FAIL (`Failed to resolve import "../CurveEditor.svelte"`).

- [ ] **Step 3: Implement** `src/ui/blend/CurveEditor.svelte`:

```svelte
<script lang="ts">
  // Owner: WINTERMUTE (created 2026-10-15)
  // The drawable per-DiT-block curve (spec 2026-10-15-adapter-mixer-design §4.2). Drag across the
  // columns to draw (every column between two pointer samples is filled), double-click a column to
  // type its value. Emits a NEW array on every change; never mutates `values`.
  import { CURVE_MAX, CURVE_MIN, N_BLOCKS, clampValue, drawSegment } from "../../lib/blend/curves";

  interface Props {
    values: number[];
    onChange: (v: number[]) => void;
    /** Grey bars behind the curve, same scale (e.g. the adapter's per-block change size). */
    underlay?: number[] | null;
    height?: number;
  }
  let { values, onChange, underlay = null, height = 110 }: Props = $props();

  const W = 240;                      // viewBox width: 10 units per block
  const COL = W / N_BLOCKS;
  const SPAN = CURVE_MAX - CURVE_MIN;
  const yOf = (v: number) => ((CURVE_MAX - v) / SPAN) * 100;
  const zeroY = yOf(0);
  const oneY = yOf(1);

  let svgEl: SVGSVGElement | undefined = $state();
  let last: { i: number; v: number } | null = null;
  let working: number[] = [];
  let editing = $state<number | null>(null);
  let typed = $state<number | string>("");   // bind:value on a number input yields a number

  function sample(e: PointerEvent): { i: number; v: number } {
    const r = svgEl!.getBoundingClientRect();
    const i = Math.max(0, Math.min(N_BLOCKS - 1, Math.floor(((e.clientX - r.left) / r.width) * N_BLOCKS)));
    const v = clampValue(Number((CURVE_MAX - ((e.clientY - r.top) / r.height) * SPAN).toFixed(2)));
    return { i, v };
  }
  function down(e: PointerEvent) {
    if (editing !== null) return;
    (e.currentTarget as Element).setPointerCapture?.(e.pointerId);
    const s = sample(e);
    working = drawSegment(values, s.i, s.v, s.i, s.v);
    last = s;
    onChange(working);
  }
  function move(e: PointerEvent) {
    if (!last) return;
    const s = sample(e);
    working = drawSegment(working, last.i, last.v, s.i, s.v);
    last = s;
    onChange(working);
  }
  function up() {
    last = null;
  }
  function startEdit(i: number) {
    editing = i;
    typed = String(values[i]);
  }
  function commit() {
    const v = Number(typed);
    if (editing !== null && Number.isFinite(v)) {
      const next = [...values];
      next[editing] = clampValue(v);
      onChange(next);
    }
    editing = null;
  }
</script>

<div class="curve">
  <svg bind:this={svgEl} data-testid="curve-svg" viewBox="0 0 {W} 100" preserveAspectRatio="none"
    style="height:{height}px" role="application" aria-label="per-block curve"
    onpointerdown={down} onpointermove={move} onpointerup={up} onpointercancel={up}>
    <line x1="0" x2={W} y1={oneY} y2={oneY} class="ref" />
    <line x1="0" x2={W} y1={zeroY} y2={zeroY} class="zero" />
    {#each values as v, i (i)}
      {#if underlay}
        <rect class="under" x={i * COL + 1} width={COL - 2}
          y={Math.min(yOf(underlay[i] ?? 0), zeroY)} height={Math.abs(yOf(underlay[i] ?? 0) - zeroY)} />
      {/if}
      <rect class="col" data-testid="curve-col-{i}" data-value={String(v)}
        x={i * COL + 1.5} width={COL - 3}
        y={Math.min(yOf(v), zeroY)} height={Math.max(0.5, Math.abs(yOf(v) - zeroY))}
        ondblclick={() => startEdit(i)} />
    {/each}
  </svg>
  <div class="axis"><span>block 0</span><span>12</span><span>23</span></div>
  {#if editing !== null}
    <label class="edit">block {editing}
      <input data-testid="curve-value-input" type="number" step="0.05" min={CURVE_MIN} max={CURVE_MAX}
        bind:value={typed} onkeydown={(e) => { if (e.key === "Enter") commit(); if (e.key === "Escape") editing = null; }}
        onblur={commit} />
    </label>
  {/if}
</div>

<style>
  .curve { position: relative; user-select: none; }
  svg { width: 100%; display: block; background: #121318; border: 1px solid #2a2a30; cursor: crosshair; touch-action: none; }
  .col { fill: #6aa8ff; }
  .under { fill: #3a3d46; }
  .ref { stroke: #444; stroke-dasharray: 2 2; stroke-width: 0.5; }
  .zero { stroke: #777; stroke-width: 0.6; }
  .axis { display: flex; justify-content: space-between; font-size: 10px; color: #888; }
  .edit { position: absolute; right: 4px; top: 4px; font-size: 11px; background: #1c1d22; padding: 2px 4px; }
  .edit input { width: 56px; }
</style>
```

Note on the test's numbers: with height 100 px, y=75 → value 1.5 − 0.75·2 = 0; y=25 → 1.0. With width 240 px, x=25 → block 2, x=65 → block 6.

- [ ] **Step 4: Run to verify it passes**

Run: `cd /home/kim/Projects/SAO/latent-forge && npx vitest run src/ui/blend && npm run check`
Expected: PASS, 0 type errors.

- [ ] **Step 5: Commit**

```bash
cd /home/kim/Projects/SAO && git add latent-forge/src/ui/blend
Misc/agent_commit.sh WINTERMUTE -m "latent-forge: CurveEditor, the drawable 24-block curve"
```

---

### Task 6: ADAPTER MIX bottom tab (ADVANCED FX switch, mode, shapes, transforms, editor)

**Files:**
- Modify: `latent-forge/src/lib/stores/view.svelte.ts` (`BottomTabId`, `BOTTOM_TAB_IDS`)
- Modify: `latent-forge/src/ui/shell/bottomTabs.ts` (tab + hint)
- Modify: `latent-forge/src/ui/shell/BottomPane.svelte` (render the tab)
- Create: `latent-forge/src/ui/blend/AdapterMixTab.svelte`
- Test: `latent-forge/src/ui/shell/__tests__/bottomTabs.test.ts` (update), `latent-forge/src/ui/blend/__tests__/AdapterMixTab.component.test.ts`

**Interfaces:**
- Consumes: `LoraBlend` (Task 2), `BLEND_IDEAS` (Task 3), `CURVE_SHAPES`, `soloCurve`, `invertCurve`, `smoothCurve`, `scaleCurve`, `flatCurve` (Task 4), `CurveEditor` (Task 5), `arrangement.lanes[view.activeLane].chain`, `view.setBottomTab`.
- Produces: tab id `"adapter-mix"`; test ids `adapter-fx-toggle`, `adapter-mode`, `adapter-shape`, `adapter-solo`, `adapter-invert`, `adapter-smooth`, `adapter-half`, `adapter-double`, `adapter-reset`, `adapter-missing`.

- [ ] **Step 1: Write the failing tests**

Update `bottomTabs.test.ts` expectations to five tabs:

```ts
    expect(BOTTOM_TABS.map((t) => t.id)).toEqual(["chroma", "prompt", "mix", "adapter-mix", "terminal"]);
    expect(BOTTOM_TABS.map((t) => t.label)).toEqual([
      "CHROMA", "PROMPT + SIGMA", "MIX + SIGNAL PATH", "ADAPTER MIX", "TERMINAL",
    ]);
```

and add `expect(bottomHint("adapter-mix")).toBe("draw how much of the adapter acts in each DiT block");`. Rename the `describe` to `"the bottom tab row: spec §4.5's four tabs plus ADAPTER MIX"`.

Create `src/ui/blend/__tests__/AdapterMixTab.component.test.ts`:

```ts
// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/svelte";
import { tick } from "svelte";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { CHAIN_DEFAULTS } from "../../../lib/forge/defaults";
import { arrangement } from "../../../lib/stores/arrangement.svelte";
import { view } from "../../../lib/stores/view.svelte";
import AdapterMixTab from "../AdapterMixTab.svelte";

afterEach(cleanup);
beforeEach(() => {
  view.setActiveLane(0);
  for (const lane of arrangement.lanes) lane.chain = structuredClone(CHAIN_DEFAULTS);
});

describe("ADAPTER MIX tab", () => {
  it("says what is missing when the lane has no adapter on", () => {
    render(AdapterMixTab);
    expect(screen.getByTestId("adapter-missing").textContent).toMatch(/LORA \/ DORA/);
  });

  it("ADVANCED FX creates a flat amount curve on the active lane's chain, in place", async () => {
    arrangement.lanes[0].chain.lora_on = true;
    arrangement.lanes[0].chain.lora.ckpt_path = "/a.ckpt";
    const before = arrangement.lanes[0].chain;
    render(AdapterMixTab);
    await fireEvent.click(screen.getByTestId("adapter-fx-toggle"));
    expect(arrangement.lanes[0].chain).toBe(before);
    expect(arrangement.lanes[0].chain.lora.blend).toEqual({ on: true, mode: "amount", curve: Array(24).fill(1) });
  });

  it("a shape and a transform rewrite the curve", async () => {
    arrangement.lanes[0].chain.lora = { ckpt_path: "/a.ckpt", slot: null, strength: 1,
      blend: { on: true, mode: "amount", curve: Array(24).fill(1) } };
    arrangement.lanes[0].chain.lora_on = true;
    render(AdapterMixTab);
    await fireEvent.change(screen.getByTestId("adapter-shape"), { target: { value: "last8_off" } });
    expect(arrangement.lanes[0].chain.lora.blend!.curve.slice(16)).toEqual(Array(8).fill(0));
    await fireEvent.click(screen.getByTestId("adapter-invert"));
    expect(arrangement.lanes[0].chain.lora.blend!.curve[0]).toBe(0);
  });

  it("follows the active lane", async () => {
    arrangement.lanes[1].chain.lora_on = true;
    arrangement.lanes[1].chain.lora = { ckpt_path: "/b.ckpt", slot: null, strength: 1,
      blend: { on: true, mode: "direction", curve: Array(24).fill(0.5) } };
    render(AdapterMixTab);
    view.setActiveLane(1);
    await tick();
    expect((screen.getByTestId("adapter-mode") as HTMLSelectElement).value).toBe("direction");
    expect(screen.getByTestId("curve-col-0").getAttribute("data-value")).toBe("0.5");
  });
});
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd /home/kim/Projects/SAO/latent-forge && npx vitest run src/ui/shell/__tests__/bottomTabs.test.ts src/ui/blend`
Expected: FAIL (tab list has four entries; `AdapterMixTab.svelte` missing).

- [ ] **Step 3: Implement**

`view.svelte.ts`: `export type BottomTabId = "chroma" | "prompt" | "mix" | "adapter-mix" | "terminal";` and `export const BOTTOM_TAB_IDS: BottomTabId[] = ["chroma", "prompt", "mix", "adapter-mix", "terminal"];`

`bottomTabs.ts`: insert `{ id: "adapter-mix", label: "ADAPTER MIX" },` before the terminal entry, and in `bottomHint` add `case "adapter-mix": return "draw how much of the adapter acts in each DiT block";`.

`BottomPane.svelte`: `import AdapterMixTab from "../blend/AdapterMixTab.svelte";` and add `{:else if tab === "adapter-mix"}<AdapterMixTab />` before the `{:else}` (Terminal) branch. Update the comment line that lists the tab bodies to mention ADAPTER MIX (adapter mixer phase 1).

`src/ui/blend/AdapterMixTab.svelte`:

```svelte
<script lang="ts">
  // Owner: WINTERMUTE (created 2026-10-15)
  // ADAPTER MIX, phase 1 (spec 2026-10-15-adapter-mixer-design §4.2): the active lane's LoRA/DoRA as a
  // per-DiT-block curve. Edits arrangement.lanes[view.activeLane].chain.lora IN PLACE (the $state proxy
  // rule in LaneChain.svelte); the curve array itself is replaced on every edit.
  import { arrangement } from "../../lib/stores/arrangement.svelte";
  import { view } from "../../lib/stores/view.svelte";
  import { BLEND_IDEAS } from "../../lib/blend/registry";
  import {
    CURVE_SHAPES, N_BLOCKS, flatCurve, invertCurve, scaleCurve, smoothCurve, soloCurve,
  } from "../../lib/blend/curves";
  import type { BlendMode } from "../../lib/forge/types";
  import CurveEditor from "./CurveEditor.svelte";

  const chain = $derived(arrangement.lanes[view.activeLane].chain);
  const blend = $derived(chain.lora.blend ?? null);
  const missing = $derived(!chain.lora_on || !chain.lora.ckpt_path);
  let solo = $state(0);
  let shapePick = $state("");

  function toggleFx() {
    if (!chain.lora.blend) chain.lora.blend = { on: true, mode: "amount", curve: flatCurve(1) };
    else chain.lora.blend.on = !chain.lora.blend.on;
  }
  function setCurve(c: number[]) {
    if (chain.lora.blend) chain.lora.blend.curve = c;
  }
  function setMode(m: string) {
    if (chain.lora.blend) chain.lora.blend.mode = m as BlendMode;
  }
  function applyShape(id: string) {
    const s = CURVE_SHAPES.find((x) => x.id === id);
    if (s) setCurve(s.make());
    shapePick = "";
  }
</script>

<div class="adapter-mix">
  <div class="row">
    <button data-testid="adapter-fx-toggle" class:on={blend?.on} onclick={toggleFx}>
      ADVANCED FX {blend?.on ? "ON" : "OFF"}
    </button>
    <span class="lane">lane {view.activeLane + 1}</span>
    {#if missing}
      <span class="warn" data-testid="adapter-missing">turn on LORA / DORA and pick an adapter in LANE CHAIN first</span>
    {/if}
  </div>
  {#if blend}
    <div class="row" class:dim={!blend.on}>
      <select data-testid="adapter-mode" value={blend.mode} onchange={(e) => setMode((e.currentTarget as HTMLSelectElement).value)}>
        {#each BLEND_IDEAS as b (b.id)}<option value={b.id} title={b.help}>{b.label}</option>{/each}
      </select>
      <select data-testid="adapter-shape" value={shapePick} onchange={(e) => applyShape((e.currentTarget as HTMLSelectElement).value)}>
        <option value="">shape…</option>
        {#each CURVE_SHAPES as s (s.id)}<option value={s.id}>{s.label}</option>{/each}
      </select>
      <label>solo <input data-testid="adapter-solo" type="number" min="0" max={N_BLOCKS - 1} step="1" bind:value={solo}
        onchange={() => setCurve(soloCurve(Math.max(0, Math.min(N_BLOCKS - 1, Math.round(solo)))))} /></label>
      <button data-testid="adapter-invert" onclick={() => setCurve(invertCurve(blend.curve))}>invert</button>
      <button data-testid="adapter-smooth" onclick={() => setCurve(smoothCurve(blend.curve))}>smooth</button>
      <button data-testid="adapter-half" onclick={() => setCurve(scaleCurve(blend.curve, 0.5))}>×½</button>
      <button data-testid="adapter-double" onclick={() => setCurve(scaleCurve(blend.curve, 2))}>×2</button>
      <button data-testid="adapter-reset" onclick={() => setCurve(flatCurve(1))}>reset</button>
    </div>
    <CurveEditor values={blend.curve} onChange={setCurve} height={96} />
  {/if}
</div>

<style>
  .adapter-mix { padding: 4px 8px; font-size: 12px; }
  .row { display: flex; gap: 6px; align-items: center; margin-bottom: 4px; flex-wrap: wrap; }
  .dim { opacity: 0.5; }
  .on { background: #2f5d2f; }
  .warn { color: #e0a040; }
  .lane { color: #888; }
  input[type="number"] { width: 44px; }
</style>
```

- [ ] **Step 4: Run to verify they pass, plus the shell/layout suites**

Run: `cd /home/kim/Projects/SAO/latent-forge && npx vitest run src/ui/shell src/ui/blend && npm run check`
Expected: PASS (the layout test's height budget still holds: the tab body is 162 px; the editor is 96 px + two rows + axis).

- [ ] **Step 5: Commit**

```bash
cd /home/kim/Projects/SAO && git add latent-forge/src/lib/stores/view.svelte.ts latent-forge/src/ui/shell/bottomTabs.ts latent-forge/src/ui/shell/BottomPane.svelte latent-forge/src/ui/shell/__tests__/bottomTabs.test.ts latent-forge/src/ui/blend/AdapterMixTab.svelte latent-forge/src/ui/blend/__tests__/AdapterMixTab.component.test.ts
Misc/agent_commit.sh WINTERMUTE -m "latent-forge: ADAPTER MIX bottom tab (ADVANCED FX, mode, shapes, transforms, curve)"
```

---

### Task 7: Right pane — SCALE greyed out, status line, "open mixer"

**Files:**
- Modify: `latent-forge/src/ui/modules/LaneChain.svelte` (LoRA block)
- Modify: `latent-forge/src/lib/help/strings.ts` (`HelpKey` union + `loraBlend` string)
- Test: `latent-forge/src/ui/modules/__tests__/LaneChain.component.test.ts`

**Interfaces:**
- Consumes: `LoraBlend` (Task 2), `blendIdea` (Task 3), `isFlatOne` (Task 4), `view.setBottomTab` with `"adapter-mix"` (Task 6).
- Produces: test ids `lora-blend-status`, `lora-open-mixer`; the SCALE `ParamField` gets `disabled={!!chain.lora.blend?.on}`.

- [ ] **Step 1: Write the failing test** (append to `LaneChain.component.test.ts`; its `beforeEach` already mocks the network):

```ts
describe("LORA / DORA with ADVANCED FX (adapter mixer phase 1)", () => {
  it("greys out SCALE, shows the blend status and opens the mixer tab", async () => {
    arrangement.lanes[0].chain.lora_on = true;
    arrangement.lanes[0].chain.lora = { ckpt_path: "/SERVER/lora1.safetensors", slot: null, strength: 1,
      blend: { on: true, mode: "amount", curve: [...Array(16).fill(1), ...Array(8).fill(0)] } };
    render(LaneChain);
    const scale = screen.getByLabelText("LORA / DORA SCALE") as HTMLInputElement;
    expect(scale.disabled).toBe(true);
    expect(screen.getByTestId("lora-blend-status").textContent).toBe("blend: amount · 8 of 24 blocks shaped");
    await fireEvent.click(screen.getByTestId("lora-open-mixer"));
    expect(view.bottomTab).toBe("adapter-mix");
  });

  it("without ADVANCED FX the LoRA block is unchanged", () => {
    render(LaneChain);
    expect(screen.queryByTestId("lora-blend-status")).toBeNull();
    expect((screen.getByLabelText("LORA / DORA SCALE") as HTMLInputElement).disabled).toBe(false);
  });
});
```

(`ParamField` labels its number field exactly `name` and its slider `"<name> slider"`, so `getByLabelText("LORA / DORA SCALE")` is the number field; both carry the same `disabled`.)

- [ ] **Step 2: Run to verify it fails**

Run: `cd /home/kim/Projects/SAO/latent-forge && npx vitest run src/ui/modules/__tests__/LaneChain.component.test.ts`
Expected: FAIL (no `lora-blend-status`; SCALE enabled).

- [ ] **Step 3: Implement**

`strings.ts`: add `| "loraBlend"` to the `HelpKey` union after `"loraScale"`, and the entry
`loraBlend: "ADVANCED FX is on: the ADAPTER MIX curve sets this adapter's strength per DiT block, so SCALE is off. Turn ADVANCED FX off in ADAPTER MIX to get SCALE back.",` after `loraScale`.

`LaneChain.svelte`: add imports `import { blendIdea } from "../../lib/blend/registry";` and `import { N_BLOCKS } from "../../lib/blend/curves";`, and in the script

```ts
  const blendOn = $derived(!!chain.lora.blend?.on);
  const blendStatus = $derived.by(() => {
    const b = chain.lora.blend;
    if (!b?.on) return "";
    const shaped = b.curve.filter((v) => v !== 1).length;
    return `blend: ${blendIdea(b.mode).label.split(" ")[0]} · ${shaped} of ${N_BLOCKS} blocks shaped`;
  });
```

Replace the SCALE `ParamField` with:

```svelte
  <ParamField label="SCALE" name="LORA / DORA SCALE" help={blendOn ? HELP.loraBlend : HELP.loraScale}
    value={chain.lora.strength} onValue={(v) => (chain.lora.strength = v)} min={0} max={1} step={0.01} decimals={2}
    disabled={blendOn} />
  {#if blendOn}
    <div class="row">
      <span data-testid="lora-blend-status">{blendStatus}</span>
      <button data-testid="lora-open-mixer" onclick={() => view.setBottomTab("adapter-mix")}>open mixer</button>
    </div>
  {/if}
```

Add `// Last edited: WINTERMUTE 2026-10-15 — LoRA: SCALE greyed under ADVANCED FX, blend status, open mixer` as the first line inside the `<script>` block's comment. With 16 ones and 8 zeros the status reads exactly `blend: amount · 8 of 24 blocks shaped`.

- [ ] **Step 4: Run to verify it passes, and the full suite**

Run: `cd /home/kim/Projects/SAO/latent-forge && npx vitest run && npm run check`
Expected: the whole latent-forge suite PASSES, 0 type errors.

- [ ] **Step 5: Commit**

```bash
cd /home/kim/Projects/SAO && git add latent-forge/src/ui/modules/LaneChain.svelte latent-forge/src/lib/help/strings.ts latent-forge/src/ui/modules/__tests__/LaneChain.component.test.ts
Misc/agent_commit.sh WINTERMUTE -m "latent-forge: LoRA SCALE greyed under ADVANCED FX, blend status, open mixer"
```

---

### Task 8: Contract doc + one end-to-end GPU check

**Files:**
- Create: `docs/latent-forge/contract/chain-lora-blend.md`
- Modify: `RUNBOOK.md` (one short entry under the Latent Forge / render server section)

**Interfaces:**
- Consumes: everything above; the render server must be running code that includes SAO `5522423` (restart it if it predates that commit).

- [ ] **Step 1: Write the contract doc** `docs/latent-forge/contract/chain-lora-blend.md`:

```markdown
# chain.lora blend fields (adapter mixer phase 1, WINTERMUTE 2026-10-15)

Spec: docs/superpowers/specs/2026-10-15-adapter-mixer-design.md. Server: eval/forge/render_settings.py
(parse_chain / chain_to_request) -> the `dora` request -> GHOST-NOTE's _apply_block_profile (SAO 5522423).

| field | type | default | meaning |
|---|---|---|---|
| `lora.block_strengths` | 24 numbers in -0.5..1.5, or absent | absent | per-DiT-block multiplier on `lora.strength` |
| `lora.blend` | `"interp"` or absent | absent | `"interp"` = true weight interpolation with the base (`amount`); absent = stock strength (`direction`) |

- The GUI sends neither key unless ADVANCED FX is on, so an untouched chain is byte-identical to before.
- With blending on, the GUI sends `strength: 1` (the curve is the strength) and `slot: null`; the server
  rejects `block_strengths` without a `ckpt_path` (the block profile only applies to an adapter loaded by path).
- GUI state: `LaneChain.lora.blend = {on, mode: "amount" | "direction", curve[24]}`, saved in sessions and in
  `lora` module presets; `src/lib/blend/registry.ts` maps it to the wire fields.
```

- [ ] **Step 2: Verify the server is on the backend commit**

Run: `curl -s -m 5 http://127.0.0.1:8056/status && ps -o lstart= -p $(pgrep -f "explorer_render_server.py --port 8056" | head -1)` and compare with `git -C /home/kim/Projects/SAO log -1 --format=%ci 5522423`.
Expected: the server started after the commit time. If not, coordinate with whoever holds the GPU lock (`Misc/gpu_guard.sh who WINTERMUTE`), then `eval/forge/dev_server.sh stop` and `eval/forge/dev_server.sh start WINTERMUTE`.

- [ ] **Step 3: GPU check — `amount` flat 1 equals a plain DoRA render; a shaped curve differs**

Run (SAO root; replace `<DORA>` with a real adapter path from the model picker, e.g. the punch DoRA in `/home/kim/Music/latch/combo/punch/cleanest-20261009-143711-gen/result.json` → `meta.dora_loaded`):

```bash
cd /tmp && /home/kim/Projects/SAO/.venv/bin/python - <<'EOF'
import json, numpy as np, requests
D = "<DORA>"
base = {"prompt": "psytrance, 140 bpm", "duration": 10, "steps": 24, "cfg_scale": 7, "seed": 1234, "sampler_type": "euler"}
def z(dora):
    r = requests.post("http://127.0.0.1:8056/generate", json={**base, "dora": dora}, timeout=600).json()
    return np.load(r["latents"][0])
plain = z({"ckpt_path": D, "strength": 1.0})
flat = z({"ckpt_path": D, "strength": 1.0, "block_strengths": [1.0] * 24, "blend": "interp"})
late = z({"ckpt_path": D, "strength": 1.0, "block_strengths": [1.0] * 16 + [0.0] * 8, "blend": "interp"})
cos = lambda a, b: float((a * b).sum() / np.linalg.norm(a) / np.linalg.norm(b))
print(json.dumps({"flat_vs_plain": round(cos(plain, flat), 5), "late_off_vs_plain": round(cos(plain, late), 5)}))
EOF
```

Expected: `flat_vs_plain` ≥ 0.999 (interp at 1 = the full adapter); `late_off_vs_plain` clearly lower (e.g. < 0.99). If `flat_vs_plain` is low, `interp` at strength 1 is not the plain adapter: stop and report to GHOST-NOTE (backend owner) before shipping.

- [ ] **Step 4: Manual GUI check** — `cd latent-forge && npm run dev`, open the app, LANE CHAIN → LORA / DORA ON + pick an adapter, open ADAPTER MIX, ADVANCED FX ON, pick "last 8 off", render one clip. Confirm in the TERMINAL tab / server log the line `[dora] block profile applied: blend=interp ... blocks_set=` and that SCALE is greyed in LANE CHAIN.

- [ ] **Step 5: RUNBOOK entry + commit**

Add under the Latent Forge section of `RUNBOOK.md`:

```markdown
- **Per-block LoRA/DoRA blending (ADAPTER MIX tab, 2026-10-15):** LANE CHAIN → LORA / DORA on + an adapter →
  ADAPTER MIX → ADVANCED FX ON, draw or pick a shape. SCALE greys out; the curve is the strength per DiT block.
  Needs a render server started after SAO 5522423. Contract: docs/latent-forge/contract/chain-lora-blend.md.
```

```bash
cd /home/kim/Projects/SAO && git add docs/latent-forge/contract/chain-lora-blend.md RUNBOOK.md
Misc/agent_commit.sh WINTERMUTE -m "docs: chain.lora blend contract + RUNBOOK entry (adapter mixer phase 1)"
```

---

## After Phase 1

Phase 2 (own plan): the server-side weight compositor (`eval/adapter_mixer.py`), the `mix` request object, pairs with
crossfade / sum / subtract / A-only, PARALLEL / CHAIN, the expand toggle, `/mix/profile` underlay, presets of whole
mixes. Phase 3 (own plan): both patch bays, EXPORT, experiment log.
