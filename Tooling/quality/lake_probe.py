"""Shared `lake env lean` probe primitive (Library cleanup + dedup).

ONE home for the subprocess boilerplate — throwaway `.lean` under `.attempts`,
utf-8, timeout, cleanup — and for Lean error-line parsing, so the cleanup/dedup
probe call sites stop each re-implementing timeout / encoding / error-parse.

Crucially it separates the THREE outcomes a probe can have:
  - `ok`     — rc 0 and no Lean error line;
  - `error`  — real Lean errors (with attributable line numbers);
  - `infra`  — timeout / spawn error / broken env (no rc, or rc≠0 with no error
               line). NOT a verdict — callers must not conflate it with "false".

`batch_defeq` relied on the latter distinction implicitly and silently returned
all-False on timeout, making a load-dependent miss indistinguishable from a real
"not defeq" with no audit trail; `LeanRun.infra` makes that explicit + loggable.
"""
from __future__ import annotations

import re
import subprocess
import uuid
from pathlib import Path
from typing import NamedTuple

from ..core.process_group import no_window_creationflags

# `<file>:<line>:<col>: error` — the (1-based) line number is group(1).
LAKE_ERR_RE = re.compile(r"^.+?:(\d+):\d+:\s*error", re.MULTILINE)

DEFAULT_TIMEOUT_SEC = 240


class LeanRun(NamedTuple):
    """Raw outcome of one `lake env lean` invocation.

    `returncode is None` iff the probe never produced one (timeout / OSError) —
    an INFRA failure, not a verdict. `output` is `stdout + "\\n" + stderr`, or
    the exception text on infra."""

    returncode: "int | None"
    output: str
    timed_out: bool

    @property
    def infra(self) -> bool:
        """No usable verdict: timeout / spawn error, or rc≠0 with no error line
        (broken env — e.g. a missing/stale dependency olean mid-cleanup)."""
        return self.returncode is None or (
            self.returncode != 0 and not LAKE_ERR_RE.search(self.output))

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not LAKE_ERR_RE.search(self.output)

    @property
    def error_lines(self) -> "frozenset[int]":
        """1-based line numbers carrying a Lean error (empty unless real errors
        were parsed)."""
        return frozenset(int(m.group(1)) for m in LAKE_ERR_RE.finditer(self.output))


def run_lean_source(workspace: Path, content: str, *, prefix: str = "_probe",
                    json: bool = False,
                    timeout: int = DEFAULT_TIMEOUT_SEC) -> LeanRun:
    """Write `content` to a throwaway `.lean` under `.attempts` and cold-run
    `lake env lean [--json] <file>` (typecheck only, no olean). Always cleans up
    the temp file. On timeout / OSError returns `LeanRun(returncode=None, …)`
    (infra) with the exception text in `output`."""
    tmp_dir = workspace / ".attempts"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp = tmp_dir / f"{prefix}_{uuid.uuid4().hex}.lean"
    tmp.write_text(content, encoding="utf-8")
    cmd = ["lake", "env", "lean"] + (["--json"] if json else []) + [str(tmp)]
    try:
        r = subprocess.run(
            cmd, cwd=str(workspace), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
            creationflags=no_window_creationflags())
        return LeanRun(r.returncode, r.stdout + "\n" + r.stderr, False)
    except subprocess.TimeoutExpired as e:
        return LeanRun(None, f"timeout after {timeout}s: {e}", True)
    except OSError as e:
        return LeanRun(None, f"spawn error: {e}", False)
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass
