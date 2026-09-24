#!/usr/bin/env python3
"""Definitive longform caption sidecars for the fp32/T4096 LUMI campaign.

Kim direct (via C's DM 2026-07-14): supersedes lumi/goa_kimlong_sidecar.json
(artist/title fuzzy matcher, t1-only, 3151/5400). This builder uses the design
Kim pointed at — the existing MF->Granite caption selection + the stratified
cluster division — and emits FULL-TIER entries so --caption_probs mixes terse
and longform meaningfully.

GOA (-> lumi/goa_longform_sidecar.json, keyed by latents_sa3 stems):
  t1 = stored terse caption (mir/data/feature_tables/goa/captions.json)
  t3 priority per stem's source_track:
    1. "first_class": track is one of the 273 flamingo_budget goa rows AND has
       a Music-Flamingo caption (the individually-selected stratified set);
    2. "own": track has an MF caption in the full pool (eval/kimlong_pool.json,
       2642 tracks, extracted from Lehto/latents' per-crop music_flamingo_full);
    3. "borrowed": no own caption -> a captioned representative from the SAME
       CLUSTER (merged_clusters_k48.npz, the 36-cluster division the budget was
       stratified over). Representatives prefer the cluster's first-class
       (budget) tracks; deterministic hash(stem) spreads stems across them.
    4. absent (t3=null): track not captioned, not in the cluster division (or
       cluster has no captioned member). Sampler falls back to t1.
  Join key: latent json source_track == pool 'track' == npz 'names' (verbatim
  Lehto/Goa dir-name space); C's relaxed artist/title matcher is the fallback
  for name drift.

AVP (-> lumi/avp_longform_sidecar.json, keyed by latents_avp stems):
  Base: latents_avp/captions_tiered.json (t1/t2 kept verbatim; t3 on the 270
  original crops from the Granite pass). Fill: an aug-variant crop's
  source_track is "Parent Track/variant" — propagate t2/t3 from a captioned
  crop of the SAME PARENT (the "disjoint" in C's coverage note was this join,
  not missing data). No cluster division exists for avp; parent-propagation is
  the whole mechanism.

Provenance maps (parallel files, *_provenance.json): {stem: {tier, source_track,
caption_track, cluster}} so borrowed status is auditable and page/eval builders
can mark borrowed captions.

Run: python3 eval/build_longform_sidecars.py   (stdlib + numpy only)
"""
import hashlib
import json
import os
import re
import sys
import unicodedata
from collections import defaultdict

import numpy as np

SAO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIR_FT = "/home/kim/Projects/mir/data/feature_tables"
LATENTS_GOA = "/home/kim/Projects/latents_sa3"
LATENTS_AVP = "/run/media/kim/Kosmos/latents_avp"
POOL = os.path.join(SAO, "eval", "kimlong_pool.json")
BUDGET = os.path.join(MIR_FT, "flamingo_budget.json")
CLUSTERS = os.path.join(MIR_FT, "merged_clusters_k48.npz")
GOA_CAPTIONS = os.path.join(MIR_FT, "goa", "captions.json")
OUT_GOA = os.path.join(SAO, "lumi", "goa_longform_sidecar.json")
OUT_AVP = os.path.join(SAO, "lumi", "avp_longform_sidecar.json")


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", s.casefold()).strip()


def spread(stem: str, n: int) -> int:
    """Deterministic stem -> index in [0, n): stable across runs/machines."""
    return int(hashlib.sha1(stem.encode()).hexdigest(), 16) % n


def build_goa():
    pool = json.load(open(POOL))
    cap_by_track = {e["track"]: e["prompt"] for e in pool}
    cap_by_norm = {norm(e["track"]): e["prompt"] for e in pool}
    budget_tracks = {e["track"] for e in json.load(open(BUDGET))
                     if e.get("source") == "goa"}

    z = np.load(CLUSTERS, allow_pickle=True)
    cluster_of = {str(n): int(l) for n, l, s in
                  zip(z["names"], z["labels"], z["src"]) if s == "goa"}
    # cluster -> captioned representatives (first-class first, then any own)
    reps_fc = defaultdict(list)
    reps_any = defaultdict(list)
    for name, cl in sorted(cluster_of.items()):
        if name in cap_by_track:
            (reps_fc if name in budget_tracks else reps_any)[cl].append(name)

    tiers = json.load(open(GOA_CAPTIONS))          # {stem: {t1,t2,t3}}
    out, prov = {}, {}
    counts = defaultdict(int)
    for stem in sorted(tiers.keys()):
        base = dict(tiers[stem])
        jpath = os.path.join(LATENTS_GOA, f"{stem}.json")
        track = None
        if os.path.exists(jpath):
            track = json.load(open(jpath)).get("source_track")
        tier, cap_track, cluster = None, None, None
        if track:
            cluster = cluster_of.get(track)
            if track in cap_by_track:
                cap_track = track
                tier = "first_class" if track in budget_tracks else "own"
            elif norm(track) in cap_by_norm:
                base["t3"] = cap_by_norm[norm(track)]
                cap_track, tier = track, "own"          # name-drift own match
            elif cluster is not None:
                fc, anyr = reps_fc.get(cluster, []), reps_any.get(cluster, [])
                reps = fc if fc else anyr
                if reps:
                    cap_track = reps[spread(stem, len(reps))]
                    tier = "borrowed"
        if cap_track and base.get("t3") is None:
            base["t3"] = cap_by_track.get(cap_track) or cap_by_norm[norm(cap_track)]
        out[stem] = base
        counts[tier or "absent"] += 1
        prov[stem] = {"tier": tier, "source_track": track,
                      "caption_track": cap_track, "cluster": cluster}
    return out, prov, dict(counts)


