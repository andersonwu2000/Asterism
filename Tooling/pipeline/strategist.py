"""Phase 2 — Strategist pipeline (Step 6 scaffolding).

Strategist emits a single meta-level decision per invocation:
  Inject / ConfirmShelve / Reopen / EmitDirective
  / RequestUserAmend / Noop

This module covers decision validation + commit; the agent stage
(actually spawning the LLM, writing `decision.json` to attempts_dir)
is the next-session piece. The framework-side logic — schema check,
Reopen ancestor safety walk, atomic side effects, strategist_decisions
audit row, last_strategist_at touch — is implemented in full.

Stage order (docs/archive/design/phase2/pipelines.md §2.4):
  1. trigger_context  (pure)   compile input per trigger_kind
  2. failure_replay   (pure)   last 5 strategist_decisions
  3. agent            (agent)  spawn LLM, get decision.json  ← TODO
  4. self_verify      (pure)   schema + Reopen ancestor walk
  5. commit           (pure)   execute decision + audit row

Public surface:
  - DECISION_KINDS              — frozenset of valid `decision_kind`
  - parse_decision(json_text)    -> Decision | (None, error_msg)
  - verify_decision(decision, conn, problem) -> ok | error_msg
  - commit_decision(decision, conn, *, problem, tick, trigger_kind,
                    workspace, attempts_dir) -> Outcome
  - run_strategist(...)         — outer entry (stub awaiting agent stage)
"""
from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..state import db, transitions
from ..core import dispatcher as _dispatcher


# Decision kinds Strategist may emit (subset of the DB CHECK enum —
# the schema still accepts 'Reopen' for legacy rows from before
# 2026-05-28, but the parser/verifier/commit handler no longer
# recognise it; Inject(Backward|Builder) is the unified reactivation
# mechanism).
DECISION_KINDS: frozenset[str] = frozenset({
    "Inject", "ConfirmShelve", "EmitDirective",
    "RequestUserAmend", "Noop", "MarkDeliverable", "Ingest",
    "FetchPaper", "AttemptDisproof",
})


def _as_bool(v: Any) -> bool:
    """Coerce a config value (yaml bool or string) to bool."""
    return v if isinstance(v, bool) else \
        str(v).strip().lower() in ("1", "true", "yes", "on")

# Trigger kinds (mirrors strategist_decisions.trigger_kind CHECK enum).
TRIGGER_KINDS: frozenset[str] = frozenset({
    # Retired at runtime — the DB CHECK keeps the values for old rows:
    # "first_launch" (Phase 6: fresh problem = initial stall →
    # inject_batch_done wake); "audit" (2026-07-25: the v26 epistemic
    # auditor's belief sweep is now phase 1 of the routine wake).
    "pending_review", "routine",
    "inject_batch_done",
})

# Research mode (research_mode_design.md §1) — the proposal-package
# gate keys on decision SHAPE: a batch wholly within the exempt kinds
# moves no route (literature intake / hand-back / no-op). Any other
# batch must carry a Programme proposal (four sections in
# `proposal.md`) and pass the Adversary.
_PACKAGE_EXEMPT_KINDS: frozenset[str] = frozenset(
    {"FetchPaper", "RequestUserAmend", "Noop"})
_ENDGAME_KINDS: frozenset[str] = frozenset({"MarkDeliverable", "Ingest"})
_EXPERIMENT_KINDS: frozenset[str] = frozenset({"Inject", "AttemptDisproof"})
PROPOSAL_BASENAME = "proposal.md"


def package_gate_applies(decisions, trigger_kind: str | None) -> bool:
    return any(d.kind not in _PACKAGE_EXEMPT_KINDS for d in decisions)


def verify_proposal_package(decisions, attempts_dir) -> tuple[
        "str | None", "dict[str, str] | None", "str | None"]:
    """Package-side checks for a gated batch: proposal file present,
    four-section contract, and the ≥1-experiment rule (endgame batches
    exempt). Returns (body, sections, err)."""
    from ..state import programme
    path = attempts_dir / PROPOSAL_BASENAME
    if not path.exists():
        return None, None, (
            "this batch moves the route, so it must carry a Programme "
            f"proposal: Write `{PROPOSAL_BASENAME}` (bare filename, in "
            "your attempts dir) with the four sections `# <Title>`, "
            "`## Argument`, `## Proof`, `## Roadmap`. Then re-emit "
            "decision.json (unchanged if it was already right).")
    try:
        body = path.read_text(encoding="utf-8")
    except OSError as e:
        return None, None, f"{PROPOSAL_BASENAME} unreadable: {e}"
    sections, err = programme.parse_proposal(body)
    if err:
        return None, None, err
    kinds = {d.kind for d in decisions}
    if not (kinds & _ENDGAME_KINDS) and not (kinds & _EXPERIMENT_KINDS):
        return None, None, (
            "a proposal must carry at least one experiment (Inject or "
            "AttemptDisproof) — thinking runs inside the wake; the "
            "commit is how the argument touches the machine. (Endgame "
            "batches carrying MarkDeliverable/Ingest are exempt.)")
    # P2 — every Inject brief names its Roadmap entry (parse-level
    # existence check; experiments trace to the argument they test).
    roadmap_lc = sections["roadmap"].lower()
    for d in decisions:
        if d.kind != "Inject":
            continue
        tag = ""
        for line in str(getattr(d, "brief", "") or "").splitlines():
            if line.strip().lower().startswith("roadmap:"):
                tag = line.split(":", 1)[1].strip()
                break
        if not tag:
            return None, None, (
                "every Inject brief must name its Roadmap entry with a "
                "`Roadmap: <entry phrase>` line (copy the entry's "
                "leading phrase from `## Roadmap`).")
        if tag.lower() not in roadmap_lc:
            return None, None, (
                f"an Inject brief cites `Roadmap: {tag}` but no "
                "`## Roadmap` line contains that phrase — copy the "
                "entry text verbatim, or add the entry.")
    return body, sections, None


def _format_rebuttal(verdict: dict, round_no: int,
                     rounds_left: int) -> str:
    crits = "\n".join(f"- {c}" for c in verdict.get("criticisms", []))
    return (
        f"ADVERSARY REBUTTAL (round {round_no}; {rounds_left} revision "
        "round(s) left before this proposal is discarded and the next "
        "wake restarts fresh):\n" + crits + "\n"
        "For EACH point: either revise (rewrite proposal.md — and "
        "decision.json if the experiments change) or defend (keep your "
        "position and answer the point inside `## Argument`). Do not "
        "concede points you believe are misreadings. Re-emit "
        "decision.json in every case.")


# Files allowed in RequestUserAmend(file=...).
# Root.lean joined 2026-07-08 (feature D live livelock): a FALSE root
# claim is amendable — before this, the hand-back verb could not
# point at the file that was wrong and the Strategist looped on
# schema_invalid forever.
USER_AMEND_FILES: frozenset[str] = frozenset(
    {"Defs.lean", "Manifest.md", "Root.lean"})

# ---------------------------------------------------------------------
# Decision dataclass
# ---------------------------------------------------------------------

@dataclass
class Decision:
    """Parsed Strategist decision. Mirrors `docs/archive/design/phase2/pipelines.md`
    §2.3 schema. `brief` and `reason` are mutually-orthogonal (per
    decision kind) text fields; `payload` holds structured params
    (pipeline name / file / lean_body / question / scope / body /
    directive) keyed by decision kind."""
    kind: str
    target_id: int | None = None
    brief: str | None = None
    reason: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------

def resolve_directive_body_files(decisions: "list[Decision]",
                                 attempts_dir: Path) -> str:
    """File-form hand-off for the two multi-KB text fields: EmitDirective
    `body_file` → payload['body'], and Inject `brief_file` → `brief`
    (2026-07-19; agent_feedback ×3 in the a5 run — briefs are multi-KB
    Lean-and-markdown blobs the sandbox forces agents to hand-escape
    into JSON, one stray backslash from silent corruption). Each ref is
    a bare filename inside the strategist's attempts dir. The framework
    ingests the content HERE, right after parse: downstream (verify,
    commit, worker Context rendering) sees plain text — the file is a
    hand-off vehicle, never a live reference. The file wins over an
    inline value when both are present. Returns a verify-style error
    string ('' = ok)."""
    def _read(ref: object, field: str) -> "tuple[str | None, str]":
        name = Path(str(ref)).name        # basename only — no traversal
        try:
            text = (attempts_dir / name).read_text(encoding="utf-8")
        except OSError as e:
            return None, (f"{field} {ref!r} unreadable ({e}). Write the "
                          f"text to a file in your attempts dir first, "
                          f"then reference its bare filename.")
        if not text.strip():
            return None, f"{field} {ref!r} is empty"
        return text.strip(), ""

    for d in decisions:
        if d.kind == "EmitDirective" and d.payload.get("body_file"):
            text, err = _read(d.payload["body_file"],
                              "EmitDirective.body_file")
            if err:
                return err
            d.payload["body"] = text
        elif d.kind == "Inject" and d.payload.get("brief_file"):
            text, err = _read(d.payload["brief_file"], "Inject.brief_file")
            if err:
                return err
            d.brief = text
    return ""


def parse_decisions(json_text: str) -> tuple[list[Decision] | None, str]:
    """Parse the agent's `decision.json` content into a list of decisions.

    Multi-decision schema: top-level is a JSON array of one or more
    decision objects. Single-decision back-compat: a top-level dict is
    accepted and wrapped as `[dict]` so agents that still emit one
    object work unchanged. Returns (decisions, '') on success or
    (None, error_message) on any malformed item.
    """
    try:
        obj = json.loads(json_text)
    except (json.JSONDecodeError, TypeError) as e:
        return None, f"not valid JSON: {e}"
    if isinstance(obj, dict):
        items = [obj]
    elif isinstance(obj, list):
        if not obj:
            return None, "decision array is empty; emit at least one decision"
        items = obj
    else:
        return None, (
            "decision.json must be a JSON object or array of objects "
            f"(got {type(obj).__name__})"
        )
    out: list[Decision] = []
    for i, raw in enumerate(items):
        if not isinstance(raw, dict):
            return None, (
                f"decision #{i} must be a JSON object (got "
                f"{type(raw).__name__})"
            )
        d, err = _parse_one(raw)
        if d is None:
            return None, (f"decision #{i}: {err}" if len(items) > 1 else err)
        out.append(d)
    return out, ""


def parse_decision(json_text: str) -> tuple[Decision | None, str]:
    """Single-decision wrapper around `parse_decisions`. Returns the
    sole Decision when the payload contains exactly one; errors when
    it parses cleanly but contains multiple. Existing call sites that
    only handle one decision at a time go through here; the agent
    runner (`run_strategist`) calls `parse_decisions` directly.
    """
    decisions, err = parse_decisions(json_text)
    if decisions is None:
        return None, err
    if len(decisions) != 1:
        return None, (
            f"expected a single decision; got {len(decisions)}. Use "
            f"parse_decisions for multi-decision batches."
        )
    return decisions[0], ""


def _parse_one(obj: dict[str, Any]) -> tuple[Decision | None, str]:
    """Parse a single decision-object into a `Decision`. Shared by both
    the single-decision and multi-decision parsers.

    Accepts both the canonical shape (`kind` + flat fields) and a
    forgiving variant where structured params can live either at top
    level or inside a `payload` sub-dict.
    """
    kind = obj.get("kind")
    if not isinstance(kind, str) or kind not in DECISION_KINDS:
        return None, (
            f"missing or unknown 'kind' ({kind!r}); expected one of "
            f"{sorted(DECISION_KINDS)}"
        )
    # target_id accepts int (goal_id) or str (slug). Slug → int lookup
    # happens in verify_decision (it has `problem` context). Integer
    # strings (e.g. "2019") are coerced here so callers don't need to
    # special-case them.
    target_id = obj.get("target_goal_id") or obj.get("target_id")
    if target_id is not None and not isinstance(target_id, int):
        if isinstance(target_id, str):
            try:
                target_id = int(target_id)
            except ValueError:
                pass  # leave as str; verify_decision will lookup by slug
        else:
            return None, (f"target_id must be int, slug string, or null "
                          f"(got {type(target_id).__name__})")
    brief = obj.get("brief")
    reason = obj.get("reason")
    # Pull all structured params (anything not already consumed) into
    # payload. Lets agent send either nested-payload or flat shape.
    payload_inner = obj.get("payload")
    if isinstance(payload_inner, dict):
        payload = dict(payload_inner)
    else:
        payload = {}
    for k, v in obj.items():
        if k in ("kind", "target_goal_id", "target_id",
                 "brief", "reason", "payload"):
            continue
        payload[k] = v
    return Decision(kind=kind, target_id=target_id, brief=brief,
                    reason=reason, payload=payload), ""


