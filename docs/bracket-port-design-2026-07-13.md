# Bracketing + presets: Gradio_Lab → SA3 explorer port design — 2026-07-13

Design only (no code). Ports the parameter-bracket fan-out, per-output parameter
recall and preset save/load from Kim's `avp/Gradio_Lab` fork of
`stable-audio-tools` into the Dash explorer (`mir/plots/explorer_sa3/`), as
**client-side fan-out** against the existing render server
(`SAO/eval/explorer_render_server.py`, :8056). Companion to the parity audit
(`docs/latent-tool-parity-audit-2026-07-12.md`, build-plan item 5).

Source inventory refs: `git show avp/Gradio_Lab:stable_audio_tools/interface/gradio.py`
in `SAO/stable-audio-tools` (2371 lines; line refs below are that file).

---

## 1. Inventory: what the fork actually does

### 1a. Param-bracket fan-out
- **Axes** (Bracketing Settings accordion, :1084-1116): five comma-list
  textboxes — `steps`, `cfg_scale`, `cfg_rescale`, `sigma_min`, `sigma_max` —
  plus **11 sampler checkboxes** (dpmpp-2m-sde … v-ddim-cfgpp, :1099-1105) as a
  sixth axis. **Seed is NOT an axis**: one seed per run, `-1` resolved once via
  `np.random.randint` and shared by every combo (:1503).
- **Enumeration** (:1497-1500): full Cartesian product,
  `itertools.product(steps, cfg, cfg_rescale, sigma_min, sigma_max, selected_samplers)`
  — fixed axis order, rightmost (sampler) varies fastest. Empty/whitespace
  tokens dropped; `int()`/`float()` parse errors abort the whole run with a
  message (:1474-1490). Zero samplers selected is a hard error (:1485).
- **Count display** (`calculate_generation_count`, :1018-1046): a read-only
  textbox live-updated by a `.change` handler on **every** axis component
  (:1111-1116); text = `"Will generate N files (C combinations × M models)"`,
  where M = number of active models (dual-model A/B is a run multiplier, not a
  product axis). Empty axis counts as 1.
- **Execution** (`generate_dual_model_comparison`, :1345-1688): despite the
  "lazy" naming, all combos are generated **eagerly and sequentially** in a
  Python loop per active model (:1546-1614), each via `generate_audio_lazy`
  (:397) which forwards `(steps, cfg, cfg_rescale, sigma_min, sigma_max,
  sampler)` over the shared `generation_args` dict. The lazy path only survives
  as a re-generate fallback: `get_current_audio_a/b` (:586-694) re-render from a
  `generation_params_cache[cache_key]` if a result's audio is `None`.
- **Results storage**: module-level globals `current_results_a/b` — one dict per
  combo: `{audio, spectrogram, params (description string), param_combo
  (tuple), cache_key, index}` (:1560-1567). Single-audio-widget UI: dropdown +
  `[i/N]` counter, not a grid.

### 1b. Per-output parameter recall
- `create_param_description` (:426-437) builds the human label:
  `"Steps: 100 | CFG: 7.0 | Sigma: 0.03-300 | Sampler: dpmpp-3m-sde | Seed: 123"`
  (`CFG Rescale` included only when ≠ 0; prompt excluded).
- After a run the two per-model dropdowns are repopulated with these strings
  (:1674-1686); **selection is recalled by string-matching** the description
  back to the results list (:697-725) — collisions impossible only because seed
  is shared and the description covers every axis.
- Selecting an entry re-shows: audio, a **per-combo CFG-interval/σ-schedule
  matplotlib viz** regenerated from the recalled params (:611-631), spectrogram,
  and the `[i/N] …` params text. Recall is display-only — it never writes the
  values back into the input form.

### 1c. Preset save/load (:943-1016)
- Flat file `./presets.json` (cwd-relative), `{name: preset_dict}`.
- `save_preset` merges `{prompt, negative_prompt, steps, cfg_scale,
  cfg_rescale, sigma_min, sigma_max, selected_samplers}` — note the bracket
  fields are saved as their raw **comma-list strings**, so a preset stores a
  whole bracket, not a scalar; steering/seed/duration/init-audio are NOT saved.
- `load_preset` fills the form (7 fields + 11 checkbox booleans) with
  hard-coded defaults on any failure; backward-compat shim for an older
  singular `sampler_type` key (:953).
