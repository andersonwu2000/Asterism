"""What a lab run has to take down behind it.

A lab workspace is DISCARDED when the run ends — that is the whole
model (`lab_design.md` §2: "runs, then discarded; there is no
restore"). Every process the run started therefore has to be gone
before the clear, and the LSP gateway is the one that is built not to
be: in production it OUTLIVES its daemon on purpose (spawned with
`CREATE_BREAKAWAY_FROM_JOB` so a daemon restart reuses the warm
Mathlib), and nothing in the daemon's own shutdown touches it.

In a lab run that reuse never comes. On 2026-09-07 the first daemon arm
of the day left `gateway -> lake serve -> lean --server -> 10 x lean
--worker` standing: ~2 GB, an open handle on
`.asterism/logs/gateway.log`, and a workspace that would not clear.
Killed by hand, by pid, after being found by hand.

The pid comes from the workspace's OWN presence markers and from
nowhere else. The process name is shared with the operator's live
gateway and so is the default port; a teardown that went by either
would take a warm production pool down with it.
"""
from __future__ import annotations

import time
from pathlib import Path


#: How long the teardown waits for the killed tree to actually leave the
#: process table before it reports failure.
GATEWAY_STOP_TIMEOUT_SEC = 60.0

#: How long a workspace whose gateway LOG exists but whose presence
#: marker does not is given to produce one. The daemon creates
#: `gateway.log` before it starts the subprocess and the gateway writes
#: its marker seconds later, from inside it — a `--once` daemon that
#: drains an empty queue exits in between, and a teardown that looked
#: exactly once would call that "no gateway" and leave behind the very
#: tree that was still being launched.
GATEWAY_MARKER_GRACE_SEC = 5.0


def gateway_log_path(ws: Path) -> Path:
    """`.asterism/logs/gateway.log` — created by the daemon BEFORE the
    gateway subprocess starts, so its presence is the earliest evidence
    that this workspace launched one at all."""
    return Path(ws) / ".asterism" / "logs" / "gateway.log"


def gateway_pid(ws: Path) -> "int | None":
    """The pid of the gateway THIS workspace has, serving or warming.

    Read off the workspace's own presence markers, which is the only
    name for it that cannot be confused with somebody else's. The
    process NAME is shared with the operator's live gateway and so is
    the default PORT — a lab teardown that killed by either would take
    a warm 16-worker production pool down with it. The markers are
    files inside the workspace, and a lab workspace is built from a
    `git archive` plus a `carry` bundle, neither of which can carry
    one in."""
    from Tooling.lsp.lifecycle import gateway_live_pid, warming_pid
    ws = Path(ws)
    return gateway_live_pid(ws) or warming_pid(ws)


def _kill_gateway_tree(pid: int, timeout: float) -> "tuple[bool, str]":
    from Tooling.core.process_group import kill_process_tree
    return kill_process_tree(pid, timeout=timeout)


def stop_workspace_gateway(ws: Path, *,
                           timeout: float = GATEWAY_STOP_TIMEOUT_SEC,
                           grace_sec: float = GATEWAY_MARKER_GRACE_SEC,
                           _pid=None, _kill=None) -> dict:
    """Take down the LSP gateway tree this lab workspace started.

    In PRODUCTION a gateway outliving its daemon is the feature: warming
    Mathlib costs minutes, so it is deliberately spawned with
    `CREATE_BREAKAWAY_FROM_JOB` and reused across daemon restarts. In a
    LAB workspace it never is — the workspace is discarded at the end of
    the run, so what survives is an orphan holding ~2 GB of Lean
    workers and an open handle on `.asterism/logs/gateway.log`, which
    then defeats the clear (2026-09-07: pid 103068 with ten
    descendants, killed by hand).

    Returns `{gateway_stopped, gateway_pid, gateway_stop_detail}` for
    the driver result. "The run finished" and "the run left nothing
    behind" are two different facts, and only the first of them was
    ever written down."""
    ws = Path(ws)
    resolve = _pid or gateway_pid
    kill = _kill or _kill_gateway_tree
    deadline = time.monotonic() + (grace_sec
                                   if gateway_log_path(ws).exists() else 0.0)
    while True:
        try:
            pid = resolve(ws)
        except Exception as exc:        # noqa: BLE001 — a teardown that
            return {"gateway_stopped": False, "gateway_pid": None,
                    "gateway_stop_detail":  # crashes is worse than one
                    f"gateway pid lookup failed: {exc!r}"}  # that reports
        if pid is not None or time.monotonic() >= deadline:
            break
        time.sleep(0.25)
    if pid is None:
        return {"gateway_stopped": False, "gateway_pid": None,
                "gateway_stop_detail":
                f"no live gateway marker under {ws / '.asterism'} — "
                f"nothing to stop"}
    print(f"[lab] stopping this workspace's gateway tree (pid {pid})",
          flush=True)
    try:
        gone, detail = kill(int(pid), timeout)
    except Exception as exc:            # noqa: BLE001 — same reason
        return {"gateway_stopped": False, "gateway_pid": int(pid),
                "gateway_stop_detail": f"gateway kill failed: {exc!r}"}
    print(f"[lab] gateway pid {pid}: {detail}", flush=True)
    return {"gateway_stopped": bool(gone), "gateway_pid": int(pid),
            "gateway_stop_detail": str(detail)}


def with_gateway_teardown(driver, spec: dict, ws: Path, out: Path) -> dict:
    """Run one driver and take this workspace's gateway down behind it,
    on EVERY road out — the normal return, the stop-condition path and
    the exception alike.

    One wrapper rather than a teardown per kind, because "does this kind
    start a gateway?" is not a stable property of the kind: `daemon`
    starts one outright, and a `strategist_wake` reaches one through its
    own commit (`strategist/commit.py` -> `quality/review.store_review_
    snapshot` -> `start_gateway`, which warms the closure the sign-off
    surface reads). The others do not today. A helper that must be
    remembered when that changes is a leak with a date on it; a helper
    that is a no-op when no marker exists costs a `stat`."""
    try:
        result = driver(spec, ws, out)
    except BaseException:
        report = stop_workspace_gateway(ws)
        print(f"[lab] driver raised — gateway teardown: "
              f"{report['gateway_stop_detail']}", flush=True)
        raise
    result.update(stop_workspace_gateway(ws))
    return result