AVP_ROOT = "/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/avp-analyzed"


def _avp_info_caption(parent: str):
    """Fallback caption source: the parent track's .INFO Music-Flamingo fields.
    Needed for parents whose latents_avp crops are ALL aug-variants (no original
    crop stems exist, so the granite pass's crop-keyed sidecar can't carry them
    — the 2026-07-15 MF fill wrote their captions into the INFOs directly)."""
    d = os.path.join(AVP_ROOT, parent)
    if not os.path.isdir(d):
        return None
    for f in sorted(os.listdir(d)):
        if f.endswith(".INFO"):
            try:
                info = json.load(open(os.path.join(d, f)))
            except Exception:
                return None
            t3 = info.get("music_flamingo_genre_mood") or info.get("music_flamingo_full")
            if t3:
                return {"t2": info.get("granite_t2"), "t3": t3, "from": "INFO"}
    return None


def build_avp():
    tiers = json.load(open(os.path.join(LATENTS_AVP, "captions_tiered.json")))
    # parent track -> a captioned entry (t3 present)
    parent_caps = {}
    parent_of = {}
    for stem in sorted(tiers.keys()):
        jpath = os.path.join(LATENTS_AVP, f"{stem}.json")
        st = json.load(open(jpath)).get("source_track") or "" if os.path.exists(jpath) else ""
        parent = st.split("/")[0] if st else ""
        parent_of[stem] = parent
        if parent and tiers[stem].get("t3") and parent not in parent_caps:
            parent_caps[parent] = {"t2": tiers[stem].get("t2"),
                                   "t3": tiers[stem]["t3"], "from": stem}
    # INFO-fallback for parents with no captioned crop entry
    for parent in {p for p in parent_of.values() if p and p not in parent_caps}:
        cap = _avp_info_caption(parent)
        if cap:
            parent_caps[parent] = cap
    out, prov = {}, {}
    counts = defaultdict(int)
    for stem in sorted(tiers.keys()):
        base = dict(tiers[stem])
        parent = parent_of.get(stem, "")
        tier = "own" if base.get("t3") else None
        cap_from = stem if tier else None
        if not base.get("t3") and parent in parent_caps:
            pc = parent_caps[parent]
            base["t3"] = pc["t3"]
            if not base.get("t2") and pc.get("t2"):
                base["t2"] = pc["t2"]
            tier, cap_from = "parent", pc["from"]
        out[stem] = base
        counts[tier or "absent"] += 1
        prov[stem] = {"tier": tier, "parent_track": parent, "caption_stem": cap_from}
    return out, prov, dict(counts)


def main():
    goa, goa_prov, gc = build_goa()
    json.dump(goa, open(OUT_GOA, "w"), ensure_ascii=False, indent=0)
    json.dump(goa_prov, open(OUT_GOA.replace(".json", "_provenance.json"), "w"),
              ensure_ascii=False, indent=0)
    n = len(goa)
    t3 = sum(1 for v in goa.values() if v.get("t3"))
    print(f"[goa] {n} stems -> {OUT_GOA}")
    print(f"[goa] t3 coverage {t3}/{n} ({100*t3/n:.1f}%) | tiers: {gc}")

    avp, avp_prov, ac = build_avp()
    json.dump(avp, open(OUT_AVP, "w"), ensure_ascii=False, indent=0)
    json.dump(avp_prov, open(OUT_AVP.replace(".json", "_provenance.json"), "w"),
              ensure_ascii=False, indent=0)
    n = len(avp)
    t3 = sum(1 for v in avp.values() if v.get("t3"))
    print(f"[avp] {n} stems -> {OUT_AVP}")
    print(f"[avp] t3 coverage {t3}/{n} ({100*t3/n:.1f}%) | tiers: {ac}")


if __name__ == "__main__":
    sys.exit(main())
