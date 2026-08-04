#!/bin/bash
# headb_bracket_eval.sh — Head B melody-conditioning BRACKET eval.
# DESIGN: CONTINUITY 2026-07-24. TO BE RUN BY GHOST-NOTE when the GPU frees (Kim's routing).
# Spec: docs/superpowers/specs/2026-07-22-melodic-latch-film.md §2/§8.
#
# WHAT: every Head B checkpoint PAST step 5280 (epochs ~9-15 + final) × the bracket
#   cfg{1,7,16} × gain{1.0,1.5} = 6 settings/ckpt. Per cell: 4 motif-conditioned renders
#   + null floor, muscriptor transcription, adoption-vs-null + disintegration-gate analysis.
#   Adoption > null floor with clean gates (per-cell, NEVER pooled) = conditioning took;
#   cfg1 = melody-dominant anchor, cfg16 = does conditioning survive the M2 averaging.
# BASE-PT COMPARISON: the final ckpt also gets a no-adapter baseline (base/pt-medium, same
#   prompt+seeds+cfg, NO melody stream) — see the BASE-PT block at the bottom (G's pt-medium
#   render path; this script prints the exact spec, does not itself render base-pt).
# OUTPUT: eval drive (MASTER §4: NEVER the SAO tree). Resumable (harness skips existing wavs).
#
# DOCTRINE (MASTER §5): rc on its OWN line ($(date) clobbers $?); artifact-count checks, never
#   trust rc; measured free-VRAM gate (not pgrep); canonical absolute lock path; pid-aware lock
#   with the script's own long-lived $$.
#
# CRASH-CHECK FIRST: the LOCAL pilot TRAIN crashed with ROCm heap corruption (free(): chunks in
#   smallbin corrupted, rc=134). Rendering is forward-only so it should be fine, but this script
#   renders ONE cell first and ABORTS with a reroute message if local inference is also broken —
#   in which case the eval moves to a LUMI render job (do NOT keep retrying locally).
set -u
cd /home/kim/Projects/SAO
VENV=/home/kim/Projects/SAO/.venv/bin/python
LOCK=/home/kim/Projects/SAO/.gpu.lock
HANDLE=${HEADB_HANDLE:-GHOST-NOTE-headb}
CKDIR=/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs/runs/headb_melody
EVALROOT=/run/media/kim/Mantu/sa3_control_runs/headb_bracket_2026-07-24
LOG=$EVALROOT/bracket.log
CKPTS="riffer_step5940 riffer_step6600 riffer_step7260 riffer_step7920 riffer_step8580 riffer_step9240 riffer_step9900 riffer_final"
CFGS="1 7 16"
GAINS="1.0 1.5"
mkdir -p "$EVALROOT"

export FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_FIND_MODE=2
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4

# --- ckpts present? ---
for ck in $CKPTS; do
  [ -f "$CKDIR/${ck}.pt" ] || { echo "FATAL: missing $CKDIR/${ck}.pt (pull incomplete?)"; exit 1; }
done

# --- GPU lock (pid-aware, this script's $$) ---
echo "=== $(date -Is) bracket start (pid $$); acquiring $LOCK ===" | tee -a "$LOG"
python3 Misc/filelock.py acquire "$LOCK" --handle "$HANDLE" --pid-aware --pid $$ --timeout 28800 >> "$LOG" 2>&1
rc=$?
[ $rc -eq 0 ] || { echo "LOCK-FAIL rc=$rc" | tee -a "$LOG"; exit 3; }

release_lock () { python3 Misc/filelock.py release "$LOCK" --handle "$HANDLE" >> "$LOG" 2>&1; }

# --- VRAM guard: >9 GiB free, 3 consecutive 20s polls (max 6h) ---
vram_free_gib () {
  rocm-smi --showmeminfo vram --json 2>/dev/null | python3 -c '
import json,sys
d=json.load(sys.stdin)["card0"]
print((int(d["VRAM Total Memory (B)"])-int(d["VRAM Total Used Memory (B)"]))/2**30)'
}
ok=0; polls=0; f=0
while [ $ok -lt 3 ] && [ $polls -lt 1080 ]; do
  f=$(vram_free_gib || echo 0)
  if python3 -c "exit(0 if float('$f')>9.0 else 1)"; then ok=$((ok+1)); else ok=0; fi
  polls=$((polls+1)); sleep 20
done
[ $ok -ge 3 ] || { echo "VRAM-GUARD-FAIL last=$f GiB" | tee -a "$LOG"; release_lock; exit 5; }
echo "=== $(date -Is) VRAM guard passed (free ${f} GiB) ===" | tee -a "$LOG"

# --- CRASH-CHECK: one cell (final, cfg7, g1) ---
CC=$EVALROOT/_crashcheck
HEADB_OUT=$CC HEADB_CFG=7 HEADB_GAIN=1.0 "$VENV" control/sa3_control/melody_pilot_eval.py render \
  --ckpt "$CKDIR/riffer_final.pt" >> "$LOG" 2>&1
