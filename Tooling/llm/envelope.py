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
