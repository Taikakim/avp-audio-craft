#!/usr/bin/env python3
"""score_and_publish.py — legs (b) and (c) of the post-training pipeline, as ONE callable.

Kim 2026-08-09, from the open-tails audit (docs/audit-open-tails-2026-08-07.md §0 as revised).
The audit's finding was "train_lora.py has no auto-render hook"; the correction was that a
checkpoint only becomes AUDITABLE when three things complete in series:

    (a) RENDER   -> clips exist                (train_lora.py hook — not this script)
    (b) SCORE    -> clips have metric rows     -> they can be ranked, they get table rows
    (c) PUBLISH  -> clips are on the host      -> Kim can actually hear them

Build only (a) and the backlog changes shape from "checkpoint with no clips" into "clips nobody
can see or rank" — the state 5,532 clips across 7 models sat in for weeks, which surfaced as
"the DoRA rows are missing for many models" and was never a board bug. This script is (b)+(c),
so the render hook can finish the job with one call.

    eval/score_and_publish.py --pattern winning_goa      # scope is REQUIRED, see below
    eval/score_and_publish.py --pattern aug8 --src /path/to/pulled/renders
    eval/score_and_publish.py --pattern x0eq --no-publish        # local only
    eval/score_and_publish.py --pattern x0eq --dry-run           # plan + preflight, no writes

DESIGN RULES, each one paid for by a specific failure this session:

  * EVERY STEP IS GATED ON ITS ARTIFACT, NEVER ON AN EXIT CODE. Both scoring runs that
    produced good data this week exited nonzero (rc=134 SIGABRT, rc=139 SIGSEGV) in ROCm
    teardown AFTER writing everything; conversely `rc=$?` after a pipe reports the last
    stage's status, and `rsync ... 2>/dev/null` makes a connection failure look identical to
    "nothing to do". So we check rows-in-db, models-in-aggregate, bytes-on-host.
  * --pattern IS MANDATORY. An unscoped Audiobox pass pulls in the board-wide missing-ce
    backlog (59k clips at last count) instead of the campaign you just trained.
  * GPU WORK GOES THROUGH gpu_guard.sh. rocm-smi is ground truth; a foreign instance shares
    this box and does not reliably write /tmp/gpu.lock.
  * PUBLISH READS rsync --itemize FLAGS. A bulk page regen restamps hundreds of byte-identical
    files; on the last reconcile 87 of 102 "stale" pages and 5,110 of 5,693 "stale" clips were
    mtime-only. Uploading those is pure churn.
  * LEAK-SCAN AT SHIP TIME, and verify over HTTP by SAMPLING ACTUAL CLIPS — a page can go live
    with all of its audio missing (headb_bracket was one command away from exactly that).
"""
import argparse
import json
import os
import random
import re
import shlex
import sqlite3
import subprocess
import sys
import urllib.request
from pathlib import Path

SAO = Path("/home/kim/Projects/SAO")
STAGE = Path("/home/kim/evals_aac")
MATRIX = STAGE / "model_matrix"
MANIFEST = MATRIX / "manifest_live.jsonl"
DB = SAO / "eval/clip_metrics.db"
AGG = SAO / "eval/clap_dora_aggregate.csv"
CLAP_SCAN = SAO / "eval/clap_degen_model_matrix.csv"
GUARD = SAO / "Misc/gpu_guard.sh"
MIR_PY = "/home/kim/Projects/mir/mir/bin/python"      # Audiobox must run in mir's venv
SAO_PY = str(SAO / ".venv/bin/python")
HOST = "dh_4txyt6@iad1-shared-b8-25.dreamhost.com"
HOST_EVALS = "/home/dh_4txyt6/aavepyora.online/files/evals/"
PUBLIC = "https://aavepyora.online/files/evals/"
SSH = "ssh -o BatchMode=yes -i /home/kim/.ssh/id_ed25519"
# plumbing that must never reach a public page (science/hyperparams are fine, see spec §4).
# Anchored patterns only: a bare \.ckpt matches JS property accesses like noteCtx.ckpt and
# produced two phantom "leaks" in one day.
# BLEND.*.json (soup recipes: which two checkpoint snapshots were blended) and AUDIT_*.json
# (per-dir provenance audits) are the same class as run_meta: local provenance that carries
# absolute paths BY DESIGN and that no served page reads. Withhold them rather than redact --
# redacting would destroy the only record of which snapshot a soup came from. (W, 2026-09-09)
LOCAL_ONLY = re.compile(r"(^|/)(run_meta|_meta)\.json$|\.commentary\.json$|/longclips\.json$"
                        r"|(^|/)BLEND[^/]*\.json$|(^|/)AUDIT_[^/]*\.json$")
