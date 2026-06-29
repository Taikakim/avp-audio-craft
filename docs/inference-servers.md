# CPU eval / inference servers — reference

Practical how-to for the **all-CPU** SA3 eval/inference servers, for any Claude
instance (or human) that needs to render eval clips without touching the GPU.
Everything below is verified against the scripts in
`stable-audio-3/scripts/`. Cross-context: `MASTER.md` §5 (ONNX/CPU-eval gotchas),
`stable-audio-3/docs/onnx-amd-inference.md` (the ONNX export pipeline).

There are **two file-drop queue servers** (control-adapter, LatCH-guidance), **one
GPU/MIGraphX HTTP server** (plain text→audio), and **one torch-CPU CLI harness**
(DoRA). Pick by what you're evaluating:

| You want to eval/render… | Use | Path | Transport |
|---|---|---|---|
| a **control adapter** (FiLM scalar → onset/density steering) | `control_eval_server.py` + `submit_control_job.py` | ONNX, **CPU EP** | file-drop queue `SAO/control_eval_queue` |
| a **LatCH guidance head** (gradient steering of a frozen DiT) | `latch_eval_server.py` + `submit_latch_job.py` | ONNX DiT (CPU) + torch head autograd | file-drop queue `SAO/latch_eval_queue` |
| **plain text→audio**, low-VRAM on the GPU | `latent_server_dit_onnx.py` | ONNX, **MIGraphX GPU EP** | HTTP (`/generate`) |
| a **DoRA finetune** of the base model | `eval_dora_cpu.py` (+ `eval_dora_quality.py`) | **torch-CPU** (weight edit, NOT ONNX) | CLI, not a server |

**Venv for all of them:** `/home/kim/Projects/SAO/stable-audio-3/.venv/bin/python`
(the SA3 venv; py 3.13, torch 2.10 ROCm). Exception: the DoRA *quality scorer*
`eval_dora_quality.py` runs in the **mir venv** `/home/kim/Projects/mir/mir/bin/python`
(needs Audiobox + MERT). The two **submitters** are stdlib-only and run in *any*
python.

---

## The CPU device gotcha (applies to all CPU servers + the DoRA harness)

These run on CPU but the GPU **must stay visible**:

- Load the model on CPU: `StableAudioModel.from_pretrained(device="cpu",
  model_half=False)` (via `make_text_cond.load_conditioner` in the servers). The
  1.4 B-param T5-Gemma conditioner stays on CPU → no VRAM spike, coexists with a
  training job on the card.
- **Do NOT set `HIP_VISIBLE_DEVICES=""`.** `flash_attn`/`aiter` probes a Triton
  driver at *import* time; with zero visible devices it crashes. The servers just
  never *allocate* on the GPU. (`eval_dora_cpu.py` additionally sets
  `SA3_DISABLE_FLASH_ATTN=1` to force the math-SDPA path, which is CPU-safe.)
- The ONNX servers run `providers=["CPUExecutionProvider"]` — MIGraphX being absent
  in the SA3 venv is **expected**, CPU is the target. (`MASTER.md` §5.)

Why CPU is the *default* for evals, not a fallback: the CPU EP has **no AOT compile**,
so a server boots in ~16 s and an 8-step control job is ~20 s. The GPU/MIGraphX path
pays a **~13–18 min AOT compile per session** (per `MASTER.md` §5 measurements) and
ORT 1.23.2 exposes **no compile cache** (the `migraphx_save/load_compiled_model`
options are rejected → silent CPU fallback). So GPU only wins for a resident VST;
for evals, CPU frees the card for training. Thread tip: `--threads 12` (physical
cores; ~25% faster than 24 SMT on the 9900X).

---

## 1. Control-adapter eval server (`control_eval_server.py`)

**What it evals:** a trained **control adapter** baked into the control-DiT ONNX
graph (decoupled cross-attn per block + scalar FiLM conditioner). It compiles the
control-DiT + SAME decoder ONNX once on the CPU EP, loads the resident T5-Gemma text
conditioner and the scalar FiLM `.cond.npz`, then renders one clip per job at a
requested `onset_density` (or whatever scalar field the export was trained for —
`field` is read from the `.cond.npz`). z0 is bit-exact with `dit_control_onnx_infer.py`
for the same seed (shared core `sa3_control_onnx.py`).

**Start it:**
```bash
cd /home/kim/Projects/SAO/stable-audio-3
.venv/bin/python scripts/control_eval_server.py \
    --dit-onnx   dit_medium-base_L256_ctrl_onset_density_fp16.onnx \
    --cond-npz   dit_medium-base_L256_ctrl_onset_density.cond.npz \
    --decoder-onnx same_decoder_L128_fp16.onnx \
    --threads 12
# optional: --queue-root <dir> (default /home/kim/Projects/SAO/control_eval_queue)
#           --model medium-base  --poll 1.0  --decode-chunk 128 --decode-overlap 16
```
The server touches `<queue-root>/.server_ready` once sessions + conditioner are
resident. **Frames (length rung) are read from the DiT graph's `x` input** and are
authoritative — a job that names a different `frames` is rejected, not mis-rendered.

