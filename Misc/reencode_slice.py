import torch, numpy as np, json, os, soundfile as sf
from stable_audio_3 import AutoencoderModel
device=torch.device("cuda")
ae=AutoencoderModel.from_pretrained("same-l", device=str(device)); ae.autoencoder=ae.autoencoder.half()
man=json.load(open("/run/media/kim/Mantu/aug_validation/aug_manifest.json"))
OUT="/run/media/kim/Mantu/aug_validation_latents"; os.makedirs(OUT,exist_ok=True); ok=0
for e in man:
    try:
        audio,sr=sf.read(e['wav'],dtype='float32')
        if audio.ndim==1: audio=np.stack([audio,audio],1)
        a=torch.tensor(audio.T,dtype=torch.float32).unsqueeze(0).to(device).half()
        with torch.no_grad(): lat=ae.encode(a, ae.sample_rate)
        cid=os.path.basename(e['src'])[:-5]+"_aug"
        np.save(f"{OUT}/{cid}.npy", lat[0].cpu().numpy().astype(np.float16))
        src=json.load(open(e['src']))
        speed=(e['new_bpm']/e['orig_bpm']) if e['orig_bpm'] else 1.0
        if src.get('onset_density') is not None: src['onset_density']=round(src['onset_density']*speed,4)
        src['bpm_madmom']=e['new_bpm']; src['augmented']=True; src['aug_type']=e['type']; src['aug_semitones']=e['semitones']; src['aug_bpm_delta']=e['bpm_delta']
        json.dump(src, open(f"{OUT}/{cid}.json","w")); ok+=1
        if ok%25==0: print(f"{ok}/{len(man)}",flush=True)
    except Exception as ex: print("err",str(ex)[:80],flush=True)
print(f"REENCODE_DONE {ok}/{len(man)}",flush=True)
