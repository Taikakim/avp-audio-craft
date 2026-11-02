#!/usr/bin/env python3
"""crossmodal_mf2_essentia.py --
1. Joins the 4,461 original Music Flamingo 2 long captions (goa_src_captions/json/*.json)
   with the 5,400 Goa crops (/run/media/kim/Kosmos/latents/latents_sa3/*.json +
   /run/media/kim/Mantu/latents_sa3_mood/*.npy).
2. Discovers the intrinsic Mood Factors of Music Flamingo 2's own discriminative mood
   vocabulary on Goa_Separated (after stripping >65% genre boilerplate).
3. Computes the cross-modal alignment between MF2's mood concepts and Essentia's
   de-confounded mood dimensions — showing both where they agree AND what unique
   mood axes MF2 captures that Essentia's 56 Jamendo stock-music tags lack!
4. Compares Unhinted vs Hinted MF2 on the SAME tracks in goa_archive to see how
   unhinted MF2 exposes raw acoustic moods (dark, brooding, ominous, contemplative,
   meditative, claustrophobic, dystopian, melancholic) that the genre hint compressed.
"""
import glob, json, os, re
from collections import Counter, defaultdict
import numpy as np

BASE_CAP = "/run/media/kim/Kosmos/captions"
LAT_JSON_DIR = "/run/media/kim/Kosmos/latents/latents_sa3"
MOOD_NPY_DIR = "/run/media/kim/Mantu/latents_sa3_mood"
META_JSON = "/home/kim/Projects/mir/models/essentia/mtg_jamendo_moodtheme-discogs-effnet-1.json"

with open(META_JSON) as f:
    ESS_CLASSES = json.load(f)["classes"]

# Discriminative MF2 mood terms (5% to 55% doc freq or distinct semantic clusters)
DISC_TERMS = [
    # Cluster candidates in MF2 prose
    "euphoric", "uplifting", "bright", "ecstatic", "exhilarating", "warm", "playful",
    "searching", "unsettled", "tension", "oscillates", "modal",
    "dark", "darker", "aggressive", "intense", "ominous", "brooding", "unsettling", "dystopian", "gritty", "raw",
    "spacious", "expansive", "ambient", "ethereal", "airy", "floating", "dreamy", "cavernous",
    "otherworldly", "futuristic", "sci-fi", "alien", "cosmic", "surreal", "mysterious", "cryptic",
    "robotic", "metallic", "mechanical", "industrial",
    "introspective", "contemplative", "meditative", "calm", "reflective", "serene", "tranquil",
    "melancholic", "melancholy", "emotional", "yearning", "wistful", "nostalgic", "haunting",
    "mantra-like", "spiritual", "mystical", "tribal", "ritualistic",
    "trance-inducing", "energetic", "pulsating", "resonant"
]

# 1. Load goa_src_captions keyed by normalized track stem / relpath
src_caps = {}
for p in sorted(glob.glob(f"{BASE_CAP}/goa_src_captions/json/*.json")):
    d = json.load(open(p))
    rel = d.get("rel", "")
    txt = d.get("captions", {}).get("full", "")
    if not txt:
        continue
    folder = os.path.basename(os.path.dirname(rel))
    src_caps[folder] = txt.lower()

print(f"Loaded {len(src_caps)} goa_src_captions tracks.")

# 2. Match to the 5,400 crops in latents_sa3 + latents_sa3_mood
mood_files = sorted(glob.glob(f"{MOOD_NPY_DIR}/*.npy"))
matched_ess = []
matched_txt = []
matched_folders = []

for mp in mood_files:
    cid = os.path.splitext(os.path.basename(mp))[0]
    jp = f"{LAT_JSON_DIR}/{cid}.json"
    if not os.path.exists(jp):
        continue
    jd = json.load(open(jp))
    st = jd.get("source_track", "")
    if st in src_caps:
        arr = np.load(mp, mmap_mode="r").mean(axis=1)
        matched_ess.append(arr)
        matched_txt.append(src_caps[st])
        matched_folders.append(st)

P_ess = np.clip(np.array(matched_ess, dtype=np.float64), 1e-6, 1.0 - 1e-6)
Z_ess = np.log(P_ess / (1.0 - P_ess))
print(f"Matched {len(matched_ess)} crops ({len(set(matched_folders))} unique tracks) between MF2 goa_src_captions and 56-d Essentia mood crops!")

