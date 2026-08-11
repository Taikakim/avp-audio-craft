#!/usr/bin/env python3
"""extract_sf2_presets.py — catalog every preset in every SoundFont under given roots.

Pure stdlib, streams RIFF chunks and SEEKS past sample data (sdta can be GBs; we never
read it), so cataloging hundreds of fonts is IO-cheap. Output: JSONL, one line per preset:
  {"sf2": "<abspath>", "font": "<basename>", "mb": <size>, "bank": B, "preset": P,
   "name": "<patch name>"}
plus one {"sf2": ..., "error": ...} line per unreadable file (never silently skipped).

Made for Kim's external classification loop (Gemini Notebook) — 2026-07-23, CONTINUITY.
Usage: extract_sf2_presets.py OUT.jsonl ROOT [ROOT...]
"""
import json
import os
import struct
import sys


def read_phdr(path):
    """Yield (bank, preset, name) from the sf2's pdta/phdr chunk."""
    with open(path, "rb") as f:
        riff, size, form = struct.unpack("<4sI4s", f.read(12))
        if riff != b"RIFF" or form != b"sfbk":
            raise ValueError(f"not an sf2 (RIFF={riff!r} form={form!r})")
        end = 8 + size
        while f.tell() < end:
            hdr = f.read(8)
            if len(hdr) < 8:
                break
            cid, csz = struct.unpack("<4sI", hdr)
            if cid == b"LIST":
                ltype = f.read(4)
                if ltype == b"pdta":
                    lend = f.tell() + csz - 4
                    while f.tell() < lend:
                        sid, ssz = struct.unpack("<4sI", f.read(8))
                        if sid == b"phdr":
                            n = ssz // 38
                            for _ in range(max(0, n - 1)):  # last record = EOP terminator
                                rec = f.read(38)
                                name = rec[:20].split(b"\0")[0].decode("latin-1").strip()
                                preset, bank = struct.unpack("<HH", rec[20:24])
                                yield bank, preset, name
                            return
                        f.seek(ssz + (ssz & 1), 1)
                    return
                f.seek(csz - 4 + (csz & 1), 1)
            else:
                f.seek(csz + (csz & 1), 1)


def main():
    out_path, roots = sys.argv[1], sys.argv[2:]
    n_files = n_presets = n_err = 0
    with open(out_path, "w") as out:
        for root in roots:
            for dirpath, _, files in os.walk(root):
                for fn in sorted(files):
                    if not fn.lower().endswith((".sf2", ".sf3")):
                        continue
                    p = os.path.join(dirpath, fn)
                    n_files += 1
                    mb = round(os.path.getsize(p) / 1e6, 1)
                    try:
                        for bank, preset, name in read_phdr(p):
                            out.write(json.dumps({"sf2": p, "font": fn, "mb": mb,
                                                  "bank": bank, "preset": preset,
                                                  "name": name}) + "\n")
                            n_presets += 1
                    except Exception as e:
                        out.write(json.dumps({"sf2": p, "mb": mb, "error": str(e)}) + "\n")
                        n_err += 1
    print(f"{n_files} sf2 files -> {n_presets} presets ({n_err} unreadable) -> {out_path}")


if __name__ == "__main__":
    main()
