"""Subscription-quota truth sources.

Two materials, because the providers differ in kind and the framework
refuses to pretend otherwise:

  - AN ENDPOINT to ask — api.anthropic.com/api/oauth/usage. Live, and
    answerable BEFORE spending anything. `usage_endpoint=True` declares
    it; claude is the only one.
  - A LEDGER the provider already wrote — codex appends `rate_limits`
    to its own rollout once per turn. `usage_from_session_log=True`
    declares it. Nothing can be known before the first spawn of a
    window, and every reading carries the age of the spawn that made
    it; `session_log_usage` therefore returns `measured_at` alongside,
    and a consumer that drops it is publishing a stale number as a live
    one.

Consumers:

  - `serve/run.py` — UI meter shape (five_hour/seven_day/scoped dicts,
    memoized); keeps its own parsing on top of `fetch_usage`, and reads
    `session_log_usage` for the providers that have no endpoint.
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
from typing import Callable

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


#: Providers whose usage can be READ BACK off a ledger they wrote
#: themselves. Wired here only if the declaration says they write one,
#: and `session_log_usage` reads the DECLARATION, never the name — the
#: same rule, for the same reason, as `core.quota._RESET_SOURCES`: the
#: alternative is `if provider == "codex"` in the console, which is the
#: branch-per-backend `llm/capabilities` exists to stop.
_SESSION_LOG_SOURCES: "dict[str, Callable[[Path], dict | None]]" = {}


def _load_session_log_sources() -> None:
    """Lazy, like the reset sources: a provider module pulls in its CLI
    helpers and this module is imported by paths that must not."""
    if _SESSION_LOG_SOURCES:
        return
    from ..llm import codex_cli as _codex
    _SESSION_LOG_SOURCES["codex"] = _codex.latest_rate_limits


def session_log_usage(workspace: "Path | str") -> "list[dict]":
    """One entry per provider that keeps its own usage ledger, newest
    reading each, normalised for a meter.

    ```
    {"provider": "codex", "plan": "pro", "measured_at": <epoch>,
     "reached": None,
     "windows": [{"minutes": 10080, "utilization": 8.0,
                  "resets_at": <epoch|None>}]}
    ```

    `utilization` is a PERCENT, matching the endpoint's scale so one
    meter renders both. Windows are keyed by their own `window_minutes`
    rather than by position: codex reports a single weekly window on
    some accounts and 5-hour + weekly on others (measured 2026-08-26,
    both shapes in the same workspace), and a reader that assumed
    "primary = 5 hours" would mislabel the common case.

    A provider that declares the ledger but has no source wired is a
    LOUD gap, not a silent skip — the console would otherwise show
    "no live meter" forever and look like a provider fact.
    """
    from ..llm import capabilities as _caps
    out: "list[dict]" = []
    _load_session_log_sources()
    for name in sorted(_caps.CAPABILITIES):
        cap = _caps.capabilities_for(name)
        if not cap.usage_from_session_log:
            continue
        source = _SESSION_LOG_SOURCES.get(cap.name)
        if source is None:
            print(f"[quota] provider {cap.name!r} declares it writes its "
                  f"usage to its session log but core/usage_quota.py wires "
                  f"no reader for it — its meter stays blank", flush=True)
            continue
        try:
            read = source(Path(workspace))
        except Exception:  # noqa: BLE001 — a meter is garnish, never a failure
            read = None
        if not read:
            continue
        limits = read.get("limits") or {}
        windows = []
        for node in (limits.get("primary"), limits.get("secondary")):
            if not node or node.get("used_percent") is None:
                continue
            windows.append({
                "minutes": node.get("window_minutes"),
                "utilization": float(node["used_percent"]),
                "resets_at": node.get("resets_at"),
            })
        if not windows:
            continue
        out.append({
            "provider": cap.name,
            "plan": limits.get("plan_type"),
            "measured_at": read.get("measured_at"),
            "reached": limits.get("rate_limit_reached_type"),
            "windows": windows,
        })
    return out


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
