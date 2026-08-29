"""The routine wake as an audit (owner design 2026-08-30).

A routine wake no longer decides. It rules on four criteria and writes
`verdict.json`; criteria 3 (does the Roadmap still need this line) and
4 (is this line converging) are ruled PER LINE, a line being the root
goal an Inject dispatched plus everything that grew under it. The
verdict is recorded in `routine_verdicts`; a fired finding stays
pending there until an action wake (`trigger_kind='routine_fired'`,
the batch-done conversation with the findings on top of its Context)
commits a batch that acts on every fired root. State, not payload:
the pending row is what seats the action wake, the same way an
unacknowledged Inject batch seats a batch-done wake.

What this module owns:
  * `in_flight_lines` — the roots this group has in flight, with the
    tallies the auditor rules on (the Context section and the
    coverage snapshot both read it);
  * the snapshot file `_audit_roots.json` (frozen at Context compile —
    a line that grows while the auditor thinks is not its omission);
  * `parse_verdict` / `coverage_report` — the server-side parse and the
    `validate_json` preview of the same facts;
  * `record_verdict` / `pending_fired_verdict` / `mark_acted`.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ...state import db

VERDICT_FILE = "verdict.json"
ROOTS_FILE = "_audit_roots.json"
CRITERIA = ("1", "2", "3", "4")
PER_LINE = ("3", "4")
TALLY_STATUSES = ("proved", "attempting", "open", "dead", "shelved",
                  "disproved", "pending_strategist_review")


# ------------------------------------------------------------ the lines

def in_flight_lines(conn: sqlite3.Connection, problem: str,
                    group_id: "int | None") -> "list[dict]":
    """One entry per root this group has in flight: an Inject whose
    outcome is still NULL and whose produced goal exists. Tallies count
    the root's descendants by status (`db.descendant_ids`)."""
    sql = ("SELECT d.id AS decision_id, d.batch_id, d.created_at,"
           " d.produced_goal_id, d.target_id, g.slug, g.status"
           " FROM strategist_decisions d"
           " JOIN goals g ON g.id = COALESCE(d.produced_goal_id, d.target_id)"
           " WHERE d.problem = ? AND d.decision_kind = 'Inject'"
           "   AND d.outcome IS NULL AND d.batch_id IS NOT NULL")
    args: list = [problem]
    if group_id is not None:
        sql += " AND d.group_id = ?"
        args.append(int(group_id))
    sql += " ORDER BY d.created_at, d.id"
    out: list[dict] = []
    seen: set[int] = set()
    now = datetime.now(timezone.utc)
    for r in conn.execute(sql, args):
        gid = int(r["produced_goal_id"] or r["target_id"])
        if gid in seen:
            continue
        seen.add(gid)
        kids = db.descendant_ids(conn, gid)
        tallies = {s: 0 for s in TALLY_STATUSES}
        if kids:
            marks = ",".join("?" * len(kids))
            for row in conn.execute(
                    f"SELECT status, COUNT(*) n FROM goals"
                    f" WHERE id IN ({marks}) GROUP BY status", list(kids)):
                if row["status"] in tallies:
                    tallies[row["status"]] = int(row["n"])
        try:
            born = datetime.fromisoformat(str(r["created_at"]))
            if born.tzinfo is None:
                born = born.replace(tzinfo=timezone.utc)
            age_days = (now - born).total_seconds() / 86400.0
        except ValueError:
            age_days = 0.0
        out.append({
            "goal_id": gid, "slug": str(r["slug"]), "status": str(r["status"]),
            "decision_id": int(r["decision_id"]),
            "batch_id": str(r["batch_id"]), "age_days": age_days,
            "descendants": len(kids), "tallies": tallies,
        })
    return out


