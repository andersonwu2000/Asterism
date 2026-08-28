from __future__ import annotations

import sqlite3

from .core import now


# ---------------------------------------------------------------------
# library_decls — Librarian per-declaration state (plan §7)
# ---------------------------------------------------------------------

def upsert_library_decl(conn: sqlite3.Connection, *, problem: str,
                        slug: str, source_goal_id: int | None) -> int:
    """Insert a candidate library_decl, or return the existing row's id.
    Idempotent on (problem, slug) so re-running Step 0 inventory / dedup
    is safe (re-entrancy, plan §8). Does not reset verdict/lifecycle on
    an existing row — later work-kind setters advance those."""
    ts = now()
    conn.execute(
        "INSERT INTO library_decls (problem, slug, source_goal_id,"
        " created_at, updated_at) VALUES (?, ?, ?, ?, ?)"
        " ON CONFLICT(problem, slug) DO NOTHING",
        (problem, slug, source_goal_id, ts, ts),
    )
    conn.commit()
    row = conn.execute(
        "SELECT id FROM library_decls WHERE problem = ? AND slug = ?",
        (problem, slug),
    ).fetchone()
    return int(row["id"])


def set_library_verdict(conn: sqlite3.Connection, *, problem: str,
                        slug: str, verdict: str,
                        citation: str | None = None) -> None:
    """dedup work: record a verdict + optional citation, advance to
    'deduped' (or terminal 'dropped'/'cited' when the verdict is final).
    Verdict→lifecycle: keep→deduped, cite-mathlib/cite-library→cited,
    drop/merge→dropped."""
    lifecycle = {
        "keep": "deduped",
        "cite-mathlib": "cited",
        "cite-library": "cited",
        "drop": "dropped",
        "merge": "dropped",
    }.get(verdict, "deduped")
    conn.execute(
        "UPDATE library_decls SET verdict = ?, citation = ?,"
        " lifecycle = ?, updated_at = ? WHERE problem = ? AND slug = ?",
        (verdict, citation, lifecycle, now(), problem, slug),
    )
    conn.commit()


def set_library_classification(conn: sqlite3.Connection, *, problem: str,
                               slug: str, target_file: str,
                               target_name: str | None,
                               file_order: int) -> None:
    """classify work: record file placement + in-file order, advance a
    'deduped' (keep) decl to 'classified'. No-op on already-terminal
    (dropped/cited) rows."""
    conn.execute(
        "UPDATE library_decls SET target_file = ?, target_name = ?,"
        " file_order = ?, lifecycle = 'classified', updated_at = ?"
        " WHERE problem = ? AND slug = ? AND lifecycle = 'deduped'",
        (target_file, target_name, file_order, now(), problem, slug),
    )
    conn.commit()


def mark_library_migrated(conn: sqlite3.Connection, *, problem: str,
                          slug: str, target_name: str | None = None) -> None:
    """migrate work: a 'classified' decl was reshaped into its Library
    file and passed Gate A + build. Advance to terminal 'migrated'.

    `target_name` backfills the migrated Library declaration's fully-
    qualified name — classify wrote it NULL because the Library decl name
    isn't known until the migrate patch exists. `COALESCE` keeps any
    existing value when called without one, so no caller regresses a name
    already recorded."""
    conn.execute(
        "UPDATE library_decls SET lifecycle = 'migrated',"
        " target_name = COALESCE(?, target_name), updated_at = ?"
        " WHERE problem = ? AND slug = ? AND lifecycle = 'classified'",
        (target_name, now(), problem, slug),
    )
    conn.commit()


def mark_library_cleaned(conn: sqlite3.Connection, *, problem: str,
                         slug: str) -> None:
    """cleanup work (Step 4): a 'migrated' decl was reshaped to PR-ready form
    (unused hyps removed, variables factored, docstring) and passed the
    re-gate. Advance to terminal 'cleaned'."""
    conn.execute(
        "UPDATE library_decls SET lifecycle = 'cleaned', updated_at = ?"
        " WHERE problem = ? AND slug = ? AND lifecycle = 'migrated'",
        (now(), problem, slug),
    )
    conn.commit()


