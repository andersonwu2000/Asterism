"""pipeline.adversary — the Adversary role (research_mode_design.md §3).

A fresh, hard-isolated judge for every proposal package. Isolation is
a projection DIRECTORY: the framework assembles the allowed files
verbatim into `<attempts>/adversary/r<N>/` and the spawn's cwd (and
sole trust surface) is that directory — the problem dir, plan note and
directive history sit outside the CLI's `cwd ∪ --add-dir` boundary
(claude_cli narrows the add-dirs for kind='adversary'). Fresh session
per round: a resumed judge defends its own previous rebuttal, so each
round's judge instead reads the cycle dialogue as documents.

Verdict contract (`verdict.json` written by the judge into its cwd —
per-criterion adjudication, 2026-07-25; five instances across three
b6_1 legs of the judge naming a defect and passing anyway, so the
pass/rebut decision is no longer the model's to write):
    {"criteria": {"1": "clear" | "fired: <objection>", ..., "5": ...},
     "reservations": ["...", ...]}   # advisory notes; legal only for
                                     # concerns that fire no criterion
The framework DERIVES the verdict: any `fired` → rebut (the fired
lines go to the strategist via the retry channel), all `clear` → pass.
`parse_verdict` synthesizes the legacy keys ("verdict"/"criticisms"/
"reservations") so downstream consumers are unchanged.
"""
from __future__ import annotations

import json
import re
import shutil
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Optional

VERDICT_BASENAME = "verdict.json"
PROJECTION_DIRNAME = "adversary"


