"""`asterism lab run` — build a fresh workspace per repetition, wake the
arm's driver in it, and keep the RECORD.

    <root>/runs/<exp>/<arm>_r<n>/          the workspace (deleted after)
    <root>/runs/<exp>/<arm>_r<n>/_out/     artefacts + transcripts (kept)
    <root>/runs/<exp>/<arm>_r<n>/run_record.json

WHAT THE RECORD HAS TO ANSWER, and why each one is in it rather than
derivable later:

  slice + code commit    the workspace is gone; nothing else can say
                         what scene and what code this ran on.
  prompt sha256          per file under the workspace's OWN
                         `Tooling/prompts/`. Not the arm's declared
                         overlay: the declaration is what was ASKED FOR
                         and the hashes are what the seat actually read,
                         and the gap between those is every "the arm ran
                         the unedited prompt and looked like it worked"
                         failure this lab exists to stop.
  seats                  read INSIDE the workspace by the driver, from
                         the config the run used. Reading a filename is
                         how a run gets attributed to a model it never
                         used (memory: `which_models_actually_ran`).
  tokens / turns / wall  the provider's own accounting, out of the
                         workspace's `spawn_usage`.
  outcome + artefacts    what came back, and where it is.

Transcripts are the builder's responsibility, not the seat's: claude
files them under `~/.claude/projects/<munged cwd>/` and codex under the
workspace's own `.asterism/codex_sessions/`, and the first of those
survives the workspace being deleted only if something copies it out
first.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from . import LabError, runs_dir
from . import build as _build
from . import snapshot as _snapshot
from .driver import RESULT_BASENAME

OUT_DIRNAME = "_out"
RECORD_BASENAME = "run_record.json"
SPEC_BASENAME = "_driver_spec.json"

#: What survives the workspace being cleared. `lab gc` reads exactly
#: this pair to decide a run dir is finished.
KEEP_AFTER_RUN = (OUT_DIRNAME, RECORD_BASENAME)


# ---------------------------------------------------------------------
# the prompts the seat actually read
# ---------------------------------------------------------------------

def prompt_hashes(ws: Path) -> "dict[str, str]":
    """sha256 per file under the workspace's `Tooling/prompts/`.

    Every file, not the arm's declared overlay: the declaration says
    what was asked for, this says what was there. An overlay whose
    target moved, a prompt the archived commit never had, a hand-edit
    somebody made in the workspace between build and run — all three are
    invisible in the declaration and all three are a different
    experiment."""
    root = Path(ws) / "Tooling" / "prompts"
    out: "dict[str, str]" = {}
    if not root.is_dir():
        return out
    for p in sorted(root.rglob("*")):
        if p.is_file():
            out[p.relative_to(root).as_posix()] = hashlib.sha256(
                p.read_bytes()).hexdigest()
    return out


# ---------------------------------------------------------------------
# transcripts
# ---------------------------------------------------------------------

def claude_transcript_dir(cwd: Path) -> Path:
    """`~/.claude/projects/<munged cwd>/` — the CLI's own home for a
    session's jsonl, outside the framework's scratch and never pruned.

    The munge is "every character that is not a letter or a digit
    becomes `-`" (`D:\\Asterism` -> `D--Asterism`). It is the claude
    CLI's rule, not ours, so it is spelled once, here."""
    return (Path.home() / ".claude" / "projects"
            / re.sub(r"[^A-Za-z0-9]", "-", str(Path(cwd))))


def collect_transcripts(ws: Path, out: Path) -> "list[str]":
    """Both providers' reasoning, copied out before the workspace goes.

    codex keeps its rollout inside the workspace (`_preserve_transcript`
    moves it out of the doomed per-spawn home), so it dies with the
    workspace unless it is copied. claude keeps its jsonl in its own
    home under a name derived from the cwd, which survives — but a
    reader a week later should not have to reconstruct the munge to find
    it."""
    kept: "list[str]" = []
    codex = ws / ".asterism" / "codex_sessions"
    if codex.is_dir():
        dst = out / "transcripts" / "codex"
        if dst.exists():
            shutil.rmtree(dst, ignore_errors=True)
        shutil.copytree(codex, dst)
        kept.append("transcripts/codex")
    claude = claude_transcript_dir(ws)
    if claude.is_dir():
        dst = out / "transcripts" / "claude"
        dst.mkdir(parents=True, exist_ok=True)
        for jsonl in sorted(claude.glob("*.jsonl")):
            shutil.copyfile(jsonl, dst / jsonl.name)
            kept.append(f"transcripts/claude/{jsonl.name}")
    return kept


# ---------------------------------------------------------------------
# launching the driver
# ---------------------------------------------------------------------

