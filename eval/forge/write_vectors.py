"""Write shared test vectors so the TypeScript client and this server agree by construction.

Run: /home/kim/Projects/SAO/.venv/bin/python eval/forge/write_vectors.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from forge.envelope import sample_envelope  # noqa: E402

VECTOR_DIR = Path(__file__).resolve().parents[2] / "docs" / "latent-forge" / "contract" / "vectors"

ENVELOPE_CASES = [
    {"name": "flat", "env": {"points": [0.4, 0.4, 0.4, 0.4], "curves": [0, 0, 0]}, "n": 5},
    {"name": "linear", "env": {"points": [0, 0.333333, 0.666667, 1], "curves": [0, 0, 0]}, "n": 7},
    {"name": "bent", "env": {"points": [0, 0, 0, 0], "curves": [0.5, 0, 0]}, "n": 7},
    {"name": "single", "env": {"points": [0.2, 0.9, 0.1, 0.6], "curves": [-1, 1, 0.25]}, "n": 1},
    {"name": "mixed", "env": {"points": [0.2, 0.9, 0.1, 0.6], "curves": [-1, 1, 0.25]}, "n": 13},
]


def envelope_vectors():
    return [{**c, "values": [round(float(v), 6) for v in sample_envelope(c["env"], c["n"])]}
            for c in ENVELOPE_CASES]


def main():
    VECTOR_DIR.mkdir(parents=True, exist_ok=True)
    (VECTOR_DIR / "envelope.json").write_text(json.dumps(envelope_vectors(), indent=2) + "\n")
    print(f"wrote {VECTOR_DIR / 'envelope.json'}")


if __name__ == "__main__":
    main()
