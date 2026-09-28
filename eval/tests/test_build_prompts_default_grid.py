"""build_prompts()'s default grid size is a documented, load-bearing invariant -- pin it exactly.

History (2026-09-28): BRACKET_PROMPTS was briefly auto-appended inside build_prompts() with no
comment (12 -> 14 prompts, 109 -> 127 cells/LoRA ckpt); reverted by W's review as an unexplained
regression against the then-documented 12/109 convention; then Kim direct chose to keep it after
all (kl_bracket_0 is the single most-rated prompt on the whole board; rb_bracket_0 kept for its own
rating history despite sharing rb_common_0's text) -- so 14/127 (42 full-FT) is now the intended
default, and CLAUDE.md / RUNBOOK.md / the sa3-canonical-clips skill were updated to match. This
test exists so the NEXT accidental change (either direction) fails loud instead of drifting the
convention silently again.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import model_matrix_gen as mmg  # noqa: E402


def test_default_grid_is_exactly_fourteen_prompts():
    prompts = mmg.build_prompts()
    assert len(prompts) == 14, sorted(p["id"] for p in prompts)


def test_bracket_prompt_ids_are_in_the_default_grid_exactly_once():
    ids = [p["id"] for p in mmg.build_prompts()]
    assert ids.count("rb_bracket_0") == 1
    assert ids.count("kl_bracket_0") == 1


def test_all_prompts_union_does_not_duplicate_the_now_default_bracket_ids():
    # mirrors the --all-prompts branch in main(): union of build_prompts() + EXTRA_PROMPTS +
    # BRACKET_PROMPTS + NEW_PROMPTS, deduped by id (first occurrence wins). Now that build_prompts()
    # itself carries the bracket ids, the explicit BRACKET_PROMPTS source in that union is a no-op
    # for them (already seen), not a duplicate -- confirm the dedup still holds.
    merged, seen = [], set()
    for src in (mmg.build_prompts(),
                [{"id": pid, "text": t, "seed": mmg.EXTRA_SEED} for pid, t in mmg.EXTRA_PROMPTS.items()],
                mmg.BRACKET_PROMPTS, mmg.NEW_PROMPTS):
        for p in src:
            if p["id"] not in seen:
                merged.append(p)
                seen.add(p["id"])
    ids = [p["id"] for p in merged]
    assert ids.count("rb_bracket_0") == 1
    assert ids.count("kl_bracket_0") == 1