# ---------------------------------------------------------------------
# Schema validation (self_verify stage)
# ---------------------------------------------------------------------

def verify_decision(decision: Decision, conn: sqlite3.Connection,
                    *, problem: str,
                    workspace: "Path | None" = None) -> str:
    """Validate decision shape + cross-row constraints. Returns '' if
    OK, an error message string otherwise.

    Checks:
      - Required fields per decision kind
      - target_id exists in goals (when set)
      - Inject.pipeline is currently restricted to 'Forward'
      - Reopen ancestor safety walk (no `disproved` ancestor)
      - RequestUserAmend file ∈ {Defs.lean, Manifest.md}
      - RequestUserAmend dedup: no other awaiting_human row for this problem

    Side effect: when `decision.target_id` is a slug string (e.g. agent
    emitted `target_goal_id="main"`), looks up the corresponding goal_id
    by (problem, slug) and rewrites `decision.target_id` to the int.
    Unknown slug → error. Keeps the agent-facing schema forgiving
    without leaking string IDs into commit_decision's int-typed paths.
    """
    k = decision.kind

    # Slug → int normalization for kinds that carry target_id.
    if isinstance(decision.target_id, str):
        row = conn.execute(
            "SELECT id FROM goals WHERE problem = ? AND slug = ?",
            (problem, decision.target_id),
        ).fetchone()
        if row is None:
            return (f"target_id={decision.target_id!r} (slug) not found "
                    f"in problem {problem!r}; use the integer goal id "
                    f"shown in Context.md's active goal list")
        decision.target_id = int(row["id"])

    if k == "Inject":
        pipeline = decision.payload.get("pipeline")
        if pipeline not in ("Forward", "Backward", "Builder"):
            return (f"Inject.pipeline must be one of "
                    f"'Forward'/'Backward'/'Builder' (got {pipeline!r})")
        # Phase 6 unified — one Inject = one decision = one pipeline
        # dispatch. `brief` is the agent-facing text payload across all
        # three variants:
        #   - Forward: lemma description (what to produce on a new goal)
        #   - Backward / Builder: directive (how to redispatch on an
        #     existing goal — "try this angle"). Used for the change-
        #     direction workflow on pending_review.
        # Multi-Inject in one Strategist call lands later via the
        # multi-decision schema, where each Inject is its own decision.
        if not isinstance(decision.brief, str) or not decision.brief.strip():
            return f"Inject({pipeline}) requires non-empty `brief` (string)"
        if decision.payload.get("briefs") or decision.payload.get("directive"):
            return (f"Inject schema uses top-level `brief: str`; "
                    f"`briefs` / `directive` payload fields are legacy "
                    f"— remove them and put your text in `brief`")
        if pipeline == "Forward":
            if decision.target_id is not None:
                return ("Inject(Forward) targets the problem (no goal yet "
                        "produced); `target_goal_id` must be null. Use "
                        "Inject(Backward, target_goal_id=...) for "
                        "redispatch on an existing goal.")
            return ""
        # Backward / Builder
        target = decision.target_id
        if target is None:
            return (f"Inject({pipeline}) requires `target_goal_id` "
                    f"(integer id or slug shown in Context.md's "
                    f"active goal list)")
        g = db.get_goal(conn, int(target))
        if g is None:
            return f"target_goal_id={target} not found"
        if str(g["problem"]) != problem:
            return (f"target goal belongs to problem "
                    f"{g['problem']!r}, not {problem!r}")
        if str(g["status"]) in ("proved", "disproved", "dead"):
            return (f"target_goal_id={target} is {g['status']!r}; "
                    f"Inject({pipeline}) cannot redispatch a terminal "
                    f"goal. proved/disproved/dead are hard terminals; "
                    f"open a different angle on a different goal instead.")
        # Ancestor safety walk (was Reopen's responsibility pre-2026-05-28;
        # now Inject(Backward|Builder) takes over as the unified
        # reactivation mechanism). disproved ancestor = counterexample
        # already shown for a parent statement; descendant is moot. dead
        # ancestor is also a hard terminal (parent strategy was wrong);
        # commit's auto-detach handles `shelved` chains but not these.
        bad, anc_kind = _dispatcher._has_hard_terminal_ancestor(
            conn, int(target))
        if bad:
            if anc_kind == "disproved":
                return (
                    f"Inject({pipeline}) rejected: goal {target} has a "
                    f"'disproved' ancestor (counterexample already shown). "
                    f"Use ConfirmShelve."
                )
            return (
                f"Inject({pipeline}) rejected: goal {target} has a "
                f"'dead' ancestor (parent strategy was wrong; this "
                f"descendant exists only in that abandoned context). "
                f"Inject(Backward, target=<parent-goal>) to try a "
                f"different decomposition instead."
            )
        return ""

    if k == "Noop":
        if not decision.reason or not str(decision.reason).strip():
            return "Noop requires non-empty reason"
        return ""

    if k == "EmitDirective":
        scope = decision.payload.get("scope")
        body = decision.payload.get("body")
        if not isinstance(scope, str) or not scope.startswith("problem:"):
            return f"EmitDirective.scope must be 'problem:<name>' (got {scope!r})"
        if not isinstance(body, str) or not body.strip():
            return "EmitDirective requires non-empty body"
        return ""

    if k == "ConfirmShelve":
        if decision.target_id is None:
            return "ConfirmShelve requires target_goal_id"
        g = db.get_goal(conn, decision.target_id)
        if g is None:
            return f"target_goal_id={decision.target_id} not found"
        if str(g["problem"]) != problem:
            return (f"target goal belongs to problem {g['problem']!r}, "
                    f"not this Strategist's {problem!r}")
        if not decision.reason or not str(decision.reason).strip():
            return "ConfirmShelve requires non-empty reason"
        return ""

    if k == "MarkDeliverable":
        if decision.target_id is None:
            return "MarkDeliverable requires target_goal_id"
        g = db.get_goal(conn, decision.target_id)
        if g is None:
            return f"target_goal_id={decision.target_id} not found"
        if str(g["problem"]) != problem:
            return (f"target goal belongs to problem {g['problem']!r}, "
                    f"not this Strategist's {problem!r}")
        # Only framework-GENERATED nodes are deliverables the human must
        # vouch for; a hand-written root/Defs is already author-vouched.
        if str(g["origin"]) != "forward":
            return (f"MarkDeliverable target must be a Forward-produced node "
                    f"(origin='forward'); goal {decision.target_id} is "
                    f"origin={g['origin']!r}")
        # FSM §3.2 (2026-07-12): marking is a real edge only for a PROVED,
        # not-yet-marked node — an unproved mark is a promise the review
        # cannot vouch, and a re-mark is a no-op that must not read as
        # progress.
        if str(g["status"]) != "proved":
            return (f"MarkDeliverable target g{decision.target_id} is "
                    f"{g['status']!r} — only a PROVED node can be marked")
        if int(g["is_deliverable"] or 0):
            return (f"goal g{decision.target_id} is already marked — "
                    f"re-marking changes nothing (a rollback clears the "
                    f"mark; re-marking after that is legal)")
        return ""

    if k == "FetchPaper":
        # Paper pipeline v2 (D11): request a cited paper. Payload needs
        # a resolvable description; the Scholar pipeline does the fuzzy
        # work. Cap checked here so a capped problem fails the DECISION
        # (visible to the agent immediately) instead of burning a spawn.
        query = str(decision.payload.get("query") or "").strip()
        if not query:
            return ("FetchPaper requires payload.query — the citation "
                    "as printed (authors, title fragment, year) or an "
                    "arXiv id/DOI")
        if not decision.reason or not str(decision.reason).strip():
            return "FetchPaper requires non-empty reason (why needed)"
        from ..papers.fetch import MAX_SCHOLAR_FETCHES_PER_PROBLEM
        n = db.scholar_fetch_count(conn, problem)
        if n >= MAX_SCHOLAR_FETCHES_PER_PROBLEM:
            return (f"FetchPaper blocked: per-problem scholar fetch cap "
                    f"reached ({n}/{MAX_SCHOLAR_FETCHES_PER_PROBLEM})")
        return ""

    if k == "AttemptDisproof":
        # Feature D: the Strategist suspects a user-requested claim is
        # FALSE. The framework mints ¬P MECHANICALLY (never an LLM
        # restatement — a re-stated negation could be a strawman).
        # Prop-only: negating a data-def is meaningless. Scope = any
        # theorem-kind goal (deliverable claims + hand-written root).
        if decision.target_id is None:
            return "AttemptDisproof requires target_goal_id"
        g = db.get_goal(conn, decision.target_id)
        if g is None:
            return f"target_goal_id={decision.target_id} not found"
        if str(g["problem"]) != problem:
            return (f"target goal belongs to problem {g['problem']!r}, "
                    f"not this Strategist's {problem!r}")
        if str(g["kind"]) != "theorem":
            return (f"AttemptDisproof target must be a claim "
                    f"(kind='theorem'); goal {decision.target_id} is "
                    f"kind={g['kind']!r} — negating data is meaningless")
        if str(g["status"]) == "proved":
            return (f"AttemptDisproof target g{decision.target_id} is "
                    f"already proved — a disproof attempt now would be "
                    f"hunting a contradiction; if you distrust the "
                    f"proof, tell the human instead")
        if not decision.reason or not str(decision.reason).strip():
            return ("AttemptDisproof requires non-empty reason (the "
                    "structural falsity evidence — counterexample "
                    "sketch / failing special case)")
        prior = conn.execute(
            "SELECT id FROM strategist_decisions WHERE decision_kind ="
            " 'AttemptDisproof' AND target_id = ? AND outcome IS NULL",
            (int(decision.target_id),)).fetchone()
        if prior is not None:
            return (f"AttemptDisproof already in flight for goal "
                    f"{decision.target_id} (decision {prior['id']})")
        return ""

    if k == "Ingest":
        # Phase 6 — Ingest is the ONLY terminal (Done fused into it).
        # HARD gate: a present root is a user-pinned must-prove-exactly-
        # this requirement, machine-checkable; the framework rejects the
        # terminal judgment outright while it is unproved. (Manifest's
        # other requirements are SOFT — NL, only the Strategist can judge
        # them — so they are prompt-governed, not gated here.)
        root = conn.execute(
            "SELECT status FROM goals WHERE problem = ? AND"
            " origin = 'root' LIMIT 1", (problem,)).fetchone()
        root_proved = root is not None and str(root["status"]) == "proved"
        if root is not None and not root_proved:
            return ("Ingest is blocked: this problem has a root goal "
                    f"(status={root['status']!r}) that must be proved "
                    "before the terminal judgment is valid")
        # A proved root counts toward the >=1-deliverable requirement:
        # a pure-root problem (no Forward deliverables, e.g. a classic
        # single-theorem Manifest) must still be able to exit.
        if not db.deliverables(conn, problem=problem) and not root_proved:
            return ("Ingest requires at least one marked deliverable "
                    "(MarkDeliverable) or a proved root goal")
        # Feature D — a PROVED negation of a still-pursued target blocks
        # the terminal judgment: the user asked for P and the kernel
        # says ¬P; the honest exit is RequestUserAmend (hand the
        # disproof back), not Ingest. Released once the target is
        # retired (shelved/dead/disproved — the user amended, or the
        # negation was adopted as the deliverable). Both-proved is a
        # CONSISTENCY ALARM: an axiom leak or framework bug upstream.
        settled = conn.execute(
            "SELECT d.id AS did, d.target_id AS t, gp.status AS ts,"
            " gn.slug AS ns"
            " FROM strategist_decisions d"
            " JOIN goals gn ON gn.id = d.produced_goal_id"
            " JOIN goals gp ON gp.id = d.target_id"
            " WHERE d.problem = ? AND d.decision_kind = 'AttemptDisproof'"
            " AND gn.status = 'proved'", (problem,)).fetchall()
        for row in settled:
            if str(row["ts"]) == "proved":
                print(f"[strategist] CONSISTENCY ALARM: goal "
                      f"g{row['t']} and its negation {row['ns']} are "
                      f"BOTH proved — axiom leak or framework bug; "
                      f"tell the operator immediately", flush=True)
                return (f"Ingest blocked: g{row['t']} and its negation "
                        f"are both proved — consistency alarm, human "
                        f"must investigate")
            if str(row["ts"]) in ("open", "attempting", "frozen",
                                  "pending_strategist_review"):
                return (f"Ingest blocked: negation of g{row['t']} is "
                        f"proved ({row['ns']}) while the target is "
                        f"still pursued — RequestUserAmend to hand the "
                        f"disproof back, or retire the target")
            # 返回用戶 enforcement (decision-pure, user call 2026-07-08):
            # a kernel-settled disproof requires one user round-trip
            # AFTER it — a RequestUserAmend resolved later than this
            # AttemptDisproof decision (ordered by decision id; no
            # Manifest text guessing).
            amended = conn.execute(
                "SELECT 1 FROM strategist_decisions WHERE problem = ?"
                " AND decision_kind = 'RequestUserAmend'"
                " AND outcome IN ('accepted', 'consumed')"
                " AND id > ? LIMIT 1",
                (problem, int(row["did"]))).fetchone()
            if amended is None:
                return (f"Ingest blocked: the disproof of g{row['t']} "
                        f"({row['ns']}) has not been handed back — "
                        f"RequestUserAmend first; Ingest after the "
                        f"user responds")
        return ""

    if k == "RequestUserAmend":
        if decision.payload.get("problem") and \
                decision.payload["problem"] != problem:
            return (f"RequestUserAmend.problem mismatch: payload says "
                    f"{decision.payload['problem']!r}, expected {problem!r}")
        file = decision.payload.get("file")
        if file not in USER_AMEND_FILES:
            return (f"RequestUserAmend.file must be one of "
                    f"{sorted(USER_AMEND_FILES)} (got {file!r})")
        proposed_body = decision.payload.get("proposed_body")
        if not isinstance(proposed_body, str) or not proposed_body.strip():
            return "RequestUserAmend requires non-empty proposed_body"
        question = decision.payload.get("question")
        if not isinstance(question, str) or not question.strip():
            return "RequestUserAmend requires non-empty question"
        # Phase 2 §2.5 — one awaiting_human row per problem at a time
        if db.problem_has_awaiting_human(conn, problem):
            return (
                f"RequestUserAmend rejected: problem {problem!r} already "
                f"has an outstanding awaiting_human strategist_decisions "
                f"row; resolve it before issuing another."
            )
        # FSM §3.3 (2026-07-12, human-attention guard): a request byte-
        # identical to one the user already adjudicated re-asks the same
        # question — mechanical reject; a changed proposal is a new ask.
        prior = conn.execute(
            "SELECT payload FROM strategist_decisions"
            " WHERE problem = ? AND decision_kind = 'RequestUserAmend'"
            "   AND outcome IS NOT NULL AND outcome != 'awaiting_human'",
            (problem,)).fetchall()
        for r in prior:
            try:
                prev_body = json.loads(r["payload"] or "{}").get(
                    "proposed_body")
            except ValueError:
                continue
            if prev_body == proposed_body:
                return (
                    "RequestUserAmend rejected: this proposed_body is "
                    "byte-identical to a request the user already "
                    "adjudicated — re-asking the same question costs "
                    "human attention and changes nothing. Amend the "
                    "proposal or keep working the problem."
                )
        return ""

    return f"verify_decision: unhandled kind {k!r}"


