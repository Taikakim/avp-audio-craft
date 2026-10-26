// Owner: WINTERMUTE (created 2026-10-26)
// help-pane.js: docked help pane for glossary terms (spec 2026-10-26-help-pane-design.md, section 6).
// Plain ES module, no dependencies. Reads <script type="module" data-glossary data-viz-base> (contract C3),
// fetches glossary.json (C4) once, and loads animation modules (C5) on demand.
// It uses no browser storage of any kind and sends nothing except those two kinds of fetch.
// If glossary.json cannot be loaded, or this script throws, no click handler exists and the links keep
// navigating to glossary.html: reading is never blocked.

const PHONE_QUERY = '(max-width: 700px)';
const SEEN = 'gl-seen';
const isPhone = () => window.matchMedia(PHONE_QUERY).matches;

const NON_TEXT_INPUTS = new Set(['radio', 'checkbox', 'button', 'submit', 'reset', 'range', 'color', 'file', 'image']);
function isTextEntry(n) {
  if (n.closest('textarea, select, [contenteditable]:not([contenteditable="false"])')) return true;
  return n instanceof HTMLInputElement && !NON_TEXT_INPUTS.has(n.type);
}

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

function freshQuiz() {
  return { i: 0, score: 0, stage: 'ask', chosen: null };
}

class HelpPane {
  constructor(entries, vizBase, glossaryUrl) {
    this.entries = entries;
    this.glossaryUrl = glossaryUrl;
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
    if (e.key !== 'Escape' || e.defaultPrevented || e.isComposing) return;
    const tg = e.target;
    if (tg instanceof Element && isTextEntry(tg)) return;     // Escape belongs to the field, not the pane
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
    // C4 hrefs are relative to help/; make them absolute so new-tab, copy-link and long-press work from any page
    this.bodyEl.querySelectorAll('a.gl').forEach((a) => {
      const id = a.dataset.term;
      if (id) a.href = new URL('glossary.html#' + id, this.glossaryUrl).href;
    });
    this.bodyEl.scrollTop = 0;
    this.markSeen(item.id);
  }

  markSeen(id) {
    this.seen.add(id);
    document.querySelectorAll('a.gl').forEach((a) => {
      if (this.seen.has(a.dataset.term)) a.classList.add(SEEN);
    });
  }

  renderEntry(entry) {
    const b = this.bodyEl;
    b.append(rich('p', 'hp-plain', entry.plain));
    if (entry.ours) {
      const s = el('section', 'hp-ours');
      s.append(el('h3', null, 'In our models'), rich('div', 'hp-text', entry.ours));
      b.append(s);
    }
    if (entry.viz) b.append(this.buildViz(entry));
    if (entry.deeper) {
      const d = el('details', 'hp-deeper');
      d.append(el('summary', null, 'Going deeper'), rich('div', 'hp-text', entry.deeper));
      b.append(d);
    }
    if (entry.papers && entry.papers.length) {
      const s = el('section', 'hp-papers');
      s.append(el('h3', null, 'Papers'));
      const ul = el('ul');
      for (const p of entry.papers) {
        const li = el('li');
        if (/^https?:/i.test(p.url || '')) {
          const a = el('a', null, p.title);
          a.href = p.url;
          a.target = '_blank';
          a.rel = 'noopener noreferrer';
          li.append(a);
        } else {
          li.append(el('span', null, p.title));      // not an http(s) link: show the title only
        }
        ul.append(li);
      }
      s.append(ul);
      b.append(s);
    }
    if (entry.quiz && entry.quiz.length) {
      const n = entry.quiz.length;
      const q = btn('hp-quiz-start', `Check your understanding (${n} ${n === 1 ? 'question' : 'questions'})`);
      q.addEventListener('click', () => this.startQuiz());
      b.append(q);
    }
  }

  // ---- animation ------------------------------------------------------------------------------------------

