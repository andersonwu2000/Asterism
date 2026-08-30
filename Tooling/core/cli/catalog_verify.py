"""`asterism catalog-verify` — the standing full cold build of a problem's
proof catalog (owner ruling 2026-08-30, task #231; stage one of the
kernel-replay end-game gate in `framework_backlog.md`).

The 2026-08-30 flagship olean rebuild was the first time union_closed's
4,828 proved bricks were cold-built together. It found bricks that do
not compile — an alias whose elaboration blows maxRecDepth, strategies
citing helper decls a promotion dropped, an import cycle closed by a
promotion — and no framework surface would ever have said so: the
verify-collapse design elaborates nothing at promotion and gates
integrity only at root.

This command builds every proof module of a problem through the lake
build lease (one lake at a time, `LEAN_NUM_THREADS` bounded), maps each
failing module back to its strategy / goal, reports, and records the
verdict in the degraded ledger. `--rollback` hands each culprit to the
existing `rollback_cascade_chain` — no new state: the culprit strategy
dies, its goal reopens, upstream re-verifies — and reopens strategy-less
bricks (Forward / alias) directly. It refuses to write while a daemon
owns the database.
"""
from __future__ import annotations

import argparse
import re
from dataclasses import dataclass, field
from pathlib import Path

from ...pipeline import _lake
from ...quality import verify as _verify
from ...state import db, transitions


@dataclass
class Failure:
    module: str
    goal_id: "int | None"
    strategy_id: "int | None"
    slug: str = ""
    first_error: str = ""


@dataclass
class Report:
    problem: str
    total: int
    failures: list[Failure] = field(default_factory=list)
    output: str = ""


def _build(workspace: Path, modules: list[str]) -> tuple[bool, str]:
    return _lake.lake_build_modules(workspace, modules)


def _rollback_cascade_chain(conn, workspace: Path, culprit: int) -> int:
    return _verify.rollback_cascade_chain(conn, workspace, culprit)


def _daemon_alive(workspace: Path) -> "int | None":
    """PID of a live daemon holding this workspace, else None."""
    pid_file = workspace / ".asterism" / "daemon.pid"
    try:
        first = pid_file.read_text(encoding="utf-8").split()[0]
        pid = int(first)
    except (OSError, ValueError, IndexError):
        return None
    from ..dispatcher.lock import _pid_alive
    return pid if _pid_alive(pid) else None


def _proof_modules(conn, workspace: Path, problem: str) -> list[str]:
    """The catalog = what the DB vouches for: every goal file and every
    succeeded strategy's scratch file of the problem that exists on disk.
    Stray `proofs/*.lean` the DB does not know (agent `new_*.lean`
    residue, dead-file gap in the backlog) are not bricks and are not
    built here."""
    rels: list[str] = []
    for r in conn.execute(
            "SELECT lean_path FROM goals WHERE problem = ? ORDER BY id", (problem,)):
        rels.append(str(r["lean_path"]))
    for r in conn.execute(
            "SELECT s.scratch_path FROM strategies s JOIN goals g ON g.id = s.goal_id"
            " WHERE g.problem = ? AND s.status = 'succeeded'"
            "   AND s.scratch_path IS NOT NULL ORDER BY s.id", (problem,)):
        rels.append(str(r["scratch_path"]))
    mods: list[str] = []
    for rel in rels:
        p = workspace / rel
        if not p.exists():
            continue
        mod = _lake.lean_path_to_module(workspace, p)
        if mod not in mods:
            mods.append(mod)
    return mods


_STRATEGY_MOD_RE = re.compile(r"\._strategy_(s?\d+|[A-Za-z0-9_]+)$")


