"""JUDGE SESSION CONTINUITY — two lab kinds that run the same review
round twice, once on a RESUMED provider session and once on a fresh one.

Today every review round mints a fresh judge: `adversary.review` and
`theorist/review.review` both do `sid = str(uuid.uuid4())` on the cold
spawn, and the design comment beside the codex session map says so out
loud ("each Adversary round gets its own projection directory and must
not [resume] — a fresh judge per round is the design"). So round 2 pays
to re-read the charter, the Programme, the record files and the document
it already ruled on in round 1. The question these kinds exist to answer
is whether carrying the round-1 session into round 2 buys that back
without the judge going soft on a document it has already argued with.

    theory_review_round   the Theorist's reviewer, on a document
    judge_review_round    the Adversary, on a Programme proposal

Both run the SAME round twice — `resumed` first (it is the treatment,
and a chain's next step is fed from it), then `fresh` (today's control)
— against an identical dossier. Identical on purpose: the only variable
is session memory, so the resumed leg gets the same `dialogue.md` the
fresh one does even though its session already remembers round 1. An arm
that withheld it would be measuring two changes at once.

The session half — finding the historical rollout, staging it where
codex will look for it, and rewriting the round's cold spawn to resume
it — is `lab/session_resume.py`. THAT is why neither kind reimplements
its round: `adversary.review` and `theorist/review.review` are called
exactly as production calls them, so the arm runs the production
prompt, the production projection and the production verdict-retry
loop, and the only thing that differs between the two legs is whose
conversation the spawn lands in.

An arm's INPUTS are frozen files beside its `lab.yaml`, not DB rows: the
body a mid-debate round judged is not what `programme_revisions.body`
holds (that is the round the debate ENDED on), and a per-round theory
draft is in no table at all. Freezing them also makes them part of the
record — a run whose inputs live only in a query cannot be read back
against the verdicts it produced.
"""
from __future__ import annotations

import json
import shutil
import time
import uuid
from pathlib import Path

from .session_resume import (ContinuityError, assert_resumable_seat,
                             find_rollout, harvest_rollout, prepare_rollout,
                             resume_cold_spawn, stage_resume)

#: The two legs of every comparison, in the order they run. `resumed`
#: first because a chain's revision step is fed from ITS verdict (owner
#: order 2026-09-07) — a chain fed from `fresh` would be measuring the
#: control's downstream effect.
LEGS = ("resumed", "fresh")

#: What each chain does, in order. Named rather than derived from a
#: count of steps: an arm says which shape of experiment it is, and a
#: reader of the record should not have to infer it.
CHAINS = ("pair", "revise_then_pair", "pair_revise_pair")


# ---------------------------------------------------------------------
# the chain
# ---------------------------------------------------------------------

def plan_chain(chain: str, round_no: int) -> "list[dict]":
    """The ordered steps a chain runs.

    `pair`              one round, both legs           (arm a)
    `revise_then_pair`  the author answers an INCOMING verdict, then
                        one round, both legs           (arm b)
    `pair_revise_pair`  a round, the author answers ITS resumed
                        verdict, then the next round   (arm c)
    """
    if chain == "pair":
        return [{"step": "pair", "round": int(round_no)}]
    if chain == "revise_then_pair":
        return [{"step": "revise", "round": int(round_no)},
                {"step": "pair", "round": int(round_no)}]
    if chain == "pair_revise_pair":
        return [{"step": "pair", "round": int(round_no)},
                {"step": "revise", "round": int(round_no) + 1},
                {"step": "pair", "round": int(round_no) + 1}]
    raise ContinuityError(
        f"unknown chain {chain!r} — have {list(CHAINS)}")


