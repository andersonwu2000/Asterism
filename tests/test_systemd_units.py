"""Invariant tests for installer/systemd/*.service (rule 6: config
files get tests too — the journal WARNED and dropped StartLimit* when
they sat in [Service], leaving Restart unbraked, 2026-08-24)."""
import pathlib
from pathlib import Path

UNITS = Path(__file__).resolve().parents[1] / "installer" / "systemd"


def _sections(text: str) -> dict:
    out: dict = {}
    cur = None
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            cur = s
            out[cur] = []
        elif cur and s and not s.startswith("#"):
            out[cur].append(s)
    return out


def test_startlimit_keys_live_in_the_unit_section() -> None:
    for svc in UNITS.glob("*.service"):
        secs = _sections(svc.read_text(encoding="utf-8"))
        service = "\n".join(secs.get("[Service]", []))
        unit = "\n".join(secs.get("[Unit]", []))
        assert "StartLimit" not in service, (
            f"{svc.name}: StartLimit* in [Service] is IGNORED by this "
            f"systemd — move it to [Unit]")
        assert "StartLimitIntervalSec" in unit and "StartLimitBurst" in unit, (
            f"{svc.name}: Restart must stay braked")


def test_daemon_unit_keeps_the_owner_ruled_shape() -> None:
    text = (UNITS / "asterism-daemon.service").read_text(encoding="utf-8")
    # KillMode=process preserves the warm gateway across restarts
    assert "KillMode=process" in text
    # memory caps are PERCENTAGES of RAM (owner call 2026-08-24)
    assert "MemoryMax=85%" in text and "MemoryHigh=75%" in text
    # drift handoff relies on this restart policy (dispatcher rc=75)
    assert "Restart=on-failure" in text


def test_drift_handoff_exits_nonzero_under_systemd() -> None:
    """Mechanism pin: under systemd (INVOCATION_ID set) the dispatcher
    must NOT self-spawn a successor (an unsupervised orphan whose crash
    is a silent fleet stop — measured 2026-08-24); it exits rc=75 and
    Restart=on-failure relaunches the unit on current code."""
    src = pathlib.Path("Tooling/core/dispatcher.py").read_text(
        encoding="utf-8")
    assert 'os.environ.get("INVOCATION_ID")' in src
    assert "return 75" in src