def verify_decisions(decisions: list[Decision], conn: sqlite3.Connection,
                     *, problem: str,
                     workspace: "Path | None" = None,
                     trigger_kind: str = "") -> str:
    """Validate a multi-decision batch. Runs `verify_decision` on each
    item in declared order, then applies cross-decision invariants that
    only matter when multiple decisions land in the same call.

    Cross-decision rules:
      - At most one `RequestUserAmend` per batch (the per-item check
        already forbids a second awaiting_human row, but two amends in
        the SAME batch both see an empty awaiting_human row at verify
        time and would both pass; this explicit check catches it).
      - No `(ConfirmShelve(G), Reopen(G))` pair on the same target
        within one batch — contradictory intent, almost certainly an
        agent error. Order independent: either ordering is rejected.

    Returns '' if all pass, an error message otherwise (first failure
    short-circuits). Caller must abort the commit when this returns
    non-empty — `commit_decisions` assumes verify passed.
    """
    for i, d in enumerate(decisions):
        err = verify_decision(d, conn, problem=problem,
                              workspace=workspace)
        if err:
            return (f"decision #{i}: {err}" if len(decisions) > 1 else err)

    # Cross-decision: no ConfirmShelve(G) + Inject(Backward/Builder,
    # target=G) pair. The Inject force-reopens G (shelved /
    # pending_strategist_review / frozen → open in
    # `_commit_inject_redispatch`) and queues a retry; the
    # ConfirmShelve then flips G back to shelved. End state: G is
    # shelved but a Backward/Builder dispatch sits in the queue
    # targeting it. BFS would then try to dispatch a worker on a
    # shelved goal — undefined behaviour.
    confirm_targets: set[int] = {
        int(d.target_id) for d in decisions
        if d.kind == "ConfirmShelve" and d.target_id is not None
    }
    inject_bb_targets: set[int] = {
        int(d.target_id) for d in decisions
        if d.kind == "Inject"
        and d.payload.get("pipeline") in ("Backward", "Builder")
        and d.target_id is not None
    }
    overlap_bb = confirm_targets & inject_bb_targets
    if overlap_bb:
        gid = next(iter(overlap_bb))
        return (
            f"batch contains both ConfirmShelve and Inject(Backward/"
            f"Builder) for goal {gid} — the Inject force-reopens the "
            f"target, the ConfirmShelve then shelves it; the queued "
            f"retry would dispatch on a shelved goal. Drop the "
            f"ConfirmShelve (the redispatch already keeps the goal "
            f"alive) or aim the Inject at a different goal."
        )

    # Cross-decision: ConfirmShelve(ancestor) + Inject(Backward/Builder,
    # target=descendant) is also rejected. ConfirmShelve flips the
    # ancestor to 'shelved' and dispatcher._set_goal_terminal_and_
    # propagate cascades that shelve down through strategy_subgoals to
    # every still-active descendant (dispatcher._cascade_shelve_
    # descendants). The cascade fires AFTER the Inject's auto-reopen
    # within the same batch, silently overriding it. The queued
    # Backward/Builder then dispatches on a goal whose status got flipped
    # back to shelved underneath it and moots immediately — observed BT
    # 2026-05-29 batch [Inject(g3298 sphere_paradoxical), ConfirmShelve(
    # g3296 main)]: Inject reopened g3298 at .475, ConfirmShelve cascade
    # re-shelved it at .486, Builder dispatched at .494 and the
    # goal_still_active check on entry returned False (status='shelved')
    # → moot, Strategist's rescue attempt dropped on the floor.
    if confirm_targets and inject_bb_targets:
        for ij_target in inject_bb_targets:
            if ij_target in confirm_targets:
                continue  # already caught above
            ancestors: set[int] = set()
            frontier = [ij_target]
            visited: set[int] = set()
            while frontier:
                next_frontier: list[int] = []
                for gid in frontier:
                    if gid in visited:
                        continue
                    visited.add(gid)
                    for r in conn.execute(
                        "SELECT s.goal_id FROM strategies s"
                        " JOIN strategy_subgoals ss ON ss.strategy_id = s.id"
                        " WHERE ss.subgoal_id = ?",
                        (gid,),
                    ).fetchall():
                        pid = int(r["goal_id"])
                        if pid not in ancestors:
                            ancestors.add(pid)
                            next_frontier.append(pid)
                frontier = next_frontier
            bad = ancestors & confirm_targets
            if bad:
                anc_id = next(iter(bad))
                return (
                    f"batch contains ConfirmShelve(goal {anc_id}) and "
                    f"Inject(Backward/Builder, target_goal_id={ij_target})"
                    f" where target is a descendant of the ConfirmShelve"
                    f" target through strategy_subgoals. ConfirmShelve"
                    f" cascades shelve to all descendants (dispatcher._"
                    f"cascade_shelve_descendants), which fires AFTER the"
                    f" Inject's auto-reopen and silently overrides it —"
                    f" the queued Backward/Builder dispatches on a now-"
                    f"shelved goal and moots immediately. Pick one"
                    f" intent: drop the ConfirmShelve and Inject(target="
                    f"{anc_id}, brief=\"…retry with the new tools at"
                    f" hand…\") to re-attack the whole subtree with the"
                    f" sub-rescue brief; OR keep the ConfirmShelve and"
                    f" drop this Inject (the descendant is acknowledged"
                    f" as cascade-dead)."
                )

    # Cross-decision: ConfirmShelve must be paired with at least one
    # ACTION decision in the same batch — Inject. EmitDirective is notes
    # only (not action); RequestUserAmend is the user-escalation channel
    # reserved for Defs.lean / Manifest.md errors. Forces Strategist to
    # keep trying — articulating defeat without dispatching a fresh
    # attempt or redirecting focus is the lazy pattern this rule catches.
    #
    # SCOPE (2026-07-06, ConfirmShelve 終態): the pairing obligation
    # applies to FIRST-TIME shelves only (target not already 'shelved').
    # A ConfirmShelve re-confirming an already-shelved goal is the
    # "still dead" verdict — forcing an Inject onto it mints a fresh
    # reopen-promise (the shared batch_id), so the confirmation itself
    # re-armed the loop it was answering (feedback ×2: a superseded goal
    # re-fired after every batch, forever). A standalone re-confirm acks
    # the old promise and carries none (no Inject sibling = no promise),
    # permanently silencing the goal. Forcing is NOT weakened where it
    # matters: the root-blocked gate below still rejects ANY no-Inject
    # batch when nothing live is in flight, and an explicit
    # Inject(target=...) / G1 dedupe revival can always bring the goal
    # back.
    def _is_first_shelve(d) -> bool:
        g = db.get_goal(conn, d.target_id) if d.target_id is not None \
            else None
        return g is None or str(g["status"]) != "shelved"

    if any(d.kind == "ConfirmShelve" and _is_first_shelve(d)
           for d in decisions):
        action = sum(1 for d in decisions if d.kind == "Inject")
        if action == 0:
            return (
                "ConfirmShelve must be paired with at least one Inject "
                "decision in the same batch. EmitDirective alone (notes) "
                "and RequestUserAmend alone (user escalation) do not "
                "count — they don't dispatch a fresh attempt or redirect "
                "focus. Pair with one of:\n"
                "  - Inject(Forward, brief=...) to build the missing "
                "tool the shelved goal needed.\n"
                "  - Inject(Backward/Builder, target_goal_id=..., "
                "brief=...) to redispatch another goal (typically the "
                "parent of the shelved subgoal — its strategy will "
                "otherwise stay 'proposed' with an unfeasible subgoal), "
                "or to refocus on another goal worth attacking with a "
                "fresh hint.\n"
                "EmitDirective is fine as an EXTRA decision in the "
                "same batch to record learning, but it cannot be the "
                "sole sibling. If you genuinely have no fresh action "
                "to dispatch, the problem is upstream-blocked — "
                "escalate via RequestUserAmend in a separate Strategist "
                "call (which pauses dispatch via the awaiting_human "
                "gate)."
            )

    # Cross-decision: review-discharge (2026-07-11, b6 wake-pump). While
    # ANY goal sits in `pending_strategist_review`, the batch must contain
    # at least one decision TARGETING one of them (ConfirmShelve / Reopen /
    # Inject / AttemptDisproof on that goal) — pending_review means "the
    # framework cannot progress without your verdict on THIS goal", and
    # `reconcile_stuck_states` re-wakes every tick until the set empties.
    # A batch that leaves every reviewed goal untouched (the EmitDirective-
    # only pattern) discharges nothing: the wake loop just paid an LLM
    # spawn for a note (301 spawns / 2.05M output tokens, b6 2026-07-10).
    # EmitDirective stays legal as an EXTRA sibling — what is rejected is
    # the notes-only batch, not the note. Exempt: Ingest (terminal exit —
    # queued Strategists are dropped after it) and RequestUserAmend (the
    # awaiting_human gate pauses the wake pump itself).
    # Scope (2026-07-12, periodic wakes outrank events): a routine
    # wake may now legally fire WHILE goals await review — discharging
    # them is the frontier wakes' job (the pending_review pressure keeps
    # re-arming until the set empties), not the periodic survey's.
    # Forcing the discharge here would bounce every periodic wake on a
    # busy tree (the parse-fail pump shape, e1ecc5c).
    pending_review_ids: set[int] = set()
    if trigger_kind != "routine":
        pending_review_ids = {
            int(r["id"]) for r in conn.execute(
                "SELECT id FROM goals WHERE problem = ?"
                "  AND status = 'pending_strategist_review'",
                (problem,),
            )
        }
    if pending_review_ids:
        exempt = any(d.kind in ("Ingest", "RequestUserAmend")
                     for d in decisions)
        addressed = any(
            d.target_id is not None and int(d.target_id) in pending_review_ids
            for d in decisions)
        if not exempt and not addressed:
            ids = ", ".join(f"g{i}" for i in sorted(pending_review_ids))
            return (
                f"review not discharged: goal(s) {ids} are in "
                f"pending_strategist_review — they wait on YOUR verdict, "
                f"and the framework re-wakes you every tick until you "
                f"give one. This batch targets none of them, so it "
                f"resolves nothing. Include at least one decision "
                f"targeting a reviewed goal:\n"
                f"  - ConfirmShelve(target_goal_id=...) — park it, "
                f"paired with an Inject per the shelve rule (build the "
                f"missing tool, or redirect focus elsewhere; a parked "
                f"goal stays revivable), OR\n"
                f"  - Inject(Backward/Builder, target_goal_id=...) — "
                f"keep it alive and re-attack it with a fresh brief "
                f"(force-reopens the goal), OR\n"
                f"  - AttemptDisproof(target_goal_id=...) — if you now "
                f"suspect the statement is false.\n"
                f"EmitDirective may accompany these, but cannot be the "
                f"whole batch."
            )

    # Cross-decision: stall-advance (problem FSM design §3.1,
    # 2026-07-12 — the pure-NL re-confirm pump). Forced advance is THE
    # design philosophy; its old mechanical anchor was the root status,
    # so a rootless (pure-NL) problem had no enforcement and the gate
    # counted decision KINDS, not state deltas — a zero-delta batch
    # (re-confirm shelve / Noop / re-mark) passed as action. New
    # currency: `predicted_batch_delta` (transitions §2.3) — a stalled
    # wake with nothing live in flight must move ≥1 state or dispatch
    # ≥1 new piece of work, root or no root.
    if trigger_kind == "inject_batch_done":
        try:
            _stalled = db.is_problem_stalled(conn, problem)
        except Exception:  # noqa: BLE001 — predicate must not break verify
            _stalled = False
        if _stalled and not db.has_live_inflight_inject(conn, problem):
            from ..state import transitions as _transitions
            if _transitions.predicted_batch_delta(conn, decisions) < 1:
                return (
                    "framework stalled and this batch changes nothing "
                    "(re-confirmed shelves, re-marks, Noop — all no-ops).\n"
                    "You are the researcher here, and this wall is yours "
                    "to break. Think deeply, be inventive, and explore "
                    "genuinely different possibilities — the breakthrough "
                    "comes from work only you can do: study the dead "
                    "attempts and name the assumption they share (that is "
                    "the dimension to vary); build the missing vocabulary "
                    "as Forward bricks; question your own DO-NOTs (a "
                    "verdict covers only the instantiation it cites); "
                    "test a false-looking statement; pick the experiment "
                    "whose outcome most changes your Thesis.\n"
                    "Commit the work as: `Inject` (a genuinely new angle) "
                    "/ `ConfirmShelve` (a live goal) paired with an "
                    "`Inject` / `AttemptDisproof` / `MarkDeliverable` (a "
                    "PROVED forward node) then `Ingest`. "
                    "`RequestUserAmend` ONLY if a user file is factually "
                    "WRONG — difficulty or a missing API is work, not "
                    "wrongness. EmitDirective / Noop may accompany, "
                    "never alone."
                )

    # Cross-decision: if the root is in a state only Strategist can
    # unfreeze (`shelved` / `frozen` / `pending_strategist_review`),
    # AND this batch dispatches no fresh work (no Inject),
    # AND no LIVE Inject is still in flight from a prior Strategist call
    # — the daemon will idle-exit after this commit. BFS cannot dispatch
    # the root's subtree (`db.open_goals`'s alive seed is
    # `root ∪ detached ∪ alive-strategy descendants`; a non-actively-
    # dispatchable root contributes no seed). Reject.
    #
    # `pending_strategist_review` is included because that state means
    # "agent declined `shelve`, Strategist must decide" — the framework
    # cannot make progress without a Strategist verdict. A Noop on a
    # pending_review root is a logical contradiction (Strategist invoked
    # specifically to break the impasse, declines to act).
    #
    # `disproved` / `dead` roots intentionally NOT covered: those are
    # genuine dead ends (counterexample / wrong parent context) where
    # Strategist legitimately cannot recover; Noop is the right
    # acknowledgement.
    root_row = conn.execute(
        "SELECT id, status FROM goals"
        " WHERE problem = ? AND origin = 'root'",
        (problem,),
    ).fetchone()
    BLOCKED_STATES = ("shelved", "frozen", "pending_strategist_review")
    if root_row is not None and str(root_row["status"]) in BLOCKED_STATES:
        has_action = any(d.kind == "Inject" for d in decisions)
        if not has_action:
            # A NULL-outcome Inject counts as in-flight ONLY if it is LIVE
            # — its produced goal is NOT parked. A `shelved`-produced inject
            # stays NULL forever (shelved no longer settles — see
            # db.propagate_inject_outcome_from_goal), so the old blanket
            # "any NULL-outcome batch row" test wrongly read it as in-flight
            # and ALLOWED a Noop here, while T4 (db.is_problem_stalled) read
            # the same problem as stalled and re-fired the Strategist → Noop
            # → re-fire LIVELOCK (the P13 4284 spin). `has_live_inflight_
            # inject` excludes shelved-produced injects so the two agree: no
            # live inject ⇒ reject Noop ⇒ force a real action. It is BROADER
            # than the stall predicate's active-check on purpose (a Forward
            # inject whose worker has not yet registered its lemma is LIVE
            # here — we have no `running`-set visibility — so the Strategist
            # may Noop and wait instead of injecting overlapping work).
            has_live_inflight = db.has_live_inflight_inject(conn, problem)
            if not has_live_inflight:
                rstat = str(root_row["status"])
                rid = int(root_row["id"])
                hint_for_pending = (
                    " Pending-review state means the last Backward agent "
                    "declined `shelve` on the root — you were invoked "
                    "specifically to break the impasse. Noop here is a "
                    "logical contradiction." if rstat == "pending_strategist_review"
                    else ""
                )
                return (
                    f"Root (goal_id={rid}) is {rstat!r} and nothing in "
                    f"the framework will progress without your action: "
                    f"no live in-flight Inject (any prior inject's brick is "
                    f"parked/shelved, not producing), no Inject "
                    f"in this batch. BFS cannot dispatch from a "
                    f"{rstat!r} root, so a Noop/EmitDirective-only batch "
                    f"leaves the daemon idle.{hint_for_pending}\n"
                    f"In most cases the right call is "
                    f"`Inject(Backward, target_goal_id={rid}, brief=...)` "
                    f"— re-engage BFS on the root subtree with whatever "
                    f"toolkit is now available. Alternatives:\n"
                    f"  - Inject(Forward, brief=...) to build a missing "
                    f"tool (root stays {rstat!r}; inject_batch_done "
                    f"will re-fire you), OR\n"
                    f"  - Inject(Backward/Builder, target_goal_id=..., "
                    f"brief=...) to redispatch a non-root goal, OR\n"
                    f"  - RequestUserAmend(...) to escalate Defs.lean / "
                    f"Manifest.md."
                )
    return ""


