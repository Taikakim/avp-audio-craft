# Help pane and glossary for site pages: design

Status: DESIGN, approved section by section in chat on 2026-10-26 (WINTERMUTE, brainstorming). Awaiting review of this
written spec; the implementation plan follows only after it is approved.
Inputs: `2026-10-26-help-pane-glossary-design.md` (requirements stub, CONTINUITY), `2026-10-26-help-pane-kim-messages-verbatim.md`
(the review, M1-M10), `2026-10-26-muon-guide-kim-review.md` (sorted review + look-ups).

## 1. Goal

A reader who meets an unfamiliar term can open a plain explanation next to the text, follow it to related terms and back,
and check their understanding with a short quiz, without leaving the page. Purpose (from the review): stop the gap that
opens when a reader glosses over a concept and then understands less of everything after it. One reusable component for
the whole site; the first page is the Muon survival guide (`blog/2026-10-21-muon-survival-guide-DRAFT.md`).

## 2. Decisions taken in chat

| Question | Decision |
|---|---|
| What must exist before the Muon guide goes live | **Everything in the review**: the pane, all terms (~60) with reviewed quizzes, all six animations, the guide rewrite incl. the new EMA and DoRA-vs-full-fine-tune sections |
| How often a term is marked | **Every occurrence** |
| Quiz memory | **None**: nothing stored anywhere, quizzes reset on every visit |
| Desktop layout | **Docked right column** (~40% on wide screens); the article narrows, nothing is covered |
| Entry depth | **Three layers**: plain sentence / "In our models" / collapsed "Going deeper" |
| Build approach | **A**: terms marked at build time in Python, pane in the browser |
| Animation code | Plain JavaScript, SVG or canvas, no third-party libraries or CDNs; real computation where the entry claims a mechanism |

## 3. Work split (each part gets its own plan)

1. **The pane** (this spec, sections 4-8): marker, entry checks and compiled glossary, pane, quiz, module loader.
2. **Glossary content**: CONTINUITY writes entries in the section 5 format (first five done, SAO `6ee0efe`); the
   questions are reviewed by Kim in chat.
3. **The six animations** (section 7), one at a time, WINTERMUTE.
4. **The guide rewrite**: Kim's section-by-section notes (review file section C), the two new sections, and the clip spectra
   (static images computed at build time). WINTERMUTE, the draft's owner.
5. **Outside the blog, not gated on the pane**: ModularOptimizer warnings (review file section F) and the experiment list
   (section E).

## 4. Architecture

**At publish time**
1. Entries live in `SAO/glossary/<topic>.json` (one JSON list per topic file).
2. `Misc/glossary/build_page.py` validates every entry (section 5) and writes `glossary.html` (all entries, readable without
   JavaScript, one anchor per entry id) and a single compiled `glossary.json` (what the pane fetches).
3. `Misc/publish_blog.py` renders the post as today, then calls `Misc/glossary/mark.py::mark(html, glossary)`, which turns
   every occurrence of a term into `<a class="gl" data-term="<id>" href="glossary.html#<id>">`. A per-post switch turns
   the pane on; the post then includes `help-pane.css` and `help-pane.js`.
4. Page, glossary files and `site/help/` files are uploaded together; the existing leak scan covers the glossary text too.

**When reading**
1. A click on a marked term opens the docked pane with that entry (JavaScript on), or goes to the entry on `glossary.html`
   (JavaScript off).
2. Terms inside an entry are marked the same way; each click adds a step to the pane's back history.
3. An entry's animation module (`site/help/viz/<id>.js`) loads only when that entry opens.

**Reuse on another page:** its builder calls `mark()` and includes the two help files. Nothing else.

**Marker rules**
- Case-insensitive, whole words; simple plurals ("weights", "matrices") match automatically; other forms through `aliases`.
- Longest match wins ("LoRA A" before "LoRA"); no nested marks.
- Skipped: headings, `code`/`pre`, existing links, figure captions, table header cells.
- Inside an entry, the entry's own term is not marked.
- The marker works on the rendered HTML text nodes (not the Markdown), so the same function serves any page builder.

## 5. Entry format

`SAO/glossary/<topic>.json` = a JSON list of entries:

```json
{
  "id": "momentum",
  "term": "momentum",
  "aliases": ["momentum buffer", "running average of gradients"],
  "plain": "A running average of recent gradients, so one noisy batch cannot steer the training on its own.",
  "ours": "Each weight matrix in our heads keeps one ...",
  "deeper": "m = beta * m + (1 - beta) * g ...",
  "papers": [{"title": "Muon (Jordan, 2024)", "url": "https://kellerjordan.github.io/posts/muon/"}],
  "viz": {"module": "batch-noise", "params": {}},
  "quiz": [
    {"level": 1, "q": "What does momentum average?",
     "options": ["Recent gradients", "Recent weights", "The learning rate", "The loss", "The batch size"],
     "answer": 0,
     "why": "Momentum keeps a running average of the gradients ...",
     "wrong": {"1": "That is what EMA does: it averages the weights, not the gradients."}}
  ],
  "quiz_reviewed": null
}
```

- Required: `id` (unique slug), `term`, `plain` (one sentence; the build warns if longer), `quiz` (3-5 questions).
- `ours`, `deeper`, `papers`, `viz`, `aliases`, `wrong` are optional.
- Text fields use the blog's inline syntax only: `` `code` ``, `**bold**`, `[text](https://...)`. No link syntax for terms:
  entries are marked automatically.
- Questions: exactly five `options`; `answer` is an index 0-4; `level` 1-3 says which layer it tests and sets the order
  (easiest first); `why` is always shown after answering; `wrong` maps an option index to feedback for that choice.
