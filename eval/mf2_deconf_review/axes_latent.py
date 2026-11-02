import os
src_code=open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'axes.py')).read().split('# single-word sizes')[0]
exec(src_code)
print('--- latent-based reading')
LAT=[];
rng2=np.random.default_rng(1)
crop_of={}
for mp in sorted(glob.glob(f"{MOOD_NPY_DIR}/*.npy")):
    cid=os.path.splitext(os.path.basename(mp))[0];jp=f"{LAT_JSON_DIR}/{cid}.json"
    if not os.path.exists(jp):continue
    st=json.load(open(jp)).get('source_track','')
    if st in src: crop_of.setdefault(st,cid)
miss=0
for t in tn:
    a=np.load(f"{LAT_JSON_DIR}/{crop_of[t]}.npy",mmap_mode='r');a=np.asarray(a).astype(np.float32)
    if a.shape[0]!=256: a=a.T
    LAT.append(np.r_[a.mean(1),a.std(1)])
X=np.array(LAT);X=(X-X.mean(0))/X.std(0);print('latent feats',X.shape)
def cvr(y,X,alpha=2000):
    s=np.zeros(len(y))
    for a,b in GroupKFold(5).split(X,y,gi): s[b]=Ridge(alpha=alpha).fit(X[a],y[a]).predict(X[b])
    return r2_score(y,s),np.corrcoef(y,s)[0,1]
for tag in ['calm','dark','melodic','energetic']:
    print('known-pos: Essentia %-10s from latent R2 %.3f r %.3f'%(tag,*cvr(Z[:,ESS_CLASSES.index(tag)],X)))
print('known-neg: shuffled R2 %.3f r %.3f'%cvr(rng.permutation(Z[:,ESS_CLASSES.index('calm')]),X))
for k in range(8):
    print('axis%d %-44s latent R2 %+.3f r %.3f'%(k+1,TOP[k],*cvr(ax[:,k],X)))
from sklearn.metrics import roc_auc_score
from sklearn.linear_model import LogisticRegression
for w in ['meditative','contemplative','sci-fi','futuristic','robotic','mantra-like','ritualistic','searching','dark','uplifting','euphoric','otherworldly']:
    y=Tm[:,terms.index(w)]>0
    if y.sum()<25: print(w,'too few',y.sum());continue
    s=np.zeros(len(y));s2=np.zeros(len(y))
    for a,b in GroupKFold(5).split(X,y,gi):
        s[b]=LogisticRegression(C=0.002,max_iter=300).fit(X[a],y[a]).decision_function(X[b]);s2[b]=LogisticRegression(C=0.05,max_iter=300).fit(Z[a],y[a]).decision_function(Z[b])
    print('  word %-14s n %4d  AUC latent %.3f  AUC 56 tags %.3f'%(w,y.sum(),roc_auc_score(y,s),roc_auc_score(y,s2)))