- UI: name textbox + Load/Save buttons + preset dropdown (choices read at UI
  build; **no refresh after save** and no delete — known fork quirks, don't
  port them).

**Port-relevant quirks to avoid:** eager-but-called-lazy generation with zero
per-item progress feedback; recall-by-string-match; presets invisible until
restart; seed not sweepable.

---

## 2. Port design: "Bracket" panel in the explorer

### 2.0 Shape of the port
- **Client-side fan-out.** The UI enumerates combos, then issues **sequential
  POSTs** to the existing `/generate` / `/a2a_track` endpoints — no server
  change. The server already serializes on `GPU_LOCK` and echoes the full
  request back as `meta.params_echo` (`explorer_render_server.py:492`), which
  is the recall record.
- **Lives on the Inference tab** (`inference_tab.py`), as an `html.Details`
  section between the steering panel and the Render button. One instance
  (namespace prefix `brk-`); the a2a routing rule is inherited (non-empty
  `inf-init-path` → op `a2a_track`).
- **The 35-state steering contract is untouched.** `controls.steering_states`
  / `steering_payload` are consumed as-is to build the *base* payload; every
  new component id below is `brk-*` and rides its own State groups.
- Base payload = exactly what today's `_render` callback builds
  (`inference_tab.py:379-436`); a combo is a small **override dict** merged on
  top per POST.

### 2.1 Axes (per task spec) and token grammars

| axis | field id | token grammar | payload override | applies |
|---|---|---|---|---|
| steps | `brk-ax-steps` | ints: `16, 24, 48` | `steps` | both ops |
| cfg | `brk-ax-cfg` | floats: `4, 6, 8.5` | `cfg_scale` | both |
| seed | `brk-ax-seed` | ints, `-1` allowed: `-1, 1234` | `seed` | both |
| nl | `brk-ax-nl` | floats 0.05–0.95: `0.35, 0.5` | `noise_level` | a2a_track only |
| weight | `brk-ax-weight` | floats: `0.5, 1.0, 1.5` | see target dropdown | both |
| interval | `brk-ax-interval` | `lo:hi` pairs: `0:1, 0.25:1, 0.25:0.75` | `cfg_interval` `[lo,hi]` | both |
| dist_shift | `brk-ax-dshift` | floats or `auto`: `auto, 1, 3` | `dist_shift` (`auto` → omit key → ckpt default) | both |

