# Adapter mixer: per-block blending of LoRAs/DoRAs and block patching (Latent Forge ADVANCED FX)

Owner: WINTERMUTE (created 2026-10-15). Status: design approved in conversation 2026-10-15; this spec awaits review.
Origin: GHOST-NOTE's per-block DoRA strength backend (SAO `5522423`, stable-audio-3 `lora_interp`) and the request for a
drawable "LoRA blending options" module, widened in the design conversation into a mixer board.

## 1. Purpose and success

An experimentation instrument for sound design: combine LoRA/DoRA adapters block by block across the DiT, draw how
much of each acts where, and deliberately mis-wire blocks. A secondary aim is learning about the architecture: every
render made with the mixer keeps its exact configuration, so experimenting accumulates evidence about what the
blocks do.

Success: the user draws a curve or picks a shape, renders, and hears a difference, without typing numbers. The
default path (no mixer) is byte-identical to today.

Decisions taken in the conversation (owner's choices):
- Combination topology is a user switch per board: PARALLEL (pair results summed) or CHAIN (each result feeds the
  next pair). Row order matters in CHAIN.
- A curve addresses the 24 DiT blocks; an expand toggle splits it into attention and feed-forward curves.
- Cross-patching: (a) adapter-block routing and (c) base-model block order. Weight-garden ops (shuffle, blur, ...)
  become a separate module later.
- Patch bay workflow: a scramble-distance knob + seed + Apply, then manual swaps.
- Mixing happens server-side in a weight compositor; an EXPORT button writes the result as a checkpoint.
- The whole mixer is an optional ADVANCED FX. The plain LoRA strength stays in the right pane for quick work; turning
  ADVANCED FX on greys it out and the board takes over.

Out of scope: the T5 text encoder and the FiLM adapter (DiT blocks only); repeating or skipping blocks in the base
order (a later extension); weight-garden ops (later, own module); the mir Dash explorer (may adopt the payload later).

## 2. Architecture

```
GUI (Latent Forge)                       render server :8056                         model
Mixer board (bottom pane) ──┐
LoRA module (right pane) ───┼─► "mix" object in the request ─► compositor ─► mixed DiT weights ─► sampler
Patch bays ─────────────────┘     (one source of truth)        │ cache keyed by mix hash
                                                               └─► EXPORT: merged checkpoint + sidecar
```

### 2.1 The `mix` request object

Optional key on `/generate` (and every op that takes a `dora` block). Absent = unchanged behaviour.

```json
"mix": {
  "schema": 1,
  "adapters": [{"id": "a", "path": "<ckpt>", "weights": "online"}, {"id": "b", "path": "<ckpt>"}],
  "routing": "parallel",                       // "parallel" | "chain"
  "pairs": [
    {"a": "a", "b": "b", "op": "crossfade", "gain": 1.0,
     "curve": [24 floats]                      // collapsed
     // or "curves": {"attn": [24], "ff": [24]} when expanded
    },
    {"a": "a", "b": null, "op": "amount", "gain": 1.0, "curve": [24 floats]}
  ],
  "patch": {
    "adapter_routing": [24 ints],              // slot i receives the COMBINED delta (after all pairs) of block routing[i]; repeats allowed
    "base_order": [24 ints]                    // a permutation of 0..23: the order the DiT runs its blocks
  }
}
```

- `b` may be another adapter id or `"base"` (zero delta). In CHAIN mode pair k>0 takes the previous result as its A;
  its `a` field is ignored and the GUI shows "<- result of pair k-1".
- `weights`: "online" or "ema", for checkpoints that carry both; ignored otherwise.
- A request carrying `mix` together with the plain `dora` adapter fields is rejected (400): one mechanism per request.
- GHOST-NOTE's existing `dora.block_strengths` / `dora.blend` keep working unchanged; they are the single-adapter case
  and the GUI's phase-1 module may emit either form (see 6.1).

### 2.2 Compositor (new server module, `eval/adapter_mixer.py`)

Pure functions over a module tree plus a thin stateful wrapper; unit-testable on CPU.

- Adapters are held as their checkpoint tensors (low-rank factors and DoRA magnitudes), not as full deltas.
- Build, per DiT linear layer in block b: compute each adapter's full weight change `Δ = W_adapter - W_base`, including
  DoRA's magnitude normalisation, so DoRA is exact. Combine per section 3, apply `gain`, then the patch, and write
  `W_base + Δ_total` into the working DiT.
- Block of a parameter: `layers.<N>.` in the DiT's module names (the T5 conditioner's own `layers.N` is excluded, as
  in `_apply_block_profile`). Attention group = self- and cross-attention projections; feed-forward group = everything
  else in the block (feed-forward, conditioning/adaLN projections).
- `base_order` reorders the DiT's block list for the request (a view, not a copy).
- The base weights are restored in a `finally` after every request.
- Cache: the last 3 built mixes, keyed by a hash of the canonical `mix` JSON plus the adapter files' mtimes, on CPU.
- `/mix/profile?path=<ckpt>`: per-block relative size of an adapter's change (`||Δ_b|| / ||W_b||`), for the curve
  underlay. GHOST-NOTE's punch-DoRA profile (`Mantu2/latch_sweep/dora_blend_2026-10-15/punch_dora_layer_profile.json`)
  is the reference output.

