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

HOW that dossier reaches the reviewer is `theory_reviewer.dossier`
(owner ruling 2026-09-07, the batch judge's flag one seat over):
`files` — today — names the projection's files and the reviewer opens
them; `inline` puts the small always-read ones in the prompt verbatim
and maps the rest. The block shapes are shared (`pipeline/dossier.py`);
which file gets which is below, because it is a reading of THIS
projection.
"""
from __future__ import annotations

import shutil
import sqlite3
import time
import uuid
from pathlib import Path

from .. import dossier as _dossier
from ..adversary import INFRA_RETRY_BACKOFF_SEC, INFRA_SPAWN_RETRIES
from .verdict import (REPORT_BASENAME, VERDICT_BASENAME, VERDICT_TRIES,
                      describe_verdict_shape, keep_rejected_verdict,
                      parse_theory_verdict, write_rubric)

PROJECTION_DIRNAME = "review"
REQUEST_BASENAME = "request.md"

#: The two names `prompts/theorist/review.md` splits criterion 3's PUSH
#: half on. Exactly one is true on any round, and BOTH are always
#: spelled — `agent/runtime.render_prompt_template` is FAIL-OPEN (a
#: conditional whose flag it was never given is rendered), so handing it
#: only the true one would render the other block too and the reviewer
#: would read two contradictory instructions: "require the next step"
#: and "no revision follows this round".
FLAG_MORE_ROUNDS = "more_rounds"
FLAG_FINAL_ROUND = "final_round"


def round_prompt_flags(final_round: bool) -> "dict[str, bool]":
    """Criterion 3's flags for a round that is (or is not) the last one.

    A round is FINAL when no revision is owed after it — the author will
    never see this ruling, so a line the reviewer finds past the
    author's stop has nowhere to go but `reservations`, which travels
    with the document to the Strategist."""
    return {FLAG_MORE_ROUNDS: not final_round,
            FLAG_FINAL_ROUND: bool(final_round)}

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


# ---------------------------------------------------------------------
# how the dossier reaches the reviewer (`theory_reviewer.dossier`)
# ---------------------------------------------------------------------

#: Inlined FIRST, in this order, and round-INVARIANT: the same bytes for
#: every round of one review. That is the whole reason the order is
#: fixed rather than alphabetical or directory order — a provider caches
#: a prompt by its prefix, so anything that changes between rounds has
#: to sit after everything that does not, or round 2 pays full price for
#: text round 1 already paid for.
DOSSIER_INLINE_INVARIANT = ("charter.md", REQUEST_BASENAME, "PROGRAMME.md")
#: Inlined after them, and round-VARYING: `report.md` IS the thing under
#: review and is rewritten by every revision, so it can never sit in the
#: prefix. It is inlined whole rather than mapped — 28-45KB, and the
#: rubric's second criterion is "re-derive it", which is not a thing
#: anyone does from a section at a time.
#:
#: `since.md` is the batch judge's name for "what landed while the
#: author was writing" and this projection does not write one today; it
#: is listed so that the day it does, it lands after the report instead
#: of silently outside the dossier.
DOSSIER_INLINE_TAIL = (REPORT_BASENAME, "since.md")
DOSSIER_INLINE_ORDER = DOSSIER_INLINE_INVARIANT + DOSSIER_INLINE_TAIL

#: Mapped, not inlined. TREE.md because it is big (~40KB) and a
#: minority of rounds turn on a line of it; `dialogue.md` because it
#: grows by one round every round — it could never sit in the cacheable
#: prefix, and what a reviewer wants out of it is one round's bullets,
#: which its headings ARE. What rides is the OUTLINE — the headings,
#: line ranges and sizes `inspect` would answer with.
DOSSIER_OUTLINED = ("TREE.md", "dialogue.md")

#: Not even outlined: CATALOG.md is hundreds of sections, so its map IS
#: a roster and printing it would cost more than the file.
DOSSIER_ROSTERS = ("CATALOG.md",)

#: The two sub-roots of `{papers_dir}`, listed by NAME. Criterion 1 asks
#: whether the document has something the record and the notes do not
#: already have, so what exists on that shelf is evidence — see
#: `dossier.notes_block`.
DOSSIER_NOTE_AREAS = ("agent", "user")


def dossier_mode() -> str:
    """`files` (today) or `inline`, from `theory_reviewer.dossier`."""
    from ...core import config
    return _dossier.normalize(
        config.get("theory_reviewer.dossier", default=_dossier.FILES,
                   env_var="ASTERISM_THEORY_REVIEWER_DOSSIER"),
        key="theory_reviewer.dossier", seat="theorist")


def dossier_sections(proj: Path, *, proofs_dir: Path,
                     papers_dir: Path) -> str:
    """`## Dossier (inline)` + `## Table of contents`, for `inline` mode.

    Everything the reviewer is otherwise sent to `inspect` for, resolved
    by the builder that already knows the answer. The two sections sit
    BETWEEN the rubric and the per-spawn manifest: the rubric is the
    same text for every review, this is the same text for every round of
    one review down to `### report.md`, and the manifest is the one part
    that is this spawn's alone."""
    out: "list[str]" = [
        "", "## Dossier (inline)", "",
        "These files are here in full. They are the dossier — do not "
        "open them, and do not spend a query re-reading one.", ""]
    for name in DOSSIER_INLINE_ORDER:
        p = proj / name
        if p.is_file():
            out += _dossier.inline_block(name, p)
    out += ["## Table of contents (read on demand)", "",
            "These are NOT inlined — they are big and most rounds need "
            "one section of one of them. Read a section with "
            '`inspect([{"read": "<file>", "sections": ["<heading>"]}])`; '
            "the line ranges below are what that call answers from.", ""]
    for name in DOSSIER_OUTLINED:
        p = proj / name
        if p.is_file():
            out += _dossier.outline_block(name, p)
    for name in DOSSIER_ROSTERS:
        p = proj / name
        if p.is_file():
            out += _dossier.roster_block(name, p)
    out += _dossier.notes_block("papers dir", papers_dir,
                                areas=DOSSIER_NOTE_AREAS)
    out += _dossier.dir_block("proofs dir", proofs_dir)
    return "\n".join(out) + "\n"


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
                   papers_dir: Path, present: "list[str]",
                   dossier: str = "") -> Path:
    """The reviewer's prompt with its two workspace placeholders filled,
    the inline dossier (empty in `files` mode) and this round's manifest.

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
    # Rubric, then (in `inline` mode) the dossier and its table of
    # contents, then the per-spawn manifest LAST — cheapest-to-cache
    # first. In `files` mode the middle is empty and this is byte for
    # byte the prompt every round has been written since the manifest
    # landed; the `#if dossier_inline` sentence in the rubric is dropped
    # by the template renderer on the flag `review` passes.
    dst.write_text(
        src.read_text(encoding="utf-8")
        .replace(PROOFS_DIR_PLACEHOLDER, proofs_dir.as_posix())
        .replace(PAPERS_DIR_PLACEHOLDER, papers_dir.as_posix())
        + dossier + manifest,
        encoding="utf-8")
    return dst


def review(*, round_no: int, attempts_dir: Path, conn: sqlite3.Connection,
           workspace: Path, problem: str, group_id: "int | None",
           objective: str, situation: str, report_body: str,
           dialogue: "list[dict]", pipeline_id: str, final_round: bool,
           quota_park=None) -> "tuple[dict | None, str, int]":
    """One review round: fresh reviewer, projection-isolated.

    `final_round` says whether a revision is owed AFTER this round, and
    it has no default ON PURPOSE: it selects one of criterion 3's two
    push halves and the renderer is fail-open, so a caller that forgot
    it would show the reviewer both. Every caller must decide.

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
    mode = dossier_mode()
    prompt_path = _render_prompt(
        PROMPT_DIR / "theorist" / "review.md",
        proj / "_theory_review_prompt.md",
        proofs_dir=proofs_dir, papers_dir=papers_dir, present=present,
        dossier=(dossier_sections(proj, proofs_dir=proofs_dir,
                                  papers_dir=papers_dir)
                 if mode == _dossier.INLINE else ""))
    tools_cfg = write_tools_mcp_config(proj, workspace,
                                       seat="theory_reviewer",
                                       problem=problem)
    last_err = ""
    infra_tries = 0
    # A refused verdict goes back to the SAME reviewer, carrying the
    # parser's message (2026-09-06, the judge's `479fd579` one seat
    # over): the retry used to mint a blind fresh reviewer and `last_err`
    # was only printed, so one shape error could burn every try. A
    # non-empty `retry_ctx` IS the resume; the sid is re-minted only for
    # a cold spawn.
    sid = ""
    retry_ctx = ""
    spawn_kw = dict(
        kind="theory_reviewer", prompt_path=prompt_path,
        problem_dir=proj, attempts_dir=proj, timeout_sec=timeout_sec,
        mcp_config_path=tools_cfg,
        # Criterion 3's push half, per round, and which dossier wording
        # the `## What you see` section carries. Both names of each pair
        # are always given — see `round_prompt_flags`.
        prompt_flags={**round_prompt_flags(final_round),
                      **_dossier.prompt_flags(mode)},
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
        nonlocal infra_tries, sid, retry_ctx
        from ...state import failures as _failures
        from . import _rc_reason
        while True:
            if not retry_ctx:
                sid = str(uuid.uuid4())
            rc = agent.spawn_llm(
                session_id=sid, is_retry=bool(retry_ctx),
                retry_context=retry_ctx or None, **spawn_kw)
            if rc == 0 or not _failures.is_infra(
                    _rc_reason(rc, "theory_reviewer", proj)):
                return rc
            # The resume itself died on the provider side, so that
            # session is not a thing to go back to: the next spawn is
            # cold (the refused file stays on disk either way).
            retry_ctx = ""
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
            retry_ctx = ""   # no file, so no refusal to hand back
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
            # The whole refusal, authored here — no provider knows the
            # parser's message or where the file went, so each renders
            # this as written (`_RETRY_PROMPTS["theory_reviewer"]`).
            retry_ctx = (
                f"The framework refused your {VERDICT_BASENAME}: {perr}"
                f"\n\nRewrite {proj}/{VERDICT_BASENAME} — your reading "
                f"of the document is unchanged; this is its shape. The "
                f"refused file was kept as {kept.name}.")
        print(f"[theorist] review r{round_no} try {attempt + 1}: "
              f"{last_err}", flush=True)
    return None, last_err, 0
