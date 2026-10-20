#!/bin/bash
# Owner: WINTERMUTE (created 2026-10-20)
# publish_synth_inv_v6_1.sh -- puts ANTIGRAVITY's V6.1 synth-inversion audition pages (real-stem consensus, arms occam / lexi4k /
# decay4k) online. Waits until the decay4k page exists and the ANTIGRAVITY GPU lock is gone (step 6 of run_v6_1_pipeline.sh rewrites
# all three index pages last), converts each arm's WAVs to 128k AAC, points the page at the .m4a files, leak-scans, writes a small
# landing page and rsyncs to the eval site under evals/synth_inv_v6_1/.
#   setsid nohup bash eval/publish_synth_inv_v6_1.sh > <scratch>/publish_v6_1.log 2>&1 < /dev/null &
set -u
SRC=/home/kim/sao_runs
OUT=$HOME/evals_aac/synth_inv_v6_1
DEST_FILE=/tmp/claude-1000/-home-kim-Projects-mir/b207d8c1-afa9-47b8-bbe0-60db9d0c4899/scratchpad/dest
ARMS="dpo_occam:occam lexi4k:lexi4k decay4k:decay4k"
until [ -f "$SRC/stems_v6_c_decay4k/listen/index.html" ] && ! grep -qs "^ANTIGRAVITY" /tmp/gpu.lock; do sleep 60; done
sleep 120   # let the last page writes settle
echo "$(date +%H:%M) pipeline done; converting"
mkdir -p "$OUT"
for a in $ARMS; do
  src=$SRC/stems_v6_c_${a%%:*}/listen; dst=$OUT/${a##*:}
  mkdir -p "$dst"
  for w in "$src"/*.wav; do
    m=$dst/$(basename "${w%.wav}").m4a
    [ -s "$m" ] || ffmpeg -nostdin -loglevel error -y -i "$w" -c:a aac -b:a 128k "$m"
  done
  sed 's/\.wav"/.m4a"/g' "$src/index.html" > "$dst/index.html"
  echo "$(date +%H:%M) ${a##*:}: $(ls "$dst"/*.m4a | wc -l) clips"
done
cat > "$OUT/index.html" <<'EOF'
<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Synth Inversion V6.1</title>
<style>:root{--bg:#fafafa;--fg:#222;--link:#0b5cad}@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#16181b;--fg:#ddd;--link:#7ab8ff}}
:root[data-theme="dark"]{--bg:#16181b;--fg:#ddd;--link:#7ab8ff}body{background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,sans-serif;max-width:720px;margin:0 auto;padding:16px}a{color:var(--link)}</style></head>
<body><h1>Synth inversion V6.1: real-stem consensus</h1>
<p>Surge XT patch inversion on 24 real stems: the real phrase, then the inverted patch from S5, S5 + Flow-DPO (beta 300), V6_C and V6_C + Flow-DPO (beta 100/300). Three arms of the selection rule:</p>
<ul><li><a href="occam/index.html">Base (Occam)</a></li><li><a href="lexi4k/index.html">Lexi 4k</a></li><li><a href="decay4k/index.html">Decay 4k</a></li></ul>
</body></html>
EOF
if grep -rnoE '/home/|/run/media|\.ckpt|\.safetensors|\.pt"|[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}|password|token=' "$OUT"/*.html "$OUT"/*/index.html; then
  echo "$(date +%H:%M) LEAK SCAN HIT: not publishing"; exit 3
fi
[ -f "$DEST_FILE" ] && rsync -a "$OUT" "$(cat "$DEST_FILE")" && echo "$(date +%H:%M) published evals/synth_inv_v6_1/"
echo "$(date +%H:%M) ALL DONE"
