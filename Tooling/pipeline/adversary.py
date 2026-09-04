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
    {"criteria": {"1": ["fired: <objection>", ...] | ["clear"], ...},
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
import time
import uuid
from pathlib import Path
from typing import Any, Optional

from ..state import failures


def _rc_reason(rc: int) -> str:
    """The judge's rc, read against the JUDGE's provider contract.

    The Adversary routinely sits on a different provider from its
    author, and an `uninformative` rc (agy exits 1 for every ERROR
    envelope) must not be reported as a specific cause — see
    `llm/capabilities.py`."""
    from ..llm import capabilities as _caps
    return failures.rc_to_reason(
        rc, rc_contract=_caps.for_kind("adversary").rc_contract)


VERDICT_BASENAME = "verdict.json"
PROJECTION_DIRNAME = "adversary"
#: `review` budgets, kept separate on purpose: a judge that produced no
#: usable ruling twice is a wake-level failure (the agent is the
#: problem), whereas a provider-side rc is nobody's ruling and must not
#: cost the Strategist's finished proposal (task #132).
VERDICT_TRIES = 2
INFRA_SPAWN_RETRIES = 2
INFRA_RETRY_BACKOFF_SEC = 15.0


#: Fields the head line already carries — skipped by the field dump so
#: the judge does not read the same value twice. This is the whole of
#: the exclusion list, and it exists because the value is rendered
#: ELSEWHERE, never because a field is judged unimportant: see
#: `_decisions_digest`.
_HEAD_FIELDS = ("pipeline",)

#: A single-line value no longer than this rides its label; anything
#: longer, or anything containing a newline, gets its own fenced block.
#: NOT a cap — nothing is ever truncated. The fence is a boundary: an
#: `Ingest.report` is itself a markdown paper whose `## Introduction`
#: would otherwise read as a section of `decisions.md`, sitting at the
#: same level as the `## N. Kind` headings around it.
_INLINE_MAX = 120


def _fence_for(text: str) -> str:
    """A backtick fence longer than any run inside `text`, so a field
    that quotes code or Lean stays byte-identical inside its block."""
    longest = max((len(r) for r in re.findall(r"`+", text)), default=0)
    return "`" * max(3, longest + 1)


def _render_field(name: str, value: Any) -> "list[str]":
    """One field as the judge reads it, labelled with the name the
    Strategist's contract uses for it (`contract.md` names every field
    by its decision.json key, so the judge can match a clause to a
    value without translating)."""
    if isinstance(value, str):
        text = value
    elif isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, indent=2)
    else:
        text = str(value)
    if not text.strip():
        return []
    if "\n" not in text and len(text) <= _INLINE_MAX:
        return [f"{name}: {text}"]
    fence = _fence_for(text)
    return [f"{name}:", fence, text.rstrip("\n"), fence]


def _decisions_digest(decisions, conn=None, problem=None) -> str:
    """Render the batch's decisions for the judge — EVERY field the
    Strategist wrote, because this file is the judge's only sight of
    the batch it is ruling on.

    07-29 judge feedback: goal targets rendered as bare ids were
    unverifiable inside the sandbox (CATALOG carries names, not ids) —
    annotate with `(slug, status)` when a conn is given.

    The field dump has NO allowlist (2026-09-03, union_closed group
    693). A hand list of rendered fields grew stale the moment the
    contract gained a field: `Ingest.report` — the mathematician-facing
    paper the judge is held responsible for ruling on — and
    `MarkDeliverable.paper_ref` were both written in decision.json and
    both absent from this projection, so three consecutive rounds fired
    "bare Ingest with no report" / "MarkDeliverable omits paper_ref" at
    fields that were already there, and the Strategist had no way to
    satisfy the objection. The kinds' declared fields live in
    `prompts/adversary/_contract.md` and are checked by
    `strategist/verify.py`; the renderer does not re-declare them —
    it renders what the parser kept (`brief`, `reason`, and every
    payload entry), so a field added to the contract tomorrow reaches
    the judge without touching this function."""
    from .strategist import model as _model

    out: list[str] = ["# This batch's decisions\n"]
    for i, d in enumerate(decisions, 1):
        kind = str(getattr(d, "kind", "?"))
        payload = dict(getattr(d, "payload", None) or {})
        pipeline = getattr(d, "pipeline", None) or payload.get("pipeline")
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
        # The prose column first (its contract name depends on the kind:
        # an Inject's is `proof`, a Delegate's `charter` — one mapping,
        # shared with the parser that filled it), then the payload in
        # the author's own key order, then `reason` last.
        fields: "list[tuple[str, Any]]" = []
        brief = getattr(d, "brief", None)
        if brief:
            fields.append((_model.brief_field(kind), brief))
        # `.body` is the pre-2026 fixture shape of `payload['body']`
        # (the directive text); real Decision objects only ever carry
        # the payload key.
        legacy_body = getattr(d, "body", None)
        if legacy_body and "body" not in payload:
            payload["body"] = legacy_body
        fields += [(str(k), v) for k, v in payload.items()
                   if k not in _HEAD_FIELDS]
        reason = getattr(d, "reason", None)
        if reason:
            fields.append(("reason", reason))
        for name, value in fields:
            out += _render_field(name, value)
        out.append("")
    return "\n".join(out)


