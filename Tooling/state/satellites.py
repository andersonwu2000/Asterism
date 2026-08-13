"""What belongs to a problem — one registry, and auditors that read the
complement.

Eight resets between 2026-06 and 2026-08 leaked something a problem
owned: FK children (04109fbb), `.presearch/` (86684341), queue rows /
`PROGRAMME.md` / `_plan.md` (the three 07-19 fixes, "same leak class"),
`patch.lean` (d45a17b9 — where the sweeper and its own auditor turned
out to share one hand-written tuple, so the check could only ever
report what the sweeper already knew), `.groups/` (#167). Every one of
those was the same shape: a problem's satellites live in N places, each
operation that must enumerate them carried its own hand-list, and every
new satellite silently widened the gap between the lists.

This module is the one place the enumeration lives, and the auditors
are COMPLEMENT-based on purpose: they ask "what exists that nothing
claims", never "is the sweeper's list still swept" — the latter is
structurally blind to whatever the list forgot (the d45a17b9 lesson).

Three parts:

  * FILE_SATELLITES — every path shape the framework may leave in or
    around a problem directory, with a disposition (`swept` at reset /
    `kept` deliberately). `cmd_reset` SWEEPS from this registry and its
    verifier re-checks from it, so the two cannot drift; the complement
    walk then reports anything on disk that no entry claims.
  * DB classification — derived from the schema itself (`PRAGMA
    table_info` / `foreign_key_list`), not from a list: a table is
    problem-keyed if it carries a `problem` column or reaches
    `problems` through FKs. Only linkage the schema cannot express
    (polymorphic target_kind/target_id, the librarian's prefix-encoded
    key) is declared by hand, and a test fails on any table in neither
    bucket — a new table cannot arrive unclassified.
  * Auditors — `db_leftovers` (per-problem complement, run after a
    wipe) and `orphan_rows` (global referential complement). REPORT
    ONLY. Widening what reset deletes is the operator's call, made on
    this report — never this module's.

`SURVIVES_RESET` names the problem-keyed tables a wipe deliberately
does not touch, each with a reason. An undeclared survivor shows up in
every `db_leftovers` report; a declared one is visible here instead of
silent in the wipe's blind spot.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

# ─────────────────────────────── file side ───────────────────────────────

#: Where an entry's pattern is rooted.
SCOPE_PROOFS = "proofs"            # Problems/<p>/proofs/
SCOPE_PROBLEM_ROOT = "problem_root"  # Problems/<p>/
SCOPE_RUNTIME_SLOTS = "runtime_slots"  # <ws>/.asterism/runtime_slots/
SCOPE_WORKSPACE = "workspace"      # <ws>/ (legacy artifact locations)

SWEPT = "swept"
KEPT = "kept"


@dataclass(frozen=True)
class FileSatellite:
    scope: str
    pattern: str          # glob for files; a literal name for dirs
    disposition: str      # SWEPT (reset removes) | KEPT (reset preserves)
    is_dir: bool
    why: str


FILE_SATELLITES: "tuple[FileSatellite, ...]" = (
    # — proofs/: everything that belongs to a RUN rather than the problem —
    FileSatellite(SCOPE_PROOFS, "L_*.lean", SWEPT, False,
                  "the problem's own bricks"),
    FileSatellite(SCOPE_PROOFS, "_strategy_*.lean", SWEPT, False,
                  "the problem's own strategy wraps"),
    FileSatellite(SCOPE_PROOFS, "patch.lean", SWEPT, False,
                  "Backward worker sandbox output whose home is the "
                  "attempts dir; one landed here 2026-07-14 and outlived "
                  "the SLC reset three weeks (d45a17b9)"),
    FileSatellite(SCOPE_PROOFS, "new_*.lean", SWEPT, False,
                  "worker sandbox sub-goal stubs, same escape route as "
                  "patch.lean"),
    FileSatellite(SCOPE_PROOFS, "*.backup", SWEPT, False,
                  "Backward/Builder spawn-retry copy left by a watchdog "
                  "kill before _restore_backup"),
    FileSatellite(SCOPE_PROOFS, "*.verify_backup", SWEPT, False,
                  "Verify's atomic-write safety copy"),
    FileSatellite(SCOPE_PROOFS, "*.verify_backup_s*", SWEPT, False,
                  "sid-keyed variant; a stale one outlived reset on "
                  "2026-05-18 and got resurrected into a goal-less orphan"),
    FileSatellite(SCOPE_PROOFS, "*.lean.tmp", SWEPT, False,
                  "Verify pre-replace staging"),
    FileSatellite(SCOPE_PROOFS, "*.lean.tmp_s*", SWEPT, False,
                  "sid-keyed staging, never safe to keep across runs"),
    # — problem root: run artifacts —
    FileSatellite(SCOPE_PROBLEM_ROOT, "TREE.md", SWEPT, False,
                  "live tree rendering; goal rows gone means it would "
                  "render 'no root goal' anyway"),
    FileSatellite(SCOPE_PROBLEM_ROOT, "LESSONS.md", SWEPT, False,
                  "legacy Model-A reflection cache (Phase 12 moved "
                  "lessons into the KB); swept to clean pre-Model-B dirs"),
    FileSatellite(SCOPE_PROBLEM_ROOT, "Root.lean.backup", SWEPT, False,
                  "spawn-side snapshot from the in-pipeline retry path; "
                  "only an unclean shutdown leaves one"),
    FileSatellite(SCOPE_PROBLEM_ROOT, "PROGRAMME.md", SWEPT, False,
                  "rendered from programme_revisions (wiped with the "
                  "rows); left behind it hands a rerun the prior run's "
                  "winning worldview (2026-07-19 leak audit)"),
    FileSatellite(SCOPE_PROBLEM_ROOT, "_plan.md", SWEPT, False,
                  "strategists sometimes write the plan note at the "
                  "problem root instead of .drafts/ — same leak class as "
                  "PROGRAMME.md"),
    FileSatellite(SCOPE_PROBLEM_ROOT, ".drafts", SWEPT, True,
                  "postmortem progress notes from timed-out spawns; "
                  "carrying partial sketches over would pre-bias a "
                  "clean baseline"),
    FileSatellite(SCOPE_PROBLEM_ROOT, ".presearch", SWEPT, True,
                  "per-goal candidate cache keyed by goal id; ids "
                  "restart after reset, so a survivor is silently served "
                  "to an UNRELATED new goal with the same id"),
    FileSatellite(SCOPE_PROBLEM_ROOT, ".groups", SWEPT, True,
                  "per-sub-group PROGRAMME projections keyed by group "
                  "id; same id-reuse hazard as .presearch, and the one "
                  "file whose whole job is carrying a worldview forward "
                  "(#167: a rerun's revision 2 cited .groups/369 from "
                  "the run before it)"),
    # — problem root: deliberately preserved —
    FileSatellite(SCOPE_PROBLEM_ROOT, "Manifest.md", KEPT, False,
                  "user-owned problem statement"),
    FileSatellite(SCOPE_PROBLEM_ROOT, "Defs.lean", KEPT, False,
                  "user-owned vocabulary"),
    FileSatellite(SCOPE_PROBLEM_ROOT, "Root.lean", KEPT, False,
                  "user-owned since task #66; operator restores the "
                  "sorry-stub manually before re-init"),
    FileSatellite(SCOPE_PROBLEM_ROOT, "BRIEF.md", KEPT, False,
                  "auto-regenerated at daemon startup from "
                  "Manifest+Library — sweeping it buys nothing"),
    FileSatellite(SCOPE_PROBLEM_ROOT, "proofs", KEPT, True,
                  "the directory itself; its RUN-owned contents are the "
                  "proofs-scope swept entries above"),
    # — workspace-level artifacts a reset also clears —
    FileSatellite(SCOPE_RUNTIME_SLOTS, "_gateway_slot_*.lean", SWEPT, False,
                  "per-worker gateway didOpen surface"),
    FileSatellite(SCOPE_WORKSPACE, "_gateway_slot_*.lean", SWEPT, False,
                  "legacy pre-move location, retained for migration "
                  "cleanup of old daemons"),
    FileSatellite(SCOPE_WORKSPACE, "_gateway_smoke_*.lean", SWEPT, False,
                  "legacy gateway smoke artifact"),
    FileSatellite(SCOPE_WORKSPACE, "_axiom_probe_*.lean", SWEPT, False,
                  "legacy axiom-probe artifact"),
)


def swept(scope: str, *, dirs: bool = False) -> "tuple[str, ...]":
    """The reset-swept patterns for one scope — the sweeper's and the
    verifier's shared source."""
    return tuple(e.pattern for e in FILE_SATELLITES
                 if e.scope == scope and e.disposition == SWEPT
                 and e.is_dir == dirs)


