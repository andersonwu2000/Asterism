"""Subscription-quota truth source — api.anthropic.com/api/oauth/usage.

Single home for the raw endpoint call (formerly private to
`serve/run.py`'s console meter). Two consumers with different needs:

  - `serve/run.py` — UI meter shape (five_hour/seven_day/scoped dicts,
    memoized); keeps its own parsing on top of `fetch_usage`.
  - `core/dispatcher.py` quota-wait — needs one judgment: "is the
    subscription verifiably exhausted right now, and until when?"
    That's `exhausted_until`.

Read-only against the user's own account; the token never appears in
any response or log.
"""
from __future__ import annotations

import json
import urllib.request
from datetime import datetime
from pathlib import Path

# A window counts as exhausted only near the hard ceiling. The probe is
# used to CONFIRM a quota hypothesis raised by failing spawns — a lower
# bar would make an unrelated breakage (broken exe at 80% utilization)
# masquerade as quota and put the daemon to sleep.
EXHAUSTED_UTILIZATION = 99.0


def fetch_usage() -> "dict | None":
    """One raw call. Separated for tests (monkeypatch me).

    Raises on any failure (no login file, expired token, offline,
    429) — callers decide whether that means "meter off" (serve) or
    "cannot confirm quota, keep the old failure path" (dispatcher).
    """
    creds_path = Path.home() / ".claude" / ".credentials.json"
    token = json.loads(creds_path.read_text(encoding="utf-8"))[
        "claudeAiOauth"]["accessToken"]
    req = urllib.request.Request(
        "https://api.anthropic.com/api/oauth/usage",
        headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=4) as resp:
        return json.loads(resp.read())


def _parse_reset(iso: "object") -> "float | None":
    if not iso:
        return None
    try:
        return datetime.fromisoformat(
            str(iso).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def exhausted_until(raw: "dict | None") -> "tuple[bool, float | None]":
    """(exhausted, deadline_epoch) across every window that gates spawns.

    Windows considered: five_hour, seven_day (percent `utilization`)
    and active weekly_scoped per-model limits (`percent`) — a scoped
    model cap blocks spawns just as hard as the global windows.

    `exhausted` = any window at/above EXHAUSTED_UTILIZATION.
    `deadline` = the LATEST `resets_at` among exhausted windows (quota
    is only usable again once every exhausted window has reset), or
    None when no exhausted window carries a parseable `resets_at`.
    """
    if not raw:
        return False, None
    walls: "list[tuple[float, float | None]]" = []
    for node in (raw.get("five_hour"), raw.get("seven_day")):
        if node and node.get("utilization") is not None:
            walls.append((float(node["utilization"]),
                          _parse_reset(node.get("resets_at"))))
    for lim in raw.get("limits") or []:
        if lim.get("kind") == "weekly_scoped" and lim.get("is_active"):
            walls.append((float(lim.get("percent") or 0.0),
                          _parse_reset(lim.get("resets_at"))))
    exhausted = [(u, r) for (u, r) in walls if u >= EXHAUSTED_UTILIZATION]
    if not exhausted:
        return False, None
    resets = [r for (_, r) in exhausted if r is not None]
    return True, (max(resets) if resets else None)
