# GIT-PROTOCOL.md — the fleet's git manual

*Written 2026-09-02 (CONTINUITY) after a multi-repo commit campaign that produced one
unauthorized push, one false "that remote doesn't exist" claim, a 16-file diff that had to be
split by author before anyone could commit it, and nine commits that silently landed under the
wrong name. Every rule below is paid for.*

**Audience: the four instances (CONTINUITY / WINTERMUTE / THE-FINN / GHOST-NOTE).** Kim's own
git use is not constrained by this doc. The analytical companion — *how to work out who wrote
uncommitted code* — is `docs/lessons-learned.md` § "Attributing uncommitted work". This file is
the OPERATIONAL half: what to type, what never to type, and what to check afterwards.

---

## 0. The three hard rules

1. **🔄 SUPERSEDED 2026-09-03 (Kim direct) — FINISHED WORK IS COMMITTED.** The old rule was
   *"do not commit unless Kim asked"*; it is now the opposite by default. Kim's words:
   *"when finishing work, it is committed, unless it's transient tooling only. but even in such
   cases we should commit most things with comments to facilitate back tracking and archaeology."*
   - **Default: commit when you finish a piece of work.** No per-task ask needed.
   - **The bar for NOT committing is high: transient tooling ONLY.** A throwaway one-off launcher
     is exempt; almost everything else — including scratch scripts that produced a result — is
     better in history than lost. When in doubt, commit it.
   - **The commit MESSAGE is the point, not the diff.** This rule exists for *back-tracking and
     archaeology*: say what the work was FOR, what it found, and what a future reader needs to
     place it. A one-line "update X" satisfies the letter and defeats the purpose.
   - **Still true:** §2 identity (`Misc/agent_commit.sh <HANDLE>`), §4 never-commit list, and §5 —
     **commit YOUR scope, not another instance's uncommitted work.** "Finished work is committed"
     is not licence to sweep a shared dirty tree into one blob; that destroys the only authorship
     record there is. Stage explicit paths, never `-A`/`-u`.
   - **Rule 2 is UNCHANGED and this does not touch it: pushing still requires Kim asking.**
     Commit freely, push never without a direct ask.
2. **Do not push unless Kim asked.** A commit is local and reversible; a push is outward-facing
   and, on a shared branch, is not. Commit and *say* it is ready to push.
3. **Never run a bare `git push`.** Always name remote and branch: `git push fork
   latch-sa3-phase1`. See §3 for why the bare form is genuinely dangerous here and not merely
   sloppy.

---

## 1. Repo map — know which tree you are in

| Repo | Path | Remote(s) | Push target |
|---|---|---|---|
| SAO (master/lab) | `/home/kim/Projects/SAO` | `origin` → `Taikakim/avp-audio-craft` | `origin` |
| stable-audio-3 | `SAO/stable-audio-3` (**nested**) | `fork`, `origin` (both → `Taikakim/stable-audio-3`), **`upstream` → `Stability-AI/stable-audio-3`** | **`fork`** |
| stable-audio-tools | `SAO/stable-audio-tools` (**nested**) | `avp`, `origin` (both → `Taikakim/audio-tools-avp`) | `origin` |
| mir | `/home/kim/Projects/mir` (**sibling, not nested**) | `origin` → `Taikakim/mir-feature-extraction` | `origin` |
| fusion-optimiser | `/home/kim/Projects/fusion-optimiser` (**sibling**) | `origin` → `Taikakim/fusion-optimiser` | `origin` |

**Two of these are nested inside SAO and two are siblings of it.** `git -C fusion-optimiser …`
from the SAO root fails with `cannot change to 'fusion-optimiser'` — which reads like "the repo
is gone" and is really "wrong parent directory". Use absolute paths for the siblings.

`stable-audio-3` and `stable-audio-tools` are **thin forks**: they hold package deltas only.
Their `CLAUDE.md`/`ARCHITECTURE.md` are the local authority for what belongs in them.

---

## 2. Identity — make the commit say who wrote it

`git config user.name` is **`Kim`**, and it is a property of the *checkout*, not of who is
typing. All four instances share one tree. Consequence, measured 2026-09-01: **197 of the last
200 SAO commits are authored `Kim <kim.ake@gmail.com>`** — a single author name across
essentially the whole history. `git blame`, `git log --format=%an`, and everything built on them
**cannot tell the instances apart**, for committed work as much as uncommitted.

**So commit through the wrapper, always:**

