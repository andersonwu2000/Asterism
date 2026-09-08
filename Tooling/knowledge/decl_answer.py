"""`decl` — the one `inspect` query answered from the run's own tables.

Every other query in `workspace_query` is a file read: a path, a glob,
a walk. This one is not. It asks the database what a name IS — the
statement, where it lives, whether it is proved, which strategy is
carrying it — and the file system only ever confirms what the record
already said. That is a different kind of answer with a different kind
of failure, and it is why this half moved out of `workspace_query`
(which stood at its size watermark carrying the note "next growth =
split, not a bump" through three bumps, all three of them `decl`).

The rule the whole module turns on: WHEN THE RECORD KNOWS, ASK THE
RECORD. `_wrapper_target` guessed a filename beside `Root.lean` while
`strategies.scratch_path` held the real one, and on 2026-09-06 a
Strategist and an Adversary spent a full round on a root whose complete
proof the tool reported as `<unreadable: No such file or directory>`.
`_strategy_gate_line` is the same rule for the question nobody could
answer that round — why a goal sits at `attempting` with everything
under it proved — which is likewise two columns away.

`workspace_query` reaches this module lazily, through its own `_q_decl`
dispatch entry, so the import edge runs one way: the path layer never
depends on the record layer.
"""
from __future__ import annotations

import re
from pathlib import Path

from .workspace_query import (_declared_problem, _problem_dir_of,
                              _read_text, workspace_of)


def _ws_rel(p: Path, ws: Path) -> str:
    """A workspace-relative posix path, or the absolute one if it lies
    outside — `relative_to` raising must never cost the whole answer."""
    try:
        return p.resolve().relative_to(ws.resolve()).as_posix()
    except (ValueError, OSError):
        return p.as_posix()


def _strategy_gate_line(strats: "list[dict]", goal_status: str) -> str:
    """Why a goal sits at `attempting` with everything under it proved.

    That was the one question the 2026-09-06 round turned on, and no
    tool answered it: the Strategist and the Adversary both reasoned
    from the tree shape, spent a full adversary round, and neither
    could see the two facts that settle it — the strategy is
    `succeeded` and the goal has not been settled. Both are rows in
    this run's own tables. One line, from the record."""
    # The kernel-settled set comes from `transitions`, which declares it:
    # a hand-spelled copy here is a second answer to "what counts as
    # settled" and goes stale the day the vocabulary moves.
    from ..state.transitions import GOAL_HARD_TERMINALS
    if goal_status in GOAL_HARD_TERMINALS:
        return ""
    done = [s for s in strats if s["status"] == "succeeded"]
    if not done:
        return ""
    word = "strategy" if len(done) == 1 else "strategies"
    names = ", ".join(f"s{s['id']}" for s in done)
    return (f"    {word} {names}: succeeded; goal: {goal_status} — "
            f"promotion pending or unsettled. The proof is written and "
            f"the goal is waiting on the framework (verify / promotion, "
            f"or an unfinished step above it), NOT on a missing proof.")


#: What a goal is doing when nothing needs explaining: BFS will pick it
#: up, a worker holds it, or the kernel took it. Everything else — a
#: park, a review queue, a refutation, a freeze — is a state somebody
#: DECIDED, and the decision left a row.
_MOVING_OR_DONE = frozenset({"open", "attempting", "proved"})

#: Per-part budget for the reason block. Generous when the caller typed
#: the whole name (that is the audit, and the decisive text is usually
#: an agent's paragraph, not a sentence — the Strategist's own decline
#: digest measured median 1,250 / p90 2,348), tight on a substring
#: shortlist: a shortlist is for picking a name, not for reading six
#: post-mortems, and six full ones would eat the 12,000-char answer the
#: signatures also have to fit in.
_REASON_CHARS = 1_000
_REASON_CHARS_SHORTLIST = 300


def _elide_middle(text: str, budget: int) -> str:
    """Keep both ends of `text`, drop the middle, say how much went.

    A head-only cut hides whatever the writer put LAST, and agents put
    the ask last: "so re-state this sub-goal with (hUW : …) added" is
    the sentence the reader needs. Sibling of `phase2_context/
    outcomes._elide_middle` and of `lsp/gateway.rpc._echo_removed`,
    which do the same for the Strategist's decline digest and for the
    region an edit removed — the shape recurs because the failure
    does."""
    if len(text) <= budget:
        return text
    half = (budget - 40) // 2
    return (f"{text[:half].rstrip()} … [{len(text) - 2 * half} chars "
            f"elided] … {text[-half:].lstrip()}")


