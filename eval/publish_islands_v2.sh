#!/usr/bin/env bash
set -euo pipefail

HOST="dh_4txyt6@iad1-shared-b8-25.dreamhost.com"
REMOTE_BASE="/home/dh_4txyt6/aavepyora.online/files/evals"
LOCAL_AAC="$HOME/evals_aac/mixtape_trackpool_v3_islands_v2"
LOCAL_HTML="$HOME/evals_aac/mixtape_trackpool_v3_islands_v2.html"

echo "=== Building Mixtape Track Pool V3 Islands V2 HTML Page ==="
/home/kim/Projects/SAO/.venv/bin/python /home/kim/Projects/SAO/Misc/build_mixtape_trackpool_v3_islands_v2_page.py

echo "=== Running Leak Scan on HTML ==="
if grep -iE '/home/kim|/run/media|/media/kim' "$LOCAL_HTML"; then
    echo "ERROR: Leak detected in $LOCAL_HTML!"
    exit 1
fi
echo "Leak scan clean!"

echo "=== Syncing AAC Audio to DreamHost ==="
rsync -avz --progress "$LOCAL_AAC/" "$HOST:$REMOTE_BASE/mixtape_trackpool_v3_islands_v2/"

echo "=== Uploading HTML Page to DreamHost ==="
scp "$LOCAL_HTML" "$HOST:$REMOTE_BASE/mixtape_trackpool_v3_islands_v2.html"

echo "=== Verifying Live URL ==="
curl -sI "https://aavepyora.online/files/evals/mixtape_trackpool_v3_islands_v2.html" | head -n 5

echo "Publish complete! Live at: https://aavepyora.online/files/evals/mixtape_trackpool_v3_islands_v2.html"
