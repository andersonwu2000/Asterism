"""Every commit path assembles through ONE function (#179).

`assemble_for_commit` has called itself "ONE normalization rule for every
file the framework commits" since task #5. The leaf-bypass path did not
use it: it called `manifest.inject_defs_opens` — step 3 of five, chosen
by hand. That is the class, and it had already bitten once before under
the same name: the comment removed by this fix records Defs opens being
missing on exactly this line in June 2026 ("the decomposition path below
already does this; the leaf-bypass path was the gap"), fixed by adding
the one missing step rather than by routing through the one function.
Steps 1, 2, 4 and 5 stayed missing, and step 5 — proved-sibling imports —
is what a patch citing a proved sibling needs.

The failure was invisible in the direction that matters: the sandbox
pre-loads sibling stubs, so the probe went green and the real build said
`Unknown identifier`. 37 agent reports read that as "sibling not found"
and doubted their own mathematics.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _leaf_bypass_source() -> str:
    """The leaf-bypass branch of `_commit_backward`, by its landmarks."""
    src = (REPO / "Tooling" / "pipeline" / "backward.py").read_text(
        encoding="utf-8")
    start = src.index("_strategy_{sid_token}.lean")
    end = src.index("Verify-unification", start)
    return src[start:end]


def test_leaf_bypass_commits_through_assemble_for_commit() -> None:
    body = _leaf_bypass_source()
    assert "assemble.assemble_for_commit(" in body, (
        "the leaf-bypass path stopped routing through the one assembly "
        "function — that is how #179 happened")


def test_no_commit_path_hand_picks_an_assembly_step() -> None:
    """`inject_defs_opens` is one of five steps. Calling it directly from
    a COMMIT path means the other four were skipped.

    Seed construction is a different job and stays allowed: a seed file
    is what the agent starts from, and it deliberately carries no
    imports (`forward._seed_text`, `librarian.bridge`)."""
    offenders: "list[str]" = []
    for rel in ("Tooling/pipeline/backward.py",
                "Tooling/pipeline/forward.py"):
        for i, line in enumerate(
                (REPO / rel).read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"\binject_defs_opens\s*\(", line):
                offenders.append(f"{rel}:{i}")
    # forward's single remaining call builds the SEED, not a commit.
    allowed = {"Tooling/pipeline/forward.py"}
    unexpected = [o for o in offenders if o.rsplit(":", 1)[0] not in allowed]
    assert not unexpected, (
        f"commit paths hand-picking one assembly step: {unexpected}. "
        f"Route through `assemble.assemble_for_commit` instead — the "
        f"steps it runs are the ones a hand-picked call keeps forgetting.")


def test_assemble_injects_the_sibling_import_a_leaf_bypass_needs(
    conn, tmp_path: Path,
) -> None:
    """The behaviour under the structure: a patch that cites a proved
    sibling by bare name, with no import line, comes back importable."""
    from Tooling.state import assemble

    problem = "T.p"
    pdir = tmp_path / "Problems" / "T" / "p"
    (pdir / "proofs").mkdir(parents=True)
    (pdir / "Defs.lean").write_text("import Mathlib\n", encoding="utf-8")
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at)"
        " VALUES (?, ?, '2026-08-10')", (problem, "Manifest.md"))
    conn.execute(
        "INSERT INTO goals (problem, slug, lean_path, statement, status,"
        " origin, created_at, updated_at) VALUES (?, 'helper_lemma', ?,"
        " '1 = 1', 'proved', 'root', '2026-08-10', '2026-08-10')",
        (problem, f"Problems/{problem}/proofs/L_helper_lemma.lean"))
    conn.commit()

    patch = ("namespace Problems.T.p\n"
             "theorem s1 : 1 = 1 := by exact helper_lemma\n"
             "end Problems.T.p\n")
    out = assemble.assemble_for_commit(
        patch, problem=problem, workspace=tmp_path, conn=conn)
    assert "helper_lemma" in " ".join(out.injected_sibling_imports), (
        f"the cited proved sibling was not imported: "
        f"{out.injected_sibling_imports}")
    assert f"import Problems.{problem}.proofs.L_helper_lemma" in out.text
