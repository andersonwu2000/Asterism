"""Pending-review dossier sections — the four pieces of context a
Strategist wake renders for every goal awaiting its verdict: why it
failed (`_section_pending_review_failure`), its ruling history plus
live citation waiters (`_section_pending_review_adjudications`), its
existing strategies (`_section_pending_review_strategies`), and its
ancestor chain (`_section_pending_review_ancestors`).

Split out of `phase2_context.py` 2026-08-28 (Phase B, B2) unchanged.
`_slugify_ident` rides along — it has zero call sites anywhere in the
repo (checked at split time; dead code untouched by this move) and
sits in the source immediately after this cluster with no caller to
weigh a placement by.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from ...state import db


def _section_pending_review_failure(
    conn: sqlite3.Connection, pending_review_id: int,
    attempts_dir: "Path | None" = None,
) -> list[str]:
    """Why this goal is under review: one line per attempt, and the
    autopsies in `PAST_DIRECT_ATTEMPTS.md` beside them.

    Phase 2 §2.2 calls for the failure summary, and the agent's own
    shelve description (`dead_attempts.proposal_md`) is the review's
    primary evidence — without it the Strategist saw only a goal
    statement and re-issued directives for blockers the worker had
    already enumerated (the take-5 SG misfire).

    Both used to ride inline under head truncation, and both got cut at
    the payload the verdict hinges on: the brief's cap went 1500 -> 4000
    on 2026-07-05 because 1500 sliced real proposals mid-signature and
    the Strategist rebuilt them by grepping source. Raising a cap is not
    a fix for truncation, only a delay — so the caps are gone and the
    full text rides the companion, the same split the worker's own goal
    history uses (2026-08-11).
    """
    rows = list(conn.execute(
        "SELECT pipeline_id, failure_reason, failure_detail, proposal_md,"
        " artifacts, ts"
        " FROM dead_attempts WHERE target_kind = 'Goal' AND target_id = ?"
        " ORDER BY id DESC LIMIT 5",
        (str(pending_review_id),),
    ))
    if not rows:
        return []
    from ..context import _digest_failure
    from .. import context_files
    out = ["### Recent failed attempts on this goal (newest first)", ""]
    for r in rows:
        out.append(
            f"- pipeline=`{str(r['pipeline_id'])[:8]}`  "
            f"reason=`{r['failure_reason']}`  ts={r['ts']}"
        )
        digest = _digest_failure(str(r["failure_reason"] or ""),
                                 str(r["failure_detail"] or ""))
        if digest:
            out.append(f"  {digest}")
    out.append("")
    if attempts_dir is not None:
        try:
            written = context_files.write_past_attempts(rows, attempts_dir)
        except OSError:
            written = None
        if written is not None:
            out += ["Each attempt's full autopsy — raw failure_detail, the "
                    "agent's own brief, its parting note — in "
                    f"`{context_files.PAST_DIRECT_ATTEMPTS_FILENAME}`.", ""]
    return out


def _first_sentence(text: str, cap: int = 110) -> str:
    t = " ".join((text or "").split())
    for sep in (". ", "; "):
        i = t.find(sep)
        if 0 < i < cap:
            return t[:i + 1]
    return t[:cap] + ("…" if len(t) > cap else "")


def _section_pending_review_adjudications(
    conn: sqlite3.Connection, pending_review_id: int,
    attempts_dir: "Path | None" = None,
) -> list[str]:
    """The goal's ruling history, one SENTENCE per ruling (owner call
    2026-08-25: no ruling text inlined — the full rulings live in the
    lazily-loaded `ADJUDICATIONS.md`), plus the live citation waiters
    a park here would strand. Cure for the review roulette: 110 of 210
    parked union_closed goals were re-adjudicated by ≥2 different
    groups, each reviewer blind to the last ruling."""
    from .. import context
    rows = list(conn.execute(
        "SELECT group_id, decision_kind, reason, created_at"
        " FROM strategist_decisions"
        " WHERE target_id = ? AND decision_kind IN"
        "       ('ConfirmShelve', 'Inject')"
        " ORDER BY id", (pending_review_id,)))
    parked = [r for r in rows if r["decision_kind"] == "ConfirmShelve"]
    waiters = list(conn.execute(
        "SELECT s.id AS sid, s.goal_id, g.slug FROM strategy_subgoals ss"
        " JOIN strategies s ON s.id = ss.strategy_id"
        " JOIN goals g ON g.id = s.goal_id"
        " WHERE ss.subgoal_id = ? AND ss.link_kind = 'cited'"
        "   AND s.status = 'proposed'", (pending_review_id,)))
    if not parked and not waiters:
        return []
    out = ["### Adjudication history on this goal", ""]
    if parked:
        for r in rows:
            ts = str(r["created_at"])[:16]
            if r["decision_kind"] == "ConfirmShelve":
                out.append(f"- {ts} grp{r['group_id']} parked it: "
                           f"{_first_sentence(str(r['reason'] or ''))}")
            else:
                out.append(f"- {ts} grp{r['group_id']} re-dispatched it")
        where = (context.adjudications_companion_path(attempts_dir)
                 if attempts_dir is not None
                 else context.ADJUDICATIONS_COMPANION)
        out += ["", f"Full rulings: `{where}` § `g{pending_review_id}` "
                     "— overturning a park should answer the recorded "
                     "reason, not rediscover it.", ""]
    if waiters:
        out += ["Live strategies CITING this goal (they block at verify "
                "until it proves; a ConfirmShelve here sends each one's "
                "own goal back to its group's review):", ""]
        out += [f"- s{w['sid']} under goal {w['goal_id']} "
                f"(`{w['slug']}`)" for w in waiters]
        out.append("")
    return out


def _section_pending_review_strategies(
    conn: sqlite3.Connection, pending_review_id: int,
) -> list[str]:
    """Existing strategies on the pending-review goal.

    Phase 2 §2.2 review_context spec: '既有 strategy 內容'. Surfaces
    what's already been tried structurally so Strategist can judge
    'Reopen with directive' vs 'Inject Forward to expand toolkit' from
    the actual proposal text — not from the goal statement alone.
    """
    rows = list(conn.execute(
        "SELECT id, status, proposal_md, created_at"
        " FROM strategies WHERE goal_id = ?"
        " ORDER BY id",
        (pending_review_id,),
    ))
    if not rows:
        return []
    out = ["### Existing strategies on this goal", ""]
    for r in rows:
        out.append(
            f"- s{r['id']} status=`{r['status']}` created={r['created_at']}"
        )
        prop = (r["proposal_md"] or "").strip()
        if prop:
            if len(prop) > 800:
                prop = prop[:800].rstrip() + "\n…(truncated)"
            out += ["", "  proposal:", "  ```", prop, "  ```"]
        out.append("")
    return out


def _section_pending_review_ancestors(
    conn: sqlite3.Connection, pending_review_id: int,
) -> list[str]:
    """Walk goal → parent-strategy → strategy.goal_id chain upward to
    root. Phase 2 §2.2 review_context spec: 'ancestor 鏈'.

    At most one live parent strategy per goal (BFS invariant — others
    are superseded or dead). Walk picks the live one if any, else the
    most recently linked dead strategy (so context shows the historical
    chain even after upstream death).
    """
    chain: list[sqlite3.Row] = []
    seen: set[int] = set()
    cur = pending_review_id
    while cur not in seen:
        seen.add(cur)
        # Find parent strategy via strategy_subgoals
        parent = conn.execute(
            "SELECT s.id AS sid, s.goal_id AS pg, s.status AS sstatus"
            " FROM strategy_subgoals ss"
            " JOIN strategies s ON s.id = ss.strategy_id"
            " WHERE ss.subgoal_id = ?"
            " ORDER BY CASE s.status WHEN 'proposed' THEN 0"
            "                       WHEN 'succeeded' THEN 1"
            "                       ELSE 2 END, s.id DESC"
            " LIMIT 1",
            (cur,),
        ).fetchone()
        if parent is None:
            break
        pg = int(parent["pg"])
        g = db.get_goal(conn, pg)
        if g is None:
            break
        chain.append(g)
        cur = pg
    if not chain:
        return ["### Ancestor chain", "",
                "(none — this goal is its own root)", ""]
    out = ["### Ancestor chain (parent → root)", ""]
    for g in chain:
        st = str(g["statement"])
        if len(st) > 200:
            st = st[:200].rstrip() + "…"
        marker = " (ROOT)" if g["origin"] == "root" else ""
        out.append(
            f"- [{g['id']}] depth={g['depth']} status=`{g['status']}`"
            f" `{g['slug']}`{marker}"
        )
        out.append(f"  `{st}`")
    out.append("")
    return out


def _slugify_ident(name: str) -> str:
    """camelCase / PascalCase → snake_case, primes dropped — the slug
    charset normalization ([a-z][a-z0-9_]*) workers apply when a brief
    pins a name the commit gate would reject."""
    s = re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", name)
    return s.lower().replace("'", "")