# ---------------------------------------------------------------------
# Commit (side-effect stage)
# ---------------------------------------------------------------------

@dataclass
class CommitOutcome:
    """What commit_decision did — for the caller (run_strategist) to
    record into the pipeline's PipelineResult and dead_attempt rows.

    `decision_row_id`: id of the FIRST inserted strategist_decisions
      row in the batch (for callers that need a single canonical id).
      Full row id list in `batch_decision_row_ids`.
    `enqueued_forward`: True iff the commit emitted >= 1 Inject(Forward)
      queue entry.
    `batch_id`: always non-None when the committed decision was Inject
      (every Inject — including N=1 — is a batch under the unified
      Phase 2.5 schema); None for non-Inject decision kinds.
    `batch_decision_row_ids`: row ids in `briefs` list order (length N
      for Inject; empty for non-Inject kinds).
    `final_outcome`: 'committed' (decision applied) / 'awaiting_human'
      (RequestUserAmend wrote .proposed_<file> + INSERT row, dispatcher
      blocks problem until operator resolves) / 'noop'.
    """
    decision_row_id: int
    enqueued_forward: bool = False
    final_outcome: str = "committed"
    batch_id: str | None = None
    batch_decision_row_ids: list[int] = field(default_factory=list)


def _commit_inject_batch(decision: Decision, conn: sqlite3.Connection,
                         *, problem: str, tick: int,
                         trigger_kind: str,
                         inject_batch_id: str | None = None,
                         step_index: int = 0,
                         batch_size: int = 1) -> CommitOutcome:
    """Commit one Strategist Inject decision. Dispatches to the
    pipeline-specific helper.

    Batch semantics (unified across pipeline kinds): every Inject row
    carries a `batch_id`. The framework fires Strategist with
    `inject_batch_done` once every decision in the batch has reached
    a terminal outcome.

      - Forward outcome fills when the produced lemma reaches a
        terminal goal status (proved / shelved / disproved / dead).
      - Backward outcome fills when the produced strategy reaches
        a terminal status (succeeded / dead / superseded).
      - Builder outcome fills when the target goal reaches terminal
        (Builder writes the proof directly into the goal's stub).

    Multi-decision callers pass `inject_batch_id` to share one UUID
    across the whole batch — including across pipeline kinds — so a
    single wake-up coalesces all completions.
    """
    pipeline = decision.payload.get("pipeline")
    if pipeline == "Forward":
        return _commit_inject_forward(
            decision, conn, problem=problem, tick=tick,
            trigger_kind=trigger_kind, batch_id_override=inject_batch_id,
            step_index=step_index, batch_size=batch_size)
    if pipeline in ("Backward", "Builder"):
        return _commit_inject_redispatch(
            decision, conn, problem=problem, tick=tick,
            trigger_kind=trigger_kind, pipeline=pipeline,
            batch_id_override=inject_batch_id,
            step_index=step_index, batch_size=batch_size)
    raise RuntimeError(
        f"_commit_inject_batch: unhandled pipeline {pipeline!r} "
        f"(verify_decision should have caught this)")


