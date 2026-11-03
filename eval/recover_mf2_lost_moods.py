#!/usr/bin/env python3
"""recover_mf2_lost_moods.py — Deterministic Cross-Merge & Boilerplate-Stripping Mood Recovery
for `goa_archive` (23,232 tracks) and `goa_src_captions` / `Goa_Separated` (4,461 tracks, 5,400 crops).

WHY THIS EXISTS:
  Adding the global genre hint ("goa trance / psytrance") to Music Flamingo 2 and Granite fixed
  the genre mislabeling (1.2% -> 89.1% goa/psy), but caused a massive mode-collapse into 7
  genre-template boilerplate adjectives:
    hypnotic (96.3%), psychedelic (94.1%), driving (86.2%), high-energy (84.5%),
    relentless (75.9%), evolving (66.8%), immersive (61.1%)
  while suppressing genuine acoustic & emotional moods present in the Unhinted pass by 3.9x-57x:
    dark (49.2% -> 12.7%), aggressive (40.1% -> 10.1%), metallic (40.7% -> 4.3%),
    raw (32.1% -> 0.9%), gritty (27.8% -> 0.9%), mechanical (16.3% -> 0.3%),
    dystopian (13.1% -> 0.6%), unsettling (9.4% -> 0.8%), ominous (7.2% -> 0.9%),
    brooding (6.3% -> 0.3%), contemplative/meditative/introspective (~10.3% -> ~4.5%).
  Worse, on ~15-20% of dark/minimal/industrial/melancholic tracks, the Hinted pass actively
  hallucinated "euphoric" or "uplifting" solely from the "Goa trance" genre prior.

WHAT THIS SCRIPT DOES (100% CPU deterministic cross-merge):
  1. `goa_archive` (23,232 tracks):
     - Cross-merges Unhinted Granite v5 (`goa_archive_captions/granite/*.json`) + Unhinted MF2
       prose (`lumi/goa_bigset_sidecar_v5.json` T3) with Hinted Granite
       (`goa_archive_captions_hinted/granite/*.json`) + Hinted MF2 prose
       (`lumi/goa_bigset_sidecar_hinted.json` T3) + Essentia EffNet audio T1 tags.
     - Resolves mood contradictions (strips hallucinated `euphoric`/`uplifting` when Unhinted is
       purely dark/ominous/mechanical/melancholic without minor-to-major harmonic oscillation).
     - Demotes the 7 Goa-template boilerplate words (capping at <=1 boilerplate tag when >=2
       discriminative acoustic/emotional mood tags exist).
     - Scrubs leaked wrong-genre nouns (`techno`, `house`, `edm`, etc.) from Unhinted `short_mood`
       and `short_technical` while preserving specific timbral descriptors (`sparse synth stabs`,
       `abrasive synths`, `acidic squelchy bass`, `metallic percussion`).
     - Rebuilds clean `short_genremood`, `short_technical`, `short_mood`, `medium_review` into
       `/run/media/kim/Kosmos/captions/goa_archive_captions_merged/granite/*.json` and writes the
       ready-to-train sidecars:
         * `/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/goa_archive_features/goa_archive_caption_sidecar_merged_year.json`
         * `/home/kim/Projects/SAO/lumi/goa_bigset_sidecar_merged.json`
  2. `goa_src_captions` / `Goa_Separated` (4,461 tracks, 5,400 crops):
     - Combines `goa_src_captions/json/*.json` (4,461 full-track MF2 captions with per-track year/genre
       hints) + `eval/kimlong_pool.json` (2,750 earlier unhinted/lightly-hinted full-track captions) +
       `_quarantine/plots/feature_explorer_captions.js` & `feature_explorer_classes.js` (4,494 tracks
       with earlier Granite-tiny revisions and Essentia genre/mood/instrument).
     - Generates `/run/media/kim/Kosmos/captions/goa_src_captions/granite/*.json` (4,461 tracks)
       and updates `/home/kim/Projects/SAO/lumi/goa_longform_sidecar_merged.json` (5,400 crops, with
       populated `t2` alongside `t1` and `t3`!).
     - Emits a detailed JSON audit report + conflict/ambiguous track manifest.
"""
import argparse
import ast
import collections
import glob
import hashlib
import json
import os
import random
import re
import sys
import time
import unicodedata
from pathlib import Path

SAO = Path("/home/kim/Projects/SAO")
sys.path.insert(0, str(SAO / "eval"))
from inject_year_into_captions import rewrite as rewrite_year, correct_decade, year_for  # noqa: E402

# ── Lexicons & Taxonomies ──────────────────────────────────────────────────────────────────────

BOILERPLATE_MOODS = {
    "hypnotic", "psychedelic", "driving", "high-energy", "high energy",
    "relentless", "evolving", "immersive", "trance-inducing", "trance inducing",
    "energetic", "energizing", "dance-floor", "dancefloor", "dance-floor-ready",
    "dancefloor-ready", "dance-floor focused", "club-ready", "peak-time",
    "festival-ready", "high-octane", "pulsating", "pumping", "forward-moving",
    "rhythmically intense", "dynamic", "modern", "classic", "polished",
    "high-fidelity", "wide-stereo", "electronic", "trance", "goa", "psytrance",
}

