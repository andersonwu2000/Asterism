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


# ------------------------------ transitive collisions (2026-08-30 fix)
#
# Lean names the module that FAILED to import — which is the transitive
# one (`L_four_packet_mask_certificate`, pulled in by a header module),
# not the header line that pulled it. The partition looked the name up
# in the header set, found nothing, and the whole room went out as a
# "header refused" global error: 81 times in one local run, 331 modules
# voided each time, the probe blind for that batch. And Lean stops at
# the FIRST collision, so a room with k colliders costs k cold rounds
# unless the names are compared before Lean is asked at all.

def _file(ws: Path, mod: str, text: str) -> None:
    p = ws / (mod.replace(".", "/") + ".lean")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_partition_attributes_a_transitive_collision_to_its_importer():
    at = {2: "Problems.p.proofs.L_a", 3: "Problems.p.proofs.L_b"}
    out = ("x.lean:1:0: error: import Problems.p.proofs.L_helper failed, "
           "environment already contains 'Problems.p.foo' from "
           "Problems.p.proofs.L_a")

    def closure(mod: str) -> set[str]:
        return {"Problems.p.proofs.L_helper"} if mod.endswith("L_b") else set()

    dropped, deferred = dp.partition_header_errors(out, at, closure=closure)
    assert deferred == ["Problems.p.proofs.L_b"], (dropped, deferred)
    assert not dropped


def test_import_batches_fall_back_to_the_closure_when_lean_names_a_helper(
        tmp_path):
    """The exact local failure shape: stub files carry no names to
    pre-house by, Lean names the helper, the importer must be deferred
    — never the whole room refused."""
    dp.import_batches.cache_clear()
    ws = tmp_path
    _file(ws, "P.A", "-- stub\n")
    _file(ws, "P.H", "-- stub\n")
    _file(ws, "P.B", "import P.H\n-- stub\n")
    runs: list[str] = []

    def run(content: str) -> tuple[int, str]:
        runs.append(content)
        if "import P.A" in content and "import P.B" in content:
            return 1, ("h.lean:1:0: error: import P.H failed, environment "
                       "already contains 'P.foo' from P.A")
        return 0, ""

    batches, dropped = dp.import_batches(ws, ["P.A", "P.B"], run)
    assert not dropped, f"a room was refused instead of split: {dropped}"
    assert sorted(map(sorted, batches)) == [["P.A"], ["P.B"]]
    assert len(runs) == 3   # collide → A alone → B alone


def test_import_batches_pre_house_by_closure_names_before_asking_lean(
        tmp_path):
    """Two header modules whose import closures define the same name
    never share a room, so Lean is never asked a header it will refuse."""
    dp.import_batches.cache_clear()
    ws = tmp_path
    _file(ws, "P.A", "theorem foo : True := trivial\n")
    _file(ws, "P.H", "theorem foo : True := trivial\n")
    _file(ws, "P.B", "import P.H\ntheorem bar : True := trivial\n")
    _file(ws, "P.C", "theorem baz : True := trivial\n")
    runs: list[str] = []

    def run(content: str) -> tuple[int, str]:
        runs.append(content)
        if "import P.A" in content and "import P.B" in content:
            return 1, ("h.lean:1:0: error: import P.H failed, environment "
                       "already contains 'foo' from P.A")
        return 0, ""

    batches, dropped = dp.import_batches(ws, ["P.A", "P.B", "P.C"], run)
    assert not dropped
    rooms = [set(b) for b in batches]
    assert not any({"P.A", "P.B"} <= r for r in rooms), rooms
    assert all(run_ok for run_ok in (
        not ("import P.A" in c and "import P.B" in c) for c in runs)), (
        "Lean was asked a header the names already ruled out")
    assert len(runs) == len(batches), "one clean header run per room"
