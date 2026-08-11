#!/usr/bin/env python
"""post_sweep.py — after the layer x t sweep: build the table, pick the best
cell (by VAL bacc; test reported), run the conditional stages of the design:
  * best test bacc < 0.25  -> sequence readout (GRU) at the best cell
  * best test bacc > 0.40  -> y14 head at the best cell + acceptance retest
Copies the best head into the repo dir, writes summary.json.
GPU stages are subprocesses of this process — run under the same .gpu.lock.
"""
import json, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ACTS = '/run/media/kim/Mantu/sa3_lora_runs/head_a_ceiling_act'
RESULTS = os.path.join(HERE, 'results.json')
PY = '/home/kim/Projects/SAO/.venv/bin/python'


def main():
    runs = json.load(open(RESULTS))['runs']
    cells = [r for r in runs if r.get('kind') == 'act' and r['target'] == 'y8']
    if not cells:
        sys.exit('no act cells in results.json')

    best = max(cells, key=lambda r: r['val_bacc'])
    tb = best['test_all']['balanced_acc']
    print(f"BEST cell: {best['arch']} t={best['t']} L{best['layer']} "
          f"val {best['val_bacc']} test bacc {tb:.4f} "
          f"F1 {best['test_all']['macro_f1']:.4f}")

    # table: per (layer, t) max over archs of test bacc
    table = {}
    for r in cells:
        k = (r['layer'], r['t'])
        v = dict(arch=r['arch'],
                 bacc=round(r['test_all']['balanced_acc'], 4),
                 f1=round(r['test_all']['macro_f1'], 4),
                 val_bacc=r['val_bacc'])
        if k not in table or v['val_bacc'] > table[k]['val_bacc']:
            table[k] = v

    summary = dict(best=dict(arch=best['arch'], layer=best['layer'],
                             t=best['t'], val_bacc=best['val_bacc'],
                             test_bacc=round(tb, 4),
                             test_macro_f1=round(best['test_all']['macro_f1'], 4),
                             per_class_f1=best['test_all']['per_class_f1'],
                             ckpt=best['ckpt']),
                   table={f"L{k[0]:02d}_t{k[1]}": v for k, v in table.items()})

    src = os.path.join(ACTS, best['ckpt'])
    dst = os.path.join(HERE, os.path.basename(best['ckpt']).replace(
        'act_', 'best_act_'))
    shutil.copy2(src, dst)
    summary['best']['ckpt_repo'] = os.path.basename(dst)

    if tb < 0.25:
        print('[cond] ceiling near-chance -> sequence readout (GRU)')
        rc = subprocess.call([PY, os.path.join(HERE, 'seq_readout.py'),
                              '--t', str(best['t']),
                              '--layer', str(best['layer'])])
        summary['seq_readout_rc'] = rc
        if rc == 0:
            runs2 = json.load(open(RESULTS))['runs']
            seq = [r for r in runs2 if r.get('kind') == 'act_seq']
            if seq:
                s = seq[-1]
                summary['seq_readout'] = dict(
                    bacc=round(s['test_all']['balanced_acc'], 4),
                    f1=round(s['test_all']['macro_f1'], 4))
    elif tb > 0.40:
        print('[cond] ceiling usable -> y14 head + acceptance retest')
        rc = subprocess.call([PY, os.path.join(HERE, 'train_readout_act.py'),
                              '--t', str(best['t']),
                              '--layer', str(best['layer']),
                              '--target', 'y14', '--archs', best['arch'],
                              '--epochs', '25', '--patience', '6'])
        summary['y14_rc'] = rc
        if rc == 0:
            ck14 = os.path.join(
                ACTS, 'ckpts',
                f"act_{best['arch']}_t{int(round(best['t']*100)):03d}"
                f"_L{best['layer']:02d}_y14.pt")
            rc2 = subprocess.call([PY, os.path.join(HERE, 'eval_acceptance_act.py'),
                                   '--ckpt', ck14])
            summary['acceptance_rc'] = rc2
            if rc2 == 0 and os.path.exists(os.path.join(HERE, 'acceptance.json')):
                acc = json.load(open(os.path.join(HERE, 'acceptance.json')))
                summary['acceptance'] = dict(r=acc['pearson_r'],
                                             n_both=acc['n_both'],
                                             no_lead_agreement=acc['no_lead_agreement'])

    json.dump(summary, open(os.path.join(HERE, 'summary.json'), 'w'), indent=1)
    print('summary ->', os.path.join(HERE, 'summary.json'))


if __name__ == '__main__':
    main()
