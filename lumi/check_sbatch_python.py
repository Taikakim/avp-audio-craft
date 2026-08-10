#!/usr/bin/env python3
"""check_sbatch_python.py -- syntax-check every python heredoc in lumi/sbatch/*.sbatch.

Run it BEFORE submitting. Exit 0 = every embedded python block parses.

    python3 lumi/check_sbatch_python.py

A python block embedded in a shell heredoc is never parsed until the job runs it -- so a
quoting error inside one is invisible until the step it guards silently dies. G + C found
exactly that in fullft_reg_ab.sbatch and fullft_wd_ab.sbatch on 2026-08-10 (escaped double
quotes inside an f-string, wrapped in a single-quoted heredoc): the latent-std VERDICT table
never printed for ANY run, passing or failing. This sweeps them all.

A job whose verdict step dies is worse than a job that fails: it exits COMPLETED, produces
its artifacts, and quietly omits the number you launched it for -- the same shape as the
5336-of-6690 render (see check_render_complete.py).

NOTE on false positives, learned the hard way: the outer `bash -c '...'` splices shell
values in with the '"${VAR}"' idiom, which is GONE by the time python sees the line. A
checker that reads the heredoc verbatim flags every correct use of that idiom -- this one
reported both already-fixed files as broken until it modelled the splice.
"""
import ast, re, sys, pathlib, collections

HD = re.compile(r"""
    (?P<cmd>\bpython3?\b[^\n<]*)          # python ... 
    <<\s*(?P<q>'|")?(?P<tag>[A-Za-z_][A-Za-z0-9_]*)(?P=q)?  # <<TAG / <<'TAG'
    \s*\n(?P<body>.*?)\n(?P=tag)\b        # ... body ... TAG
""", re.S | re.X)

bad, total, files = [], 0, 0
for p in sorted(pathlib.Path("lumi/sbatch").glob("*.sbatch")):
    txt = p.read_text()
    hits = list(HD.finditer(txt))
    if hits: files += 1
    for m in hits:
        total += 1
        body, quoted = m.group("body"), m.group("q") is not None
        line0 = txt[:m.start("body")].count("\n") + 1
        # unquoted heredoc => shell expands $... first; substitute a placeholder so we can
        # still parse the python structure rather than choking on shell syntax.
        # The outer `bash -c '...'` splices shell values in with the '"${VAR}"' idiom: it CLOSES
        # the single quote, emits the expanded value, and reopens. By the time python sees the
        # line the splice is gone, so model it here -- reading the file verbatim otherwise
        # reports every correct use of the idiom as a SyntaxError (it did, on both files that
        # were already fixed).
        src = re.sub(r"""'"\$\{?[A-Za-z_][A-Za-z0-9_]*\}?"'""", "SHVAL", body)
        if not quoted:                       # unquoted tag => remaining $VARs expand too
            src = re.sub(r"\$\{?[A-Za-z_][A-Za-z0-9_]*\}?", "SHVAL", src)
        try:
            ast.parse(src)
        except SyntaxError as e:
            bad.append((p.name, line0 + (e.lineno or 1) - 1, quoted, e.msg,
                        (e.text or "").strip()[:90]))

print(f"scanned {files} sbatch files, {total} python heredocs")
if not bad:
    print("all parse clean")
for name, ln, q, msg, txt in bad:
    print(f"\n  {name}:{ln}  ({'quoted' if q else 'UNquoted -- shell expands first'})")
    print(f"    SyntaxError: {msg}")
    print(f"    | {txt}")
sys.exit(1 if bad else 0)
