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
    # MemoryMax is a LIFELINE above the ledger budget, not a resource
    # manager; MemoryHigh must stay ABSENT — with no swap, its reclaim
    # loop evicts the shared olean pages every worker refaults (two
    # flagship crushes, 2026-08-26; owner ruling: the RAM axis has ONE
    # governor, the ledger)
    assert "MemoryMax=95%" in text
    assert not [ln for ln in text.splitlines()
                if ln.strip().startswith("MemoryHigh")], \
        "MemoryHigh is a second silent governor — retired 2026-08-26"
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


def test_stale_gateway_kill_escalates_to_sigkill_on_posix() -> None:
    """TERM alone is not a kill on POSIX: uvicorn traps it for graceful
    shutdown and a warm gateway hangs in the drain — the zombie listener
    starved four daemon generations into the StartLimit brake
    (2026-08-24). The kill loop must escalate to SIGKILL in-window."""
    src = pathlib.Path("Tooling/lsp/lifecycle.py").read_text(
        encoding="utf-8")
    assert "SIGKILL" in src
    assert "escalating to SIGKILL" in src
