# Owner: THE-FINN (created 2026-11-03) -- dry run: which DoRA layers does upstream's resolver map? No patching.
import sys,mmap,collections
sys.path.insert(0,'.')
import lora_patch as lp, lora_core as lc
fb,ad=sys.argv[1:3]
atype,scaling,layers=lc.parse_adapter(ad)
f=open(fb,'rb'); buf=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ)
fcs=list(lp._fc_weight_buffers(buf)); m=lp._Mapper(fcs)
print('adapter',atype,scaling,'layers',len(layers),'graph FCs',len(fcs))
ok=0;bad=[]
for l,p in layers.items():
    want=(p['lora_B'].shape[0],p['lora_A'].shape[1])
    try: m.resolve(l,want); ok+=1
    except lc.LoraError as e: bad.append((l,want,str(e)[:110]))
print('resolved',ok,'unresolved',len(bad))
for b in bad: print(' ',b[0],b[1],'|',b[2])
print('graph FCs named cond_embed/global/timestep:')
for r in fcs:
    if any(s in r['name'] for s in ('to_cond_embed','to_global_embed','to_timestep_embed','seconds','project_in','project_out')): print('  ',r['shape'],r['name'][-70:])
