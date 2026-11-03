# Eval page standard

Owner: WINTERMUTE (created 2026-11-03, after a set of restyled pages went live with a re-drawn logo, a different nav on every page
and their own audio bars). Applies to every page under `files/evals/`, from any agent, external ones included.

`files/reference.html` defines the site's look (paper, one monospace typeface, one accent, no emoji in chrome), but it has no section
on eval pages. This file is that section. It does not replace MASTER section 4, which sets what an eval page must SAY.

## Use these, do not invent

| Part | Use | Never |
|---|---|---|
| Stylesheet | `evals.css` (same folder as the page). Colours as its tokens: `--paper`, `--paper-dim`, `--ink`, `--body`, `--dim`, `--faint`, `--rule`, `--edge`, `--edge-ink` | dark backgrounds, new colour schemes, a second typeface |
| Header | `<p class="over">VIBE ON THE EDG3 · EVALS</p>` | the site masthead, or any re-drawn logo |
| Navigation | One line: `<p class="nav"><a href="index.html">← all evals</a></p>` | `mainnav`, per-page link sets. Related pages go in the text, as sentences |
| Player | `Misc/float_player.py`: `html = inject(html)`. Keep one `<audio>` element per page, or `new Audio()` | a visible page-level `<audio controls>` or a custom transport bar |
| Clip buttons | `.cell` / `.cell.playing` from `evals.css`, or `Misc/eval_grid.py` for tables | new button styles |
| Notes | `Misc/comment_notes_block.py` `notes_block(...)` | anything that reads the notes back (MASTER section 4) |
| Chrome for a finished page | `python3 Misc/eval_page_finish.py <page.html>` fixes header, nav and player on a page that has drifted | |

Paths are relative to the page, so a page opens from any location. Root-absolute audio URLs such as `/my_board/clip.m4a` return 404.

## What every page must carry (MASTER section 4)

1. **Clips first:** every result section has clips to click. Switching clips keeps the playhead; clicking the playing clip stops it.
2. **What it tests and why,** in plain words, at the top.
3. **The red ❗** until a listening verdict is recorded (`kim_feedback` in the sidecar).
4. **The disintegration gate:** for anything that steers, show gate results, or say plainly that it has not been run. Without it the page cannot name a usable range or a "sweet spot".
5. **A guided baseline:** the gain-0 clip comes from the guided sampler at gain 0 (MASTER section 5). If it does not, say so on the page.
6. **`run_meta.json`** beside the clips: purpose, hypothesis, recipe, result, `kim_feedback`.

## Claims

- State what was measured. A hypothesis is labelled as one. No "proven", "record", "solves" or "overwhelming".
- Numbers come from the data files, not typed into the builder. Give n, prompts and seeds; one prompt and one seed establish nothing, and the page says so.
- A classifier score is a classifier score. It is not "sounds better".

## Publishing

- **Only WINTERMUTE publishes** to the site. Stage the page in `~/evals_aac/` and say it is ready.
- Before publishing: leak scan (no drive paths, hosts or credentials; checkpoint filenames are fine), every clip reference exists, the page plays in a browser, and the claims have been read against the data.
- Commit the builder. A correction made only in the staged HTML is lost at the next rebuild, so corrections go into the builder.
- The server caches pages for 10 minutes. After a republish, test with `?v=2` on the URL.
