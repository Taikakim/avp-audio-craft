"""
1992 Ibiza trance intro — A Dorian, 8 bars, bittersweet.

Two passes:
  chords  -> records voice-led pad progression to track 1
  lead    -> records lone descending melody to track 2 (octave above)

Usage:
  python play_ibiza_chords.py chords
  python play_ibiza_chords.py lead

Set the target track's MIDI input to VirMIDI 3-0 and arm happens via OSC.
"""

import sys
import time
import heapq
import mido
from pythonosc import udp_client

BPM = 132
BEAT = 60.0 / BPM
VELOCITY = 88
LEAD_VELOCITY = 78
MIDI_PORT = "Virtual Raw MIDI 3-0:VirMIDI 3-0 28:0"
BITWIG_HOST = "127.0.0.1"
BITWIG_OSC_PORT = 8000

# ---- Voice-led pad chords: (start_beat, [notes]) ----
# Bars 1-3 / 5-7 share Am->D->G; bars 4 & 8 are the unique cadences.
CHORD_HOLD_BEATS = 3.8
CHORDS = [
    (0,  [57, 64, 67, 71]),   # 1 Am9        A3 E4 G4 B4
    (4,  [54, 62, 66, 69]),   # 2 D/F#       F#3 D4 F#4 A4
    (8,  [55, 62, 66, 71]),   # 3 Gmaj7      G3 D4 F#4 B4
    (12, [52, 62, 67, 71]),   # 4 Em7        E3 D4 G4 B4   (soft comma)
    (16, [57, 67, 71, 76]),   # 5 Am9 open   A3 G4 B4 E5
    (20, [54, 64, 69, 76]),   # 6 Dadd9/F#   F#3 E4 A4 E5
    (24, [55, 66, 71, 74]),   # 7 Gmaj7 sprd G3 F#4 B4 D5
    (28, [48, 64, 67, 71]),   # 8 Cmaj7      C3 E4 G4 B4   (bright-sad resolve)
]

