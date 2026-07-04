"""Phase 6 — full-auto Library un-harvest (rollback decision ①).

A post-Ingest un-prove (rogue-sorryAx rollback) invalidates the terminal
judgment the harvest was predicated on, so the published artifacts come
DOWN automatically: Library files, the INDEX section, the library_decls
lifecycle rows and the librarian fail-count slate. User's design call
(2026-07-04): Library membership means "reliable and citable", so a
revoked ingest must not leave its content published; cross-problem
dependents of the removed modules — which per the same premise should not
exist for content unsound enough to be rolled back — are surfaced LOUDLY
(they were built on the revoked base and must break visibly at the next
Library gate, not survive silently).

Deleting Library files goes through plain unlink, NOT proof_store: the
ownership guard governs `Problems/<p>/proofs/` (per-goal lean_path);
Library artifacts are the Librarian's own output tree.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from ...state import db


def _library_dependents(workspace: Path, modules: set[str],
                        own_files: set[Path]) -> list[tuple[Path, str]]:
    """Scan Library/*.lean (excluding the files being removed) for imports
    of any module in `modules`. Returns [(file, imported_module)]."""
    hits: list[tuple[Path, str]] = []
    lib_root = workspace / "Library"
    if not lib_root.is_dir():
        return hits
    for f in lib_root.rglob("*.lean"):
        if f in own_files:
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            ls = line.strip()
            if not ls.startswith("import "):
                continue
            mod = ls[len("import "):].strip()
            if mod in modules:
                hits.append((f, mod))
    return hits


def un_harvest(conn: sqlite3.Connection, workspace: Path,
               problem: str) -> int:
    """Remove `problem`'s harvested artifacts from the Library. Returns
    the number of Library files removed (0 = nothing was harvested).

    Steps: delete migrated Library files → drop the `## <problem>` INDEX
    section → DELETE library_decls rows → clear librarian_fail_counts
    (TEXT keys: the serial phase uses the bare problem name, per-file
    units use `problem\\x1ffile`). DB rows go last so a crash mid-way
    leaves the rows pointing at missing files — which `drift-check` and
    the selfstart re-harvest path both surface — rather than orphaned
    files that nothing tracks."""
    rows = conn.execute(
        "SELECT DISTINCT target_file FROM library_decls"
        " WHERE problem = ? AND target_file IS NOT NULL",
        (problem,),
    ).fetchall()
    files = {workspace / str(r["target_file"]) for r in rows}

    # Loud dependent surface: another Library file importing a module we
    # are about to remove was built on the revoked base.
    modules = set()
    for f in files:
        try:
            rel = f.relative_to(workspace)
        except ValueError:
            continue
        modules.add(".".join(rel.with_suffix("").parts))
    dependents = _library_dependents(workspace, modules, files)
    for dep_file, mod in dependents:
        print(f"[un-harvest] {problem}: CRITICAL — {dep_file} imports "
              f"removed module {mod}; it was built on the revoked base "
              f"and will fail the next Library gate", flush=True)

    removed = 0
    for f in sorted(files):
        try:
            f.unlink()
            removed += 1
        except FileNotFoundError:
            pass
        except OSError as e:
            print(f"[un-harvest] {problem}: could not remove {f}: {e}",
                  flush=True)

    index = workspace / "Library" / "INDEX.md"
    if index.exists():
        from .bridge import _drop_index_section
        text = index.read_text(encoding="utf-8", errors="replace")
        new = _drop_index_section(text, problem)
        if new != text:
            index.write_text(new, encoding="utf-8")

    conn.execute("DELETE FROM library_decls WHERE problem = ?", (problem,))
    conn.execute(
        "DELETE FROM librarian_fail_counts"
        " WHERE target_id = ? OR target_id LIKE ? || char(31) || '%'",
        (problem, problem),
    )
    conn.commit()
    if removed or rows:
        print(f"[un-harvest] {problem}: removed {removed} Library file(s), "
              f"INDEX section dropped, lifecycle rows cleared", flush=True)
    return removed
