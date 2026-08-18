Terminal fat checkpoints to pull from LUMI — 2026-08-18 (CONTINUITY, Kim direct).
106 runs have a terminal fat (1319.9 GB). 52 already local. Of the 54 missing (810.4 GB):
  -172.9 GB  cfg7/w1 renders measurably corrupted (clip_metrics.db, non-_ptm labels only)
  -98.6  GB  smokes / near-zero-step / a -v2 dup from the uncoordinated-trainer era
  -48.4  GB  TERMINAL EPOCH > 64 (Kim 2026-08-18: 'those models are very cooked by now,
             pulling the last checkpoints would leave us with trash') — ep69/134/153/228.
             These runs are NOT abandoned: render every 10th checkpoint and audition first,
             then pull whichever epoch actually sounds right.
  =490.5 GB  KEPT, 39 files (below).
_ptm labels were EXCLUDED from the corruption test — _ptm is the same checkpoint re-rendered
on medium-base (the base-mismatch control), so a bad _ptm is expected for a full-FT and is
NOT evidence the checkpoint is bad. 9 of 24 flagged labels were _ptm.