MEDIA_EXT = (".m4a", ".flac", ".wav", ".mp3", ".ogg")


def is_local_only(rel):
    """True for local provenance that must not leave the box.

    Beyond the named files above, a .json sitting beside a clip of the SAME STEM is a per-clip
    sidecar (render params, blend recipe, checkpoint snapshot paths). Those carry absolute paths
    by design and no served page fetches them -- the boards bake provenance into the HTML at
    build time. The test has to be structural, not a name pattern: these sidecars are named
    after their clip, so there is no name to match. (W, 2026-09-09)
    """
    if LOCAL_ONLY.search(rel):
        return True
    p = STAGE / rel
    if p.suffix == ".json":
        return any(p.with_suffix(e).exists() for e in MEDIA_EXT)
    # A page with a redacted twin beside it: the twin is what boards link to and what ships
    # (build_morph_page --public, dora_table_public.html). The unredacted original keeps its
    # source paths on purpose and must stay home. (W, 2026-09-09)
    if p.suffix == ".html" and not p.stem.endswith("_public"):
        return p.with_name(p.stem + "_public.html").exists()
    return False
# A FILENAME, not a bare extension: requiring a filename character immediately before the
# extension keeps 'epoch=7-step=10800.weights.ckpt' matching while letting PROSE through --
# model_matrix legitimately says 'PRUNED (slim .weights.ckpt - no optimizer state)', which is
# science (why the field is empty), not plumbing. Third phantom-leak of 2026-08-09: a bare
# \.ckpt also matches JS property accesses (dataset.ckpt). Anchor, or the gate cries wolf and
# blocks every publish.
LEAK_RE = re.compile(r"/home/kim|/run/media|/scratch/|Mantu|epoch=\d+-step=|[\w=-]\.weights\.ckpt"
                     r"|dh_4txyt6|dreamhost|akekim|\.ssh/")


class Step:
    def __init__(self, name):
        self.name, self.ok, self.detail = name, False, ""

    def done(self, ok, detail=""):
        self.ok, self.detail = ok, detail
        print(f"  [{'OK ' if ok else 'FAIL'}] {self.name}: {detail}", flush=True)
        return self          # legs return the Step, not a bool


def run(cmd, **kw):
    """Run and return (rc, stdout+stderr). We never trust rc alone -- callers gate on artifacts."""
    p = subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True, text=True, **kw)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def db_counts(pattern):
    """(rows, with_ce, with_clap) for clips whose path matches the pattern."""
    if not DB.exists():
        return 0, 0, 0
    con = sqlite3.connect(DB)
    like = f"%{pattern}%"
    q = lambda w: con.execute(f"SELECT COUNT(*) FROM metrics WHERE path LIKE ?{w}", (like,)).fetchone()[0]
    try:
        return q(""), q(" AND ce IS NOT NULL"), q(" AND clap IS NOT NULL")
    finally:
        con.close()


def manifest_models(pattern):
    if not MANIFEST.exists():
        return []
    out = set()
    for ln in MANIFEST.read_text().splitlines():
        if ln.strip() and pattern in ln:
            try:
                out.add(json.loads(ln)["model"])
            except Exception:
                pass
    return sorted(out)


def scoped_manifest(pattern, dest):
    """A manifest containing only this campaign's non-native cells, for a scoped CLAP pass."""
    keep = [l for l in MANIFEST.read_text().splitlines()
            if l.strip() and pattern in l and '"duration_mode": "native"' not in l]
    dest.write_text("\n".join(keep) + "\n")
    return len(keep)


