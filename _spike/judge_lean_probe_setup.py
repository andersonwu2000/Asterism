"""Roll a probe workspace back to the moment SG's batch 2 was judged.

The first probe run replayed a rev-2-era proposal against the world as it
looks AFTER the run finished — 19 goals proved, `main` proved, every
brick in CATALOG.md. Four of five criteria then fired on artefacts of
that anachronism ("you are re-proposing landed work"), and worse, the
judge could read the CORRECT `dst_param` statement (`|t - s|`) straight
out of CATALOG.md, so its criterion-3 finding cannot be cleanly
attributed to doing the mathematics.

State at 2026-08-02T01:24:17Z, when batch b1383b6a was submitted:
  * goals 7193 (root, frozen) and 7194-7197 (batch 1's bricks, proved);
  * nothing from 7198 on exists;
  * programme rev 1 is the one in force (rev 2 is the candidate);
  * batch 2's own decisions are committed but unsettled (outcome NULL);
  * proofs/ holds batch 1's four bricks and no root assembly.
"""
from __future__ import annotations

import shutil
import sqlite3
import sys
from pathlib import Path

REPO = Path(r"D:\Asterism")
sys.path.insert(0, str(REPO))

SCRATCH = Path(__file__).resolve().parent  # _spike/; artefacts land beside this file
WS = SCRATCH / "probe_ws"
PROBLEM = "sylvester_gallai"

#: last goal id that existed when batch 2 was submitted
CUTOFF_GOAL = 7197
#: batch 1 + batch 2 decisions; 2806+ belong to later batches
CUTOFF_DECISION = 2805
KEEP_BRICKS = ("det3", "dst", "sq_inner_lt_of_det_ne_zero", "line_param")


def main() -> int:
    if WS.exists():
        shutil.rmtree(WS)
    WS.mkdir(parents=True)

    # 1. the problem dir, trimmed to what had landed
    src = REPO / "Problems" / PROBLEM
    dst = WS / "Problems" / PROBLEM
    shutil.copytree(src, dst)
    kept, dropped = [], []
    for f in sorted((dst / "proofs").glob("*.lean")):
        if f.stem in {f"L_{s}" for s in KEEP_BRICKS}:
            kept.append(f.name)
        else:
            f.unlink()
            dropped.append(f.name)
    print(f"[setup] proofs/: kept {kept}")
    print(f"[setup] proofs/: dropped {len(dropped)} incl. "
          f"{[n for n in dropped if not n.startswith('L_')]}")

    # 2. the DB, rolled back
    db = WS / "asterism.db"
    shutil.copyfile(REPO / "asterism.db", db)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    gone = [int(r[0]) for r in conn.execute(
        "SELECT id FROM goals WHERE problem = ? AND id > ?",
        (PROBLEM, CUTOFF_GOAL))]
    marks = ",".join("?" * len(gone))
    conn.execute(f"DELETE FROM strategies WHERE goal_id IN ({marks})", gone)
    conn.execute(f"DELETE FROM goals WHERE id IN ({marks})", gone)
    # the root had not been launched yet
    conn.execute("UPDATE goals SET status = 'frozen' WHERE id = 7193")
    conn.execute("DELETE FROM strategies WHERE goal_id = 7193")
    # later batches never happened; batch 2's own rows are unsettled
    conn.execute("DELETE FROM strategist_decisions WHERE problem = ?"
                 " AND id > ?", (PROBLEM, CUTOFF_DECISION))
    conn.execute("UPDATE strategist_decisions SET outcome = NULL,"
                 " outcome_detail = NULL, produced_goal_id = NULL"
                 " WHERE problem = ? AND id >= 2796", (PROBLEM,))
    # rev 1 is the Programme in force while rev 2 is the candidate
    conn.execute("DELETE FROM programme_revisions WHERE problem = ?"
                 " AND rev >= 2", (PROBLEM,))
    conn.execute("UPDATE problems SET ingested_at = NULL,"
                 " ingest_signoff_pending = 0 WHERE name = ?", (PROBLEM,))
    conn.commit()
    print(f"[setup] deleted {len(gone)} goals, root back to frozen")
    print("[setup] goals now:", [
        (r["id"], r["slug"], r["status"]) for r in conn.execute(
            "SELECT id,slug,status FROM goals WHERE problem = ? ORDER BY id",
            (PROBLEM,))])
    print("[setup] programme revs now:", [
        (r["rev"], r["status"]) for r in conn.execute(
            "SELECT rev,status FROM programme_revisions WHERE problem = ?",
            (PROBLEM,))])

    # 3. TREE.md regenerated from the rolled-back rows
    from Tooling.state import tree
    out = tree.write(conn, WS, PROBLEM)
    print(f"[setup] TREE.md -> {out}")
    if out is not None:
        print((WS / "Problems" / PROBLEM / "TREE.md").read_text(
            encoding="utf-8")[:400])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
