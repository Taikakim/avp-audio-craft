"""
Goa/Ibiza-trance variation renderer (style engine).

Reads a JSON file holding a list of variation specs and writes one multi-track
type-1 .mid per spec, matching the 7-track layout of ibiza-example-mine.mid:
  0 Chords | 1 Ostinato Lead | 2 Wailing Backing | 3 303 Riff |
  4 909 Kit | 5 Sub Bass | 6 Kick

The CREATIVE content (chords, lead ostinato, wail, root motion, energy) comes
from the spec (LLM-designed). The IDIOMATIC content (octave-bounce bass, 16th
acid drone, 909 groove, four-on-floor kick) is expanded here from templates so
every file is valid and genre-correct.

Spec schema (one object per variation):
{
  "name": "var01_hypnotic_dawn",          # used as filename
  "concept": "sparse hypnotic intro",     # free text (mood/energy)
  "tempo": 132,
  "bars": [                               # EXACTLY 8
     {"chord": "Am9", "notes": [57,64,67,71]}, ... x8
  ],
  "lead_notes": [[start,dur,pitch,vel], ...],   # full 8-bar ostinato (cell x8, vary bars 4&8)
  "wail_notes": [[start,dur,pitch,vel], ...],   # sustained high backing
  "bass":  {"roots": [8 low-midi], "pattern": "octave_bounce|driving|rolling|half"},
  "acid":  {"roots": [8 low-midi], "pattern": "drone16|rolling|offbeat|sparse",
            "accents": [[bar0,beat,pitch], ...]},   # bar0 is 0-indexed
  "drums": {"kit": "goa909|minimal|driving|breaks", "kick": "four|broken|offbeat",
            "intensity": 0.0-1.0}
}

Usage:  render_variation.py specs.json outdir
"""

import sys
import json
import os
import mido

PPQ = 480
BEATS_PER_BAR = 4
N_BARS = 8

# ---- GM-ish percussion notes (channel 9) ----
KICK = 36
SNARE = 38
CLAP = 39
RIM = 37
LTOM = 41
CHAT = 42
OHAT = 46


# ============================ pattern libraries ============================

def bass_pattern(name, root):
    """Return [(beat, dur, pitch, vel)] for one bar given low-octave root midi."""
    r, hi = root, root + 12
    if name == "driving":          # relentless straight 8ths on the low root
        return [(i * 0.5, 0.48, r, 100) for i in range(8)]
    if name == "rolling":          # 16th offbeat gallop, octave jumps
        out = []
        for i in range(8):
            b = i * 0.5
            out.append((b, 0.12, r, 100))
            out.append((b + 0.25, 0.12, hi, 78))
        return out
    if name == "half":             # sparse, long roots on 1 and 3
        return [(0.0, 1.6, r, 100), (2.0, 1.6, r, 100)]
    # default octave_bounce: low/high alternating 8ths (the example's feel)
    pat = []
    for i in range(8):
        pat.append((i * 0.5, 0.48, r if i % 2 == 0 else hi, 100 if i % 2 == 0 else 86))
    return pat


def acid_pattern(name, root, bar_accents):
    """Return [(beat, dur, pitch, vel)] for one bar. bar_accents: {beat: pitch}."""
    out = []
    if name == "sparse":
        grid = [(i * 0.5) for i in range(8)]
        dur = 0.45
    elif name == "offbeat":
        grid = [0.25 + i * 0.5 for i in range(8)]
        dur = 0.2
    else:  # drone16 / rolling => 16th grid
        grid = [i * 0.25 for i in range(16)]
        dur = 0.12
    for j, b in enumerate(grid):
        pitch = bar_accents.get(round(b, 3), root)
        if name == "rolling" and pitch == root and j % 4 == 2:
            pitch = root + 12          # octave pop on the rolling variant
        accent = (round(b, 3) in bar_accents) or (b == 0.0) or (abs(b - 1.0) < 1e-6)
        vel = 112 if accent else 86
        out.append((b, dur, pitch, vel))
    return out


