"""Which weight sets a checkpoint REALLY contains, and how far its EMA got from where it started.

Built 2026-10-29 (CONTINUITY) for WINTERMUTE's weights-in-the-GUI work (the /ckpts weights
dropdown, render metadata tag, on-load info popup). `weight_report(path)` is the function to call;
`python eval/ckpt_weights.py <ckpt> [...] [--json]` is the same thing on the command line.

Why this exists: every loader we have prefers the EMA shadow when a file carries one, or picks
`"state"` without saying what `"state"` is, and the EMA's horizon is counted in UPDATES, which differ
per trainer (per microbatch for Lightning full-FT, per optimizer step for the control and LatCH
trainers). A low-turnover EMA renders mostly its starting point, so a dropdown that says "EMA"
without the residual share hides the thing the listener most needs to know (sa3-training skill §1).

What it reads, per family (family from `ckpt_probe.probe`, which never unpickles tensors):
- fullft (Lightning .ckpt): `diffusion.model.*` = online, `diffusion_ema.ema_model.*` = EMA,
  `diffusion_ema.ema_step` = the true EMA update count (NOT global_step: it counts microbatches).
- adapter (LoRA/DoRA Lightning): online only -- train_lora force-disables EMA for adapters.
- control_adapter (riffer_*.pt): `state` = EMA when args.ema > 0 (else the Schedule-Free average
  when SF is on, else online); `state_online` (since 2026-10-15); `model_train` = the train-mode
  iterate saved for exact resume (adapter + conditioner only, NO DoRA); `lora_state` follows
  `state`. The step counter counts MICROBATCHES; EMA updates = step // grad_accum.
- latch_head: one weight set per file (`weights: online_sf_average` marks the online copy, else
  EMA when `ema` > 0); sibling `_online.pt` / `_ema<h>.pt` files of the same epoch are listed.

Residual share of the start: beta ** U, U = number of decay updates. beta is NOT stored in the
Lightning checkpoint, so it comes from run_meta.json or falls back to 0.9999, flagged "assumed".

Loads with torch.load(mmap=True) so a 44 GB fat checkpoint reads only its pickle and the few
scalars touched (~5 s on the UUID drive). Never raises: problems land in `errors`.
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ckpt_probe  # noqa: E402

EMA_PREFIX = "diffusion_ema.ema_model."
EMA_STEP_KEY = "diffusion_ema.ema_step"
ONLINE_PREFIXES = ("diffusion.model.", "model.")
LIGHTNING_DEFAULT_BETA = 0.9999          # train_lora --ema-beta default
LIGHTNING_DEFAULT_EMA_WARMUP = 100       # train_lora --ema-warmup-steps: hard copies, not decays
CONVERGED_HALFLIVES = 3.0                # sa3-training skill: R 3..10 is the useful range
RESUME_EMA_FIX_TS = 1793261596.0          # 2026-10-29 10:13 EET, WINTERMUTE a1335a0: exact resume keeps the EMA
_INIT_KEY = re.compile(r"(init_state_ckpt|init_from|init_ckpt|warm_?start|base_state_ckpt|resume_exact|^resume$)", re.I)
_INIT_LOG = re.compile(r"\[init\] full-FT warm-start from (\S+)")


def ema_residual(updates: int | None, beta: float | None) -> dict | None:
    """beta**U and the half-life count. None when either side is unknown."""
    if updates is None or beta is None or not (0.0 < beta < 1.0):
        return None
    half = math.log(0.5) / math.log(beta)       # exact; ln2/(1-beta) is the small-(1-beta) limit
    r = updates / half
    return {"updates": int(updates), "beta": float(beta), "halflife_updates": half,
            "halflives": r, "residual_start": beta ** updates,
            "converged": r >= CONVERGED_HALFLIVES}


def _load(path: Path):
    import torch
    try:
        return torch.load(str(path), map_location="cpu", weights_only=False, mmap=True)
    except Exception:
        return torch.load(str(path), map_location="cpu", weights_only=False)


def _scalar(v):
    try:
        return v.item() if hasattr(v, "item") else v
    except Exception:
        return None


def _count(sd: dict, prefix: str) -> int:
    return sum(1 for k in sd if k.startswith(prefix))


def find_run_meta(path: Path, max_up: int = 3) -> Path | None:
    """run_meta.json in the checkpoint's dir or up to `max_up` parents (run dirs nest ckpts/)."""
    cur = path.parent
    for _ in range(max_up + 1):
        cand = cur / "run_meta.json"
        if cand.is_file():
            return cand
        if cur.parent == cur:
            break
        cur = cur.parent
    return None


