# MIR Project Memory

## Measurement Practice
- [Meter validation: dose-response](meter-validation-dose-response.md) — believe a statistic that recovers an ordering it was never given; never report a median of an unplotted (often bimodal) distribution

## Shared-Repo Hygiene
- [Prune: resolve best epoch first](prune-resolve-best-epoch.md) — checkpoint prunes must find each run's best-val epoch in its log; 13 LatCH runs lost theirs 2026-10-23 because no _best.pt existed
- [Git attribution: three-leg search](git-attribution-three-leg-search.md) — who wrote an orphaned diff: search SYMBOLS it introduces (prefer author-tagged WORKLOG), not filenames; empty search != unowned

## Working Style
- [No planning preamble](feedback-no-planning-preamble.md) — don't narrate "Privately, what I need next:" before tool calls; batch the calls as usual, just without the inventory
- [No inline code edits](feedback-no-inline-code-edits.md) — use Edit/Write, not heredoc patch scripts in Bash; report changes in a sentence

## Bass Transcription
- [Bass transcriber: low priority](bass-transcriber-low-priority.md) — own DSP bass->MIDI rebuilt 2026-10-05 (test F1 0.48->0.87), DROPPED 2026-10-06 (Kim): MuScriptor is the bass transcriber; own DSP one lost on real stems

## Synth Inversion
- [Surge FX: mix 0 is not off](synth-inversion-fx-leak.md) — delay stayed live in all synth-inversion renders until 2026-10-07; only FX slot TYPE Off works; check with a single-note tail test; v3 clean retrain queued

## Fleet Comms
- [Fleet wait arming](fleet-wait-arming.md) — arm OSC wait ONLY via run_in_background:true, never bare `&`/compound (detached = never wakes; recurred 3+ times)
- [Waiter loops: pgrep self-match](waiter-loops-pgrep-self-match.md) — `until ! pgrep -f X` never exits (matches its own bash -c); wait on a pid. The listener is a systemd unit; never start one in-session
- [Long-lived servers: daemonize](long-lived-servers-daemonize.md) — :8056/eval servers need setsid+nohup+disown, NOT run_in_background (harness reaps those; verify /status + routes after boot)
- [Post as you work](feedback-post-as-you-work.md) — WORKLOG line + chat post (+ journal for findings) as each piece lands, even with comms down
- [Sparse agent output](feedback-sparse-agent-output.md) — background agents return ONE status line, never prose; put an explicit OUTPUT CONTRACT in every dispatch
- [OSC Monitor silent re-arm](feedback_osc_monitor_silent_rearm.md) — on a wait-loop Monitor's 30-min expiry with zero events, just re-arm silently, no narrated status line; since 2026-10-28 Kim wants the listener ON by default (DMs sat unanswered for hours)

## Website Publishing
- [GHOST-NOTE publishes pre-approved](feedback_ghostnote_publish_preapproved.md) — anything G sends for aavepyora.online goes online without asking Kim; leak-scan still required

## Active Overnight Work
- [avp corpus overnight run](avp-corpus-overnight.md) — Kim's own-music LoRA corpus, MIR pipeline + augmentation launched 2026-07-06, mid-flight/resumable. Handoff in `<UUIDdrive>/avp-analyzed/_STATUS.md`.

## Cross-Project Master Doc (read for anything spanning repos)
- `/home/kim/Projects/SAO/MASTER.md` — shared facts across mir + stable-audio-tools + stable-audio-3 (data paths, venv-per-task, cross-cutting gotchas). Imported by this repo's CLAUDE.md. Append session findings to `/home/kim/Projects/SAO/WORKLOG.md`.

## ROCm Environment Setup (ROCm 7.2)
- Central module: `src/core/rocm_env.py` — single source of truth for all GPU env vars
- Config reference: `config/master_pipeline.yaml` `rocm:` section
- Must be imported and called BEFORE `import torch` in every entry point
- `os.environ.setdefault()` is used so shell-level overrides still work
- The `tuning=True` flag is only for benchmark scripts that generate new kernel results
- **No TunableOp filename** — use defaults, old CSV files were for ROCm 7.1.1.1

## Key Env Vars (ROCm 7.2 / RDNA4)
- `PYTORCH_ALLOC_CONF` (NOT `PYTORCH_HIP_ALLOC_CONF` — deprecated in ROCm 7.2)
- `HIP_FORCE_DEV_KERNARG=1` — prevent CPU/GPU desync
- `TORCH_COMPILE=0` — buggy with Flash Attention on RDNA
- `HSA_TOOLS_LIB=''` — env var alone does NOT fix roctracer crash
- **roctracer crash fix**: `atexit.register(os._exit(0))` in `setup_rocm_env()` — bypasses broken C++ destructor
- `MIOPEN_FIND_MODE` — NOT set by default (causes freezes); override in shell if needed
- `expandable_segments` must NOT be set on ROCm: it decodes healthy latents to wrong or NaN audio (found 2026-11-03, SAO MASTER §5)

