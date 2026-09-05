"""`asterism lab …` — the CLI surface.

Registered in `Tooling/core/cli/main.py` the way `carry` is: one
subcommand, a positional action, and flags that name what each action
takes. What this file pins is the shape a caller depends on — the
actions that exist, the refusal when the root is not named, and the
non-zero rc a refusal returns.
"""
from __future__ import annotations

import argparse

from Tooling import lab
from Tooling.core.cli.main import main as cli_main
from Tooling.lab import cli as lab_cli


def _parse(argv, monkeypatch):
    """The namespace the REAL CLI builds for an `asterism lab …` argv.

    `main()` imports `cmd_lab` while it builds the parser, so replacing
    the module attribute first is enough to record the namespace instead
    of running the command — and it exercises the registration itself
    rather than a copy of it made in this file."""
    seen = {}

    def _record(args):
        seen["args"] = args
        return 0

    monkeypatch.setattr(lab_cli, "cmd_lab", _record)
    assert cli_main(list(argv)) == 0
    return seen["args"]


def test_lab_is_registered_with_its_four_actions(monkeypatch):
    args = _parse(["lab", "snapshot", "--scope", "Erdos.p1",
                   "--root", "R", "--rewind", "2026-09-02T23:31:00+00:00"],
                  monkeypatch)
    assert args.lab_action == "snapshot"
    assert args.scope == "Erdos.p1" and args.root == "R"
    assert args.rewind == "2026-09-02T23:31:00+00:00"
    run = _parse(["lab", "run", "e1", "baseline", "--reps", "3", "--keep",
                  "--root", "R"], monkeypatch)
    assert (run.lab_action, run.exp, run.arm) == ("run", "e1", "baseline")
    assert run.reps == 3 and run.keep is True
    gc = _parse(["lab", "gc", "--keep-latest", "5", "--root", "R"],
                monkeypatch)
    assert gc.lab_action == "gc" and gc.keep_latest == 5
    build = _parse(["lab", "build", "e1", "a", "--root", "R"], monkeypatch)
    assert build.lab_action == "build"


def test_the_standard_sets_are_run_through_lab_run(monkeypatch):
    """`asterism lab run standard <set|item|all>` — the same two
    positionals `lab run <exp> <arm>` takes, because a standard set IS
    an experiment whose arms have recorded answers. `--seats` moves a
    seat for the whole run, which is the one thing a standard set is
    re-run to measure."""
    args = _parse(["lab", "run", "standard", "traps", "--root", "R",
                   "--seats", "adversary=codex/gpt-5:xhigh",
                   "--seats", "strategist=claude/opus"], monkeypatch)
    assert (args.lab_action, args.exp, args.arm) == ("run", "standard",
                                                     "traps")
    assert args.seats == ["adversary=codex/gpt-5:xhigh",
                          "strategist=claude/opus"]


def test_a_seat_override_must_be_seat_equals_provider_slash_model(tmp_path,
                                                                  capsys):
    rc = lab_cli.cmd_lab(argparse.Namespace(
        lab_action="run", root=str(tmp_path), exp="standard", arm="all",
        reps=None, keep=False, seats=["adversary:codex/gpt-5"]))
    assert rc == 1
    assert "seat=provider/model" in capsys.readouterr().err


def test_lab_run_standard_refuses_a_root_with_no_sets(tmp_path, capsys):
    rc = lab_cli.cmd_lab(argparse.Namespace(
        lab_action="run", root=str(tmp_path), exp="standard", arm="all",
        reps=None, keep=False, seats=None))
    assert rc == 1
    assert "standard.yaml" in capsys.readouterr().err


def test_the_cli_refuses_when_no_root_is_named(monkeypatch, capsys):
    """The refusal has to reach the operator as a message and an rc, not
    as a traceback: `lab` is run from a shell and its failures are read
    from a terminal."""
    monkeypatch.delenv(lab.ROOT_ENV, raising=False)
    rc = lab_cli.cmd_lab(argparse.Namespace(lab_action="gc", root=None,
                                            keep_latest=3))
    assert rc == 1
    err = capsys.readouterr().err
    assert "--root" in err and lab.ROOT_ENV in err


def test_the_cli_refuses_a_snapshot_with_no_scope(tmp_path, capsys):
    rc = lab_cli.cmd_lab(argparse.Namespace(
        lab_action="snapshot", root=str(tmp_path), scope=None, rewind=None))
    assert rc == 1
    assert "--scope" in capsys.readouterr().err


def test_the_cli_refuses_an_experiment_that_does_not_exist(tmp_path, capsys):
    rc = lab_cli.cmd_lab(argparse.Namespace(
        lab_action="run", root=str(tmp_path), exp="nope", arm="a",
        reps=None, keep=False))
    assert rc == 1
    assert "lab.yaml" in capsys.readouterr().err


def test_gc_runs_through_the_cli(tmp_path, capsys):
    (lab.snapshots_dir(tmp_path)).mkdir(parents=True)
    rc = lab_cli.cmd_lab(argparse.Namespace(lab_action="gc",
                                            root=str(tmp_path),
                                            keep_latest=3))
    assert rc == 0
    assert "0 workspace(s) cleared" in capsys.readouterr().out
