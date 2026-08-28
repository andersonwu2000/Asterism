"""Diagnostics/health-check surfaces: `asterism status`, `asterism doctor`
[--cloud], `asterism library-verify`, `asterism review`, `asterism regress`,
`asterism knowledge-stats`, `asterism drift-check`, `asterism logs`,
`asterism config` — read-mostly reporting commands, icon-prefixed
OK/FAIL/WARN output. Split out of `Tooling/core/cli.py` (task A3,
move-only) into the `core/cli/` package; `Tooling/core/cli/__init__.py`
re-exports this module's public (and tested private) surface."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from ...state import db
from ...state import intent as intent_mod


def _status_payload(conn, problem: str) -> dict:
    """Pure data: collect status info for one problem. Shared between
    text and --json output paths so both see the same shape."""
    goals = [dict(r) for r in conn.execute(
        "SELECT id, slug, status, attempts, depth FROM goals "
        "WHERE problem = ? ORDER BY id", (problem,)).fetchall()]
    if not goals:
        return {"problem": problem, "exists": False}

    gids = [g["id"] for g in goals]
    ph_g = ",".join("?" * len(gids))
    strategies = [dict(r) for r in conn.execute(
        f"SELECT id, goal_id, status FROM strategies "
        f"WHERE goal_id IN ({ph_g}) ORDER BY id", gids).fetchall()]
    sids = [s["id"] for s in strategies]

    # Recent dead_attempts targeting this problem's goals or strategies.
    deads = []
    if gids and sids:
        ph_s = ",".join("?" * len(sids))
        deads = [dict(r) for r in conn.execute(
            f"SELECT id, target_kind, target_id, failure_reason, ts "
            f"FROM dead_attempts "
            f"WHERE (target_kind='Goal' AND target_id IN ({ph_g})) "
            f"   OR (target_kind='Strategy' AND target_id IN ({ph_s})) "
            f"ORDER BY id DESC LIMIT 50",
            list(gids) + list(sids)).fetchall()]
    elif gids:
        deads = [dict(r) for r in conn.execute(
            f"SELECT id, target_kind, target_id, failure_reason, ts "
            f"FROM dead_attempts "
            f"WHERE target_kind='Goal' AND target_id IN ({ph_g}) "
            f"ORDER BY id DESC LIMIT 50", gids).fetchall()]

    fr_counts: dict[str, int] = {}
    for d in deads:
        fr_counts[d["failure_reason"]] = fr_counts.get(
            d["failure_reason"], 0) + 1

    # Recent pipelines (filtered to this problem). pipelines.target_id is TEXT,
    # so compare against str() of our int ids.
    gid_strs = {str(g) for g in gids}
    sid_strs = {str(s) for s in sids}
    pipes_recent = [dict(r) for r in conn.execute(
        "SELECT id, kind, target_id, target_kind, status, outcome, "
        "started_at, finished_at FROM pipelines "
        "ORDER BY finished_at DESC LIMIT 50").fetchall()]
    pipes_recent = [
        p for p in pipes_recent
        if (p["target_kind"] == "Goal" and p["target_id"] in gid_strs)
        or (p["target_kind"] == "Strategy" and p["target_id"] in sid_strs)
    ][:10]

    queue_count = conn.execute(
        f"SELECT count(*) FROM queue "
        f"WHERE (kind!='Verify' AND target_id IN ({ph_g}))"
        + (f" OR (kind='Verify' AND target_id IN ({','.join('?'*len(sids))}))"
           if sids else ""),
        list(map(str, gids)) + list(map(str, sids)),
    ).fetchone()[0] if gids else 0

    return {
        "problem": problem,
        "exists": True,
        "goals": goals,
        "strategies": strategies,
        "live_strategies_count": sum(
            1 for s in strategies if s["status"] == "proposed"),
        "queue_count": queue_count,
        "recent_failure_reasons": fr_counts,
        "recent_pipelines": pipes_recent,
        "dead_attempts_window": len(deads),
    }


def cmd_status(args: argparse.Namespace) -> int:
    """Show one Problem's current state: goal table, live strategies,
    queue depth, recent dead_attempts grouped by failure_reason, recent
    pipelines. Replaces the ad-hoc `python -c 'import sqlite3; ...'`
    one-liners. `--json` emits the same data structure for piping."""
    conn = db.connect()
    db.init_schema(conn)
    payload = _status_payload(conn, args.problem)

    if args.json:
        print(json.dumps(payload, indent=2, default=str))
        return 0 if payload.get("exists") else 1

    if not payload.get("exists"):
        print(f"problem '{args.problem}' not initialized "
              f"(run `asterism init {args.problem}`)")
        return 1

    print(f"=== {payload['problem']} ===")
    print(f"\nGoals ({len(payload['goals'])}):")
    for g in payload["goals"]:
        print(f"  [{g['id']:>3}] depth={g['depth']} {g['status']:<11}"
              f" attempts={g['attempts']} {g['slug']}")
    print(f"\nLive strategies: {payload['live_strategies_count']} "
          f"of {len(payload['strategies'])} total")
    for s in payload["strategies"]:
        if s["status"] == "proposed":
            print(f"  [{s['id']:>3}] goal={s['goal_id']} {s['status']}")
    print(f"\nQueue depth: {payload['queue_count']}")

    fr = payload["recent_failure_reasons"]
    if fr:
        print(f"\nFailure reasons (last {payload['dead_attempts_window']} "
              f"dead_attempts):")
        for reason, count in sorted(fr.items(), key=lambda x: -x[1]):
            print(f"  {count:>3}  {reason}")

    pipes = payload["recent_pipelines"]
    if pipes:
        print(f"\nRecent pipelines (last {len(pipes)}):")
        for p in pipes:
            print(f"  {p['kind']:<8} {p['target_kind']}={p['target_id']:<3}"
                  f" {p['status']:<10} {p['outcome']}")
    return 0


def cmd_doctor_cloud(workspace: Path) -> int:
    """`asterism doctor --cloud` body — see `cmd_doctor`'s docstring for
    scope. Pure verdict-printing: every measurement lives in
    `cloud_doctor.py` so it can be unit-tested without a real Linux box;
    this function only prints and tallies. FAIL only counts against the
    exit code — WARN/SKIP are visible but do not fail the run, matching
    the desktop doctor's convention."""
    from .. import cloud_doctor as cd

    fails = 0

    def line(status: str, msg: str) -> None:
        nonlocal fails
        if status == "FAIL":
            fails += 1
        print(f"  [{status:>4}] {msg}")

    def emit(section: str, verdict: "dict[str, str]") -> None:
        line(verdict["verdict"], f"{section}: {verdict['detail']}")

    print("\n=== OS / architecture ===")
    emit("os", cd.os_arch())

    print("\n=== CPU / RAM / disk ===")
    emit("resources", cd.resources(workspace))

    print("\n=== cgroup v2 / memory cap ===")
    emit("cgroup", cd.cgroup_memory_cap())

    print("\n=== Python / Node ===")
    emit("python", cd.python_version())
    emit("node", cd.node_version())

    print("\n=== Provider CLIs (enabled seats only) ===")
    try:
        providers = cd.enabled_providers(workspace)
    except Exception as exc:  # noqa: BLE001 — a config read must not crash doctor
        line("SKIP", f"could not read enabled providers: {exc}")
        providers = []
    for name in providers:
        emit(name, cd.provider_presence(name))

    print("\n=== Lean toolchain ===")
    for exe, verdict in cd.lean_toolchain_presence().items():
        emit(exe, verdict)
    emit("leantar arch", cd.leantar_status())

    print("\n=== Ports (must be localhost-only) ===")
    for name, port in sorted(cd.CLOUD_PORTS.items(), key=lambda kv: kv[1]):
        emit(f"{name} :{port}", cd.port_status(port))

    print()
    print(f"=== Summary: {fails} FAIL ===" if fails else
          "=== Summary: all checks passed (some WARN/SKIP OK) ===")
    return 0 if fails == 0 else 1


