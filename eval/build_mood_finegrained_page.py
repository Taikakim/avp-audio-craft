#!/usr/bin/env python3
"""build_mood_finegrained_page.py -- generates interactive HTML dashboard for the
fine-grained weight ladder (g=0, 256, 512, 1024, 1536, 2048, 3072) and 8 model
combinations / adapter blends on benchmark prompt rb_bracket_0.
Outputs: /home/kim/evals_aac/mood_finegrained.html
"""
import os, sys, json
from pathlib import Path

AAC_DIR = Path("/home/kim/evals_aac/mood_finegrained")
OUT_HTML = Path("/home/kim/evals_aac/mood_finegrained.html")

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
        "badge_cls": "badge-base",
        "desc": "Unfine-tuned base SA3 medium model. Zero LoRA/FT adaptation."
    },
    {
        "id": "adamw",
        "name": "AdamW ep5 (avp_t512_bs4_lr5e5)",
        "type": "lora",
        "badge": "LoRA r64",
        "badge_cls": "badge-lora",
        "desc": "Standard AdamW baseline trained on AVP audio dataset (lr=5e-5, ep5)."
    },
    {
        "id": "fusion",
        "name": "Fusion LoRA r128 ep159",
        "type": "lora",
        "badge": "LoRA r128",
        "badge_cls": "badge-lora",
        "desc": "Dorlor FusionOpt rank-128 adapter trained with AVP-augmented data (ep159)."
    },
    {
        "id": "goa",
        "name": "Goa LoRA r128 ep63",
        "type": "lora",
        "badge": "LoRA r128",
        "badge_cls": "badge-lora",
        "desc": "Dorlor FusionOpt rank-128 adapter specialized on Goa trance catalogue (ep63)."
    },
    {
        "id": "combo_adamw_fusion",
        "name": "Combo: AdamW + Fusion (50 / 50)",
        "type": "combo",
        "badge": "Blend 50/50",
        "badge_cls": "badge-combo",
        "desc": "Multi-adapter linear parameter blend: 50% AdamW + 50% Fusion LoRA (w=0.5, 0.5)."
    },
    {
        "id": "combo_adamw_goa",
        "name": "Combo: AdamW + Goa (50 / 50)",
        "type": "combo",
        "badge": "Blend 50/50",
        "badge_cls": "badge-combo",
        "desc": "Multi-adapter linear parameter blend: 50% AdamW + 50% Goa LoRA (w=0.5, 0.5)."
    },
    {
        "id": "combo_fusion_goa",
        "name": "Combo: Fusion + Goa (50 / 50)",
        "type": "combo",
        "badge": "Blend 50/50",
        "badge_cls": "badge-combo",
        "desc": "Multi-adapter linear parameter blend: 50% Fusion + 50% Goa LoRA (w=0.5, 0.5)."
    },
    {
        "id": "fullft",
        "name": "Full Fine-Tune DiT ep39",
        "type": "fullft",
        "badge": "Full-FT",
        "badge_cls": "badge-fullft",
        "desc": "Full fine-tuning of all 24 DiT transformer blocks (A_control ep39)."
    }
]

TARGETS = [
    {
        "id": "Space",
        "name": "Space",
        "full_name": "Space / Ambient Soundscape",
        "icon": "🌌",
        "color": "#38bdf8",
        "desc": "Dominant channel: space=1.0, soundscape=0.3, dream=0.3. Cosmic expansiveness, atmospheric reverb, evolving textures."
    },
    {
        "id": "Dark",
        "name": "Dark",
        "full_name": "Dark / Heavy Night Psy",
        "icon": "🌑",
        "color": "#f43f5e",
        "desc": "Dominant channel: dark=1.0, heavy=0.4, deep=0.3. Menacing FM leads, deep rolling basslines, tense nocturnal atmosphere."
    },
    {
        "id": "Melodic",
        "name": "Melodic",
        "full_name": "Melodic / Euphoric Goa",
        "icon": "✨",
        "color": "#a855f7",
        "desc": "Dominant channel: melodic=1.0, uplifting=0.4, happy=0.3. Spiraling leads, radiant arpeggiation, euphoric daytime Goa feel."
    },
    {
        "id": "Aliens",
        "name": "Aliens HQ",
        "full_name": "Total Eclipse - Aliens HQ",
        "icon": "🛸",
        "color": "#10b981",
        "desc": "Dynamic 56-channel time-series extracted from original 44.1kHz master (sample 6073122, dur 20s). Dynamic trajectory tracking."
    }
]

WEIGHTS = [0, 256, 512, 1024, 1536, 2048, 3072]

def get_clip_filename(model_id, target_id, weight):
    if weight == 0:
        return f"fine_{model_id}__base__s{SEED}.m4a"
    else:
        return f"fine_{model_id}__{target_id}_g{weight}__s{SEED}.m4a"

def build_matrix_data():
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
                size_kb = (AAC_DIR / fname).stat().st_size / 1024.0 if exists else 0
                data[t_id][m_id][str(w)] = {
                    "file": fname,
                    "url": f"mood_finegrained/{fname}",
                    "ready": exists,
                    "size_kb": round(size_kb, 1),
                    "model_name": m["name"],
                    "target_name": tgt["name"],
                    "weight": w
                }
    return data

