"""Lake/Lean subprocess harness.

Wraps `lake env lean --json <file>`, parses newline-delimited JSON from
stdout (stderr is always empty per spike-003), and applies the spike-003
decision tree to produce a structured LakeResult.
"""
from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field


@dataclass
class LakeResult:
    outcome: str  # "proved" | "exhausted"
    messages: list[dict] = field(default_factory=list)
    timed_out: bool = False


def _kill_tree(pid: int) -> None:
    """Kill process and its entire child tree (Windows-safe)."""
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        import os
        import signal
        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except ProcessLookupError:
            pass


def _parse_json_lines(text: str) -> list[dict]:
    msgs: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            msgs.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return msgs


def run_lean(lean_file: str, cwd: str, timeout: float = 600.0) -> LakeResult:
    """Run ``lake env lean --json <lean_file>`` from ``cwd``.

    Decision tree (spike-003 §D4):
      TimeoutExpired              → outcome=exhausted, timed_out=True
      rc != 0                     → outcome=exhausted
      rc == 0 + kind=hasSorry     → outcome=exhausted
      rc == 0, no error/sorry     → outcome=proved
    """
    cmd = ["lake", "env", "lean", "--json", lean_file]
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        stdout_bytes, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_tree(proc.pid)
        proc.wait()
        return LakeResult(outcome="exhausted", timed_out=True)

    messages = _parse_json_lines(stdout_bytes.decode("utf-8", errors="replace"))

    if proc.returncode != 0:
        return LakeResult(outcome="exhausted", messages=messages)

    if any(m.get("kind") == "hasSorry" for m in messages):
        return LakeResult(outcome="exhausted", messages=messages)

    return LakeResult(outcome="proved", messages=messages)
