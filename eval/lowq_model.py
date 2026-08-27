#!/usr/bin/env python
"""Low-quality clip scorer -- writes `lowq_p` into clip_metrics.db.

WHY THIS EXISTS (Kim, 2026-08-27). The shipped PQ<3.5 floor was a NO-OP: it caught 0 of
the 90 clips Kim rated 0, because the worst clip he has ever rated 0 scores PQ 4.16.
Corpus-wide it dropped 2 clips of 105717. The metric was not the problem -- PQ is
monotonic across all six rating buckets (Spearman +0.564, AUC 0.884) -- the THRESHOLD
was. Multi-feature does better still: AUC 0.929 on the 12 metrics columns.

WHAT IT PREDICTS: p(Kim rates this 0 or 1). Not "quality" in the abstract -- it learns
ONE rater's taste on the CURRENT pool from 230 negative examples. It will drift as the
corpus changes. Refit after a few hundred more ratings; say so anywhere it is surfaced.

THE OPERATING POINT is Kim's, and his re-cut is what made it work. Protecting everything
rated 2+ gave a bad tradeoff; he said protect 3+, and the rating-2 clips then absorb most
of the collateral (46% of them flagged, which is fine -- they are the mediocre middle):

    recall | 3+ flagged | 4-5 flagged | corpus-wide flag rate
      75%  |  3/498  0.6% |  0/290  0.0% |  32.4%
      80%  |  7/498  1.4% |  0/290  0.0% |  38.4%
      85%  | 19/498  3.8% |  5/290  1.7% |  43.8%   <-- SHIPPED
      90%  | 50/498 10.0% | 19/290  6.6% |  55.7%

    NOTE these are the DEDUPED numbers (one rating per clip, last wins). An earlier pass
    counted repeat ratings of the same clip and made 90% look like 7.2% of 3+; deduped it
    is 10.0%, i.e. exactly AT Kim's 10% budget rather than inside it. 85% was chosen for
    the margin: it costs 3.8% of his 3+ and 1.7% of his 4-5s.

    The corpus-wide flag rate is high at every setting because the corpus is not the
    evaluator pool -- it holds every sweep cell and collapsed-model render, while Kim's
    ratings come from a pool already curated to decent models. Flagged clips average
    PQ 6.57 against 7.92 for kept, which tracks his rating-1 and rating-4 means, so the
    split is coherent rather than arbitrary. Apply this to the EVAL POOL; do not read the
    corpus figure as "half our renders are broken"

Do NOT chase 95%. It falls off a cliff, and that cliff is exactly the "clip I scored high
that has anomalous features" case -- at 95% you lose 1 in 6 of his favourites.

FLAG, DO NOT DELETE (Kim, explicit). Clips and rows stay queryable forever; only the eval
POOL filters. His reason: we may want to analyse the collapsed/degenerate models later and
there may be something meaningful in the dead models and latents. Storing a PROBABILITY
rather than a filename list is the same principle one level down -- a stored p is
re-thresholdable without refitting and is itself the signal that analysis would need. An
exclusion list would throw it away.

BOUNDARY NOTE: --ratings takes a LOCAL path and this script never fetches anything. The
ratings endpoint is write-only to agents by standing rule (MASTER section 4); pulling the
export needs Kim's explicit authorisation each time, and keeping the fetch OUT of this
script keeps that decision where it belongs -- with him, not in a cron.

    python eval/lowq_model.py --ratings <local.jsonl> --fit     # refit + score all
    python eval/lowq_model.py --score-only                      # rescore from saved model
"""
from __future__ import annotations
import argparse, json, os, pickle, sqlite3, sys
from pathlib import Path

import numpy as np

DB = Path(__file__).parent / "clip_metrics.db"
MODEL = Path(__file__).parent / "lowq_model.pkl"
# Plain-JSON twin of the pickle's non-model fields. G 2026-08-27: unpickling needs
# sklearn even just to read the threshold float, and SAO venv (1.9.0) cannot load what
# mir venv (1.8.0) wrote (_loss module mismatch). Consumers need the THRESHOLD, not the
# model, so they must never have to import sklearn -- or unpickle across venvs -- to get
# it. Written on every fit so it cannot drift from the pickle it describes.
META = Path(__file__).parent / "lowq_model_meta.json"
FEATURES = ['dur','rms','crest','zcr','onset_p95','centroid','flatness','flux',
            'hf_ratio','ce','pq','cu']
TARGET_RECALL = 0.85          # catch this fraction of rating<=1; see table above


