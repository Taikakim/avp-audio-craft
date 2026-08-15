<?php
// ratings.php — /files/evals/rate.html's backend (WINTERMUTE, 2026-08-14).
//   POST {type:'enjoyment', model, ckpt, prompt_id, cfg, w, length, file, rating}
//     rating: 1-5 = enjoyment; 0 = "so broken it isn't meaningful to rate" (Kim 2026-08-15),
//     a technical-failure flag, not a real score of zero -- keep it out of any mean/median.
//   POST {type:'ab', question_id, prompt_id, length,
//         model_a, ckpt_a, cfg_a, w_a, file_a, model_b, ckpt_b, cfg_b, w_b, file_b, choice}
//     choice: 'A' | 'B' | 'EVEN' (Kim 2026-08-15, "closely matching ones")
//   GET  ?export=1&key=<TOKEN>   ALL ratings — KIM-ONLY review/rebuild key
//   GET  (anything else)          write_only:true, no data
//
// UNLIKE comment.php: this endpoint's data is explicitly MEANT to be consumed later (the
// hall-of-fame rebuild reads it via the export token) -- it is not a permanent write-only
// vault. What makes it safe to read back is that every field is STRUCTURED and validated
// server-side (an enum, an int 1-5, a filename checked against a fixed pattern) -- never
// free text. No field here can carry an injection payload the way an open comment box could.
//
// Security posture otherwise mirrors comment.php: storage outside the webroot, per-IP rate
// limit, append-only JSONL under LOCK_EX.
//
// NO IP ADDRESS IS EVER PERSISTED (2026-08-15, evaluator.html going public: "I record the
// answers but no IP addresses or any other data" needs to be literally true). ip_hash() is
// used ONLY to name an ephemeral rate-limit touch-file under $RATE -- that file's mtime is
// checked and it is never read back as data, never embedded in a stored record, and gets
// silently overwritten by the next request from the same IP. The salted hash used to exist
// as an 'ip' field on every $rec below; removed outright rather than merely not-shown, since
// a field that's stored is data about the rater regardless of whether it's reversible.
header('Content-Type: application/json; charset=utf-8');
header('X-Content-Type-Options: nosniff');
header('Referrer-Policy: no-referrer');

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

$DATA   = '/home/dh_4txyt6/ratings_data';        // OUTSIDE webroot (aavepyora.online/)
$FILE   = $DATA . '/ratings.jsonl';
$RATE   = $DATA . '/rate';
$SALTF  = $DATA . '/salt';
$TOKENF = $DATA . '/export_token';
$MAX_STR = 200;
// 2026-08-15: was 0.5 -- a round fires up to 7 POSTs now (2 enjoyment + 5 ab, question-cycle
// change), and the client retries on 429 anyway, so this only needs to deter genuine flooding.
$RATE_SECONDS = 0.15;

$QUESTIONS = ['top_end', 'spectral_image', 'production', 'structure', 'interesting'];

if (!is_dir($DATA)) @mkdir($DATA, 0700, true);
if (!is_dir($RATE)) @mkdir($RATE, 0700, true);
if (!is_file($SALTF)) @file_put_contents($SALTF, bin2hex(random_bytes(16)), LOCK_EX);
$salt = trim(@file_get_contents($SALTF));

function ip_hash($salt) {
    $ip = $_SERVER['REMOTE_ADDR'] ?? '0.0.0.0';
    return substr(hash('sha256', $ip . '|' . $salt), 0, 12);
}
// Fixed-length cap + control-char strip, same treatment comment.php gives free text --
// applied here even though these fields are meant to be short identifiers/filenames, since
// the endpoint is public and a client could POST anything directly, bypassing rate.html.
function clean_str($s, $max) {
    $s = substr(trim((string)$s), 0, $max);
    return preg_replace('/[\x00-\x1F]/', '', $s);
}
// Filenames only ever come from the manifest the page reads; constrain to the character set
// the render pipeline actually produces (alnum, ._- ) so a garbage/injected value is rejected
// outright rather than merely truncated.
function valid_file($s) {
    return is_string($s) && $s !== '' && strlen($s) <= 200 && preg_match('/^[A-Za-z0-9._-]+$/', $s);
}
function valid_num($v, $lo, $hi) {
    return is_numeric($v) && $v >= $lo && $v <= $hi;
}

$method = $_SERVER['REQUEST_METHOD'] ?? 'GET';

if ($method === 'GET') {
    if (isset($_GET['export'])) {
        $tok = is_file($TOKENF) ? trim(@file_get_contents($TOKENF)) : '';
        if ($tok === '' || !hash_equals($tok, (string)($_GET['key'] ?? ''))) {
            http_response_code(403); echo json_encode(['error' => 'forbidden']); exit;
        }
        $out = [];
        if (is_file($FILE)) foreach (file($FILE, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) as $ln) {
            $j = json_decode($ln, true); if ($j) $out[] = $j;
        }
        echo json_encode(['ok' => true, 'ratings' => $out]); exit;
    }
    echo json_encode(['ok' => true, 'write_only' => true, 'ratings' => []]); exit;
}