def _prose(s: "str | None") -> str:
    """One line of an agent's own words. `--` goes because a decline is
    written as Lean comments (`-- decline: return_to_nl`) and the
    marker is transport, not reasoning — the same normalisation the
    Strategist's decline digest applies to the same column."""
    return " ".join(str(s or "").replace("--", " ").split())


def _reason_parts(conn, gid: int, status: str) -> "list[tuple[str, str]]":
    """WHY this goal is not proved, from the rows that know — the
    question `inspect`'s own description promised and never answered.

    Three tables hold three halves of it and the tool showed none:
    `strategist_decisions` carries the park (a ConfirmShelve's prose is
    the Strategist saying what would have to change), `goal_events` the
    transition that put the goal where it is, and `dead_attempts` the
    last worker's own account. On 2026-09-07 a Strategist audited
    g10944 through this query, got status + file + an elided statement,
    and had to go find `.drafts/backward_g10944_patch.lean` to learn
    that a `j = 0, M = 3` counterexample had refuted it; four hours
    later another one asked the same query about a shelved goal and was
    told nothing about the shelf at all.

    Returns `(head, prose)` pairs — never rendered text — because the
    per-part budget is not known until the answer knows how many
    declarations it is showing."""
    try:
        park = conn.execute(
            "SELECT actor, brief, reason, created_at"
            " FROM strategist_decisions"
            " WHERE target_id = ? AND decision_kind = 'ConfirmShelve'"
            " ORDER BY id DESC LIMIT 1", (gid,)).fetchone()
        event = conn.execute(
            "SELECT event, reason, at FROM goal_events"
            " WHERE goal_id = ? AND to_status = ?"
            " ORDER BY id DESC LIMIT 1", (gid, status)).fetchone()
        dead = conn.execute(
            "SELECT failure_reason, failure_detail, proposal_md, ts"
            " FROM dead_attempts WHERE target_id = ? AND target_kind = 'Goal'"
            " ORDER BY id DESC LIMIT 1", (gid,)).fetchone()
        n_dead = int(conn.execute(
            "SELECT COUNT(*) FROM dead_attempts"
            " WHERE target_id = ? AND target_kind = 'Goal'",
            (gid,)).fetchone()[0])
    except Exception:  # noqa: BLE001 — a DB that answers less, not none
        return []
    parts: "list[tuple[str, str]]" = []
    if park is not None:
        # `reason` is where a ConfirmShelve's prose lands and `brief`
        # where some kinds put theirs; take whichever this row has
        # rather than assuming the column.
        parts.append((
            f"parked by ConfirmShelve ({park['actor'] or 'strategist'}, "
            f"{str(park['created_at'])[:10]})",
            _prose(park["reason"] or park["brief"])))
    elif event is not None:
        parts.append((f"entered `{status}` by `{event['event']}` "
                      f"({str(event['at'])[:10]})", _prose(event["reason"])))
    if dead is not None:
        # `proposal_md` carries the mathematics (the counterexample, the
        # missing hypothesis); `failure_detail` for a decline is only
        # the routing enum, so it is the fallback and not the answer.
        parts.append((
            f"last of {n_dead} recorded attempt(s) "
            f"[{dead['failure_reason']}] ({str(dead['ts'])[:10]})",
            _prose(dead["proposal_md"] or dead["failure_detail"])))
    return parts


