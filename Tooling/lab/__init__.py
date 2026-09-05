"""The lab — run one experiment on the framework, and record it.

An experiment is four nouns, and each has exactly one implementation
here (lab_design.md §2):

  SLICE      `lab snapshot` — ONE problem's state, exported the way
             `asterism carry` exports it (a DB pruned to that problem's
             rows plus the global `library_*`/`projects`, its problem
             directory and bound papers in a tarball, a manifest saying
             where and when it came from). Optionally rewound to a
             historical instant, DB and file plane in the same action.
  WORKSPACE  `lab build` — a throwaway workspace: the base skeleton, the
             slice imported into it, `Tooling/` from a named commit
             (never the working tree), the arm's prompt/seat overlay,
             the heavy read-only trees linked. Never a `.git`, never a
             `daemon.pid`; nothing here ever writes the live workspace.
  DRIVER     `lab run` — what is actually woken in that workspace: one
             Adversary round (`judge_round`), one Strategist wake
             (`strategist_wake`), one Theorist wake (`theory_wake`), a
             free-instruction push (`push_wake`), or the framework's own
             daemon (`daemon`).
  RECORD     `run_record.json` beside the artefacts in `_out/` — the
             slice, the code commit, the sha256 of every prompt the
             workspace actually held, the seats as configured, the
             tokens/turns/wall the run spent, the outcome. The workspace
             is deleted once `_out/` is written unless `--keep`.

THE ROOT IS NOT DEFAULTED, EVER. The lab's state (`snapshots/`, `runs/`,
`docs/<exp>/lab.yaml`) lives in the operator's development area, and
production — daemon, agent, pipeline, prompts — may not reference that
area at all (lab_design.md §0). A default here would be exactly such a
reference, compiled into the framework and shipped to every checkout, so
the root comes from `--root` or `ASTERISM_LAB_ROOT` and from nowhere
else. `Tooling/lab/` is dev tooling that ships with the framework
because it has tests and moves with the schema; its INPUTS do not.
"""
from __future__ import annotations

import os
from pathlib import Path


class LabError(Exception):
    """A refusal the CLI prints as `FAIL: <message>` and returns 1 on.

    Every one of these names the action that gets past it — a lab
    command that stops without saying what to do next is a command the
    next operator works around."""


#: Where the lab's state lives, when it is not given on the command
#: line. A NAME, never a path: see the module docstring.
ROOT_ENV = "ASTERISM_LAB_ROOT"

#: The framework checkout this code is part of — derived from this
#: file's own location, so it follows a worktree or a cloud clone. It is
#: the source of `git archive <commit> Tooling`, and it is NOT the lab
#: root: the lab writes nothing into the repo.
REPO = Path(__file__).resolve().parents[2]


def resolve_root(explicit: "str | Path | None" = None) -> Path:
    """The lab root, or `LabError`. `--root` wins over the environment;
    there is no third source and no default."""
    raw = str(explicit or os.environ.get(ROOT_ENV) or "").strip()
    if not raw:
        raise LabError(
            f"the lab has no root — pass `--root <dir>` or set "
            f"{ROOT_ENV}. There is deliberately no default: the lab's "
            f"snapshots, runs and lab.yaml live in the operator's "
            f"development area, and the framework must not know where "
            f"that is (lab_design.md §0).")
    return Path(raw).expanduser().resolve()


def snapshots_dir(root: Path) -> Path:
    """`<root>/snapshots/` — one directory per slice."""
    return Path(root) / "snapshots"


def docs_dir(root: Path, exp: str) -> Path:
    """`<root>/docs/<exp>/` — where `lab.yaml` and `report.md` live."""
    return Path(root) / "docs" / exp


def runs_dir(root: Path, exp: str) -> Path:
    """`<root>/runs/<exp>/` — one directory per arm repetition."""
    return Path(root) / "runs" / exp


def base_dir(root: Path) -> Path:
    """`<root>/base/` — the workspace skeleton every build copies."""
    return Path(root) / "base"


__all__ = ["LabError", "REPO", "ROOT_ENV", "base_dir", "docs_dir",
           "resolve_root", "runs_dir", "snapshots_dir"]