def cmd_doctor(args: argparse.Namespace) -> int:
    """Pre-flight diagnostic. Checks the toolchain (claude / gemini /
    lake), the Asterism.yaml config, every initialized Problem's
    intent, and on-disk state (`.attempts/` zombies + log retention).
    Output is icon-prefixed lines (`OK / FAIL / WARN`) the operator —
    or a future Claude session — can scan top to bottom.

    Exits 0 if every check is OK or WARN; 1 if any FAIL fired.

    `--cloud` swaps in a separate, narrower check set (Oracle ARM64
    readiness — `docs/internal/dev/oracle_arm64_cloud_readiness.md`
    P0#1/P1#6): OS/arch, CPU/RAM/disk, cgroup v2 visibility, python/
    node/provider presence, the Lean toolchain + leantar architecture,
    and the three well-known ports' bind posture. It does not run the
    desktop checks below (problems/.attempts/log retention are not
    cloud-readiness questions) and never starts a daemon or the shim."""
    if getattr(args, "cloud", False):
        return cmd_doctor_cloud(Path.cwd())

    import shutil
    import subprocess

    workspace = Path.cwd()
    fails = 0

    def line(status: str, msg: str) -> None:
        nonlocal fails
        if status == "FAIL":
            fails += 1
        print(f"  [{status:>4}] {msg}")

    print("\n=== External tools ===")
    # Claude CLI
    if shutil.which("claude"):
        try:
            r = subprocess.run(
                ["claude", "--version"],
                capture_output=True, text=True, timeout=10,
                encoding="utf-8", errors="replace",
            )
            v = (r.stdout or "").strip().splitlines()[0] if r.stdout else "?"
            line("OK", f"claude  {v}")
        except (subprocess.TimeoutExpired, OSError) as exc:
            line("FAIL", f"claude --version timed out or errored: {exc}")
    else:
        line("WARN", "claude CLI not on PATH (Claude provider unavailable)")

    # Antigravity CLI (`agy`) — the subscription-priced path to Gemini
    # models since Google cut the Gemini CLI's individual tiers off
    # (2026-06-18). Resolver probes the installer location first: the
    # PowerShell installer edits the USER PATH, which a daemon started
    # before the install never sees.
    from ...llm import antigravity_cli as _agy
    agy_exe = _agy.resolve_agy_executable()
    if agy_exe:
        try:
            r = subprocess.run(
                [agy_exe, "--version"],
                capture_output=True, text=True, timeout=15,
                encoding="utf-8", errors="replace",
            )
            v = (r.stdout or "").strip().splitlines()[0] if r.stdout else "?"
            line("OK", f"agy     {v}")
        except (subprocess.TimeoutExpired, OSError) as exc:
            line("FAIL", f"agy --version timed out or errored: {exc}")
        # The permission file is what makes the write fence real; without
        # it every tool falls to headless auto-deny and a spawn returns
        # SUCCESS having written nothing (see antigravity_cli.py).
        perms = _agy.permissions_path()
        if perms.is_file():
            line("OK", f"agy permissions: {perms}")
            # The closed shape (2026-07-30): capability comes from OUR
            # MCP server and nothing else. `command(*)` is what let an
            # agent-authored `python -c` loop pin a wake for 32 minutes;
            # `read_url` ungated is a route to the answer for a problem
            # whose solution is on the public web.
            try:
                _p = json.loads(perms.read_text(encoding="utf-8"))
                _al = set(_p.get("permissions", {}).get("allow") or [])
                _dn = set(_p.get("permissions", {}).get("deny") or [])
            except Exception:  # noqa: BLE001
                _al = _dn = set()
            for tok, where, why in (
                ("mcp(*)", _al, "the framework's tools are unreachable"),
                ("command(*)", _dn, "arbitrary shell is open"),
                ("read_url(*)", _dn, "outbound fetch is open"),
            ):
                if tok not in where:
                    line("WARN", f"agy permissions: {tok} not in "
                                 f"{'allow' if where is _al else 'deny'} — "
                                 f"{why}")
            if "command(*)" in _al:
                line("WARN", "agy permissions: command(*) is ALLOWED — "
                             "any shell command, hence any write and any "
                             "unbounded computation")
        else:
            line("WARN", f"agy permissions file missing ({perms}) — every "
                         f"tool call will be auto-denied in headless mode")
        mcfg = _agy.mcp_config_path()
        try:
            _srv = json.loads(mcfg.read_text(encoding="utf-8") or "{}")
            _has = "asterism_tools" in (_srv.get("mcpServers") or {})
        except Exception:  # noqa: BLE001
            _has = False
        if _has:
            line("OK", f"agy MCP tools registered: {mcfg}")
        else:
            line("WARN", f"agy MCP tools not registered in {mcfg} — the "
                         f"next agy spawn re-writes it (ensure_mcp_config)")
        # Which ACCOUNT serves the run is decided silently (§2b): this
        # file outranks the Antigravity IDE session, so its presence can
        # quietly move the run onto a different subscription's quota.
        verdict, legacy = _agy.agy_identity()
        if verdict == _agy.IDENTITY_LEGACY_FILE:
            line("WARN", f"{legacy} exists — agy prefers it over the "
                         f"Antigravity IDE session, so THIS file's account "
                         f"pays for the run; rename it away to fall back to "
                         f"the IDE login")
        else:
            line("OK", "agy identity: Antigravity IDE session (no "
                       "oauth_creds.json overriding it)")
    else:
        line("WARN", "agy CLI not on PATH (Antigravity provider "
                     "unavailable)")

    # Provider capability declarations vs. what is actually installed.
    # The daemon runs this in the background at start; doctor runs it in
    # the foreground because doctor IS the place you look when a
    # detector has gone quiet. Warnings only — a version bump or a
    # reworded error never blocks a run.
    print("\n=== Provider capabilities ===")
    from ...llm import capabilities as _caps
    from ...llm import drift_guard as _drift
    for _prov in sorted(_caps.CAPABILITIES):
        _c = _caps.CAPABILITIES[_prov]
        line("OK", f"{_prov}: rc={_c.rc_contract} "
                   f"usage_endpoint={_c.usage_endpoint} "
                   f"stream_events={_c.stream_events} "
                   f"resume={_c.session_resume} "
                   f"enforcement={_c.enforcement_strength} "
                   f"tested@{_c.tested_version or '—'}")
    try:
        for _w in _drift.check(workspace):
            line("WARN", _w)
    except Exception as exc:  # noqa: BLE001 — a guard never fails doctor
        line("WARN", f"provider drift guard errored: {exc}")

    # Lake (Lean build tool)
    if shutil.which("lake"):
        try:
            r = subprocess.run(
                ["lake", "env", "lean", "--version"],
                capture_output=True, text=True, timeout=30,
                encoding="utf-8", errors="replace",
            )
            v = (r.stdout or "").strip().splitlines()[0] if r.stdout else "?"
            line("OK", f"lake env lean  {v}")
        except (subprocess.TimeoutExpired, OSError) as exc:
            line("FAIL", f"lake env lean errored: {exc}")
    else:
        line("FAIL", "lake not on PATH — cannot build Lean (mandatory)")

    # Asterism.yaml
    print("\n=== Asterism.yaml ===")
    cfg_path = workspace / "Asterism.yaml"
    if not cfg_path.exists():
        line("WARN", f"{cfg_path.name} absent — using built-in defaults "
                     f"(see Tooling/core/config.py for keys)")
    else:
        try:
            from .. import config as _config
            _config._reset_cache()
            data = _config.load(workspace)
            keys = []
            for top in ("dispatch", "builder", "backward"):
                if top in data and isinstance(data[top], dict):
                    keys.append(f"{top}({len(data[top])})")
            line("OK", f"{cfg_path.name}: " + ", ".join(keys)
                       if keys else f"{cfg_path.name}: empty / no known sections")
        except Exception as exc:
            line("FAIL", f"{cfg_path.name} parse error: {exc}")

    # Problems
    print("\n=== Problems ===")
    conn = db.connect()
    db.init_schema(conn)
    rows = conn.execute(
        "SELECT name FROM problems ORDER BY name"
    ).fetchall()
    if not rows:
        line("WARN", "no problems initialized — run `asterism init <p>`")
    for r in rows:
        name = r["name"]
        pintent = intent_mod.read(conn, name)
        if pintent is None or not pintent.charter.strip():
            line("FAIL", f"{name}: no charter — the top group's goal is "
                         f"empty (re-init from problem.json, or set it "
                         f"via `asterism charter`)")
            continue
        if not intent_mod.seed_path(workspace, name).exists():
            line("WARN", f"{name}: problem.json missing — reset would "
                         f"be unrecoverable (any charter/word/settings "
                         f"write regenerates it)")
        # Root goal status
        root = conn.execute(
            "SELECT id, status, attempts FROM goals "
            "WHERE problem = ? AND slug = 'main'", (name,)
        ).fetchone()
        if root:
            line("OK", f"{name}: root goal id={root['id']} "
                       f"status={root['status']} attempts={root['attempts']}")
        else:
            line("WARN", f"{name}: registered but no root goal "
                         f"(re-run `asterism init {name}`)")

    # Filesystem state
    print("\n=== Filesystem state ===")
    attempts_dir = workspace / ".attempts"
    if attempts_dir.exists():
        n = sum(1 for _ in attempts_dir.iterdir())
        if n > 5:
            line("WARN", f".attempts/ has {n} dirs — likely zombies, "
                         f"`rm -rf .attempts/` after killing daemon")
        elif n:
            line("OK", f".attempts/ has {n} dir(s) — possibly live or recent")
        else:
            line("OK", ".attempts/ empty")
    else:
        line("OK", ".attempts/ does not exist (clean state)")

    log_dir = workspace / LOG_DIR
    if log_dir.exists():
        logs = list(log_dir.glob("*.log"))
        total = sum(p.stat().st_size for p in logs) if logs else 0
        line("OK", f".asterism/logs/  {len(logs)} file(s), "
                   f"{total // 1024} KB")

    print()
    print(f"=== Summary: {fails} FAIL ===" if fails else
          "=== Summary: all checks passed (some WARN OK) ===")
    return 0 if fails == 0 else 1


