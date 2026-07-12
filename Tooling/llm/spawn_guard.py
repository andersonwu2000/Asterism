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
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

FILE_TOOLS = {"Read", "Grep", "Glob", "Edit", "Write", "MultiEdit",
              "NotebookEdit"}

# Path-bearing input fields per tool (Grep/Glob use `path`).
_PATH_FIELDS = ("file_path", "path", "notebook_path")

_POSIX_DRIVE = re.compile(r"^/(?:mnt/)?([A-Za-z])(/|$)")
# Absolute-path tokens inside a Bash command: windows drive form,
# posix drive form, or ~-anchored. Quotes/spaces delimit tokens.
_BASH_TOKEN = re.compile(
    r"""(?:[A-Za-z]:[\\/]|(?<![\w.])/(?:mnt/)?[A-Za-z]/|~[\\/])"""
    r"""[^\s'"();|&<>]*""")


def _normalize(raw: str, cwd: str | None) -> Path | None:
    """Best-effort canonical absolute Path for a raw path string.
    Returns None for relative paths when no cwd is known (treated as
    in-workspace — the session cwd is always inside the repo)."""
    p = raw.strip().strip("'\"")
    if not p:
        return None
    if p.startswith("~"):
        p = os.path.expanduser(p)
    m = _POSIX_DRIVE.match(p.replace("\\", "/"))
    if m:
        rest = p.replace("\\", "/")[m.end(1):]   # keep the leading slash
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


def check(tool_name: str, tool_input: dict, cwd: str | None) -> str | None:
    """Return a deny reason, or None to allow."""
    wl = _whitelist()
    if tool_name in FILE_TOOLS:
        for field in _PATH_FIELDS:
            raw = tool_input.get(field)
            if not raw:
                continue
            path = _normalize(str(raw), cwd)
            if path is None:
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
        home = Path.home()
        allowed_home = _allowed_home()
        for m in _BASH_TOKEN.finditer(str(tool_input.get("command", ""))):
            path = _normalize(m.group(0), cwd)
            if path is None or not _under(path, home):
                continue
            if not any(_under(path, root) for root in allowed_home):
                return (
                    f"Bash command references {m.group(0)}, which is "
                    "under the user's home directory. Home is outside "
                    "the problem workspace (only the Lean toolchain "
                    "~/.elan and your temp dir are allowed). Work with "
                    "the files inside your problem directory and "
                    ".attempts workspace.")
        return None
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
