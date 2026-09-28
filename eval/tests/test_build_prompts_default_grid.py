"""build_prompts() must not silently widen the documented default grid.

sa3-canonical-clips / CLAUDE.md / RUNBOOK.md all document the standard grid as 12 canonical
prompts -> 109 cells per LoRA/DoRA checkpoint (36 for full-FT). BRACKET_PROMPTS (rb_bracket_0,
kl_bracket_0) was briefly auto-appended inside build_prompts() itself (2026-09-2x, no comment/
rationale), which silently took every DEFAULT-path render from 12 to 14 prompts (109 -> 127
cells) -- verified live: --only-labels lion_lr1e-5 --only-ckpts ep399 went from 109 to 126
manifest cells. BRACKET_PROMPTS remains reachable via --all-prompts / --extra-prompts, unaffected.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import model_matrix_gen as mmg  # noqa: E402


def test_default_grid_is_exactly_twelve_prompts():
    prompts = mmg.build_prompts()
    assert len(prompts) == 12, sorted(p["id"] for p in prompts)


def test_bracket_prompt_ids_are_not_in_the_default_grid():
    ids = {p["id"] for p in mmg.build_prompts()}
    assert "rb_bracket_0" not in ids
    assert "kl_bracket_0" not in ids


def test_bracket_prompts_still_reachable_via_all_prompts_union():
    # mirrors the --all-prompts branch in main(): union of build_prompts() + EXTRA_PROMPTS +
    # BRACKET_PROMPTS + NEW_PROMPTS, deduped by id (first occurrence wins)
    merged, seen = [], set()
    for src in (mmg.build_prompts(),
                [{"id": pid, "text": t, "seed": mmg.EXTRA_SEED} for pid, t in mmg.EXTRA_PROMPTS.items()],
                mmg.BRACKET_PROMPTS, mmg.NEW_PROMPTS):
        for p in src:
            if p["id"] not in seen:
                merged.append(p)
                seen.add(p["id"])
    ids = {p["id"] for p in merged}
    assert {"rb_bracket_0", "kl_bracket_0"} <= ids
