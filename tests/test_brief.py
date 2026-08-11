"""Unit tests for `Tooling/brief.py` — BRIEF.md render + write surface.

The reflection-spawn side of LESSONS.md is tested in
`test_pipeline_reflection.py`. This file covers the framework-managed
half: section assembly, atomic write, multi-problem fan-out.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from Tooling import agent  # noqa - establishes import order, see brief.py
from Tooling.state import brief
from Tooling.state.manifest import Manifest


def _mk_problem_dir(tmp_path: Path, name: str = "p") -> Path:
    pdir = tmp_path / "Problems" / name
    pdir.mkdir(parents=True, exist_ok=True)
    return pdir


def test_render_minimal_manifest_includes_sandbox_header(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An almost-empty Manifest still renders the always-on Sandbox
    section + the BRIEF auto-render header."""
    # Stub lemma_lookup so the test doesn't shell out to lake.
    from Tooling.knowledge import lemma_lookup
    monkeypatch.setattr(lemma_lookup, "lookup_batch", lambda names, ws: {})

    mfst = Manifest(problem="p", body="True")
    out = brief.render(tmp_path, mfst)
    assert "# p — BRIEF" in out
    assert "## Sandbox" in out
    assert "Reads allowed" in out


def test_render_includes_forbidden_and_strategic_notes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from Tooling.knowledge import lemma_lookup
    monkeypatch.setattr(lemma_lookup, "lookup_batch", lambda names, ws: {})

    mfst = Manifest(
        problem="p",
        forbidden_lemmas=["Some.banned_lemma"],
        body="T\n\nAvoid path X. Prefer path Y.",
    )
    out = brief.render(tmp_path, mfst)
    assert "## FORBIDDEN_LEMMAS" in out
    assert "Some.banned_lemma" in out
    # The operator's prose arrives whole, under one heading — no named
    # section is extracted from a file whose headings they choose.
    assert "## Manifest (from the operator)" in out
    assert "Avoid path X" in out


def test_worker_surface_carries_no_retired_pipeline_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """BRIEF is inlined into `Context.md` on every dispatch, so it is the
    highest-traffic agent-facing text there is — and the d75500a7 sweep
    missed it. It still told workers the framework renders this "for
    every Builder / Backward dispatch", and that "Builder fills in the
    proof; Backward edits the strategy skeleton's body", three months
    after v33 collapsed all three into the Formalizer. The companion pin
    in test_phase2_context.py covers only the strategist surfaces; this
    one covers the worker side, header and Sandbox section together
    (`brief.render` composes both).

    The Sandbox line also claimed `patch.lean` was the "single output"
    while formalize.md ships `patch.lean + new_*.lean` as the
    deliverable — stale role names travel with stale contracts."""
    from Tooling.knowledge import lemma_lookup
    monkeypatch.setattr(lemma_lookup, "lookup_batch", lambda names, ws: {})

    out = brief.render(tmp_path, Manifest(problem="p", body="True"))
    for dead in ("Builder", "Backward", "Forward", "single output"):
        assert dead not in out, dead
    # The replacement has to still say what the output contract is.
    assert "`patch.lean` is your output" in out
    assert "new_<slug>.lean" in out
    assert "the signature is locked" in out