def _decisions_digest(decisions, conn=None, problem=None) -> str:
    """Render the batch's decisions for the judge (briefs + directive —
    the package members it reviews alongside the Programme).

    07-29 judge feedback: goal targets rendered as bare ids were
    unverifiable inside the sandbox (CATALOG carries names, not ids) —
    annotate with `(slug, status)` when a conn is given. The directive
    body lives in `payload['body']` on real Decision objects (the
    `.body` attribute only ever existed on test fixtures), so criterion
    5 was judging a directive it could not read."""
    out: list[str] = ["# This batch's decisions\n"]
    for i, d in enumerate(decisions, 1):
        kind = getattr(d, "kind", "?")
        pipeline = getattr(d, "pipeline", None)
        target = getattr(d, "target_id", None)
        head = f"## {i}. {kind}"
        if pipeline:
            head += f"({pipeline})"
        if target is not None:
            anno = ""
            if conn is not None:
                try:
                    if str(target).lstrip("-").isdigit():
                        row = conn.execute(
                            "SELECT slug, status FROM goals WHERE id = ?",
                            (int(target),)).fetchone()
                    else:
                        row = conn.execute(
                            "SELECT slug, status FROM goals"
                            " WHERE slug = ? AND (? IS NULL OR problem = ?)"
                            " ORDER BY id DESC LIMIT 1",
                            (str(target), problem, problem)).fetchone()
                    if row is not None:
                        anno = f" (`{row['slug']}`, {row['status']})"
                except Exception:  # noqa: BLE001 — annotation only
                    anno = ""
            head += f" → {target}{anno}"
        out.append(head)
        brief = getattr(d, "brief", None)
        body = getattr(d, "body", None) or (
            getattr(d, "payload", None) or {}).get("body")
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
                     proof_warn: Optional[str]) -> Path:
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
    # Formal ground truth (user call 07-19): proposal claims cite the
    # actual Lean statement; without read-only copies the judge could
    # only check them against the Manifest's prose (07-19 feedback ×7
    # — permission-denied on every Root/Defs read attempt). Isolation
    # unchanged: copies into the projection, no sandbox widening.
    # TREE.md joined 07-29 (judge feedback ×2): tree-shape and status
    # claims were uncheckable; names+statuses live here (ids do not —
    # decisions.md annotates its id targets with slug+status instead).
    for fname in ("Root.lean", "Defs.lean", "TREE.md"):
        src = problem_dir / fname
        if src.exists():
            shutil.copyfile(src, proj / fname)
    # CATALOG.md is lazily machine-generated per assembly and never
    # lives in problem_dir — generate it into the projection directly
    # (the old problem_dir copy was dead code: the judge could never
    # check "X already landed" claims; 07-19 feedback).
    # Workspace from attempts_dir (fixed <workspace>/.attempts/<pid>
    # layout), NOT problem_dir: problem nesting varies (flat vs
    # Problems/<Domain>/<name>), and the wrong root made the signature
    # file-read silently fall back to the bare DB statement — the judge
    # then saw `Prop` where the strategist's own CATALOG carried the
    # full def, and prosecuted an honest citation as fabrication for
    # two rounds (cube_e2e 07-29).
    from ..agent.context import write_catalog_companion
    write_catalog_companion(conn, problem, proj,
                            workspace=attempts_dir.parent.parent)

    # Current rev + the terminal outcomes since it, welded into one
    # file: the outcomes ARE this rev's execution record, and the
    # judge's first duty is checking the candidate's Argument against
    # them (判官必見源). Outcome lines reuse the exact section the
    # strategist context renders.
    current = programme.current_rev(conn, problem)
    outcome_lines = _section_inject_batch_outcomes(
        conn, problem, workspace=attempts_dir.parent.parent)
    (proj / "PROGRAMME.md").write_text(
        (current["body"] if current is not None else
         "(no Programme yet — this cycle's proposal is rev 1; judge it "
         "as the founding revision)")
        + "\n\n---\n\n"
        # Label the weld (a5 rev-13 verdict called a Thesis line stale
        # because of it): the execution record below exists only in
        # THIS projection; the problem-dir PROGRAMME.md carries the
        # revision text alone, so proposal text describing that file
        # is judged against the right referent.
        + "_(Execution record below is assembled for this review; the "
        "problem's PROGRAMME.md file carries the revision text only.)_"
        + "\n\n"
        + ("\n".join(outcome_lines) if outcome_lines else
           "## Completed Inject batches\n(none since the last commit)")
        + "\n", encoding="utf-8")

    head = ""
    if proof_warn:
        head = proof_warn + "\n\n"
    (proj / "proposal.md").write_text(head + proposal_body + "\n",
                                      encoding="utf-8")
    decisions_text = _decisions_digest(decisions, conn=conn,
                                       problem=problem)
    (proj / "decisions.md").write_text(decisions_text, encoding="utf-8")
    # Cited landed proofs (07-29 judge feedback ×6): the artifacts the
    # package's claims cite must be checkable inside the sandbox — a
    # RETARGETED dispute's only deciding document is the landed file.
    # Any on-disk proofs/L_<slug>.lean whose slug the package text
    # mentions rides along read-only. Cap 20 with a loud log (no
    # silent caps).
    proofs_src = problem_dir / "proofs"
    if proofs_src.is_dir():
        package_text = proposal_body + "\n" + decisions_text
        staged = 0
        for f in sorted(proofs_src.glob("L_*.lean")):
            slug = f.stem[2:]
            if not re.search(rf"\b{re.escape(slug)}\b", package_text):
                continue
            if staged >= 20:
                print("[adversary] cited-proofs staging cap (20) hit — "
                      "remaining cited files NOT staged", flush=True)
                break
            (proj / "proofs").mkdir(exist_ok=True)
            shutil.copyfile(f, proj / "proofs" / f.name)
            staged += 1
    if dialogue:
        (proj / "dialogue.md").write_text(_dialogue_digest(dialogue),
                                          encoding="utf-8")
    return proj


CRITERIA_KEYS = ("1", "2", "3", "4", "5")


def parse_verdict(text: str) -> tuple[Optional[dict[str, Any]], str]:
    """Validate the per-criterion verdict.json and DERIVE the ruling.

    Each criterion line is `"clear"` or `"fired: <objection>"`; any
    fired line makes the verdict a rebut. Returns a dict carrying the
    synthesized legacy keys (`verdict` / `criticisms` / `reservations`)
    plus the raw `criteria`, or (None, err) on a malformed file."""
    try:
        v = json.loads(text)
    except ValueError as e:
        return None, f"verdict.json is not valid JSON: {e}"
    if not isinstance(v, dict):
        return None, "verdict.json must be a JSON object"
    criteria = v.get("criteria")
    if not isinstance(criteria, dict):
        return None, ("verdict.json needs a `criteria` object "
                      "adjudicating every criterion \"1\"..\"5\"")
    missing = [k for k in CRITERIA_KEYS if k not in criteria]
    if missing:
        return None, (f"verdict.json `criteria` missing criterion "
                      f"{', '.join(missing)} — every criterion gets a "
                      f"line, `\"clear\"` or `\"fired: <objection>\"`")
    fired: list[str] = []
    for k in CRITERIA_KEYS:
        val = criteria[k]
        if not isinstance(val, str):
            return None, f"criterion {k} must be a string"
        s = val.strip()
        # Prefix-keyed, annotation-tolerant (07-29, third occurrence of
        # the same wake-killing parse: opus-tier judges annotate their
        # verdicts — `"clear — I checked the chain end to end…"` — and
        # the literal match threw away two full adversary rounds per
        # hit. The DISCRIMINATOR is the leading word (word-boundary, so
        # "clearly…" stays malformed); suffix prose is tolerated.
        if re.match(r"clear\b", s, re.IGNORECASE):
            continue
        if re.match(r"fired\b", s, re.IGNORECASE):
            reason = (s.split(":", 1)[1].strip() if ":" in s
                      else s[5:].strip(" -—–:"))
            if not reason:
                return None, (f"criterion {k} is fired but carries no "
                              f"objection — `\"fired: <objection>\"`")
            fired.append(f"[criterion {k}] {reason}")
            continue
        return None, (f"criterion {k} must be \"clear\" or "
                      f"\"fired: <objection>\" (got {val!r})")
    reservations = v.get("reservations", [])
    if not (isinstance(reservations, list)
            and all(isinstance(x, str) for x in reservations)):
        return None, "verdict.json `reservations` must be a list of strings"
    return {
        "verdict": "rebut" if fired else "pass",
        "criticisms": fired,
        "reservations": reservations,
        "criteria": {k: criteria[k] for k in CRITERIA_KEYS},
    }, ""


def review(*, round_no: int, attempts_dir: Path, problem_dir: Path,
           conn: sqlite3.Connection, problem: str, proposal_body: str,
           decisions, dialogue: list[dict[str, Any]],
           proof_warn: Optional[str]) -> tuple[
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
        dialogue=dialogue, proof_warn=proof_warn)
    prompt_path = PROMPT_DIR / "adversary" / "adversary.md"

    # One re-spawn on a missing/malformed verdict (cheap; a judge that
    # produced no usable ruling twice is a wake-level failure).
    last_err = ""
    for _attempt in range(2):
        sid = str(uuid.uuid4())
        rc = agent.spawn_llm(
            kind="adversary", prompt_path=prompt_path,
            problem_dir=proj, attempts_dir=proj,
            session_id=sid, timeout_sec=timeout_sec,
            # The projection dir breaks the standard attempts layout —
            # attribute the judge's cost explicitly or the spawn_usage
            # row is silently dropped (invisible-judge class, 07-18).
            usage_workspace=attempts_dir.parent.parent,
            usage_problem=problem,
            usage_pipeline_id=attempts_dir.name,
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
        # Framework-feedback questionnaire — the judge was the one spawn
        # family without the channel (zero adversary lines ever landed).
        # Resume cwd stays the projection: isolation holds; only the
        # record's label names the real problem.
        from . import _feedback
        _feedback.attempt_feedback(
            kind="adversary", sid=sid, slug=f"r{round_no}",
            outcome=str(verdict.get("verdict", "")),
            problem_dir=proj, attempts_dir=proj,
            workspace=attempts_dir.parent.parent,
            problem_label=problem)
        return verdict, "", 0
    return None, last_err, 0
