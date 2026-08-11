#!/usr/bin/env python
"""hook_metric.py — reusable per-clip lead-melody hook metrics.

Factored out of the corpus study (phase1_features.py grid/lead extraction +
phase3_motifs.py per-file motif mining) so the SAME numbers computed for the
muscriptor_full corpus (memorability.json) can be scored on OUR RENDERS
(model_matrix clips) via eval/hook_eval_renders.py.

Core entry point:

    hook_metrics(notes, beat_period_s=None) -> dict

notes = list of (start_s, end_s, pitch, velocity, is_drum, track_idx).
beat_period_s = seed beat period (60/bpm). If None it is estimated from the
kick track; either way it is REFINED (±4%) by maximizing the circular
concentration of kick onsets mod T — this refinement is load-bearing: a 0.5%
BPM error drifts the 16th grid by whole beats over a 380 s clip
(corpus kick_on_beat went 0.27 -> 0.99 with it).

Pipeline (identical to phase1+phase3, verified against memorability.json):
  1. bass pick: non-drum track maximizing n_notes*frac(pitch<=55), med pitch<=50
  2. lead = skyline: highest onset with pitch>=56 per 16th slot over the
     remaining non-drum tracks; needs >= 40 lead notes else {"no_lead": true}
  3. phrases = runs of lead slots with gaps < 3 empty 16th slots (>=3 notes)
  4. grid tier: within-phrase 4-6-grams of successive semitone intervals
     (clipped ±12, zeros included) -> best-repeated gram = pedal hook
  5. contour tier: same grams over NONZERO intervals only (zero-runs
     collapsed = melodic skeleton) -> best-repeated gram = melodic hook
     hook_melodic_ratio = count * (len(gram)+1) / n_lead_notes
     (hooky corpus decile: best motif ~56x per 380 s; non-hooky: 0)

Returned keys (subset): hook_melodic_ratio, hook_melodic_count,
hook_melodic_gram, contour_compression (distinct 4-6 contour-gram ratio; hooky
~0.41, bland ~0.98), hook_pedal_count/ratio/gram, distinct46_grid_ratio,
lead_density_nps, pedal_occupancy (frac of within-phrase lead intervals == 0,
i.e. rolling same-note-16th surface), pitch_range_st (lead p95-p5),
top_motif {intervals, count, degree_seq}, n_lead, bpm, beat_period_s,
beat_refined, tonic, mode.

NOTE FOR CONSUMERS: hook_eval_renders.py emits plain JSONL only — no
clip_metrics.db writes, no page-builder edits here. W wires the columns into
the eval tables downstream.

phase3_motifs.py may import grams_of / contour_grams_of / classify /
phrase-iteration from here; the functions are verbatim-identical to the ones
the corpus artifacts were built with.

Pure numpy + stdlib (imports in mir venv, SAO venv, sa3 venv alike). The
optional MIDI parsers at the bottom need mido or pretty_midi respectively.
"""
from collections import Counter
import numpy as np

LEAD_PITCH_MIN = 56
MIN_LEAD_NOTES = 40
PHRASE_GAP_SLOTS = 3
HOOK_MIN_GRAMS = 20        # phase3: files with < 20 4-6-gram instances get no hook stats

DEGNAMES_MIN = {0: '1', 1: 'b2', 2: '2', 3: 'b3', 4: '3', 5: '4', 6: 'b5',
                7: '5', 8: 'b6', 9: '6', 10: 'b7', 11: '7'}

# Krumhansl-Kessler profiles (phase1)
KK_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
KK_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


# ---------------------------------------------------------------- beat grid

def estimate_bpm_from_kick(kick_onsets):
    """Median kick IOI in the 80..200 bpm beat-period band (phase1)."""
    if len(kick_onsets) < 20:
        return None
    ioi = np.diff(np.sort(kick_onsets))
    ioi = ioi[(ioi > 0.3) & (ioi < 0.75)]
    if len(ioi) < 10:
        return None
    return float(60.0 / np.median(ioi))


