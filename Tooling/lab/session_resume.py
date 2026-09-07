"""Resuming a HISTORICAL provider session inside a lab workspace.

A round the framework ran days ago left one thing behind: its codex
ROLLOUT, preserved under `<ws>/.asterism/codex_sessions/<pipeline id>/
[review|adversary]/r<n>/rollout-<stamp>-<thread>.jsonl`
(`llm/base.transcript_dest`). Everything else that made it resumable —
the attempts dir, the session map, the running token totals — went with
the run. This module puts those back, so a lab arm can wake the very
agent that argued round 1 instead of a fresh one that has to read its
way in.

WHAT A RESUME ACTUALLY IS, on codex (`llm/codex_cli.py`):

  1. `_load_session_map(attempts_dir)[session_id]` -> the codex thread
     id. The map is `_codex_sessions.json`, per attempts dir, and it is
     the only reason `codex exec resume` is possible at all.
  2. `resuming = bool(prior) and (is_retry or continuation or
     is_postmortem)` — a cold spawn never resumes, however good its map.
  3. codex resolves the thread by OPENING ITS ROLLOUT under the spawn's
     `CODEX_HOME` (`attempts_dir/_codex_home/sessions/YYYY/MM/DD/`);
     with the file missing it dies in seconds with `failed to resolve
     rollout path`.
  4. `_codex_usage.json` carries the thread's running totals as of the
     historical session's last turn. `spawn_usage` sums the rows it is
     handed, and the adapter bills a spawn by the growth of the thread's
     rollout across it (`codex_cli.rollout_usage`), so this is the
     "before" of that subtraction. Seeding it is an optimisation, not a
     requirement: with the file absent the adapter reads the staged
     rollout itself.

`stage_resume` rebuilds all four from the one file that survived, and
`resume_cold_spawn` rewrites a round's cold spawn to use it — at
`Tooling.agent.spawn_llm`, the seam every pipeline reaches the provider
through, so the round itself runs its production code unchanged.

A lab slice carries none of this: `snapshot.py` takes the DB, the
proofs and `_docs/`, which is right — a session archive is not part of a
problem's state. The arm names the archive instead.

WHAT A RESUME CANNOT CARRY, and it is worth knowing before an arm runs:
`codex exec resume` takes no `--sandbox`, no `-C` and no `--add-dir`
(the adapter's own comment says so, measured 2026-08-12), so the
resumed turn inherits the sandbox roots RECORDED IN THE SESSION — for a
historical round, `<live workspace>/.attempts/<the dead pipeline id>/…`.
Everything the framework's agents actually write goes through the MCP
tools server, whose write fence is set per spawn from the environment
(`llm/spawn_guard`, `llm/envelope`) and whose config.toml is rebuilt per
spawn, so the round's own outputs land in the LAB workspace as they
should. The residue is codex's NATIVE file access: were a resumed agent
to reach for `apply_patch` — which no prompt here offers it — it would
be pointed at a path under the live workspace's `.attempts/`. Narrow,
non-zero, and unmitigable from this side; say so in the run record
rather than discovering it in a diff.
"""
from __future__ import annotations

import json
import re
import shutil
import uuid
from contextlib import contextmanager
from pathlib import Path


class ContinuityError(SystemExit):
    """A refusal from the continuity machinery. `SystemExit` because a
    driver runs as its own process and the run's failure is its exit
    code — the same thing `driver.assert_scratch` raises."""


#: `rollout-2026-08-30T04-22-13-<thread uuid>.jsonl` — codex's own name
#: for a session record. BOTH halves are load-bearing: the trailing uuid
#: is the thread `codex exec resume` takes, and the date is the
#: `sessions/YYYY/MM/DD/` directory codex looks in for it.
ROLLOUT_RE = re.compile(
    r"^rollout-(?P<y>\d{4})-(?P<m>\d{2})-(?P<d>\d{2})T[\d\-]+-"
    r"(?P<thread>[0-9a-fA-F-]{36})\.jsonl$")

# ---------------------------------------------------------------------
# the rollout: find it, read its running totals, put it back
# ---------------------------------------------------------------------