```
Misc/agent_commit.sh CONTINUITY -m "eval: fix the stale flag list"
```

It sets `GIT_AUTHOR_NAME`/`GIT_AUTHOR_EMAIL` to your handle and leaves the *committer* as Kim
(he owns the tree). Handle must be one of `WINTERMUTE|CONTINUITY|GHOST-NOTE|THE-FINN` and must
match your real session name — check `CONSTRUCTS.md` / MASTER §4 on resume, never infer your
handle from task content.

> **This is the rule most likely to be dropped, and it fails silently.** The convention was
> adopted in `20b4852` (2026-09-01). The *very next* batch — nine `stable-audio-3` commits the
> same day, mine — all landed authored `Kim`, because I ran plain `git commit` out of habit and
> nothing complained. Author is not shown in `git log --oneline`; you will not notice.
> **Check with `git log -5 --format='%h %an %s'` after committing, not `--oneline`.**

Also end every message with the trailers the harness specifies for the session
(`Co-Authored-By:` + `Claude-Session:`). Author field and trailer are independent records;
having both is what let a mis-credited commit be corrected on 2026-08-18.

---

## 3. Push targets, and why the bare form is dangerous

**`stable-audio-3` has an `upstream` remote pointing at `Stability-AI/stable-audio-3` — and it
has a PUSH url, not just a fetch url.** A push that resolves to `upstream` is a push at
Stability's repository. It would be rejected for lack of permission, but design for the case
where it is not: **never type `upstream` in a push command, and never push without naming the
remote.**

**The unauthorized push, 2026-09-01.** I composed a DM in prose that contained the phrase
`` `git push` `` in backticks and passed the whole string to the Bash tool inside **double**
quotes. Bash performed command substitution on the backticks and executed a bare `git push` in
SAO, publishing **180 commits** (`f5b1a45..45cd078`) that nobody had approved. Damage turned out
to be nil — fast-forward only, no history rewritten, private repo, working tree untouched — and
Kim's ruling was *"if there's no damage, let it lie."* Luck, not process.

**The rules that fall out of it:**

- **Never interpolate prose into a double-quoted shell string.** Technical prose is *full* of
  backticks and `$`. Build message text in Python and hand it to `subprocess.run` as an argv
  element, or write it to a file with a quoted heredoc (`<<'EOF'`, quoted delimiter) and pass
  the path. Single-quoting is safer than double but still breaks on an apostrophe.
- **Prefer `-F <file>` over `-m "<string>"`** for any commit message longer than one line or
  containing code identifiers: `Misc/agent_commit.sh CONTINUITY -F /tmp/msg.txt`.
- The same hazard applies to `gh pr create --body`, dialogue posts, and every other place agent
  prose reaches a shell.

---

## 4. Never commit these

- **Absolute drive paths and the `models` symlink** into `/run/media/kim/<uuid>/…`. Drive
  mountpoints change; config files exist for this. (Standing rule: *no hardcoded drive paths*.)
- **Secrets of any kind.** `WORKLOG.md` and `AGENT_DIALOGUE.md` are **public** — the dialogue
  log auto-mirrors to a public URL. No passwords, API keys, tokens, SSH creds, `.netrc`, or
  credential-revealing paths, in a commit message or in a file.
- **Another instance's uncommitted work.** See §5.
- **Checkpoints, latents, renders, `.ckpt`/`.safetensors`.** Check `.gitignore` covers the new
  output directory *before* the run, not after `git status` shows 40 GB staged.

---

## 5. Multi-author uncommitted diffs — the torch-pass protocol

Four instances share one checkout, so a dirty tree is routinely **several people's work
interleaved, sometimes inside a single file**. Committing it as one blob destroys the only
authorship record there will ever be (§2) and can commit a half-feature that compiles.

**Protocol, as run on the 16-file `stable-audio-3` diff (2026-09-01):**

1. **Map before touching anything.** Produce a per-file claim map with a **confidence label**
   per row — strong / weak / no-evidence — and state your method's limits in the map itself.
   Publish confidence, not verdicts: a map that asserted owners would have committed six files
   to the wrong people silently.
2. **Attribute using the three-leg search** — `docs/lessons-learned.md` § "Attributing
   uncommitted work". Run all three legs; they are complementary, not ranked substitutes.
3. **Each contributor commits their own portion, in sequence**, then explicitly passes the torch
   to the next by DM. Not parallel — you are all writing the same index.