def _standing_directive_digest(conn: sqlite3.Connection,
                               problem: str) -> str:
    """The directive in force RIGHT NOW, whether or not this batch
    touches it.

    The rubric holds the batch against the directive in force, but
    `decisions.md` only carries a directive body when the batch
    emits one — so on an unchanged directive the judge was ruling on
    text it could not read, and a possibly-real mis-citation had to be
    demoted to a reservation (07-29 SG judge feedback). Every worker on
    every spawn reads this text; the judge now reads the same bytes."""
    try:
        row = conn.execute(
            "SELECT strategist_directive FROM problems WHERE name = ?",
            (problem,)).fetchone()
    except sqlite3.OperationalError:
        row = None
    body = (row["strategist_directive"] or "") if row is not None else ""
    head = ["# Standing directive (in force for every worker spawn)\n"]
    if not body.strip():
        return "\n".join(head + ["(none — no directive in force.)\n"])
    src = conn.execute(
        "SELECT batch_id, created_at FROM strategist_decisions"
        " WHERE problem = ? AND decision_kind = 'EmitDirective'"
        " ORDER BY id DESC LIMIT 1", (problem,)).fetchone()
    if src is not None:
        head.append(f"_Emitted by batch `{src['batch_id']}` "
                    f"({str(src['created_at'])[:16]})._\n")
    return "\n".join(head + [body.strip(), ""])


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


#: The judge's `{proofs_dir}` / `{papers_dir}` prompt placeholders —
#: substituted at spawn time (`review` below) with the problem's landed
#: proofs directory and its Project's document root, which is where the
#: papers live since §3.9 retired the workspace-global shelf.
PROOFS_DIR_PLACEHOLDER = "{proofs_dir}"
PAPERS_DIR_PLACEHOLDER = "{papers_dir}"