- Empty field = axis inactive (falls back to the form's single value; count 1)
  — same semantics as the fork.
- **Seed axis**: any `-1` token is resolved **once per run** to one shared
  random int (fork behavior, generalized: `-1, 1234` = [shared-random, 1234]).
  Resolution is client-side (`random.randint(0, 2**31-1)`) so the recall
  record and the label agree; the server echo confirms.
- **weight target** (`brk-ax-weight-target` dropdown, only shown when the
  weight axis is non-empty): `dora_strength` (default) overrides
  `payload["dora"]["strength"]` (error if steering DoRA is `none`);
  `latch1_gain` overrides `payload["latch"][0]["gain"]` (error if slot 1 has
  no head). Note: with blank ρ/μ in the steering panel, sweeping `latch1_gain`
  also sweeps ρ=μ (server ties them to g0, `explorer_render_server.py:473-476`)
  — that is the natural gain sweep; set explicit ρ/μ to pin them.
- **nl** with an empty init path: hard error at Start ("nl axis needs an init
  audio path"), not silently ignored. Conversely `inf-noise-ladder` must be
  empty when the nl axis is used (two ladder mechanisms would multiply).
- Parse errors report the axis + offending token in `brk-status` and abort
  before any POST (fork behavior, better message).

**Enumeration:** `itertools.product` in the fixed column order above
(dist_shift fastest). Combo dict carries only the axes the user activated,
e.g. `{"steps": 24, "cfg_scale": 8.0, "cfg_interval": [0.25, 1.0]}`.

### 2.2 Component tree (all new ids, no steering-contract change)

```
html.Details(id="brk-panel", open=False)
├─ html.Summary("Bracket — param fan-out (comma lists; empty = form value)")
├─ presets row
│  ├─ dcc.Dropdown(id="brk-preset-dd")            # names from brk-presets store
│  ├─ dcc.Input(id="brk-preset-name", type="text")
│  ├─ html.Button("Save",   id="brk-preset-save")
│  ├─ html.Button("Load",   id="brk-preset-load")
│  ├─ html.Button("Delete", id="brk-preset-del")
│  ├─ html.Button("Export JSON", id="brk-preset-export")
│  ├─ dcc.Upload(id="brk-preset-import", children=html.Button("Import JSON"))
│  ├─ dcc.Download(id="brk-preset-dl")
│  └─ dcc.Store(id="brk-presets", storage_type="local", data={})
├─ axes row 1: brk-ax-steps · brk-ax-cfg · brk-ax-seed          (dcc.Input text)
├─ axes row 2: brk-ax-nl · brk-ax-weight · brk-ax-weight-target
│              · brk-ax-interval · brk-ax-dshift
├─ run row
│  ├─ html.Span(id="brk-count")                   # "12 combos (2×3×2) · ~14 min"
│  ├─ html.Button("Start bracket", id="brk-start")
│  ├─ html.Button("Stop", id="brk-stop")
│  └─ html.Pre(id="brk-status")                   # progress / errors
├─ machinery (invisible)
│  ├─ dcc.Store(id="brk-queue",   data=None)      # {"base":…, "op":…, "combos":[…]}
│  ├─ dcc.Store(id="brk-results", data=[])        # done entries, run-scoped
│  └─ dcc.Interval(id="brk-tick", interval=400, disabled=True)
└─ html.Div(id="brk-grid")                        # results grid
```

Grid entry (built by `_brk_grid`, one per finished combo):

```
html.Div [style: card, inline-block]
├─ html.B(label)                                  # "s24 · cfg8 · seed1234 · ci[0.25,1] · ds auto"
├─ html.Audio(src=render_client.audio_url(url), controls=True)   # one per batch item
├─ html.Button("Recall → form", id={"type": "brk-recall", "index": i})
└─ html.Details([html.Summary("params"),
                 html.Pre(json.dumps(entry["params_echo"], indent=2))])
```

Label = compact fork-style `create_param_description` port: only active axes,
`key value` pairs joined with " · " (always includes seed). Uniqueness comes
from the entry **index**, never from string matching — recall is by index
(fixes the fork's string-match recall).

### 2.3 Result entry schema (`brk-results` items)

```json
{
  "index": 3,
  "label": "s24 · cfg8.0 · seed1234 · ci[0.25,1.0] · ds auto",
  "combo": {"steps": 24, "cfg_scale": 8.0, "cfg_interval": [0.25, 1.0]},
  "op": "generate",
  "urls": ["/audio/gen_000123/out_00.wav"],
  "files": ["/…/out_dir/gen_000123/out_00.wav"],
  "seed": 1234,
  "total_sec": 71.3,
  "params_echo": { "…full request as the server saw it…" },
  "error": null
}
```

`params_echo` is taken verbatim from `resp["meta"]["params_echo"]`
(`explorer_render_server.py:492`) — full reproducibility including steering
blocks, no client bookkeeping of the merged payload needed. A failed combo
gets `error: "<RenderError text>"`, empty `urls`, and stays in the grid (the
run continues — unlike the fork, which printed and dropped).

### 2.4 Callback signatures

All in a new `mir/plots/explorer_sa3/bracket.py` (`layout(ns=...)` not needed —
single instance), registered from `inference_tab.register_callbacks` via
`bracket.register(app)`. Dash 4.0 (verified in `mir/mir/bin/python`):
`allow_duplicate=True` available and required where noted.

```python
# 1. live count — mirrors fork calculate_generation_count
@app.callback(Output("brk-count", "children"),
    Input("brk-ax-steps", "value"), Input("brk-ax-cfg", "value"),
    Input("brk-ax-seed", "value"), Input("brk-ax-nl", "value"),
    Input("brk-ax-weight", "value"), Input("brk-ax-interval", "value"),
    Input("brk-ax-dshift", "value"),
    Input("inf-init-path", "value"), Input("inf-batch", "value"))
def _brk_count(steps, cfg, seed, nl, weight, interval, dshift, init_path, batch):
    # product of per-axis token counts (empty axis = 1); nl counts only if
    # init_path non-empty; text: "N combos (a×b×c) × batch B"; parse errors
    # shown inline; soft warning style when N > 32.

# 2. start — snapshot form -> base payload + combo list, arm the ticker
@app.callback(
    Output("brk-queue", "data"), Output("brk-results", "data"),
    Output("brk-tick", "disabled"), Output("brk-status", "children"),
    Input("brk-start", "n_clicks"),
    State("brk-ax-steps", "value"), …the 7 axis States…,
    State("brk-ax-weight-target", "value"),
    # exactly the States of today's _render (inference_tab.py:349-377):
    State("inf-prompt", "value"), State("inf-variation", "value"),
    …duration/steps/cfg/cfg-interval/seed/batch/apg/durpad/dist-shift/
     ckpt-dd/ckpt-path/init-path/init-noise/noise-ladder/mut-*/pres-*…,
    *controls.steering_states("inf"),          # the frozen 35, consumed as-is
    prevent_initial_call=True)
def _brk_start(n, *vals):
    # build base payload with the SAME code as _render (factor its payload
    # construction into a shared helper _build_payload(...) -> (op, payload)
    # so single-render and bracket cannot drift);
    # parse axes -> combos (itertools.product, §2.1 order); resolve -1 seed;
    # validate (nl needs init path; weight target needs dora/latch1; noise
    # ladder × nl axis conflict);
    # queue = {"op": op, "base": payload, "combos": combos, "t_start": time.time()}
    # returns (queue, [], False, f"queued {len(combos)} combos")

# 3. ticker — ONE render per tick = the sequential POST loop with per-item UI updates
@app.callback(
    Output("brk-queue", "data", allow_duplicate=True),
    Output("brk-results", "data", allow_duplicate=True),
    Output("brk-tick", "disabled", allow_duplicate=True),
    Output("brk-status", "children", allow_duplicate=True),
    Input("brk-tick", "n_intervals"),
    State("brk-queue", "data"), State("brk-results", "data"),
    prevent_initial_call=True)
def _brk_tick(_n, queue, results):
    # if queue empty/None: return no_update*3 + done-summary;
    # pop combos[0]; payload = merge(base, combo)  (see §2.5 merge rules);
    # resp = render_client.render(op, payload)   # blocks THIS tick only;
    # append result entry (params_echo from resp.meta; RenderError -> error
    # entry, run continues); disabled = not queue["combos"];
    # status = f"[{len(results)}/{total}] last {t:.0f}s · ETA {eta}"
    #   (ETA = mean per-item × remaining, fork had nothing like it).
    # NOTE interval=400ms is just the re-arm latency between renders; the POST
    # itself blocks a Flask worker thread — same blocking model as today's
    # single render, and the badge/interval callbacks stay live because the
    # Dash dev server is threaded. GPU_LOCK on the server makes overlap
    # harmless even if a tick ever double-fires.

# 4. stop — drain the queue
@app.callback(
    Output("brk-queue", "data", allow_duplicate=True),
    Output("brk-tick", "disabled", allow_duplicate=True),
    Output("brk-status", "children", allow_duplicate=True),
    Input("brk-stop", "n_clicks"), prevent_initial_call=True)
def _brk_stop(n):
    # (None, True, "stopped — finished renders kept"); the in-flight POST
    # cannot be aborted (server has no cancel), it just becomes the last entry.

# 5. grid — pure render of the results store
@app.callback(Output("brk-grid", "children"), Input("brk-results", "data"))
def _brk_grid(results): ...   # cards per §2.2; error cards styled red

# 6. per-clip recall — combo values back INTO the form (fork never had this)
@app.callback(
    Output("inf-steps", "value", allow_duplicate=True),
    Output("inf-cfg", "value", allow_duplicate=True),
    Output("inf-seed", "value", allow_duplicate=True),
    Output("inf-init-noise", "value", allow_duplicate=True),
    Output("inf-cfg-interval", "value", allow_duplicate=True),
    Output("inf-dist-shift", "value", allow_duplicate=True),
    Output("inf-ctl-dora-strength", "value", allow_duplicate=True),
    Output("inf-ctl-latch1-gain", "value", allow_duplicate=True),
    Input({"type": "brk-recall", "index": ALL}, "n_clicks"),
    State("brk-results", "data"), prevent_initial_call=True)
def _brk_recall(clicks, results):
    # ctx.triggered_id["index"] -> entry; return each form value from
    # entry["combo"] if that axis was active else no_update.
    # allow_duplicate needed: inf-ctl-latch1-gain is already an Output of the
    # controls.register autofill (controls.py:221).
```

### 2.5 Merge rules (base payload × combo)

Plain `payload = {**base, **combo}` with three special keys:
- `dist_shift`: `auto` token means **delete** the key (server falls back to
  ckpt default, `resolve_dist_shift`), not `None`-set.
- `noise_level`: only valid for op `a2a_track` (guaranteed by §2.1 validation).
- weight axis: reaches inside a nested block —
  `payload["dora"] = {**base["dora"], "strength": w}` or
  `payload["latch"] = [{**base["latch"][0], "gain": w}, *rest]` — never mutate
  the base dict in place (it's reused by every combo).

Single-axis-nl optimization (optional, later): when nl is the **only** active
axis, send one POST with the server's existing `noise_levels` ladder
(`server:792`) instead of N POSTs — one job, shared everything. Not in v1;
keeps _brk_tick uniform.

### 2.6 Payload examples

Base (op `generate`, as `_build_payload` returns it today):

```json
{
  "prompt": "TrackType: Music, …, rolling nighttime psytrance",
  "negative_prompt": "", "duration": 47.0, "batch_size": 1,
  "duration_padding_sec": 6.0, "steps": 24, "cfg_scale": 6.0, "seed": -1,
  "cfg_interval": [0.0, 1.0], "apg_scale": 1.0,
  "ckpt_path": "/run/media/kim/Mantu1/sa3_lora_runs/…/last.safetensors",
  "latch": [{"head": "onset_envelope", "kind": "beat_grid", "value": 140.0,
             "gain": 512.0, "start_pct": 0.0, "end_pct": 0.6}],
  "film": null,
  "dora": {"name": "none", "interval_min": 0.0, "interval_max": 1.0}
}
```

Axes `steps="16,24"`, `cfg="6,9"`, `interval="0:1, 0.25:1"`, seed `-1` resolved
to 7331 → 8 combos; combo #6 (product order: steps → cfg → … → interval fastest):

```json
{"steps": 24, "cfg_scale": 9.0, "seed": 7331, "cfg_interval": [0.0, 1.0]}
```

POST #6 body = base ⊕ combo. Response fields consumed:

```json
{
  "status": "ok", "job_id": "gen_000124",
  "urls": ["/audio/gen_000124/out_00.wav"], "files": ["…"],
  "seed": 7331, "timings": {"total_sec": 68.9},
  "meta": {"op": "generate", "dora_loaded": null, "film_loaded": false,
           "model_rebuilt": false, "params_echo": { "…the merged request…" }}
}
```

### 2.7 Presets

- **Storage:** `dcc.Store(id="brk-presets", storage_type="local")` — browser
  localStorage, `{name: preset}`; survives restarts with zero server surface
  (improves on the fork's cwd-relative `presets.json`).
- **Preset content** = one JSON object with two sections:

```json
{
  "saved": "2026-07-13T02:10:00",
  "form": {
    "inf-prompt": "…", "inf-variation": "", "inf-negprompt": "",
    "inf-duration": 47, "inf-steps": 24, "inf-cfg": 6.0,
    "inf-cfg-interval": [0.0, 1.0], "inf-seed": -1, "inf-batch": 1,
    "inf-apg": 1.0, "inf-durpad": 6.0, "inf-dist-shift": null,
    "inf-ckpt-dd": null, "inf-ckpt-path": "", "inf-init-path": "",
    "inf-init-noise": 0.4, "inf-noise-ladder": "",
    "…all 35 steering component ids (inf-ctl-*) by id…": "…"
  },
  "bracket": {
    "steps": "16,24", "cfg": "6,9", "seed": "", "nl": "",
    "weight": "", "weight_target": "dora_strength",
    "interval": "0:1, 0.25:1", "dshift": ""
  }
}
```

  Keyed by component id so save/load are one zip over a single whitelist
  constant `_PRESET_IDS` (form ids above + the 8 bracket ids); the fork's
  positional-tuple fragility (its :1358-1467 arg-unpacking swamp) is exactly
  what this avoids. Unknown/missing ids on load → `no_update` (forward/backward
  compatible; mirrors the fork's `sampler_type` shim in spirit).
- **Callbacks:**

```python
# save: merge into store, refresh dropdown (fork never refreshed)
@app.callback(Output("brk-presets", "data"),
              Output("brk-preset-dd", "options"),
              Output("brk-status", "children", allow_duplicate=True),
              Input("brk-preset-save", "n_clicks"),
              State("brk-preset-name", "value"), State("brk-presets", "data"),
              *[State(i, "value") for i in _PRESET_IDS],
              prevent_initial_call=True)

# load: fan values back out; every Output allow_duplicate=True (latch
# gain/kind/value ids clash with controls.register autofill, and steps/cfg/…
# clash with _brk_recall)
@app.callback(*[Output(i, "value", allow_duplicate=True) for i in _PRESET_IDS],
              Output("brk-status", "children", allow_duplicate=True),
              Input("brk-preset-load", "n_clicks"),
              State("brk-preset-dd", "value"), State("brk-presets", "data"),
              prevent_initial_call=True)

# delete: pop name from store, refresh dropdown (allow_duplicate on both)

# export: whole store (or the selected preset) as a file
@app.callback(Output("brk-preset-dl", "data"),
              Input("brk-preset-export", "n_clicks"),
              State("brk-presets", "data"), prevent_initial_call=True)
def _preset_export(n, presets):
    return dict(content=json.dumps(presets, indent=2),
                filename=f"explorer_presets_{date}.json")

# import: dcc.Upload contents (base64 json) merged into the store
@app.callback(Output("brk-presets", "data", allow_duplicate=True),
              Output("brk-preset-dd", "options", allow_duplicate=True),
              Input("brk-preset-import", "contents"), State("brk-presets", "data"),
              prevent_initial_call=True)
```

  Dropdown options also need an initial fill: `Input("brk-preset-dd", "id")`
  one-shot (same pattern as `controls.register`'s `_fill_options`).
- The FiLM checklist value (`["on"]`/`[]`) and dropdown values round-trip as-is
  (JSON-serializable). `inf-ckpt-dd` may reference a checkpoint that has moved;
  load keeps it and the render fails loudly server-side — acceptable.

### 2.8 What is intentionally NOT ported
- **Dual resident models** — doesn't fit 16 GB with medium (audit §4.5); the
  ckpt/DoRA axis idea (base-vs-adapter A/B via `ckpt_path` as a bracket axis)
  is a natural v2 axis but out of scope here.
- **Sampler-checkbox axis** — the explorer UI never sends `sampler_type`
  (server accepts it); add as a v2 axis only after the single-value control
  exists (audit feature-matrix row "Sampler type").
- **cfg_rescale / sigma_min / sigma_max axes** — `/generate` accepts none of
  them; SA3-era equivalents are covered by `interval` + `dist_shift`.
- **Per-combo σ-schedule viz** — the live sigma chart already redraws from the
  form; recall (§2.4 cb 6) reuses it for free by writing the form.
- Fork's 30-second auto-delete/session file GC — server jobs dir already owns
  output lifecycle.

### 2.9 Effort + files touched
- new `mir/plots/explorer_sa3/bracket.py` (~350 lines: layout, parsing,
  `_build_payload` shared helper, 10 callbacks);
- `inference_tab.py`: insert `bracket.layout()` into `layout()`, call
  `bracket.register(app)`, refactor `_render`'s payload construction into the
  shared `_build_payload` (behavior-neutral);
- no changes to `controls.py` (35-state contract untouched), no changes to
  `explorer_render_server.py`, no changes to `render_client.py`.
- Runtime constraints honored: all UI code under `mir/mir/bin/python` (Dash
  4.0 verified, `dcc.Download`/`dcc.Upload` present); server untouched/CPU-only
  work.

---

*Design by CONTINUITY subagent, 2026-07-13. Sources:
`avp/Gradio_Lab:stable_audio_tools/interface/gradio.py` (:397-437, :586-725,
:943-1046, :1048-1236, :1345-1688), `mir/plots/explorer_sa3/inference_tab.py`,
`controls.py`, `render_client.py`, `SAO/eval/explorer_render_server.py`
(:431-501, :660-728), parity audit 2026-07-12 §4.5.*
