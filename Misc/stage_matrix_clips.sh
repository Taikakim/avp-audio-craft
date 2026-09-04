#!/usr/bin/env bash
# stage_matrix_clips.sh -- fold newly RENDERED model_matrix clips into the served pool.
# GHOST-NOTE 2026-09-04, Kim: "as new clips come available, add them to the eval page pool."
#
# WHY THIS EXISTS. model_matrix_gen.py writes .m4a into the RENDER dir on the eval drive and
# appends to manifest.jsonl. Every SERVED page instead reads manifest_live.jsonl, which
# Misc/build_model_matrix.py regenerates from ONLY those manifest rows whose .m4a exists in
# STAGING (~/.cache/evals_aac/model_matrix). Nothing automated copies render -> staging, so a
# freshly rendered clip is on disk, in the manifest, and invisible to every page and to the
# evaluator pool. That is not a page bug and it does not surface as an error; the row simply
# never appears. Found 2026-09-04 with manifest_live 2,396 rows and 11,010 clips behind.
#
# Idempotent: copies only what is missing, then rebuilds the board + the evaluator manifest.
# Does NOT publish -- the server is WINTERMUTE's lane (MASTER sec 4).
set -uo pipefail
SRC=${1:-/run/media/kim/Mantu/sa3_lora_runs/model_matrix}
STAGE=$HOME/.cache/evals_aac/model_matrix
SAO=/home/kim/Projects/SAO
mkdir -p "$STAGE"
echo "[stage] source: $SRC"
n=0; copied=0
while IFS= read -r f; do
  n=$((n+1)); b=$(basename "$f")
  [ -f "$STAGE/$b" ] && continue
  cp -f "$f" "$STAGE/$b" && copied=$((copied+1))
  [ $((copied % 500)) -eq 0 ] && echo "[stage] copied $copied ..."
done < <(find "$SRC" -maxdepth 1 -name '*.m4a')
echo "[stage] source clips: $n | newly staged: $copied"
echo "[stage] rebuilding board (manifest_live + model_matrix.html)"
"$SAO/.venv/bin/python" "$SAO/Misc/build_model_matrix.py" || echo "[stage] board build FAILED"
echo "[stage] rebuilding evaluator pool"
"$SAO/.venv/bin/python" "$SAO/eval/build_evaluator_manifest.py" || echo "[stage] evaluator build FAILED"
echo "[stage] manifest_live rows: $(wc -l < "$STAGE/manifest_live.jsonl" 2>/dev/null || echo '?')"
echo "[stage] DONE -- publish is WINTERMUTE's step, not this script's"
