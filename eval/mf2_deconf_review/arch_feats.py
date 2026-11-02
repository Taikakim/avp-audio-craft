import glob,numpy as np,os,sys,json
from concurrent.futures import ThreadPoolExecutor
D='/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/goa_archive_features/npz/'
K=[os.path.basename(f)[:-5] for f in sorted(glob.glob('/run/media/kim/Kosmos/captions/goa_archive_captions/json/*.json'))]
def one(k):
    try:
        with np.load(D+k+'.npz',allow_pickle=False) as z:
            m=np.nanmean(z['f__effnet_moodtheme_ts'],0);g=np.nanmean(z['f__effnet_genre400_ts'],0);v=np.nanmean(z['f__va_deam_ts'],0);e=np.nanmean(z['f__va_emomusic_ts'],0)
            d=float(np.nanmean(z['f__dissonance_ts']));b=np.nanmean(z['f__bark_bands_ts'],0);ma=np.nanmean(z['f__maest_embed_ts'],0)
            return k,m,g,np.r_[v,e,d],b,ma
    except Exception as ex:
        return k,None,None,None,None,None
os.environ['OMP_NUM_THREADS']='1'
out=[]
with ThreadPoolExecutor(6) as ex:
    for i,r in enumerate(ex.map(one,K)):
        if r[1] is not None: out.append(r)
        if i%2000==0: print(i,len(out),flush=True)
np.savez(os.environ.get('SP','/run/media/kim/Kosmos/captions/review_20261103')+'/arch_feats.npz',keys=np.array([r[0] for r in out]),mood=np.stack([r[1] for r in out]),genre=np.stack([r[2] for r in out]),va=np.stack([r[3] for r in out]),bark=np.stack([r[4] for r in out]),maest=np.stack([r[5] for r in out]))
print('DONE',len(out))