def build_projection(*, round_no: int, attempts_dir: Path,
                     problem_dir: Path, conn: sqlite3.Connection,
                     problem: str, proposal_body: str, decisions,
                     dialogue: list[dict[str, Any]],
                     proof_warn: Optional[str],
                     group_id: "int | None" = None) -> Path:
    """Assemble the whitelist verbatim into an isolated working dir."""
    from ..state import programme

    proj = attempts_dir / PROJECTION_DIRNAME / f"r{round_no}"
    if proj.exists():
        shutil.rmtree(proj, ignore_errors=True)
    proj.mkdir(parents=True, exist_ok=True)

    # v40 — every group's judge, top included, gets `charter.md` from
    # the one renderer (own charter + ancestor chain + returned
    # charters); the retired Manifest.md copy is gone. `user_word.md`
    # rides beside it: the user's standing directives, at every depth,
    # never part of the claim under judgment.
    from ..state import groups as _groups
    from ..state import intent as _intent
    charter_text = _groups.charter_digest(conn, problem, group_id)
    if charter_text:
        (proj / "charter.md").write_text(charter_text, encoding="utf-8")
    _pi = _intent.read(conn, problem)
    if _pi is not None and _pi.word:
        (proj / "user_word.md").write_text(
            "# The user's word\n\nStanding directives from the user — "
            "they govern conduct for every group at every depth and are "
            "not part of the claim under judgment.\n\n" + _pi.word + "\n",
            encoding="utf-8")
    # Formal ground truth (user call 07-19): proposal claims cite the
    # actual Lean statement; without read-only copies the judge could
    # only check them against the goal's prose (07-19 feedback ×7
    # — permission-denied on every Root/Defs read attempt). Isolation
    # unchanged: copies into the projection, no sandbox widening.
    # TREE.md joined 07-29 (judge feedback ×2): tree-shape and status
    # claims were uncheckable; names+statuses live here (ids do not —
    # decisions.md annotates its id targets with slug+status instead).
    for fname in ("Root.lean", "Defs.lean"):
        src = problem_dir / fname
        if src.exists():
            shutil.copyfile(src, proj / fname)
    # TREE.md / CATALOG.md / BATCHES.md / ADJUDICATIONS.md are the
    # round-fresh record, written by the ONE refresher both sides of the
    # debate now call (`round_materials.refresh`, 2026-09-03) — the
    # author gets the same four files in its own dir at every rebuttal
    # round, so a brick that lands mid-debate stops being a fact only
    # the judge can see. The batch-outcome render falls out of writing
    # BATCHES.md; it is welded into PROGRAMME.md below.
    #
    # Workspace from attempts_dir (fixed <workspace>/.attempts/<pid>
    # layout), NOT problem_dir: problem nesting varies (flat vs
    # Problems/<Domain>/<name>), and the wrong root made the catalog's
    # signature file-read silently fall back to the bare DB statement —
    # the judge then saw `Prop` where the strategist's own CATALOG
    # carried the full def, and prosecuted an honest citation as
    # fabrication for two rounds (cube_e2e 07-29).
    #
    # `target_dir=proj` also gives the judge the same lazy BATCHES.md
    # companion the strategist has — the briefs it is checking the
    # Argument against are the ones under judgement, and a 1200-byte cut
    # through them is how a judge came to quote a sentence that ended
    # mid-clause (08-02).
    from . import round_materials as _round_materials
    outcome_lines = _round_materials.refresh(
        conn, workspace=attempts_dir.parent.parent, problem=problem,
        group_id=group_id, target_dir=proj)
    # The decision-kind contract is reference material, not instruction:
    # 17 lines that were inlined into every judge spawn's prompt. It
    # rides the projection instead, next to the decisions it governs.
    # Its OWN file, not the head of `decisions.md` — that file is what
    # the Strategist wrote, and mixing framework text into it blurs
    # authorship for a reader who prosecutes attribution (07-31).
    contract = (Path(__file__).resolve().parents[1] / "prompts"
                / "adversary" / "_contract.md")
    if contract.exists():
        shutil.copyfile(contract, proj / "contract.md")
    # The Strategist's own Context.md, verbatim (08-01 judge feedback):
    # a proposal may quote it, and a citation the judge cannot open is a
    # free pass — one round-1 fire on "you misquoted contract.md" came
    # back in round 2 re-attributed to Context.md and had to be cleared
    # unverified. Whole file, not selected sections: a filtered copy
    # would let the judge fire on a line that exists but was withheld,
    # which is the same defect wearing framework colours, and a section
    # allowlist rots the first time someone adds a section. Lazily
    # available — it rides the projection, nothing is inlined.
    # Hoisted above the Context.md snapshot: the elision below compares
    # the snapshot's embedded Programme against this same revision text.
    current = programme.current_rev(conn, problem, group_id)
    ctx = attempts_dir / "Context.md"
    if ctx.exists():
        # Label it, same move as the PROGRAMME weld below and for the
        # same reason: judged against the wrong referent it manufactures
        # defects. This file is the author's snapshot, frozen when the
        # wake spawned; the four companions beside it are re-rendered
        # from the DB every round by `round_materials.refresh`, so they
        # are the NEWER bytes — the label says so rather than calling
        # either side live (08-15: the label
        # pointed the judge at the staler of two renders and called it
        # authoritative). A long debate (7 and 10 rounds, 60-90min,
        # 2026-08-06) widens that gap monotonically while sibling groups
        # land bricks, and the judge then fires the honesty criterion on
        # "roadmap says landed, TREE says open" — a contradiction the packet
        # itself created. The judge said so in its own feedback 5×
        # ("a stale snapshot shipped alongside live TREE/CATALOG, which
        # manufactures exactly the status-drift defects the adversary
        # keeps firing"; "no stated precedence"). The evidence stays
        # byte-identical below the label, so quotations remain checkable.
        _t = _round_materials.snapshot_taken(ctx)
        _taken = (_t.strftime("%Y-%m-%d %H:%M UTC") if _t is not None
                  else "unknown")
        ctx_text = ctx.read_text(encoding="utf-8")
        # Identity-gated elision (owner condition, 2026-08-15): the
        # snapshot embeds the Programme revision the author saw, and
        # PROGRAMME.md in this same projection opens with that text —
        # the adversary's grounding sweep paid the same 20-26KB twice
        # per round on union_closed. Elide ONLY on byte-identity, so
        # every elided byte is recoverable verbatim from the named
        # file; any difference at all and the snapshot ships whole,
        # because "what the author saw" must survive verbatim wherever
        # it is not byte-recoverable. The length guard keeps a
        # degenerate short body from matching unrelated text.
        body = str(current["body"] or "") if current is not None else ""
        if len(body) >= 100 and body in ctx_text:
            ctx_text = ctx_text.replace(
                body,
                "_(Programme revision text elided — byte-identical to"
                " the revision at the top of PROGRAMME.md in this"
                " projection.)_", 1)
        (proj / "Context.md").write_text(
            "_(Framework label — not part of the file. This is the"
            f" author's context SNAPSHOT, taken {_taken} when the wake"
            " spawned; it is what the author saw. `TREE.md`,"
            " `CATALOG.md`, `BATCHES.md`, `ADJUDICATIONS.md` beside it"
            " are refreshed for this round."
            " Where they disagree about what has landed, later is"
            " closer to the truth and the difference is this"
            " packet's timing, not a defect in the proposal. When a"
            " status decides your verdict, ask the record:"
            " `inspect({\"decl\": \"<slug>\"})` reads it live.)_\n\n"
            + ctx_text, encoding="utf-8")
    # Current rev (hoisted above) + the terminal outcomes since it,
    # welded into one file: the outcomes ARE this rev's execution
    # record, and the judge's first duty is checking the candidate's
    # Argument against them (判官必見源). The outcome lines are the ones
    # `refresh` above rendered — the exact section the strategist
    # context renders, off the same call that wrote BATCHES.md.
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
    (proj / "directive.md").write_text(
        _standing_directive_digest(conn, problem), encoding="utf-8")
    # Landed proofs are NOT staged (user call 2026-08-04): the judge
    # reads the problem's `proofs/` in place via a read-only grant
    # (`extra_read_dirs` on the spawn — see `review`). The prior
    # cited-file staging + cap-20 systematically truncated the evidence
    # late in a big problem (SLC: 43 of 63 reachable files NOT staged
    # at Ingest-adjacent rounds), and every curation rule was itself
    # the defect. proofs/ is landed ground truth, not strategist
    # narrative — reading it in place widens no independence boundary.
    if dialogue:
        (proj / "dialogue.md").write_text(_dialogue_digest(dialogue),
                                          encoding="utf-8")
    return proj


