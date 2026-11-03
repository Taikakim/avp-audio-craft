import numpy as np, glob, random, json, warnings; warnings.filterwarnings("ignore")
from scipy.signal import correlate
fs=glob.glob("/run/media/kim/Lehto/timeseries/*.TIMESERIES.npz"); random.seed(1); random.shuffle(fs); fs=fs[:500]
FEATS=['onset_envelope_drums_ts','onset_envelope_bass_ts','onset_envelope_other_ts','onset_envelope_vocals_ts',
 'beat_activation_ts','downbeat_activation_ts','rms_energy_bass_ts','rms_energy_body_ts','rms_energy_mid_ts','rms_energy_air_ts',
 'rms_drums_ts','rms_bass_ts','rms_other_ts','rms_vocals_ts','spectral_flatness_ts','spectral_flux_ts','spectral_skewness_ts','spectral_kurtosis_ts']
def lag_fft(a,b,ml=50):
    a=(a-a.mean())/(a.std()+1e-9); b=(b-b.mean())/(b.std()+1e-9); n=len(a)
    c=correlate(a,b,mode='full')/n; mid=n-1; w=c[mid-ml:mid+ml+1]
    i=int(np.argmax(np.abs(w))); return float(w[i]), (i-ml)
agg={f:{'pw':[],'mx':[],'lag':[]} for f in FEATS}; nt=0
for fp in fs:
    try: z=np.load(fp,allow_pickle=True); od=z['onset_envelope_ts'].astype(float)
    except: continue
    if od.std()<1e-9: continue
    nt+=1
    for f in FEATS:
        if f not in z.files: continue
        v=z[f].astype(float)
        if v.std()<1e-9: continue
        agg[f]['pw'].append(float(np.corrcoef(od,v)[0,1])); mx,lg=lag_fft(od,v); agg[f]['mx'].append(mx); agg[f]['lag'].append(lg*10)
res={f:{'pw':float(np.mean(a['pw'])),'mx':float(np.mean(a['mx'])),'lag':float(np.median(a['lag'])),'n':len(a['pw'])} for f,a in agg.items() if a['pw']}
json.dump({'n_tracks':nt,'feats':res}, open("/tmp/ts_xcorr.json","w"))
print(f"TS_XCORR_DONE n_tracks={nt}",flush=True)
for f,r in sorted(res.items(),key=lambda x:-abs(x[1]['mx'])):
    print(f"  {f:26}{r['pw']:>+7.2f}{r['mx']:>+7.2f}{r['lag']:>7.0f}ms  gain {abs(r['mx'])-abs(r['pw']):+.2f}",flush=True)
