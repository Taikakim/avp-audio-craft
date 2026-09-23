#!/usr/bin/env python3
"""check_train_manual.py — fail if train_lora_modular.py has a command-line flag that
docs/train_lora_modular.md does not mention (or the manual names a flag that no longer exists).

Run after changing the trainer's options:
  /home/kim/Projects/SAO/.venv/bin/python /home/kim/Projects/SAO/Misc/check_train_manual.py
Exit 0 = in sync; exit 1 = lists what to document or delete.
"""
import argparse
import re
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Misc/ holds our own filelock.py, which would shadow the real `filelock` package that
# huggingface_hub imports while the trainer module loads.
sys.path[:] = [p for p in sys.path if Path(p or ".").resolve() != Path(__file__).resolve().parent]
SCRIPT = ROOT / "stable-audio-3" / "scripts" / "train_lora_modular.py"
MANUAL = ROOT / "docs" / "train_lora_modular.md"


def script_flags():
    """Every option string the script's parser defines (captured without running training)."""
    found = []

    def grab(self, *a, **k):
        for act in self._actions:
            found.extend(s for s in act.option_strings if s.startswith("--") and s != "--help")
        raise SystemExit(0)

    orig = argparse.ArgumentParser.parse_args
    argparse.ArgumentParser.parse_args = grab
    argv = sys.argv
    sys.argv = [str(SCRIPT)]
    try:
        runpy.run_path(str(SCRIPT), run_name="__main__")
    except SystemExit:
        pass
    finally:
        argparse.ArgumentParser.parse_args = orig
        sys.argv = argv
    return set(found)


# flags of OTHER tools that the manual quotes on purpose (analysis commands, rocm-smi, train_lora.py)
OTHER_TOOLS = {"--help", "--ckpt-dir", "--data_dir", "--epoch-steps", "--glob", "--label", "--out",
               "--showpids", "--milestone", "--jump"}


def main():
    flags = script_flags()
    if not flags:
        raise SystemExit("could not read the script's flags")
    text = MANUAL.read_text()
    mentioned = set(re.findall(r"--[a-z0-9][a-z0-9_-]*", text))
    # an option is documented if ANY of its aliases appears; aliases share one argparse action,
    # so check per alias group
    missing = sorted(f for f in flags if f not in mentioned)
    # aliases like --batch-size/--batch_size: accept if the other spelling is present
    def norm(s):
        return s.replace("_", "-")
    mentioned_norm = {norm(m) for m in mentioned}
    missing = [f for f in missing if norm(f) not in mentioned_norm]
    alias_ok = {"--modular_wd", "--output_dir", "--wandb_project", "--wd_overtraining",
                "--warmup_steps", "--num-workers", "--batch-size", "--accumulate-grad-batches",
                "--modular-wd", "--wd-overtraining", "--output-dir"}
    missing = [f for f in missing if f not in alias_ok]
    stale = sorted(m for m in mentioned if norm(m) not in {norm(f) for f in flags}
                   and m not in OTHER_TOOLS)
    if missing:
        print("NOT DOCUMENTED in docs/train_lora_modular.md:\n  " + "\n  ".join(missing))
    if stale:
        print("Mentioned in the manual but not a flag of the script (check these):\n  " + "\n  ".join(stale))
    if missing:
        raise SystemExit(1)
    print(f"OK: all {len(flags)} option strings of train_lora_modular.py are covered.")


if __name__ == "__main__":
    main()
