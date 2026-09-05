"""`asterism lab …` — the CLI shell over the four nouns.

Thin on purpose: every refusal worth making is made by the module that
owns the noun (`snapshot`, `spec`, `build`, `run`), and this layer turns
a `LabError` into the one thing a CLI owes its caller — a printed
message that names the action, and a non-zero rc.
"""
from __future__ import annotations

import argparse
import sys

from . import LabError, resolve_root
from . import build as _build
from . import run as _run
from . import snapshot as _snapshot
from . import spec as _spec
from . import standard as _standard

RC_OK, RC_FAIL = 0, 1


def _workspace() -> "object":
    from ..core import config
    return config.resolve_workspace(None)


def cmd_lab(args: argparse.Namespace) -> int:
    """`asterism lab <action>` — snapshot / build / run / gc."""
    # Idempotent, and here rather than only in `main()`: a script that
    # imports and calls this function is an entry point into the same
    # pipeline, and a `⚠` in a warning killed a whole wake once
    # (2026-09-03, push arm C run 2).
    from ..core.cli.run import _force_utf8_io
    _force_utf8_io()
    action = getattr(args, "lab_action", None)
    try:
        root = resolve_root(getattr(args, "root", None))
        if action == "snapshot":
            return _cmd_snapshot(args, root)
        if action == "build":
            return _cmd_build(args, root)
        if action == "run":
            return _cmd_run(args, root)
        if action == "gc":
            _run.gc(root, keep_latest=int(getattr(args, "keep_latest", 3)))
            return RC_OK
    except LabError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return RC_FAIL
    print(f"FAIL: unknown lab action {action!r}", file=sys.stderr)
    return RC_FAIL


def _cmd_snapshot(args: argparse.Namespace, root) -> int:
    problem = getattr(args, "scope", None)
    if not problem:
        raise LabError(
            "`lab snapshot` needs `--scope <problem>` — a slice is ONE "
            "problem's state (the union_closed slice is 78 MB against a "
            "2.5 GB whole-DB copy)")
    sl = _snapshot.take(_workspace(), root, problem=problem,
                        cutoff=getattr(args, "rewind", None) or None)
    m = sl.manifest
    print(f"OK: lab snapshot {problem} -> {sl.path}")
    print(f"  taken       {m['taken_utc']}")
    print(f"  code        {m.get('code_commit') or '?'}")
    print(f"  schema      v{m['schema_user_version']}")
    print(f"  scene       rev {m.get('programme_rev')} · "
          f"{m.get('goal_count')} goal(s)")
    print(f"  files       {m['files']['entries']} entr(ies)")
    if m.get("rewind"):
        print(f"  rewound to  {m['rewind']['cutoff']}")
        for key, row in sorted(m["rewind"]["directories"].items()):
            print(f"    {key}: kept {row['kept']} / dropped "
                  f"{row['dropped']} ({row['provenance']})")
        if m["rewind"]["undated"]:
            print(f"    {len(m['rewind']['undated'])} file(s) had NO "
                  f"provenance signal and were dropped")
    return RC_OK


def _need(args: argparse.Namespace) -> "tuple[str, str]":
    exp, arm = getattr(args, "exp", None), getattr(args, "arm", None)
    if not exp or not arm:
        raise LabError("usage: asterism lab <build|run> <experiment> <arm>")
    return str(exp), str(arm)


def _cmd_build(args: argparse.Namespace, root) -> int:
    exp_name, arm = _need(args)
    exp = _spec.load(root, exp_name)
    slice_ = _run.resolve_slice(root, exp, _workspace())
    ws = _build.build(root, exp, arm, slice_=slice_)
    print(f"OK: lab build {exp_name}/{arm} -> {ws}")
    return RC_OK


def seat_overrides(raw) -> "dict[str, str]":
    """`--seats seat=provider/model[:effort]` -> `{seat: spec}`.

    Split HERE and validated against the one seat parser, so a
    malformed one is refused while the operator is still looking at the
    command line — not minutes later, in a workspace already built."""
    out: "dict[str, str]" = {}
    for entry in list(raw or []):
        seat, sep, value = str(entry).partition("=")
        if not sep or not seat.strip() or not value.strip():
            raise LabError(
                f"--seats {entry!r} is not `seat=provider/model[:effort]` "
                f"(e.g. `--seats adversary=codex/gpt-5:xhigh`)")
        _spec._seat_spec(seat.strip(), value.strip())   # refuse it here
        out[seat.strip()] = value.strip()
    return out


def _cmd_run(args: argparse.Namespace, root) -> int:
    exp_name, arm = _need(args)
    seats = seat_overrides(getattr(args, "seats", None))
    if exp_name == _standard.EXPERIMENT_NAME:
        return _cmd_run_standard(args, root, arm, seats)
    exp = _spec.load(root, exp_name)
    if seats:
        exp = _spec.with_seats(exp, seats)
    dirs = _run.run_arm(root, exp, arm, workspace=_workspace(),
                        reps=getattr(args, "reps", None),
                        keep=bool(getattr(args, "keep", False)))
    print(f"OK: lab run {exp_name}/{arm} — {len(dirs)} rep(s)")
    for d in dirs:
        print(f"  {d / _run.OUT_DIRNAME}")
    return RC_OK


def _cmd_run_standard(args: argparse.Namespace, root, target: str,
                      seats: "dict[str, str]") -> int:
    """`lab run standard <set|item|all>` — run the sets and SCORE them.

    Non-zero when an item missed its expectation: a standard set is run
    to be told whether the framework still does what it did, and a
    runner that always returns 0 makes that answer something a human
    has to read the scrollback for."""
    rows = _standard.run(root, target, workspace=_workspace(), seats=seats,
                         keep=bool(getattr(args, "keep", False)))
    n_ok = sum(1 for r in rows if r["score"]["ok"])
    print(f"OK: lab run standard {target} — {n_ok}/{len(rows)} met their "
          f"expectation; scorecard {_standard.scorecard_path(root)}")
    return RC_OK if rows and n_ok == len(rows) else RC_FAIL