- `quiz_reviewed`: the date Kim approved that entry's questions in chat, written only from his chat verdict.

**Build errors** (the build stops): missing required field; option count other than 5; `answer` out of range; question
count outside 3-5; duplicate `id` or alias; an alias equal to another entry's term or alias; unknown `viz.module`;
`wrong` given for the correct option; a page using an entry whose `quiz_reviewed` is empty (publish only; local
dry-runs warn instead, so unreviewed entries can be tested).

## 6. Pane behaviour

**Opening and moving**
- Clicking a term opens the right-hand column; the article narrows and keeps the clicked term in view.
- Header: back, term name, close. Escape closes.
- Back walks the history of this visit; close keeps it, reopening returns to the last entry; a reload starts empty.
- The address shows `#gl=<id>`, so a link can open the page with an entry showing. An unknown id is ignored.

**Entry layout, top to bottom:** plain sentence; "In our models"; the animation with an "enlarge" button (full-page
overlay); "Going deeper" (collapsed); paper links; "Check your understanding (n questions)".

**Quiz**
- One question at a time, five radio options.
- Answering replaces the question with its feedback: right or wrong, `why`, and the `wrong` note for the chosen option;
  then "Next question".
- End: score ("3 of 4"), "Try again", "Back to the entry". Back from a quiz returns to its entry.
- Nothing recorded, sent or stored.

**Marked terms:** thin dotted underline in the site accent colour, solid on hover, no background. Terms opened during
this visit get a fainter underline (page memory only, gone on reload).

**Phones:** a bottom sheet (~70% of the screen), dismissed by swiping down or the close button; animations open full-screen.

**Accessibility:** terms are real links (tab-reachable); opening moves focus into the pane, closing returns it to the
term; quiz feedback is announced to screen readers (live region); the pane is a labelled complementary region.

## 7. Animation modules

**Interface:** `site/help/viz/<id>.js` exports `mount(container, params, help) -> { destroy() }`. `help` provides the site
colours, `openTerm(id)`, and `reducedMotion` (true when the reader's system asks for less motion: start still, offer a step
button). Modules pause when out of view and are destroyed when their entry closes.

**"What's real here" note, required in every module:** what is computed live, which numbers come from our runs (run
named), and what is illustration only. Our numbers sit in a small table in the module with their source in a comment.
Update maths (AdamW, Newton-Schulz/Muon, the noise model) lives in a shared `site/help/viz/lib/` file with numeric tests.

| id | Shows | Real / measured / illustrative |
|---|---|---|
| `step-size` | Nodes and wires, wire thickness = per-weight step; AdamW left, Muon right; scenarios steady / noisy / gradient drops 100x / rises; "precision" switch greys out steps too small for bf16, fp16, fp8 | real AdamW and Muon updates on a tiny matrix; rounding thresholds computed |
| `batch-noise` | 2-D loss valley, true gradient and a cloud of minibatch gradients; batch slider 1-256; momentum switch; SNR readout | noise calibrated to the batch-64 half-batch cosines (0.37 early, 0.08 late); below 64 labelled "extrapolated" |
| `lora-rank` | d -> r -> d bottleneck, rank slider, parameter count, a small input transform; energy-kept curve; DoRA switch with per-row magnitude dials | measured 26% (r128), 65% (r512), 89.5% (r1024); between points drawn as interpolated |
| `qkv-line` | Assembly line: one fused machine stamps Q, K, V vs three machines; then fused vs separate orthogonalisation | the step difference computed live on a small matrix |
| `routing` | One of our heads coloured by optimiser group: recommended routing vs ours (unsplit QKV, AdaLN emitter, time embedding); gradients in, updates out | routing from TRAINING.md F30; step sizes from section 4 of the guide |
| `lora-a-rotation` | Rows of LoRA A and B as arrows over training; A barely turns, B moves; A at 20x lr rotates | toy model; percentages from the run (99.2% vs 35% unchanged) |

## 8. Publishing, failures, testing

**Publishing:** `publish_blog.py --dry-run` renders to a scratch folder for a local browser check; nothing goes public
without Kim's go; the leak scan covers `glossary.json` and `glossary.html`; the guide stays held until section 3 items 1-4
are done.

**Failures never block reading:** glossary fetch fails -> links fall through to `glossary.html`; an animation fails -> its
entry shows the text with "animation unavailable"; a script error in the pane leaves the article untouched.

**Tests**
- Python (`Misc/glossary/tests/`): marker (every occurrence, longest match, skip zones, aliases, plurals, own-term rule),
  one test per build error in section 5, glossary page build.
- Browser (Playwright, on the built dry-run page): open/close, back history, full quiz run, deep link, no-JavaScript fallback,
  phone viewport, keyboard path.
- Animations: numeric tests of the shared update maths; screenshot review of each module before Kim sees it.

**Order:** pane + marker on CONTINUITY's first five entries; then the animations one at a time; the guide rewrite in parallel.

## 9. Housekeeping

- `.gitignore` whitelists top-level paths: `!/glossary/` was added by CONTINUITY; `Misc/` is ignored (add files with
  `git add -f`); check `site/help/` before the first commit.
- New scripts carry the ownership header. Owner of the pane code: WINTERMUTE.

## 10. Out of scope here

The glossary content itself (part 2), the guide text (part 4), ModularOptimizer changes and experiments (part 5),
quiz analytics of any kind (decided: no memory), a resizable pane, a runtime text scanner for pages not built by our Python
builders (approach C, not needed while every page comes from them).
