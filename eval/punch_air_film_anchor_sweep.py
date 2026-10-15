#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-10-15)
"""punch_air_film_anchor_sweep.py -- punch combo + A2 air head (low gains) + FiLM, across trajectory-anchor values.

WHY. Listening verdict 2026-10-15: the anchor (s0 1.2) removes seed 764's saturation under FiLM "practically completely"
while the sound's character stays; even air weight 4k "seems like a lot". The final latent std tracks the heard saturation
(764: combo 1.16, combo + FiLM 1.47, + air -10 dB 1.6-2.0; anchored 1.2). This maps the useful low air range with FiLM and
the anchor on, and, out of curiosity, what tighter anchors do: s0 1.2 / 1.1 / 1.0 / 0.9 / 0.8 (below the unguided level
~1.0-1.15 the anchor starts pulling every render quieter/flatter, not only the runaway ones).
Grid: seeds 764 + 3050; air gain {500, 1000, 2000, 3000} x target {-20, -10} dB x anchor {1.2, 1.1, 1.0, 0.9, 0.8}, FiLM 1.0 @ 6/s
on top; references: combo + FiLM at each anchor. Same base payload as eval/punch_air_film_matrix.py; z_std recorded per clip.
Output: Mantu/sa3_control_runs/punch_air_film_anchor_sweep_20261015/. RUN: SAO/.venv/bin/python eval/punch_air_film_anchor_sweep.py render
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import punch_air_film_matrix as m  # noqa: E402

ANCHORS = (1.2, 1.1, 1.0, 0.9, 0.8)
GAINS = (500, 1000, 2000, 3000)
TARGETS = (-20.0, -10.0)
m.OUT = f"{m._MANTU}/sa3_control_runs/punch_air_film_anchor_sweep_20261015"
m.__doc__ = __doc__
_payload = m.payload


def cells():
    out = []
    for s in m.SEEDS:
        for an in ANCHORS:
            out.append(dict(seed=s, head=None, gain=0, target=None, film=True, anchor=an, id=f"s{s}__punch_film_anc{an:g}"))
            for g in GAINS:
                for t in TARGETS:
                    out.append(dict(seed=s, head="a2", gain=g, target=t, film=True, anchor=an,
                                    id=f"s{s}__a2_g{g}_t{int(t)}_film_anc{an:g}"))
    return out


def payload(c, base, film_ckpt):
    p = _payload(c, base, film_ckpt)
    p["guide_anchor"] = float(c["anchor"])
    return p


m.cells, m.payload = cells, payload

if __name__ == "__main__":
    sys.exit(m.main())