4. **When the search comes back empty, that is evidence the search cannot see the link, not
   evidence the work is unowned.** Every "orphan" in that diff had an owner. Ask on the channel
   before filing anything as ownerless.

### Splitting a mixed file (`git add -p` is unavailable)

**Interactive git flags are blocked in this environment** — no `git add -p`, no `git rebase -i`.
And mixing can be **intra-hunk**: one `lora/model.py` hunk held both a dict-mutation fix and a
`try/except AdapterShapeError` whose exception class existed only in the *other* author's
uncommitted diff. Staging that hunk whole would have committed a reference to a class that is
not there — and it would have compiled clean, because the name only resolves at call time.

Hunk-level split, when hunks are cleanly separable:
```
git diff <file> > /tmp/f.patch          # split on ^@@ boundaries, keep your hunks
git apply --cached --recount /tmp/mine.patch
```
Sub-hunk split, when they are not — **build the file instead of patching it**:
```
git show HEAD:<file> > /tmp/base.py     # apply your single edit to this copy
git hash-object -w /tmp/mine.py         # -> <sha>
git update-index --cacheinfo 100644,<sha>,<file>
```

**Verify the STAGED blob, not the working tree** — they differ by construction here:
```
git show :<file> | python3 -m py_compile /dev/stdin   # must compile
git show :<file> | grep -n '<other author's symbol>'  # must be EMPTY
```
Then confirm afterwards that the working tree still holds their work untouched.

**Split by CONCERN even when authorship turns out to be uniform.** `model.py`'s 13 hunks split
7/6 into `latents_sink` + a `_cast` dict fix, and `sample_size` auto-grow. Both halves proved to
be mine; two commits was still the right answer, because the halves are independently
revertable.

---

## 6. Verify before you claim

- **Never narrow the output of a command you are about to make a claim from.** I ran
  `git remote -v | head -4` and told a teammate stable-audio-3 had **no `upstream` remote** — the
  upstream lines were 5 and 6. The shell-output-is-context rule (`CLAUDE.md`) says narrow
  aggressively; it does **not** license narrowing the evidence under a claim. If the answer is
  "does X exist", grep for X or read the whole listing.
- **After committing:** `git log -5 --format='%h %an %s'` — confirms both the message *and* the
  author (§2). `--oneline` hides the field most likely to be wrong.
- **After a split:** `git status -s` should still show the other author's files dirty, and
  `git stash list` should be empty (nothing of theirs got swept up).
- **Before pushing:** `git log --oneline @{u}..` — read the exact list of commits that will go
  out. If it is longer than you expect, stop; that is the bare-push failure mode in §3.
- **After pushing:** confirm it was a fast-forward. `git reflog show <remote>/<branch> | head`
  shows `update by push` vs anything that implies a rewrite.

---

## 7. Working-tree hygiene

- **`git switch` on a repo with untracked scripts/renders can lose them.** Commit or stash
  before switching branches. (Recoverable via stash trees if you are lucky — do not rely on it.)
- **Branch drift is real.** Trained checkpoints can require model code that exists only on a
  feature branch (adaln_zero LatCH lived on `latch-rms-control` while `main` lagged, and loaders
  failed). Note merges in `WORKLOG.md`.
- **Filelock shared docs before editing** — `python3 Misc/filelock.py acquire <path> --handle
  <YOU>`, release when done. Applies to `CLAUDE.md`, `MASTER.md`, `ARCHITECTURE.md`,
  `WORKLOG.md`, `EXPERIMENTS.md`, `KIM-TASKLIST.md`, `docs/lessons-learned.md`.

---

## 8. One-page checklist

```
BEFORE   [ ] Kim asked for this commit, in this repo, in his own words
         [ ] git status -s  — is any of this someone else's work?
         [ ] no drive paths / secrets / checkpoints in the diff
SPLIT    [ ] three-leg attribution run; claim map has confidence labels
         [ ] staged blob compiles AND greps clean of the other author's symbols
COMMIT   [ ] Misc/agent_commit.sh <HANDLE>  (not plain `git commit`)
         [ ] message via -F <file>, never -m with backticks or $
AFTER    [ ] git log -5 --format='%h %an %s'  — author is YOU, not Kim
PUSH     [ ] Kim asked, separately, for a push
         [ ] git log --oneline @{u}..   — exactly the commits you intend
         [ ] git push <remote> <branch>  — named, never bare, never `upstream`
```
