import re

with open("docs/superpowers/specs/2026-10-07-dj-mix-v7-transitions-spec.md", "r") as f:
    text = f.read()

chroma_text = """* **Chroma Steering (LatCH):** Integrate the Chroma LatCH head to explicitly morph the harmonic content (chroma) during the A2A pass. This forces the generative mid-range to bridge the harmonic gap seamlessly, creating a true timbre morph with zero glitches."""

if "Chroma Steering" not in text:
    text = text.replace(
        "* **Prompt/CLAP Interpolation:** Do not use static text prompts. Extract the CLAP audio embeddings for Clip A and Clip B, and spherically interpolate (slerp) them across the transition window to drive the conditioning.",
        "* **Prompt/CLAP Interpolation:** Do not use static text prompts. Extract the CLAP audio embeddings for Clip A and Clip B, and spherically interpolate (slerp) them across the transition window to drive the conditioning.\n" + chroma_text
    )

with open("docs/superpowers/specs/2026-10-07-dj-mix-v7-transitions-spec.md", "w") as f:
    f.write(text)
