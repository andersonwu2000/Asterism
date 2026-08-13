"""Does the installed CLI still behave the way we measured it?

Two different questions, and the second is the one that has teeth.

1. VERSION. Each provider declares the CLI version its capability entry
   was verified against (`capabilities.tested_version`). A mismatch is a
   warning, never a block: the daemon must start on a machine whose
   vendor CLI self-updated overnight — both of ours do — and refusing
   would convert a paperwork gap into an outage.

2. BEHAVIOUR. Version equality cannot catch "same CLI version, changed
   server-side wording", and that is the most brittle thing in this
   system: nearly every quota and misconfig detector we own is a
   substring match against vendor prose, and `capabilities.marker_tables`
   is where each provider declares which tables those are. When one of
   them stops matching, nothing errors: a quota refusal becomes an
   ordinary failure, the backoff probes a three-hour wall, and the first
   symptom is a run that got nowhere. So the guard captures a small
   BEHAVIOUR SNAPSHOT and diffs it against the stored one, and it
   surfaces in the first seconds of daemon start instead of mid-run.

   READ `marker_coverage()` BEFORE TRUSTING THIS PARAGRAPH. It used to
   claim the guard covered every one of those tables, and it did not —
   `PROBES` exercises one table per provider and seven are declared.
   `claude_cli`'s quota prose sat unwatched from roughly 2026-07-03
   (the vendor sentence gained a word) to 2026-08-13 (a window died and
   the daemon exited calling a healthy provider broken), and the reason
   nobody noticed is that the guard reported green the whole time — for
   the OTHER table. Coverage is now declared per table and a test fails
   on anything unclassified.

The probes are chosen so they are FREE — no API call, no token, no
quota — and so that each one exercises a real marker rather than some
unrelated string:

  claude  `--resume <fixed nonexistent uuid> -p x`
          → prints "No conversation found with session ID: <uuid>" and
          exits. That IS `_STALE_SESSION_MARKER`, the sentinel the
          in-pipeline retry helper needs to re-mint a session without
          burning budget. The session does not exist locally, so the
          CLI cannot have talked to the API. Measured 2026-08-09: 2.5s.

  agy     `--model <invalid slug> -p x`
          → rc=1, "Error: invalid model selection ... is not recognized
          as a known model" (that is `_MISCONFIG_MARKERS[0]`) PLUS the
          full list of models the account may use. The model list is a
          bonus worth having: an entitlement change (a model retired, a
          tier downgraded) shows up here rather than as a mid-run
          `provider_misconfigured` storm. Measured 2026-08-09: 4.2s.

Both probes run in a background thread and every failure mode is a
warning. A guard that can stop a run is a new way for the run to die.

WHERE THE SNAPSHOT LIVES: `<workspace>/.asterism/provider_snapshots.json`.
`.asterism/` is the workspace's machine-generated runtime state (logs,
daemon markers, the generated spawn_guard settings) and is gitignored
in full. That is the right home because the snapshot is MACHINE-local,
not repo-local: it depends on which CLI version this box installed and
which models this account is entitled to, so committing it would make
every other machine diff against a stranger's entitlements. It is also
disposable — a missing file means "first run, record the baseline",
which is exactly the behaviour you want after a `git clean`.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from . import capabilities

#: Relative to the workspace. See the module docstring for why here.
SNAPSHOT_REL = Path(".asterism") / "provider_snapshots.json"

#: A syntactically valid UUID that has never been a session. Fixed so
#: the captured signature is stable across runs.
_DEAD_SESSION_UUID = "00000000-0000-4000-8000-000000000000"
#: A model slug no vendor will ever ship. Same reason.
_INVALID_MODEL_SLUG = "asterism-drift-probe-not-a-model"

_PROBE_TIMEOUT_SEC = 30


@dataclass(frozen=True)
class BehaviourProbe:
    """One free, API-call-free question and the marker it must exercise.

    `argv_tail`   appended to the resolved executable.
    `must_contain` a substring that MUST appear (lowercased compare) —
                  its absence is the drift we are hunting.
    `marker_source` where that substring is defined, so the warning can
                  point at the table to fix rather than at a symptom.
    `keep_line`   which output lines belong in the stored signature.
    `redact`      substitutions applied before storing, so the probe's
                  own arguments do not become part of the signature.
    """

    argv_tail: "tuple[str, ...]"
    must_contain: str
    marker_source: str
    keep_line: "object"
    redact: "tuple[tuple[str, str], ...]" = ()


def _claude_keep(line: str) -> bool:
    return "conversation" in line.lower() or "session id" in line.lower()


def _agy_keep(line: str) -> bool:
    low = line.lower()
    return (low.startswith("error:")
            or low.startswith("available models")
            or line.startswith("  "))


PROBES: "dict[str, BehaviourProbe]" = {
    "claude": BehaviourProbe(
        argv_tail=("--resume", _DEAD_SESSION_UUID, "-p", "x"),
        must_contain="no conversation found with session id",
        marker_source="Tooling.llm.claude_cli._STALE_SESSION_MARKER",
        keep_line=_claude_keep,
        redact=((_DEAD_SESSION_UUID, "<uuid>"),),
    ),
    "antigravity": BehaviourProbe(
        argv_tail=("--model", _INVALID_MODEL_SLUG, "-p", "x"),
        must_contain="invalid model selection",
        marker_source="Tooling.llm.antigravity_cli._MISCONFIG_MARKERS",
        keep_line=_agy_keep,
        redact=((_INVALID_MODEL_SLUG, "<slug>"),),
    ),
}


# ─── Which declared marker table is covered by what ───────────────────
#
# The docstring above promised this guard watches every quota and
# misconfig detector we own. It did not. `PROBES` exercises ONE table
# per provider, `capabilities.marker_tables` declares seven, and the
# five in between were watched by nothing — including
# `claude_cli`'s quota prose, which stopped matching around 2026-07-03
# (the CLI's sentence gained the word "session") and was not noticed
# until 2026-08-13, when a window died and the daemon exited calling a
# healthy provider broken.
#
# Nothing here probes anything new. What it does is make SILENCE
# IMPOSSIBLE: every declared table must say which of three kinds of
# coverage it has, and `test_provider_drift_guard.py` fails if one is
# unclassified. A table nobody watches is now a table that says so.
#
# The three kinds are not a quality ranking of the tables; they are a
# statement about what the world lets us check for free:

#: Pinned against a REAL captured sample of the vendor's output. Not a
#: live probe — it cannot notice a change made this morning — but it
#: cannot rot into agreeing with itself either, which is how the
#: hand-written May wording survived: the marker and the test that
#: exercised it were both written from the same guess.
COVERED_BY_CORPUS: "dict[str, str]" = {
    "Tooling.llm.claude_cli._QUOTA_PROSE_RE":
        "tests/test_quota_refusal.py — the 2026-08-13 five-hour refusal "
        "copied verbatim out of .attempts/9006e09d-…/_spawn.stderr, "
        "prose and rate_limit_event both",
}

#: No free probe and no captured sample. Each entry states WHY, and what
#: would close it — an honest gap beats a probe that exercises some
#: unrelated string and reports green.
UNVERIFIED: "dict[str, str]" = {
    "Tooling.llm.antigravity_cli._QUOTA_MARKERS":
        "a quota refusal cannot be triggered for free — it requires "
        "actually spending the account's window. Closes the day one is "
        "captured: keep the refusal text from the next agy quota death "
        "and pin it the way claude's is.",
    "Tooling.llm.antigravity_cli._TIMEOUT_MARKERS":
        "the vendor's own timeout wording; reproducing it means waiting "
        "out a real timeout on a real call. Same fix — capture one.",
    "Tooling.llm.codex_cli._QUOTA_MARKERS":
        "same as agy's, and codex's quota signal has a structured "
        "second channel (`rate_limits` in the rollout) that the prose "
        "is only a fallback for — so this table is the less load-"
        "bearing half. Still unwatched, still worth capturing.",
    "Tooling.llm.codex_cli._MISCONFIG_MARKERS":
        "no free probe wired yet. Unlike the two above this one IS "
        "cheaply probeable — an invalid `--model` slug should do for "
        "codex what it already does for agy — so this is a gap in the "
        "PROBES table, not in the world.",
}


def marker_coverage() -> "dict[str, str]":
    """Every declared marker table → how it is watched.

    `live-probe` / `corpus` / `unverified`. Built by asking
    `capabilities` what exists rather than by listing tables here: a
    second list of the same names is the thing this whole exercise is
    about."""
    by_probe = {p.marker_source for p in PROBES.values()}
    out: "dict[str, str]" = {}
    for caps in capabilities.CAPABILITIES.values():
        for dotted in caps.marker_tables:
            if dotted in by_probe:
                out[dotted] = "live-probe"
            elif dotted in COVERED_BY_CORPUS:
                out[dotted] = "corpus"
            elif dotted in UNVERIFIED:
                out[dotted] = "unverified"
            else:
                out[dotted] = "UNCLASSIFIED"
    return out


def resolve_executable(provider: str) -> "str | None":
    """Launchable path for a provider's CLI, or None if not installed."""
    name = capabilities.canonical(provider)
    if name == "antigravity":
        from .antigravity_cli import resolve_agy_executable
        return resolve_agy_executable()
    if name == "claude":
        # Not `shutil.which` — the installer's PATH edit only reaches
        # NEW sessions, and a bare which() here made the guard skip
        # every probe (`if not exe: continue`) on a machine whose CLI is
        # installed but off this process's PATH. The provider owns the
        # answer; see `claude_cli.resolve_claude_executable`.
        from .claude_cli import resolve_claude_executable
        return resolve_claude_executable()
    return shutil.which(name)