def driver_command(ws: Path, spec_path: Path) -> "list[str]":
    return [sys.executable, "-m", "Tooling.lab.driver",
            "--spec", str(spec_path)]


def launch_subprocess(ws: Path, spec_path: Path) -> "tuple[int, float]":
    """Run the driver as its own process with `cwd` in the workspace.

    `-m` puts the cwd first on `sys.path`, so `Tooling` resolves to the
    workspace's archived copy — which is the whole point of `git archive
    <commit>`, and which the driver re-checks on the way in
    (`assert_workspace_code`). PYTHONPATH is dropped for the same
    reason: an entry pointing at a checkout would win over the
    workspace for anything the cwd does not shadow."""
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env["PYTHONIOENCODING"] = "utf-8"
    cmd = driver_command(ws, spec_path)
    log = Path(ws) / OUT_DIRNAME / "run.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    with open(log, "w", encoding="utf-8", buffering=1) as fh:
        fh.write(f"$ cd {ws} && {' '.join(cmd)}\n")
        fh.flush()
        rc = subprocess.call(cmd, cwd=str(ws), env=env, stdout=fh,
                             stderr=subprocess.STDOUT,
                             stdin=subprocess.DEVNULL)
    return rc, time.monotonic() - t0


# ---------------------------------------------------------------------
# one repetition
# ---------------------------------------------------------------------

