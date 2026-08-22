"""PreToolUse hook: filesystem whitelist for spawned agents.

Claude Code permission rules cannot express a whitelist (deny > ask >
allow precedence — a broad deny swallows every allow, a broad ask
aborts headless sessions), so the true default-deny lives here. The
spawn cmd injects this hook via a generated settings file (see
claude_cli._spawn_guard_settings_path). Empirical basis: one month of
spawn traffic (2026-06-12..07-13, ~33k Bash + ~1.3k file-tool calls)
touched exactly three roots outside the repo — the operator auto-memory
dir (the leak this closes), the spawn's own scratchpad, and the elan
toolchain. See decision_log 2026-07-13.

Policy:
- File tools (Read/Grep/Glob/Edit/Write/MultiEdit/NotebookEdit):
  path must be inside WHITELIST = {repo root, <home>/AppData/Local/Temp,
  <home>/.elan, /tmp}. Everything else → deny with a teaching message.
- Write family (Edit/Write/MultiEdit/NotebookEdit), when the spawn cmd
  injects ASTERISM_SPAWN_WRITE_ROOTS (task #128, 2026-07-29): default-
  deny outside {attempts sandbox, the kind's sanctioned edit surface,
  temp}. The repo tree stays readable but is NOT a write surface —
  problem files are framework- or user-owned (07-29: a strategist wrote
  its plan note to the problem root and the persist chain silently
  missed it; same rule closes worker writes into mathlib packages /
  Library). Env absent (manual/legacy spawn) → broad whitelist as
  before.
- Read fence (all file tools + Bash), when the spawn cmd injects
  ASTERISM_SPAWN_READ_DENY_ROOTS (#162, 2026-08-10): the repo tree was
  readable WHOLE until this ruling, so a spawn could open
  `docs/internal/` (the operator's own notes and paper takeaways), the
  live `asterism.db`, `.asterism/backups/`, or another problem's proofs.
  Those roots are now default-deny. For Grep/Glob the path argument is a
  search ROOT, so a root that CONTAINS a private subtree is refused too —
  a prefix check alone passes `Grep(path=<repo>)` and prints the contents
  anyway. RESIDUAL GAP, named rather than papered over: the Bash pass
  only sees ABSOLUTE path tokens (see `_BASH_TOKEN`), so a relative
  `cat ../../docs/internal/STATUS.md` is not caught. Spawn cwd is the
  problem dir, which makes that a deliberate traversal rather than an
  accident, and the same limit has always applied to the home guard.
- Bash: home-directory guard. A command is denied only if it contains
  an absolute-path token that resolves under the user's home dir and
  outside the whitelist (~/.claude, ~/.ssh, ...). Tokens elsewhere are
  left to the OS — hallucinated paths fail naturally, and regex-like
  tokens ("s:\\s*") don't live under home. Zero false positives on the
  historical corpus.
- Fail-open: any internal error allows the call (the permission-rule
  deny on ~/.claude/projects/** remains as the second layer).

Deny protocol: stdout JSON permissionDecision=deny (per hooks docs) —
the model gets the reason and continues; exit stays 0.
"""
from __future__ import annotations

import json
import os
import re
import sys
from contextvars import ContextVar
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

FILE_TOOLS = {"Read", "Grep", "Glob", "Edit", "Write", "MultiEdit",
              "NotebookEdit"}

WRITE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}

# Per-spawn write whitelist, injected by claude_cli (os.pathsep-
# separated absolute paths; attempts dir FIRST — the deny message
# points at roots[0]).
WRITE_ROOTS_ENV = "ASTERISM_SPAWN_WRITE_ROOTS"

# Per-spawn READ blacklist, injected by claude_cli from
# `envelope.read_deny_roots` (#162, user ruling 2026-08-10). The repo
# root was readable whole until then, so a spawn could open
# `docs/internal/`, the live `asterism.db`, `.asterism/backups/`, or
# another problem's proofs. Env absent (manual/legacy spawn) → nothing
# denied, matching the write fence's fallback.
READ_DENY_ROOTS_ENV = "ASTERISM_SPAWN_READ_DENY_ROOTS"

