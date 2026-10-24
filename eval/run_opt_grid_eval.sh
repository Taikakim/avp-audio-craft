#!/usr/bin/env bash
# Owner: WINTERMUTE (created 2026-10-22)
# Last edited: WINTERMUTE 2026-10-22 -- FT=/FT_TAG=/FT_DESC= render the grid on a finetune; render rc captured before $(date)
# Last edited: WINTERMUTE 2026-10-22 -- leak gate ignores the note widget's dataset.ckpt / noteCtx.ckpt JS (false positive)
# Last edited: WINTERMUTE 2026-10-23 -- PAGE_ONLY=1 rebuilds + uploads the page without rendering or scoring (no GPU)
# Last edited: WINTERMUTE 2026-10-23 -- phase C renders all heads (adds AdamW_const, AWc, C1_switch, Muon_b256); page B links to page C
# Last edited: WINTERMUTE 2026-10-24 -- pages D and E list only their own heads (--only-order)
# Last edited: WINTERMUTE 2026-10-24 -- phase E (MuonG / Muon512 / KS512 continued to 40 epochs -> latch_opt_grid_e.html)
# Last edited: WINTERMUTE 2026-10-24 -- page C lists only its own heads too (ONLY=1)
# Last edited: WINTERMUTE 2026-10-24 -- eval/ring_score.py per head after scoring (advisory ring column on the page)
# Last edited: WINTERMUTE 2026-10-24 -- phase EPS (Muon_b64 every epoch, biggoa, extended grid); NOTES/TITLE/INTRO overridable per phase
# Last edited: WINTERMUTE 2026-10-23 -- phase D (soups, MuonG, width-512 Muon / KL-SOAP -> latch_opt_grid_d.html); dim read from the head
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
[ "$PHASE" = B ] && NAMES="$NAMES AEMc_ademamix KSc_klsoap" \
  && INTRO_X=" The wider grid (gains 32 to 4096, requested 1 to 16 onsets/s) for all these heads plus the continuation runs is on latch_opt_grid_c.html.$INTRO_X"
GAINS=128,512,2048,8192; DENS=2,4,6,8,10
# Phase C (2026-10-23, after the listening pass): the wider grid asked for (gains 32-4096, 8192 dropped; 1-16 onsets/s) on the
# reference, the two heads judged interesting, and the continuation runs from eval/run_cont_20261023.sh. Own dirs + page, on the
# UUID drive (Mantu is 98% full).
if [ "$PHASE" = C ]; then
  ONLY=1   # pages D and E share this prefix; without it page C also lists their heads
  C=$R/cont_20261023
  CKPT+=([AEMc_cont_best]=$C/AEMc_cont/$F [AEMc_cont_ep20]=$C/AEMc_cont/latch_sa3_onset_per_beat_ts_ep20.pt
         [KSc075_best]=$C/KSc075/$F [KSc075_ep40]=$C/KSc075/latch_sa3_onset_per_beat_ts_ep40.pt)
  DESC+=([AEMc_cont_best]="AEMc's epoch-28 head + 20 epochs AdEMAMix (fresh state), lr 1e-4, 1-epoch warmup, cosine to 0; best val"
         [AEMc_cont_ep20]="as AEMc_cont_best, last epoch (20)"
         [KSc075_best]="KL-SOAP from scratch at 0.75x lr (2.25e-4), warmup 0.68 epoch, cosine over 40 epochs; best val"
         [KSc075_ep40]="as KSc075_best, last epoch (40)")
  NAMES="Muon_b64 AWcG_adagc AEMc_ademamix AEMc_cont_best AEMc_cont_ep20 KSc_klsoap KSc075_best KSc075_ep40 AdamW_const AWc C1_switch Muon_b256_linlr"
  ORDER="${NAMES// /,}"
  GAINS=32,64,128,512,1024,2048,4096; DENS=1,2,4,6,8,10,12,16
  SRC=/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/sa3_control_runs
  PREFIX=onset_eval_optcmpC${FT:+FT_${FT_TAG}}_; SUB=latch_opt_grid_c${FT:+_$FT_TAG}
  TITLE_X=", wider grid$TITLE_X"
  INTRO_X=" This page is the follow-up after a listening pass: a wider grid (gains 32 to 4096, requested 1 to 16 onsets/s) for every head of the first page, plus AdEMAMix continued for 20 more epochs and KL-SOAP retrained from scratch at 0.75x the learning rate (best and last epoch for both new runs). The first page is latch_opt_grid.html.$INTRO_X"
