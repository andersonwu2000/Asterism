"""Inject-batch outcomes — what a completed (or still-running) batch
handed back: the delegate/delivered-group summary, the per-step
scoreboard and its `BATCHES.md` companion, the prose-label vocabulary
shared with `_section_failure_replay`, the worker-decline digest, and
the reopen-promise section that reads its complement (a promise's
Inject siblings all resolved).

`_section_inject_batch_outcomes` is the render both the Strategist's
Context.md and the Adversary's PROGRAMME projection call directly
(`pipeline/round_materials.py` imports it from this package by name — the
facade and this module both have to keep answering to it).

Split out of `phase2_context.py` 2026-08-28 (Phase B, B2) unchanged.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ...state import db


def _delegate_result_lines(conn: sqlite3.Connection,
                           row: sqlite3.Row,
                           attempts_dir: "Path | None" = None,
                           ) -> list[str]:
    """What a finished sub-group handed back: the bricks the parent may
    now cite, or the charter it returned and why.

    RS-D (research_mission_design.md §3.3) — a delivered group's final
    passed Programme revision is its NL report upward: what it came to
    believe and why, in the child's own argued prose. Bricks alone are
    the WHAT; the parent also needs the WHY to compose them without
    re-deriving the child's reasoning. Rides as a lazy companion
    (`PROGRAMME_G<id>.md`, same pattern as `BATCHES.md`), so nothing is
    truncated and nothing is inlined. The judge projection re-renders
    this section with `attempts_dir=proj`, so the judge gets the same
    file. A returned group's plan note stays on disk as archaeology —
    its upward report is the ReturnToParent post-mortem below."""
    gid = row["produced_group_id"]
    if gid is None:
        return ["  (the group row is gone; nothing to collect)"]
    from ...state import groups as _groups
    g = _groups.get(conn, int(gid))
    if g is None:
        return ["  (the group row is gone; nothing to collect)"]
    charter = " ".join(str(g["charter"] or "").split())
    if len(charter) > 300:
        charter = charter[:300].rstrip() + "…"
    out = [f"  DELEGATED group {gid} — charter: {charter}",
           f"  status: `{g['status']}`"]
    if str(g["status"]) == "delivered":
        bricks = db.deliverables(conn, problem=str(g["problem"]),
                                 group_id=int(gid))
        if bricks:
            names = ", ".join(f"`{b['slug']}`" for b in bricks)
            out.append(f"  delivered, citable now: {names}")
        else:
            out.append("  delivered, but marked NO deliverable — nothing "
                       "to cite; check what it landed before building on it")
        out += _delivered_programme_companion(conn, str(g["problem"]),
                                              int(gid), attempts_dir)
        return out
    ret = conn.execute(
        "SELECT reason, payload FROM strategist_decisions"
        " WHERE produced_group_id = ?"
        "   AND decision_kind = 'ReturnToParent'"
        " ORDER BY id DESC LIMIT 1", (int(gid),)).fetchone()
    if ret is None:
        return out
    flavour = ""
    try:
        flavour = str(json.loads(ret["payload"] or "{}").get("flavour") or "")
    except (TypeError, ValueError):
        pass
    if flavour:
        out.append(f"  handed back: `{flavour}`")
    if flavour == "amend":
        try:
            proposed = str(json.loads(ret["payload"] or "{}").get(
                "proposed_charter") or "")
        except (TypeError, ValueError):
            proposed = ""
        if proposed:
            out.append(f"  it proposes instead: {proposed}")
    # Whole: a returned charter's post-mortem is why the delegation came
    # back, and it is the single input to deciding what to do next. One
    # per return, so the surface is bounded by count.
    reason = " ".join(str(ret["reason"] or "").split())
    if reason:
        out.append(f"  post-mortem: {reason}")
    return out


def _delivered_programme_companion(conn: sqlite3.Connection, problem: str,
                                   gid: int,
                                   attempts_dir: "Path | None",
                                   ) -> list[str]:
    """Write `PROGRAMME_G<gid>.md` beside Context.md and return the
    pointer lines. Best-effort: no rev (delivered before writing one)
    or no attempts_dir (worker-facing render) → no pointer, silently."""
    if attempts_dir is None:
        return []
    from ...state import programme as _programme
    rev = _programme.current_rev(conn, problem, int(gid))
    if rev is None:
        return []
    name = f"PROGRAMME_G{int(gid)}.md"
    body = str(rev["body"] or "").strip()
    text = (f"# Group {int(gid)} — final Programme (rev {rev['rev']})\n"
            "_The delivered group's last passed revision: its own argued"
            " account of what it established and why. Machine-copied per"
            " spawn._\n\n" + body + "\n")
    try:
        (attempts_dir / name).write_text(text, encoding="utf-8")
    except OSError:
        return []
    return [f"  its final Programme (rev {rev['rev']}) — the argued"
            f" account behind those bricks: `{name}`, beside this file"]


BATCHES_COMPANION = "BATCHES.md"


def _step_artifact_lines(conn: sqlite3.Connection,
                         row: sqlite3.Row) -> "list[str]":
    """What the step LEFT BEHIND, as opposed to how its worker exited.

    An `outcome` records the exit; the Strategist is instructed to read
    the scoreboard mechanically, and the two are routinely opposite.
    Measured 2026-08-11 (its own report): a step labelled `failed:<...>`
    had left a `proposed` strategy with one brick already proved and one
    open child, and a step labelled `exhausted:forward_no_new_goal` had
    created the group's deliverable node and linked it — so the wake
    "re-dispatched work that already landed and missed leaves that were
    ready", and "every real fact I acted on came from re-reading
    TREE.md". The operator hit the same misreading the same day tracing
    g7491 by hand.

    This is the lazy layer on purpose (companion file, no inline bytes):
    the numbers are all re-derivable by reading the DB or the tree, which
    is exactly this file's admission criterion. What the scoreboard keeps
    is what cannot be re-derived — outcome, attribution, the signature.
    """
    gid = row["produced_goal_id"] if "produced_goal_id" in row.keys() else None
    if not gid:
        return []
    try:
        strategies = list(conn.execute(
            "SELECT id, status FROM strategies WHERE goal_id = ?"
            " ORDER BY id", (int(gid),)))
    except (sqlite3.Error, TypeError, ValueError):
        return []
    if not strategies:
        return []
    out = ["", "#### what it left (current tree state)", ""]
    for s in strategies:
        subs = list(conn.execute(
            "SELECT g.slug, g.status FROM strategy_subgoals ss"
            " JOIN goals g ON g.id = ss.subgoal_id"
            " WHERE ss.strategy_id = ? ORDER BY ss.position", (s["id"],)))
        head = f"- strategy `s{s['id']}` — {s['status']}"
        if not subs:
            out.append(head + ", no sub-goals")
            continue
        done = sum(1 for x in subs if x["status"] == "proved")
        out.append(f"{head}, {done}/{len(subs)} sub-goals proved")
        out += [f"    - `{x['slug']}` — {x['status']}" for x in subs]
    return out


def _step_prose(row, empty: str = "(no brief)") -> str:
    """The step's own prose. `brief` for every kind that has one — and
    for a `Theorize`, which has none, the request itself: the objective
    and the situation are what a reader of this step needs, and they
    live in the payload because a decision carries one brief column and
    this kind writes two pieces of prose."""
    if str(row["decision_kind"]) != "Theorize":
        return str(row["brief"] or empty).strip()
    try:
        payload = json.loads(str(row["payload"]) or "{}")
    except (TypeError, ValueError):
        payload = {}
    parts = [f"**objective** — {str(payload.get('objective') or '').strip()}",
             f"**situation** — {str(payload.get('situation') or '').strip()}"]
    return "\n\n".join(parts)


def _theorize_result_lines(row) -> list[str]:
    """What the theory layer answered, on the one surface the Strategist
    reads a finished batch from.

    A `Theorize` step has no landed slug and no produced goal, so every
    attribution line below it renders nothing — and without this the
    scoreboard would show `outcome=success` over a blank step, which is
    the shape a reader treats as "it did not really happen". The two
    roads say different things and both are actionable: an accepted
    document names its PATH (read it; it is under the Project's shelf
    and the next wake's `## Notes on this problem` lists it), a refused
    one names the refusal and the verdict, which is the evidence the
    next request on the same wall is written against."""
    try:
        payload = json.loads(str(row["payload"]) or "{}")
    except (TypeError, ValueError):
        payload = {}
    objective = " ".join(str(payload.get("objective") or "").split())
    if len(objective) > 300:
        objective = objective[:300].rstrip() + "…"
    out = [f"  THEORY request — objective: {objective}"
           if objective else "  THEORY request"]
    detail = str(row["outcome_detail"] or "").strip()
    outcome = str(row["outcome"] or "")
    if outcome.startswith("success"):
        out.append(f"  document: `{detail}`" if detail else
                   "  accepted, but no path was recorded — grep "
                   "`_docs/agent/` for this group's newest document")
    elif detail:
        if len(detail) > 1200:
            detail = detail[:1200].rstrip() + "…"
        out.append(f"  {detail}")
    else:
        out.append("  no document came back and no reason was recorded")
    return out


def _prose_label(decision_kind: "str | None") -> str:
    """What to CALL a decision's prose when showing it back to the agent.

    One column, three contracts (`strategist._parse_one`): an Inject's
    prose is the `proof` that settles its brick; a Delegate's is the
    `charter` a new group must settle (2026-08-19 reshape — its old key
    `brief` now names the optional guidance hand-off). They share the
    DB column `brief` because a decision carries one piece of prose —
    but echoing the COLUMN name at the agent teaches the wrong field
    name, and the agent writes back what it was shown. That is the
    whole mechanism by which a 2026-08-11 rename of the wire field kept
    costing rejected batches into 2026-08-14: the spec moved, and every
    surface that still spelled it the old way taught the old way.
    """
    if decision_kind == "Inject":
        return "proof"
    if decision_kind == "Delegate":
        return "charter"
    return "brief"


def _bucket(step: dict) -> str:
    """Which of the three unfinished-step readings this step is: work of
    yours that MOVES ('run'), work of yours that no worker holds any
    more ('park'), or a line the OWNER opened beside yours ('owner').

    One function so the inline scoreboard and the `BATCHES.md` companion
    cannot disagree about a step — the disease this whole section keeps
    paying for (SP7 2026-09-03)."""
    if step.get("owner_line"):
        return "owner"
    return "run" if step["running"] else "park"


def _owner_opened_lines(steps: "list[dict]") -> list[str]:
    """The owner's own line, one per group. Deliberately NOT under "do
    not re-dispatch": there is nothing here for the reader to
    re-dispatch, and reading it as its own in-flight work is what froze
    union_closed's top group for two hours (owner ruling 2026-09-03)."""
    return [f"_{str(r['produced_ref'] or 'A group').capitalize()} was"
            " opened by the owner; it runs independently of your line —"
            " its delivery will reach you as a batch-done. Do not wait"
            " for it._"
            for r in steps]


def _write_batches_companion(conn: sqlite3.Connection,
                             attempts_dir: "Path | None",
                             order: "list[str]",
                             grouped: "dict[str, list[sqlite3.Row]]",
                             step_idx,
                             open_steps: "list[dict] | None" = None,
                             ) -> bool:
    """`BATCHES.md` — every completed step's brief, reply, and what it left.

    The inline scoreboard used to carry both bodies cut at 1200 bytes, and
    SG briefs run 1.2-9.5KB, so the cut landed mid-sentence — once on the
    exact line the Adversary had criticised (2026-08-02 feedback). An
    arbitrary truncation is the worst of the two options: it costs the
    budget of a long quotation and delivers the reliability of a short one.

    Lazily loaded, so there is nothing to truncate (operator ruling): the
    same pattern as `CATALOG.md` / `LESSONS.md` / `PAST_*.md`. What stays
    inline is what cannot be re-derived by reading a file — outcome,
    attribution, the landed signature."""
    if attempts_dir is None:
        return False
    # Same snapshot-disclosure pattern as CATALOG.md / TREE.md (the one
    # snapshot file that carried NO stamp — autopsy 2026-08-24).
    from datetime import datetime, timezone
    _taken = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    lines = ["# Completed Inject batches — full proofs and replies",
             f"_Machine-generated per spawn; snapshot taken {_taken} — "
             "in-flight statuses move while you work (ask the record "
             "live: `inspect({\"decl\": ...})`). The inline"
             " `## Completed Inject batches` section carries the"
             " scoreboard; the untruncated text lives here._", ""]
    # Unfinished batches first, IN FULL (owner ruling 2026-08-22: lazy
    # surfaces don't truncate — inline carries existence + pointer,
    # the substance lives here where inspect reads it by section).
    # Cross-group included: sub-groups see each other by design.
    # Three headings, not one. A step whose product the Strategist
    # parked is not running, and filing it under `## In flight` says the
    # false thing at greater length (SP7 2026-09-03); a group the OWNER
    # opened is running but on the owner's line, and `## In flight` is
    # the roster of the reader's OWN dispatched work (owner ruling
    # 2026-09-03 — `db._NOT_HUMAN_OPENED`).
    for key, head in (("run", "In flight"), ("park", "Parked, no worker"),
                      ("owner", "Opened by the owner")):
        by_batch: "dict[str, list[dict]]" = {}
        for r in (open_steps or []):
            if _bucket(r) == key:
                by_batch.setdefault(str(r["batch_id"]), []).append(r)
        for bid, steps in by_batch.items():
            lines.append(f"## {head} — batch `{bid[:8]}` "
                         f"(group {steps[0]['grp']})")
            lines.append("")
            for r in steps:
                if key == "owner":
                    tgt = (f"{r['produced_ref']}, opened by the owner"
                           " — it runs independently of your line")
                elif str(r["decision_kind"]) == "Theorize":
                    tgt = "a question for the theory layer"
                elif r["target_slug"]:
                    tgt = (f"target `{r['target_slug']}` "
                           f"({r['target_status']})")
                else:
                    tgt = "mint (a new brick from the brief)"
                if key == "park" and r["produced_ref"]:
                    tgt += (f" — produced {r['produced_ref']}"
                            f" `{r['produced_slug'] or '?'}`, now"
                            f" {r['produced_status']}; yours to reopen,"
                            f" re-dispatch or leave")
                lines += [f"### {r['decision_kind']} — {tgt}", "",
                          _step_prose(r), ""]
    for bid in order:
        lines.append(f"## Batch `{bid[:8]}`")
        lines.append("")
        for r in sorted(grouped[bid], key=step_idx):
            lines.append(f"### step {step_idx(r)} — outcome"
                         f" `{r['outcome'] or '(none)'}`")
            if r["landed_slug"]:
                lines.append(f"landed `{r['landed_slug']}`"
                             f" — `{r['landed_path'] or '?'}`")
            lines += _step_artifact_lines(conn, r)
            lines += ["", f"#### {_prose_label(r['decision_kind'])}", "",
                      _step_prose(r, empty="(none)"), ""]
            detail = str(r["outcome_detail"] or "").strip()
            if detail:
                lines += ["#### worker reply", "", detail, ""]
    try:
        (attempts_dir / BATCHES_COMPANION).write_text(
            "\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        return False
    return True


def _section_inject_batch_outcomes(conn: sqlite3.Connection,
                                   problem: str,
                                   workspace: "Path | None" = None,
                                   group_id: "int | None" = None,
                                   attempts_dir: "Path | None" = None,
                                   ) -> list[str]:
    """Surface every Inject batch on this problem that completed since
    the last Strategist commit (`last_strategist_at` ratchet — see
    `db.unacknowledged_inject_batches`).

    Emitted on ANY trigger when unack batches exist, not gated on
    `trigger_kind='inject_batch_done'`. Rationale: `_maybe_enqueue_
    inject_batch_done` does not advance `last_strategist_at`; a
    concurrent Strategist invocation under a different trigger (e.g.
    pending_review) can commit between batch completion and the queued
    inject_batch_done Strategist popping — that commit advances the
    ratchet and the queued inject_batch_done call no longer recognises
    the batch as unack. By always surfacing here, whichever Strategist
    runs first sees the batch and gets a chance to act on it. Acking
    via the ratchet still prevents double-processing across calls.

    Per-step "landed" line: `produced_goal_id` (backfilled by the
    Forward commit / redispatch target) resolves each step to the decl
    that actually exists — kernel truth, not the Strategist's past
    intent. The Strategist repeatedly reported having to guess which
    decl a `success` step landed as (feedback 2026-07-04, 30+ entries);
    an earlier docstring claimed attribution was impossible, which
    predates the `produced_goal_id` column.
    """
    # Worker declines since the last wake (user call 2026-07-19): the
    # mathematical WHY of a mid-flight decline (parent_needs_fix
    # counterexamples, no_progress / circularity analyses) lived only in
    # per-goal surfaces, so a cousin branch re-invented a refuted
    # statement before any steering surface ever showed it (b6_1
    # growth_exponent re-mint). Rendered on the batch scoreboard — the
    # one wall the strategist already reads — bounded to 5 entries.
    decline_lines = _recent_decline_lines(conn, problem)
    batch_ids = db.unacknowledged_inject_batches(conn, problem, group_id)
    # WORK STILL RUNNING IS NOT WORK THAT VANISHED. This section lists
    # batches that have fully terminated, so a batch with a spawn still
    # in flight appears nowhere — and "in flight" then reads exactly
    # like "lost". Both readers of this section paid for that: the
    # Strategist re-dispatched what was already running, and the judge
    # spent a whole round reconstructing chronology by hand (08-12/13,
    # the largest cluster in that week's feedback). One line, from the
    # rows the DB already has.
    #
    # …AND WORK THAT IS PARKED IS NOT WORK THAT IS RUNNING. The roster
    # was `outcome IS NULL`, which a parked product satisfies forever
    # (`db.open_batch_steps` carries the whole autopsy), so the two
    # states shared one line that only ever named the running one.
    try:
        open_steps = db.open_batch_steps(conn, problem)
    except sqlite3.OperationalError:
        open_steps = []
    # Own-group hashes only (2026-08-18 context diet): a mature run had
    # ~60 problem-wide in-flight batch ids inlined here, ~1.6KB of hex
    # the reader cannot act on — the actionable fact is "don't
    # re-dispatch MINE"; other groups' work needs a count, not a roster.
    # `group_id=None` (top-group / legacy callers) keeps the full list.
    mine = [r for r in open_steps
            if group_id is None or r["grp"] == group_id]
    # …AND WORK THE OWNER OPENED IS NOT THE READER'S WORK. A person's
    # Delegate is filed under the parent group and its produced group is
    # active, so it satisfied every "still running, do not re-dispatch"
    # test — and the parent read a line it never dispatched as a reason
    # to wait (owner ruling 2026-09-03; union_closed 691/693).
    handed = [r for r in mine if _bucket(r) == "owner"]
    running_batches: "dict[str, int]" = {}
    for r in mine:
        if _bucket(r) == "run":
            running_batches[r["batch_id"]] = (
                running_batches.get(r["batch_id"], 0) + 1)
    other_n = len({r["batch_id"] for r in open_steps
                   if _bucket(r) == "run"}) - len(running_batches)
    in_flight = [f"`{b[:8]}` ({n} step(s))"
                 for b, n in running_batches.items()]
    others_note = (f" (+{other_n} other groups' batch(es) also in flight)"
                   if other_n > 0 else "")
    # A parked step names its product and its status: the reader has to
    # be able to tell WHICH goal it parked without a second lookup, and
    # the fact that no wake is coming for it is the actionable half.
    parked = [f"`{r['batch_id'][:8]}` → {r['produced_ref']}"
              f" `{r['produced_slug'] or '?'}` {r['produced_status']}"
              + (f" since {str(r['produced_at'])[:19]}"
                 if r["produced_at"] else "")
              for r in mine
              if _bucket(r) == "park" and r["produced_ref"]]
    parked_line = (
        "_Parked, NOT running — no worker exists for these; their step "
        "has no outcome because you parked what it produced, not "
        "because it is still computing. No batch-done wake is coming: "
        "reopening, re-dispatching or leaving them parked is your call. "
        + ", ".join(parked) + "._") if parked else ""
    # WHAT the unfinished batches contain rides the LAZY companion in
    # full (owner ruling 2026-08-22: lazy surfaces don't truncate;
    # inline carries existence + the pointer). "Don't re-dispatch mine"
    # was unactionable from a bare hash — checking one proposed Inject
    # for duplication took a four-source inference (46+2 self-reports).
    pointer = (" Each one's targets and full briefs: "
               f"`{BATCHES_COMPANION}`, the `## In flight` sections."
               if running_batches else "")
    owner_lines = _owner_opened_lines(handed)
    if not batch_ids:
        if in_flight or other_n or parked or owner_lines:
            _write_batches_companion(conn, attempts_dir, [], {},
                                     lambda r: 0, open_steps=open_steps)
            head = ("## Dispatched, still running" if in_flight or other_n
                    else "## Dispatched, now parked" if parked
                    else "## Open lines")
            body = ([] if not (in_flight or other_n) else
                    ["Not finished, and therefore not below: "
                     + (", ".join(in_flight) or "(none of yours)")
                     + others_note
                     + ". Their outcomes reach you on the batch-done "
                       "wake — do not re-dispatch them." + pointer, ""])
            return ([head, ""] + body
                    + ([parked_line, ""] if parked_line else [])
                    + ([*owner_lines, ""] if owner_lines else [])
                    + decline_lines)
        return decline_lines
    out = ["## Completed Inject batches (newest first)", ""]
    if in_flight or other_n:
        out += ["_Still running, so not listed below: "
                + (", ".join(in_flight) or "(none of yours)")
                + others_note + "._" + pointer, ""]
    if parked_line:
        out += [parked_line, ""]
    if owner_lines:
        out += [*owner_lines, ""]
    placeholders = ",".join("?" * len(batch_ids))
    # Inject rows only: every wake's decisions share the batch_id, so
    # ConfirmShelve/EmitDirective siblings used to render as brief-less
    # phantom "step 0" rows (agent_feedback 2026-07-11..13).
    rows = list(conn.execute(
        f"SELECT d.id, d.batch_id, d.brief, d.payload, d.outcome,"
        f" d.outcome_detail, d.updated_at, d.produced_kind,"
        f" d.decision_kind, d.produced_group_id, d.produced_goal_id,"
        f" g.slug AS landed_slug, g.status AS landed_status,"
        f" g.is_deliverable AS landed_marked,"
        f" g.statement AS landed_statement, g.lean_path AS landed_path"
        f" FROM strategist_decisions d"
        f" LEFT JOIN goals g ON g.id = d.produced_goal_id"
        f" WHERE d.batch_id IN ({placeholders})"
        f"   AND d.decision_kind IN {db._BATCH_KINDS_SQL}"
        f" ORDER BY MAX(d.updated_at) OVER (PARTITION BY d.batch_id) DESC,"
        f"          d.batch_id, d.id",
        batch_ids,
    ))
    grouped: dict[str, list[sqlite3.Row]] = {}
    order: list[str] = []
    for r in rows:
        bid = str(r["batch_id"])
        if bid not in grouped:
            grouped[bid] = []
            order.append(bid)
        grouped[bid].append(r)

    def _step_idx(r: sqlite3.Row) -> int:
        try:
            return int(json.loads(str(r["payload"]) or "{}")
                       .get("step_index", 0))
        except (ValueError, TypeError):
            return 0

    lazy = _write_batches_companion(conn, attempts_dir, order, grouped,
                                    _step_idx, open_steps=open_steps)
    if lazy:
        out += [f"Full proof/brief and worker reply per step:"
                f" `{BATCHES_COMPANION}`, beside this file.", ""]

    for bid in order:
        steps = grouped[bid]
        steps.sort(key=_step_idx)
        out.append(f"### Batch `{bid[:8]}` ({len(steps)} steps)")
        out.append("")
        for r in steps:
            idx = _step_idx(r)
            # This is the batch the wake is ABOUT — show its feedback in
            # full (generous cap, not the short recap truncation used by
            # `_section_failure_replay`) so the Strategist can compare what
            # it briefed against what actually came back (#4).
            brief = (r["brief"] or "").strip()
            if len(brief) > 1200:
                brief = brief[:1200].rstrip() + "…"
            outcome_text = r["outcome"] or "(no outcome)"
            out.append(f"- **step {idx}** outcome=`{outcome_text}`")
            if str(r["decision_kind"]) == "Theorize":
                out += _theorize_result_lines(r)
                out.append("")
                continue
            if str(r["decision_kind"]) == "Delegate":
                # v35 — a delegated burden's result is the whole reason
                # the parent was woken. Without this it reached the
                # Strategist only as a daemon log line: the parent read
                # "a batch completed" and could not see which bricks it
                # may now cite, nor why a charter came back.
                out += _delegate_result_lines(conn, r, attempts_dir)
                out.append("")
                continue
            kind = str(r["produced_kind"] or "")
            # MarkDeliverable is this turn's to emit since the wake
            # split retired (2026-08-11), and verify_decision bounces
            # a second mark on the same goal — so say which of your
            # own landed bricks is already marked, here, where the
            # batch is being read. Scope is deliberate: a wake marks
            # against the batch it just closed, not against every
            # proved node the problem ever accumulated.
            def _landed(row=r) -> str:
                s = f"status={row['landed_status']}"
                try:
                    marked = int(row["landed_marked"] or 0)
                except (IndexError, KeyError, TypeError, ValueError):
                    marked = 0
                return s + (", already a deliverable" if marked else "")

            if r["landed_slug"]:
                # Full signature off the landed file when reachable
                # (07-29: the DB statement is the RESULT TYPE for a def
                # — `— Prop` — which cannot establish arity; the arity
                # dispute fueled a five-round verdict war).
                stmt = ""
                if workspace is not None and r["landed_path"]:
                    try:
                        from ..context import _catalog_signature
                        stmt = " ".join((_catalog_signature(
                            workspace, str(r["landed_path"]),
                            str(r["landed_slug"])) or "").split())
                    except Exception:  # noqa: BLE001 — cosmetic only
                        stmt = ""
                if not stmt:
                    stmt = " ".join(str(r["landed_statement"] or "").split())
                # Whole, no cut. This signature is the EVIDENCE for
                # "is this what I briefed" — the judgement the regex
                # used to pretend to make (removed 2026-08-07). A
                # signature clipped at 300 chars is exactly the state in
                # which a reader cannot tell, which is how the framework
                # ended up guessing on its behalf in the first place.
                # v32 attribution: say HOW the artifact relates to the
                # brief instead of making the Strategist guess (#3 —
                # the success-without-landing / renamed-landing pair).
                if kind == "reuse":
                    out.append(
                        f"  REPOINTED to existing goal "
                        f"`{r['landed_slug']}` "
                        f"({_landed()}) — nothing new "
                        f"was minted; your statement matched it")
                elif kind == "alias":
                    out.append(
                        f"  landed as ALIAS: `{r['landed_slug']}` "
                        f"({_landed()})"
                        + (f" — `{stmt}`" if stmt else "")
                        + " — an existing decl carries the content; "
                          "cite this slug")
                elif kind == "redispatch":
                    settled_note = (
                        " — CAUTION: outcome=`superseded` means the "
                        "target settled via ANOTHER route, not your "
                        "briefed decomposition"
                        if str(r["outcome"] or "") == "superseded"
                        else "")
                    out.append(
                        f"  redispatch of goal `{r['landed_slug']}` "
                        f"({_landed()})" + settled_note)
                else:
                    # Delivered-vs-briefed is YOUR call, not a regex's
                    # (user ruling 2026-08-07: no mechanical checking of
                    # natural language). What stood here searched the
                    # brief's prose for the landed slug and cried
                    # RETARGETED when it missed — so the framework's own
                    # convention (briefs name the FILE `L_<slug>`, the
                    # theorem lands as `<slug>`) tripped it on correct
                    # work, 24 complaints in one run, each telling the
                    # reader to diff a brick that matched its brief. It
                    # was a patch over a different defect anyway: the
                    # Strategist could not judge for itself because both
                    # artifacts reached it truncated. They no longer do —
                    # the signature below is whole and the brief is whole
                    # in BATCHES.md, so the comparison is available to
                    # the one reader who can actually read.
                    out.append(
                        f"  landed: `{r['landed_slug']}` "
                        f"({_landed()})"
                        + (f" — `{stmt}`" if stmt else ""))
            elif str(r["outcome"] or "") in ("success", "proved"):
                out.append(
                    "  landed: (nothing attributed to this step — the "
                    "brick may have landed renamed/merged; grep "
                    "CATALOG.md before treating it as landed)")
            if r["landed_path"]:
                # Where the landed idioms live. The strategist had to
                # hunt for `proofs/L_line_param.lean` to confirm a
                # tactic was available (2026-08-02); naming the path
                # makes that one hop instead of a search.
                out.append(f"  file: `{r['landed_path']}`")
            detail = (r["outcome_detail"] or "").strip()
            _label = _prose_label(r["decision_kind"])
            if lazy:
                out.append(
                    f"  {_label} + reply: `{BATCHES_COMPANION}` step {idx}"
                    if detail else
                    f"  {_label}: `{BATCHES_COMPANION}` step {idx}")
            else:
                out.append(f"  {_label}: {brief}")
                if detail:
                    if len(detail) > 1200:
                        detail = detail[:1200].rstrip() + "…"
                    out.append(f"  why: {detail}")
        out.append("")
    out.extend(decline_lines)
    return out


_DECLINE_REASONS_SURFACED = (
    "parent_needs_fix", "agent_declined", "no_progress",
    "circular_decomposition",
)

#: Per-decline inline budget. It was 250, head-truncated, against a
#: measured distribution (196 declines) of median 1,250 / p90 2,348 /
#: max 2,987 — so 79% of them were cut, and cut at the head, which is
#: where the diagnosis lives and NOT where the ask does. Live case
#: 2026-08-11: a worker found a sub-goal whose locked signature dropped
#: a hypothesis the Argument's own Step 3 needs, wrote 1,095 characters
#: ending "please re-state this sub-goal with (hUW : …) added", and the
#: Strategist received the first 250, stopping mid-expression.
#:
#: Inline rather than a companion file, deliberately: a decline is not
#: reference material the Strategist looks up when it wants to — it is
#: evidence that contradicts the batch it is about to write, and it
#: matters in exactly this wake. The same reasoning already keeps the
#: newest attempt's progress note inline ("agents miss companion
#: files, so the inline section is the canonical surface", agent/
#: context.py). 2,000 covers everything up to p90 whole; the writer
#: side is unbounded, so past that both ENDS survive and the middle —
#: the derivation, the least load-bearing third — is what goes.
DECLINE_INLINE_CHARS = 2000


def _elide_middle(text: str, budget: int) -> str:
    """Keep both ends of `text`, drop the middle, say how much went.

    A head-only cut hides whatever the writer put last, and agents put
    the ask last: a conclusion, a request, a "so do X instead". Sibling
    of `lsp/gateway._echo_removed`, which does the same for the region
    an edit removed — the shape recurs because the failure does.
    """
    if len(text) <= budget:
        return text
    half = (budget - 40) // 2
    return (f"{text[:half].rstrip()} … [{len(text) - 2 * half} chars "
            f"elided] … {text[-half:].lstrip()}")


def _recent_decline_lines(conn: sqlite3.Connection,
                          problem: str, k: int = 5) -> list[str]:
    """`### Worker declines since your last wake` — goal slug + the
    decline's own reasoning (proposal_md carries the math; the
    failure_detail for a decline is just the routing enum). Windowed to
    dead_attempts newer than the problem's last strategist decision
    (first wake: last 24h of rows), capped at `k`."""
    try:
        since = conn.execute(
            "SELECT MAX(created_at) FROM strategist_decisions"
            " WHERE problem = ?", (problem,)).fetchone()[0]
        marks = ",".join("?" * len(_DECLINE_REASONS_SURFACED))
        sql = (f"SELECT da.failure_reason, da.failure_detail,"
               f" da.proposal_md, g.slug"
               f" FROM dead_attempts da JOIN goals g ON g.id = da.target_id"
               f" WHERE da.target_kind = 'Goal' AND g.problem = ?"
               f"   AND da.failure_reason IN ({marks})")
        args: list = [problem, *_DECLINE_REASONS_SURFACED]
        if since:
            # >= not >: a decline landing the same clock tick as the
            # wake's own commit must not vanish (Windows timestamp
            # granularity); an exact-boundary repeat is harmless.
            sql += " AND da.ts >= ?"
            args.append(since)
        rows = conn.execute(
            sql + " ORDER BY da.id DESC LIMIT ?", (*args, k)).fetchall()
    except sqlite3.OperationalError:
        return []
    if not rows:
        return []
    out = ["### Worker declines since your last wake",
           "_A decline's reasoning is evidence about statements in your"
           " roadmap — a refuted formulation stays refuted under a new"
           " slug._", ""]
    for r in rows:
        why = " ".join((r["proposal_md"] or r["failure_detail"] or "")
                       .replace("--", " ").split())
        out.append(f"- `{r['slug']}` [{r['failure_reason']}]: "
                   f"{_elide_middle(why, DECLINE_INLINE_CHARS)}")
    out.append("")
    return out


def _section_pending_reopens(conn: sqlite3.Connection,
                             problem: str,
                             trigger_kind: str) -> list[str]:
    """Surface shelved goals whose promised follow-up batch just landed.

    Promise model: when Strategist ships a decision array `[ConfirmShelve(G),
    Inject(F1), Inject(F2), ...]` it's implicitly saying "I'm shelving G
    because I'm injecting F1/F2 to unblock it; wake me to re-evaluate G
    when they're done". `_commit_one` writes the shared `batch_id` on
    every row in the array, so the framework can later recover the
    promise by querying ConfirmShelve rows whose batch siblings (Inject
    rows) have all reached terminal `outcome`.

    Gated on `trigger_kind == 'inject_batch_done'` — that's the wake
    fired when a batch's last Inject reaches terminal. Other triggers
    (routine / pending_review / first_launch) skip this section.

    Scoping rule (brouwer 2026-05-22 G2): pre-fix this section dumped
    *every* shelved goal in the problem on every inject_batch_done
    wake, causing Strategist to re-ConfirmShelve g2771 four times with
    no new evidence between calls. Post-fix it lists ONLY goals whose
    own promised batch (the one cited by their promise-bearing
    ConfirmShelve — the first since the goal's latest Reopen) is now
    complete — i.e., goals where the Inject(s) Strategist explicitly
    designed to address them have produced their outcomes and there's
    now genuine new evidence to re-evaluate.

    Fortuitous unblock (a Forward designed for an unrelated batch
    happens to make a shelved goal provable) is handled separately by
    the G1 dedupe revival pass (`find_shelved_revivals_for_forward` →
    `_revive_shelved_alias`) — no need to re-surface unrelated
    shelved goals here.

    Per surfaced goal:
      * the promise-bearing ConfirmShelve's `reason` (the explicit
        promise);
      * the now-complete promised batch's Inject decisions + their
        produced goals (so Strategist sees exactly what landed).
    """
    if trigger_kind not in ("inject_batch_done", "stall"):
        # 'stall' rides along (v43 identity split): T4 rescues used to
        # BE inject_batch_done wakes, and a stalled group's pending
        # promises are often exactly what the rescue must adjudicate.
        return []

    # Find shelved goals whose PROMISE-BEARING ConfirmShelve was
    # committed in a batch whose every sibling Inject row has `outcome
    # IS NOT NULL` (batch fully terminal). Promise-bearing = the FIRST
    # ConfirmShelve since the goal's latest Reopen (or first ever) —
    # that's the one the verifier forced to pair with a compensating
    # Inject. Later re-confirms are terminal answers, not new promises:
    # every wake's decisions share one batch_id, so a standalone
    # re-confirm co-batched with an UNRELATED forced-advance Inject
    # used to read as a fresh pairing and re-arm this section every
    # wake (agent_feedback 2026-07-14, goal 5941 — 15 reports).
    # A promise waits on WORK. The exclusion below used to read "any
    # Inject/Delegate sibling with outcome NULL", which a PARKED product
    # satisfies forever (P13 4284 — see `db.open_batch_steps`): the
    # promise never came due, so the goal waiting on it never surfaced
    # here again. Only a RUNNING sibling is still worth waiting for; a
    # batch whose remainder is parked is as done as it will get without
    # a decision. Re-surfacing is bounded by the newer-ConfirmShelve /
    # Reopen guard below — once, until the Strategist answers.
    running = sorted({s["batch_id"] for s in db.open_batch_steps(conn, problem)
                      if s["running"]}) or [""]
    _ph = ",".join("?" * len(running))
    rows = list(conn.execute(
        f"""
        WITH latest_cs AS (
            SELECT g.id AS goal_id, g.slug AS goal_slug,
                   g.updated_at AS shelved_at,
                   MIN(d.id) AS cs_decision_id
            FROM goals g
            JOIN strategist_decisions d
              ON d.target_id = CAST(g.id AS TEXT)
             AND d.decision_kind = 'ConfirmShelve'
             AND d.problem = g.problem
             AND d.batch_id IS NOT NULL
             AND d.id > COALESCE((
                 SELECT MAX(r.id) FROM strategist_decisions r
                 WHERE r.problem = g.problem
                   AND r.target_id = CAST(g.id AS TEXT)
                   AND r.decision_kind = 'Reopen'
             ), 0)
            WHERE g.problem = ? AND g.status = 'shelved'
            GROUP BY g.id
        )
        SELECT lcs.goal_id, lcs.goal_slug, lcs.shelved_at,
               cs.id AS cs_id, cs.reason AS cs_reason,
               cs.batch_id AS cs_batch_id
        FROM latest_cs lcs
        JOIN strategist_decisions cs ON cs.id = lcs.cs_decision_id
        -- exclude batches still RUNNING: an Inject OR Delegate sibling
        -- whose work is moving means the promise hasn't landed yet
        -- ('Delegate' joined the promise-carrier set 2026-08-06,
        -- mirroring transitions._awaiting_promised_batch: a park
        -- waiting on a sub-group's charter surfaced as "due" the
        -- moment the batch's mints resolved, prompting a re-park
        -- adjudication of a non-question)
        WHERE cs.batch_id NOT IN ({_ph})
        AND EXISTS (
            -- and the batch must contain at least one promise carrier —
            -- pure ConfirmShelve+Reopen batches carry no promise to
            -- wait on (a shelve batched with only a Delegate IS a
            -- promise: the group's result is what it waits for)
            SELECT 1 FROM strategist_decisions sib
            WHERE sib.batch_id = cs.batch_id
              AND sib.decision_kind IN ('Inject', 'Delegate')
        )
        AND NOT EXISTS (
            -- and Strategist hasn't already addressed this completed
            -- batch with a newer ConfirmShelve / Reopen on the same
            -- goal (i.e., this surfacing has actually new
            -- information vs the last time we surfaced)
            SELECT 1 FROM strategist_decisions later
            WHERE later.problem = ?
              AND later.target_id = CAST(lcs.goal_id AS TEXT)
              AND later.decision_kind IN ('ConfirmShelve', 'Reopen')
              AND later.id > cs.id
        )
        ORDER BY lcs.shelved_at DESC
        LIMIT 12
        """,
        (problem, *running, problem),
    ))
    if not rows:
        return []

    out = [
        "## Pending reopen-promises",
        "",
        "Shelved goal(s) whose ConfirmShelve batch promised a follow-up "
        "Inject set — and that follow-up set has now fully landed. "
        "Strategist's own batch-time promise is the trigger; this is "
        "the moment to evaluate `Inject(target_goal_id=<id>, "
        "proof=...)` vs a further mint vs a second "
        "`ConfirmShelve` with a refined promise. Fortuitous unblock by "
        "unrelated Forwards is handled "
        "automatically by the G1 dedupe revival pass — no need to "
        "re-surface unrelated shelved goals here.",
        "",
    ]
    for r in rows:
        gid = int(r["goal_id"])
        slug = str(r["goal_slug"])
        shelved_at = str(r["shelved_at"])[:19]
        # Whole: this is the predecessor's own account of WHY the goal
        # was shelved, and it has no companion to fall back to — a
        # judge noted its post-mortem survived only because charter.md
        # happened to carry a second copy. One row per shelved goal, so
        # the surface is bounded by count, not by clipping each entry.
        reason = str(r["cs_reason"] or "").strip()
        batch_id = str(r["cs_batch_id"])

        out.append(f"### `{slug}` (id={gid}, shelved {shelved_at})")
        out.append(f"shelve reason: {reason}" if reason
                   else "shelve reason: (empty)")
        # Pull what the promised batch actually produced.
        siblings = list(conn.execute(
            "SELECT d.id, d.brief, d.target_id, d.produced_goal_id,"
            " d.outcome, g.slug AS produced_slug, g.status AS produced_status"
            " FROM strategist_decisions d"
            " LEFT JOIN goals g ON g.id = d.produced_goal_id"
            " WHERE d.batch_id = ? AND d.decision_kind = 'Inject'"
            " ORDER BY d.id",
            (batch_id,),
        ))
        out.append(f"promised batch ({len(siblings)} Inject(s)):")
        for s in siblings:
            brief_head = (s["brief"] or "").strip().split("\n", 1)[0][:70]
            if s["produced_slug"] is not None:
                tail = (f"→ `{s['produced_slug']}` "
                        f"(status={s['produced_status']})")
            else:
                tail = f"→ outcome={s['outcome'] or 'pending'}"
            out.append(f"  - {brief_head}  {tail}")
        out.append("")
    return out


#: Freshness floor for the inline Active-goals tail (newest by id).
