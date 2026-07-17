"""pipeline.adversary — the Adversary role (research_mode_design.md §3).

A fresh, hard-isolated judge for every proposal package. Isolation is
a projection DIRECTORY: the framework assembles the allowed files
verbatim into `<attempts>/adversary/r<N>/` and the spawn's cwd (and
sole trust surface) is that directory — the problem dir, plan note and
directive history sit outside the CLI's `cwd ∪ --add-dir` boundary
(claude_cli narrows the add-dirs for kind='adversary'). Fresh session
per round: a resumed judge defends its own previous rebuttal, so each
round's judge instead reads the cycle dialogue as documents.

Verdict contract (`verdict.json` written by the judge into its cwd):
    {"verdict": "pass" | "rebut",
     "reservations": ["...", ...],   # pass: advisory notes, rendered
                                     # attributed to workers + header
     "criticisms":   ["...", ...]}   # rebut: returned verbatim to the
                                     # strategist via the retry channel
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Optional

VERDICT_BASENAME = "verdict.json"
PROJECTION_DIRNAME = "adversary"


def _decisions_digest(decisions) -> str:
    """Render the batch's decisions for the judge (briefs + directive —
    the package members it reviews alongside the Programme)."""
    out: list[str] = ["# This batch's decisions\n"]
    for i, d in enumerate(decisions, 1):
        kind = getattr(d, "kind", "?")
        pipeline = getattr(d, "pipeline", None)
        target = getattr(d, "target_id", None)
        head = f"## {i}. {kind}"
        if pipeline:
            head += f"({pipeline})"
        if target is not None:
            head += f" → {target}"
        out.append(head)
        brief = getattr(d, "brief", None)
        body = getattr(d, "body", None)
        reason = getattr(d, "reason", None)
        if brief:
            out.append(str(brief))
        if body:
            out.append("Directive body:\n" + str(body))
        if reason:
            out.append(f"reason: {reason}")
        out.append("")
    return "\n".join(out)


def _dialogue_digest(dialogue: list[dict[str, Any]]) -> str:
    """Prior rounds of this cycle, projected as a document so the fresh
    judge can rule on the standing defence without inheriting the
    previous judge's session."""
    out = ["# Cycle dialogue so far\n",
           "Earlier rounds of this proposal cycle. Judge the CURRENT "
           "proposal (proposal.md); treat a point the strategist already "
           "defended as settled unless you bring a new argument.\n"]
    for entry in dialogue:
        role = entry.get("role", "?")
        rnd = entry.get("round", "?")
        out.append(f"## round {rnd} — {role}")
        if entry.get("criticisms"):
            out += [f"- {c}" for c in entry["criticisms"]]
        if entry.get("proposal"):
            out.append("(the proposal those criticisms targeted:)\n"
                       + str(entry["proposal"]))
        out.append("")
    return "\n".join(out)


def build_projection(*, round_no: int, attempts_dir: Path,
                     problem_dir: Path, conn: sqlite3.Connection,
                     problem: str, proposal_body: str, decisions,
                     dialogue: list[dict[str, Any]],
                     thesis_warn: Optional[str]) -> Path:
    """Assemble the whitelist verbatim into an isolated working dir."""
    from ..agent.phase2_context import _section_inject_batch_outcomes
    from ..state import programme

    proj = attempts_dir / PROJECTION_DIRNAME / f"r{round_no}"
    if proj.exists():
        shutil.rmtree(proj, ignore_errors=True)
    proj.mkdir(parents=True, exist_ok=True)

    manifest = problem_dir / "Manifest.md"
    if manifest.exists():
        shutil.copyfile(manifest, proj / "Manifest.md")
    catalog = problem_dir / "CATALOG.md"
    if catalog.exists():
        shutil.copyfile(catalog, proj / "CATALOG.md")

    # Current rev + the terminal outcomes since it, welded into one
    # file: the outcomes ARE this rev's execution record, and the
    # judge's first duty is checking the candidate's Argument against
    # them (判官必見源). Outcome lines reuse the exact section the
    # strategist context renders.
    current = programme.current_rev(conn, problem)
    outcome_lines = _section_inject_batch_outcomes(conn, problem)
    (proj / "PROGRAMME.md").write_text(
        (current["body"] if current is not None else
         "(no Programme yet — this cycle's proposal is rev 1; judge it "
         "as the founding revision)")
        + "\n\n---\n\n"
        + ("\n".join(outcome_lines) if outcome_lines else
           "## Completed Inject batches\n(none since the last commit)")
        + "\n", encoding="utf-8")

    head = ""
    if thesis_warn:
        head = thesis_warn + "\n\n"
    (proj / "proposal.md").write_text(head + proposal_body + "\n",
                                      encoding="utf-8")
    (proj / "decisions.md").write_text(_decisions_digest(decisions),
                                       encoding="utf-8")
    if dialogue:
        (proj / "dialogue.md").write_text(_dialogue_digest(dialogue),
                                          encoding="utf-8")
    return proj