def test_no_retired_kind_name_survives_in_any_rendered_string() -> None:
    """Class-level pin over the two modules that render worker context.

    Fixing the strings twice (d75500a7, then the BRIEF header and Sandbox
    line) fixed instances. Four more sites were still live afterwards —
    the Library pointer, the `agent_declined` note, and both
    dead-strategy headers — because every pin so far rendered one
    section with one fixture, and a section nobody set up in a test is a
    section nobody checks.

    So this walks the AST instead of the output: every string constant in
    `agent/context.py` and `state/brief.py` that is not a docstring is
    either agent-facing prose or an internal key, and neither may name a
    kind that v33 retired. Comments never enter the AST, which is the
    behaviour we want — `dispatcher.py` and friends keep their historical
    incident notes; only text that can reach an agent is pinned."""
    import ast

    from Tooling.agent import context as agent_context

    retired = ("Builder", "Backward", "Forward")
    offenders: list[str] = []
    for mod in (agent_context, brief):
        path = Path(mod.__file__)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docstrings = {
            id(node.body[0].value)
            for node in ast.walk(tree)
            if isinstance(node, (ast.Module, ast.FunctionDef,
                                 ast.AsyncFunctionDef, ast.ClassDef))
            and node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        }
        for node in ast.walk(tree):
            if (isinstance(node, ast.Constant)
                    and isinstance(node.value, str)
                    and id(node) not in docstrings):
                for dead in retired:
                    if dead in node.value:
                        offenders.append(
                            f"{path.name}:{node.lineno} {dead!r} in "
                            f"{node.value[:70]!r}")
    assert not offenders, (
        "v33 merged every worker kind into the Formalizer; these strings "
        "still name the retired ones:\n  " + "\n  ".join(offenders))


def test_render_no_mathlib_hints_section(tmp_path: Path) -> None:
    """`## Lemma hints` was retired (target-1 pre-search replaces it): a
    Manifest with mathlib hints no longer renders a `## Mathlib lemmas`
    section in BRIEF."""
    mfst = Manifest(problem="p", body="T")
    out = brief.render(tmp_path, mfst)
    assert "## Mathlib lemmas" not in out
    assert "Nat.factorial" not in out


def test_write_returns_none_when_problem_dir_missing(
    tmp_path: Path,
) -> None:
    """No `Problems/<p>/` on disk → no write, returns None. Defends
    against test fixtures + mid-reset races without crashing."""
    mfst = Manifest(problem="ghost_problem", body="T")
    assert brief.write(tmp_path, mfst) is None


def test_write_produces_atomic_brief_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`brief.write` writes BRIEF.md atomically. Final file content
    equals what `render` would have produced."""
    from Tooling.knowledge import lemma_lookup
    monkeypatch.setattr(lemma_lookup, "lookup_batch", lambda names, ws: {})

    pdir = _mk_problem_dir(tmp_path)
    mfst = Manifest(problem="p", body="T\n\nhello world")

    target = brief.write(tmp_path, mfst)
    assert target is not None
    assert target == pdir / "BRIEF.md"
    assert target.exists()
    assert target.read_text(encoding="utf-8") == brief.render(tmp_path, mfst)
    # No tmp leftovers in the problem dir.
    leftovers = [p for p in pdir.iterdir() if p.name.startswith("BRIEF.")]
    assert leftovers == [target], f"unexpected files: {leftovers}"


def test_write_for_all_problems_swallows_per_problem_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If one problem's render raises, `write_for_all_problems` logs
    and continues so other problems still get refreshed."""
    from Tooling.knowledge import lemma_lookup
    monkeypatch.setattr(lemma_lookup, "lookup_batch", lambda names, ws: {})

    _mk_problem_dir(tmp_path, "good")
    _mk_problem_dir(tmp_path, "bad")
    good_mfst = Manifest(problem="good", body="T")
    bad_mfst = Manifest(problem="bad", body="T")

    # Force `bad` to raise inside write.
    real_write = brief.write
    def faulty_write(workspace, mfst):
        if mfst.problem == "bad":
            raise RuntimeError("simulated render failure")
        return real_write(workspace, mfst)
    monkeypatch.setattr(brief, "write", faulty_write)

    # No exception should escape.
    brief.write_for_all_problems(
        conn=None,  # write_for_all_problems doesn't use conn currently
        workspace=tmp_path,
        manifests={"good": good_mfst, "bad": bad_mfst},
    )

    # `good` still got its BRIEF.md.
    assert (tmp_path / "Problems/good/BRIEF.md").exists()
    # `bad` did not (the faulty write raised).
    assert not (tmp_path / "Problems/bad/BRIEF.md").exists()