def file_complement(pdir: Path) -> "list[str]":
    """Paths present in the problem dir that NO registry entry claims.

    The complement question, asked of the problem root and proofs/:
    anything the framework generates but nobody registered shows up
    here the first time a reset runs after it appears — as a REPORT.
    Deleting it is the operator's call; an unclaimed path may equally
    be the user's own file, which is exactly why this never deletes.
    """
    import fnmatch

    def claimed(name: str, scope: str, is_dir: bool) -> bool:
        return any(
            fnmatch.fnmatch(name, e.pattern)
            for e in FILE_SATELLITES
            if e.scope == scope and e.is_dir == is_dir)

    out: "list[str]" = []
    if pdir.exists():
        for p in sorted(pdir.iterdir()):
            if not claimed(p.name, SCOPE_PROBLEM_ROOT, p.is_dir()):
                out.append(p.name + ("/" if p.is_dir() else ""))
        proofs = pdir / "proofs"
        if proofs.exists():
            for p in sorted(proofs.iterdir()):
                if not claimed(p.name, SCOPE_PROOFS, p.is_dir()):
                    out.append(f"proofs/{p.name}"
                               + ("/" if p.is_dir() else ""))
    return out


# ──────────────────────────────── DB side ────────────────────────────────

#: `pipelines.target_id` for a Problem-kind row is either the problem
#: name or the Librarian's composed `problem\x1ffile` key. This SQL
#: fragment is the decoder both the per-problem question and the global
#: orphan audit ask through — one spelling of one fact, because the two
#: asking it differently is how the audit came to disagree with the
#: wipe about which rows even belong to a problem.
PROBLEM_OF_TARGET = (
    "(CASE WHEN instr(target_id, char(31)) > 0 "
    " THEN substr(target_id, 1, instr(target_id, char(31)) - 1) "
    " ELSE target_id END)")

