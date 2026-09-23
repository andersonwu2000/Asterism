"""spawn_guard — PreToolUse whitelist fence for spawned agents.

Design basis (2026-07-13): permission rules cannot express a whitelist
(deny > ask > allow, first match wins), so the true default-deny is
this hook. Validated by replaying one month of real spawn traffic
(83,805 guarded tool calls): zero false positives; every deny was the
operator-memory channel or an already-broken path.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from Tooling.llm.spawn_guard import (READ_DENY_ROOTS_ENV, REPO_ROOT,
                                     SHELL_ALLOW_ENV, WRITE_ROOTS_ENV, check,
                                     shell_allow_prefixes)

CWD = str(REPO_ROOT / "Problems" / "Topology" / "some_problem")
HOME = Path.home()


def _mem(name: str = "MEMORY.md") -> str:
    return str(HOME / ".claude" / "projects" / "D--Asterism" / "memory" / name)


# ---------- file tools: whitelist semantics ----------

def test_file_tools_allow_repo_paths() -> None:
    cases = [
        str(REPO_ROOT / "Problems" / "p" / "proofs" / "L_x.lean"),
        str(REPO_ROOT / ".attempts" / "abc" / "patch.lean"),
        str(REPO_ROOT / ".lake" / "packages" / "mathlib" / "M.lean"),
        "relative/inside/cwd.lean",
    ]
    if os.name == "nt":
        # POSIX drive spelling and doubled separators, as seen live —
        # Windows-host spellings; meaningless where REPO_ROOT has no drive
        cases += [
            "/" + str(REPO_ROOT)[0].lower()
            + str(REPO_ROOT)[2:].replace("\\", "/") + "/TREE.md",
            str(REPO_ROOT).replace("\\", "\\\\") + "\\\\proofs\\\\a.lean",
        ]
    for raw in cases:
        assert check("Read", {"file_path": raw}, CWD) is None, raw
        assert check("Grep", {"path": raw}, CWD) is None, raw


def test_file_tools_allow_scratchpad_toolchain_programs() -> None:
    for raw in (
        str(HOME / "AppData" / "Local" / "Temp" / "claude" / "x" / "out.txt"),
        str(HOME / ".elan" / "toolchains" / "lean4" / "Init.lean"),
        str(HOME / "AppData" / "Local" / "Programs" / "Python" / "python.exe"),
    ):
        assert check("Read", {"file_path": raw}, CWD) is None, raw


def test_file_tools_deny_operator_state_and_escapes() -> None:
    assert check("Read", {"file_path": _mem()}, CWD)
    assert check("Edit", {"file_path": _mem("some_lesson.md")}, CWD)
    assert check("Write", {"file_path": str(HOME / ".ssh" / "config")}, CWD)
    # ..-traversal that lands outside the repo (live b6 sample);
    # separator spelling per host — POSIX keeps backslashes literal
    sep = "\\" if os.name == "nt" else "/"
    esc = (str(REPO_ROOT / "Problems" / "P" / "proofs")
           + (f"{sep}.." * 5) + f"{sep}.attempts{sep}x.lean")
    assert check("Write", {"file_path": esc}, CWD)
    # ..-traversal that STAYS inside the repo is fine
    ok = str(REPO_ROOT / "Problems" / "P" / "proofs" / ".." / "Defs.lean")
    assert check("Read", {"file_path": ok}, CWD) is None


def test_file_tools_deny_message_teaches() -> None:
    reason = check("Read", {"file_path": _mem()}, CWD)
    assert "workspace" in reason and "problem" in reason


# ---------- Bash: closed ----------

def test_bash_is_refused_and_the_refusal_teaches() -> None:
    """The home-directory guard retired with its premise (rule 13:
    a mechanism goes when the thing it guarded is gone, not when it
    stops firing). Bash is denied at the flag — `--disallowedTools Bash`,
    probe-verified 2026-08-10 — so the hook no longer sorts commands into
    allowed and denied. What it still owes an agent that somehow reaches
    it is the way out, which is the whole point of a gate message."""
    for cmd in ("ls -la",
                "cat ~/.claude/projects/p/memory/MEMORY.md",
                "timeout 580 ~/.elan/bin/lake env lean x.lean",
                "python -m Tooling.knowledge.loogle 'Nat.add_comm'"):
        reason = check("Bash", {"command": cmd}, CWD)
        assert reason, cmd
        assert "inspect" in reason and "compute" in reason, cmd


# ---------- Bash: the per-spawn shell grant ----------

def test_shell_allow_prefixes_unwraps_the_bash_pattern() -> None:
    """The CLI flag's spelling and the hook's question are different:
    `--allowed-tools` wants a glob pattern, the hook wants the command
    prefix. One helper derives the second from the first, so the two
    fences can never disagree about what was granted."""
    assert shell_allow_prefixes(
        ["Bash(lake env lean *)", "lake build"]) == [
            "lake env lean", "lake build"]


def test_shell_allow_opens_exactly_the_granted_command(monkeypatch) -> None:
    """The grant is the SECOND fence's business too: lifting the CLI's
    blanket `Bash` deny left this hook refusing every call, so a spawn
    that was handed `lake env lean` still could not run it (live
    direct-session arm, 2026-09-23). What the env var opens is the
    granted prefix as the WHOLE command — a wrapper or a shell operator
    would carry anything at all past a fence that only read the front."""
    monkeypatch.setenv(SHELL_ALLOW_ENV, '["lake env lean"]')
    patch = str(REPO_ROOT / ".attempts" / "x" / "patch.lean")
    assert check("Bash", {"command": f"lake env lean {patch}"}, CWD) is None
    assert check("Bash", {"command": "lake env lean"}, CWD) is None
    assert check("Bash", {"command": "lake build Foo"}, CWD)
    assert check("Bash", {"command": "rm -rf x"}, CWD)
    reason = check(
        "Bash", {"command": f"cd {REPO_ROOT} && lake env lean f.lean"}, CWD)
    assert reason and "single command" in reason, reason


def test_shell_allow_keeps_the_home_and_read_guards(monkeypatch) -> None:
    """A granted command is still a command: the two path fences the
    module docstring says cover Bash — the home-directory guard and the
    operator-private read deny — apply to it. They had no live Bash path
    to run on while every call was refused up front."""
    monkeypatch.setenv(SHELL_ALLOW_ENV, '["lake env lean"]')
    assert check("Bash", {"command": f"lake env lean {_mem()}"}, CWD)
    priv = str(REPO_ROOT / "docs" / "internal")
    monkeypatch.setenv(READ_DENY_ROOTS_ENV, priv)
    assert check("Bash", {"command": f"lake env lean {priv}/STATUS.md"}, CWD)


def test_bash_refusal_unchanged_without_the_grant(monkeypatch) -> None:
    """Control: every ordinary spawn carries no grant, and its refusal
    is the teaching message, byte for byte."""
    monkeypatch.delenv(SHELL_ALLOW_ENV, raising=False)
    reason = check("Bash", {"command": "lake env lean f.lean"}, CWD)
    assert reason and "inspect" in reason and "compute" in reason


# ---------- write family: per-spawn whitelist (task #128) ----------

ATT = str(REPO_ROOT / ".attempts" / "abc12345")


def test_write_family_default_deny_outside_roots(monkeypatch) -> None:
    """07-29 SG: a strategist wrote `_plan.md` to the problem root
    (cwd-relative) and the persist chain silently missed it. With the
    per-spawn roots env set, every write outside {attempts, temp} is
    denied with a message pointing at the attempts dir — including the
    soundness-adjacent surfaces every kind could previously write
    (mathlib packages, Library, other problems, Tooling)."""
    monkeypatch.setenv(WRITE_ROOTS_ENV, ATT)
    reason = check("Write", {"file_path": "_plan.md"}, CWD)
    assert reason and ATT in reason
    for raw in (
        str(REPO_ROOT / "Problems" / "p" / "notes.md"),
        str(REPO_ROOT / ".lake" / "packages" / "mathlib" / "M.lean"),
        str(REPO_ROOT / "Library" / "L.lean"),
        str(REPO_ROOT / "Tooling" / "pipeline" / "strategist.py"),
        str(HOME / ".ssh" / "config"),
    ):
        assert check("Edit", {"file_path": raw}, CWD), raw
    assert check("Write",
                 {"file_path": ATT + os.sep + "patch.lean"}, CWD) is None
    assert check("Write", {"file_path": str(
        HOME / "AppData" / "Local" / "Temp" / "t.txt")}, CWD) is None
    # read family unaffected by the write roots
    assert check("Read", {"file_path": str(
        REPO_ROOT / "Problems" / "p" / "Defs.lean")}, CWD) is None
    assert check("Grep", {"path": str(REPO_ROOT / "Library")}, CWD) is None


def test_write_family_kind_extras_and_env_absent(monkeypatch) -> None:
    lib = str(REPO_ROOT / "Library")
    monkeypatch.setenv(WRITE_ROOTS_ENV, ATT + os.pathsep + lib)
    assert check("Edit", {"file_path": lib + os.sep + "L.lean"}, CWD) is None
    assert check("Edit", {"file_path": str(
        REPO_ROOT / "Problems" / "p" / "x.md")}, CWD)
    monkeypatch.delenv(WRITE_ROOTS_ENV, raising=False)
    # legacy fallback (manual spawn): broad whitelist as before
    assert check("Write", {"file_path": str(
        REPO_ROOT / "Problems" / "p" / "_plan.md")}, CWD) is None


def test_claude_cli_injects_write_roots(tmp_path) -> None:
    """The env var this guard parses must actually be produced, and its
    first root must be the spawn's attempts dir (deny messages point at
    roots[0]). Asserted through `envelope.envelope_for` — the shared
    definition both providers render since 2026-08-01 — rather than by
    matching a source line, which froze the moment the line moved."""

    from Tooling.llm.base import LLMRequest
    from Tooling.llm.envelope import envelope_for

    att = tmp_path / ".attempts" / "pipe1"
    att.mkdir(parents=True)
    env_spec = envelope_for(LLMRequest(
        kind="backward", prompt_path=tmp_path / "p.md",
        problem_dir=tmp_path / "prob", attempts_dir=att, timeout_sec=60))
    assert env_spec.write_roots[0] == att
    assert env_spec.write_roots_env().split(os.pathsep)[0] == str(att)



# ---------- fail-open + hook protocol ----------

def test_check_never_raises_on_garbage() -> None:
    assert check("Read", {"file_path": None}, None) is None
    assert check("Read", {}, None) is None
    assert check("Weird", {"anything": 1}, None) is None


def test_main_denies_via_json_and_exits_zero() -> None:
    payload = json.dumps({"tool_name": "Read",
                          "tool_input": {"file_path": _mem()},
                          "cwd": CWD})
    r = subprocess.run(
        [sys.executable, str(REPO_ROOT / "Tooling" / "llm" / "spawn_guard.py")],
        input=payload, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_main_fail_open_on_bad_stdin() -> None:
    r = subprocess.run(
        [sys.executable, str(REPO_ROOT / "Tooling" / "llm" / "spawn_guard.py")],
        input="not json at all", capture_output=True, text=True, timeout=60)
    assert r.returncode == 0
    assert r.stdout.strip() == ""


# ---------- settings generation + spawn wiring ----------

def test_settings_file_generated_and_wired() -> None:
    from Tooling.llm.claude_cli import _spawn_guard_settings_path
    p = _spawn_guard_settings_path()
    assert p.exists()
    cfg = json.loads(p.read_text(encoding="utf-8"))
    hook = cfg["hooks"]["PreToolUse"][0]
    assert "Bash" in hook["matcher"] and "Read" in hook["matcher"]
    assert "spawn_guard.py" in hook["hooks"][0]["command"]
    src = (REPO_ROOT / "Tooling" / "llm" / "claude_cli.py").read_text(
        encoding="utf-8")
    assert '"--settings", str(_spawn_guard_settings_path()),' in src