def refine_period(onsets, T0, span=0.04, n=801):
    """Refine beat period around T0 by maximizing circular concentration of
    onsets mod T (phase1). The ±4% sweep is load-bearing for long clips."""
    if len(onsets) < 16:
        return T0
    t = np.asarray(onsets)
    Ts = T0 * np.linspace(1 - span, 1 + span, n)
    conc = np.abs(np.exp(2j * np.pi * t[None, :] / Ts[:, None]).mean(axis=1))
    return float(Ts[int(np.argmax(conc))])


def grid_phase(onsets, beat):
    """Circular-mean phase of onsets w.r.t. beat period (phase1)."""
    if len(onsets) == 0:
        return 0.0
    ang = 2 * np.pi * (np.asarray(onsets) % beat) / beat
    m = np.angle(np.mean(np.exp(1j * ang)))
    if m < 0:
        m += 2 * np.pi
    return float(m / (2 * np.pi) * beat)


def fold_bpm(bpm):
    """Fold halved/doubled detections into the 90..200 dance band (phase1)."""
    bpm = float(bpm)
    if bpm < 90:
        bpm *= 2
    if bpm > 200:
        bpm /= 2
    return bpm


# ------------------------------------------------------------ motif grams
# Verbatim from phase3_motifs.py (per-file mining uses n = 4..6 only; the
# corpus miner also generates 7-8-grams but filters them out of the per-file
# hook stats, so iterating 4..6 here preserves insertion order exactly —
# which matters for its first-max tie-breaking).

NS_HOOK = range(4, 7)


def grams_of(pitches, ns=NS_HOOK):
    iv = [max(-12, min(12, pitches[j + 1] - pitches[j])) for j in range(len(pitches) - 1)]
    for n in ns:
        for j in range(len(iv) - n + 1):
            yield tuple(iv[j:j + n]), j


def contour_grams_of(pitches, ns=NS_HOOK):
    """n-grams over NONZERO intervals only (zero-runs collapsed): the melodic
    skeleton, invariant to how many same-note 16th repeats sit between moves."""
    moves = []
    for j in range(len(pitches) - 1):
        d = pitches[j + 1] - pitches[j]
        if d != 0:
            moves.append((j, max(-12, min(12, d))))
    iv = [d for _, d in moves]
    for n in ns:
        for j in range(len(iv) - n + 1):
            yield tuple(iv[j:j + n]), moves[j][0]


def classify(g):
    s = set(g)
    if s == {0}: return 'pedal'
    nz = [x for x in g if x != 0]
    if not nz: return 'pedal'
    if all(x < 0 for x in nz) and all(abs(x) <= 2 for x in nz): return 'descending run'
    if all(x > 0 for x in nz) and all(abs(x) <= 2 for x in nz): return 'ascending run'
    if all(x < 0 for x in nz): return 'descending arp/leap line'
    if all(x > 0 for x in nz): return 'ascending arp/leap line'
    if len(s - {0}) <= 2 and any(-x in s for x in s if x): return 'oscillation'
    if any(abs(x) >= 12 for x in g): return 'octave-jump figure'
    if max(abs(x) for x in g) >= 5: return 'zigzag w/ leaps'
    return 'zigzag stepwise'


def _phrase_iter(slots, pitches, bounds):
    for i in range(len(bounds) - 1):
        a, b = bounds[i], bounds[i + 1]
        if b - a >= 3:
            yield slots[a:b], pitches[a:b]


def _best46(slots, pitches, bounds, gram_fn):
    """phase3 per-file mining: count all 4-6-grams within phrases, return
    (best_gram, best_count, n_instances, n_distinct, first_seen_index_of_best)."""
    local = Counter()
    first = {}
    for sl, pi in _phrase_iter(slots, pitches, bounds):
        for g, j in gram_fn(pi):
            local[g] += 1
            if g not in first:
                first[g] = (sl, pi, j)
    tot = sum(local.values())
    if tot < HOOK_MIN_GRAMS:
        return None, 0, tot, len(local), None
    best_g, best_c = max(local.items(), key=lambda kv: kv[1])
    return best_g, int(best_c), tot, len(local), first[best_g]