def set_library_renamed(conn: sqlite3.Connection, *, problem: str,
                        slug: str, old_fqn: str, new_fqn: str) -> None:
    """cleanup work (Step 4, P4 rename): a kept decl was renamed to a mathlib-
    aligned name. Record the new fqn in `target_name` (INDEX harvest + Gate B
    re-derivation use it) and the ORIGINAL fqn in `renamed_from` so consumer
    files self-apply `{old → new}` via deferred-rewire when their turn comes.

    `renamed_from` uses COALESCE: a decl renamed more than once across re-cleans
    keeps its FIRST (pre-cleanup) fqn, so the consumer rewrite chain stays
    anchored to the name consumers actually wrote. Lifecycle is untouched — the
    decl survives; `mark_library_cleaned` advances it separately."""
    conn.execute(
        "UPDATE library_decls SET target_name = ?,"
        " renamed_from = COALESCE(renamed_from, ?), updated_at = ?"
        " WHERE problem = ? AND slug = ?",
        (new_fqn, old_fqn, now(), problem, slug),
    )
    conn.commit()


# ---------------------------------------------------------------------
# Library index (v18) — the DB IS the index (task #4; INDEX.md retired).
# ---------------------------------------------------------------------

def mark_library_bridged(conn: sqlite3.Connection, problem: str,
                         note: str = "") -> None:
    """Bridge/Gate B PASSED for `problem` — the librarian chain's terminal
    done-marker (was: the `## <problem>` section existing in INDEX.md).
    `note` records the gate flavor (classic root re-derivation vs
    deliverable per-decl gate) for provenance."""
    conn.execute(
        "UPDATE problems SET library_bridged_at = ?,"
        " library_bridge_note = ? WHERE name = ?",
        (now(), note, problem))
    conn.commit()


def clear_library_bridged(conn: sqlite3.Connection, problem: str) -> None:
    """Invalidate the done-marker (re-clean / reject-driven un-harvest) so
    the terminal bridge re-fires on the rewritten Library — the DB successor
    of `_drop_index_section` (STATUS reset rule 2's manual step retired)."""
    conn.execute(
        "UPDATE problems SET library_bridged_at = NULL,"
        " library_bridge_note = NULL WHERE name = ?", (problem,))
    conn.commit()


def problem_library_bridged(conn: sqlite3.Connection, problem: str) -> bool:
    row = conn.execute(
        "SELECT library_bridged_at FROM problems WHERE name = ?",
        (problem,)).fetchone()
    return bool(row and row["library_bridged_at"])


def bridged_library_index(conn: sqlite3.Connection,
                          problem: "str | None" = None,
                          ) -> "dict[str, list[sqlite3.Row]]":
    """{problem: [placed decl rows]} for every BRIDGED problem — the query
    behind every former INDEX.md read (prover context menu, dedupe pool,
    pre-search verification) AND the serve chapter (`problem=` narrows to
    one). Placed = lifecycle IN ('migrated','cleaned'), the exact set the
    old INDEX sections recorded — this is the ONLY place that set is
    spelled; widen it here and every consumer follows. Rows also carry
    `library_bridged_at` from the JOIN."""
    sql = ("SELECT ld.*, p.library_bridged_at FROM library_decls ld"
           " JOIN problems p ON p.name = ld.problem"
           " WHERE p.library_bridged_at IS NOT NULL"
           " AND ld.lifecycle IN ('migrated','cleaned')")
    args: tuple = ()
    if problem is not None:
        sql += " AND ld.problem = ?"
        args = (problem,)
    out: "dict[str, list[sqlite3.Row]]" = {}
    for r in conn.execute(sql + " ORDER BY ld.problem, ld.id", args):
        out.setdefault(str(r["problem"]), []).append(r)
    return out


def library_decl_names(conn: sqlite3.Connection) -> "set[str]":
    """Fully-qualified names of every placed decl in every BRIDGED problem —
    the pre-search library-block verification set (replaces the INDEX.md
    substring probe; exact membership, no short-name false positives)."""
    return {
        str(r["target_name"] or r["slug"])
        for rows in bridged_library_index(conn).values() for r in rows}


