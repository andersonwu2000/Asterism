"""`asterism lab build` — the WORKSPACE: a throwaway place to wake the
framework in, that can never reach the live one.

    <root>/base/                 the skeleton, materialised once per
                                 commit: `Tooling/`, `Asterism/`, the
                                 Lean project files and `Asterism.yaml`
                                 from `git archive <commit>`, plus empty
                                 `Library/`, `Benchmarks/` and
                                 `Problems/README.md`
    <root>/runs/<exp>/<arm>_r<n>/  a copy of it, with the slice imported,
                                 the arm's overlay applied and `.lake`
                                 linked

FIVE RULES, EACH ONE PAID FOR.

  * `Tooling/` COMES FROM A COMMIT, never the working tree. An
    experiment whose code is "whatever was unsaved at launch" cannot be
    re-run, and the tree carries edits that have nothing to do with the
    question being asked.
  * NO `.git` IN THE WORKSPACE. A link to the live repo puts every
    concurrent run's `git status` on the live index, and
    `agent.runtime._repo_status` degrades to "not a repo" under it.
  * NO `daemon.pid` IN THE TARGET. That marker means the directory is
    somebody's live workspace; rebuilding one wipes a running board.
  * THE SLICE LANDS THROUGH `carry import`. Not a copied `asterism.db`:
    carry owns the definition of "P's rows", it migrates a COPY of the
    bundle up to this workspace's schema on the way in (the 1119 lesson
    — a slice older than the schema is a slice whose workspace cannot be
    opened), and it re-renders and drift-checks what it landed.
  * AN OVERLAY REPLACES, IT DOES NOT CREATE. An overlay file with no
    target is an overlay whose prompt moved, and a byte-identical one is
    a control the report will call a variant. Both refuse.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import shutil
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path

from . import LabError, REPO, base_dir, runs_dir
from .snapshot import Slice

#: What `git archive <commit>` puts in the base. `Asterism.yaml` rides
#: along because a run's config is part of what it ran: taken from the
#: commit rather than from the operator's live file, an arm's baseline
#: is the framework's, and only the arm's `seats:` moves it.
ARCHIVE_PATHS = ("Tooling", "Asterism", "Asterism.yaml", "lakefile.lean",
                 "lake-manifest.json", "lean-toolchain")

#: Created empty in the base — a workspace with no problems in it is
#: still a valid one, and `carry import` mints the rest.
EMPTY_TREES = ("Library", "Benchmarks", "Problems")

#: What `Problems/README.md` says. The directory has to exist for the
#: lakefile's glob and for `db.problem_dir`; a marker file is how it
#: survives a copy that skips empty directories.
PROBLEMS_README = (
    "# Problems\n\n"
    "One directory per problem, `Problems/<Project>/<problem>/`.\n"
    "A lab workspace starts empty; `asterism lab build` lands exactly "
    "one problem here, imported from a slice.\n")

#: Never in a lab workspace. `.lake/packages` is deliberately NOT here:
#: it is the one heavy tree that IS linked (see `LINKED_TREES`).
FORBIDDEN = ("daemon.pid", ".asterism/daemon.pid", ".git")

#: Linked into the workspace instead of copied.
#:
#: `.lake/PACKAGES`, NOT `.lake`. The two halves of that directory are
#: opposites. `packages/` is Mathlib and its friends — 6.8 GB, built
#: once, only read once built, and the whole difference between a lab
#: run that starts now and one that starts tomorrow. `build/` is the
#: LIVE workspace's own output: 78 GB of it, written by the daemon that
#: is running right now, under lake's own lock. Linking the parent would
#: put a lab `lake build` inside that — writing this experiment's oleans
#: into the live tree and contending for its lock, which is precisely
#: what "the lab never writes the live workspace" forbids. So the
#: workspace gets its own `build/`, and pays a cold build of this
#: problem's modules for it.
LINKED_TREES = (".lake/packages",)

BASE_STAMP = "base.json"
WORKSPACE_STAMP = "workspace.json"

#: `<root>/sets/` — the standard test sets' own tree (the owner's, in
#: the private repo). Named here because the base reads its seed
#: problems out of it.
SETS_DIRNAME = "sets"


# ---------------------------------------------------------------------
# the base
# ---------------------------------------------------------------------

def resolve_commit(commit: "str | None") -> str:
    """A lab.yaml's `code_commit:` (or HEAD) as a full sha.

    Resolved once, up front: an experiment that says `HEAD` and is built
    twice across a commit would otherwise be two experiments wearing one
    name, and neither run's record could tell you which."""
    ref = (commit or "HEAD").strip()
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO), "rev-parse", "--verify", f"{ref}^{{commit}}"],
            capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        raise LabError(f"cannot resolve {ref!r} in {REPO}: {exc}") from None
    if out.returncode != 0:
        raise LabError(
            f"{ref!r} is not a commit in {REPO} — `code_commit:` names "
            f"the framework revision the arm runs, and the lab never "
            f"falls back to the working tree")
    return out.stdout.strip()


