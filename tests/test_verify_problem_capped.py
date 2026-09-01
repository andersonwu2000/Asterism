"""The lazy Root/Defs verify gate (`refill._verify_problem`) quarantines
a problem for the whole daemon run on a failed build. A build the OS
fence stopped for lack of room is not that verdict: the problem stays
unverified and is asked again on its next dispatch."""
from __future__ import annotations

from Tooling.core.dispatcher import refill
from Tooling.pipeline import _lake


def _problem(tmp_path):
    from Tooling.state import db
    pdir = db.problem_dir(tmp_path, "Test.capped")
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "Root.lean").write_text("theorem main : True := trivial\n",
                                    encoding="utf-8")


def test_capped_verify_is_not_cached_as_a_failure(tmp_path, monkeypatch):
    _problem(tmp_path)
    r = _lake.BuildOutcome(False, "build capped — waited 900s for room above 2.0G")
    r.capped = True
    monkeypatch.setattr(_lake, "lake_build_modules", lambda ws, mods: r)
    assert refill._verify_problem(tmp_path, "Test.capped") is None, \
        "None = no verdict yet; False would quarantine the problem"


def test_a_real_failure_still_quarantines(tmp_path, monkeypatch):
    _problem(tmp_path)
    monkeypatch.setattr(_lake, "lake_build_modules",
                        lambda ws, mods: (False, "error: Root.lean:1:0: boom"))
    assert refill._verify_problem(tmp_path, "Test.capped") is False