def http_len(url):
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=45) as r:
            return r.status, int(r.headers.get("content-length") or 0)
    except Exception as e:
        return 0, f"{e}"


# ---------------------------------------------------------------- legs

def leg_ingest(pattern, src, dry) -> Step:
    s = Step("ingest rendered clips")
    if not src:
        return s.done(True, "skipped (no --src; clips assumed already staged)")
    before = len(manifest_models(pattern))
    if dry:
        return s.done(True, f"DRY: would ingest from {src}")
    rc, out = run([SAO_PY, str(SAO / "eval/ingest_matrix_cells.py"), "--src", str(src),
                   "--only-prefix", pattern, "--rebuild"])
    after = manifest_models(pattern)
    # gate on the manifest, not rc
    return s.done(bool(after), f"{before} -> {len(after)} models in manifest"
                  + ("" if after else f" | rc={rc} {out[-200:]}"))


# Roots holding the rendered latents, keyed by the same stem as the clip: <stem>.z0.npy.
Z0_ROOTS = [Path("/run/media/kim/Mantu/sa3_lora_runs/model_matrix"),
            Path("/run/media/kim/Mantu/sa3_control_runs/model_matrix")]
Z0_STD_MAX = 2.0          # healthy global latent std is ~1.0; the drone runs away 1.3 -> 5.6 -> inf


OP_POINT_BAD_FRACTION_LIMIT = 0.20  # Kim 2026-08-15, see is_op_point() below


def is_op_point(e):
    """cfg7/w1 -- the real operating point everywhere except _ptm rows (cfg1/w1, their only
    native config; higher cfg 'cooks' them). Same cut dora_table.html's own default scoring
    narrowed to the same day (build_clap_hyperparam_table.py) -- what anyone actually
    auditions by default now."""
    is_ptm = str(e.get("model", "")).endswith("_ptm")
    cfg, w = e.get("cfg"), e.get("strength")
    return (cfg == 1 and w == 1) if is_ptm else (cfg == 7 and w == 1)