def _walk(obj, trail=()):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk(v, trail + (str(k),))
    else:
        yield trail, obj


def _meta_init(meta: dict) -> tuple[str | None, str | None]:
    """First string under an init-like key anywhere in run_meta. Returns (value, dotted key)."""
    for trail, v in _walk(meta):
        if trail and _INIT_KEY.search(trail[-1]) and isinstance(v, str) and v.strip():
            return v.strip(), ".".join(trail)
    return None, None


def _meta_beta(meta: dict) -> tuple[float | None, str | None]:
    for trail, v in _walk(meta):
        if trail and re.fullmatch(r"(ema|ema_beta|ema_decay|ema-beta)", trail[-1], re.I):
            try:
                b = float(v)
            except (TypeError, ValueError):
                continue
            if 0.0 < b < 1.0:
                return b, ".".join(trail)
    # recipe prose: "--ema-beta 0.9995"
    blob = json.dumps(meta)
    m = re.search(r"ema[-_ ]?beta[\"' =:]+([0-9.]+)", blob, re.I)
    if m:
        try:
            b = float(m.group(1))
            if 0.0 < b < 1.0:
                return b, "run_meta text"
        except ValueError:
            pass
    return None, None


def _log_init(run_dir: Path) -> str | None:
    """train_lora prints '[init] full-FT warm-start from X'; look for it in small logs."""
    try:
        logs = [p for p in run_dir.iterdir()
                if p.suffix in (".log", ".out", ".txt") and p.stat().st_size < 50_000_000]
    except OSError:
        return None
    for p in sorted(logs):
        try:
            with open(p, "r", errors="replace") as f:
                for line in f:
                    m = _INIT_LOG.search(line)
                    if m:
                        return m.group(1)
        except OSError:
            continue
    return None


def _init_entry(value: str | None, source: str | None, note: str | None = None) -> dict:
    if not value:
        return {"name": None, "path": None, "source": source, "note": note}
    p = Path(value)
    name = p.name if p.suffix else value
    # A run dir's checkpoint name alone is ambiguous ("epoch=7-step=...ckpt"); keep the run dir too.
    if p.suffix and p.parent.name:
        name = f"{p.parent.name}/{p.name}"
    return {"name": name, "path": value, "source": source, "note": note}


# ---------------------------------------------------------------- per-family readers

def _fullft(path: Path, ck: dict, meta: dict | None, out: dict) -> None:
    sd = ck.get("state_dict", ck)
    n_online = max(_count(sd, p) for p in ONLINE_PREFIXES)
    n_ema = _count(sd, EMA_PREFIX)
    out["weight_sets"].append({"name": "online", "key": "diffusion.model.*", "n_tensors": n_online,
                               "covers": "DiT", "note": "the live weights at save time"})
    if n_ema:
        out["weight_sets"].append({"name": "ema", "key": EMA_PREFIX + "*", "n_tensors": n_ema,
                                   "covers": "DiT", "note": "SimpleEMA shadow"})
    n_cond = _count(sd, "diffusion.conditioner.") + _count(sd, "conditioner.")
    if n_cond:
        out["extras"].append(f"{n_cond} conditioner tensors (loaded with either weight set)")
    gs = ck.get("global_step")
    out["steps"] = {"optimizer_steps": gs, "epoch": ck.get("epoch")}
    out["default_weights"] = "online"
    out["default_note"] = ("render server + model_matrix_gen default to online (Kim 2026-09-11); "
                           "train_lora --init_state_ckpt and model_matrix_gen --weights auto "
                           "PREFER the EMA when present")
    if not n_ema:
        return
    ema_step = _scalar(sd.get(EMA_STEP_KEY))
    beta, bsrc = _meta_beta(meta or {})
    if beta is None:
        beta, bsrc = LIGHTNING_DEFAULT_BETA, "assumed default (beta not stored in the checkpoint)"
    # ema_step counts every update() call, including the --ema-warmup-steps hard copies.
    warm = LIGHTNING_DEFAULT_EMA_WARMUP
    upd = None if ema_step is None else max(0, int(ema_step) - warm)
    res = ema_residual(upd, beta)
    if res is not None:
        res.update({"beta_source": bsrc, "ema_step": int(ema_step),
                    "updates_source": f"diffusion_ema.ema_step - {warm} warm-up copies (assumed default)",
                    "start_point": "the online weights after the EMA warm-up copies, i.e. the run's "
                                   "starting model (medium-base, or the --init_state_ckpt warm start)"})
        if gs:
            res["updates_per_optimizer_step"] = round(int(ema_step) / int(gs), 3)
    out["ema"] = res


