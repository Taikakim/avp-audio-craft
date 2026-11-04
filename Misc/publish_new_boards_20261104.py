#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-11-04)
"""publish_new_boards_20261104.py -- stage and publish the eval boards that had never gone online (Kim 2026-11-04: "publish all new eval sites online").
All were built by ANTIGRAVITY: drum separation gates G0 to G3, the AudEdit benchmark, the IDM benchmark, the v7 smoke mix, and the synth inversion H6 page.
Stage: copy each page and every clip it references into ~/evals_aac/<board>/, move clips from outside the run folder under the board and rewrite their paths, restyle with eval_page_retheme, add a note and run_meta.json, leak-scan.
The H6 page keeps its clips in synth_inversion/ but gets its own name, because synth_inversion.html is a different live page (the FX-fixed rerun).
Publish: rsync only the listed files, then the two updated mixtape pages and the evals index. Never prints host, key or destination.
RUN: python3 Misc/publish_new_boards_20261104.py stage ; ... check ... ; python3 Misc/publish_new_boards_20261104.py push
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
EV = Path.home() / "evals_aac"
RUNS = Path.home() / "sao_runs"
BOARDS = {
    "drum_sep_g0": (RUNS / "drum_sep_g0/listen/index.html", "SAME autoencoder ceiling for drum transients: does the round trip keep onsets and attacks well enough to separate from?"),
    "drum_sep_g1": (RUNS / "drum_sep_g1/listen/index.html", "Can text prompts on the frozen base model separate drums with no training, through SDEdit or flow inversion?"),
    "drum_sep_g2": (RUNS / "drum_sep_g2_eval/index.html", "Kick separation with the modular mixture inlet, against BS-RoFormer, MSG-LD and untrained priors."),
    "drum_sep_g3": (RUNS / "drum_sep_g3_eval/index.html", "Kick, snare, hats and percussion from one prompt-conditioned model, with Wiener mask reconciliation."),
    "drum_sep_audedit": (RUNS / "drum_sep_benchmarks_div4_eval/index.html", "The G3 console with AudEdit (inversion-free FlowEdit) added as a zero-training comparison."),
    "idm_drums_benchmark": (RUNS / "idm_stems_eval/listen/index.html", "Inverse Drum Machine (Torres et al. 2025): nine drum stems and symbolic onsets on real stems, on CPU."),
}
TOP = {
    "v7_smoke_mix.html": (EV / "v7_smoke_mix.html", "The first four clips of the v7 mixtape joined through ten transition variants, plus each 8-bar transition alone."),
    "synth_inversion_h6.html": (EV / "synth_inversion.html", "Does training on noisy conditioning (H6, 4 h more) improve reconstruction of 24 real bass stems?"),
}
UPDATED = ["mixtape_chain.html", "mixtape_relcut.html"]
NOTE = '<p class="note" style="border-left:3px solid var(--edge,#b33);padding:6px 10px;margin:10px 0;font-size:13px;line-height:1.5"><b>&#10071; No listening verdict on record.</b> {purpose} Built by ANTIGRAVITY. The wording and numbers below are its own and have not been checked by the team.</p>'
REF = re.compile(r'''(["'(])([^"'()\s<>]+?\.(?:m4a|mp3|wav|png))(["')])''')
LEAK = re.compile(r"/home/kim|/run/media|\bMantu\b|\bLehto\b|\bKosmos\b|lumi_runs|\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b|localhost|127\.0\.0\.1")
MANIFEST = EV / "_publish_20261104.lst"


def add_note(html, purpose):
    note = NOTE.format(purpose=purpose)
    m = re.search(r'<p class="nav">.*?</p>', html, flags=re.S)
    if m:
        return html[:m.end()] + "\n" + note + html[m.end():]
    m = re.search(r"<body[^>]*>", html)
    return html[:m.end()] + "\n" + note + html[m.end():]


def retheme(page, up):
    r = subprocess.run([sys.executable, str(HERE / "eval_page_retheme.py"), *(["--up", up] if up else []), str(page)], capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"retheme failed on {page.name}: {r.stderr[-300:]}")


def meta(path, name, purpose, source):
    path.write_text(json.dumps({"purpose": purpose, "hypothesis": purpose, "built_by": "ANTIGRAVITY", "source_page": str(source), "published": "2026-11-04, on project direction, wording unchecked by the team", "result": "see the page; not re-measured", "kim_feedback": None}, indent=1))


def stage():
    files = []
    for name, (src, purpose) in BOARDS.items():
        out = EV / name
        out.mkdir(exist_ok=True)
        html = src.read_text(errors="replace")
        d = src.parent
        seen = {}
        missing = []

        def sub(m):
            ref = m.group(2)
            if ref.startswith(("http:", "https:", "data:")):
                return m.group(0)
            q = (d / ref).resolve()
            if not q.exists():
                missing.append(ref)
                return m.group(0)
            try:
                rel = str(q.relative_to(d.resolve()))
            except ValueError:
                rel = "audio_ext/" + re.sub(r"^(\.\./)+", "", ref)
            seen[rel] = q
            return m.group(1) + rel + m.group(3)

        html = REF.sub(sub, html)
        if missing:
            sys.exit(f"{name}: {len(missing)} referenced files missing, e.g. {missing[:2]}")
        for rel, q in seen.items():
            t = out / rel
            t.parent.mkdir(parents=True, exist_ok=True)
            if not t.exists():
                shutil.copy2(q, t)
            files.append(f"{name}/{rel}")
        page = out / "index.html"
        page.write_text(html)
        retheme(page, "../")
        page.write_text(add_note(page.read_text(), purpose))
        meta(out / "run_meta.json", name, purpose, src)
        files.append(f"{name}/index.html")  # the sidecar carries local paths and stays local (MASTER section 4)
        print(f"{name}: {len(seen)} clips, {sum(q.stat().st_size for q in seen.values()) >> 20} MB")
    for name, (src, purpose) in TOP.items():
        html = src.read_text(errors="replace")
        refs = sorted({m.group(2) for m in REF.finditer(html)})
        miss = [r for r in refs if not (EV / r).exists()]
        if miss:
            sys.exit(f"{name}: missing {miss[:2]}")
        page = EV / name
        if page != src:
            page.write_text(html)
        retheme(page, "")
        page.write_text(add_note(page.read_text(), purpose))
        files += [name] + refs
        print(f"{name}: {len(refs)} clips")
    files += UPDATED
    for f in UPDATED:
        base = f[:-5]
        files += [str(p.relative_to(EV)) for p in (EV / base).glob("*.m4a")]
    bad = {}
    for f in files:
        if f.endswith(".html"):
            found = sorted(set(LEAK.findall((EV / f).read_text(errors="replace"))))
            if found:
                bad[f] = found
    if bad:
        sys.exit(f"LEAKS, nothing staged for push: {bad}")
    MANIFEST.write_text("\n".join(sorted(set(files))) + "\n")
    print(f"staged {len(set(files))} files; leak scan clean; manifest {MANIFEST.name}")


def conf():
    out = {}
    for line in (Path.home() / ".config/aavepyora.conf").read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"')
    return out


def push(extra=()):
    c = conf()
    files = MANIFEST.read_text().split() + list(extra)
    with tempfile.NamedTemporaryFile("w", suffix=".lst") as fl:
        fl.write("\n".join(files) + "\n")
        fl.flush()
        r = subprocess.run(["rsync", "-az", "--chmod=D755,F644", f"--files-from={fl.name}", "-e", f"ssh -o BatchMode=yes -o LogLevel=ERROR -i {c['KEY']}", f"{EV}/", f"{c['HOST']}:{c['DEST_DIR']}/evals/"], capture_output=True, text=True)
    print(f"rsync rc={r.returncode}, {len(files)} files")
    if r.returncode:
        sys.exit("rsync failed; output withheld because it can name the destination")


if __name__ == "__main__":
    a = sys.argv[1:] or ["stage"]
    {"stage": stage, "push": push}[a[0]]()