CRITERIA_KEYS = ("1", "2", "3", "4", "5")

#: The criteria whose `clear` must carry its naming (see the check in
#: `parse_verdict`). Held to `Tooling/prompts/adversary/adversary.md` by
#: `tests/test_adversary_criteria_contract.py`: the prompt states the
#: rule, this enforces it, and a judge that obeys a prompt its verifier
#: disagrees with loses the round.
#:
#: A SET, not a number, since v6 (d5916446): the rubric hangs a naming
#: on criterion 1 (each NOW Inject's consumption chain and endpoint)
#: and on criterion 2 (the Relation's argument and the handling of the
#: wall). Each has its own way out, quoted from its own template entry
#: — one shared shape would answer half the refusals with the wrong
#: job.
NAMING_CRITERIA = ("1", "2")


def _prompt_text() -> str:
    """The judge's rubric as it stands right now, or "" if unreadable.

    ONE reader for every consumer of the rubric's own words, so a
    renumber, a rename or a reword reaches all of them at once. Nothing
    in this module spells a criterion's meaning out for itself: the
    numbers and the names have been reassigned before (Value and
    Reachability swapped on 2026-08-13) and are reassigned again
    whenever the owner revises the rubric, so every hard-coded copy is
    a silent mislabel waiting for the next revision."""
    from . import PROMPT_DIR
    try:
        return (PROMPT_DIR / "adversary" / "adversary.md").read_text(
            encoding="utf-8")
    except OSError:
        return ""