DISCRIMINATIVE_MOOD_PATTERNS = [
    # Axis 1: Dark / Industrial / Aggressive / Gritty
    ("dystopian", r"\bdystopian\b"),
    ("apocalyptic", r"\bapocalyptic\b"),
    ("cyberpunk", r"\bcyberpunk\b"),
    ("ominous", r"\bominous\b"),
    ("brooding", r"\bbrooding\b"),
    ("unsettling", r"\bunsettling\b"),
    ("menacing", r"\bmenacing\b"),
    ("sinister", r"\bsinister\b"),
    ("foreboding", r"\bforeboding\b"),
    ("bleak", r"\bbleak\b"),
    ("grim", r"\bgrim\b"),
    ("haunting", r"\bhaunting\b"),
    ("eerie", r"\beerie\b"),
    ("nocturnal", r"\bnocturnal\b"),
    ("shadowy", r"\bshadowy\b"),
    ("mechanical", r"\bmechanical\b"),
    ("industrial", r"\bindustrial\b"),
    ("metallic", r"\bmetallic\b"),
    ("abrasive", r"\babrasive\b"),
    ("gritty", r"\bgritt(?:y|iness)\b"),
    ("raw", r"\braw\b"),
    ("aggressive", r"\baggressive\b"),
    ("ferocious", r"\bferocious\b"),
    ("visceral", r"\bvisceral\b"),
    ("hard-edged", r"\bhard[-\s]edged\b"),
    ("cold", r"\bcold\b"),
    ("dark", r"\bdark(?:er|ness)?\b"),
    ("tense", r"\btens(?:e|ion)\b"),
    ("suspenseful", r"\bsuspense(?:ful)?\b"),

    # Axis 2: Contemplative / Introspective / Meditative / Melancholic / Chill
    ("melancholic", r"\bmelanchol(?:ic|y)\b"),
    ("mournful", r"\bmournful\b"),
    ("somber", r"\bsomb(?:er|re)\b"),
    ("wistful", r"\bwistful\b"),
    ("bittersweet", r"\bbittersweet\b"),
    ("yearning", r"\byearning\b"),
    ("poignant", r"\bpoignant\b"),
    ("nostalgic", r"\bnostalg(?:ic|ia)\b"),
    ("introspective", r"\bintrospective\b"),
    ("contemplative", r"\bcontemplative\b"),
    ("meditative", r"\bmeditative\b"),
    ("reflective", r"\breflective\b"),
    ("serene", r"\bserene\b"),
    ("tranquil", r"\btranquil\b"),
    ("peaceful", r"\bpeaceful\b"),
    ("calm", r"\bcalm(?:ing)?\b"),
    ("soothing", r"\bsoothing\b"),
    ("relaxed", r"\brelax(?:ed|ing)\b"),
    ("laid-back", r"\blaid[-\s]back\b"),
    ("dreamy", r"\bdream(?:y|like)\b"),
    ("ethereal", r"\bethereal\b"),
    ("floating", r"\bfloating\b"),
    ("weightless", r"\bweightless\b"),
    ("spacious", r"\bspacious\b"),
    ("expansive", r"\bexpansive\b"),
    ("airy", r"\bairy\b"),
    ("warm", r"\bwarm\b"),
    ("intimate", r"\bintimate\b"),
    ("emotional", r"\bemotional\b"),

    # Axis 3: Sci-Fi / Futuristic / Cosmic / Alien / Searching
    ("sci-fi", r"\bsci[-\s]fi\b|\bscience[-\s]fiction\b"),
    ("futuristic", r"\bfuturistic\b"),
    ("alien", r"\balien\b"),
    ("robotic", r"\brobotic\b"),
    ("otherworldly", r"\botherworldly\b"),
    ("cosmic", r"\bcosmic\b"),
    ("interstellar", r"\binterstellar\b"),
    ("astral", r"\bastral\b"),
    ("celestial", r"\bcelestial\b"),
    ("spacey", r"\bspacey\b"),
    ("mysterious", r"\bmysterious\b"),
    ("enigmatic", r"\benigmatic\b"),
    ("cryptic", r"\bcryptic\b"),
    ("surreal", r"\bsurreal\b"),
    ("hallucinatory", r"\bhallucinatory\b"),
    ("trippy", r"\btrippy\b"),
    ("mind-bending", r"\bmind[-\s]bending\b"),
    ("disorienting", r"\bdisorienting\b"),
    ("searching", r"\bsearching\b"),
    ("restless", r"\brestless\b"),
    ("unsettled", r"\bunsettled\b"),

    # Axis 4: Ritualistic / Mantra-Like / Spiritual / Mystical / Tribal
    ("mantra-like", r"\bmantra(?:[-\s]like)?\b"),
    ("ritualistic", r"\britual(?:istic)?\b"),
    ("shamanic", r"\bshamanic\b"),
    ("spiritual", r"\bspiritual\b"),
    ("mystical", r"\bmystic(?:al)?\b"),
    ("sacred", r"\bsacred\b"),
    ("ceremonial", r"\bceremonial\b"),
    ("transcendent", r"\btranscend(?:ent|ence)\b"),
    ("tribal", r"\btribal\b"),
    ("primal", r"\bprimal\b"),
    ("exotic", r"\bexotic\b"),
    ("eastern-inflected", r"\beastern\b|\boriental\b|\bphrygian\b|\braga\b"),
    ("organic", r"\borganic\b"),
    ("earthy", r"\bearthy\b"),

    # Axis 5: Minimalist / Acidic / Focused
    ("minimalist", r"\bminimal(?:ist|istic)?\b"),
    ("stripped-back", r"\bstripped[-\s]back\b"),
    ("sparse", r"\bsparse\b"),
    ("focused", r"\bfocused\b"),
    ("clinical", r"\bclinical\b"),
    ("acidic", r"\bacid(?:ic)?\b"),
    ("squelchy", r"\bsquelch(?:y|ing)?\b"),
    ("resonant", r"\bresonant\b"),
    ("urgent", r"\burgent\b"),
    ("kinetic", r"\bkinetic\b"),

    # Axis 6: Uplifting / Euphoric / Playful / Ecstatic
    ("ecstatic", r"\becstatic\b"),
    ("triumphant", r"\btriumphant\b"),
    ("exuberant", r"\bexuberant\b"),
    ("blissful", r"\bbliss(?:ful)?\b"),
    ("joyful", r"\bjoy(?:ful|ous)\b"),
    ("radiant", r"\bradiant\b"),
    ("anthemic", r"\banthemic\b"),
    ("soaring", r"\bsoaring\b"),
    ("celebratory", r"\bcelebratory\b"),
    ("playful", r"\bplayful\b"),
    ("quirky", r"\bquirky\b"),
    ("whimsical", r"\bwhimsical\b"),
    ("funky", r"\bfunky\b"),
    ("groovy", r"\bgroov(?:y|e)\b"),
    ("bouncy", r"\bbouncy\b"),
    ("uplifting", r"\buplifting\b"),
    ("euphoric", r"\beuphori(?:c|a)\b"),
    ("bright", r"\bbright\b"),
    ("intense", r"\bintens(?:e|ity)\b"),
    ("atmospheric", r"\batmospheric\b"),
]

COMPILED_MOOD_RE = [(tag, re.compile(pat, re.IGNORECASE)) for tag, pat in DISCRIMINATIVE_MOOD_PATTERNS]

DARK_ANTI_EUPHORIC = {
    "dark", "ominous", "brooding", "dystopian", "unsettling", "menacing",
    "sinister", "foreboding", "bleak", "grim", "cold", "mechanical",
    "industrial", "abrasive", "gritty", "raw", "aggressive", "ferocious",
    "melancholic", "mournful", "somber",
}
POSITIVE_EUPHORIC = {
    "euphoric", "uplifting", "ecstatic", "triumphant", "exuberant",
    "blissful", "joyful", "radiant", "celebratory", "playful", "optimistic",
}

OSCILLATION_RE = re.compile(
    r"(?:oscillat|alternat|shift|mov|balanc|blend|combin|juxtapos)[a-z]*\s+between\s+[^.]{0,60}"
    r"(?:minor\s+and\s+major|dark[^.]{0,30}(?:uplift|bright|euphor|light)|tensi[^.]{0,30}(?:releas|resolut|euphor))"
    r"|(?:minor[-\s]to[-\s]major|dark[-\s]to[-\s]light)",
    re.IGNORECASE,
)

WRONG_GENRE_SCRUB_RE = re.compile(
    r"\b(?:industrial\s+techno|minimal\s+techno|detroit\s+techno|hard\s+techno|acid\s+techno|"
    r"dub\s+techno|peak[-\s]time\s+techno|techno|deep\s+house|progressive\s+house|tech\s+house|"
    r"afro\s+house|electro\s+house|tribal\s+house|microhouse|euro\s+house|house|"
    r"drum\s+and\s+bass|drum\s*&\s*bass|dnb|jungle|dubstep|brostep|hardstyle|gabber|"
    r"trance[-\s]pop|eurodance|synthwave|retrowave|vaporwave|edm|big\s+room|"
    r"gregorian\s+chant|medieval\s+early\s+music|indie\s+rock|garage\s+rock|black\s+metal|k[-\s]rap)\b",
    re.IGNORECASE,
)