def _commit_inject_forward(decision: Decision, conn: sqlite3.Connection,
                           *, problem: str, tick: int,
                           trigger_kind: str,
                           batch_id_override: str | None = None,
                           step_index: int = 0,
                           batch_size: int = 1) -> CommitOutcome:
    """Forward variant — 1 brief → 1 row + 1 Forward enqueue.

    `batch_id_override` lets a multi-decision call share one batch_id
    across all N Inject(Forward) decisions so cascade fires a single
    `inject_batch_done` once every produced lemma terminates. Solo
    (single-decision) calls leave it None and get a fresh batch_id.
    """
    brief = decision.brief.strip()
    batch_id = batch_id_override or uuid.uuid4().hex
    ts = db.now()
    row_payload = {
        "pipeline": "Forward",
        "step_index": step_index,
        "batch_size": batch_size,
    }
    cur = conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, target_id, brief, reason, payload,"
        " batch_id, outcome, created_at, updated_at)"
        " VALUES (?, ?, ?, 'Inject', NULL, ?, ?, ?, ?, NULL, ?, ?)",
        (problem, tick, trigger_kind, brief,
         decision.reason, json.dumps(row_payload, ensure_ascii=False),
         batch_id, ts, ts),
    )
    row_id = int(cur.lastrowid)
    db.enqueue(
        conn, kind="Forward", target_id=problem,
        target_kind="Problem", priority=10,
        decision_id=row_id, problem=problem,
    )
    db.update_problem_last_strategist_at(conn, problem)
    conn.commit()
    return CommitOutcome(
        decision_row_id=row_id,
        enqueued_forward=True,
        final_outcome="committed",
        batch_id=batch_id,
        batch_decision_row_ids=[row_id],
    )


def _commit_inject_redispatch(decision: Decision, conn: sqlite3.Connection,
                              *, problem: str, tick: int,
                              trigger_kind: str,
                              pipeline: str,
                              batch_id_override: str | None = None,
                              step_index: int = 0,
                              batch_size: int = 1,
                              ) -> CommitOutcome:
    """Backward / Builder variant — 1 row + 1 enqueue on target goal.

    `brief` carries the agent's hint for the redispatch.

    Every Inject row carries a `batch_id` (a fresh UUID for solo
    commits, shared across the batch when multiple decisions commit
    together) so the framework can fire `inject_batch_done` once the
    batch's last decision reaches terminal — mirroring Forward.

    `produced_goal_id = target_id`: lets the goal-side propagation
    fill outcome when the target reaches a terminal goal status
    (Builder's intent is to prove the goal directly, so this is the
    canonical completion signal for Builder). For Backward the
    worker additionally sets `produced_strategy_id` after reserving
    its strategy id; outcome fills via whichever path resolves first
    (idempotent via the `outcome IS NULL` guard), so a Backward
    Inject whose injected strategy dies via cascade still surfaces a
    wake-up even while the target goal stays 'attempting' under a
    sibling.
    """
    target_id = int(decision.target_id)
    brief = decision.brief.strip()
    batch_id = batch_id_override or uuid.uuid4().hex
    ts = db.now()
    row_payload = {
        "pipeline": pipeline,
        "step_index": step_index,
        "batch_size": batch_size,
        "target_goal_id": target_id,
    }
    cur = conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, target_id, brief, reason, payload,"
        " batch_id, produced_goal_id, produced_kind, outcome,"
        " created_at, updated_at)"
        " VALUES (?, ?, ?, 'Inject', ?, ?, ?, ?, ?, ?, 'redispatch',"
        " NULL, ?, ?)",
        (problem, tick, trigger_kind, target_id,
         brief, decision.reason,
         json.dumps(row_payload, ensure_ascii=False),
         batch_id, target_id, ts, ts),
    )
    row_id = int(cur.lastrowid)

    # Force-reopen target so BFS / inject dispatch can run on it.
    # Auto-detach if the upward chain has died — same path Strategist
    # Reopen takes. `dead` is a hard terminal already rejected by
    # verify_decision; this list intentionally excludes it.
    g = db.get_goal(conn, target_id)
    if g and str(g["status"]) in ("shelved", "pending_strategist_review",
                                   "frozen"):
        transitions.apply_goal_transition(
            conn, target_id, "open", event="strategist_reopen")
        if _dispatcher._has_dead_strategy_in_chain(conn, target_id):
            db.set_goal_detached(conn, target_id, True)
        # Un-stall the upward chain (Phase 11): a parent strategy PARKED
        # as 'stalled' because this goal was its last settled sub-goal
        # returns to 'proposed', so the alive-DAG conducts through it again
        # and BFS can reach the just-reopened goal — otherwise it stays
        # orphaned. ('proposed' is non-terminal → no inject-outcome
        # re-propagation; the prior 'failed:stalled' record stands, the
        # fresh redispatch Inject below tracks the revived attempt.)
        for s in conn.execute(
            "SELECT s.id FROM strategies s"
            " JOIN strategy_subgoals ss ON ss.strategy_id = s.id"
            " WHERE ss.subgoal_id = ? AND s.status = 'stalled'",
            (target_id,),
        ).fetchall():
            transitions.apply_strategy_transition(
                conn, int(s["id"]), "proposed", event="strategist_unstall")

    # Pin entry_kind to the requested pipeline so bfs_refill doesn't
    # enqueue a parallel pipeline of the prior kind. Without this, an
    # Inject(Builder) on an entry_kind='Backward' goal lets bfs_refill
    # enqueue a Backward of its own on the same goal — both spawn in
    # parallel under pool=2, the Backward's outcome dominates, and
    # Strategist's redispatch intent is bypassed (LU lu_step_assembly
    # 2026-05-28: 3 consecutive Backward shelves while Strategist
    # explicitly Injected Builder).
    db.update_goal_entry_kind(conn, target_id, pipeline)

    db.enqueue(
        conn, kind=pipeline, target_id=str(target_id),
        target_kind="Goal", priority=10,
        decision_id=row_id, problem=problem,
    )
    db.update_problem_last_strategist_at(conn, problem)
    conn.commit()
    return CommitOutcome(
        decision_row_id=row_id,
        enqueued_forward=False,
        final_outcome="committed",
        batch_id=batch_id,
        batch_decision_row_ids=[row_id],
    )


def commit_decisions(decisions: list[Decision], conn: sqlite3.Connection,
                     *, problem: str, tick: int, trigger_kind: str,
                     workspace: Path) -> list[CommitOutcome]:
    """Execute a multi-decision batch in declared order.

    Caller must have already passed `verify_decisions`. All decisions
    commit; per-kind side effects fire individually. The transaction
    boundary is per-decision (each per-kind helper calls
    `conn.commit()`); a mid-batch raise leaves earlier rows committed,
    which mirrors the existing single-decision contract — verify is
    expected to catch every user-error case, so any raise here
    indicates a framework bug to investigate, not graceful recovery
    territory.

    Inject batching is unified across pipeline kinds: every Inject
    decision in `decisions` shares one `batch_id`, so the cascade
    fires `inject_batch_done` exactly once — when the LAST of the
    Forward / Backward / Builder injects reaches terminal. Each kind
    has its own completion signal (see `_commit_inject_batch`).

    Returns one CommitOutcome per decision (same order).
    """
    inject_batch_id: str | None = None
    n_inject = sum(1 for d in decisions if d.kind == "Inject")
    if n_inject:
        inject_batch_id = uuid.uuid4().hex
    # Real per-step indices: the audit payload's step_index was hardcoded
    # 0 for every row, so `## Completed Inject batches` labelled all
    # steps "step 0" and the Strategist couldn't line outcomes up with
    # its briefs (feedback 2026-07-04, repeated).
    out: list[CommitOutcome] = []
    step = 0
    for d in decisions:
        idx = step
        if d.kind == "Inject":
            step += 1
        out.append(_commit_one(
            d, conn, problem=problem, tick=tick,
            trigger_kind=trigger_kind, workspace=workspace,
            inject_batch_id=inject_batch_id,
            inject_step_index=idx, inject_batch_size=n_inject))
    return out


def commit_decision(decision: Decision, conn: sqlite3.Connection,
                    *, problem: str, tick: int, trigger_kind: str,
                    workspace: Path) -> CommitOutcome:
    """Single-decision wrapper around `commit_decisions`. Preserved
    so existing callers (single-decision tests, anyone hand-driving
    one decision) keep their CommitOutcome-returning contract.
    """
    return commit_decisions(
        [decision], conn, problem=problem, tick=tick,
        trigger_kind=trigger_kind, workspace=workspace,
    )[0]


def _commit_fetch_paper(decision: Decision, conn: sqlite3.Connection,
                        *, problem: str, tick: int,
                        trigger_kind: str) -> CommitOutcome:
    """FetchPaper (paper v2, D11) — 1 audit row + 1 Scholar enqueue.

    Mirrors `_commit_inject_forward`: the audit row is inserted first
    so the queue row carries `decision_id`; the dispatcher fills this
    decision's `outcome` when the Scholar pipeline finishes
    ('paper_fetched' / the failure reason). The queue payload carries
    query+reason so the Scholar's Context renders them without a
    decision-row read."""
    ts = db.now()
    query = str(decision.payload.get("query") or "").strip()
    row_payload = {"query": query}
    cur = conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, target_id, brief, reason, payload,"
        " outcome, created_at, updated_at)"
        " VALUES (?, ?, ?, 'FetchPaper', NULL, NULL, ?, ?, NULL, ?, ?)",
        (problem, tick, trigger_kind, decision.reason,
         json.dumps(row_payload, ensure_ascii=False), ts, ts),
    )
    row_id = int(cur.lastrowid)
    db.enqueue(
        conn, kind="Scholar", target_id=problem,
        target_kind="Problem", priority=3,
        decision_id=row_id, problem=problem,
        payload={"query": query, "reason": str(decision.reason or "")})
    db.update_problem_last_strategist_at(conn, problem)
    conn.commit()
    return CommitOutcome(
        decision_row_id=row_id,
        enqueued_forward=False,
        final_outcome="committed",
    )


def _negation_statement(target_text: str) -> "str | None":
    """MECHANICAL negation surgery (feature D): from the target's own
    file text, extract `<binders> : <conclusion>`, close it to
    ∀-form, and wrap in `¬ (...)`. No LLM touches the statement — a
    re-stated negation could be a strawman, which would make the whole
    settle semantics unsound. Returns None when the signature can't be
    extracted (caller surfaces the error; never guesses)."""
    from ..quality.dedupe import _extract_full_signature, _to_forall_form
    sig = _extract_full_signature(target_text)
    if not sig:
        return None
    return f"¬ ({_to_forall_form(sig)})"


def _header_lines(target_text: str) -> "list[str]":
    """The target file's import/open header — the vocabulary surface the
    negation statement needs (comment lines skipped)."""
    out = []
    for ln in target_text.splitlines():
        s = ln.strip()
        if s.startswith("import ") or s.startswith("open "):
            out.append(ln)
        elif s.startswith(("theorem ", "lemma ", "def ", "structure ",
                           "class ", "inductive ", "instance ",
                           "noncomputable ", "@[")):
            break
    return out