def _attribute(conn, module: str) -> Failure:
    rel = module.replace(".", "/") + ".lean"
    st = conn.execute("SELECT id, goal_id FROM strategies WHERE scratch_path = ?"
                      " ORDER BY id DESC LIMIT 1", (rel,)).fetchone()
    if st is not None:
        g = conn.execute("SELECT slug FROM goals WHERE id = ?",
                         (int(st["goal_id"]),)).fetchone()
        return Failure(module, int(st["goal_id"]), int(st["id"]),
                       slug=str(g["slug"]) if g else "")
    g = conn.execute("SELECT id, slug FROM goals WHERE lean_path = ?", (rel,)).fetchone()
    if g is None:
        return Failure(module, None, None)
    win = conn.execute(
        "SELECT id FROM strategies WHERE goal_id = ? AND status = 'succeeded'"
        " ORDER BY id DESC LIMIT 1", (int(g["id"]),)).fetchone()
    return Failure(module, int(g["id"]), int(win["id"]) if win else None,
                   slug=str(g["slug"]))


def audit(conn, workspace: Path, *, problem: str) -> Report:
    mods = _proof_modules(conn, workspace, problem)
    rep = Report(problem=problem, total=len(mods))
    if not mods:
        return rep
    ok, out = _build(workspace, mods)
    rep.output = out or ""
    if not ok:
        first_lines = {}
        for ln in (out or "").splitlines():
            if ln.startswith("error:") and ".lean" in ln:
                m = _verify._BUILD_ERROR_PATH_RE.match(ln)
                if m:
                    mod = m.group(1).replace("\\", "/")[:-len(".lean")].replace("/", ".")
                    first_lines.setdefault(mod, ln)
        for mod in _verify.failing_modules_from_build_output(out or ""):
            f = _attribute(conn, mod)
            f.first_error = first_lines.get(mod, "")
            rep.failures.append(f)
    from .. import degraded
    if rep.failures:
        degraded.record(workspace, "catalog_verify",
                        f"{problem}: {len(rep.failures)} of {rep.total} proof "
                        f"module(s) do not cold-build")
    return rep


def rollback(conn, workspace: Path, rep: Report) -> int:
    """Hand every culprit to the cascade; reopen strategy-less bricks.
    Refuses while a daemon owns the database (the two would race)."""
    pid = _daemon_alive(workspace)
    if pid:
        raise RuntimeError(f"a daemon (pid {pid}) owns this database — stop it "
                           f"before --rollback (or run without it for the report)")
    n = 0
    done: set[int] = set()
    for f in rep.failures:
        if f.strategy_id is not None:
            if f.strategy_id in done:
                continue
            done.add(f.strategy_id)
            _rollback_cascade_chain(conn, workspace, f.strategy_id)
            n += 1
        elif f.goal_id is not None:
            g = db.get_goal(conn, f.goal_id)
            if g is not None and g["status"] == "proved":
                db.increment_goal_attempts(conn, f.goal_id)
                transitions.apply_goal_transition(
                    conn, f.goal_id, "open", event="catalog_verify_unbuildable")
                n += 1
    conn.commit()
    return n


def cmd_catalog_verify(args: argparse.Namespace) -> int:
    workspace = Path.cwd()
    conn = db.connect()
    problems = [args.scope] if args.scope else [
        str(r["name"]) for r in conn.execute("SELECT name FROM problems ORDER BY name")]
    worst = 0
    for problem in problems:
        rep = audit(conn, workspace, problem=problem)
        print(f"[catalog-verify] {problem}: {rep.total} module(s), "
              f"{len(rep.failures)} failing")
        for f in rep.failures:
            who = (f"s{f.strategy_id}" if f.strategy_id else "no strategy")
            print(f"  [FAIL] {f.module}  goal={f.goal_id} {f.slug} ({who})")
            if f.first_error:
                print(f"         {f.first_error[:200]}")
        if rep.failures and args.rollback:
            n = rollback(conn, workspace, rep)
            print(f"[catalog-verify] {problem}: {n} rollback(s) applied")
        worst = max(worst, 1 if rep.failures else 0)
    return worst
