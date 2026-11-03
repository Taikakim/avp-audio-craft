import re

with open("docs/superpowers/specs/2026-10-07-dj-mix-v7-transitions-spec.md", "r") as f:
    text = f.read()

# Update R0.4
text = re.sub(
    r"Options \(a\s+\*\*KIM\*\* decision, default b\): \(a\) lengthen every clip",
    r"Decision (KIM): Lengthen every clip",
    text
)

# Update R0.3 Phase alignment to include centering
if "centered exactly on the SSM structural boundary" not in text:
    text = text.replace(
        "**R0.3 Phase alignment.** Pick B's entry so that a B downbeat lands on an A downbeat (shared bar grid).",
        "**R0.3 Phase alignment.** Use SSM structural analysis (`eval/mixtape_structural_bounds.py`) to find macro-structural boundaries. The transition overlap window must be **centered exactly on the structural boundary**, and the bass handover ($H$) must trigger precisely on this boundary."
    )

# Also update Phase 2 Bass rule
text = text.replace(
    "* **bass, percussion:** per S2 (inpainted, or the hard hand-over fallback). Never two basslines at once.",
    "* **bass, percussion:** Asymmetric swap. Bass drops exactly on the structural boundary $H$ (which is now exactly at the center of the mixing window)."
)

with open("docs/superpowers/specs/2026-10-07-dj-mix-v7-transitions-spec.md", "w") as f:
    f.write(text)