def set_library_signature(conn: sqlite3.Connection, *, problem: str,
                          slug: str, signature: str,
                          decl_kind: str = "",
                          docstring: "str | None" = None,
                          src_line: "int | None" = None) -> None:
    """Backfill kernel-true facts from the declInfo oracle at bridge time.
    Best-effort: a decl whose signature stays NULL falls back to file
    parsing at the consumer (dedupe pool / serve chapter). `docstring`
    '' means the oracle confirmed there is none (NULL = not backfilled);
    `src_line` is the 1-based start line of the decl's command."""
    conn.execute(
        "UPDATE library_decls SET signature = ?, decl_kind = ?,"
        " docstring = ?, src_line = ?,"
        " updated_at = ? WHERE problem = ? AND slug = ?",
        (signature, decl_kind, docstring, src_line, now(), problem, slug))
    conn.commit()


# ---------------------------------------------------------------------
# librarian_fail_counts — persistent Librarian chain retry cap (#92, B#3)
# ---------------------------------------------------------------------

def librarian_fail_counts_all(conn: sqlite3.Connection) -> "dict[str, int]":
    """The whole persisted per-unit fail tally — loaded into the dispatcher's
    in-memory dict at daemon startup so the chain retry cap survives a restart
    (a genuinely-stuck unit STALLs instead of looping forever across restarts)."""
    return {r["target_id"]: r["n"] for r in conn.execute(
        "SELECT target_id, n FROM librarian_fail_counts")}


def set_librarian_fail_count(conn: sqlite3.Connection, *, target_id: str,
                             n: int) -> None:
    """Write-through a unit's fail count (upsert) when the in-memory dict is
    bumped."""
    ts = now()
    conn.execute(
        "INSERT INTO librarian_fail_counts (target_id, n, updated_at)"
        " VALUES (?, ?, ?) ON CONFLICT(target_id) DO UPDATE SET"
        " n = excluded.n, updated_at = excluded.updated_at",
        (target_id, n, ts),
    )
    conn.commit()


def clear_librarian_fail_count(conn: sqlite3.Connection, *,
                               target_id: str) -> None:
    """Drop a unit's fail count on success (mirrors the in-memory pop)."""
    conn.execute("DELETE FROM librarian_fail_counts WHERE target_id = ?",
                 (target_id,))
    conn.commit()


def clear_librarian_fail_counts_for_problem(conn: sqlite3.Connection,
                                            problem: str) -> int:
    """Drop ALL of a problem's Librarian fail counts — the plain `problem`
    serial-phase row and every `problem\\x1ffile` per-file row. Called when a
    fresh `classify` lays the problem out anew (a new chain attempt): the
    stall-cap is per-attempt, so a count left over from a PRIOR ingestion
    (e.g. a library reset + re-run) must not make `_librarian_refill` skip a
    file as already-stalled before the new attempt even runs it. Returns the
    number of rows dropped.

    Matches in Python (exact `problem` row + `problem\\x1f<file>` rows) rather
    than SQL LIKE, since a problem slug can contain `_` — a LIKE wildcard —
    which would over-match a sibling problem."""
    prefix = problem + "\x1f"
    victims = [t for (t,) in conn.execute(
        "SELECT target_id FROM librarian_fail_counts")
        if t == problem or t.startswith(prefix)]
    for t in victims:
        conn.execute("DELETE FROM librarian_fail_counts WHERE target_id = ?",
                     (t,))
    conn.commit()
    return len(victims)


def library_decls_for(conn: sqlite3.Connection, problem: str,
                      *, lifecycle: str | None = None) -> list[sqlite3.Row]:
    """All library_decls for a problem, optionally filtered to one
    lifecycle state. Ordered by file_order then id for stable display."""
    if lifecycle is None:
        return list(conn.execute(
            "SELECT * FROM library_decls WHERE problem = ?"
            " ORDER BY file_order IS NULL, file_order, id",
            (problem,),
        ))
    return list(conn.execute(
        "SELECT * FROM library_decls WHERE problem = ? AND lifecycle = ?"
        " ORDER BY file_order IS NULL, file_order, id",
        (problem, lifecycle),
    ))
