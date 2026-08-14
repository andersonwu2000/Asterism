"""A capability the caller grants must reach the CLI, or fail loudly.

THE BUG FAMILY. `LLMRequest` is provider-independent and every backend
renders it in its own dialect, so a field one backend reads and another
ignores is invisible: nothing raises, nothing logs, the spawn just runs
with less than it was given. Three instances so far, all silent:

  mcp_config_path    dropped by agy — the gemini formalizer ran with no
                     `validate_file` and could not type-check a line it
                     wrote (2026-08-02).
  extra_read_dirs    dropped by agy and codex — the Adversary was granted
                     `proofs/` and `Papers/`, agy soft-denied the read,
                     and a soft-deny ENDS THE TURN. Twelve wakes, ~1.9M
                     input tokens, reported as `agent_no_output`
                     (2026-08-15).
  read_deny_roots    the inverse: had it been dropped, the private
                     subtrees would have been readable with nobody the
                     wiser.

The grant now lives on `Envelope`, which every backend already consults,
and these tests hold each backend to it.
"""
from __future__ import annotations

import inspect
from pathlib import Path

from Tooling.llm import antigravity_cli, claude_cli, codex_cli, envelope
from Tooling.llm.base import LLMRequest

#: Fields of `LLMRequest` that are a CAPABILITY — something the spawn
#: can or cannot do because the caller said so. A new one belongs here
#: the day it is added; that is the point of the list.
CAPABILITY_FIELDS = ("write_roots", "mcp_config_path", "extra_read_dirs")


def test_the_envelope_carries_every_capability_the_caller_grants(
        tmp_path: Path):
    """The envelope is the one place all three backends read from, so a
    grant that never lands on it can only be honoured by whichever
    backend happens to look at the request directly."""
    proofs = tmp_path / "Problems" / "P" / "proofs"
    papers = tmp_path / "Papers"
    req = LLMRequest(kind="adversary", prompt_path=tmp_path / "p.md",
                     problem_dir=tmp_path / "Problems" / "P",
                     attempts_dir=tmp_path / ".attempts" / "pid",
                     timeout_sec=900,
                     extra_read_dirs=(proofs, papers))
    env = envelope.envelope_for(req)
    assert env.read_allow_roots == (proofs, papers), (
        "extra_read_dirs never reached the envelope, so a backend that "
        "reads only the envelope cannot honour it")


def test_every_backend_renders_the_read_grant():
    """agy needs it most — its unmatched actions are soft-denied and a
    soft-deny ends the turn — but a backend that cannot express a grant
    must say so rather than drop it."""
    for mod in (antigravity_cli, claude_cli, codex_cli):
        src = inspect.getsource(mod)
        assert ("read_allow_roots" in src or "extra_read_dirs" in src), (
            f"{mod.__name__} renders neither the envelope's "
            f"read_allow_roots nor the request's extra_read_dirs — the "
            f"caller's grant is dropped on the floor")


def test_the_judge_is_granted_its_two_directories_and_not_the_workspace(
        tmp_path: Path):
    """The Adversary's `problem_dir` is its projection ON PURPOSE, so
    `_workspace_of` returns None and there is no workspace-wide read.
    Restoring one to make that None go away would hand the judge the
    live problem dir, sibling attempts and the author's scratch — the
    isolation fresh-per-round exists to keep. The grant is exactly the
    named directories."""
    proj = tmp_path / ".attempts" / "pid" / "adversary" / "r1"
    proj.mkdir(parents=True)
    proofs = tmp_path / "Problems" / "P" / "proofs"
    papers = tmp_path / "Papers"
    req = LLMRequest(kind="adversary", prompt_path=tmp_path / "p.md",
                     problem_dir=proj, attempts_dir=proj, timeout_sec=900,
                     extra_read_dirs=(proofs, papers))
    env = envelope.envelope_for(req)
    perms = antigravity_cli._spawn_permissions(
        env, antigravity_cli._workspace_of(proj))
    reads = [a for a in perms["permissions"]["allow"]
             if a.startswith("read_file(")]
    assert reads == [f"read_file({proofs})", f"read_file({papers})"], reads
    assert not any(str(tmp_path) == a[len("read_file("):-1]
                   for a in reads), "the judge was handed the workspace"
