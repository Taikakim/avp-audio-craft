import json,os,numpy as np
A='/home/kim/evals_aac/mood_finegrained/';SP=os.environ.get('SP','/run/media/kim/Kosmos/captions/review_20261103')
raw=json.load(open(A+'raw_dsp_mood_cache.json'));ab=json.load(open(A+'audiobox_cache.json'));ins=json.load(open(A+'clip_inspect_data.json'));N=json.load(open(SP+'/naive_scores.json'));C=json.load(open(A+'deconf_targets.json'))['classes']
S=1102008041;MS=['base','adamw','goa','combo_fusion_goa'];G=[1024,2048,4096,8192];ix=C.index
f=lambda m,c:f'fine_{m}__{c}__s{S}.m4a'
def q(m,c):
    fn=f(m,c); return np.array(raw[fn]['all_moods']) if fn in raw else np.array(N[fn])
ce=lambda m,c:ab[f(m,c)]['CE']
key=lambda m,c:(ins[f(m,c)]['key'],ins[f(m,c)]['scale'])
for k in ['Melodic','Space','Dark']:
    w=sum(ce(m,f'Deconf_{k}_g{g}')>ce(m,f'{k}_g{g}') for m in MS for g in G);d=np.mean([ce(m,f'Deconf_{k}_g{g}')-ce(m,f'{k}_g{g}') for m in MS for g in G])
    kn=sum(key(m,f'{k}_g{g}')==key(m,'base') for m in MS for g in G);kd=sum(key(m,f'Deconf_{k}_g{g}')==key(m,'base') for m in MS for g in G)
    print(k,'CE deconf>naive',w,'/16 mean %+.2f'%d,'| key kept naive',kn,'deconf',kd,'of 16')
for k in ['Uplifting','AntiDark']:
    print(k,'key kept',sum(key(m,f'Deconf_{k}_g{g}')==key(m,'base') for m in MS for g in G),'/16', 'CE-baseCE mean %+.2f'%np.mean([ce(m,f'Deconf_{k}_g{g}')-ce(m,'base') for m in MS for g in G]))
LIB=["advertising","commercial","corporate","background","documentary","movie","trailer","game","sport","christmas"]
print('\nlibrary floor: sum of 10 tags, change from baseline at each gain')
for m in MS:
    b=q(m,'base');lb=[ix(t) for t in LIB]
    print(' ',m,'base %.3f'%b[lb].sum(),'naive Space',' '.join(f"{q(m,f'Space_g{g}')[lb].sum()-b[lb].sum():+.3f}" for g in G),'| deconf Space',' '.join(f"{q(m,f'Deconf_Space_g{g}')[lb].sum()-b[lb].sum():+.3f}" for g in G),'| naive Melodic',' '.join(f"{q(m,f'Melodic_g{g}')[lb].sum()-b[lb].sum():+.3f}" for g in G),'| deconf Melodic',' '.join(f"{q(m,f'Deconf_Melodic_g{g}')[lb].sum()-b[lb].sum():+.3f}" for g in G))
print('\nmatched-effect: melodic loss when the own tag has moved about the same (Space, Dark), nearest gain pair within 0.015')
for k,t in [('Space','space'),('Dark','dark')]:
    for m in MS:
        b=q(m,'base');out=[]
        for g in G:
            for h in G:
                x=q(m,f'{k}_g{g}');y=q(m,f'Deconf_{k}_g{h}')
                dx,dy=x[ix(t)]-b[ix(t)],y[ix(t)]-b[ix(t)]
                if abs(dx-dy)<0.015 and min(dx,dy)>0.02: out.append(f'{dx:+.3f}/{dy:+.3f}:mel {x[ix("melodic")]-b[ix("melodic")]:+.3f} vs {y[ix("melodic")]-b[ix("melodic")]:+.3f}')
        print(' ',k,m,out or 'no matched pair')
print('peak check',[(k,v.get('peak')) for k,v in list(ins.items())[:1]], 'dead-like crest/rms sample', {k:ins[f('goa','Deconf_Dark_g8192')].get(k) for k in ['rms_db','crest','peak_db']})