GENERIC_TECH_TOKENS = {
    "arpeggiated", "leads", "lead", "synths", "synth", "deep", "bass", "bassline",
    "sub-bass", "sub", "punchy", "kick", "crisp", "hi-hats", "hats", "percussion",
    "drums", "drum", "kit", "electronic", "tight", "evolving", "pads", "lush",
    "polished", "mix", "high-fidelity", "wide", "stereo", "field", "side-chained",
    "sidechain", "compressed", "powerful", "driving", "hypnotic", "psychedelic",
}

SPECIFIC_TECH_RE = re.compile(
    r"\b(?:acid(?:ic)?|squelch(?:y|ing)?|303|abrasive|distorted|overdriven|saturated|gritty|"
    r"metallic|industrial|mechanical|sparse|stabs|drone|drones|breakbeat|breaks|syncopated|"
    r"tribal|bongos|congas|hand\s+drums|shakers|tambourine|rimshot|clap|claps|snare\s+rolls|"
    r"female\s+vocal|male\s+vocal|vocal\s+sample|spoken[-\s]word|chant|choir|choral|mantra|"
    r"breathy|whispered|robotic|vocoder|gated|chopped|glitch(?:y)?|granular|flanger|phaser|"
    r"resonant\s+filter|filter\s+sweep|band[-\s]pass|high[-\s]pass|low[-\s]pass|delay\s+tails|"
    r"spring\s+reverb|cavernous|sub[-\s]oscillator|sawtooth|square[-\s]wave|fm\s+synth|"
    r"arpeggio|counter[-\s]melod|portamento|pitch[-\s]bend|ostinato|polyrhythm)\b",
    re.IGNORECASE,
)


