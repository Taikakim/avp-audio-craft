#!/usr/bin/env python
import json
from pathlib import Path

def main():
    out_dir = Path("/run/media/kim/Mantu/sa3_lora_runs/mixtape_v7_phase0")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    clips = [f"clip_id_{i}" for i in range(41)]
    dur = 2000.0
    
    clip_bounds = [0.0]
    trans = []
    
    current_time = 0.0
    for i in range(40):
        # mock 16-bar transition length (~27 seconds at 140 bpm)
        t0 = current_time + 40.0
        t1 = t0 + 27.0
        trans.append([round(t0, 2), round(t1, 2)])
        clip_bounds.append(round((t0 + t1) / 2, 2))
        current_time = t1
        
    clip_bounds.append(round(dur, 2))
    
    timeline = {
        "dur": dur,
        "clips": clips,
        "clip_bounds": clip_bounds,
        "trans": trans
    }
    
    (out_dir / "timeline.json").write_text(json.dumps(timeline, indent=2))
    print(f"Mock timeline.json generated at {out_dir / 'timeline.json'}")

if __name__ == "__main__":
    main()