def run_once(root: Path, exp, arm_name: str, *, slice_, base: Path,
             commit: str, rep: int, keep: bool = False,
             launch=launch_subprocess) -> Path:
    """Build, wake, record, clean up. Returns the run directory."""
    arm = exp.arm(arm_name)
    ws = _build.build(root, exp, arm_name, slice_=slice_, base=base,
                      commit=commit, rep=rep)
    out = ws / OUT_DIRNAME
    out.mkdir(parents=True, exist_ok=True)
    spec = {
        "kind": arm.kind,
        "problem": slice_.problem,
        "cutoff": slice_.cutoff,
        "workspace": str(ws),
        "out": str(out),
        "source_db": str(slice_.source_db),
        "options": arm.options,
    }
    spec_path = ws / SPEC_BASENAME
    spec_path.write_text(json.dumps(spec, indent=2, ensure_ascii=False),
                         encoding="utf-8")

    hashes = prompt_hashes(ws)
    started = datetime.now(timezone.utc).isoformat()
    rc, wall = launch(ws, spec_path)
    result = {}
    rpath = out / RESULT_BASENAME
    if rpath.is_file():
        try:
            result = json.loads(rpath.read_text(encoding="utf-8"))
        except ValueError as exc:
            result = {"_unreadable": repr(exc)}

    artefacts = list(result.get("artefacts") or [])
    artefacts += collect_transcripts(ws, out)
    record = {
        "experiment": exp.name,
        "arm": arm_name,
        "rep": rep,
        "kind": arm.kind,
        "started_utc": started,
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "wall_sec": round(wall, 1),
        "rc": rc,
        "outcome": result.get("outcome") or ("failed" if rc else "unknown"),
        "slice": slice_.id,
        "slice_manifest": {
            k: slice_.manifest.get(k)
            for k in ("problem", "taken_utc", "programme_rev", "goal_count",
                      "code_commit", "schema_user_version", "rewind")},
        "code_commit": commit,
        "overlay": {"prompts": sorted(arm.prompts), "seats": arm.seats},
        "prompt_sha256": hashes,
        "seats": result.get("seats") or {},
        "usage": result.get("usage") or {},
        "driver_result": result,
        "artefacts": sorted(set(artefacts)),
        "workspace_kept": bool(keep),
    }
    (out / RECORD_BASENAME).write_text(
        json.dumps(record, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8")
    (ws / RECORD_BASENAME).write_text(
        json.dumps(record, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8")
    if not keep:
        # The workspace is throwaway BY DESIGN — "runs, then discarded;
        # there is no restore" (lab_design.md §2). `_out/` and the
        # record survive because they are the experiment; the rest is a
        # copy of a slice and a copy of a commit, both reproducible.
        _build.clear_workspace(ws, keep=KEEP_AFTER_RUN)
    print(f"[lab] {exp.name}/{arm_name}_r{rep}: rc={rc} "
          f"outcome={record['outcome']} wall={wall:.0f}s → {out}",
          flush=True)
    return ws


def resolve_slice(root: Path, exp, workspace: Path):
    """The slice the experiment names — loaded, or taken.

    `snapshot:` names one that must already be there; `rewind:` names a
    problem and an instant, which is reproducible, so it is taken once
    and reused by every later arm and repetition."""
    if exp.snapshot:
        return _snapshot.load(root, exp.snapshot)
    rw = exp.rewind or {}
    return _snapshot.ensure_slice(root, workspace=Path(workspace),
                                  problem=str(rw["problem"]),
                                  cutoff=str(rw["cutoff"]))


def run_arm(root: Path, exp, arm_name: str, *, workspace: Path,
            reps: "int | None" = None, keep: bool = False,
            launch=launch_subprocess) -> "list[Path]":
    """`--reps` repetitions of one arm, each in a workspace of its own.

    One slice and one base for all of them: repetitions are supposed to
    differ only in the seat's own variance, and a second snapshot taken
    a minute later is a second spacetime."""
    exp.arm(arm_name)                       # refuse an unknown arm early
    commit = _build.resolve_commit(exp.code_commit)
    base = _build.ensure_base(root, commit)
    slice_ = resolve_slice(root, exp, workspace)
    n = int(reps if reps is not None else exp.reps)
    if n < 1:
        raise LabError(f"--reps must be at least 1 (got {n})")
    done: "list[Path]" = []
    for _ in range(n):
        rep = _build.next_rep(root, exp.name, arm_name)
        done.append(run_once(root, exp, arm_name, slice_=slice_, base=base,
                             commit=commit, rep=rep, keep=keep,
                             launch=launch))
    return done


# ---------------------------------------------------------------------
# gc
# ---------------------------------------------------------------------

def is_finished(run_dir: Path) -> bool:
    """A run dir whose experiment is safely on disk: both survivors are
    there. Anything else is a run that is still going or that died
    part-way, and neither is gc's business."""
    return ((run_dir / OUT_DIRNAME).is_dir()
            and (run_dir / OUT_DIRNAME / RECORD_BASENAME).is_file())


def referenced_slices(root: Path) -> "set[str]":
    """Every slice id some `docs/<exp>/lab.yaml` names, plus the id a
    `rewind:` block would produce. A lab.yaml that cannot be parsed
    counts as referencing everything: gc never deletes on the strength
    of a file it failed to read."""
    from . import docs_dir
    from .spec import load as load_spec
    base = Path(root) / "docs"
    out: "set[str]" = set()
    if not base.is_dir():
        return out
    for d in sorted(base.iterdir()):
        if not (d / "lab.yaml").is_file():
            continue
        try:
            exp = load_spec(root, d.name)
        except LabError:
            print(f"[lab gc] {docs_dir(root, d.name) / 'lab.yaml'} does not "
                  f"parse — treating every slice as referenced", flush=True)
            return {s.id for s in _snapshot.list_slices(root)}
        if exp.snapshot:
            out.add(exp.snapshot)
        elif exp.rewind:
            out.add(_snapshot.slice_id(exp.rewind["problem"],
                                       cutoff=exp.rewind["cutoff"]))
    return out


def gc(root: Path, *, keep_latest: int = 3) -> dict:
    """Clear finished workspaces, and drop slices nothing points at
    beyond the newest N.

    Two different questions. A finished workspace is pure waste: its
    `_out/` and record are already written and everything else in it is
    a copy of a slice and a copy of a commit. A SLICE is not — it is
    what makes a run reproducible — so one is dropped only when no
    lab.yaml names it AND it is not among the newest few."""
    root = Path(root)
    cleared: "list[str]" = []
    runs = root / "runs"
    if runs.is_dir():
        for exp_dir in sorted(runs.iterdir()):
            for run_dir in sorted(p for p in exp_dir.iterdir()
                                  if p.is_dir()):
                if not is_finished(run_dir):
                    continue
                leftovers = [p.name for p in run_dir.iterdir()
                             if p.name not in KEEP_AFTER_RUN]
                if not leftovers:
                    continue
                _build.clear_workspace(run_dir, keep=KEEP_AFTER_RUN)
                cleared.append(
                    run_dir.relative_to(root).as_posix())
    referenced = referenced_slices(root)
    slices = _snapshot.list_slices(root)
    newest = {s.id for s in sorted(
        slices, key=lambda s: str(s.manifest.get("taken_utc") or ""),
        reverse=True)[:max(0, int(keep_latest))]}
    dropped: "list[str]" = []
    for s in slices:
        if s.id in referenced or s.id in newest:
            continue
        shutil.rmtree(s.path, ignore_errors=True)
        dropped.append(s.id)
    for line in cleared:
        print(f"[lab gc] cleared workspace {line}", flush=True)
    for sid in dropped:
        print(f"[lab gc] dropped slice {sid}", flush=True)
    print(f"[lab gc] {len(cleared)} workspace(s) cleared, "
          f"{len(dropped)} slice(s) dropped, "
          f"{len(slices) - len(dropped)} kept", flush=True)
    return {"cleared": cleared, "dropped": dropped,
            "kept": sorted({s.id for s in slices} - set(dropped))}