def norm_key(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", s.casefold()).strip()


def extract_discriminative_moods(text: str, focus_mood_section: bool = True) -> list[str]:
    """Extract ordered discriminative mood tags from prose or short tag strings."""
    if not text:
        return []
    found = []
    seen = set()
    sections = [text]
    if focus_mood_section and len(text) > 400:
        m = re.search(r"(?:overall\s+mood|mood\s*&\s*aesthetic|overall\s*,|emotionally|atmosphere)[^.]*.*",
                      text, re.IGNORECASE | re.DOTALL)
        if m:
            sections = [m.group(0), text[:350], text]
        else:
            sections = [text[:350], text[-600:], text]

    for sec in sections:
        for tag, rx in COMPILED_MOOD_RE:
            if tag not in seen and rx.search(sec):
                seen.add(tag)
                found.append(tag)
    return found


def parse_short_mood_list(variants: list[str]) -> tuple[list[str], list[str]]:
    """Parse a Granite `short_mood` list into (discriminative_tags, boilerplate_tags)."""
    disc, boiler = [], []
    seen_d, seen_b = set(), set()
    joined = " , ".join(variants or [])
    cleaned = WRONG_GENRE_SCRUB_RE.sub("", joined)
    tokens = [t.strip(" .,;:!?'\"()[]").lower() for t in re.split(r"[,;/]|\band\b", cleaned) if t.strip()]
    for tok in tokens:
        if not tok or len(tok) < 3:
            continue
        if tok in BOILERPLATE_MOODS:
            if tok not in seen_b and tok not in ("goa", "psytrance", "trance", "electronic", "modern", "classic"):
                seen_b.add(tok)
                boiler.append(tok)
            continue
        matched_any = False
        for tag, rx in COMPILED_MOOD_RE:
            if rx.search(tok):
                if tag not in seen_d:
                    seen_d.add(tag)
                    disc.append(tag)
                matched_any = True
        if not matched_any:
            words = tok.split()
            if 1 <= len(words) <= 2 and all(w.isalpha() for w in words):
                if tok not in seen_d and tok not in BOILERPLATE_MOODS:
                    seen_d.add(tok)
                    disc.append(tok)
    return disc, boiler


def clean_technical_variant(s: str) -> str:
    """Scrub wrong genre nouns from an Unhinted `short_technical` variant while keeping timbre."""
    if not s:
        return ""
    s = re.sub(r"\bindustrial\s+techno\b", "industrial", s, flags=re.IGNORECASE)
    s = re.sub(r"\bminimal\s+techno\b", "minimalist", s, flags=re.IGNORECASE)
    s = re.sub(r"\bacid\s+techno\b", "acidic", s, flags=re.IGNORECASE)
    s = re.sub(r"\bdub\s+techno\b", "dubby reverberant", s, flags=re.IGNORECASE)
    s = re.sub(r"\btribal\s+house\b", "tribal percussive", s, flags=re.IGNORECASE)
    s = WRONG_GENRE_SCRUB_RE.sub("", s)
    s = re.sub(r"\s+,", ",", s)
    s = re.sub(r",\s*(?:,\s*)+", ", ", s)
    s = re.sub(r"\s{2,}", " ", s)
    return s.strip(" ,;.")


def specificity_score_tech(s: str) -> int:
    """Score how many concrete/non-generic technical/timbral terms a `short_technical` string has."""
    if not s:
        return 0
    hits = len(SPECIFIC_TECH_RE.findall(s))
    words = [w.lower() for w in re.findall(r"[a-z0-9-]+", s)]
    non_generic = sum(1 for w in words if w not in GENERIC_TECH_TOKENS and len(w) > 3)
    return hits * 3 + non_generic


def extract_t1_moods(t1_str: str) -> list[str]:
    """Extract Essentia moodtheme tags embedded in T1 (e.g. 'mid 90s goa trance, energetic space mood')."""
    if not t1_str:
        return []
    m = re.search(r",\s*([a-z\s-]+?)\s+mood\b", t1_str.lower())
    if not m:
        return []
    raw_words = m.group(1).strip().split()
    ESS_MAP = {
        "dark": "dark", "melodic": "melodic", "space": "cosmic",
        "meditative": "meditative", "relaxing": "relaxed", "calm": "calm",
        "dream": "dreamy", "sad": "melancholic", "melancholic": "melancholic",
        "emotional": "emotional", "epic": "anthemic", "uplifting": "uplifting",
        "retro": "vintage", "groovy": "groovy", "deep": "deep",
    }
    return [ESS_MAP[w] for w in raw_words if w in ESS_MAP]


def merge_single_goa_archive_track(
    key: str,
    rel: str,
    unh_granite: dict,
    hnt_granite: dict,
    unh_mf_text: str,
    hnt_mf_text: str,
    effnet_moods: list[str],
) -> tuple[dict, dict]:
    """Deterministic cross-merge of Unhinted + Hinted Granite & MF2 for one goa_archive track."""
    unh_disc_g, unh_boil_g = parse_short_mood_list(unh_granite.get("short_mood") or [])
    hnt_disc_g, hnt_boil_g = parse_short_mood_list(hnt_granite.get("short_mood") or [])

    unh_disc_mf = extract_discriminative_moods(unh_mf_text)
    hnt_disc_mf = extract_discriminative_moods(hnt_mf_text)

    has_oscillation = bool(OSCILLATION_RE.search(unh_mf_text or "") or OSCILLATION_RE.search(hnt_mf_text or ""))

    unh_all_disc = []
    for t in unh_disc_g + unh_disc_mf[:5]:
        if t not in unh_all_disc:
            unh_all_disc.append(t)

    unh_has_dark = any(t in DARK_ANTI_EUPHORIC for t in unh_all_disc)
    unh_has_pos = any(t in POSITIVE_EUPHORIC for t in unh_all_disc) or ("uplifting" in effnet_moods)
    hnt_injected_pos = [t for t in (hnt_disc_g + hnt_disc_mf[:3]) if t in ("euphoric", "uplifting")]

    contradiction_fixed = False
    if unh_has_dark and not unh_has_pos and hnt_injected_pos and not has_oscillation:
        contradiction_fixed = True
        hnt_disc_g = [t for t in hnt_disc_g if t not in POSITIVE_EUPHORIC]
        hnt_disc_mf = [t for t in hnt_disc_mf if t not in POSITIVE_EUPHORIC]

    merged_disc = []
    for t in unh_disc_g + unh_disc_mf[:4] + hnt_disc_g + [m for m in effnet_moods if m not in BOILERPLATE_MOODS]:
        if t and t not in merged_disc and t not in BOILERPLATE_MOODS:
            merged_disc.append(t)

    if has_oscillation and "dark" in merged_disc and "uplifting" not in merged_disc:
        merged_disc.insert(min(2, len(merged_disc)), "uplifting")

    merged_boil = []
    for b in hnt_boil_g + unh_boil_g:
        if b not in merged_boil:
            merged_boil.append(b)

    if len(merged_disc) >= 3:
        v0 = ", ".join(merged_disc[:4])
        v1_list = merged_disc[1:4] + (merged_boil[:1] if merged_boil else [merged_disc[0]])
        v1 = ", ".join(dict.fromkeys(v1_list))
        v2_list = [merged_disc[0]] + merged_disc[2:5] + (merged_boil[1:2] if len(merged_boil) > 1 else [])
        v2 = ", ".join(dict.fromkeys(v2_list))
        short_mood_variants = [v0, v1, v2]
    elif len(merged_disc) >= 1:
        v0 = ", ".join(merged_disc + merged_boil[:1])
        v1 = ", ".join(merged_disc + merged_boil[1:2]) if len(merged_boil) > 1 else v0
        short_mood_variants = list(dict.fromkeys([v0, v1]))
    else:
        short_mood_variants = hnt_granite.get("short_mood") or ["hypnotic, atmospheric"]

    unh_tech_clean = [clean_technical_variant(x) for x in (unh_granite.get("short_technical") or [])]
    unh_tech_clean = [x for x in unh_tech_clean if len(x) >= 12]
    hnt_tech_clean = [clean_technical_variant(x) for x in (hnt_granite.get("short_technical") or [])]
    hnt_tech_clean = [x for x in hnt_tech_clean if len(x) >= 12]

    all_tech = []
    for src_label, cand_list in (("unh", unh_tech_clean), ("hnt", hnt_tech_clean)):
        for c in cand_list:
            if contradiction_fixed:
                c = re.sub(r"\beuphoric\s+", "", c, flags=re.IGNORECASE)
                c = re.sub(r"\buplifting\s+", "", c, flags=re.IGNORECASE)
            score = specificity_score_tech(c) + (2 if src_label == "unh" else 0)
            all_tech.append((score, c))
    all_tech.sort(key=lambda x: -x[0])
    short_tech_variants = []
    seen_tech_norm = set()
    for _, c in all_tech:
        nk = norm_key(c)
        if nk not in seen_tech_norm:
            seen_tech_norm.add(nk)
            short_tech_variants.append(c)
            if len(short_tech_variants) >= 3:
                break
    if not short_tech_variants:
        short_tech_variants = hnt_granite.get("short_technical") or ["arpeggiated synths, deep bass, crisp percussion"]

    year = year_for(rel)
    h_frac = int(hashlib.sha1(rel.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    use_exact_year = (h_frac < 0.5)

    raw_gm_list = hnt_granite.get("short_genremood") or ["1990s goa trance, psytrance, 140 bpm"]
    new_gm_variants = []
    for idx, gm in enumerate(raw_gm_list[:3]):
        bpm_m = re.search(r"\b(\d{2,3}(?:\.\d+)?\s*bpm)\b", gm, re.IGNORECASE)
        bpm_str = bpm_m.group(1).lower() if bpm_m else None

        if year:
            gm_fixed, _ = rewrite_year(gm, year) if use_exact_year else correct_decade(gm, year)
        else:
            gm_fixed = gm

        clauses = [c.strip() for c in gm_fixed.split(",") if c.strip()]
        kept_genre_era = []
        for cl in clauses:
            cl_low = cl.lower()
            if bpm_str and bpm_str in cl_low:
                continue
            if any(g in cl_low for g in ("goa", "psy", "trance", "ambient", "downtempo", "acid", "dub", "breaks", "breakbeat", "90s", "199")):
                cl_clean = re.sub(r"\b(?:hypnotic|driving|euphoric|uplifting|energizing|energetic|psychedelic|relentless|evolving|immersive)\b", "", cl, flags=re.IGNORECASE).strip(" ,-")
                if cl_clean:
                    kept_genre_era.append(cl_clean)
        if not kept_genre_era:
            era_tok = str(year) if (year and use_exact_year) else (f"{(year // 10) * 10}s" if year else "1990s")
            kept_genre_era = [f"{era_tok} goa trance", "psytrance"]

        if merged_disc:
            offset = idx % max(1, len(merged_disc))
            chosen_moods = (merged_disc[offset:] + merged_disc[:offset])[:2]
        else:
            chosen_moods = merged_boil[:2] if merged_boil else ["hypnotic"]

        parts_gm = kept_genre_era + chosen_moods + ([bpm_str] if bpm_str else [])
        dedup_gm = []
        seen_gm = set()
        for p in parts_gm:
            pl = p.lower().strip()
            if pl and pl not in seen_gm:
                seen_gm.add(pl)
                dedup_gm.append(p.strip())
        new_gm_variants.append(", ".join(dedup_gm))

    med = hnt_granite.get("medium_review") or unh_granite.get("medium_review") or ""
    if med and year:
        med, _ = rewrite_year(med, year) if use_exact_year else correct_decade(med, year)
    if med and contradiction_fixed and merged_disc:
        replacement_mood = merged_disc[0]
        med = re.sub(r"\b(?:euphoric|uplifting|euphoria)\b", replacement_mood, med, flags=re.IGNORECASE)

    merged_entry = {
        "short_genremood": new_gm_variants,
        "short_technical": short_tech_variants,
        "short_mood": short_mood_variants,
        "medium_review": med or None,
    }
    audit_info = {
        "key": key,
        "rel": rel,
        "unh_disc": unh_all_disc,
        "hnt_disc_orig": hnt_disc_g,
        "merged_disc": merged_disc,
        "contradiction_fixed": contradiction_fixed,
        "has_oscillation": has_oscillation,
        "tech_upgraded_from_unh": bool(unh_tech_clean and short_tech_variants[0] in unh_tech_clean),
    }
    return merged_entry, audit_info


def build_t2_dedup(entry: dict, rng: random.Random) -> str | None:
    """Assemble T2 from `short_genremood`, `short_technical`, `short_mood` WITHOUT repeating clauses."""
    gm_list = entry.get("short_genremood") or []
    tech_list = entry.get("short_technical") or []
    mood_list = entry.get("short_mood") or []

    gm = rng.choice(gm_list) if gm_list else ""
    tech = rng.choice(tech_list) if tech_list else ""
    mood = rng.choice(mood_list) if mood_list else ""

    raw_clauses = []
    for seg in (gm, tech, mood):
        if seg:
            for cl in seg.split(","):
                cl = cl.strip()
                if cl:
                    raw_clauses.append(cl)
    out_clauses = []
    seen = set()
    for cl in raw_clauses:
        k = cl.lower()
        if k not in seen:
            seen.add(k)
            out_clauses.append(cl)
    return ", ".join(out_clauses) if out_clauses else None


def extract_technical_from_mf_prose(prose: str) -> list[str]:
    """Deterministically extract 3 concise `short_technical` variants (<=15 words, no genre words)
    from a 5-paragraph MF2 long caption when no Granite directory exists (`goa_src_captions`)."""
    if not prose:
        return ["arpeggiated synth leads, deep resonant bassline, punchy four-on-the-floor kick"]

    DRUM_PATTERNS = [
        (r"punchy[^,.]{0,25}kick", "punchy kick"),
        (r"distorted[^,.]{0,20}kick", "distorted kick"),
        (r"four-on-the-floor\s+kick", "four-on-the-floor kick"),
        (r"breakbeat[^,.]{0,20}(?:rhythm|drum|groove)?", "breakbeat percussion"),
        (r"tribal\s+percussion|hand\s+drums|bongos|congas", "tribal percussion"),
        (r"metallic\s+percussion|metallic\s+hi-hats", "metallic percussion"),
        (r"crisp\s+(?:open\s+and\s+closed\s+)?hi-hats", "crisp hi-hats"),
        (r"intricate\s+percuss(?:ion|ive\s+layers)", "intricate percussive layers"),
        (r"syncopated\s+(?:hi-hats|percussion|snares)", "syncopated percussion"),
    ]
    drums_found = [label for pat, label in DRUM_PATTERNS if re.search(pat, prose, re.IGNORECASE)]

    BASS_PATTERNS = [
        (r"acid(?:ic)?\s+(?:303\s+)?bass(?:line)?|squelch(?:y|ing)\s+bass", "acidic squelchy bassline"),
        (r"rolling\s+(?:16th-note\s+)?(?:synth\s+)?bass(?:line)?", "rolling synth bassline"),
        (r"off-beat\s+(?:synth\s+)?bass(?:line)?", "off-beat synth bass"),
        (r"side-chain(?:ed|-ducked)\s+(?:sub-)?bass", "side-chained sub-bass"),
        (r"deep,\s+sustained\s+(?:synth\s+)?bass|sustained\s+drone\s+bass", "deep sustained bass drone"),
        (r"pulsating\s+(?:synth\s+|sub-)?bass", "pulsating synth bass"),
        (r"deep,\s+resonant\s+(?:synth\s+)?bass(?:line)?", "deep resonant bassline"),
    ]
    bass_found = [label for pat, label in BASS_PATTERNS if re.search(pat, prose, re.IGNORECASE)]

    SYNTH_PATTERNS = [
        (r"acid(?:ic)?\s+(?:303\s+)?(?:synth|lead|line)|squelch(?:y|ing)\s+(?:synth|lead|filter)", "squelchy acid synth lines"),
        (r"swirling\s+(?:synth\s+)?arpeggios|arpeggiated\s+(?:synth\s+)?(?:leads|melod|lines)", "swirling arpeggiated leads"),
        (r"sparse\s+synth\s+stabs|percussive\s+synth\s+stabs", "sparse synth stabs"),
        (r"abrasive\s+synth|distorted\s+synth", "abrasive distorted synths"),
        (r"soaring\s+(?:melodic\s+)?lead", "soaring lead synths"),
        (r"sustained\s+(?:ambient\s+)?drone|evolving\s+drone", "sustained evolving drones"),
        (r"lush(?:,\s+evolving)?\s+(?:atmospheric\s+)?pads|expansive\s+(?:synth\s+)?pads", "lush atmospheric pads"),
        (r"resonant\s+filter\s+sweeps|automated\s+filter\s+sweeps", "resonant filter sweeps"),
        (r"glitch(?:-y|y)?\s+fx|granular\s+fx", "glitchy FX textures"),
        (r"female\s+vocal|breathy\s+vocal", "processed female vocal samples"),
        (r"male\s+vocal|spoken[-\s]word\s+sample|vocal\s+chant|mantra", "processed vocal chants"),
        (r"wide(?:,\s+immersive)?\s+stereo\s+(?:field|imaging)", "wide stereo imaging"),
    ]
    synth_found = [label for pat, label in SYNTH_PATTERNS if re.search(pat, prose, re.IGNORECASE)]

    c0 = (synth_found[:2] + bass_found[:1] + drums_found[:1]) or ["arpeggiated leads", "deep synth bass", "crisp percussion"]
    c1 = (drums_found[:2] + bass_found[:1] + synth_found[1:3]) or c0
    c2 = (synth_found[:3] + bass_found[1:2]) or c0
    out = []
    for c in (c0, c1, c2):
        s = ", ".join(dict.fromkeys(c))
        if s and s not in out:
            out.append(s)
    return out


def process_goa_archive(limit: int | None = None):
    t0 = time.time()
    print("\n" + "=" * 78)
    print("PART 1: GOA_ARCHIVE (23,232 tracks) — UNHINTED + HINTED CROSS-MERGE")
    print("=" * 78, flush=True)

    unh_dir = Path("/run/media/kim/Kosmos/captions/goa_archive_captions")
    hnt_dir = Path("/run/media/kim/Kosmos/captions/goa_archive_captions_hinted")
    merged_dir = Path("/run/media/kim/Kosmos/captions/goa_archive_captions_merged")
    merged_granite_dir = merged_dir / "granite"
    merged_granite_dir.mkdir(parents=True, exist_ok=True)
    features_dir = Path("/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/goa_archive_features")

    # Fast bulk load of precomputed T1 + Unhinted T3 (`goa_bigset_sidecar_v5.json`)
    # and Hinted year-corrected T1/T3 (`goa_bigset_sidecar_hinted.json`)
    print("  [goa_archive] Loading precomputed sidecars from NVMe...", flush=True)
    sidecar_v5 = json.loads((SAO / "lumi" / "goa_bigset_sidecar_v5.json").read_text())
    sidecar_hnt = json.loads((SAO / "lumi" / "goa_bigset_sidecar_hinted.json").read_text())

    # Map key <-> rel via curated.jsonl (plus any extra from sidecar_hnt)
    key_to_rel = {}
    curated_path = features_dir / "curated.jsonl"
    if curated_path.exists():
        with open(curated_path) as f:
            for line in f:
                if line.strip():
                    row = json.loads(line)
                    key_to_rel[row["key"]] = row["rel"]

    hnt_gfiles = sorted(glob.glob(str(hnt_dir / "granite" / "*.json")))
    if limit:
        hnt_gfiles = hnt_gfiles[:limit]
    print(f"  [goa_archive] Cross-merging {len(hnt_gfiles)} Granite + MF2 records...", flush=True)

    stats = collections.Counter()
    mood_counts_before = collections.Counter()
    mood_counts_after = collections.Counter()
    gm_mood_counts_before = collections.Counter()
    gm_mood_counts_after = collections.Counter()
    contradiction_examples = []
    recovery_examples = []
    ambiguous_conflicts = []

    sidecar_table = {}

    for i, hnt_gpath in enumerate(hnt_gfiles):
        key = os.path.splitext(os.path.basename(hnt_gpath))[0]
        rel = key_to_rel.get(key)
        if not rel:
            # Fallback to reading json/<key>.json if not in curated.jsonl (1 track out of 23,232)
            jp = hnt_dir / "json" / f"{key}.json"
            if jp.exists():
                rel = json.loads(jp.read_text()).get("rel")
        if not rel:
            continue

        unh_gpath = unh_dir / "granite" / f"{key}.json"
        unh_g = json.loads(unh_gpath.read_text()) if unh_gpath.exists() else {}
        hnt_g = json.loads(Path(hnt_gpath).read_text())

        v5_entry = sidecar_v5.get(rel) or {}
        hnt_entry = sidecar_hnt.get(rel) or {}

        t1_str = hnt_entry.get("t1") or v5_entry.get("t1")
        unh_mf_text = v5_entry.get("t3") or ""
        hnt_mf_text = hnt_entry.get("t3") or ""
        eff_moods = extract_t1_moods(t1_str)

        # Count before-merge moods in Hinted Granite short_mood and short_genremood
        hnt_disc_before, hnt_boil_before = parse_short_mood_list(hnt_g.get("short_mood") or [])
        for m in set(hnt_disc_before + hnt_boil_before):
            mood_counts_before[m] += 1
        gm_disc_before, gm_boil_before = parse_short_mood_list(hnt_g.get("short_genremood") or [])
        for m in set(gm_disc_before + gm_boil_before):
            gm_mood_counts_before[m] += 1

        merged_g, audit = merge_single_goa_archive_track(
            key, rel, unh_g, hnt_g, unh_mf_text, hnt_mf_text, eff_moods
        )

        # Count after-merge moods in merged Granite short_mood and short_genremood
        merged_disc_after, merged_boil_after = parse_short_mood_list(merged_g.get("short_mood") or [])
        for m in set(merged_disc_after + merged_boil_after):
            mood_counts_after[m] += 1
        gm_disc_after, gm_boil_after = parse_short_mood_list(merged_g.get("short_genremood") or [])
        for m in set(gm_disc_after + gm_boil_after):
            gm_mood_counts_after[m] += 1

        stats["total"] += 1
        if audit["contradiction_fixed"]:
            stats["contradiction_fixed"] += 1
            if len(contradiction_examples) < 12:
                contradiction_examples.append({
                    "key": key,
                    "rel": rel,
                    "unh_mood": unh_g.get("short_mood"),
                    "hnt_mood_old": hnt_g.get("short_mood"),
                    "merged_mood_new": merged_g.get("short_mood"),
                    "hnt_genremood_old": (hnt_g.get("short_genremood") or [None])[0],
                    "merged_genremood_new": (merged_g.get("short_genremood") or [None])[0],
                    "unh_tech": (unh_g.get("short_technical") or [None])[0],
                    "hnt_tech_old": (hnt_g.get("short_technical") or [None])[0],
                    "merged_tech_new": (merged_g.get("short_technical") or [None])[0],
                })
        if audit["has_oscillation"]:
            stats["has_oscillation"] += 1
        if audit["tech_upgraded_from_unh"]:
            stats["tech_upgraded_from_unh"] += 1
        if len(audit["merged_disc"]) > len(audit["hnt_disc_orig"]):
            stats["disc_moods_recovered"] += 1
            if len(recovery_examples) < 12 and not audit["contradiction_fixed"]:
                recovery_examples.append({
                    "key": key,
                    "rel": rel,
                    "unh_mood": unh_g.get("short_mood"),
                    "hnt_mood_old": hnt_g.get("short_mood"),
                    "merged_mood_new": merged_g.get("short_mood"),
                    "hnt_genremood_old": (hnt_g.get("short_genremood") or [None])[0],
                    "merged_genremood_new": (merged_g.get("short_genremood") or [None])[0],
                    "hnt_tech_old": (hnt_g.get("short_technical") or [None])[0],
                    "merged_tech_new": (merged_g.get("short_technical") or [None])[0],
                })

        if ("dark" in audit["unh_disc"] and "euphoric" in audit["unh_disc"]) and not audit["has_oscillation"]:
            stats["ambiguous_dual_pole"] += 1
            if len(ambiguous_conflicts) < 200:
                ambiguous_conflicts.append({"key": key, "rel": rel, "unh_disc": audit["unh_disc"]})

        if limit is None:
            (merged_granite_dir / f"{key}.json").write_text(json.dumps(merged_g, ensure_ascii=False))

        rng = random.Random(key)
        t2 = build_t2_dedup(merged_g, rng)
        sidecar_table[rel] = {
            "t1": t1_str,
            "t2": t2,
            "t3": hnt_mf_text or None,
        }

        if (i + 1) % 5000 == 0:
            print(f"  [goa_archive] {i + 1}/{len(hnt_gfiles)} ({time.time() - t0:.1f}s) | "
                  f"moods_recovered={stats['disc_moods_recovered']} "
                  f"contradictions_fixed={stats['contradiction_fixed']} "
                  f"tech_upgraded={stats['tech_upgraded_from_unh']}", flush=True)

    out_sidecar_feat = features_dir / "goa_archive_caption_sidecar_merged_year.json"
    out_sidecar_lumi = SAO / "lumi" / "goa_bigset_sidecar_merged.json"
    if limit is None:
        out_sidecar_feat.write_text(json.dumps(sidecar_table, ensure_ascii=False, indent=1))
        out_sidecar_lumi.write_text(json.dumps(sidecar_table, ensure_ascii=False, indent=1))
        print(f"  [goa_archive] Wrote {len(sidecar_table)} tracks -> {out_sidecar_feat}")
        print(f"  [goa_archive] Wrote {len(sidecar_table)} tracks -> {out_sidecar_lumi}")

    return {
        "stats": dict(stats),
        "mood_counts_before": dict(mood_counts_before),
        "mood_counts_after": dict(mood_counts_after),
        "gm_mood_counts_before": dict(gm_mood_counts_before),
        "gm_mood_counts_after": dict(gm_mood_counts_after),
        "contradiction_examples": contradiction_examples,
        "recovery_examples": recovery_examples,
        "ambiguous_conflicts_sample": ambiguous_conflicts[:30],
    }


def process_goa_src(limit: int | None = None):
    t0 = time.time()
    print("\n" + "=" * 78)
    print("PART 2: GOA_SRC / GOA_SEPARATED (4,461 tracks, 5,400 crops)")
    print("=" * 78, flush=True)

    gs_dir = Path("/run/media/kim/Kosmos/captions/goa_src_captions")
    gs_granite_dir = gs_dir / "granite"
    gs_granite_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load kimlong_pool.json (2,750 tracks with earlier unhinted/lightly-hinted full-track MF2)
    kp_list = json.load(open(SAO / "eval" / "kimlong_pool.json"))
    kp_by_norm = {norm_key(e["track"]): e["prompt"] for e in kp_list}

    # 2. Load _quarantine/plots/feature_explorer_data.js + feature_explorer_captions.js + feature_explorer_classes.js
    quar_dir = Path("/home/kim/Projects/mir/_quarantine/plots")
    quar_by_norm = {}
    if (quar_dir / "feature_explorer_data.js").exists():
        txt_d = (quar_dir / "feature_explorer_data.js").read_text()
        dec = json.JSONDecoder()
        pos = 0
        tracks_4494 = []
        while pos < len(txt_d):
            idx1 = txt_d.find("const ", pos)
            if idx1 == -1:
                break
            eq = txt_d.find("=", idx1)
            name = txt_d[idx1 + 6:eq].strip()
            start = eq + 1
            while start < len(txt_d) and txt_d[start] in " \t\r\n":
                start += 1
            if txt_d[start] not in "[{":
                break
            val, end = dec.raw_decode(txt_d[start:])
            if name == "TRACKS":
                tracks_4494 = val
                break
            pos = start + end

        txt_c = (quar_dir / "feature_explorer_captions.js").read_text()
        caps_4494 = json.loads(txt_c[txt_c.find("{"):txt_c.rfind("}") + 1])
        txt_cl = (quar_dir / "feature_explorer_classes.js").read_text()
        cls_4494 = json.loads(txt_cl[txt_cl.find("{"):txt_cl.rfind("}") + 1])

        for idx, tr_raw in enumerate(tracks_4494):
            tr_clean = re.sub(r"^\d{2,4}\s+", "", tr_raw).strip()
            nk = norm_key(tr_clean)
            quar_by_norm[nk] = {
                "short_mood": caps_4494["music_flamingo_short_mood"][idx],
                "short_tech": caps_4494["music_flamingo_short_technical"][idx],
                "short_genre": caps_4494["music_flamingo_short_genre"][idx],
                "full_crop": caps_4494["music_flamingo_full"][idx],
                "essentia_mood": cls_4494["essentia_mood"][idx],
                "essentia_genre": cls_4494["essentia_genre"][idx],
            }
        print(f"  [goa_src] Loaded {len(quar_by_norm)} earlier Granite-tiny + Essentia records from feature_explorer", flush=True)

    # 3. Load provenance map (5,400 crops -> source_track) in 0.02s
    prov_path = SAO / "lumi" / "goa_longform_sidecar_provenance.json"
    prov_map = json.loads(prov_path.read_text()) if prov_path.exists() else {}

    gs_files = sorted(glob.glob(str(gs_dir / "json" / "*.json")))
    if limit:
        gs_files = gs_files[:limit]

    stats = collections.Counter()
    mood_counts_before = collections.Counter()
    mood_counts_after = collections.Counter()
    granite_by_norm_track = {}
    t3_by_norm_track = {}
    examples = []

    ESS_MAP = {
        "dark": "dark", "melodic": "melodic", "space": "cosmic",
        "meditative": "meditative", "relaxing": "relaxed", "calm": "calm",
        "dream": "dreamy", "sad": "melancholic", "melancholic": "melancholic",
        "emotional": "emotional", "epic": "anthemic", "uplifting": "uplifting",
        "retro": "vintage", "groovy": "groovy", "deep": "deep",
    }

    for i, fp in enumerate(gs_files):
        key = os.path.splitext(os.path.basename(fp))[0]
        d = json.loads(Path(fp).read_text())
        rel = d.get("rel") or ""
        track_name = os.path.basename(os.path.dirname(rel))
        nk = norm_key(track_name)
        prose = (d.get("captions") or {}).get("full") or ""
        hint = d.get("genre_hint") or ""

        ym = re.search(r"release year:\s*(\d{4})", hint)
        year = int(ym.group(1)) if ym else None
        gm = re.search(r"genres:\s*([^.;]+)", hint)
        meta_genres = [g.strip().lower() for g in gm.group(1).split(",")] if gm else ["goa trance", "psytrance"]

        bpm_m = re.search(r"\b(\d{2,3}(?:\.\d+)?)\s*bpm\b", prose, re.IGNORECASE)
        bpm_str = f"{bpm_m.group(1)} bpm" if bpm_m else None

        kp_prose = kp_by_norm.get(nk, "")
        quar_rec = quar_by_norm.get(nk, {})
        quar_mood_str = quar_rec.get("short_mood") or ""
        if "10-20 words" in quar_mood_str or "Insufficient" in quar_mood_str:
            quar_mood_str = ""
        quar_full_crop = quar_rec.get("full_crop") or ""
        if "Insufficient" in quar_full_crop or "Debuginfod" in quar_full_crop:
            quar_full_crop = ""

        # Parse Essentia mood dict from feature_explorer_classes.js
        ess_disc = []
        em_str = quar_rec.get("essentia_mood") or ""
        if em_str and em_str.startswith("{"):
            try:
                em_dict = ast.literal_eval(em_str)
                for k_em, _ in sorted(em_dict.items(), key=lambda kv: -kv[1]):
                    if k_em in ESS_MAP and ESS_MAP[k_em] not in ess_disc:
                        ess_disc.append(ESS_MAP[k_em])
            except Exception:
                pass

        disc_kp = extract_discriminative_moods(kp_prose)
        disc_quar, boil_quar = parse_short_mood_list([quar_mood_str]) if quar_mood_str else ([], [])
        disc_crop = extract_discriminative_moods(quar_full_crop)
        disc_prose = extract_discriminative_moods(prose)

        for m in set(disc_prose):
            mood_counts_before[m] += 1

        has_oscillation = bool(OSCILLATION_RE.search(prose) or OSCILLATION_RE.search(kp_prose) or OSCILLATION_RE.search(quar_full_crop))

        earlier_pool = disc_kp + disc_quar + disc_crop[:3] + ess_disc
        earlier_dark_or_calm = any(t in DARK_ANTI_EUPHORIC or t in ("meditative", "calm", "serene", "ambient", "melancholic", "introspective")
                                   for t in earlier_pool)
        earlier_pos = any(t in POSITIVE_EUPHORIC for t in earlier_pool)
        contradiction_fixed = False
        if earlier_dark_or_calm and not earlier_pos and not has_oscillation:
            if any(t in POSITIVE_EUPHORIC for t in disc_prose):
                contradiction_fixed = True
                stats["contradiction_fixed"] += 1
                disc_prose = [t for t in disc_prose if t not in POSITIVE_EUPHORIC]

        merged_disc = []
        for t in disc_kp[:3] + disc_quar[:3] + disc_crop[:2] + disc_prose[:5] + ess_disc[:2]:
            if t and t not in merged_disc and t not in BOILERPLATE_MOODS:
                merged_disc.append(t)

        if has_oscillation:
            stats["has_oscillation"] += 1
            if "dark" in merged_disc and "uplifting" not in merged_disc:
                merged_disc.insert(min(2, len(merged_disc)), "uplifting")

        if len(merged_disc) > len(disc_prose):
            stats["disc_moods_recovered"] += 1

        for m in set(merged_disc[:5]):
            mood_counts_after[m] += 1

        if len(merged_disc) >= 3:
            sm_variants = [
                ", ".join(merged_disc[:4]),
                ", ".join(dict.fromkeys(merged_disc[1:4] + ["hypnotic"])),
                ", ".join(dict.fromkeys([merged_disc[0]] + merged_disc[2:5])),
            ]
        elif merged_disc:
            sm_variants = [", ".join(merged_disc + ["hypnotic", "atmospheric"][:3 - len(merged_disc)])]
        else:
            sm_variants = ["hypnotic, atmospheric, driving"]

        tech_variants = extract_technical_from_mf_prose(kp_prose if ("Dark Ambient" in kp_prose and "Goa" not in kp_prose) else prose)
        quar_tech = clean_technical_variant(quar_rec.get("short_tech") or "")
        if quar_tech and len(quar_tech) < 120 and "Insufficient" not in quar_tech:
            quar_tech_short = re.sub(r"^(?:This|The|A|An)\s+[^,]+,\s*featuring\s+", "", quar_tech, flags=re.IGNORECASE)
            quar_tech_short = re.sub(r"\.\s*.*$", "", quar_tech_short).strip()
            if contradiction_fixed:
                quar_tech_short = re.sub(r"\b(?:euphoric|uplifting)\s+", "", quar_tech_short, flags=re.IGNORECASE)
            if 15 <= len(quar_tech_short) <= 105 and quar_tech_short not in tech_variants:
                tech_variants.insert(0, quar_tech_short)

        h_frac = int(hashlib.sha1(key.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
        era_exact = str(year) if year else "1990s"
        era_decade = f"{(year // 10) * 10}s" if year else "1990s"
        era_primary = era_exact if (h_frac < 0.5) else era_decade

        primary_genres = [g for g in meta_genres if g not in ("electronic", "dance")][:2] or ["goa trance", "psytrance"]
        gm_variants = []
        for v_idx, era_tok in enumerate((era_primary, era_exact, era_decade)):
            g_str = f"{era_tok} {primary_genres[0]}"
            if len(primary_genres) > 1 and primary_genres[1] != primary_genres[0]:
                g_str += f", {primary_genres[1]}"
            m_slice = (merged_disc[v_idx:] + merged_disc[:v_idx])[:2] if merged_disc else ["hypnotic"]
            parts = [g_str] + m_slice + ([bpm_str] if bpm_str else [])
            v_str = ", ".join(dict.fromkeys(parts))
            if v_str not in gm_variants:
                gm_variants.append(v_str)

        first_sent_m = re.match(r"^(.*?\.)(?:\s|$)", prose.strip())
        med_review = first_sent_m.group(1) if first_sent_m else prose[:200]

        rec_granite = {
            "short_genremood": gm_variants,
            "short_technical": tech_variants[:3],
            "short_mood": sm_variants,
            "medium_review": med_review,
        }
        if limit is None:
            (gs_granite_dir / f"{key}.json").write_text(json.dumps(rec_granite, ensure_ascii=False))
        granite_by_norm_track[nk] = (key, rec_granite)

        ends = [m.end() for m in re.finditer(r"[.!?](?:\"|')?(?:\s|$)", prose)]
        t3_clean = prose[:ends[-1]].strip() if ends else prose.strip()
        if "Dark Ambient" in kp_prose and "high-energy Goa Trance" in prose and any("ambient" in g for g in meta_genres):
            t3_clean = kp_prose.strip()
            stats["ambient_t3_restored_from_kimlong"] += 1
        t3_by_norm_track[nk] = t3_clean

        stats["total"] += 1
        if len(examples) < 12 and (contradiction_fixed or len(merged_disc) >= 3):
            examples.append({
                "track": track_name,
                "year": year,
                "meta_genres": meta_genres,
                "contradiction_fixed": contradiction_fixed,
                "prose_moods_only": disc_prose[:4],
                "recovered_moods": merged_disc[:5],
                "short_genremood": gm_variants[0],
                "short_technical": tech_variants[0],
                "short_mood": sm_variants[0],
            })

    lf_path = SAO / "lumi" / "goa_longform_sidecar.json"
    if lf_path.exists() and limit is None:
        lf_sidecar = json.loads(lf_path.read_text())
        n_t2_filled = 0
        n_t3_filled = 0
        for stem, entry in lf_sidecar.items():
            pinfo = prov_map.get(stem) or {}
            st = pinfo.get("source_track") or pinfo.get("caption_track")
            nk = norm_key(st) if st else None
            if nk and nk in granite_by_norm_track:
                _, g_rec = granite_by_norm_track[nk]
                rng = random.Random(stem)
                entry["t2"] = build_t2_dedup(g_rec, rng)
                if entry["t2"]:
                    n_t2_filled += 1
            if nk and nk in t3_by_norm_track and t3_by_norm_track[nk]:
                entry["t3"] = t3_by_norm_track[nk]
                n_t3_filled += 1
            elif entry.get("t3"):
                n_t3_filled += 1

        out_lf = SAO / "lumi" / "goa_longform_sidecar_merged.json"
        out_lf.write_text(json.dumps(lf_sidecar, ensure_ascii=False, indent=0))
        stats["longform_crops_t2_filled"] = n_t2_filled
        stats["longform_crops_t3_filled"] = n_t3_filled
        print(f"  [goa_src] Updated 5,400-crop sidecar -> {out_lf} "
              f"(t2 populated: {n_t2_filled}/5400, t3 populated: {n_t3_filled}/5400) ({time.time() - t0:.1f}s)", flush=True)

    return {
        "stats": dict(stats),
        "mood_counts_before": dict(mood_counts_before),
        "mood_counts_after": dict(mood_counts_after),
        "examples": examples,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="Cap tracks per corpus for smoke test")
    ap.add_argument("--report-out", type=Path,
                    default=SAO / "eval" / "mf2_mood_recovery_report.json")
    args = ap.parse_args()

    res_archive = process_goa_archive(args.limit)
    res_src = process_goa_src(args.limit)

    report = {
        "goa_archive": res_archive,
        "goa_src": res_src,
    }
    args.report_out.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\n[DONE] Wrote full recovery report -> {args.report_out}")


if __name__ == "__main__":
    main()