fi

# Phase D (2026-10-23, second listening pass): weight soups of the heads judged best, AdaGC on the Muon recipe, and width 512
# for Muon and KL-SOAP (eval/run_soups_d512_20261023.sh). Same prefix + drive as phase C, so the Muon / KSc075 references are
# not rendered again; own page latch_opt_grid_d.html. Heads that do not exist yet are left out until a re-run.
if [ "$PHASE" = D ]; then
  ONLY=1
  C=$R/cont_20261023; SP=$R/soups_20261023; N=$R/d512_20261023
  CKPT+=([KSc075_best]=$C/KSc075/$F)
  for s in MK50 MK50_ksc MKA33 bell_KSc075 bell_AEMc_cont bell_MuonG bell_Muon512 bell_KS512; do CKPT[$s]=$SP/$s/$F; done
  for r in MuonG Muon512 KS512; do CKPT[${r}_best]=$N/$r/$F; CKPT[${r}_ep20]=$N/$r/latch_sa3_onset_per_beat_ts_ep20.pt; done
  DESC+=([KSc075_best]="KL-SOAP from scratch at 0.75x lr (2.25e-4), cosine over 40 epochs; best val (reference)"
         [MK50]="soup: 50/50 weight average of Muon_b64 and KSc075_best (same seed-0 start)"
         [MK50_ksc]="soup: 50/50 weight average of Muon_b64 and the first KSc (the one auditioned)"
         [MKA33]="soup: 1/3 each of Muon_b64, KSc075_best and AWcG (AdaGC)"
         [bell_KSc075]="soup: Gaussian-weighted epochs of KSc075 around its best epoch (sigma 5; saved every 5 epochs)"
         [bell_AEMc_cont]="soup: Gaussian-weighted epochs of AEMc_cont around its best epoch (sigma 3; saved every 5 epochs)"
         [bell_MuonG]="soup: Gaussian-weighted epochs of MuonG around its best epoch (sigma 2)"
         [bell_Muon512]="soup: Gaussian-weighted epochs of Muon512 around its best epoch (sigma 2)"
         [bell_KS512]="soup: Gaussian-weighted epochs of KS512 around its best epoch (sigma 2)"
         [MuonG_best]="Muon_b64's recipe + AdaGC per-tensor clip (lambda 1.04), lr 9e-4, 20 epochs; best val"
         [MuonG_ep20]="as MuonG_best, epoch 20"
         [Muon512_best]="Muon_b64's recipe at width 512, lr 9e-4, 20 epochs; best val"
         [Muon512_ep20]="as Muon512_best, epoch 20"
         [KS512_best]="KL-SOAP at width 512, lr 1.82e-4 (KSc075 x0.81), cosine planned over 40 epochs, first 20 trained; best val"
         [KS512_ep20]="as KS512_best, epoch 20")
  NAMES="Muon_b64 KSc075_best MK50 MK50_ksc MKA33 bell_KSc075 bell_AEMc_cont MuonG_best MuonG_ep20 bell_MuonG Muon512_best Muon512_ep20 bell_Muon512 KS512_best KS512_ep20 bell_KS512"
  ORDER="${NAMES// /,}"
  GAINS=32,64,128,512,1024,2048,4096; DENS=1,2,4,6,8,10,12,16
  SRC=/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/sa3_control_runs
  PREFIX=onset_eval_optcmpC${FT:+FT_${FT_TAG}}_; SUB=latch_opt_grid_d${FT:+_$FT_TAG}
  TITLE_X=", soups and width 512$TITLE_X"
  INTRO_X=" This page follows the second listening pass: weight averages (soups) of the heads judged best (Muon with KL-SOAP, plus AdaGC; Gaussian-weighted epochs around a run's best epoch), the Muon recipe with AdaGC added, and Muon and KL-SOAP at width 512 (first 20 epochs; the runs can continue). A soup has no held-out loss of its own. Same grid as latch_opt_grid_c.html.$INTRO_X"
fi