def _archive(commit: str, dest: Path) -> None:
    blob = subprocess.run(
        ["git", "-C", str(REPO), "archive", "--format=tar", commit,
         *ARCHIVE_PATHS],
        capture_output=True)
    if blob.returncode != 0:
        raise LabError(
            f"`git archive {commit[:12]}` failed: "
            f"{blob.stderr.decode('utf-8', 'replace')[:400]}")
    with tarfile.open(fileobj=io.BytesIO(blob.stdout)) as tf:
        tf.extractall(str(dest), filter="data")
    if not (dest / "Tooling" / "prompts" / "strategist").is_dir():
        raise LabError(
            f"the archive of {commit[:12]} carried no Tooling/prompts/ — "
            f"the commit predates the prompt tree, so no arm built on it "
            f"would be running the prompts it declares")


def ensure_base(root: Path, commit: str) -> Path:
    """`<root>/base/` at `commit`, materialised if it is not already.

    Rebuilt when the recorded commit differs rather than kept per
    commit: the base is a cache of one `git archive`, and a directory
    per commit would quietly accumulate a copy of `Tooling/` per
    experiment for a saving of about a second."""
    base = base_dir(root)
    stamp = base / BASE_STAMP
    if stamp.is_file():
        try:
            have = json.loads(stamp.read_text(encoding="utf-8"))
        except ValueError:
            have = {}
        if have.get("commit") == commit:
            return base
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True)
    _archive(commit, base)
    for rel in EMPTY_TREES:
        (base / rel).mkdir(parents=True, exist_ok=True)
    (base / "Problems" / "README.md").write_text(PROBLEMS_README,
                                                 encoding="utf-8")
    seeded = seed_base_problems(root, base)
    stamp.write_text(json.dumps(
        {"commit": commit, "built_utc": datetime.now(timezone.utc).isoformat(),
         "archive": list(ARCHIVE_PATHS), "seeded_problems": seeded},
        indent=2) + "\n", encoding="utf-8")
    return base


# ---------------------------------------------------------------------
# the base's own problems
# ---------------------------------------------------------------------