#: Problem linkage the schema cannot express, declared by hand. The
#: predicate answers "rows referencing problem :p"; None means the rows
#: are keyed by ids whose referents a wipe deletes first, so the
#: per-problem question is unanswerable afterwards and only the global
#: orphan audit can see the leftovers.
POLYMORPHIC_TABLES: "dict[str, tuple[str | None, str]]" = {
    "pipelines": (
        "target_kind = 'Problem' AND " + PROBLEM_OF_TARGET + " = :p",
        "target_kind/target_id rows; Goal/Strategy/Group targets are "
        "id-keyed and orphan-auditable only. The Group kind arrived in "
        "v35 and the wipe's hand-written kind list did not follow it "
        "until 2026-08-14 (68 pipelines + 54 dead_attempts stranded, "
        "swept then and covered by the wipe since)"),
    "dead_attempts": (
        None,
        "polymorphic target + pipeline_id FK; per-problem rows hang off "
        "pipelines the wipe deletes first"),
    "librarian_fail_counts": (
        "target_id = :p OR target_id LIKE :p || char(31) || '%'",
        "key encodes the problem as 'problem' or 'problem\\x1ffile' "
        "(#92); a fresh classify clears its own, so reset leaves them "
        "defused-but-present"),
}

#: Problem-keyed tables a wipe DELIBERATELY leaves alone. Each entry is
#: a standing ruling, visible here instead of silent in the wipe.
SURVIVES_RESET: "dict[str, str]" = {
    # `spawn_usage` sat here from 2026-08-13 to 2026-08-14 as an
    # undeclared survivor turned declared one: token/wall telemetry,
    # argued to be a record of money already spent rather than of run
    # state, and marked "deliberateness unconfirmed by the owner". The
    # owner's ruling was to WIPE it, so it left this dict for
    # `wipe_problem_rows` — which is the intended traffic direction
    # here. An entry is a standing ruling, not a resting place.
    "librarian_fail_counts": (
        "defused at the next classify "
        "(clear_librarian_fail_counts_for_problem) rather than swept; "
        "rows for a DELETED problem linger until then — owner may "
        "prefer the wipe to clear the prefix rows."),
}


def _tables(conn: sqlite3.Connection) -> "list[str]":
    return [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
        " AND name NOT LIKE 'sqlite_%' ORDER BY name")]


def _has_problem_column(conn: sqlite3.Connection, table: str) -> bool:
    return any(r[1] == "problem" for r in conn.execute(
        f"PRAGMA table_info({table})"))


def classify_tables(conn: sqlite3.Connection) -> "dict[str, str]":
    """Every table → how it relates to a problem. DERIVED from the
    schema where the schema can say (problem column; FK reachability to
    `problems`), declared in `POLYMORPHIC_TABLES` where it cannot.
    'UNCLASSIFIED' is the failure the invariant test exists to catch:
    a new table must land in a bucket the auditors can read."""
    out: "dict[str, str]" = {}
    tables = _tables(conn)
    reaches: "dict[str, bool]" = {"problems": True}

    def _reaches(table: str, seen: "frozenset[str]" = frozenset()) -> bool:
        if table in reaches:
            return reaches[table]
        if table in seen:
            return False
        hit = any(
            _reaches(r[2], seen | {table})
            for r in conn.execute(f"PRAGMA foreign_key_list({table})"))
        reaches[table] = hit
        return hit

    for t in tables:
        if t == "problems":
            out[t] = "anchor"
        elif _has_problem_column(conn, t):
            out[t] = "problem-column"
        elif t in POLYMORPHIC_TABLES:
            out[t] = "polymorphic"
        elif _reaches(t):
            out[t] = "fk-transitive"
        else:
            out[t] = "UNCLASSIFIED"
    return out


