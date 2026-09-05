"""One review round: the reviewer's dossier, and the spawn that rules
on it.

The projection is built around a DOCUMENT, which is why it is not
`adversary.build_projection` — that one is built around a proposal
package (proposal.md, decisions.md, contract.md) and there is no
proposal here. What `review.md` names is: the charter, the request the
document answers, the Programme with its execution record, the four
round-fresh record files, the document itself, and the dialogue once a
round has been argued. The Project's documents and the landed proofs
are read IN PLACE on a read-only grant, exactly as the batch judge
reads them.
"""
from __future__ import annotations

import shutil
import sqlite3
import time
import uuid
from pathlib import Path

from ..adversary import INFRA_RETRY_BACKOFF_SEC, INFRA_SPAWN_RETRIES
from .verdict import (REPORT_BASENAME, VERDICT_BASENAME, VERDICT_TRIES,
                      describe_verdict_shape, keep_rejected_verdict,
                      parse_theory_verdict, write_rubric)

PROJECTION_DIRNAME = "review"
REQUEST_BASENAME = "request.md"

#: What `agent/` under the papers dir actually holds, appended to the
#: reviewer's rendered prompt rather than written into the static one:
#: the shelf gained refused documents on 2026-09-06 and the prompt still
#: describes it as the accepted ones. A reviewer reading a refusal as
#: settled prior work fires criterion 1 on a document for restating
#: something nothing established.
AGENT_SHELF_NOTE = (
    "`agent/` under the papers dir holds REFUSED theory documents "
    "beside the accepted ones. A refused one is named `_rejected_` and "
    "its header opens `status: rejected`; it is a record of what was "
    "tried, not a result. Its theorems count as established only if "
    "that header clears criterion 2 (Rigour) — one marked "
    "`rigour: defective` establishes nothing, so a document under review "
    "here is not restating known work by proving what such a file "
    "claims.")


def projection_dir(attempts_dir: Path, round_no: int) -> Path:
    """Where round `round_no`'s reviewer runs — its dossier, its verdict
    and its `_spawn.stderr`. One home for the path, because the caller
    that reads a dead reviewer's stderr must not spell it differently
    from the builder that made it."""
    return attempts_dir / PROJECTION_DIRNAME / f"r{round_no}"


def request_body(objective: str, situation: str) -> str:
    """The request, as the reviewer reads it. Its own file rather than a
    section of the report: criterion 1 asks whether the document
    answers THIS request, and a request the author could have edited on
    the way past is not a thing to judge against."""
    return ("# The request this document answers\n\n"
            "_(Framework text — the Strategist's `Theorize`, verbatim.)_\n\n"
            "## Objective\n\n" + (objective.strip() or "(none given)")
            + "\n\n## Situation\n\n" + (situation.strip() or "(none given)")
            + "\n")