def seed_base_problems(root: Path, base: Path) -> "list[str]":
    """Copy `<root>/sets/`'s seed problems into the base and INITIALISE
    them, the way `asterism init` does. Returns the slugs.

    A standard test set is self-contained: its problems ship with the
    set (`sets/base/Problems/…`) instead of arriving in a slice, because
    a trap judged against a slice of union_closed would be measuring the
    slice. So the base — the skeleton every workspace is copied from —
    carries them already registered: root minted `frozen`, top group
    created from the charter, TREE/BRIEF rendered. Through
    `problems.init_problem`, the same chokepoint the CLI and the serve
    layer use; a second registration path is a second definition of what
    a registered problem is.

    IN-PROCESS AND AGAINST THE BASE'S OWN DB, never the live one:
    `init_problem` takes its workspace as an argument, so nothing here
    depends on the cwd.

    `force=True` — the type-check gate is SKIPPED here, and that is not
    a shortcut. The gate runs `lake build` on Root.lean/Defs.lean, and
    the base has no `.lake` at all: the dependency tree is junctioned
    per RUN workspace (`LINKED_TREES`), so a build at base time would
    have no Mathlib to check against and would refuse every seed. The
    seeds are the owner's, versioned with the set, and the first real
    build of them happens in the run workspace like any other problem's.

    Idempotent: `init_problem` re-inits a registered problem without
    minting a second root, so this runs on every `ensure_base`.
    """
    from ..core.cli.problems import init_problem
    from ..state import db as _db

    root, base = Path(root), Path(base)
    seeds = _seed_dirs(root)
    if not seeds:
        return []
    (base / "Problems").mkdir(parents=True, exist_ok=True)
    done: "list[str]" = []
    for src in seeds:
        rel = src.relative_to(root / SETS_DIRNAME / "base" / "Problems")
        dst = base / "Problems" / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dst, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__"))
        problem = _db.slug_from_problem_dir(base, dst)
        rc, msg = init_problem(base, problem, force=True)
        if rc != 0:
            raise LabError(
                f"the base could not initialise the seed problem "
                f"{problem!r} from {src}: {msg}")
        print(f"[lab] base problem {problem} — {msg.splitlines()[-1]}",
              flush=True)
        done.append(problem)
    return done


def _seed_dirs(root: Path) -> "list[Path]":
    """`sets/standard.yaml`'s `base.problems`, absolute. Empty when the
    root holds no standard sets — `lab build` predates them and every
    experiment that does not use one still builds a bare skeleton."""
    from .standard import base_problem_dirs
    return base_problem_dirs(root)


# ---------------------------------------------------------------------
# the workspace
# ---------------------------------------------------------------------

def workspace_path(root: Path, exp: str, arm: str, rep: int) -> Path:
    return runs_dir(root, exp) / f"{arm}_r{rep}"


def next_rep(root: Path, exp: str, arm: str) -> int:
    """The lowest `r<n>` nobody has taken. Never reuses a directory: a
    rebuilt run dir would put a fresh workspace on top of the `_out/` of
    the run that already happened there."""
    n = 1
    while workspace_path(root, exp, arm, n).exists():
        n += 1
    return n


@contextlib.contextmanager
def in_workspace(ws: Path):
    """chdir into a workspace and back.

    The framework's write chokepoints — `carry import` among them — open
    the DB through the cwd-relative default path, exactly as every
    terminal invocation does. Standing somewhere else and passing a path
    would be a second way to name a workspace, and the two would drift."""
    prev = Path.cwd()
    os.chdir(ws)
    try:
        yield ws
    finally:
        os.chdir(prev)


def _assert_no_forbidden(ws: Path) -> None:
    for rel in FORBIDDEN:
        p = ws / rel
        if p.exists() or p.is_symlink():
            raise LabError(f"{ws}: {rel} must not exist in a lab workspace")


def _link_or_copy(src: Path, dst: Path) -> str:
    """Junction `src` into the workspace; copy it if links are refused.

    Windows junctions (`mklink /J`) need no privilege, which is why they
    are tried first and why this almost never falls back. It says which
    it did either way — a copied `.lake` is a different experiment from
    a shared one on both disk and cold-build time, and a reader of
    `workspace.json` has to be able to tell."""
    try:
        if os.name == "nt":
            subprocess.run(["cmd", "/c", "mklink", "/J", str(dst), str(src)],
                           check=True, capture_output=True)
        else:
            os.symlink(src, dst, target_is_directory=True)
        return "link"
    except (OSError, subprocess.SubprocessError):
        print(f"[lab] cannot link {dst.name} — COPYING {src} instead; the "
              f"workspace is now its own, and that is a different "
              f"experiment on disk and on cold-build time", flush=True)
        shutil.copytree(src, dst, symlinks=False)
        return "copy"