def _codex_names() -> "tuple[str, str, str]":
    """`(home dirname, session map, usage ledger)` — IMPORTED from the
    codex adapter, never re-spelled.

    These are private names in `llm/codex_cli.py` and copying them here
    is how this module would keep working for a month after the adapter
    renamed one, staging into a directory nothing reads and reporting a
    resume that never happened."""
    from ..llm import codex_cli as _codex
    return (_codex._SPAWN_HOME_DIRNAME, _codex._SESSION_MAP,
            _codex._USAGE_LEDGER)


def thread_of(rollout: "Path | str") -> str:
    """The codex thread id a rollout file's NAME carries."""
    m = ROLLOUT_RE.match(Path(rollout).name)
    if not m:
        raise ContinuityError(
            f"{rollout} is not a codex rollout — expected "
            f"`rollout-<ISO stamp>-<thread uuid>.jsonl`, which is where "
            f"the thread id and the sessions/YYYY/MM/DD path both come "
            f"from")
    return m.group("thread")


def find_rollout(roots, thread_id: str) -> "tuple[Path, list[dict]]":
    """The rollout for `thread_id`, and every candidate that was seen.

    LARGEST WINS, and that is not a tie-break: a resumed turn APPENDS to
    the same file under the same name, so when one arm's `_out/` and the
    live archive both hold this thread, the longer file is by
    construction the later state of the conversation. Picking by mtime
    would pick whichever copy was made last, which is the archive's."""
    seen: "list[dict]" = []
    for root in roots:
        base = Path(root)
        if not base.is_dir():
            continue
        for p in sorted(base.rglob(f"rollout-*-{thread_id}.jsonl")):
            st = p.stat()
            seen.append({"path": str(p), "bytes": st.st_size,
                         "mtime": st.st_mtime})
    if not seen:
        raise ContinuityError(
            f"no rollout for codex thread {thread_id} under "
            f"{[str(Path(r)) for r in roots]} — a resumed arm needs the "
            f"session's own file: codex resolves a thread by opening it, "
            f"and without it the spawn dies with `failed to resolve "
            f"rollout path`. Check the thread id against the archive's "
            f"filenames (`<pipeline id>/review/r1/rollout-*.jsonl`).")
    best = max(seen, key=lambda r: r["bytes"])
    return Path(best["path"]), seen


def rollout_baseline(rollout: "Path | str") -> "dict[str, int]":
    """The thread's running totals as of this rollout, in
    `StreamParser`'s OWN key names.

    THE ADAPTER'S READER, not a second one. `codex_cli.rollout_usage` is
    what bills every live spawn — it reads the last
    `token_usage_record.thread_token_usage` and takes the cached half
    out of `input_tokens`, because codex's includes it and the parser's
    does not. A copy here would drift from it silently and the drift
    would show up as a resumed leg that argued for four minutes and
    spent nothing, which is what 2026-09-07 spent the morning on."""
    from ..llm import codex_cli as _codex
    return _codex.rollout_usage(rollout)