def leg_sanity(pattern, dry, skip) -> Step:
    """Refuse to score or publish audio decoded from blown-up latents.

    WHY THIS EXISTS: on 2026-08-10 a full run of this tool returned 4/4 GREEN on
    fullft_bigset -- 108 clips staged, 108 DSP rows, 108 CLAP scores -- while 59 of those
    108 clips had decoded from non-finite latents and were spectrally destroyed. Every step
    verified its own artifact and not one asked whether the audio was sane, so green meant
    COMPLETE, never GOOD. Worse than shipping nothing: a fully-scored row over corrupt audio
    reads as a training-recipe result, and someone then has to un-learn it.

    The check is CONTINUITY's own first diagnostic for the spectral drone -- load z0.npy,
    compare global std against ~1.0 -- applied per clip before anything downstream runs.

    Unverifiable is NOT the same as clean: if no latent is found for any clip the step FAILS
    rather than passing quietly. --skip-sanity is the deliberate escape hatch, so bypassing
    is a choice someone typed rather than a silence they never saw.

    SCOPE + TOLERANCE (Kim 2026-08-15, after the dronesweep batch tripped this at 177/432
    bad across the FULL cfg1/7/16 x w0.6-3 sweep): the ship/no-ship verdict now looks ONLY at
    cfg7/w1 (ptm: cfg1/w1) clips -- see is_op_point() -- and tolerates up to
    OP_POINT_BAD_FRACTION_LIMIT (20%) bad even within that subset, rather than failing on any
    single bad clip. Off-operating-point renders (cfg1/16, w0.6/1.5/2/3) are diagnostic sweep
    cells nobody audits by default anymore; a model unstable only out there shouldn't block a
    release that's fine where it's actually heard. The full-sweep audit is still written to
    the sidecar for visibility (a model that's fine at cfg7/w1 but disintegrating everywhere
    else is worth knowing), it just no longer gates the decision by itself.
    """
    s = Step("latent sanity (z0 std, cfg7/w1 operating point)")
    if skip:
        return s.done(True, "SKIPPED by --skip-sanity (nothing was checked)")
    if dry:
        return s.done(True, "DRY: skipped")
    try:
        import numpy as np
    except ImportError:
        return s.done(False, "numpy unavailable -- cannot verify, refusing to call it clean")

    matched = [e for e in (json.loads(l) for l in
               MANIFEST.read_text().splitlines() if l.strip())
               if e.get("model", "").startswith(pattern)]
    op_entries = [e for e in matched if is_op_point(e)]
    clips = [e["file"] for e in op_entries]
    if not clips:
        # "NOTHING TO CHECK" IS NOT "NOTHING IS WRONG". This returned True and let a run
        # proceed to scoring on 2026-08-13: leg_ingest had just staged 432 dronesweep clips
        # and appended 432 manifest lines, but the parent's MANIFEST.read_text() here did not
        # see them yet, so sanity matched zero clips, passed, and DSP + Audiobox then scored
        # all 432 -- including 177 decoded from blown-up or NaN latents. The gate that exists
        # precisely to stop that reported OK, for the second time in four days, by a different
        # route than the first. The same race also made leg_ingest report "0 -> 0 models".
        #
        # A pattern with no cfg7/w1 clips means one of: the ingest has not landed, the pattern
        # is wrong, or the manifest is stale -- none of which is evidence the audio is sane.
        # Fail, and say which one it looks like.
        staged = len(list(MATRIX.glob(f"{pattern}*.m4a")))
        return s.done(False, f"no cfg7/w1 (ptm: cfg1/w1) manifest clips match '{pattern}' "
                             f"({len(matched)} matched at other cfg/w, {staged} "
                             f"{pattern}*.m4a staged) -- the manifest has not caught up "
                             f"(re-run this step) or the pattern is wrong. Refusing to call "
                             f"unchecked audio sane."
                      if staged or matched else
                      f"no staged clips and no manifest clips match '{pattern}' -- nothing to "
                      f"verify, which is not the same as verified. Check the pattern.")

    def verdict(name):
        stem = name.rsplit(".", 1)[0]
        for root in Z0_ROOTS:
            p = root / f"{stem}.z0.npy"
            if p.exists():
                z = np.load(p, mmap_mode="r")
                a = np.asarray(z, dtype=np.float64)
                if not np.isfinite(a).all():
                    return {"file": name, "std": None, "bad": True, "why": "non-finite"}
                sd = float(a.std())
                return {"file": name, "std": sd, "bad": sd > Z0_STD_MAX,
                        "why": f"std {sd:.2f} > {Z0_STD_MAX}" if sd > Z0_STD_MAX else ""}
        return None                                     # no latent on disk for this clip

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(8) as ex:
        results = list(ex.map(verdict, clips))
    checked = [r for r in results if r]
    bad = [r for r in checked if r["bad"]]
    if not checked:
        # DRIVE-OFFLINE vs LATENTS-MISSING are different conditions and must not share a verdict.
        # Kim disconnects Mantu periodically (2026-08-12: to pull DAW project files). With the
        # drive unmounted every z0 lookup misses, and a naive "cannot verify" would block ALL
        # publishing for the duration -- turning a planned maintenance window into a total
        # outage of the publish path. That is a self-inflicted wound, not a safety property.
        roots_present = [r for r in Z0_ROOTS if r.exists()]
        if not roots_present:
            return s.done(True, f"latent roots UNREACHABLE ({Z0_ROOTS[0].parents[1]} not mounted?) "
                                f"-- sanity NOT CHECKED for {len(clips)} cfg7/w1 clips. Publishing "
                                f"anyway: an unmounted drive is an infrastructure state, not "
                                f"evidence about the audio. Re-run when the drive is back to get "
                                f"a real verdict.")
        return s.done(False, f"0 of {len(clips)} cfg7/w1 (ptm: cfg1/w1) clips have a z0.npy "
                             f"under {Z0_ROOTS[0].parent} (roots ARE mounted) -- cannot verify, "
                             f"refusing to call it clean (--skip-sanity to override)")
    bad_frac = len(bad) / len(checked)
    if bad:
        # Full-sweep audit for visibility, even on a pass -- a model fine at cfg7/w1 but
        # disintegrating at cfg16/high-w is a real finding, just not a blocking one anymore.
        side = MATRIX / f"{pattern}.latent_sanity.json"
        side.write_text(json.dumps(
            {"artifact": f"{pattern} latent-sanity audit (cfg7/w1 operating point)",
             "criterion": f"bad = non-finite OR global z0 std > {Z0_STD_MAX} (healthy ~1.0); "
                          f"ship/no-ship threshold = {OP_POINT_BAD_FRACTION_LIMIT:.0%} of this "
                          f"cfg7/w1-only subset",
             "summary": {"clips": len(clips), "checked": len(checked), "bad": len(bad),
                         "bad_fraction": round(bad_frac, 3)},
             "clips": sorted(checked, key=lambda r: r["file"])}, indent=1))
    if bad_frac > OP_POINT_BAD_FRACTION_LIMIT:
        return s.done(False, f"{len(bad)}/{len(checked)} ({bad_frac:.0%}) cfg7/w1 op-point "
                             f"clips decoded from blown-up latents, over the "
                             f"{OP_POINT_BAD_FRACTION_LIMIT:.0%} tolerance -- per-clip verdict "
                             f"written to {pattern}.latent_sanity.json; NOT scoring or "
                             f"publishing")
    return s.done(True, f"{len(checked)}/{len(clips)} cfg7/w1 op-point clips verified sane"
                  + (f", {len(bad)} bad ({bad_frac:.0%}, within the "
                     f"{OP_POINT_BAD_FRACTION_LIMIT:.0%} tolerance)" if bad else "")
                  + (f" ({len(clips)-len(checked)} had no latent on disk)"
                     if len(checked) < len(clips) else ""))