def _library_consistency_findings(conn, workspace: Path
                                  ) -> "list[tuple[str, str]]":
    """DB <-> disk consistency over the *placed* decl set (v18: the DB IS
    the index — the former INDEX.md three-way checks I3/I4 are structurally
    impossible and retired).

    "Placed" = `library_decls.lifecycle IN ('migrated','cleaned')` — exactly
    the harvested set. 'cited'/'dropped'/'classified' decls are NOT placed
    (no file contribution), so they never participate. Mirrors the
    problem-side recovery orphan-sweep, but for `Library/`.

    Printer-free on purpose: returns `[(status, message), ...]` with status in
    {OK, WARN, FAIL} so the caller prints/exits and tests assert on findings.
    Severity rationale:
      - DB row -> missing file / orphan disk file: hard breaks (a citer is
        misled, or a file nothing owns lingers) -> FAIL.
      - bridged marker set but no placed decls: stale marker -> FAIL.
      - placed decls but not yet bridged: legit mid-flight -> WARN."""
    out: "list[tuple[str, str]]" = []
    lib = workspace / "Library"

    placed = conn.execute(
        "SELECT problem, target_name, target_file, slug, lifecycle "
        "FROM library_decls WHERE lifecycle IN ('migrated','cleaned')"
    ).fetchall()
    db_files = {r["target_file"] for r in placed if r["target_file"]}
    db_by_problem: "dict[str, set[tuple[str, str]]]" = {}
    for r in placed:
        name = r["target_name"] or r["slug"]
        db_by_problem.setdefault(r["problem"], set()).add(
            (name, r["target_file"] or "?"))

    disk_files = {p.relative_to(workspace).as_posix()
                  for p in lib.rglob("*.lean")}

    # I1 — every DB-placed file exists on disk.
    missing = sorted(f for f in db_files if f not in disk_files)
    for f in missing:
        out.append(("FAIL", f"DB places a decl in a missing file: {f}"))
    if not missing:
        out.append(("OK", f"{len(db_files)} DB-placed file(s) present on disk"))

    # I2 — every on-disk Library file is owned by a placed DB decl (orphan).
    orphans = sorted(f for f in disk_files if f not in db_files)
    for f in orphans:
        out.append(("FAIL", f"orphan Library file (no placed DB decl): {f}"))
    if not orphans:
        out.append(("OK", f"{len(disk_files)} on-disk file(s) all DB-owned"))

    # I3 — bridged marker <-> placed-set agreement (was: INDEX section vs
    # DB; the marker is now `problems.library_bridged_at`).
    bridged = {str(r["name"]) for r in conn.execute(
        "SELECT name FROM problems WHERE library_bridged_at IS NOT NULL")}
    for prob in sorted(bridged | set(db_by_problem)):
        if prob in bridged and prob not in db_by_problem:
            out.append(("FAIL", f"{prob}: bridge marker set but no placed "
                                f"DB decls (stale marker)"))
        elif prob not in bridged:
            out.append(("WARN", f"{prob}: {len(db_by_problem[prob])} placed "
                                f"decl(s) but not bridged yet (mid-flight?)"))
        else:
            out.append(("OK", f"{prob}: bridged, {len(db_by_problem[prob])} "
                              f"placed decl(s)"))

    # I5 — a CLEANED file should carry no `import Mathlib` umbrella. decide
    # minimises imports mechanically (`#import_bumps`); a surviving umbrella is
    # the rare degraded fallback (the linter could not produce a buildable set)
    # — non-idiomatic and rejected by a mathlib PR. WARN, not FAIL: the file
    # still builds, so this surfaces the defect without blocking the gate.
    # 'migrated'-but-not-'cleaned' files legitimately still carry it (mid-flight).
    cleaned_files = sorted({r["target_file"] for r in placed
                            if r["target_file"] and r["lifecycle"] == "cleaned"})
    umbrella = []
    for f in cleaned_files:
        try:
            txt = (workspace / f).read_text(encoding="utf-8")
        except OSError:
            continue
        if any(ln.strip() == "import Mathlib" for ln in txt.splitlines()):
            umbrella.append(f)
    for f in umbrella:
        out.append(("WARN", f"cleaned file keeps the `import Mathlib` umbrella "
                            f"(decide import-min degraded to fallback): {f}"))
    if cleaned_files and not umbrella:
        out.append(("OK", f"{len(cleaned_files)} cleaned file(s) carry precise "
                          f"imports (no `import Mathlib` umbrella)"))
    return out


