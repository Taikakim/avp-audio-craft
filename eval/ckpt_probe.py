"""Classify ONE checkpoint file cheaply: no torch.load, no GPU, no unpickling.

A Lightning .ckpt (and a torch.save'd riffer_*.pt) is a zip archive whose
`data.pkl` member is small even when the tensor payload is 44 GB -- reading and
byte-scanning that one member is enough to tell the four families apart
(docs/INFERENCE-SURFACE.md section 2). A .safetensors file states its JSON
header length in its first 8 bytes.

Families: adapter (LoRA/DoRA) | fullft | control_adapter (Head-B) | latch_head |
unknown. A checkpoint does NOT announce its family in its filename -- that is
exactly why this exists.
"""
from __future__ import annotations

import json
import re
import struct
import zipfile
from pathlib import Path

FAMILIES = ("adapter", "fullft", "control_adapter", "latch_head", "unknown")

_EPOCH_STEP = re.compile(r"epoch=(\d+)-step=(\d+)")
_STEP_ONLY = re.compile(r"step(\d+)")
# Pickled str values appear verbatim in data.pkl; scan for ASCII runs.
_ASCII = re.compile(rb"[ -~]{4,}")
_LORA_A_KEY = re.compile(rb"parametrizations\.weight\.\d+\.lora_A")
_DIT_KEY = re.compile(rb"(transformer\.layers\.\d+|to_timestep_embed|to_cond_embed)")


def _blank(path: Path, kind: str) -> dict:
    try:
        st = path.stat()
        size, mtime = st.st_size, st.st_mtime
    except OSError:
        size, mtime = 0, 0.0
    return {"family": "unknown", "kind": kind, "slim": None, "rank": None,
            "alpha": None, "adapter_type": None, "control_mode": None,
            "epoch": None, "step": None, "n_target_modules": None,
            "dtype_hint": None, "size": size, "mtime": mtime, "probe_error": None}


def _epoch_step_from_name(name: str) -> tuple[int | None, int | None]:
    m = _EPOCH_STEP.search(name)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = _STEP_ONLY.search(name)
    if m:
        return None, int(m.group(1))
    return None, None


def _strings(raw: bytes) -> list[bytes]:
    return _ASCII.findall(raw)


def _scalar_after(raw: bytes, key: bytes) -> bytes | None:
    """Bytes following a pickled key, for cheap value sniffing."""
    i = raw.find(key)
    return None if i < 0 else raw[i:i + 400]


def _probe_zip(path: Path, kind: str) -> dict:
    out = _blank(path, kind)
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        pkl = next((n for n in names if n.endswith("data.pkl")), None)
        if pkl is None:
            out["probe_error"] = "no data.pkl member"
            return out
        raw = z.read(pkl)

    out["dtype_hint"] = next((d for d, tok in (
        ("float32", b"FloatStorage"), ("float16", b"HalfStorage"),
        ("bfloat16", b"BFloat16Storage")) if tok in raw), None)
    # Two different optimizer-state conventions, and testing only the first
    # mis-reported an entire family as slim (C, 2026-08-26):
    #   * Lightning .ckpt                          -> key "optimizer_states"
    #   * riffer_*.pt (control-adapter trainer)    -> top-level key "opt"
    # Measured on morphcond/morph_L3_ft_s1/riffer_final.pt: opt = 1359.6 MB of
    # 1813 MB, i.e. 75% of the file. Calling those slim understated their pull
    # cost 4x and told the census 32 arms had no resumable copy.
    #
    # Matched as LENGTH-PREFIXED pickle strings so a bare "opt" cannot collide
    # with substrings of longer names ("optimizer", "opt_state", ...). torch
    # writes BINUNICODE (4-byte LE length) here, but SHORT_BINUNICODE (1-byte)
    # is equally legal and appears in other protocol/version combinations, so
    # both forms are tested.
    def _pickled_key(raw_bytes, name):
        b = name.encode()
        n = len(b)
        return (bytes([n]) + b) in raw_bytes or \
               (n.to_bytes(4, "little") + b) in raw_bytes
    out["slim"] = not (_pickled_key(raw, "optimizer_states")
                       or _pickled_key(raw, "opt"))

    lora_a = _LORA_A_KEY.findall(raw)
    has_control_mode = b"control_mode" in raw
    has_latch = b"out_proj" in raw and b"feature_stats" in raw

    if has_control_mode:
        out["family"] = "control_adapter"
        blob = _scalar_after(raw, b"control_mode")
        for cand in (b"melody_contour", b"metrical_position", b"fingerprint",
                     b"dual_scalar", b"attribute", b"scalar"):
            if blob and cand in blob:
                out["control_mode"] = cand.decode()
                break
    elif lora_a:
        out["family"] = "adapter"
        out["n_target_modules"] = len(lora_a)
        blob = _scalar_after(raw, b"adapter_type")
        for cand in (b"dora-rows", b"dora-xs", b"lora-xs", b"dora", b"lora"):
            if blob and cand in blob:
                out["adapter_type"] = cand.decode()
                break
    elif has_latch:
        out["family"] = "latch_head"
    elif _DIT_KEY.search(raw):
        out["family"] = "fullft"

    # epoch/step: Lightning pickles them as bare ints, which a byte scan cannot
    # read reliably. The filename convention carries the same numbers; the
    # payload values are recovered only on the adapter path (_lora_config_fields).
    out["epoch"], out["step"] = _epoch_step_from_name(path.name)
    return out


