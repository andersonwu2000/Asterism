"""One THEORY wake — the Strategist seat woken to write mathematics
instead of a batch, then put through a reviewer (2026-09-04, arm 3 of
the theory-wake experiment).

Arms 2 / 4 / 24 of that experiment change prompt WORDS inside the
normal pipeline (`replay_strategist`). Arm 3 changes the PIPELINE: the
wake's product is a document, not a proposal package, so there is no
`decision.json`, no verifier and no commit — but there is still a
judge, because a document nobody presses on is not evidence about what
the seat can do. The shape is therefore push_wake's wake (the real
Context and companions for a live group) welded to adversary's review
loop (a projection the judge rules on, fired bullets back to the author
on the same session, up to `--rounds` revisions).

Two things are deliberately NOT reused from `pipeline.adversary`:

* `parse_verdict` — its contract is criteria "1".."5" and criterion 2's
  naming rule, held level with `Tooling/prompts/adversary/adversary.md`
  by `test_adversary_criteria_contract.py`. `theory_judge.md` rules on
  three (Value / Relation / Rigour) and `theory5_judge.md` on four.
  Bending the shared parser to admit either would move the batch
  judge's contract to serve an experiment; `parse_theory_verdict` below
  is the experiment's own, and the key set it expects is a parameter
  declared per judge prompt (`JUDGE_CRITERIA`).
* `build_projection` — the batch judge's dossier is built around a
  proposal package (decisions.md, contract.md, proposal.md). This one
  is built around a document: charter, the Programme record, the four
  round-fresh files, `report.md`, and the running `dialogue.md`.

Nothing here writes into `_docs/`: the report is an experiment
artefact, not a Project document, and the seat's write fence keeps it
in the attempts dir regardless.

    cd D:/Asterism_exp/arm3_r1 && python -m Tooling.experiments.theory_wake \
        --problem Combinatorics.union_closed --group 691 \
        --trigger inject_batch_done \
        --author-prompt theory_prompts/theory.md \
        --judge-prompt theory_prompts/theory_judge.md \
        --rounds 3 --out D:/Asterism/docs/internal/experiments/theory_wake/runs/arm3_r1
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import time
import uuid
from pathlib import Path

from . import harden_console
from .push_wake import assert_scratch

#: The document the author hands in, and the ruling the judge hands
#: back. Both are bare names in the prompts, resolved by each spawn's
#: own write fence into its own directory.
REPORT_BASENAME = "report.md"
VERDICT_BASENAME = "verdict.json"

#: `theory_judge.md`'s rubric: Value / Relation / Rigour. Three, not
#: the batch judge's five — see the module docstring.
CRITERIA_KEYS = ("1", "2", "3")

#: judge prompt file name → the criteria that rubric adjudicates.
#: DECLARED, never counted out of the prompt text or out of the verdict:
#: a key set read off the verdict would take a judge who skipped a
#: criterion for a smaller rubric, and a key set the parse does not
#: expect is silently dropped — a fired criterion 4 read against
#: `CRITERIA_KEYS` comes back "pass" with the objection thrown away.
#: A judge prompt nobody registered stops the wake instead.
JUDGE_CRITERIA = {
    # Value / Relation / Rigour
    "theory_judge.md": CRITERIA_KEYS,
    # Worth / Rigour / Load-bearing work / Leads (arms 5F, 5X)
    "theory5_judge.md": ("1", "2", "3", "4"),
}


def criteria_keys_for(judge_prompt) -> "tuple[str, ...]":
    """The criteria the given judge prompt rules on, by its file name."""
    name = Path(judge_prompt).name
    try:
        return JUDGE_CRITERIA[name]
    except KeyError:
        raise SystemExit(
            f"{name}: no rubric registered for this judge prompt — add "
            f"its criteria keys to theory_wake.JUDGE_CRITERIA "
            f"(have: {', '.join(sorted(JUDGE_CRITERIA))})") from None

#: Judge re-spawns on a missing/malformed verdict, per round. Same
#: number and same reason as `adversary.VERDICT_TRIES`: a judge that
#: produced no usable ruling twice is a wake-level failure, and one
#: malformed file must not cost the author's document.
VERDICT_TRIES = 2

#: What the runner keeps once per wake — the materials the author was
#: given, so a reading of the report can be checked against them.
_WAKE_ARTEFACTS = ("Context.md", "_context_stats.json", "charter.md",
                   "TREE.md", "CATALOG.md", "BATCHES.md",
                   "ADJUDICATIONS.md", "_plan_full.md")


# ---------------------------------------------------------------------
# the flag that removes one Context section
# ---------------------------------------------------------------------

def hide_owner_notes():
    """Make `## Owner's notes` absent from the compiled Context.

    Arm 3h's single variable. `union_closed`'s `_docs/user/` holds four
    owner notes (SPLIT and its pair warning among them), and the roster
    section tells the seat they exist — so a report that re-derives
    SPLIT under the notes is a different observation from one that
    re-derives it blind. The section is a module-level function the
    compiler calls by attribute (`compile.py`:
    `context._section_owner_notes(...)`), so replacing the attribute
    removes the section without touching the compiler or the prompts.

    Returns the original function, so a caller in one process (a test)
    can put it back.
    """
    from ..agent import context as _context
    original = _context._section_owner_notes
    _context._section_owner_notes = lambda *a, **k: []
    return original


# ---------------------------------------------------------------------
# the verdict this rubric produces
# ---------------------------------------------------------------------

#: A judge that renders a bullet as an OBJECT names the ruling and the
#: prose with one of these. Not a guess: `mcp_tools.validate_json`
#: mis-routes a three-criterion verdict into the AUDITOR's schema check
#: (its heuristic is `criteria["3"]` is a list and `"5"` absent), and
#: `theory_judge.md` tells the judge to validate before finishing — so
#: the tool told arm3h_r2's judge, twice, to re-render its bullets as
#: `{"goal_id", "verdict", "reason"}`, and both wakes died on the
#: rendering of a ruling that was otherwise exactly right (2026-09-04).
#: The contract is one bullet per objection; the bullet's SHAPE is not
#: the contract, the same reason the batch parser still takes the
#: legacy bare string.
_BULLET_HEAD_KEYS = ("verdict", "ruling", "status", "result")
_BULLET_TEXT_KEYS = ("reason", "text", "objection", "bullet", "detail",
                     "note", "comment", "message")


def _as_bullet(entry) -> "str | None":
    """One criterion entry as the `"<head>: <prose>"` line the rest of
    the parser reads, or None if it is no rendering of a bullet at all.

    An object whose ruling is `clear` and whose prose is empty comes
    back as the bare word — so the bare-clear refusal below fires on
    this rendering exactly as it does on the string one.
    """
    if isinstance(entry, str):
        return entry
    if not isinstance(entry, dict):
        return None
    def _pick(keys):
        for k in keys:
            v = entry.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        return ""
    head, body = _pick(_BULLET_HEAD_KEYS), _pick(_BULLET_TEXT_KEYS)
    if not head:
        # No ruling key: the prose may already carry it ("fired: …").
        # If it does not, the head check refuses it, which is right.
        return body or None
    return f"{head}: {body}" if body else head


def _bullets(val) -> "list[str] | None":
    """A criterion's value as a flat list of bullet lines: a bare
    string (legacy, one bullet), a list of strings, a list of objects,
    or a list nested one level deeper."""
    if isinstance(val, str):
        return [val]
    if not isinstance(val, list) or not val:
        return None
    out: list[str] = []
    for entry in val:
        if isinstance(entry, list):
            inner = _bullets(entry)
            if inner is None:
                return None
            out += inner
            continue
        line = _as_bullet(entry)
        if line is None:
            return None
        out.append(line)
    return out or None


def describe_verdict_shape(text: str) -> str:
    """What the judge actually wrote, per criterion, as one log line.

    A rejected verdict is the evidence for why it was rejected, and
    arm3h_r2 had to be recovered from the codex rollout because the
    log carried only the refusal. Types and key names, never values —
    the raw file kept beside it carries those.
    """
    try:
        v = json.loads(text, strict=False)
    except ValueError as e:
        return f"not JSON ({e})"
    if not isinstance(v, dict):
        return f"top level is {type(v).__name__}, not an object"

    def shape(x) -> str:
        if isinstance(x, dict):
            return "dict{" + ",".join(sorted(map(str, x))) + "}"
        if isinstance(x, list):
            inner = sorted({shape(i) for i in x})
            return f"list[{'|'.join(inner) or 'empty'}]({len(x)})"
        return type(x).__name__
    criteria = v.get("criteria")
    if not isinstance(criteria, dict):
        return (f"top-level keys {sorted(map(str, v))}; "
                f"`criteria` is {shape(criteria)}")
    return ("criteria " + ", ".join(
        f'"{k}"={shape(criteria[k])}' for k in sorted(map(str, criteria)))
        + f"; reservations={shape(v.get('reservations'))}")


def keep_rejected_verdict(vpath: Path, *, round_no: int,
                          out: "Path | None") -> Path:
    """Move a refused `verdict.json` aside instead of deleting it.

    It leaves the contract path (the next try must not be read as a
    verdict this judge did not write) and lands as
    `verdict_r<n>_raw.json` beside it, copied into the runs dir too. A
    second refusal in the same round takes `…_raw2.json`, so no
    rejected file is ever overwritten by a later one.
    """
    raw = vpath.read_bytes()
    for i in range(1, 100):
        dst = vpath.with_name(
            f"verdict_r{round_no}_raw{'' if i == 1 else i}.json")
        if not dst.exists():
            break
    dst.write_bytes(raw)
    vpath.unlink(missing_ok=True)
    if out is not None:
        out.mkdir(parents=True, exist_ok=True)
        (out / dst.name).write_bytes(raw)
    return dst


def parse_theory_verdict(text: str, criteria_keys=CRITERIA_KEYS
                         ) -> "tuple[dict | None, str]":
    """Validate a theory judge's verdict.json and derive the ruling.

    Same shape as the batch judge's — a list per criterion, one bullet
    per objection, each bullet `"clear: <reason>"` or
    `"fired: <objection>"`, any fired makes the verdict a rebut — over
    the criteria THIS rubric has: `criteria_keys`, which the caller
    takes from the judge prompt it spawned (`criteria_keys_for`), not
    from the file the judge wrote. `strict=False` for the same reason
    the batch parser uses it: a literal newline inside a string value
    is not structural damage and has killed a wake over it.

    A bullet may also arrive as an OBJECT carrying the ruling and its
    prose, or nested one list deeper (`_bullets`): those are renderings
    of the same one-bullet-per-objection contract, and refusing them
    cost arm3h_r2 both tries. What is NOT tolerated is a bare `clear` —
    in any rendering.

    Returns `({"verdict", "criticisms", "reservations", "criteria"},
    "")`, or `(None, <what to tell the judge>)`. The criticisms are the
    objection text VERBATIM with only a criterion label added — they go
    back to the author as they were written.
    """
    try:
        v = json.loads(text, strict=False)
    except ValueError as e:
        return None, f"verdict.json is not valid JSON: {e}"
    if not isinstance(v, dict):
        return None, "verdict.json must be a JSON object"
    criteria = v.get("criteria")
    if not isinstance(criteria, dict):
        return None, ("verdict.json needs a `criteria` object "
                      "adjudicating every criterion "
                      + ", ".join(f'"{k}"' for k in criteria_keys))
    missing = [k for k in criteria_keys if k not in criteria]
    if missing:
        return None, (f"verdict.json `criteria` missing criterion "
                      f"{', '.join(missing)} — every criterion gets a "
                      f"line, `\"clear: <reason>\"` or "
                      f"`\"fired: <objection>\"`")
    fired: list[str] = []
    for k in criteria_keys:
        vals = _bullets(criteria[k])
        if vals is None:
            return None, (f"criterion {k} must be a list of strings "
                          f"(one bullet per objection) or a single "
                          f"string")
        heads = [("clear" if re.match(r"clear\b", x.strip(), re.IGNORECASE)
                  else "fired" if re.match(r"fired\b", x.strip(),
                                           re.IGNORECASE)
                  else "?") for x in vals]
        if "?" in heads:
            return None, (f"criterion {k}: every bullet must start "
                          f"\"clear\" or \"fired: <objection>\"")
        if "clear" in heads and "fired" in heads:
            return None, (f"criterion {k} mixes \"clear\" and \"fired\" "
                          f"bullets — a criterion is one or the other")
        if heads[0] == "clear" and len(vals) > 1:
            return None, (f"criterion {k}: \"clear\" takes exactly one "
                          f"entry")
        if heads[0] == "clear":
            # The prompt says "No criterion takes a bare `clear`" and
            # this is the enforcement half. Prefix-keyed and
            # annotation-tolerant, the batch parser's shape.
            if not vals[0].strip()[len("clear"):].strip(" -—–:"):
                return None, (
                    f"criterion {k} never takes a bare \"clear\" — say "
                    f"why it holds for THIS document: `\"clear: <one "
                    f"concrete reason>\"`")
            continue
        for x in vals:
            xs = x.strip()
            reason = (xs.split(":", 1)[1].strip() if ":" in xs
                      else xs[len("fired"):].strip(" -—–:"))
            if not reason:
                return None, (f"criterion {k} is fired but carries no "
                              f"objection — `\"fired: <objection>\"`")
            fired.append(f"[criterion {k}] {reason}")
    reservations = v.get("reservations", [])
    if not (isinstance(reservations, list)
            and all(isinstance(x, str) for x in reservations)):
        return None, "verdict.json `reservations` must be a list of strings"
    return {
        "verdict": "rebut" if fired else "pass",
        "criticisms": fired,
        "reservations": reservations,
        "criteria": {k: criteria[k] for k in criteria_keys},
    }, ""


# ---------------------------------------------------------------------
# the judge's dossier
# ---------------------------------------------------------------------

def build_review_projection(*, round_no: int, attempts_dir: Path,
                            conn, workspace: Path, problem: str,
                            group_id: "int | None",
                            report_body: str,
                            dialogue: "list[dict]") -> Path:
    """The whitelist `theory_judge.md` names, assembled into an
    isolated directory: `charter.md`, `report.md`, `PROGRAMME.md`,
    `CATALOG.md`, `TREE.md`, and `dialogue.md` once a round has been
    argued. The papers and the landed proofs are read IN PLACE, as the
    batch judge reads them (`extra_read_dirs` on the spawn).
    """
    from ..pipeline import round_materials as _round_materials
    from ..state import groups as _groups
    from ..state import programme as _programme

    proj = attempts_dir / "review" / f"r{round_no}"
    if proj.exists():
        shutil.rmtree(proj, ignore_errors=True)
    proj.mkdir(parents=True, exist_ok=True)

    charter_text = _groups.charter_digest(conn, problem, group_id)
    if charter_text:
        (proj / "charter.md").write_text(charter_text, encoding="utf-8")
    # TREE / CATALOG / BATCHES / ADJUDICATIONS, rendered from the DB for
    # this round — the one refresher both sides of a debate call.
    outcome_lines = _round_materials.refresh(
        conn, workspace=workspace, problem=problem, group_id=group_id,
        target_dir=proj)
    current = _programme.current_rev(conn, problem, group_id)
    (proj / "PROGRAMME.md").write_text(
        (current["body"] if current is not None else
         "(no Programme yet)")
        + "\n\n---\n\n"
        + "_(Execution record below is assembled for this review; the "
          "problem's PROGRAMME.md file carries the revision text "
          "only.)_\n\n"
        + ("\n".join(outcome_lines) if outcome_lines else
           "## Completed Inject batches\n(none since the last commit)")
        + "\n", encoding="utf-8")
    (proj / REPORT_BASENAME).write_text(report_body + "\n",
                                        encoding="utf-8")
    if dialogue:
        out = ["# Review so far\n",
               "Earlier rounds of THIS review. Judge the CURRENT "
               "document (report.md); treat a point the author already "
               "answered as settled unless you bring a new argument.\n"]
        for entry in dialogue:
            out.append(f"## round {entry.get('round', '?')} — judge")
            out += [f"- {c}" for c in entry.get("criticisms", [])]
            out.append("")
        (proj / "dialogue.md").write_text("\n".join(out), encoding="utf-8")
    return proj


def _render_judge_prompt(src: Path, dst: Path, *, proofs_dir: Path,
                         papers_dir: Path) -> Path:
    """The judge's prompt with the two workspace placeholders filled.

    `{attempts_dir}` and the tool-line conditionals are NOT touched
    here — `render_prompt_template` inside the provider adapter owns
    both, and doing it twice would render the wrong seat's tool line.
    """
    from ..pipeline.adversary import (PAPERS_DIR_PLACEHOLDER,
                                      PROOFS_DIR_PLACEHOLDER)
    dst.write_text(
        src.read_text(encoding="utf-8")
        .replace(PROOFS_DIR_PLACEHOLDER, proofs_dir.as_posix())
        .replace(PAPERS_DIR_PLACEHOLDER, papers_dir.as_posix()),
        encoding="utf-8")
    return dst


# ---------------------------------------------------------------------

def _read_usage(attempts_dir: Path) -> dict:
    try:
        raw = (attempts_dir / "_parser_state.json").read_text(
            encoding="utf-8")
    except OSError:
        return {}
    try:
        return dict(json.loads(raw).get("usage") or {})
    except ValueError:
        return {}


def _snapshot(src: Path, out: "Path | None", names, suffix: str = ""
              ) -> "list[str]":
    if out is None:
        return []
    out.mkdir(parents=True, exist_ok=True)
    kept: list[str] = []
    for name in names:
        p = src / name
        if not p.is_file():
            continue
        stem, dot, ext = name.partition(".")
        dst = out / (f"{stem}{suffix}{dot}{ext}" if suffix else name)
        shutil.copyfile(p, dst)
        kept.append(dst.name)
    return kept


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--workspace", default=".", help="the scratch workspace")
    ap.add_argument("--problem", required=True)
    ap.add_argument("--group", required=True, type=int)
    ap.add_argument("--trigger", default="inject_batch_done",
                    help="trigger_kind the Context is compiled for")
    ap.add_argument("--author-prompt", default="theory_prompts/theory.md",
                    help="the author's prompt file, verbatim")
    ap.add_argument("--judge-prompt",
                    default="theory_prompts/theory_judge.md",
                    help="the reviewer's prompt file; its NAME selects the "
                         "rubric the verdict is read against "
                         "(theory_wake.JUDGE_CRITERIA)")
    ap.add_argument("--rounds", type=int, default=3,
                    help="revision rounds a fired verdict may buy")
    ap.add_argument("--hide-owner-notes", action="store_true",
                    help="compile the Context WITHOUT `## Owner's notes`")
    ap.add_argument("--out", default=None,
                    help="directory to copy the artefacts into")
    a = ap.parse_args(argv)
    harden_console()

    workspace = Path(a.workspace).resolve()
    assert_scratch(workspace)
    author_prompt = Path(a.author_prompt).resolve()
    judge_prompt_src = Path(a.judge_prompt).resolve()
    for p in (author_prompt, judge_prompt_src):
        if not p.is_file():
            raise SystemExit(f"no prompt file at {p}")
    # Before the DB is touched: an unregistered judge prompt is a wake
    # that would spawn a judge and then refuse whatever it wrote.
    criteria_keys = criteria_keys_for(judge_prompt_src)
    out = Path(a.out).resolve() if a.out else None

    os.chdir(workspace)
    sys.path.insert(0, str(workspace))

    from Tooling import agent
    from Tooling.agent import runtime as _rt
    from Tooling.agent.phase2_context import compile_strategist_context
    from Tooling.core import config
    from Tooling.experiments import theory_wake as _self
    from Tooling.pipeline import write_tools_mcp_config
    from Tooling.state import db, intent as intent_mod
    from Tooling.state import project_docs as _project_docs
    from Tooling.state import projects as _projects

    if a.hide_owner_notes:
        # The workspace's OWN copy of this module — `sys.path` now
        # leads at the scratch, and patching the copy this process
        # imported first would leave the compiler's `context` module
        # untouched.
        _self.hide_owner_notes()

    conn = db.connect(workspace / "asterism.db")
    intent = intent_mod.read(conn, a.problem)
    if intent is None:
        raise SystemExit(f"{a.problem}: no problems row in this DB")

    pipeline_id = str(uuid.uuid4())
    attempts_dir = _rt.attempts_dir_for(workspace, pipeline_id)
    attempts_dir.mkdir(parents=True, exist_ok=True)
    db.record_pipeline_start(conn, pipeline_id=pipeline_id,
                             kind="Strategist", target_id=str(a.group),
                             target_kind="Group")
    conn.commit()

    compile_strategist_context(
        conn, problem=a.problem, trigger_kind=a.trigger,
        attempts_dir=attempts_dir, workspace=workspace, intent=intent,
        group_id=a.group)
    ctx_text = (attempts_dir / "Context.md").read_text(encoding="utf-8")
    owner_notes_present = "## Owner's notes" in ctx_text
    if a.hide_owner_notes and owner_notes_present:
        raise SystemExit(
            "--hide-owner-notes did not remove the section — the "
            "compiled Context still carries `## Owner's notes`")

    tools_cfg = write_tools_mcp_config(attempts_dir, workspace,
                                       seat="strategist")
    author_timeout = config.get(
        "strategist.timeout_sec", default=10800,
        env_var="ASTERISM_STRATEGIST_TIMEOUT_SEC", cast=int)
    judge_timeout = config.get(
        "adversary.timeout_sec", default=7200,
        env_var="ASTERISM_ADVERSARY_TIMEOUT_SEC", cast=int)
    problem_dir = db.problem_dir(workspace, a.problem)
    proofs_dir = (problem_dir / "proofs").resolve()
    project = _projects.project_of(conn, a.problem) \
        or a.problem.split(".", 1)[0]
    papers_dir = _project_docs.root(workspace, project).resolve()
    report_path = attempts_dir / REPORT_BASENAME
    sid = str(uuid.uuid4())
    print(f"[theory] {a.problem} g{a.group} trigger={a.trigger!r} "
          f"pipeline={pipeline_id} attempts={attempts_dir} "
          f"owner_notes={'hidden' if a.hide_owner_notes else 'present'} "
          f"author={author_prompt.name} judge={judge_prompt_src.name} "
          f"criteria={','.join(criteria_keys)}",
          flush=True)

    turns: list[dict] = []
    rounds: list[dict] = []
    dialogue: list[dict] = []
    verdict: "dict | None" = None
    outcome = "no_report"

    for revision in range(0, max(0, a.rounds) + 1):
        # --- the author. Round 0 is the cold wake; every later round is
        # a RESUME of the same session carrying the fired bullets, the
        # exact path the batch wake's rebuttal rides
        # (`is_retry=True` + `retry_context`).
        rebuttal = None
        if revision:
            rebuttal = "\n".join(f"- {c}" for c in
                                 (verdict or {}).get("criticisms", []))
        t0 = time.monotonic()
        rc = agent.spawn_llm(
            kind="strategist", prompt_path=author_prompt,
            problem_dir=problem_dir, attempts_dir=attempts_dir,
            session_id=sid, is_retry=bool(revision),
            retry_context=rebuttal, timeout_sec=author_timeout,
            mcp_config_path=tools_cfg)
        wall = time.monotonic() - t0
        report_chars = (len(report_path.read_text(encoding="utf-8"))
                        if report_path.is_file() else 0)
        turns.append({"revision": revision, "rc": rc,
                      "wall_sec": round(wall, 1),
                      "rebuttal": rebuttal,
                      "report_chars": report_chars,
                      "usage": _read_usage(attempts_dir)})
        print(f"[theory] author r{revision}: rc={rc} wall={wall:.0f}s "
              f"report={report_chars}ch usage={turns[-1]['usage']}",
              flush=True)
        _snapshot(attempts_dir, out, (REPORT_BASENAME,), f"_r{revision}")
        if rc != 0:
            outcome = "author_rc"
            break
        if not report_chars:
            outcome = "no_report"
            print("[theory] author produced no report.md — stopping",
                  flush=True)
            break

        # --- the reviewer
        report_body = report_path.read_text(encoding="utf-8")
        proj = build_review_projection(
            round_no=revision + 1, attempts_dir=attempts_dir, conn=conn,
            workspace=workspace, problem=a.problem, group_id=a.group,
            report_body=report_body, dialogue=dialogue)
        judge_prompt = _render_judge_prompt(
            judge_prompt_src, proj / "_theory_judge_prompt.md",
            proofs_dir=proofs_dir, papers_dir=papers_dir)
        judge_cfg = write_tools_mcp_config(proj, workspace,
                                           seat="adversary")
        verdict, verr = None, ""
        for attempt in range(VERDICT_TRIES):
            jt0 = time.monotonic()
            jrc = agent.spawn_llm(
                kind="adversary", prompt_path=judge_prompt,
                problem_dir=proj, attempts_dir=proj,
                session_id=str(uuid.uuid4()), timeout_sec=judge_timeout,
                mcp_config_path=judge_cfg,
                extra_read_dirs=(proofs_dir, papers_dir),
                usage_workspace=workspace, usage_problem=a.problem,
                usage_pipeline_id=pipeline_id)
            jwall = time.monotonic() - jt0
            vpath = proj / VERDICT_BASENAME
            shape = ""
            if jrc != 0:
                verr = f"judge spawn rc={jrc}"
            elif not vpath.is_file():
                verr = "judge produced no verdict.json"
            else:
                raw = vpath.read_text(encoding="utf-8")
                verdict, verr = parse_theory_verdict(
                    raw, criteria_keys=criteria_keys)
                if verdict is None:
                    # The refused file IS the evidence for the refusal;
                    # it moves aside, it does not vanish.
                    shape = describe_verdict_shape(raw)
                    kept = keep_rejected_verdict(
                        vpath, round_no=revision + 1, out=out)
                    verr += f" [kept {kept.name}]"
            print(f"[theory] judge r{revision + 1} try {attempt + 1}: "
                  f"rc={jrc} wall={jwall:.0f}s "
                  f"verdict={(verdict or {}).get('verdict', verr)!r}"
                  + (f" wrote: {shape}" if shape else ""),
                  flush=True)
            if verdict is not None:
                break
        _snapshot(proj, out, (VERDICT_BASENAME,), f"_r{revision + 1}")
        rounds.append({"round": revision + 1,
                       "verdict": (verdict or {}).get("verdict"),
                       "error": verr,
                       "criticisms": (verdict or {}).get("criticisms", []),
                       "reservations": (verdict or {}).get(
                           "reservations", []),
                       "projection": proj.as_posix()})
        if verdict is None:
            outcome = "judge_no_verdict"
            break
        if verdict["verdict"] == "pass":
            outcome = "accepted"
            break
        dialogue.append({"round": revision + 1,
                         "criticisms": verdict["criticisms"]})
        outcome = "rejected"

    db.finish_pipeline(
        conn, pipeline_id=pipeline_id,
        status="succeeded" if outcome == "accepted" else "failed",
        outcome=f"theory:{outcome}")
    conn.commit()

    from Tooling.llm.base import transcript_dest
    transcript = transcript_dest(attempts_dir, "codex_sessions")
    result = {
        "pipeline_id": pipeline_id, "session_id": sid,
        "problem": a.problem, "group": a.group, "trigger": a.trigger,
        "hide_owner_notes": bool(a.hide_owner_notes),
        "owner_notes_in_context": owner_notes_present,
        "context_chars": len(ctx_text),
        "author_prompt": author_prompt.as_posix(),
        "judge_prompt": judge_prompt_src.as_posix(),
        "criteria_keys": list(criteria_keys),
        "outcome": outcome,
        "attempts_dir": attempts_dir.as_posix(),
        "transcript_dir": transcript.as_posix() if transcript else None,
        "turns": turns, "rounds": rounds,
    }
    (attempts_dir / "theory_result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    _snapshot(attempts_dir, out, _WAKE_ARTEFACTS)
    _snapshot(attempts_dir, out, ("theory_result.json",))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if outcome in ("accepted", "rejected") else 1


if __name__ == "__main__":
    sys.exit(main())