  buildViz(entry) {
    const token = this.token;
    const wrap = el('div', 'hp-viz');
    const stage = el('div', 'hp-viz-stage');
    stage.append(el('p', 'hp-viz-note', 'Loading the animation...'));
    const big = btn('hp-enlarge', null);
    big.innerHTML = '<span class="hp-wide">Enlarge</span><span class="hp-narrow">Open full screen</span>';
    big.addEventListener('click', () => this.enlarge(wrap, big));
    wrap.append(stage, big);
    this.mountViz(entry, stage, wrap, token);      // async; the import always resolves after wrap is attached
    return wrap;
  }

  async mountViz(entry, stage, wrap, token) {
    try {
      const mod = await import(this.vizBase + entry.viz.module + '.js');
      if (token !== this.token) return;            // the reader already left this entry
      stage.replaceChildren();
      const handle = mod.mount(stage, entry.viz.params || {}, this.helpApi());
      this.viz = { handle, wrap };
    } catch (err) {
      if (token !== this.token) return;
      stage.replaceChildren(el('p', 'hp-viz-note', 'Animation unavailable.'));
      wrap.classList.add('hp-viz-failed');
    }
  }

  enlarge(wrap, opener) {
    if (this.overlay) return;
    const overlay = el('div', 'hp-overlay');
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.setAttribute('aria-label', 'Animation, enlarged');
    const close = btn('hp-overlay-close', 'Close');
    close.setAttribute('aria-label', 'Close the enlarged animation');
    close.addEventListener('click', () => this.closeOverlay(true));
    const marker = document.createComment('hp-viz-home');
    wrap.before(marker);                            // remember where the animation lives
    overlay.append(close, wrap);                    // move the live node: state and canvas survive
    wrap.classList.add('hp-viz-big');
    document.body.append(overlay);
    this.overlay = { overlay, wrap, marker, opener };
    close.focus({ preventScroll: true });
    window.dispatchEvent(new Event('resize'));      // lets the module re-measure its container
  }

  closeOverlay(refocus) {
    const o = this.overlay;
    if (!o) return;
    this.overlay = null;
    o.wrap.classList.remove('hp-viz-big');
    if (o.marker.parentNode) o.marker.replaceWith(o.wrap);   // back home (if the entry was not re-rendered)
    o.overlay.remove();
    window.dispatchEvent(new Event('resize'));
    if (refocus && o.opener && o.opener.isConnected) o.opener.focus({ preventScroll: true });
  }

  // ---- quiz -----------------------------------------------------------------------------------------------

  startQuiz() {
    const t = this.top();
    if (!t) return;
    this.trail.push({ id: t.id, mode: 'quiz', quiz: freshQuiz() });   // Back pops this and shows the entry again
    this.render();
    this.syncHash();
    this.focusFirst('.hp-progress');
  }

  focusFirst(selector) {
    const n = this.bodyEl.querySelector(selector);
    if (n) { n.tabIndex = -1; n.focus({ preventScroll: true }); }
  }

  renderQuiz(entry, item) {
    const qs = entry.quiz;
    const st = item.quiz;
    const n = qs.length;
    if (st.stage === 'done') { this.renderScore(n, st); return; }
    const q = qs[st.i];
    const wrap = el('div', 'hp-quiz');
    wrap.append(el('p', 'hp-progress', `Question ${st.i + 1} of ${n}`));
    if (st.stage === 'ask') {
      const form = el('form', 'hp-q');
      const fs = el('fieldset');
      fs.append(rich('legend', 'hp-qtext', q.q));
      q.options.forEach((opt, k) => {
        const label = el('label', 'hp-opt');
        const input = el('input');
        input.type = 'radio';
        input.name = 'hp-opt';
        input.value = String(k);
        label.append(input, rich('span', null, opt));
        fs.append(label);
      });
      const submit = el('button', 'hp-answer', 'Check answer');
      submit.type = 'submit';
      submit.disabled = true;
      form.addEventListener('change', () => { submit.disabled = !form.querySelector('input:checked'); });
      form.addEventListener('submit', (e) => {
        e.preventDefault();
        const c = form.querySelector('input:checked');
        if (c) this.answer(Number(c.value));
      });
      form.append(fs, submit);
      wrap.append(form);
    } else {
      wrap.append(this.buildFeedback(q, st, n));
    }
    this.bodyEl.append(wrap);
  }

