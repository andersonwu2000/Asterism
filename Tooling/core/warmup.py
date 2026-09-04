"""core.warmup — NL-first gateway warm-up (research era, 2026-07-18).

The NL argumentation layer (Strategist wakes incl. their Adversary
rounds — loogle is a local index — plus Scholar) needs no Lean, so the
daemon warms the gateway in the BACKGROUND and dispatches NL kinds
immediately; Lean kinds stay queued (unleased, keeping their queue
position) until the warm finishes AND the Lean interface-contract gate
(task #12) passed on the warm gateway. A cold-cache slot-0 warm (300s+
observed 2026-07-16..18) then overlaps the first strategist wake
instead of delaying it. Warm/contract failure keeps the old
refuse-to-run semantics, deferred: the dispatcher stops popping,
drains in-flight NL work (its commits are durable), and exits rc 2.
"""
from __future__ import annotations

import threading
from pathlib import Path

# Queue kinds that need the warm Lean gateway. A drift test pins this
# against the queue-kind enum so a new kind must pick a side of the
# partition (NL side today: Strategist, Scholar, Theorist).
# Forward/Backward/Builder are pre-merge legacy rows; Formalizer is
# the live worker.
LEAN_QUEUE_KINDS: "tuple[str, ...]" = (
    "Formalizer", "Forward", "Backward", "Builder", "Librarian", "Verify")

#: The other side of the same partition — the RAM ledger's NL admission
#: excludes these when only Lean capacity is available (and vice
#: versa). The partition drift test pins LEAN | NL == the queue enum.
NL_QUEUE_KINDS: "tuple[str, ...]" = ("Strategist", "Scholar",
                                     "Theorist")


def start_background(workspace: Path) -> dict:
    """Kick off the gateway warm in a daemon thread.

    Returns the live state dict the dispatcher polls each tick:
    {'ready': bool, 'failed': str | None}. `ready` flips only after
    the contract gate passed; `failed` carries the reason when the
    warm (or the gate) refused."""
    from ..lsp import lifecycle as gateway_lifecycle
    from ..quality import lean_contracts

    state: dict = {"ready": False, "failed": None}

    def _run() -> None:
        try:
            gateway_lifecycle.start_gateway(workspace)
        except Exception as e:  # noqa: BLE001 — surfaced via the flag
            state["failed"] = f"{type(e).__name__}: {e}"
            return
        # Framework⇄Lean contract gate (task #12): a red contract
        # means every proving spawn would burn budget against a broken
        # probe/parser. The warm workers themselves are usually what a
        # red contract indicts — kill the gateway so retries can't
        # reuse them.
        if not lean_contracts.check_on_startup(workspace):
            gateway_lifecycle.kill_current_gateway()
            state["failed"] = "lean interface-contract gate red"
            return
        state["ready"] = True

    threading.Thread(target=_run, name="gateway-warm",
                     daemon=True).start()
    return state
