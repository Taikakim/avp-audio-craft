#!/usr/bin/env python
"""eval_acceptance_act.py — spec S3 acceptance (r > 0.7) for the ACTIVATION
readout: forward each hook-render z0 through medium-base DiT at the best
(t, layer), decode a directional contour stream with the y14 activation head,
correlate z0-side hook_melodic_ratio vs wav-side muscriptor (hook_renders.jsonl).

Reuses head_a_ceiling/eval_acceptance.py's decode_stream/stream_stats VERBATIM
(imported) and extract_acts.py's forward/hook conventions.

Run (SAO venv, GPU, under .gpu.lock):
  .venv/bin/python eval_acceptance_act.py --ckpt <y14 act head> [--out acceptance.json]
"""
import argparse, json, os, sys
os.environ.setdefault('FLASH_ATTENTION_TRITON_AMD_ENABLE', 'FALSE')
os.environ.setdefault('PYTORCH_TUNABLEOP_ENABLED', '0')
os.environ.setdefault('MIOPEN_FIND_MODE', '2')
import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
CEIL = os.path.join(os.path.dirname(HERE), 'head_a_ceiling')
sys.path.insert(0, CEIL)
sys.path.insert(0, os.path.dirname(CEIL))     # eval/musicology for hook_metric
sys.path.insert(0, HERE)
from eval_acceptance import decode_stream, stream_stats  # noqa: E402
from train_readout_act import ReadoutAct                  # noqa: E402
from extract_acts import get_blocks, EPS_SEED             # noqa: E402

RENDERS = '/home/kim/Projects/SAO/eval/hook_renders.jsonl'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ckpt', required=True)
    ap.add_argument('--out', default=os.path.join(HERE, 'acceptance.json'))
    args = ap.parse_args()
    dev = 'cuda'
    ck = torch.load(args.ckpt, map_location=dev, weights_only=False)
    names = ck['class_names']
    t_star, L_star = float(ck['t']), int(ck['layer'])
    head = ReadoutAct(ck['arch'], ck['n_cls']).to(dev).eval()
    head.load_state_dict(ck['model'])
    mu = torch.tensor(ck['norm_mu'], device=dev)[None, :, None]
    sd = torch.tensor(ck['norm_sd'], device=dev)[None, :, None]

    from stable_audio_3 import StableAudioModel
    model = StableAudioModel.from_pretrained('medium-base', device='cuda')
    cdm = model.model
    blocks = get_blocks(model)
    mdtype = next(model.model.model.parameters()).dtype

    grabbed = {}

    def hook(_m, _inp, out):
        o = out[0] if isinstance(out, tuple) else out
        grabbed['a'] = o

    h = blocks[L_star].register_forward_hook(hook)

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
            if z.ndim == 2:
                z = z[None]
            z = torch.tensor(z).float()
            T = z.shape[-1]
            prompt = ''
            mp = r['file'].replace('.wav', '.json')
            if os.path.exists(mp):
                try:
                    prompt = json.load(open(mp)).get('prompt', '')
                except Exception:
                    pass
            conditioning = [{'prompt': prompt,
                             'seconds_total': T * 4096.0 / 44100.0}]
            tensors = cdm.conditioner(conditioning, str(dev))
            tensors['inpaint_mask'] = [torch.zeros((1, 1, T), device=dev)]
            tensors['inpaint_masked_input'] = [torch.zeros_like(z).to(dev)]
            ci = cdm.get_conditioning_inputs(tensors)
            ci = {k: (v.type(mdtype) if torch.is_tensor(v) else v)
                  for k, v in ci.items()}
            g = torch.Generator(device='cpu').manual_seed(EPS_SEED)
            eps = torch.randn(z.shape, generator=g).to(dev, mdtype)
            zd = z.to(dev, mdtype)
            x_t = (1 - t_star) * zd + t_star * eps
            tt = torch.full((1,), t_star, device=dev, dtype=mdtype)
            grabbed.clear()
            cdm.model(x_t, tt, **ci)
            a = grabbed['a'][0, -T:, :].float()            # (T,1536)
            x = a.T[None]                                  # (1,1536,T)
            cls = head((x - mu) / sd).argmax(1)[0].cpu().numpy()
            slots, pitches = decode_stream(cls, names)
            st = stream_stats(slots, pitches)
            per_clip.append(dict(clip=r['clip'], wav_hmr=wav_hmr,
                                 wav_no_lead=wav_nolead,
                                 z0_no_lead=st['no_lead'],
                                 z0_n_lead=st['n_lead'],
                                 z0_hmr=st.get('hook_melodic_ratio'),
                                 rest_frac=float(np.mean(cls == 0))))
    h.remove()

    both = [(c['z0_hmr'], c['wav_hmr']) for c in per_clip
            if c['z0_hmr'] is not None and c['wav_hmr'] is not None]
    r_val = None
    if len(both) >= 3:
        a, b = np.array(both).T
        if a.std() > 1e-9 and b.std() > 1e-9:
            r_val = float(np.corrcoef(a, b)[0, 1])
    agree = [c for c in per_clip if c['wav_no_lead'] == c['z0_no_lead']]
    out = dict(ckpt=args.ckpt, t=t_star, layer=L_star,
               n_clips=len(per_clip), n_both=len(both), pearson_r=r_val,
               no_lead_agreement=(len(agree) / max(1, len(per_clip))),
               spec_bar='r > 0.7', per_clip=per_clip)
    json.dump(out, open(args.out, 'w'), indent=1)
    print(f'acceptance: n={len(per_clip)} both={len(both)} r={r_val} '
          f'no_lead_agree={out["no_lead_agreement"]:.2f} -> {args.out}')


if __name__ == '__main__':
    main()
    sys.stdout.flush()
    os._exit(0)      # skip ROCm/torch teardown (heap-corruption abort)
