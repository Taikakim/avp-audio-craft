# Owner: THE-FINN (created 2026-11-03) -- after moving a run under sa3_control_runs: update __MOVED_MAP.json by hand or with a re-scan, then run this with --apply to repoint symlinks and code paths. Dry run by default.
import os,re,json,sys,subprocess
R='/run/media/kim/Mantu/sa3_control_runs'; m=json.load(open(R+'/__MOVED_MAP.json')); apply='--apply' in sys.argv
names=sorted(m,key=len,reverse=True)
pat=re.compile(r'sa3_control_runs/('+'|'.join(re.escape(n) for n in names)+r')(?![A-Za-z0-9_.+=-])')
# 1. symlinks
fixed=broken=0
for root in (R,'/run/media/kim/Mantu/latch_sweep','/run/media/kim/Mantu/sa3_lora_runs','/home/kim/Projects/SAO/.render_root_aliases'):
    for dp,dn,fn in os.walk(root):
        if 'model_matrix' in dp: dn[:]=[]; continue
        for f in dn+fn:
            p=os.path.join(dp,f)
            if os.path.islink(p):
                t=os.readlink(p); n=pat.sub(lambda x:f'sa3_control_runs/{m[x.group(1)]}/{x.group(1)}',t)
                if n!=t:
                    fixed+=1
                    if apply: os.remove(p); os.symlink(n,p)
                elif not os.path.exists(p): broken+=1
print('symlinks repointed',fixed,'other broken (pre-existing)',broken)
# 2. code
S='/home/kim/Projects/SAO'
targets=[S+'/'+x for x in ('eval','control','latch','onnx','scripts','Misc','stable-audio-3/scripts','stable-audio-3/stable_audio_3','latent-forge/src','latent-forge/serve','RUNBOOK.md','lumi')]+['/home/kim/Projects/mir/plots','/home/kim/Projects/mir/src']+[os.path.join('/home/kim',f) for f in os.listdir('/home/kim') if f.startswith('build_') and f.endswith('.py')]+['/home/kim/.claude/skills']
EXT={'.py','.sh','.ts','.svelte','.mjs','.md','.yaml','.toml'}; SKIPD={'__pycache__','node_modules','musicology','top100_work','tests'}
changed={}
def scan(p):
    if os.path.splitext(p)[1] not in EXT and not (p.endswith('.json') and '/presets/' in p): return
    try:
        if os.path.getsize(p)>3e6: return
        s=open(p,encoding='utf-8').read()
    except Exception: return
    n=0
    def rep(x):
        nonlocal n; n+=1; return f'sa3_control_runs/{m[x.group(1)]}/{x.group(1)}'
    s2=pat.sub(rep,s)
    if n:
        changed[p]=n
        if apply:
            open(p,'w',encoding='utf-8').write(s2)
for t in targets:
    if os.path.isfile(t): scan(t); continue
    for dp,dn,fn in os.walk(t):
        dn[:]=[d for d in dn if d not in SKIPD and not d.endswith('venv')]
        for f in fn: scan(os.path.join(dp,f))
print('files changed',len(changed),'refs',sum(changed.values()))
json.dump(changed,open('/home/kim/sao_runs/june_prune/rewrite_files.json','w'),indent=0)
for p,n in sorted(changed.items(),key=lambda x:-x[1])[:12]: print(f' {n:3} {p.replace("/home/kim/Projects/","")}')