def cmd_library_verify(args: argparse.Namespace) -> int:
    """Whole-Library coherence gate (P1). Two mechanical checks, no agent:

      (B) DB <-> disk consistency over the placed decl set — orphan
          files, DB rows pointing at missing files, stale bridge markers.
          Mirrors the problem-side recovery orphan-sweep.
      (A) `lake build Library` — the whole placed Library compiles together.
          The per-file / per-problem bridge gates only ever see ONE problem's
          files, so a cross-problem breakage is invisible to them; this is the
          missing whole-Library view, and the precondition for any future
          Library rewrite (cross-problem rewire): you cannot safely edit a
          cross-cited shared lemma without proving every downstream consumer
          still builds.

    Output is icon-prefixed `[OK/FAIL/WARN]` lines (same shape as `doctor`).
    Exit 0 if every check is OK/WARN; 1 if any FAIL. `--no-build` runs the
    fast consistency-only pass (skips A)."""
    import shutil
    import subprocess

    workspace = Path.cwd()
    fails = 0

    def line(status: str, msg: str) -> None:
        nonlocal fails
        if status == "FAIL":
            fails += 1
        print(f"  [{status:>4}] {msg}")

    if not (workspace / "Library").exists():
        print("Library/ absent — nothing to verify")
        return 0

    print("\n=== Consistency (DB <-> disk) ===")
    conn = db.connect()
    db.init_schema(conn)
    for status, msg in _library_consistency_findings(conn, workspace):
        line(status, msg)

    if args.no_build:
        print("\n=== Whole-Library build: SKIPPED (--no-build) ===")
    else:
        print("\n=== Whole-Library build (`lake build Library`) ===")
        if not shutil.which("lake"):
            line("FAIL", "lake not on PATH — cannot build Library")
        else:
            try:
                r = subprocess.run(
                    ["lake", "build", "Library"],
                    cwd=str(workspace), capture_output=True, text=True,
                    timeout=args.build_timeout,
                    encoding="utf-8", errors="replace",
                )
                if r.returncode == 0:
                    line("OK", "lake build Library succeeded")
                else:
                    # Surface the REAL Lean errors, not lake's terminal
                    # "error: build failed" summary: scan both streams for
                    # `error:` lines (the unresolved-reference / type errors a
                    # cross-problem breakage shows up as), and only fall back
                    # to the tail when none are present.
                    both = ((r.stdout or "") + "\n" + (r.stderr or "")).splitlines()
                    errs = [ln.strip() for ln in both
                            if "error:" in ln and "build failed" not in ln]
                    shown = errs[:5] or [ln.strip() for ln in both
                                         if ln.strip()][-5:]
                    snippet = " | ".join(shown)[:800]
                    line("FAIL", f"lake build Library failed "
                                 f"(rc={r.returncode}): {snippet or '(no output)'}")
            except subprocess.TimeoutExpired:
                line("FAIL", f"lake build Library timed out "
                             f"(>{args.build_timeout}s)")
            except OSError as exc:
                line("FAIL", f"lake build Library errored: {exc}")

    print()
    print(f"=== Summary: {fails} FAIL ===" if fails else
          "=== Summary: all checks passed (some WARN OK) ===")
    return 0 if fails == 0 else 1