# ---- Lone lead: ONE 2-bar rhythmic cell, stated 4x with melodic variation ----
# A Dorian (natural 2nd, NO Phrygian b2). The rhythm is a fixed groove skeleton
# (the "drum map") repeated every two bars; only the pitches change, and they
# are a sequence of one motif, so every note relates to the earlier ones.
#
# Cell rhythm (local beats, dur):  this is the SAME in all four cells
#   0.0 q   beat 1  -- anchor (kick)
#   1.0 e   beat 2  -- ACCENT (snare/backbeat)
#   1.5 e   and-of-2 -- ghost answer
#   [beat 3 = REST: breath]
#   3.0 e   beat 4  -- ACCENT (snare/backbeat)
#   3.5 e   and-of-4 -- anticipation, pushes over the barline
#   4.0 h   beat 1  -- LANDING, sustained (held through the backbeat)
#   6.0 q   beat 3  -- restate
#   [rest]
#   7.5 e   and-of-4 -- anticipation, loops into the next cell
#
# Velocity follows the drummer: backbeats (beats 2 & 4) and the landing are
# accented; the and-of-2 ghost and the pickups are soft.
LEAD = [
    # === Cell 1 (bars 1-2: Am9 -> D/F#) : the statement ===
    (0.0, 1.0, 76, 78),   # E5  anchor (5th of Am)
    (1.0, 0.5, 79, 88),   # G5  ACCENT, up to the b7
    (1.5, 0.5, 76, 66),   # E5  ghost answer, back down
    (3.0, 0.5, 72, 84),   # C5  ACCENT, the melancholy minor 3rd
    (3.5, 0.5, 74, 74),   # D5  anticipation -> targets the D chord
    (4.0, 2.0, 78, 90),   # F#5 LANDING, 3rd of D, sustained (the Dorian bloom)
    (6.0, 1.0, 76, 76),   # E5  restate (9th of D)
    (7.5, 0.5, 74, 70),   # D5  pickup, loops into cell 2
    # === Cell 2 (bars 3-4: Gmaj7 -> Em7) : same motif, dropped low (loss) ===
    (8.0, 1.0, 74, 78),   # D5  anchor (5th of G)
    (9.0, 0.5, 78, 88),   # F#5 ACCENT, the maj7
    (9.5, 0.5, 74, 66),   # D5  ghost answer
    (11.0, 0.5, 71, 84),  # B4  ACCENT, the 3rd of G
    (11.5, 0.5, 71, 74),  # B4  anticipation -> Em
    (12.0, 2.0, 67, 90),  # G4  LANDING low, b3 of Em, sustained (the loss)
    (14.0, 1.0, 71, 76),  # B4  restate (5th of Em)
    (15.5, 0.5, 71, 70),  # B4  pickup (9th of Am), loops into cell 3
    # === Cell 3 (bars 5-6: Am9 -> Dadd9) : motif opened into a climb (sublime) ===
    (16.0, 1.0, 81, 80),  # A5  anchor (root, up an octave)
    (17.0, 0.5, 83, 90),  # B5  ACCENT, the 9th
    (17.5, 0.5, 84, 68),  # C6  keeps climbing (variation: up, not back)
    (19.0, 0.5, 86, 86),  # D6  ACCENT, climbing
    (19.5, 0.5, 86, 76),  # D6  anticipation -> D chord
    (20.0, 2.0, 88, 100), # E6  LANDING = THE PEAK, 9th of D (sublime)
    (22.0, 1.0, 86, 80),  # D6  restate, step down from the peak
    (23.5, 0.5, 83, 72),  # B5  pickup, descending, loops into cell 4
    # === Cell 4 (bars 7-8: Gmaj7 -> Cmaj7) : home, then hang (letting go) ===
    (24.0, 1.0, 74, 78),  # D5  anchor (5th of G, back to mid register)
    (25.0, 0.5, 79, 88),  # G5  ACCENT
    (25.5, 0.5, 78, 66),  # F#5 ghost answer, the maj7
    (27.0, 0.5, 74, 84),  # D5  ACCENT
    (27.5, 0.5, 72, 74),  # C5  anticipation -> C chord
    (28.0, 2.0, 76, 90),  # E5  LANDING, 3rd of C, sustained (gentle)
    (30.0, 1.0, 74, 76),  # D5  restate, step down
    (31.5, 0.5, 71, 70),  # B4  pickup = maj7 of C, HANGS, loops back to Am9
]


def write_midi():
    """Write bar-perfect MIDI files for chords and lead (drag into Bitwig)."""
    import mido as _m
    PPQ = 480
    tempo = _m.bpm2tempo(BPM)

    def ticks(beats):
        return int(round(beats * PPQ))

    # ---- chords file ----
    mf = _m.MidiFile(ticks_per_beat=PPQ)
    tr = _m.MidiTrack(); mf.tracks.append(tr)
    tr.append(_m.MetaMessage("set_tempo", tempo=tempo, time=0))
    tr.append(_m.MetaMessage("track_name", name="Ibiza Chords", time=0))
    # flatten to absolute-time on/off events, then delta-encode
    evs = []
    for start, notes in CHORDS:
        on = ticks(start)
        off = ticks(start + CHORD_HOLD_BEATS)
        for n in notes:
            evs.append((on, "note_on", n, VELOCITY))
            evs.append((off, "note_off", n, 0))
    evs.sort(key=lambda e: (e[0], e[1] == "note_on"))
    prev = 0
    for t, kind, n, v in evs:
        tr.append(_m.Message(kind, note=n, velocity=v, time=t - prev))
        prev = t
    mf.save("/home/kim/Projects/bitwig-mcp-server/ibiza_chords.mid")

    # ---- lead file ----
    mf2 = _m.MidiFile(ticks_per_beat=PPQ)
    tr2 = _m.MidiTrack(); mf2.tracks.append(tr2)
    tr2.append(_m.MetaMessage("set_tempo", tempo=tempo, time=0))
    tr2.append(_m.MetaMessage("track_name", name="Ibiza Lead", time=0))
    evs2 = []
    for start, dur, n, vel in LEAD:
        on = ticks(start)
        off = ticks(start + dur * 0.95)
        evs2.append((on, "note_on", n, vel))
        evs2.append((off, "note_off", n, 0))
    evs2.sort(key=lambda e: (e[0], e[1] == "note_on"))
    prev = 0
    for t, kind, n, v in evs2:
        tr2.append(_m.Message(kind, note=n, velocity=v, time=t - prev))
        prev = t
    mf2.save("/home/kim/Projects/bitwig-mcp-server/ibiza_lead.mid")

    print("Wrote ibiza_chords.mid (8 chords) and ibiza_lead.mid")
    print(f"Tempo {BPM} BPM, 4 beats/bar. Drag onto track 1 (chords) and track 2 (lead).")