def _probe_safetensors(path: Path) -> dict:
    out = _blank(path, "safetensors")
    with open(path, "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        header = json.loads(f.read(n).decode("utf-8"))
    keys = [k for k in header if k != "__metadata__"]
    lora_a = [k for k in keys if "lora_A" in k]
    if lora_a:
        out["family"] = "adapter"
        out["n_target_modules"] = len(lora_a)
        out["rank"] = int(header[lora_a[0]]["shape"][0])
    elif any(re.search(r"transformer\.layers\.\d+", k) for k in keys):
        out["family"] = "fullft"
    out["slim"] = True
    md = header.get("__metadata__") or {}
    out["adapter_type"] = md.get("adapter_type")
    out["epoch"], out["step"] = _epoch_step_from_name(path.name)
    return out


def probe(path: str | Path) -> dict:
    """Classify one checkpoint. Never raises -- errors land in probe_error."""
    p = Path(path)
    suffix = p.suffix.lower()
    kind = ("safetensors" if suffix == ".safetensors"
            else "pt" if suffix == ".pt" else "ckpt")
    try:
        if suffix == ".safetensors":
            return _probe_safetensors(p)
        out = _probe_zip(p, kind)
    except Exception as e:                      # unreadable / racing delete / not a zip
        out = _blank(p, kind)
        out["probe_error"] = f"{type(e).__name__}: {e}"
        return out

    # rank/alpha come from the pickled lora_config; read them with a bounded
    # torch.load of the METADATA ONLY when the cheap scan found an adapter.
    if out["family"] == "adapter" and out["rank"] is None:
        out.update(_lora_config_fields(p))
    return out


def _lora_config_fields(path: Path) -> dict:
    """rank/alpha/adapter_type from lora_config. Uses torch.load(mmap=True) so
    only the small config object is materialised, never the tensor payload."""
    try:
        import torch
        ck = torch.load(str(path), map_location="meta", weights_only=False, mmap=True)
    except Exception:
        try:
            import torch
            ck = torch.load(str(path), map_location="cpu", weights_only=False)
        except Exception as e:
            return {"probe_error": f"lora_config read failed: {type(e).__name__}: {e}"}
    lc = (ck or {}).get("lora_config") or {}
    sd = (ck or {}).get("state_dict") or {}
    rank = lc.get("rank")
    if rank is None:
        for k, v in sd.items():
            if "lora_A" in k and hasattr(v, "shape"):
                rank = int(v.shape[0])
                break
    out = {"rank": int(rank) if rank is not None else None,
           "alpha": float(lc["alpha"]) if lc.get("alpha") is not None else None}
    if lc.get("adapter_type"):
        out["adapter_type"] = lc["adapter_type"]
    ep, st = ck.get("epoch"), ck.get("global_step")
    if ep is not None:
        out["epoch"] = int(ep)
    if st is not None:
        out["step"] = int(st)
    return out