def _adapter(path: Path, ck: dict, out: dict) -> None:
    sd = ck.get("state_dict", ck) if isinstance(ck, dict) else {}
    lc = ck.get("lora_config") or {} if isinstance(ck, dict) else {}
    n = sum(1 for k in sd if "lora_" in k or "magnitude" in k)
    out["weight_sets"].append({"name": "online", "key": "state_dict (lora_A/lora_B/magnitude)",
                               "n_tensors": n, "covers": f"{lc.get('adapter_type') or 'LoRA/DoRA'} adapter",
                               "note": "no EMA: train_lora force-disables it for adapters"})
    out["default_weights"] = "online"
    out["steps"] = {"optimizer_steps": ck.get("global_step"), "epoch": ck.get("epoch")}
    if lc.get("base_model") or lc.get("model"):
        out["base_model"] = lc.get("base_model") or lc.get("model")


def _control(path: Path, ck: dict, out: dict) -> None:
    a = ck.get("args") or {}
    ema_decay = float(a.get("ema") or 0.0)
    has_online = "state_online" in ck
    has_dora = bool(ck.get("lora_state"))
    sf = _sf_guess(a)
    if ema_decay > 0:
        state_is, state_note = "ema", f"EMA shadow, decay {ema_decay:g}"
        if sf and not has_online:
            state_is = "sf_average?"
            state_note = ("saved before the 2026-10-16 fix with Schedule-Free + EMA: opt.eval() overwrote "
                          "the EMA, so 'state' is probably the SF average, not the EMA")
    elif sf:
        state_is, state_note = "sf_average", "Schedule-Free averaged iterate (no EMA)"
    else:
        state_is, state_note = "online", "live weights (no EMA, no SF)"
    dec = ck.get("ema_deconvolved")
    if dec:
        # eval/ema_deconv_ckpt.py rewrote "state" from two EMA saves: an estimate of the ONLINE
        # weights, averaged over the gap between the pair. Not an EMA, so no residual applies.
        state_is = "online_deconvolved"
        state_note = (f"recovered from EMA {dec.get('from')} - {dec.get('prev')} (beta {dec.get('beta')}, "
                      f"{dec.get('gap_optimizer_steps')} optimizer steps): {dec.get('note')}")
        ema_decay = 0.0
    covers = "adapter + conditioner" + (" + DoRA (lora_state)" if has_dora else "")
    out["weight_sets"].append({"name": state_is, "key": "state" + (" + lora_state" if has_dora else ""),
                               "n_tensors": len(ck.get("state") or {}) + len(ck.get("lora_state") or {}),
                               "covers": covers, "note": state_note})
    if has_online:
        out["weight_sets"].append({"name": "online", "key": "state_online",
                                   "n_tensors": len(ck["state_online"] or {}),
                                   "covers": "adapter + conditioner",
                                   "note": "SF averaged iterate when SF is on, else the live weights"
                                           + ("; DoRA has no online copy" if has_dora else "")})
    if "model_train" in ck:
        out["weight_sets"].append({"name": "train_iterate", "key": "model_train",
                                   "n_tensors": len(ck["model_train"] or {}),
                                   "covers": "adapter + conditioner (NO DoRA)",
                                   "note": ("exact-resume iterate (SF y point)" if sf else
                                            "exact-resume iterate = the online adapter weights")
                                           + ("; the DoRA it trained with is only saved EMA-averaged"
                                              if has_dora and ema_decay > 0 else "")})
    out["default_weights"] = state_is
    out["default_note"] = "sa3_control loaders (generate.load_adapter_state, render_morph) read 'state'"
    ga = max(1, int(a.get("grad_accum") or 1))
    step = ck.get("step")
    out["steps"] = {"microbatches": step, "grad_accum": ga,
                    "optimizer_steps": None if step is None else int(step) // ga}
    out["base_model"] = a.get("model")
    # init / warm start
    if a.get("resume_exact"):
        out["init"] = _init_entry(a["resume_exact"], "args.resume_exact",
                                  "exact resume (weights + optimizer + step)")
    elif a.get("resume"):
        out["init"] = _init_entry(a["resume"], "args.resume", "warm start: weights only, fresh optimizer")
    if a.get("base_state_ckpt"):
        out["backbone"] = _init_entry(a["base_state_ckpt"], "args.base_state_ckpt",
                                      ("online" if a.get("base_state_online") else "EMA")
                                      + " weights of a full finetune under the controls")
    if ema_decay > 0 and step is not None and state_is == "ema":
        start_step, start_point = 0, "the zero-init adapter (fresh run)"
        if a.get("resume"):
            start_point = "the --resume warm-start weights"
        if a.get("resume_exact") and path.stat().st_mtime < RESUME_EMA_FIX_TS:
            # Before a1335a0 the EMA was built BEFORE --resume-exact loaded (train.py ~L771 vs ~L782), so
            # the shadow restarted from the fresh zero-init adapter at start_step and the pre-resume history
            # was lost. Files written after the fix continue the saved EMA, so the default count applies.
            start_step = _resume_step(a["resume_exact"])
            start_point = ("the zero-init adapter again: saved before the 2026-10-29 fix (a1335a0), when "
                           "--resume-exact restarted the EMA shadow and forgot the run so far")
            if start_step is None:
                out["errors"].append("resume_exact source unreadable; EMA update count assumes step 0")
                start_step = 0
        upd = max(0, (int(step) - start_step) // ga)
        res = ema_residual(upd, ema_decay)
        res.update({"beta_source": "args.ema", "start_point": start_point,
                    "updates_source": f"(step {step} - start {start_step}) // grad_accum {ga}"})
        out["ema"] = res


def _sf_guess(a: dict) -> bool:
    """Is Schedule-Free averaging on? Mirrors control/sa3_control/train.py's optimizer setup:
    sfadamw / fusion / fusion_nm / fusion_full all carry 'sf' unless --hyperball removed it;
    modular follows --mod-sf (default on); adamw and lion have none."""
    opt = str(a.get("optimizer") or "").lower()
    if opt in ("sfadamw", "fusion", "fusion_nm", "fusion_full"):
        return not bool(a.get("hyperball"))
    if opt == "modular":
        return bool(a.get("mod_sf", True))
    return False


def _resume_step(p: str) -> int | None:
    try:
        return int(_load(Path(p)).get("step", 0))
    except Exception:
        return None


def _latch(path: Path, ck: dict, out: dict) -> None:
    ema = float(ck.get("ema") or 0.0)
    online = ck.get("weights") == "online_sf_average" or ema == 0.0
    name = "online" if online else "ema"
    note = ("live weights (the SF averaged iterate under modular/Fusion)" if online
            else f"EMA shadow, decay {ema:g} per optimizer step")
    if "ema" not in ck:
        note = "no 'ema' field: saved by the pre-EMA trainer, so these are the live weights"
    out["weight_sets"].append({"name": name, "key": "state_dict", "n_tensors": len(ck.get("state_dict") or {}),
                               "covers": "LatCH head", "note": note})
    out["default_weights"] = name
    out["steps"] = {"epoch": ck.get("epoch"), "grad_accum": ck.get("grad_accum"),
                    "effective_batch": ck.get("effective_batch")}
    out["selected_on"] = ck.get("selected_on")
    if ck.get("init_from"):
        out["init"] = _init_entry(ck["init_from"], "ckpt.init_from",
                                  f"epoch {ck.get('init_from_epoch')}" if ck.get("init_from_epoch") else None)
    # siblings of the same epoch carry the other weight sets
    m = re.match(r"(latch_sa3_.+_ep\d+)(?:_online|_ema[0-9.]+)?\.pt$", path.name)
    if m:
        sib = sorted(str(p.name) for p in path.parent.glob(m.group(1) + "*.pt") if p != path)
        if sib:
            out["siblings"] = sib
    if not online:
        out["ema"] = {"beta": ema, "halflife_updates": math.log(0.5) / math.log(ema) if 0 < ema < 1 else None,
                      "updates": None, "residual_start": None,
                      "updates_source": "not recorded in the head checkpoint (epoch only; steps/epoch not saved)",
                      "start_point": "the head's random init" + (" or init_from" if ck.get("init_from") else "")}


# ---------------------------------------------------------------- public

def weight_report(path: str | Path, run_meta: dict | None = None) -> dict:
    """Describe the weight sets inside one checkpoint. Never raises.

    Returns {path, family, weight_sets: [{name, key, n_tensors, covers, note}], default_weights,
    default_note, ema: {updates, beta, beta_source, halflife_updates, halflives, residual_start,
    converged, start_point, updates_source} | None, init: {name, path, source, note} | None,
    backbone, base_model, steps, extras, errors, run_meta_path}.
    """
    p = Path(path)
    out = {"path": str(p), "family": None, "weight_sets": [], "default_weights": None,
           "default_note": None, "ema": None, "init": None, "backbone": None, "base_model": None,
           "steps": {}, "extras": [], "errors": [], "run_meta_path": None}
    pr = ckpt_probe.probe(p)
    out["family"] = pr["family"]
    if pr.get("probe_error"):
        out["errors"].append(f"probe: {pr['probe_error']}")
    meta = run_meta
    if meta is None:
        mp = find_run_meta(p)
        if mp is not None:
            out["run_meta_path"] = str(mp)
            try:
                meta = json.loads(mp.read_text())
            except Exception as e:
                out["errors"].append(f"run_meta unreadable: {type(e).__name__}: {e}")
    if p.suffix.lower() == ".safetensors":
        out["weight_sets"].append({"name": "online", "key": "safetensors", "n_tensors": None,
                                   "covers": pr["family"], "note": "safetensors exports carry one set"})
        out["default_weights"] = "online"
        return out
    try:
        ck = _load(p)
    except Exception as e:
        out["errors"].append(f"load: {type(e).__name__}: {e}")
        return out
    if not isinstance(ck, dict):
        out["errors"].append(f"unexpected checkpoint type {type(ck).__name__}")
        return out
    try:
        fam = pr["family"]
        if fam == "fullft":
            _fullft(p, ck, meta, out)
        elif fam == "adapter":
            _adapter(p, ck, out)
        elif fam == "control_adapter":
            _control(p, ck, out)
        elif fam == "latch_head":
            _latch(p, ck, out)
        else:
            out["errors"].append(f"family {fam!r}: no reader")
    except Exception as e:
        out["errors"].append(f"{type(e).__name__}: {e}")
    if out["init"] is None and meta:
        v, k = _meta_init(meta)
        if v:
            out["init"] = _init_entry(v, f"run_meta.{k}")
    if out["init"] is None and out["family"] in ("fullft", "adapter"):
        v = _log_init(p.parent)
        if v:
            out["init"] = _init_entry(v, "train log '[init] full-FT warm-start from'")
    return out


_CACHE: dict = {}


def weight_report_cached(path: str | Path) -> dict:
    """weight_report memoised on (path, size, mtime): a fat checkpoint on the UUID drive costs
    5-30 s to open, and a GUI asks about the same file every time a picker opens."""
    p = Path(path)
    try:
        st = p.stat()
        key = (str(p.resolve()), st.st_size, st.st_mtime)
    except OSError:
        return weight_report(p)
    if key not in _CACHE:
        _CACHE[key] = weight_report(p)
    return _CACHE[key]


def summary_line(r: dict) -> str:
    """One human line for a tooltip / on-load popup."""
    sets = "/".join(w["name"] for w in r["weight_sets"]) or "?"
    s = f"{r['family']}: {sets} (default {r['default_weights']})"
    e = r.get("ema")
    if e and e.get("residual_start") is not None:
        s += (f"; EMA {e['halflives']:.2f} half-lives, still {e['residual_start']:.0%} its start"
              f"{' (beta assumed)' if 'assumed' in str(e.get('beta_source')) else ''}")
    if r.get("init") and r["init"].get("name"):
        s += f"; init {r['init']['name']}"
    return s


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("ckpts", nargs="+")
    ap.add_argument("--json", action="store_true", help="full report as JSON lines")
    a = ap.parse_args(argv)
    for c in a.ckpts:
        r = weight_report(c)
        print(json.dumps(r, default=str) if a.json else f"{c}\n  {summary_line(r)}"
              + "".join(f"\n  ! {e}" for e in r["errors"]))


if __name__ == "__main__":
    main()