def build_events(part):
    """Return a min-heap of (time_sec, order, 'on'/'off', note, vel)."""
    events = []
    order = 0
    if part == "chords":
        for start, notes in CHORDS:
            on_t = start * BEAT
            off_t = (start + CHORD_HOLD_BEATS) * BEAT
            for n in notes:
                events.append((on_t, order, "on", n, VELOCITY)); order += 1
                events.append((off_t, order, "off", n, 0)); order += 1
    else:  # lead
        for start, dur, n, vel in LEAD:
            on_t = start * BEAT
            off_t = (start + dur * 0.95) * BEAT
            events.append((on_t, order, "on", n, vel)); order += 1
            events.append((off_t, order, "off", n, 0)); order += 1
    heapq.heapify(events)
    return events


def main():
    part = sys.argv[1] if len(sys.argv) > 1 else "chords"
    if part == "midi":
        write_midi()
        return 0
    if part not in ("chords", "lead"):
        print("Usage: play_ibiza_chords.py [chords|lead|midi]")
        return 1

    track = 1 if part == "chords" else 2
    other = 2 if track == 1 else 1
    osc = udp_client.SimpleUDPClient(BITWIG_HOST, BITWIG_OSC_PORT)
    events = build_events(part)

    with mido.open_output(MIDI_PORT) as port:
        print("Resetting transport to bar 1...")
        osc.send_message("/stop", 1)
        time.sleep(0.25)
        osc.send_message("/stop", 1)   # 2nd stop returns playhead to start
        time.sleep(0.25)

        print(f"Arming track {track} (disarming {other})...")
        osc.send_message(f"/track/{other}/recarm", 0)
        osc.send_message(f"/track/{track}/recarm", 1)
        time.sleep(0.3)

        # PUNCH-IN order is required: /record alone arms but doesn't roll, and
        # sending /play AFTER /record cancels record. So roll first with /play,
        # THEN punch in /record while the transport is already moving.
        print("Rolling transport (/play)...")
        osc.send_message("/play", 1)
        time.sleep(0.25)
        print("Punching in record (/record)...")
        osc.send_message("/record", 1)
        time.sleep(0.5 * BEAT)

        print("Count-in: 1 bar...")
        time.sleep(4 * BEAT)

        print(f"Recording {part}...")
        t0 = time.perf_counter()
        active = set()
        while events:
            ev_time, _, kind, note, vel = heapq.heappop(events)
            now = time.perf_counter() - t0
            if ev_time > now:
                time.sleep(ev_time - now)
            if kind == "on":
                port.send(mido.Message("note_on", note=note, velocity=vel))
                active.add(note)
            else:
                port.send(mido.Message("note_off", note=note, velocity=0))
                active.discard(note)

        # safety: all notes off
        for n in list(active):
            port.send(mido.Message("note_off", note=n, velocity=0))

        time.sleep(BEAT)
        print("Stopping transport...")
        osc.send_message("/stop", 1)
        osc.send_message("/record", 0)   # disengage arranger record
        print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