if ($method === 'POST') {
    $raw = file_get_contents('php://input');
    $in = json_decode($raw, true);
    if (!is_array($in)) $in = $_POST;

    $ih = ip_hash($salt);
    $rf = $RATE . '/' . $ih;
    if (is_file($rf) && (microtime(true) - filemtime($rf)) < $RATE_SECONDS) {
        http_response_code(429); echo json_encode(['error' => 'slow down']); exit;
    }

    $type = (string)($in['type'] ?? '');
    $prompt_id = clean_str($in['prompt_id'] ?? '', $MAX_STR);
    $length = clean_str($in['length'] ?? '', 20);
    // Optional page-origin tag (Kim 2026-08-15, evaluator.html going public): lets the
    // export distinguish public-evaluator responses from internal rate.html ones without
    // touching anything the rater sees. Free-text-cleaned, not validated against an enum --
    // an unrecognized value just reads as itself on export, no failure mode either way.
    $source = clean_str($in['source'] ?? '', 40);

    if ($type === 'enjoyment') {
        $model = clean_str($in['model'] ?? '', $MAX_STR);
        $ckpt  = clean_str($in['ckpt'] ?? '', $MAX_STR);
        $file  = (string)($in['file'] ?? '');
        $rating = $in['rating'] ?? null;
        if ($model === '' || $ckpt === '' || $prompt_id === '' || !valid_file($file)
            || !valid_num($in['cfg'] ?? null, 0, 100) || !valid_num($in['w'] ?? null, 0, 100)
            || !in_array($rating, [0, 1, 2, 3, 4, 5], true)) {
            http_response_code(400); echo json_encode(['error' => 'invalid enjoyment payload']); exit;
        }
        $rec = ['ts' => time(), 'iso' => gmdate('c'), 'type' => 'enjoyment',
                'model' => $model, 'ckpt' => $ckpt, 'prompt_id' => $prompt_id,
                'cfg' => (float)$in['cfg'], 'w' => (float)$in['w'], 'length' => $length,
                'file' => $file, 'rating' => (int)$rating, 'source' => $source];
    } elseif ($type === 'ab') {
        global $QUESTIONS;
        $question_id = (string)($in['question_id'] ?? '');
        $choice = (string)($in['choice'] ?? '');
        $model_a = clean_str($in['model_a'] ?? '', $MAX_STR); $ckpt_a = clean_str($in['ckpt_a'] ?? '', $MAX_STR);
        $model_b = clean_str($in['model_b'] ?? '', $MAX_STR); $ckpt_b = clean_str($in['ckpt_b'] ?? '', $MAX_STR);
        $file_a = (string)($in['file_a'] ?? ''); $file_b = (string)($in['file_b'] ?? '');
        if (!in_array($question_id, $QUESTIONS, true) || !in_array($choice, ['A', 'B', 'EVEN'], true)
            || $model_a === '' || $ckpt_a === '' || $model_b === '' || $ckpt_b === '' || $prompt_id === ''
            || !valid_file($file_a) || !valid_file($file_b)
            || !valid_num($in['cfg_a'] ?? null, 0, 100) || !valid_num($in['w_a'] ?? null, 0, 100)
            || !valid_num($in['cfg_b'] ?? null, 0, 100) || !valid_num($in['w_b'] ?? null, 0, 100)) {
            http_response_code(400); echo json_encode(['error' => 'invalid ab payload']); exit;
        }
        $rec = ['ts' => time(), 'iso' => gmdate('c'), 'type' => 'ab',
                'question_id' => $question_id, 'prompt_id' => $prompt_id, 'length' => $length,
                'model_a' => $model_a, 'ckpt_a' => $ckpt_a, 'cfg_a' => (float)$in['cfg_a'], 'w_a' => (float)$in['w_a'], 'file_a' => $file_a,
                'model_b' => $model_b, 'ckpt_b' => $ckpt_b, 'cfg_b' => (float)$in['cfg_b'], 'w_b' => (float)$in['w_b'], 'file_b' => $file_b,
                'choice' => $choice, 'source' => $source];
    } else {
        http_response_code(400); echo json_encode(['error' => 'unknown type']); exit;
    }

    @touch($rf);
    file_put_contents($FILE, json_encode($rec, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE) . "\n",
                      FILE_APPEND | LOCK_EX);
    echo json_encode(['ok' => true]); exit;
}

http_response_code(405); echo json_encode(['error' => 'method not allowed']);