def clear_workspace(ws: Path, *, keep: "tuple[str, ...]" = ()) -> None:
    """Delete a workspace's contents, minus `keep`.

    THE LINKED TREES ARE UNLINKED, NEVER DESCENDED INTO.
    `.lake/packages` is a junction into the framework's own dependency
    tree — Mathlib's oleans, shared by every lab workspace on the box —
    and a delete that followed it would take the live tree with it. A
    top-level link is unlinked here; a nested one (which is where
    `.lake/packages` actually sits) is left to `rmtree`, which has not
    followed a junction since 3.8. Both depths are pinned by
    `tests/test_lab_build.py`, because an `onerror=` handler or a `copy`
    fallback added later would reintroduce exactly that.
    """
    ws = Path(ws)
    if not ws.is_dir():
        return
    for entry in sorted(ws.iterdir()):
        if entry.name in keep:
            continue
        if entry.is_symlink() or entry.is_junction():
            entry.unlink(missing_ok=True)
        elif entry.is_dir():
            shutil.rmtree(entry, ignore_errors=True)
        else:
            entry.unlink(missing_ok=True)


def _import_slice(ws: Path, slice_: Slice) -> None:
    """Land the slice with `carry import`, migrating a copy of its DB up
    to this workspace's schema on the way in."""
    from ..core.cli.carry import cmd_carry_import
    args = argparse.Namespace(bundle=str(slice_.path), problem=None,
                              dry_run=False, allow_migrate=True)
    with in_workspace(ws):
        rc = cmd_carry_import(args)
    if rc != 0:
        raise LabError(
            f"`carry import` refused the slice {slice_.id} (rc={rc}) — the "
            f"output above says which check; the workspace at {ws} is "
            f"left as it stands for the post-mortem")


def _apply_prompts(ws: Path, arm) -> "list[str]":
    applied: "list[str]" = []
    for rel, src in sorted(arm.prompts.items()):
        dst = ws / "Tooling" / "prompts" / rel
        if not dst.is_file():
            raise LabError(
                f"arm {arm.name!r}: overlay {rel} replaces nothing at "
                f"{dst} — the prompt it was cut from has moved, and the "
                f"arm would run against the unedited one while looking "
                f"like it worked")
        if dst.read_bytes() == src.read_bytes():
            raise LabError(
                f"arm {arm.name!r}: overlay {rel} is byte-identical to "
                f"the prompt it replaces — this arm is a control, and the "
                f"report would call it a variant")
        shutil.copyfile(src, dst)
        applied.append(f"Tooling/prompts/{rel}")
    return applied


def _apply_seats(ws: Path, arm) -> None:
    """Write the arm's seats into the workspace's own `Asterism.yaml`.

    Merged into the archived config, not written over it: an arm names
    the ONE seat it moves, and a file that replaced the whole config
    would silently take every other seat back to a built-in default."""
    import yaml
    if not arm.seats:
        return
    path = ws / "Asterism.yaml"
    try:
        cfg = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        cfg = {}
    if not isinstance(cfg, dict):
        cfg = {}
    for seat, keys in arm.seats.items():
        section = dict(cfg.get(seat) or {})
        section.update(keys)
        cfg[seat] = section
    path.write_text(
        "# Written by `asterism lab build` — the archived config with "
        "this arm's\n# seat overrides merged in. Edited by hand, this "
        "workspace stops\n# matching its own run_record.\n"
        + yaml.safe_dump(cfg, sort_keys=True, allow_unicode=True),
        encoding="utf-8")


