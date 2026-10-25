#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-10-25)
"""latch_film_e18_report.py -- EXPERIMENTS E18 numbers from the finished renders (no GPU, no re-render).

Reads OUT/cells.jsonl (measured onsets/s per clip), OUT/clap.json (CLAP drift to the same context+seed unguided render)
and clip_metrics.db (texture + Audiobox, scored from the 192k AAC copies) and writes OUT/report.json + a text table:
  per arm   onsets/s at density 3/6/9 (mean over contexts x seeds), range d9-d3, CLAP drift, gate fails vs unguided
  A2 vs A3  paired texture deltas (the hard-stop question: does the exp tail change what the hard end leaves behind)
  A6        does a real onsets-per-beat curve transfer: corr of the render's local onset rate with the target curve,
            against the constant-at-the-mean arm (same seed) as the null
The disintegration gate is control_head_disintegration_eval.gate(), unchanged thresholds.
RUN: mir/bin/python eval/latch_film_e18_report.py      (mir venv: librosa for the A6 onset-rate curve)
"""
import json
import os
import sqlite3
import statistics as st
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from control_head_disintegration_eval import DB, gate  # noqa: E402

OUT = "/run/media/kim/Mantu/sa3_control_runs/latch_film_e18_20261025"
AAC = os.path.expanduser("~/evals_aac/latch_film_e18")
ARMS = ("film", "A1", "A2", "A3", "A4a", "A4b", "A4c", "A5")
BPM = {"base": 140.0, "house": 122.0}
TEX = ("rms", "crest", "flatness", "hf_ratio", "zcr", "centroid", "ce", "pq")


def metrics():
    db = sqlite3.connect(DB)
    cols = [r[1] for r in db.execute("PRAGMA table_info(metrics)").fetchall()]
    rows = db.execute(f"select {','.join(cols)} from metrics where path like ?", (f"%{AAC}/%",)).fetchall()
    return {os.path.basename(d["path"]).rsplit(".", 1)[0]: d for d in (dict(zip(cols, r)) for r in rows)}


def local_rate(wav, fps, n):
    """Onsets/s over time: onset times -> 2 s boxcar count, sampled on n frames at fps."""
    import librosa
    import numpy as np
    y, sr = librosa.load(wav, sr=None, mono=True)
    on = librosa.onset.onset_detect(y=y, sr=sr, units="time")
    t = (np.arange(n) + 0.5) / fps
    return np.array([((on > x - 1.0) & (on <= x + 1.0)).sum() / 2.0 for x in t])


