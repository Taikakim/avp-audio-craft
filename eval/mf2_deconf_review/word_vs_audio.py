import json,os,re,glob,numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.metrics import roc_auc_score
SP=os.environ.get('SP','/run/media/kim/Kosmos/captions/review_20261103');B="/run/media/kim/Kosmos/captions"
z=np.load(SP+'/arch_feats.npz');keys=[str(k) for k in z['keys']];mood=z['mood'];genre=z['genre'];va=z['va'];bark=z['bark'];maest=z['maest']
C=json.load(open('/home/kim/Projects/mir/models/essentia/mtg_jamendo_moodtheme-discogs-effnet-1.json'))['classes'];G=json.load(open('/home/kim/Projects/mir/models/essentia/genre_discogs400-discogs-effnet-1.json'))['classes']
un=[];hi=[];rel=[];ok=[]
for i,k in enumerate(keys):
    try:
        a=json.load(open(f"{B}/goa_archive_captions/json/{k}.json"));b=json.load(open(f"{B}/goa_archive_captions_hinted/json/{k}.json"))
        x,y=a['captions']['full'].lower(),b['captions']['full'].lower()
        if x and y: un.append(x);hi.append(y);rel.append(a['rel']);ok.append(i)
    except Exception: pass
ok=np.array(ok);mood,genre,va,bark,maest=mood[ok],genre[ok],va[ok],bark[ok],maest[ok];n=len(ok);print('n',n)
album=np.array([os.path.dirname(r) for r in rel]);ua,gid=np.unique(album,return_inverse=True);print('albums',len(ua))
L=lambda p:np.log(np.clip(p,1e-6,1-1e-6)/(1-np.clip(p,1e-6,1-1e-6)))
Zm=L(mood);Zg=L(genre)
has=lambda T,w:np.array([bool(re.search(rf"\b{re.escape(w)}\b",t)) for t in T])
first=lambda T:[t.split('.')[0] for t in T]
fu=first(un)
ind=np.array([bool(re.search(r"\b(industrial|techno|ebm)\b",t)) for t in fu]);tra=np.array([bool(re.search(r"\b(trance|psytrance|goa)\b",t)) for t in fu])
def auc(y,s):
    return float('nan') if y.sum()<20 or (~y).sum()<20 else roc_auc_score(y,s)
# 0. instrument: known positives and known negative
amb=np.array([bool(re.search(r"\bambient\b",t)) for t in fu])
Gi={g:i for i,g in enumerate(G)}
gamb=[i for i,g in enumerate(G) if 'Ambient' in g and 'Electronic' in g];gind=[i for i,g in enumerate(G) if g.endswith('Industrial')];gpsy=[i for i,g in enumerate(G) if 'Psy-Trance' in g or 'Goa Trance' in g];gtrance=[i for i,g in enumerate(G) if g.endswith('---Trance')];gtech=[i for i,g in enumerate(G) if g.endswith('---Techno')]
print('genre idx',[G[i] for i in gamb+gind+gpsy+gtrance+gtech])
print('INSTRUMENT known-pos: unhinted first sentence "ambient" vs effnet ambient AUC %.3f; meditative tag %.3f'%(auc(amb,Zg[:,gamb].mean(1)),auc(amb,Zm[:,C.index('meditative')])))
print('INSTRUMENT known-neg: shuffled %.3f'%auc(np.random.default_rng(0).permutation(amb),Zg[:,gamb].mean(1)))
print('effnet top genre share on all tracks:',[(G[i],round(float((genre.argmax(1)==i).mean()*100),1)) for i in np.argsort(-np.bincount(genre.argmax(1),minlength=400))[:7]])
print('said industrial/techno/ebm: %.1f%%; said trance/goa %.1f%%; effnet audio says psy/goa or trance top %.1f%%, techno/industrial top %.1f%%'%(ind.mean()*100,tra.mean()*100,np.isin(genre.argmax(1),gpsy+gtrance).mean()*100,np.isin(genre.argmax(1),gtech+gind).mean()*100))
print('said-ind tracks whose effnet top is techno/industrial %.1f%%, psy/trance %.1f%%'%(np.isin(genre.argmax(1)[ind],gtech+gind).mean()*100,np.isin(genre.argmax(1)[ind],gpsy+gtrance).mean()*100))
print('AUC said-ind ~ effnet techno+industrial minus psy+trance: %.3f'%auc(ind,Zg[:,gtech+gind].mean(1)-Zg[:,gpsy+gtrance].mean(1)))
# 1. word vs matching tag
PAIR=[('dark','dark'),('uplifting','uplifting'),('euphoric','uplifting'),('melancholic','melancholic'),('meditative','meditative'),('contemplative','calm'),('ominous','dark'),('brooding','dark'),('aggressive','powerful'),('aggressive','heavy'),('gritty','heavy'),('raw','heavy'),('metallic','heavy'),('futuristic','space'),('dystopian','dark'),('unsettling','dark')]
print('\n1. WORD vs matching Essentia tag from the AUDIO, AUC (0.5 = no information)');print('%-14s %-11s %6s %6s %6s %6s | %s'%('word','tag','unhint','hinted','un|ind','un|trn','n_un n_hi'))
for w,t in PAIR:
    u,h=has(un,w),has(hi,w);s=Zm[:,C.index(t)]
    print('%-14s %-11s %6.3f %6.3f %6.3f %6.3f | %d %d'%(w,t,auc(u,s),auc(h,s),auc(u[ind&~tra],s[ind&~tra]),auc(u[tra&~ind],s[tra&~ind]),u.sum(),h.sum()))
