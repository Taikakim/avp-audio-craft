# Owner: THE-FINN (created 2026-11-03) -- capture a LatCH head's backward as an FX graph (AOTAutograd), export fw+bw to ONNX, verify with ORT. CPU only.
import sys, time, os, importlib.util as iu, torch, torch.nn.functional as F
from torch.func import functional_call
from functorch.compile import aot_function
torch.set_num_threads(12)
s=iu.spec_from_file_location('latch_std','/home/kim/Projects/SAO/stable-audio-3/stable_audio_3/models/latch.py'); L=iu.module_from_spec(s); s.loader.exec_module(L)
H=sys.argv[1]; T=int(sys.argv[2]) if len(sys.argv)>2 else 259; out_p=sys.argv[3]
head=L.load_latch_from_checkpoint(H,'cpu').eval().float()
head._time_cache=None
ref_head=L.load_latch_from_checkpoint(H,'cpu').eval().float()   # keeps the real SDPA, the reference for every check
class _F:   # math-form SDPA for capture only: its backward is plain ops, so it can reach ONNX
    def __getattr__(s,k): return getattr(F,k)
    @staticmethod
    def scaled_dot_product_attention(q,k,v,**kw):
        w=torch.matmul(q,k.transpose(-2,-1))/(q.size(-1)**0.5)
        return torch.matmul(torch.softmax(w,dim=-1),v)
for p in head.parameters(): p.requires_grad_(False)
names=[k for k,_ in head.named_parameters()]+[k for k,_ in head.named_buffers()]
vals=[v for _,v in head.named_parameters()]+[v for _,v in head.named_buffers()]
print('params+buffers',len(vals))
torch.manual_seed(0); x0=torch.randn(1,256,T); t0=torch.tensor([0.6])
with torch.no_grad(): out=head(x0,t0)
tgt0=torch.zeros_like(out)+0.5
LOSS=sys.argv[4] if len(sys.argv)>4 else 'mse'
def lossf(p,tg):
    if LOSS=='mse': return torch.mean((p-tg)**2)
    e=p-tg; ab=torch.sqrt(e*e+1e-24)   # smooth_l1 beta=1 in plain ops, matches F.smooth_l1_loss
    return torch.mean(torch.where(ab<1.0,0.5*e*e,ab-0.5))
def reflossf(p,tg): return F.mse_loss(p,tg) if LOSS=='mse' else F.smooth_l1_loss(p,tg,beta=1.0)
def refgrad(x,t,tg):
    L.F=F
    x=x.detach().requires_grad_(True); l=reflossf(ref_head(x,t),tg); g,=torch.autograd.grad(l,x); return g.detach(),l.detach()
def fn(plist,x,t,target):
    L.F=_F()
    return lossf(functional_call(head,dict(zip(names,plist)),(x,t)),target)
cap={}
def fw(gm,_): cap['fw']=gm; return gm
def bw(gm,_): cap['bw']=gm; return gm
f=aot_function(fn,fw_compiler=fw,bw_compiler=bw)
xx=x0.clone().requires_grad_(True); l=f(vals,xx,t0,tgt0); l.backward()
gr,lr=refgrad(x0,t0,tgt0)
print('AOT grad cos vs torch',F.cosine_similarity(xx.grad.flatten(),gr.flatten(),dim=0).item())
FW,BW=cap['fw'],cap['bw']
fw_in=[n for n in FW.graph.nodes if n.op=='placeholder']; bw_in=[n for n in BW.graph.nodes if n.op=='placeholder']
print('fw inputs',len(fw_in),'nodes',len(list(FW.graph.nodes)),'bw inputs',len(bw_in),'nodes',len(list(BW.graph.nodes)))
ops=lambda g:sorted({str(getattr(n.target,'__name__',n.target)) for n in g.graph.nodes if n.op=='call_function'})
print('bw ops',ops(BW))
class GradExport(torch.nn.Module):
    def __init__(s):
        super().__init__(); s.FW=FW; s.BW=BW
        for i,v in enumerate(vals): s.register_buffer(f'p{i}',v.clone(),persistent=True)
        s.n=len(vals)
    def forward(s,x,t,target):
        ps=[getattr(s,f'p{i}') for i in range(s.n)]
        r=s.FW(*ps,x,t,target)
        loss=r[0]; saved=r[1:]
        cot=torch.ones_like(loss)
        g=s.BW(*saved,cot)
        return g[s.n],loss   # grad w.r.t. x
m=GradExport().eval()
g1,l1=m(x0,t0,tgt0); print('wrapper cos',F.cosine_similarity(g1.flatten(),gr.flatten(),dim=0).item(),'loss',l1.item(),lr.item())
t=time.time()
torch.onnx.export(m,(x0,t0,tgt0),out_p,input_names=['x','t','target'],output_names=['grad','loss'],dynamo=True,opset_version=20,external_data=True,verbose=False)
print('exported',round(time.time()-t,1),'s; MB',round(sum(os.path.getsize(p) for p in (out_p,out_p+'.data') if os.path.exists(p))/1e6,1))
import onnxruntime as ort
so=ort.SessionOptions(); so.intra_op_num_threads=12
S=ort.InferenceSession(out_p,so,providers=['CPUExecutionProvider'])
print('inputs',[(i.name,i.shape) for i in S.get_inputs()])
for seed,tv in ((0,0.6),(1,0.2),(2,0.9),(3,0.05)):
    torch.manual_seed(seed); a=torch.randn(1,256,T); tt=torch.tensor([tv]); tg=torch.randn_like(out)*0.3
    gg,ll=refgrad(a,tt,tg)
    b=time.time(); go,lo=S.run(None,{'x':a.numpy(),'t':tt.numpy(),'target':tg.numpy()}); ms=(time.time()-b)*1000
    go=torch.from_numpy(go); print(f' seed {seed} t {tv}: cos {F.cosine_similarity(go.flatten(),gg.flatten(),dim=0).item():.8f} rel {((go-gg).norm()/gg.norm()).item():.2e} loss {float(lo):.6f} vs {ll.item():.6f} ort {ms:.0f} ms')