# E (2026-10-24): MuonG / Muon512 / KS512 continued from their epoch-20 resume states to 40 epochs
# (eval/run_cont40_20261024.sh). The 20-epoch bests were copied to *_best_ep1-20.pt first, so page D's heads stay as rendered.
if [ "$PHASE" = E ]; then
  ONLY=1
  C=$R/cont_20261023; SP=$R/soups_20261023; N=$R/d512_20261023
  CKPT+=([KSc075_best]=$C/KSc075/$F)
  NAMES="Muon_b64 KSc075_best"
  for r in MuonG Muon512 KS512; do
    CKPT[${r}_best20]=$N/$r/latch_sa3_onset_per_beat_ts_best_ep1-20.pt; CKPT[${r}_best40]=$N/$r/$F
    CKPT[${r}_ep40]=$N/$r/latch_sa3_onset_per_beat_ts_ep40.pt; CKPT[bell40_$r]=$SP/bell40_$r/$F
    DESC+=([${r}_best20]="$r, best val within the first 20 epochs (as on latch_opt_grid_d.html)"
           [${r}_best40]="$r continued to 40 epochs from its epoch-20 state; best val over all 40 (may still be the epoch-20 best)"
           [${r}_ep40]="$r continued to 40 epochs; epoch 40"
           [bell40_$r]="soup: Gaussian-weighted epochs of $r (40 epochs) around its best epoch (sigma 2)")
    NAMES="$NAMES ${r}_best20"
    # best40 = the live _best.pt, which is still the epoch-20 best until the continuation finishes: list it only after DONE40
    [ -f "$N/$r/DONE40" ] && NAMES="$NAMES ${r}_best40"
    NAMES="$NAMES ${r}_ep40 bell40_$r"
  done
  DESC+=([KSc075_best]="KL-SOAP from scratch at 0.75x lr (2.25e-4), cosine over 40 epochs; best val (reference)")
  ORDER="${NAMES// /,}"
  GAINS=32,64,128,512,1024,2048,4096; DENS=1,2,4,6,8,10,12,16
  SRC=/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/sa3_control_runs
  PREFIX=onset_eval_optcmpC${FT:+FT_${FT_TAG}}_; SUB=latch_opt_grid_e${FT:+_$FT_TAG}
  TITLE_X=", 40 epochs$TITLE_X"
  INTRO_X=" This page continues three runs from latch_opt_grid_d.html from 20 to 40 epochs from their saved training state: the Muon recipe with AdaGC (MuonG), Muon at width 512 and KL-SOAP at width 512. For each: the best head of the first 20 epochs, the best over all 40, epoch 40 and a Gaussian epoch soup. Same grid as pages C and D.$INTRO_X"
fi