def run_chain(*, chain: str, round_no: int, out: Path, judge, revise,
              after_pair=None, incoming_verdict: "dict | None" = None,
              revision_basename: str = "draft.md",
              notes: "dict | None" = None) -> dict:
    """Walk a chain, writing the record as it goes.

    `judge(round_no, leg, resumed)` runs one leg and returns a dict with
    at least `verdict`; `revise(round_no, verdict)` runs the author's
    answer and returns a dict with at least `body`. Both are injected so
    the chain can be exercised without a provider — the kinds below wire
    the real ones in.

    `after_pair(round_no, verdict)` fires ONCE per pair, after both legs
    have run, carrying the RESUMED leg's ruling. That is where the
    debate advances, and it is here rather than inside `judge` because
    the two legs must be handed the SAME dossier: a leg that appended
    its own ruling as it finished gave the second leg a `dialogue.md`
    one round longer than the first's, which is a second variable
    (measured on the first dry smoke, 2026-09-07 — 1,925 bytes against
    1,850).

    Everything is written UNDER `out` as it completes, not at the end: a
    chain that dies on its third leg still has to leave the first two
    where the operator can read them."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    steps = plan_chain(chain, round_no)
    rounds: "list[dict]" = []
    revisions: "list[dict]" = []
    verdicts: "dict[str, dict]" = {}
    carried = incoming_verdict
    ok = True

    for spec in steps:
        n = spec["round"]
        if spec["step"] == "revise":
            if not carried:
                raise ContinuityError(
                    f"chain {chain!r} owes the author a revision at "
                    f"round {n} and has no verdict to hand it — a "
                    f"`revise_then_pair` arm reads one out of its "
                    f"`from_arm:` run, and a `pair_revise_pair` arm "
                    f"produces one in its first step")
            t0 = time.monotonic()
            rec = revise(n, carried)
            rec = dict(rec or {})
            rec.update({"round": n, "wall_sec": round(time.monotonic() - t0, 1)})
            body = str(rec.pop("body", "") or "")
            if body:
                (out / revision_basename).write_text(body, encoding="utf-8")
                rec["artefact"] = revision_basename
                rec["body_chars"] = len(body)
            revisions.append(rec)
            _write_json(out, "revision.json", revisions)
            if rec.get("rc"):
                ok = False
                if not body:
                    break
            continue

        pair_verdict = None
        for leg in LEGS:
            t0 = time.monotonic()
            rec = judge(n, leg, leg == "resumed")
            rec = dict(rec or {})
            verdict = rec.get("verdict")
            rec.update({"round": n, "leg": leg,
                        "wall_sec": round(time.monotonic() - t0, 1)})
            rounds.append(rec)
            name = f"verdict_r{n}_{leg}.json"
            _write_json(out, name, verdict if verdict is not None else {
                "_no_verdict": rec.get("err") or "", "rc": rec.get("rc")})
            if verdict is not None:
                verdicts[f"r{n}_{leg}"] = verdict
                _write_prose(out, f"verdict_r{n}_{leg}.md", n, leg, verdict)
            else:
                ok = False
            # The arm's HEADLINE pair, under the plain names the run
            # order asks for. Rewritten at every pair so a chain's last
            # round — the one the arm exists to compare — is what a
            # reader who opens `verdict_resumed.json` gets.
            _write_json(out, f"verdict_{leg}.json",
                        verdict if verdict is not None else {})
            if leg == "resumed" and verdict is not None:
                carried = pair_verdict = verdict
            _write_json(out, "rounds.json", rounds)
        # The round is over for BOTH legs — now the debate may move.
        if after_pair is not None and pair_verdict is not None:
            after_pair(n, pair_verdict)

    timing = {
        "legs": [{k: r.get(k) for k in
                  ("round", "leg", "wall_sec", "rc", "pipeline_id",
                   "resumed_thread", "usage")} for r in rounds],
        "revisions": [{k: r.get(k) for k in
                       ("round", "wall_sec", "rc", "pipeline_id",
                        "resumed_thread", "usage")} for r in revisions],
    }
    for n in sorted({r["round"] for r in rounds}):
        pair = {r["leg"]: r for r in rounds if r["round"] == n}
        if len(pair) == 2:
            timing[f"r{n}_wall_delta_sec"] = round(
                float(pair["resumed"].get("wall_sec") or 0)
                - float(pair["fresh"].get("wall_sec") or 0), 1)
    _write_json(out, "timing.json", timing)

    return {"outcome": "success" if ok else "failed",
            "chain": chain, "steps": steps, "rounds": rounds,
            "revisions": revisions, "timing": timing,
            "verdict_summary": {k: {"verdict": v.get("verdict"),
                                    "criticisms": len(v.get("criticisms")
                                                      or []),
                                    "reservations": len(
                                        v.get("reservations") or [])}
                                for k, v in verdicts.items()},
            "notes": notes or {}}


def _write_json(out: Path, name: str, obj) -> None:
    (Path(out) / name).write_text(
        json.dumps(obj, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8")


def _write_prose(out: Path, name: str, round_no: int, leg: str,
                 verdict: dict) -> None:
    """The ruling as prose, beside the JSON — the arm is read by a
    person comparing two rulings sentence by sentence, and doing that
    through `json.loads` in a terminal is how a difference gets missed."""
    lines = [f"# round {round_no} — {leg}", "",
             f"**verdict**: {verdict.get('verdict')}", ""]
    crits = verdict.get("criticisms") or []
    lines += [f"## criticisms ({len(crits)})", ""]
    lines += [f"- {c}" for c in crits] or ["(none)"]
    res = verdict.get("reservations") or []
    lines += ["", f"## reservations ({len(res)})", ""]
    lines += [f"- {r}" for r in res] or ["(none)"]
    crit = verdict.get("criteria") or {}
    if isinstance(crit, dict):
        lines += ["", "## criteria", ""]
        for k in sorted(crit):
            vals = crit[k] if isinstance(crit[k], list) else [crit[k]]
            lines.append(f"### {k}")
            lines += [f"- {v}" for v in vals]
            lines.append("")
    (Path(out) / name).write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------
# arm inputs
# ---------------------------------------------------------------------

def _read_input(opts: dict, key: str, *, required: bool = True) -> str:
    path = opts.get(key)
    if not path:
        if required:
            raise ContinuityError(f"this arm needs `{key}:` (a file)")
        return ""
    return Path(path).read_text(encoding="utf-8")


def _read_json_input(opts: dict, key: str, default):
    path = opts.get(key)
    if not path:
        return default
    return json.loads(Path(path).read_text(encoding="utf-8"))


def copy_inputs(opts: dict, out: Path, keys) -> "list[str]":
    """Every file the arm fed in, copied beside the verdicts.

    The inputs are frozen extracts from a live record — a mid-debate
    draft, the round-1 criticisms — and a run whose inputs live only in
    the operator's development area cannot be read a month later against
    the verdicts they produced. `reference:` rides along for the same
    reason and reaches no agent: the HISTORICAL ruling on this very
    round is what both of this arm's verdicts are read against, and a
    comparison whose third term has to be re-queried is one nobody
    makes."""
    dst = Path(out) / "inputs"
    dst.mkdir(parents=True, exist_ok=True)
    kept: "list[str]" = []
    named = [opts.get(k) for k in keys] + list(opts.get("reference") or [])
    for src in named:
        if not src:
            continue
        p = Path(src)
        if not p.is_file():
            continue
        shutil.copyfile(p, dst / p.name)
        kept.append(f"inputs/{p.name}")
    return kept


def resolve_chain_source(spec: dict, ws: "Path | str", opts: dict
                         ) -> "tuple[Path | None, dict | None]":
    """`(the run this arm continues, the verdict its author answers)`.

    Resolved from `from_arm:` rather than from a pasted path: a chained
    arm is launched minutes after the one it continues, by a person
    running two commands under time pressure, and a mistyped path would
    run the arm against another experiment's verdict and look like it
    worked."""
    arm = opts.get("from_arm")
    if not arm:
        return None, None
    root, exp, _me = locate_lab(ws)
    prior = find_prior_run(root, exp, str(arm))
    print(f"[continuity] continuing {exp}/{arm} from {prior}", flush=True)
    return prior, incoming_verdict(prior)


def resolve_sessions_roots(from_run: "Path | None",
                           opts: dict) -> "list[Path]":
    """Where a rollout may be found, nearest first.

    `from_arm`'s `_out/transcripts/codex/` comes FIRST because a chained
    arm resumes a session its predecessor already carried a round
    further; `sessions_root` is the live archive, which holds the
    historical state of the same thread. `find_rollout` picks the larger
    of the two anyway — this order only decides which is reported as the
    nearest when they tie."""
    roots: "list[Path]" = []
    if from_run:
        roots.append(Path(from_run) / "_out" / "transcripts" / "codex")
    if opts.get("sessions_root"):
        roots.append(Path(opts["sessions_root"]))
    if not roots:
        raise ContinuityError(
            "a resumed arm needs `sessions_root:` — the directory the "
            "framework preserves codex rollouts under "
            "(`<workspace>/.asterism/codex_sessions`). It is not part of "
            "a slice (`lab snapshot` carries the DB, the proofs and "
            "`_docs/`), so the arm has to name it.")
    return roots


def locate_lab(ws: "Path | str") -> "tuple[Path, str, str]":
    """`(lab root, experiment, arm)` for the workspace this driver is in.

    Read off `workspace.json` — the stamp `lab build` writes — and off
    the path `<root>/runs/<exp>/<arm>_r<n>` it was built at. The driver
    is handed a spec, not a lab root: the root lives in the operator's
    development area, and `lab/README` is explicit that nothing may
    compile a default for it. Deriving it from where this workspace
    actually stands names no path and invents no default."""
    from .build import WORKSPACE_STAMP

    ws = Path(ws).resolve()
    exp = arm = ""
    try:
        stamp = json.loads((ws / WORKSPACE_STAMP).read_text(
            encoding="utf-8"))
        exp, arm = str(stamp.get("experiment") or ""), str(
            stamp.get("arm") or "")
    except (OSError, ValueError):
        pass
    if not exp:
        exp = ws.parent.name
    if len(ws.parents) < 3 or ws.parents[1].name != "runs":
        raise ContinuityError(
            f"{ws} is not a lab run directory (`<root>/runs/<exp>/"
            f"<arm>_r<n>`), so the arm it continues cannot be found. A "
            f"chained arm is only meaningful inside `lab run`.")
    return ws.parents[2], exp, arm


def find_prior_run(root: Path, exp: str, arm: str) -> Path:
    """The newest FINISHED run dir of `arm` under this lab root.

    A chained arm is launched minutes after the one it continues, by a
    person running two commands — so it resolves its predecessor rather
    than being handed a path that has to be pasted correctly under time
    pressure. Finished means the pair that survives a run is there
    (`_out/run_record.json`), which is also what `lab gc` reads."""
    base = Path(root) / "runs" / exp
    if not base.is_dir():
        raise ContinuityError(
            f"no runs of {exp!r} under {base} — `from_arm: {arm}` reads "
            f"the arm it continues out of its own run directory, so "
            f"that arm has to have been run first")
    hits = [d for d in sorted(base.iterdir())
            if d.is_dir() and d.name.startswith(f"{arm}_r")
            and (d / "_out" / "run_record.json").is_file()]
    if not hits:
        raise ContinuityError(
            f"{base} holds no finished run of arm {arm!r} — "
            f"`from_arm:` continues a run that produced a record; run "
            f"`lab run {exp} {arm}` first")
    return max(hits, key=lambda d: (d / "_out" / "run_record.json").stat().st_mtime)


def incoming_verdict(prior_run: "Path | None", leg: str = "resumed"
                     ) -> "dict | None":
    """The verdict a chained arm's author answers — the PREDECESSOR's
    resumed one, by the run order that defines this experiment."""
    if prior_run is None:
        return None
    path = Path(prior_run) / "_out" / f"verdict_{leg}.json"
    if not path.is_file():
        raise ContinuityError(
            f"{path} is not there — a chained arm answers the verdict "
            f"its predecessor's {leg!r} leg produced, and that leg "
            f"either did not run or produced no ruling")
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not obj or not obj.get("criticisms"):
        raise ContinuityError(
            f"{path} carries no criticisms — the author has nothing to "
            f"answer, so the revision step would spend a turn on an "
            f"empty rebuttal. The predecessor's {leg!r} leg passed the "
            f"document; this chain needs one that rebutted.")
    return obj


#: The attempts tree travels whole, minus the per-spawn CODEX_HOME. The
#: home holds a COPY OF THE OPERATOR'S `auth.json` (`codex_cli._spawn_
#: home`) and, here, the staged rollouts as well — a credential that
#: outlives its attempt is exactly what `_preserve_transcript` refuses
#: to let happen, and `_out/` is the part of a run that survives. The
#: rollouts are collected separately, from `.asterism/codex_sessions/`.
_ATTEMPT_IGNORES = ("__pycache__", "_codex_home")


def keep_attempts(workspace: Path, out: Path,
                  pipeline_ids: "list[str]") -> "list[str]":
    kept: "list[str]" = []
    for pid in pipeline_ids:
        src = Path(workspace) / ".attempts" / pid
        if not src.is_dir():
            continue
        dst = Path(out) / "attempts" / pid
        if dst.exists():
            shutil.rmtree(dst, ignore_errors=True)
        shutil.copytree(src, dst,
                        ignore=shutil.ignore_patterns(*_ATTEMPT_IGNORES))
        kept.append(f"attempts/{pid}")
    return kept


# ---------------------------------------------------------------------
# kind: theory_review_round
# ---------------------------------------------------------------------

def run_theory_review_round(spec: dict, ws: Path, out: Path, *,
                            review=None, spawn=None) -> dict:
    """One Theorist review round, resumed against fresh — and, on a
    chained arm, the author's revision in front of it."""
    from ..agent import runtime as _rt
    from ..agent.phase2_context import compile_strategist_context
    from ..core import config
    from ..pipeline import PROMPT_DIR, write_tools_mcp_config
    from ..pipeline.theorist import review as _review
    from ..state import db
    from . import driver as _driver

    review = review or _review.review
    opts = dict(spec["options"])
    problem = spec["problem"]
    ws = Path(ws)
    out = Path(out)
    request = dict(opts.get("request") or {})
    objective = str(request.get("objective") or "")
    situation = str(request.get("situation") or "")
    if not objective.strip():
        raise ContinuityError(
            "this arm needs `request: {objective, situation}` — it is "
            "the request the reviewer's criterion 1 judges the document "
            "against, and the historical episode's own Theorize row is "
            "what it must be")

    assert_resumable_seat("theory_reviewer", ws)
    chain = str(opts.get("chain") or "pair")
    if chain != "pair":
        assert_resumable_seat("theorist", ws)

    report_body = _read_input(opts, "report")
    dialogue = _read_json_input(opts, "dialogue", [])
    from_run, incoming = resolve_chain_source(spec, ws, opts)
    roots = resolve_sessions_roots(from_run, opts)
    reviewer_rollout, reviewer_seen = find_rollout(
        roots, str(opts["resume_sid"]))
    author_rollout = author_seen = author_cut = None
    if chain != "pair":
        if not opts.get("author_resume_sid"):
            raise ContinuityError(
                f"chain {chain!r} runs the author's own revision turn, "
                f"which production takes on the author's session "
                f"(`theorist/__init__` — `is_retry=True` on the same "
                f"sid). It needs `author_resume_sid:`.")
        author_rollout, author_seen = find_rollout(
            roots, str(opts["author_resume_sid"]))
        author_rollout, author_cut = prepare_rollout(
            author_rollout, turns=opts.get("author_resume_turns"),
            workdir=Path(out) / "sessions")

    # The round this arm CONTINUES is part of the argument the reviewer
    # is handed, and it did not happen in this run: `theorist_b` opens
    # on `theorist_a`'s resumed verdict, so that round has to be in the
    # dialogue or the r3 reviewer would read the debate as one round
    # shorter than it was. A `pair_revise_pair` arm needs no seeding —
    # its own first leg appends the round it produced.
    dialogue = list(dialogue)
    if chain == "revise_then_pair" and incoming:
        dialogue.append({"round": int(opts.get("round_no") or 1) - 1,
                         "criticisms": incoming.get("criticisms") or []})

    conn = db.connect(ws / "asterism.db")
    problem_dir = db.problem_dir(ws, problem)
    pipeline_ids: "list[str]" = []
    state = {"body": report_body, "dialogue": list(dialogue),
             "reviewer_rollout": reviewer_rollout,
             "reviewer_sid": str(uuid.uuid4())}
    try:
        who = _driver._intent(conn, problem)
        group = (_driver.resolve_group(conn, problem, opts["group"])
                 if opts.get("group") is not None else None)

        def _leg(round_no: int, leg: str, resumed: bool) -> dict:
            pid = _driver._new_pipeline(
                conn, kind="Theorist",
                target_id=str(group if group is not None else problem),
                target_kind="Group" if group is not None else "Problem")
            pipeline_ids.append(pid)
            attempts = _rt.attempts_dir_for(ws, pid)
            attempts.mkdir(parents=True, exist_ok=True)
            (attempts / _review.REPORT_BASENAME).write_text(
                state["body"], encoding="utf-8")
            args = dict(round_no=round_no, attempts_dir=attempts, conn=conn,
                        workspace=ws, problem=problem, group_id=group,
                        objective=objective, situation=situation,
                        report_body=state["body"],
                        dialogue=list(state["dialogue"]), pipeline_id=pid)
            if not resumed:
                verdict, err, rc = review(**args)
                thread = None
            else:
                with resume_cold_spawn(
                        kinds=("theory_reviewer",),
                        rollout=state["reviewer_rollout"],
                        session_id=state["reviewer_sid"],
                        label=f"theory_reviewer r{round_no}") as res:
                    verdict, err, rc = review(**args)
                thread = res.get("thread_id")
                grown = harvest_rollout(
                    _review.projection_dir(attempts, round_no), thread)
                if grown is not None:
                    state["reviewer_rollout"] = grown
            return {"verdict": verdict, "err": err, "rc": rc,
                    "pipeline_id": pid, "resumed_thread": thread,
                    "usage": _driver.usage_for(conn, [pid]),
                    "projection": str(
                        _review.projection_dir(attempts, round_no))}

        def _advance(round_no: int, verdict: dict) -> dict:
            """The debate moves — once the round is over for both legs.

            The same append `run_theorist` makes between rounds; it is
            not inside `_leg` because both legs must read the SAME
            `dialogue.md`."""
            state["dialogue"] = list(state["dialogue"]) + [
                {"round": round_no,
                 "criticisms": verdict.get("criticisms") or []}]
            return {}

        def _revise(round_no: int, verdict: dict) -> dict:
            """The author's answer, on the author's OWN session.

            The same two moves production makes (`theorist/__init__`):
            resume the session with the fired bullets as
            `retry_context`, and read `report.md` back out of the
            attempts dir. It is spawned here rather than through
            `run_theorist` because that entry point would author a COLD
            document first — a whole extra turn, and not the one the
            experiment is about."""
            from .. import agent
            pid = _driver._new_pipeline(
                conn, kind="Theorist",
                target_id=str(group if group is not None else problem),
                target_kind="Group" if group is not None else "Problem")
            pipeline_ids.append(pid)
            attempts = _rt.attempts_dir_for(ws, pid)
            attempts.mkdir(parents=True, exist_ok=True)
            compile_strategist_context(
                conn, problem=problem, trigger_kind="theory",
                attempts_dir=attempts, workspace=ws, intent=who,
                group_id=group,
                theory_request={"objective": objective,
                                "situation": situation})
            (attempts / _review.REPORT_BASENAME).write_text(
                state["body"], encoding="utf-8")
            tools_cfg = write_tools_mcp_config(attempts, ws,
                                               seat="theorist",
                                               problem=problem)
            staged = stage_resume(attempts, sid=str(uuid.uuid4()),
                                  rollout=author_rollout)
            rebuttal = "\n".join(
                f"- {c}" for c in (verdict.get("criticisms") or []))
            t0 = time.monotonic()
            rc = (spawn or agent.spawn_llm)(
                kind="theorist",
                prompt_path=PROMPT_DIR / "theorist" / "theory.md",
                problem_dir=problem_dir, attempts_dir=attempts,
                session_id=staged["session_id"], is_retry=True,
                retry_context=rebuttal,
                timeout_sec=config.get(
                    "theorist.timeout_sec", default=10800,
                    env_var="ASTERISM_THEORIST_TIMEOUT_SEC", cast=int),
                mcp_config_path=tools_cfg)
            body = ""
            rpath = attempts / _review.REPORT_BASENAME
            if rpath.is_file():
                body = rpath.read_text(encoding="utf-8")
            if body.strip() and body != state["body"]:
                state["body"] = body
            return {"rc": rc, "pipeline_id": pid, "body": body,
                    "resumed_thread": staged["thread_id"],
                    "spawn_wall_sec": round(time.monotonic() - t0, 1),
                    "usage": _driver.usage_for(conn, [pid])}

        result = run_chain(
            chain=chain, round_no=int(opts.get("round_no") or 1), out=out,
            judge=_leg, revise=_revise, after_pair=_advance,
            incoming_verdict=incoming,
            revision_basename=f"draft_r{int(opts.get('round_no') or 1)}.md",
            notes=_notes(opts, spec, reviewer_seen, author_seen,
                         author_cut))
        result["usage"] = _driver.usage_for(conn, pipeline_ids)
    finally:
        conn.close()
    result["pipeline_ids"] = pipeline_ids
    result["artefacts"] = (keep_attempts(ws, out, pipeline_ids)
                           + copy_inputs(opts, out,
                                         ("report", "dialogue")))
    return result