def cmd_review(args: argparse.Namespace) -> int:
    """anchor+claim review surface (docs/internal/archive/anchor_claim_design.md).

    For every goal the Strategist marked `is_deliverable=1` (optionally
    scoped by `problem`), compute its kernel anchor closure and present
    the anchors (defs the human must vouch for) + claims (lemmas the
    closure rests on), partitioned. Reject an entry with
    `asterism reject <decl>` (Phase 3).

    Read-only. Needs the gateway (reused if already warm; else warmed —
    slow on a cold Mathlib cache). Exit 0 always (a review, not a gate);
    deliverables whose closure could not be computed print a WARN."""
    from ...quality import review as review_mod

    workspace = Path.cwd()
    conn = db.connect()
    db.init_schema(conn)
    scope = getattr(args, "problem", None)
    fresh = bool(getattr(args, "fresh", False))
    # Snapshot-first (charter §5-4): the Ingest commit stored the closure
    # while the gateway was warm; reading it costs nothing. --fresh (or a
    # problem never snapshotted) recomputes live and refreshes the store.
    data = None
    snap_note = ""
    if scope and not fresh:
        snap = review_mod.load_review_snapshot(conn, scope)
        if snap is not None:
            data, at = snap
            snap_note = (f"(snapshot from {at[:19]} — "
                         f"`--fresh` recomputes)")
    if data is None:
        data = review_mod.review_data(conn, workspace, problem=scope)
        if scope and data["deliverables"]:
            db.set_review_snapshot(
                conn, scope, json.dumps(data, ensure_ascii=False))

    if not data["deliverables"]:
        conn.close()
        where = f" for '{scope}'" if scope else ""
        print(f"no deliverables{where} (Strategist marks them via "
              f"is_deliverable; none set yet)")
        return 0
    conn.close()

    def render(items: list[dict], head: str) -> None:
        if not items:
            return
        print(f"    {head}")
        for c in sorted(items, key=lambda x: x["name"]):
            mod = c.get("module") or "<local>"
            print(f"      - {c['name']}   ({mod})")

    print(f"\n=== anchor+claim review: {scope or 'all problems'} "
          f"{snap_note}===")
    for d in data["deliverables"]:
        if not d["ok"]:
            print(f"\n▸ {d['fq']}  [WARN] closure unavailable: {d['error']}")
            continue
        print(f"\n▸ {d['fq']}  [{d['kind']}]   "
              f"(module {d['module'] or '<local>'})")
        if d["paper"]:
            print(f"    {d['paper']}")
        if not d["anchors"] and not d["claims"]:
            print("    (no pending anchors — statement rests entirely on "
                  "Mathlib ∪ Library)")
        render(d["anchors"], "anchors (defs you must vouch for):")
        render(d["claims"], "claims (lemmas the closure rests on):")
        if d["folded"]:
            print(f"      (+{d['folded']} compiler-generated companions "
                  f"folded into their parent inductive)")

    print(f"\n=== {len(data['deliverables'])} deliverable(s), "
          f"{data['union_count']} distinct pending anchor(s)/claim(s) ===")
    return 0


