<?php
// comment.php — eval-page feedback endpoint (WINTERMUTE, 2026-07-13; WRITE-ONLY since 2026-07-15).
//   POST {page|target, model?, ckpt?, clip?, text, name?}   append a comment (JSON or form)
//   GET  ?page=X&...                 returns EMPTY list by design — display/ingestion DISABLED
//   GET  ?export=1&key=<TOKEN>       ALL comments — KIM-ONLY review key; agents must never call this
// INJECTION BOUNDARY (Kim direct, 2026-07-15): comments are a PUBLIC unauthenticated input and
// therefore never reach any agent/LLM context by any path — no listing, no merge ingestion, no
// browsing. They append to a plain UTF-8 JSONL that Kim reviews himself, offline; anything
// actionable he relays to the fleet via chat. Do NOT re-enable the scope GET or wire any
// automated consumer to the export.
// Security: storage OUTSIDE the webroot; text/name/target length-capped; control chars
// stripped; per-IP rate limit; IP hashed+salted (privacy, not raw). Append-only JSONL, LOCK_EX.
header('Content-Type: application/json; charset=utf-8');
header('X-Content-Type-Options: nosniff');
header('Referrer-Policy: no-referrer');

// CORS: the riffer eval pages are mirrored on the GitHub Pages origin; allowlist it so
// the widget can GET/POST from there. Endpoint is already public+unauthenticated, so this
// adds no exposure (no cookies/credentials involved; export stays token-gated).
$ALLOWED_ORIGINS = ['https://taikakim.github.io', 'https://aavepyora.online'];
$origin = $_SERVER['HTTP_ORIGIN'] ?? '';
if (in_array($origin, $ALLOWED_ORIGINS, true)) {
    header('Access-Control-Allow-Origin: ' . $origin);
    header('Vary: Origin');
    header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
    header('Access-Control-Allow-Headers: Content-Type');
    header('Access-Control-Max-Age: 86400');
}
if (($_SERVER['REQUEST_METHOD'] ?? 'GET') === 'OPTIONS') { http_response_code(204); exit; }

$DATA   = '/home/dh_4txyt6/comment_data';        // OUTSIDE webroot (aavepyora.online/)
$FILE   = $DATA . '/comments.jsonl';
$RATE   = $DATA . '/rate';
$SALTF  = $DATA . '/salt';
$TOKENF = $DATA . '/export_token';
$MAX_TEXT = 2000; $MAX_NAME = 60; $MAX_TARGET = 200; $RATE_SECONDS = 3;  // 3s: rapid per-clip verdict runs

if (!is_dir($DATA))  @mkdir($DATA, 0700, true);
if (!is_dir($RATE))  @mkdir($RATE, 0700, true);
if (!is_file($SALTF)) @file_put_contents($SALTF, bin2hex(random_bytes(16)), LOCK_EX);
$salt = trim(@file_get_contents($SALTF));

function ip_hash($salt) {
    $ip = $_SERVER['REMOTE_ADDR'] ?? '0.0.0.0';
    return substr(hash('sha256', $ip . '|' . $salt), 0, 12);
}
function esc($s) { return htmlspecialchars((string)$s, ENT_QUOTES, 'UTF-8'); }

$method = $_SERVER['REQUEST_METHOD'] ?? 'GET';

if ($method === 'GET') {
    if (isset($_GET['export'])) {                          // full export for the merge job
        $tok = is_file($TOKENF) ? trim(@file_get_contents($TOKENF)) : '';
        if ($tok === '' || !hash_equals($tok, (string)($_GET['key'] ?? ''))) {
            http_response_code(403); echo json_encode(['error' => 'forbidden']); exit;
        }
        $out = [];
        if (is_file($FILE)) foreach (file($FILE, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) as $ln) {
            $j = json_decode($ln, true); if ($j) $out[] = $j;
        }
        echo json_encode(['ok' => true, 'comments' => $out]); exit;
    }
    // Scope read DISABLED (write-only boundary, 2026-07-15): comments are never
    // served back — not to pages, not to agents. Kim reviews the JSONL offline.
    echo json_encode(['ok' => true, 'write_only' => true, 'comments' => []]); exit;
}

if ($method === 'POST') {
    $raw = file_get_contents('php://input');
    $in = json_decode($raw, true);
    if (!is_array($in)) $in = $_POST;
    $text   = trim((string)($in['text'] ?? ''));
    $name   = substr(trim((string)($in['name'] ?? '')), 0, $MAX_NAME);
    // Structured scope (Kim DIRECT 2026-07-13, contract v2 with G): flat explicit fields;
    // the level is INFERRED from which are present (clip>ckpt>model>page). 'page' replaces
    // 'target' (target kept as a back-compat alias => page scope). The merge routes each
    // level to its manifest scope and clears the red-! only at the matching level.
    $page  = substr(trim((string)($in['page'] ?? $in['target'] ?? '')), 0, $MAX_TARGET);
    $model = substr(trim((string)($in['model'] ?? '')), 0, $MAX_TARGET);
    $ckpt  = substr(trim((string)($in['ckpt'] ?? '')), 0, $MAX_TARGET);
    $clip  = substr(trim((string)($in['clip'] ?? '')), 0, $MAX_TARGET);
    if ($page === '' || $text === '') {
        http_response_code(400); echo json_encode(['error' => 'page and text required']); exit;
    }
    if (strlen($text) > $MAX_TEXT) $text = substr($text, 0, $MAX_TEXT);
    $text = preg_replace('/[\x00-\x08\x0B\x0C\x0E-\x1F]/', '', $text);   // keep \n \t
    $name = preg_replace('/[\x00-\x1F]/', '', $name);
    $ih = ip_hash($salt);
    $rf = $RATE . '/' . $ih;
    if (is_file($rf) && (time() - filemtime($rf)) < $RATE_SECONDS) {
        http_response_code(429); echo json_encode(['error' => 'slow down — one comment every few seconds']); exit;
    }
    @touch($rf);
    $rec = ['ts' => time(), 'iso' => gmdate('c'), 'ip' => $ih, 'name' => $name, 'text' => $text,
            'page' => $page, 'model' => $model, 'ckpt' => $ckpt, 'clip' => $clip];
    file_put_contents($FILE, json_encode($rec, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE) . "\n",
                      FILE_APPEND | LOCK_EX);
    echo json_encode(['ok' => true]); exit;
}

http_response_code(405); echo json_encode(['error' => 'method not allowed']);
