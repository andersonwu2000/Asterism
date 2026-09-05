"""Build the theory-wake experiment's scratch workspaces and run the
matrix in them, concurrently (2026-09-04).

The arms of one matrix run at ONE spacetime — the live state as of the
build, group 691 of `Combinatorics.union_closed`, the configured seats.
A matrix launched later takes its OWN snapshot (the daemon never stops),
so each run's record carries the instant its copy was taken and the
Programme revision that copy holds.

  arm2  / arm4 / arm24  a normal Strategist wake (`replay_strategist`:
                        agent → verify → judge loop → commit into the
                        SCRATCH DB) with the arm's prompt overlay laid
                        over the workspace's own `Tooling/prompts/`.
  arm3                  the theory wake (`theory_wake`): one document,
                        one reviewer, up to three revisions.
  arm3h                 arm3 with the Context's `## Owner's notes`
                        removed.
  arm5F / arm5X         the theory wake under the four-criterion judge
                        (`theory5_judge.md`), the author's report shape
                        fixed (5F) or left to the mathematics (5X).

The snapshot is taken ONCE per matrix — a `mode=ro` connection and the
sqlite backup API, which is WAL-safe against the daemon writing
underneath — and copied into every workspace, so the runs of that
matrix really do start from the same instant rather than from as many
instants a minute apart.

Two things the workspaces deliberately do NOT carry: `.git` (a symlink
to the live repo would put ten concurrent `git status` calls on the
live index — `agent.runtime._repo_status` degrades to "not a repo" and
the artifact audit is not what this experiment measures) and `.lake`
(the NL layer builds no Lean).

    python -m Tooling.experiments.run_matrix --build --launch
    python -m Tooling.experiments.run_matrix --build --launch \
        --matrix arm3:1 --exp-root D:/Asterism_exp
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

REPO = Path(__file__).resolve().parents[2]

#: The matrix's own design files — each theory arm's author and judge
#: prompt, each pipeline arm's prompt overlay — beside the runner that
#: copies them into a workspace. They lived in the operator's private
#: tree until it moved out of the workspace (owner ruling 2026-09-06);
#: a runner whose inputs are not in the repo is re-runnable only on the
#: machine that happens to hold them, and on 2026-09-06 the move alone
#: made `--build` fail for every arm.
DESIGN_DIR = Path(__file__).resolve().parent / "_design" / "theory_wake"
OVERLAY_ROOT = DESIGN_DIR / "prompts"

#: Where the runs land — OUTSIDE the repo. A run's artefacts are lab
#: material (transcripts, verdicts, a copy of the scratch DB's rows),
#: not framework source, and `--runs-dir` overrides this anyway.
RUNS_ROOT = Path("D:/Asterism_lab/runs")

PROBLEM = "Combinatorics.union_closed"
GROUP = 691
TRIGGER = "inject_batch_done"

class Arm(NamedTuple):
    """One arm of the matrix.

    A pipeline arm is defined by its prompt OVERLAY (a directory under
    `prompts/` whose every file replaces one of the workspace's own).
    A theory arm has no overlay: it is defined by the two prompts it
    names, which are files of this design directory and are copied into
    the workspace's `theory_prompts/`. The arm is what binds prompt to
    run — arms 5F and 5X differ in the author's prompt alone, and a
    binding read from anywhere else would run one of them twice while
    looking like it worked.
    """
    overlay: "str | None" = None
    theory: bool = False
    flags: "tuple[str, ...]" = ()
    author_prompt: str = "theory.md"
    judge_prompt: str = "theory_judge.md"


ARMS = {
    "arm2": Arm(overlay="arm2"),
    "arm4": Arm(overlay="arm4"),
    "arm24": Arm(overlay="arm24"),
    "arm3": Arm(theory=True),
    "arm3h": Arm(theory=True, flags=("--hide-owner-notes",)),
    # 2026-09-04, second matrix: the four-criterion rubric (worth /
    # rigour / load-bearing work / leads) on a fixed report shape (5F)
    # and on a free one (5X). Same judge, same Context, notes present.
    "arm5F": Arm(theory=True, author_prompt="theory5F.md",
                 judge_prompt="theory5_judge.md"),
    "arm5X": Arm(theory=True, author_prompt="theory5X.md",
                 judge_prompt="theory5_judge.md"),
}

DEFAULT_MATRIX = "arm2:2,arm4:2,arm24:2,arm3:2,arm3h:2"

#: Copied verbatim from the live workspace into every scratch. The
#: problem tree and its Project's document root are both here: the
#: papers and the owner's notes live under `Problems/<project>/_docs`
#: since §3.9 retired the workspace-global shelf, and a judge whose
#: `{papers_dir}` does not exist burns a round finding that out.
#:
#: This tree is the LIVE one at build time, which is right for a matrix
#: (it runs at now, `--since` is `now()`). A workspace built this way
#: and then rewound to an earlier cutoff must additionally run
#: `timetravel.rewind_files(..., cutoff=...)`: the DB rewind moves no
#: files, so BOTH trees above would still hold everything written after
#: the cutoff. `proofs/` cost the 2026-09-04 judge replay a rebuttal for
#: re-dispatching a proof that had not landed yet; `_docs/` cost the
#: second one two fires citing an owner note written 10.4 hours later.
#: `rewind_files` covers `proofs/`, `_docs/`, the run-scoped scratch and
#: the rendered companions in one call — `prune_proof_files` alone is
#: the state that produced the second leak.
COPY_TREES = (
    "Problems/Combinatorics/union_closed",
    "Problems/Combinatorics/_docs",
    "Library",
    "Benchmarks",
    "Asterism",
)
COPY_FILES = ("Asterism.yaml", ".env", "lakefile.lean",
              "lake-manifest.json", "lean-toolchain")

#: Never in a scratch: the marker `push_wake.assert_scratch` and both
#: replay runners refuse on, and the two symlinks discussed above.
FORBIDDEN = ("daemon.pid", ".asterism/daemon.pid", ".git", ".lake")


# ---------------------------------------------------------------------
# the snapshot
# ---------------------------------------------------------------------

def snapshot_db(live_db: Path, dst: Path) -> None:
    """One consistent copy of the live DB, taken while a daemon writes.

    `mode=ro` plus the backup API: the read side takes no write lock and
    the copy is a single atomic step, so the daemon's own transactions
    neither block it nor bleed into it. Never `shutil.copyfile` — in WAL
    mode the committed state lives partly in `-wal`, and a bare file
    copy silently loses it.
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        dst.unlink()
    src = sqlite3.connect(f"file:{live_db.as_posix()}?mode=ro", uri=True)
    try:
        out = sqlite3.connect(str(dst))
        try:
            src.backup(out)
        finally:
            out.close()
    finally:
        src.close()
    verify_db(dst)


def snapshot_meta_path(snapshot: Path) -> Path:
    """The sidecar beside a snapshot DB recording when it was taken."""
    return snapshot.with_suffix(".json")


def snapshot_record(snapshot: Path) -> dict:
    """What a run started from: the copy, the instant it was taken, and
    the Programme revision it carries.

    The live state moves under the experiment — the daemon never stops —
    so a matrix launched after an earlier one is NOT at the same
    spacetime as it, and two arms' documents are comparable only against
    the state they each saw. The sidecar carries the instant (only the
    process that took the copy knows it); the rev is read back out of
    the copy itself, so a record can be rebuilt from the DB alone.
    """
    p = snapshot_meta_path(snapshot)
    if p.is_file():
        try:
            return dict(json.loads(p.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass
    return {"snapshot": snapshot.as_posix(), "taken_utc": None,
            **verify_db(snapshot)}


def verify_db(path: Path) -> dict:
    """The copy opens, and it carries the group the matrix runs on."""
    c = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        row = c.execute("SELECT id, problem, status FROM groups "
                        "WHERE id = ?", (GROUP,)).fetchone()
        if row is None:
            raise SystemExit(f"{path}: no group {GROUP} in the copy")
        rev = c.execute("SELECT MAX(rev) FROM programme_revisions "
                        "WHERE group_id = ? AND status = 'passed'",
                        (GROUP,)).fetchone()[0]
        goals = c.execute("SELECT COUNT(*) FROM goals WHERE problem = ?",
                          (PROBLEM,)).fetchone()[0]
        return {"group": row[0], "problem": row[1], "status": row[2],
                "programme_rev": rev, "goals": goals}
    finally:
        c.close()


# ---------------------------------------------------------------------
# the workspace
# ---------------------------------------------------------------------

def tooling_at_head(ws: Path) -> None:
    """`Tooling/` exactly as HEAD has it — never the working tree.

    An experiment whose code is "whatever was unsaved at launch" cannot
    be re-run, and the working tree carries edits (gateway, ram ledger)
    that have nothing to do with this question.
    """
    blob = subprocess.run(
        ["git", "-C", str(REPO), "archive", "--format=tar", "HEAD",
         "Tooling"],
        capture_output=True, check=True).stdout
    with tarfile.open(fileobj=io.BytesIO(blob)) as tf:
        tf.extractall(ws)
    if not (ws / "Tooling" / "prompts" / "strategist").is_dir():
        raise SystemExit("the HEAD archive carried no Tooling/prompts/")


def apply_overlay(ws: Path, arm: str) -> "list[str]":
    """Lay the arm's prompt edits over the workspace's own prompts.

    Every overlay file must REPLACE one — an overlay that creates a new
    file is an overlay whose target moved, and it would run the arm
    against the unedited prompt while looking like it worked.

    A theory arm's files are not prompts of the pipeline at all (the
    theory wake's author and judge prompts are its own), so the two the
    arm names land beside the workspace as `theory_prompts/` instead —
    those two and nothing else, so no other arm's prompt is reachable
    from the workspace by a mistyped path.
    """
    spec = ARMS[arm]
    applied: list[str] = []
    if spec.theory:
        dst_dir = ws / "theory_prompts"
        dst_dir.mkdir(parents=True, exist_ok=True)
        for rel in (spec.author_prompt, spec.judge_prompt):
            src = DESIGN_DIR / rel
            if not src.is_file():
                raise SystemExit(f"{arm}: no prompt file at {src}")
            shutil.copyfile(src, dst_dir / src.name)
            applied.append(f"theory_prompts/{src.name}")
        return applied
    src = OVERLAY_ROOT / spec.overlay
    if not src.is_dir():
        raise SystemExit(f"{arm}: no overlay at {src} — the arm's prompt "
                         f"edits ship with the repo; restore them there")
    for p in sorted(src.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(src)
        dst = ws / "Tooling" / "prompts" / rel
        if not dst.is_file():
            raise SystemExit(
                f"{arm}: overlay file {rel.as_posix()} replaces nothing "
                f"at {dst} — the prompt it was cut from has moved")
        if dst.read_bytes() == p.read_bytes():
            raise SystemExit(
                f"{arm}: overlay file {rel.as_posix()} is byte-identical "
                f"to the live prompt — this arm would be a control")
        shutil.copyfile(p, dst)
        applied.append(f"Tooling/prompts/{rel.as_posix()}")
    return applied


def build_workspace(ws: Path, arm: str, snapshot: Path) -> dict:
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True)
    shutil.copyfile(snapshot, ws / "asterism.db")
    tooling_at_head(ws)
    applied = apply_overlay(ws, arm)
    for rel in COPY_TREES:
        src = REPO / rel
        if src.is_dir():
            shutil.copytree(src, ws / rel,
                            ignore=shutil.ignore_patterns("__pycache__"))
    for rel in COPY_FILES:
        src = REPO / rel
        if src.is_file():
            shutil.copyfile(src, ws / rel)
    for rel in FORBIDDEN:
        p = ws / rel
        if p.exists() or p.is_symlink():
            raise SystemExit(f"{ws}: {rel} must not exist in a scratch")
    return {"workspace": ws.as_posix(), "arm": arm,
            "overlay": applied, "db": verify_db(ws / "asterism.db")}


# ---------------------------------------------------------------------
# the runs
# ---------------------------------------------------------------------

def command_for(arm: str, run_dir: Path) -> "list[str]":
    spec = ARMS[arm]
    if spec.theory:
        return [sys.executable, "-m", "Tooling.experiments.theory_wake",
                "--workspace", ".", "--problem", PROBLEM,
                "--group", str(GROUP), "--trigger", TRIGGER,
                "--author-prompt",
                f"theory_prompts/{Path(spec.author_prompt).name}",
                "--judge-prompt",
                f"theory_prompts/{Path(spec.judge_prompt).name}",
                "--rounds", "3", "--out", str(run_dir), *spec.flags]
    return [sys.executable, "-m",
            "Tooling.experiments.replay_strategist",
            "--workspace", ".", "--problem", PROBLEM,
            "--group", str(GROUP), "--trigger", TRIGGER,
            "--since", datetime.now(timezone.utc).isoformat(),
            *spec.flags]


#: The pipeline id a run prints for itself — `[theory] … pipeline=<id>`
#: from the theory wake, `"pipeline_id": "<id>"` in the replay's result
#: JSON. Both runners emit one, which is what makes the binding below
#: possible without the collector guessing.
_PIPELINE_RE = re.compile(
    r"pipeline(?:_id)?[=\"':\s]+"
    r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}"
    r"-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})")


def pipeline_id_from_log(log_path: Path) -> "str | None":
    """The pipeline THIS run created, read from its own stdout."""
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    m = _PIPELINE_RE.search(text)
    return m.group(1) if m else None


def collect(ws: Path, arm: str, run_dir: Path) -> dict:
    """Copy this run's artefacts out of the scratch.

    The theory wake already wrote its own into `--out`; what is left is
    the replay's, which lives in the pipeline's attempts dir (the wake
    does not tear it down) plus the rows it committed into the scratch
    DB.

    Bound to the pipeline the run PRINTED, not to the newest marker
    file: a scratch can hold more than one wake. arm3h_r2's did on
    2026-09-04 — its first run died on a verdict rendering and was
    relaunched into the same workspace — and an mtime pick would have
    copied the dead wake's artefacts over the live one's. The glob
    stays as the fallback for a run that died before printing an id.
    """
    run_dir.mkdir(parents=True, exist_ok=True)
    kept: list[str] = []
    theory = ARMS[arm].theory
    marker = "theory_result.json" if theory else "replay_result.json"
    attempts = None
    bound = pipeline_id_from_log(run_dir / "run.log")
    if bound and (ws / ".attempts" / bound / marker).is_file():
        attempts = ws / ".attempts" / bound
    else:
        hits = sorted((ws / ".attempts").glob(f"*/{marker}"),
                      key=lambda p: p.stat().st_mtime)
        if not hits:
            return {"kept": kept, "bound_pipeline": bound,
                    "note": f"no {marker} under .attempts/"}
        attempts = hits[-1].parent
    names = ("replay_result.json", "theory_result.json", "Context.md",
             "proposal.md", "decision.json", "_plan_full.md",
             "_context_stats.json", "charter.md", "TREE.md",
             "CATALOG.md", "BATCHES.md", "ADJUDICATIONS.md",
             "report.md")
    for name in names:
        p = attempts / name
        if p.is_file():
            shutil.copyfile(p, run_dir / name)
            kept.append(name)
    # From the dir this collection is BOUND to, never from whichever
    # marker the glob happened to rank last — the two are the same
    # file only when the fallback chose it.
    result = json.loads((attempts / marker).read_text(encoding="utf-8"))
    if not theory:
        ids = [r["id"] for r in result.get("programme_revisions", [])]
        if ids:
            c = sqlite3.connect(
                f"file:{(ws / 'asterism.db').as_posix()}?mode=ro", uri=True)
            c.row_factory = sqlite3.Row
            try:
                rows = [dict(r) for r in c.execute(
                    "SELECT * FROM programme_revisions WHERE id IN (%s)"
                    % ",".join("?" * len(ids)), ids)]
            finally:
                c.close()
            for row in rows:
                # `dialogue` is a JSON blob in the column; inline it so
                # the artefact is one readable document.
                try:
                    row["dialogue"] = json.loads(row["dialogue"] or "null")
                except (TypeError, ValueError):
                    pass
            (run_dir / "programme_revisions.json").write_text(
                json.dumps(rows, ensure_ascii=False, indent=2),
                encoding="utf-8")
            kept.append("programme_revisions.json")
    return {"kept": kept, "attempts_dir": attempts.as_posix(),
            "bound_pipeline": bound, "result": result}


def status_line(arm: str, k: int, rec: dict) -> str:
    r = rec.get("collected", {}).get("result") or {}
    if ARMS[arm].theory:
        tail = (f"outcome={r.get('outcome')} "
                f"rounds={len(r.get('rounds', []))} "
                f"author={Path(r.get('author_prompt') or '').name} "
                f"owner_notes="
                f"{'hidden' if r.get('hide_owner_notes') else 'present'}")
    else:
        revs = r.get("programme_revisions", [])
        tail = (f"outcome={r.get('outcome')} "
                f"reason={r.get('failure_reason')} "
                f"decisions={len(r.get('decisions', []))} "
                f"revs={[(x.get('rev'), x.get('status'), x.get('rounds'))
                         for x in revs]}")
    return (f"{arm}_r{k}: rc={rec.get('rc')} "
            f"wall={rec.get('wall_sec', 0):.0f}s {tail}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--exp-root", default="D:/Asterism_exp")
    ap.add_argument("--runs-dir", default=str(RUNS_ROOT))
    ap.add_argument("--matrix", default=DEFAULT_MATRIX,
                    help="comma list of <arm>:<runs>")
    ap.add_argument("--snapshot", default=None,
                    help="reuse an existing snapshot DB instead of "
                         "taking a fresh one")
    ap.add_argument("--build", action="store_true",
                    help="(re)build the workspaces")
    ap.add_argument("--launch", action="store_true",
                    help="launch the runs and wait for them")
    a = ap.parse_args(argv)
    from . import harden_console
    harden_console()

    exp_root = Path(a.exp_root).resolve()
    runs_dir = Path(a.runs_dir).resolve()
    matrix: "list[tuple[str, int]]" = []
    for part in a.matrix.split(","):
        arm, _, n = part.strip().partition(":")
        if arm not in ARMS:
            raise SystemExit(f"unknown arm {arm!r}; have {sorted(ARMS)}")
        matrix.append((arm, int(n or 1)))

    snapshot = (Path(a.snapshot).resolve() if a.snapshot
                else exp_root / "_snapshot.db")
    if a.build:
        if a.snapshot is None:
            print(f"[matrix] snapshotting the live DB → {snapshot}",
                  flush=True)
            snapshot_db(REPO / "asterism.db", snapshot)
            snapshot_meta_path(snapshot).write_text(json.dumps(
                {"snapshot": snapshot.as_posix(),
                 "taken_utc": datetime.now(timezone.utc).isoformat(),
                 **verify_db(snapshot)}, indent=2), encoding="utf-8")
        print(f"[matrix] snapshot: {snapshot_record(snapshot)}", flush=True)
        for arm, n in matrix:
            for k in range(1, n + 1):
                ws = exp_root / f"{arm}_r{k}"
                info = build_workspace(ws, arm, snapshot)
                print(f"[matrix] built {ws} — overlay "
                      f"{info['overlay']}", flush=True)
    if not a.launch:
        return 0

    procs: "list[tuple[str, int, Path, Path, subprocess.Popen, object, float]]" = []
    # The spacetime each run starts from, read BEFORE it runs: the
    # snapshot's instant, and the Programme revision this workspace's
    # own copy carries (a replay arm commits into its copy, so the same
    # question asked afterwards answers about the end state).
    snap_rec = snapshot_record(snapshot)
    started: "dict[tuple[str, int], dict]" = {}
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    for arm, n in matrix:
        for k in range(1, n + 1):
            ws = exp_root / f"{arm}_r{k}"
            if not (ws / "asterism.db").is_file():
                raise SystemExit(f"{ws}: not built — pass --build")
            started[(arm, k)] = {"snapshot": snap_rec,
                                 "db_at_launch": verify_db(ws / "asterism.db"),
                                 "arm": ARMS[arm]._asdict()}
            run_dir = runs_dir / f"{arm}_r{k}"
            run_dir.mkdir(parents=True, exist_ok=True)
            cmd = command_for(arm, run_dir)
            log = open(run_dir / "run.log", "w", encoding="utf-8",
                       buffering=1)
            log.write(f"$ cd {ws} && {' '.join(cmd)}\n")
            log.flush()
            p = subprocess.Popen(cmd, cwd=str(ws), env=env, stdout=log,
                                 stderr=subprocess.STDOUT,
                                 stdin=subprocess.DEVNULL)
            procs.append((arm, k, ws, run_dir, p, log,
                          time.monotonic()))
            print(f"[matrix] launched {arm}_r{k} pid={p.pid} "
                  f"log={run_dir / 'run.log'}", flush=True)

    records: "list[tuple[str, int, dict]]" = []
    for arm, k, ws, run_dir, p, log, t0 in procs:
        rc = p.wait()
        log.close()
        rec = {"rc": rc, "wall_sec": time.monotonic() - t0,
               "workspace": ws.as_posix(), **started[(arm, k)]}
        try:
            rec["collected"] = collect(ws, arm, run_dir)
        except Exception as e:  # noqa: BLE001 — a broken run must not
            rec["collected"] = {"error": repr(e)}  # eat the others
        (run_dir / "run_record.json").write_text(
            json.dumps(rec, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8")
        records.append((arm, k, rec))
        print(f"[matrix] done {arm}_r{k} rc={rc}", flush=True)

    print("\n=== theory-wake matrix ===", flush=True)
    for arm, k, rec in records:
        print(status_line(arm, k, rec), flush=True)
    return 0 if all(r["rc"] == 0 for _, _, r in records) else 1


if __name__ == "__main__":
    sys.exit(main())
