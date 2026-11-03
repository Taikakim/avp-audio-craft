#!/usr/bin/env python3
# Last edited: WINTERMUTE 2026-11-03 -- chroma head is 384-dim; link to the finished 15-prompt run
"""build_mood_finegrained_page.py -- generates the listening page for the
fine-grained weight ladder (g=0, 256, 512, 1024, 1536, 2048, 3072, 4096, 8192) and 8 model
combinations / adapter blends on prompt rb_bracket_0.
Follows docs/eval-page-standard.md and site/reference.html (evals.css + Misc/float_player.py + Misc/comment_notes_block.py).
Outputs: /home/kim/evals_aac/mood_finegrained.html and /home/kim/evals_aac/mood_finegrained/run_meta.json
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, "/home/kim/Projects/SAO/Misc")
from comment_notes_block import notes_block  # noqa: E402
from float_player import inject  # noqa: E402

AAC_DIR = Path("/home/kim/evals_aac/mood_finegrained")
OUT_HTML = Path("/home/kim/evals_aac/mood_finegrained.html")
INSPECT_JSON = AAC_DIR / "clip_inspect_data.json"
RUN_META_JSON = AAC_DIR / "run_meta.json"

PROMPT = "2020s goa trance, melodic mood, 148 bpm"
SEED = 1102008041
CFG = 7.0
DURATION = 20.0

MODELS = [
    {
        "id": "base",
        "name": "Medium Base (Unadapted DiT)",
        "type": "base",
        "badge": "Base DiT",
        "desc": "sa3_medium_base (no adapter). Unguided g=0: key D minor, melodic=0.1847, space=0.0548, SC=3088 Hz, CE=7.62."
    },
    {
        "id": "adamw",
        "name": "AdamW ep5 (avp_t512_bs4_lr5e5)",
        "type": "lora",
        "badge": "LoRA r64",
        "desc": "AdamW rank-64 LoRA on AVP set (lr=5e-5, ep5). Unguided g=0: key C minor, melodic=0.2708, space=0.0834, SC=2687 Hz, CE=7.14."
    },
    {
        "id": "fusion",
        "name": "Fusion LoRA r128 ep159",
        "type": "lora",
        "badge": "LoRA r128",
        "desc": "Dorlor FusionOpt rank-128 LoRA on AVP-augmented set (ep159). Unguided g=0: key G minor, melodic=0.3892, space=0.0884, SC=3151 Hz, CE=7.07."
    },
    {
        "id": "goa",
        "name": "Goa LoRA r128 ep63",
        "type": "lora",
        "badge": "LoRA r128",
        "desc": "Dorlor FusionOpt rank-128 LoRA on Goa set (ep63). Unguided g=0: key C major, melodic=0.5090, space=0.0965, SC=3707 Hz, CE=6.23."
    },
    {
        "id": "combo_adamw_fusion",
        "name": "Combo: AdamW + Fusion (50 / 50)",
        "type": "combo",
        "badge": "Blend 0.5/0.5",
        "desc": "Linear LoRA blend: 0.5 AdamW ep5 + 0.5 Fusion ep159. Unguided g=0: key G minor, melodic=0.3402, space=0.0806, SC=2660 Hz, CE=7.25."
    },
    {
        "id": "combo_adamw_goa",
        "name": "Combo: AdamW + Goa (50 / 50)",
        "type": "combo",
        "badge": "Blend 0.5/0.5",
        "desc": "Linear LoRA blend: 0.5 AdamW ep5 + 0.5 Goa ep63. Unguided g=0: key G minor, melodic=0.5384, space=0.0741, SC=3307 Hz, CE=7.15."
    },
    {
        "id": "combo_fusion_goa",
        "name": "Combo: Fusion + Goa (50 / 50)",
        "type": "combo",
        "badge": "Blend 0.5/0.5",
        "desc": "Linear LoRA blend: 0.5 Fusion ep159 + 0.5 Goa ep63. Unguided g=0: key G minor, melodic=0.6073, space=0.0828, SC=3605 Hz, CE=6.79."
    },
    {
        "id": "fullft",
        "name": "Full Fine-Tune DiT ep39",
        "type": "fullft",
        "badge": "Full-FT",
        "desc": "Full 24-block DiT fine-tune (A_control ep39). Unguided g=0: key G minor, melodic=0.5022, space=0.0840, SC=3472 Hz, CE=7.25."
    }
]

TARGETS = [
    {
        "id": "Space",
        "name": "Space",
        "full_name": "Space (Sparse 3-Tag)",
        "spec": "space=1.0, soundscape=0.3, dream=0.3 (53 dims = 0)",
        "desc": "Sparse 3-channel target. On this 1 prompt/seed, raises space (+0.05..+0.12) while reducing melodic (-35% to -60% at g>=2048)."
    },
    {
        "id": "Dark",
        "name": "Dark",
        "full_name": "Dark (Sparse 3-Tag)",
        "spec": "dark=1.0, heavy=0.4, deep=0.3 (53 dims = 0)",
        "desc": "Sparse 3-channel target. On this 1 prompt/seed, raises dark (+0.02..+0.04) and lowers spectral centroid (-200..-850 Hz)."
    },
    {
        "id": "Melodic",
        "name": "Melodic",
        "full_name": "Melodic (Sparse 3-Tag)",
        "spec": "melodic=1.0, uplifting=0.4, happy=0.3 (53 dims = 0)",
        "desc": "Sparse 3-channel target. On this 1 prompt/seed, Base peaks at g=2048 (0.185->0.275); Goa LoRA stays near baseline (0.509->0.504 at g=8192)."
    },
    {
        "id": "Aliens",
        "name": "Aliens HQ",
        "full_name": "Total Eclipse - Aliens (20s TS)",
        "spec": "sample 6073122 (137.7s..157.7s); mean: mel=0.40, spc=0.16, ene=0.12",
        "desc": "56-dim Essentia time-series from Aliens. Low temporal variance (std<0.03) and high cosine similarity (0.95..0.99) to unguided Goa renders -> small gradient."
    },
    {
        "id": "Deconf_Melodic",
        "name": "Deconf Melodic",
        "full_name": "Deconf Melodic (Kriging)",
        "spec": "melodic: +3.5 SD via 27x27 Goa cov; 10 library tags = -0.15",
        "desc": "Gaussian conditional completion from Goa logit covariance (+energetic, +retro, +space) with -0.15 on 10 library tags. Like-for-like vs Melodic on Goa LoRA is flat (+0.005..+0.012)."
    },
    {
        "id": "Deconf_Space",
        "name": "Deconf Space",
        "full_name": "Deconf Space (Kriging)",
        "spec": "space: +3.5 SD via 27x27 Goa cov; 10 library tags = -0.15",
        "desc": "Conditionally completes space with Goa co-occurring priors. Moves space less than naive Space at equal gain (0/16 wins on own tag), while dropping melodic less."
    },
    {
        "id": "Deconf_Dark",
        "name": "Deconf Dark",
        "full_name": "Deconf Dark (Kriging)",
        "spec": "dark: +3.5 SD via 27x27 Goa cov; 10 library tags = -0.15",
        "desc": "Conditionally completes dark (+space, +soundscape, +melodic prior). Moves dark less than naive Dark at equal gain (2/16 wins on own tag), while keeping Base melodic closer to g=0."
    },
    {
        "id": "Deconf_Uplifting",
        "name": "Deconf Uplifting",
        "full_name": "Deconf Uplifting (Kriging)",
        "spec": "uplifting +3.5 SD, happy +2.5 SD, melodic +1.5 SD; library = -0.15",
        "desc": "Conditioned on uplifting/happy/melodic (largest positive entries: melodic 0.355, energetic 0.164, uplifting 0.088). Raises Goa LoRA melodic from 0.509 to 0.665 at g=8192 on this seed."
    },
    {
        "id": "Deconf_AntiDark",
        "name": "Deconf AntiDark",
        "full_name": "Deconf AntiDark (Bipolar)",
        "spec": "mel +2.5, upl +2.5, ene +2.0, dark -3.5, slow -2.5 SD",
        "desc": "Bipolar target (largest positive entries: melodic 0.355, energetic 0.193). Raises Base melodic to 0.295 and Goa LoRA melodic to 0.657 at g=8192 on this seed."
    }
]

WEIGHTS = [0, 256, 512, 1024, 1536, 2048, 3072, 4096, 8192]


def get_clip_filename(model_id, target_id, weight):
    if weight == 0:
        return f"fine_{model_id}__base__s{SEED}.m4a"
    return f"fine_{model_id}__{target_id}_g{weight}__s{SEED}.m4a"


def build_matrix_data(inspect_data):
    data = {}
    for tgt in TARGETS:
        t_id = tgt["id"]
        data[t_id] = {}
        for m in MODELS:
            m_id = m["id"]
            data[t_id][m_id] = {}
            for w in WEIGHTS:
                fname = get_clip_filename(m_id, t_id, w)
                exists = (AAC_DIR / fname).exists()
                if not exists:
                    data[t_id][m_id][str(w)] = {"ready": False, "weight": w}
                    continue
                size_kb = (AAC_DIR / fname).stat().st_size / 1024.0
                ins = inspect_data.get(fname, {})
                tm = {d["dim"]: d["score"] for d in ins.get("top_moods", [])}
                ce = ins.get("audiobox", {}).get("CE", None)
                pq = ins.get("audiobox", {}).get("PQ", None)
                key_str = f"{ins.get('key', '')} {ins.get('scale', '')}".strip()
                data[t_id][m_id][str(w)] = {
                    "file": fname,
                    "url": f"mood_finegrained/{fname}",
                    "ready": True,
                    "size_kb": round(size_kb, 1),
                    "model_name": m["name"],
                    "target_name": tgt["name"],
                    "weight": w,
                    "mel": tm.get("melodic", None),
                    "spc": tm.get("space", None),
                    "drk": tm.get("dark", None),
                    "ene": tm.get("energetic", None),
                    "ce": ce,
                    "pq": pq,
                    "key": key_str,
                    "key_changed": ins.get("key_changed", False)
                }
    return data


def make_ext_clip(inspect_data, file, label, primary_dim="melodic"):
    ins = inspect_data.get(file, {})
    tm = {d["dim"]: d["score"] for d in ins.get("top_moods", [])}
    val = tm.get(primary_dim, None)
    mel = tm.get("melodic", None)
    crest = ins.get("crest_factor", None)
    sc = ins.get("spectral_centroid", None)
    sc_d = ins.get("sc_delta", None)
    ce = ins.get("audiobox", {}).get("CE", None)
    key_s = f"{ins.get('key', '')} {ins.get('scale', '')}".strip()
    note_parts = []
    if key_s:
        note_parts.append(key_s)
    if sc_d is not None and abs(sc_d) >= 1.0:
        note_parts.append(f"dSC {sc_d:+.0f}Hz")
    if ce is not None:
        note_parts.append(f"CE {ce:.2f}")
    return {
        "file": file,
        "label": label,
        "primary_dim": primary_dim,
        "primary_val": val,
        "mel": mel,
        "crest": crest,
        "sc": sc,
        "note": " · ".join(note_parts) if note_parts else "measured"
    }


def build_extreme_and_neg_data(inspect_data):
    return [
        {
            "category": "Melodic Guidance (g=0..12288 Extended Weight Sweep · n=1 seed)",
            "subtitle": "Measured Essentia melodic score, crest factor, key, and Audiobox CE across Base DiT vs Goa LoRA r128 on prompt rb_bracket_0.",
            "target": "Melodic",
            "weights": ["g=0", "g=1024", "g=2048", "g=4096", "g=6144", "g=8192", "g=12288"],
            "rows": [
                {
                    "model_id": "base",
                    "model_name": "Medium Base DiT",
                    "badge": "Base DiT",
                    "clips": [
                        make_ext_clip(inspect_data, f"fine_base__base__s{SEED}.m4a", "g=0", "melodic"),
                        make_ext_clip(inspect_data, f"fine_base__Melodic_g1024__s{SEED}.m4a", "g=1024", "melodic"),
                        make_ext_clip(inspect_data, f"fine_base__Melodic_g2048__s{SEED}.m4a", "g=2048", "melodic"),
                        make_ext_clip(inspect_data, f"fine_base__Melodic_g4096__s{SEED}.m4a", "g=4096", "melodic"),
                        make_ext_clip(inspect_data, f"fine_base__Melodic_g6144__s{SEED}.m4a", "g=6144", "melodic"),
                        make_ext_clip(inspect_data, f"fine_base__Melodic_g8192__s{SEED}.m4a", "g=8192", "melodic"),
                        make_ext_clip(inspect_data, f"fine_base__Melodic_g12288__s{SEED}.m4a", "g=12288", "melodic"),
                    ]
                },
                {
                    "model_id": "goa",
                    "model_name": "Goa LoRA r128 ep63",
                    "badge": "LoRA r128",
                    "clips": [
                        make_ext_clip(inspect_data, f"fine_goa__base__s{SEED}.m4a", "g=0", "melodic"),
                        make_ext_clip(inspect_data, f"fine_goa__Melodic_g1024__s{SEED}.m4a", "g=1024", "melodic"),
                        make_ext_clip(inspect_data, f"fine_goa__Melodic_g2048__s{SEED}.m4a", "g=2048", "melodic"),
                        make_ext_clip(inspect_data, f"fine_goa__Melodic_g4096__s{SEED}.m4a", "g=4096", "melodic"),
                        make_ext_clip(inspect_data, f"fine_goa__Melodic_g6144__s{SEED}.m4a", "g=6144", "melodic"),
                        make_ext_clip(inspect_data, f"fine_goa__Melodic_g8192__s{SEED}.m4a", "g=8192", "melodic"),
                        make_ext_clip(inspect_data, f"fine_goa__Melodic_g12288__s{SEED}.m4a", "g=12288", "melodic"),
                    ]
                }
            ]
        },
        {
            "category": "Aliens HQ Time-Series (g=0..12288 Extended Weight Sweep · n=1 seed)",
            "subtitle": "Aliens target mean is mel=0.404, spc=0.161, ene=0.123. On Goa LoRA (g=0 mel=0.509), steering toward Aliens pulls melodic toward 0.44 and shifts C major -> C minor at g>=2048.",
            "target": "Aliens",
            "weights": ["g=0", "g=1024", "g=2048", "g=4096", "g=6144", "g=8192", "g=12288"],
            "rows": [
                {
                    "model_id": "base",
                    "model_name": "Medium Base DiT",
                    "badge": "Base DiT",
                    "clips": [
                        make_ext_clip(inspect_data, f"fine_base__base__s{SEED}.m4a", "g=0", "melodic"),
                        make_ext_clip(inspect_data, f"fine_base__Aliens_g1024__s{SEED}.m4a", "g=1024", "melodic"),
                        make_ext_clip(inspect_data, f"fine_base__Aliens_g2048__s{SEED}.m4a", "g=2048", "melodic"),
                        make_ext_clip(inspect_data, f"fine_base__Aliens_g4096__s{SEED}.m4a", "g=4096", "melodic"),
                        make_ext_clip(inspect_data, f"fine_base__Aliens_g6144__s{SEED}.m4a", "g=6144", "melodic"),
                        make_ext_clip(inspect_data, f"fine_base__Aliens_g8192__s{SEED}.m4a", "g=8192", "melodic"),
                        make_ext_clip(inspect_data, f"fine_base__Aliens_g12288__s{SEED}.m4a", "g=12288", "melodic"),
                    ]
                },
                {
                    "model_id": "goa",
                    "model_name": "Goa LoRA r128 ep63",
                    "badge": "LoRA r128",
                    "clips": [
                        make_ext_clip(inspect_data, f"fine_goa__base__s{SEED}.m4a", "g=0", "melodic"),
                        make_ext_clip(inspect_data, f"fine_goa__Aliens_g1024__s{SEED}.m4a", "g=1024", "melodic"),
                        make_ext_clip(inspect_data, f"fine_goa__Aliens_g2048__s{SEED}.m4a", "g=2048", "melodic"),
                        make_ext_clip(inspect_data, f"fine_goa__Aliens_g4096__s{SEED}.m4a", "g=4096", "melodic"),
                        make_ext_clip(inspect_data, f"fine_goa__Aliens_g6144__s{SEED}.m4a", "g=6144", "melodic"),
                        make_ext_clip(inspect_data, f"fine_goa__Aliens_g8192__s{SEED}.m4a", "g=8192", "melodic"),
                        make_ext_clip(inspect_data, f"fine_goa__Aliens_g12288__s{SEED}.m4a", "g=12288", "melodic"),
                    ]
                }
            ]
        },
        {
            "category": "Negative Guidance: -Space & -Dark (g=0..-4096 · n=1 seed)",
            "subtitle": "Negated gradient direction (-grad L_cos) on Space and Dark targets.",
            "target": "NegSpace / NegDark",
            "weights": ["g=0", "g=-1024", "g=-2048", "g=-4096"],
            "rows": [
                {
                    "model_id": "base",
                    "model_name": "Medium Base — NegSpace",
                    "badge": "-Space",
                    "clips": [
                        make_ext_clip(inspect_data, f"fine_base__base__s{SEED}.m4a", "g=0", "space"),
                        make_ext_clip(inspect_data, f"fine_base__NegSpace_g1024__s{SEED}.m4a", "g=-1024", "space"),
                        make_ext_clip(inspect_data, f"fine_base__NegSpace_g2048__s{SEED}.m4a", "g=-2048", "space"),
                        make_ext_clip(inspect_data, f"fine_base__NegSpace_g4096__s{SEED}.m4a", "g=-4096", "space"),
                    ]
                },
                {
                    "model_id": "goa",
                    "model_name": "Goa LoRA — NegSpace",
                    "badge": "-Space",
                    "clips": [
                        make_ext_clip(inspect_data, f"fine_goa__base__s{SEED}.m4a", "g=0", "space"),
                        make_ext_clip(inspect_data, f"fine_goa__NegSpace_g1024__s{SEED}.m4a", "g=-1024", "space"),
                        make_ext_clip(inspect_data, f"fine_goa__NegSpace_g2048__s{SEED}.m4a", "g=-2048", "space"),
                        make_ext_clip(inspect_data, f"fine_goa__NegSpace_g4096__s{SEED}.m4a", "g=-4096", "space"),
                    ]
                },
                {
                    "model_id": "base",
                    "model_name": "Medium Base — NegDark",
                    "badge": "-Dark",
                    "clips": [
                        make_ext_clip(inspect_data, f"fine_base__base__s{SEED}.m4a", "g=0", "melodic"),
                        make_ext_clip(inspect_data, f"fine_base__NegDark_g1024__s{SEED}.m4a", "g=-1024", "melodic"),
                        make_ext_clip(inspect_data, f"fine_base__NegDark_g2048__s{SEED}.m4a", "g=-2048", "melodic"),
                        make_ext_clip(inspect_data, f"fine_base__NegDark_g4096__s{SEED}.m4a", "g=-4096", "melodic"),
                    ]
                },
                {
                    "model_id": "goa",
                    "model_name": "Goa LoRA — NegDark",
                    "badge": "-Dark",
                    "clips": [
                        make_ext_clip(inspect_data, f"fine_goa__base__s{SEED}.m4a", "g=0", "melodic"),
                        make_ext_clip(inspect_data, f"fine_goa__NegDark_g1024__s{SEED}.m4a", "g=-1024", "melodic"),
                        make_ext_clip(inspect_data, f"fine_goa__NegDark_g2048__s{SEED}.m4a", "g=-2048", "melodic"),
                        make_ext_clip(inspect_data, f"fine_goa__NegDark_g4096__s{SEED}.m4a", "g=-4096", "melodic"),
                    ]
                }
            ]
        },
        {
            "category": "Conditional De-Confounding (Kriging) vs Sparse 3-Tag Targets (g=0..8192 · n=1 seed)",
            "subtitle": "Side-by-side on prompt rb_bracket_0 (seed 1102008041). Note: Deconf_Melodic vs Sparse Melodic on Goa LoRA is flat (+0.005..+0.012); Deconf_Uplifting and Deconf_AntiDark raise melodic on Goa LoRA because melodic (0.355) + energetic are their largest positive components.",
            "target": "Deconf vs Naive",
            "weights": ["g=0", "g=1024", "g=2048", "g=4096", "g=8192"],
            "rows": [
                {
                    "model_id": "goa",
                    "model_name": "Goa LoRA — Sparse Melodic",
                    "badge": "Sparse 3-Tag",
                    "clips": [
                        make_ext_clip(inspect_data, f"fine_goa__base__s{SEED}.m4a", "g=0", "melodic"),
                        make_ext_clip(inspect_data, f"fine_goa__Melodic_g1024__s{SEED}.m4a", "g=1024", "melodic"),
                        make_ext_clip(inspect_data, f"fine_goa__Melodic_g2048__s{SEED}.m4a", "g=2048", "melodic"),
                        make_ext_clip(inspect_data, f"fine_goa__Melodic_g4096__s{SEED}.m4a", "g=4096", "melodic"),
                        make_ext_clip(inspect_data, f"fine_goa__Melodic_g8192__s{SEED}.m4a", "g=8192", "melodic"),
                    ]
                },
                {
                    "model_id": "goa",
                    "model_name": "Goa LoRA — Deconf_Melodic",
                    "badge": "Kriging (like-for-like)",
                    "clips": [
                        make_ext_clip(inspect_data, f"fine_goa__base__s{SEED}.m4a", "g=0", "melodic"),
                        make_ext_clip(inspect_data, f"fine_goa__Deconf_Melodic_g1024__s{SEED}.m4a", "g=1024", "melodic"),
                        make_ext_clip(inspect_data, f"fine_goa__Deconf_Melodic_g2048__s{SEED}.m4a", "g=2048", "melodic"),
                        make_ext_clip(inspect_data, f"fine_goa__Deconf_Melodic_g4096__s{SEED}.m4a", "g=4096", "melodic"),
                        make_ext_clip(inspect_data, f"fine_goa__Deconf_Melodic_g8192__s{SEED}.m4a", "g=8192", "melodic"),
                    ]
                },
                {
                    "model_id": "goa",
                    "model_name": "Goa LoRA — Deconf_Uplifting",
                    "badge": "Kriging (upl+hap+mel)",
                    "clips": [
                        make_ext_clip(inspect_data, f"fine_goa__base__s{SEED}.m4a", "g=0", "melodic"),
                        make_ext_clip(inspect_data, f"fine_goa__Deconf_Uplifting_g1024__s{SEED}.m4a", "g=1024", "melodic"),
                        make_ext_clip(inspect_data, f"fine_goa__Deconf_Uplifting_g2048__s{SEED}.m4a", "g=2048", "melodic"),
                        make_ext_clip(inspect_data, f"fine_goa__Deconf_Uplifting_g4096__s{SEED}.m4a", "g=4096", "melodic"),
                        make_ext_clip(inspect_data, f"fine_goa__Deconf_Uplifting_g8192__s{SEED}.m4a", "g=8192", "melodic"),
                    ]
                },
                {
                    "model_id": "combo_fusion_goa",
                    "model_name": "Combo F+G — Sparse Space",
                    "badge": "Sparse 3-Tag",
                    "clips": [
                        make_ext_clip(inspect_data, f"fine_combo_fusion_goa__base__s{SEED}.m4a", "g=0", "space"),
                        make_ext_clip(inspect_data, f"fine_combo_fusion_goa__Space_g1024__s{SEED}.m4a", "g=1024", "space"),
                        make_ext_clip(inspect_data, f"fine_combo_fusion_goa__Space_g2048__s{SEED}.m4a", "g=2048", "space"),
                        make_ext_clip(inspect_data, f"fine_combo_fusion_goa__Space_g4096__s{SEED}.m4a", "g=4096", "space"),
                        make_ext_clip(inspect_data, f"fine_combo_fusion_goa__Space_g8192__s{SEED}.m4a", "g=8192", "space"),
                    ]
                },
                {
                    "model_id": "combo_fusion_goa",
                    "model_name": "Combo F+G — Deconf_Space",
                    "badge": "Kriging",
                    "clips": [
                        make_ext_clip(inspect_data, f"fine_combo_fusion_goa__base__s{SEED}.m4a", "g=0", "space"),
                        make_ext_clip(inspect_data, f"fine_combo_fusion_goa__Deconf_Space_g1024__s{SEED}.m4a", "g=1024", "space"),
                        make_ext_clip(inspect_data, f"fine_combo_fusion_goa__Deconf_Space_g2048__s{SEED}.m4a", "g=2048", "space"),
                        make_ext_clip(inspect_data, f"fine_combo_fusion_goa__Deconf_Space_g4096__s{SEED}.m4a", "g=4096", "space"),
                        make_ext_clip(inspect_data, f"fine_combo_fusion_goa__Deconf_Space_g8192__s{SEED}.m4a", "g=8192", "space"),
                    ]
                },
                {
                    "model_id": "base",
                    "model_name": "Base DiT — Deconf_AntiDark",
                    "badge": "Bipolar Kriging",
                    "clips": [
                        make_ext_clip(inspect_data, f"fine_base__base__s{SEED}.m4a", "g=0", "melodic"),
                        make_ext_clip(inspect_data, f"fine_base__Deconf_AntiDark_g1024__s{SEED}.m4a", "g=1024", "melodic"),
                        make_ext_clip(inspect_data, f"fine_base__Deconf_AntiDark_g2048__s{SEED}.m4a", "g=2048", "melodic"),
                        make_ext_clip(inspect_data, f"fine_base__Deconf_AntiDark_g4096__s{SEED}.m4a", "g=4096", "melodic"),
                        make_ext_clip(inspect_data, f"fine_base__Deconf_AntiDark_g8192__s{SEED}.m4a", "g=8192", "melodic"),
                    ]
                }
            ]
        }
    ]


def write_run_meta(actual_ready_distinct, total_distinct):
    existing_feedback = None
    if RUN_META_JSON.exists():
        try:
            existing_feedback = json.loads(RUN_META_JSON.read_text()).get("kim_feedback")
        except Exception:
            existing_feedback = None
    meta = {
        "purpose": "Single-prompt (rb_bracket_0, seed 1102008041) weight ladder (g=0..8192, plus extended g=6144/12288 and negative guidance) across 8 model/adapter configurations and 9 56-dim Mood LatCH targets (3 sparse 3-tag, 1 Aliens 20s time-series, 5 conditionally de-confounded).",
        "hypothesis": "Test how different adapters (Medium Base, AdamW ep5, Fusion r128 ep159, Goa r128 ep63, 50/50 blends, Full-FT ep39) respond across a fine guidance gain ladder on one prompt, and whether completing unspecified mood dimensions via the 27x27 Goa logit covariance reduces collateral suppression of melodic.",
        "recipe": {
            "script": "eval/build_mood_finegrained_page.py",
            "prompt_id": "rb_bracket_0",
            "prompt": PROMPT,
            "seed": SEED,
            "n_prompts": 1,
            "n_seeds_per_cell": 1,
            "sampler": "euler (24 steps, CFG 7.0, 20.0s)",
            "baseline_g0_source": "unguided generate() (NOT guided sampler at gain=0; carries MASTER section 5 baseline confound)",
            "disintegration_gate": "not run on this page",
            "head": "56-dim Essentia mtg_jamendo_moodtheme LatCH probe ep40 (val loss 0.0598), cosine loss (n_iter=4, gamma=0.3)"
        },
        "result": (
            f"{actual_ready_distinct}/{total_distinct} clips rendered on 1 prompt and 1 seed (not established). "
            "Aliens HQ moves Goa renders very little because its 20s slice sits at 0.95-0.99 cosine similarity to unguided Goa renders (flat temporal std < 0.03). "
            "On this 1 prompt, naive 3-tag targets moved their own tag more than Deconf_* at equal gain (Space 16/16, Dark 14/16, Melodic 12/16); "
            "like-for-like Deconf_Melodic vs Melodic on Goa LoRA was flat (+0.005..+0.012), while Deconf_Uplifting (+0.156) and Deconf_AntiDark (+0.148) raised melodic on Goa LoRA at g=8192. "
            "Multi-prompt verification (15 prompts x 4 models, guided g=0 baseline, disintegration gate) is in eval/mood_deconf_render.py and eval/mood_deconf_report.py."
        ),
        "kim_feedback": existing_feedback or {
            "date": "2026-11-03",
            "verbatim": "I wonder why the Total Eclipse steering target doesn't seen to do nearly anything on many tracks? It's a bit of hit and miss if the control heads take note, but everthing is promising. The descriptions on the changes on the boxes where the user chooses the adapter seem completely hallucinated. You can already add to the page's introduction that the range of useful weight and the sweet spot for the different adapters vary greatly depending on the source material.",
            "summary": "Aliens target barely moves many tracks; control heads are hit-or-miss across tracks/adapters though promising overall; range of useful weight varies greatly by adapter and source material."
        }
    }
    RUN_META_JSON.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")


def main():
    AAC_DIR.mkdir(parents=True, exist_ok=True)
    inspect_data = {}
    if INSPECT_JSON.exists():
        try:
            with open(INSPECT_JSON, "r") as f:
                inspect_data = json.load(f)
            print(f"Loaded inspector data for {len(inspect_data)} clips")
        except Exception as e:
            print(f"Warning: could not load inspector json: {e}")

    matrix_data = build_matrix_data(inspect_data)
    extreme_data = build_extreme_and_neg_data(inspect_data)

    matrix_json = json.dumps(matrix_data)
    models_json = json.dumps(MODELS)
    targets_json = json.dumps(TARGETS)
    weights_json = json.dumps(WEIGHTS)
    extreme_json = json.dumps(extreme_data)
    inspect_json = json.dumps(inspect_data)

    distinct_files = set()
    for t in TARGETS:
        for m in MODELS:
            for w in WEIGHTS:
                cell = matrix_data[t["id"]][m["id"]][str(w)]
                if cell.get("ready") and cell.get("file"):
                    distinct_files.add(cell["file"])
    actual_ready_distinct = len(distinct_files)
    total_distinct = len(distinct_files)
    pct = 100.0

    write_run_meta(actual_ready_distinct, total_distinct)
    notes_html = notes_block("mood_finegrained", levels=[("clip", "this clip"), ("page", "page")],
                             hint="click a clip in the matrix, then record a listening note")

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>56-dim Mood LatCH Fine-Grained Weight Ladder — Evals</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="evals.css">
<style>
.wrap {{ max-width: 1420px; }}
body.inspector-open .wrap {{
    margin-right: 430px;
    max-width: calc(100vw - 450px);
}}
.findings-box {{
    background: var(--paper-dim);
    border: 1px solid var(--rule);
    border-left: 3px solid var(--edge);
    padding: 12px 16px;
    margin: 12px 0 16px 0;
    font-size: 12px;
    line-height: 1.65;
    color: var(--body);
}}
.findings-box b {{ color: var(--ink); }}
.findings-box ul {{ margin: 6px 0 0 18px; }}
.findings-box li {{ margin-bottom: 5px; }}
.caveat-box {{
    background: #fff8f6;
    border: 1px solid var(--rule);
    border-left: 3px solid #b42318;
    padding: 10px 14px;
    margin: 10px 0 16px 0;
    font-size: 12px;
    line-height: 1.6;
    color: var(--body);
}}
.caveat-box b {{ color: var(--ink); }}
.meta-strip {{
    display: flex;
    flex-wrap: wrap;
    gap: 14px;
    padding: 8px 12px;
    background: var(--paper-dim);
    border: 1px solid var(--rule);
    font-size: 11px;
    color: var(--dim);
    margin-bottom: 16px;
}}
.meta-strip b {{ color: var(--ink); }}
.target-tabs-bar {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(265px, 1fr));
    gap: 8px;
    margin-bottom: 18px;
}}
.target-tab {{
    background: var(--paper-dim);
    border: 1px solid var(--rule);
    padding: 9px 11px;
    cursor: pointer;
    text-align: left;
}}
.target-tab:hover {{ border-color: var(--edge); }}
.target-tab.active {{
    background: #e6f4f3;
    border-color: var(--edge);
    border-top: 2px solid var(--edge);
}}
.tab-name {{
    font-size: 12px;
    font-weight: 600;
    color: var(--ink);
    display: flex;
    justify-content: space-between;
    align-items: baseline;
}}
.target-tab.active .tab-name {{ color: var(--edge-ink); }}
.tab-spec {{
    font-size: 10px;
    color: var(--edge-ink);
    margin: 2px 0 4px 0;
    font-variant-numeric: tabular-nums;
}}
.tab-desc {{
    font-size: 11px;
    color: var(--dim);
    line-height: 1.4;
}}
.matrix-card {{
    border: 1px solid var(--rule);
    overflow-x: auto;
    margin-bottom: 22px;
}}
table.matrix-table {{
    width: 100%;
    border-collapse: collapse;
    min-width: 1000px;
    font-size: 11px;
}}
table.matrix-table th, table.matrix-table td {{
    padding: 6px 7px;
    border-bottom: 1px solid var(--rule-light);
    border-right: 1px solid var(--rule-light);
    text-align: left;
    vertical-align: top;
}}
table.matrix-table th {{
    background: var(--paper-dim);
    color: var(--dim);
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    border-bottom: 1px solid var(--rule);
}}
table.matrix-table th.col-model {{ width: 245px; }}
table.matrix-table th.col-w {{ text-align: center; width: 90px; }}
table.matrix-table th.col-w-base {{ text-align: center; width: 96px; border-right: 2px solid var(--rule); }}
td.col-model-info {{
    background: var(--paper-dim);
    border-right: 1px solid var(--rule);
}}
.model-name {{ font-size: 12px; font-weight: 600; color: var(--ink); }}
.model-badge {{
    display: inline-block;
    font-size: 9px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding: 1px 5px;
    border: 1px solid var(--rule);
    color: var(--dim);
    background: var(--paper);
    margin: 2px 0 4px 0;
}}
.model-desc {{ font-size: 10px; color: var(--dim); line-height: 1.35; }}
td.cell-w {{ text-align: center; padding: 4px; vertical-align: middle; }}
td.cell-w-base {{ border-right: 2px solid var(--rule) !important; background: var(--paper-dim); }}
.cell.clip-btn {{
    width: 100%;
    min-height: 48px;
    font-family: var(--mono);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 4px 3px;
    gap: 1px;
}}
.cell.clip-btn.pending {{ opacity: 0.35; cursor: not-allowed; }}
.cell.clip-btn .w-label {{ font-size: 11px; font-weight: 600; }}
.cell.clip-btn .m-line {{ font-size: 9px; color: var(--dim); font-variant-numeric: tabular-nums; }}
.exp-block {{
    border: 1px solid var(--rule);
    padding: 12px 14px;
    margin-bottom: 16px;
    overflow-x: auto;
}}
.exp-header h3 {{ font-size: 12px; font-weight: 600; color: var(--ink); margin: 0 0 2px 0; }}
.exp-header p {{ font-size: 11px; color: var(--dim); margin: 0 0 8px 0; }}
.ext-table {{ width: 100%; border-collapse: collapse; font-size: 11px; }}
.ext-table th, .ext-table td {{ padding: 6px 8px; border: 1px solid var(--rule-light); }}
.ext-table th {{ background: var(--paper-dim); color: var(--dim); font-size: 10px; text-transform: uppercase; }}
.metric-tag {{ font-size: 10px; color: var(--body); font-variant-numeric: tabular-nums; }}
.analysis-section {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
    gap: 14px;
    margin: 18px 0;
}}
.analysis-card {{
    background: var(--paper-dim);
    border: 1px solid var(--rule);
    padding: 12px 14px;
    font-size: 12px;
    color: var(--body);
    line-height: 1.6;
}}
.analysis-card h3 {{
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--ink);
    margin: 0 0 8px 0;
    padding-bottom: 5px;
    border-bottom: 1px solid var(--rule-light);
}}
.analysis-card p {{ margin: 0 0 8px 0; }}
.analysis-card ul {{ margin: 0 0 8px 18px; }}
.analysis-card li {{ margin-bottom: 4px; }}
.dsp-table {{ width: 100%; border-collapse: collapse; margin: 6px 0; font-size: 10px; }}
.dsp-table th, .dsp-table td {{ padding: 4px 6px; border: 1px solid var(--rule-light); text-align: right; font-variant-numeric: tabular-nums; }}
.dsp-table th:first-child, .dsp-table td:first-child {{ text-align: left; }}
.dsp-table th {{ background: var(--paper); color: var(--dim); }}

/* Slide-out Inspector Drawer */
.inspector-drawer {{
    position: fixed;
    top: 0;
    right: 0;
    width: 410px;
    bottom: 52px;
    background: var(--paper);
    border-left: 1px solid var(--rule);
    z-index: 999;
    display: flex;
    flex-direction: column;
    transform: translateX(100%);
    transition: transform 0.2s ease;
}}
.inspector-drawer.open {{ transform: translateX(0); }}
.inspector-toggle-tab {{
    position: fixed;
    right: 0;
    top: 110px;
    background: var(--paper-dim);
    border: 1px solid var(--rule);
    border-right: none;
    padding: 10px 6px;
    cursor: pointer;
    color: var(--edge-ink);
    font-family: var(--mono);
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.08em;
    z-index: 1001;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
}}
body.inspector-open .inspector-toggle-tab {{ right: 410px; }}
.inspector-header {{
    padding: 9px 12px;
    border-bottom: 1px solid var(--rule);
    background: var(--paper-dim);
    display: flex;
    justify-content: space-between;
    align-items: center;
}}
.inspector-title {{ font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; color: var(--ink); }}
.inspector-close-btn {{ background: none; border: 1px solid var(--rule); color: var(--dim); font-family: var(--mono); font-size: 11px; cursor: pointer; padding: 2px 6px; }}
.inspector-body {{ flex: 1; overflow-y: auto; padding: 10px; display: flex; flex-direction: column; gap: 8px; }}
.inspect-card {{ background: var(--paper-dim); border: 1px solid var(--rule); padding: 9px 11px; font-size: 11px; }}
.inspect-card-title {{
    font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--dim);
    margin-bottom: 6px; padding-bottom: 3px; border-bottom: 1px solid var(--rule-light);
    display: flex; justify-content: space-between; align-items: center;
}}
.key-badge {{ font-size: 14px; font-weight: 600; color: var(--ink); }}
.tonal-locked {{ font-size: 10px; color: var(--edge-ink); border: 1px solid var(--edge); padding: 1px 5px; }}
.tonal-shifted {{ font-size: 10px; color: #9e2a2b; border: 1px solid #9e2a2b; padding: 1px 5px; }}
.chord-bar-item {{ display: flex; align-items: center; font-size: 10px; margin-top: 3px; }}
.chord-label {{ width: 40px; font-weight: 600; color: var(--ink); }}
.chord-bar-track {{ flex: 1; height: 5px; background: var(--paper); border: 1px solid var(--rule-light); margin: 0 6px; }}
.chord-bar-fill {{ height: 100%; background: var(--edge); }}
.chord-pct {{ width: 42px; text-align: right; color: var(--dim); font-size: 10px; }}
.chord-flow-box {{ margin-top: 6px; padding: 5px 7px; background: var(--paper); border: 1px solid var(--rule-light); font-size: 10px; color: var(--body); }}
.audiobox-grid, .dsp-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }}
.aes-meter, .dsp-box {{ background: var(--paper); border: 1px solid var(--rule-light); padding: 5px 7px; }}
.aes-header {{ display: flex; justify-content: space-between; font-size: 10px; color: var(--dim); }}
.aes-val {{ font-size: 12px; font-weight: 600; color: var(--ink); margin-top: 2px; }}
.dsp-box-lbl {{ font-size: 9px; color: var(--dim); text-transform: uppercase; }}
.dsp-box-val {{ font-size: 11px; font-weight: 600; color: var(--ink); margin-top: 2px; }}
.moods-table {{ width: 100%; border-collapse: collapse; font-size: 10px; }}
.moods-table th, .moods-table td {{ padding: 2px 4px; border-bottom: 1px solid var(--rule-light); }}
.moods-table th {{ color: var(--dim); text-align: left; }}
.delta-pos {{ color: var(--edge-ink); font-weight: 600; }}
.delta-neg {{ color: #9e2a2b; font-weight: 600; }}
.delta-zero {{ color: var(--faint); }}
</style>
</head>
<body class="inspector-open">
<div class="wrap">
<p class="over">VIBE ON THE EDG3 · EVALS</p>
<p class="nav"><a href="index.html">← all evals</a></p>

<h1>56-dim Mood LatCH: Fine-Grained Weight Ladder &amp; De-Confounded Targets <span class="unaudited" title="Initial listening note recorded; full matrix verdict pending.">&#10071;</span></h1>

<p>
  <b>What this tests and why.</b> This page sweeps guidance gain <code>g = 0..8192</code> (plus extended <code>g = 6144, 12288</code> and negative guidance) across 8 model/adapter configurations and 9 targets for the 56-dim Essentia <code>mtg_jamendo_moodtheme</code> LatCH probe (<code>ep40</code>, validation loss <code>0.0598</code>). Related mood and chroma listening pages: <a href="choice_clips_mood.html">choice_clips_mood.html</a> tests this head across 6 models at <code>g=1024, 2048</code>, <a href="mood_oppose.html">mood_oppose.html</a> tests reinforcement vs. opposition on 2 prompts, and <a href="choice_clips_chroma.html">choice_clips_chroma.html</a> / <a href="ep10_vs_ep40_chroma.html">ep10_vs_ep40_chroma.html</a> test the 384-dim chroma head.
</p>

<div class="caveat-box">
  <b>Scope, Baseline &amp; Disintegration Gate Disclosures (Not Established):</b>
  <ul style="margin:5px 0 0 18px;">
    <li><b>One prompt and one seed (not established):</b> Every cell on this page uses a single prompt (<code>rb_bracket_0</code>: <code>"{PROMPT}"</code>) and a single seed (<code>{SEED}</code>, <code>n = 1</code> per cell). One prompt and one seed establish nothing; all trends below are single-seed observations, <b>not established</b> results. WINTERMUTE's 15-prompt &times; 4-model run (<code>eval/mood_deconf_render.py</code> / <code>eval/mood_deconf_report.py</code>) tested these targets across prompts: see <a href="mood_deconf.html">the 15-prompt page</a>.</li>
    <li><b>Disintegration gate not run on this page:</b> The automated disintegration gate (<code>control_head_disintegration_eval.gate()</code>) has not been run on the clips in this table. Without the gate, this page does <b>not</b> establish a usable gain range or a confirmed sweet spot. As an informal listening observation, the range of useful weight varies strongly depending on the adapter and source material.</li>
    <li><b>Unguided <code>g=0</code> baseline confound (MASTER &sect;5):</b> The <code>g=0</code> clips on this page were rendered with unguided <code>generate()</code> rather than the guided sampler at <code>gain=0</code>, so differences between <code>g=0</code> and <code>g &gt; 0</code> combine guidance steering with the guided-sampler trajectory difference.</li>
  </ul>
</div>

<div class="findings-box">
  <b>Listening &amp; Diagnostic Notes on This 1-Prompt / 1-Seed Sweep:</b>
  <ul>
    <li><b>Why <code>Total Eclipse - Aliens HQ</code> barely moves many Goa tracks:</b> The 20s Essentia mood slice from <i>Total Eclipse - Aliens</i> (<code>sample 6073122</code>, <code>137.7s..157.7s</code>) has mean profile <code>melodic = 0.404, space = 0.161, energetic = 0.123, retro = 0.070</code> with very small temporal variance across the 20s window (<code>std &lt; 0.03</code> per channel). This vector sits at <b>0.84 cosine similarity to the Goa corpus centroid</b> and <b>0.95 to 0.99 cosine similarity to our unguided <code>g=0</code> Goa/Fusion renders</b>. Because cosine distance loss <code>1 - &lt;p&#770;, t&#770;&gt;</code> has gradient norm proportional to <code>sin(&theta;)</code>, steering a render whose baseline mood is already nearly collinear with the target yields a near-zero gradient.</li>
    <li><b>Adapter response differences:</b> Different adapters and source prompts respond at very different gain scales. On this seed, unadapted <code>Medium Base</code> peaks in classifier <code>melodic</code> score around <code>g = 1024..2048</code> before turning downward at higher gains, whereas rank-128 LoRA adapters (<code>Goa LoRA ep63</code>, <code>Fusion LoRA ep159</code>) tolerate higher numerical gains before audible breakup.</li>
    <li><b>Sparse 3-Tag vs. Conditional De-Confounding (E25 Review Summary):</b> Setting 53 of 56 channels to zero under cosine loss pushes unmentioned mood tags downward and interacts with the 10 stock-library tags (<code>advertising, corporate, commercial, ...</code>) that share a common-mode ReLU factor (77.6% variance). However, on this 1-prompt sweep, naive 3-tag targets moved their own requested tag more than <code>Deconf_*</code> at equal gain (<code>Space</code> 16/16 cells, <code>Dark</code> 14/16, <code>Melodic</code> 12/16). Like-for-like <code>Deconf_Melodic</code> vs. naive <code>Melodic</code> on <code>Goa LoRA</code> was flat (<code>+0.005</code> to <code>+0.012</code>); the targets that raised <code>melodic</code> on <code>Goa LoRA</code> (<code>0.509 &rarr; 0.665</code> and <code>0.657</code> at <code>g=8192</code>) were <code>Deconf_Uplifting</code> and <code>Deconf_AntiDark</code>, whose largest positive entries are <code>melodic</code> (<code>0.355</code>) and <code>energetic</code>. Across all 16 model &times; gain cells, key retention was no higher overall for <code>Deconf_*</code> (<code>Melodic</code> naive 15/16 vs deconf 13/16; <code>Space</code> 11/16 vs 11/16; <code>Dark</code> 10/16 vs 10/16).</li>
  </ul>
</div>

<div class="meta-strip">
  <span>Prompt: <b>"{PROMPT}" (rb_bracket_0, n=1)</b></span>
  <span>Seed: <b>{SEED} (n=1)</b></span>
  <span>CFG: <b>{CFG}</b></span>
  <span>Duration: <b>{DURATION}s (24 Euler steps)</b></span>
  <span>Loss: <b>Cosine (n_iter=4, &gamma;=0.3)</b></span>
  <span>Clips Ready: <b id="readyStatus">{actual_ready_distinct}/{total_distinct} ({pct}%)</b></span>
  <span>Playhead: <b>Preserved across clip switches · Re-click pauses</b></span>
</div>

<h2><span class="mark">&sect;</span> 1 · Target Selector (Click to Switch Matrix Target)</h2>
<p class="dim">9 targets: 3 sparse 3-tag, 1 reference track time-series (Aliens HQ), 5 conditionally de-confounded (Kriging). All descriptions below report single-seed measurements on <code>rb_bracket_0</code> (not established).</p>
<div class="target-tabs-bar" id="targetTabsBar"></div>

<h2><span class="mark">&sect;</span> 2 · Model &times; Guidance Weight Matrix (n = 1 prompt, 1 seed)</h2>
<p class="dim">Each cell shows the measured Essentia score for the target's primary tag and Audiobox CE (1–10). Click any cell to switch immediately at the current playhead time; click the playing cell again to pause.</p>
<div class="matrix-card">
  <table class="matrix-table" id="matrixTable">
    <thead>
      <tr>
        <th class="col-model">Model / Blend Configuration</th>
        <th class="col-w-base">Base (g=0)<br><span style="font-weight:normal;color:var(--faint);">Unguided gen()</span></th>
        <th class="col-w">g = 256</th>
        <th class="col-w">g = 512</th>
        <th class="col-w">g = 1024</th>
        <th class="col-w">g = 1536</th>
        <th class="col-w">g = 2048</th>
        <th class="col-w">g = 3072</th>
        <th class="col-w">g = 4096</th>
        <th class="col-w">g = 8192</th>
      </tr>
    </thead>
    <tbody id="matrixTableBody"></tbody>
  </table>
</div>

<h2><span class="mark">&sect;</span> 3 · Extended Weight Sweeps (g=0..12288), Negative Guidance &amp; De-Confounding (n = 1 seed)</h2>
<p class="dim">Single-seed comparisons on <code>rb_bracket_0</code> (seed <code>{SEED}</code>). Classifier scores measure movement along the probe's own teacher model, not audio quality.</p>
<div id="extremeExperimentsContainer"></div>

<h2><span class="mark">&sect;</span> 4 · Single-Seed Acoustic Diagnostics (n = 1 prompt, not established)</h2>
<div class="analysis-section">
  <div class="analysis-card">
    <h3>Negative Dark &amp; Bipolar Steering on Seed {SEED}</h3>
    <p>
      On this prompt and seed, subtracting <code>Dark</code> (<code>-Dark</code> or <code>Deconf_AntiDark</code>) reduces the Essentia <code>deep</code> score by 23%–33% and raises spectral centroid by +70 to +240 Hz.
    </p>
    <p>
      On <code>Medium Base</code>, <code>Deconf_AntiDark</code> raises classifier <code>melodic</code> from <code>0.1847</code> (<code>g=0</code>) to <code>0.2951</code> (<code>g=8192</code>) on this seed while staying in D minor, whereas sparse <code>Melodic</code> peaks at <code>0.2752</code> (<code>g=2048</code>). Whether this holds across prompts is not established by <code>n=1</code>.
    </p>
  </div>

  <div class="analysis-card">
    <h3>Key &amp; Mode Changes Observed on Seed {SEED}</h3>
    <p>
      Across all 16 model &times; gain cells on this single prompt, key retention vs. <code>g=0</code> was <b>15/16</b> for naive <code>Melodic</code> vs. <b>13/16</b> for <code>Deconf_Melodic</code>, <b>11/16</b> vs. <b>11/16</b> for <code>Space</code>, and <b>10/16</b> vs. <b>10/16</b> for <code>Dark</code>. Individual cell transitions on this seed include:
    </p>
    <ul>
      <li><b>AdamW under Sparse Dark:</b> Shifts from <code>C minor &rarr; Ab major</code> at <code>g &ge; 1536</code> on this seed.</li>
      <li><b>Base DiT under Sparse Dark vs. Deconf_Dark:</b> Sparse <code>Dark</code> shifts <code>D minor &rarr; G minor</code> at <code>g=8192</code>; <code>Deconf_Dark</code> stays in <code>D minor</code> (while moving <code>dark</code> less at equal gain).</li>
      <li><b>Goa LoRA under Aliens HQ:</b> Shifts from parallel <code>C major &rarr; C minor</code> at <code>g &ge; 2048</code> as <code>melodic</code> moves from <code>0.509</code> toward the <code>Aliens</code> mean (<code>0.404</code>).</li>
    </ul>
  </div>

  <div class="analysis-card">
    <h3>Multiband RMS Profile Under Space Guidance (Base DiT, Seed {SEED})</h3>
    <p>
      On <code>Medium Base</code> under sparse <code>Space</code> guidance (1 seed), broadband RMS changes by 0.85 dB from <code>g=0</code> to <code>g=3072</code> while energy shifts from 80–2000 Hz into sub-80 Hz:
    </p>
    <table class="dsp-table">
      <thead>
        <tr>
          <th>Weight</th>
          <th>Total RMS</th>
          <th>Sub (20-80Hz)</th>
          <th>Bass (80-300Hz)</th>
          <th>Mid (300-2kHz)</th>
          <th>Hi-Mid (2-8k)</th>
          <th>Air (8-20k)</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><b>g = 0</b></td>
          <td>-15.27 dB</td>
          <td>-16.13 dB</td>
          <td>-25.54 dB</td>
          <td>-28.16 dB</td>
          <td>-30.50 dB</td>
          <td>-40.92 dB</td>
        </tr>
        <tr>
          <td><b>g = 1024</b></td>
          <td>-14.84 dB</td>
          <td>-15.42 dB</td>
          <td>-26.64 dB</td>
          <td>-29.75 dB</td>
          <td>-30.97 dB</td>
          <td>-41.79 dB</td>
        </tr>
        <tr>
          <td><b>g = 3072 (&Delta;)</b></td>
          <td>-14.42 dB</td>
          <td>+1.27 dB</td>
          <td>-2.10 dB</td>
          <td>-2.08 dB</td>
          <td>-0.92 dB</td>
          <td>+0.33 dB</td>
        </tr>
      </tbody>
    </table>
  </div>

  <div class="analysis-card">
    <h3>Equal-Gain vs. Matched-Movement De-Confounding Trade-Off</h3>
    <p>
      In <code>mtg_jamendo_moodtheme-discogs-effnet-1.onnx</code>, all 56 output weight rows have negative means multiplying non-negative ReLU features, making the 10 dead stock-library tags act as a common-mode factor (77.6% variance, <code>r = 0.988</code> with mean logit).
    </p>
    <ul>
      <li><b>Less collateral drop, but also less own-tag push at equal gain:</b> On <code>Combo Fusion + Goa</code> at <code>g=2048</code>, sparse <code>Space</code> moves <code>space</code> to <code>0.168</code> while dropping <code>melodic</code> from <code>0.607 &rarr; 0.243</code>; <code>Deconf_Space</code> retains <code>melodic = 0.389</code>, but only moves <code>space</code> to <code>0.119</code>.</li>
      <li><b>Multi-prompt evaluation:</b> Comparing collateral movement at <i>matched</i> own-tag movement across 15 prompts and 4 models (with a true guided <code>g=0</code> baseline and the disintegration gate) is performed in <code>eval/mood_deconf_report.py</code>.</li>
    </ul>
  </div>
</div>

{notes_html}
</div>

<!-- Slide-out Side-Tab Inspector Drawer -->
<div id="inspectorDrawer" class="inspector-drawer open">
  <div class="inspector-header">
    <div class="inspector-title">Clip &amp; Harmonic Inspector</div>
    <button class="inspector-close-btn" onclick="toggleInspector()" title="Close Inspector">[x]</button>
  </div>
  <div class="inspector-body" id="inspectorBody">
    <div style="color:var(--dim); font-size:11px; text-align:center; padding:24px 8px;">
      Click any clip in the matrix to inspect its measured Essentia, chord, DSP, and Audiobox metrics.
    </div>
  </div>
</div>

<button id="inspectorToggleTab" class="inspector-toggle-tab" onclick="toggleInspector()" title="Toggle Inspector Panel">
  <span id="inspectorToggleIcon">&gt;</span>
  <span style="writing-mode: vertical-lr; transform: rotate(180deg);">INSPECTOR</span>
</button>

<audio id="audioPlayer" preload="auto" style="display:none"></audio>

<script>
const MATRIX = {matrix_json};
const MODELS = {models_json};
const TARGETS = {targets_json};
const WEIGHTS = {weights_json};
const EXTREME = {extreme_json};
const INSPECT = {inspect_json};

let currentTarget = "Melodic";
let currentModelId = null;
let currentWeight = null;
let currentCustomUrl = null;
let currentActiveFile = null;
let isPlaying = false;
let inspectorOpen = true;
let lastKnownTime = 0;

const audio = document.getElementById("audioPlayer");
const drawer = document.getElementById("inspectorDrawer");
const toggleIcon = document.getElementById("inspectorToggleIcon");
const inspectorBody = document.getElementById("inspectorBody");

function init() {{
    renderTabs();
    renderMatrix();
    renderExtremeSection();
    setupAudioEvents();
    setupKeyboard();
    updateInspector("fine_base__base__s1102008041.m4a");
}}

function toggleInspector() {{
    inspectorOpen = !inspectorOpen;
    if (inspectorOpen) {{
        drawer.classList.add("open");
        document.body.classList.add("inspector-open");
        toggleIcon.textContent = ">";
    }} else {{
        drawer.classList.remove("open");
        document.body.classList.remove("inspector-open");
        toggleIcon.textContent = "<";
    }}
}}

function primaryMetricForTarget(tId, clip) {{
    if (tId.includes("Space")) return clip.spc !== null && clip.spc !== undefined ? `spc ${{clip.spc.toFixed(3)}}` : "";
    if (tId === "Dark" || tId === "Deconf_Dark") return clip.drk !== null && clip.drk !== undefined ? `drk ${{clip.drk.toFixed(3)}}` : "";
    return clip.mel !== null && clip.mel !== undefined ? `mel ${{clip.mel.toFixed(3)}}` : "";
}}

function renderTabs() {{
    const bar = document.getElementById("targetTabsBar");
    bar.innerHTML = "";
    TARGETS.forEach(t => {{
        const active = (t.id === currentTarget) ? "active" : "";
        const tab = document.createElement("div");
        tab.className = `target-tab ${{active}}`;
        tab.onclick = () => selectTarget(t.id);
        tab.innerHTML = `
            <div class="tab-name">
                <span>${{t.full_name}}</span>
                <span style="font-size:10px;color:var(--faint);">[${{t.id}}]</span>
            </div>
            <div class="tab-spec">${{t.spec}}</div>
            <div class="tab-desc">${{t.desc}}</div>
        `;
        bar.appendChild(tab);
    }});
}}

function selectTarget(targetId) {{
    if (currentTarget === targetId) return;
    currentTarget = targetId;
    renderTabs();
    renderMatrix();
    if (currentModelId && currentWeight !== null) {{
        playClip(currentModelId, currentWeight, true);
    }}
}}

function renderMatrix() {{
    const tbody = document.getElementById("matrixTableBody");
    tbody.innerHTML = "";

    MODELS.forEach(m => {{
        const tr = document.createElement("tr");
        tr.className = "model-row";
        tr.id = `row-${{m.id}}`;

        let cellsHtml = `
            <td class="col-model-info">
                <div class="model-name">${{m.name}}</div>
                <span class="model-badge">${{m.badge}}</span>
                <div class="model-desc">${{m.desc}}</div>
            </td>
        `;

        WEIGHTS.forEach(w => {{
            const clip = MATRIX[currentTarget][m.id][w.toString()];
            const isBase = (w === 0);
            const baseClass = isBase ? "cell-w-base" : "";
            if (!clip || !clip.ready) {{
                cellsHtml += `<td class="cell-w ${{baseClass}}"><span class="dim">&mdash;</span></td>`;
                return;
            }}
            const isCurrent = (currentModelId === m.id && currentWeight === w && currentCustomUrl === null);
            const statusClass = (isCurrent && isPlaying) ? "playing" : "ready";
            const icon = (isCurrent && isPlaying) ? "||" : "&#9654;";
            const label = isBase ? "g=0" : `g=${{w}}`;
            const m1 = primaryMetricForTarget(currentTarget, clip);
            const m2 = clip.ce ? `CE ${{clip.ce.toFixed(2)}}` : `${{clip.size_kb}} KB`;

            cellsHtml += `
                <td class="cell-w ${{baseClass}}">
                    <button class="cell clip-btn ${{statusClass}}" data-src="${{clip.url}}" id="btn-${{m.id}}-${{w}}" onclick="handleCellClick('${{m.id}}', ${{w}})" title="${{clip.file}} (${{clip.key || ''}})">
                        <span class="w-label"><span class="play-icon">${{icon}}</span> ${{label}}</span>
                        <span class="m-line">${{m1}}</span>
                        <span class="m-line">${{m2}}</span>
                    </button>
                </td>
            `;
        }});

        tr.innerHTML = cellsHtml;
        tbody.appendChild(tr);
    }});
}}

function handleCellClick(modelId, weight) {{
    const clip = MATRIX[currentTarget][modelId][weight.toString()];
    if (!clip.ready) return;

    updateInspector(clip.file);
    if (window.noteSet) noteSet({{model: modelId, ckpt: currentTarget, clip: clip.file}});

    if (currentModelId === modelId && currentWeight === weight && currentCustomUrl === null) {{
        togglePlay();
    }} else {{
        playClip(modelId, weight, true);
    }}
}}

function renderExtremeSection() {{
    const container = document.getElementById("extremeExperimentsContainer");
    if (!container) return;
    container.innerHTML = "";

    EXTREME.forEach((cat) => {{
        const block = document.createElement("div");
        block.className = "exp-block";

        let tableHtml = `
            <div class="exp-header">
                <h3>${{cat.category}}</h3>
                <p>${{cat.subtitle}}</p>
            </div>
            <table class="ext-table">
                <thead>
                    <tr>
                        <th style="width: 220px;">Model / Condition</th>
        `;

        cat.weights.forEach(w => {{
            tableHtml += `<th style="text-align:center;">${{w}}</th>`;
        }});

        tableHtml += `
                    </tr>
                </thead>
                <tbody>
        `;

        cat.rows.forEach(r => {{
            tableHtml += `
                <tr>
                    <td>
                        <div style="font-weight:600; color:var(--ink);">${{r.model_name}}</div>
                        <span class="model-badge">${{r.badge}}</span>
                    </td>
            `;

            r.clips.forEach(c => {{
                const cleanId = c.file.replace(/[^a-zA-Z0-9]/g, "_");
                const isPlayingThis = (currentCustomUrl && currentCustomUrl.includes(c.file) && isPlaying);
                const playIcon = isPlayingThis ? "||" : "&#9654;";

                const pVal = (c.primary_val !== null && c.primary_val !== undefined)
                    ? `${{c.primary_dim.slice(0,3)}}: ${{c.primary_val.toFixed(4)}}`
                    : "";
                const cVal = (c.crest !== null && c.crest !== undefined)
                    ? `crest: ${{c.crest.toFixed(2)}}`
                    : "";

                tableHtml += `
                    <td style="text-align:center;">
                        <button class="cell ${{isPlayingThis ? 'playing' : ''}}" data-src="mood_finegrained/${{c.file}}" id="extbtn-${{cleanId}}" onclick="playCustomClip('mood_finegrained/${{c.file}}', '${{r.model_name}} — ${{c.label}}', '${{c.file}}')">
                            <span>${{playIcon}}</span>
                            <span>${{c.label}}</span>
                        </button>
                        <div style="margin-top:4px; display:flex; flex-direction:column; gap:1px; align-items:center;">
                            <span class="metric-tag"><b>${{pVal}}</b></span>
                            <span class="metric-tag">${{cVal}}</span>
                            <span style="font-size:9px; color:var(--dim);">${{c.note}}</span>
                        </div>
                    </td>
                `;
            }});

            tableHtml += `</tr>`;
        }});

        tableHtml += `
                </tbody>
            </table>
        `;

        block.innerHTML = tableHtml;
        container.appendChild(block);
    }});
}}

function updateInspector(filename) {{
    currentActiveFile = filename;
    const d = INSPECT[filename];
    if (!d) {{
        inspectorBody.innerHTML = `
            <div style="color:var(--dim); font-size:11px; text-align:center; padding:24px 8px;">
                No feature data cached for ${{filename}}.
            </div>
        `;
        return;
    }}

    const modelObj = MODELS.find(m => m.id === d.model_id) || {{ name: d.model_id, badge: d.model_id }};
    const tgtObj = TARGETS.find(t => t.id === d.target_id) || {{ name: d.target_id }};
    const weightLabel = d.weight === 0 ? "g=0 (Unguided Base)" : `g = ${{d.weight}}`;

    const tonalPill = d.key_changed
        ? `<span class="tonal-shifted">Shift: ${{d.tonal_shift}}</span>`
        : `<span class="tonal-locked">Key Locked</span>`;

    let chordsHtml = "";
    if (d.dominant_chords && d.dominant_chords.length > 0) {{
        d.dominant_chords.forEach(ch => {{
            chordsHtml += `
                <div class="chord-bar-item">
                    <span class="chord-label">${{ch.chord}}</span>
                    <div class="chord-bar-track">
                        <div class="chord-bar-fill" style="width: ${{Math.min(100, ch.pct)}}%;"></div>
                    </div>
                    <span class="chord-pct">${{ch.pct.toFixed(1)}}%</span>
                </div>
            `;
        }});
    }}

    const ce = d.audiobox.CE || 0;
    const pq = d.audiobox.PQ || 0;
    const cu = d.audiobox.CU || 0;
    const pc = d.audiobox.PC || 0;

    const renderDelta = (v, digits=2) => {{
        if (v > 0.0001) return `<span class="delta-pos">+${{v.toFixed(digits)}}</span>`;
        if (v < -0.0001) return `<span class="delta-neg">${{v.toFixed(digits)}}</span>`;
        return `<span class="delta-zero">0.00</span>`;
    }};

    let moodsHtml = "";
    if (d.top_moods && d.top_moods.length > 0) {{
        d.top_moods.slice(0, 10).forEach(m => {{
            moodsHtml += `
                <tr>
                    <td><b>${{m.dim}}</b></td>
                    <td style="text-align:right; font-variant-numeric: tabular-nums;">${{m.score.toFixed(4)}}</td>
                    <td style="text-align:right; font-variant-numeric: tabular-nums; color:var(--dim);">${{m.base.toFixed(4)}}</td>
                    <td style="text-align:right; font-variant-numeric: tabular-nums;">${{renderDelta(m.delta, 4)}}</td>
                </tr>
            `;
        }});
    }}

    inspectorBody.innerHTML = `
        <div class="inspect-card">
            <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                <div>
                    <div style="font-size:12px; font-weight:600; color:var(--ink);">${{modelObj.name}}</div>
                    <div style="font-size:11px; color:var(--dim); margin-top:2px;">
                        ${{tgtObj.name}} · <b>${{weightLabel}}</b>
                    </div>
                </div>
                <span class="model-badge">${{modelObj.badge}}</span>
            </div>
            <div style="font-size:9px; color:var(--faint); word-break:break-all; margin-top:4px;">
                ${{d.file}}
            </div>
        </div>

        <div class="inspect-card">
            <div class="inspect-card-title">
                <span>Harmonic &amp; Tonal Center</span>
                ${{tonalPill}}
            </div>
            <div style="display:flex; justify-content:space-between; align-items:baseline; margin-bottom:4px;">
                <div class="key-badge">${{d.key}} ${{d.scale}}</div>
                <div style="font-size:10px; color:var(--dim);">Strength: <b>${{(d.key_strength * 100).toFixed(1)}}%</b></div>
            </div>
            <div>${{chordsHtml}}</div>
            <div class="chord-flow-box">
                <span style="color:var(--dim);">Flow:</span> ${{d.chord_flow}}
            </div>
        </div>

        <div class="inspect-card">
            <div class="inspect-card-title">
                <span>Audiobox Aesthetics (1-10)</span>
                <span>&Delta; vs g=0</span>
            </div>
            <div class="audiobox-grid">
                <div class="aes-meter">
                    <div class="aes-header"><span>Enjoyment (CE)</span>${{renderDelta(d.audiobox_deltas.CE)}}</div>
                    <div class="aes-val">${{ce.toFixed(2)}}</div>
                </div>
                <div class="aes-meter">
                    <div class="aes-header"><span>Quality (PQ)</span>${{renderDelta(d.audiobox_deltas.PQ)}}</div>
                    <div class="aes-val">${{pq.toFixed(2)}}</div>
                </div>
                <div class="aes-meter">
                    <div class="aes-header"><span>Usefulness (CU)</span>${{renderDelta(d.audiobox_deltas.CU)}}</div>
                    <div class="aes-val">${{cu.toFixed(2)}}</div>
                </div>
                <div class="aes-meter">
                    <div class="aes-header"><span>Complexity (PC)</span>${{renderDelta(d.audiobox_deltas.PC)}}</div>
                    <div class="aes-val">${{pc.toFixed(2)}}</div>
                </div>
            </div>
        </div>

        <div class="inspect-card">
            <div class="inspect-card-title">
                <span>Top 10 Essentia Mood Dimensions</span>
                <span>&Delta; vs g=0</span>
            </div>
            <table class="moods-table">
                <thead>
                    <tr>
                        <th>Channel</th>
                        <th style="text-align:right;">Score</th>
                        <th style="text-align:right;">g=0</th>
                        <th style="text-align:right;">&Delta;</th>
                    </tr>
                </thead>
                <tbody>${{moodsHtml}}</tbody>
            </table>
        </div>

        <div class="inspect-card">
            <div class="inspect-card-title">
                <span>Acoustic DSP Metrics</span>
                <span>librosa</span>
            </div>
            <div class="dsp-grid">
                <div class="dsp-box">
                    <div class="dsp-box-lbl">Crest Factor</div>
                    <div class="dsp-box-val">${{d.crest_factor.toFixed(2)}} (${{d.crest_delta >= 0 ? '+' : ''}}${{d.crest_delta.toFixed(2)}})</div>
                </div>
                <div class="dsp-box">
                    <div class="dsp-box-lbl">Spectral Centroid</div>
                    <div class="dsp-box-val">${{Math.round(d.spectral_centroid)}} Hz (${{d.sc_delta >= 0 ? '+' : ''}}${{Math.round(d.sc_delta)}} Hz)</div>
                </div>
                <div class="dsp-box">
                    <div class="dsp-box-lbl">RMS Loudness</div>
                    <div class="dsp-box-val">${{d.rms_db.toFixed(2)}} dB (${{d.rms_delta >= 0 ? '+' : ''}}${{d.rms_delta.toFixed(2)}} dB)</div>
                </div>
                <div class="dsp-box">
                    <div class="dsp-box-lbl">HPSS Harm/Perc</div>
                    <div class="dsp-box-val">${{d.hpss_ratio.toFixed(2)}}</div>
                </div>
            </div>
        </div>
    `;
}}

function switchAudioPreserveTime(url) {{
    const prevTime = (audio && audio.currentTime > 0 && !audio.ended) ? audio.currentTime : lastKnownTime;
    audio.src = url;
    const applySeekAndPlay = () => {{
        if (prevTime > 0) {{
            try {{
                audio.currentTime = Math.min(prevTime, (audio.duration || 20.0) - 0.05);
            }} catch (e) {{}}
        }}
        audio.play().catch(e => console.log("Play interrupted", e));
    }};
    if (audio.readyState >= 1) {{
        applySeekAndPlay();
    }} else {{
        audio.addEventListener("loadedmetadata", applySeekAndPlay, {{ once: true }});
    }}
}}

function playClip(modelId, weight, keepTime = true) {{
    const clip = MATRIX[currentTarget][modelId][weight.toString()];
    if (!clip.ready) return;

    currentModelId = modelId;
    currentWeight = weight;
    currentCustomUrl = null;

    switchAudioPreserveTime(clip.url);
    updateButtonStates();
    updateInspector(clip.file);
}}

function playCustomClip(url, title, meta) {{
    const fname = url.replace("mood_finegrained/", "");
    if (window.noteSet) noteSet({{model: title, ckpt: "", clip: fname}});
    if (currentCustomUrl === url) {{
        togglePlay();
        updateInspector(fname);
        return;
    }}

    currentModelId = null;
    currentWeight = null;
    currentCustomUrl = url;

    switchAudioPreserveTime(url);
    updateButtonStates();
    updateInspector(fname);
}}

function togglePlay() {{
    if (!currentModelId && !currentCustomUrl) {{
        for (let m of MODELS) {{
            const c = MATRIX[currentTarget][m.id]["1024"];
            if (c && c.ready) {{
                playClip(m.id, 1024, true);
                return;
            }}
        }}
        return;
    }}
    if (isPlaying) audio.pause();
    else audio.play();
}}

function updateButtonStates() {{
    document.querySelectorAll(".clip-btn").forEach(btn => {{
        btn.classList.remove("playing");
        const iconSpan = btn.querySelector(".play-icon");
        if (iconSpan) iconSpan.innerHTML = "&#9654;";
    }});

    if (currentModelId !== null && currentWeight !== null && currentCustomUrl === null) {{
        const activeBtn = document.getElementById(`btn-${{currentModelId}}-${{currentWeight}}`);
        if (activeBtn && isPlaying) {{
            activeBtn.classList.add("playing");
            const iconSpan = activeBtn.querySelector(".play-icon");
            if (iconSpan) iconSpan.innerHTML = "||";
        }}
    }}

    document.querySelectorAll("#extremeExperimentsContainer .cell").forEach(btn => {{
        btn.classList.remove("playing");
        const iconSpan = btn.querySelector("span:first-child");
        if (iconSpan) iconSpan.innerHTML = "&#9654;";
    }});

    if (currentCustomUrl !== null) {{
        const cleanId = currentCustomUrl.replace("mood_finegrained/", "").replace(/[^a-zA-Z0-9]/g, "_");
        const extBtn = document.getElementById(`extbtn-${{cleanId}}`);
        if (extBtn && isPlaying) {{
            extBtn.classList.add("playing");
            const iconSpan = extBtn.querySelector("span:first-child");
            if (iconSpan) iconSpan.innerHTML = "||";
        }}
    }}
}}

function setupAudioEvents() {{
    audio.addEventListener("play", () => {{
        isPlaying = true;
        updateButtonStates();
    }});
    audio.addEventListener("pause", () => {{
        isPlaying = false;
        updateButtonStates();
    }});
    audio.addEventListener("timeupdate", () => {{
        if (!audio.duration) return;
        lastKnownTime = audio.currentTime;
    }});
    audio.addEventListener("ended", () => {{
        isPlaying = false;
        lastKnownTime = 0;
        updateButtonStates();
    }});
}}

function setupKeyboard() {{
    window.addEventListener("keydown", (e) => {{
        if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;
        if (e.code === "Space") {{
            e.preventDefault();
            togglePlay();
        }} else if (e.code === "ArrowUp") {{
            e.preventDefault();
            navigateModel(-1);
        }} else if (e.code === "ArrowDown") {{
            e.preventDefault();
            navigateModel(1);
        }} else if (e.key === "[") {{
            e.preventDefault();
            navigateWeight(-1);
        }} else if (e.key === "]") {{
            e.preventDefault();
            navigateWeight(1);
        }} else if (["1", "2", "3", "4", "5", "6", "7", "8", "9"].includes(e.key)) {{
            const idx = parseInt(e.key) - 1;
            if (idx < TARGETS.length) selectTarget(TARGETS[idx].id);
        }} else if (e.key.toLowerCase() === "i") {{
            e.preventDefault();
            toggleInspector();
        }}
    }});
}}

function navigateModel(dir) {{
    if (!currentModelId) return;
    const curIdx = MODELS.findIndex(m => m.id === currentModelId);
    if (curIdx === -1) return;
    const nextIdx = (curIdx + dir + MODELS.length) % MODELS.length;
    playClip(MODELS[nextIdx].id, currentWeight, true);
}}

function navigateWeight(dir) {{
    if (currentWeight === null) return;
    const curIdx = WEIGHTS.indexOf(currentWeight);
    if (curIdx === -1) return;
    const nextIdx = (curIdx + dir + WEIGHTS.length) % WEIGHTS.length;
    playClip(currentModelId, WEIGHTS[nextIdx], true);
}}

document.addEventListener("DOMContentLoaded", init);
</script>
</body>
</html>
"""

    html_content = inject(html_content)
    with open(OUT_HTML, "w", encoding="utf-8") as f_out:
        f_out.write(html_content)

    print(f"Generated {OUT_HTML} ({len(html_content)} bytes)")
    print(f"Ready clips: {actual_ready_distinct}/{total_distinct}")


if __name__ == "__main__":
    main()
