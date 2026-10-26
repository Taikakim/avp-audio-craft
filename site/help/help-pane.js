// Owner: WINTERMUTE (created 2026-10-26)
// help-pane.js: docked help pane for glossary terms (spec 2026-10-26-help-pane-design.md, section 6).
// Plain ES module, no dependencies. Reads <script type="module" data-glossary data-viz-base> (contract C3),
// fetches glossary.json (C4) once, and loads animation modules (C5) on demand.
// It stores nothing (no localStorage, cookies, IndexedDB) and sends nothing except those two kinds of fetch.
// If glossary.json cannot be loaded, or this script throws, no click handler exists and the links keep
// navigating to glossary.html: reading is never blocked.

const PHONE_QUERY = '(max-width: 700px)';
const SEEN = 'gl-seen';
const isPhone = () => window.matchMedia(PHONE_QUERY).matches;

function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  return n;
}

// markup comes from glossary.json, which the build has already rendered and leak-scanned (C4)
function rich(tag, cls, markup) {
  const n = el(tag, cls);
  n.innerHTML = markup;
  return n;
}

function btn(cls, label) {
  const b = el('button', cls, label);
  b.type = 'button';
  return b;
}

class HelpPane {
  constructor(entries, vizBase) {
    this.entries = entries;
    this.vizBase = vizBase;
    this.trail = [];          // [{id, mode: 'entry' | 'quiz', quiz: null | {...}}], this visit only, in memory
    this.isOpen = false;
    this.lastTrigger = null;  // the page link that opened the pane, so closing can return focus to it
    this.token = 0;           // bumped on every render and close; stale async viz loads compare against it
    this.viz = null;          // {handle, wrap} of the mounted animation
    this.overlay = null;      // the enlarge overlay, if open
    this.seen = new Set();    // terms opened during this visit
  }

  top() { return this.trail[this.trail.length - 1] || null; }

  has(id) { return Object.prototype.hasOwnProperty.call(this.entries, id); }

  install() {
    const pane = (this.pane = el('aside', 'hp-pane'));
    pane.id = 'help-pane';
    pane.hidden = true;
    pane.setAttribute('aria-labelledby', 'hp-title');

    this.head = el('div', 'hp-head');
    const grip = el('span', 'hp-grip');
    grip.setAttribute('aria-hidden', 'true');
    this.backBtn = btn('hp-back', 'Back');
    this.backBtn.setAttribute('aria-label', 'Back to the previous term');
    this.backBtn.disabled = true;
    this.titleEl = el('h2', 'hp-title');
    this.titleEl.id = 'hp-title';
    this.titleEl.tabIndex = -1;
    this.closeBtn = btn('hp-close', 'Close');
    this.closeBtn.setAttribute('aria-label', 'Close help');
    this.head.append(grip, this.backBtn, this.titleEl, this.closeBtn);

    this.bodyEl = el('div', 'hp-body');
    this.live = el('div', 'hp-live');
    this.live.setAttribute('role', 'status');
    this.live.setAttribute('aria-live', 'polite');
    pane.append(this.head, this.bodyEl, this.live);

    this.reopenBtn = btn('hp-reopen', 'Reopen help');
    this.reopenBtn.hidden = true;
    document.body.append(pane, this.reopenBtn);

    this.backBtn.addEventListener('click', () => this.back());
    this.closeBtn.addEventListener('click', () => this.close());
    this.reopenBtn.addEventListener('click', () => this.reopen());
    document.addEventListener('click', (e) => this.onDocClick(e));
    document.addEventListener('keydown', (e) => this.onKey(e));
    window.addEventListener('hashchange', () => this.openFromHash(false));
    this.installSwipe();
    this.openFromHash(true);
  }

  // ---- events -------------------------------------------------------------------------------------------