# ---------------------------------------------------------------------
# kind: judge_review_round
# ---------------------------------------------------------------------

def run_judge_review_round(spec: dict, ws: Path, out: Path, *,
                           review=None, spawn=None) -> dict:
    """One Adversary round on a Programme proposal, resumed against
    fresh — and, in the middle of a `pair_revise_pair` chain, the
    Strategist's own rebuttal turn."""
    from ..agent import runtime as _rt
    from ..agent.phase2_context import compile_strategist_context
    from ..core import config
    from ..pipeline import PROMPT_DIR, adversary, write_tools_mcp_config
    from ..pipeline import round_materials as _round_materials
    from ..pipeline.strategist.model import parse_decisions, prompt_kind
    from ..pipeline.strategist.wake import _format_rebuttal
    from ..state import db
    from . import driver as _driver

    review = review or adversary.review
    opts = dict(spec["options"])
    problem = spec["problem"]
    ws = Path(ws)
    out = Path(out)
    trigger = str(opts.get("trigger") or "inject_batch_done")

    assert_resumable_seat("adversary", ws)
    chain = str(opts.get("chain") or "pair")
    if chain != "pair":
        assert_resumable_seat("strategist", ws)

    proposal_body = _read_input(opts, "proposal")
    decision_objs = _read_json_input(opts, "decisions", [])
    dialogue = _read_json_input(opts, "dialogue", [])
    from_run, incoming = resolve_chain_source(spec, ws, opts)
    roots = resolve_sessions_roots(from_run, opts)
    judge_rollout, judge_seen = find_rollout(roots, str(opts["resume_sid"]))
    author_rollout = author_seen = author_cut = None
    if chain != "pair":
        if not opts.get("author_resume_sid"):
            raise ContinuityError(
                f"chain {chain!r} runs the Strategist's rebuttal turn, "
                f"which production takes on the wake's own session "
                f"(`strategist/wake` — `is_retry=True` on the same sid). "
                f"It needs `author_resume_sid:`.")
        author_rollout, author_seen = find_rollout(
            roots, str(opts["author_resume_sid"]))
        author_rollout, author_cut = prepare_rollout(
            author_rollout, turns=opts.get("author_resume_turns"),
            workdir=Path(out) / "sessions")

    # See the note one kind up: a `revise_then_pair` arm's opening round
    # happened in the run it continues, and the judge's dialogue entry
    # carries the BODY that round ruled on as well as the ruling.
    dialogue = list(dialogue)
    if chain == "revise_then_pair" and incoming:
        dialogue.append({"round": int(opts.get("round_no") or 1) - 1,
                         "role": "adversary",
                         "criticisms": incoming.get("criticisms") or [],
                         "verdict": incoming, "proposal": proposal_body})

    conn = db.connect(ws / "asterism.db")
    problem_dir = db.problem_dir(ws, problem)
    pipeline_ids: "list[str]" = []
    state = {"body": proposal_body, "decisions": list(decision_objs),
             "dialogue": list(dialogue), "judge_rollout": judge_rollout,
             "judge_sid": str(uuid.uuid4())}
    try:
        who = _driver._intent(conn, problem)
        group = _driver.resolve_group(conn, problem, opts["group"])

        def _scene(pid: str) -> Path:
            attempts = _rt.attempts_dir_for(ws, pid)
            attempts.mkdir(parents=True, exist_ok=True)
            compile_strategist_context(
                conn, problem=problem, trigger_kind=trigger,
                attempts_dir=attempts, workspace=ws, intent=who,
                group_id=group)
            (attempts / "proposal.md").write_text(state["body"],
                                                  encoding="utf-8")
            (attempts / "decision.json").write_text(
                json.dumps(state["decisions"], ensure_ascii=False,
                           indent=2), encoding="utf-8")
            return attempts

        def _leg(round_no: int, leg: str, resumed: bool) -> dict:
            pid = _driver._new_pipeline(conn, kind="Strategist",
                                        target_id=str(group),
                                        target_kind="Group")
            pipeline_ids.append(pid)
            attempts = _scene(pid)
            decisions, err = parse_decisions(
                json.dumps(state["decisions"]))
            if err or decisions is None:
                raise ContinuityError(f"decisions do not parse: {err}")
            args = dict(round_no=round_no, attempts_dir=attempts,
                        problem_dir=problem_dir, conn=conn,
                        problem=problem, proposal_body=state["body"],
                        decisions=decisions,
                        dialogue=list(state["dialogue"]),
                        proof_warn=None, group_id=group)
            if not resumed:
                verdict, jerr, rc = review(**args)
                thread = None
            else:
                with resume_cold_spawn(
                        kinds=("adversary",),
                        rollout=state["judge_rollout"],
                        session_id=state["judge_sid"],
                        label=f"adversary r{round_no}") as res:
                    verdict, jerr, rc = review(**args)
                thread = res.get("thread_id")
                grown = harvest_rollout(
                    attempts / adversary.PROJECTION_DIRNAME
                    / f"r{round_no}", thread)
                if grown is not None:
                    state["judge_rollout"] = grown
            return {"verdict": verdict, "err": jerr, "rc": rc,
                    "pipeline_id": pid, "resumed_thread": thread,
                    "usage": _driver.usage_for(conn, [pid]),
                    "projection": str(attempts
                                      / adversary.PROJECTION_DIRNAME
                                      / f"r{round_no}")}

        def _advance(round_no: int, verdict: dict) -> dict:
            """The debate moves — once the round is over for both legs.

            The dialogue entry keeps the BODY the round ruled on beside
            the ruling, the way `wake.py` files it, so the next judge
            reads the round as documents. Not inside `_leg`: both legs
            must read the SAME `dialogue.md`."""
            state["dialogue"] = list(state["dialogue"]) + [
                {"round": round_no, "role": "adversary",
                 "criticisms": verdict.get("criticisms") or [],
                 "verdict": verdict, "proposal": state["body"]}]
            return {}

        def _revise(round_no: int, verdict: dict) -> dict:
            """The Strategist's rebuttal turn, on its own session — the
            path `wake.py` takes: `is_retry=True` with `_format_rebuttal`
            as `retry_context`, the four record files refreshed into the
            author's dir first, and `proposal.md` + `decision.json` read
            back afterwards."""
            from .. import agent
            pid = _driver._new_pipeline(conn, kind="Strategist",
                                        target_id=str(group),
                                        target_kind="Group")
            pipeline_ids.append(pid)
            attempts = _scene(pid)
            _round_materials.refresh(conn, workspace=ws, problem=problem,
                                     group_id=group, target_dir=attempts)
            label, since = _round_materials.delta(
                conn, problem=problem, attempts_dir=attempts)
            tools_cfg = write_tools_mcp_config(attempts, ws,
                                               seat="strategist",
                                               problem=problem)
            staged = stage_resume(attempts, sid=str(uuid.uuid4()),
                                  rollout=author_rollout)
            rebuttal = _format_rebuttal(
                verdict, round_no - 1,
                max(0, int(opts.get("rounds_left") or 1)),
                since_label=label, since=since)
            t0 = time.monotonic()
            rc = (spawn or agent.spawn_llm)(
                kind="strategist",
                prompt_path=(PROMPT_DIR / "strategist"
                             / f"{prompt_kind(trigger)}.md"),
                problem_dir=problem_dir, attempts_dir=attempts,
                session_id=staged["session_id"], is_retry=True,
                retry_context=rebuttal,
                timeout_sec=config.get(
                    "strategist.timeout_sec", default=10800,
                    env_var="ASTERISM_STRATEGIST_TIMEOUT_SEC", cast=int),
                mcp_config_path=tools_cfg)
            body = ""
            ppath = attempts / "proposal.md"
            if ppath.is_file():
                body = ppath.read_text(encoding="utf-8")
            dpath = attempts / "decision.json"
            if dpath.is_file():
                try:
                    state["decisions"] = json.loads(
                        dpath.read_text(encoding="utf-8"))
                except ValueError:
                    pass
            if body.strip() and body != state["body"]:
                state["body"] = body
            (Path(out) / "decision_r{}.json".format(round_no)).write_text(
                json.dumps(state["decisions"], ensure_ascii=False,
                           indent=2), encoding="utf-8")
            return {"rc": rc, "pipeline_id": pid, "body": body,
                    "resumed_thread": staged["thread_id"],
                    "spawn_wall_sec": round(time.monotonic() - t0, 1),
                    "usage": _driver.usage_for(conn, [pid])}

        first = int(opts.get("round_no") or 1)
        result = run_chain(
            chain=chain, round_no=first, out=out, judge=_leg,
            revise=_revise, after_pair=_advance, incoming_verdict=incoming,
            revision_basename=f"proposal_r{first + 1}.md",
            notes=_notes(opts, spec, judge_seen, author_seen,
                         author_cut))
        result["usage"] = _driver.usage_for(conn, pipeline_ids)
    finally:
        conn.close()
    result["pipeline_ids"] = pipeline_ids
    result["artefacts"] = (keep_attempts(ws, out, pipeline_ids)
                           + copy_inputs(opts, out,
                                         ("proposal", "decisions",
                                          "dialogue")))
    return result