# ---------------------------------------------------------------- key (phase1)

def krumhansl(pc):
    pc = np.asarray(pc, float)
    if pc.sum() <= 0:
        return None
    best = None
    for mode, prof in (('major', KK_MAJOR), ('minor', KK_MINOR)):
        for tonic in range(12):
            r = np.corrcoef(np.roll(prof, tonic), pc)[0, 1]
            if best is None or r > best[2]:
                best = (tonic, mode, float(r))
    return best


# ---------------------------------------------------------------- main entry

def hook_metrics(notes, beat_period_s=None):
    """Per-clip hook metrics. notes = [(start_s, end_s, pitch, velocity,
    is_drum, track_idx), ...]; beat_period_s = optional seed beat period.
    Returns {"no_lead": true, ...} if the skyline lead has < 40 notes, or
    {"no_beat": true} if no beat period could be seeded (caller may retry
    with e.g. a librosa tempo estimate)."""
    notes = sorted(notes, key=lambda n: (n[0], n[2]))
    drums = [n for n in notes if n[4]]
    melodic_by_track = {}
    for n in notes:
        if not n[4]:
            melodic_by_track.setdefault(n[5], []).append(n)
    tracks = sorted(melodic_by_track)
    if not tracks:
        return {"no_lead": True, "n_lead": 0, "reason": "no melodic notes"}

    # --- bass pick (phase1)
    def bass_score(ns):
        ps = np.array([n[2] for n in ns])
        if np.median(ps) > 50:
            return -1.0
        return len(ps) * float(np.mean(ps <= 55))
    scores = [bass_score(melodic_by_track[t]) for t in tracks]
    bi = int(np.argmax(scores))
    has_bass = scores[bi] > 0
    other_tracks = [t for j, t in enumerate(tracks) if not has_bass or j != bi]

    # --- beat grid
    kick = [n[0] for n in drums if n[2] in (35, 36)]
    if beat_period_s is not None:
        bpm = fold_bpm(60.0 / float(beat_period_s))
    else:
        bpm = estimate_bpm_from_kick(kick)
        if bpm is None:
            return {"no_beat": True, "n_kick": len(kick)}
        bpm = fold_bpm(bpm)
    beat = 60.0 / bpm
    refined = False
    if len(kick) >= 16:
        beat = refine_period(kick, beat)
        bpm = 60.0 / beat
        refined = True
    step = beat / 4.0
    phase = grid_phase(kick, beat) if len(kick) >= 16 else 0.0

    def slot_of(t):
        return int(round((t - phase) / step))

    # --- lead skyline on the 16th grid (phase1)
    lead_events = {}
    for t in other_tracks:
        for (s0, e0, p, v, _d, _t) in melodic_by_track[t]:
            if p < LEAD_PITCH_MIN:
                continue
            s = slot_of(s0)
            if s < 0:
                continue
            cur = lead_events.get(s)
            if cur is None or p > cur:
                lead_events[s] = p
    lead_slots = sorted(lead_events)
    n_lead = len(lead_slots)
    base = dict(bpm=round(bpm, 3), beat_period_s=round(beat, 6),
                beat_refined=refined, n_kick=len(kick), n_lead=n_lead)
    if n_lead < MIN_LEAD_NOTES:
        return {"no_lead": True, **base}

    lp = [int(lead_events[s]) for s in lead_slots]
    lt = np.array(lead_slots)
    gaps = np.diff(lt)
    brk = np.where(gaps >= PHRASE_GAP_SLOTS)[0]
    bounds = np.concatenate([[0], brk + 1, [len(lt)]]).astype(int).tolist()
    slots_l = [int(s) for s in lt]

    # --- key for degree naming (phase1: duration-weighted midi pc, all melodic)
    midi_pc = np.zeros(12)
    for t in tracks:
        for (s0, e0, p, v, _d, _t) in melodic_by_track[t]:
            midi_pc[p % 12] += min(e0 - s0, 2.0)
    ks = krumhansl(midi_pc)
    tonic, mode = (ks[0], ks[1]) if ks else (0, 'minor')

    # --- grid tier (pedal/surface hook)
    g_gram, g_cnt, g_tot, g_dist, _gf = _best46(slots_l, lp, bounds, grams_of)
    # --- contour tier (melodic hook)
    c_gram, c_cnt, c_tot, c_dist, c_first = _best46(slots_l, lp, bounds, contour_grams_of)

    dur = max(1.0, max(n[1] for n in notes) - min(n[0] for n in notes))
    ivs = [pi[j + 1] - pi[j] for _sl, pi in _phrase_iter(slots_l, lp, bounds)
           for j in range(len(pi) - 1)]
    lp_a = np.array(lp)

    out = dict(base)
    out.update(
        hook_melodic_ratio=round(c_cnt * (len(c_gram) + 1) / max(1, n_lead), 4) if c_gram else 0.0,
        hook_melodic_count=c_cnt if c_gram else 0,
        hook_melodic_gram=list(c_gram) if c_gram else None,
        contour_compression=round(c_dist / c_tot, 4) if c_tot >= HOOK_MIN_GRAMS else None,
        hook_pedal_count=g_cnt if g_gram else 0,
        hook_pedal_ratio=round(g_cnt * (len(g_gram) + 1) / max(1, n_lead), 4) if g_gram else 0.0,
        hook_pedal_gram=list(g_gram) if g_gram else None,
        distinct46_grid_ratio=round(g_dist / g_tot, 4) if g_tot >= HOOK_MIN_GRAMS else None,
        sparse_lead=bool(g_tot < HOOK_MIN_GRAMS),   # phase3 dropped such files entirely
        lead_density_nps=round(n_lead / dur, 4),
        pedal_occupancy=round(float(np.mean([iv == 0 for iv in ivs])), 4) if ivs else 0.0,
        pitch_range_st=round(float(np.percentile(lp_a, 95) - np.percentile(lp_a, 5)), 2),
        tonic=int(tonic), mode=mode,
    )
    top = None
    if c_gram:
        top = dict(intervals=list(c_gram), count=c_cnt, klass=classify(c_gram))
        if c_first is not None:
            sl, pi, j = c_first
            degs = [(p - tonic) % 12 for p in pi[j:j + len(c_gram) + 1]]
            top['degree_seq'] = '-'.join(DEGNAMES_MIN[d] for d in degs)
    out['top_motif'] = top
    return out


