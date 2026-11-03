#!/usr/bin/env bash
# Transcode all eval audio -> AAC .m4a @128k (already-compressed clips copied as-is) and upload
# to aavepyora.online/files/evals/<root>/<relpath>. Resumable (skips existing outputs) and
# nice'd so it yields to other instances' CPU jobs. Zero LLM tokens.
set -uo pipefail
STAGE=/home/kim/.cache/evals_aac
KEY=/home/kim/.ssh/id_ed25519
HOST=dh_4txyt6@iad1-shared-b8-25.dreamhost.com
DEST=/home/dh_4txyt6/aavepyora.online/files/evals
mkdir -p "$STAGE"
ssh -o BatchMode=yes -i "$KEY" "$HOST" "mkdir -p $DEST" 2>/dev/null

roots="control_runs:/run/media/kim/Mantu/sa3_control_runs renders:/home/kim/Projects/SAO/stable-audio-3 riffer:/home/kim/riffer-evals"
done=0
for pair in $roots; do
  name="${pair%%:*}"; root="${pair#*:}"; [ -d "$root" ] || continue
  while IFS= read -r src; do
    rel="${src#"$root"/}"; extl="${src##*.}"; extl="${extl,,}"
    case "$extl" in
      m4a|mp3) out="$STAGE/$name/$rel" ;;              # already web-playable: keep as-is
      *)       out="$STAGE/$name/${rel%.*}.m4a" ;;     # wav/flac -> AAC
    esac
    [ -f "$out" ] && { done=$((done+1)); continue; }
    mkdir -p "$(dirname "$out")"
    case "$extl" in
      m4a|mp3) cp -f "$src" "$out" ;;
      *) nice -n15 ffmpeg -nostdin -threads 2 -loglevel error -y -i "$src" -c:a aac -b:a 128k "$out" </dev/null || { rm -f "$out"; continue; } ;;
    esac
    done=$((done+1)); [ $((done % 100)) -eq 0 ] && echo "[evals] $done done"
  done < <(find "$root" -type f \( -iname '*.wav' -o -iname '*.flac' -o -iname '*.mp3' -o -iname '*.m4a' \) 2>/dev/null)
  echo "[evals] uploading $name ..."
  rsync -az --chmod=F644 -e "ssh -o BatchMode=yes -i $KEY" "$STAGE/$name/" "$HOST:$DEST/$name/" 2>&1 | tail -1
done
echo "[evals] DONE: $done files at https://aavepyora.online/files/evals/"