def _notes(opts: dict, spec: dict, judge_seen, author_seen,
           author_cut=None) -> dict:
    """What the record has to say about this arm beyond its numbers.

    `resume_note` above all: the resumed session was argued under the
    prompt of ITS day, and this arm runs the CURRENT one (the experiment
    is about session memory, not prompt version). A rubric that has
    changed since — the batch judge lost criterion 5 on 2026-09-07, and
    an Inject names its brick now instead of carrying a copy — is
    therefore part of what the resumed leg measures, and a reader who
    does not know that will read the difference as the resume's."""
    return {"resume_note": str(opts.get("resume_note") or ""),
            "legs_order": list(LEGS),
            "dossier": ("identical for both legs — the resumed leg gets "
                        "the same dialogue.md the fresh one does, so the "
                        "only variable is session memory"),
            "resumed_session_sandbox": (
                "`codex exec resume` takes no --sandbox/-C/--add-dir, so "
                "the resumed turn inherits the sandbox roots recorded in "
                "the historical session (a dead `.attempts/<pid>/` under "
                "the LIVE workspace). Framework writes go through the "
                "MCP tools server, whose fence is set per spawn, so the "
                "round's outputs land in the lab workspace; codex's "
                "native file access is the residue and no prompt here "
                "offers it."),
            "from_run": str(spec.get("from_run") or ""),
            "rollout_candidates": {"judge": judge_seen or [],
                                   "author": author_seen or []},
            "author_session_cut": author_cut or {}}


