import glob,json,os,re,numpy as np,collections
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold
from sklearn.metrics import r2_score
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'antigravity_crossmodal_mf2_essentia.py')).read().split('# 1. Load goa_src_captions')[0].split('import glob, json, os, re')[1].split('\n',1)[1]) # constants: DISC_TERMS, paths, ESS_CLASSES
src={}
hs=collections.Counter()
for p in sorted(glob.glob(f"{BASE_CAP}/goa_src_captions/json/*.json")):
    d=json.load(open(p));t=d.get('captions',{}).get('full','')
    if t:
        src[os.path.basename(os.path.dirname(d['rel']))]=t.lower();hs[d.get('genre_hint_source')]+=1
print('n',len(src),'hint source',hs.most_common(3))
txt=list(src.values());names=list(src)
T=np.array([[bool(re.search(rf"\b{re.escape(w)}\b",t)) for w in DISC_TERMS] for t in txt],float)
keep=T.sum(0)>=20;terms=[w for w,k in zip(DISC_TERMS,keep) if k];T=T[:,keep];print('terms',len(terms),'mean terms per caption %.1f'%T.sum(1).mean())
for w in ['searching','dark','raw','uplifting','hypnotic','mantra-like','sci-fi','alien']:
    if w in terms: print(' rate',w,round(T[:,terms.index(w)].mean()*100,1))
def vm(Phi,q=100,tol=1e-6):
    p,k=Phi.shape;R=np.eye(k);d=0
    for _ in range(q):
        L=Phi@R;u,s,vh=np.linalg.svd(Phi.T@(L**3-(1/p)*L@np.diag(np.diag(L.T@L))));R=u@vh;o=d;d=s.sum()
        if o and d/o<1+tol:break
    return Phi@R
def axes(M,K=8):
    C=np.corrcoef(M,rowvar=False);C=np.nan_to_num(C);e,v=np.linalg.eigh(C);o=np.argsort(e)[::-1];return vm(v[:,o[:K]]*np.sqrt(np.maximum(e[o[:K]],0))),e[o]
L,e=axes(T)
print('eig top12',np.round(e[:12],2),'| var explained by 8: %.1f%% of %d terms'%(e[:8].sum()/e.sum()*100,len(terms)),'| eig>1 count',(e>1).sum())
# parallel analysis
rng=np.random.default_rng(0);Ts=np.column_stack([rng.permutation(T[:,j]) for j in range(T.shape[1])]);es=np.linalg.eigvalsh(np.corrcoef(Ts,rowvar=False))[::-1];print('parallel analysis: random eig1 %.2f; real eigs above it: %d'%(es[0],(e>es[0]).sum()))
# split half by ALBUM-agnostic random: tucker congruence, best match
from scipy.optimize import linear_sum_assignment
res=[]
for s in range(10):
    idx=rng.permutation(len(T));a,b=idx[:len(T)//2],idx[len(T)//2:]
    A,_=axes(T[a]);B,_=axes(T[b]);c=np.abs((A/np.linalg.norm(A,axis=0)).T@(B/np.linalg.norm(B,axis=0)));r,cc=linear_sum_assignment(-c);res.append(np.sort(c[r,cc]))
print('split-half congruence per axis, sorted, mean of 10 splits',np.round(np.mean(res,0),2))
ref=L/np.linalg.norm(L,axis=0)
# 3. does each axis exist in the audio? track-level, group by label-ish folder prefix, predict axis score from 56-d mood and vs shuffle
F=np.load if 0 else None
tr=collections.defaultdict(list)
for mp in sorted(glob.glob(f"{MOOD_NPY_DIR}/*.npy")):
    cid=os.path.splitext(os.path.basename(mp))[0];jp=f"{LAT_JSON_DIR}/{cid}.json"
    if not os.path.exists(jp):continue
    st=json.load(open(jp)).get('source_track','')
    if st in src: tr[st].append(np.load(mp,mmap_mode='r').mean(1))
tn=sorted(tr);print('tracks with crops',len(tn),'crops',sum(map(len,tr.values())))
P=np.clip(np.array([np.mean(tr[t],0) for t in tn]),1e-6,1-1e-6);Z=np.log(P/(1-P));Z=(Z-Z.mean(0))/Z.std(0)
pos={n:i for i,n in enumerate(names)};Tm=T[[pos[t] for t in tn]];Tstd=(Tm-T.mean(0))/(T.std(0)+1e-8)
ax=np.linalg.lstsq(L,Tstd.T,rcond=None)[0].T   # factor scores
grp=np.array([re.split(r'\s+-\s+',t)[0].lower() for t in tn]);ug,gi=np.unique(grp,return_inverse=True);print('artists',len(ug))
TOP=[', '.join(terms[i] for i in np.argsort(-np.abs(L[:,k]))[:3]) for k in range(8)]
for k in range(8):
    y=ax[:,k];s=np.zeros(len(y));sn=np.zeros(len(y));yn=rng.permutation(y)
    for a,b in GroupKFold(5).split(Z,y,gi):
        s[b]=Ridge(alpha=30).fit(Z[a],y[a]).predict(Z[b]);sn[b]=Ridge(alpha=30).fit(Z[a],yn[a]).predict(Z[b])
    print('axis%d %-44s R2 from 56 Essentia tags, artist-held-out %+.3f r %.3f | shuffled R2 %+.3f'%(k+1,TOP[k],r2_score(y,s),np.corrcoef(y,s)[0,1],r2_score(yn,sn)))
# single-word sizes, by track, cluster
def n_tr(w): return int(Tm[:,terms.index(w)].sum())
for w in ['meditative','contemplative','introspective','calm','melancholic','ethereal','sci-fi','alien','mantra-like','searching']:
    if w in terms:
        m=Tm[:,terms.index(w)]==1;d=[(Z[m].mean(0)-Z[~m].mean(0))[ESS_CLASSES.index(t)] for t in ['calm','relaxing','meditative','melancholic']]
        print('  %-14s tracks %4d artists %3d | delta sigma calm %+.2f relaxing %+.2f meditative %+.2f melancholic %+.2f'%(w,m.sum(),len(set(grp[m])),*d))
# mechanism claims by text
txtl=txt
sp=np.array([bool(re.search(r"\b(spoken|speech|monologue|vocal sample|narrat)",t)) for t in txtl]);ph=np.array([bool(re.search(r"\bphrygian\b",t)) for t in txtl])
ma=T[:,terms.index('mantra-like')]==1
print('mantra-like n %d: spoken-word rate %.1f%% (all %.1f%%), phrygian %.1f%% (all %.1f%%)'%(ma.sum(),sp[ma].mean()*100,sp.mean()*100,ph[ma].mean()*100,ph.mean()*100))
se=T[:,terms.index('searching')]==1;hd=np.array([bool(re.search(r"m7b5|half-dim|ø",t)) for t in txtl]);print('searching n %d: half-dim mention %.1f%% (all %.1f%%)'%(se.sum(),hd[se].mean()*100,hd.mean()*100))
up=T[:,terms.index('uplifting')]==1;mj=np.array([bool(re.search(r"\bm(?:in)?\b.*?maj7|oscillat",t)) for t in txtl]);print('uplifting n %d: major-colour/oscillates mention %.1f%% (all %.1f%%)'%(up.sum(),mj[up].mean()*100,mj.mean()*100))
