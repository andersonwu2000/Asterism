"""The per-spawn capability envelope, in one place.

Every provider hands its agent the same three grants — which tools, which
write roots, which MCP servers — and each renders them in its own dialect
because each CLI reads its rules from somewhere different:

  claude  flags + env, per invocation (`--allowedTools`, `--mcp-config`,
          `ASTERISM_SPAWN_WRITE_ROOTS`). Nothing on disk; two concurrent
          spawns cannot interfere.
  agy     files under the home directory, and nothing else — it has no
          config flag (`agy --help`, probed 2026-08-01) and its own docs
          give exactly two scopes, global and per-plugin
          (`builtin/skills/agy-customizations/docs/mcp_servers.md`). So a
          per-spawn envelope means a per-spawn HOME.
  openai  no tools at all (single-shot fence parsing) — it can host no
          role that needs one, which is a property of the provider, not
          of this module.

The grants themselves are provider-independent, so they are computed
here rather than in each provider. A new backend implements one function:
"render this envelope in my dialect", and MUST fail loudly if it cannot —
the failure mode that cost the most so far was agy silently ignoring a
config written where it does not look, which is indistinguishable from
"this provider has no MCP support" (2026-07-30).
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from .base import LLMRequest

#: Kinds whose sanctioned edit surface is `Library/` — the librarian
#: family edits it in place. Every other persisted artifact is written by
#: framework code, not by a spawn's tools.
_LIBRARY_EDITING_KINDS = ("librarian", "migrate", "classify", "alias")


@dataclass(frozen=True)
class Envelope:
    """What one spawn may do. Paths are absolute.

    write_roots[0] is the attempts sandbox and stays first: deny messages
    point at it as "write here instead"."""
    write_roots: "tuple[Path, ...]"
    mcp_config_path: "Path | None"

    def write_roots_env(self) -> str:
        """`ASTERISM_SPAWN_WRITE_ROOTS` value (spawn_guard's parser)."""
        return os.pathsep.join(str(p) for p in self.write_roots)


def spawn_env(base: "dict[str, str] | None" = None) -> "dict[str, str]":
    """The inherited environment with THIS interpreter's directory first
    on PATH.

    Agents are handed shell commands that start with a bare `python`
    (scholar's `python -m Tooling.papers.fetch`, and the allowlist
    patterns that authorize exactly that spelling). A bare name is
    resolved against PATH, and the PATH a spawn inherits is the one the
    operator's shell happened to have when the daemon started — so an
    unrelated venv sitting earlier on it hands the agent an interpreter
    without the framework's dependencies. Observed 2026-08-06: scholar's
    fetch died on `ModuleNotFoundError: fitz` and reported "could not
    retrieve the paper", which reads as a paywall, not as a broken
    environment. Two papers were written off before the real cause
    surfaced.

    The daemon knows which interpreter it is; every child should agree.
    Fixing it here rather than in the prompt keeps the allowlist pattern
    (`Bash(python -m Tooling.papers.fetch *)`) matching the literal the
    agent types — a prompt rewritten to an absolute path would have to
    be kept byte-identical with a permission pattern in another file,
    which is the drift this project has paid for before.
    """
    env = dict(os.environ if base is None else base)
    own = str(Path(sys.executable).resolve().parent)
    cur = env.get("PATH", "")
    if cur.split(os.pathsep)[:1] != [own]:
        env["PATH"] = own + (os.pathsep + cur if cur else "")
    return env


def envelope_for(req: LLMRequest, *, library_dir: "Path | None" = None
                 ) -> Envelope:
    """The grants this spawn gets, independent of who will render them."""
    roots: "list[Path]" = [Path(req.attempts_dir)]
    if req.kind in _LIBRARY_EDITING_KINDS and library_dir is not None:
        roots.append(Path(library_dir))
    if req.kind == "paper_index":
        # Its problem_dir IS Papers/<pid>, and the agent's contract is to
        # write map.md there (papers/index.py re-stamps the frontmatter).
        roots.append(Path(req.problem_dir))
    return Envelope(
        write_roots=tuple(roots),
        mcp_config_path=(Path(req.mcp_config_path)
                         if req.mcp_config_path is not None else None),
    )
