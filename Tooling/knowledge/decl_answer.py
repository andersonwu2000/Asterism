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
        rows = []
        if gid:
            rows = conn.execute(
                "SELECT id, slug, lean_path, statement, status, problem, "
                "alias_target_id FROM goals WHERE id = ?",
                (int(gid.group(1)),)).fetchall()
        else:
            if prob:
                rows = conn.execute(
                    "SELECT id, slug, lean_path, statement, status, problem, "
                    "alias_target_id FROM goals "
                    "WHERE problem = ? AND (slug = ? OR slug LIKE ?) "
                    "ORDER BY (slug = ?) DESC, slug LIMIT 6",
                    (prob, name, f"%{name}%", name)).fetchall()
            if not rows:
                rows = conn.execute(
                    "SELECT id, slug, lean_path, statement, status, problem, "
                    "alias_target_id FROM goals "
                    "WHERE slug = ? OR slug LIKE ? "
                    "ORDER BY (slug = ?) DESC, slug LIMIT 6",
                    (name, f"%{name}%", name)).fetchall()
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
        return [f"no declaration named {name!r} in this run's record. "
                f"For a Mathlib name use `loogle`."]
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
    # An EXACT hit answers alone. Substring matching is the fallback for
    # a half-remembered name, but once the caller has typed the whole
    # thing, attaching every near-miss is the CATALOG's old failure in a
    # new place — the answer is in there somewhere, under two others.
    # Measured: three matches on one query, ~1,000 characters each,
    # because a full signature is a full signature.
    exact = [r for r in rows if r["slug"] == name]
    others = len(rows) - len(exact)
    if exact:
        rows, note = exact, (f"({others} other slug(s) contain {name!r} — "
                             f"ask for one by its full name)" if others else "")
    else:
        note = ""
    out: "list[str]" = []
    if note:
        out.append(note)
    for r in rows:
        out.append(f"{r['slug']}  [{r['status']}]  {r['lean_path']}")
        slug, lp, stmt = str(r["slug"]), r["lean_path"], r["statement"]
        strats = strategies_of.get(int(r["id"]), [])
        gate = _strategy_gate_line(strats, str(r["status"]))
        if gate:
            out.append(gate)
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