def _run(argv: "list[str]", cwd: "Path | None") -> "tuple[int, str]":
    from .envelope import spawn_env
    from ..core.process_group import no_window_creationflags
    r = subprocess.run(
        argv, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=_PROBE_TIMEOUT_SEC,
        cwd=str(cwd) if cwd else None,
        # The SAME environment a spawn gets (Part C's allowlist). A
        # probe run under the operator's full environment would answer
        # a question nobody asked — "does the CLI work for me?" rather
        # than "does it work for a spawn?".
        env=spawn_env(),
        creationflags=no_window_creationflags(),
    )
    return r.returncode, ((r.stdout or "") + "\n" + (r.stderr or ""))


def series(version: "str | None") -> "str | None":
    """`2.1.226` → `2.1`. The grain the capability record vouches at."""
    if not version:
        return None
    parts = str(version).strip().split(".")
    return ".".join(parts[:2]) if len(parts) >= 2 else str(version).strip()


def same_series(a: "str | None", b: "str | None") -> bool:
    """Do these two versions share a minor series?

    Exact equality was the rule until 2026-08-12, and it made this guard
    useless by making it permanent: claude and agy ship patches every
    few days, so the pin sat red for a week at a time and stopped being
    read. A guard nobody reads protects nothing.

    A patch bump is now silent and a minor bump still fires, because
    that is where the record's expensive facts — rc contract, permission
    semantics, stream shape, 15 probes on 2026-07-30 — actually move.
    What this does NOT do is catch a lie inside one series: on
    2026-08-09 `tested_version` went 1.1.8 → 1.1.11 on a bare
    `--version` while the facts stayed 1.1.8's, and this comparison
    would wave that through exactly as the old one did. The guard for
    THAT is the live marker probe below, which re-measures on every run
    and is deliberately left exact."""
    sa, sb = series(a), series(b)
    return sa is not None and sa == sb