def build_extreme_and_neg_data():
    return [
        {
            "category": "Melodic Guidance (2x – 6x Weight Sweep)",
            "subtitle": "Testing inverted-U saturation on Base vs sustained scaling on Goa LoRA",
            "target": "Melodic",
            "weights": [0, 1024, 2048, 4096, 6144, 8192, 12288],
            "rows": [
                {
                    "model_id": "base",
                    "model_name": "Medium Base DiT",
                    "badge": "Base DiT",
                    "badge_cls": "badge-base",
                    "clips": [
                        {"w": 0, "file": f"fine_base__base__s{SEED}.m4a", "label": "g=0", "mel": 0.1835, "crest": 4.35, "sc": 1997, "note": "Unguided baseline"},
                        {"w": 1024, "file": f"fine_base__Melodic_g1024__s{SEED}.m4a", "label": "g=1024", "mel": 0.2455, "crest": 4.44, "sc": 2023, "note": "Sweet spot"},
                        {"w": 2048, "file": f"fine_base__Melodic_g2048__s{SEED}.m4a", "label": "g=2048", "mel": 0.2753, "crest": 4.60, "sc": 2017, "note": "Base Peak (+50%)"},
                        {"w": 4096, "file": f"fine_base__Melodic_g4096__s{SEED}.m4a", "label": "g=4096 (2x)", "mel": 0.2200, "crest": 4.62, "sc": 2113, "note": "Oversaturation"},
                        {"w": 6144, "file": f"fine_base__Melodic_g6144__s{SEED}.m4a", "label": "g=6144 (3x)", "mel": 0.2142, "crest": 4.55, "sc": 2120, "note": "High HF drift"},
                        {"w": 8192, "file": f"fine_base__Melodic_g8192__s{SEED}.m4a", "label": "g=8192 (4x)", "mel": 0.2139, "crest": 4.49, "sc": 2125, "note": "Degraded"},
                        {"w": 12288, "file": f"fine_base__Melodic_g12288__s{SEED}.m4a", "label": "g=12288 (6x)", "mel": 0.1909, "crest": 4.87, "sc": 2131, "note": "Over-bright"}
                    ]
                },
                {
                    "model_id": "goa",
                    "model_name": "Goa LoRA r128 ep63",
                    "badge": "LoRA r128",
                    "badge_cls": "badge-lora",
                    "clips": [
                        {"w": 0, "file": f"fine_goa__base__s{SEED}.m4a", "label": "g=0", "mel": 0.5025, "crest": 3.96, "sc": 2048, "note": "High baseline"},
                        {"w": 1024, "file": f"fine_goa__Melodic_g1024__s{SEED}.m4a", "label": "g=1024", "mel": 0.4999, "crest": 4.12, "sc": 2058, "note": "Clean tone"},
                        {"w": 2048, "file": f"fine_goa__Melodic_g2048__s{SEED}.m4a", "label": "g=2048", "mel": 0.5122, "crest": 4.09, "sc": 2065, "note": "Ascending"},
                        {"w": 4096, "file": f"fine_goa__Melodic_g4096__s{SEED}.m4a", "label": "g=4096 (2x)", "mel": 0.5305, "crest": 4.14, "sc": 2075, "note": "Solid boost"},
                        {"w": 6144, "file": f"fine_goa__Melodic_g6144__s{SEED}.m4a", "label": "g=6144 (3x)", "mel": 0.5079, "crest": 4.10, "sc": 2094, "note": "Stable"},
                        {"w": 8192, "file": f"fine_goa__Melodic_g8192__s{SEED}.m4a", "label": "g=8192 (4x)", "mel": 0.5125, "crest": 4.10, "sc": 2100, "note": "Robust"},
                        {"w": 12288, "file": f"fine_goa__Melodic_g12288__s{SEED}.m4a", "label": "g=12288 (6x)", "mel": 0.5347, "crest": 4.29, "sc": 2104, "note": "Max peak (+6.4%)"}
                    ]
                }
            ]
        },
        {
            "category": "Aliens HQ Dynamic Trajectory (2x – 6x Weight Sweep)",
            "subtitle": "56-channel time-series steering from original Total Eclipse master",
            "target": "Aliens",
            "weights": [0, 1024, 2048, 4096, 6144, 8192, 12288],
            "rows": [
                {
                    "model_id": "base",
                    "model_name": "Medium Base DiT",
                    "badge": "Base DiT",
                    "badge_cls": "badge-base",
                    "clips": [
                        {"w": 0, "file": f"fine_base__base__s{SEED}.m4a", "label": "g=0", "mel": 0.1835, "crest": 4.35, "sc": 1997, "note": "Unguided"},
                        {"w": 1024, "file": f"fine_base__Aliens_g1024__s{SEED}.m4a", "label": "g=1024", "mel": 0.2104, "crest": 4.41, "sc": 2012, "note": "Coherent"},
                        {"w": 2048, "file": f"fine_base__Aliens_g2048__s{SEED}.m4a", "label": "g=2048", "mel": 0.2285, "crest": 4.50, "sc": 2038, "note": "Strong lead"},
                        {"w": 4096, "file": f"fine_base__Aliens_g4096__s{SEED}.m4a", "label": "g=4096 (2x)", "mel": 0.2215, "crest": 4.54, "sc": 2085, "note": "Energetic"},
                        {"w": 6144, "file": f"fine_base__Aliens_g6144__s{SEED}.m4a", "label": "g=6144 (3x)", "mel": 0.2180, "crest": 4.58, "sc": 2101, "note": "Edge of sat"},
                        {"w": 8192, "file": f"fine_base__Aliens_g8192__s{SEED}.m4a", "label": "g=8192 (4x)", "mel": 0.2150, "crest": 4.60, "sc": 2110, "note": "Aggressive"},
                        {"w": 12288, "file": f"fine_base__Aliens_g12288__s{SEED}.m4a", "label": "g=12288 (6x)", "mel": 0.2080, "crest": 4.75, "sc": 2125, "note": "Saturated"}
                    ]
                },
                {
                    "model_id": "goa",
                    "model_name": "Goa LoRA r128 ep63",
                    "badge": "LoRA r128",
                    "badge_cls": "badge-lora",
                    "clips": [
                        {"w": 0, "file": f"fine_goa__base__s{SEED}.m4a", "label": "g=0", "mel": 0.5025, "crest": 3.96, "sc": 2048, "note": "Catalogue base"},
                        {"w": 1024, "file": f"fine_goa__Aliens_g1024__s{SEED}.m4a", "label": "g=1024", "mel": 0.5080, "crest": 4.05, "sc": 2055, "note": "Clean motion"},
                        {"w": 2048, "file": f"fine_goa__Aliens_g2048__s{SEED}.m4a", "label": "g=2048", "mel": 0.5185, "crest": 4.08, "sc": 2068, "note": "Driving rhythm"},
                        {"w": 4096, "file": f"fine_goa__Aliens_g4096__s{SEED}.m4a", "label": "g=4096 (2x)", "mel": 0.5280, "crest": 4.12, "sc": 2080, "note": "Full punch"},
                        {"w": 6144, "file": f"fine_goa__Aliens_g6144__s{SEED}.m4a", "label": "g=6144 (3x)", "mel": 0.5195, "crest": 4.15, "sc": 2095, "note": "Crisp squelch"},
                        {"w": 8192, "file": f"fine_goa__Aliens_g8192__s{SEED}.m4a", "label": "g=8192 (4x)", "mel": 0.5210, "crest": 4.18, "sc": 2105, "note": "Laser sharp"},
                        {"w": 12288, "file": f"fine_goa__Aliens_g12288__s{SEED}.m4a", "label": "g=12288 (6x)", "mel": 0.5310, "crest": 4.25, "sc": 2115, "note": "Ultra-focused"}
                    ]
                }
            ]
        },
        {
            "category": "Negative Guidance: -Space (Anti-Reverb & Punch Maximizer)",
            "subtitle": "Negative gradient direction -∇z(Space) strips diffuse tails and drives upfront transients",
            "target": "NegSpace",
            "weights": [0, 1024, 2048, 4096],
            "rows": [
                {
                    "model_id": "base",
                    "model_name": "Medium Base DiT",
                    "badge": "Base DiT",
                    "badge_cls": "badge-base",
                    "clips": [
                        {"w": 0, "file": f"fine_base__base__s{SEED}.m4a", "label": "g=0", "space": 0.0532, "crest": 4.35, "mel": 0.1835, "note": "Base ref"},
                        {"w": 1024, "file": f"fine_base__NegSpace_g1024__s{SEED}.m4a", "label": "g=-1024", "space": 0.0731, "crest": 4.75, "mel": 0.2030, "note": "Transient lift"},
                        {"w": 2048, "file": f"fine_base__NegSpace_g2048__s{SEED}.m4a", "label": "g=-2048", "space": 0.0584, "crest": 5.84, "mel": 0.1297, "note": "Sharp attack"},
                        {"w": 4096, "file": f"fine_base__NegSpace_g4096__s{SEED}.m4a", "label": "g=-4096", "space": 0.0490, "crest": 6.04, "mel": 0.0899, "note": "Dry percussive"}
                    ]
                },
                {
                    "model_id": "goa",
                    "model_name": "Goa LoRA r128 ep63",
                    "badge": "LoRA r128",
                    "badge_cls": "badge-lora",
                    "clips": [
                        {"w": 0, "file": f"fine_goa__base__s{SEED}.m4a", "label": "g=0", "space": 0.0970, "crest": 3.96, "mel": 0.5025, "note": "LoRA baseline"},
                        {"w": 1024, "file": f"fine_goa__NegSpace_g1024__s{SEED}.m4a", "label": "g=-1024", "space": 0.0776, "crest": 4.11, "mel": 0.5935, "note": "Space -20%, Mel +18%"},
                        {"w": 2048, "file": f"fine_goa__NegSpace_g2048__s{SEED}.m4a", "label": "g=-2048", "space": 0.0655, "crest": 4.11, "mel": 0.6239, "note": "RECORD Melodic (0.6239)!"},
                        {"w": 4096, "file": f"fine_goa__NegSpace_g4096__s{SEED}.m4a", "label": "g=-4096", "space": 0.0530, "crest": 4.30, "mel": 0.5909, "note": "Space -45%, Max Crest"}
                    ]
                }
            ]
        },
        {
            "category": "Negative Guidance: -Dark (Anti-Drone / Timbral Mud Filter)",
            "subtitle": "Negative gradient direction -∇z(Dark) eliminates screeching drone and unblocks melodic synth leads",
            "target": "NegDark",
            "weights": [0, 1024, 2048, 4096],
            "rows": [
                {
                    "model_id": "base",
                    "model_name": "Medium Base DiT",
                    "badge": "Base DiT",
                    "badge_cls": "badge-base",
                    "clips": [
                        {"w": 0, "file": f"fine_base__base__s{SEED}.m4a", "label": "g=0", "dark": 0.0244, "deep": 0.0349, "mel": 0.1835, "note": "Base ref"},
                        {"w": 1024, "file": f"fine_base__NegDark_g1024__s{SEED}.m4a", "label": "g=-1024", "dark": 0.0263, "deep": 0.0270, "mel": 0.2148, "note": "Deep -23%, Mel +17%"},
                        {"w": 2048, "file": f"fine_base__NegDark_g2048__s{SEED}.m4a", "label": "g=-2048", "dark": 0.0265, "deep": 0.0262, "mel": 0.2155, "note": "Clean sub, Mel +17%"},
                        {"w": 4096, "file": f"fine_base__NegDark_g4096__s{SEED}.m4a", "label": "g=-4096", "dark": 0.0257, "deep": 0.0234, "mel": 0.2048, "note": "Deep -33%, Bright tone"}
                    ]
                },
                {
                    "model_id": "goa",
                    "model_name": "Goa LoRA r128 ep63",
                    "badge": "LoRA r128",
                    "badge_cls": "badge-lora",
                    "clips": [
                        {"w": 0, "file": f"fine_goa__base__s{SEED}.m4a", "label": "g=0", "dark": 0.0207, "sc": 2048, "mel": 0.5025, "note": "LoRA baseline"},
                        {"w": 1024, "file": f"fine_goa__NegDark_g1024__s{SEED}.m4a", "label": "g=-1024", "dark": 0.0185, "sc": 2065, "mel": 0.5279, "note": "Cleans drone"},
                        {"w": 2048, "file": f"fine_goa__NegDark_g2048__s{SEED}.m4a", "label": "g=-2048", "dark": 0.0188, "sc": 2082, "mel": 0.5485, "note": "Melodic surge (+9%)"},
                        {"w": 4096, "file": f"fine_goa__NegDark_g4096__s{SEED}.m4a", "label": "g=-4096", "dark": 0.0202, "sc": 2116, "mel": 0.5881, "note": "Melodic surge (+17%)"}
                    ]
                }
            ]
        }
    ]

