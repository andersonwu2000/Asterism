"""The Formalizer's stage chain (`Tooling/pipeline/_stages.py`).

`update_plan_2026_07.md` §1 ratified ONE chain with fixed stations; the
code carried it as two hand-written sequences, and a station missing
from one arm survived a CONFIRMED code-review finding on 2026-07-27
because editing the prompt that promised it was cheaper than wiring it.
These tests pin the chain itself: the station order, that both arms walk
the same one, and that the delivery step after pre-search is not
optional.
"""
from pathlib import Path

import pytest

from Tooling.pipeline import _stages


class _Intake:
    def __init__(self, sid=None, declined=None, infra_rc=None):
        self.sid = sid
        self.declined = declined
        self.infra_rc = infra_rc


@pytest.fixture
def trace(monkeypatch):
    """Record station order; stub the intake spawn."""
    seen: "list[str]" = []
    box = {"intake": _Intake(sid="sid-1")}

    def fake_intake(**kw):
        seen.append(f"intake({kw['label']})")
        return box["intake"]

    monkeypatch.setattr("Tooling.pipeline._intake.run_intake", fake_intake)
    return seen, box


def _arm(seen, **over):
    from Tooling.pipeline import PipelineResult
    spec = dict(
        label="g1 slug",
        compile_context=lambda: seen.append("compile"),
        seed=lambda: seen.append("seed"),
        presearch=lambda: seen.append("presearch"),
        decline_result=lambda r, n: PipelineResult(
            outcome="failed", failure_reason=r, failure_detail=n),
    )
    spec.update(over)
    return _stages.Arm(**spec)


def _run(arm, tmp_path):
    return _stages.run_prework(
        arm, prompt_dir=tmp_path, attempts_dir=tmp_path,
        problem_dir=tmp_path, workspace=tmp_path)


def test_station_order_and_the_delivery_recompile(trace, tmp_path):
    """compile → seed → intake → presearch → compile.

    The trailing compile is the DELIVERY, not tidiness: after intake the
    first work spawn is a continuation (`initial_sid` set → `cold=False`
    → `_retry` skips `cold_prep_fn`), so nothing downstream rebuilds the
    context. Drop it and pre-search runs, writes its cache, and the work
    turn never sees a candidate — which is precisely what the mint arm
    did before this module existed."""
    seen, _ = trace
    result, sid = _run(_arm(seen), tmp_path)
    assert result is None
    assert sid == "sid-1"
    assert seen == ["compile", "seed", "intake(g1 slug)",
                    "presearch", "compile"]


def test_decline_pays_for_no_search(trace, tmp_path):
    """The cheapest exit stays cheap — a declined assignment must not
    pay for pre-search, and must not reach the work turn."""
    seen, box = trace
    box["intake"] = _Intake(declined=("no_nl_correspondence", "not argued"))
    result, sid = _run(_arm(seen), tmp_path)
    assert sid is None
    assert result is not None and result.outcome == "failed"
    assert result.failure_reason == "no_nl_correspondence"
    assert "presearch" not in seen
    assert seen == ["compile", "seed", "intake(g1 slug)"]


def test_infra_death_is_the_frameworks_not_the_assignments(trace, tmp_path):
    """An intake spawn killed by shutdown/quota/missing-CLI maps to an
    infra reason on BOTH arms — the assignment is not at fault, so it
    must not be recorded as one."""
    from Tooling.llm.base import SpawnRC
    seen, box = trace
    box["intake"] = _Intake(infra_rc=SpawnRC.QUOTA_EXHAUSTED)
    result, sid = _run(_arm(seen), tmp_path)
    assert sid is None
    assert result.failure_reason == "quota_exhausted"
    assert "presearch" not in seen


def test_guard_short_circuits_before_the_intake_spawn(trace, tmp_path):
    """The goal arm's over-budget guard exists to spend NOTHING; if it
    fires after the spawn it has already failed at its one job."""
    from Tooling.pipeline import PipelineResult
    seen, _ = trace
    arm = _arm(seen, pre_intake_guard=lambda: PipelineResult(outcome="moot"))
    result, sid = _run(arm, tmp_path)
    assert result.outcome == "moot"
    assert sid is None
    assert seen == []


def test_a_degraded_intake_falls_back_to_a_cold_work_turn(trace, tmp_path):
    """Intake malfunction must cost the early exit, never the work: no
    sid means the work turn spawns cold, the pre-staging behaviour."""
    seen, box = trace
    box["intake"] = _Intake(sid=None)
    result, sid = _run(_arm(seen), tmp_path)
    assert result is None
    assert sid is None
    # the search still runs — the assignment was not declined
    assert "presearch" in seen


def test_both_arms_walk_this_chain(tmp_path):
    """Neither pipeline may keep a private copy of the sequence — that
    is how the mint arm lost a station. Pin the call sites."""
    fwd = Path("Tooling/pipeline/forward.py").read_text(encoding="utf-8")
    bwd = Path("Tooling/pipeline/backward.py").read_text(encoding="utf-8")
    for src, name in ((fwd, "forward.py"), (bwd, "backward.py")):
        assert "_stages.run_prework(" in src, f"{name} bypasses the chain"
        assert "run_intake(" not in src, f"{name} re-implements the chain"