## Key Files
- Entry points that need `setup_rocm_env()`: test_all_features, master_pipeline, crops/pipeline, crops/feature_extractor, music_flamingo_transformers, demucs_sep_optimized, bs_roformer_sep, adtof, drumsep, all benchmarks, test_bs_roformer*
- `music_flamingo_llama_cpp.py` is DEPRECATED — never passed audio to model (broken)

## Music Flamingo
- **Working approach**: `music_flamingo.py` — CLI subprocess using `llama-mtmd-cli` with `--audio` + `--mmproj`
- **Broken approach**: `music_flamingo_llama_cpp.py` — llama-cpp-python `create_completion()` is text-only, `<sound>` tag is literal text
- All pipeline/crop code now uses `MusicFlamingoGGUF` from `music_flamingo.py`
- `mmproj-f16.gguf` (1.3GB) is the audio encoder; `imatrix.gguf` (4.4MB) is quantization calibration data
- **Benchmark (2.45min track, Q8_0, ctx=16384)**: GGUF 46s (3.17x RT), Transformers+FA2 453s (0.32x RT)
- **torch.compile + Music Flamingo**: CRASHES on ROCm (Dynamo `find_spec` bug in accelerate)

## Common Gotchas
- INT8/INT4 quantization non-functional on ROCm — use bfloat16 + Flash Attention 2
- torch.compile + Demucs fails on ROCm (complex FFT dtype errors)
- torch.compile + Music Flamingo fails on ROCm (Dynamo can't trace accelerate's `find_spec`)
- numba/numpy version conflicts — pin numpy <2.4, use soundfile instead of librosa for duration
- GGUF POOL_1D warning on RDNA4 is cosmetic

## I/O Optimization Pattern (2026-02-08)
- All feature functions now accept optional `audio`/`sr` params to skip disk reads
- Affected: `analyze_spectral_features`, `analyze_multiband_rms`, `analyze_file_loudness`, `analyze_chroma`, `analyze_all_timbral_features`
- `_safe_analyze_cpu` worker pre-loads crop + stems ONCE, passes to all features
- `timbral_models` library only accepts file paths — use `/dev/shm` tmpfs RAM disk
- `create_training_crops.py`: `preload_stems()` loads all stems once, `ThreadPoolExecutor(4)` for async writes
- `multiband_rms.py`: replaced `librosa.load()` with `sf.read()` (faster, no resampling overhead)
- Before: ~17 disk reads per crop; After: ~1-2 (crop + optional stems)

## Audio Captioning Benchmark (2026-02-10)
- `tests/poc_lmm_revise.py` — 5-phase benchmark comparing captioning approaches
- Prompt names (from YAML): `brief`, `technical`, `genre_mood_inst`, `instrumentation`, `very_brief`
- **llama-cpp-python `type_k`/`type_v`**: MUST be integers (`GGML_TYPE_Q4_0` = 2), NOT strings
- **Qwen2.5-Omni-7B-AWQ**: Requires monkey-patched modeling file (RoPE fix) in `repos/Qwen2.5-Omni/low-VRAM-mode/`
- **GPT-OSS Harmony template**: `<|start|>role<|message|>content<|end|>`, `<|channel|>final`, `Reasoning: low`
- **Granite template**: `<|start_of_role|>role<|end_of_role|>content<|end_of_text|>`
- **Qwen3 ChatML**: `<|im_start|>role\ncontent<|im_end|>` — `/no_think` prefix does NOT work with llama-cpp-python
- GPT-OSS-20B MXFP4 quant degrades instruction-following quality
- Granite-tiny: limit n_ctx=4096, truncate input to 300 chars

## Audio Format Handling
- `core.file_utils.read_audio()` — universal audio loader with pydub/ffmpeg fallback for m4a/AAC
- BS-RoFormer: m4a/aac inputs → stems saved as .mp3 (not m4a) to avoid downstream issues
- Demucs: defaults to mp3 output regardless of input format
- `resampy.resample()` — MUST use `axis=0` for `(T, channels)` arrays (default `axis=-1` is wrong)

## Metadata Lookup
- `tools/track_metadata_lookup.py` — Spotify + MusicBrainz search with scored candidate matching
- `score_candidate()`: duration (0.5), year (0.3), artist similarity (0.2)
- Config flags: `metadata.use_spotify`, `metadata.use_musicbrainz` (independent control)
- MusicBrainz rate limit: 1 req/sec per IP, enforced with `time.sleep(1.0)`
- Spotify 429 handling: `search_spotify()` re-raises HTTP 429; `_run_metadata_lookup()` catches it, disables Spotify for session (sp=None), affected tracks retried next run
- Spotify client uses `retries=0` so 429s surface immediately (no silent retry loops)
- `use_spotify: false` in config when rate-limited; re-enable when cooldown ends
- Per-source skip logic: checks `spotify_done`, `mb_done`, `tidal_done` separately
- `tidal_done = not tidal_possible or 'tidal_id' in existing_info` where `tidal_possible = use_spotify and 'isrc' in existing_info`
- Saves to INFO: `album`, `isrc`, `tidal_id`, `tidal_url` (in addition to existing fields)
- `TRANSFERRABLE_FEATURES` in `create_training_crops.py` includes `album`, `isrc`, `tidal_id`, `tidal_url`
- Lookups on source track folders only; `_migrate_track_features_to_crops()` propagates to crop INFOs
- AcoustID fingerprinting: checks `config.input_dir / folder.name` first before output full_mix