def _compile_lake_config(ws: Path) -> None:
    """Establish the compiled lakefile configuration in the run
    workspace — once, here, before any driver is handed the directory.

    A fresh workspace's `.lake/` holds nothing but the `packages`
    junction, so the FIRST lake front-end to run in it compiles
    `lakefile.lean` into `.lake/config/`. A driver's daemon starts the
    gateway and its first `lake build` in the same second: two front-
    ends write that directory at once, the loser gets `compiled
    configuration is invalid; run with '-R' to reconfigure`, and every
    later invocation in the workspace reads the same thing — which is
    how the 2026-09-06 even_sum smoke run died on `[verify] FAILED`
    with an unbuilt problem and an empty queue.

    A workspace handed to a driver must never be the first thing to
    compile the lakefile. Refuses loudly with lake's output: a run
    launched on a workspace lake cannot configure has no Lean in it at
    all, and would spend its budget discovering that."""
    from ..pipeline._lake import lake_reconfigure
    ok, out = lake_reconfigure(ws)
    if not ok:
        raise LabError(
            f"lake could not configure {ws} — the workspace is not "
            f"runnable, and a driver started on it would fail every "
            f"build with no way to tell why:\n{out}")
    print(f"[lab] lake configuration compiled in {ws.name} "
          f"({out.splitlines()[-1] if out else 'no output'})", flush=True)


def build(root: Path, exp, arm_name: str, *, slice_: "Slice | None",
          base: "Path | None" = None, commit: "str | None" = None,
          rep: "int | None" = None) -> Path:
    """Build one workspace and return its path.

    `slice_=None` is a workspace that starts from the BASE alone —
    which is what a standard set's own problems are: seeded into the
    base and initialised there, so there is no live scene to import and
    `carry import` would have nothing to land."""
    arm = exp.arm(arm_name)
    commit = commit or resolve_commit(exp.code_commit)
    base = base if base is not None else ensure_base(root, commit)
    rep = rep if rep is not None else next_rep(root, exp.name, arm_name)
    ws = workspace_path(root, exp.name, arm_name, rep)

    for rel in FORBIDDEN:
        if (ws / rel).exists():
            raise LabError(
                f"{ws} holds {rel} — a daemon owns that workspace, or it "
                f"is a checkout. The lab never rebuilds over one; pick "
                f"another rep or clear it by hand.")
    if ws.exists():
        # Through `clear_workspace`, not `rmtree`: a previous build's
        # `.lake` junction is still there, and the shared tree behind it
        # is not this workspace's to delete.
        clear_workspace(ws)
        ws.rmdir()
    ws.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(base, ws,
                    ignore=shutil.ignore_patterns("__pycache__", BASE_STAMP))
    (ws / ".attempts").mkdir(exist_ok=True)
    (ws / ".asterism").mkdir(exist_ok=True)

    if slice_ is not None:
        _import_slice(ws, slice_)
    prompts = _apply_prompts(ws, arm)
    _apply_seats(ws, arm)

    links: "dict[str, str]" = {}
    for rel in LINKED_TREES:
        src = REPO / rel
        if src.is_dir():
            (ws / rel).parent.mkdir(parents=True, exist_ok=True)
            links[rel] = _link_or_copy(src, ws / rel)
        else:
            links[rel] = "absent"
    _assert_no_forbidden(ws)
    # After the junction, because the configuration lake compiles names
    # the dependency tree it found.
    _compile_lake_config(ws)

    (ws / WORKSPACE_STAMP).write_text(json.dumps({
        "experiment": exp.name,
        "arm": arm_name,
        "rep": rep,
        "kind": arm.kind,
        "slice": slice_.id if slice_ is not None else None,
        "slice_manifest": slice_manifest(slice_),
        "commit": commit,
        "built_utc": datetime.now(timezone.utc).isoformat(),
        "overlay": {"prompts": prompts, "seats": arm.seats},
        "links": links,
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[lab] built {ws} — slice "
          f"{slice_.id if slice_ is not None else 'none (base only)'}, "
          f"commit {commit[:12]}, overlay {prompts or 'none'}", flush=True)
    return ws


#: What a record keeps of the slice's manifest: where and when the
#: scene came from, and how big it was.
SLICE_MANIFEST_KEYS = ("problem", "taken_utc", "programme_rev", "goal_count",
                       "code_commit", "schema_user_version", "rewind")


def slice_manifest(slice_: "Slice | None") -> dict:
    if slice_ is None:
        return {}
    return {k: slice_.manifest.get(k) for k in SLICE_MANIFEST_KEYS}
