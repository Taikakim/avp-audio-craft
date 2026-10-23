#!/usr/bin/env bash
# Owner: WINTERMUTE (created 2026-10-22)
# Last edited: WINTERMUTE 2026-10-22 -- FT=/FT_TAG=/FT_DESC= render the grid on a finetune; render rc captured before $(date)
# Last edited: WINTERMUTE 2026-10-22 -- leak gate ignores the note widget's dataset.ckpt / noteCtx.ckpt JS (false positive)
# Last edited: WINTERMUTE 2026-10-23 -- PAGE_ONLY=1 rebuilds + uploads the page without rendering or scoring (no GPU)
# Onset gain x density grids for the batch-64 optimizer comparison (eval/run_adamw_cosine_20261022.sh), page latch_opt_grid.html.
# Called by that queue while it holds the GPU lock:  bash eval/run_opt_grid_eval.sh A|B
#   A = the Muon / AdamW / batch-256 references + phase A heads (C1, AWc, AWcG); B = adds the phase B heads (AEMc, KSc) that exist.
# Per head: eval/latch_onset_eval.py (prompt "psytrance, 140 bpm", seed 1234, 20 s, 50 steps, cfg 7; gains 128/512/2048/8192 x
# requested 2..10 onsets/s; skips heads already rendered) -> m4a 192k in ~/evals_aac/latch_opt_grid/<head>/ -> DSP + Audiobox
# scores -> Misc/build_latch_onset_grid_page.py (disintegration gate, PQ leg) -> leak gate -> upload page + clips.
set -u
PHASE=${1:-A}
SAO=/home/kim/Projects/SAO
PY=$SAO/.venv/bin/python
MIR=/home/kim/Projects/mir/mir/bin/python
R=/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/sa3_control_runs/film_precision_A_20261017_overflow
F=latch_sa3_onset_per_beat_ts_best.pt
SRC=/run/media/kim/Mantu/sa3_control_runs
PREFIX=onset_eval_optcmp_
SUB=latch_opt_grid
# FT=<DoRA/LoRA ckpt> FT_TAG=<short name> FT_DESC=<one line for the page>: guide that finetune instead of plain medium-base;
# clips go to their own dirs (onset_eval_optcmp_<tag>_<head>) and page (latch_opt_grid_<tag>.html).
FT=${FT:-}; FT_TAG=${FT_TAG:-ft}; FT_DESC=${FT_DESC:-a finetune}
FTARGS=(); TITLE_X=""; INTRO_X=""
if [ -n "$FT" ]; then
  PREFIX=onset_eval_optcmpFT_${FT_TAG}_; SUB=latch_opt_grid_$FT_TAG; FTARGS=(--finetune "$FT")
  TITLE_X=" (on a finetune)"
  INTRO_X=" On this page the heads guide $FT_DESC instead of the plain medium-base model, to see whether a model trained on the same data as the heads follows them differently. Compare with latch_opt_grid.html (same heads, prompt and seed on medium-base)."
fi
STAGE=$HOME/evals_aac
export ROCR_VISIBLE_DEVICES=0 FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_FIND_MODE=2
cd "$SAO" || exit 2

