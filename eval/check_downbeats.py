# Owner: unconfirmed, likely Antigravity/KUANG (kone-mixtape v7 stem pipeline, 2026-10-08); not W, C or G
# One-off check of downbeat alignment between two adjacent mixtape_v7_phase0 clips.
import json
from pathlib import Path
import numpy as np

phase0 = Path("/run/media/kim/Mantu/sa3_lora_runs/mixtape_v7_phase0")
with open(phase0 / 'order_used.json') as f:
    order = json.load(f)

k = 10
c1_id = order[k]['id']
c2_id = order[k+1]['id']

dbc = json.loads((phase0 / "downbeats_native.json").read_text())
db1 = np.array(dbc[c1_id])
db2 = np.array(dbc[c2_id])

bounds = json.loads(Path("/run/media/kim/Mantu/sa3_lora_runs/mixtape_v6_rerender/work48b/bounds.json").read_text())
bk1 = bounds[c1_id]
bk2 = bounds[c2_id]

out_s1 = float(db1[np.argmin(abs(db1 - bk1["end_pre_zc"]))])
out_i1 = int(np.argmin(abs(db1 - out_s1)))
W = 9

print(f"Track A downbeat intervals near transition:")
for i in range(out_i1 - W, out_i1 + 1):
    if i > 0:
        diff = db1[i] - db1[i-1]
        print(f"db1[{i}]: {db1[i]:.2f}s (diff: {diff:.3f}s)")
        
in_s2 = float(db2[np.argmin(abs(db2 - bk2["start"]))])
in_i2 = int(np.argmin(abs(db2 - in_s2)))
print(f"\nTrack B downbeat intervals near transition:")
for i in range(in_i2, in_i2 + W + 1):
    if i > 0:
        diff = db2[i] - db2[i-1]
        print(f"db2[{i}]: {db2[i]:.2f}s (diff: {diff:.3f}s)")

