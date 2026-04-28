"""spike-011 — SQLite json_patch atomicity under concurrent blocked_pipelines writes.

Tests three update strategies for concurrent appends to a JSON array column:
  A) Python-level read-modify-write (no lock): baseline, expected lost updates
  B) Atomic SQL json_insert in single statement: expected no lost updates
  C) Python-level read-modify-write + multiprocessing.Lock: expected no lost updates

Also tests effect of WHERE commit_state='live' filter on strategies A and B.

Setup: 2 worker processes; Process-1 appends 'Backward', Process-2 appends 'Builder'.
Each trial: reset row to '[]', both workers concurrently append, verify final list.
N_TRIALS = 100 per strategy.

Run: python Tooling/tests/fixtures/spikes/spike011_json_patch.py
"""

import json
import multiprocessing
import os
import sqlite3
import sys
import tempfile
import time


N_TRIALS = 100


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _setup_db(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS goals (
            id              INTEGER PRIMARY KEY,
            blocked_pipelines TEXT NOT NULL DEFAULT '[]',
            commit_state    TEXT NOT NULL DEFAULT 'live'
        )
    """)
    conn.execute(
        "INSERT OR REPLACE INTO goals (id, blocked_pipelines, commit_state)"
        " VALUES (1, '[]', 'live')"
    )
    conn.commit()
    conn.close()


def _reset_row(db_path: str) -> None:
    conn = sqlite3.connect(db_path, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("UPDATE goals SET blocked_pipelines='[]' WHERE id=1")
    conn.commit()
    conn.close()


def _read_blocked(db_path: str) -> list[str]:
    conn = sqlite3.connect(db_path, timeout=30)
    row = conn.execute("SELECT blocked_pipelines FROM goals WHERE id=1").fetchone()
    conn.close()
    return json.loads(row[0]) if row else []


# ---------------------------------------------------------------------------
# Worker functions (must be top-level for multiprocessing pickle)
# ---------------------------------------------------------------------------

def _worker_python_rw(db_path, entry, n_trials, start_barrier, done_barrier, lost_count):
    """Strategy A: non-atomic Python read-modify-write (no lock)."""
    conn = sqlite3.connect(db_path, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    for _ in range(n_trials):
        start_barrier.wait()
        row = conn.execute("SELECT blocked_pipelines FROM goals WHERE id=1").fetchone()
        lst = json.loads(row[0]) if row else []
        if entry not in lst:
            lst.append(entry)
        # small sleep to widen the race window
        time.sleep(0.0002)
        conn.execute(
            "UPDATE goals SET blocked_pipelines=? WHERE id=1",
            (json.dumps(lst),),
        )
        conn.commit()
        done_barrier.wait()
    conn.close()


def _worker_python_rw_with_filter(db_path, entry, n_trials, start_barrier, done_barrier, lost_count):
    """Strategy A2: non-atomic Python read-modify-write with WHERE commit_state='live' filter."""
    conn = sqlite3.connect(db_path, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    for _ in range(n_trials):
        start_barrier.wait()
        row = conn.execute(
            "SELECT blocked_pipelines FROM goals WHERE id=1 AND commit_state='live'"
        ).fetchone()
        lst = json.loads(row[0]) if row else []
        if entry not in lst:
            lst.append(entry)
        time.sleep(0.0002)
        conn.execute(
            "UPDATE goals SET blocked_pipelines=? WHERE id=1 AND commit_state='live'",
            (json.dumps(lst),),
        )
        conn.commit()
        done_barrier.wait()
    conn.close()


def _worker_atomic_sql(db_path, entry, n_trials, start_barrier, done_barrier, lost_count):
    """Strategy B: atomic json_insert in single SQL statement."""
    conn = sqlite3.connect(db_path, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    for _ in range(n_trials):
        start_barrier.wait()
        conn.execute(
            "UPDATE goals SET blocked_pipelines = json_insert(blocked_pipelines, '$[#]', ?)"
            " WHERE id=1 AND commit_state='live'",
            (entry,),
        )
        conn.commit()
        done_barrier.wait()
    conn.close()


def _worker_locked_rw(db_path, entry, n_trials, start_barrier, done_barrier, lock):
    """Strategy C: Python read-modify-write protected by multiprocessing.Lock."""
    conn = sqlite3.connect(db_path, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    for _ in range(n_trials):
        start_barrier.wait()
        with lock:
            row = conn.execute(
                "SELECT blocked_pipelines FROM goals WHERE id=1"
            ).fetchone()
            lst = json.loads(row[0]) if row else []
            if entry not in lst:
                lst.append(entry)
            conn.execute(
                "UPDATE goals SET blocked_pipelines=? WHERE id=1",
                (json.dumps(lst),),
            )
            conn.commit()
        done_barrier.wait()
    conn.close()


# ---------------------------------------------------------------------------
# Trial orchestrator
# ---------------------------------------------------------------------------

def run_strategy(label, db_path, worker1_fn, worker2_fn, extra_arg=None):
    """Run N_TRIALS for a strategy, return lost_update count + rate."""
    _reset_row(db_path)
    lost = 0

    start_barrier = multiprocessing.Barrier(3)  # 2 workers + main
    done_barrier = multiprocessing.Barrier(3)

    if extra_arg is not None:
        p1 = multiprocessing.Process(
            target=worker1_fn,
            args=(db_path, "Backward", N_TRIALS, start_barrier, done_barrier, extra_arg),
        )
        p2 = multiprocessing.Process(
            target=worker2_fn,
            args=(db_path, "Builder", N_TRIALS, start_barrier, done_barrier, extra_arg),
        )
    else:
        p1 = multiprocessing.Process(
            target=worker1_fn,
            args=(db_path, "Backward", N_TRIALS, start_barrier, done_barrier, None),
        )
        p2 = multiprocessing.Process(
            target=worker2_fn,
            args=(db_path, "Builder", N_TRIALS, start_barrier, done_barrier, None),
        )

    p1.start()
    p2.start()

    for trial in range(N_TRIALS):
        _reset_row(db_path)
        start_barrier.wait()   # release both workers
        done_barrier.wait()    # wait for both to finish
        final = _read_blocked(db_path)
        if "Backward" not in final or "Builder" not in final:
            lost += 1

    p1.join()
    p2.join()

    rate = lost / N_TRIALS
    status = "PASS (0 lost)" if lost == 0 else f"FAIL ({lost} lost updates)"
    print(f"  {label:<55}  lost={lost:>3}/{N_TRIALS}  rate={rate:.3f}  [{status}]")
    return lost, rate


def main():
    print("=" * 72)
    print("spike-011  SQLite json_patch atomicity — concurrent blocked_pipelines writes")
    print(f"N_TRIALS={N_TRIALS} per strategy, 2 workers (Backward + Builder)")
    print("=" * 72)
    print()

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        _setup_db(db_path)
        print(f"DB: {db_path}")
        print(f"journal_mode=WAL")
        print()

        summary = []

        # Strategy A: non-atomic Python read-modify-write
        print("Strategy A — Python read-modify-write (no lock, no WHERE filter):")
        lost, rate = run_strategy(
            "A  no-lock, no-filter",
            db_path,
            _worker_python_rw,
            _worker_python_rw,
        )
        summary.append(("A  no-lock, no-filter", lost, rate))
        print()

        # Strategy A2: non-atomic Python rw WITH WHERE commit_state='live'
        print("Strategy A2 — Python read-modify-write + WHERE commit_state='live' filter:")
        lost, rate = run_strategy(
            "A2 no-lock, with-filter",
            db_path,
            _worker_python_rw_with_filter,
            _worker_python_rw_with_filter,
        )
        summary.append(("A2 no-lock, with-filter", lost, rate))
        print()

        # Strategy B: atomic SQL json_insert
        print("Strategy B — Atomic SQL json_insert (single statement):")
        lost, rate = run_strategy(
            "B  atomic-sql, with-filter",
            db_path,
            _worker_atomic_sql,
            _worker_atomic_sql,
        )
        summary.append(("B  atomic-sql, with-filter", lost, rate))
        print()

        # Strategy C: Python rw + application-level Lock
        lock = multiprocessing.Lock()
        print("Strategy C — Python read-modify-write + multiprocessing.Lock:")
        lost, rate = run_strategy(
            "C  app-lock, no-filter",
            db_path,
            _worker_locked_rw,
            _worker_locked_rw,
            extra_arg=lock,
        )
        summary.append(("C  app-lock, no-filter", lost, rate))
        print()

        # Summary table
        print("=" * 72)
        print("SUMMARY")
        print(f"  {'Strategy':<55}  {'Lost':>5}  {'Rate':>6}  Result")
        print("-" * 72)
        for name, lost, rate in summary:
            result = "PASS" if lost == 0 else "FAIL"
            print(f"  {name:<55}  {lost:>5}  {rate:>6.3f}  {result}")
        print()

        # Conclusions
        print("CONCLUSIONS:")
        a_lost = summary[0][1]
        a2_lost = summary[1][1]
        b_lost = summary[2][1]
        c_lost = summary[3][1]

        if a_lost > 0:
            print(f"  [CONFIRMED] Non-atomic Python rw loses updates ({a_lost}/{N_TRIALS})")
        else:
            print(f"  [NOTE] Non-atomic Python rw had no observed lost updates — race window too narrow?")
        if a2_lost > 0:
            print(f"  [CONFIRMED] WHERE commit_state filter does NOT prevent lost updates ({a2_lost}/{N_TRIALS})")
        else:
            print(f"  [NOTE] WHERE filter case also had 0 lost updates (same race window)")
        if b_lost == 0:
            print(f"  [CONFIRMED] Atomic SQL json_insert: 0 lost updates — safe for P3")
        else:
            print(f"  [UNEXPECTED] Atomic SQL had {b_lost} lost updates — investigate!")
        if c_lost == 0:
            print(f"  [CONFIRMED] App-level Lock: 0 lost updates — safe fallback")
        else:
            print(f"  [UNEXPECTED] App-level Lock had {c_lost} lost updates — investigate!")

    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