# review_data / _deliverable_paper_line moved to Tooling/quality/review.py
# (charter §5-4): the Strategist's Ingest-commit snapshot hook needs them,
# and pipeline code must not import the CLI entrypoint layer.


def cmd_regress(args: argparse.Namespace) -> int:
    """Regression-manifest report (task #8): compare the tracked
    `Benchmarks/proved_manifest.jsonl` against the CURRENT workspace.
    RESET/PARTIAL lines are re-verification CANDIDATES (resets are a
    normal workflow), DRIFT = not re-verified since a toolchain bump.
    Always exits 0 — this is a report, not a gate."""
    from ...state import regress
    workspace = Path.cwd()
    conn = db.connect()
    try:
        findings = regress.report(conn, workspace)
    finally:
        conn.close()
    if not findings:
        print("regress: manifest empty — nothing recorded yet")
        return 0
    icons = {"OK": "[OK]  ", "RESET": "[RESET]", "PARTIAL": "[PART] ",
             "DRIFT": "[DRIFT]"}
    for status, msg in findings:
        print(f"{icons.get(status, status)} {msg}")
    n = sum(1 for s, _ in findings if s != "OK")
    print(f"regress: {len(findings)} recorded problem(s), "
          f"{n} re-verification candidate(s)")
    return 0


