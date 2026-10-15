#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-10-15)
"""punch_air_film_anchor.py -- does the trajectory anchor clear the seed-764 saturation on punch + A2 air + FiLM?

WHY. Listening verdict 2026-10-15 on punch_air_film.html: "The A2 air head + FiLM on top sound all distorted/saturated for
s764 (the originally degraded one), for 3050 the combos are good." Saturation is often the latent's level running away
over the late steps, which latch_hparams["guide_anchor"] caps (latch_guided._anchor_std; it fixed the loudness push of
hard LatCH guidance, latch_guide_anchor_20261015). Same cells as eval/punch_air_film_matrix.py (A2 air head, gain x target,
FiLM 1.0 @ 6/s on top, seed 764) plus the combo + FiLM reference, all with guide_anchor 1.2.
Compare against the un-anchored cells in punch_air_film_matrix_20261015 (same ids without the _anc suffix).
Output: Mantu2/sa3_control_runs/punch_air_film_anchor_20261015/. RUN: SAO/.venv/bin/python eval/punch_air_film_anchor.py render
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import punch_air_film_matrix as m  # noqa: E402

ANCHOR = 1.2
m.OUT = f"{m._MANTU}/sa3_control_runs/punch_air_film_anchor_20261015"
m.__doc__ = __doc__   # run_meta "purpose" is taken from the module docstring
_cells, _payload = m.cells, m.payload


def cells():
    out = []
    for c in _cells():
        if c["seed"] == 764 and c["film"] and c["head"] in (None, "a2"):
            out.append({**c, "anchor": ANCHOR, "id": c["id"] + "_anc"})
    return out


def payload(c, base, film_ckpt):
    p = _payload(c, base, film_ckpt)
    p["guide_anchor"] = ANCHOR
    return p


m.cells, m.payload = cells, payload

if __name__ == "__main__":
    sys.exit(m.main())