def build_review_projection(*, round_no: int, attempts_dir: Path,
                            conn: sqlite3.Connection, workspace: Path,
                            problem: str, group_id: "int | None",
                            objective: str, situation: str,
                            report_body: str,
                            dialogue: "list[dict]") -> Path:
    """Assemble the whitelist `review.md` names into an isolated dir."""
    from .. import round_materials as _round_materials
    from ...state import groups as _groups
    from ...state import programme as _programme

    proj = projection_dir(attempts_dir, round_no)
    if proj.exists():
        shutil.rmtree(proj, ignore_errors=True)
    proj.mkdir(parents=True, exist_ok=True)

    charter_text = _groups.charter_digest(conn, problem, group_id)
    if charter_text:
        (proj / "charter.md").write_text(charter_text, encoding="utf-8")
    (proj / REQUEST_BASENAME).write_text(
        request_body(objective, situation), encoding="utf-8")
    # TREE / CATALOG / BATCHES / ADJUDICATIONS, rendered from the DB for
    # THIS round — the one refresher both sides of a debate call.
    outcome_lines = _round_materials.refresh(
        conn, workspace=workspace, problem=problem, group_id=group_id,
        target_dir=proj)
    current = _programme.current_rev(conn, problem, group_id)
    (proj / "PROGRAMME.md").write_text(
        (str(current["body"]) if current is not None else
         "(no Programme yet)")
        + "\n\n---\n\n"
        # Label the weld: the execution record below exists only in THIS
        # projection, and a document describing the problem's own
        # PROGRAMME.md must be judged against the right referent.
        + "_(Execution record below is assembled for this review; the "
          "problem's PROGRAMME.md file carries the revision text "
          "only.)_\n\n"
        # Always rendered by the section itself now (heading + "(none)"),
        # so this weld carries no fallback of its own.
        + "\n".join(outcome_lines)
        + "\n", encoding="utf-8")
    (proj / REPORT_BASENAME).write_text(report_body.rstrip("\n") + "\n",
                                        encoding="utf-8")
    if dialogue:
        out = ["# Review so far", "",
               "Earlier rounds of THIS review. Judge the CURRENT "
               "document (report.md); treat a point the author already "
               "answered as settled unless you bring a new argument.",
               ""]
        for entry in dialogue:
            out.append(f"## round {entry.get('round', '?')} — reviewer")
            out += [f"- {c}" for c in entry.get("criticisms", [])]
            out.append("")
        (proj / "dialogue.md").write_text("\n".join(out), encoding="utf-8")
    write_rubric(proj)
    return proj


def _render_prompt(src: Path, dst: Path, *, proofs_dir: Path,
                   papers_dir: Path, present: "list[str]") -> Path:
    """The reviewer's prompt with its two workspace placeholders filled
    and this round's dossier named.

    `{attempts_dir}` and the tool-line conditionals are NOT touched
    here — `render_prompt_template` inside the provider adapter owns
    both, and doing it twice renders the wrong seat's tool line."""
    from ..adversary import (PAPERS_DIR_PLACEHOLDER, PROOFS_DIR_PLACEHOLDER)
    ext = []
    for label, path in (("proofs dir", proofs_dir),
                        ("papers dir", papers_dir)):
        if path.is_dir():
            ext.append(f"- {label} `{path.as_posix()}`: exists, "
                       f"{sum(1 for _ in path.iterdir())} entries")
        else:
            ext.append(f"- {label} `{path.as_posix()}`: DOES NOT EXIST "
                       f"— do not probe it")
    # Appended dynamically, not written into the static prompt: which
    # dossier files exist varies per round, and judges burned probe
    # rounds discovering the layout (2026-08-22, x8).
    manifest = ("\n\n## This round's dossier — actually present\n"
                + ", ".join(f"`{n}`" for n in present)
                + "\n(a file the prompt names that is not listed here "
                  "does not exist this round — do not probe for it)\n\n"
                  "Workspace paths the prompt references:\n"
                + "\n".join(ext) + "\n\n"
                # The papers dir's `agent/` holds REFUSED documents too
                # since 2026-09-06, and a reviewer that reads one as
                # settled prior work would fire criterion 1 on a
                # document for restating something nothing established.
                + AGENT_SHELF_NOTE + "\n")
    dst.write_text(
        src.read_text(encoding="utf-8")
        .replace(PROOFS_DIR_PLACEHOLDER, proofs_dir.as_posix())
        .replace(PAPERS_DIR_PLACEHOLDER, papers_dir.as_posix())
        + manifest,
        encoding="utf-8")
    return dst