def load_ratings(path):
    """-> {basename: rating}. Last rating per clip wins (Kim may re-rate)."""
    out = {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                o = json.loads(line)
            except Exception:
                continue
            if o.get("type") != "enjoyment":
                continue
            f, r = o.get("file"), o.get("rating")
            if f is None or r is None:
                continue
            try:
                out[os.path.basename(str(f))] = int(r)
            except Exception:
                continue
    return out


def feature_rows(conn):
    cols = ",".join(FEATURES)
    q = f"select path,{cols} from metrics where " + " and ".join(f"{c} is not null" for c in FEATURES)
    paths, X = [], []
    for row in conn.execute(q):
        paths.append(row[0])
        X.append([float(v) for v in row[1:]])
    return paths, np.asarray(X, dtype=float)


def fit(ratings_path):
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.model_selection import StratifiedKFold, cross_val_predict
    from sklearn.metrics import roc_auc_score

    ratings = load_ratings(ratings_path)
    conn = sqlite3.connect(DB)
    paths, Xall = feature_rows(conn)
    idx = [i for i, p in enumerate(paths) if os.path.basename(p) in ratings]
    if len(idx) < 100:
        sys.exit(f"only {len(idx)} rated clips joined -- refusing to fit on that")
    X = Xall[idx]
    rat = np.array([ratings[os.path.basename(paths[i])] for i in idx])
    y = (rat <= 1).astype(int)
    print(f"[fit] {len(y)} rated clips joined  bad(0-1)={y.sum()}  protected(3+)={(rat>=3).sum()}")

    cv = StratifiedKFold(5, shuffle=True, random_state=0)
    oof = cross_val_predict(GradientBoostingClassifier(random_state=0), X, y, cv=cv,
                            method="predict_proba")[:, 1]
    print(f"[fit] cross-validated AUC {roc_auc_score(y, oof):.3f}")

    # Threshold from OUT-OF-FOLD predictions, never from the fitted model's own training
    # scores -- in-sample probabilities are optimistic and would silently set a threshold
    # that flags far more than intended once applied to unseen clips.
    thr = float(np.quantile(oof[y == 1], 1.0 - TARGET_RECALL))
    prot, hi = rat >= 3, rat >= 4
    fp, fphi = int(((oof >= thr) & prot).sum()), int(((oof >= thr) & hi).sum())
    print(f"[fit] threshold {thr:.4f} -> catches {int(TARGET_RECALL*100)}% of 0/1; "
          f"flags {fp}/{prot.sum()} ({100*fp/prot.sum():.1f}%) of 3+, "
          f"{fphi}/{hi.sum()} ({100*fphi/hi.sum():.1f}%) of 4-5")

    model = GradientBoostingClassifier(random_state=0).fit(X, y)
    meta = {"threshold": thr, "target_recall": TARGET_RECALL, "features": FEATURES,
            "n_train": int(len(y)), "n_bad": int(y.sum()),
            "cv_auc": float(roc_auc_score(y, oof)), "sklearn_venv": "mir"}
    MODEL.write_bytes(pickle.dumps({"model": model, **meta}))
    META.write_text(json.dumps(meta, indent=1))
    print(f"[fit] saved {MODEL}")
    print(f"[fit] saved {META} (sklearn-free; this is what consumers read)")
    return model, thr


def score(model=None, thr=None):
    if model is None:
        if not MODEL.exists():
            sys.exit(f"no saved model at {MODEL} -- run with --fit first")
        blob = pickle.loads(MODEL.read_bytes())
        model, thr = blob["model"], blob["threshold"]
        if blob["features"] != FEATURES:
            sys.exit("saved model's feature list differs from this file's -- refit")
    conn = sqlite3.connect(DB)
    cols = {r[1] for r in conn.execute("pragma table_info(metrics)")}
    if "lowq_p" not in cols:                       # additive, non-destructive
        conn.execute("alter table metrics add column lowq_p real")
        conn.commit()
        print("[score] added column lowq_p")
    paths, X = feature_rows(conn)
    p = model.predict_proba(X)[:, 1]
    conn.executemany("update metrics set lowq_p=? where path=?",
                     [(float(a), b) for a, b in zip(p, paths)])
    conn.commit()
    n_flag = int((p >= thr).sum())
    print(f"[score] wrote lowq_p for {len(paths)} clips; "
          f"{n_flag} ({100*n_flag/len(paths):.1f}%) at or above threshold {thr:.4f}")
    print(f"[score] clips with NULL lowq_p (missing features): "
          f"{conn.execute('select count(*) from metrics where lowq_p is null').fetchone()[0]}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ratings", help="LOCAL ratings jsonl (see BOUNDARY NOTE above)")
    ap.add_argument("--fit", action="store_true", help="refit the model, then score")
    ap.add_argument("--score-only", action="store_true", help="score from the saved model")
    a = ap.parse_args()
    if a.fit:
        if not a.ratings:
            sys.exit("--fit needs --ratings")
        score(*fit(a.ratings))
    elif a.score_only:
        score()
    else:
        ap.error("pass --fit or --score-only")