# EPS (2026-10-24, listening pass on latch_opt_grid_biggoa.html): every epoch of Muon_b64, retrained with the same recipe and seed
# with every epoch saved (eval/run_eb64_epochs_20261024.sh), to hear where it stops learning (by ear ~ep10-15, while val falls to
# ep27) and where the spectral sound starts. Rendered on the biggoa finetune (call with FT=... FT_TAG=biggoa) on the extended grid
# asked for: gains 64-512 incl. 192/256/384, requested 0.5-16 onsets/s. Own prefix + page.
if [ "$PHASE" = EPS ]; then
  ONLY=1; N=$R/eb64_epochs_20261024/EB64r; NAMES=""
  for e in $(seq 1 40); do
    n=$(printf 'ep%02d' "$e"); CKPT[$n]=$N/latch_sa3_onset_per_beat_ts_ep$e.pt
    DESC[$n]="Muon_b64 (lr 1e-3, Schedule-Free, batch 64) retrained with the same recipe and seed; epoch $e"; NAMES="$NAMES $n"
  done
  NAMES=${NAMES# }; ORDER="${NAMES// /,}"
  GAINS=64,128,192,256,384,512; DENS=0.5,1,2,4,8,16
  SRC=/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/sa3_control_runs
  PREFIX=onset_eval_eb64ep${FT:+FT_${FT_TAG}}_; SUB=latch_eb64_epochs${FT:+_$FT_TAG}
  NOTES="Every epoch of the Muon_b64 onset head (retrained, same recipe and seed): where does it stop learning, and where does the spectral / ringing sound begin?"
  TITLE="LatCH onset head: Muon_b64 epoch by epoch, gain &times; requested density$TITLE_X"
  INTRO="The Muon_b64 onset_per_beat head (width 256, depth 8, batch 64, lr 1e-3, Schedule-Free) retrained with the same recipe, data and seed, with every one of its 40 epochs saved. A listening pass found it already sounding spectral at gain 512 and suspected it learns little after epoch 10-15, while its validation loss kept falling to epoch 27. This page plays every epoch on a finer, lower grid (gains 64 to 512, requested 0.5 to 16 onsets/s) to hear where it stops improving and where the ringing starts.$INTRO_X"
fi

# PAGE_ONLY=1: rebuild + upload the page from what is on disk (e.g. after a new kim_feedback verdict); no render, no scoring, no GPU.
# (Below the phase blocks: until 2026-10-24 phases D and E sat inside this if, so PAGE_ONLY=1 D/E would have built page A.)
if [ -z "${PAGE_ONLY:-}" ]; then
heads=""
for n in $NAMES; do [ -f "${CKPT[$n]}" ] && heads="$heads${heads:+,}$n=${CKPT[$n]}" || echo "eval $PHASE: no checkpoint for $n (not trained), left out"; done
[ -n "$heads" ] || { echo "eval $PHASE: nothing to render"; exit 3; }
"$PY" eval/latch_onset_eval.py "${FTARGS[@]}" --heads "$heads" --prefix "$PREFIX" --out-root "$SRC" --gains "$GAINS" --densities "$DENS" \
    --notes "${NOTES:-Batch-64 optimizer comparison on the LatCH onset_per_beat head (eval/run_adamw_cosine_20261022.sh): does the optimizer change how the head steers, not only its val loss?}"
rc=$?
echo "$(date +%H:%M) render rc=$rc"

# per-head summary row for the page (optimizer, batch, lr, best val) from the checkpoint itself
for n in $NAMES; do
  d="$SRC/$PREFIX$n"; [ -f "$d/run_meta.json" ] || continue
  "$PY" - "$d/run_meta.json" "${CKPT[$n]}" "${DESC[$n]}" "${BATCH[$n]:-64}" "${NOTES:-}" <<'EOF'
import json, sys, torch
p, ck, desc, batch, notes = sys.argv[1:6]
m = json.load(open(p)); c = torch.load(ck, map_location="cpu", weights_only=False)
lr = {"Muon_b256": "4e-3", "AdamW": "3e-4", "Muon_b64": "1e-3", "C1": "1e-4", "AEMc_cont": "1e-4", "KSc075": "2.25e-4",
      "MuonG": "9e-4", "Muon512": "9e-4", "KS512": "1.82e-4", "MK": "soup", "bell_": "soup", "bell40_": "soup", "ep": "1e-3"}
name = m.get("arm", "")
m["summary"] = {"opt": desc, "dim": str(c["state_dict"]["latent_proj.weight"].shape[0]), "depth": "8", "batch": batch,
                "lr": next((v for k, v in lr.items() if name.startswith(k)), "3e-4"), "seed": "0",
                "best_val": f"{c['val_loss']:.4f}" if c.get("val_loss") is not None else ""}
m["purpose"] = notes or ("LatCH onset_per_beat head from the batch-64 optimizer comparison, rendered as an onset gain x density grid: "
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
# advisory ringing score per cell (page column, not part of the gate); skips dirs already scored
for n in $NAMES; do [ -d "$SRC/$PREFIX$n" ] && echo "$SRC/$PREFIX$n"; done | xargs -r "$MIR" eval/ring_score.py --workers 6 2>&1 | tail -3
fi

python3 Misc/build_latch_onset_grid_page.py --prefix "$PREFIX" --src "$SRC" --sub "$SUB" --page "$SUB.html" --order "$ORDER" ${ONLY:+--only-order} \
  --title "${TITLE:-LatCH onset head: which optimizer? gain &times; requested density$TITLE_X}" \
  --intro "${INTRO:-The same LatCH guidance head (onsets per beat, width 256, depth 8, same data and held-out split) trained with different optimizers at batch 64: our Muon setup, plain AdamW with and without a cosine schedule, AdamW with AdaGC gradient clipping, a warm switch from Muon to AdamW late in training, and (when trained) AdEMAMix and KL-SOAP, plus Muon at batch 256. The question: does the optimizer change how the head steers, not only its validation loss?$INTRO_X}" \
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
