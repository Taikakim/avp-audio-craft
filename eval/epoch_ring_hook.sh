#!/usr/bin/env bash
# Owner: WINTERMUTE (created 2026-10-24)
# Per-epoch ringing check for LatCH onset heads, called by train_latch.py --epoch-hook as: epoch_ring_hook.sh <epoch> <ep ckpt>
# (project call 2026-10-24: render the gain-256 bracket after every epoch, on the finetuned model, and cut bad runs early).
#   1 renders the head at gain 256 x requested 0.5/1/2/4/8/16 onsets/s (+ the unsteered clip) on the finetune
#     (eval/latch_onset_eval.py; prompt/seed/steps as the grid pages) into $SRC/onset_eval_ring256FT_<FT_TAG>_<TAG>_ep<NN>
#   2 eval/ring_score.py on that dir
#   3 exit 3 (stop the run) when a gain-256 cell rings >= 0.5 in this AND the previous epoch at the same requested density
# Exit 4 = out of GPU memory (the trainer offloads its state to the CPU and calls once more); 0 = continue.
# Env: HOOK_TAG (run name, default: the checkpoint's dir name), HOOK_FT / HOOK_FT_TAG (finetune, default the biggoa DoRA),
#      HOOK_RING (0.5), HOOK_GAIN (256), HOOK_DENS (0.5,1,2,4,8,16). Log: <run dir>/epoch_ring.jsonl
set -u
ep=$1; ck=$2
SAO=/home/kim/Projects/SAO
PY=$SAO/.venv/bin/python
MIR=/home/kim/Projects/mir/mir/bin/python
SRC=/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/sa3_control_runs
FT=${HOOK_FT:-/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs/runs/subloss_k24/subloss_k24_biggoa_t512_bf16_s1/epoch=63-step=12480.ckpt}
FT_TAG=${HOOK_FT_TAG:-biggoa}
run=$(dirname "$ck"); TAG=${HOOK_TAG:-$(basename "$run")}
RING=${HOOK_RING:-0.5}; GAIN=${HOOK_GAIN:-256}; DENS=${HOOK_DENS:-0.5,1,2,4,8,16}
PFX=onset_eval_ring256FT_${FT_TAG}_${TAG}_
n=$(printf 'ep%02d' "$ep")
# the trainer's own env may carry training-profile settings; SA3 medium needs these (MASTER: find mode 6 crashes the DiT)
export ROCR_VISIBLE_DEVICES=0 FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_FIND_MODE=2
cd "$SAO" || exit 2

out=$("$PY" eval/latch_onset_eval.py --finetune "$FT" --heads "$n=$ck" --prefix "$PFX" --out-root "$SRC" \
        --gains "$GAIN" --densities "$DENS" \
        --notes "Per-epoch ringing check during training (eval/epoch_ring_hook.sh): gain $GAIN on the finetune; the run stops when a cell rings >= $RING in two consecutive epochs at the same requested density." 2>&1)
rc=$?
if echo "$out" | grep -qiE 'out of memory|OutOfMemory'; then
  echo "[ring-hook] epoch $ep: out of GPU memory while rendering"; exit 4
fi
[ $rc -eq 0 ] || { echo "[ring-hook] epoch $ep: render failed (rc $rc)"; echo "$out" | tail -5; exit 1; }
echo "$out" | grep -E "^  $n g" | cut -c1-160
"$MIR" eval/ring_score.py --workers 6 "$SRC/$PFX$n" | tail -1

"$PY" - "$SRC" "$PFX" "$ep" "$GAIN" "$RING" "$run/epoch_ring.jsonl" <<'EOF'
import json, os, sys
src, pfx, ep, gain, ring, log = sys.argv[1], sys.argv[2], int(sys.argv[3]), float(sys.argv[4]), float(sys.argv[5]), sys.argv[6]
def cells(k):
    p = f"{src}/{pfx}ep{k:02d}/ring_score.json"
    return [c for c in json.load(open(p))["cells"] if c["gain"] == gain] if os.path.exists(p) else []
now = cells(ep)
hot = lambda cs: {c["requested"] for c in cs if c["ring"] >= ring}
both = sorted(hot(cells(ep - 1)) & hot(now)) if ep > 1 else []
rec = {"epoch": ep, "gain": gain, "ring_by_density": {f"{c['requested']:g}": c["ring"] for c in now},
       "ring_hz_by_density": {f"{c['requested']:g}": c["ring_hz"] for c in now}, "threshold": ring,
       "cut": bool(both), "cut_densities": both, "dir": f"{pfx}ep{ep:02d}"}
open(log, "a").write(json.dumps(rec) + "\n")
print(f"[ring-hook] epoch {ep} gain {gain:g}: " + " ".join(f"d{k}={v:.2f}" for k, v in rec["ring_by_density"].items())
      + (f"  -> CUT: >= {ring} in epochs {ep - 1} and {ep} at {', '.join(f'{q:g}' for q in both)}/s" if both else ""), flush=True)
sys.exit(3 if both else 0)
EOF