  onDocClick(e) {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    const a = e.target instanceof Element ? e.target.closest('a.gl') : null;
    if (!a) return;
    const id = a.dataset.term || (a.hash || '').replace(/^#/, '');
    if (!this.has(id)) return;          // unknown term: let the link navigate to glossary.html
    e.preventDefault();
    this.open(id, a);
  }

  onKey(e) {
    if (e.key !== 'Escape' || e.defaultPrevented) return;
    if (this.overlay) { e.preventDefault(); this.closeOverlay(true); return; }
    if (this.isOpen) { e.preventDefault(); this.close(); }
  }

  // ---- opening, closing, history -------------------------------------------------------------------------

  open(id, trigger) {
    if (!this.has(id)) return false;
    const fromPage = trigger && !this.pane.contains(trigger);
    if (fromPage) this.lastTrigger = trigger;
    const t = this.top();
    if (!(t && t.id === id && t.mode === 'entry')) this.trail.push({ id, mode: 'entry', quiz: null });
    this.show();
    if (fromPage) this.revealTrigger(trigger);
    return true;
  }

  show() {
    this.isOpen = true;
    this.pane.hidden = false;
    document.body.classList.add('help-pane-open');
    this.reopenBtn.hidden = true;
    this.render();
    this.syncHash();
    this.titleEl.focus({ preventScroll: true });
  }

  reopen() {
    if (this.top()) this.show();
  }

  close() {
    if (!this.isOpen) return;
    this.closeOverlay(false);
    this.destroyViz();
    this.token++;                       // abandon any animation still loading
    this.isOpen = false;
    this.pane.hidden = true;
    this.pane.style.transform = '';
    this.pane.style.transition = '';
    document.body.classList.remove('help-pane-open');
    this.reopenBtn.hidden = !this.trail.length;
    this.syncHash();
    const t = this.lastTrigger;
    if (t && t.isConnected) t.focus({ preventScroll: true });
    else if (!this.reopenBtn.hidden) this.reopenBtn.focus({ preventScroll: true });
  }

  back() {
    if (this.trail.length <= 1) return;
    this.trail.pop();
    this.render();
    this.syncHash();
    this.titleEl.focus({ preventScroll: true });
  }

  // ---- rendering -----------------------------------------------------------------------------------------

  render() {
    this.token++;
    this.closeOverlay(false);
    this.destroyViz();
    const item = this.top();
    if (!item) return;
    const entry = this.entries[item.id];
    this.titleEl.textContent = entry.term;
    this.backBtn.disabled = this.trail.length <= 1;
    this.bodyEl.replaceChildren();
    if (item.mode === 'quiz') this.renderQuiz(entry, item);
    else this.renderEntry(entry);
    this.bodyEl.scrollTop = 0;
    this.markSeen(item.id);
  }

  markSeen(id) {
    this.seen.add(id);
    document.querySelectorAll('a.gl').forEach((a) => {
      if (this.seen.has(a.dataset.term)) a.classList.add(SEEN);
    });
  }

  // STUB: Task 2.3 replaces this with the full three-layer layout.
  renderEntry(entry) {
    this.bodyEl.append(rich('p', 'hp-plain', entry.plain));
  }

  // STUB: Task 2.4 replaces this.
  renderQuiz() {}

  // STUB: Task 2.3 replaces this.
  closeOverlay() {}

  // STUB: Task 2.5 replaces this.
  installSwipe() {}

  destroyViz() {
    const v = this.viz;
    this.viz = null;
    if (!v) return;
    try {
      if (v.handle && typeof v.handle.destroy === 'function') v.handle.destroy();
    } catch (err) { /* a broken destroy() must not block navigation */ }
  }

  helpApi() {
    const cs = getComputedStyle(document.documentElement);
    const v = (name, fallback) => cs.getPropertyValue(name).trim() || fallback;
    return {
      colors: {
        accent: v('--edge', '#0f9e99'),
        fg: v('--ink', '#2b3538'),
        muted: v('--dim', '#7a8a8e'),
        bg: v('--paper', '#fafaf7'),
        good: v('--hp-good', '#2e7d4f'),
        bad: v('--hp-bad', '#b3412e'),
      },
      openTerm: (id) => { this.open(id, null); },
      reducedMotion: window.matchMedia('(prefers-reduced-motion: reduce)').matches,
    };
  }

  // ---- address bar ---------------------------------------------------------------------------------------

  syncHash() {
    const t = this.top();
    const want = this.isOpen && t ? '#gl=' + encodeURIComponent(t.id) : '';
    if (!want && !location.hash.startsWith('#gl=')) return;   // never wipe someone else's anchor
    if (location.hash === want) return;
    history.replaceState(history.state, '', location.pathname + location.search + want);
  }

  openFromHash() {
    const m = /^#gl=(.+)$/.exec(location.hash);
    if (!m) return;
    let id;
    try { id = decodeURIComponent(m[1]); } catch (err) { return; }
    if (!this.has(id)) return;
    const t = this.top();
    if (this.isOpen && t && t.id === id) return;
    this.open(id, null);
  }

  // Keep the clicked term in view: beside the docked pane it may have moved; above a bottom sheet it may be
  // hidden underneath it.
  revealTrigger(a) {
    requestAnimationFrame(() => {
      if (!a.isConnected) return;
      const r = a.getBoundingClientRect();
      if (isPhone()) {
        const limit = window.innerHeight * 0.3;      // the sheet covers the lower 70%
        if (r.bottom > limit || r.top < 0) {
          window.scrollBy({ top: r.top - window.innerHeight * 0.08, behavior: 'instant' });
        }
      } else if (r.top < 0 || r.bottom > window.innerHeight) {
        a.scrollIntoView({ block: 'center' });
      }
    });
  }
}

async function start(scriptEl) {
  const glossaryUrl = new URL(scriptEl.dataset.glossary, document.baseURI).href;
  const vizBase = new URL(scriptEl.dataset.vizBase || 'viz/', document.baseURI).href;
  let data;
  try {
    const r = await fetch(glossaryUrl);
    if (!r.ok) return;
    data = await r.json();
  } catch (err) {
    return;                                  // links stay plain links to glossary.html
  }
  if (!data || typeof data.entries !== 'object' || data.entries === null) return;
  new HelpPane(data.entries, vizBase).install();
}

const scriptEl = document.querySelector('script[type="module"][data-glossary]');
if (scriptEl) {
  start(scriptEl).catch(() => { /* a script error leaves the article untouched */ });
}