def drum_kit(name, intensity):
    """Return per-bar [(beat, note, dur, vel)] (channel 9), scaled by intensity."""
    def v(x):
        return max(1, min(127, int(x * (0.6 + 0.4 * intensity))))

    if name == "minimal":
        bar = [(1.0, CLAP, 0.25, v(100)), (3.0, CLAP, 0.25, v(100))]
        bar += [(i * 0.5, CHAT, 0.2, v(40 if i % 2 else 60)) for i in range(8)]
        return bar
    if name == "driving":
        bar = []
        for i in range(16):
            bar.append((i * 0.25, CHAT, 0.12, v(70 if i % 2 == 0 else 38)))
        bar += [(1.0, SNARE, 0.25, v(100)), (3.0, SNARE, 0.25, v(100)),
                (1.0, CLAP, 0.25, v(90)), (3.0, CLAP, 0.25, v(90)),
                (2.5, LTOM, 0.25, v(70))]
        return bar
    if name == "breaks":
        bar = [(0.0, SNARE, 0.25, v(40)), (0.75, SNARE, 0.25, v(80)),
               (1.0, CLAP, 0.25, v(100)), (1.75, SNARE, 0.25, v(60)),
               (2.25, SNARE, 0.25, v(70)), (3.0, CLAP, 0.25, v(100)),
               (3.5, SNARE, 0.25, v(55))]
        bar += [(0.25 + i * 0.5, CHAT, 0.15, v(55)) for i in range(8)]
        return bar
    # default goa909 — faithful to the example's per-bar groove
    bar = [
        (0.0, SNARE, 0.25, v(48)), (0.25, SNARE, 0.25, v(15)), (0.25, CHAT, 0.25, v(42)),
        (0.5, CLAP, 0.25, v(100)), (0.75, CHAT, 0.25, v(45)),
        (1.0, SNARE, 0.25, v(100)), (1.0, LTOM, 0.25, v(100)),
        (1.25, SNARE, 0.25, v(15)), (1.5, CLAP, 0.25, v(15)),
        (2.0, SNARE, 0.25, v(43)), (2.25, SNARE, 0.25, v(15)), (2.5, CLAP, 0.25, v(100)),
        (3.0, SNARE, 0.25, v(100)), (3.0, LTOM, 0.25, v(100)), (3.0, RIM, 0.75, v(100)),
        (3.25, SNARE, 0.25, v(100)), (3.5, CLAP, 0.25, v(15)),
    ]
    return bar


def kick_pattern(name):
    """Return per-bar [(beat, dur, vel)] for the kick (channel 9, note KICK)."""
    if name == "broken":
        return [(0.0, 0.3, 100), (1.0, 0.3, 100), (2.0, 0.3, 100),
                (2.75, 0.3, 90), (3.5, 0.3, 95)]
    if name == "offbeat":
        return [(0.0, 0.3, 100), (1.0, 0.3, 100), (1.5, 0.3, 80),
                (2.0, 0.3, 100), (3.0, 0.3, 100), (3.5, 0.3, 80)]
    return [(i * 1.0, 0.3, 100) for i in range(4)]   # four-on-the-floor


# ============================ midi assembly ============================

def t(beats):
    return int(round(beats * PPQ))


def add_notes(track, notes, channel):
    """notes: list of (start_beat, dur_beat, pitch, vel). Emits delta-timed msgs."""
    evs = []
    for s, d, p, v in notes:
        evs.append((t(s), 1, "note_on", p, v))
        evs.append((t(s + max(d * 0.96, 0.02)), 0, "note_off", p, 0))
    evs.sort(key=lambda e: (e[0], e[1]))
    prev = 0
    for tick, _, kind, p, v in evs:
        track.append(mido.Message(kind, note=int(p), velocity=int(v),
                                  time=tick - prev, channel=channel))
        prev = tick