# De-confound Z_ess using the 10 library tags
LIB_TAGS = ["advertising", "commercial", "corporate", "background", "documentary", "movie", "trailer", "game", "sport", "christmas"]
MUS_TAGS = ["melodic", "energetic", "space", "retro", "dark", "dream", "relaxing", "meditative", "calm", "soundscape", "film", "epic", "deep", "uplifting", "happy", "party", "positive", "upbeat", "groovy", "cool", "heavy", "powerful", "fast", "slow", "sad", "melancholic", "emotional"]
lib_idx = [ESS_CLASSES.index(c) for c in LIB_TAGS]
mus_idx = [ESS_CLASSES.index(c) for c in MUS_TAGS]

Z_lib = Z_ess[:, lib_idx]
Z_lib_std = (Z_lib - Z_lib.mean(0)) / Z_lib.std(0)
U_l, S_l, _ = np.linalg.svd(Z_lib_std, full_matrices=False)
F_lib = U_l[:, :2] * S_l[:2]

Z_mus = Z_ess[:, mus_idx]
U_mus = (Z_mus - Z_mus.mean(0)) / Z_mus.std(0)
X_c = np.column_stack([np.ones(len(F_lib)), F_lib])
U_deconf = U_mus - X_c @ np.linalg.lstsq(X_c, U_mus, rcond=None)[0]
U_deconf /= U_deconf.std(0)

# 3. Build binary term matrix on unique tracks (4,461 goa_src_captions)
all_txts = list(src_caps.values())
term_mat = np.zeros((len(all_txts), len(DISC_TERMS)), dtype=np.float64)
for i, t in enumerate(all_txts):
    for j, w in enumerate(DISC_TERMS):
        if re.search(rf"\b{re.escape(w)}\b", t):
            term_mat[i, j] = 1.0

# Filter terms with at least 20 occurrences
keep_j = [j for j in range(len(DISC_TERMS)) if term_mat[:, j].sum() >= 20]
kept_terms = [DISC_TERMS[j] for j in keep_j]
T_sub = term_mat[:, keep_j]
T_std = (T_sub - T_sub.mean(0)) / (T_sub.std(0) + 1e-8)

# PCA + Varimax on MF2's own discriminative mood vocabulary across the 4,461 Goa tracks
Corr_T = np.corrcoef(T_std, rowvar=False)
eigvals, eigvecs = np.linalg.eigh(Corr_T)
order = np.argsort(eigvals)[::-1]
eigvals = eigvals[order]
eigvecs = eigvecs[:, order]

def varimax(Phi, gamma=1.0, q=50, tol=1e-6):
    p, k = Phi.shape
    R = np.eye(k)
    d = 0
    for _ in range(q):
        d_old = d
        Lambda = Phi @ R
        u, s, vh = np.linalg.svd(Phi.T @ (Lambda**3 - (gamma/p) * Lambda @ np.diag(np.diag(Lambda.T @ Lambda))))
        R = u @ vh
        d = np.sum(s)
        if d_old != 0 and d / d_old < 1 + tol:
            break
    return Phi @ R

K = 8
loadings = eigvecs[:, :K] * np.sqrt(eigvals[:K])
rot_loadings = varimax(loadings)

print(f"\n=== 2. VARIMAX PRINCIPAL MOOD AXES INSIDE MUSIC FLAMINGO 2 LONG CAPTIONS (K={K}, N=4,461 Goa tracks) ===")
for k in range(K):
    col = rot_loadings[:, k]
    if np.abs(col.min()) > np.abs(col.max()):
        col = -col
    pos = [(kept_terms[idx], round(float(col[idx]), 3)) for idx in np.argsort(col)[::-1][:6] if col[idx] > 0.18]
    neg = [(kept_terms[idx], round(float(col[idx]), 3)) for idx in np.argsort(col)[:5] if col[idx] < -0.15]
    print(f"  MF2 Axis {k+1}:")
    print(f"    (+) Pole: {pos}")
    print(f"    (-) Anti: {neg}")

