"""Lean is the proof; `compute` is the laboratory (owner ruling 2026-08-30).

The Strategist's ≥1-experiment quota retired on 2026-08-16, but the
vocabulary stayed: the judge was told a batch's decisions were "its
experiments", asked to "suggest the discriminating experiment", and the
stalled-gate teaching text told the Strategist to "pick the experiment
whose outcome most changes your Thesis". Under those words a 2^20-row
kernel table was a legitimate answer to criterion 1 ("does the charter
need this plan?") — it was dispatched as an experiment (rev 20 of the
union_closed (3,1) group), grew 596 nodes and burned half the fleet.

So: no agent-facing text calls dispatched work an experiment. Prompts
are checked as files; the two code-side messages (the rebuttal wrapper
and the stalled-gate teaching text) are checked as the string literals
the modules ship — comments and docstrings are not agent-facing.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROMPTS = ROOT / "Tooling" / "prompts"
AGENT_FACING_MODULES = [
    ROOT / "Tooling" / "pipeline" / "strategist" / "verify.py",
    ROOT / "Tooling" / "pipeline" / "strategist" / "wake.py",
    # The rebuttal's delta pack (2026-09-03): its headings and its
    # record lines are read by the author, so the same class of drift
    # applies here.
    ROOT / "Tooling" / "pipeline" / "round_materials.py",
    ROOT / "Tooling" / "sandbox" / "__init__.py",
]
WORD = re.compile(r"\bexperiments?\b", re.IGNORECASE)


def _string_literals(path: Path) -> list[tuple[int, str]]:
    """Every str literal in the module except docstrings."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstring_nodes: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef,
                             ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) \
                    and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                docstring_nodes.add(id(body[0].value))
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and id(node) not in docstring_nodes:
            out.append((node.lineno, node.value))
    return out


@pytest.mark.parametrize(
    "prompt", sorted(PROMPTS.rglob("*.md")),
    ids=lambda p: str(p.relative_to(PROMPTS)))
def test_prompts_never_call_dispatched_work_an_experiment(prompt: Path):
    hits = [(i, line) for i, line in enumerate(
        prompt.read_text(encoding="utf-8").splitlines(), 1)
        if WORD.search(line)]
    assert not hits, (
        f"{prompt.relative_to(ROOT)} still speaks of experiments: "
        + "; ".join(f"L{i}: {line.strip()[:90]}" for i, line in hits))


@pytest.mark.parametrize(
    "module", AGENT_FACING_MODULES,
    ids=lambda p: str(p.relative_to(ROOT)))
def test_agent_facing_messages_never_say_experiment(module: Path):
    hits = [(ln, s) for ln, s in _string_literals(module) if WORD.search(s)]
    assert not hits, (
        f"{module.relative_to(ROOT)} ships an agent-facing string that "
        "speaks of experiments: "
        + "; ".join(f"L{ln}: {s.strip()[:90]}" for ln, s in hits))