KINDS = {
    "theory_review_round": run_theory_review_round,
    "judge_review_round": run_judge_review_round,
}

#: The arm keys each kind takes beyond `spec._COMMON_ARM_KEYS`, in the
#: shape `spec.DRIVER_KINDS` wants. Declared HERE, beside the code that
#: reads them, so a key added to a kind cannot be forgotten in the
#: validator — which would refuse the lab.yaml that uses it.
ARM_KEYS = {
    "theory_review_round": (
        "group", "round_no", "chain", "request", "report", "dialogue",
        "sessions_root", "resume_sid", "author_resume_sid",
        "author_resume_turns", "from_arm", "resume_note", "reference"),
    "judge_review_round": (
        "group", "round_no", "chain", "trigger", "proposal", "decisions",
        "dialogue", "rounds_left", "sessions_root", "resume_sid",
        "author_resume_sid", "author_resume_turns", "from_arm",
        "resume_note", "reference"),
}

#: Arm keys naming a FILE, resolved against the lab.yaml like every
#: other lab input.
FILE_KEYS = ("report", "proposal", "decisions", "dialogue")


def check_options(name: str, kind: str, opts: dict, base: Path) -> None:
    """`spec._check_options`'s branch for these kinds — refused while
    the operator is still looking at the file that has the mistake,
    rather than after a workspace has been built and a seat warmed."""
    from . import LabError

    def _need(key: str) -> None:
        if opts.get(key) in (None, "", [], {}):
            raise LabError(f"arm {name!r} ({kind}): `{key}:` is required")

    _need("group")
    _need("resume_sid")
    _need("sessions_root")
    _need("report" if kind == "theory_review_round" else "proposal")
    chain = str(opts.get("chain") or "pair")
    if chain not in CHAINS:
        raise LabError(
            f"arm {name!r} ({kind}): chain {chain!r} is not one of "
            f"{list(CHAINS)}")
    if chain == "revise_then_pair" and not opts.get("from_arm"):
        raise LabError(
            f"arm {name!r} ({kind}): `chain: revise_then_pair` answers a "
            f"verdict the PREVIOUS arm produced, so it needs "
            f"`from_arm: <arm>` to say which run to read it out of")
    if chain != "pair" and not opts.get("author_resume_sid"):
        raise LabError(
            f"arm {name!r} ({kind}): chain {chain!r} runs the author's "
            f"own turn on the author's own session — it needs "
            f"`author_resume_sid:`")
    if kind == "theory_review_round":
        req = opts.get("request") or {}
        if not isinstance(req, dict) or not str(
                req.get("objective") or "").strip():
            raise LabError(
                f"arm {name!r} ({kind}): `request: {{objective, "
                f"situation}}` is required — criterion 1 judges the "
                f"document against the request, and the historical "
                f"episode's own Theorize row is what it must be")
    refs = opts.get("reference")
    if refs is not None:
        if not isinstance(refs, list):
            raise LabError(
                f"arm {name!r} ({kind}): `reference:` is a LIST of files "
                f"carried into the record for comparison and shown to no "
                f"agent (the historical ruling on this round, above all)")
        out: "list[str]" = []
        for src in refs:
            path = (base / str(src)).resolve()
            if not path.is_file():
                raise LabError(
                    f"arm {name!r} ({kind}): no reference file at {path}")
            out.append(str(path))
        opts["reference"] = out
    for key in FILE_KEYS:
        if opts.get(key):
            path = (base / str(opts[key])).resolve()
            if not path.is_file():
                raise LabError(
                    f"arm {name!r} ({kind}): no {key} file at {path} — a "
                    f"continuity arm's inputs are frozen extracts from "
                    f"the record and are resolved beside the lab.yaml "
                    f"that names them")
            opts[key] = str(path)