def db_leftovers(conn: sqlite3.Connection,
                 problem: str) -> "dict[str, int]":
    """Per-problem complement: rows still referencing `problem`, asked
    of every table the classification says CAN be asked. Run after a
    wipe, non-zero counts are the wipe's blind spots. REPORT ONLY —
    tables in `SURVIVES_RESET` are skipped because their survival is a
    declared ruling, not a blind spot."""
    out: "dict[str, int]" = {}
    for table, kind in classify_tables(conn).items():
        if table in SURVIVES_RESET:
            continue
        if kind == "anchor":
            sql = "SELECT COUNT(*) FROM problems WHERE name = :p"
        elif kind == "problem-column":
            sql = f"SELECT COUNT(*) FROM {table} WHERE problem = :p"
        elif kind == "polymorphic":
            pred = POLYMORPHIC_TABLES[table][0]
            if pred is None:
                continue
            sql = f"SELECT COUNT(*) FROM {table} WHERE {pred}"
        else:               # fk-transitive: parents deleted first
            continue
        n = conn.execute(sql, {"p": problem}).fetchone()[0]
        if n:
            out[table] = int(n)
    return out


def orphan_rows(conn: sqlite3.Connection) -> "dict[str, int]":
    """Global referential complement: rows whose referent no longer
    exists. This is the only grain that can see the id-keyed leftovers
    a per-problem question cannot (their parent rows are already
    gone). REPORT ONLY, same rule as everything here.

    THE FLOOR IS ZERO. On 2026-08-14 the operator's live DB was swept to
    empty (owner ruling, #209: 38 fossils from June/July, every one of
    their classes covered by today's wipe). That is worth stating
    because a standing non-zero teaches the next reader that the noise
    IS the baseline — after which two genuinely new rows read as
    weather. Anything this reports now is new, and means the wipe grew
    a blind spot."""
    checks: "dict[str, str]" = {
        "strategies(goal gone)":
            "SELECT COUNT(*) FROM strategies WHERE goal_id NOT IN "
            "(SELECT id FROM goals)",
        "strategy_subgoals(strategy/goal gone)":
            "SELECT COUNT(*) FROM strategy_subgoals WHERE strategy_id "
            "NOT IN (SELECT id FROM strategies) OR subgoal_id NOT IN "
            "(SELECT id FROM goals)",
        "pipelines(Goal target gone)":
            "SELECT COUNT(*) FROM pipelines WHERE target_kind='Goal' "
            "AND target_id NOT IN (SELECT CAST(id AS TEXT) FROM goals)",
        "pipelines(Strategy target gone)":
            "SELECT COUNT(*) FROM pipelines WHERE target_kind='Strategy' "
            "AND " + PROBLEM_OF_TARGET + " NOT IN "
            "(SELECT CAST(id AS TEXT) FROM strategies)",
        "pipelines(Group target gone)":
            "SELECT COUNT(*) FROM pipelines WHERE target_kind='Group' "
            "AND target_id NOT IN (SELECT CAST(id AS TEXT) FROM groups)",
        # Two key shapes share this column. A Forward pipeline's
        # target_id IS the problem name; a Librarian per-file unit's is
        # the composed `problem\x1ffile` (the in-process dispatch
        # identity, see `dispatcher._lib_encode`). Comparing the raw
        # column against `problems` therefore indicted 1,063 rows on
        # 2026-08-14 whose problems all exist — an auditor that cries
        # wolf a thousand times is one nobody reads, which is the exact
        # failure this module was built to prevent. Decode, then ask.
        "pipelines(Problem target gone)":
            "SELECT COUNT(*) FROM pipelines WHERE target_kind='Problem' "
            "AND " + PROBLEM_OF_TARGET + " NOT IN "
            "(SELECT name FROM problems)",
        "dead_attempts(Goal target gone)":
            "SELECT COUNT(*) FROM dead_attempts WHERE target_kind='Goal' "
            "AND target_id NOT IN (SELECT CAST(id AS TEXT) FROM goals)",
        "dead_attempts(Group target gone)":
            "SELECT COUNT(*) FROM dead_attempts WHERE target_kind='Group' "
            "AND target_id NOT IN (SELECT CAST(id AS TEXT) FROM groups)",
        "queue(problem gone)":
            "SELECT COUNT(*) FROM queue WHERE problem NOT IN "
            "(SELECT name FROM problems)",
        "goal_events(problem gone)":
            "SELECT COUNT(*) FROM goal_events WHERE problem NOT IN "
            "(SELECT name FROM problems)",
    }
    out: "dict[str, int]" = {}
    for label, sql in checks.items():
        n = conn.execute(sql).fetchone()[0]
        if n:
            out[label] = int(n)
    return out
