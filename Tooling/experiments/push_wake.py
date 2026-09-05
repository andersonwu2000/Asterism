"""One PUSH wake — the Strategist seat, this wake's real Context, an
arbitrary prompt, and no framework verdict at the end (2026-09-03).

The question the push experiment asks is whether the seat that has spent
27 Programme revisions on local Hall/compensation inequalities can be
moved off that step by being asked to, or whether the route is the
model's rather than the scaffolding's. Answering it needs a wake that is
normal in everything except its instructions: the same Context.md and
companions a batch wake gets, the same seat, the same tools — but no
`decision.json`, no proposal package, no verifier, no judge and no
commit. What comes back is a note file, not a batch.

TWO TURNS, ONE SESSION. The operator's own trajectory was two pushes:
the first produced a diagnosis, the statement came only after the
second. `--prompt2` therefore RESUMES the same session (the codex
adapter's `exec resume`, the identical path the in-pipeline rebuttal
rounds ride) and sends its text as the whole second turn. The note of
turn 1 is snapshotted before it, because turn 2 overwrites it.

Nothing here writes to the live workspace: `assert_scratch` runs BEFORE
the chdir, which is the only moment "is this somebody's live workspace?"
is still an answerable question.

    python -m Tooling.experiments.push_wake \
        --workspace <scratch_ws> --problem Combinatorics.union_closed \
        --group 691 --prompt prompt_b1.md --prompt2 prompt_b2.md \
        --out <lab_root>/runs/push_B_1
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
import uuid
from pathlib import Path

from . import harden_console

#: What the runner keeps from the attempts dir, per turn and once.
_TURN_ARTEFACTS = ("note.md",)
_WAKE_ARTEFACTS = ("Context.md", "_context_stats.json", "charter.md",
                   "TREE.md", "CATALOG.md", "BATCHES.md",
                   "ADJUDICATIONS.md", "_plan_full.md", "decision.json",
                   "proposal.md")


def assert_scratch(workspace: Path) -> None:
    """Refuse any workspace a daemon owns — `daemon.pid` is the marker,
    the same rule `replay_strategist` and `replay_judge` refuse on.

    NOT `timetravel._looks_live`: its first clause is "this is the
    CURRENT directory's database", which is true of a scratch workspace
    the moment you `cd` into it — and cd-ing into the scratch is how
    these tools are documented to run. A guard that fires on the
    documented invocation teaches operators to disable it. The check is
    therefore about OWNERSHIP (a marker in the tree) rather than about
    where the caller happens to be standing.
    """
    ws = Path(workspace)
    for marker in (ws / "daemon.pid", ws / ".asterism" / "daemon.pid"):
        if marker.exists():
            raise SystemExit(
                f"refusing: {marker} exists — a daemon owns this "
                f"workspace; the push runs only on a scratch copy")


def _read_usage(attempts_dir: Path) -> dict:
    """The provider's own per-spawn accounting (`_parser_state.json`);
    `{}` when the provider wrote none."""
    try:
        raw = (attempts_dir / "_parser_state.json").read_text(
            encoding="utf-8")
    except OSError:
        return {}
    try:
        return dict(json.loads(raw).get("usage") or {})
    except ValueError:
        return {}


def _thread_id(attempts_dir: Path, session_id: str) -> "str | None":
    """The provider thread this session is filed under — present only
    once the cold turn recorded one, which is exactly the condition a
    resume needs."""
    try:
        raw = (attempts_dir / "_codex_sessions.json").read_text(
            encoding="utf-8")
        return json.loads(raw).get(session_id) or None
    except (OSError, ValueError, AttributeError):
        return None


def _snapshot(attempts_dir: Path, out: "Path | None", names, suffix: str
              ) -> "list[str]":
    if out is None:
        return []
    out.mkdir(parents=True, exist_ok=True)
    kept: list[str] = []
    for name in names:
        src = attempts_dir / name
        if not src.is_file():
            continue
        stem, dot, ext = name.partition(".")
        dst = out / (f"{stem}{suffix}{dot}{ext}" if suffix else name)
        shutil.copyfile(src, dst)
        kept.append(dst.name)
    return kept


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--workspace", default=".", help="the scratch workspace")
    ap.add_argument("--problem", required=True)
    ap.add_argument("--group", required=True, type=int)
    ap.add_argument("--trigger", default="inject_batch_done",
                    help="trigger_kind the Context is compiled for")
    ap.add_argument("--prompt", required=True,
                    help="file holding turn 1's prompt, verbatim")
    ap.add_argument("--prompt2", default=None,
                    help="file holding turn 2's prompt — sent as a RESUME "
                         "of the same session, after turn 1's note is kept")
    ap.add_argument("--out", default=None,
                    help="directory to copy the artefacts into")
    a = ap.parse_args(argv)
    harden_console()

    workspace = Path(a.workspace).resolve()
    assert_scratch(workspace)
    prompts = [Path(a.prompt).resolve()]
    if a.prompt2:
        prompts.append(Path(a.prompt2).resolve())
    for p in prompts:
        if not p.is_file():
            raise SystemExit(f"no prompt file at {p}")
    out = Path(a.out).resolve() if a.out else None

    os.chdir(workspace)
    sys.path.insert(0, str(workspace))

    from Tooling import agent
    from Tooling.agent import runtime as _rt
    from Tooling.agent.phase2_context import compile_strategist_context
    from Tooling.core import config
    from Tooling.pipeline import write_tools_mcp_config
    from Tooling.state import db, intent as intent_mod

    conn = db.connect(workspace / "asterism.db")
    intent = intent_mod.read(conn, a.problem)
    if intent is None:
        raise SystemExit(f"{a.problem}: no problems row in this DB")

    pipeline_id = str(uuid.uuid4())
    attempts_dir = _rt.attempts_dir_for(workspace, pipeline_id)
    attempts_dir.mkdir(parents=True, exist_ok=True)
    db.record_pipeline_start(conn, pipeline_id=pipeline_id, kind="Strategist",
                             target_id=str(a.group), target_kind="Group")
    conn.commit()

    # The wake's real materials: the same compile a batch wake runs, so
    # the companions (TREE / CATALOG / BATCHES / ADJUDICATIONS, the plan
    # note, the charter) land beside Context.md exactly as usual.
    compile_strategist_context(
        conn, problem=a.problem, trigger_kind=a.trigger,
        attempts_dir=attempts_dir, workspace=workspace, intent=intent,
        group_id=a.group)
    tools_cfg = write_tools_mcp_config(attempts_dir, workspace,
                                       seat="strategist",
                                       problem=a.problem)
    timeout = config.get("strategist.timeout_sec", default=10800,
                         env_var="ASTERISM_STRATEGIST_TIMEOUT_SEC", cast=int)
    problem_dir = db.problem_dir(workspace, a.problem)
    sid = str(uuid.uuid4())
    print(f"[push] {a.problem} g{a.group} trigger={a.trigger!r} "
          f"pipeline={pipeline_id} attempts={attempts_dir}", flush=True)

    turns: list[dict] = []
    for n, prompt_path in enumerate(prompts, start=1):
        prior = _thread_id(attempts_dir, sid)
        t0 = time.monotonic()
        rc = agent.spawn_llm(
            kind="strategist", prompt_path=prompt_path,
            problem_dir=problem_dir, attempts_dir=attempts_dir,
            session_id=sid, continuation=n > 1, timeout_sec=timeout,
            mcp_config_path=tools_cfg)
        wall = time.monotonic() - t0
        note = attempts_dir / "note.md"
        rec = {
            "turn": n,
            "prompt": prompt_path.as_posix(),
            "rc": rc,
            "wall_sec": round(wall, 1),
            "resumed": bool(prior) if n > 1 else False,
            "thread_before": prior,
            "note_chars": (len(note.read_text(encoding="utf-8"))
                           if note.is_file() else 0),
            "usage": _read_usage(attempts_dir),
        }
        rec["kept"] = _snapshot(attempts_dir, out, _TURN_ARTEFACTS,
                                f"_turn{n}")
        rec["kept"] += _snapshot(attempts_dir, out,
                                 ("_parser_state.json",), f"_turn{n}")
        turns.append(rec)
        print(f"[push] turn {n}: rc={rc} wall={wall:.0f}s "
              f"note={rec['note_chars']}ch resumed={rec['resumed']} "
              f"usage={rec['usage']}", flush=True)
        if rc != 0:
            print(f"[push] turn {n} returned rc={rc} — stopping here",
                  flush=True)
            break

    db.finish_pipeline(conn, pipeline_id=pipeline_id,
                       status="succeeded" if turns and turns[-1]["rc"] == 0
                       else "failed",
                       outcome="push")
    conn.commit()
    from Tooling.llm.base import transcript_dest
    transcript = transcript_dest(attempts_dir, "codex_sessions")
    result = {
        "pipeline_id": pipeline_id, "session_id": sid,
        "problem": a.problem, "group": a.group, "trigger": a.trigger,
        "attempts_dir": attempts_dir.as_posix(),
        "transcript_dir": transcript.as_posix() if transcript else None,
        "turns": turns,
    }
    (attempts_dir / "push_result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    _snapshot(attempts_dir, out, _WAKE_ARTEFACTS, "")
    _snapshot(attempts_dir, out, ("push_result.json",), "")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if turns and all(t["rc"] == 0 for t in turns) else 1


if __name__ == "__main__":
    sys.exit(main())