def main():
    import numpy as np
    rows = [json.loads(l) for l in open(f"{OUT}/cells.jsonl") if l.strip()]
    drift = json.load(open(f"{OUT}/clap.json"))["drift"]
    M = metrics()
    base = {(c["ctx"], c["seed"]): M.get(c["id"]) for c in rows if c["arm"] == "unguided"}
    missing = [c["id"] for c in rows if c["id"] not in M]
    if missing:
        print(f"WARNING {len(missing)} cells without clip_metrics rows, e.g. {missing[:3]}")

    per = defaultdict(lambda: defaultdict(list))
    fails = defaultdict(list)
    for c in rows:
        if c["arm"] not in ARMS:
            continue
        m, b = M.get(c["id"]), base.get((c["ctx"], c["seed"]))
        per[c["arm"]][c["dens"]].append(c["onsets"])
        per[c["arm"]]["drift"].append(drift[c["id"]])
        per[c["arm"]]["ce"].append(m["ce"] - b["ce"])
        bad, why, _ = gate(m, b, rhythmic=True)
        if bad:
            fails[c["arm"]].append(f"{c['id']}: {', '.join(why)}")

    unguided = {f"{k[0]}_s{k[1]}": next(c["onsets"] for c in rows if c["arm"] == "unguided"
                                        and (c["ctx"], c["seed"]) == k) for k in base}
    seed_ref = json.load(open(f"{OUT}/clap.json"))["seed_reference"]
    table = {}
    print(f"unguided onsets/s {unguided}; CLAP seed reference (unguided seed A vs seed B) {seed_ref}\n")
    print(f"{'arm':6s} {'d3':>5s} {'d6':>5s} {'d9':>5s} {'range':>6s} {'drift':>6s} {'dCE':>6s}  gate")
    for a in ARMS:
        d = per[a]
        r = {k: round(st.mean(d[k]), 2) for k in (3, 6, 9)}
        rng = [x9 - x3 for x3, x9 in zip(d[3], d[9])]
        table[a] = dict(onsets=r, range=round(st.mean(rng), 2), range_each=[round(x, 2) for x in rng],
                        clap_drift=round(st.mean(d["drift"]), 4), clap_drift_max=round(max(d["drift"]), 4),
                        dce=round(st.mean(d["ce"]), 2), gate_fail=len(fails[a]), gate_n=len(d["drift"]),
                        gate_reasons=fails[a])
        print(f"{a:6s} {r[3]:5.2f} {r[6]:5.2f} {r[9]:5.2f} {table[a]['range']:6.2f} {table[a]['clap_drift']:6.3f} "
              f"{table[a]['dce']:+6.2f}  {len(fails[a])}/{len(d['drift'])}")

    # A2 (hard end at 0.8) vs A3 (same weights to 0.8 + exp tail) vs A1, paired by context/seed/density
    pair = defaultdict(list)
    for c in rows:
        if c["arm"] != "A2":
            continue
        k = c["id"].replace("__A2_", "__{}_")
        m2, m3, m1 = M[c["id"]], M[k.format("A3")], M[k.format("A1")]
        for f in TEX:
            pair[f"{f} A3-A2"].append(m3[f] - m2[f])
            pair[f"{f} A2-A1"].append(m2[f] - m1[f])
        pair["onsets A3-A2"].append(next(x["onsets"] for x in rows if x["id"] == k.format("A3")) - c["onsets"])
        pair["drift A3-A2"].append(drift[k.format("A3")] - drift[c["id"]])
    hard = {k: dict(mean=round(st.mean(v), 4), n_pos=sum(x > 0 for x in v), n=len(v)) for k, v in sorted(pair.items())}
    print("\nA2 hard end vs A3 exp tail vs A1 (paired, 12 each): mean delta, #positive")
    for k, v in hard.items():
        print(f"  {k:18s} {v['mean']:+.4f}  {v['n_pos']}/{v['n']}")

    # A6: real curve vs constant at its mean
    cur = json.load(open(f"{OUT}/real_curve.json"))
    fps = 44100 / 4096
    a6 = {}
    for c in rows:
        if c["arm"] != "A6curve":
            continue
        tgt = np.array(cur["curve"]) * BPM[c["ctx"]] / 60.0   # onsets per beat -> per second
        n = len(tgt)
        rc = local_rate(f"{OUT}/{c['ctx']}/{c['id']}.wav", fps, n)
        rk = local_rate(f"{OUT}/{c['ctx']}/{c['id'].replace('A6curve', 'A6const')}.wav", fps, n)
        ru = local_rate(f"{OUT}/{c['ctx']}/{c['ctx']}_s{c['seed']}__unguided.wav", fps, n)
        cc = lambda x: round(float(np.corrcoef(x, tgt)[0, 1]), 3)
        a6[f"{c['ctx']}_s{c['seed']}"] = dict(corr_curve=cc(rc), corr_const=cc(rk), corr_unguided=cc(ru),
                                              mean_curve=round(float(rc.mean()), 2), mean_const=round(float(rk.mean()), 2),
                                              target_mean=round(float(tgt.mean()), 2),
                                              drift_curve=drift[c["id"]], drift_const=drift[c["id"].replace("A6curve", "A6const")])
    print("\nA6 real curve: corr(local onset rate, target curve) for curve / constant-at-mean / unguided")
    for k, v in a6.items():
        print(f"  {k:12s} {v['corr_curve']:+.3f} / {v['corr_const']:+.3f} / {v['corr_unguided']:+.3f}   "
              f"mean on/s {v['mean_curve']} vs const {v['mean_const']} (target {v['target_mean']})")

    out = dict(unguided_onsets=unguided, clap_seed_reference=seed_ref, arms=table, hard_end_vs_tail=hard, arm6=a6,
               meters="onsets/s = librosa onset_detect on the wav; drift = 1-cos CLAP to the same ctx+seed unguided; "
                      "dCE = Audiobox CE minus unguided; gate = control_head_disintegration_eval.gate (rhythmic) vs unguided")
    json.dump(out, open(f"{OUT}/report.json", "w"), indent=1)
    print(f"\nwrote {OUT}/report.json")


if __name__ == "__main__":
    main()