def parse_verdict(text: str) -> tuple[Optional[dict[str, Any]], str]:
    """Validate verdict.json. Returns (verdict, '') or (None, err)."""
    try:
        v = json.loads(text)
    except ValueError as e:
        return None, f"verdict.json is not valid JSON: {e}"
    if not isinstance(v, dict):
        return None, "verdict.json must be a JSON object"
    verdict = v.get("verdict")
    if verdict not in ("pass", "rebut"):
        return None, ("verdict.json `verdict` must be \"pass\" or "
                      f"\"rebut\" (got {verdict!r})")
    for key in ("reservations", "criticisms"):
        val = v.get(key, [])
        if not (isinstance(val, list)
                and all(isinstance(x, str) for x in val)):
            return None, f"verdict.json `{key}` must be a list of strings"
        v[key] = val
    if verdict == "rebut" and not v["criticisms"]:
        return None, ("a rebut verdict must carry at least one concrete "
                      "criticism in `criticisms`")
    return v, ""


def review(*, round_no: int, attempts_dir: Path, problem_dir: Path,
           conn: sqlite3.Connection, problem: str, proposal_body: str,
           decisions, dialogue: list[dict[str, Any]],
           thesis_warn: Optional[str]) -> tuple[
               Optional[dict[str, Any]], str, int]:
    """One adversarial round: fresh judge, projection-isolated.

    Returns (verdict, err, rc): rc != 0 → provider failure (verdict and
    err empty); rc == 0 with err → the judge produced no usable
    verdict; else verdict is validated."""
    from .. import agent
    from ..core import config
    from . import PROMPT_DIR

    # NL argumentation layer runs without a work budget (design §0);
    # the cap is a hang guard, same class as strategist.timeout_sec.
    timeout_sec = config.get(
        "adversary.timeout_sec", default=7200,
        env_var="ASTERISM_ADVERSARY_TIMEOUT_SEC", cast=int,
    )
    proj = build_projection(
        round_no=round_no, attempts_dir=attempts_dir,
        problem_dir=problem_dir, conn=conn, problem=problem,
        proposal_body=proposal_body, decisions=decisions,
        dialogue=dialogue, thesis_warn=thesis_warn)
    prompt_path = PROMPT_DIR / "adversary" / "adversary.md"

    # One re-spawn on a missing/malformed verdict (cheap; a judge that
    # produced no usable ruling twice is a wake-level failure).
    last_err = ""
    for _attempt in range(2):
        rc = agent.spawn_llm(
            kind="adversary", prompt_path=prompt_path,
            problem_dir=proj, attempts_dir=proj,
            session_id=str(uuid.uuid4()), timeout_sec=timeout_sec,
        )
        if rc != 0:
            return None, "", rc
        vpath = proj / VERDICT_BASENAME
        if not vpath.exists():
            last_err = "adversary produced no verdict.json"
            continue
        try:
            text = vpath.read_text(encoding="utf-8")
        except OSError as e:
            last_err = f"verdict.json unreadable: {e}"
            continue
        verdict, perr = parse_verdict(text)
        if verdict is None:
            last_err = perr
            vpath.unlink(missing_ok=True)
            continue
        return verdict, "", 0
    return None, last_err, 0
