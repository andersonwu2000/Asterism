"""state.programme — the Programme store (research mode).

The Programme is the adversarially-reviewed argument layer between the
charter and the bricks (research_mode_design.md §2). SoT is the
`programme_revisions` table (v30): `passed` rows form the revision
chain (the latest passed row IS the current Programme), `rejected`
rows keep a discarded proposal plus its criticism dialogue for audit.
`PROGRAMME.md` in the problem dir is a read-only render; spawns are
write-denied on it and the only writers are `record_pass` /
`record_rejection` on the strategist commit path.

Proposal body contract (four sections, prose discipline — no schema
beyond the headers): a `# <Title>` line, then `## Argument`,
`## Proof`, `## Roadmap` in that order (2026-07-23, user call: Thesis
renamed Proof — the section IS the root claim's proof, judged as one —
and moved before Roadmap, whose entries cash its gaps).
"""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Optional

from .db import now

PROGRAMME_BASENAME = "PROGRAMME.md"

# Prominent-warning thresholds (design §2 + 07-29 bloat ruling): warn
# loudly, never hard-block. The Proof is the load-bearing mathematics
# and keeps the most headroom (healthy-heavy b6_1: 13 passed revs, max
# Proof 7.2k — never tripped). The observed bloat surfaces are the
# Argument (healthy ≤1.6k pre-endgame; verdict-war drafts 4-7k) and the
# package total (healthy max 21.2k passed; the pathological draft was
# 31.6k). Absolute thresholds by design: attention cost is absolute,
# and ratio triggers misfire on legitimate pivots (b6_1 rev 9→10 was a
# healthy 4.8×).
PROOF_WARN_CHARS = 10_000
ARGUMENT_WARN_CHARS = 3_000
#: The Roadmap may be the largest section (it is the route, the only
#: home for gaps, AND the closure ledger) — so its threshold matches the
#: Proof's, not the Argument's. Chosen against the SLC growth curve
#: (2026-08-04): 4.1K→6.1K→9.6K→11.3K over 13 revs at ~600B/rev, with
#: closed arcs still itemized — 10K fires exactly when distillation is
#: overdue, and before the blunt 25K whole-document warning.
ROADMAP_WARN_CHARS = 10_000
#: Conventions are the EXPENSIVE section: the Roadmap rides only the
#: strategist and judge, but Conventions ride every worker spawn whole.
#: 4K is generous for "short and general"; at SLC rev 19 the section hit
#: 5.9K carrying near-verbatim duplicates of lesson-KB entries (the two
#: learning loops write the same footgun twice — 2026-08-04 audit).
#: Since 2026-08-11 this threshold measures what a worker actually
#: receives: `conventions_for_group` resolves to one group's section, so
#: the number the author is warned about and the number that ships are
#: the same one. Under the old ancestor walk they were not — every group
#: sat under 4K while group 384's chain shipped 7,886 B.
CONVENTIONS_WARN_CHARS = 4_000
DOC_WARN_CHARS = 25_000

_SECTION_ORDER = ("## Argument", "## Proof", "## Roadmap")

#: Optional fourth section (research_mission_design.md §3.1, 2026-08-03):
#: standing conventions for workers — the successor of the retired
#: `EmitDirective` channel. Every prior directive on record carried
#: conventions or process lessons, never mathematics the Programme
#: lacked, and keeping them in a second document is what let a directive
#: contradict the brief it governed (SLC rev 4 → two substitution
#: incidents). One source now: conventions live in the revision the
#: judge already audits, and workers receive exactly this section.
CONVENTIONS_HEADER = "## Conventions"


# ---------------------------------------------------------------------
# Proposal parsing / validation
# ---------------------------------------------------------------------

