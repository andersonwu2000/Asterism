"""Owner ruling 2026-08-29: the dedupe probe must never let ONE bad
module refuse a whole batch. A module that fails on its own (olean
missing, syntax error) is dropped and recorded; two modules that
cannot share an environment (`environment already contains`) are
housed in separate batches; every pair is judged in the batch that
holds its own canonical. "Which one is bad" is not a question the
probe can answer — and it does not need to."""
from __future__ import annotations

from pathlib import Path

import pytest

from Tooling.quality import dedupe_probe as dp


def _ws(tmp_path: Path, modules: list[str]) -> Path:
    for m in modules:
        p = tmp_path / (m.replace(".", "/") + ".lean")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("-- stub\n", encoding="utf-8")
    return tmp_path


# ------------------------------------------------ pure error partition

def test_partition_reads_collisions_missing_oleans_and_broken_imports():
    at = {2: "Problems.p.proofs.L_a", 3: "Problems.p.proofs.L_b",
          4: "Problems.p.proofs.L_c", 5: "Problems.p.proofs.L_d"}
    out = "\n".join([
        "x.lean:3:0: error: import Problems.p.proofs.L_b failed, "
        "environment already contains 'Problems.p.four_packet_valid'",
        "x.lean:4:0: error: object file 'D:\\ws\\.lake\\build\\lib\\lean\\"
        "Problems\\p\\proofs\\L_c.olean' of module Problems.p.proofs.L_c "
        "does not exist",
        "x.lean:5:0: error: unknown package 'Problems.p.proofs.L_d'",
    ])
    dropped, deferred = dp.partition_header_errors(out, at)
    assert deferred == ["Problems.p.proofs.L_b"]
    assert set(dropped) == {"Problems.p.proofs.L_c", "Problems.p.proofs.L_d"}
    assert "olean" in dropped["Problems.p.proofs.L_c"]
    assert "unknown package" in dropped["Problems.p.proofs.L_d"]


def test_partition_is_empty_on_a_clean_header():
    assert dp.partition_header_errors("", {2: "M"}) == ({}, [])


# ------------------------------------------------------- batching loop

def test_import_batches_house_colliders_apart_and_drop_the_broken(tmp_path):
    ws = _ws(tmp_path, ["P.A", "P.B", "P.C", "P.D"])
    runs: list[str] = []

    def run(content: str) -> tuple[int, str]:
        runs.append(content)
        mods = [ln.split()[1] for ln in content.splitlines()
                if ln.startswith("import ") and ln != "import Mathlib"]
        errs = []
        for ln, m in enumerate(content.splitlines(), start=1):
            if m == "import P.C":
                errs.append(f"h.lean:{ln}:0: error: object file 'x/P/C.olean' "
                            f"of module P.C does not exist")
            if m == "import P.B" and "import P.A" in content:
                errs.append(f"h.lean:{ln}:0: error: import P.B failed, "
                            f"environment already contains 'P.foo'")
        del mods
        return (1 if errs else 0), "\n".join(errs)

    batches, dropped = dp.import_batches(ws, ["P.A", "P.B", "P.C", "P.D"], run)
    assert batches == [["P.A", "P.D"], ["P.B"]]
    assert list(dropped) == ["P.C"]
    # round 1 (A B C D): drops C, defers B; round 2 (A D): clean;
    # round 3 (B alone): clean
    assert len(runs) == 3


def test_import_batches_are_cached_while_the_files_do_not_change(tmp_path):
    ws = _ws(tmp_path, ["P.A", "P.B"])
    n = {"runs": 0}

    def run(content: str) -> tuple[int, str]:
        n["runs"] += 1
        return 0, ""
    dp.import_batches(ws, ["P.A", "P.B"], run)
    dp.import_batches(ws, ["P.B", "P.A"], run)
    assert n["runs"] == 1, "same module set, unchanged files → no second header run"
    (ws / "P" / "A.lean").write_text("-- edited\n", encoding="utf-8")
    import os
    os.utime(ws / "P" / "A.lean", (2_000_000_000, 2_000_000_000))
    dp.import_batches(ws, ["P.A", "P.B"], run)
    assert n["runs"] == 2, "a changed file invalidates the cache"


# ------------------------------------------ the apply probe, end to end

@pytest.fixture
def scripted_lean(monkeypatch, tmp_path):
    """A `lake env lean` stand-in: the header of (A, B) collides on B,
    C's olean is missing; pair files pass every pair except the one
    whose canonical is `P.B.bad`."""
    dp.import_batches.cache_clear()
    recorded: list[tuple[str, str]] = []
    monkeypatch.setattr(dp._degraded, "record",
                        lambda ws, kind, detail="": recorded.append((kind, detail)))

    def run(workspace: Path, content: str) -> tuple[int, str]:
        lines = content.splitlines()
        errs = []
        if "theorem _dc_" not in content:            # header probe
            for ln, m in enumerate(lines, start=1):
                if m == "import P.C":
                    errs.append(f"h.lean:{ln}:0: error: object file 'x/P/C.olean'"
                                f" of module P.C does not exist")
                if m == "import P.B" and "import P.A" in content:
                    errs.append(f"h.lean:{ln}:0: error: import P.B failed, "
                                f"environment already contains 'P.foo'")
        else:                                        # pair probe
            for ln, m in enumerate(lines, start=1):
                if "apply @P.B.bad" in m:
                    errs.append(f"p.lean:{ln}:2: error: could not unify")
        return (1 if errs else 0), "\n".join(errs)
    monkeypatch.setattr(dp, "_run_lean", run)
    return recorded


def test_apply_probe_judges_every_pair_in_a_room_it_can_load(
        scripted_lean, tmp_path):
    ws = _ws(tmp_path, ["P.A", "P.B", "P.C"])
    pairs = [
        ("(x : Nat) : x = x", "P.A", "P.A.good"),   # judged in batch [A]
        ("(x : Nat) : x = x", "P.B", "P.B.good"),   # judged in batch [B]
        ("(x : Nat) : x = x", "P.B", "P.B.bad"),    # real per-pair failure
        ("(x : Nat) : x = x", "P.C", "P.C.any"),    # module dropped
    ]
    flags = dp._batch_provable_via_apply(ws, "p", pairs)
    assert flags == [True, True, False, False]
    kinds = [k for k, _ in scripted_lean]
    assert "dedupe_probe_module_dropped" in kinds
    assert any("P.C" in d for k, d in scripted_lean
               if k == "dedupe_probe_module_dropped")
    assert "dedupe_probe_global_error" not in kinds, \
        "a bad module is a dropped module, not a refused batch"


def test_statement_defeq_probe_shares_the_partition(scripted_lean, tmp_path):
    ws = _ws(tmp_path, ["P.A", "P.B", "P.C"])
    pairs = [
        ("∀ x : Nat, x = x", "∀ y : Nat, y = y", "P.A"),
        ("∀ x : Nat, x = x", "∀ y : Nat, y = y", "P.B"),
        ("∀ x : Nat, x = x", "∀ y : Nat, y = y", "P.C"),
    ]
    flags = dp._batch_statement_defeq(ws, "p", pairs)
    assert flags == [True, True, False]