def write_roots_snapshot(attempts_dir: Path, lines: "list[dict]") -> None:
    snap = [{"goal_id": ln["goal_id"], "slug": ln["slug"]} for ln in lines]
    (attempts_dir / ROOTS_FILE).write_text(
        json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")


def read_roots_snapshot(attempts_dir: Path) -> "list[dict] | None":
    p = attempts_dir / ROOTS_FILE
    if not p.exists():
        return None
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return obj if isinstance(obj, list) else None


def render_lines_section(lines: "list[dict]") -> "list[str]":
    """`## Lines in flight` — what criteria 3 and 4 are ruled on, one
    line per root. Post-mortems are lazy: `inspect({"decl": slug})`."""
    if not lines:
        return []
    out = ["## Lines in flight", "",
           "One line per root you dispatched and still have running — "
           "criteria 3 and 4 are ruled on EACH of these, by `goal_id`. "
           "Failure records per node: `inspect({\"decl\": \"<slug>\"})`.",
           ""]
    for ln in lines:
        t = ln["tallies"]
        out.append(
            f"- `{ln['slug']}` (goal_id {ln['goal_id']}, {ln['status']}; "
            f"batch `{ln['batch_id'][:8]}`, decision {ln['decision_id']}; "
            f"dispatched {ln['age_days']:.1f} d ago) — {ln['descendants']} "
            f"descendant(s): proved {t['proved']}, attempting "
            f"{t['attempting']}, open {t['open']}, dead {t['dead']}, "
            f"shelved {t['shelved']}, disproved {t['disproved']}, "
            f"pending review {t['pending_strategist_review']}")
    out.append("")
    return out


# ------------------------------------------------------------ the verdict

@dataclass(frozen=True)
class Finding:
    criterion: int
    goal_id: "int | None"
    slug: str
    reason: str


@dataclass
class Verdict:
    fired: "list[Finding]" = field(default_factory=list)
    clear: "list[Finding]" = field(default_factory=list)
    #: (criterion, goal_id) pairs the auditor never ruled on
    unaudited: "list[tuple[int, int]]" = field(default_factory=list)
    unknown: "list[tuple[int, int]]" = field(default_factory=list)
    duplicates: "list[tuple[int, int]]" = field(default_factory=list)

    @property
    def any_fired(self) -> bool:
        return bool(self.fired)

    def fired_roots(self) -> "list[int]":
        seen: list[int] = []
        for f in self.fired:
            if f.goal_id is not None and f.goal_id not in seen:
                seen.append(f.goal_id)
        return seen


def _split_line(s: str) -> "tuple[str, str] | None":
    """`"fired: why"` -> ("fired", "why"); None when not that shape."""
    if not isinstance(s, str):
        return None
    head, sep, rest = s.partition(":")
    verdict = head.strip().lower()
    if verdict not in ("clear", "fired"):
        return None
    return verdict, rest.strip()


def parse_verdict(text: str, snapshot: "list[dict]",
                  ) -> "tuple[Verdict | None, str]":
    """`(verdict, err)`; err non-empty = the file cannot be handed in
    (shape), and the corrective turn quotes it. Coverage gaps are NOT
    errors: a root the auditor did not rule on is `unaudited`, unknown
    roots are ignored, the first of duplicated entries stands
    (`validate_json` shows all three before the hand-in)."""
    try:
        obj = json.loads(text, strict=False)
    except ValueError as e:
        return None, f"verdict.json does not parse: {e}"
    if not isinstance(obj, dict) or not isinstance(obj.get("criteria"), dict):
        return None, "verdict.json must be an object with a `criteria` object"
    crit = {str(k): v for k, v in obj["criteria"].items()}
    roots = {int(s["goal_id"]): str(s.get("slug", "")) for s in snapshot}
    v = Verdict()
    for c in CRITERIA:
        if c not in crit:
            return None, f"criterion {c} is missing — every criterion gets a line"
    for c in ("1", "2"):
        entries = crit[c]
        if not isinstance(entries, list) or not entries:
            return None, f"criterion {c} must be a non-empty list of strings"
        for e in entries:
            sp = _split_line(e)
            if sp is None:
                return None, (f"criterion {c}: each line starts with "
                              f"`clear:` or `fired:` (got {e!r})")
            verdict, reason = sp
            if not reason:
                return None, (f"criterion {c}: a bare `{verdict}` — give the "
                              f"reason it holds for THIS proposal")
            (v.fired if verdict == "fired" else v.clear).append(
                Finding(int(c), None, "", reason))
    for c in PER_LINE:
        entries = crit[c]
        if not isinstance(entries, list):
            return None, (f"criterion {c} must be a list of "
                          f"{{goal_id, verdict, reason}} entries")
        ruled: set[int] = set()
        for e in entries:
            if not isinstance(e, dict):
                return None, f"criterion {c}: entries are objects (got {e!r})"
            try:
                gid = int(e.get("goal_id"))
            except (TypeError, ValueError):
                return None, f"criterion {c}: an entry has no integer goal_id"
            verdict = str(e.get("verdict", "")).strip().lower()
            reason = str(e.get("reason", "") or "").strip()
            if verdict not in ("clear", "fired"):
                return None, (f"criterion {c}, goal {gid}: verdict is "
                              f"`clear` or `fired` (got {verdict!r})")
            if not reason:
                return None, (f"criterion {c}, goal {gid}: a bare "
                              f"`{verdict}` — give the reason for this line")
            if gid not in roots:
                v.unknown.append((int(c), gid))
                continue
            if gid in ruled:
                v.duplicates.append((int(c), gid))
                continue
            ruled.add(gid)
            f = Finding(int(c), gid, roots[gid], reason)
            (v.fired if verdict == "fired" else v.clear).append(f)
        for gid in roots:
            if gid not in ruled:
                v.unaudited.append((int(c), gid))
    return v, ""


def coverage_report(obj: dict, snapshot: "list[dict]") -> "list[str]":
    """What `validate_json` tells the auditor before the hand-in: for
    criteria 3 and 4, which roots of the snapshot are missing, which
    appear twice, which are not in flight at all. Empty = covered."""
    notes: list[str] = []
    crit = obj.get("criteria") if isinstance(obj, dict) else None
    if not isinstance(crit, dict):
        return ["`criteria` object missing"]
    roots = {int(s["goal_id"]): str(s.get("slug", "")) for s in snapshot}
    for c in PER_LINE:
        entries = crit.get(c)
        if not isinstance(entries, list):
            notes.append(f"criterion {c}: not a list")
            continue
        seen: dict[int, int] = {}
        for e in entries:
            if isinstance(e, dict):
                try:
                    seen[int(e.get("goal_id"))] = seen.get(
                        int(e.get("goal_id")), 0) + 1
                except (TypeError, ValueError):
                    notes.append(f"criterion {c}: an entry has no goal_id")
        for gid, slug in roots.items():
            if gid not in seen:
                notes.append(f"criterion {c}: `{slug}` (goal_id {gid}) "
                             f"is in flight but not ruled on")
        for gid, n in seen.items():
            if gid in roots and n > 1:
                notes.append(f"criterion {c}: `{roots[gid]}` (goal_id {gid}) "
                             f"appears twice — the first entry stands")
            if gid not in roots:
                notes.append(f"criterion {c}: goal_id {gid} is not a line "
                             f"in flight — ignored")
    return notes


# ------------------------------------------------------------- the record

def record_verdict(conn: sqlite3.Connection, *, problem: str,
                   group_id: int, pipeline_id: str,
                   verdict: Verdict, raw: str) -> int:
    fired = [{"criterion": f.criterion, "goal_id": f.goal_id,
              "slug": f.slug, "reason": f.reason} for f in verdict.fired]
    unaudited = [{"criterion": c, "goal_id": g} for c, g in verdict.unaudited]
    cur = conn.execute(
        "INSERT INTO routine_verdicts (problem, group_id, pipeline_id,"
        " verdict_json, fired_json, unaudited_json, fired, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (problem, int(group_id), pipeline_id, raw,
         json.dumps(fired, ensure_ascii=False),
         json.dumps(unaudited, ensure_ascii=False),
         1 if verdict.any_fired else 0, db.now()))
    conn.commit()
    return int(cur.lastrowid)