# 4. Cross-modal correlation: for key MF2 mood terms, what is the shift in De-confounded Essentia space?
print("\n=== 3. CROSS-MODAL ALIGNMENT: MF2 LONG-CAPTION MOOD -> DE-CONFOUNDED ESSENTIA MOOD SHIFT (N=5,380 crops) ===")
crop_term_mat = np.zeros((len(matched_txt), len(kept_terms)))
for i, t in enumerate(matched_txt):
    for j, w in enumerate(kept_terms):
        if re.search(rf"\b{re.escape(w)}\b", t):
            crop_term_mat[i, j] = 1.0

key_probe_terms = [
    "euphoric", "uplifting", "bright", "searching", "dark", "aggressive", "ominous",
    "ambient", "spacious", "ethereal", "otherworldly", "futuristic", "robotic",
    "meditative", "introspective", "contemplative", "calm", "melancholic", "mantra-like"
]
for w in key_probe_terms:
    if w not in kept_terms:
        continue
    j = kept_terms.index(w)
    mask = crop_term_mat[:, j] == 1.0
    n_pos = int(mask.sum())
    if n_pos < 10:
        continue
    # Mean standardized de-confounded shift (in sigma units) when MF2 uses word `w`
    diff_sigma = U_deconf[mask].mean(0) - U_deconf[~mask].mean(0)
    top_p = [(MUS_TAGS[m], round(float(diff_sigma[m]), 3)) for m in np.argsort(diff_sigma)[::-1][:4] if diff_sigma[m] > 0.08]
    top_n = [(MUS_TAGS[m], round(float(diff_sigma[m]), 3)) for m in np.argsort(diff_sigma)[:3] if diff_sigma[m] < -0.08]
    print(f"  MF2 '{w:14s}' (n={n_pos:4d} crops): Essentia (+) {top_p} | (-) {top_n}")

# 5. Unhinted vs Hinted comparison on the exact same 3,000 tracks in goa_archive
print("\n=== 4. UNHINTED vs HINTED MF2 LONG CAPTIONS ON IDENTICAL TRACKS (N=3,000 paired tracks) ===")
unhint_files = sorted(glob.glob(f"{BASE_CAP}/goa_archive_captions/json/*.json"))[:3000]
unhint_counts = Counter()
hint_counts = Counter()
n_paired = 0
for up in unhint_files:
    bn = os.path.basename(up)
    hp = f"{BASE_CAP}/goa_archive_captions_hinted/json/{bn}"
    if not os.path.exists(hp):
        continue
    tu = json.load(open(up)).get("captions", {}).get("full", "").lower()
    th = json.load(open(hp)).get("captions", {}).get("full", "").lower()
    if not tu or not th:
        continue
    n_paired += 1
    for w in DISC_TERMS + ["hypnotic", "psychedelic", "driving", "high-energy", "claustrophobic", "menacing"]:
        if re.search(rf"\b{re.escape(w)}\b", tu):
            unhint_counts[w] += 1
        if re.search(rf"\b{re.escape(w)}\b", th):
            hint_counts[w] += 1

print(f"Paired tracks analyzed: {n_paired}")
diffs = []
for w in set(list(unhint_counts.keys()) + list(hint_counts.keys())):
    u_pct = unhint_counts[w] / n_paired * 100
    h_pct = hint_counts[w] / n_paired * 100
    if max(u_pct, h_pct) >= 1.5:
        diffs.append((w, u_pct, h_pct, h_pct - u_pct, (u_pct + 0.1) / (h_pct + 0.1)))

print("\n  [A] Moods REVEALED by Unhinted MF2 (suppressed when 'Goa trance' genre hint was added):")
for w, u_pct, h_pct, d_pct, ratio in sorted(diffs, key=lambda x: x[3])[:15]:
    print(f"    {w:18s}: Unhinted={u_pct:5.1f}%  ->  Hinted={h_pct:5.1f}%  (Delta={d_pct:+5.1f}%, {u_pct/max(0.1,h_pct):.1f}x more in Unhinted)")

print("\n  [B] Moods INJECTED by the 'Goa trance' Genre Hint:")
for w, u_pct, h_pct, d_pct, ratio in sorted(diffs, key=lambda x: x[3], reverse=True)[:12]:
    print(f"    {w:18s}: Unhinted={u_pct:5.1f}%  ->  Hinted={h_pct:5.1f}%  (Delta={d_pct:+5.1f}%)")
