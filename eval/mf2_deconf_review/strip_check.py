"""Does the audio back the merge's 'hallucinated euphoric' rule (eval/recover_mf2_lost_moods.py)? Proxy on MF2 full captions: among tracks
whose HINTED caption says euphoric/uplifting, compare those whose UNHINTED caption is dark-family with no euphoric/uplifting (would be stripped)
against the rest (kept). The merge itself works on Granite tags, so this approximates its rule, it does not replay it."""
import json,os,re,numpy as np
from sklearn.metrics import roc_auc_score as A
SP=os.environ.get('SP','/run/media/kim/Kosmos/captions/review_20261103');B="/run/media/kim/Kosmos/captions"
z=np.load(SP+'/arch_feats.npz');K=[str(k) for k in z['keys']];C=json.load(open('/home/kim/Projects/mir/models/essentia/mtg_jamendo_moodtheme-discogs-effnet-1.json'))['classes']
un=[json.load(open(f"{B}/goa_archive_captions/json/{k}.json"))['captions']['full'].lower() for k in K];hi=[json.load(open(f"{B}/goa_archive_captions_hinted/json/{k}.json"))['captions']['full'].lower() for k in K]
h=lambda T,r:np.array([bool(re.search(r,t)) for t in T])
pos=r"\b(euphoric|uplifting)\b";darkf=r"\b(dark|ominous|mechanical|melancholic|menacing|sinister|brooding)\b";osc=r"\b(oscillat\w+)\b"
hp=h(hi,pos);up=h(un,pos);ud=h(un,darkf);uo=h(un,osc)
strip=hp&ud&~up&~uo;keep=hp&~strip
print('hinted euphoric/uplifting',hp.sum(),'strip group',strip.sum(),'kept',keep.sum())
P=np.clip(z['mood'],1e-6,1-1e-6);Zm=np.log(P/(1-P));va=z['va']
rows=[('uplifting',Zm[:,C.index('uplifting')]),('happy',Zm[:,C.index('happy')]),('positive',Zm[:,C.index('positive')]),('dark',Zm[:,C.index('dark')]),('heavy',Zm[:,C.index('heavy')]),('valence_emomusic',va[:,2]),('arousal_emomusic',va[:,3]),('valence_deam',va[:,0])]
print('AUC strip group higher than kept group (0.5 = audio cannot tell them apart); mean std diff')
for n,s in rows:
    print(' %-18s AUC %.3f  d %+.3f'%(n,A(strip[strip|keep],s[strip|keep]),(s[strip].mean()-s[keep].mean())/s.std()))
print('\nreference: tracks whose UNHINTED says euphoric/uplifting vs unhinted dark-family only (same words, same meter)')
a=up&~ud;b=ud&~up
for n,s in rows:
    print(' %-18s AUC(dark-only higher) %.3f  d %+.3f'%(n,A(b[a|b],s[a|b]),(s[b].mean()-s[a].mean())/s.std()))
print('\nhinted positive word rate: strip group said-trance/goa in unhinted first sentence %.1f%%, said industrial/techno %.1f%%'%(np.mean([bool(re.search(r"\b(trance|psytrance|goa)\b",un[i].split('.')[0])) for i in np.where(strip)[0]])*100,np.mean([bool(re.search(r"\b(industrial|techno|ebm)\b",un[i].split('.')[0])) for i in np.where(strip)[0]])*100))