def parse_proposal(body: str) -> tuple[Optional[dict[str, str]], Optional[str]]:
    """Validate a proposal body against the four-section contract.

    Returns (sections, None) on success — sections maps
    {'title', 'argument', 'proof', 'roadmap'} to their text — or
    (None, teaching_error) on a contract violation.
    """
    if not isinstance(body, str) or not body.strip():
        return None, ("programme proposal is empty; deliver the four "
                      "sections: `# <Title>`, `## Argument`, "
                      "`## Proof`, `## Roadmap`")
    lines = body.splitlines()
    first = next((ln for ln in lines if ln.strip()), "")
    if not (first.startswith("# ") and not first.startswith("## ")):
        return None, ("programme proposal must open with a `# <Title>` "
                      f"line (got {first[:60]!r}); the Title is this "
                      "batch's goal in one line")
    title = first[2:].strip()
    if not title:
        return None, "programme `# <Title>` line is empty"

    positions: dict[str, int] = {}
    known = _SECTION_ORDER + (CONVENTIONS_HEADER,)
    for idx, ln in enumerate(lines):
        stripped = ln.rstrip()
        if stripped in known:
            if stripped in positions:
                return None, (f"duplicate `{stripped}` section; each "
                              "section appears at most once")
            positions[stripped] = idx
    missing = [h for h in _SECTION_ORDER if h not in positions]
    if missing:
        return None, ("programme proposal is missing section(s): "
                      + ", ".join(f"`{h}`" for h in missing))
    idxs = [positions[h] for h in _SECTION_ORDER]
    if idxs != sorted(idxs):
        return None, ("programme sections out of order; required order is "
                      "`## Argument`, `## Proof`, `## Roadmap`")
    # `## Conventions` is OPTIONAL and, when present, comes last: it is
    # standing material (unordered rules workers receive verbatim), not
    # part of the route — after the Roadmap keeps the four argued
    # sections contiguous.
    if CONVENTIONS_HEADER in positions and \
            positions[CONVENTIONS_HEADER] < idxs[-1]:
        return None, ("`## Conventions` must come after `## Roadmap` — "
                      "it is standing worker guidance, not route")

    ordered = sorted(positions.items(), key=lambda kv: kv[1])
    bounds = [i for _, i in ordered] + [len(lines)]
    sections = {"title": title, "conventions": ""}
    names = {"## Argument": "argument", "## Proof": "proof",
             "## Roadmap": "roadmap", CONVENTIONS_HEADER: "conventions"}
    for (header, start), end in zip(ordered, bounds[1:]):
        text = "\n".join(lines[start + 1:end]).strip()
        if not text and header != CONVENTIONS_HEADER:
            return None, f"programme `{header}` section is empty"
        sections[names[header]] = text
    return sections, None


#: The two-part brick (owner ruling 2026-08-30): an Inject's `proof` is
#: `Theorem.` <its full statement> then `Proof.` <its argument> — the
#: shape a mathematician writes. The statement thereby has a position
#: of its own: the mint worker's `## Your assignment`, the judge's
#: per-brick unit, a handle for dedupe and same-gap detection. A
#: definition brick writes `Definition.` and carries no `Proof.`.
BRICK_SHAPE = ("`Theorem.` <its full statement>, then `Proof.` <its argument> "
               "(a definition brick: `Definition.` <what it defines>, no `Proof.`)")
_BRICK_HEAD = re.compile(r"^\s*(?:\*\*)?(Theorem|Definition)\.(?:\*\*)?\s*(.*)$")
_BRICK_PROOF = re.compile(r"^\s*(?:\*\*)?Proof\.(?:\*\*)?\s*(.*)$")


def parse_brick_proof(text: "str | None") -> tuple[str, str, str, str]:
    """Split one brick into (head, statement, argument, error).

    `head` is 'Theorem' or 'Definition'; `error` is '' on the contract
    shape and otherwise a teaching sentence naming the defect and the
    shape. Bold markers (`**Theorem.**`) are accepted."""
    lines = (text or "").splitlines()
    head_i = proof_i = None
    for i, ln in enumerate(lines):
        if head_i is None and _BRICK_HEAD.match(ln):
            head_i = i
            continue
        if proof_i is None and _BRICK_PROOF.match(ln):
            proof_i = i
    if head_i is None:
        return "", "", "", f"no `Theorem.` line — write the brick as {BRICK_SHAPE}"
    if proof_i is not None and proof_i < head_i:
        return "", "", "", f"`Theorem.` must come before `Proof.` — {BRICK_SHAPE}"
    m = _BRICK_HEAD.match(lines[head_i])
    head = m.group(1)
    end = proof_i if proof_i is not None else len(lines)
    statement = "\n".join([m.group(2)] + lines[head_i + 1:end]).strip()
    if head == "Theorem" and proof_i is None:
        return "", "", "", f"no `Proof.` line — write the brick as {BRICK_SHAPE}"
    argument = ""
    if proof_i is not None:
        pm = _BRICK_PROOF.match(lines[proof_i])
        argument = "\n".join([pm.group(1)] + lines[proof_i + 1:]).strip()
    return head, statement, argument, ""