# WHICH attempt this spawn owns — the one directory `inspect` may treat
# as "mine" when a bare `Context.md` misses the problem dir. It is
# `write_roots[0]`, but it needs its own name because it travels a
# different ROUTE: the fence vars are read by the spawn's own process,
# while this one is read by the MCP tools server, a child the provider
# starts. claude passes its whole environment down, codex hands its MCP
# children a fixed core set and only `[mcp_servers.<n>.env]` reaches
# them, and agy needs it in the per-spawn mcp_config. So every adapter
# renders it in its own dialect — the `read_deny_roots` lesson (#162),
# re-learned 2026-08-16 when a fix that read only the claude route
# shipped while all three NL seats were on codex.
ATTEMPT_DIR_ENV = "ASTERISM_SPAWN_ATTEMPT_DIR"

#: Request-local override for ATTEMPT_DIR_ENV. The zen shim executes
#: tools for MANY spawns inside ONE process, and pinning the env var
#: needed a process-global lock — one 28-minute grep then starved all
#: twelve spawns' tool calls (2026-08-23). A ContextVar is per-thread
#: state, so concurrent requests carry their own attempt dir and the
#: lock is gone. Standalone MCP servers (one process per spawn) keep
#: the env route; readers go through `current_attempt_dir()`.
ATTEMPT_DIR_CONTEXT: "ContextVar[str | None]" = ContextVar(
    "asterism_attempt_dir", default=None)


def current_attempt_dir() -> "str | None":
    """This request's attempt dir: context first, env fallback."""
    ctx = ATTEMPT_DIR_CONTEXT.get()
    if ctx:
        return ctx
    return os.environ.get(ATTEMPT_DIR_ENV) or None

#: Tools whose path argument is a search ROOT, not a target: they
#: traverse it, so a private subtree INSIDE the root leaks even though
#: the root itself is allowed.
SEARCH_TOOLS = {"Grep", "Glob"}


def _write_roots() -> "list[Path] | None":
    """Parse the per-spawn write whitelist. None = env absent
    (manual/legacy spawn) → the write family falls back to the broad
    whitelist. Temp scratchpads ride along so probe scripts keep
    working."""
    raw = os.environ.get(WRITE_ROOTS_ENV, "").strip()
    if not raw:
        return None
    roots = [Path(p.strip()) for p in raw.split(os.pathsep) if p.strip()]
    if not roots:
        return None
    home = Path.home()
    roots += [home / "AppData" / "Local" / "Temp", Path(os.sep + "tmp")]
    return roots

# Path-bearing input fields per tool (Grep/Glob use `path`).
_PATH_FIELDS = ("file_path", "path", "notebook_path")

_POSIX_DRIVE = re.compile(r"^/(?:mnt/)?([A-Za-z])(/|$)")
# Absolute-path tokens inside a Bash command: windows drive form,
# posix drive form, plain POSIX absolute (so a Linux host's
# /home/... references are guarded too), or ~-anchored. Quotes/spaces
# delimit tokens. The generic /-form can over-match (URLs' //host,
# /dev/null) — harmless: deny still requires under-home ∧ ¬whitelist.
_BASH_TOKEN = re.compile(
    r"""(?:[A-Za-z]:[\\/]|(?<![\w.])/(?:mnt/)?[A-Za-z]/|(?<![\w.])/|~[\\/])"""
    r"""[^\s'"();|&<>]*""")


def _normalize(raw: str, cwd: str | None) -> Path | None:
    """Best-effort canonical absolute Path for a raw path string.
    Returns None for relative paths when no cwd is known (treated as
    in-workspace — the session cwd is always inside the repo).
    Drive-letter rewriting and backslash folding are Windows-host
    semantics — on POSIX a backslash is a literal filename char and
    /c/... is a real directory, so both are gated on os.name."""
    p = raw.strip().strip("'\"")
    if not p:
        return None
    if p.startswith("~"):
        p = os.path.expanduser(p)
    if os.name == "nt":
        m = _POSIX_DRIVE.match(p.replace("\\", "/"))
        if m:
            rest = p.replace("\\", "/")[m.end(1):]  # keep the leading slash
            p = f"{m.group(1)}:{rest or '/'}"
        # collapse doubled separators from shell/JSON escaping
        p = re.sub(r"[\\/]+", lambda _: os.sep, p)
    if not os.path.isabs(p):
        if cwd is None:
            return None
        p = os.path.join(cwd, p)
    try:
        return Path(os.path.normpath(p))
    except (ValueError, OSError):
        return None


