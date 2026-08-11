#!/usr/bin/env python
"""eval_acceptance.py — Head A use-case #1 acceptance test (spec S3: r > 0.7).

Apply the clean DIRECTIONAL readout to render z0s that already carry wav-side
muscriptor hook stats (eval/hook_renders.jsonl), decode a per-frame contour
stream, mine hook_metric-style contour grams on it, and correlate z0-side vs
wav-side hook_melodic_ratio across clips (+ no-lead agreement).

Frame ~ 16th-slot approximation: SAME frame 92.9 ms vs corpus 16th ~103-110 ms;
each non-rest frame is treated as one slot entry, phrase gap = 3 frames —
mirrors phase1/phase3 semantics.

Run: /home/kim/Projects/SAO/.venv/bin/python eval_acceptance.py [--ckpt PATH]
"""
import argparse, json, os, sys
os.environ.setdefault('FLASH_ATTENTION_TRITON_AMD_ENABLE', 'FALSE')
import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
from train_readout import Readout                     # noqa: E402
import hook_metric as HM                              # noqa: E402

RENDERS = '/home/kim/Projects/SAO/eval/hook_renders.jsonl'
MIN_LEAD = HM.MIN_LEAD_NOTES


def decode_stream(cls_seq, names):
    """Frame classes -> (slots, pitches). New pitch at each move-run START;
    within-run continuation frames sustain (interval 0), pedal sustains,
    rest emits nothing."""
    slots, pitches = [], []
    p = 72
    prev = 0  # rest
    for f, c in enumerate(cls_seq):
        name = names[c]
        if name == 'rest':
            prev = c
            continue
        if name != 'pedal' and c != prev:
            p += int(name)          # names like '+7' / '-2'
        slots.append(f)
        pitches.append(p)
        prev = c
    return slots, pitches


def stream_stats(slots, pitches):
    n_lead = len(slots)
    if n_lead < MIN_LEAD:
        return dict(no_lead=True, n_lead=n_lead)
    lt = np.array(slots)
    brk = np.where(np.diff(lt) >= HM.PHRASE_GAP_SLOTS)[0]
    bounds = np.concatenate([[0], brk + 1, [len(lt)]]).astype(int).tolist()
    c_gram, c_cnt, c_tot, c_dist, _ = HM._best46(slots, pitches, bounds,
                                                 HM.contour_grams_of)
    return dict(
        no_lead=False, n_lead=n_lead,
        hook_melodic_ratio=(c_cnt * (len(c_gram) + 1) / max(1, n_lead))
                           if c_gram else 0.0,
        hook_melodic_gram=list(c_gram) if c_gram else None,
        contour_compression=(c_dist / c_tot) if c_tot >= HM.HOOK_MIN_GRAMS else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ckpt', default=os.path.join(HERE, 'readout_mlp_ctx2_y14.pt'))
    ap.add_argument('--out', default=os.path.join(HERE, 'acceptance.json'))
    args = ap.parse_args()
    dev = 'cuda' if torch.cuda.is_available() else 'cpu'
    ck = torch.load(args.ckpt, map_location=dev, weights_only=False)
    names = ck['class_names']
    model = Readout(ck['arch'], ck['ctx'], ck['n_cls'],
                    hidden=ck.get('hidden', 512),
                    t_cond=ck['t_conditioned']).to(dev).eval()
    model.load_state_dict(ck['model'])
    mu = torch.tensor(ck['norm_mu'], device=dev)[None, :, None]
    sd = torch.tensor(ck['norm_sd'], device=dev)[None, :, None]

    rows = [json.loads(l) for l in open(RENDERS)]
    per_clip = []
    with torch.no_grad():
        for r in rows:
            if not r.get('file'):
                continue
            z0p = r['file'].replace('.wav', '.z0.npy')
            if not os.path.exists(z0p):
                continue
            wav_hmr = r.get('hook_melodic_ratio')
            wav_nolead = bool(r.get('no_lead', False))
            if wav_hmr is None and not wav_nolead:
                continue
            z = np.load(z0p)
            if z.ndim == 3:
                z = z[0]
            x = torch.from_numpy(z.astype(np.float32))[None].to(dev)
            x = (x - mu) / sd
            cls = model(x).argmax(1)[0].cpu().numpy()
            slots, pitches = decode_stream(cls, names)
            st = stream_stats(slots, pitches)
            per_clip.append(dict(clip=r['clip'], wav_hmr=wav_hmr,
                                 wav_no_lead=wav_nolead,
                                 z0_no_lead=st['no_lead'],
                                 z0_n_lead=st['n_lead'],
                                 z0_hmr=st.get('hook_melodic_ratio'),
                                 z0_gram=st.get('hook_melodic_gram'),
                                 rest_frac=float(np.mean(cls == 0))))

    both = [(c['z0_hmr'], c['wav_hmr']) for c in per_clip
            if c['z0_hmr'] is not None and c['wav_hmr'] is not None]
    a = np.array(both, float)
    from scipy import stats as SS
    pear = SS.pearsonr(a[:, 0], a[:, 1]) if len(a) > 2 else (np.nan, np.nan)
    spear = SS.spearmanr(a[:, 0], a[:, 1]) if len(a) > 2 else (np.nan, np.nan)
    nl = [(c['z0_no_lead'], c['wav_no_lead']) for c in per_clip]
    nl = np.array(nl, bool)
    agree = float((nl[:, 0] == nl[:, 1]).mean())
    tp = int((nl[:, 0] & nl[:, 1]).sum()); tn = int((~nl[:, 0] & ~nl[:, 1]).sum())
    fp = int((nl[:, 0] & ~nl[:, 1]).sum()); fn = int((~nl[:, 0] & nl[:, 1]).sum())
    out = dict(ckpt=os.path.basename(args.ckpt), n_clips=len(per_clip),
               n_hmr_pairs=len(a),
               pearson_r=round(float(pear[0]), 4), pearson_p=float(pear[1]),
               spearman_rho=round(float(spear[0]), 4), spearman_p=float(spear[1]),
               no_lead_agreement=round(agree, 4),
               no_lead_confusion=dict(tp=tp, tn=tn, fp=fp, fn=fn),
               per_clip=per_clip)
    json.dump(out, open(args.out, 'w'), indent=1)
    print(f'n={len(per_clip)} hmr-pairs={len(a)} pearson r={pear[0]:.4f} '
          f'spearman rho={spear[0]:.4f} no-lead agree={agree:.3f} '
          f'(tp{tp} tn{tn} fp{fp} fn{fn})')


if __name__ == '__main__':
    main()