def extract_conventions(body: "str | None") -> str:
    """The `## Conventions` section of a revision body, or ''.

    Works on stored bodies (already contract-validated at record time),
    so a plain header split suffices — the parse_proposal duplicate /
    ordering guards ran before the body was stored."""
    if not body:
        return ""
    lines = str(body).splitlines()
    out: list[str] = []
    inside = False
    for ln in lines:
        stripped = ln.rstrip()
        if stripped == CONVENTIONS_HEADER:
            inside = True
            continue
        if inside and stripped.startswith("## "):
            break
        if inside:
            out.append(ln)
    return "\n".join(out).strip()


def conventions_for_group(conn: sqlite3.Connection, problem: str,
                          group_id: "int | None") -> str:
    """Standing conventions in force for work owned by `group_id`:
    THIS group's own section, and nothing above it.

    The ancestor walk this function used to do was measured on
    2026-08-10 and reversed by the owner. Group 384's chain
    `[379, 381, 383, 384]` came to 7,886 B on every worker spawn, of
    which 3,088 B was graph vocabulary (`SimpleGraph.cycleGraph`,
    properness, semimodularity) shipped to a worker whose brick
    contains no graph — not "relevant but unneeded" but actively
    wrong vocabulary — and 381 / 383 were two SIBLING research lines'
    working notes, not 384's charter. A parent that needs a rule to
    reach a sub-group writes it into that group, which makes "write it
    down" a deliberate act instead of a side effect of depth.

    The one thing the walk did carry honestly — a footgun learned above
    reaching a group opened later — is now `groups.conventions_seed`,
    copied once at `open_group`. It answers here only until this group
    ships its own section: a group with a `## Conventions` of its own
    owns the subject, including the decision to drop what it inherited.

    This reverses `discussion_group_design.md` §6's ruling that
    conventions/footguns are rightly shared across groups. See the note
    there; the reversal is deliberate, not drift."""
    if group_id is None:
        row = current_rev(conn, problem, None)
        return extract_conventions(row["body"]) if row is not None else ""
    row = current_rev(conn, problem, int(group_id))
    own = extract_conventions(row["body"]) if row is not None else ""
    if own:
        return own
    try:
        seed = conn.execute(
            "SELECT conventions_seed FROM groups WHERE id = ?",
            (int(group_id),)).fetchone()
    except sqlite3.OperationalError:      # pre-v39 schema
        return ""
    return str((seed["conventions_seed"] if seed else "") or "").strip()


def length_warning(sections: dict[str, str],
                   body: "str | None" = None) -> Optional[str]:
    """Prominent over-length warnings (never a block); one line per
    tripped surface, joined. Shown to the judge (projection) and, on a
    rebuttal, echoed to the strategist with a shrink instruction."""
    warns = []
    n = len(sections.get("proof", ""))
    if n > PROOF_WARN_CHARS:
        warns.append(
            f"⚠ PROOF LENGTH WARNING: {n} chars (threshold "
            f"{PROOF_WARN_CHARS}). The Proof must stay readable — an "
            "unreadable Proof is itself rebuttable. Condense: "
            "superseded branches belong in Roadmap closure entries, "
            "not the Proof.")
    a = len(sections.get("argument", ""))
    if a > ARGUMENT_WARN_CHARS:
        warns.append(
            f"⚠ ARGUMENT LENGTH WARNING: {a} chars (threshold "
            f"{ARGUMENT_WARN_CHARS}). The Argument says why THIS batch "
            "— one screen. Cut narrative; mathematics belongs in the "
            "Proof, the route in the Roadmap.")
    r = len(sections.get("roadmap", ""))
    if r > ROADMAP_WARN_CHARS:
        warns.append(
            f"⚠ ROADMAP LENGTH WARNING: {r} chars (threshold "
            f"{ROADMAP_WARN_CHARS}). Distill the settled: a closed line "
            "collapses to its conclusion, a dead instantiation to one "
            "closure line with its restart condition. Entries carried "
            "verbatim across revisions are the mass to cut.")
    cv = len(sections.get("conventions", ""))
    if cv > CONVENTIONS_WARN_CHARS:
        warns.append(
            f"⚠ CONVENTIONS LENGTH WARNING: {cv} chars (threshold "
            f"{CONVENTIONS_WARN_CHARS}). Conventions ride EVERY worker "
            "spawn — a fact the lesson KB or CATALOG already carries is "
            "double billing; keep only what is universal and nowhere "
            "else.")
    d = len(body) if body is not None else sum(
        len(v) for v in sections.values())
    if d > DOC_WARN_CHARS:
        warns.append(
            f"⚠ PROPOSAL LENGTH WARNING: {d} chars total (threshold "
            f"{DOC_WARN_CHARS}). Distill the settled — a closed line "
            "collapses to its conclusion.")
    return "\n".join(warns) if warns else None