def leg_dsp(pattern, dry) -> Step:
    s = Step("DSP metering (CPU)")
    if dry:
        return s.done(True, "DRY: skipped")
    run([SAO_PY, str(SAO / "control/sa3_control/clip_metrics.py"),
         "--roots", "model_matrix", "--workers", "12"])
    rows, _, _ = db_counts(pattern)
    return s.done(rows > 0, f"{rows} rows in clip_metrics.db for '{pattern}'")


def leg_gpu(pattern, dry) -> Step:
    """Audiobox + CLAP, both scoped, both under the GPU mutex."""
    s = Step("Audiobox + CLAP (GPU)")
    if dry:
        return s.done(True, "DRY: skipped")
    rc, out = run(f'{shlex.quote(str(GUARD))} acquire WINTERMUTE $$')
    if rc != 0:
        return s.done(False, f"GPU busy, refusing to start -- {out.strip()[:120]}")
    try:
        run([MIR_PY, str(SAO / "control/sa3_control/clip_metrics_audiobox.py"),
             "--roots", "model_matrix", "--pattern", pattern, "--batch", "8"])
        tmp = Path("/tmp") / f"clapscope_{pattern.replace('/', '_')}.jsonl"
        n = scoped_manifest(pattern, tmp)
        env = dict(os.environ, FLASH_ATTENTION_TRITON_AMD_ENABLE="FALSE")
        run([SAO_PY, str(SAO / "eval/clap_score.py"), "--manifest", str(tmp),
             "--clips-dir", str(MATRIX), "--sample", "0", "--device", "cuda",
             "--write-db", "--append", "--out", str(CLAP_SCAN)], env=env)
    finally:
        run(f'{shlex.quote(str(GUARD))} release WINTERMUTE $$')
    rows, ce, clap = db_counts(pattern)
    return s.done(ce > 0 and clap > 0, f"{rows} rows | ce {ce} | clap {clap}"
                  " (nonzero rc from ROCm teardown is expected and ignored)")