def installed_version(provider: str) -> "str | None":
    """`<cli> --version`, or None when the CLI is absent / mute."""
    caps = capabilities.capabilities_for(provider)
    if not caps.version_argv:
        return None
    exe = resolve_executable(provider)
    if not exe:
        return None
    try:
        rc, out = _run([exe, *caps.version_argv], None)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if rc != 0:
        return None
    first = (out or "").strip().splitlines()
    if not first:
        return None
    # "2.1.224 (Claude Code)" / "1.1.11" -> the dotted number.
    m = re.search(r"\d+(?:\.\d+)+", first[0])
    return m.group(0) if m else first[0].strip()


def behaviour_snapshot(provider: str, *,
                       workspace: "Path | None" = None) -> "dict | None":
    """Run the provider's free probe and return its stored shape.

    None when there is no probe or the CLI is not installed. Never
    raises: a probe that cannot run is a warning, not a failure.
    """
    name = capabilities.canonical(provider)
    probe = PROBES.get(name)
    if probe is None:
        return None
    exe = resolve_executable(name)
    if not exe:
        return None
    try:
        rc, out = _run([exe, *probe.argv_tail], workspace)
    except (subprocess.TimeoutExpired, OSError) as exc:
        return {"rc": None, "marker_ok": False, "signature": [],
                "error": f"{type(exc).__name__}: {exc}"}
    for src, dst in probe.redact:
        out = out.replace(src, dst)
    keep = probe.keep_line
    lines = [ln.rstrip() for ln in out.splitlines() if ln.strip()]
    signature = [ln for ln in lines if keep(ln)]  # type: ignore[operator]
    return {
        "rc": rc,
        "marker_ok": probe.must_contain in out.lower(),
        "signature": signature,
    }


