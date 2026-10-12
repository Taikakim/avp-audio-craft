import forge_testutil  # noqa: F401
from forge import logseq, progress


def test_logseq_since():
    logseq.reset()
    logseq.append("a")
    logseq.append("b")
    last, lines = logseq.since(0)
    assert last == 2
    assert lines == [{"seq": 1, "text": "a"}, {"seq": 2, "text": "b"}]
    assert logseq.since(1)[1] == [{"seq": 2, "text": "b"}]
    assert logseq.since(2) == (2, [])


def test_logseq_ring_is_bounded():
    logseq.reset()
    for i in range(450):
        logseq.append(str(i))
    last, lines = logseq.since(0)
    assert last == 450 and len(lines) == 400 and lines[0]["seq"] == 51


def test_progress_lifecycle():
    progress.end()
    assert progress.snapshot() is None
    progress.on_step(1, 8)                       # no job: ignored
    assert progress.snapshot() is None
    progress.begin("j1", "commit", 16, ["S1", "S2"])
    s = progress.snapshot()
    assert s == {"job_id": "j1", "op": "commit", "stage": "", "stage_index": 0, "stage_count": 2,
                 "step": 0, "steps": 0, "steps_left_total": 16, "steps_total": 16}
    progress.stage(1, "S1")
    progress.on_step(1, 8)
    progress.on_step(2, 8)
    s = progress.snapshot()
    assert (s["stage"], s["stage_index"], s["step"], s["steps"], s["steps_left_total"]) == ("S1", 1, 2, 8, 14)
    progress.stage(2, "S2")
    assert progress.snapshot()["step"] == 0
    for i in range(1, 30):
        progress.on_step(i, 8)
    assert progress.snapshot()["steps_left_total"] == 0      # never negative
    progress.end()
    assert progress.snapshot() is None