def expand_spec(spec):
    """Normalize a compact spec (lead_cell + cadence variations, wail_pitches)
    into a full render spec (lead_notes, wail_notes). Enforces the ostinato
    principle structurally: one fixed cell repeated, varied only at named bars."""
    spec = dict(spec)
    # ---- lead: repeat the fixed cell across all 8 bars, swap variation bars ----
    if "lead_notes" not in spec and "lead_cell" in spec:
        cell = spec["lead_cell"]
        var = {}
        for entry in spec.get("lead_var", []):
            var[int(entry["bar"])] = entry["cell"]
        lead = []
        for bi in range(N_BARS):
            c = var.get(bi, cell)
            for beat, d, p, v in c:
                lead.append([bi * 4 + beat, d, p, v])
        spec["lead_notes"] = lead
    # ---- wail: one sustained pitch per bar; optional bar-8 run override ----
    if "wail_notes" not in spec and "wail_pitches" in spec:
        wp = spec["wail_pitches"]
        wail = []
        last = N_BARS - 1
        for bi in range(N_BARS):
            if bi == last and spec.get("wail_bar8"):
                for s, d, p, v in spec["wail_bar8"]:
                    wail.append([bi * 4 + s, d, p, v])
            else:
                wail.append([bi * 4, 4.0, wp[bi], 100])
        spec["wail_notes"] = wail
    return spec


def render(spec):
    spec = expand_spec(spec)
    mf = mido.MidiFile(type=1, ticks_per_beat=PPQ)
    tempo = mido.bpm2tempo(spec.get("tempo", 132))

    def new_track(name):
        tr = mido.MidiTrack(); mf.tracks.append(tr)
        tr.append(mido.MetaMessage("track_name", name=name, time=0))
        tr.append(mido.MetaMessage("set_tempo", tempo=tempo, time=0))
        return tr

    # 0 Chords
    tr = new_track("Chords")
    cn = []
    for bi, bar in enumerate(spec["bars"]):
        for p in bar["notes"]:
            cn.append((bi * 4, 3.8, p, 88))
    add_notes(tr, cn, 0)

    # 1 Ostinato Lead
    tr = new_track("Bittersweet Ostinato Lead")
    add_notes(tr, [tuple(x) for x in spec["lead_notes"]], 1)

    # 2 Wailing Backing
    tr = new_track("Wailing Melody Backing")
    add_notes(tr, [tuple(x) for x in spec.get("wail_notes", [])], 2)

    # 3 303 Riff
    tr = new_track("303 Riff")
    acid = spec["acid"]
    acc_by_bar = {}
    for a in acid.get("accents", []):
        bar0, beat, pitch = a
        acc_by_bar.setdefault(int(bar0), {})[round(float(beat), 3)] = int(pitch)
    an = []
    for bi in range(N_BARS):
        for b, d, p, v in acid_pattern(acid.get("pattern", "drone16"),
                                       acid["roots"][bi], acc_by_bar.get(bi, {})):
            an.append((bi * 4 + b, d, p, v))
    add_notes(tr, an, 3)

    # 4 909 Kit (channel 9)
    tr = new_track("909 Kit")
    dn = []
    kit = drum_kit(spec["drums"].get("kit", "goa909"), spec["drums"].get("intensity", 0.8))
    for bi in range(N_BARS):
        for b, note, d, v in kit:
            dn.append((bi * 4 + b, d, note, v))
    add_notes(tr, dn, 9)

    # 5 Sub Bass
    tr = new_track("Sub Bass")
    bn = []
    bass = spec["bass"]
    for bi in range(N_BARS):
        for b, d, p, v in bass_pattern(bass.get("pattern", "octave_bounce"), bass["roots"][bi]):
            bn.append((bi * 4 + b, d, p, v))
    add_notes(tr, bn, 5)

    # 6 Kick (channel 9)
    tr = new_track("Kick")
    kn = []
    for bi in range(N_BARS):
        for b, d, v in kick_pattern(spec["drums"].get("kick", "four")):
            kn.append((bi * 4 + b, d, KICK, v))
    add_notes(tr, kn, 9)

    return mf


def main():
    specs_path, outdir = sys.argv[1], sys.argv[2]
    os.makedirs(outdir, exist_ok=True)
    specs = json.load(open(specs_path))
    if isinstance(specs, dict):
        specs = [specs]
    for i, spec in enumerate(specs):
        name = spec.get("name", f"variation_{i+1:02d}")
        mf = render(spec)
        path = os.path.join(outdir, name + ".mid")
        mf.save(path)
        notes = sum(1 for tr in mf.tracks for m in tr if m.type == "note_on" and m.velocity > 0)
        print(f"{name}.mid  ({len(mf.tracks)} tracks, {notes} notes, {mf.length:.1f}s)")


if __name__ == "__main__":
    main()
