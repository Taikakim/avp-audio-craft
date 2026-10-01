"""Per-lane audio buffers on the common timeline origin (spec §8.1 S3)."""
import numpy as np

from .envelope import sample_envelope


def _segment(clip, audio, sr, n_samples, next_start):
    s = int(round(clip["start_sec"] * sr))
    off = int(round(clip["offset_sec"] * sr))
    d = int(round(clip["dur_sec"] * sr))
    seg = np.asarray(audio, dtype=np.float32)[:, off:off + d]
    if seg.shape[1] == 0 or s >= n_samples:
        return s, None
    if clip.get("loop"):
        span = max(seg.shape[1], min(next_start, n_samples) - s)
        seg = np.tile(seg, (1, int(np.ceil(span / seg.shape[1]))))[:, :span]
    return s, seg[:, : max(0, min(n_samples, s + seg.shape[1]) - s)]


def place_single(clip, n_samples, sr, audio):
    buf = np.zeros((2, n_samples), dtype=np.float32)
    s, seg = _segment({**clip, "loop": False}, audio, sr, n_samples, n_samples)
    if seg is not None:
        buf[:, s:s + seg.shape[1]] += seg
    return buf


def place_lanes(clips, lanes, overlaps, n_samples, sr, clip_audio):
    soloed = any(l["solo"] for l in lanes)
    audible = {l["index"]: (l["solo"] if soloed else not l["muted"]) for l in lanes}
    gains = {l["index"]: float(l["gain"]) for l in lanes}
    out = [None, None, None, None]
    for lane in range(4):
        if not audible.get(lane):
            continue
        cs = sorted((c for c in clips if c["lane"] == lane), key=lambda c: c["start_sec"])
        buf = np.zeros((2, n_samples), dtype=np.float32)
        used = False
        for k, c in enumerate(cs):
            nxt = int(round(cs[k + 1]["start_sec"] * sr)) if k + 1 < len(cs) else n_samples
            s, seg = _segment(c, clip_audio(c), sr, n_samples, nxt)
            if seg is None or seg.shape[1] == 0:
                continue
            e = s + seg.shape[1]
            w = np.ones(e - s, dtype=np.float32)
            for ov in overlaps:
                if ov["lane"] != lane or c["id"] not in (ov["a_id"], ov["b_id"]):
                    continue
                rs, re_ = int(round(ov["start_sec"] * sr)), int(round(ov["end_sec"] * sr))
                r0, r1 = max(rs, s), min(re_, e)
                if r1 <= r0:
                    continue
                v = sample_envelope(ov["curve"], max(re_ - rs, 1))[r0 - rs:r1 - rs]
                w[r0 - s:r1 - s] *= np.cos(v * np.pi / 2) if c["id"] == ov["a_id"] else np.sin(v * np.pi / 2)
            buf[:, s:e] += seg * w * gains[lane]
            used = True
        out[lane] = buf if used else None
    return out