# 1b. pooled dark term family, and valence/arousal
VA={'val_deam':va[:,0],'aro_deam':va[:,1],'val_emo':va[:,2],'aro_emo':va[:,3]}
print('\nDEAM/emomusic val/aro mean, sanity',{k:round(float(v.mean()),2) for k,v in VA.items()})
for w in ['dark','uplifting','euphoric','aggressive','contemplative','melancholic']:
    u,h=has(un,w),has(hi,w);print('  %-14s val un %.3f hi %.3f | aro un %.3f hi %.3f'%(w,auc(u,VA['val_emo']),auc(h,VA['val_emo']),auc(u,VA['aro_emo']),auc(h,VA['aro_emo'])))
# 2. held-out: how much of each word is readable from audio
Xm=(np.c_[Zm,va,bark]-np.c_[Zm,va,bark].mean(0))/np.c_[Zm,va,bark].std(0)
def cv(y,X,g=gid):
    if y.sum()<50: return float('nan')
    s=np.zeros(len(y))
    for a,b in GroupKFold(5).split(X,y,g):
        s[b]=LogisticRegression(max_iter=300,C=0.1).fit(X[a],y[a]).decision_function(X[b])
    return roc_auc_score(y,s)
print('\n2. HELD-OUT album-split AUC, audio mood+VA+bark -> word present');print('%-14s %6s %6s %8s'%('word','unhint','hinted','un|ind-only'))
for w in ['dark','aggressive','metallic','raw','gritty','dystopian','unsettling','ominous','brooding','futuristic','contemplative','meditative','searching','uplifting','euphoric','melancholic','hypnotic','driving']:
    u,h=has(un,w),has(hi,w);m=ind&~tra
    print('%-14s %6.3f %6.3f %8.3f'%(w,cv(u,Xm),cv(h,Xm),cv(u[m],Xm[m],gid[m])))
# 3. does the unhinted word add over the genre it named? regress effnet dark on all
print('\n3. OLS std effect on effnet tag, all three in the model')
for t,w in [('dark','dark'),('uplifting','uplifting'),('heavy','aggressive'),('melancholic','melancholic')]:
    y=(Zm[:,C.index(t)]-Zm[:,C.index(t)].mean())/Zm[:,C.index(t)].std()
    X=np.c_[np.ones(n),has(un,w),has(hi,w),ind,tra];b=np.linalg.lstsq(X,y,rcond=None)[0]
    print('  tag %-11s word %-12s un-word %+.3f hi-word %+.3f said-ind %+.3f said-trance %+.3f'%(t,w,b[1],b[2],b[3],b[4]))
np.savez(SP+'/h_masks.npz',ind=ind,tra=tra)