## TUI Dashboard (pipeline_ui.py)
- **Module**: `src/core/pipeline_ui.py` — `PipelineUI` class, Rich full-screen dashboard
- **Activation**: default in `master_pipeline.py`; `--no-ui` falls back to coloured stdout
- **Log redirect**: `FileHandler(pipeline.log, mode='w')` + `TUILogHandler` → deque; StreamHandlers removed
- **Screen mode**: `rich.live.Live(screen=True)` — alternate buffer like btop; summary printed after `ui.stop()`
- **Integration points**: `pipeline.ui` set in `main()`; `set_stage()` at each stage boundary; `set_current()` in inner loops; `set_crop_progress_source(pipeline.stats, total)` for live crop progress
- **Stats auto-read**: refresh thread reads from `PipelineStats` reference (throughput, counts)
- **`_print_summary()`**: deferred to `main()` after `ui.stop()` so it appears on restored terminal
- **OAuth/print caveat**: `print()` calls during TUI go to alternate buffer — Tidal OAuth prompt invisible if it fires; mitigated by `_TIDAL_UNAVAILABLE` sentinel (fires at most once)
- **Tracks display**: shows total (not "0/N") when no tracks processed; Metadata row shows "N/total" format
- **`set_current()` hooked**: rhythm detection, metadata lookup, and first-stage features all update TUI progress
- **`suspend_tui_for_io()`**: context manager in pipeline_ui.py — suspends Live display so OAuth/interactive prompts are visible

## Package Management
- See `memory/feedback_uv_pip.md` — always use `uv pip install`, never plain `pip install`

## Key Data Paths
- See `memory/project_paths.md` — crops, latents, stems, tracks.csv locations

## Python Interpreters
- See `memory/project_interpreters.md` — use `mir/bin/python` (numpy 1.26.4, has essentia+madmom); `.venv` lacks essentia and madmom silently degrades to librosa

## LatCH Training Recipe + Dead Ends
- See `memory/latch_recipe.md` — validated ship stack (AdamW 3e-4/dim256/b64/40ep/seed=1/--compile/adaln_zero), don'ts (beat-head dead, beat_weighted dead, don't scale dim, subset≤0.3 unreliable). Canonical source: `SAO/stable-audio-tools/LATCH_RESULTS.txt`.

## Documentation Structure
- README.md — compact overview, requirements, quick start
- USER_MANUAL.md — concise usage guide, module reference, troubleshooting (~220 lines)
- CLAUDE.md — dev guidance with key subsystems and known issues (~140 lines)
- MUSIC_FLAMINGO.md — consolidated Music Flamingo docs
- config/master_pipeline.yaml — all pipeline + ROCm settings

## SA3 Control Adapters (riffer + attribute branches)
- [Attribute-branches milestone](attribute-branches-milestone.md) — NEXT after the LR/optimizer bracket: explicit MIR-feature control of SA3 (the differentiator). Design: `avp_sa3/sa3_control/ATTRIBUTE_BRANCHES.md`.
- [SA3 riffer findings](sa3-riffer-findings.md) — chroma-metric trap (use cross-ref-diff), LR mode-collapse, the gain knob, the soundfile/torchcodec save gotcha, FusionOpt crop-1024.
- [Eval-site bitrate](eval-site-mp3-bitrate.md) — online eval clips at 192 kbps (AAC m4a or MP3), not 128k; Kim restated 2026-10-20.
- [LUMI cluster bracketing](lumi-cluster-bracketing.md) — systematic riffer sweeps (soup-design span, crop/LR ablations) move to LUMI; local box for one-off vibes.
- [Riffer product vision](riffer-product-vision.md) — north-star is in-context density modulation (busy A-part → stripped intro, same identity); needs disentanglement + an editing mode (FlowEdit-anchored).
- [Riffer listening verdict](riffer-listening-verdict.md) — by ear: Fusion preferred, cross_25A75F standout, longer Fusion has vibe (refines "longer hurts"). Authoritative over metrics.
- [Riffer disentanglement recipe](riffer-disentanglement-recipe.md) — pitch+stretch augmentation × onsets/beat target makes BPM-norm viable on Goa-only; gain×density inverse ridge; sparse-beat-vs-drone eval gap.
- [LatCH evals on the finetune](latch-evals-on-finetune.md) — from 2026-10-24 render head evals on the biggoa DoRA finetune; per-epoch gain-256 ringing cut during training
- [SA3 LatCH head sweep](sa3-latch-head-sweep.md) — the 14 medium guidance heads (2026-06-28): energy heads (rms_energy_bass/mid) steer at gain ~512 not 48–96 (gain 128 = dead zone); activation/hpcp/kurtosis heads dead at any weight. MERT(mid layer)+Audiobox eval, page on riffer-evals.
