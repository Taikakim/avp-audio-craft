#!/usr/bin/env bash
set -euo pipefail

HOST="dh_4txyt6@iad1-shared-b8-25.dreamhost.com"
REMOTE_BASE="/home/dh_4txyt6/aavepyora.online/files/evals"
LOCAL_AAC="$HOME/evals_aac/length_adapter_matrix"
LOCAL_HTML="$HOME/evals_aac/length_adapter_matrix.html"

echo "=== Building Length Adapter Matrix HTML Page ==="
/home/kim/Projects/SAO/.venv/bin/python /home/kim/Projects/SAO/Misc/build_length_adapter_matrix_page.py

echo "=== Running Leak Scan on HTML ==="
if grep -iE '/home/kim|/run/media|/media/kim' "$LOCAL_HTML"; then
    echo "ERROR: Leak detected in $LOCAL_HTML!"
    exit 1
fi
echo "Leak scan clean!"

echo "=== Syncing AAC Audio to DreamHost ==="
rsync -avz --progress "$LOCAL_AAC/" "$HOST:$REMOTE_BASE/length_adapter_matrix/"

echo "=== Uploading HTML Page to DreamHost ==="
scp "$LOCAL_HTML" "$HOST:$REMOTE_BASE/length_adapter_matrix.html"

echo "=== Verifying Live URL ==="
curl -sI "https://aavepyora.online/files/evals/length_adapter_matrix.html" | head -n 5

echo "Publish complete! Live at: https://aavepyora.online/files/evals/length_adapter_matrix.html"
