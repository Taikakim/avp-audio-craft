# chain.lora blend fields (adapter mixer phase 1, 2026-10-15)

Plan: docs/superpowers/plans/2026-10-15-adapter-mixer-phase1.md (WINTERMUTE). Implemented by KUANG on branch
`feature/adapter-mixer-phase1`. Spec: docs/superpowers/specs/2026-10-15-adapter-mixer-design.md. Server path:
eval/forge/render_settings.py (parse_chain / chain_to_request) -> the `dora` request -> GHOST-NOTE's
_apply_block_profile (SAO 5522423) in eval/explorer_render_server.py.

| field | type | default | meaning |
|---|---|---|---|
| `lora.block_strengths` | 24 numbers in -0.5..1.5, or absent | absent | per-DiT-block multiplier on `lora.strength` |
| `lora.blend` | `"interp"` or absent | absent | `"interp"` = true weight interpolation with the base (`amount`); absent = stock strength (`direction`) |

- The GUI sends neither key unless ADVANCED FX is on, so an untouched chain is byte-identical to before.
- With blending on, the GUI sends `strength: 1` (the curve is the strength) and `slot: null`; the server
  rejects `block_strengths` without a `ckpt_path` (the block profile only applies to an adapter loaded by path).
- GUI state: `LaneChain.lora.blend = {on, mode: "amount" | "direction", curve[24]}`, saved in sessions and in
  `lora` module presets; `src/lib/blend/registry.ts` maps it to the wire fields.

## Adapter types (what the backend actually does)

Read from stable_audio_3/models/lora/model.py (`LoRAParametrization`), 2026-10-15:

| adapter type | `amount` (`blend: "interp"`) | `direction` at exactly 0 |
|---|---|---|
| `dora`, `dora-rows`, `dora-cols` | exact interpolation `W + c·(W_dora − W)` | base weights (early return) |
| `lora`, `lora-xs`, `phm`, `phm2` | same as `direction` (linear in strength, so already interpolation) | base weights |
| `bora`, `dora-rows-xs`, `dora-cols-xs`, `bora-xs` | **not implemented**: `lora_interp` is ignored, the layer keeps the stock per-block strength | base weights |

- For the last row the render server now adds a warning to the response (`warnings`), naming the types:
  `blend 'amount' (true interpolation) is not implemented for adapter type(s) ...`. Few adapters of those types
  are trained (Kim, 2026-10-15), so this is a notification, not a fix.
- **DoRA in `direction` mode is discontinuous at 0:** a value of exactly 0 returns the base weights, but any value
  above 0 keeps the trained magnitude in full, so 0.05 is close to the full adapter. Ramp-downs therefore do not
  fade to the base in `direction` mode. The mode's help text and the ADAPTER MIX tab say so; `amount` (the
  default) has no jump.