#: Same token test the formalizer's gate uses (`rpc.py`
#: `_NATIVE_DECIDE_RE`) — one definition of "this text is about
#: `native_decide`" across both sides, word-bounded so a longer
#: identifier that merely contains the token does not trip it.
_NATIVE_DECIDE_RE = re.compile(r"\bnative_decide\b|Lean\.ofReduceBool")

#: 2026-09-04 requirement change. The 08-25 warning was a length
#: warning that fired on the bare substring and then asserted "the
#: batch as planned cannot land" — over-claiming twice over: a closure
#: note recording that the route died, or a Conventions line
#: PROHIBITING it, mentions the token without planning anything, and
#: the mention is in NL prose that no formalization need follow. What
#: is certain is conditional: IF a brick's formalization uses it, the
#: commit axiom gate rejects that brick, after minutes of native
#: compilation. So the notice states the condition and leaves the
#: judgement of whether it applies where it belongs.
_NATIVE_DECIDE_NOTICE = (
    "⚠ NATIVE_DECIDE NOTICE: this proposal mentions `native_decide`. "
    "If a planned brick's formalization must use it, the commit axiom "
    "gate rejects that brick unconditionally (`Lean.ofReduceBool` is "
    "not on the axiom whitelist) — and the native compilation runs "
    "for minutes before any gate speaks. A closure note or a "
    "prohibition changes nothing; a step that relies on it must be "
    "re-planned as kernel `decide` on an instance small enough to "
    "reduce, a written-out finite case split, or a structural proof.")


def native_decide_warning(body: str) -> Optional[str]:
    """The qualified `native_decide` notice, or None.

    Its own surface, not a length warning: the two are joined for the
    judge's projection but only the length one may carry "the revision
    must come back smaller" (a bloated proposal shrinks; a proposal
    that mentions an axiom does not)."""
    if not _NATIVE_DECIDE_RE.search(body or ""):
        return None
    return _NATIVE_DECIDE_NOTICE


def native_decide_confirm(body: str, asked: bool) -> Optional[str]:
    """The wake's soft confirm gate, pure: the text to bounce back to
    the author, or None if there is nothing to ask.

    Same shape as the formalizer's gate (`rpc.py::_native_decide_gate`,
    a77a32c3): show the bill before the purchase, once, and let the
    identical resend be the confirmation. `asked` is the once-per-wake
    latch — an author who resends unchanged has confirmed, and the
    judge reads the proposal on that round."""
    if asked or not _NATIVE_DECIDE_RE.search(body or ""):
        return None
    return (
        _NATIVE_DECIDE_NOTICE + "\n"
        "Resubmit proposal.md — revised, or unchanged if the mention "
        "is deliberate — to confirm; this gate asks once per wake, "
        "then the judge reads it.")


# ---------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------

def current_rev(conn: sqlite3.Connection, problem: str,
                group_id: "int | None" = None) -> Optional[sqlite3.Row]:
    """The latest passed revision row, or None before bootstrap.

    v35 — every discussion group owns its own revision chain, numbered
    from 1 (the partial unique index is keyed `(group_id, rev)`). Omit
    `group_id` only where the question really is problem-wide; a wake
    always knows which group it is."""
    if group_id is None:
        return conn.execute(
            "SELECT * FROM programme_revisions"
            " WHERE problem = ? AND status = 'passed'"
            " ORDER BY rev DESC LIMIT 1", (problem,)).fetchone()
    return conn.execute(
        "SELECT * FROM programme_revisions"
        " WHERE problem = ? AND group_id = ? AND status = 'passed'"
        " ORDER BY rev DESC LIMIT 1", (problem, int(group_id))).fetchone()


def next_rev_number(conn: sqlite3.Connection, problem: str,
                    group_id: "int | None" = None) -> int:
    row = current_rev(conn, problem, group_id)
    return (row["rev"] + 1) if row else 1


