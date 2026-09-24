#!/usr/bin/env python
"""Phase 1: per-file musicological features for the muscriptor_full MIDI corpus.

Corpus: /run/media/kim/Kosmos/muscriptor_full/{id}.mid + {id}.stats.json
Outputs (in this dir):
  features.jsonl   -- one JSON object per kept file (resumable, keyed by id)
  melodies.jsonl   -- per-file quantized lead melody (16th-grid slots) for phase 3
  excluded.json    -- ids excluded + reason

Inclusion cutoff: integrity_flag == true AND integrity_pc_corr >= 0.30.

Role inference:
  drums = is_drum tracks; bass = non-drum track maximizing n_notes * frac(pitch<=55)
  with median pitch <= 50 (in practice program 33); lead = skyline (highest onset
  per 16th slot, pitch >= 56) over remaining non-drum tracks.

Run: /home/kim/Projects/mir/mir/bin/python phase1_features.py [--workers N] [--limit N]
Re-runnable: skips ids already present in features.jsonl.
"""
import argparse, json, os, sys, math, glob
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed

CORPUS = '/run/media/kim/Kosmos/muscriptor_full'
META_DIR = '/home/kim/Projects/latents_sa3'
OUT_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURES = os.path.join(OUT_DIR, 'features.jsonl')
MELODIES = os.path.join(OUT_DIR, 'melodies.jsonl')
EXCLUDED = os.path.join(OUT_DIR, 'excluded.json')

CORR_CUTOFF = 0.30
LEAD_PITCH_MIN = 56
MIN_LEAD_NOTES = 40
PHRASE_GAP_SLOTS = 3          # >= this many empty 16th slots ends a phrase

# Krumhansl-Kessler profiles
KK_MAJOR = np.array([6.35,2.23,3.48,2.33,4.38,4.09,2.52,5.19,2.39,3.66,2.29,2.88])
KK_MINOR = np.array([6.33,2.68,3.52,5.38,2.60,3.53,2.54,4.75,3.98,2.69,3.34,3.17])
MAJOR_SCALE = {0,2,4,5,7,9,11}
MINOR_SCALE = {0,2,3,5,7,8,10}   # natural minor; degrees 11 (leading tone) counted separately

def krumhansl(pc):
    pc = np.asarray(pc, float)
    if pc.sum() <= 0: return None
    best = None
    for mode, prof in (('major', KK_MAJOR), ('minor', KK_MINOR)):
        for tonic in range(12):
            r = np.corrcoef(np.roll(prof, tonic), pc)[0,1]
            if best is None or r > best[2]:
                best = (tonic, mode, float(r))
    return best

def load_meta(fid):
    p = os.path.join(META_DIR, fid + '.json')
    if not os.path.exists(p): return {}
    try:
        d = json.load(open(p))
    except Exception:
        return {}
    return {k: d.get(k) for k in ('track_metadata_artist','track_metadata_title',
            'track_metadata_year','track_metadata_genre','bpm_madmom','bpm_essentia',
            'prompt','syncopation','release_year')}

def estimate_bpm_from_kick(kick_onsets):
    if len(kick_onsets) < 20: return None
    ioi = np.diff(np.sort(kick_onsets))
    ioi = ioi[(ioi > 0.3) & (ioi < 0.75)]   # 80..200 bpm beat period
    if len(ioi) < 10: return None
    return float(60.0 / np.median(ioi))

def refine_period(onsets, T0, span=0.04, n=801):
    """Refine beat period around T0 by maximizing circular concentration of
    onsets mod T. A 0.5% bpm error drifts many beats over 380s; this fixes it."""
    if len(onsets) < 16: return T0
    t = np.asarray(onsets)
    Ts = T0 * np.linspace(1-span, 1+span, n)
    conc = np.abs(np.exp(2j*np.pi*t[None,:]/Ts[:,None]).mean(axis=1))
    return float(Ts[int(np.argmax(conc))])

def grid_phase(onsets, beat):
    """Circular-mean phase of onsets w.r.t. beat period."""
    if len(onsets) == 0: return 0.0
    ang = 2*np.pi*(np.asarray(onsets) % beat)/beat
    m = np.angle(np.mean(np.exp(1j*ang)))
    if m < 0: m += 2*np.pi
    return float(m/(2*np.pi)*beat)

def interval_feats(pitches):
    if len(pitches) < 3:
        return dict(ivl_abs_mean=0., step_ratio=0., leap_ratio=0., repeat_ratio=0.,
                    octave_ratio=0., up_ratio=0.5, turning_rate=0.)
    iv = np.diff(pitches)
    nz = iv[iv != 0]
    dirs = np.sign(nz)
    turns = int(np.sum(dirs[1:] != dirs[:-1])) if len(dirs) > 1 else 0
    return dict(
        ivl_abs_mean=float(np.mean(np.abs(iv))),
        step_ratio=float(np.mean((np.abs(iv) >= 1) & (np.abs(iv) <= 2))),
        leap_ratio=float(np.mean(np.abs(iv) >= 5)),
        repeat_ratio=float(np.mean(iv == 0)),
        octave_ratio=float(np.mean(np.abs(iv) == 12)),
        up_ratio=float(np.mean(nz > 0)) if len(nz) else 0.5,
        turning_rate=float(turns / max(1, len(dirs)-1)),
    )