def _wrapper_target(ws: Path, lp: str, stok: str, strats: "list[dict]"
                    ) -> "tuple[list[str], str, str]":
    """Where `def slug := @…sNNN` actually points — from the RECORD.

    `strategies.scratch_path` is the framework's own answer and the
    only correct one. The guess it replaces — "`_strategy_sNNN.lean`
    beside the wrapper" — holds for a sub-goal, whose wrapper and
    scratch share `proofs/`, and fails for exactly the case that
    matters most: a ROOT's wrapper is `Problems/<p>/Root.lean` while
    its scratch is one directory down at `proofs/_strategy_sNNN.lean`.
    So `inspect({"decl": "main"})` answered `<unreadable: No such file
    or directory>` on the single document that held the complete root
    proof, and both seats built a round on the picture that left
    (2026-09-06, `Lab.even_sum_subsets`).

    Returns `(lines to emit, signature body, workspace-relative path)`;
    the last two are empty when nothing was readable, and the lines
    then name every path TRIED and what the record says instead — a
    miss whose message an agent can act on rather than believe."""
    rec = next((s for s in strats if f"s{s['id']}" == stok), None)
    cands: "list[Path]" = []
    if rec is not None and rec["scratch_path"]:
        cands.append(ws / rec["scratch_path"].replace("\\", "/"))
    # The old guess stays as a FALLBACK, not as the answer: a hand-built
    # or pre-migration row can carry an empty `scratch_path`, and losing
    # the sibling file in that case would trade one blind spot for
    # another.
    beside = (ws / lp).parent / f"_strategy_{stok}.lean"
    if beside not in cands:
        cands.append(beside)
    for cand in cands:
        stext = _read_text(cand)
        if not stext.strip() or stext.startswith("<unreadable:"):
            continue
        srel = _ws_rel(cand, ws)
        dm = re.search(
            r"(?m)^[ \t]*(?:@\[[^\]]*\][ \t]*)*"
            r"(?:noncomputable[ \t]+|private[ \t]+)*"
            r"(?:theorem|def|instance)[ \t]+" + stok + r"\b", stext)
        body = stext[dm.start():] if dm else stext
        return ([f"    wrapper of @{stok} — showing {srel}'s "
                 f"declaration:"], body, srel)
    tried = ", ".join(_ws_rel(c, ws) for c in cands)
    if strats:
        says = "this goal's strategies in the record: " + "; ".join(
            f"s{s['id']} [{s['status']}] "
            + (s["scratch_path"].replace("\\", "/")
               + (" (exists)"
                  if (ws / s["scratch_path"].replace("\\", "/")).is_file()
                  else " (not on disk)")
               if s["scratch_path"] else "no scratch_path recorded")
            for s in strats)
    else:
        says = "this goal has no strategy row in the record"
    return ([f"    wrapper of @{stok} — nothing readable at {tried}. "
             f"{says}."], "", "")


#: The columns every tier selects. One spelling, so a tier added later
#: cannot quietly answer with a narrower row than the renderer expects.
_COLS = ("SELECT id, slug, lean_path, statement, status, problem, "
         "alias_target_id FROM goals ")


def _tiered(conn, name: str, prob: "str | None"
            ) -> "tuple[list, bool]":
    """This problem's exact name, then this problem's substrings, then
    — only if nothing here matches — the rest of the run, LABELLED.

    Returns `(rows, foreign)`; `foreign` is True when the answer left
    the caller's problem, and the renderer says so.

    Two faults met on `decl S` (2026-09-07/08, p373 ×3). The first is
    that the local and the global search were ONE query each, `slug = ?
    OR slug LIKE ?`, so a local near-miss and a foreign near-miss were
    the same rank and the fallback fired on "nothing local" rather than
    on "nothing local matches this name". The second is that SQLite's
    `LIKE` is case-insensitive over ASCII: `%S%` matched `a_closed_form`
    and `a_inv_left_inverse` — the `s` inside `closed` and `inverse` —
    so a one-letter ask came back as six unrelated projects' theorems
    and none of this problem's. `INSTR` is the case-sensitive substring
    test, and slugs are snake_case by construction, so a capital in the
    query is a real constraint rather than noise.

    The tiers stop at the first that answers. A miss is a MISS: better
    "no declaration named 'S'" — the truth, since `S` here is a `Defs`
    definition and not a goal — than six neighbours from other
    problems."""
    tiers = []
    if prob:
        tiers.append(("WHERE problem = ? AND slug = ? ORDER BY slug LIMIT 6",
                      (prob, name), False))
        tiers.append(("WHERE problem = ? AND INSTR(slug, ?) > 0 "
                      "ORDER BY LENGTH(slug), slug LIMIT 6",
                      (prob, name), False))
    tiers.append(("WHERE slug = ? ORDER BY problem, slug LIMIT 6",
                  (name,), bool(prob)))
    tiers.append(("WHERE INSTR(slug, ?) > 0 "
                  "ORDER BY LENGTH(slug), problem, slug LIMIT 6",
                  (name,), bool(prob)))
    for where, args, foreign in tiers:
        rows = conn.execute(_COLS + where, args).fetchall()
        if rows:
            # `prob` set and every row from elsewhere is the only shape
            # that has to be disclosed: a global tier can still answer
            # with this problem's rows when `prob` is unknown.
            return rows, foreign and all(str(r["problem"]) != prob
                                         for r in rows)
    return [], False


