#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-10-13)
"""One Latent Forge RENDER preset per model-matrix test prompt: the exact text and seed the board used.

The text and seed come from the model_matrix MANIFEST, not from model_matrix_gen.py's prompt
dicts: the kimlong pool drifted after the first renders (kl_0..kl_2 have two texts on the board),
and the manifest is what the clips were actually made with. Per prompt id the majority
(text, seed) wins, as in model_matrix_gen.prompts_from_manifest.

Each preset sets prompt, negative prompt (empty, as on the board), seed, steps, CFG 7 and the
20 s board length. The sampler and schedule are left alone: the board rendered with the
backbone's own defaults. `notes` is the preset's comment: the CFGs and lengths the board also
rendered, and any other seed or text the id was rendered with.

  python3 eval/forge/make_test_prompt_presets.py              # write test-<id>.json presets
  python3 eval/forge/make_test_prompt_presets.py --dry-run
"""
import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

MANIFESTS = (Path.home() / ".cache/evals_aac/model_matrix/manifest.jsonl",
             Path.home() / "evals_aac/model_matrix/manifest.jsonl")
OUT = Path("/home/kim/Projects/sa3_render_out/_forge/presets/render")
PREFIX = "test-"
BOARD_CFG = 7.0
BOARD_SEC = 20.0
# Retired ids: still on the board, no longer rendered for new runs (model_matrix_gen EXTRA_PROMPTS).
RETIRED = {"trig2": "trig2_uml", "housestyle": "housestyle_uml"}
NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def read_manifest(path: Path) -> dict:
    by_id = defaultdict(list)
    for ln in path.read_text().splitlines():
        try:
            e = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if e.get("prompt_id"):
            by_id[str(e["prompt_id"])].append(e)
    return by_id


def _fmt(xs) -> str:
    return ", ".join(str(int(x)) if float(x).is_integer() else str(x) for x in xs)


def preset_for(pid: str, rows: list[dict]) -> dict:
    pairs = Counter((e.get("prompt_text") or "", e.get("seed")) for e in rows)
    (text, seed), n_main = pairs.most_common(1)[0]
    seeds = Counter(e.get("seed") for e in rows)
    texts = Counter(e.get("prompt_text") or "" for e in rows)
    cfgs = sorted({float(e["cfg"]) for e in rows if e.get("cfg") is not None})
    steps = Counter(int(e["steps"]) for e in rows if e.get("steps"))
    secs = sorted({float(e["duration"]) for e in rows if e.get("duration")})
    models = len({e.get("model") for e in rows})

    notes = [f"Model-matrix test prompt {pid}: {len(rows)} clips on the board across {models} models. "
             f"Board CFGs {_fmt(cfgs)}; this preset is CFG {_fmt([BOARD_CFG])}, "
             f"{BOARD_SEC:g} s, seed {seed}."]
    if secs:
        notes.append(f"Lengths also rendered: {_fmt(secs)} s.")
    if len(seeds) > 1:
        other = ", ".join(f"{s} ({n} clips)" for s, n in seeds.most_common() if s != seed)
        notes.append(f"MULTI-SEED: also rendered with seed {other}.")
    if len(texts) > 1:
        notes.append(f"The text drifted: {len(texts)} versions on the board; this is the one "
                     f"{n_main} of {len(rows)} clips used.")
    if pid in RETIRED:
        notes.append(f"Retired id (misspelt trigger word); new runs render {RETIRED[pid]}.")
    notes.append("Sampler and schedule are not set: the board used the backbone's defaults.")
    return {
        "prompt": text,
        "negative_prompt": "",
        "seed": int(seed),
        "steps": steps.most_common(1)[0][0] if steps else 24,
        "cfg_scale": BOARD_CFG,
        "duration_sec": BOARD_SEC,
        "notes": " ".join(notes),
        "source": {"kind": "model_matrix_test_prompt", "prompt_id": pid,
                   "generator": "eval/forge/make_test_prompt_presets.py"},
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    mf = a.manifest or next((p for p in MANIFESTS if p.is_file()), None)
    if mf is None:
        raise SystemExit(f"no manifest at {' or '.join(map(str, MANIFESTS))}")
    by_id = read_manifest(mf)
    if not a.dry_run:
        a.out.mkdir(parents=True, exist_ok=True)
    for pid in sorted(by_id):
        p = preset_for(pid, by_id[pid])
        name = NAME_RE.sub("-", PREFIX + pid)[:80]
        print(f"{name}: seed {p['seed']}  {p['prompt'][:60]!r}")
        if not a.dry_run:
            (a.out / f"{name}.json").write_text(json.dumps(p, indent=2, ensure_ascii=False) + "\n")
    print(f"{len(by_id)} presets from {mf}" + (" (dry run)" if a.dry_run else f" -> {a.out}"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