declare -A CKPT=(
  [Muon_b64]=$R/batch_sweep_20261021/EB64/$F
  [AdamW_const]=$R/switch_adamw_20261022/AW64/$F
  [Muon_b256_linlr]=$R/switch_adamw_20261022/EB256L/$F
  [C1_switch]=$R/adamw_cosine_20261022/C1_switch1e-4/$F
  [AWc]=$R/adamw_cosine_20261022/AWc/$F
  [AWcG_adagc]=$R/adamw_cosine_20261022/AWcG/$F
  [AEMc_ademamix]=$R/adamw_cosine_20261022/AEMc/$F
  [KSc_klsoap]=$R/adamw_cosine_20261022/KSc/$F
)
declare -A DESC=(
  [Muon_b64]="Muon (our modular SF-NorMuon + Shampoo), lr 1e-3, Schedule-Free, no decay (reference)"
  [AdamW_const]="AdamW lr 3e-4, constant, no warmup, no averaging"
  [Muon_b256_linlr]="Muon as Muon_b64 at batch 256, lr x4 (linear rule), horizons kept in samples"
  [C1_switch]="Muon_b64's epoch-27 head, then AdamW lr 1e-4, 1-epoch warmup, cosine over 13 epochs"
  [AWc]="AdamW lr 3e-4, warmup 0.68 epoch, cosine to 0 over 40 epochs"
  [AWcG_adagc]="AWc + AdaGC per-tensor gradient clip (lambda 1.04)"
  [AEMc_ademamix]="AdEMAMix (slow EMA 0.999, alpha 5) on AWc's schedule"
  [KSc_klsoap]="KL-SOAP on the hidden matrices, AdamW elsewhere, AWc's schedule"
)
declare -A BATCH=([Muon_b256_linlr]=256)
ORDER="Muon_b64,AdamW_const,AWc,AWcG_adagc,C1_switch,AEMc_ademamix,KSc_klsoap,Muon_b256_linlr"
NAMES="Muon_b64 AdamW_const Muon_b256_linlr C1_switch AWc AWcG_adagc"
[ "$PHASE" = B ] && NAMES="$NAMES AEMc_ademamix KSc_klsoap"
GAINS=128,512,2048,8192; DENS=2,4,6,8,10
# Phase C (2026-10-23, after the listening pass): the wider grid asked for (gains 32-4096, 8192 dropped; 1-16 onsets/s) on the
# reference, the two heads judged interesting, and the continuation runs from eval/run_cont_20261023.sh. Own dirs + page, on the
# UUID drive (Mantu is 98% full).
if [ "$PHASE" = C ]; then
  C=$R/cont_20261023
  CKPT+=([AEMc_cont_best]=$C/AEMc_cont/$F [AEMc_cont_ep20]=$C/AEMc_cont/latch_sa3_onset_per_beat_ts_ep20.pt
         [KSc075_best]=$C/KSc075/$F [KSc075_ep40]=$C/KSc075/latch_sa3_onset_per_beat_ts_ep40.pt)
  DESC+=([AEMc_cont_best]="AEMc's epoch-28 head + 20 epochs AdEMAMix (fresh state), lr 1e-4, 1-epoch warmup, cosine to 0; best val"
         [AEMc_cont_ep20]="as AEMc_cont_best, last epoch (20)"
         [KSc075_best]="KL-SOAP from scratch at 0.75x lr (2.25e-4), warmup 0.68 epoch, cosine over 40 epochs; best val"
         [KSc075_ep40]="as KSc075_best, last epoch (40)")
  NAMES="Muon_b64 AWcG_adagc AEMc_ademamix AEMc_cont_best AEMc_cont_ep20 KSc_klsoap KSc075_best KSc075_ep40"
  ORDER="${NAMES// /,}"
  GAINS=32,64,128,512,1024,2048,4096; DENS=1,2,4,6,8,10,12,16
  SRC=/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/sa3_control_runs
  PREFIX=onset_eval_optcmpC${FT:+FT_${FT_TAG}}_; SUB=latch_opt_grid_c${FT:+_$FT_TAG}
  TITLE_X=", wider grid$TITLE_X"
  INTRO_X=" This page is the follow-up after a listening pass: a wider grid (gains 32 to 4096, requested 1 to 16 onsets/s) for the Muon reference, AdaGC, AdEMAMix continued for 20 more epochs, and KL-SOAP retrained from scratch at 0.75x the learning rate (best and last epoch for both new runs). The first page is latch_opt_grid.html.$INTRO_X"
fi

# PAGE_ONLY=1: rebuild + upload the page from what is on disk (e.g. after a new kim_feedback verdict); no render, no scoring, no GPU.
if [ -z "${PAGE_ONLY:-}" ]; then
heads=""
for n in $NAMES; do [ -f "${CKPT[$n]}" ] && heads="$heads${heads:+,}$n=${CKPT[$n]}" || echo "eval $PHASE: no checkpoint for $n (not trained), left out"; done
[ -n "$heads" ] || { echo "eval $PHASE: nothing to render"; exit 3; }
"$PY" eval/latch_onset_eval.py "${FTARGS[@]}" --heads "$heads" --prefix "$PREFIX" --out-root "$SRC" --gains "$GAINS" --densities "$DENS" \
    --notes "Batch-64 optimizer comparison on the LatCH onset_per_beat head (eval/run_adamw_cosine_20261022.sh): does the optimizer change how the head steers, not only its val loss?"