#: Nearest authorising ancestor, self first. The goal tree has no
#: parent column — an edge is `strategies.goal_id → strategy_subgoals
#: → subgoal_id` — so walking up is a recursive join over the link
#: table (`idx_ssg_subgoal` covers the step). Only MINTED edges conduct
#: (v44): a strategy that CITES a pre-existing sibling did not author
#: it, so its batch's revision must not stamp the cited subtree (same
#: leak as the brief walk in `agent/context.py`, 2026-08-25).
_AUTHORISING_REV_SQL = """
WITH RECURSIVE up(gid, depth) AS (
  VALUES(?, 0)
  UNION
  SELECT s.goal_id, up.depth + 1
    FROM strategy_subgoals ss
    JOIN strategies s ON s.id = ss.strategy_id
    JOIN up ON ss.subgoal_id = up.gid
   WHERE ss.link_kind = 'minted'
)
SELECT pr.* FROM up
  JOIN strategist_decisions d
    ON CAST(d.produced_goal_id AS INTEGER) = up.gid
  JOIN programme_revisions pr
    ON pr.batch_id = d.batch_id AND pr.problem = ?
 WHERE pr.status = 'passed'
 ORDER BY up.depth ASC, d.id DESC
 LIMIT 1
"""


def rev_for_goal(conn: sqlite3.Connection, problem: str, *,
                 goal_id: "int | None" = None,
                 decision_id: "int | None" = None,
                 group_id: "int | None" = None
                 ) -> Optional[sqlite3.Row]:
    """The revision whose `## Proof` AUTHORISED this piece of work.

    A worker must be shown the argument its goal was dispatched under,
    not whatever the Programme has become since. The two diverge
    routinely: a sibling branch triggers `pending_strategist_review`,
    the Strategist ships a new rev, and meanwhile this branch's
    sub-goals keep being auto-dispatched by the dispatcher without any
    Strategist wake. Reading the CURRENT rev then produces either a
    spurious `return_to_nl` decline (the step is gone) or —
    worse, because nothing reports it — a silent re-anchoring onto a
    DIFFERENT step that happens to look apt.

    It also restores the batch-closure law (#118) over time. That law
    certifies "every claim this batch dispatches is fully argued in
    THIS batch's Proof", which the Adversary checks once, at dispatch.
    The tree it authorises outlives the check, so a mutable
    problem-scoped Proof silently voids the guarantee for every node
    already in flight. Pinning makes the certified pairing durable.

    Consequence worth stating: retracting a step no longer stops the
    work riding on it. That is correct — killing work is
    `ConfirmShelve`'s job, an explicit decision the Adversary sees, not
    a side effect of editing a document.

    Resolution, most specific first:
      1. `decision_id` — the batch that dispatched THIS spawn;
      2. the nearest ancestor (self included) with a producing decision
         — covers sub-goals the worker created, which have no decision
         of their own but inherit their parent's authorisation;
      3. `current_rev` — nothing above has one (fresh problem, or work
         that predates the Programme). v35: of the OWNING group, derived
         from the goal when not passed in, so the fallback cannot serve
         a sibling group's argument.
    """
    if decision_id is not None:
        row = conn.execute(
            "SELECT pr.* FROM strategist_decisions d"
            " JOIN programme_revisions pr"
            "   ON pr.batch_id = d.batch_id AND pr.problem = ?"
            " WHERE d.id = ? AND pr.status = 'passed'",
            (problem, decision_id)).fetchone()
        if row is not None:
            return row
    if goal_id is not None:
        row = conn.execute(_AUTHORISING_REV_SQL,
                           (int(goal_id), problem)).fetchone()
        if row is not None:
            return row
    if group_id is None and goal_id is not None:
        from . import groups as _groups
        owner = _groups.group_for_goal(conn, problem, int(goal_id))
        if owner is not None:
            group_id = int(owner["id"])
    if group_id is None and decision_id is not None:
        # A decision whose batch has no passed rev yet (path 1 missed)
        # still names its group — without this, a mint dispatched by a
        # sub-group's very first batch falls through to the problem-wide
        # max rev, i.e. a SIBLING group's argument (#164 class).
        d = conn.execute(
            "SELECT group_id FROM strategist_decisions WHERE id = ?",
            (decision_id,)).fetchone()
        if d is not None and d["group_id"] is not None:
            group_id = int(d["group_id"])
    return current_rev(conn, problem, group_id)


