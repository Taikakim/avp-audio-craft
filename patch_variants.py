with open("eval/mixtape_smoke_stem_transitions.py", "r") as f:
    text = f.read()

import re
text = re.sub(
    r'variants = \{.*?"opt3_latentmix_a2a06": other_v5,\s*\}',
    r'variants = {"baseline_audio_crossfade": other_v1}',
    text,
    flags=re.DOTALL
)

with open("eval/mixtape_smoke_stem_transitions.py", "w") as f:
    f.write(text)