def _commit_attempt_disproof(decision: Decision, conn: sqlite3.Connection,
                             *, problem: str, tick: int,
                             trigger_kind: str,
                             workspace: Path) -> CommitOutcome:
    """AttemptDisproof (feature D) — audit row + mechanically-minted
    ¬P goal (linkage: decision.target_id=P, produced_goal_id=¬P;
    zero schema — the pair lives in the decision row, and the Ingest
    gate / consistency alarm query it there).

    The ¬P goal is a normal open goal (origin='forward', detached,
    entry_kind='Builder' — push_neg + witness is often Builder-sized;
    the threshold escalates to Backward as usual). BFS dispatches it
    like anything else; no new pipeline."""
    gid = int(decision.target_id)  # type: ignore[arg-type]
    g = db.get_goal(conn, gid)
    target_path = workspace / str(g["lean_path"])
    try:
        target_text = target_path.read_text(encoding="utf-8")
    except OSError as e:
        raise RuntimeError(
            f"AttemptDisproof: cannot read target file {target_path}: {e}")
    neg = _negation_statement(target_text)
    if neg is None:
        raise RuntimeError(
            f"AttemptDisproof: could not extract g{gid}'s signature from "
            f"{target_path} — negation must be mechanical; aborting "
            f"rather than guessing")

    slug = f"not_{g['slug']}"[:60]
    header = _header_lines(target_text)
    body = "\n".join(
        header
        + ["",
           f"namespace Problems.{problem}",
           "",
           f"-- AttemptDisproof (framework-minted): mechanical negation "
           f"of `{g['slug']}`.",
           f"theorem {slug} : {neg} := by sorry",
           "",
           f"end Problems.{problem}",
           ""])
    from ..state import proof_store
    proofs_dir = db.problem_dir(workspace, problem) / "proofs"
    proofs_dir.mkdir(parents=True, exist_ok=True)
    dest = proofs_dir / f"L_{slug}.lean"
    if dest.exists():
        raise RuntimeError(
            f"AttemptDisproof: {dest} already exists (slug collision)")
    proof_store.place_proof(
        conn, workspace, goal_id=None,
        rel_path=dest.relative_to(workspace).as_posix(), content=body)
    neg_gid = db.insert_goal(
        conn, problem=problem, slug=slug,
        lean_path=dest.relative_to(workspace).as_posix(),
        statement=neg, origin="forward", depth=0,
        entry_kind="Builder", kind="theorem",
    )
    ts = db.now()
    cur = conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, target_id, brief, reason, payload,"
        " produced_goal_id, produced_kind, outcome, created_at,"
        " updated_at)"
        " VALUES (?, ?, ?, 'AttemptDisproof', ?, NULL, ?, '{}', ?,"
        " 'disproof', NULL, ?, ?)",
        (problem, tick, trigger_kind, gid, decision.reason,
         neg_gid, ts, ts),
    )
    row_id = int(cur.lastrowid)
    db.update_problem_last_strategist_at(conn, problem)
    conn.commit()
    print(f"[strategist] AttemptDisproof(g{gid}) → minted {slug} "
          f"(g{neg_gid}): {neg[:100]}", flush=True)
    return CommitOutcome(
        decision_row_id=row_id,
        enqueued_forward=False,
        final_outcome="committed",
    )


def _commit_ingest(conn: sqlite3.Connection, *, problem: str,
                   workspace: Path) -> None:
    """Execute a Strategist `Ingest` decision's side effect (anchor+claim
    Phase 4).

    The sign-off pause and the Library decision are separate axes
    (2026-07-18 gate retirement): `signoff: false` (machine setting,
    benchmark adapters only) × `library.require_signoff` config decide
    pause-vs-direct; `library:` decides harvest only. A paused problem
    sets `ingest_signoff_pending` and waits for `asterism
    approve-ingest` (→ enqueue Librarian iff library) or `reject-ingest`
    (→ back to proving); direct ingest harvests iff the standing
    `library` flag. The old coupling (library:false silently skipped
    the human gate) let any opt-out producer bypass sign-off.

    Phase 6 — Ingest is the problem's ONLY terminal: this commit stamps
    `problems.ingested_at`, which drives the T1/T4 liveness predicates,
    the stale-row drop, the Librarian selfstart eligibility and the
    daemon exit check. `reject-ingest` and the rollback auto-revoke
    clear the stamp (back to the live path). The old root-proved-auto
    Librarian trigger in `verify.root_integrity_gate` is retired —
    harvest is strictly Ingest-driven now."""
    from ..core import config as _config
    from ..state import manifest as _manifest
    # Decide the sign-off gate BEFORE publishing the terminal stamp.
    # `ingested_at` + a clear flag is what the Librarian selfstart path
    # reads as "approved, go" — so the flag must land in the same
    # transaction as the stamp. The pre-fix order stamped first and set
    # the flag AFTER store_review_snapshot, whose gateway warm-up is a
    # 30s+ window on a cold/stale gateway; the dispatcher tick inside
    # that window auto-started the harvest chain past the human gate
    # (observed 2026-07-06, Logic.toy_list_reverse: dedupe→migrate ran
    # before "paused for human sign-off" printed).
    harvest = True
    signoff_optout = False
    harvest_skip_msg = ""
    mfst_path = db.problem_dir(workspace, problem) / "Manifest.md"
    try:
        mfst = _manifest.parse(mfst_path)
        # Dual-read (frontmatter dissolve): this direct parse bypasses
        # the ManifestCache overlay — stamp DB settings here too, or a
        # UI library-toggle would be invisible to the harvest decision.
        from ..state import settings as _settings
        _settings.overlay(mfst, _settings.read(conn, problem))
        signoff_optout = not mfst.signoff
    except Exception as e:
        # Unreadable Manifest: no harvest, but DO pause — failing into
        # the human gate is the safe direction.
        harvest = False
        harvest_skip_msg = (f"[strategist] Ingest({problem}): Manifest "
                            f"unreadable ({e}); no harvest")
    if harvest and not mfst.library:
        harvest = False
        harvest_skip_msg = (f"[strategist] Ingest({problem}): Manifest "
                            f"library:false — opted out of Library; "
                            f"no harvest")
    require_signoff = (not signoff_optout) and _as_bool(_config.get(
        "library.require_signoff", default=True, workspace=workspace))

    # Terminal stamp + gate flag: one atomic publication. Even when the
    # Manifest opts out of harvest the Strategist's terminal judgment
    # stands; only the harvest side-effects vary.
    db.set_problem_ingested(conn, problem)
    from ..state import transitions as _transitions
    if require_signoff:
        db.set_ingest_signoff_pending(conn, problem, True)
        _transitions.apply_problem_transition(
            conn, problem, "ingest_signoff", event="ingest_committed")
    else:
        _transitions.apply_problem_transition(
            conn, problem, "ingested", event="ingest_direct")
    conn.commit()

    # Slow best-effort work AFTER the gate is closed.
    # Regression manifest (task #8): the milestone auto-records itself —
    # tracked JSONL, best-effort, never blocks the Ingest.
    from ..state import regress as _regress
    # Auditability (frontmatter dissolve): the effective machine
    # settings ride the milestone line — the axiom-whitelist history
    # stays reconstructible from git even though the yaml stopped
    # changing. Best-effort like the rest of the record.
    settings_snapshot = None
    try:
        settings_snapshot = {
            "axioms_whitelist": _manifest.effective_axioms(
                mfst, problem=problem),
            "forbidden_lemmas": list(mfst.forbidden_lemmas),
            "library": bool(mfst.library),
            "signoff": bool(mfst.signoff),
        }
    except Exception:  # noqa: BLE001 — unreadable Manifest path above
        pass
    _regress.record_terminal(
        workspace, problem=problem, terminal="ingested",
        deliverables=len(db.deliverables(conn, problem)),
        settings=settings_snapshot)
    # Review snapshot (frontend charter §5-4): compute the anchor+claim
    # closure NOW, while the gateway is warm from the proving run — the
    # sign-off surfaces (CLI default, serve API) then read the stored
    # JSON instead of paying a 30s+ cold gateway per view. Best-effort:
    # a failure degrades readers to live compute, never blocks Ingest.
    from ..quality import review as _review
    _review.store_review_snapshot(conn, workspace, problem)

    if require_signoff:
        # The Library decision is (re)made at the signature; the current
        # flag is just the standing default, so a false flag is worth a
        # note but never skips the pause.
        if not harvest:
            print(harvest_skip_msg, flush=True)
        print(f"[strategist] Ingest({problem}): paused for human sign-off — "
              f"`asterism approve-ingest {problem}` to harvest, "
              f"`asterism reject-ingest {problem} --reason ...` to keep "
              f"proving", flush=True)
    elif not harvest:
        print(harvest_skip_msg, flush=True)
    else:
        db.enqueue(conn, kind="Librarian", target_id=problem,
                   target_kind="Problem", priority=0, problem=problem)
        print(f"[strategist] Ingest({problem}): direct ingest — enqueued "
              f"Librarian", flush=True)