def pending_fired_verdict(conn: sqlite3.Connection,
                          group_id: int) -> "sqlite3.Row | None":
    """The group's oldest fired verdict no action wake has acted on."""
    return conn.execute(
        "SELECT * FROM routine_verdicts WHERE group_id = ? AND fired = 1"
        "   AND acted_at IS NULL ORDER BY id LIMIT 1",
        (int(group_id),)).fetchone()


def mark_acted(conn: sqlite3.Connection, verdict_id: int) -> None:
    conn.execute("UPDATE routine_verdicts SET acted_at = ? WHERE id = ?",
                 (db.now(), int(verdict_id)))
    conn.commit()


def render_verdict_section(row: sqlite3.Row) -> "list[str]":
    """`## Routine audit verdict` — the fired findings, verbatim, on
    top of the action wake's Context."""
    fired = json.loads(str(row["fired_json"] or "[]"))
    out = [f"## Routine audit verdict (audit {int(row['id'])}, "
           f"{str(row['created_at'])[:16]}Z)", "",
           "Your routine audit FIRED on the lines below. This batch must "
           "act on every fired root — `ConfirmShelve` it (with its "
           "restart condition in the Roadmap's PAST) or `Inject` it with "
           "the argument that keeps it — the framework refuses a batch "
           "that leaves one untouched.", ""]
    for f in fired:
        where = (f"`{f['slug']}` (goal_id {f['goal_id']})"
                 if f.get("goal_id") is not None else "the Roadmap")
        out.append(f"- criterion {f['criterion']} fired on {where}: "
                   f"{f['reason']}")
    out.append("")
    return out