## 3. Operations

`ΔA`, `ΔB`: the adapters' changes; `c(b)`: the curve value at block b (attention or feed-forward curve when expanded).

| op | per block | use |
|---|---|---|
| `amount` (one adapter) | `c·ΔA` | true blend with the base model (GHOST-NOTE's `blend: "interp"`) |
| `direction` (one adapter) | stock DoRA strength `c` per block | GHOST-NOTE's default `block_strengths` behaviour |
| `crossfade` | `(1-c)·ΔA + c·ΔB` | morph A to B block by block |
| `sum` | `ΔA + c·ΔB` | layer B on top of A |
| `subtract` | `ΔA - c·ΔB` | take B's character out of A |
| `a_only` | `ΔA - c·proj_ΔB(ΔA)`, `proj_v(u) = (⟨u,v⟩/⟨v,v⟩)·v` per layer | what A does that B does not |

Pair result = `gain · op(...)`. PARALLEL: `Δ_total = Σ pair results`. CHAIN: `r_0 = pair_0`, `r_k = op_k(r_{k-1}, B_k)`,
`Δ_total = r_last`. Curve values range -0.5..1.5.

## 4. GUI

### 4.1 Right pane, LoRA module
- ADVANCED FX off (default): checkpoint + strength, unchanged.
- ADVANCED FX on: strength greyed out; a status line ("blend: 2 pairs · chain · patched"); an "open mixer" button.

### 4.2 Bottom pane tab "ADAPTER MIX"
- Header: ADVANCED FX switch, routing PARALLEL | CHAIN, save/load preset, EXPORT.
- One row per pair: A picker, op picker, B picker (adapter or "base"), gain, expand toggle, drag handle (CHAIN order),
  and the curve editor. "+ add pair".
- Curve editor: 24 snapped columns; drag across to draw freehand, drag a point, double-click to type a value; grey
  underlay from `/mix/profile`; shapes: flat, early ramp-down, late ramp-down, middle bell, ascending exp, descending
  exp, early only, last 8 off, solo block N, alternating; transforms: invert, smooth, x0.5, x2, reset.
- Patch bay, target switch "adapter routing | base block order": 24 slots with lines from source to slot, coloured by
  distance; scramble distance knob (0-8) + seed + Apply (random permutation, each block moved at most the distance);
  drag a slot onto another to swap; reset.
- Adapter pickers use the same list as the top-bar model picker.

### 4.3 Registry
Each operation is one registry entry: id, label, its controls, and a function from its UI state to the pair's JSON. A
new blend idea = one file plus one registry line.

### 4.4 Presets and experiment log
- A mix is a preset kind in the Latent Forge's module-preset system (`src/lib/chains/modulePresets.ts`).
- Every render with ADVANCED FX on stores its `mix` JSON beside the render; a note or rating can be attached. This
  log is the architecture-probing record.

## 5. Errors, limits, export

- Validation before any GPU work: unknown/offline adapter path (400, names it); curves must have 24 finite values in
  range; `base_order` must be a permutation of 0..23; `adapter_routing` entries in 0..23.
- Non-finite render output: returned as a warning naming the mix, no file written (same guard family as
  `z0_is_finite`).
- Memory: adapters as checkpoint tensors; cache of 3 built mixes, a few GB each, on CPU (91 GB RAM).
- EXPORT: the mixed DiT state dict written as a full-finetune checkpoint on the Mantu2 data drive, plus a sidecar with
  the exact `mix` JSON, source adapters and date; it then appears in the model picker. Goa-trained mixes stay private
  (three-tier rights policy, MASTER §4).

## 6. Testing

- CPU unit tests on a tiny fake DiT (2 blocks): crossfade at 0 = A and at 1 = B; `amount` at 1 = merged DoRA;
  `a_only` removes exactly the projection; CHAIN vs PARALLEL; patch permutations; base restored after an exception;
  cache hit on a repeated mix; validation errors.
- GUI (vitest): curve snapping, shapes and transforms; registry to JSON; ADVANCED FX off leaves the request
  byte-identical; a contract fixture shared with the server (`docs/latent-forge/contract/fixtures`).
- One GPU check after the server restart: no mix = plain render; `amount` flat 1 = a plain DoRA render at strength 1
  (latents near-identical).

### 6.1 Phase-1 note
Phase 1 may send GHOST-NOTE's `dora.block_strengths` + `dora.blend` for the single-adapter case until the compositor
lands; the GUI hides the difference.

## 7. Phases (each usable on its own)

1. Compositor + single-adapter `amount` / `direction` + curve editor; right-pane switch and greying. Covers
   GHOST-NOTE's original request.
2. Pairs, the four two-adapter operations, PARALLEL / CHAIN, presets.
3. Both patch bays, EXPORT, experiment log.