def _commit_one(decision: Decision, conn: sqlite3.Connection,
                *, problem: str, tick: int, trigger_kind: str,
                workspace: Path,
                inject_batch_id: str | None,
                inject_step_index: int = 0,
                inject_batch_size: int = 1) -> CommitOutcome:
    """Execute one decision's side effects + INSERT audit row.

    Caller must have already passed `verify_decision`. This is the
    write-path; errors here indicate a bug (or a race with another
    Strategist commit), not user error. `inject_batch_id` is
    threaded through to `_commit_inject_batch` so every Inject
    decision in the same `commit_decisions` call shares one batch
    UUID (Forward / Backward / Builder mixed; see `commit_decisions`).
    """
    k = decision.kind
    outcome = "committed"
    enqueued_forward = False

    if k == "Inject":
        return _commit_inject_batch(
            decision, conn, problem=problem, tick=tick,
            trigger_kind=trigger_kind,
            inject_batch_id=inject_batch_id,
            step_index=inject_step_index,
            batch_size=inject_batch_size,
        )

    if k == "Noop":
        # No side effect beyond the audit row + last_strategist_at.
        pass

    elif k == "EmitDirective":
        db.set_problem_strategist_directive(
            conn, problem, str(decision.payload.get("body", "")).strip()
        )

    elif k == "ConfirmShelve":
        gid = int(decision.target_id)  # type: ignore[arg-type]
        # No-op guard (BT 2026-05-29 g3380): a ConfirmShelve on a goal
        # that is already a hard terminal (proved / disproved / dead) is
        # silently ignored — it does NOT bounce the batch back to the
        # Strategist for re-issue. The Strategist sometimes ConfirmShelves
        # a proved-but-superseded orphan (it has no clean "retire orphan"
        # verb); shelving it would regress a completed proof and break
        # `proved ⟺ subs proved`. The rest of the batch (paired Injects,
        # directives) commits normally. The dispatcher's
        # _set_goal_terminal_and_propagate carries the same guard as a
        # class-level backstop, but short-circuiting here also skips the
        # _propagate_shelve cascade and keeps the decision's outcome benign.
        _g = db.get_goal(conn, gid)
        if _g is not None and str(_g["status"]) in (
            "proved", "disproved", "dead",
        ):
            print(f"[strategist] ConfirmShelve(g{gid}) no-op — goal already "
                  f"{_g['status']!r}; not downgrading a terminal goal",
                  flush=True)
        else:
            _dispatcher._set_goal_terminal_and_propagate(conn, gid, "shelved")
            _dispatcher._propagate_shelve(conn, gid)
        # Downward cascade removed: shelved is reopenable (split from
        # disproved), descendants of a shelved goal stay invisible to
        # BFS via the alive-set filter in `db.open_goals` regardless
        # of their own status — no behavior gain from flipping them.
        # Strategist's context view filters descendants of dead chains
        # too (see `_section_active_goals`), so the surface area where
        # status drift could mislead Strategist is closed at the view
        # boundary, not the data boundary.

    elif k == "MarkDeliverable":
        # Synchronous: flag the Forward node top-level. `asterism review`
        # then computes + presents its anchor closure for human opt-out
        # review. Falls through to the shared audit-row INSERT (outcome
        # 'success').
        db.mark_deliverable(conn, int(decision.target_id))  # type: ignore[arg-type]

    elif k == "FetchPaper":
        # Paper v2 (D11): own commit path — audit row FIRST so the
        # Scholar queue row carries decision_id (Inject pattern; the
        # dispatcher fills this decision's `outcome` on completion).
        return _commit_fetch_paper(
            decision, conn, problem=problem, tick=tick,
            trigger_kind=trigger_kind)

    elif k == "AttemptDisproof":
        # Feature D: own commit path — mints the mechanical ¬P goal
        # (linkage rides the decision row: target_id=P,
        # produced_goal_id=¬P).
        return _commit_attempt_disproof(
            decision, conn, problem=problem, tick=tick,
            trigger_kind=trigger_kind, workspace=workspace)

    elif k == "Ingest":
        # Terminal judgment → pause for human sign-off (unless the
        # problem's `signoff: false` machine setting or config opts
        # into direct ingest); harvest to Library iff `library:`.
        # Falls through to the audit INSERT.
        _commit_ingest(conn, problem=problem, workspace=workspace)

    elif k == "RequestUserAmend":
        # Atomic three-step: tmp write -> INSERT row -> rename
        # (see docs/archive/design/phase2/pipelines.md §2.5).
        file = decision.payload["file"]
        target_path = db.problem_dir(workspace, problem) / f".proposed_{file}"
        body = str(decision.payload["proposed_body"])
        # Step 1: write to a temp file in the same directory then fsync.
        target_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".proposed_{file}.", dir=str(target_path.parent),
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(body)
                fh.flush()
                os.fsync(fh.fileno())
            # Step 2: INSERT audit row with outcome='awaiting_human'.
            # Step 3 (rename) happens below after the row is in place.
            # Stuffed into the row INSERT path below for atomicity.
        except Exception:
            # Best-effort cleanup of orphan tmp
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise
        # Stash for the post-INSERT rename below
        decision.payload["__tmp_path__"] = tmp_name
        decision.payload["__final_path__"] = str(target_path)
        outcome = "awaiting_human"

    else:
        raise RuntimeError(f"commit_decision: unhandled kind {k!r}")

    # INSERT audit row. brief and reason live in dedicated columns;
    # other structured params go in payload JSON (excluding the tmp
    # path bookkeeping for RequestUserAmend).
    #
    # `batch_id` is shared with the batch's Inject rows: when a
    # ConfirmShelve / Reopen / etc. ships in the same JSON decision
    # array as one or more Inject(s), it inherits the same UUID. The
    # `_section_pending_reopens` Context.md section uses this link to
    # surface a shelved goal ONLY when the Strategist-promised batch
    # of follow-up Injects has completed — instead of re-surfacing
    # the goal on every unrelated inject_batch_done wake (brouwer
    # 2026-05-22: g2771 ConfirmShelve'd 4× because Context.md kept
    # listing it on every wake regardless of who was woken). For
    # solo non-Inject batches (no paired Inject), inject_batch_id is
    # None and the column stays NULL, matching the pre-fix shape.
    payload_for_audit = {
        k: v for k, v in decision.payload.items()
        if not str(k).startswith("__")
    }
    # DB outcome ≠ caller signal (CommitOutcome.final_outcome). Inject
    # rows write NULL here (filled later by propagate_inject_outcome_
    # from_goal/strategy when produced_goal/strategy terminates) — but
    # Inject returns early via _commit_inject_batch and never reaches
    # this INSERT. Everything that lands here is a synchronous decision:
    # its side effect already executed above, so the row is terminal
    # at INSERT time. RequestUserAmend keeps 'awaiting_human' (terminal
    # from framework POV — blocked on operator). All other kinds
    # (ConfirmShelve/Reopen/EmitDirective/Noop) write 'success'.
    #
    # Pre-fix bug: this column wrote NULL for ConfirmShelve+friends.
    # Solo (batch_id=NULL) was harmless. Paired with Inject in same
    # batch (e.g. ConfirmShelve(G) + Inject(Forward, prereq)), the
    # NULL outcome made `maybe_enqueue_inject_batch_done`'s pending
    # count never reach 0 (the batch stayed "incomplete" forever) and
    # the in-flight-inject suppression read the batch as live — so
    # Strategist never woke to fire the promised follow-up Reopen.
    # Observed jordan_normal_form 2026-05-23: ConfirmShelve(succ_glue)
    # paired with Inject of the index-layout brick chain; bricks proved,
    # batch_id stayed "incomplete" forever, the triggers stayed gated,
    # daemon idle. (As of 2026-06-15 the in-flight suppression is a
    # precise active-check — `has_active_inflight_inject` for T4,
    # `has_live_inflight_inject` for T0 / the Noop-guard — not a blanket
    # NULL-row test; but a NULL ConfirmShelve still stalls the batch
    # pending count, so synchronous decisions MUST write a non-NULL
    # outcome here.)
    if outcome == "awaiting_human":
        db_outcome: str | None = "awaiting_human"
    else:
        db_outcome = "success"
    ts = db.now()
    cur = conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, target_id, brief, reason, payload,"
        " batch_id, outcome, created_at, updated_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (problem, tick, trigger_kind, decision.kind,
         decision.target_id, decision.brief, decision.reason,
         json.dumps(payload_for_audit, ensure_ascii=False),
         inject_batch_id,
         db_outcome,
         ts, ts),
    )
    decision_row_id = int(cur.lastrowid)

    # Post-INSERT side effects requiring the row id. Inject is handled
    # earlier via _commit_inject_batch (returns early); only
    # RequestUserAmend's atomic rename lives here.
    if k == "RequestUserAmend":
        # Atomic rename: temp -> .proposed_<file>. If this fails the
        # audit row is rolled back via the outer transaction.
        os.rename(decision.payload["__tmp_path__"],
                  decision.payload["__final_path__"])
        from ..state import transitions as _transitions
        _transitions.apply_problem_transition(
            conn, problem, "awaiting_human", event="amend_requested")

    # Touch last_strategist_at. (Phase 6: bootstrap_done is vestigial —
    # T0/first_launch retired; the column stays, nothing reads it.) The
    # ROUTINE clock (last_routine_at, which drives T1) is touched ONLY on
    # a routine commit so event-driven triggers don't reset the routine
    # audit's cadence.
    db.update_problem_last_strategist_at(conn, problem)
    if trigger_kind == "routine":
        db.update_problem_last_routine_at(conn, problem)
    conn.commit()

    return CommitOutcome(
        decision_row_id=decision_row_id,
        enqueued_forward=enqueued_forward,
        final_outcome=outcome,
    )


# ---------------------------------------------------------------------
# Outer entry — full agent integration
# ---------------------------------------------------------------------

def run_strategist(conn: sqlite3.Connection, *, problem: str,
                   trigger_kind: str, tick: int,
                   workspace: Path,
                   mfst: "Any",
                   pipeline_id: str,
                   pending_review_id: int | None = None) -> "Any":
    """Full Strategist pipeline (Phase 2 §2.4).

    Stages:
      1. trigger_context   — compile Strategist-flavoured Context.md
      2. agent             — spawn LLM, drops `decision.json` in
                             attempts_dir
      3. self_verify       — parse_decisions + verify_decisions
      4. commit            — commit_decisions side effects
      5. status mapping    — Noop-only batch / schema invalid →
                             infra-reason (no attempts++); commit
                             → success

    Returns `PipelineResult` with one of:
      - outcome='success' on a clean commit (one or more decisions,
        at least one non-Noop)
      - outcome='failed', failure_reason='strategist_noop' when the
        batch contains only Noop decisions (infra so cascade_one
        doesn't burn root.attempts)
      - outcome='failed', failure_reason='strategist_schema_invalid'
        when parse/verify rejects the agent's output (all-or-nothing
        at this stage — no row is committed if any decision fails)
      - outcome='failed', failure_reason='agent_no_output' if no
        decision.json produced
      - provider rc-based reasons (quota / spawn_fast_fail / ...) on
        agent.spawn_llm rc != 0
    """
    from .. import agent
    from ..core import config
    from . import PipelineResult, PROMPT_DIR
    from ..agent.phase2_context import compile_strategist_context

    attempts_dir = agent.attempts_dir_for(workspace, pipeline_id)
    problem_dir = db.problem_dir(workspace, problem)
    # Per-trigger prompt: each trigger has its own focused prompt so
    # the agent sees only the guidance relevant to this wake's kind
    # (routine / pending_review / inject_batch_done).
    # Loader validates that every TRIGGER_KIND has a corresponding
    # file at startup via test_strategist_prompts_cover_all_triggers.
    prompt_path = PROMPT_DIR / "strategist" / f"{trigger_kind}.md"
    if not prompt_path.exists():
        return PipelineResult(
            outcome="failed",
            failure_reason="strategist_schema_invalid",
            failure_detail=(
                f"missing prompt file for trigger_kind={trigger_kind!r}: "
                f"{prompt_path}"
            ),
        )

    # Stage 1 — Context.md
    compile_strategist_context(
        conn, problem=problem, trigger_kind=trigger_kind,
        attempts_dir=attempts_dir, workspace=workspace, mfst=mfst,
        pending_review_id=pending_review_id,
    )

    # Stage 2 — agent spawn. Mint a session id so the in-pipeline
    # revision rounds can resume the same claude session and see the
    # framework's verify error / Adversary rebuttal inline.
    # Thinking is legal work (research_mode_design.md §0): the
    # strategist cap is a hang guard, not a work budget.
    strategist_timeout = config.get(
        "strategist.timeout_sec", default=10800,
        env_var="ASTERISM_STRATEGIST_TIMEOUT_SEC", cast=int,
    )
    sid = str(uuid.uuid4())
    # D8 (2026-07-24): a fresh problem has no prior batches — the
    # meta-analysis / reopen-promise paragraphs render only once
    # history exists (conditional blocks, wording untouched).
    has_history = conn.execute(
        "SELECT 1 FROM strategist_decisions WHERE problem = ? LIMIT 1",
        (problem,)).fetchone() is not None
    # has_kb gates the routine wake's lesson-KB curation block — an
    # empty KB renders neither the Context surface nor the instruction.
    from ..state import kb as _kb
    has_kb = bool(_kb.global_lessons(conn, problem))
    rc = agent.spawn_llm(
        kind="strategist", prompt_path=prompt_path,
        problem_dir=problem_dir, attempts_dir=attempts_dir,
        session_id=sid, timeout_sec=strategist_timeout,
        prompt_flags={"has_history": has_history, "has_kb": has_kb},
    )
    # Persist the plan note BEFORE any outcome branching: the note is the
    # agent's memory of its own thinking — worth keeping even when the
    # spawn then fails parse/verify (and on rc!=0, if it got that far).
    _persist_plan(problem_dir, attempts_dir)
    if rc != 0:
        return PipelineResult(
            outcome="failed",
            failure_reason=_rc_to_reason(rc),
            failure_detail=f"agent rc={rc}",
        )

    # Stage 3-4 — parse + verify + the proposal-package gate + the
    # Adversary, unified into one N-round revision loop on the same
    # strategist session (research_mode_design.md §3). Mechanical
    # verify errors and Adversary rebuttals SHARE the round counter
    # (v14 ruling). Parse failures are still NOT retried: a malformed
    # decision.json usually means session-level breakage (no clean
    # recovery from re-prompting).
    max_rounds = config.get(
        "strategist.verify_retry", default=6,
        env_var="ASTERISM_STRATEGIST_VERIFY_RETRY", cast=int,
    )
    decision_path = attempts_dir / "decision.json"

    def _read_and_parse() -> tuple[
        list[Decision] | None, str, str
    ]:
        """Returns (decisions, parse_err, missing_reason). When the
        file is missing, missing_reason is non-empty for
        agent_no_output mapping."""
        if not decision_path.exists():
            return None, "", "decision.json not produced"
        try:
            text = decision_path.read_text(encoding="utf-8")
        except OSError as e:
            return None, "", f"decision.json unreadable: {e}"
        ds, perr = parse_decisions(text)
        return ds, perr, ""

    decisions, parse_err, missing = _read_and_parse()
    if missing:
        return PipelineResult(
            outcome="failed", failure_reason="agent_no_output",
            failure_detail=missing,
        )
    if decisions is None:
        return PipelineResult(
            outcome="failed",
            failure_reason="strategist_schema_invalid",
            failure_detail=f"parse: {parse_err}",
        )

    from ..state import programme as _programme
    from . import adversary as _adversary

    dialogue: list[dict] = []
    rounds_used = 0
    package_verdict: "dict | None" = None
    proposal_body: "str | None" = None
    first_err: "str | None" = None
    while True:
        err = (resolve_directive_body_files(decisions, attempts_dir)
               or verify_decisions(decisions, conn, problem=problem,
                                   workspace=workspace,
                                   trigger_kind=trigger_kind))
        err_is_rebuttal = False
        if not err and package_gate_applies(decisions, trigger_kind):
            proposal_body, sections, err = verify_proposal_package(
                decisions, attempts_dir)
            if not err:
                proof_warn = _programme.proof_warning(sections)
                if proof_warn:
                    print(f"[strategist] {problem}: {proof_warn}",
                          flush=True)
                verdict, aerr, arc = _adversary.review(
                    round_no=rounds_used + 1,
                    attempts_dir=attempts_dir, problem_dir=problem_dir,
                    conn=conn, problem=problem,
                    proposal_body=proposal_body, decisions=decisions,
                    dialogue=dialogue, proof_warn=proof_warn)
                if arc != 0:
                    return PipelineResult(
                        outcome="failed",
                        failure_reason=_rc_to_reason(arc),
                        failure_detail=f"adversary rc={arc}")
                if verdict is None:
                    return PipelineResult(
                        outcome="failed",
                        failure_reason="agent_no_output",
                        failure_detail=f"adversary: {aerr}")
                if verdict["verdict"] == "pass":
                    package_verdict = verdict
                    break
                # Rebuttal: the criticisms target THIS body — keep it
                # with them so the next (fresh) judge reads the round
                # as documents (fresh-per-round, design §3).
                dialogue.append({"round": rounds_used + 1,
                                 "role": "adversary",
                                 "criticisms": verdict["criticisms"],
                                 "proposal": proposal_body})
                # rounds_left = revisions still available AFTER this
                # rebuttal: a retry fires whenever rounds_used <
                # max_rounds, so exactly max_rounds - rounds_used
                # remain (off-by-one here once taught "0 left" while
                # the loop granted one more).
                err = _format_rebuttal(
                    verdict, rounds_used + 1,
                    max_rounds - rounds_used)
                err_is_rebuttal = True
        if not err:
            break  # verify clean; exempt batches skip the package gate
        if first_err is None:
            first_err = err
        if rounds_used >= max_rounds:
            if err_is_rebuttal and proposal_body is not None:
                # Exhaustion on the adversarial channel discards the
                # proposal AND the session: the rejected draft + full
                # criticism go to the DB for audit; the next wake gets
                # one line and re-derives blind (design §1/§3).
                _programme.record_rejection(
                    conn, problem, proposal_body, dialogue, rounds_used)
                conn.commit()
                return PipelineResult(
                    outcome="failed",
                    failure_reason="strategist_proposal_rejected",
                    failure_detail=(
                        f"adversary rejected after {rounds_used} "
                        "revision round(s); proposal + criticisms "
                        "recorded in programme_revisions"))
            return PipelineResult(
                outcome="failed",
                failure_reason="strategist_schema_invalid",
                failure_detail=(f"verify (round {rounds_used}): {err}; "
                                f"first-attempt: {first_err}"),
            )
        rounds_used += 1
        rc2 = agent.spawn_llm(
            kind="strategist", prompt_path=prompt_path,
            problem_dir=problem_dir, attempts_dir=attempts_dir,
            session_id=sid, is_retry=True, retry_context=err,
            timeout_sec=strategist_timeout,
        )
        _persist_plan(problem_dir, attempts_dir)  # retry may rewrite it
        if rc2 != 0:
            return PipelineResult(
                outcome="failed",
                failure_reason=_rc_to_reason(rc2),
                failure_detail=(
                    f"revision round {rounds_used} rc={rc2}; "
                    f"pending: {err}"
                ),
            )
        decisions, parse_err, missing = _read_and_parse()
        if missing or decisions is None:
            detail = missing or f"parse: {parse_err}"
            return PipelineResult(
                outcome="failed",
                failure_reason="strategist_schema_invalid",
                failure_detail=(
                    f"revision round {rounds_used} output: {detail}; "
                    f"pending: {err}"
                ),
            )

    # Stage 5 — commit + outcome mapping
    if all(d.kind == "Noop" for d in decisions):
        # Pure-Noop batch (one or more Noops): commit audit rows so
        # last_strategist_at + bootstrap_done advance, but map the
        # pipeline outcome to the infra-reason so cascade_one doesn't
        # try to attempts++ on the root. A mixed batch with at least
        # one non-Noop decision falls through to the success path
        # below — there's real work in it.
        try:
            commit_decisions(
                decisions, conn, problem=problem, tick=tick,
                trigger_kind=trigger_kind, workspace=workspace,
            )
        except Exception as e:
            return PipelineResult(
                outcome="failed",
                failure_reason="strategist_schema_invalid",
                failure_detail=f"commit raised: {type(e).__name__}: {e}",
            )
        if trigger_kind == "routine":
            _apply_kb_curation(conn, problem=problem,
                               attempts_dir=attempts_dir)
        return PipelineResult(
            outcome="failed",
            failure_reason="strategist_noop",
            failure_detail=" | ".join(
                str(d.reason or "") for d in decisions
            ),
        )

    try:
        outcomes = commit_decisions(
            decisions, conn, problem=problem, tick=tick,
            trigger_kind=trigger_kind, workspace=workspace,
        )
    except Exception as e:
        # Commit must succeed once verify passed; any error here is
        # a framework bug. Surface as schema_invalid so dispatcher
        # doesn't burn root.attempts on a framework-side issue.
        return PipelineResult(
            outcome="failed",
            failure_reason="strategist_schema_invalid",
            failure_detail=f"commit raised: {type(e).__name__}: {e}",
        )

    if package_verdict is not None and proposal_body is not None:
        # Passed proposal → the Programme revision chain advances in
        # the same wake as its batch (rev↔batch link via batch_id).
        # PROGRAMME.md render is best-effort — the DB row is the SoT.
        batch_id = next(
            (o.batch_id for o in outcomes if o.batch_id), None)
        _programme.record_pass(
            conn, problem, proposal_body, package_verdict, dialogue,
            rounds_used, batch_id)
        conn.commit()
        try:
            _programme.render(conn, problem, problem_dir)
        except OSError as e:
            print(f"[strategist] PROGRAMME.md render failed: {e}",
                  flush=True)

    if trigger_kind == "routine":
        # Curation applies only after the wake's decisions committed —
        # a rejected batch (retry loop above) must not half-apply a
        # sidecar the agent may still rewrite.
        _apply_kb_curation(conn, problem=problem,
                           attempts_dir=attempts_dir)

    kinds = ",".join(d.kind for d in decisions)
    row_ids = ",".join(str(o.decision_row_id) for o in outcomes)
    # Framework feedback (dedicated tail step) — fired here, after every
    # `--resume <sid>` (main + optional verify-retry) is done, so the feedback
    # turn never pollutes a verify-retry's session. No-op unless feedback is on.
    from . import _feedback
    _feedback.attempt_feedback(
        kind="strategist", sid=sid, slug=str(trigger_kind or "strategist"),
        outcome="success", problem_dir=problem_dir,
        attempts_dir=attempts_dir, workspace=workspace)
    return PipelineResult(
        outcome="success",
        failure_reason="",
        failure_detail=(
            f"committed {len(decisions)} decision(s): [{kinds}] "
            f"(decision_rows=[{row_ids}])"
        ),
    )


