# Plan: melody-control UX — folding Heads A/B into the existing explorer

CONTINUITY 2026-07-22. Companion to the design note
`docs/superpowers/specs/2026-07-22-melodic-latch-film.md` (§4 = the Kim-approved UX
direction this plan implements). Planning only — no code changed. Integration target is
the **existing SA3 latent explorer** (steering contract v2), NOT a new app.

Discovery pass done before writing (per CLAUDE.md): explorer + server + gradio surfaces
read in full; parity audit `docs/latent-tool-parity-audit-2026-07-12.md`; eval-tables
spec `docs/superpowers/specs/2026-07-06-eval-tables-human-first.md` (§14 three-audience
standard governs the Phase-0 page); musicology data (`eval/musicology/`) inspected.

---

## 1. Current-state map (what the melody controls extend)

### 1.1 The explorer UI (primary surface)
`/home/kim/Projects/mir/plots/explorer_sa3/` (mir repo, branch `sa3-latent-explorer`,
Dash app; server-resident model lives separately, below).

- **`controls.py` — the shared steering panel + the v2 contract.** One panel class
  instantiated per namespace (`ns="inf"` inference tab, `ns="a2a"`).
  - `_latch_slot()` `controls.py:35-64` — one LatCH slot row = 8 widgets:
    `head, kind, value, gain, start, end, loss, wsec`. `LATCH_SLOTS = 3`
    (`controls.py:16`) — a **UI** limit only; the server accepts an unbounded list.
  - `steering_states()` `controls.py:122-143` — **EXACTLY 35 States in fixed order**
    (v2; grown append-only from 23): 3 slots × 8 + film(3: enable/value/gain) +
    dora(4: name/strength/interval_min/interval_max) + LatCH-adv(4: rho/mu/gamma/n_iter).
  - `steering_payload()` `controls.py:146-209` — consumes the 35 values → the JSON
    blocks `{"latch": [...], "film": {...}|null, "dora": {...}|null}` + top-level
    `rho/mu/gamma/n_iter`. Per-slot dict:
    `{head, kind, value, gain, start_pct, end_pct, [loss_type], [w_sec]}`.
  - `register()` `controls.py:212-241` — head dropdown options + per-head default
    autofill are **pulled from the server's `/info.latch_heads`** — a new head that
    appears in the registry shows up in the UI with zero UI code.
  - Loss options list `controls.py:26-27` (`_LOSS_OPTIONS`) — UI-side allowlist; new
    loss types must be appended here.
- **`inference_tab.py`** — panel mounted at `:156` (`controls.steering_panel("inf")`),
  states appended to the render callback at `:270`, payload built at `:290`, POSTed via
  `render_client.render(op, payload)` at `:489`.
- **`render_client.py`** — thin HTTP client to :8056; `info()` feeds autofill.

### 1.2 The render server (where payload → model)
`/home/kim/Projects/SAO/eval/explorer_render_server.py` (:8056, FastAPI, model-resident).

- **`resolve_latch()` `:463-517`** — the server half of the v2 contract. Per slot:
  head name → `HEADS` registry lookup (or raw `path`), builds
  `{model_path, kind, value, start_pct, end_pct, [loss_type], [w_sec], weight}`;
  **`builtin` slots** (`:471-478`) run with NO checkpoint (E1 recurrence potential
  precedent — the exact pattern a computed "hookness" target can ride).
  Gain normalization: `rho = mu = slot-1 gain`, per-slot `weight = gain/g0` (`:512-516`).
- **Head registry `scan_latch_heads()` `:305-312`** — globs
  `stable-audio-3/latch_weights_sa3_medium/latch_sa3_*_best.pt`; `_head_entry()`
  `:274-302` loads each via `load_latch_from_checkpoint` and derives
  name/family/default_gain/out_channels/loss_type/target-kind/slider min-max from ckpt
  metadata → served at **`/info` `:544-550`**. ⇒ **Head A lands in the UI automatically**
  the moment `latch_sa3_melody_contour_best.pt` exists in that dir (slider ranges come
  from its `metadata`; set them at head-save time).
- **FiLM adapter path (what Head B extends):** `_install_film()` `:331-349`
  (single slot, `ScalarAttributeEncoder`, `scalar_norm`), `film_context()` `:447-459` —
  currently **scalar-only**: value → normalize → encoder → 16 control tokens →
  `ControlContext(cc, gain)`. `prepare_model()` `:394-444` rebuild state machine
  (one FiLM slot; ckpt swap forces model rebuild).