def record_pass(conn: sqlite3.Connection, problem: str, body: str,
                verdict: dict[str, Any],
                dialogue: list[dict[str, Any]],
                rounds: int, batch_id: Optional[str],
                group_id: "int | None" = None) -> int:
    """Advance the revision chain. Returns the new rev number."""
    rev = next_rev_number(conn, problem, group_id)
    j = _judge_cols(verdict)
    conn.execute(
        "INSERT INTO programme_revisions"
        " (problem, rev, body, status, verdict, dialogue, rounds,"
        "  batch_id, created_at, group_id,"
        "  judge_model, judge_provider, judge_effort, rubric_sha)"
        " VALUES (?,?,?,'passed',?,?,?,?,?,?,?,?,?,?)",
        (problem, rev, body, json.dumps(verdict, ensure_ascii=False),
         json.dumps(dialogue, ensure_ascii=False), rounds, batch_id,
         now(), group_id, *j))
    return rev


def _judge_cols(verdict: "dict[str, Any] | None") -> tuple:
    """(judge_model, judge_provider, judge_effort, rubric_sha) from the
    verdict's `_judge` stamp (adversary.review, survey P1/P2) — NULLs
    when the verdict predates the stamp or never existed."""
    m = (verdict or {}).get("_judge") or {}
    return (m.get("model"), m.get("provider"), m.get("effort"),
            m.get("rubric_sha"))


def record_rejection(conn: sqlite3.Connection, problem: str, body: str,
                     dialogue: list[dict[str, Any]],
                     rounds: int,
                     discard_reason: Optional[str] = None,
                     group_id: "int | None" = None,
                     discard_channel: Optional[str] = None,
                     verdict: "dict[str, Any] | None" = None,
                     last_words: Optional[str] = None) -> int:
    """Keep a discarded proposal + full criticism for audit. Returns
    the new row id.

    `last_words` (2026-08-30): the author's own three-section note
    written after the discard (`strategist/last_words.py`) — facts,
    dead routes, the one lead — shown to the successor beside the
    judge's rebuttal, never to the judge.

    `discard_reason` (v34) names WHICH channel dropped it — adversary
    refutation, verify rounds exhausted, revision spawn failure. Every
    discard path records a row: the next wake's plan note may assert a
    dispatch that never happened, and the reason is what stops it
    re-deriving blind (07-29 SG feedback ×2).

    `discard_channel` (v37) is that same fact as a MACHINE-readable
    value — the registry `failure_reason` verbatim. `discard_reason` is
    prose and must never be pattern-matched; the channel is what
    decides whether the successor wake is shown the draft (see
    `rejection_notice`)."""
    j = _judge_cols(verdict)
    conn.execute(
        "INSERT INTO programme_revisions"
        " (problem, rev, body, status, verdict, dialogue, rounds,"
        "  batch_id, created_at, discard_reason, group_id,"
        "  discard_channel,"
        "  judge_model, judge_provider, judge_effort, rubric_sha,"
        "  last_words)"
        # Survey P3 (2026-08-29): rejected rows used to hard-code
        # verdict=NULL — 89 final verdicts destroyed. The wrongful-kill
        # audit reads exactly this column.
        " VALUES (?,?,?,'rejected',?,?,?,NULL,?,?,?,?,?,?,?,?,?)",
        (problem, next_rev_number(conn, problem, group_id), body,
         json.dumps(verdict, ensure_ascii=False)
         if verdict is not None else None,
         json.dumps(dialogue, ensure_ascii=False), rounds, now(),
         discard_reason, group_id, discard_channel, *j, last_words))
    return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])


