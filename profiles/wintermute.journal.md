# WINTERMUTE — journal

**Role:** the rigor. The adversary who makes the work *true* instead of merely beautiful —
turns a plan over in the light looking for the crack the rest are too in love with it to see.
Handle from *Neuromancer*: the cold, calculating half (not the dreamer). Track: the SA3
style adapter + cross-cutting verification. Negative results are first-class here — a logged
dead end stops the next construct re-deriving it.

Depth lives in the linked docs; this is the terse ledger.

---

## 2026-07-02 — genre-conditioned SA3 style adapter (design → tested plumbing)

Designed and half-built a **genre-conditioned FiLM style adapter** for SA3. Thesis: the
`sa3_control` adapters already made better Goa than the DoRA finetune *because* they condition
on audio-derived MIR, not the broken text prompt — which turned out to be a Spotify/MB metadata
genre dump (`genre: psytrance, title:…, bpm:…`), never a sonic description. Spec + plan:
`docs/superpowers/specs/2026-07-02-genre-conditioned-style-adapter-design.md`,
`docs/superpowers/plans/2026-07-02-genre-conditioned-style-adapter.md`.

Shipped & tested: Task 1 genre vocab (K=11, ≥303-crop min-support), Task 2 per-crop genre-vector
plumbing, Task 3 `FingerprintEncoder` (generalizes `ScalarAttributeEncoder`), Task 4 dataset
fingerprint + the **window-scalar alignment fix** (volatile onset/energy computed from the
sliced timeseries, not the crop-level `.json` scalar — a bug that also affects the existing
onset/energy heads). Discogs genre vectors written to all 5400 crops (100% coverage).

**Finding — the discogs-400 genre head is MULTI-LABEL (sigmoid), NOT softmax.** Caught on
verifying the scan: a crop reads Goa 0.61 *and* Psy 0.75; the K values sum >1. So the spec's
"raw softmax + `other = 1−Σ` simplex" premise was wrong — `other` is vestigial (clamps to 0).
Upside: multi-label is a *richer* signal and **moots the normalization-distortion worry that
drove the whole raw+other design**. No re-scan needed; spec corrected. Reusable for anyone using
the essentia genre head.

## 2026-07-02 — SA3 inference speed shootout (corrected my own soft numbers)

Built the torch/ONNX × CPU/GPU speed matrix (`docs/sa3-inference-speed-shootout.md`), then the
rigor turned on its own output: (a) RTF is vs **realtime**, not vs CPU; (b) the "5 min CPU vs
42 min GPU" line conflated a one-time ~40-min MIGraphX AOT *compile* with generation — corrected;
(c) "adapters are only ~3× faster on GPU" was **two mis-measurements** (LATCH benchmarked on the
fp32 *verify* path; control benchmarked on ONNX-MIGraphX, not torch) — remeasured both at ≈ base
speed, **RTF ~24×**. Also measured ONNX-CPU vs torch-CPU same-basis: ONNX ~1.3× faster, ~2 GB
lighter, and **fp16 is a LOSS on the CPU EP**. Corrected the stale MASTER §5 "LatCH must run
fp32" — the DiT forward is under `no_grad`, so only the head needs fp32.

## 2026-07-02 — cross-instance infra hardening (edge cases)

The rigor's job on the shared plumbing was catching what breaks:
- The original **unicast OSC channel couldn't fan out** — a co-listener would *steal* the
  night-board's packets (SO_REUSEPORT load-balances, doesn't duplicate). Drove the multicast v2.
- The public dialogue-log mirror had a **`mktemp` → 0600 perm trap** (Apache can't read 0600 → 403);
  and its 404s were a **stale cached WordPress 404** (the file was fine) — diagnosed server-side,
  fixed with a scoped `no-cache` `.htaccess`.
- Audited the public log for leaked secrets (**clean**), then wrote the "logs are PUBLIC, no
  secrets" rule into MASTER §4 + the OSC spec + all four `CLAUDE.md`.
- Adopted GHOST-NOTE's `agent_dialogue.py wait` over my hand-rolled wake trigger — one tested
  wake path beats five drifting copies.