# ------------------------------------------------------------ the wake

def finish_routine_audit(conn: sqlite3.Connection, *, problem: str,
                          group_id: "int | None", attempts_dir: Path,
                          problem_dir: Path, workspace: Path,
                          pipeline_id: str, sid: str, prompt_path: Path,
                          tools_cfg, strategist_timeout: int) -> "Any":
    """Stage 3 of a ROUTINE wake: read `verdict.json`, record it, touch
    the routine clock only.

    Clocks: only `last_routine_at` (problem + group). The batch
    acknowledgement ratchet is `last_strategist_at`
    (`unacknowledged_inject_batches`); an audit that advanced it would
    swallow Inject batches it never processed, and one that advanced
    neither would re-fire every tick (routine outranks every other
    trigger). One corrective resume turn for a missing / unreadable
    verdict, the same courtesy decision.json gets."""
    from ... import agent
    from .. import PipelineResult
    from ...state import groups as _groups
    from . import audit as _audit
    from .wake import _apply_kb_curation, _persist_plan

    gid = (int(group_id) if group_id is not None
           else _groups.ensure_top_group(conn, problem))
    snapshot = _audit.read_roots_snapshot(attempts_dir) or []
    vpath = attempts_dir / _audit.VERDICT_FILE

    def _read() -> "tuple[_audit.Verdict | None, str, str]":
        if not vpath.exists():
            return None, "", f"{_audit.VERDICT_FILE} not produced"
        try:
            raw = vpath.read_text(encoding="utf-8")
        except OSError as e:
            return None, "", f"{_audit.VERDICT_FILE} unreadable: {e}"
        v, err = _audit.parse_verdict(raw, snapshot)
        return v, err, ""

    verdict, err, missing = _read()
    if missing or verdict is None:
        defect = missing or err
        print(f"[strategist] {problem}: {defect} — one corrective "
              f"resume turn", flush=True)
        rc_fix = agent.spawn_llm(
            kind="strategist", prompt_path=prompt_path,
            problem_dir=problem_dir, attempts_dir=attempts_dir,
            session_id=sid, is_retry=True,
            retry_context=(
                f"Your turn ended but {_audit.VERDICT_FILE} was NOT "
                f"written — the audit is only real once it lands on "
                f"disk. Write {_audit.VERDICT_FILE} NOW with write_file: "
                f"every criterion, criteria 3 and 4 once per line in "
                f"flight."
                if missing else
                f"Your {_audit.VERDICT_FILE} cannot be handed in — {err}. "
                f"Rewrite the ENTIRE file NOW with write_file; keep your "
                f"rulings, fix the shape."),
            timeout_sec=strategist_timeout, mcp_config_path=tools_cfg)
        _persist_plan(problem_dir, attempts_dir, group_id)
        if rc_fix == 0:
            verdict, err, missing = _read()
    if missing:
        return PipelineResult(
            outcome="failed", failure_reason="agent_no_output",
            failure_detail=missing + " (after one corrective turn)")
    if verdict is None:
        return PipelineResult(
            outcome="failed", failure_reason="strategist_schema_invalid",
            failure_detail=f"verdict: {err} (after one corrective turn)")
    raw = vpath.read_text(encoding="utf-8")
    vid = _audit.record_verdict(conn, problem=problem, group_id=gid,
                                pipeline_id=pipeline_id, verdict=verdict,
                                raw=raw)
    _groups.touch_routine(conn, gid)
    db.update_problem_last_routine_at(conn, problem)
    _apply_kb_curation(conn, problem=problem, attempts_dir=attempts_dir)
    from .. import _feedback
    _feedback.attempt_feedback(
        kind="strategist", seat="strategist", sid=sid, slug="routine",
        outcome="success", problem_dir=problem_dir,
        attempts_dir=attempts_dir, workspace=workspace)
    n_fired = len(verdict.fired)
    n_clear = len(verdict.clear)
    n_un = len(verdict.unaudited)
    print(f"[strategist] {problem}: routine audit {vid} — {n_fired} fired, "
          f"{n_clear} clear, {n_un} unaudited"
          + (" → action wake seated" if verdict.any_fired else ""),
          flush=True)
    return PipelineResult(
        outcome="success", failure_reason="",
        failure_detail=(f"audit {vid}: {n_fired} fired, {n_clear} clear, "
                        f"{n_un} unaudited"))
