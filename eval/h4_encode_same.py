"""Encode an H4 ladder file's audio with SAME (CPU) -> per-frame latents next to it (SA3 venv).

Input: any stage-1 npz with `audio` [N, samples] float16 mono and `sample_rate` (ladders_v2.npz, ladders_v2c.npz).
Out: <stem>.latents_same_s.npz with z [N, 256, T] float16 in the SAME row order. Resumable: encoded shards are
kept in <stem>.same_s_parts/ and skipped on restart (a 24k-render file takes about an hour on CPU).
Run: SA3_DISABLE_FLASH_ATTN=1 SAO/.venv/bin/python eval/h4_encode_same.py <file.npz> [--model same-s]
"""
import argparse
import os
import time

os.environ.setdefault("OMP_NUM_THREADS", "8")
import numpy as np
import torch


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("npz")
    ap.add_argument("--model", default="same-s")
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--shard", type=int, default=1024)
    ap.add_argument("--device", default="cpu", help="cuda:0 once the GPU is free (minutes instead of an hour)")
    a = ap.parse_args()
    torch.set_num_threads(int(os.environ["OMP_NUM_THREADS"]))
    stem = a.npz[:-4]
    tag = a.model.replace("-", "_")
    parts = f"{stem}.{tag}_parts"
    os.makedirs(parts, exist_ok=True)
    d = np.load(a.npz, mmap_mode="r")
    audio, sr, n = d["audio"], int(d["sample_rate"]), len(d["audio"])
    from stable_audio_3 import AutoencoderModel
    ae = AutoencoderModel.from_pretrained(a.model, device=a.device)
    t0 = time.time()
    for s0 in range(0, n, a.shard):
        p = f"{parts}/{s0:07d}.npy"
        if os.path.exists(p):
            continue
        zs = []
        for s in range(s0, min(n, s0 + a.shard), a.batch):
            x = torch.from_numpy(np.asarray(audio[s:min(s + a.batch, s0 + a.shard, n)], dtype=np.float32))
            zs.append(ae.encode(torch.stack([x, x], 1).to(a.device), sr).float().cpu().numpy().astype(np.float16))
        np.save(p + ".tmp.npy", np.concatenate(zs))
        os.replace(p + ".tmp.npy", p)
        done = min(n, s0 + a.shard)
        print(f"  {done}/{n}  {time.time() - t0:.0f}s", flush=True)
    z = np.concatenate([np.load(f"{parts}/{s0:07d}.npy") for s0 in range(0, n, a.shard)])
    assert len(z) == n, (len(z), n)
    np.savez(f"{stem}.latents_{tag}.npz", z=z)
    print(f"wrote {stem}.latents_{tag}.npz {z.shape}")


if __name__ == "__main__":
    main()
