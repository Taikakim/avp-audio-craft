import glob,json,os,re,collections,numpy as np
B="/run/media/kim/Kosmos/captions"
U={},{}
un={}
for p in glob.glob(f"{B}/goa_archive_captions/json/*.json"):
    d=json.load(open(p)); t=d.get('captions',{}).get('full','')
    if t: un[os.path.basename(p)]=(d.get('rel',''),t.lower())
hi={}
gh=collections.Counter()
for p in glob.glob(f"{B}/goa_archive_captions_hinted/json/*.json"):
    d=json.load(open(p)); t=d.get('captions',{}).get('full','')
    if t: hi[os.path.basename(p)]=(d.get('rel',''),t.lower()); gh[d.get('genre_hint','')[:160]]+=1
K=sorted(set(un)&set(hi)); print('un',len(un),'hi',len(hi),'pairs',len(K),'same rel',sum(un[k][0]==hi[k][0] for k in K))
print('distinct hints',len(gh),gh.most_common(2))
print('median chars un/hi',np.median([len(un[k][1]) for k in K]),np.median([len(hi[k][1]) for k in K]))
W=['hypnotic','psychedelic','driving','high-energy','relentless','evolving','immersive','dark','aggressive','metallic','raw','gritty','dystopian','unsettling','ominous','brooding','futuristic','contemplative','meditative','introspective','searching','uplifting','euphoric','melancholic','mystical','spiritual','industrial','techno','trance','goa','psytrance','psychedelic trance']
rx={w:re.compile(rf"\b{re.escape(w)}\b") for w in W}
F3=sorted(un)[:3000]
F3=[k for k in F3 if k in hi]
print('first-3000 pairs',len(F3),'random-ish? top dirs',collections.Counter(un[k][0].split('/')[0] for k in F3).most_common(3),'| all',collections.Counter(un[k][0].split('/')[0] for k in K).most_common(3))
print('%-20s %7s %7s %6s | %7s %7s (first3000)'%('word','un%','hi%','x','un3k','hi3k'))
R={}
for w in W:
    a=np.array([bool(rx[w].search(un[k][1])) for k in K]);b=np.array([bool(rx[w].search(hi[k][1])) for k in K]);R[w]=(a,b)
    a3=np.mean([bool(rx[w].search(un[k][1])) for k in F3])*100;b3=np.mean([bool(rx[w].search(hi[k][1])) for k in F3])*100
    print('%-20s %7.1f %7.1f %6.1f | %7.1f %7.1f'%(w,a.mean()*100,b.mean()*100,a.mean()/max(b.mean(),1e-4),a3,b3))
# what genre does the first sentence name
first=lambda t:t.split('.')[0]
gw=['industrial','techno','psytrance','goa','trance','ebm','electro','ambient','house','drum']
print('\nfirst sentence genre word rate (un / hi):')
for g in gw:
    r=re.compile(rf"\b{g}\b"); print(' ',g,round(np.mean([bool(r.search(first(un[k][1]))) for k in K])*100,1),round(np.mean([bool(r.search(first(hi[k][1]))) for k in K])*100,1))
# stereotype test: inside UNHINTED, rate of dark words conditional on the genre it said
ind=np.array([bool(re.search(r"\b(industrial|techno|ebm)\b",first(un[k][1]))) for k in K]); tr=np.array([bool(re.search(r"\b(trance|psytrance|goa)\b",first(un[k][1]))) for k in K])
print('\nunhinted: said industrial/techno/ebm n=%d, said trance/goa n=%d, both %d'%(ind.sum(),tr.sum(),(ind&tr).sum()))
for w in ['dark','aggressive','metallic','raw','gritty','dystopian','unsettling','ominous','brooding','futuristic','contemplative','uplifting','euphoric','melancholic','mystical']:
    a=R[w][0]; print('  %-14s | ind-only %5.1f%%  trance-only %5.1f%%  neither %5.1f%%'%(w,a[ind&~tr].mean()*100,a[tr&~ind].mean()*100 if (tr&~ind).sum() else 0,a[~tr&~ind].mean()*100))
# paired agreement: does a word in unhinted go with the word in hinted on the same track
print('\npaired: phi(unhinted word, hinted word) on same track')
for w in ['dark','aggressive','metallic','raw','uplifting','euphoric','melancholic','mystical','contemplative']:
    a,b=R[w]; print('  %-14s phi %.3f  n11 %d'%(w,np.corrcoef(a,b)[0,1],(a&b).sum()))
np.save(os.environ.get('SP','/run/media/kim/Kosmos/captions/review_20261103')+'/mf2_keys.npy',np.array(K))
json.dump({k:un[k][0] for k in K},open(os.environ.get('SP','/run/media/kim/Kosmos/captions/review_20261103')+'/mf2_rel.json','w'))