def criteria_names() -> "dict[str, str]":
    """`{"1": <name>, ...}` — the rubric's own names for its criteria,
    read from the prompt that states them.

    The console shows a verdict criterion by criterion and a bare "3"
    says nothing; the names must not become a THIRD copy of the rubric.
    A hard-coded list would silently mislabel every verdict it renders
    the first time the rubric is reordered. Read from the prompt, a
    renumbering carries.

    Empty when the prompt cannot be read or its list does not parse —
    the caller falls back to bare numbers, which are what the verdict
    actually stores."""
    out: "dict[str, str]" = {}
    for m in re.finditer(r"^(\d)\.\s+\*\*(.+?)\*\*\s*:", _prompt_text(),
                         re.MULTILINE):
        if m.group(1) in CRITERIA_KEYS:
            out[m.group(1)] = m.group(2).strip()
    return out if len(out) == len(CRITERIA_KEYS) else {}


#: Fallback for `naming_clear_shape` — used only when the prompt or its
#: output template cannot be read. It describes where the shape lives
#: instead of guessing at its words, because a refusal that quotes a
#: shape the rubric no longer asks for is worse than one that quotes
#: none: the judge obeys it and is refused again.
_NAMING_SHAPE_FALLBACK = ("clear: <the naming this criterion's output "
                          "template asks for>")


def naming_clear_shape(criterion: str) -> str:
    """The `clear: …` entry the output template shows for `criterion`,
    quoted from the prompt itself.

    `parse_verdict` refuses a bare `clear` on every naming criterion,
    and that refusal is the judge's only instruction at the moment its
    verdict is thrown away — so the way out has to be the shape the
    CURRENT rubric asks for, on the criterion being refused. Written as
    a literal it kept saying "the entry that closes the MAIN claim" for
    exactly as long as it took someone to reword the criterion, and a
    gate naming an action the prompt no longer describes is the class
    of gate an agent cannot obey."""
    text = _prompt_text()
    if "```json" not in text:
        return _NAMING_SHAPE_FALLBACK
    tmpl = text.split("```json", 1)[1].split("```", 1)[0]
    m = re.search(r'"' + re.escape(criterion)
                  + r'"\s*:\s*\[\s*"(clear:[^"]*)"', tmpl)
    return m.group(1).strip() if m else _NAMING_SHAPE_FALLBACK


def split_criterion(val: Any) -> "tuple[str, list[str]]":
    """One criterion's adjudication as `(state, bullets)` — state is
    `"clear"`, `"fired"` or `""`, and each bullet has its head word and
    separators stripped off.

    A criterion takes a LIST as of 2026-08-28 (owner design: a judge
    that sees three defects under one criterion fires all three this
    round instead of dripping one per round); a bare string is the
    legacy one-bullet form and both are on the record. Reading it is
    the same operation `parse_verdict` performs, so it lives beside it
    — a private copy in the serve layer is the drift that made every
    rebut read as `passed` for a week (44ff4321).

    Tolerant on purpose: this reads what the judge WROTE, including
    verdicts the parser would refuse, because a refused verdict is
    exactly the one a reader needs to look at."""
    vals = [val] if isinstance(val, str) else val
    if not isinstance(vals, list):
        return "", []
    state = ""
    out: "list[str]" = []
    for x in vals:
        if not isinstance(x, str):
            continue
        t = x.strip()
        head = ("clear" if re.match(r"clear\b", t, re.IGNORECASE)
                else "fired" if re.match(r"fired\b", t, re.IGNORECASE)
                else "")
        if head and not state:
            state = head
        out.append(t[len(head):].strip(" -—–:") if head else t)
    return state, [x for x in out if x]


