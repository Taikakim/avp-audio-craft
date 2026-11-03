# Owner: THE-FINN (created 2026-11-03) -- verify torch-free steered renders with real torch: gradients on real sampling states, head reading of final latents.
import json, importlib.util as iu, numpy as np, torch, torch.nn.functional as F, wave
s=iu.spec_from_file_location('latch_std','/home/kim/Projects/SAO/stable-audio-3/stable_audio_3/models/latch.py'); L=iu.module_from_spec(s); s.loader.exec_module(L)
H='/home/kim/Projects/SAO/stable-audio-3/latch_weights_sa3_medium/latch_sa3_rms_energy_bass_best.pt'
h=L.load_latch_from_checkpoint(H,'cpu').eval().float(); M,S=-21.92660903930664,14.534050941467285
q=np.load('renders/grad_queries.npz'); n=len([k for k in q.files if k.startswith('tg')])
cs=[];re=[]
for i in range(n):
    x=torch.from_numpy(q[f'x{i}']).requires_grad_(True); t=torch.tensor([float(q[f't{i}'])]); tg=torch.from_numpy(q[f'tg{i}'])
    g,=torch.autograd.grad(F.smooth_l1_loss(h(x,t),tg,beta=1.0),x); o=torch.from_numpy(q[f'g{i}'])
    cs.append(F.cosine_similarity(g.flatten(),o.flatten(),dim=0).item()); re.append(((g-o).norm()/g.norm()).item())
print(f'real-state gradients: {n} queries, min cos {min(cs):.7f}, max rel err {max(re):.2e}, t values {sorted({round(float(q[f"t{i}"]),3) for i in range(n)})}')
R=json.load(open('renders/results.json'))
print(f'{"render":19}{"target":>7}{"head read dB":>13}{"bass dB":>9}')
for r in R:
    z=torch.from_numpy(np.load(f"renders/{r['name']}.z0.npy"))
    with torch.no_grad(): p=h(z,torch.tensor([0.0])).mean().item()*S+M
    bass=r['bass_share_db']+r['rms_db']
    print(f"{r['name']:19}{str(r['target_db']):>7}{p:13.1f}{bass:9.2f}"); r['head_read_db']=p; r['bass_db']=bass
json.dump(R,open('renders/results.json','w'),indent=1)