_KB_CURATION_MAX_OPS = 10


def _apply_kb_curation(conn: "Any", *, problem: str,
                       attempts_dir: Path) -> None:
    """Routine-wake KB curation (2026-07-13, user call; moved from the
    retired audit wake 2026-07-25): apply the optional
    `kb_curation.json` sidecar the agent may drop next to
    decision.json. Ops:

      {"op": "delete", "id": N, "reason": "..."}
      {"op": "merge", "keep_id": N, "absorb_ids": [..],
       "title": "...", "body": "...", "reason": "..."}

    Deliberately a sidecar, NOT a decision kind: curation is
    belief-store maintenance (same class as the direct `_plan.md`
    curation), never problem-state advance — keeping it out of
    decision.json means it can never satisfy the stall-advance delta
    gate, and no DB CHECK migration is needed. Only the routine runner
    calls this, so the power is structurally routine-only.

    Strict all-or-nothing: any invalid op rejects the whole file with
    a loud `[kb-curation]` line and nothing is applied — but the wake
    itself never fails on it (the sidecar is best-effort; the wake's
    deliverables are its decisions + note). Applied ops print full
    pre-image snapshots to the daemon log as the audit trail."""
    from ..state import kb

    path = attempts_dir / "kb_curation.json"
    if not path.exists():
        return

    def _reject(msg: str) -> None:
        print(f"[kb-curation] {problem}: rejected, nothing applied — "
              f"{msg}", flush=True)

    try:
        ops = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return _reject(f"unreadable/invalid JSON: {e}")
    if not isinstance(ops, list) or not ops:
        return _reject("must be a non-empty JSON array of ops")
    if len(ops) > _KB_CURATION_MAX_OPS:
        return _reject(f"{len(ops)} ops exceeds the per-wake cap of "
                       f"{_KB_CURATION_MAX_OPS}")

    eligible = {int(r["id"]) for r in kb.global_lessons(conn, problem)}
    seen_ids: set[int] = set()

    def _claim(raw: "Any", i: int, field: str) -> int | None:
        if not isinstance(raw, int) or isinstance(raw, bool):
            _reject(f"op #{i}: {field} must be an integer id")
            return None
        if raw not in eligible:
            _reject(f"op #{i}: id {raw} is not one of this problem's "
                    "global lessons")
            return None
        if raw in seen_ids:
            _reject(f"op #{i}: id {raw} referenced by more than one op")
            return None
        seen_ids.add(raw)
        return raw

    parsed: list[dict] = []
    for i, op in enumerate(ops):
        if not isinstance(op, dict):
            return _reject(f"op #{i}: not a JSON object")
        if not str(op.get("reason", "")).strip():
            return _reject(f"op #{i}: non-empty source-checked 'reason' "
                           "is required")
        kind = op.get("op")
        if kind == "delete":
            if _claim(op.get("id"), i, "id") is None:
                return None
        elif kind == "merge":
            if _claim(op.get("keep_id"), i, "keep_id") is None:
                return None
            absorb = op.get("absorb_ids")
            if not isinstance(absorb, list) or not absorb:
                return _reject(f"op #{i}: absorb_ids must be a non-empty "
                               "list")
            for a in absorb:
                if _claim(a, i, "absorb_ids entry") is None:
                    return None
            if not str(op.get("title", "")).strip():
                return _reject(f"op #{i}: merged 'title' must be "
                               "non-empty")
        else:
            return _reject(f"op #{i}: unknown op {kind!r} (delete|merge)")
        parsed.append(op)

    for op in parsed:
        if op["op"] == "delete":
            snap = kb.delete_global_lesson(
                conn, entry_id=op["id"], problem=problem)
            print(f"[kb-curation] {problem}: deleted lesson "
                  f"[id-{op['id']}] reason={op['reason']!r} "
                  f"snapshot={dict(snap) if snap else None}", flush=True)
        else:
            snaps = kb.merge_global_lessons(
                conn, keep_id=op["keep_id"],
                absorb_ids=[int(a) for a in op["absorb_ids"]],
                problem=problem, title=str(op["title"]),
                body=str(op.get("body", "")))
            print(f"[kb-curation] {problem}: merged "
                  f"{op['absorb_ids']} into [id-{op['keep_id']}] "
                  f"reason={op['reason']!r} "
                  f"pre-images={[dict(r) for r in snaps or []]}",
                  flush=True)


def _persist_plan(problem_dir: Path, attempts_dir: Path) -> None:
    """Persist the Strategist's `_plan.md` (private cross-wake note, see
    `_drafts.persist_plan_note`) + one telemetry line. Best-effort."""
    from . import _drafts
    n = _drafts.persist_plan_note(problem_dir=problem_dir,
                                  attempts_dir=attempts_dir)
    if n is not None:
        over = (" (over soft cap)"
                if n > _drafts.PLAN_NOTE_SOFT_CAP else "")
        print(f"[strategist] plan note updated: {n} chars{over}",
              flush=True)


def _rc_to_reason(rc: int) -> str:
    """Channel failure_reason for an agent rc — thin alias of the registry's
    `failures.rc_to_reason` (task #5: the last per-pipeline mirror of the rc
    taxonomy; kept as a module-local name for the two call sites + tests)."""
    from ..state.failures import rc_to_reason
    return rc_to_reason(rc)
    if rc == 126:
        return "quota_exhausted"
    if rc == 127:
        return "missing_dep"
    if rc == 128:
        return "spawn_fast_fail"  # stuck thinking — treat as infra
    return "spawn_fast_fail"
