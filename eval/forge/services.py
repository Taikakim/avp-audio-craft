"""Server-bound helpers that touch the resident model or its config. Kept out of the pure modules."""
from __future__ import annotations  # `-> torch.Tensor` must not be evaluated when torch is absent

import hashlib
import os
from pathlib import Path

import numpy as np
import soundfile as sf
try:  # torch only matters for the methods that touch the resident model; a CPU-only box (cloud
    import torch  # skeleton session, CI) can still import this module and exercise the routes.
except ImportError:  # pragma: no cover
    torch = None

from . import refs
from .contract import HOP


class Services:
    def __init__(self, srv, paths_fn):
        self.srv = srv
        self._paths = paths_fn

    def latent_dir(self):
        d = (self.srv.PLAYER_CFG or {}).get("latent_dir") or ""
        return Path(d) if d else None

    def ref_context(self) -> refs.RefContext:
        p = self._paths()
        ld = self.latent_dir()
        roots = {"renders": Path(self.srv.OUT_DIR), "uploads": p.uploads}
        if ld is not None:
            roots["crops"] = ld
        return refs.RefContext(out_dir=Path(self.srv.OUT_DIR), uploads=p.uploads, latent_dir=ld,
                               decode_crop=self.decode_crop, roots=roots)

    def resolve_audio(self, ref) -> Path:
        return refs.resolve_audio(ref, self.ref_context())

    def decode_crop(self, crop_id) -> Path:
        out = self._paths().cache_dir("decode") / f"{refs.check_crop_id(crop_id)}.wav"
        if out.exists():
            return out
        srv = self.srv
        arr = srv._player_latent(crop_id)
        meta = srv._player_meta(crop_id) if (srv._player_latent_dir() / f"{crop_id}.json").exists() else None
        with srv.GPU_LOCK:
            audio = srv._player_decode(arr)
        audio = srv._player_trim(audio, meta, arr.shape[1])
        tmp = out.with_name(out.stem + ".part.wav")
        sf.write(tmp, np.ascontiguousarray(audio.T), srv.SR, subtype="FLOAT")
        os.replace(tmp, out)
        return out

    def load_audio(self, path) -> np.ndarray:
        return self.srv.load_audio(str(path))

    def encode_cached(self, audio: np.ndarray) -> torch.Tensor:
        """(2, N) float32 audio -> (1, 256, ceil(N/HOP)) float32 CPU latent, cached by content."""
        a = np.ascontiguousarray(audio, dtype=np.float32)
        key = hashlib.sha256(a.tobytes()).hexdigest()
        path = self._paths().cache_dir("encode") / f"{key}.npy"
        frames = int(np.ceil(a.shape[1] / HOP))
        if path.exists():
            return torch.from_numpy(np.load(path).astype(np.float32))
        srv = self.srv
        with srv.GPU_LOCK:
            z = srv.MODEL.encode(torch.from_numpy(a), srv.SR, chunked=True)
        z = z.detach().float().cpu()
        if z.dim() == 2:
            z = z.unsqueeze(0)
        if z.shape[-1] < frames:
            z = torch.nn.functional.pad(z, (0, frames - z.shape[-1]))
        z16 = z[..., :frames].contiguous().numpy().astype(np.float16)
        # Write to a temp file and rename: a /forge/stats read in the threadpool must never see a
        # half-written cache file. Return the SAME float16 round-trip a hit returns, so a fixed seed
        # gives identical audio on the first run and every later one (review 2026-10-01).
        tmp = path.with_name(path.stem + ".part.npy")
        np.save(tmp, z16)
        os.replace(tmp, path)
        return torch.from_numpy(z16.astype(np.float32))

    def stretched_path(self, src, speed, semitones):
        from . import stretch
        from .hashing import file_sha256
        src = Path(src)
        if stretch.is_identity(speed, semitones):
            return src
        stretch.validate(speed, semitones)
        sha = file_sha256(src)
        dst = self._paths().cache_dir("stretch") / f"{stretch.cache_key(sha, speed, semitones)}.wav"
        if not dst.exists():
            readable = src
            if src.suffix.lower() not in (".wav", ".flac"):
                readable = self._paths().cache_dir("decode") / f"{sha}.wav"
                if not readable.exists():
                    sf.write(readable, self.load_audio(src).T, self.srv.SR, subtype="FLOAT")
            stretch.stretch_file(readable, dst, speed, semitones)
        return dst
