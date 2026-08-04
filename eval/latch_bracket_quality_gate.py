"""latch_bracket_quality_gate.py — the aesthetic/disintegration gate for the LatCH weight
bracket (Kim ask 2026-07-19: bracket weight per head, mask fixed 0-100, "monitor output
quality so we don't render thousands of garbage clips").

Runs OVER the existing weight-bracket renders (GHOST-NOTE's latch_sa3_sweep: 14 heads ×
gains {0,64,128,512,2048,8192} × {goa[p0, rhythmic], ambient[p1]}) already scored into
eval/clip_metrics.db — no new rendering. Establishes, per head, the USABLE weight range =
the highest gain before the output disintegrates.

Kim's disintegration spec (hybrid — CE alone misleads by genre, so it only corroborates):
  * whitening / droning noise  -> spectral flatness spikes vs baseline (the spectral-whitening
    red flag) and/or zcr spikes (ringing/noise). HARD flag.
  * beat loss (rhythmic prompt only) -> onset density collapses AND bpm drifts/vanishes vs the
    same-prompt baseline. Legit intro/outro density drops are allowed (bpm must ALSO break),
    so a laid-back section doesn't false-trigger. HARD flag. Not applied to ambient.
  * CE floor -> dance prompts may sit as low as ~4.0; CE < 4.0 only counts when a hard flag
    also fired (corroboration), never on its own.
Baseline per prompt = the gain-0 clip (the clean reference, cfg 7).

Output: eval/latch_bracket_quality.json + a printed per-head table. Genre-confidence-vs-prompt
(Essentia) is a planned add-on (needs the classifier pass); the flatness/zcr/beat/CE gate
already catches the disintegration modes Kim described.
"""
import json
import re
import sqlite3
from collections import defaultdict
from pathlib import Path

DB = Path(__file__).resolve().parent / "clip_metrics.db"
OUT = Path(__file__).resolve().parent / "latch_bracket_quality.json"
SWEEP = "latch_sa3_sweep"
RHYTHMIC_PROMPTS = {"p0"}          # goa = has a beat; p1 (ambient) is not gated on beat
GAINS = [0, 64, 128, 512, 2048, 8192]

# clip name: {head}__{gN|base}__{pid}.m4a   (baseline head is literally "baseline")
NAME = re.compile(r"([a-z0-9_]+)__(base|g\d+)__(p\d+)\.m4a$")


def load_rows():
    db = sqlite3.connect(DB)
    cols = [r[1] for r in db.execute("PRAGMA table_info(metrics)").fetchall()]
    rows = db.execute(f"select {','.join(cols)} from metrics where path like ?",
                      (f"%{SWEEP}%",)).fetchall()
    out = []
    for r in rows:
        d = dict(zip(cols, r))
        m = NAME.search(d["path"])
        if not m:
            continue
        head, g, pid = m.groups()
        d["head"] = head
        d["gain"] = 0 if g == "base" else int(g[1:])
        d["pid"] = pid
        out.append(d)
    return out


def gate(clip, base, rhythmic):
    """Return (disintegrated: bool, reasons: list[str]) for a clip vs its same-prompt baseline."""
    reasons = []
    fl, flb = clip["flatness"], base["flatness"]
    zc, zcb = clip["zcr"], base["zcr"]
    # whitening / droning: flatness spikes (absolute floor + relative jump)
    if fl > 0.05 and fl > 2.5 * max(flb, 1e-4):
        reasons.append(f"whitening(flatness {flb:.3f}->{fl:.3f})")
    # noise/ringing: zcr spikes
    if zc > 1.6 * max(zcb, 1e-4) and zc > 0.15:
        reasons.append(f"noise-zcr({zcb:.3f}->{zc:.3f})")
    # beat loss (rhythmic prompts only): onset density collapses AND bpm breaks
    if rhythmic:
        op, opb = clip["onset_p95"], base["onset_p95"]
        bp, bpb = clip["bpm"] or 0, base["bpm"] or 0
        if opb > 0.5 and op < 0.4 * opb and (bp == 0 or abs(bp - bpb) > 20):
            reasons.append(f"beat-loss(onset {opb:.1f}->{op:.1f}, bpm {bpb:.0f}->{bp:.0f})")
    hard = bool(reasons)
    # CE only corroborates a hard flag (dance floor ~4.0)
    ce = clip.get("ce")
    if hard and ce is not None and ce < 4.0:
        reasons.append(f"CE<4.0({ce:.2f})")
    return hard, reasons


def main():
    rows = load_rows()
    # index: (head, pid) -> {gain: clip};  baselines: pid -> baseline clip
    by = defaultdict(dict)
    base = {}
    for d in rows:
        if d["head"] == "baseline":
            base[d["pid"]] = d
        else:
            by[(d["head"], d["pid"])][d["gain"]] = d

    result = {}
    heads = sorted({h for (h, _) in by})
    print(f"{'head':22s} {'prompt':7s} {'usable≤gain':>11s}  first-disintegration")
    for head in heads:
        result[head] = {}
        for pid in sorted(base):
            clips = by.get((head, pid), {})
            if not clips:
                continue
            rhythmic = pid in RHYTHMIC_PROMPTS
            b = base[pid]
            usable = 0
            failure = None
            for g in sorted(clips):
                bad, reasons = gate(clips[g], b, rhythmic)
                if bad:
                    failure = {"gain": g, "reasons": reasons}
                    break
                usable = g
            result[head][pid] = {"usable_max_gain": usable, "failure": failure}
            ftxt = "clean through 8192" if not failure else f"g{failure['gain']}: {', '.join(failure['reasons'])}"
            print(f"{head:22s} {pid:7s} {usable:>11d}  {ftxt}")

    OUT.write_text(json.dumps({
        "purpose": "usable weight range per LatCH head (mask 0-100), quality-gated on GHOST-NOTE's latch_sa3_sweep",
        "gate_spec": "whitening(flatness)+noise(zcr)+beat-loss(onset&bpm, rhythmic only); CE<4.0 corroborates",
        "baseline": "gain-0 clip per prompt", "gains": GAINS,
        "prompts": {"p0": "aggressive upbeat goa trance (rhythmic)", "p1": "mid 90s ambient (non-rhythmic)"},
        "result": result,
    }, indent=1))
    print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()