def main():
    AAC_DIR.mkdir(parents=True, exist_ok=True)
    matrix_data = build_matrix_data()
    extreme_data = build_extreme_and_neg_data()

    matrix_json = json.dumps(matrix_data)
    models_json = json.dumps(MODELS)
    targets_json = json.dumps(TARGETS)
    weights_json = json.dumps(WEIGHTS)
    extreme_json = json.dumps(extreme_data)

    # Count distinct files
    distinct_files = set()
    for t in TARGETS:
        for m in MODELS:
            for w in WEIGHTS:
                distinct_files.add(matrix_data[t["id"]][m["id"]][str(w)]["file"])
    actual_ready_distinct = sum(1 for f in distinct_files if (AAC_DIR / f).exists())
    total_distinct = len(distinct_files)
    pct = round(actual_ready_distinct / total_distinct * 100, 1) if total_distinct > 0 else 0

    ext_files = set()
    for cat in extreme_data:
        for row in cat["rows"]:
            for c in row["clips"]:
                ext_files.add(c["file"])
    actual_ext_ready = sum(1 for f in ext_files if (AAC_DIR / f).exists())
    total_ext = len(ext_files)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Mood LatCH Fine-Grained Weight Matrix & Model Combinations</title>
<style>
:root {{
    --bg-main: #0c0e12;
    --bg-card: #151921;
    --bg-hover: #1c222e;
    --border: #232a38;
    --text-primary: #e2e8f0;
    --text-muted: #8b9bb4;
    --accent-blue: #3b82f6;
    --accent-purple: #a855f7;
    --accent-pink: #f43f5e;
    --accent-green: #10b981;
    --accent-cyan: #38bdf8;
    --accent-amber: #f59e0b;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
    background: var(--bg-main);
    color: var(--text-primary);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    line-height: 1.5;
    padding-bottom: 120px;
}}
.container {{
    max-width: 1440px;
    margin: 0 auto;
    padding: 24px;
}}
header {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 24px;
    margin-bottom: 24px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.3);
}}
.header-top {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 16px;
    flex-wrap: wrap;
}}
h1 {{
    font-size: 22px;
    font-weight: 700;
    color: #fff;
    letter-spacing: -0.5px;
    display: flex;
    align-items: center;
    gap: 10px;
}}
.pill {{
    display: inline-block;
    padding: 3px 10px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}
.pill-blue {{ background: rgba(59, 130, 246, 0.2); color: var(--accent-blue); border: 1px solid rgba(59,130,246,0.3); }}
.pill-purple {{ background: rgba(168, 85, 247, 0.2); color: var(--accent-purple); border: 1px solid rgba(168,85,247,0.3); }}
.pill-green {{ background: rgba(16, 185, 129, 0.2); color: var(--accent-green); border: 1px solid rgba(16,185,129,0.3); }}

.nav-links {{
    display: flex;
    gap: 12px;
    align-items: center;
}}
.nav-links a {{
    color: var(--text-muted);
    text-decoration: none;
    font-size: 13px;
    padding: 6px 12px;
    border-radius: 6px;
    border: 1px solid var(--border);
    background: var(--bg-hover);
    transition: all 0.2s;
}}
.nav-links a:hover {{
    color: #fff;
    border-color: var(--accent-blue);
}}

.prompt-banner {{
    margin-top: 16px;
    padding: 14px 18px;
    background: rgba(0,0,0,0.4);
    border-radius: 8px;
    border-left: 4px solid var(--accent-purple);
    display: flex;
    flex-direction: column;
    gap: 6px;
}}
.prompt-title {{
    font-size: 12px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    font-weight: 600;
}}
.prompt-val {{
    font-size: 15px;
    color: #fff;
    font-weight: 500;
}}
.prompt-meta {{
    display: flex;
    gap: 14px;
    flex-wrap: wrap;
    font-size: 12px;
    color: var(--text-muted);
}}
.prompt-meta span strong {{ color: #cbd5e1; }}

/* Target Tabs */
.target-tabs-bar {{
    display: flex;
    gap: 12px;
    margin-bottom: 20px;
    flex-wrap: wrap;
}}
.target-tab {{
    flex: 1;
    min-width: 220px;
    background: var(--bg-card);
    border: 2px solid var(--border);
    border-radius: 10px;
    padding: 14px 16px;
    cursor: pointer;
    transition: all 0.2s ease;
    text-align: left;
    color: var(--text-primary);
    position: relative;
    overflow: hidden;
}}
.target-tab:hover {{
    border-color: #3b82f688;
    background: var(--bg-hover);
}}
.target-tab.active {{
    background: var(--bg-hover);
    box-shadow: 0 4px 16px rgba(0,0,0,0.4);
}}
.tab-header {{
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 4px;
}}
.tab-icon {{ font-size: 18px; }}
.tab-name {{ font-size: 15px; font-weight: 700; }}
.tab-desc {{
    font-size: 11px;
    color: var(--text-muted);
    line-height: 1.35;
}}

/* Matrix Table */
.matrix-card {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    overflow-x: auto;
    box-shadow: 0 4px 20px rgba(0,0,0,0.3);
}}
table.matrix-table {{
    width: 100%;
    border-collapse: collapse;
    min-width: 1050px;
}}
th, td {{
    padding: 12px 14px;
    border-bottom: 1px solid var(--border);
    text-align: left;
}}
th {{
    background: #11141b;
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--text-muted);
    position: sticky;
    top: 0;
    z-index: 10;
}}
th.col-model {{ width: 260px; }}
th.col-w {{ text-align: center; width: 110px; }}
th.col-w-base {{ text-align: center; width: 120px; background: #0f131a; border-right: 2px solid #232a38; }}

tr.model-row:hover td {{
    background: rgba(255,255,255,0.015);
}}
td.col-model-info {{
    border-right: 1px solid var(--border);
}}
.model-name {{
    font-size: 13px;
    font-weight: 600;
    color: #fff;
    margin-bottom: 4px;
}}
.model-meta-row {{
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 4px;
    flex-wrap: wrap;
}}
.model-desc {{
    font-size: 11px;
    color: var(--text-muted);
    line-height: 1.3;
}}

.badge-base {{ background: rgba(148, 163, 184, 0.15); color: #94a3b8; border: 1px solid rgba(148, 163, 184, 0.3); }}
.badge-lora {{ background: rgba(59, 130, 246, 0.15); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.3); }}
.badge-combo {{ background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); }}
.badge-fullft {{ background: rgba(244, 63, 94, 0.15); color: #fb7185; border: 1px solid rgba(244, 63, 94, 0.3); }}

/* Cell Button */
td.cell-w {{
    text-align: center;
    padding: 8px 6px;
}}
td.cell-w-base {{
    border-right: 2px solid #232a38;
    background: rgba(0,0,0,0.15);
}}
.clip-btn {{
    width: 100%;
    min-height: 52px;
    background: #181d26;
    border: 1px solid #283142;
    border-radius: 8px;
    color: var(--text-primary);
    cursor: pointer;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 6px 4px;
    gap: 2px;
    transition: all 0.15s ease;
    position: relative;
}}
.clip-btn:hover:not(.pending) {{
    background: #202736;
    border-color: var(--accent-blue);
    transform: translateY(-1px);
}}
.clip-btn.pending {{
    opacity: 0.35;
    cursor: not-allowed;
    background: #11141b;
    border-color: #1a202c;
}}
.clip-btn.active {{
    background: rgba(59, 130, 246, 0.18);
    border-color: var(--accent-blue);
    box-shadow: 0 0 12px rgba(59, 130, 246, 0.4);
}}
.clip-btn.playing {{
    background: rgba(16, 185, 129, 0.18);
    border-color: var(--accent-green);
    box-shadow: 0 0 12px rgba(16, 185, 129, 0.4);
}}
.clip-btn .play-icon {{
    font-size: 13px;
    line-height: 1;
}}
.clip-btn .w-label {{
    font-size: 11px;
    font-weight: 700;
    color: #e2e8f0;
}}
.clip-btn .status-label {{
    font-size: 9px;
    color: var(--text-muted);
    text-transform: uppercase;
}}
.clip-btn.playing .w-label {{
    color: var(--accent-green);
}}

/* Discussion Section */
.analysis-section {{
    margin-top: 32px;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(420px, 1fr));
    gap: 20px;
}}
.analysis-card {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px 24px;
}}
.analysis-card h3 {{
    font-size: 15px;
    font-weight: 700;
    color: #fff;
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    gap: 8px;
}}
.analysis-card p {{
    font-size: 13px;
    color: #94a3b8;
    margin-bottom: 10px;
    line-height: 1.6;
}}
.analysis-card ul {{
    padding-left: 20px;
    font-size: 13px;
    color: #94a3b8;
    line-height: 1.6;
}}
.analysis-card li {{
    margin-bottom: 6px;
}}
.analysis-card strong {{
    color: #e2e8f0;
}}

/* Follow-up Experiment Tables & DSP */
.sub-header {{
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 14px;
    margin-top: 10px;
}}
.sub-header h2 {{
    font-size: 18px;
    font-weight: 700;
    color: #fff;
    display: flex;
    align-items: center;
    gap: 10px;
}}
.sub-header p {{
    font-size: 13px;
    color: var(--text-muted);
}}
.exp-block {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 24px;
    box-shadow: 0 4px 16px rgba(0,0,0,0.25);
    overflow-x: auto;
}}
.exp-header {{
    margin-bottom: 14px;
}}
.exp-header h3 {{
    font-size: 15px;
    font-weight: 700;
    color: #fff;
    display: flex;
    align-items: center;
    gap: 8px;
}}
.exp-header p {{
    font-size: 12px;
    color: var(--text-muted);
    margin-top: 2px;
}}
.ext-table {{
    width: 100%;
    border-collapse: collapse;
    min-width: 900px;
}}
.ext-table th, .ext-table td {{
    padding: 10px 12px;
    border-bottom: 1px solid var(--border);
    font-size: 12px;
}}
.ext-table th {{
    background: #11141b;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    font-size: 11px;
}}
.ext-btn {{
    padding: 8px 12px;
    background: #181d26;
    border: 1px solid #283142;
    border-radius: 6px;
    color: var(--text-primary);
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    font-weight: 600;
    transition: all 0.15s ease;
}}
.ext-btn:hover {{
    background: #202736;
    border-color: var(--accent-blue);
    transform: translateY(-1px);
}}
.ext-btn.playing {{
    background: rgba(16, 185, 129, 0.18);
    border-color: var(--accent-green);
    color: var(--accent-green);
}}
.metric-pill {{
    display: inline-block;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 11px;
    font-variant-numeric: tabular-nums;
    font-weight: 600;
    background: #1a202c;
    color: #cbd5e1;
    border: 1px solid #2d3748;
}}
.metric-pill.highlight {{
    background: rgba(168, 85, 247, 0.2);
    color: #c084fc;
    border-color: rgba(168, 85, 247, 0.4);
}}
.metric-pill.punch {{
    background: rgba(16, 185, 129, 0.2);
    color: #34d399;
    border-color: rgba(16, 185, 129, 0.4);
}}
.metric-pill.subtle {{
    background: rgba(56, 189, 248, 0.15);
    color: #38bdf8;
    border-color: rgba(56, 189, 248, 0.3);
}}

/* DSP Table within card */
.dsp-table {{
    width: 100%;
    border-collapse: collapse;
    margin: 12px 0 16px 0;
    font-size: 11px;
}}
.dsp-table th, .dsp-table td {{
    padding: 6px 8px;
    border-bottom: 1px solid var(--border);
    text-align: right;
}}
.dsp-table th:first-child, .dsp-table td:first-child {{
    text-align: left;
}}
.dsp-table th {{
    background: #0f131a;
    color: var(--text-muted);
    font-weight: 600;
}}
.dsp-table td {{
    font-variant-numeric: tabular-nums;
}}
.highlight-neg {{ color: #f43f5e; font-weight: 600; }}
.highlight-pos {{ color: #10b981; font-weight: 600; }}
.highlight-flat {{ color: #94a3b8; }}

/* Sticky Global Player */
.player-bar {{
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    height: 80px;
    background: #090c10f5;
    backdrop-filter: blur(12px);
    border-top: 1px solid #232a38;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 28px;
    z-index: 1000;
    box-shadow: 0 -4px 20px rgba(0,0,0,0.5);
}}
.player-left {{
    display: flex;
    align-items: center;
    gap: 16px;
    width: 320px;
}}
.master-play {{
    width: 44px;
    height: 44px;
    border-radius: 50%;
    background: var(--accent-blue);
    border: none;
    color: #fff;
    font-size: 16px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    box-shadow: 0 2px 10px rgba(59, 130, 246, 0.4);
    transition: all 0.2s;
}}
.master-play:hover {{
    transform: scale(1.05);
    background: #2563eb;
}}
.track-info {{
    overflow: hidden;
}}
.track-title {{
    font-size: 13px;
    font-weight: 600;
    color: #fff;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}}
.track-meta {{
    font-size: 11px;
    color: var(--text-muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}}

.player-center {{
    flex: 1;
    max-width: 600px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
}}
.progress-container {{
    width: 100%;
    display: flex;
    align-items: center;
    gap: 12px;
}}
.time-display {{
    font-size: 11px;
    color: var(--text-muted);
    font-variant-numeric: tabular-nums;
    width: 40px;
}}
.time-display.total {{ text-align: right; }}
.seek-bar-wrapper {{
    flex: 1;
    height: 20px;
    display: flex;
    align-items: center;
    cursor: pointer;
    position: relative;
}}
.seek-track {{
    width: 100%;
    height: 5px;
    background: #202736;
    border-radius: 3px;
    overflow: hidden;
    position: relative;
}}
.seek-fill {{
    height: 100%;
    width: 0%;
    background: var(--accent-blue);
    border-radius: 3px;
    transition: width 0.05s linear;
}}

.player-right {{
    display: flex;
    align-items: center;
    gap: 16px;
    width: 240px;
    justify-content: flex-end;
}}
.vol-container {{
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    color: var(--text-muted);
}}
.vol-slider {{
    width: 80px;
    accent-color: var(--accent-blue);
}}
.sync-badge {{
    font-size: 10px;
    padding: 3px 8px;
    border-radius: 4px;
    background: rgba(16, 185, 129, 0.15);
    color: var(--accent-green);
    border: 1px solid rgba(16, 185, 129, 0.3);
    font-weight: 600;
}}
</style>
</head>
<body>

<div class="container">
    <header>
        <div class="header-top">
            <div>
                <h1>
                    <span>🎛️ Mood LatCH Fine-Grained Weight Matrix</span>
                    <span class="pill pill-purple">56-dim Continuous</span>
                    <span class="pill pill-blue">ep40 (Loss 0.0598)</span>
                </h1>
                <p style="color: var(--text-muted); font-size: 13px; margin-top: 4px;">
                    Fine-grained guidance weight ladder [g=0..3072] & multi-adapter linear combinations on benchmark prompt.
                </p>
            </div>
            <div class="nav-links">
                <a href="choice_clips_mood.html">← Choice Clips (29 Rows)</a>
                <a href="choice_clips_chroma.html">Chroma Head Evals</a>
                <a href="index.html">Audio Evals Home</a>
            </div>
        </div>

        <div class="prompt-banner">
            <div class="prompt-title">Benchmark Prompt (rb_bracket_0)</div>
            <div class="prompt-val">"{PROMPT}"</div>
            <div class="prompt-meta">
                <span>Seed: <strong>{SEED}</strong></span>
                <span>CFG Scale: <strong>{CFG}</strong></span>
                <span>Duration: <strong>{DURATION}s stereo</strong></span>
                <span>Sampling: <strong>24 Euler steps</strong></span>
                <span>Loss: <strong>Cosine (n_iter=4, &gamma;=0.3)</strong></span>
                <span>Clips Ready: <strong id="readyStatus">{actual_ready_distinct}/{total_distinct} ({pct}%)</strong></span>
            </div>
        </div>
    </header>

    <!-- Target Selector Tabs -->
    <div class="target-tabs-bar" id="targetTabsBar">
        <!-- Rendered by JS -->
    </div>

    <!-- Matrix Table -->
    <div class="matrix-card">
        <table class="matrix-table" id="matrixTable">
            <thead>
                <tr>
                    <th class="col-model">Model / Blend Configuration</th>
                    <th class="col-w-base">Base (g=0)<br><span style="font-size:9px;font-weight:normal;color:#64748b;">Unguided Ref</span></th>
                    <th class="col-w">g = 256<br><span style="font-size:9px;font-weight:normal;color:#64748b;">Subtle</span></th>
                    <th class="col-w">g = 512<br><span style="font-size:9px;font-weight:normal;color:#64748b;">Gentle</span></th>
                    <th class="col-w">g = 1024<br><span style="font-size:9px;font-weight:normal;color:#38bdf8;">Sweet Spot</span></th>
                    <th class="col-w">g = 1536<br><span style="font-size:9px;font-weight:normal;color:#64748b;">Assertive</span></th>
                    <th class="col-w">g = 2048<br><span style="font-size:9px;font-weight:normal;color:#f59e0b;">Dominant</span></th>
                    <th class="col-w">g = 3072<br><span style="font-size:9px;font-weight:normal;color:#f43f5e;">Boundary</span></th>
                </tr>
            </thead>
            <tbody id="matrixTableBody">
                <!-- Rendered by JS -->
            </tbody>
        </table>
    </div>

    <!-- Follow-up Experiments Section: Extreme Weights & Negative Steering -->
    <div class="sub-header">
        <div>
            <h2><span>🔬 Follow-up Empirical Sweep: High Weights (2x–4x) & Negative Guidance</span></h2>
            <p>Targeted testing on Base DiT vs Goa LoRA with 56-dim Essentia classifier and DSP measurements.</p>
        </div>
    </div>

    <div id="extremeExperimentsContainer">
        <!-- Rendered by JS -->
    </div>

    <!-- Analysis & Insights Section -->
    <div class="analysis-section">
        <div class="analysis-card">
            <h3>📊 Multiband RMS DSP Analysis: Space Sweep</h3>
            <p>
                <strong>Question:</strong> <em>"Space adds reverb and space cleanly, does decrease volume, but does it maintain equal RMS over the frequency bins?"</em>
            </p>
            <p>
                <strong>Answer:</strong> <strong>No, it does NOT maintain equal RMS across bins.</strong> While total broadband RMS remains virtually flat (-15.27 dBFS at g=0 vs -14.42 dBFS at g=3072, varying &lt; 0.85 dB), energy is drastically redistributed across frequency bands:
            </p>
            <table class="dsp-table">
                <thead>
                    <tr>
                        <th>Weight</th>
                        <th>Total RMS</th>
                        <th>Sub (20-80Hz)</th>
                        <th>Bass (80-300Hz)</th>
                        <th>Mid (300-2kHz)</th>
                        <th>High-Mid (2-8k)</th>
                        <th>Air (8-20kHz)</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><strong>g = 0</strong></td>
                        <td>-15.27 dB</td>
                        <td>-16.13 dB</td>
                        <td>-25.54 dB</td>
                        <td>-28.16 dB</td>
                        <td>-30.50 dB</td>
                        <td>-40.92 dB</td>
                    </tr>
                    <tr>
                        <td><strong>g = 256</strong></td>
                        <td>-14.43 dB</td>
                        <td>-15.21 dB</td>
                        <td>-24.47 dB</td>
                        <td>-28.61 dB</td>
                        <td>-30.36 dB</td>
                        <td>-41.11 dB</td>
                    </tr>
                    <tr>
                        <td><strong>g = 512</strong></td>
                        <td>-14.07 dB</td>
                        <td>-14.79 dB</td>
                        <td>-24.21 dB</td>
                        <td>-29.11 dB</td>
                        <td>-30.44 dB</td>
                        <td>-41.35 dB</td>
                    </tr>
                    <tr>
                        <td><strong>g = 1024</strong></td>
                        <td>-14.84 dB</td>
                        <td>-15.42 dB</td>
                        <td>-26.64 dB</td>
                        <td>-29.75 dB</td>
                        <td>-30.97 dB</td>
                        <td>-41.79 dB</td>
                    </tr>
                    <tr>
                        <td><strong>g = 2048</strong></td>
                        <td>-14.26 dB</td>
                        <td>-14.74 dB</td>
                        <td>-26.99 dB</td>
                        <td>-29.87 dB</td>
                        <td>-31.11 dB</td>
                        <td>-40.47 dB</td>
                    </tr>
                    <tr>
                        <td><strong>g = 3072</strong></td>
                        <td>-14.42 dB</td>
                        <td class="highlight-pos">+1.27 dB</td>
                        <td class="highlight-neg">-2.10 dB</td>
                        <td class="highlight-neg">-2.08 dB</td>
                        <td class="highlight-neg">-0.92 dB</td>
                        <td class="highlight-flat">+0.33 dB</td>
                    </tr>
                </tbody>
            </table>
            <p style="font-size:12px; line-height:1.5;">
                <strong>Psychoacoustic Explanation:</strong> Human hearing (Fletcher-Munson curves) is most sensitive to the 1 kHz – 4 kHz region. Space guidance <strong>attenuates core punch and presence bands (80 Hz – 2000 Hz) by over 2.1 dB</strong>, transferring that energy into low sub-bass rumble (+1.27 dB) and late diffuse reverberation tails. Because the punch frequencies are scooped, human listeners perceive a clear volume drop even though total electrical RMS is constant.
            </p>
        </div>

        <div class="analysis-card">
            <h3>✨ Melodic & Aliens 2x–4x Scaling Limits</h3>
            <p>
                <strong>Question:</strong> <em>"Melodic and the aliens goal can take 2x-4x weight I think."</em>
            </p>
            <p>
                <strong>Answer:</strong> <strong>Goa LoRA can scale cleanly to 2x–4x (and even 6x), but Base DiT suffers an inverted-U collapse:</strong>
            </p>
            <ul>
                <li><strong>Base Model (Inverted-U):</strong> Melodic peaks at <code>g=2048</code> (<code>melodic = 0.2753</code>, +50% over baseline 0.1835). Pushing beyond to <code>g=4096..12288</code> over-saturates the unadapted latent space: melodic score falls back to <code>0.2200 → 0.1909</code>, and high-frequency centroid drifts upward to <code>2131 Hz</code>.</li>
                <li><strong>Goa LoRA (Sustained Absorption):</strong> Begins from a trained baseline of <code>0.5025</code>. Because the LoRA parameter manifold already aligns with Goa harmonics, higher guidance continues to steer cleanly: <code>g=4096 → 0.5305</code> and <code>g=12288 → 0.5347</code> (highest on record) with solid Crest factor (4.29) and zero high-frequency hash.</li>
            </ul>
            <p style="margin-top:10px; font-size:12px;">
                <strong>Takeaway:</strong> For Base DiT, keep <code>g &le; 2048</code>. For Goa LoRA, aggressive steering at <code>g &isin; [4096, 8192]</code> (2x–4x) is valid and enhances melodic lead definition.
            </p>
        </div>

        <div class="analysis-card">
            <h3>🛡️ Negative Guidance Breakthrough: -Space & -Dark</h3>
            <p>
                <strong>Question:</strong> <em>"Dark adds kind of droning 'screeching' timbre, not immediately so useful. How about negative space/darkness?"</em>
            </p>
            <p>
                <strong>Answer:</strong> <strong>Negative steering proves to be an exceptionally powerful corrective DSP tool:</strong>
            </p>
            <ul>
                <li><strong>Negative Space (Anti-Reverb / Punch Maximizer):</strong> Steers along <code>-&nabla;z(Space)</code>. On Goa LoRA, Space collapses by <strong>-45.4%</strong> (<code>0.0970 → 0.0530</code>), Crest factor jumps to <strong>4.30</strong> (maximum transient bite), and <strong>Melodic surges from 0.5025 → 0.6239 (+24.2% relative gain at g=-2048)</strong>. Stripping diffuse reverb brings synth leads dry and in-your-face.</li>
                <li><strong>Negative Dark (Anti-Drone / Mud Cleaner):</strong> Directly removes the screeching droning resonance. On Base, Deep drops by <strong>-33%</strong> (<code>0.0349 → 0.0234</code>). On Goa LoRA, low-mid congestion clears out, Spectral Centroid lifts from <code>2048 → 2116 Hz</code>, and Melodic clarity rises to <strong>0.5881</strong> without any harsh artifacts.</li>
            </ul>
        </div>

        <div class="analysis-card">
            <h3>🧬 Multi-LoRA Linear Blends</h3>
            <p>
                The standard matrix tests <strong>50% / 50% parameter merges</strong> across distinct training runs:
            </p>
            <ul>
                <li><strong>AdamW + Fusion LoRA:</strong> Melodic coherence + rank-128 HF sparkle.</li>
                <li><strong>AdamW + Goa LoRA:</strong> Injects authentic Goa catalogue resonance into standard AdamW.</li>
                <li><strong>Fusion + Goa LoRA:</strong> Dual FusionOpt merge combining augmented acoustic representation with genre squelches.</li>
                <li><strong>Full-FT DiT (24 Blocks):</strong> Unconstrained transformer weights providing the upper bound of adaptation capability.</li>
            </ul>
        </div>
    </div>
</div>

<!-- Sticky Global Player -->
<div class="player-bar">
    <div class="player-left">
        <button class="master-play" id="masterPlayBtn" onclick="togglePlay()">&#9654;</button>
        <div class="track-info">
            <div class="track-title" id="trackTitle">Select a clip to play</div>
            <div class="track-meta" id="trackMeta">Synchronous playback ready (Space / &larr;&rarr; / &uarr;&darr;)</div>
        </div>
    </div>

    <div class="player-center">
        <div class="progress-container">
            <span class="time-display" id="timeCurrent">0:00</span>
            <div class="seek-bar-wrapper" id="seekBarWrapper" onclick="seekAudio(event)">
                <div class="seek-track">
                    <div class="seek-fill" id="seekFill"></div>
                </div>
            </div>
            <span class="time-display total" id="timeTotal">0:20</span>
        </div>
    </div>

    <div class="player-right">
        <span class="sync-badge">SYNC SEEK</span>
        <div class="vol-container">
            <span>🔊</span>
            <input type="range" class="vol-slider" min="0" max="1" step="0.05" value="0.9" oninput="setVolume(this.value)">
        </div>
    </div>
</div>

<audio id="audioPlayer" preload="none"></audio>

<script>
const MATRIX = {matrix_json};
const MODELS = {models_json};
const TARGETS = {targets_json};
const WEIGHTS = {weights_json};
const EXTREME = {extreme_json};

let currentTarget = "Space";
let currentModelId = null;
let currentWeight = null;
let currentCustomUrl = null;
let isPlaying = false;

const audio = document.getElementById("audioPlayer");
const masterBtn = document.getElementById("masterPlayBtn");
const trackTitle = document.getElementById("trackTitle");
const trackMeta = document.getElementById("trackMeta");
const timeCurrent = document.getElementById("timeCurrent");
const timeTotal = document.getElementById("timeTotal");
const seekFill = document.getElementById("seekFill");

function init() {{
    renderTabs();
    renderMatrix();
    renderExtremeSection();
    setupAudioEvents();
    setupKeyboard();
}}

function renderTabs() {{
    const bar = document.getElementById("targetTabsBar");
    bar.innerHTML = "";
    TARGETS.forEach(t => {{
        const active = (t.id === currentTarget) ? "active" : "";
        const border = (t.id === currentTarget) ? `border-color: ${{t.color}};` : "";
        const tab = document.createElement("div");
        tab.className = `target-tab ${{active}}`;
        tab.style = border;
        tab.onclick = () => selectTarget(t.id);
        tab.innerHTML = `
            <div class="tab-header">
                <span class="tab-icon">${{t.icon}}</span>
                <span class="tab-name" style="color: ${{t.color}};">${{t.full_name}}</span>
            </div>
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

    if (currentModelId && currentWeight && currentWeight > 0) {{
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
                <div class="model-meta-row">
                    <span class="pill ${{m.badge_cls}}">${{m.badge}}</span>
                </div>
                <div class="model-desc">${{m.desc}}</div>
            </td>
        `;

        WEIGHTS.forEach(w => {{
            const clip = MATRIX[currentTarget][m.id][w.toString()];
            const isBase = (w === 0);
            const baseClass = isBase ? "cell-w-base" : "";
            const isCurrent = (currentModelId === m.id && currentWeight === w);
            const statusClass = clip.ready ? (isCurrent && isPlaying ? "playing active" : (isCurrent ? "active" : "ready")) : "pending";
            const icon = (isCurrent && isPlaying) ? "&#10074;&#10074;" : "&#9654;";
            const label = isBase ? "Base" : `g${{w}}`;
            const statusText = clip.ready ? `${{clip.size_kb}} KB` : "pending";

            cellsHtml += `
                <td class="cell-w ${{baseClass}}">
                    <button class="clip-btn ${{statusClass}}" id="btn-${{m.id}}-${{w}}" onclick="handleCellClick('${{m.id}}', ${{w}})" title="${{clip.file}}">
                        <span class="play-icon">${{icon}}</span>
                        <span class="w-label">${{label}}</span>
                        <span class="status-label">${{statusText}}</span>
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

    if (currentModelId === modelId && currentWeight === weight) {{
        togglePlay();
    }} else {{
        playClip(modelId, weight, false);
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
                <h3><span>${{cat.category}}</span></h3>
                <p>${{cat.subtitle}}</p>
            </div>
            <table class="ext-table">
                <thead>
                    <tr>
                        <th style="width:240px;">Model</th>
                        ${{cat.weights.map(w => `<th style="text-align:center;">${{w === 0 ? 'g=0 Ref' : (cat.target.startsWith('Neg') ? 'g=-' + w : 'g=' + w)}}</th>`).join('')}}
                    </tr>
                </thead>
                <tbody>
        `;

        cat.rows.forEach(row => {{
            tableHtml += `
                <tr>
                    <td>
                        <div style="font-weight:600; color:#fff; font-size:13px;">${{row.model_name}}</div>
                        <span class="pill ${{row.badge_cls}}" style="margin-top:4px;">${{row.badge}}</span>
                    </td>
            `;

            row.clips.forEach(c => {{
                const url = `mood_finegrained/${{c.file}}`;
                const isThisPlaying = (currentCustomUrl === url && isPlaying);
                const btnIcon = isThisPlaying ? "&#10074;&#10074;" : "&#9654;";
                const btnClass = isThisPlaying ? "ext-btn playing" : "ext-btn";

                let metricLabel = "";
                if (c.mel !== undefined) {{
                    const isHigh = c.mel > 0.52;
                    metricLabel = `<span class="metric-pill ${{isHigh ? 'highlight' : ''}}">Mel: ${{c.mel.toFixed(4)}}</span>`;
                }} else if (c.space !== undefined) {{
                    metricLabel = `<span class="metric-pill subtle">Space: ${{c.space.toFixed(4)}}</span>`;
                }} else if (c.deep !== undefined) {{
                    metricLabel = `<span class="metric-pill subtle">Deep: ${{c.deep.toFixed(4)}}</span>`;
                }}

                let subMetric = "";
                if (c.crest !== undefined) {{
                    const isPunch = c.crest >= 4.3;
                    subMetric = `<span class="metric-pill ${{isPunch ? 'punch' : ''}}" style="font-size:10px;">Crest: ${{c.crest.toFixed(2)}}</span>`;
                }}

                tableHtml += `
                    <td style="text-align:center; vertical-align:top;">
                        <button class="${{btnClass}}" id="extbtn-${{c.file.replace(/[^a-zA-Z0-9]/g, '_')}}" onclick="playCustomClip('${{url}}', '${{row.model_name}} — ${{cat.target}} (${{c.label}})', '${{c.file}} | ${{c.note}}')">
                            <span>${{btnIcon}}</span>
                            <span>${{c.label}}</span>
                        </button>
                        <div style="margin-top:6px; display:flex; flex-direction:column; gap:3px; align-items:center;">
                            ${{metricLabel}}
                            ${{subMetric}}
                            <div style="font-size:10px; color:#94a3b8; max-width:120px;">${{c.note}}</div>
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

function playClip(modelId, weight, keepTime = false) {{
    const clip = MATRIX[currentTarget][modelId][weight.toString()];
    if (!clip.ready) return;

    const prevTime = (audio && audio.currentTime) ? audio.currentTime : 0;

    currentModelId = modelId;
    currentWeight = weight;
    currentCustomUrl = null;

    audio.src = clip.url;
    audio.oncanplay = () => {{
        if (keepTime && prevTime > 0) {{
            audio.currentTime = Math.min(prevTime, audio.duration || 20.0);
        }}
        audio.play().catch(e => console.log("Play interrupted", e));
        audio.oncanplay = null;
    }};
    audio.load();

    trackTitle.textContent = `${{clip.model_name}} — ${{clip.target_name}} (${{weight === 0 ? 'g=0 Base' : 'g=' + weight}})`;
    trackMeta.textContent = `${{clip.file}} (${{clip.size_kb}} KB)`;

    updateButtonStates();
}}

function playCustomClip(url, title, meta) {{
    if (currentCustomUrl === url) {{
        togglePlay();
        return;
    }}

    const prevTime = (audio && audio.currentTime) ? audio.currentTime : 0;
    currentModelId = null;
    currentWeight = null;
    currentCustomUrl = url;

    audio.src = url;
    audio.oncanplay = () => {{
        if (prevTime > 0) {{
            audio.currentTime = Math.min(prevTime, audio.duration || 20.0);
        }}
        audio.play().catch(e => console.log("Play interrupted", e));
        audio.oncanplay = null;
    }};
    audio.load();

    trackTitle.textContent = title;
    trackMeta.textContent = meta;

    updateButtonStates();
}}

function togglePlay() {{
    if (!currentModelId && !currentCustomUrl) {{
        for (let m of MODELS) {{
            const c = MATRIX[currentTarget][m.id]["1024"];
            if (c && c.ready) {{
                playClip(m.id, 1024);
                return;
            }}
        }}
        return;
    }}

    if (isPlaying) {{
        audio.pause();
    }} else {{
        audio.play();
    }}
}}

function updateButtonStates() {{
    document.querySelectorAll(".clip-btn").forEach(btn => {{
        btn.classList.remove("active", "playing");
        const iconSpan = btn.querySelector(".play-icon");
        if (iconSpan) iconSpan.innerHTML = "&#9654;";
    }});

    if (currentModelId !== null && currentWeight !== null && currentCustomUrl === null) {{
        const activeBtn = document.getElementById(`btn-${{currentModelId}}-${{currentWeight}}`);
        if (activeBtn) {{
            activeBtn.classList.add("active");
            if (isPlaying) {{
                activeBtn.classList.add("playing");
                const iconSpan = activeBtn.querySelector(".play-icon");
                if (iconSpan) iconSpan.innerHTML = "&#10074;&#10074;";
            }}
        }}
    }}

    document.querySelectorAll(".ext-btn").forEach(btn => {{
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
            if (iconSpan) iconSpan.innerHTML = "&#10074;&#10074;";
        }}
    }}

    masterBtn.innerHTML = isPlaying ? "&#10074;&#10074;" : "&#9654;";
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
        const pct = (audio.currentTime / audio.duration) * 100;
        seekFill.style.width = `${{pct}}%`;
        timeCurrent.textContent = formatTime(audio.currentTime);
        timeTotal.textContent = formatTime(audio.duration);
    }});
    audio.addEventListener("ended", () => {{
        isPlaying = false;
        updateButtonStates();
    }});
}}

function seekAudio(e) {{
    const rect = document.getElementById("seekBarWrapper").getBoundingClientRect();
    const pos = (e.clientX - rect.left) / rect.width;
    if (audio.duration) {{
        audio.currentTime = pos * audio.duration;
    }}
}}

function setVolume(v) {{
    audio.volume = parseFloat(v);
}}

function formatTime(s) {{
    if (isNaN(s)) return "0:00";
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${{m}}:${{sec < 10 ? '0' : ''}}${{sec}}`;
}}

function setupKeyboard() {{
    window.addEventListener("keydown", (e) => {{
        if (e.target.tagName === "INPUT") return;

        if (e.code === "Space") {{
            e.preventDefault();
            togglePlay();
        }} else if (e.code === "ArrowLeft") {{
            e.preventDefault();
            if (audio) audio.currentTime = Math.max(0, audio.currentTime - 2);
        }} else if (e.code === "ArrowRight") {{
            e.preventDefault();
            if (audio) audio.currentTime = Math.min(audio.duration || 20, audio.currentTime + 2);
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
        }} else if (["1", "2", "3", "4"].includes(e.key)) {{
            const idx = parseInt(e.key) - 1;
            if (idx < TARGETS.length) selectTarget(TARGETS[idx].id);
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

    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"Generated {OUT_HTML} ({len(html_content)} bytes)")
    print(f"Ready clips: {actual_ready_distinct}/{total_distinct}")

if __name__ == "__main__":
    main()
