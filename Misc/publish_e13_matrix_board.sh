#!/usr/bin/env bash
# Owner: ANTIGRAVITY <antigravity@aavepyora.online>
# publish_e13_matrix_board.sh — publish staged E13 Matrix exploration board from ~/evals_aac/ to aavepyora.online
# NOTE: Executed strictly by Kim's team per deployment policy ("only my team can publish them").
set -euo pipefail

CONF="$HOME/.config/aavepyora.conf"
if [ ! -f "$CONF" ]; then
    echo "Error: missing $CONF"
    exit 1
fi

KEY=$(grep -E '^KEY=' "$CONF" | cut -d= -f2-)
HOST=$(grep -E '^HOST=' "$CONF" | cut -d= -f2-)
DEST_DIR=$(grep -E '^DEST_DIR=' "$CONF" | cut -d= -f2-)
DEST="${DEST_DIR}/evals"

BOARD_DIR="/home/kim/evals_aac/chroma_e13_matrix"
PAGE_HTML="/home/kim/evals_aac/chroma_e13_matrix.html"
INDEX_HTML="/home/kim/evals_aac/index.html"

if [ ! -d "$BOARD_DIR" ] || [ ! -f "$BOARD_DIR/index.html" ]; then
    echo "Error: Board directory or index.html missing at $BOARD_DIR"
    exit 1
fi

if [ ! -f "$PAGE_HTML" ]; then
    echo "Error: HTML page missing at $PAGE_HTML"
    exit 1
fi

echo "=== Running leak scan on E13 Matrix HTML files ==="
if grep -rnoE '/home/|/run/media|password|token=|[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}' "$BOARD_DIR"/*.html "$PAGE_HTML"; then
    echo "LEAK SCAN FAILED: private local paths, IP addresses, or credentials found. Aborting publish."
    exit 2
fi
echo "Leak scan passed cleanly."

echo "=== Syncing E13 Matrix Assets to https://aavepyora.online/files/evals/chroma_e13_matrix/ ==="
rsync -avz --chmod=F644,D755 -e "ssh -i $KEY -o BatchMode=yes" \
    "$BOARD_DIR/" \
    "$HOST:$DEST/chroma_e13_matrix/"

echo "=== Syncing Standalone HTML Page & Catalog Index ==="
rsync -avz --chmod=F644,D755 -e "ssh -i $KEY -o BatchMode=yes" \
    "$PAGE_HTML" \
    "$INDEX_HTML" \
    "$HOST:$DEST/"

echo "=== PUBLISH COMPLETE ==="
echo "Live URLs:"
echo "  - https://aavepyora.online/files/evals/chroma_e13_matrix.html"
echo "  - https://aavepyora.online/files/evals/chroma_e13_matrix/index.html"
echo "  - https://aavepyora.online/files/evals/index.html"