**Submit a job** (stdlib-only, any python):
```bash
python scripts/submit_control_job.py \
    --prompt "goa trance, 145 bpm" --onset-density 11 --gain 3 --steps 8
# also: --cfg 6.0 --seed 42 --frames <T> --out-name <name> --queue-root <dir> --timeout 600
```

**Job JSON** (`inbox/<job_id>.job.json`): required `job_id`, `prompt`,
`onset_density`; optional `steps` (8), `cfg_scale` (6.0), `seed` (42), `gain` (1.0),
`frames`, `out_name`.

**Result JSON** (`outbox/<job_id>.result.json`): `job_id`, `prompt`, `onset_target`,
`gain`, `steps`, `cfg_scale`, `seed`, `frames`, `seconds`, `active_ep`, `timings`
(`dit_loop_s` / `decode_s` / `total_s`), `paths` (`wav`, `result`). The wav lands at
`outbox/<out_name or job_id>.wav`.

Per-prompt T5-Gemma cond/uncond is cached across jobs sharing a prompt.

---

## 2. LatCH-guidance eval server (`latch_eval_server.py`)

**What it evals:** a **LatCH guidance head** steering the *plain* (unmodified) SA3
DiT ONNX. The DiT runs forward-only on the CPU EP (numpy/ORT); guidance is applied
by **torch autograd through the tiny ~5–7 M-param head only** (the head never enters
the ONNX graph, the DiT needs no autograd → CPU-feasible). Sampler is the validated
two-stage variance+mean Selective-TFG core (`sa3_latch_onnx.generate_z0_latch_guided`).
Each job renders **a lo + a hi clip per prompt** (the steering contrast).

**Start it:**
```bash
cd /home/kim/Projects/SAO/stable-audio-3
.venv/bin/python scripts/latch_eval_server.py \
    --dit-onnx     dit_medium-base_L256.onnx \
    --decoder-onnx same_decoder_L128.onnx \
    --threads 12
# default --queue-root /home/kim/Projects/SAO/latch_eval_queue
```
Loaded heads are LRU-cached (max 8) keyed by checkpoint path.

**Submit a job:**
```bash
python scripts/submit_latch_job.py \
    --head-ckpt latch_weights_sa3_medium/latch_sa3_spectral_skewness_best.pt \
    --feature spectral_skewness --target-low -2 --target-high 6 \
    --gain 64 --prompts "psytrance, 140 bpm" --steps 30
# repeat --prompts for multiple prompts (NO comma-splitting — commas are kept verbatim)
```

**Job JSON:** required `job_id`, `head_ckpt`, `feature`, `target_low`,
`target_high`, `prompts` (str or list); optional `gain` (64), `seed` (777), `steps`
(30), `cfg` (7), `gamma` (0.3), `n_iter` (4), `start_pct` (0.4), `end_pct` (1.0),
`frames`. **Gain caveat:** the `64` default is conservative — the operating gain for
the energy heads is **≈512** (NOT 48–96, NOT 128; `MASTER.md` §5 + the head-sweep
memo). Activation/hpcp/kurtosis heads are dead at any gain.

**Result JSON:** `job_id`, `feature`, `head_ckpt`, `head_metadata`, the sampler
params, `frames`/`seconds`/`active_ep`, a `clips[]` list (per clip: `prompt`,
`prompt_idx`, `tag` lo/hi, `target_raw`, `target_std`, `gain`, `wav`, `timings`),
and `timings.total_s`. Wavs: `outbox/<job_id>_<feature>_<p_idx>_<tag>.wav`.

---

## Queue & concurrency semantics — THE precise answer

Both file-drop servers share the same mechanism. **Verified against the code:**

**Queue layout** (`<queue-root>/`): `inbox/` (jobs dropped here), `processing/`
(claimed), `outbox/` (`<name>.wav`, `<job_id>.result.json`, `<job_id>.done`,
`<job_id>.err`), and `.server_ready`.

**1. Submission is atomic.** `submit()` writes `inbox/<job_id>.job.json.tmp` then
`os.replace(tmp, inbox/<job_id>.job.json)` — an atomic rename on the same
filesystem, so the server never claims a half-written job. Job IDs are unique without
uuid (`<timestamp>_<pid ^ time_ns ^ counter, 6 hex>`), so **concurrent submitters
from different processes don't collide**, and the timestamp lead makes name-sort ==
FIFO.

**2. The server claims atomically (rename = the lock).** `claim_next_job()` sorts
`inbox/*.job.json` (FIFO) and tries `os.rename(src, processing/name)` on the oldest.
The rename **is** the atomic lock: if anyone else grabbed it first, the loser gets
`FileNotFoundError` and moves to the next candidate. So **exactly one claimer per job
file** — no double-processing.

