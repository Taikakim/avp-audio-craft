#!/usr/bin/env python3
"""build_evaluator_manifest.py -- pre-filter the shared manifest down to what evaluator.html
actually needs, at BUILD time instead of on every visitor's device (Kim 2026-08-16: "I can
perform periodic updates then, it does not have to be dynamic").

WHY THIS EXISTS: evaluator.html used to fetch manifest_live.jsonl directly -- the shared
index over the ENTIRE model_matrix corpus (every campaign, every model, every cfg x strength
x prompt x length combo), 24.5MB / ~71,700 lines at last measure -- then filter it down,
client-side, in every visitor's browser, to the tiny slice it actually uses: cfg7/w1 (or
cfg1/w1 for _ptm rows) clips from the ~68 avp-dataset scored models. On a slow mobile
connection that download alone was legitimately taking minutes, before a byte of the actual
~70k-line JSON-parse work even started. This script does that filtering ONCE, here, and
evaluator.html fetches the small result instead.

Run as part of score_and_publish.py's leg_tables() (the same table-rebuild step Kim already
runs periodically), right after build_clap_hyperparam_table.py -- which is what actually
determines the avp-scored model set (scored_models_avp.json) this script reads.

Not real-time: the output is a static file, refreshed only when this script re-runs. That is
the whole point -- it lets evaluator.html drop `cache:'no-store'` and let the browser's normal
HTTP cache do its job, since staleness between periodic rebuilds is an accepted tradeoff here
(unlike the live internal boards, which need every visit to reflect the latest scoring pass).
"""
import datetime
import json
import sqlite3
from pathlib import Path

STAGE_MATRIX = Path.home() / "evals_aac" / "model_matrix"
MANIFEST = STAGE_MATRIX / "manifest_live.jsonl"
SCORED_AVP = STAGE_MATRIX / "scored_models_avp.json"
OUT = STAGE_MATRIX / "manifest_avp_evaluator.json"
LOWQ_FLAGGED_OUT = STAGE_MATRIX / "lowq_flagged.json"
CLIP_DB = Path(__file__).resolve().parent / "clip_metrics.db"
LOWQ_META = Path(__file__).resolve().parent / "lowq_model_meta.json"

# Kim direct 2026-08-25/27: a flat PQ<3.5 floor turned out to be a NO-OP -- it caught 0 of
# the 90 clips Kim rated 0 (his worst-ever 0-rated clip scores PQ 4.16), 2 of 105717 corpus-
# wide. The METRIC was fine (Spearman +0.564 vs his own ratings) -- the flat THRESHOLD was
# not. WINTERMUTE's eval/lowq_model.py replaces it: a gradient-boosted classifier over 12
# metrics columns (incl. pq), fit on Kim's own 0/1 vs 5-scale ratings, threshold picked at
# his chosen operating point (85% recall on rating<=1, costing 3.8% of his 3+ and 1.7% of
# his 4-5s -- see that file's docstring for the full recall/cost table). lowq_model_meta.json
# is a plain-JSON sidecar of the pickle's non-model fields (threshold etc.) so this script
# never needs to unpickle a GradientBoostingClassifier -- sklearn-version-fragile, and
# pointless when all this needs is one float.
#
# FLAG, DO NOT DELETE (Kim, explicit, verbatim reason: may want to analyse the collapsed/
# degenerate models later, there may be something meaningful in the dead latents). Nothing
# is dropped from clip_metrics.db or from manifest_avp_evaluator.json here -- only a
# filename list ships, which evaluator.html filters against client-side, respecting
# ?showflagged=1 to bring them back reachable. A server-side drop (the old PQ-floor's
# approach) can't offer that toggle without a second manifest build.


def load_lowq_flagged():
    """(threshold, {filename}) -- filenames whose lowq_p >= the shipped model's threshold,
    scored corpus-wide. Basename-keyed (what manifest rows carry as `file`) since
    clip_metrics.db stores full STAGE_MATRIX paths."""
    if not CLIP_DB.exists() or not LOWQ_META.exists():
        print(f"[evaluator-manifest] WARNING: missing {CLIP_DB} or {LOWQ_META} -- "
              f"low-quality flag cannot be applied, every clip passes")
        return None, set()
    thr = json.loads(LOWQ_META.read_text())["threshold"]
    con = sqlite3.connect(CLIP_DB)
    out = {Path(p).name for (p,) in con.execute(
        "SELECT path FROM metrics WHERE lowq_p >= ?", (thr,))}
    con.close()
    return thr, out

# Exactly the fields evaluator.html's loadManifest()/lengthBucket()/eligible() read off each
# entry -- dropping prompt_text, seed, and everything else the full manifest carries but this
# page never touches is most of the size win (prompt_text alone is often longer than every
# other field on the line combined).
NOW = datetime.datetime.now().timestamp()

FIELDS = ("model", "ckpt", "cfg", "strength", "file", "prompt_id", "duration_mode", "duration")

# Plus one derived field the full manifest does NOT carry: `age_h`, the clip file's age in hours
# at build time, rounded. It exists so evaluator.html can offer ?recent=<hours> -- Kim
# 2026-08-18: "only for checkpoints that we have been pulling in the last, like, forty eight
# hours ... it's nice for [visitors] not to have to listen to mostly [old] clips". Stored as an
# AGE rather than an absolute mtime deliberately: the page compares it to a number the visitor
# typed, so a value that is meaningful without knowing when the manifest was built is the one
# that cannot be misread. It does go stale between rebuilds -- a manifest built 3 days ago will
# report everything as 3 days younger than it is -- which is why build_time_iso is written
# alongside, so a reader can tell how much to distrust it.