def leg_tables(pattern, dry) -> Step:
    s = Step("rebuild aggregate + boards")
    if dry:
        return s.done(True, "DRY: skipped")
    run([SAO_PY, str(SAO / "eval/build_clap_hyperparam_table.py")])
    run([SAO_PY, str(SAO / "eval/build_dora_table_page.py")])
    run(["python3", str(SAO / "Misc/build_model_matrix.py")])
    # evaluator.html's own pre-filtered manifest (Kim 2026-08-16, "I can perform periodic
    # updates then, it does not have to be dynamic") -- must run AFTER build_clap_hyperparam_
    # table.py, which is what writes scored_models_avp.json this script reads. Non-fatal by
    # design (matches the rest of this leg): a stale/missing evaluator manifest degrades that
    # one public page, it doesn't block scoring or publishing everything else.
    run([SAO_PY, str(SAO / "eval/build_evaluator_manifest.py")])
    agg = AGG.read_text() if AGG.exists() else ""
    models = manifest_models(pattern)
    in_agg = [m for m in models if m in agg]
    dora = (SAO / "eval/dora_table.html")
    in_page = [m for m in models if dora.exists() and m in dora.read_text()]
    ok = bool(models) and bool(in_agg) and bool(in_page)
    return s.done(ok, f"{len(in_agg)}/{len(models)} models in aggregate, "
                      f"{len(in_page)}/{len(models)} rendered into dora_table")


def leg_publish(pattern, dry) -> Step:
    s = Step("publish + verify over HTTP")
    # 1. what genuinely differs -- read itemize flags, never a raw file list
    #
    # manifest_live.jsonl NEVER MATCHED '*.json' (rsync/shell globs are literal suffix match --
    # "jsonl" does not end in "json"), so it silently never appeared in this dry-run diff, never
    # landed in `todo` below, and never reached step 3's --files-from upload. Found 2026-08-13:
    # dora_table.html's origin Last-Modified for manifest_live.jsonl was three days stale (Aug
    # 10) despite this leg reporting success on every publish since -- every dronesweep/subloss
    # clip on disk was real and correctly staged, but the client-side index that resolves a
    # click to a file was reading a snapshot from before any of tonight's work existed. The
    # symptom (rows dimmed grey, clicks producing no audio) looked exactly like a broken
    # resolver; it was an upload filter silently dropping the one file the resolver reads.
    #
    # ...and the mirror-image problem, found by THE-FINN's live-tree sweep 2026-08-17: '*.jsonl'
    # also matched `manifest.jsonl`, the PRE-native-ingest index that only LOCAL generators read
    # (model_matrix_gen.py, ingest_native_cells.py, Misc/build_model_matrix.py). Not one served
    # page fetches it -- every one of them reads manifest_live.jsonl -- so it was 24.9MB of
    # publicly-fetchable dead weight, re-uploaded on every publish, right after the 08-16 change
    # whose entire point was to stop shipping a 24.5MB index to visitors. Excluded BEFORE the
    # '*.jsonl' include because rsync takes the FIRST matching rule. It stays in the staging dir
    # (the local generators need it); it just no longer travels.
    cmd = (f"rsync -rvzn --itemize-changes --include='*/' --include='*.html' --include='*.json' "
           f"--exclude='manifest.jsonl' --exclude='*.bak_*' --exclude='*.bak-*' "
           f"--include='*.jsonl' --include='*.m4a' --include='*.flac' --exclude='*' "
           f"-e {shlex.quote(SSH)} "
           f"{shlex.quote(str(STAGE) + '/')} {shlex.quote(HOST + ':' + HOST_EVALS)}")
    rc, out = run(cmd)                       # stderr NOT silenced: a failure must not look empty
    if rc != 0:
        return s.done(False, f"diff failed rc={rc}: {out.strip().splitlines()[-1][:120] if out.strip() else 'no output'}")
    new, changed, timeonly = [], [], 0
    for ln in out.splitlines():
        if not ln.startswith("<f"):
            continue
        flags, _, name = ln.partition(" ")
        name = name.strip()
        if "+++" in flags:
            new.append(name)
        elif "s" in flags[3:]:
            changed.append(name)
        else:
            timeonly += 1
    todo = [f for f in new + changed if not is_local_only(f)]
    held = len(new) + len(changed) - len(todo)
    if not todo:
        return s.done(True, f"host already current ({timeonly} timestamp-only, "
                            f"{held} local-only sidecars withheld)")
    # 2. leak-scan every text artefact before it leaves the box
    leaks = []
    for f in todo:
        p = STAGE / f
        if p.suffix in (".html", ".json") and p.exists():
            hits = LEAK_RE.findall(p.read_text(errors="ignore"))
            if hits:
                leaks.append(f"{f} -> {sorted(set(hits))[:3]}")
    if leaks:
        return s.done(False, f"LEAK, refusing to publish: {leaks[:3]}")
    if dry:
        return s.done(True, f"DRY: would push {len(new)} new + {len(changed)} changed "
                            f"({timeonly} mtime-only, {held} local-only sidecars withheld)")
    # 3. push exactly that list
    lst = Path("/tmp") / f"publish_{pattern.replace('/', '_')}.txt"
    lst.write_text("\n".join(todo) + "\n")
    rc, out = run(f"rsync -az --chmod=F644 --files-from={shlex.quote(str(lst))} "
                  f"-e {shlex.quote(SSH)} {shlex.quote(str(STAGE) + '/')} "
                  f"{shlex.quote(HOST + ':' + HOST_EVALS)}")
    if rc != 0:
        return s.done(False, f"rsync rc={rc}: {out.strip()[-160:]}")
    # 4. verify the ARTIFACT: sample real files and compare bytes, not status codes alone
    random.seed(11)
    sample = random.sample(todo, min(4, len(todo)))
    bad = []
    for f in sample:
        st, ln = http_len(PUBLIC + f)
        local = (STAGE / f).stat().st_size
        if st != 200 or ln != local:
            bad.append(f"{f} (http {st}, {ln} vs {local})")
    return s.done(not bad, f"pushed {len(new)} new + {len(changed)} changed, "
                           f"{timeonly} mtime-only + {held} sidecars withheld; sampled {len(sample)} verified"
                  + (f" | MISMATCH {bad}" if bad else ""))


