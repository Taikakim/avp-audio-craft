with open("eval/render_v7_4track_smoketest_fast.py", "r") as f:
    text = f.read()

bad_chroma = """def get_chroma(audio, sr):
    y = librosa.to_mono(audio)
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=4096)
    return torch.tensor(chroma).unsqueeze(0)"""

good_chroma = """sys.path.insert(0, "/home/kim/Projects/mir-same-chroma/src")
from harmonic.same_chroma import compute_same_chroma

def get_chroma(audio, sr):
    c = compute_same_chroma(audio.T, sr).reshape(384, -1)
    return torch.tensor(c).unsqueeze(0)"""

text = text.replace(bad_chroma, good_chroma)

with open("eval/render_v7_4track_smoketest_fast.py", "w") as f:
    f.write(text)