def is_op_point(e):
    """Same cut as everywhere else this session: cfg7/w1, or cfg1/w1 for the model's own
    _ptm rows (their only native, non-glitchy config)."""
    is_ptm = str(e.get("model", "")).endswith("_ptm")
    cfg, w = e.get("cfg"), e.get("strength")
    return (cfg == 1 and w == 1) if is_ptm else (cfg == 7 and w == 1)


def main():
    if not MANIFEST.exists():
        raise SystemExit(f"[evaluator-manifest] no manifest at {MANIFEST} -- is the eval drive mounted?")
    if not SCORED_AVP.exists():
        raise SystemExit(f"[evaluator-manifest] no {SCORED_AVP} -- run build_clap_hyperparam_table.py first")

    scored = set(json.loads(SCORED_AVP.read_text()))

    # WINTERMUTE 2026-08-27: every refit of lowq_model.py moves the threshold (0.1514 -> 0.1355
    # on the very first refit after this shipped), so a flag list built before a refit silently
    # disagrees with the sidecar describing the model that actually produced it -- a rebuild
    # made stale by someone else's unrelated work, with no signal that it happened. Stamping the
    # threshold this build used INTO the output lets the page compare it against the current
    # sidecar and complain on mismatch instead of silently filtering on a stale cut.
    lowq_thr, lowq_flagged = load_lowq_flagged()
    LOWQ_FLAGGED_OUT.write_text(json.dumps({"threshold": lowq_thr, "flagged": sorted(lowq_flagged)}))
    print(f"[evaluator-manifest] wrote {LOWQ_FLAGGED_OUT} ({len(lowq_flagged)} filenames "
          f"flagged low-quality at threshold {lowq_thr}, corpus-wide -- FLAGGED, not dropped; "
          f"evaluator.html filters client-side, ?showflagged=1 shows them anyway)")

    # PQ values (for ?pq=<tolerance%> percentile-matched pairing, unrelated to the quality
    # flag above) -- keyed on the .m4a basename (what manifest rows carry as `file`), since
    # clip_metrics.db stores full STAGE_MATRIX paths.
    con = sqlite3.connect(CLIP_DB) if CLIP_DB.exists() else None
    pq_by_file = ({Path(p).name: pq for p, pq in
                   con.execute("SELECT path, pq FROM metrics WHERE pq IS NOT NULL")}
                  if con else {})
    if con:
        con.close()

    # Kim direct 2026-08-26: PQ-matched pairing (evaluator.html ?pq=<tolerance%>) needs the
    # actual PQ VALUE per clip, not just the below-floor boolean above. Scope to op-point-
    # eligible files only (cfg7/w1, or cfg1/w1 for _ptm) -- the same eligible() cut the client
    # already applies -- so this stays a join table over what can actually get paired, not a
    # dump of the whole 102k+-row DB (most of which is off-grid cfg/strength sweep cells no
    # evaluator pool ever surfaces). Corpus-wide (not avp-scoped): ?pq= is meant to work under
    # both ?goa=1 and the default avp pool.
    eligible_files = set()
    for ln in MANIFEST.read_text().splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            e = json.loads(ln)
        except Exception:
            continue
        if is_op_point(e):
            eligible_files.add(str(e.get("file") or ""))
    pq_by_file_out = {f: pq for f, pq in pq_by_file.items() if f in eligible_files}
    (STAGE_MATRIX / "pq_by_file.json").write_text(json.dumps(pq_by_file_out))
    print(f"[evaluator-manifest] wrote {STAGE_MATRIX / 'pq_by_file.json'} "
          f"({len(pq_by_file_out)} eligible-file PQ values)")

    # No quality filtering here anymore -- every op-point-eligible avp row ships, flagged or
    # not (see the FLAG, DO NOT DELETE note above). evaluator.html applies lowq_flagged.json
    # client-side, same as the ?pq=/?crossds= pairing constraints, so ?showflagged=1 can
    # bring them back without a second manifest build.
    out = []
    for ln in MANIFEST.read_text().splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            e = json.loads(ln)
        except Exception:
            continue
        if e.get("model") not in scored:
            continue
        if not is_op_point(e):
            continue
        row = {k: e.get(k) for k in FIELDS}
        clip = STAGE_MATRIX / str(e.get("file") or "")
        try:
            row["age_h"] = round((NOW - clip.stat().st_mtime) / 3600.0, 1)
        except OSError:
            row["age_h"] = None      # clip not staged locally -- ?recent= will exclude it
        out.append(row)

    OUT.write_text(json.dumps({"build_time_iso": datetime.datetime.now().isoformat(timespec="seconds"),
                               "entries": out}))
    size = OUT.stat().st_size
    print(f"[evaluator-manifest] wrote {OUT}  ({len(out)} entries from {len(scored)} avp "
          f"models, {size:,} bytes -- was {MANIFEST.stat().st_size:,} bytes unfiltered)")


if __name__ == "__main__":
    main()