rc=$?
n_cc=$(ls "$CC/renders"/*.wav 2>/dev/null | wc -l)
if [ $rc -ne 0 ] || [ "$n_cc" -lt 1 ]; then
  echo "CRASH-CHECK FAILED (rc=$rc, wavs=$n_cc) — local inference broken like the train crash." | tee -a "$LOG"
  echo "REROUTE: run this eval on LUMI (headb render job); do NOT keep retrying locally." | tee -a "$LOG"
  release_lock; exit 4
fi
echo "=== $(date -Is) crash-check OK ($n_cc wavs) — local inference works, running bracket ===" | tee -a "$LOG"

# --- MAIN BRACKET: render + transcribe each (ckpt × cfg × gain) cell ---
for ck in $CKPTS; do
  for c in $CFGS; do for g in $GAINS; do
    OUT=$EVALROOT/${ck}_cfg${c}_g${g}
    HEADB_OUT=$OUT HEADB_CFG=$c HEADB_GAIN=$g "$VENV" control/sa3_control/melody_pilot_eval.py render \
      --ckpt "$CKDIR/${ck}.pt" >> "$LOG" 2>&1
    rc=$?
    n=$(ls "$OUT/renders"/*.wav 2>/dev/null | wc -l)
    [ $rc -eq 0 ] && [ "$n" -ge 8 ] || echo "RENDER-WARN $ck cfg$c g$g rc=$rc wavs=$n" | tee -a "$LOG"
    # muscriptor transcription of this cell (GPU; resumable via .mid cache). Paths MUST be
    # hook_scores.jsonl / hook_scores_midi — that is exactly where `analyze` looks (it reads
    # the .mid from OUT/hook_scores_midi for the rendered contour; wrong dir => zero adoption).
    "$VENV" eval/hook_eval_renders.py --wavs "$OUT/renders/*.wav" --out "$OUT/hook_scores.jsonl" \
      --midi-dir "$OUT/hook_scores_midi" --bpm 143 >> "$LOG" 2>&1
    echo "[cell $ck cfg$c g$g] wavs=$n mids=$(ls "$OUT/hook_scores_midi"/*.mid 2>/dev/null | wc -l)" | tee -a "$LOG"
  done; done
done
release_lock
echo "=== $(date -Is) GPU phase done; lock released ===" | tee -a "$LOG"

# --- ANALYZE (CPU) each cell: adoption vs null + disintegration gate (never pooled) ---
for ck in $CKPTS; do
  for c in $CFGS; do for g in $GAINS; do
    OUT=$EVALROOT/${ck}_cfg${c}_g${g}
    HEADB_OUT=$OUT "$VENV" control/sa3_control/melody_pilot_eval.py analyze >> "$LOG" 2>&1
  done; done
done

# --- AGGREGATE -> master table (ckpt × setting → adoption, null-floor, gate-clean) ---
# analyze writes OUT/results.json = list of per-CLIP rows. Conditioned clips carry adopt_*;
# null clips carry null_<motif>_* (the empirical floor). Summarize per CELL, never pooling
# across cells (board-rep rule): conditioned adopt_moving mean vs the null-floor mean, and
# the fraction of conditioned clips whose disintegration gate is clean.
"$VENV" - "$EVALROOT" <<'PYEOF' | tee -a "$LOG"
import json, sys, glob, os
root = sys.argv[1]
def mean(xs):
    xs = [x for x in xs if isinstance(x, (int, float))]
    return round(sum(xs) / len(xs), 3) if xs else None
print(f"\n[headb-bracket] master table (per-cell; NEVER pooled across cells)")
print(f"{'cell':38} | adopt_mv | null_mv | gate_clean | n_cond")
for d in sorted(glob.glob(os.path.join(root, "riffer_*_cfg*_g*"))):
    rj = os.path.join(d, "results.json")
    if not os.path.exists(rj):
        continue
    try:
        rows = json.load(open(rj))
    except Exception:
        continue
    cond = [r for r in rows if r.get("adopt_all") is not None]              # conditioned clips
    null = [r for r in rows if r.get("adopt_all") is None]                  # null-floor clips
    adopt_mv = mean([r.get("adopt_moving") for r in cond])                  # own-stream, moving frames
    null_mv = mean([r.get(f"null_{t}_moving") for r in null                 # floor: null vs every motif
                    for t in ("pedal4", "descrun", "oct_osc", "m3_osc")])
    gclean = (round(sum(1 for r in cond if r.get("gate") == "clean") / len(cond), 2)
              if cond else None)
    print(f"{os.path.basename(d):38} | {str(adopt_mv):8} | {str(null_mv):7} | {str(gclean):10} | {len(cond)}")
print("[headb-bracket] read each cell's results.json for the full per-motif/per-clip table.")
PYEOF
echo "=== $(date -Is) bracket eval DONE -> $EVALROOT ===" | tee -a "$LOG"

# ============================ BASE-PT COMPARISON (final ckpt) ============================
# Kim 2026-07-24: render a NO-ADAPTER baseline for the FINAL ckpt to A/B against the melody-
# conditioned renders — does the melody adapter produce different / more-melodic output than
# the underlying model at the same settings? G owns the pt-medium render path (model_matrix_gen);
# render with:
#   model = base pt-medium (NO melody adapter, NO control)
#   prompt = the harness PROMPT ("psychedelic goa trance, hypnotic melodic acid lead line,
#            driving rolling bassline, 143 BPM"); duration 47.554s (T=512); steps 24;
#   seeds = 1111,2222,3333,4444; cfg = 1, 7, 16 (gain N/A, no adapter)
#   -> $EVALROOT/basept_final_cfg{1,7,16}/renders/*.wav  (+ z0, per standing directive)
# Then transcribe (eval/hook_eval_renders.py, bpm 143) and compare hook_melodic_ratio vs the
# final-ckpt conditioned cells: the melody-gap thesis predicts conditioned hmr > base-pt hmr.
echo "[base-pt] render the final-ckpt no-adapter baseline separately (see BASE-PT block in this script)." | tee -a "$LOG"