def main():
    ap = argparse.ArgumentParser(description="Score and publish a campaign's clips (legs b+c).")
    ap.add_argument("--pattern", required=True,
                    help="campaign/model substring. REQUIRED: an unscoped pass drags in the "
                         "board-wide metering backlog instead of what you just trained.")
    ap.add_argument("--src", type=Path, help="ingest freshly rendered/pulled clips from here first")
    ap.add_argument("--skip-gpu", action="store_true", help="DSP + tables only (no Audiobox/CLAP)")
    ap.add_argument("--no-publish", action="store_true", help="stop after the tables (local only)")
    ap.add_argument("--dry-run", action="store_true", help="preflight + plan, write nothing")
    ap.add_argument("--skip-sanity", action="store_true",
                    help="bypass the latent-sanity gate (deliberate override; the gate is "
                         "what stops corrupt audio being scored and published as if it were good)")
    a = ap.parse_args()

    print(f"[score+publish] pattern={a.pattern!r} dry={a.dry_run}", flush=True)
    if not MANIFEST.exists():
        sys.exit(f"[fatal] no manifest at {MANIFEST} -- is the eval drive mounted?")

    steps = [leg_ingest(a.pattern, a.src, a.dry_run),
             leg_sanity(a.pattern, a.dry_run, a.skip_sanity)]
    if not steps[-1].ok:                       # corrupt or unverifiable -> stop before scoring
        print(f"\n[score+publish] halted at '{steps[-1].name}' -- nothing scored, nothing published")
        for st in steps:
            print(f"  [{'OK ' if st.ok else 'FAIL'}] {st.name}: {st.detail}")
        sys.exit(1)
    steps.append(leg_dsp(a.pattern, a.dry_run))
    if not a.skip_gpu:
        steps.append(leg_gpu(a.pattern, a.dry_run))
    steps.append(leg_tables(a.pattern, a.dry_run))
    if not a.no_publish:
        steps.append(leg_publish(a.pattern, a.dry_run))

    failed = [s.name for s in steps if not s.ok]
    print(f"\n[score+publish] {len(steps)-len(failed)}/{len(steps)} steps passed their artifact gate")
    if failed:
        print(f"[score+publish] FAILED: {failed}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