def parse_verdict(text: str) -> tuple[Optional[dict[str, Any]], str]:
    """Validate the per-criterion verdict.json and DERIVE the ruling.

    Each criterion line is `"clear"` or `"fired: <objection>"`; any
    fired line makes the verdict a rebut. Returns a dict carrying the
    synthesized legacy keys (`verdict` / `criticisms` / `reservations`)
    plus the raw `criteria`, or (None, err) on a malformed file."""
    try:
        # strict=False admits raw control characters inside string
        # values — the same class that killed a strategist wake over
        # one literal newline (p324, 2026-08-25; parse_decisions got
        # the same treatment). Structural damage still fails.
        v = json.loads(text, strict=False)
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
        # 2026-08-28 (owner design): a criterion takes a LIST — one
        # bullet per objection — so a judge that sees three defects
        # under one criterion fires all three THIS round instead of
        # dripping one per round (measured: the one-string schema bound
        # in 4,495/4,495 rounds; ~22% of late objections were visible
        # a round earlier). A bare string stays accepted (legacy form,
        # one bullet).
        vals = [val] if isinstance(val, str) else val
        if not (isinstance(vals, list) and vals
                and all(isinstance(x, str) for x in vals)):
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
        s = vals[0].strip()
        # Prefix-keyed, annotation-tolerant (07-29, third occurrence of
        # the same wake-killing parse: opus-tier judges annotate their
        # verdicts — `"clear — I checked the chain end to end…"` — and
        # the literal match threw away two full adversary rounds per
        # hit. The DISCRIMINATOR is the leading word (word-boundary, so
        # "clearly…" stays malformed); suffix prose is tolerated.
        if re.match(r"clear\b", s, re.IGNORECASE):
            # #159 (2026-08-04): the naming criterion's judgment IS the
            # naming. Ten SLC revs cleared it with the bare word,
            # leaving the attention device without an auditable trace,
            # on the one criterion built to catch a main claim orbiting
            # untouched. Mechanical, not honor-system.
            #
            # `NAMING_CRITERIA` is the ENFORCEMENT half of a prompt
            # rule — the prompt says whose reason IS the naming — and
            # the two must move together or a judge that obeys the
            # prompt has its verdict refused (the 2026-08-13 renumber
            # nearly shipped exactly that), or names nothing on a
            # criterion the prompt tells it to name (v6, d5916446,
            # added a second naming criterion).
            # `test_adversary_criteria_contract.py` holds them level.
            #
            # WHAT that naming must say is not spelled out here: it is
            # quoted from the rubric's own output template FOR THIS
            # criterion, so a reworded criterion rewords its own way
            # out and no refusal points at the other one's job.
            rest = s[len("clear"):].strip(" -—–:")
            if k in NAMING_CRITERIA and not rest:
                return None, (
                    f"criterion {k} never takes a bare "
                    f"\"clear\" — its judgment IS the naming: "
                    f"`\"{naming_clear_shape(k)}\"`")
            if not rest:
                # Calibration survey 2026-08-29: 70-94% of clears on
                # criteria 3/4/5 were the bare word, and the survey's
                # rule-position experiment showed reasons appear only
                # where the parser demands them (the requirement moved
                # from c1 to c2 on 08-13 and the reasons moved with
                # it). A bare clear leaves no calibration transcript —
                # every criterion now carries its one sentence of why.
                return None, (
                    f"criterion {k} never takes a bare \"clear\" — say "
                    f"why it holds for THIS proposal: `\"clear: <one "
                    f"concrete reason>\"`")
            continue
        for x in vals:
            xs = x.strip()
            reason = (xs.split(":", 1)[1].strip() if ":" in xs
                      else xs[5:].strip(" -—–:"))
            if not reason:
                return None, (f"criterion {k} is fired but carries no "
                              f"objection — `\"fired: <objection>\"`")
            fired.append(f"[criterion {k}] {reason}")
        continue
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
           proof_warn: Optional[str],
           group_id: "int | None" = None,
           quota_park=None) -> tuple[
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
        dialogue=dialogue, proof_warn=proof_warn, group_id=group_id)
    # The judge reads the landed proofs and the paper shelf IN PLACE
    # (user calls 2026-08-04/05; staging retired — see build_projection).
    # Papers joined 08-05: the old SLC judge accepted a paper-grounded
    # load-bearing claim "on consistency with the prior judge's pointer"
    # because the shelf sat outside its readable roots (rev 5
    # reservation, g368) — and a paper-driven run makes
    # faithfulness-to-the-paper claims load-bearing every rev. Both are
    # ground truth, not strategist narrative; reading them in place
    # widens no independence boundary. The prompt names the concrete
    # directories: substitute the placeholders and hand the spawn the
    # rendered copy (same move as the worker prompts'
    # `__FEEDBACK_PATH__`). The write fence is untouched — the grants
    # are read-only and neither is a write root.
    #
    # The shelf is THIS problem's Project document root now (§3.9), not
    # every paper in the workspace: a judge reading another Project's
    # literature is the independence boundary leaking sideways.
    workspace = attempts_dir.parent.parent
    proofs_dir = (problem_dir / "proofs").resolve()
    from ..state import project_docs as _project_docs
    from ..state import projects as _projects
    _project = _projects.project_of(conn, problem) \
        or problem.split(".", 1)[0]
    papers_dir = _project_docs.root(workspace, _project).resolve()
    prompt_src = PROMPT_DIR / "adversary" / "adversary.md"
    prompt_path = attempts_dir / "_adversary_prompt.md"
    # Appended dynamically, not written into the static prompt: which
    # dossier files exist varies per round ("(if present)" on a fresh
    # problem covered half the list), and 8 judges reported burning a
    # probe round just discovering the package layout (2026-08-22).
    # The builder knows exactly what it wrote — say so.
    present = sorted(p.name for p in proj.iterdir()
                     if p.is_file() and not p.name.startswith("_"))
    # External paths the prompt names get the same courtesy (x62
    # feedback 2026-08-25: judges burned probe rounds discovering
    # whether the workspace side of the layout exists at all).
    _ext_lines = []
    for label, path in (("proofs dir", proofs_dir),
                        ("papers dir", papers_dir)):
        if path.is_dir():
            n_files = sum(1 for _ in path.iterdir())
            _ext_lines.append(f"- {label} `{path.as_posix()}`: "
                              f"exists, {n_files} entries")
        else:
            _ext_lines.append(f"- {label} `{path.as_posix()}`: "
                              f"DOES NOT EXIST — do not probe it")
    for name in ("Root.lean", "Defs.lean"):
        p = problem_dir / name
        _ext_lines.append(
            f"- `{p.as_posix()}`: "
            + ("exists" if p.is_file() else "DOES NOT EXIST"))
    manifest = ("\n\n## This round's dossier — actually present\n"
                + ", ".join(f"`{n}`" for n in present)
                + "\n(a dossier file from the list above that is not "
                  "named here does not exist this round — do not probe "
                  "for it)\n\nWorkspace paths the prompt references:\n"
                + "\n".join(_ext_lines) + "\n")
    prompt_path.write_text(
        prompt_src.read_text(encoding="utf-8")
        .replace(PROOFS_DIR_PLACEHOLDER, proofs_dir.as_posix())
        .replace(PAPERS_DIR_PLACEHOLDER, papers_dir.as_posix())
        + manifest,
        encoding="utf-8")

    # One re-spawn on a missing/malformed verdict (cheap; a judge that
    # produced no usable ruling twice is a wake-level failure), plus a
    # separate budget for INFRA rcs: the caller turns rc != 0 into a
    # wake-level failure, which discards a proposal the Strategist has
    # already finished (SG 07-30: one `adversary rc=1` provider blip
    # threw away 28k output tokens / 6.2 min, and the 07-27 malformed
    # pair cost 27 min — same single-point-of-failure class). A provider
    # hiccup on the judge must cost a re-spawn, not the author's work.
    last_err = ""
    verdict_tries = infra_tries = 0
    # Loogle over MCP, not a shell — the judge checks "Mathlib has X"
    # claims, and that was its only shell use. The config lands INSIDE
    # the projection, so the isolation is unchanged.
    from . import write_tools_mcp_config as _write_tools_cfg
    _tools_cfg = _write_tools_cfg(proj, attempts_dir.parent.parent,
                                  seat="adversary")
    while True:
        sid = str(uuid.uuid4())
        rc = agent.spawn_llm(
            kind="adversary", prompt_path=prompt_path,
            problem_dir=proj, attempts_dir=proj,
            session_id=sid, timeout_sec=timeout_sec,
            # Loogle over MCP, not a shell — the judge checks "Mathlib
            # has X" claims, and that was its only shell use. The config
            # lands INSIDE the projection so the isolation is unchanged.
            mcp_config_path=_tools_cfg,
            # Read-only, in place (claude renders them as Read/Grep
            # allow patterns + --add-dir; agy's reads are already
            # workspace-wide).
            extra_read_dirs=(proofs_dir, papers_dir),
            # The projection dir breaks the standard attempts layout —
            # attribute the judge's cost explicitly or the spawn_usage
            # row is silently dropped (invisible-judge class, 07-18).
            usage_workspace=attempts_dir.parent.parent,
            usage_problem=problem,
            usage_pipeline_id=attempts_dir.name,
        )
        if rc != 0:
            # A confirmed quota window costs a sleep, not the author's
            # work (2026-08-08). The judge is fresh-per-round with no
            # session at stake, so parking here is pure win — and the
            # caller's budget keeps the wake inside its lease TTL.
            if (quota_park is not None
                    and failures.is_infra(_rc_reason(rc))
                    and quota_park(f"judge round {round_no}")):
                continue
            if (failures.is_infra(_rc_reason(rc))
                    and infra_tries < INFRA_SPAWN_RETRIES):
                infra_tries += 1
                print(f"[adversary] r{round_no}: spawn rc={rc} "
                      f"(infra) — retry {infra_tries}/"
                      f"{INFRA_SPAWN_RETRIES} in "
                      f"{INFRA_RETRY_BACKOFF_SEC:.0f}s; the proposal "
                      f"stays alive", flush=True)
                time.sleep(INFRA_RETRY_BACKOFF_SEC)
                continue
            return None, "", rc
        # Verdict problems share ONE bounded budget (the loop is
        # `while True` for the infra branch above, so every no-verdict
        # path must count against it or the wake spins forever).
        vpath = proj / VERDICT_BASENAME
        verdict = None
        if not vpath.exists():
            last_err = "adversary produced no verdict.json"
        else:
            try:
                text = vpath.read_text(encoding="utf-8")
            except OSError as e:
                last_err = f"verdict.json unreadable: {e}"
            else:
                verdict, perr = parse_verdict(text)
                if verdict is None:
                    last_err = perr
                    vpath.unlink(missing_ok=True)
        if verdict is None:
            verdict_tries += 1
            if verdict_tries >= VERDICT_TRIES:
                return None, last_err, 0
            continue
        # Judge provenance (calibration survey P1/P2, 2026-08-29):
        # every seat comparison used to need yaml archaeology plus
        # date-slicing, and prompt edits crossed unmarked breakpoints.
        # This is the CONFIGURED seat — a runtime rescue swap inside
        # the provider layer is not visible here.
        import hashlib
        verdict["_judge"] = {
            "model": str(config.get("adversary.model", default="?")),
            "provider": str(config.get("adversary.provider",
                                       default="?")),
            "effort": str(config.get("adversary.reasoning_effort",
                                     default="")),
            "rubric_sha": hashlib.sha256(
                prompt_path.read_bytes()).hexdigest()[:16],
        }
        # Framework-feedback questionnaire — the judge was the one spawn
        # family without the channel (zero adversary lines ever landed).
        # Resume cwd stays the projection: isolation holds; only the
        # record's label names the real problem.
        from . import _feedback
        _feedback.attempt_feedback(
            kind="adversary", seat="adversary", sid=sid,
            slug=f"r{round_no}",
            outcome=str(verdict.get("verdict", "")),
            problem_dir=proj, attempts_dir=proj,
            workspace=attempts_dir.parent.parent,
            problem_label=problem)
        return verdict, "", 0
