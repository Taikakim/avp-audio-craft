# Genre-Conditioned FiLM Style Adapter for SA3 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capture "goa / melodic-goa" style in frozen SA3 medium-base with a `sa3_control` decoupled-cross-attn adapter conditioned on an audio-derived style fingerprint (genre softmax + release year + groove), then pick the conditioning scope by a 3-variant benchmark.

**Architecture:** Reuse the existing `sa3_control` adapter machinery unchanged (24 DiT cross-attn wrappers, base frozen, control tokens injected via a module-global ContextVar). The only structural change is a new conditioner — `FingerprintEncoder` — that maps a ~15-dim fingerprint vector to `n_tokens × 768` FiLM-modulated control tokens (generalizing the existing `ScalarAttributeEncoder`, which maps a single scalar). Data prep is purely additive: run the essentia discogs-400 genre head over the corpus and store a K-genre raw-prob vector + `other` bucket into each crop `.json`; no latent re-encode. The fingerprint is assembled at dataload, mixing static track-level dims (genre, year, bpm, syncopation) with — for one variant — window-aggregated volatile dims (onset density, energy) that also fix a real window/scalar alignment bug in the existing scalar heads.

**Tech Stack:** SA3 medium-base (rectified flow), PyTorch ROCm (CK flash-attn), `sa3_control` adapters (`adapters.py`/`inject.py`/`conditioner.py`/`dataset.py`/`train.py`), essentia discogs-400 genre head via `gmi_onnx` + MIGraphX (MIR venv), MERT-330M for eval, wandb telemetry, pytest.

## Global Constraints

Every task's requirements implicitly include these. Values copied verbatim from the spec:

- **Genre-head / MIR-side work runs in the MIR venv:** `/home/kim/Projects/mir/mir/bin/python` (has essentia + madmom + `onnxruntime_migraphx`). It is **NOT** the SA3 venv. The discogs-400 head is `mir/src/classification/gmi_onnx.py` (`get_gmi_model("genre", models_dir)` → `(n_patches, 400)`; mean over patches → 400-dim softmax).
- **Training / adapter work runs in the consolidated SA3 venv:** `/home/kim/Projects/SAO/.venv/bin/python` (torch, CK flash-attn). Always `export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE` **before** torch import (use `control/run_control_train.sh`, whose `SA3_VENV` env var overrides the interpreter). The two venvs cannot be merged — invoke each by absolute path.
- **Latents live on the NVMe mirror `/home/kim/Projects/latents_sa3`** (5401 `.npy` + `.json` + `.TIMESERIES.npz`, `(1,256,4096)` fp16). **Never** use `/run/media/kim/Lehto/latents_sa3` for training throughput.
- **Adapter/machinery dims are fixed:** `control_dim = 768`, `n_tokens = 256` (the argparse default / AudioRef bank), `crop-frames = 512` (beat-aligned random window). The FiLM token bank in the fingerprint/scalar conditioner is capped at **16 tokens** (the `ScalarAttributeEncoder` convention: `n_tokens=min(args.n_tokens, 16)` — keeps FiLM params negligible; the eval loader hard-codes `min(n_tokens,16)`).
- **Genre-vocab min-support rule:** a genre is in the fixed vocabulary only if **≥ 303 crops** carry it as a significant label. The significance rule is fixed in Task 1: **a genre is "significant" for a crop if its mean softmax probability ≥ 0.10** (matches essentia's default `threshold=0.1`).
- **Genre encoding is raw softmax probabilities + an `other = 1 − Σ(selected)` bucket** → a proper simplex, **no renormalization**. Fixed vocab (not per-track top-5).
- **Standing training recipe: EMA + grad-accum + early-stop** (~20 epoch cap). fp32/bf16 base as in control training (`model_half=False`).
- **Chroma is out of scope** (separate head, composes at inference). Per-frame contour conditioning is out of scope (v1 uses window-aggregated scalars).
- **v2 telemetry is logged, not consumed:** v1 instruments per-region flow-loss + control-extreme failures into wandb only. No importance-weighted/coverage-guided training in v1.
- **Frame rate of the T=4096 timeseries is 10.767 Hz** (4096 frames / ~380.4 s crop). A 512-frame window ≈ 47.6 s.
- **Both data drives (Mantu source audio, Lehto derived) are removable** — must be mounted or work stalls. Source audio: `/run/media/kim/Mantu/ai-music/Goa_Separated/<track>/full_mix.flac`.

---

### Task 1: Corpus genre distribution + fixed vocabulary

**Files:**
- Create: `/home/kim/Projects/mir/src/tools/genre_vocab.py`
- Create: `/home/kim/Projects/mir/tests/test_genre_vocab.py`
- Create (output artifact, written by the script): `/home/kim/Projects/SAO/control/sa3_control/genre_vocab.json`

**Interfaces:**
- Consumes: `classification.gmi_onnx.get_gmi_model("genre", models_dir)` → callable `(n_patches,1280)→(n_patches,400)`; `classification.essentia_features.get_classification_labels()["genre"]` → `list[str]` of 400 label names (format e.g. `"Electronic---Goa Trance"`); `classification.effnet_onnx.get_effnet_migraphx(onnx_path)` → callable `audio→(n_patches,1280)`.
- Produces:
  - `genre_significant_labels(mean400: np.ndarray, labels400: list[str], prob_thresh: float = 0.10) -> list[str]` — labels whose mean prob ≥ thresh.
  - `select_genre_vocab(counts: dict[str,int], min_support: int = 303) -> list[str]` — labels with `count >= min_support`, sorted by count descending then label ascending.
  - The JSON artifact: `{"vocab": [...], "min_support": 303, "significance": "mean_prob>=0.10", "counts": {label: n}, "n_crops": int, "labels400": [...]}`.

- [ ] **Step 1: Write the failing test**

```python
# /home/kim/Projects/mir/tests/test_genre_vocab.py
import numpy as np
from src.tools.genre_vocab import genre_significant_labels, select_genre_vocab

def test_genre_significant_labels_threshold():
    labels = ["A", "B", "C", "D"]
    mean400 = np.array([0.5, 0.09, 0.30, 0.11], dtype=np.float32)
    assert genre_significant_labels(mean400, labels, prob_thresh=0.10) == ["A", "C", "D"]

def test_select_genre_vocab_min_support_and_ordering():
    counts = {"Goa": 900, "Psy": 900, "Rare": 302, "Trance": 305, "Ambient": 303}
    # >=303 kept; sorted by count desc then label asc (Goa/Psy tie -> alpha)
    assert select_genre_vocab(counts, min_support=303) == ["Goa", "Psy", "Trance", "Ambient"]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd /home/kim/Projects/mir && mir/bin/python -m pytest tests/test_genre_vocab.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.tools.genre_vocab'`.

- [ ] **Step 3: Write the deterministic helpers**

```python
# /home/kim/Projects/mir/src/tools/genre_vocab.py
"""Build the fixed genre vocabulary for the SA3 style adapter from the corpus
discogs-400 distribution. Runs in the MIR venv (essentia + gmi_onnx + MIGraphX)."""
from __future__ import annotations
import numpy as np

def genre_significant_labels(mean400, labels400, prob_thresh: float = 0.10):
    mean400 = np.asarray(mean400, dtype=np.float32)
    return [labels400[i] for i in range(len(labels400)) if mean400[i] >= prob_thresh]

def select_genre_vocab(counts: dict, min_support: int = 303):
    kept = [(lbl, n) for lbl, n in counts.items() if n >= min_support]
    kept.sort(key=lambda kv: (-kv[1], kv[0]))
    return [lbl for lbl, _ in kept]
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd /home/kim/Projects/mir && mir/bin/python -m pytest tests/test_genre_vocab.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Add the corpus-scan `main()` to `genre_vocab.py`**

```python
# append to /home/kim/Projects/mir/src/tools/genre_vocab.py
import glob, json, os, sys
from collections import Counter
from pathlib import Path

def scan_corpus(latents_dir: str, out_json: str, prob_thresh: float = 0.10, min_support: int = 303):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # reach src/
    import essentia.standard as es
    from classification.effnet_onnx import get_effnet_migraphx
    from classification.essentia_features import get_model_path, get_classification_labels
    from classification.gmi_onnx import get_gmi_model

    labels400 = get_classification_labels()["genre"]
    effnet = get_effnet_migraphx(get_model_path("discogs-effnet-bsdynamic-1.onnx"))
    models_dir = Path(get_model_path("genre_discogs400-discogs-effnet-1.pb")).parent
    genre = get_gmi_model("genre", models_dir)

    # group crop jsons by source track -> run the head ONCE per track (genre is track-level)
    by_track = {}
    for j in glob.glob(os.path.join(latents_dir, "*.json")):
        m = json.load(open(j))
        by_track.setdefault(m.get("source_track") or m.get("path"), []).append((j, m))

    counts = Counter()
    n_crops = 0
    for i, (trk, crops) in enumerate(sorted(by_track.items())):
        src = crops[0][1].get("source_path") or crops[0][1].get("path")
        if not src or not os.path.exists(src):
            print(f"[skip] source missing: {src}", flush=True); continue
        audio = es.MonoLoader(filename=src, sampleRate=16000, resampleQuality=4)()
        mean400 = np.mean(genre(effnet(audio)), axis=0)   # (400,) softmax, mean over patches
        sig = set(genre_significant_labels(mean400, labels400, prob_thresh))
        for _, _m in crops:                               # every crop of this track carries the labels
            for lbl in sig:
                counts[lbl] += 1
            n_crops += 1
        if (i + 1) % 50 == 0:
            print(f"[vocab] {i+1}/{len(by_track)} tracks, {n_crops} crops", flush=True)

    vocab = select_genre_vocab(dict(counts), min_support)
    out = {"vocab": vocab, "min_support": min_support,
           "significance": f"mean_prob>={prob_thresh}", "counts": dict(counts),
           "n_crops": n_crops, "labels400": labels400}
    os.makedirs(os.path.dirname(out_json), exist_ok=True)
    json.dump(out, open(out_json, "w"), indent=1)
    print(f"[vocab] K={len(vocab)}: {vocab}\n[vocab] wrote {out_json}", flush=True)

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--latents-dir", default="/home/kim/Projects/latents_sa3")
    ap.add_argument("--out", default="/home/kim/Projects/SAO/control/sa3_control/genre_vocab.json")
    ap.add_argument("--prob-thresh", type=float, default=0.10)
    ap.add_argument("--min-support", type=int, default=303)
    a = ap.parse_args()
    scan_corpus(a.latents_dir, a.out, a.prob_thresh, a.min_support)
```

- [ ] **Step 6: Run the corpus scan (procedural, MIR venv)**

Run:
```bash
cd /home/kim/Projects/mir && \
mir/bin/python src/tools/genre_vocab.py \
  --latents-dir /home/kim/Projects/latents_sa3 \
  --out /home/kim/Projects/SAO/control/sa3_control/genre_vocab.json
```
Expected: prints `[vocab] K=<n>: ['Electronic---Goa Trance', 'Electronic---Psytrance', ...]` and writes the JSON. The first genre-head inference JIT-compiles (~28 s). Confirm `K` is a small handful (electronic-dominated on the goa corpus) and every listed label has `counts[label] >= 303`.

- [ ] **Step 7: Commit**

```bash
cd /home/kim/Projects/mir && git add src/tools/genre_vocab.py tests/test_genre_vocab.py && \
git commit -m "feat(style-adapter): corpus discogs-400 genre-vocab builder (>=303 min-support)"
cd /home/kim/Projects/SAO && git add control/sa3_control/genre_vocab.json && \
git commit -m "feat(style-adapter): fixed genre vocabulary for SA3 fingerprint conditioner"
```

---

### Task 2: Per-crop genre-vector plumbing (additive, no latent re-encode)

**Files:**
- Create: `/home/kim/Projects/mir/src/tools/crop_genre.py`
- Create: `/home/kim/Projects/mir/tests/test_crop_genre.py`
- Modify (in place, additive): every `/home/kim/Projects/latents_sa3/*.json`

**Interfaces:**
- Consumes: `genre_vocab.json` (Task 1) `{"vocab", "labels400"}`; the same effnet+genre heads as Task 1; `core.json_handler.safe_update(get_info_path(...), {...})`.
- Produces:
  - `genre_vector_from_probs(mean400: np.ndarray, vocab: list[str], labels400: list[str]) -> dict[str,float]` — `{genre: prob for genre in vocab} | {"other": 1 - sum(selected_probs)}`. A proper simplex; `other ∈ [0,1]`.
  - New crop-`.json` key `style_genre`: the dict above (vocab genres in vocab order + `"other"`). Read by Task 4.

- [ ] **Step 1: Write the failing test**

```python
# /home/kim/Projects/mir/tests/test_crop_genre.py
import numpy as np
from src.tools.crop_genre import genre_vector_from_probs

def test_genre_vector_is_a_simplex_with_other():
    labels = ["Goa", "Psy", "House", "Rock"]
    vocab = ["Goa", "Psy"]
    mean400 = np.array([0.30, 0.20, 0.10, 0.05], dtype=np.float32)  # sums <1, rest is 'other'
    v = genre_vector_from_probs(mean400, vocab, labels)
    assert set(v) == {"Goa", "Psy", "other"}
    assert abs(v["Goa"] - 0.30) < 1e-6 and abs(v["Psy"] - 0.20) < 1e-6
    assert abs(v["other"] - 0.50) < 1e-6            # 1 - (0.30+0.20)
    assert abs(sum(v.values()) - 1.0) < 1e-6        # simplex

def test_genre_vector_other_never_negative():
    labels = ["Goa", "Psy"]; vocab = ["Goa", "Psy"]
    v = genre_vector_from_probs(np.array([0.7, 0.7]), vocab, labels)
    assert v["other"] == 0.0                         # clamp, no negative
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd /home/kim/Projects/mir && mir/bin/python -m pytest tests/test_crop_genre.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.tools.crop_genre'`.

- [ ] **Step 3: Write the helper**

```python
# /home/kim/Projects/mir/src/tools/crop_genre.py
"""Store the fixed-vocab genre raw-prob vector + 'other' bucket into each crop .json.
Additive; genre is track-level so the head runs ONCE per source track. MIR venv."""
from __future__ import annotations
import numpy as np

def genre_vector_from_probs(mean400, vocab, labels400) -> dict:
    mean400 = np.asarray(mean400, dtype=np.float32)
    idx = {lbl: i for i, lbl in enumerate(labels400)}
    sel = {g: float(mean400[idx[g]]) for g in vocab}
    other = max(0.0, 1.0 - float(sum(sel.values())))
    return {**sel, "other": other}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd /home/kim/Projects/mir && mir/bin/python -m pytest tests/test_crop_genre.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Add the per-track store loop**

```python
# append to /home/kim/Projects/mir/src/tools/crop_genre.py
import glob, json, os, sys
from pathlib import Path

def store_genre(latents_dir, vocab_json):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import essentia.standard as es
    from core.json_handler import safe_update
    from classification.effnet_onnx import get_effnet_migraphx
    from classification.essentia_features import get_model_path
    from classification.gmi_onnx import get_gmi_model

    cfg = json.load(open(vocab_json)); vocab, labels400 = cfg["vocab"], cfg["labels400"]
    effnet = get_effnet_migraphx(get_model_path("discogs-effnet-bsdynamic-1.onnx"))
    models_dir = Path(get_model_path("genre_discogs400-discogs-effnet-1.pb")).parent
    genre = get_gmi_model("genre", models_dir)

    by_track = {}
    for j in glob.glob(os.path.join(latents_dir, "*.json")):
        m = json.load(open(j))
        by_track.setdefault(m.get("source_track") or m.get("path"), []).append((j, m))

    for i, (trk, crops) in enumerate(sorted(by_track.items())):
        if all("style_genre" in m for _, m in crops):
            continue                                   # resumable
        src = crops[0][1].get("source_path") or crops[0][1].get("path")
        if not src or not os.path.exists(src):
            print(f"[skip] {src}", flush=True); continue
        mean400 = np.mean(genre(effnet(es.MonoLoader(filename=src, sampleRate=16000, resampleQuality=4)())), axis=0)
        vec = genre_vector_from_probs(mean400, vocab, labels400)
        for j, _ in crops:
            safe_update(j, {"style_genre": vec})       # atomic merge; never rewrites the latent
        if (i + 1) % 50 == 0:
            print(f"[genre] {i+1}/{len(by_track)} tracks", flush=True)
    print("[genre] done", flush=True)

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--latents-dir", default="/home/kim/Projects/latents_sa3")
    ap.add_argument("--vocab", default="/home/kim/Projects/SAO/control/sa3_control/genre_vocab.json")
    a = ap.parse_args()
    store_genre(a.latents_dir, a.vocab)
```

Note: `get_info_path` expects an audio path; here the crop `.json` path is already the info path, so `safe_update(j, ...)` is called directly on the `.json`.

- [ ] **Step 6: Run the store loop (procedural, MIR venv)**

Run:
```bash
cd /home/kim/Projects/mir && \
mir/bin/python src/tools/crop_genre.py \
  --latents-dir /home/kim/Projects/latents_sa3 \
  --vocab /home/kim/Projects/SAO/control/sa3_control/genre_vocab.json
```
Expected: `[genre] done`. Verify one crop:
```bash
mir/bin/python -c "import json; d=json.load(open('/home/kim/Projects/latents_sa3/000000.json')); print(d['style_genre']); print('sum', round(sum(d['style_genre'].values()),5))"
```
Expected: a dict with the vocab genres + `other`, summing to 1.0.

- [ ] **Step 7: Commit**

```bash
cd /home/kim/Projects/mir && git add src/tools/crop_genre.py tests/test_crop_genre.py && \
git commit -m "feat(style-adapter): store per-crop genre raw-prob vector + other bucket (additive)"
```

---

### Task 3: `FingerprintEncoder` (generalize `ScalarAttributeEncoder`)

**Files:**
- Modify: `/home/kim/Projects/SAO/control/sa3_control/conditioner.py` (add class after `ScalarAttributeEncoder`, ~line 120)
- Create: `/home/kim/Projects/SAO/control/tests/test_fingerprint_encoder.py`

**Interfaces:**
- Consumes: nothing new (mirrors `ScalarAttributeEncoder`'s FiLM structure).
- Produces: `FingerprintEncoder(in_dim: int, control_dim: int = 768, n_tokens: int = 16, hidden: int = 256)`. `forward(vec: Tensor(B, in_dim)) -> Tensor(B, n_tokens, control_dim)`. Zero-init last FiLM layer → identity at init (output == broadcast base tokens), giving the same no-op training start as the scalar/audio-ref heads.

- [ ] **Step 1: Write the failing test**

```python
# /home/kim/Projects/SAO/control/tests/test_fingerprint_encoder.py
import torch
from sa3_control.conditioner import FingerprintEncoder

def test_forward_shape():
    enc = FingerprintEncoder(in_dim=15, control_dim=768, n_tokens=16)
    out = enc(torch.randn(4, 15))
    assert out.shape == (4, 16, 768)

def test_identity_at_init():
    enc = FingerprintEncoder(in_dim=15, control_dim=768, n_tokens=16)
    out = enc(torch.randn(3, 15))                 # zero-init FiLM -> scale=0, shift=0
    expected = enc.tokens[None].expand(3, -1, -1)
    assert torch.allclose(out, expected, atol=1e-6)

def test_accepts_2d_only_and_scales_params_with_in_dim():
    small = sum(p.numel() for p in FingerprintEncoder(1).parameters())
    big = sum(p.numel() for p in FingerprintEncoder(15).parameters())
    assert big - small < 5000                     # widening input is negligible param growth
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd /home/kim/Projects/SAO/control && /home/kim/Projects/SAO/.venv/bin/python -m pytest tests/test_fingerprint_encoder.py -v`
Expected: FAIL with `ImportError: cannot import name 'FingerprintEncoder'`.

- [ ] **Step 3: Implement `FingerprintEncoder`**

```python
# add to /home/kim/Projects/SAO/control/sa3_control/conditioner.py (after ScalarAttributeEncoder)
class FingerprintEncoder(nn.Module):
    """A style fingerprint VECTOR (B, in_dim) -> control tokens (B, n_tokens, control_dim).

    Generalizes ScalarAttributeEncoder from a 1-dim scalar to an in_dim-dim fingerprint
    (genre softmax + other, release_year, bpm, syncopation, [+ window onset/energy]).
    A bank of n_tokens learned base tokens is FiLM-modulated by the fingerprint. Widening
    the FiLM input from 1 to ~15 dims adds negligible params, so the adapter is the same
    size as the scalar one. Zero-init FiLM output -> identity at init (no-op start).

    Fingerprint dims are expected pre-normalized; the all-zero vector is the cfg-dropout null.
    """
    def __init__(self, in_dim: int, control_dim: int = 768, n_tokens: int = 16, hidden: int = 256):
        super().__init__()
        self.in_dim = int(in_dim)
        self.n_tokens = int(n_tokens)
        self.control_dim = int(control_dim)
        self.tokens = nn.Parameter(torch.randn(n_tokens, control_dim) * 0.02)
        self.film = nn.Sequential(
            nn.Linear(self.in_dim, hidden), nn.SiLU(),
            nn.Linear(hidden, n_tokens * control_dim * 2),
        )
        nn.init.zeros_(self.film[-1].weight)
        nn.init.zeros_(self.film[-1].bias)

    def forward(self, vec):                                     # (B, in_dim)
        x = vec.reshape(-1, self.in_dim).to(self.tokens.dtype)
        gb = self.film(x).view(-1, self.n_tokens, self.control_dim, 2)
        scale, shift = gb[..., 0], gb[..., 1]
        return self.tokens[None] * (1.0 + scale) + shift       # (B, n_tokens, control_dim)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd /home/kim/Projects/SAO/control && /home/kim/Projects/SAO/.venv/bin/python -m pytest tests/test_fingerprint_encoder.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
cd /home/kim/Projects/SAO && git add control/sa3_control/conditioner.py control/tests/test_fingerprint_encoder.py && \
git commit -m "feat(style-adapter): FingerprintEncoder (vector->FiLM control tokens)"
```

---

### Task 4: Dataset — fingerprint assembly + window-scalar alignment fix

**Files:**
- Modify: `/home/kim/Projects/SAO/control/sa3_control/dataset.py`
- Create: `/home/kim/Projects/SAO/control/tests/test_fingerprint_dataset.py`

**Interfaces:**
- Consumes: crop `.json` keys `style_genre` (Task 2), `release_year`, `bpm_madmom`, `syncopation`; the `.TIMESERIES.npz` fields `onset_envelope_ts` (4096,), `rms_energy_bass_ts`/`_body_ts`/`_mid_ts`/`_air_ts` (4096,); the already-sliced `controls` dict from `__getitem__` (the window fix).
- Produces (all in `dataset.py`; called by Task 5's trainer):
  - `fingerprint_in_dim(variant: str, k: int) -> int` — `"A"→k+1+3`, `"B"→k+1+5`, `"C"→k+1+1` (`k = len(vocab)`, genre block is `k+1` incl `other`; year always +1; A/B add bpm+sync (+2), B adds onset+energy (+2), C adds year only).
  - `window_energy(rms_window: np.ndarray) -> float` — `float(mean)`.
  - `window_onset_density(onset_env_window: np.ndarray, frame_rate: float = 10.767) -> float` — peak-count / (len/frame_rate).
  - `LatentControlDataset.__init__` new kwargs: `fingerprint: bool = False`, `genre_vocab: list[str] | None = None`, `fp_variant: str = "A"`, `year_norm=(1990.0,30.0)`, `bpm_norm=(140.0,20.0)`, `sync_norm=(0.5,0.25)`, `onset_norm=(0.0,1.0)`, `energy_norm=(0.0,1.0)`.
  - `__getitem__` adds `item["fingerprint"]: Tensor(in_dim,)` when `fingerprint=True`.

- [ ] **Step 1: Write the failing test**

```python
# /home/kim/Projects/SAO/control/tests/test_fingerprint_dataset.py
import numpy as np
from sa3_control.dataset import fingerprint_in_dim, window_energy, window_onset_density

def test_fingerprint_in_dim_variants():
    k = 6
    assert fingerprint_in_dim("A", k) == k + 1 + 3   # genre+other + year + bpm + sync
    assert fingerprint_in_dim("B", k) == k + 1 + 5    # + onset + energy
    assert fingerprint_in_dim("C", k) == k + 1 + 1    # genre+other + year

def test_window_energy_is_mean():
    assert abs(window_energy(np.array([0.2, 0.4, 0.6], np.float32)) - 0.4) < 1e-6

def test_window_onset_density_counts_peaks_per_second():
    env = np.zeros(1077, np.float32)                 # ~100 s at 10.767 Hz
    env[[100, 300, 500, 700, 900]] = 1.0             # 5 isolated peaks
    d = window_onset_density(env, frame_rate=10.767)
    assert abs(d - 5.0 / (1077 / 10.767)) < 0.2      # ~5 onsets / ~100 s
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd /home/kim/Projects/SAO/control && /home/kim/Projects/SAO/.venv/bin/python -m pytest tests/test_fingerprint_dataset.py -v`
Expected: FAIL with `ImportError: cannot import name 'fingerprint_in_dim'`.

- [ ] **Step 3: Implement the deterministic dataset helpers**

```python
# add near the top of /home/kim/Projects/SAO/control/sa3_control/dataset.py (after CONTROL_DIMS)
def fingerprint_in_dim(variant: str, k: int) -> int:
    base = k + 1 + 1                       # genre(k)+other(1)+year(1)
    return {"A": base + 2, "B": base + 4, "C": base}[variant]  # A:+bpm+sync  B:+bpm+sync+onset+energy  C:year-only

def window_energy(rms_window) -> float:
    return float(np.asarray(rms_window, dtype=np.float32).mean())

def window_onset_density(onset_env_window, frame_rate: float = 10.767) -> float:
    a = np.asarray(onset_env_window, dtype=np.float32).reshape(-1)
    if a.size < 3:
        return 0.0
    thr = a.mean() + a.std()
    pk = np.where((a[1:-1] > a[:-2]) & (a[1:-1] >= a[2:]) & (a[1:-1] > thr))[0]
    return float(len(pk)) / (len(a) / frame_rate)
```

- [ ] **Step 4: Run the helper tests to verify they pass**

Run: `cd /home/kim/Projects/SAO/control && /home/kim/Projects/SAO/.venv/bin/python -m pytest tests/test_fingerprint_dataset.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Wire the fingerprint into `LatentControlDataset` (constructor)**

Modify `__init__` signature (dataset.py:53-55) to add the kwargs from the Interfaces block, store them, and — for the volatile V-B window features — force-load the timeseries. Add after `self.random_crop_frames = ...`:

```python
        # style-fingerprint mode
        self.fingerprint = bool(fingerprint)
        self.genre_vocab = list(genre_vocab) if genre_vocab else []
        self.fp_variant = fp_variant
        self.year_norm, self.bpm_norm = year_norm, bpm_norm
        self.sync_norm, self.onset_norm, self.energy_norm = sync_norm, onset_norm, energy_norm
        if self.fingerprint and fp_variant == "B" and "fp_volatile" not in self.controls:
            self.controls = list(self.controls) + ["fp_volatile"]   # load onset+energy timeseries
```

Add a `CONTROL_FIELDS` entry so `_load_controls` fetches the two volatile channels (dataset.py:21):

```python
    "fp_volatile": ["onset_envelope_ts", "rms_energy_mid_ts"],   # V-B window onset + energy source
```
and `CONTROL_DIMS["fp_volatile"] = 2`.

- [ ] **Step 6: Add `_build_fingerprint` and call it in `__getitem__`**

```python
# method on LatentControlDataset
def _build_fingerprint(self, m: dict, controls: dict) -> torch.Tensor:
    g = m.get("style_genre", {})
    vec = [float(g.get(name, 0.0)) for name in self.genre_vocab]        # genre block (vocab order)
    vec.append(float(g.get("other", 1.0 - sum(vec))))                   # other bucket
    ym, ys = self.year_norm
    vec.append((float(m.get("release_year", ym)) - ym) / ys)           # normalized year
    if self.fp_variant in ("A", "B"):
        bm, bs = self.bpm_norm; sm, ss = self.sync_norm
        vec.append((float(m.get("bpm_madmom", bm)) - bm) / bs)         # normalized bpm (stable, track-level)
        vec.append((float(m.get("syncopation", sm)) - sm) / ss)       # normalized syncopation
    if self.fp_variant == "B":
        vol = controls["fp_volatile"]                                  # (2, tw) ALREADY sliced to the window
        onset_w, energy_w = vol[0].numpy(), vol[1].numpy()
        om, os_ = self.onset_norm; em, es_ = self.energy_norm
        vec.append((window_onset_density(onset_w) - om) / os_)        # window-aggregated (alignment fix)
        vec.append((window_energy(energy_w) - em) / es_)
    return torch.tensor(vec, dtype=torch.float32)
```

In `__getitem__`, after the controls have been sliced to the window (dataset.py:141), add:

```python
        if self.fingerprint:
            item["fingerprint"] = self._build_fingerprint(m, controls)
```

**Window-scalar alignment note:** V-B reads onset/energy from `controls["fp_volatile"]`, which `__getitem__` already slices to the beat-aligned window (`v[:, s:s+tw]`), NOT from the crop-level `.json`. This is the alignment fix from the spec — and Task 5 applies the same fix to the existing onset scalar head via `--scalar-from-timeseries`.

- [ ] **Step 7: Add an integration test against one real crop**

```python
# append to /home/kim/Projects/SAO/control/tests/test_fingerprint_dataset.py
import glob, os, pytest, json
from sa3_control.dataset import LatentControlDataset

LAT = "/home/kim/Projects/latents_sa3"

@pytest.mark.skipif(not glob.glob(os.path.join(LAT, "*.npy")), reason="NVMe latents not present")
def test_fingerprint_item_shape_variant_A():
    vocab = json.load(open("/home/kim/Projects/SAO/control/sa3_control/genre_vocab.json"))["vocab"]
    ds = LatentControlDataset(LAT, controls=(), audio_ref=None, fingerprint=True,
                              genre_vocab=vocab, fp_variant="A", random_crop_frames=512)
    fp = ds[0]["fingerprint"]
    from sa3_control.dataset import fingerprint_in_dim
    assert fp.shape == (fingerprint_in_dim("A", len(vocab)),)
```

- [ ] **Step 8: Run all dataset tests**

Run: `cd /home/kim/Projects/SAO/control && /home/kim/Projects/SAO/.venv/bin/python -m pytest tests/test_fingerprint_dataset.py -v`
Expected: PASS (4 passed; the integration test runs if latents are mounted).

- [ ] **Step 9: Commit**

```bash
cd /home/kim/Projects/SAO && git add control/sa3_control/dataset.py control/tests/test_fingerprint_dataset.py && \
git commit -m "feat(style-adapter): dataset fingerprint assembly + window-scalar alignment fix"
```

---

### Task 5: Trainer wiring for the 3 variants + EMA / grad-accum / early-stop

**Files:**
- Modify: `/home/kim/Projects/SAO/control/sa3_control/train.py`
- Modify: `/home/kim/Projects/SAO/control/sa3_control/generate.py` (conditioner selection for eval load)
- Create: `/home/kim/Projects/SAO/control/tests/test_train_wiring.py`

**Interfaces:**
- Consumes: `FingerprintEncoder` (Task 3); `LatentControlDataset(..., fingerprint=True, genre_vocab=, fp_variant=)`, `fingerprint_in_dim` (Task 4).
- Produces: new args `--control-mode fingerprint`, `--fp-variant {A,B,C}`, `--genre-vocab <path>`, `--ema <decay>` (0 disables), `--grad-accum <n>`, `--max-epochs <n>`, `--val-frac <f>`, `--early-stop-patience <epochs>`. Checkpoint keys extended: `"control_mode": "fingerprint"`, `"fp_variant"`, `"genre_vocab"`, `"fp_in_dim"`. `collate` handles `"fingerprint"`. An `EMA` helper class. `generate.load_adapter_state` unchanged; `generate.py` gains a `build_conditioner(ck, device, dtype)` factory returning the right encoder from a checkpoint (used by eval, Task 7).

- [ ] **Step 1: Write the failing test (deterministic wiring unit)**

```python
# /home/kim/Projects/SAO/control/tests/test_train_wiring.py
import torch
from sa3_control.train import EMA

def test_ema_tracks_toward_current_weights():
    p = [torch.zeros(4, requires_grad=True)]
    ema = EMA(p, decay=0.9)
    with torch.no_grad():
        p[0].add_(1.0)              # weights move to 1.0
    ema.update()
    assert torch.allclose(ema.shadow[0], torch.full((4,), 0.1), atol=1e-6)  # 0.9*0 + 0.1*1

def test_ema_copy_and_restore_roundtrip():
    p = [torch.ones(3)]
    ema = EMA(p, decay=0.5)
    ema.shadow[0].fill_(9.0)
    ema.copy_to();  assert torch.allclose(p[0], torch.full((3,), 9.0))
    ema.restore();  assert torch.allclose(p[0], torch.ones(3))
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd /home/kim/Projects/SAO/control && /home/kim/Projects/SAO/.venv/bin/python -m pytest tests/test_train_wiring.py -v`
Expected: FAIL with `ImportError: cannot import name 'EMA'`.

- [ ] **Step 3: Add the `EMA` helper and new args to `train.py`**

```python
# add near the top of train.py (after imports)
class EMA:
    """Exponential moving average of the trainable params (standing recipe: EMA + grad-accum + early-stop)."""
    def __init__(self, params, decay: float):
        self.decay = float(decay)
        self.params = list(params)
        self.shadow = [p.detach().float().clone() for p in self.params]
        self.backup = None
    @torch.no_grad()
    def update(self):
        for s, p in zip(self.shadow, self.params):
            s.mul_(self.decay).add_(p.detach().float(), alpha=1.0 - self.decay)
    @torch.no_grad()
    def copy_to(self):
        self.backup = [p.detach().clone() for p in self.params]
        for s, p in zip(self.shadow, self.params):
            p.data.copy_(s.to(p.dtype))
    @torch.no_grad()
    def restore(self):
        for b, p in zip(self.backup, self.params):
            p.data.copy_(b)
        self.backup = None
```

Add argparse entries (near the other `ap.add_argument` calls):

```python
    ap.add_argument("--fp-variant", choices=["A", "B", "C"], default="A",
                    help="fingerprint scope: A=style+groove (genre+year+bpm+sync); "
                         "B=maximal (+window onset+energy); C=style-only (genre+year)")
    ap.add_argument("--genre-vocab", default=os.path.join(os.path.dirname(__file__), "genre_vocab.json"))
    ap.add_argument("--ema", type=float, default=0.999, help="EMA decay (0 disables)")
    ap.add_argument("--grad-accum", type=int, default=2, help="accumulate this many microbatches per opt.step")
    ap.add_argument("--max-epochs", type=int, default=20, help="early-stop epoch cap (standing recipe ~20)")
    ap.add_argument("--val-frac", type=float, default=0.05, help="held-out track fraction for early-stop RF loss")
    ap.add_argument("--early-stop-patience", type=int, default=4, help="stop after N epochs w/o val-loss improvement")
```

Extend the `--control-mode` choices to include `"fingerprint"` (train.py:212).

- [ ] **Step 4: Wire the fingerprint conditioner + dataset in `main()`**

In the conditioner-selection block (train.py:261-280) add a branch:

```python
    elif args.control_mode == "fingerprint":
        import json as _json
        from sa3_control.conditioner import FingerprintEncoder
        from sa3_control.dataset import fingerprint_in_dim
        vocab = _json.load(open(args.genre_vocab))["vocab"]
        in_dim = fingerprint_in_dim(args.fp_variant, len(vocab))
        cond_enc = FingerprintEncoder(in_dim=in_dim, control_dim=args.control_dim,
                                      n_tokens=min(args.n_tokens, 16)).to(device=device, dtype=dtype)
        print(f"[control] fingerprint V-{args.fp_variant} in_dim={in_dim} (K={len(vocab)}) -> FingerprintEncoder",
              flush=True)
```

In the dataset-selection block (train.py:330-363) add:

```python
    elif args.control_mode == "fingerprint":
        import json as _json
        vocab = _json.load(open(args.genre_vocab))["vocab"]
        ds = LatentControlDataset(args.encoded_dir, controls=(), audio_ref=None,
                                  seed=args.seed, subset_tracks=args.subset_tracks,
                                  fingerprint=True, genre_vocab=vocab, fp_variant=args.fp_variant,
                                  random_crop_frames=args.crop_frames)
```

In `collate` (train.py:36-47) add:

```python
    if "fingerprint" in batch[0]:
        out["fingerprint"] = torch.stack([b["fingerprint"] for b in batch])
```

In the training step (train.py:425-436) add the fingerprint control path:

```python
            elif args.control_mode == "fingerprint":
                ctrl = cond_enc(b["fingerprint"].to(device=device, dtype=dtype))   # (B, n_tokens, control_dim)
```

- [ ] **Step 5: Wire EMA + grad-accum into the loop**

After the optimizer is built, add:

```python
    ema = EMA(params, args.ema) if args.ema and args.ema > 0 else None
```

Wrap the step: divide `loss` by `args.grad_accum` before `loss.backward()`, and only call `opt.step()` / `opt.zero_grad()` / `ema.update()` every `args.grad_accum` micro-steps. Concretely, replace the `opt.zero_grad(...)` / `opt.step()` region so:

```python
            loss = loss / args.grad_accum
            ...
                loss.backward()
            if (step + 1) % args.grad_accum == 0:
                gnorm = torch.nn.utils.clip_grad_norm_(params, 1.0)
                opt.step()
                opt.zero_grad(set_to_none=True)
                if ema is not None:
                    ema.update()
```

At each checkpoint save and the final save, if `ema is not None`: `ema.copy_to()` before `adapter_state_dict(...)`, then `ema.restore()` after — so the saved `"state"` is the EMA (averaged) weights, matching the standing recipe. Extend the saved dict with:

```python
                "control_mode": args.control_mode, "fp_variant": getattr(args, "fp_variant", None),
                "genre_vocab": (_json.load(open(args.genre_vocab))["vocab"] if args.control_mode == "fingerprint" else None),
                "fp_in_dim": (getattr(cond_enc, "in_dim", None)),
```

- [ ] **Step 6: Add epoch-based early-stop on held-out RF loss**

Split tracks into train/val by `args.val_frac` (reuse the `subset_tracks` track-level split pattern, dataset.py:70-76). After each epoch, with EMA weights active (`ema.copy_to()`), compute mean RF loss over a fixed ~200-crop val sample (same forward as train, no backward); track best; `ema.restore()`. Stop when `epochs_since_best >= args.early_stop_patience` or `epoch >= args.max_epochs`, saving `riffer_final.pt` (EMA weights). Log `val/rf_loss` to wandb each epoch. Keep the RF-loss-blindness caveat in a comment: RF val loss is a coarse early-stop signal (loss is nearly blind to control); the `--max-epochs 20` cap is the practical stop, val loss guards against divergence.

- [ ] **Step 7: Add `build_conditioner` factory to `generate.py`**

```python
# in generate.py
def build_conditioner(ck, device, dtype):
    cm = ck.get("control_mode", "audio_ref")
    control_dim = int(ck["args"].get("control_dim", 768))
    if cm == "fingerprint":
        from sa3_control.conditioner import FingerprintEncoder
        enc = FingerprintEncoder(in_dim=int(ck["fp_in_dim"]), control_dim=control_dim,
                                 n_tokens=min(int(ck["args"].get("n_tokens", 16)), 16))
    elif cm == "scalar":
        from sa3_control.conditioner import ScalarAttributeEncoder
        enc = ScalarAttributeEncoder(control_dim=control_dim,
                                     n_tokens=min(int(ck["args"].get("n_tokens", 16)), 16))
    else:
        from sa3_control.conditioner import AudioRefEncoder
        enc = AudioRefEncoder(256, control_dim, int(ck["args"].get("n_tokens", 256)))
    return enc.to(device=device, dtype=dtype)
```

- [ ] **Step 8: Run the wiring test + a 3-step smoke of each variant**

Run:
```bash
cd /home/kim/Projects/SAO/control && /home/kim/Projects/SAO/.venv/bin/python -m pytest tests/test_train_wiring.py -v
FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_FIND_MODE=2 \
  /home/kim/Projects/SAO/.venv/bin/python sa3_control/train.py \
  --encoded_dir /home/kim/Projects/latents_sa3 --control-mode fingerprint --fp-variant A \
  --crop-frames 512 --smoke
```
Expected: pytest PASS (2); the smoke prints `[control] fingerprint V-A in_dim=... -> FingerprintEncoder` and `[smoke OK] ... adapter tensors got grads; ... base cross-attn frozen=True got_no_grad=True`. Repeat `--fp-variant B` and `--fp-variant C`.

- [ ] **Step 9: Commit**

```bash
cd /home/kim/Projects/SAO && git add control/sa3_control/train.py control/sa3_control/generate.py control/tests/test_train_wiring.py && \
git commit -m "feat(style-adapter): trainer wiring for 3 fingerprint variants + EMA/grad-accum/early-stop"
```

---

### Task 6: v2 telemetry hook (per-region flow-loss + control-extreme failures, logged only)

**Files:**
- Modify: `/home/kim/Projects/SAO/control/sa3_control/telemetry.py`
- Modify: `/home/kim/Projects/SAO/control/sa3_control/train.py` (call the hook)
- Create: `/home/kim/Projects/SAO/control/tests/test_telemetry_coverage.py`

**Interfaces:**
- Consumes: `TrainTelemetry` (existing); per-step `t` (Tensor(B,)), `loss` (float), `fp_vec` (Tensor(B, in_dim)).
- Produces:
  - `region_bin(t: float, n_bins: int = 8) -> int` — floor(t*n_bins), clamped to `[0, n_bins-1]`.
  - `is_control_extreme(fp_vec: np.ndarray, thresh: float = 2.5) -> bool` — any normalized fingerprint dim with `abs >= thresh` (an out-of-distribution/extreme request).
  - `TrainTelemetry.log_coverage(step, t, loss, fp_vec)` — accumulates flow-loss per timestep region and counts control-extreme steps; logs `coverage/region_<i>_loss` and `coverage/n_extreme` to wandb. **v2-only data; nothing consumes it in v1.**

- [ ] **Step 1: Write the failing test**

```python
# /home/kim/Projects/SAO/control/tests/test_telemetry_coverage.py
import numpy as np
from sa3_control.telemetry import region_bin, is_control_extreme

def test_region_bin_edges():
    assert region_bin(0.0, 8) == 0
    assert region_bin(0.999, 8) == 7
    assert region_bin(1.0, 8) == 7           # clamped
    assert region_bin(0.5, 8) == 4

def test_is_control_extreme():
    assert is_control_extreme(np.array([0.1, 3.0, -0.2]), thresh=2.5) is True
    assert is_control_extreme(np.array([0.1, 0.2, -0.2]), thresh=2.5) is False
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd /home/kim/Projects/SAO/control && /home/kim/Projects/SAO/.venv/bin/python -m pytest tests/test_telemetry_coverage.py -v`
Expected: FAIL with `ImportError: cannot import name 'region_bin'`.

- [ ] **Step 3: Implement the helpers + `log_coverage`**

```python
# add to telemetry.py
def region_bin(t: float, n_bins: int = 8) -> int:
    return int(min(n_bins - 1, max(0, int(float(t) * n_bins))))

def is_control_extreme(fp_vec, thresh: float = 2.5) -> bool:
    return bool(np.abs(np.asarray(fp_vec, dtype=np.float32)).max() >= thresh)
```
(Add `import numpy as np` to telemetry.py.) On `TrainTelemetry`:

```python
    def log_coverage(self, step, t, loss, fp_vec, n_bins: int = 8):
        """v2 hook: per-timestep-region flow-loss + control-extreme count. LOGGED ONLY —
        v2 (importance-weighted / coverage-guided training) consumes this later; v1 does not."""
        if self.wb is None:
            return
        try:
            import numpy as _np
            tb = float(_np.asarray(t.detach().cpu()).mean())
            d = {f"coverage/region_{region_bin(tb, n_bins)}_loss": float(loss),
                 "coverage/n_extreme": int(sum(is_control_extreme(v) for v in _np.asarray(fp_vec.detach().cpu())))}
            self.wb.log(d, step=step)
        except Exception:
            pass
```

- [ ] **Step 4: Call the hook from `train.py`**

After the existing `telem.log(...)` call (train.py:500), add:

```python
                if args.control_mode == "fingerprint":
                    telem.log_coverage(step, t, loss.item(), b["fingerprint"])
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd /home/kim/Projects/SAO/control && /home/kim/Projects/SAO/.venv/bin/python -m pytest tests/test_telemetry_coverage.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
cd /home/kim/Projects/SAO && git add control/sa3_control/telemetry.py control/sa3_control/train.py control/tests/test_telemetry_coverage.py && \
git commit -m "feat(style-adapter): v2 coverage telemetry hook (per-region loss + extremes, logged only)"
```

---

### Task 7: Eval — genre-softmax-of-output metric + comparison harness + benchmark + winner bracket

**Files:**
- Create: `/home/kim/Projects/mir/src/tools/genre_softmax_of_audio.py` (MIR venv — reruns the discogs head on generated wavs)
- Create: `/home/kim/Projects/mir/tests/test_genre_softmax_of_audio.py`
- Create: `/home/kim/Projects/SAO/control/sa3_control/style_eval.py` (SA3 venv — generates clips for a fingerprint ckpt)
- Create: `/home/kim/Projects/SAO/control/sa3_control/mert_dist.py` (MERT mid-layer cos-dist-to-goa)

**Interfaces:**
- Consumes: `build_conditioner(ck, ...)` (Task 5); `install_adapters`, `load_adapter_state`, `use_control_context`, `ControlContext` (existing); `MeritScorer` (merit_eval.py); `genre_vocab.json`; the discogs head (Task 1/2).
- Produces:
  - `goa_prob_from_probs(mean400: np.ndarray, labels400: list[str]) -> float` — sum of mean probs over labels whose name contains `"Goa"` (i.e. `Electronic---Goa Trance`).
  - `style_eval.py` CLI: `<ckpt.pt> --out <dir> --prompts a||b --seeds ... --gain ... --duration 20` → wavs + `manifest.json` (`file, prompt, seed, gain, fingerprint_target`). Target fingerprint = goa (genre one-hot on the Goa vocab dim, year=1996-normalized, corpus-mean bpm/sync).
  - `mert_dist.py`: `mert_mid_cos_dist(wav, sr, goa_centroid) -> float` = `1 - cos(mean_pool(MERT hidden layer 12), goa_centroid)`.

- [ ] **Step 1: Write the failing test for the output metric**

```python
# /home/kim/Projects/mir/tests/test_genre_softmax_of_audio.py
import numpy as np
from src.tools.genre_softmax_of_audio import goa_prob_from_probs

def test_goa_prob_sums_goa_labels():
    labels = ["Electronic---Goa Trance", "Electronic---Psytrance", "Rock---Pop Rock"]
    mean400 = np.array([0.42, 0.30, 0.05], dtype=np.float32)
    assert abs(goa_prob_from_probs(mean400, labels) - 0.42) < 1e-6

def test_goa_prob_zero_when_absent():
    labels = ["Electronic---Psytrance", "Rock---Pop Rock"]
    assert goa_prob_from_probs(np.array([0.3, 0.2]), labels) == 0.0
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd /home/kim/Projects/mir && mir/bin/python -m pytest tests/test_genre_softmax_of_audio.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `genre_softmax_of_audio.py`**

```python
# /home/kim/Projects/mir/src/tools/genre_softmax_of_audio.py
"""Re-run the discogs-400 head on GENERATED audio: does the adapter make output
classify more 'goa'? The objective style metric the design uniquely enables. MIR venv."""
from __future__ import annotations
import numpy as np, sys
from pathlib import Path

def goa_prob_from_probs(mean400, labels400) -> float:
    mean400 = np.asarray(mean400, dtype=np.float32)
    return float(sum(mean400[i] for i, l in enumerate(labels400) if "Goa" in l))

def goa_prob_of_wav(wav_path: str) -> float:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import essentia.standard as es
    from classification.effnet_onnx import get_effnet_migraphx
    from classification.essentia_features import get_model_path, get_classification_labels
    from classification.gmi_onnx import get_gmi_model
    labels400 = get_classification_labels()["genre"]
    effnet = get_effnet_migraphx(get_model_path("discogs-effnet-bsdynamic-1.onnx"))
    models_dir = Path(get_model_path("genre_discogs400-discogs-effnet-1.pb")).parent
    genre = get_gmi_model("genre", models_dir)
    audio = es.MonoLoader(filename=wav_path, sampleRate=16000, resampleQuality=4)()
    return goa_prob_from_probs(np.mean(genre(effnet(audio)), axis=0), labels400)

if __name__ == "__main__":
    import argparse, glob, json, os
    ap = argparse.ArgumentParser(); ap.add_argument("wav_dir"); ap.add_argument("--out", default=None)
    a = ap.parse_args()
    rows = [{"file": os.path.basename(w), "goa_prob": goa_prob_of_wav(w)}
            for w in sorted(glob.glob(os.path.join(a.wav_dir, "*.wav")))]
    print(json.dumps(rows, indent=1))
    if a.out: json.dump(rows, open(a.out, "w"), indent=1)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd /home/kim/Projects/mir && mir/bin/python -m pytest tests/test_genre_softmax_of_audio.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Implement `mert_dist.py` and `style_eval.py`**

`mert_dist.py`:
```python
# /home/kim/Projects/SAO/control/sa3_control/mert_dist.py
"""MERT mid-layer cosine distance to a cached goa centroid (the head-sweep ranker)."""
from __future__ import annotations
import numpy as np, torch
MODEL_ID = "m-a-p/MERT-v1-330M"; SR = 24_000; MID = 12

class MertMid:
    def __init__(self, device="cpu"):
        from transformers import AutoModel, Wav2Vec2FeatureExtractor
        self.device = device
        self.proc = Wav2Vec2FeatureExtractor.from_pretrained(MODEL_ID, trust_remote_code=True)
        self.mert = AutoModel.from_pretrained(MODEL_ID, trust_remote_code=True).to(device).eval()
    @torch.no_grad()
    def embed(self, wav, sr):
        import torchaudio
        w = torch.as_tensor(wav).float()
        if w.ndim == 2: w = w.mean(0)
        if sr != SR: w = torchaudio.functional.resample(w, sr, SR)
        w = w[:SR * 30]
        inp = {k: v.to(self.device) for k, v in self.proc(w.cpu().numpy(), sampling_rate=SR, return_tensors="pt").items()}
        h = self.mert(**inp, output_hidden_states=True).hidden_states[MID].mean(1)  # (1,1024)
        return torch.nn.functional.normalize(h, dim=-1)

def mert_mid_cos_dist(emb, goa_centroid) -> float:
    return float(1.0 - (emb * goa_centroid).sum().item())
```

`style_eval.py` mirrors `multi_eval.py` but uses `build_conditioner` and a fingerprint target vector (goa). Load ckpt, `install_adapters`, `build_conditioner(ck, ...)`, `load_adapter_state(ck["state"], wrappers, enc)`; build the goa fingerprint from `ck["genre_vocab"]` + `ck["fp_variant"]` (genre one-hot on `Electronic---Goa Trance`, year norm for 1996, corpus-mean bpm/sync, V-B onset/energy = 0 = null); generate with `use_control_context(ControlContext(ctrl, gain=args.gain))`; `save_audio(...)` (never raw `torchaudio.save`); write `manifest.json`. CFG batch-doubling as in `multi_eval.gen` (concat control with zeros).

- [ ] **Step 6: Run the 3-variant ~5-epoch benchmark (procedural)**

For each variant, launch via the good-settings wrapper (NVMe latents, CK FA, thread caps baked in). Override the interpreter and pass fingerprint args through:
```bash
cd /home/kim/Projects/SAO/control
for V in A B C; do
  SA3_VENV=/home/kim/Projects/SAO/.venv/bin/python \
  ENCODED_DIR=/home/kim/Projects/latents_sa3 STEPS=999999 SAVE_EVERY=2700 \
  ./run_control_train.sh style_V${V}_5ep 7.5e-5 adamw \
    --control-mode fingerprint --fp-variant ${V} \
    --genre-vocab /home/kim/Projects/SAO/control/sa3_control/genre_vocab.json \
    --ema 0.999 --grad-accum 2 --max-epochs 5 --crop-frames 512 \
    --control-dim 768 --n-tokens 256 --no-checkpoint --random-crop
done
```
Expected: three run dirs under `$SAVE_ROOT/style_V{A,B,C}_5ep/` each with `riffer_final.pt` (EMA weights). The first step compiles kernels (~minutes, no log line — do not kill). Read `wandb` `val/rf_loss` and `coverage/*` per run.

- [ ] **Step 7: Score each variant and pick the winner (procedural)**

Generate + score for each variant:
```bash
# generate (SA3 venv)
for V in A B C; do
  FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE /home/kim/Projects/SAO/.venv/bin/python \
    -m sa3_control.style_eval "$SAVE_ROOT/style_V${V}_5ep/riffer_final.pt" \
    --out "$SAVE_ROOT/style_V${V}_5ep/eval" --prompts "psytrance||ambient electronic" \
    --seeds 1234,777 --gain 512 --duration 20
done
# genre-softmax-of-output (MIR venv)
for V in A B C; do
  /home/kim/Projects/mir/mir/bin/python \
    /home/kim/Projects/mir/src/tools/genre_softmax_of_audio.py \
    "$SAVE_ROOT/style_V${V}_5ep/eval" --out "$SAVE_ROOT/style_V${V}_5ep/eval/goa_prob.json"
done
```
Then compute per-variant: mean `goa_prob` (higher = more goa), MERT mid cos-dist-to-goa (lower = closer; `mert_dist.MertMid` vs a goa centroid = mean MERT-mid embedding over ~20 corpus goa clips), and Audiobox CE via `mir/src/timbral/audiobox_aesthetics.py` (single-file mode, MIR venv). Rank by MERT cos_dist_mid (the ranker), gate on Audiobox CE ≥ base. Also render a riffer-evals same-playhead playable cell page for by-ear (authoritative). **Winner = lowest MERT cos_dist_mid among CE-non-regressing variants, confirmed by ear.** Record the choice in the run dir's `run_meta.json`.

- [ ] **Step 8: Run the winner bracket (LR / optimizer / capacity) (procedural)**

For the winning variant `W`, sweep at full `--max-epochs 20`:
```bash
cd /home/kim/Projects/SAO/control
for LR in 5e-5 7.5e-5 1e-4; do for OPT in adamw fusion; do
  SA3_VENV=/home/kim/Projects/SAO/.venv/bin/python ENCODED_DIR=/home/kim/Projects/latents_sa3 \
  STEPS=999999 SAVE_EVERY=2700 ./run_control_train.sh style_V${W}_lr${LR}_${OPT} ${LR} ${OPT} \
    --control-mode fingerprint --fp-variant ${W} \
    --genre-vocab /home/kim/Projects/SAO/control/sa3_control/genre_vocab.json \
    --ema 0.999 --grad-accum 2 --max-epochs 20 --crop-frames 512 --control-dim 768 --n-tokens 256 \
    --no-checkpoint --random-crop
done; done
```
Capacity axis: additionally rerun the best LR/opt with `--n-tokens 32` (FiLM bank up to 32 vs 16 — edit the `min(args.n_tokens, 16)` cap to `min(args.n_tokens, 32)` behind the same arg) to test whether more control tokens help. Score each with Step 7's pipeline; pick the final ship checkpoint by MERT cos_dist_mid + Audiobox CE + by-ear.

- [ ] **Step 9: Commit the eval tooling**

```bash
cd /home/kim/Projects/mir && git add src/tools/genre_softmax_of_audio.py tests/test_genre_softmax_of_audio.py && \
git commit -m "feat(style-adapter): genre-softmax-of-output eval metric"
cd /home/kim/Projects/SAO && git add control/sa3_control/style_eval.py control/sa3_control/mert_dist.py && \
git commit -m "feat(style-adapter): fingerprint eval harness (style_eval + MERT mid cos-dist)"
```

---

### Task 8: Sanity checks — discogs head separation + onset head after the alignment fix

**Files:**
- Create: `/home/kim/Projects/mir/src/tools/genre_sanity_check.py`
- Test artifacts only (no new module tested beyond the reused helpers)

**Interfaces:**
- Consumes: `genre_softmax_of_audio.goa_prob_of_wav` (Task 7); the existing onset scalar head + `multi_eval.py` (existing).
- Produces: a printed pass/fail on (a) discogs head separates 90s-goa from modern-psy, and (b) the onset head's control correlation is not regressed by the window-scalar fix.

- [ ] **Step 1: Assemble the 10-track sanity set**

Pick 5 known 90s-goa tracks and 5 modern-psy tracks from `/run/media/kim/Mantu/ai-music/Goa_Separated/` (list their `full_mix.flac` paths in `genre_sanity_check.py`). Use `track_metadata_year` from their crop `.json`s to confirm the era split.

- [ ] **Step 2: Implement and run the separation check (MIR venv)**

```python
# /home/kim/Projects/mir/src/tools/genre_sanity_check.py
"""Confirm the discogs head separates 90s-goa from modern-psy (design risk item)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.genre_softmax_of_audio import goa_prob_of_wav

GOA_90S = [ "/run/media/kim/Mantu/ai-music/Goa_Separated/<goa1>/full_mix.flac", ]  # fill 5
MODERN_PSY = [ "/run/media/kim/Mantu/ai-music/Goa_Separated/<psy1>/full_mix.flac", ]  # fill 5

if __name__ == "__main__":
    g = [goa_prob_of_wav(p) for p in GOA_90S]
    m = [goa_prob_of_wav(p) for p in MODERN_PSY]
    print(f"90s-goa goa_prob mean={sum(g)/len(g):.3f}  modern-psy mean={sum(m)/len(m):.3f}")
    assert sum(g)/len(g) > sum(m)/len(m), "discogs head does NOT separate goa from psy — reconsider the genre dim"
    print("[sanity] discogs head separates 90s-goa > modern-psy  OK")
```
Run: `/home/kim/Projects/mir/mir/bin/python /home/kim/Projects/mir/src/tools/genre_sanity_check.py`
Expected: `[sanity] ... OK` (90s-goa mean goa_prob > modern-psy mean). If it fails, the genre dim is noise — flag; the `release_year` dim reduces reliance but confirm before trusting genre.

- [ ] **Step 3: Re-verify the existing onset head after the window-scalar fix (procedural)**

Train a short onset scalar head twice at the good settings — once reading the crop-level `.json` scalar (pre-fix behavior), once with the window-aggregated timeseries (`--scalar-from-timeseries density_ts`, the fix) — and compare control-response correlation:
```bash
cd /home/kim/Projects/SAO/control
SA3_VENV=/home/kim/Projects/SAO/.venv/bin/python ENCODED_DIR=/home/kim/Projects/latents_sa3 STEPS=8100 \
  ./run_control_train.sh onset_prefix_check 7.5e-5 adamw --scalar-field onset_density --random-crop
SA3_VENV=/home/kim/Projects/SAO/.venv/bin/python ENCODED_DIR=/home/kim/Projects/latents_sa3 STEPS=8100 \
  ./run_control_train.sh onset_windowfix_check 7.5e-5 adamw --scalar-field onset_density \
  --scalar-from-timeseries density_ts --random-crop
# score both with the onset control grid
for R in onset_prefix_check onset_windowfix_check; do
  FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE /home/kim/Projects/SAO/.venv/bin/python \
    sa3_control/multi_eval.py "$SAVE_ROOT/$R/riffer_final.pt" \
    --prompts "psytrance" --gains 512 --densities 4,6,8,10,15 --out "$SAVE_ROOT/$R/eval"
done
```
Expected: the windowed-fix run's requested-vs-measured onset correlation is ≥ the pre-fix run's (the fix aligns labels to windows). Record both correlations. Confirm the fix does not regress the onset head (spec risk item).

- [ ] **Step 4: Commit**

```bash
cd /home/kim/Projects/mir && git add src/tools/genre_sanity_check.py && \
git commit -m "test(style-adapter): discogs goa/psy separation sanity + onset window-fix re-verify"
```

---

## Self-Review

**Spec coverage:** Corpus distribution + ≥303 vocab (Task 1) ✓; per-crop genre vec + `other` bucket, no re-encode (Task 2) ✓; FingerprintEncoder generalizing ScalarAttributeEncoder, negligible params (Task 3) ✓; static/stable/volatile granularity + window-scalar alignment fix (Task 4) ✓; 3 variants V-A/V-B/V-C at good settings, EMA+grad-accum+early-stop, crop-frames 512 / control-dim 768 / n-tokens 256, NVMe latents (Tasks 4–5, 7) ✓; v2 telemetry logged-not-consumed (Task 6) ✓; MERT cos_dist_mid + Audiobox CE + genre-softmax-of-output + by-ear, 3-way benchmark then winner bracket (Task 7) ✓; discogs 90s-goa vs modern-psy sanity + onset head re-verify (Task 8) ✓; chroma / contour explicitly out of scope (Global Constraints) ✓.

**Type consistency:** `select_genre_vocab`/`genre_significant_labels` (T1) → `genre_vector_from_probs` (T2) writes `style_genre` → read by `_build_fingerprint` (T4); `fingerprint_in_dim(variant,k)` defined T4, called in T4 test, T5 wiring; `FingerprintEncoder(in_dim, control_dim, n_tokens)` T3 → T5/T7 `build_conditioner`; `window_energy`/`window_onset_density` T4; `EMA` T5; `region_bin`/`is_control_extreme`/`log_coverage` T6; `goa_prob_from_probs`/`goa_prob_of_wav` T7 → T8; `mert_mid_cos_dist` T7. Names are consistent across tasks.

**Placeholders:** the only `<...>` are the concrete corpus track paths in Task 8 (real filesystem paths the engineer fills from the mounted Mantu drive) and the vocab genre labels (emitted by Task 1's scan) — both are data the plan explicitly derives at run time, not undefined code.

Plan complete. Two execution options: **(1) Subagent-Driven** (fresh subagent per task, review between tasks — recommended) or **(2) Inline Execution** (batch with checkpoints). This was a draft-only task, so the plan markdown above is the deliverable; no repo file was written and nothing was implemented.agentId: a9318727e01bb92ff (use SendMessage with to: 'a9318727e01bb92ff' to continue this agent)
<usage>subagent_tokens: 139694
tool_uses: 18
duration_ms: 431398</usage>