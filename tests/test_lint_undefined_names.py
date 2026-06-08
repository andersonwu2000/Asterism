"""Static guard against undefined-name regressions (ruff F821).

Catches the `real_mods` class of bug — a `NameError` in executed code that no
unit test happens to exercise — cheaply and early, before it surfaces as an e2e
crash. (The 2026-06-08 `_build_decl_isolated` regression shipped to main because
nothing static checked for undefined names.) F821 only, not full lint, to stay
targeted and noise-free.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]


def _have_ruff() -> bool:
    try:
        subprocess.run([sys.executable, "-m", "ruff", "--version"],
                       capture_output=True, check=True)
        return True
    except Exception:  # noqa: BLE001
        return False


@pytest.mark.skipif(not _have_ruff(), reason="ruff not installed")
def test_no_undefined_names_in_tooling() -> None:
    r = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--select", "F821",
         "--no-cache", str(_ROOT / "Tooling")],
        capture_output=True, text=True, cwd=str(_ROOT))
    assert r.returncode == 0, (
        "ruff F821 found undefined name(s) — a NameError waiting to happen:\n"
        + r.stdout + r.stderr)
