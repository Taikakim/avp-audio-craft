# Owner: GHOST-NOTE (created 2026-10-16)
# Compares our ModularOptimizer NorMuon (whitening off, SF off, beta1 0.95, no nesterov) against /home/kim/Projects/NorMuon/normuon.py on identical gradients.
# Result 2026-10-16: update DIRECTION identical (cos 1.000 at every step/shape); our step norm is 4-8% larger (rows normalised to exactly unit norm vs the official keeping the NS5 output norm).
import sys, torch, math
sys.path.insert(0,'/home/kim/Projects/NorMuon'); sys.path.insert(0,'/home/kim/Projects/SAO/stable-audio-tools')
torch.manual_seed(0)
import importlib.util
spec=importlib.util.spec_from_file_location('normuon_ref','/home/kim/Projects/NorMuon/normuon.py'); R=importlib.util.module_from_spec(spec); spec.loader.exec_module(R)
from stable_audio_tools.training.modular_opt import ModularOptimizer, build_modular_param_groups
def run(shape, steps=30):
    W0=torch.randn(*shape)*0.05
    grads=[torch.randn(*shape)*(0.3+i%3)+0.2*torch.randn(*shape[:1],1) for i in range(steps)]  # row-scale heterogeneity
    # official
    p1=torch.nn.Parameter(W0.clone()); mom=torch.zeros_like(p1); sm=torch.zeros_like(p1[...,0:1]); ups=[]
    for g in grads:
        u=R.normuon_update(g.clone(), mom, sm, beta=0.95, beta2=0.95, ns_steps=5, nesterov=False); ups.append(u.clone())
    # ours: single spectral group, whitening none, no SF, no brake
    lin=torch.nn.Linear(shape[1],shape[0],bias=False); lin.weight.data=W0.clone()
    groups=build_modular_param_groups(lin, default_whitening='none', spectral_wd=0.0, spectral_all=True)
    opt=ModularOptimizer(groups, lr=1.0, normuon=True, schedule_free=False, warmup_steps=0, beta1=0.95, strict_group_lrs=False)
    mine=[]
    for g in grads:
        lin.weight.grad=g.clone(); before=lin.weight.data.clone(); opt.step(); mine.append((before-lin.weight.data).clone())
    for i in (0,1,5,29):
        a,b=ups[i],mine[i]
        print(shape,f"step{i}: ||official||={a.norm():.2f} ||ours||={b.norm():.2f} cos={torch.nn.functional.cosine_similarity(a.flatten(),b.flatten(),dim=0):.3f} rowrms-ratio-cv official={a.pow(2).mean(1).sqrt().std()/a.pow(2).mean(1).sqrt().mean():.3f} ours={b.pow(2).mean(1).sqrt().std()/b.pow(2).mean(1).sqrt().mean():.3f}")
for s in [(512,512),(1536,512),(256,512)]: run(s)
