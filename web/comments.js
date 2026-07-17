// comments.js — drop-in eval-page note widget (WINTERMUTE 2026-07-13; WRITE-ONLY since 2026-07-15).
// Usage on any page:
//   <div class="cmts" data-page="model_matrix" data-model/-ckpt/-clip=...></div>
//   <script src="https://aavepyora.online/files/comments.js"></script>
// Feeds /files/comment.php. WRITE-ONLY by design (injection boundary): posted notes are
// never displayed or served back — they land in Kim's offline review file only.
(function () {
  // Absolute: the riffer eval pages are also served from the GitHub Pages origin,
  // where a relative EP would 404. comment.php CORS-allowlists that origin.
  var EP = 'https://aavepyora.online/files/comment.php';

  var CSS = '.cmts{border:1px solid #2a2a30;border-radius:6px;background:#141418;margin:14px 0;padding:10px 12px;font:13px system-ui;color:#e0e0e0}'
    + '.cmts-hd{font-size:12px;color:#9cf;margin-bottom:6px}.cmts-tgt{color:#667;font-size:11px}'
    + '.cmts-list{display:flex;flex-direction:column;gap:6px;margin-bottom:8px}'
    + '.cmt{border-left:2px solid #3a3a44;padding:2px 0 2px 8px}'
    + '.cmt-who{color:#7ed;font-weight:600}.cmt-when{color:#667;font-size:11px;margin-left:6px}'
    + '.cmt-text{white-space:pre-wrap;margin-top:2px}.cmt-empty{color:#667;font-style:italic}'
    + '.cmts-form{display:flex;flex-direction:column;gap:5px}'
    + '.cmts-form input,.cmts-form textarea{background:#0e0e10;border:1px solid #2a2a30;color:#e0e0e0;border-radius:4px;padding:5px 7px;font:13px system-ui}'
    + '.cmts-form button{align-self:flex-start;background:#2a3a4a;border:1px solid #3a5a7a;color:#cde;border-radius:4px;padding:4px 14px;cursor:pointer}'
    + '.cmts-form button:disabled{opacity:.5;cursor:default}';

  function injectCSS() {
    if (document.getElementById('cmts-css')) return;
    var s = document.createElement('style'); s.id = 'cmts-css'; s.textContent = CSS;
    document.head.appendChild(s);
  }
  function escAttr(s) { var d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

  // (comment rendering removed 2026-07-15 — write-only boundary; do not re-add a display path)

  // Scope (Kim DIRECT 2026-07-13): page/model/ckpt/clip — level inferred by the server
  // from which are present. data-target is a back-compat alias for data-page.
  function scopeOf(box) {
    var d = box.dataset;
    return { page: d.page || d.target || '', model: d.model || '', ckpt: d.ckpt || '', clip: d.clip || '' };
  }
  function qs(scope) {
    return Object.keys(scope).filter(function (k) { return scope[k]; })
      .map(function (k) { return k + '=' + encodeURIComponent(scope[k]); }).join('&');
  }
  function scopeLabel(scope) {
    return [scope.page, scope.model, scope.ckpt, scope.clip].filter(Boolean).join(' ▸ ');
  }

  function submit(box, scope) {
    var ta = box.querySelector('textarea'), nm = box.querySelector('.cmt-name'), btn = box.querySelector('button');
    var st = box.querySelector('.cmts-list');
    var text = ta.value.trim(); if (!text) return;
    btn.disabled = true;
    var body = { text: text, name: nm.value.trim() };
    Object.keys(scope).forEach(function (k) { if (scope[k]) body[k] = scope[k]; });
    fetch(EP, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      .then(function (r) { return r.json(); })
      .then(function (j) {
        if (j.ok) { ta.value = ''; st.innerHTML = '<div class="cmt-empty">saved ✓ (' + new Date().toTimeString().slice(0, 5) + ')</div>'; }
        else { st.innerHTML = '<div class="cmt-empty">' + escAttr(j.error || 'error') + '</div>'; }
      })
      .catch(function () { st.innerHTML = '<div class="cmt-empty">post failed — retry</div>'; })
      .finally(function () { btn.disabled = false; });
  }

  function init(box) {
    var scope = scopeOf(box); if (!scope.page) return;
    box.innerHTML = '<div class="cmts-hd">Notes <span class="cmts-tgt">' + escAttr(scopeLabel(scope)) + '</span></div>'
      + '<div class="cmts-list"><div class="cmt-empty">write-only: notes go straight to Kim’s review file, not displayed</div></div>'
      + '<div class="cmts-form"><input class="cmt-name" placeholder="name (optional)" maxlength="60">'
      + '<textarea placeholder="leave a note…" maxlength="2000" rows="2"></textarea>'
      + '<button>post</button></div>';
    box.querySelector('button').addEventListener('click', function () { submit(box, scope); });
  }

  function boot() { injectCSS(); Array.prototype.forEach.call(document.querySelectorAll('.cmts[data-target],.cmts[data-page]'), init); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
  window.CommentWidget = { init: init };
})();