def cmd_knowledge_stats(args: argparse.Namespace) -> int:
    """Offline knowledge-layer telemetry (read-only; safe alongside a
    running daemon). See Tooling/quality/knowledge_stats.py for metric
    semantics — the presearch citation number is a drift canary, NOT
    the value metric."""
    import sqlite3 as _sq
    from ...core import config as _config
    from ...quality import knowledge_stats
    workspace = _config.resolve_workspace(getattr(args, "workspace", None))
    conn = _sq.connect(
        f"file:{(workspace / 'asterism.db').as_posix()}?mode=ro", uri=True)
    conn.row_factory = _sq.Row
    print(knowledge_stats.render(conn, workspace,
                                 problem_like=args.problem))
    return 0


def cmd_drift_check(args: argparse.Namespace) -> int:
    """Consistency gate, two layers (run with the daemon STOPPED — a
    mid-tick snapshot can transiently trip the tree predicates):
      1. DB<->file (`proof_store.inventory`): orphan proof files, missing
         files, proved-with-sorry.
      2. Tree-level DB (`consistency.consistency_sweep`, task #11): the
         crash-window audit's predicates — interrupted-cascade leftovers
         no single-row reconciler sees (succeeded strategy under an
         unproved goal, live strategy under a terminal goal, unreachable
         alive goals, pending revivals).
    Exit 0 if consistent, 1 on any finding. `--scope` limits (LIKE)."""
    from ...state import consistency, proof_store
    workspace = Path.cwd()
    conn = db.connect()
    scope = getattr(args, "scope", None)
    try:
        rep = proof_store.inventory(conn, workspace, scope=scope)
        sweep = consistency.consistency_sweep(conn, scope=scope)
    finally:
        conn.close()
    # (The old layer-3 frontmatter-vs-DB drift check retired with
    # Manifest.md at v40: problem.json is written only by the intent
    # chokepoint that also writes the DB, so there is no second author
    # to drift against.)
    for rel in rep.orphan_files:
        print(f"  [FAIL] orphan proof file (no DB row): {rel}")
    for rel in rep.missing_files:
        print(f"  [FAIL] missing proof file (row past 'open'): {rel}")
    for rel in rep.proved_with_sorry:
        print(f"  [FAIL] proved goal's file carries `sorry`: {rel}")
    sweep_bad = 0
    for cat, rows in sweep.items():
        for r in rows:
            sweep_bad += 1
            print(f"  [FAIL] {cat}: {r}")
    ok = rep.ok() and sweep_bad == 0
    print(f"  [{'  OK' if ok else 'FAIL'}] {rep.summary()}"
          + (f"; tree sweep: {sweep_bad} finding(s)" if sweep_bad
             else "; tree sweep clean"))
    return 0 if ok else 1