**3. One resident worker, jobs run SERIALLY.** Each server is a single `while True`
loop: claim → render → publish → `unlink` the processing file → next. There is **no
threading/multiprocessing of jobs**. So when several instances submit at the same
time, their jobs **queue up and run one at a time in FIFO order** — they do *not*
execute in parallel within one server. The atomic claim only guarantees correctness,
not parallelism.

**4. Two server instances on the same queue = SAFE, and actually parallelize.**
Nothing in the code prevents starting two servers on one `queue-root`; the atomic
rename guarantees each job is claimed by exactly one of them (the other gets
`FileNotFoundError`), and unique job IDs mean output files never collide. So two
servers safely double throughput — at the cost of two resident model copies in RAM.
(The design *intent* is one server; safety comes purely from the atomic rename, not
from any singleton lock.)

**5. Results are published atomically; `.done` is the sentinel.** The wav and
`result.json` are written to `.tmp` siblings, `os.replace`'d into place, and **only
then** is `<job_id>.done` touched (errors: `<job_id>.err` via tmp+replace too). A
submitter that sees `.done` is **guaranteed both artifacts are complete**.

**6. How a submitter waits.** After dropping the job it first blocks on
`.server_ready` (`wait_for_server_ready`), then polls `outbox/` every 0.5 s for
`<job_id>.done` (→ returns the parsed `result.json`) or `<job_id>.err` (→ raises with
the traceback), until `--timeout` (control default 600 s, latch default 1800 s).

**Caveat / known race-free-but-imperfect edge:** there is **no lease/heartbeat**. If
a server is killed *mid-job*, that job's file is left orphaned in `processing/` (the
`finally: unlink` only runs after the job completes or its exception is caught) and is
**not** re-scanned from `inbox/` → the submitter times out. Recovery is manual (move
the file back to `inbox/`). The claim rename itself is atomic only on a single
POSIX filesystem (don't put a `queue-root` on NFS expecting atomic rename).

---

## 3. GPU sibling (for context): `latent_server_dit_onnx.py`

Low-VRAM **text→audio generation** over ONNX + **MIGraphX (AMD GPU)** — the
generative sibling of the CPU servers. **HTTP**, not a file-drop queue:
`/generate?cond=<npz>&uncond=<npz>` runs the ONNX DiT rectified-flow sampler + ONNX
decoder. Text→embeddings is precached offline by `precache_dit_cond.py` (so the
server is torch-free at runtime). Runs in the **mir venv** (`onnxruntime_migraphx`;
the SA3 venv's ORT is CPU-only). AOT-compiles DiT + decoder once at boot
(~min each; pass **fp16-exported** onnx for co-residency on 16 GB — NOT the
`migraphx_fp16_enable` EP option, which OOMs). LatCH gradient guidance is **N/A**
here (needs torch backprop through the DiT). Use this for low-VRAM resident
generation; use the CPU servers for evals.

---

## 4. DoRA eval — torch-CPU CLI, NOT a queued ONNX server

DoRA is a **weight edit** (`W' = magnitude · V/‖V‖_row`, `V = W + (α/r)·BA`), not a
forward-only cross-attn add, so the control-adapter ONNX graph **cannot** be reused.
The DoRA path is therefore plain **torch-CPU** and a **CLI**, not a server — the
contrast with the queued ONNX servers above.

**Render (torch-CPU, SA3 venv):** `eval_dora_cpu.py` loads base medium-base on CPU
(fp32, flash-attn off), attaches the DoRA adapter via `model.load_lora()` (the
validated `LoRAParametrization` forward — never a hand-merge), then renders 3 fixed
prompts × seed 1234 per checkpoint → `<tag>__p<i>_seed<seed>.wav`. Same CPU device
gotcha (no `HIP_VISIBLE_DEVICES=""`).
```bash
cd /home/kim/Projects/SAO/stable-audio-3
VENV=.venv/bin/python
# one checkpoint:
$VENV scripts/eval_dora_cpu.py --ckpt <run>/checkpoints/epoch=9-step=50.ckpt --out-dir renders_dora/ep9
# loop a run (skips rendered; --watch to poll):
$VENV scripts/eval_dora_cpu.py --run-dir <run> --out-dir renders_dora --watch
# base sanity:
$VENV scripts/eval_dora_cpu.py --base --out-dir renders_dora/base
```

**Score (mir venv):** `eval_dora_quality.py` scores a render dir on Audiobox
Aesthetics (CE/PQ/PC/CU, single-file mode — batch OOMs WavLM @16 GB) and **MERT
distance-to-Goa** (Fréchet + cosine to the Goa centroid, mid layers 3–6; upper layer
23 secondary). Goa reference embeddings cached to disk. `--dry-run` validates
paths/loaders without the GPU.
```bash
MV=/home/kim/Projects/mir/mir/bin/python
$MV scripts/eval_dora_quality.py --render-dir renders_dora --dry-run   # no GPU
$MV scripts/eval_dora_quality.py --render-dir renders_dora             # real scoring
```