  buildFeedback(q, st, n) {
    const right = st.chosen === q.answer;
    const fb = el('div', 'hp-feedback ' + (right ? 'hp-right' : 'hp-wrong'));
    fb.tabIndex = -1;
    fb.append(rich('p', 'hp-qtext', q.q));
    fb.append(el('p', 'hp-verdict', right ? 'Correct.' : 'Not quite.'));
    if (!right) {
      const note = q.wrong && q.wrong[String(st.chosen)];
      if (note) fb.append(rich('p', 'hp-wrong-note', note));
      const ra = el('p', 'hp-right-answer');
      ra.append('The right answer: ', rich('span', null, q.options[q.answer]));
      fb.append(ra);
    }
    fb.append(rich('p', 'hp-why', q.why));
    const next = btn('hp-next', st.i + 1 >= n ? 'See your score' : 'Next question');
    next.addEventListener('click', () => this.nextQuestion());
    fb.append(next);
    return fb;
  }

  answer(k) {
    const item = this.top();
    const q = this.entries[item.id].quiz[item.quiz.i];
    item.quiz.chosen = k;
    item.quiz.stage = 'feedback';
    if (k === q.answer) item.quiz.score += 1;
    this.render();
    const fb = this.bodyEl.querySelector('.hp-feedback');
    if (fb) {
      // announce verdict, note, correct option and explanation (not the Next button) to screen readers
      this.live.textContent = [...fb.querySelectorAll('.hp-verdict, .hp-wrong-note, .hp-right-answer, .hp-why')]
        .map((n) => n.textContent.replace(/\s+/g, ' ').trim()).join(' ');
      fb.focus({ preventScroll: true });
    }
  }

  nextQuestion() {
    const item = this.top();
    const n = this.entries[item.id].quiz.length;
    const st = item.quiz;
    if (st.i + 1 >= n) st.stage = 'done';
    else { st.i += 1; st.stage = 'ask'; st.chosen = null; }
    this.render();
    this.focusFirst(st.stage === 'done' ? '.hp-score-line' : '.hp-progress');
  }

  renderScore(n, st) {
    const wrap = el('div', 'hp-quiz hp-done');
    wrap.append(el('p', 'hp-score-line', `You got ${st.score} of ${n} right.`));
    const again = btn('hp-again', 'Try again');
    again.addEventListener('click', () => {
      this.top().quiz = freshQuiz();
      this.render();
      this.focusFirst('.hp-progress');
    });
    const back = btn('hp-entry-back', 'Back to the entry');
    back.addEventListener('click', () => this.back());
    const row = el('div', 'hp-actions');
    row.append(again, back);
    wrap.append(row);
    this.bodyEl.append(wrap);
  }

  // Swipe down on the header dismisses the bottom sheet. Only the header listens, so the pane body and the
  // page keep their normal touch scrolling; nothing here locks page scroll.
  installSwipe() {
    const head = this.head;
    const pane = this.pane;
    let startY = 0;
    let dy = 0;
    let dragging = false;
    head.addEventListener('touchstart', (e) => {
      if (!isPhone() || e.touches.length !== 1) return;
      startY = e.touches[0].clientY;
      dy = 0;
      dragging = true;
      pane.style.transition = 'none';
    }, { passive: true });
    head.addEventListener('touchmove', (e) => {
      if (!dragging) return;
      dy = Math.max(0, e.touches[0].clientY - startY);
      pane.style.transform = `translateY(${dy}px)`;
    }, { passive: true });
    const end = () => {
      if (!dragging) return;
      dragging = false;
      pane.style.transition = '';
      pane.style.transform = '';
      if (dy > 80) this.close();
      dy = 0;
    };
    head.addEventListener('touchend', end);
    head.addEventListener('touchcancel', end);
  }

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
  new HelpPane(data.entries, vizBase, glossaryUrl).install();
}

const scriptEl = document.querySelector('script[type="module"][data-glossary]');
if (scriptEl) {
  start(scriptEl).catch(() => { /* a script error leaves the article untouched */ });
}
