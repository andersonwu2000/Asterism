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


# ---------------------------------------------------------------------
# The fourth instance, and the first caught by a verifier rather than by
# production: which attempt a spawn owns (2026-08-16).
#
# `inspect` must resolve a bare `Context.md` against the spawn's own
# attempt dir — its briefing lives there while its cwd is the problem
# dir — and it must never resolve it against a SIBLING's, which is what
# it did (43 self-reports in one day). The fix read the declaration from
# the process environment, which is claude's dialect and only claude's:
# codex hands its MCP children a fixed core set (measured: 19-21
# variables, none of ours) and only `[mcp_servers.<n>.env]` reaches
# them; agy never set the variable at all. All three NL seats were on
# codex, so the fix was inert exactly where the bug was reported.
#
# The consumer here is not the spawn but the MCP TOOLS SERVER, a child
# the provider starts — a different route from the write/read fences,
# which the spawn's own process reads. That is why it needs its own
# name and its own parity test.
# ---------------------------------------------------------------------

def _spec(tmp_path: Path):
    cfg = tmp_path / "_mcp_config.json"
    cfg.write_text(
        '{"mcpServers": {"asterism_tools": {"command": "py", '
        '"args": ["-m", "Tooling.knowledge.mcp_tools"]}}}',
        encoding="utf-8")
    req = LLMRequest(kind="strategist", prompt_path=tmp_path / "p.md",
                     problem_dir=tmp_path / "Problems" / "P",
                     attempts_dir=tmp_path / ".attempts" / "pid",
                     timeout_sec=900, mcp_config_path=cfg)
    return envelope.envelope_for(req)


def test_codex_tells_the_tools_server_which_attempt_it_serves(
        tmp_path: Path):
    """codex's ONE verified route to that process is the config env
    block — the same one `ASTERISM_INSPECT_DELIVERY_CHARS` already
    uses."""
    from Tooling.llm.spawn_guard import ATTEMPT_DIR_ENV
    spec = _spec(tmp_path)
    toml = codex_cli._mcp_servers_toml(
        spec.mcp_config_path, spec.write_roots[0])
    assert "[mcp_servers.asterism_tools.env]" in toml
    assert ATTEMPT_DIR_ENV in toml
    assert str(spec.write_roots[0]) in toml


def test_agy_tells_the_tools_server_which_attempt_it_serves(
        tmp_path: Path):
    """agy's route is the per-spawn `mcp_config.json` it writes into the
    fake HOME; its env allowlist never carried this."""
    from Tooling.llm.spawn_guard import ATTEMPT_DIR_ENV
    src = inspect.getsource(antigravity_cli)
    assert ATTEMPT_DIR_ENV in src or "ATTEMPT_DIR_ENV" in src, (
        "agy writes the tools server's config and must declare the "
        "attempt dir in it")
    # …and it must land in the file, not merely be mentioned.
    assert 'entry.setdefault("env", {})' in src


def test_claude_tells_the_tools_server_which_attempt_it_serves():
    from Tooling.llm.spawn_guard import ATTEMPT_DIR_ENV
    src = inspect.getsource(claude_cli)
    assert "ATTEMPT_DIR_ENV" in src
    assert ATTEMPT_DIR_ENV == "ASTERISM_SPAWN_ATTEMPT_DIR"


def test_the_tool_reads_the_declaration_every_backend_writes():
    """The consumer end of the same fact — and it must not depend on
    the fence variable, which is the route codex drops."""
    from Tooling.knowledge import workspace_query as wq
    src = inspect.getsource(wq._own_attempt_dir)
    assert "ATTEMPT_DIR_ENV" in src