def review(*, round_no: int, attempts_dir: Path, conn: sqlite3.Connection,
           workspace: Path, problem: str, group_id: "int | None",
           objective: str, situation: str, report_body: str,
           dialogue: "list[dict]", pipeline_id: str,
           quota_park=None) -> "tuple[dict | None, str, int]":
    """One review round: fresh reviewer, projection-isolated.

    Returns (verdict, err, rc): rc != 0 → provider failure; rc == 0 with
    err → the reviewer produced no usable ruling; else the verdict is
    validated."""
    from ... import agent
    from ...core import config
    from ...state import project_docs as _project_docs
    from ...state import projects as _projects
    from ...state import db
    from .. import PROMPT_DIR, write_tools_mcp_config

    timeout_sec = config.get(
        "theory_reviewer.timeout_sec", default=7200,
        env_var="ASTERISM_THEORY_REVIEWER_TIMEOUT_SEC", cast=int)
    proj = build_review_projection(
        round_no=round_no, attempts_dir=attempts_dir, conn=conn,
        workspace=workspace, problem=problem, group_id=group_id,
        objective=objective, situation=situation,
        report_body=report_body, dialogue=dialogue)
    problem_dir = db.problem_dir(workspace, problem)
    proofs_dir = (problem_dir / "proofs").resolve()
    project = (_projects.project_of(conn, problem)
               or problem.split(".", 1)[0])
    papers_dir = _project_docs.root(workspace, project).resolve()
    present = sorted(p.name for p in proj.iterdir()
                     if p.is_file() and not p.name.startswith("_"))
    prompt_path = _render_prompt(
        PROMPT_DIR / "theorist" / "review.md",
        proj / "_theory_review_prompt.md",
        proofs_dir=proofs_dir, papers_dir=papers_dir, present=present)
    tools_cfg = write_tools_mcp_config(proj, workspace,
                                       seat="theory_reviewer",
                                       problem=problem)
    last_err = ""
    infra_tries = 0
    spawn_kw = dict(
        kind="theory_reviewer", prompt_path=prompt_path,
        problem_dir=proj, attempts_dir=proj, timeout_sec=timeout_sec,
        mcp_config_path=tools_cfg,
        # Read-only, in place — the same grant the batch judge has, and
        # for the same reason: the landed proofs and the Project's
        # documents are ground truth, not the author's narrative, so
        # reading them widens no independence boundary.
        extra_read_dirs=(proofs_dir, papers_dir),
        # The projection breaks the standard attempts layout; attribute
        # the cost explicitly or the spawn_usage row is silently dropped
        # (the invisible-judge class).
        usage_workspace=workspace, usage_problem=problem,
        usage_pipeline_id=pipeline_id)

    def _spawn() -> int:
        """The reviewer, with the PROVIDER's own failures absorbed.

        An infra rc here costs the AUTHOR's document: the round hands rc
        back, the wake fails, and the whole run is re-authored from
        cold. Same budget and the same park the batch judge gets
        (`adversary.review`) — a confirmed quota window is slept to, a
        blind one buys two re-spawns."""
        nonlocal infra_tries
        from ...state import failures as _failures
        from . import _rc_reason
        while True:
            rc = agent.spawn_llm(session_id=str(uuid.uuid4()), **spawn_kw)
            if rc == 0 or not _failures.is_infra(
                    _rc_reason(rc, "theory_reviewer", proj)):
                return rc
            if quota_park is not None and quota_park(
                    f"theory review r{round_no}"):
                continue
            if infra_tries >= INFRA_SPAWN_RETRIES:
                return rc
            infra_tries += 1
            print(f"[theorist] review r{round_no}: spawn rc={rc} (infra) "
                  f"— retry {infra_tries}/{INFRA_SPAWN_RETRIES} in "
                  f"{INFRA_RETRY_BACKOFF_SEC:.0f}s; the document stays "
                  f"alive", flush=True)
            time.sleep(INFRA_RETRY_BACKOFF_SEC)

    for attempt in range(VERDICT_TRIES):
        rc = _spawn()
        if rc != 0:
            return None, "", rc
        vpath = proj / VERDICT_BASENAME
        if not vpath.is_file():
            last_err = "the reviewer produced no verdict.json"
        else:
            raw = vpath.read_text(encoding="utf-8")
            verdict, perr = parse_theory_verdict(raw)
            if verdict is not None:
                return verdict, "", 0
            # The refused file IS the evidence for the refusal; it moves
            # aside, it does not vanish.
            kept = keep_rejected_verdict(vpath, round_no=round_no)
            last_err = (f"{perr} [wrote: {describe_verdict_shape(raw)}; "
                        f"kept {kept.name}]")
        print(f"[theorist] review r{round_no} try {attempt + 1}: "
              f"{last_err}", flush=True)
    return None, last_err, 0