# ------------------------------------------------------------- MIDI parsers

def notes_from_midi_bytes(b):
    """Parse MIDI bytes (e.g. muscriptor transcribe_to_midi output) with mido
    -> notes tuples. Drums = channel 9. track_idx groups by (track, channel)
    so multi-channel type-0/1 files split like pretty_midi instruments."""
    import io, mido
    m = mido.MidiFile(file=io.BytesIO(b))
    tempo = 500000
    notes = []
    open_notes = {}
    keys = {}
    for ti, tr in enumerate(m.tracks):
        t = 0
        for msg in tr:
            t += msg.time
            sec = mido.tick2second(t, m.ticks_per_beat, tempo)
            if msg.type == 'set_tempo':
                tempo = msg.tempo
            elif msg.type == 'note_on' and msg.velocity > 0:
                open_notes[(ti, msg.channel, msg.note)] = (sec, msg.velocity)
            elif msg.type in ('note_off', 'note_on'):
                k = (ti, msg.channel, msg.note)
                if k in open_notes:
                    s0, vel = open_notes.pop(k)
                    gk = (ti, msg.channel)
                    if gk not in keys:
                        keys[gk] = len(keys)
                    notes.append((s0, sec, msg.note, vel,
                                  msg.channel == 9, keys[gk]))
    return notes


def notes_from_pretty_midi(pm):
    """pretty_midi.PrettyMIDI -> notes tuples (track_idx = instrument index,
    matching phase1's per-instrument bass pick exactly)."""
    notes = []
    for ti, inst in enumerate(pm.instruments):
        for n in inst.notes:
            notes.append((n.start, n.end, n.pitch, n.velocity, inst.is_drum, ti))
    return notes