def _load(workspace: Path) -> dict:
    try:
        data = json.loads((workspace / SNAPSHOT_REL).read_text(
            encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _store(workspace: Path, data: dict) -> None:
    path = workspace / SNAPSHOT_REL
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    except OSError:
        pass


def check(workspace: Path,
          providers: "tuple[str, ...] | None" = None) -> "list[str]":
    """Compare every seated provider against its declaration + stored
    snapshot. Returns warning lines (empty = nothing drifted) and
    rewrites the snapshot file. NEVER raises, never blocks.

    `providers=None` means "whatever the seats say right now", so a
    workspace that never touches agy pays nothing for agy's probe.
    """
    if providers is None:
        providers = _seated_providers()
    stored = _load(workspace)
    warnings: "list[str]" = []
    fresh: dict = dict(stored)

    for provider in providers:
        caps = capabilities.capabilities_for(provider)
        if capabilities.warn_if_undeclared(
                provider, context="drift guard"):
            # Nothing to compare against; the undeclared warning has
            # already been printed by the one consumer that owns it.
            continue
        exe = resolve_executable(provider)
        if not exe:
            continue  # not installed here — `asterism doctor` says so
        entry: dict = {"checked_at": datetime.now(
            timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}

        version = installed_version(provider)
        entry["version"] = version
        if version and caps.tested_version and not same_series(
                version, caps.tested_version):
            warnings.append(
                f"{provider}: installed {version}, capabilities declared "
                f"against {caps.tested_version} — a different {series(version)}"
                f" series. Re-measure the FACTS this record vouches for "
                f"(rc contract, permission semantics, stream shape) and the "
                f"marker tables "
                f"{', '.join(caps.marker_tables) or '(none declared)'}, then "
                f"update `tested_version`.")

        snap = behaviour_snapshot(provider, workspace=workspace)
        if snap is None:
            fresh[provider] = entry
            continue
        entry["probe"] = snap
        probe = PROBES[capabilities.canonical(provider)]
        if not snap.get("marker_ok"):
            warnings.append(
                f"{provider}: the behaviour probe no longer produces "
                f"{probe.must_contain!r} (rc={snap.get('rc')}). That "
                f"string is {probe.marker_source} — the detector built "
                f"on it is now DEAD SILENT, which looks exactly like "
                f"'this never happens'. Probe output kept in "
                f"{SNAPSHOT_REL.as_posix()}.")
        prev = (stored.get(provider) or {}).get("probe")
        if prev and prev.get("signature") != snap.get("signature"):
            warnings.append(
                f"{provider}: behaviour snapshot CHANGED at the same "
                f"probe (version {version or '?'}).\n"
                f"  was: {prev.get('signature')}\n"
                f"  now: {snap.get('signature')}\n"
                f"  Wording or the available-model list moved under us; "
                f"every string-match detector for this provider "
                f"({', '.join(caps.marker_tables) or 'none declared'}) "
                f"is now suspect.")
        fresh[provider] = entry

    _store(workspace, fresh)
    return warnings


def _seated_providers() -> "tuple[str, ...]":
    """Canonical providers actually configured for a pipeline seat."""
    try:
        from ..core.dispatcher import _pipeline_seats
        seats = _pipeline_seats()
    except Exception:  # noqa: BLE001 — a guard must never block a run
        return ("claude",)
    out: "list[str]" = []
    for provider, _model in seats.values():
        name = capabilities.canonical(provider)
        if name not in out:
            out.append(name)
    return tuple(out) or ("claude",)


def run_and_report(workspace: Path) -> "list[str]":
    """`check` + print. Returns the warnings for tests / callers."""
    try:
        warnings = check(workspace)
    except Exception as exc:  # noqa: BLE001 — never blocks a run
        print(f"[provider-drift] guard itself failed "
              f"({type(exc).__name__}: {exc}) — continuing", flush=True)
        return []
    for w in warnings:
        print(f"[provider-drift] {w}", flush=True)
    if not warnings:
        print("[provider-drift] provider CLIs match their declarations",
              flush=True)
    return warnings


def start_background(workspace: Path) -> threading.Thread:
    """Run the guard off the startup path.

    Both probes are CLI cold starts (~2.5s + ~4.2s measured 2026-08-09),
    which is small but not free, and nothing about dispatch depends on
    the answer — so the daemon must not wait for it. The warnings land
    in the run log a few seconds in, beside the seat banner.

    Opt out with `ASTERISM_SKIP_PROVIDER_DRIFT_CHECK=1` (a machine with
    no CLIs installed, or a test harness that must not shell out).
    """
    if os.environ.get("ASTERISM_SKIP_PROVIDER_DRIFT_CHECK", "").strip():
        t = threading.Thread(target=lambda: None, daemon=True)
        t.start()
        return t
    t = threading.Thread(target=run_and_report, args=(workspace,),
                         name="provider-drift", daemon=True)
    t.start()
    return t
