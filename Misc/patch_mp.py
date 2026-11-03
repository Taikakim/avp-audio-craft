import json
RP='/home/kim/riffer-evals/run_purposes.json'
MP='/home/kim/riffer-evals/mp.html'
runs={
 "AdamW-20ep":{"run":"AdamW-20ep","optimizer":"AdamW","lr":"7.5e-5","scalar_field":"onset_density","epochs":"20ep · random-crop","purpose":"AdamW baseline to 20 epochs with full per-layer telemetry — the rich-matrix run we cross-correlate training signals against control quality."},
 "AdamW-first":{"run":"AdamW-first","optimizer":"AdamW","lr":"7.5e-5","scalar_field":"onset_density","epochs":"continuous crops","purpose":"Crop-mode ablation: fixed continuous crops instead of random — tests whether random-crop augmentation matters for control authority."},
 "AdamW-rand":{"run":"AdamW-rand","optimizer":"AdamW","lr":"7.5e-5","scalar_field":"onset_density","epochs":"random-crop","purpose":"AdamW random-crop baseline (the shorter sibling of AdamW-20ep) — the random-crop comparator."},
 "Fusion-40ep":{"run":"Fusion-40ep","optimizer":"Fusion (SF-NorMuon)","lr":"2e-5","scalar_field":"onset_density","epochs":"40ep","purpose":"The longer-Fusion 'vibe' favourite — 40 epochs of schedule-free NorMuon; by ear the preferred timbre/groove even where metrics tie."},
 "Fusion-rand":{"run":"Fusion-rand","optimizer":"Fusion (SF-NorMuon)","lr":"1e-4","scalar_field":"onset_density","epochs":"random-crop","purpose":"Fusion at higher LR (1e-4), random-crop — the optimizer/LR comparator to the AdamW runs."},
 "soup":{"run":"model soup","optimizer":"weight-averaged","lr":"—","scalar_field":"onset_density","epochs":"post-hoc","purpose":"Weight-averaged checkpoints: per-run schemes (expasc/exppeak/expdecay = checkpoint weighting) + cross-run interpolation (cross_NNAMM = NN% AdamW + MM% Fusion). Tests whether averaging beats the best single late checkpoint — ratio is in the set name."},
}
# 1) canonical store
rp=json.load(open(RP)); rp.update(runs); json.dump(rp,open(RP,'w'),indent=1,ensure_ascii=False)
# 2) patch mp.html
h=open(MP).read(); n=0
patches=[
 ('.hl{color:#5c5}</style>',
  '.hl{color:#5c5}#info{background:#11161c;border:1px solid #243;border-left:3px solid #5d9;padding:7px 11px;font-size:12px;margin:6px 0;max-width:780px}#info b{color:#9ec}#info .p{color:#9aa;margin-top:3px}</style>'),
 ('<div class=sc id=sc></div>','<div class=sc id=sc></div><div id=info></div>'),
 ('function el(i){return document.getElementById(i);}',
  'function el(i){return document.getElementById(i);}\nconst PURP='+json.dumps(runs,ensure_ascii=False)+';'),
 ("function up(){const s=D.sets[+el('set').value];",
  "function up(){const s=D.sets[+el('set').value];const P=PURP[s.run]||{};el('info').innerHTML=P.run?`<b>${P.run}</b> · ${P.optimizer} · lr ${P.lr} · ${P.scalar_field}${P.epochs?' · '+P.epochs:''}<div class=p>${P.purpose}</div>`:'';"),
]
for old,new in patches:
    c=h.count(old)
    if c!=1: print(f'WARN count={c}: {old[:55]}'); continue
    h=h.replace(old,new); n+=1
open(MP,'w').write(h)
print(f'{n}/{len(patches)} mp.html patches applied; run_purposes now has {len(rp)} keys')