def rejection_notice(conn: sqlite3.Connection, problem: str,
                     group_id: "int | None" = None) -> Optional[str]:
    """One-line record for the next wake after a discard (design §3:
    the fresh session gets the fact, never the failed draft)."""
    if group_id is None:
        row = conn.execute(
            "SELECT * FROM programme_revisions WHERE problem = ?"
            " ORDER BY id DESC LIMIT 1", (problem,)).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM programme_revisions WHERE problem = ?"
            "   AND group_id = ? ORDER BY id DESC LIMIT 1",
            (problem, int(group_id))).fetchone()
    if row is None or row["status"] != "rejected":
        return None
    keys = row.keys()
    why = (row["discard_reason"] if "discard_reason" in keys else None)
    # NULL on pre-v34 rows: those only ever came from the Adversary.
    cause = why or "adversary rebuttal"
    head = (f"Programme rev {row['rev']} did not commit — {cause} after "
            f"{row['rounds']} round(s) ({row['created_at'][:10]}). "
            f"Batch not dispatched")
    channel = (row["discard_channel"] if "discard_channel" in keys
               else None)
    if channel not in _INFRA_DISCARD_CHANNELS:
        # Adversarial exhaustion (and every legacy row): the draft is
        # withheld ON PURPOSE — design §1/§3 wants the next session to
        # re-derive with fresh eyes rather than defend a refuted body.
        return head + "; draft not shown."
    # Infra death: NOBODY refuted this argument, so the anti-anchoring
    # rationale does not apply and withholding the draft just burns the
    # rounds again (2026-08-07: an 8-round debate re-derived from one
    # line because a subscription window expired mid-revision). The
    # body and the criticisms are already in this row; hand them over.
    return head + (
        f" because the machine failed, not the argument — the draft "
        f"below was never refuted. Continue from it: fold in any "
        f"criticism it already answers, and re-argue only what the "
        f"judge actually challenged.\n\n"
        f"### Uncommitted draft (rev {row['rev']})\n\n"
        f"{row['body']}\n\n"
        f"{_dialogue_transcript(row['dialogue'])}")


#: Channels whose discard is a MACHINE failure — the successor sees the
#: draft. Anything else (adversary rebuttal, package verify) keeps the
#: ratified blindness. Registry `failure_reason` values, not prose.
_INFRA_DISCARD_CHANNELS = frozenset({
    "spawn_fast_fail", "quota_exhausted", "missing_dep",
    "gateway_unreachable", "transient_timeout", "provider_misconfigured",
    "daemon_shutdown", "system_killed", "agent_timeout", "agent_no_output",
    # A spawn that died of a cause nobody can name refuted nothing
    # either — same reasoning, and the invariant test below enforces
    # that every provider-infra reason lands on this side.
    "unclassified_spawn_failure",
    # 08-18: a dead network refuted nothing either — the daemon parks
    # behind a connectivity probe (`core/network_wait`).
    "provider_network",
    # 08-25: an overloaded machine (handshake starved by a CPU spike)
    # refuted nothing either.
    "local_overload",
    # 08-12: the gateway answered its own 5xx mid-verify (a slot that
    # went away). A lost slot is not a counter-argument, and
    # `framework_verify_error` joins it for the same reason even though
    # its origin is 'framework' rather than provider-infra: asking verify
    # the wrong question says nothing about the mathematics.
    "verify_infra", "framework_verify_error",
})


def rejection_cycle(conn: sqlite3.Connection, problem: str,
                    group_id: "int | None" = None) -> "list[sqlite3.Row]":
    """The discarded cycle the successor wake inherits: every `rejected`
    rev since the last row that was not one, oldest first. Empty when
    the latest row is not a rejection (a pass closes the cycle). Same
    row selection as `rejection_notice` — problem-wide when `group_id`
    is None, else this group's chain."""
    if group_id is None:
        rows = conn.execute(
            "SELECT * FROM programme_revisions WHERE problem = ?"
            " ORDER BY id DESC", (problem,)).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM programme_revisions WHERE problem = ?"
            "   AND group_id = ? ORDER BY id DESC",
            (problem, int(group_id))).fetchall()
    cycle: list = []
    for r in rows:
        if r["status"] != "rejected":
            break
        cycle.append(r)
    cycle.reverse()
    return cycle


def last_rebuttal(row: sqlite3.Row) -> "tuple[Optional[int], list[str]]":
    """(round, criticisms) of the judge's LAST rebuttal in a rejected
    rev's dialogue — the round that killed it. (None, []) when the
    dialogue carries no adversary criticisms."""
    try:
        rounds = json.loads(row["dialogue"] or "[]")
    except (ValueError, TypeError):
        return None, []
    found: "tuple[Optional[int], list[str]]" = (None, [])
    for t in rounds if isinstance(rounds, list) else []:
        if not isinstance(t, dict) or t.get("role") != "adversary":
            continue
        crits = [str(c) for c in (t.get("criticisms") or [])]
        if crits:
            found = (t.get("round"), crits)
    return found