def process_one(fid):
    import pretty_midi
    stats = json.load(open(os.path.join(CORPUS, fid + '.stats.json')))
    if not stats.get('integrity_flag') or (stats.get('integrity_pc_corr') or -1) < CORR_CUTOFF:
        return ('excluded', fid, 'integrity')
    meta = load_meta(fid)
    try:
        pm = pretty_midi.PrettyMIDI(os.path.join(CORPUS, fid + '.mid'))
    except Exception as e:
        return ('excluded', fid, 'parse_error:%s' % e)

    dur = max(pm.get_end_time(), 1.0)
    drums = [i for i in pm.instruments if i.is_drum]
    melodic = [i for i in pm.instruments if not i.is_drum and i.notes]
    if not melodic:
        return ('excluded', fid, 'no_melodic')

    # --- bass pick
    def bass_score(inst):
        ps = np.array([n.pitch for n in inst.notes])
        if np.median(ps) > 50: return -1
        return len(ps) * float(np.mean(ps <= 55))
    scores = [bass_score(i) for i in melodic]
    bi = int(np.argmax(scores))
    bass = melodic[bi] if scores[bi] > 0 else None
    others = [i for j,i in enumerate(melodic) if bass is None or j != bi]

    # --- tempo
    bpm = meta.get('bpm_madmom') or meta.get('bpm_essentia')
    kick = [n.start for d in drums for n in d.notes if n.pitch in (35,36)]
    if not bpm:
        bpm = estimate_bpm_from_kick(kick)
    if not bpm:
        bpm = 140.0
    bpm = float(bpm)
    if bpm < 90: bpm *= 2       # fold halved detections into dance range
    if bpm > 200: bpm /= 2
    beat = 60.0/bpm
    if len(kick) >= 16:
        beat = refine_period(kick, beat)
        bpm = 60.0/beat
    step = beat/4.0
    phase = grid_phase(kick, beat) if len(kick) >= 16 else 0.0

    def slot_of(t): return int(round((t - phase)/step))
    def pos16(t): return slot_of(t) % 16
    def pos4(t): return slot_of(t) % 4

    # --- key: Krumhansl on duration-weighted MIDI pitch classes (self-consistent
    # with the notes we codify; audio pc_profile kept only as integrity signal)
    midi_pc = np.zeros(12)
    for inst in melodic:
        for n in inst.notes:
            midi_pc[n.pitch % 12] += min(n.end - n.start, 2.0)
    ks = krumhansl(midi_pc)
    tonic, mode, kcorr = ks if ks else (0, 'minor', 0.0)
    ks_audio = krumhansl(stats['pc_profile'])
    key_agree = bool(ks_audio and ks_audio[0] == tonic)

    # --- drums
    drum_onsets = [n.start for d in drums for n in d.notes]
    n_kick = len(kick)
    drum_density = len(drum_onsets)/dur
    kick_rate = n_kick/dur
    kick_on_beat = float(np.mean([pos4(t)==0 for t in kick])) if kick else 0.0

    # --- bass
    bass_f = {}
    if bass is not None and len(bass.notes) >= 16:
        bt = sorted(n.start for n in bass.notes)
        bp = [n.pitch for n in sorted(bass.notes, key=lambda n: n.start)]
        p4 = np.array([pos4(t) for t in bt])
        slots = set(slot_of(t) for t in bt)
        span_slots = max(1, slot_of(bt[-1]) - slot_of(bt[0]) + 1)
        bass_f = dict(
            bass_rate=len(bt)/dur,
            bass_offbeat16=float(np.mean(p4 != 0)),
            bass_pos_p1=float(np.mean(p4==1)), bass_pos_p2=float(np.mean(p4==2)),
            bass_pos_p3=float(np.mean(p4==3)),
            bass_occupancy=float(len(slots)/span_slots),
            bass_pitch_std=float(np.std(bp)),
            bass_root_ratio=float(np.mean([(p%12)==tonic for p in bp])),
        )
        bass_f.update({('bass_'+k): v for k,v in interval_feats(np.array(bp)).items()
                       if k in ('repeat_ratio','step_ratio','ivl_abs_mean')})
    has_bass = bool(bass_f)

    # --- lead skyline on 16th grid
    lead_events = {}
    for inst in others:
        for n in inst.notes:
            if n.pitch < LEAD_PITCH_MIN: continue
            s = slot_of(n.start)
            if s < 0: continue
            cur = lead_events.get(s)
            if cur is None or n.pitch > cur[0]:
                lead_events[s] = (n.pitch, n.end - n.start, n.velocity)
    lead_slots = sorted(lead_events)
    lead_f = {}
    melody = None
    has_lead = len(lead_slots) >= MIN_LEAD_NOTES
    if has_lead:
        lp = np.array([lead_events[s][0] for s in lead_slots])
        lt = np.array(lead_slots)
        # phrases by slot gaps
        gaps = np.diff(lt)
        brk = np.where(gaps >= PHRASE_GAP_SLOTS)[0]
        bounds = np.concatenate([[0], brk+1, [len(lt)]])
        phr_lens = np.diff(bounds)
        phr_secs = [(lt[bounds[i+1]-1]-lt[bounds[i]]+1)*step for i in range(len(bounds)-1)]
        deg = (lp % 12 - tonic) % 12
        deg_hist = np.bincount(deg, minlength=12).astype(float); deg_hist /= deg_hist.sum()
        scale = MAJOR_SCALE if mode=='major' else MINOR_SCALE
        chroma_out = float(sum(deg_hist[d] for d in range(12) if d not in scale and not (mode=='minor' and d==11)))
        raised7 = float(deg_hist[11]) if mode=='minor' else 0.0
        p16 = lt % 4
        ivf = interval_feats(lp)
        lead_f = dict(
            lead_n=len(lt), lead_rate=len(lt)/dur,
            lead_pitch_med=float(np.median(lp)),
            lead_range=float(np.percentile(lp,95)-np.percentile(lp,5)),
            lead_offbeat16=float(np.mean(p16 != 0)),
            lead_phrase_n=len(phr_lens),
            lead_phrase_len_med=float(np.median(phr_lens)),
            lead_phrase_len_p90=float(np.percentile(phr_lens,90)),
            lead_phrase_sec_med=float(np.median(phr_secs)),
            lead_chromaticism=chroma_out,
            lead_raised7=raised7,
            lead_b2=float(deg_hist[1]), lead_b6=float(deg_hist[8]), lead_nat6=float(deg_hist[9]),
            lead_deg_hist=[round(float(x),4) for x in deg_hist],
        )
        lead_f.update({('lead_'+k): v for k,v in ivf.items()})
        melody = dict(id=fid, bpm=bpm, tonic=tonic, mode=mode, step=step,
                      slots=[int(s) for s in lt], pitches=[int(p) for p in lp],
                      phrase_bounds=[int(b) for b in bounds])

    # syncopation proxy: all melodic onsets off the beat-grid
    all_on = [n.start for i in melodic for n in i.notes]
    sync = float(np.mean([pos4(t)!=0 for t in all_on])) if all_on else 0.0

    row = dict(id=fid, integrity_pc_corr=stats.get('integrity_pc_corr'),
               n_notes=stats['n_notes'], notes_per_sec=stats['notes_per_sec'],
               bpm=bpm, tonic=tonic, mode=mode, key_corr=kcorr, key_agree_audio=key_agree,
               drum_density=drum_density, kick_rate=kick_rate, kick_on_beat=kick_on_beat,
               syncopation=sync, has_bass=has_bass, has_lead=has_lead,
               artist=meta.get('track_metadata_artist'), title=meta.get('track_metadata_title'),
               year=meta.get('track_metadata_year') or meta.get('release_year'),
               genre=meta.get('track_metadata_genre'), prompt=meta.get('prompt'))
    row.update(bass_f); row.update(lead_f)
    return ('ok', row, melody)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--workers', type=int, default=16)
    ap.add_argument('--limit', type=int, default=0)
    args = ap.parse_args()

    ids = sorted(os.path.basename(p)[:-4] for p in glob.glob(os.path.join(CORPUS,'*.mid')))
    done = set()
    if os.path.exists(FEATURES):
        for line in open(FEATURES):
            try: done.add(json.loads(line)['id'])
            except Exception: pass
    excluded = {}
    if os.path.exists(EXCLUDED):
        excluded = json.load(open(EXCLUDED))
    todo = [i for i in ids if i not in done and i not in excluded]
    if args.limit: todo = todo[:args.limit]
    print(f'{len(ids)} ids, {len(done)} done, {len(excluded)} excluded, {len(todo)} to do', flush=True)

    ff = open(FEATURES, 'a'); mf = open(MELODIES, 'a')
    n_ok = n_ex = 0
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(process_one, fid): fid for fid in todo}
        for k, fut in enumerate(as_completed(futs)):
            try:
                res = fut.result()
            except Exception as e:
                res = ('excluded', futs[fut], 'worker_error:%s' % e)
            if res[0] == 'ok':
                ff.write(json.dumps(res[1]) + '\n')
                if res[2]: mf.write(json.dumps(res[2]) + '\n')
                n_ok += 1
            else:
                excluded[res[1]] = res[2]; n_ex += 1
            if (k+1) % 200 == 0:
                ff.flush(); mf.flush()
                json.dump(excluded, open(EXCLUDED,'w'))
                print(f'{k+1}/{len(todo)} ok={n_ok} ex={n_ex}', flush=True)
    ff.close(); mf.close()
    json.dump(excluded, open(EXCLUDED,'w'), indent=0)
    print(f'DONE ok={n_ok} excluded={n_ex}', flush=True)

if __name__ == '__main__':
    main()