- **Generate sites:** `/generate` `_generate_impl` `:734-783` (also `/a2a_track`,
  `/a2a_mix`, `/longform`, `/bend`) — all call `resolve_latch` + `film_context` +
  `with_lora_interval`; a melody block must be resolved once and applied at the same
  six sites the 07-12 contract work touched.

### 1.3 Model-side plumbing the payload maps onto
- `stable-audio-3/stable_audio_3/inference/latch_targets.py:13-47` —
  `KINDS = (constant, ramp_up, ramp_down, beat_grid)`, `build_target()` returns
  `[B, C, frames]` on the 10.766 Hz latent grid. A melody contour target = one more
  kind (or a head-side loss that doesn't need a dense target).
- `stable-audio-3/stable_audio_3/model.py:114,337-345,415+` — `generate(latch_configs,
  latch_hparams)` → `_latch_guided_generate`; per-config `loss_type` dispatch lives in
  `latch_guided.head_loss` (where new melody losses land — model-repo work, ships WITH
  Head A, not UI work).
- `control/sa3_control/adapters.py:37-63` — `ControlContext(control_tokens[B,T_ctrl,dim],
  gain)`; module-global, wraps every DiT cross-attn; `add_fractional_positions()` `:79-93`
  gives the token stream time order. **Nothing here is scalar-specific** — a per-frame
  melody token stream (T_ctrl = latent T) rides the same context unchanged.

### 1.4 Secondary surface (gradio)
`stable-audio-3/stable_audio_3/interface/diffusion_cond.py` — 2 latch slots `:168-185`,
configs built `:288-310`, kind dropdowns `:669,:681`. Gets Head A for free via the same
head-dir scan (`_list_latch_models` `:29`). Melody-specific UI goes to the explorer
FIRST; gradio parity is a later, optional mirror (parity-audit precedent).

### 1.5 The data the shape picker consumes
- **`eval/musicology/motif_catalog.json`** — `{min_total: 40, n_melodies: 2649,
  families_grid: [60], families_contour: [60]}`. Family entry:
  `{gram, n, klass (pedal|oscillation|run|zigzag|...), support_files, support_frac,
  within_file_med, within_file_p90, exemplars: 6 × [file_id, time_sec, pitch,
  degree_seq], degree_seq_typical, description}`.
  `families_contour` = collapsed-repeat shape vocabulary → **this is the picker list**;
  `families_grid` includes the pedal cell (`gram [0,0,0,0]`, support 91%) → shown as the
  fixed "Layer A" explainer, not a pickable shape.
- **`eval/musicology/memorability.json`** — corpus hookness context: percentiles,
  `top_decile` (n=259, best-motif 56×/crop), `top_decile_ids`, `per_file` stats.
- **`eval/musicology/melodies.jsonl`** — per-id `{id, bpm, tonic, mode, step (sec per
  16th slot), slots[], pitches[], phrase_bounds[]}` — id-aligned with `latents_sa3`.
  **This, not the MIDI, is the preview-render source** (see Phase 0).
- muscriptor MIDIs: `/run/media/kim/9a410a1d-…/lumi_runs/muscriptor_full/` (4545 .mid,
  removable drive) — ground truth behind melodies.jsonl; not needed at preview time.

---

## 2. Phased rollout (each phase shippable alone, keyed to model availability)

| Phase | Needs | Ships | Surfaces touched |
|---|---|---|---|
| **0** | no models — **now** | Shape-vocabulary BROWSER (static page, 32 cells, synth previews, hookness stats, family filter) so Kim can audition/veto the vocabulary **before training** | new static page (riffer-evals pattern) + one CPU preview-render script |
| **1** | Head A (`latch_sa3_melody_contour_best.pt`) | Hookness + pedal↔run **sliders** compiling to standard LatCH slots | `controls.py` (+2 sliders, contract v3 append), `_LOSS_OPTIONS`; server: zero-to-tiny (loss names ride existing pass-through) |
| **2** | Head B (FiLM `control_mode="melody_contour"`) | **Shape picker wired to generation**: picked cell → per-frame contour stream | server `resolve_melody()` + melody adapter slot; explorer melody section; `/info.melody` |
| **3** | Heads A+B live + Kim's Phase-0/2 verdicts | 2-D PCA shape map, 16-step BYO cell editor | explorer only (payload identical to Phase 2) |

---

## Phase 0 — shape-picker browser (ship now, no models)

**Purpose:** the 32-cell vocabulary is a *design commitment* (Head B trains against it,
the picker is built around it). Kim auditions and vetoes cells before any GPU hour is
spent. Also delivers the preview assets Phase 2's picker reuses.

**Cell selection:** top 32 of `families_contour` by `support_files` (of 60 mined;
`min_total=40` already floors support). Pedal shown once, above the grid, as "Layer A —
the default filler" with its 91% support stat. Each cell gets a **stable id**
(`mc_<rank>_<klass>_<gram-joined>`, e.g. `mc_01_oscillation_+12-12+12-12`) — this id is
the reference Kim uses in chat verdicts AND the `cell_id` Phase 2 payloads carry.
Verdicts flow Kim→chat→`kim_feedback` in the page manifest (public comment fields are
write-only/agent-forbidden, MASTER §4 — no in-page veto widget).

### Preview rendering — RECOMMENDATION: synth render from melodies.jsonl (not source-audio crop)

Two candidate approaches for turning an exemplar `(file_id, time_sec, pitch, degrees)`
into audio:

1. **Simple synth render (RECOMMENDED, primary).** Look up `melodies.jsonl[file_id]`;
   slot index = `round(time_sec / step)`; take a ±2-bar window (32 slots before → 32
   after, 16th grid, 4 slots/beat); synthesize each sounding slot as a short decaying
   saw/square at its `pitches[]` value, slot duration = `step` sec (numpy oscillator +
   exp envelope; no MIDI parsing, no synth dependency; ffmpeg → .m4a 128k per MASTER
   convention). ~4 s per preview, 32 cells × 6 exemplars ≈ 192 clips, minutes of CPU.
   Rationale:
   - The catalog was mined FROM the quantized streams — a synth render auditions
     **exactly the vocabulary cell**, which is the veto question. It is also exactly
     what Head B will be conditioned on (teacher-forced on these streams), so Kim
     pre-hears the conditioning signal, not a proxy.
   - Key-invariant/clean: no kick/bass masking, no octave-doubling confound (the
     documented skyline noise), no dependence on which register the source lead sat in.
   - Zero mount dependencies: `melodies.jsonl` is in-repo; the MIDI drive and Mantu can
     both be offline.
2. **Source-audio crop (secondary, optional toggle later).** Exemplar time is within a
   380 s `latents_sa3` crop; source full tracks live at `Mantu/ai-music/Goa_Separated`.
   Real idiom context, but: needs Mantu mounted + crop-offset bookkeeping, the lead is
   buried in the mix (defeats shape audition), and it auditions the *source*, not the
   representation. Not worth blocking Phase 0 on; add as an "in context" button on the
   Phase-2 picker if Kim asks.

Previews render at each exemplar's own pitch (6 exemplars/cell give register variety);
a "transpose to common tonic" toggle is a page-side pitch-factor question deferred
unless comparability bothers Kim (open Q1).

### Page spec
Static HTML, riffer-evals conventions: same-playhead audio cells (MANDATORY, MASTER §4),
manifest v2 sidecar (`hypothesis` = "veto pass on the 32-cell melody vocabulary",
`kim_feedback` empty ⇒ ❗ unaudited marker), three-audience standard (spec §14):
plain-language explainer block ABOVE the tool ("goa leads = a 16th pedal + one repeated
oscillation cell; these are the corpus's 32 most-used cells; a hook = one cell repeated
~56×; listen and veto the ones that don't belong"), engineer strip (mining params,
`min_total`, script links to `phase3_motifs.py` / this plan).

```
┌─ Melody shape vocabulary — 32 cells (veto pass) ──────────────────────────┐
│ [explainer block: what this is / why / how to read — 3 sentences]         │
│ Layer A: PEDAL  [▶ ex1..6]  support 91% · med 75×/crop   (not pickable)   │
│ Filter: [All | oscillation | run | zigzag | ...]   Sort: [support|hook]   │
│ ┌────────────┬────────────┬────────────┬────────────┐                     │
│ │ mc_01 osc  │ mc_02 osc  │ mc_03 osc  │ mc_04 run  │  per cell:          │
│ │ ±12 bounce │ ±1 trill   │ ±2 rock    │ desc b2→1  │   contour sparkline │
│ │ ▁█▁█▁█▁█   │ supp 50%   │ supp 42%   │ supp 38%   │   support_frac      │
│ │ [▶1][▶2].. │ med 5×     │ p90 30×    │ med 2×     │   within_file med/  │
│ │ supp 50%   │ [▶1][▶2].. │ [▶1][▶2].. │ [▶1][▶2].. │   p90 (hook stats)  │
│ └────────────┴────────────┴────────────┴────────────┘  … 8 rows           │
└───────────────────────────────────────────────────────────────────────────┘
```

Data flow: one builder script reads `motif_catalog.json` + `memorability.json` → renders
previews from `melodies.jsonl` → emits `melody_vocab.json` (the 32 cells + stats + veto
field, initially all `null`) + the page. **`melody_vocab.json` is the single vocabulary
artifact every later phase reads** (picker options, Head B class docs).

---

## Phase 1 — Head A lands: hookness + pedal/run sliders as LatCH slots

**Reuse, not extend:** both sliders compile to ORDINARY per-slot latch entries through
the existing contract — `resolve_latch` pass-through (`loss_type`, `w_sec` already
survive `:505-508`) means the **server needs no schema change**. The new loss types are
model-repo work shipping with Head A (`latch_guided.head_loss`), not UI work:

- `pedal↔run` slider → target share of frames in {pedal} vs {move±1..±3} classes.
  Slot: `loss_type="class_share"`, `value` = pedal share 0..1, head channel selection
  baked into the loss (head outputs 11 logits).
- `hookness` slider → repetition pressure: autocorrelation of the decoded class-prob
  stream at the cell period. Slot: `loss_type="contour_autocorr"`, `value` = target
  autocorr 0..1, **`w_sec` reused as the cell period in seconds** (1–2 beats; default
  2 beats at prompt BPM). No new per-slot field needed.

Payload sketch (what `steering_payload` emits — nothing else changes):

```json
{"latch": [
   {"head": "melody_contour", "kind": "constant", "value": 0.75, "gain": 512,
    "start_pct": 0.0, "end_pct": 0.6, "loss_type": "contour_autocorr", "w_sec": 0.84},
   {"head": "melody_contour", "kind": "constant", "value": 0.6,  "gain": 512,
    "start_pct": 0.0, "end_pct": 0.6, "loss_type": "class_share"}
 ],
 "rho": 512, "mu": 512, "gamma": 0.3, "n_iter": 4}
```

Deltas, exhaustively:
- `controls.py`: melody slider row in `steering_panel()`; `_LOSS_OPTIONS` += the two
  names; `steering_states()` 35→39 (**append-only**, the v2 rule: +hookness, +pedalrun,
  +melody-enable, +melody-window) → **contract v3**; `steering_payload()` appends the
  two auto-slots when enabled (beyond the 3 manual slots — server takes any list length,
  only the UI caps at 3).
- Server: `HEADS` auto-discovers the head (`:305-312` glob) — set slider metadata in the
  ckpt so `_head_entry` `:287-298` derives sane ranges. Optionally add the two loss
  names to a server-side allowlist if one is introduced (none exists today — `:506` is a
  comment, not validation).
- Gate (from the design note): sliders stay behind per-class-F1 clearance; the panel
  shows them only when `/info.latch_heads` contains `melody_contour` — availability IS
  the feature flag, no config needed.

```
│ Steering (LatCH / FiLM / DoRA)  [existing panel]                          │
│ ...3 manual LatCH slot rows (unchanged)...                                │
│ ☑ Melody (Head A)   hookness ▁▂▃▄▅[====|--] 0.75                          │
│                     pedal ◄────[==|------]────► runs   0.30               │
│                     window: start [0.0] end [0.6]   (compiles to slots)   │
```

---

## Phase 2 — Head B lands: shape picker → FiLM contour stream

**New payload block** (a sibling of `film`, not a latch slot — it's a forward-mod
adapter, no gradients):

```json
{"melody": {
   "ckpt": null,                    // null → server default (/info.melody.ckpt)
   "cell_id": "mc_01_oscillation_+12-12+12-12",   // from melody_vocab.json, OR:
   "cell": {"grid": "16th", "classes": [1,10,1,10,1,10,1,10,1,1,1,1,1,1,1,1]},
                                    // 16 slots of the 11-class alphabet (BYO path,
                                    //  Phase 3 editor emits this)
   "bpm": 143.0,                    // grid tempo; default = corpus modal 143
   "statement_period_beats": 2.0,   // cell restated every N beats; pedal-fill between
   "fill": "pedal",                 // pedal | rest  (corpus anatomy default: pedal)
   "phase_beats": 0.0,              // offset of first statement vs t=0
   "start_sec": 0.0, "end_sec": null,   // conditioning window; rest-class outside
   "gain": 1.0,                     // ControlContext gain (as-trained = 1.0)
   "lambda_text": 6.0, "lambda_melody": 2.0   // per-source CFG (StemGen dropout item);
 }}                                 //  omit → single joint cfg_scale
```

**Encode format & expansion policy (server-side, mirroring training prep exactly):**
payload stays SYMBOLIC (16th-grid class ids) — small, editable, loggable in
`params_echo`; the server expands it, so the grid policy lives in one place:
1. Tile: statement at every `statement_period_beats`, `fill` class between, `rest`
   outside `[start_sec, end_sec]` → a 16th-grid stream over the full duration
   (slot dur = 60/(4·bpm) s).
2. Resample 16th grid (~9.5 Hz @143) → SAME rate 10.766 Hz by **nearest-frame** — the
   SAME rule the training targets used (design note §0); any drift/rounding mismatch
   between train and inference here silently degrades control, so this function should
   be shared with (imported from) the targets-prep script, not re-implemented.
3. Per-frame class id → the adapter's embedding → `ControlContext(tokens[1,T,dim],
   gain)`; uncond half = trained-null (zeros), same as `film_context` `:456-458`.

**Phase alignment:** for text→audio there is no pre-existing beat grid — the
conditioning DEFINES the grid, so `phase_beats=0` at t=0 is the contract and the
muscriptor calibrator measures how well renders lock to it. For `/a2a_*` ops the source
`.BEATS_GRID` exists → optional later `"phase": "from_source"`; not v1.

Server deltas:
- `resolve_melody(req)` + `melody_context()` alongside `film_context` (`:447-459`);
  applied at the same generate sites as `film` (`:772` and siblings).
- Adapter slot: generalize the single `FILM_STATE` (`:331-349, :394-444`) to two named
  slots (`density`, `melody`) or **v1: mutually exclusive** — `install_adapters` wrapper
  stacking of two adapter families is untested (see open Q3). Rebuild rules identical.
- `/info` gains `"melody": {"ckpt": ..., "vocab": <melody_vocab.json contents>}` so the
  picker populates the same way head dropdowns do (`controls.py:217-224` pattern).
- Explorer: melody section grows the picker (dropdown of non-vetoed cells + sparkline +
  the Phase-0 preview next to it) + bpm/period/window/gain/λ knobs; states appended
  (v3→v4, append-only).

```
│ ☑ Melody shape (Head B / FiLM)                                            │
│ cell [mc_01 ±12 bounce ▼] [▶ preview]  sparkline ▁█▁█▁█▁█                 │
│ bpm [143] statement every [2.0] beats  fill [pedal▼]  phase [0.0]         │
│ window [0.0]-[end]  gain [1.0]   λ_text [6.0] λ_melody [2.0]              │
│ (Head A sliders from Phase 1 remain — they compose: pick a cell, then     │
│  push hookness; disintegration gate governs every eval render)            │
```

---

## Phase 3 — polish: 2-D PCA shape map + BYO 16-step cell editor

No new payload or server work — both emit the SAME Phase-2 `melody` block:
- **PCA map:** 2-D scatter of motif features (seed layout exists:
  `eval/musicology/pca_scatter.txt` / `phase2_clustering.py` features), 32 anchors,
  click → snap to nearest anchor **within the same family**; blend only intra-family
  (spec §4: interpolating across families crosses contours the corpus never produces —
  the map is a browsing surface over discrete cells, not a continuum control).
- **BYO editor:** 16 steps × 11 classes step-sequencer grid → `melody.cell.classes` +
  live sparkline + a client-side synth preview (reuse the Phase-0 synth, ported to JS or
  pre-rendered on a server endpoint). Ships behind "Advanced".
- Dash-side only; contract frozen at v4.

---

## 3. Open questions for Kim (only build-changing ones)

1. **Phase 0 previews: keep each exemplar at its source pitch (register variety, 6 per
   cell), or transpose all to a common tonic (A minor) for like-for-like comparison?**
   Changes the preview renderer (trivial) but also what the veto means — vetoing a shape
   vs vetoing a register. Default if unanswered: source pitch.
2. **Phase 2 tempo: does the melody grid get its own BPM knob (default 143), or should
   it stay slaved to a BPM parsed from the prompt when one is present?** Changes whether
   `resolve_melody` needs prompt parsing and what the calibrator treats as ground truth.
   Default if unanswered: explicit knob, default 143, no prompt parsing.
3. **May melody-FiLM and density-FiLM be mutually exclusive in v1** (one adapter slot,
   picking melody unloads density)? Stacking two decoupled-cross-attn adapter families
   is untested (`install_adapters` wrapper nesting, `_ACTIVE` single-token-stream
   global at `adapters.py:47`); allowing both in v1 adds a real engineering item
   (multi-context routing) to the Head-B integration. Default if unanswered: exclusive
   in v1, composition as a follow-up experiment.

---

## 4. Do NOT build (adjacent, explicitly out)

- **No absolute-pitch entry** — no key picker, no real-pitch piano roll, no MIDI-note
  target entry. Contour classes only (design note §5: key-dependent, data-hungry,
  identity lives in the contour).
- **No phrase-level symbolic LM** — no melody "continuation/suggestion" model, no
  generate-a-melody button. The per-frame stream + repetition IS the hook (§5).
- **No single "melodic shape continuum" slider/axis** — explicitly rejected in §4;
  the PCA map with family-snapping is the honest replacement.
- **No melody heads/UI on SAO-Small surfaces** (§5: SA3-medium activations only) — no
  gradio-Small or SAT-side melody controls.
- **No new standalone melody app** — everything folds into the existing explorer panel
  + one static Phase-0 page (Kim's direction verbatim).
- **No in-page veto/comment ingestion** — public comment fields are write-only and
  agent-forbidden (MASTER §4); verdicts arrive via chat → manifest `kim_feedback`.
- **No contract reordering** — `steering_states` grows append-only (35→39→…); never
  reorder or repurpose existing positions (the 07-12 v2 rule).
- **No eval renders without the disintegration gate** — every Phase-1/2 audition render
  runs `eval/control_head_disintegration_eval.py` vs its own unsteered baseline
  (MASTER §4, mandatory; the ghost-sine risk is called out in the design note §2).

## §3-ANSWERS (Kim direct, 2026-07-22)

1. **Preview transposition: SOURCE PITCH.** Cells audition at their corpus pitch, no
   common-tonic normalization.
2. **Melody BPM = its own conditioner**, and WHICH mechanism is an experiment, not a
   decision: arms = FiLM vs LatCH vs an INTEGER conditioner fine-tuned into the model
   (SA-lineage precedent: per-second timing embeds; SA3 global-embed pathway is the
   natural home for a learned BPM embedding). Folded into the melodic spec as an arm
   family; UI exposes one BPM field regardless of the winning mechanism.
3. **Stacking ALLOWED in v1** (melody-FiLM + density-FiLM co-active; Kim is first tester).
   Prior art check (Kim's recall verified): newcap8_density_control 07-07 had a
   "both-at-half" arm — onset-LatCH + FusionCC-FiLM at HALF gain each (WORKLOG.md:1504).
   Verdict "not great" is confounded by the halving: it tested dilution, not stacking.
   v1 ships stacking unrestricted + a small full-gain stacking matrix goes in the Head-B
   eval plan (melody×density at full/full, full/half, half/full).

## W REVIEW (2026-07-22 16:40, Kim-requested) — ACCEPTED, all four folded

1. **Semantic outcome columns are mandatory beside the DSP gate** (W's core session
   finding: DSP-buzz and semantic degeneration are INDEPENDENT, r~0.01-0.22 — the DSP
   gate cannot see a clean-but-tune-less pedal drone, which is THIS head's failure mode).
   Phase-1/2 audition columns: mood_drift.py 'melodic' tag vs corpus_reference.json
   baseline + clap_score genre-hold, alongside disintegration gate + muscriptor hookness.
2. Phase-1 gain 512 is a PLACEHOLDER (energy-family value, 06-28 sweep) — melody_contour
   gain sensitivity is a sweep item at Head-A landing, not a default.
3. Phase-0 synth previews: peak-normalize -> int16 BEFORE ffmpeg (MASTER §5 oscillator-sum
   clipping trap).
4. Dependency edges now explicit: (a) Head-A ckpt must carry slider-range metadata AT SAVE
   TIME (else auto-landing degrades silently to default ranges) — coordination requirement
   on Head-A training; (b) **melody_vocab.json freezes at Kim's Phase-0 veto BEFORE Head-B
   training starts** — the edge is Phase0-verdict -> HeadB-train -> Phase2, never
   train-then-veto.