def _under(path: Path, root: Path) -> bool:
    try:
        sp, sr = str(path).lower().rstrip("\\/"), str(root).lower().rstrip("\\/")
        return sp == sr or sp.startswith(sr + os.sep)
    except Exception:
        return False


def _allowed_home() -> list[Path]:
    """Home subtrees spawns legitimately touch (from the one-month
    corpus): their scratchpad, the Lean toolchain, and installed
    interpreters invoked by absolute path (the corpus' single
    would-be false positive)."""
    home = Path.home()
    return [
        home / "AppData" / "Local" / "Temp",
        home / "AppData" / "Local" / "Programs",
        home / ".elan",
    ]


def _whitelist() -> list[Path]:
    return [REPO_ROOT, *_allowed_home(), Path(os.sep + "tmp")]


def _read_deny_roots() -> list[Path]:
    raw = os.environ.get(READ_DENY_ROOTS_ENV, "").strip()
    return [Path(p.strip()) for p in raw.split(os.pathsep) if p.strip()]


def _read_denied(tool_name: str, raw: str, path: Path,
                 droots: list[Path]) -> str | None:
    """Deny reason if this path lands in — or would traverse — a private
    subtree."""
    for root in droots:
        if _under(path, root):
            return (
                f"{tool_name} on {raw} is inside {root}, which is "
                "operator-private: the framework's own notes, earlier "
                "runs' databases, and other problems' proofs. Your "
                "problem's own files, Library/ and Papers/ are the "
                "surfaces meant for you — everything you are supposed to "
                "know is in Context.md and BRIEF.md.")
    if tool_name in SEARCH_TOOLS:
        # The root is allowed, but searching it walks the private
        # subtrees inside it. A prefix check alone would pass this and
        # print the contents anyway.
        inside = [r for r in droots if _under(r, path)]
        if inside:
            return (
                f"{tool_name} rooted at {raw} would search "
                f"{inside[0]} and the other operator-private subtrees "
                "under it. Narrow the search to your problem directory, "
                "Library/ or Papers/.")
    return None


def check(tool_name: str, tool_input: dict, cwd: str | None) -> str | None:
    """Return a deny reason, or None to allow."""
    wl = _whitelist()
    droots = _read_deny_roots()
    if tool_name in FILE_TOOLS:
        wroots = _write_roots() if tool_name in WRITE_TOOLS else None
        for field in _PATH_FIELDS:
            raw = tool_input.get(field)
            if not raw:
                continue
            path = _normalize(str(raw), cwd)
            if path is None:
                continue
            # Read fence first: it applies to the write family too (a
            # write root can never be private, but the check is cheap
            # and the ordering keeps one rule for one question).
            denied = _read_denied(tool_name, str(raw), path, droots)
            if denied:
                return denied
            if wroots is not None:
                if not any(_under(path, root) for root in wroots):
                    return (
                        f"{tool_name} on {raw} is outside your write "
                        "surface. The repository is readable but its "
                        "files are framework- or user-owned; write "
                        "your outputs into your attempts dir: "
                        f"{wroots[0]}")
                continue
            if not any(_under(path, root) for root in wl):
                return (
                    f"{tool_name} on {raw} is outside the problem "
                    "workspace. You may access the repository tree, "
                    "your scratchpad temp dir, and the Lean toolchain "
                    "only. Work with the files inside your problem "
                    "directory and .attempts workspace.")
        return None
    if tool_name == "Bash":
        # Belt to `--disallowedTools Bash`'s braces (2026-08-10). The
        # flag is the control; this is what an agent READS if a Bash call
        # ever reaches the hook again — a provider change, a legacy
        # spawn, an operator override. A gate message has to carry the
        # way out, so it names the replacements rather than just saying
        # no.
        return (
            "Bash is not available. Reading, searching and listing go "
            "through `inspect` — one call can carry several queries, e.g. "
            '[{"grep": "Foo", "in": "proofs/*.lean", "context": 3}, '
            '{"decl": "foo"}]. Running a calculation goes through '
            "`compute`. Loogle and JSON validation have their own tools.")
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        reason = check(
            str(payload.get("tool_name", "")),
            payload.get("tool_input") or {},
            payload.get("cwd"),
        )
    except Exception:
        return 0                      # fail-open by design
    if reason is not None:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