def cmd_logs(args: argparse.Namespace) -> int:
    """List / tail framework run logs from `.asterism/logs/`.
    Default: list with sizes, mtime, sorted newest first.
    `--tail N`: print the last N lines of the most recent log.
    """
    workspace = Path.cwd()
    log_dir = workspace / LOG_DIR
    if not log_dir.exists():
        print(f"no log dir at {log_dir}")
        return 0
    logs = sorted(log_dir.glob("*.log"),
                  key=lambda p: p.stat().st_mtime, reverse=True)
    if not logs:
        print(f"no logs in {log_dir}")
        return 0
    if args.tail:
        latest = logs[0]
        print(f"# {latest.name}  ({latest.stat().st_size:,} bytes)")
        with latest.open("r", encoding="utf-8", errors="replace") as f:
            tail_lines = f.readlines()[-args.tail:]
        sys.stdout.writelines(tail_lines)
        return 0
    print(f"# {log_dir} ({len(logs)} logs)")
    for p in logs:
        st = p.stat()
        ts = datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M")
        print(f"  {st.st_size:>8,} B  {ts}  {p.name}")
    return 0


def cmd_config(args: argparse.Namespace) -> int:
    """Print the resolved Asterism config — what `dispatch.*`,
    `builder.*`, `backward.*` actually evaluate to right now (env >
    Asterism.yaml > legacy env > built-in default). Eliminates
    "what's actually active?" confusion when env vars + yaml + defaults
    interact.
    """
    from .. import config as _cfg
    from ...llm import claude_cli as _cc
    rows = [
        ("dispatch.pool",
         _cfg.get("dispatch.pool", env_var="ASTERISM_POOL", default=12, cast=int)),
        ("dispatch.budget_sec",
         _cfg.get("dispatch.budget_sec", env_var="ASTERISM_BUDGET_SEC",
                  default=1800, cast=int)),
        ("dispatch.shelve_threshold",
         _cfg.get("dispatch.shelve_threshold",
                  env_var="ASTERISM_SHELVE_THRESHOLD", default=8, cast=int)),
        ("formalizer.model", _cc.resolve_model("formalizer")),
    ]
    for k, v in rows:
        print(f"  {k:<30} = {v}")
    return 0