rc=$?
echo "$(date +%H:%M) render rc=$rc"

# per-head summary row for the page (optimizer, batch, lr, best val) from the checkpoint itself
for n in $NAMES; do
  d="$SRC/$PREFIX$n"; [ -f "$d/run_meta.json" ] || continue
  "$PY" - "$d/run_meta.json" "${CKPT[$n]}" "${DESC[$n]}" "${BATCH[$n]:-64}" <<'EOF'
import json, sys, torch
p, ck, desc, batch = sys.argv[1:5]
m = json.load(open(p)); c = torch.load(ck, map_location="cpu", weights_only=False)
lr = {"Muon_b256": "4e-3", "AdamW": "3e-4", "Muon_b64": "1e-3", "C1": "1e-4", "AEMc_cont": "1e-4", "KSc075": "2.25e-4"}
name = m.get("arm", "")
m["summary"] = {"opt": desc, "dim": "256", "depth": "8", "batch": batch,
                "lr": next((v for k, v in lr.items() if name.startswith(k)), "3e-4"), "seed": "0",
                "best_val": f"{c['val_loss']:.4f}" if c.get("val_loss") is not None else ""}
m["purpose"] = ("LatCH onset_per_beat head from the batch-64 optimizer comparison, rendered as an onset gain x density grid: "
                "does the optimizer change how the head steers (and when it breaks), not only its validation loss?")
json.dump(m, open(p, "w"), indent=2)
EOF
done

mkdir -p "$STAGE/$SUB"
for n in $NAMES; do
  d="$SRC/$PREFIX$n"; [ -d "$d" ] || continue; mkdir -p "$STAGE/$SUB/$n"
  for w in "$d"/*.wav; do o="$STAGE/$SUB/$n/$(basename "$w" .wav).m4a"; [ -f "$o" ] || echo "$w $o"; done
done | xargs -r -P 12 -n 2 sh -c 'ffmpeg -nostdin -y -loglevel error -i "$0" -c:a aac -b:a 192k "$1"'
"$MIR" control/sa3_control/clip_metrics.py --roots "$SUB" --workers 12 2>&1 | tail -1
"$MIR" control/sa3_control/clip_metrics_audiobox.py --roots "$SUB" 2>&1 | tail -1
fi

python3 Misc/build_latch_onset_grid_page.py --prefix "$PREFIX" --src "$SRC" --sub "$SUB" --page "$SUB.html" --order "$ORDER" \
  --title "LatCH onset head: which optimizer? gain &times; requested density$TITLE_X" \
  --intro "The same LatCH guidance head (onsets per beat, width 256, depth 8, same data and held-out split) trained with different optimizers at batch 64: our Muon setup, plain AdamW with and without a cosine schedule, AdamW with AdaGC gradient clipping, a warm switch from Muon to AdamW late in training, and (when trained) AdEMAMix and KL-SOAP, plus Muon at batch 256. The question: does the optimizer change how the head steers, not only its validation loss?$INTRO_X" \
  || { echo "page build failed"; exit 4; }

PAGE="$STAGE/$SUB.html"
# The note widget's own JS uses the property names dataset.ckpt / noteCtx.ckpt; drop those two before scanning so a real
# checkpoint filename still blocks the upload but the widget does not (it blocked both eval A and eval B on 2026-10-22).
if sed -E 's/\b(dataset|noteCtx)\.ckpt\b//g' "$PAGE" \
   | grep -Eiq 'goa[_.[:space:]-]?archive|/home/[a-z]|/run/media/|\bMantu\b|\bLehto\b|\.pt\b|\.ckpt\b'; then
  echo "LEAK GATE: $PAGE mentions a path or checkpoint; not uploaded"; exit 5
fi
eval "$(grep -E '^(KEY|HOST|DEST)=' "$HOME/bin/transcode_evals.sh")"
rsync -az --chmod=D755,F644 -e "ssh -o BatchMode=yes -i $KEY" "$STAGE/$SUB" "$PAGE" "$HOST:$DEST/" >/dev/null 2>&1
rc=$?
echo "$(date +%H:%M) upload rc=$rc -> https://aavepyora.online/files/evals/$SUB.html"
exit $rc
