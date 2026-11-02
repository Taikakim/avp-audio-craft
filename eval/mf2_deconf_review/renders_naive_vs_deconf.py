import json,os,numpy as np
A='/home/kim/evals_aac/mood_finegrained/';SP=os.environ.get('SP','/run/media/kim/Kosmos/captions/review_20261103')
raw=json.load(open(A+'raw_dsp_mood_cache.json'));ab=json.load(open(A+'audiobox_cache.json'));ins=json.load(open(A+'clip_inspect_data.json'));N=json.load(open(SP+'/naive_scores.json'));C=json.load(open(A+'deconf_targets.json'))['classes'];T=json.load(open(A+'deconf_targets.json'))['targets']
S=1102008041;MS=['base','adamw','goa','combo_fusion_goa'];G=[1024,2048,4096,8192];ix=C.index
f=lambda m,c:f'fine_{m}__{c}__s{S}.m4a'
# instrument check: does my CPU scorer reproduce the cached baseline?
for m in MS:
    a=np.array(N[f(m,'base')]);b=np.array(raw[f(m,'base')]['all_moods']);print('baseline reproduce',m,'max|diff| %.4f r %.4f'%(abs(a-b).max(),np.corrcoef(a,b)[0,1]))
def q(m,c):
    fn=f(m,c); return np.array(raw[fn]['all_moods']) if fn in raw else np.array(N[fn])
def cm(m,c,k='CE'): return ab.get(f(m,c),{}).get(k,float('nan'))
print('\nNAIVE vs DECONF, change from that models unguided clip, seed 1, one prompt')
for name,t in [('Melodic','melodic'),('Space','space'),('Dark','dark')]:
    print(f'\n-- target {name}: d[{t}] / d[melodic] / |d profile| / CE')
    for m in MS:
        b=q(m,'base')
        for pre in ['','Deconf_']:
            r=[q(m,f'{pre}{name}_g{g}') for g in G]
            print(f'  {m:17s}{pre or "naive":8s}',' '.join(f'{x[ix(t)]-b[ix(t)]:+.3f}' for x in r),'|',' '.join(f'{x[ix("melodic")]-b[ix("melodic")]:+.3f}' for x in r),'|',' '.join(f'{np.linalg.norm(x-b):.2f}' for x in r),'|',' '.join(f"{cm(m,f'{pre}{name}_g{g}'):.2f}" for g in G),' base CE %.2f'%cm(m,'base'))
# wins table
print('\nwin count deconf vs naive over 16 model x gain cells (one seed)')
for name,t in [('Melodic','melodic'),('Space','space'),('Dark','dark')]:
    p=d=0;pm=dm=0;n=0;sel=[];
    for m in MS:
        b=q(m,'base')
        for g in G:
            x=q(m,f'{name}_g{g}');y=q(m,f'Deconf_{name}_g{g}');n+=1
            d+=(y[ix(t)]-b[ix(t)])>(x[ix(t)]-b[ix(t)]);dm+=(y[ix('melodic')])>(x[ix('melodic')])
            sel.append(((y[ix(t)]-b[ix(t)])-(x[ix(t)]-b[ix(t)])))
    print(f' {name}: deconf hits own tag harder {d}/{n}, mean diff {np.mean(sel):+.3f}; keeps melodic higher {dm}/{n}')
# identity shift: target cosines
tv={k:np.array(v['vector']) for k,v in T.items()}
print('\ntarget nonzero count + top');
for k,v in tv.items(): print(' ',k,'pos',(v>0.02).sum(),'neg',(v<-0.02).sum(),'top',[(C[i],round(float(v[i]),3)) for i in np.argsort(v)[::-1][:5]],'melodic %.3f dark %.3f'%(v[ix('melodic')],v[ix('dark')]))
# key claims
print('\nkey at each gain');
for m,c in [('base','Dark'),('base','Deconf_Dark'),('adamw','Dark'),('adamw','Deconf_Uplifting'),('adamw','Deconf_AntiDark'),('goa','Deconf_Dark')]:
    print(' ',m,c,' base',ins[f(m,'base')]['key'],ins[f(m,'base')]['scale'],[ins[f(m,f'{c}_g{g}')]['key']+' '+ins[f(m,f'{c}_g{g}')]['scale'][:3] for g in G])
print('\nspread of CE across all 4 models unguided',[cm(m,'base') for m in MS],'; CE sd over all clips %.2f'%np.nanstd([v['CE'] for v in ab.values()]))