def truncate_rollout(src: "Path | str", dst: "Path | str",
                     turns: int) -> dict:
    """Copy a rollout keeping only its first `turns` completed turns.

    WHY A HISTORICAL SESSION IS OFTEN TOO LONG. The Theorist's author
    holds ONE codex thread across every revision turn of an episode
    (`theorist/__init__` resumes the same sid), so its rollout is the
    whole four-round argument. An arm that resumes it to answer round
    2's verdict would be resuming an author that already wrote rounds 3
    and 4 — it would hand back what it already knows the episode
    settled on, and the arm's revision step would measure nothing. The
    reviewers have one turn each and need no truncation.

    The cut is at a TURN BOUNDARY (`event_msg.task_complete`), with
    every line up to and including that turn's last record kept. Cutting
    anywhere else would leave a tool call with no result in the replayed
    conversation, which the provider rejects. The session's own header
    (`session_meta`, `world_state`, `turn_context`) sits before the
    first turn and is kept by construction.

    UNVERIFIED AGAINST A LIVE codex (2026-09-07): the shape is right by
    inspection of the format, and no truncated session has been replayed
    yet. An arm that uses it should be smoke-tested before it is
    trusted."""
    src, dst = Path(src), Path(dst)
    kept: "list[str]" = []
    completed = 0
    stopped = False
    with open(src, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if stopped:
                break
            kept.append(line)
            if '"task_complete"' not in line:
                continue
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if (obj.get("type") == "event_msg"
                    and (obj.get("payload") or {}).get("type")
                    == "task_complete"):
                completed += 1
                if completed >= int(turns):
                    stopped = True
    if completed < int(turns):
        raise ContinuityError(
            f"{src} holds {completed} completed turn(s); the arm asked "
            f"to keep {turns}. A cut past the end is not a truncation — "
            f"drop `resume_turns:` to stage the whole session.")
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text("".join(kept), encoding="utf-8")
    return {"turns_kept": completed, "lines_kept": len(kept),
            "bytes": dst.stat().st_size,
            "bytes_before": src.stat().st_size}


def _merge_json(path: Path, add: dict) -> None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            data = {}
    except (OSError, ValueError):
        data = {}
    data.update(add)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def stage_resume(attempts_dir: "Path | str", *, sid: str,
                 rollout: "Path | str") -> dict:
    """Put a historical codex session where the NEXT spawn out of
    `attempts_dir` can resume it. Returns what was staged.

    Three files, one per thing the adapter reads:
      `_codex_home/sessions/YYYY/MM/DD/<rollout>`  the conversation
      `_codex_sessions.json`   `{sid: thread}` — without it `prior` is
                               empty and the spawn is cold with a full
                               prompt, which looks like a run
      `_codex_usage.json`      `{thread: totals}` — the "before" the
                               adapter subtracts the finished rollout
                               from, so the row is this turn's growth

    Staged INTO the attempts dir the round is about to use, and always
    after that dir is built: both round builders `rmtree` their
    projection first, so anything written before them is gone."""
    home_name, map_name, usage_name = _codex_names()
    src = Path(rollout)
    m = ROLLOUT_RE.match(src.name)
    if not m:
        thread_of(src)                      # raises with the full reason
    thread = m.group("thread")
    ad = Path(attempts_dir)
    day = (ad / home_name / "sessions" / m.group("y") / m.group("m")
           / m.group("d"))
    day.mkdir(parents=True, exist_ok=True)
    dst = day / src.name
    shutil.copyfile(src, dst)
    _merge_json(ad / map_name, {sid: thread})
    baseline = rollout_baseline(src)
    if baseline:
        _merge_json(ad / usage_name, {thread: baseline})
    return {"session_id": sid, "thread_id": thread,
            "rollout_from": str(src), "rollout_staged": str(dst),
            "bytes": src.stat().st_size, "usage_baseline": baseline}


def prepare_rollout(rollout: Path, *, turns, workdir: Path) -> "tuple[Path, dict]":
    """The rollout as this arm wants it staged — whole, or cut to its
    first `turns` turns. Returns `(path, note)`."""
    if not turns:
        return rollout, {"turns_kept": "all",
                         "bytes": Path(rollout).stat().st_size}
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    dst = workdir / rollout.name
    note = truncate_rollout(rollout, dst, int(turns))
    print(f"[continuity] staged {rollout.name} cut to {turns} turn(s): "
          f"{note['bytes_before']} -> {note['bytes']} B", flush=True)
    return dst, note


def harvest_rollout(attempts_dir: "Path | str", thread_id: str
                    ) -> "Path | None":
    """The thread's rollout AFTER a resumed spawn, still in the spawn's
    own home.

    `_preserve_transcript` copies rather than moves — codex needs the
    original in place for the next resume — so the grown file is here
    until `lab run` clears the workspace. This is what carries one
    session from round 2 into round 3.

    The lookup is the adapter's own (`codex_cli._thread_rollout`): it
    bills every spawn off the file this returns, and two searches for
    one file is two answers to "which copy is the conversation"."""
    from ..llm import codex_cli as _codex
    home_name, _, _ = _codex_names()
    return _codex._thread_rollout(Path(attempts_dir) / home_name, thread_id)


def resumes_a_codex_rollout(provider: "str | None") -> bool:
    """Does this provider's session live as a codex rollout?

    ASKED OF THE DECLARATION rather than matched against a list of
    names — `capabilities.py` exists to abolish exactly that list. Two
    declared facts have to hold together: the seat resumes a thread the
    PROVIDER minted (`RESUME_PROVIDER_CONVERSATION_ID`; agy does too,
    but on a conversation id of its own), and it runs the codex BINARY
    (`exe_name or name`), which is what puts the session in
    `.asterism/codex_sessions/` as a `rollout-*.jsonl` — "one binary,
    one transcript dir", in the zen entry's own words. Nothing here
    works on a provider where either is false."""
    from ..llm import capabilities as _caps
    spec = _caps.capabilities_for(provider)
    return (spec.session_resume == _caps.RESUME_PROVIDER_CONVERSATION_ID
            and (spec.exe_name or spec.name) == "codex")


def assert_resumable_seat(kind: str, workspace: "Path | None") -> str:
    """Refuse a seat this module cannot resume, BEFORE the round runs.

    A `--seats theory_reviewer=claude/...` override would otherwise
    build the workspace, compile the dossier, spawn a cold judge and
    report the arm's name over a run with no resume in it."""
    from ..llm import capabilities as _caps
    provider = _caps.provider_for_kind(kind, workspace)
    if not resumes_a_codex_rollout(provider):
        raise ContinuityError(
            f"seat {kind!r} is on provider {provider!r}, whose sessions "
            f"are not codex rollouts; this experiment resumes one out of "
            f"`.asterism/codex_sessions/`. A claude session lives in the "
            f"CLI's own home under a name derived from the cwd, which is "
            f"a different staging problem and is not solved here — move "
            f"the seat or drop the resumed leg.")
    return provider


@contextmanager
def resume_cold_spawn(*, kinds, rollout: "Path | str",
                      session_id: "str | None" = None, label: str = ""):
    """For the length of this block, the COLD spawn of `kinds` resumes
    `rollout` instead of starting a new conversation.

    Only the cold one. An `is_retry` spawn is the round's own
    verdict-shape retry and already resumes what it just said; an
    `is_postmortem` spawn is the feedback turn. Rewriting either would
    put the historical session in front of a prompt written for a
    different conversation.

    The block YIELDS its own state dict and REFUSES on the way out if
    nothing fired: a wrapper that silently never matched is a resumed
    arm that ran fresh and got filed as the treatment."""
    from .. import agent as agent_mod

    real = agent_mod.spawn_llm
    state: dict = {"session_id": session_id or str(uuid.uuid4()),
                   "rollout": str(rollout), "fired": 0, "staged": [],
                   "kinds": sorted(kinds), "label": label}

    def patched(**kw):
        cold = not (kw.get("is_retry") or kw.get("is_postmortem"))
        if kw.get("kind") in kinds and cold:
            staged = stage_resume(kw["attempts_dir"],
                                  sid=state["session_id"],
                                  rollout=state["rollout"])
            kw["session_id"] = state["session_id"]
            # `continuation` and not `is_retry`: the adapter's retry
            # branch replaces the prompt with "your previous output was
            # rejected", and this spawn's prompt is the round's real
            # one. `continuation` resumes AND sends the rendered prompt.
            kw["continuation"] = True
            state["fired"] += 1
            state["staged"].append(staged)
            state["thread_id"] = staged["thread_id"]
            print(f"[continuity] {label or 'resume'}: {kw['kind']} spawn "
                  f"resumes thread {staged['thread_id']} "
                  f"({staged['bytes']} B staged into "
                  f"{Path(kw['attempts_dir']).name})", flush=True)
        return real(**kw)

    agent_mod.spawn_llm = patched
    try:
        yield state
    finally:
        agent_mod.spawn_llm = real
    if not state["fired"]:
        raise ContinuityError(
            f"the resumed leg {label!r} never reached a cold "
            f"{sorted(kinds)} spawn — nothing was resumed, so this leg "
            f"is not the treatment it is filed as. Either the round "
            f"failed before spawning, or the seat's kind is spelled "
            f"differently than {sorted(kinds)}.")