def answer(q: dict, cwd: Path, deny) -> "list[str]":
    """Answered from the framework's own tables, not from a regex.

    The agent asks "what is `foo`" and gets the statement, where it
    lives and whether it is proved — three facts the shell could only
    approximate by grepping for a keyword at the start of a line."""
    name = str(q.get("decl") or "").strip()
    if not name:
        return ["give a declaration name"]
    ws = workspace_of(cwd)
    if ws is None:
        return ["cannot locate the workspace from here"]
    try:
        from ..state import db as _db
        conn = _db.connect_readonly(ws / "asterism.db")
    except Exception as exc:  # noqa: BLE001 — never fail the whole batch
        return [f"declaration index unavailable ({type(exc).__name__})"]
    # `gNNNN` is how TREE.md / Context.md label a goal — its row id, an
    # exact address; a slug is exact first, then substring: an agent
    # that typed the whole name wants THAT one, and burying it among six
    # near-misses is the same "answer is in there somewhere" failure the
    # CATALOG had.
    gid = re.fullmatch(r"g(\d+)", name)
    # Scope to the caller's problem first (2026-08-31: 100 reports in a
    # day — a common slug like `main` answered with a pile of unrelated
    # problems' goals, burning the reply budget without resolving the
    # one the caller meant). Nothing local → the old unscoped search,
    # so cross-problem library lookups still answer.
    #
    # The DECLARED problem wins over the cwd guess, and that is the
    # whole point: the seat filing those reports is the judge, whose
    # cwd is its round's projection and therefore under no problem at
    # all — the cwd branch could never fire for it, so the same ask
    # kept arriving (120 more reports 2026-08-30..09-04) after the fix
    # had "landed". cwd stays the fallback for a spawn launched by hand.
    prob = _declared_problem()
    if prob is None:
        pdir = _problem_dir_of(cwd, ws)
        if pdir is not None:
            try:
                prob = ".".join(pdir.relative_to(ws / "Problems").parts)
            except (ValueError, OSError):
                prob = None
    try:
        rows, foreign = [], False
        if gid:
            rows = conn.execute(
                "SELECT id, slug, lean_path, statement, status, problem, "
                "alias_target_id FROM goals WHERE id = ?",
                (int(gid.group(1)),)).fetchall()
        else:
            rows, foreign = _tiered(conn, name, prob)
        # The goal's own strategies, by the sid the wrapper names.
        #
        # This is the RECORD for two questions the answer could not
        # reach without it, and both cost a whole round on 2026-09-06:
        # (a) WHERE the strategy's proof is — `scratch_path` says
        # `proofs/_strategy_s1.lean` while the wrapper sits at
        # `Root.lean`, so the old "beside the wrapper" guess named a
        # file that does not exist and the one document that refuted
        # both seats' picture read as absent; (b) WHY a goal sits at
        # `attempting` with everything under it proved — a succeeded
        # strategy against an unsettled goal, which is a fact of the
        # tables and of nothing else.
        # WHY a goal that is neither moving nor done is where it is —
        # collected here, beside the strategies, because the connection
        # closes before anything is rendered (see `_reason_parts`).
        reasons_of: "dict[int, list[tuple[str, str]]]" = {
            int(r["id"]): _reason_parts(conn, int(r["id"]), str(r["status"]))
            for r in rows if str(r["status"]) not in _MOVING_OR_DONE}
        strategies_of: "dict[int, list[dict]]" = {}
        for r in rows:
            strategies_of[int(r["id"])] = [
                {"id": int(s["id"]),
                 "scratch_path": str(s["scratch_path"] or ""),
                 "status": str(s["status"])}
                for s in conn.execute(
                    "SELECT id, scratch_path, status FROM strategies "
                    "WHERE goal_id = ? ORDER BY id", (int(r["id"]),))]
        # An alias row's own file is `def slug := @sNNN` — truthful and
        # useless (90 self-reports: "shows the full statement for
        # unproved goals but only the alias for proved ones"). The
        # framework KNOWS the target; showing the pointer instead of
        # what it points at is the flattening family. Resolve it here,
        # disclosed, one hop at a time up to a short chain.
        alias_of: "dict[str, tuple[str, str, str, str]]" = {}
        for r in rows:
            tid, seen = r["alias_target_id"], 0
            target = None
            while tid is not None and seen < 4:
                target = conn.execute(
                    "SELECT slug, lean_path, statement, status, "
                    "alias_target_id FROM goals WHERE id = ?",
                    (tid,)).fetchone()
                if target is None:
                    break
                tid, seen = target["alias_target_id"], seen + 1
            if target is not None:
                alias_of[str(r["slug"])] = (
                    str(target["slug"]), target["lean_path"],
                    target["statement"], str(target["status"]))
    except Exception as exc:  # noqa: BLE001
        return [f"declaration index unavailable ({type(exc).__name__})"]
    finally:
        conn.close()
    if not rows:
        # The record holds GOALS. A `Defs.lean` definition is not one,
        # and `S` on p373 was exactly that — so the miss names the door
        # that answers instead of leaving the reader to guess (it used
        # to guess "search harder", and the unscoped substring search
        # obliged with six other problems' theorems).
        return [f"no declaration named {name!r} in this run's record — "
                f"that record holds this run's GOALS. A definition from "
                f"`Defs.lean` or a `let` inside a proof is not one: "
                f'{{"grep": {name!r}, "in": "*.lean"}} finds it in the '
                f"files. For a Mathlib name use `loogle`."]
    # The FULL signature from the stub file, not the stored `statement`.
    # `goals.statement` holds the pp-canonical CONCLUSION only, so a
    # by_contra sub-goal renders as literally `False` — which is why the
    # eager `## Active goals` section had used `goal_display_signature`
    # since 2026-07-18. When that section went lazy (2026-08-10) this
    # query became its replacement and, for one hour, gave back LESS than
    # what it replaced: the exact goals whose signature matters most were
    # the ones it flattened. Same helper, so the lazy path is equivalent
    # to the eager one it retired rather than a cheaper imitation of it.
    from ..agent import context as _ctx
    # An EXACT hit answers alone, and `_tiered` is what makes that true:
    # its first tier is this problem's exact name, so a near-miss never
    # shares a reply with the name the caller actually typed. Attaching
    # every neighbour is the CATALOG's old failure in a new place — the
    # answer is in there somewhere, under two others, at ~1,000
    # characters each because a full signature is a full signature.
    out: "list[str]" = []
    if foreign:
        # Never silently: an answer from another project looks exactly
        # like a local one on the line below, and that is how `decl S`
        # came back as Minif2f and Geometry theorems while the reviewer
        # read them as p373's own (×3, 2026-09-07/08).
        out.append(f"nothing in {prob} matches {name!r}. These are from "
                   f"OTHER problems — not this problem's declarations:")
    budget = _REASON_CHARS if len(rows) == 1 else _REASON_CHARS_SHORTLIST
    for r in rows:
        where = f"  ({r['problem']})" if foreign else ""
        out.append(f"{r['slug']}  [{r['status']}]  {r['lean_path']}{where}")
        slug, lp, stmt = str(r["slug"]), r["lean_path"], r["statement"]
        strats = strategies_of.get(int(r["id"]), [])
        gate = _strategy_gate_line(strats, str(r["status"]))
        if gate:
            out.append(gate)
        parts = reasons_of.get(int(r["id"]))
        if parts is not None:
            # An EMPTY block would reproduce the silence one layer down,
            # so a goal the record says nothing about says that instead.
            if not parts:
                out.append("    why this goal is not proved: nothing on "
                           "record — no park reason, no decline, no "
                           "failed attempt.")
            else:
                out.append("    why this goal is not proved — from this "
                           "run's record:")
                out += [f"      {head}"
                        + (f" — {_elide_middle(body, budget)}" if body else "")
                        for head, body in parts]
        target = alias_of.get(slug)
        if target is not None:
            tslug, lp, stmt, tstatus = target
            out.append(f"    alias of {tslug}  [{tstatus}] — "
                       f"showing the target's signature:")
            slug = tslug
        try:
            sig = _ctx.goal_display_signature(ws, slug, lp, stmt,
                                              flatten=False)
        except Exception:  # noqa: BLE001 — a missing stub falls back
            sig = stmt or ""
        if target is None:
            # Second alias shape (~29 reports, 2026-08-24): a proved
            # goal's file can be a WRAPPER `def slug ... := @…sNNN`
            # with no `alias_target_id` row — the promote path writes
            # the pointer without the DB marker. Follow the pointer
            # here, disclosed, instead of shipping a line the reader
            # must chase by hand — through the RECORD, never a guessed
            # filename (see `_wrapper_target`).
            m = re.search(r":=\s*@[\w'.]*?\b(s\d+)\b", sig or "")
            if m:
                banner, body, srel = _wrapper_target(ws, lp, m.group(1),
                                                     strats)
                out += banner
                if srel:
                    sig, lp = body, srel
        sig_lines = (sig or "").strip().splitlines()
        out += [f"    {ln}" for ln in sig_lines[:16]]
        # Truncation is a VIEW, never a loss (framework rule): the old
        # silent `[:16]` cut is the same "stopped mid-definition" failure
        # the grep path already discloses — ~26 agent reports read a
        # clipped signature as the WHOLE declaration. Name the count and
        # the reachable action: the file path is already on the line
        # above, so `read` + `lines` picks up exactly where this left off.
        if len(sig_lines) > 16:
            out.append(
                f"    … {len(sig_lines) - 16} more line(s) elided — "
                f'read the rest: {{"read": {lp!r}, "lines": "17-"}}')
    return out