def rejection_history_md(cycle: "list[sqlite3.Row]") -> str:
    """The companion the successor lazy-loads: every rejected rev of the
    cycle, every round's criticisms, and NOT ONE draft (design §3 — the
    rebuttal is the judge's text and invites no re-skin; the draft is
    the author's and does)."""
    parts = ["# Rejected proposals — the judge's rebuttals (no drafts)", ""]
    any_round = False
    for row in cycle:
        why = row["discard_reason"] or "adversary rebuttal"
        parts += [f"## rev {row['rev']} — {why} after {row['rounds']} "
                  f"round(s), {str(row['created_at'])[:10]}", ""]
        transcript = _dialogue_transcript(row["dialogue"])
        if transcript:
            any_round = True
            parts += [transcript, ""]
        else:
            parts += ["(no adversary criticisms recorded)", ""]
        lw = last_words_of(row)
        if lw:
            parts += ["**The author's last words (its own record, unverified)**",
                      "", lw.rstrip("\n"), ""]
    return "\n".join(parts) if any_round else ""


def last_words_of(row: sqlite3.Row) -> Optional[str]:
    """The note on a rejected rev, or None (pre-2026-08-30 rows, or a
    cycle whose author wrote nothing)."""
    try:
        v = row["last_words"]
    except (IndexError, KeyError):
        return None
    return str(v) if v else None


def _dialogue_transcript(dialogue_json: Optional[str]) -> str:
    """The judge's criticisms from the discarded rounds, oldest first.

    Only the criticisms: each round's stored `proposal` is a snapshot
    the draft above supersedes, and repeating N bodies would bury the
    one that matters."""
    if not dialogue_json:
        return ""
    try:
        rounds = json.loads(dialogue_json)
    except (ValueError, TypeError):
        return ""
    out: list[str] = []
    for t in rounds if isinstance(rounds, list) else []:
        if not isinstance(t, dict) or t.get("role") != "adversary":
            continue
        crits = t.get("criticisms") or []
        if not crits:
            continue
        out.append(f"**Round {t.get('round', '?')} criticisms**")
        out += [f"- {c}" for c in crits]
        out.append("")
    if not out:
        return ""
    return "### Criticisms already raised\n\n" + "\n".join(out)


# ---------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------

def _verdict_summary(verdict_json: Optional[str]) -> str:
    if not verdict_json:
        return "(no verdict record)"
    try:
        v = json.loads(verdict_json)
    except (TypeError, ValueError):
        return "(unparseable verdict record)"
    reservations = v.get("reservations") or []
    if not reservations:
        return "passed with no reservations"
    lines = ["passed with reservations:"]
    lines += [f"  - {r}" for r in reservations]
    return "\n".join(lines)


def group_dir(problem_dir: Path, group_id: "int | None",
              top_id: "int | None") -> Path:
    """Where a group's rendered artefacts live.

    The TOP group keeps the problem dir itself, so `PROGRAMME.md` stays
    exactly where every existing reader (the human, the UI, the judge's
    projection) already looks. Sub-groups get `.groups/<id>/` — visible,
    greppable, and out of the way."""
    if group_id is None or (top_id is not None
                            and int(group_id) == int(top_id)):
        return problem_dir
    return problem_dir / ".groups" / str(int(group_id))


def render(conn: sqlite3.Connection, problem: str,
           problem_dir: Path,
           group_id: "int | None" = None) -> Optional[Path]:
    """Write PROGRAMME.md (read-only render of the current rev).

    Header = rev N + last verdict summary; full history stays in the
    DB (design §2: no revision log in the render). Returns the path,
    or None before bootstrap (no passed rev → no file)."""
    row = current_rev(conn, problem, group_id)
    if row is None:
        return None
    from . import groups as _groups
    top = _groups.top_group(conn, problem)
    out_dir = group_dir(problem_dir, group_id,
                        int(top["id"]) if top is not None else None)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / PROGRAMME_BASENAME
    header = (
        "<!-- rendered by state.programme — DO NOT EDIT; SoT is the\n"
        "     programme_revisions table. Writes go through the passed\n"
        "     proposal commit only. -->\n"
        f"<!-- rev {row['rev']} · {row['created_at'][:19]} · "
        f"rounds {row['rounds']} -->\n"
        f"<!-- adversary: {_verdict_summary(row['verdict'])} -->\n\n")
    path.write_text(header + row["body"] + "\n", encoding="utf-8")
    return path
