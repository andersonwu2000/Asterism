"""Forward context compilation — the argument for one brick, the
Library inventory, past Forward proposals, the Programme proof, mint
presearch and per-decision conventions, and `compile_forward_context`
itself (the Phase 2 entry that assembles Context.md for the Forward
agent).

Split out of `phase2_context.py` 2026-08-28 (Phase B, B2) unchanged.
Imports `_section_active_goals` / `_section_charter` / `_CATALOG_
RECENT_N` back from `compile.py` — Forward reuses the Strategist-side
active-goals and charter renders rather than keeping its own copy.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from ...state import db
from ...state import intent as intent_mod
from .. import context

from .compile import _CATALOG_RECENT_N, _section_active_goals, _section_charter


def _section_forward_brief(conn: sqlite3.Connection,
                           decision_id: int | None) -> list[str]:
    """The argument for THIS brick — Forward's primary input: the part of
    the batch's `## Proof` that settles it, copied into the Inject when
    the batch was written and judged along with it. Falls back to a
    placeholder if decision_id is None / row missing (shouldn't happen
    in production but tests / replay may exercise this)."""
    header = "## The argument for this brick"
    if decision_id is None:
        return [
            header,
            "",
            "(dispatched without one — default to a broadly useful new "
            "lemma in the problem's domain.)",
            "",
        ]
    try:
        row = conn.execute(
            "SELECT brief FROM strategist_decisions WHERE id = ?",
            (int(decision_id),),
        ).fetchone()
    except sqlite3.OperationalError:
        row = None
    if row is None or not row["brief"]:
        return [
            header,
            "",
            "(decision row carries none; treat as open-ended.)",
            "",
        ]
    return [header, "", str(row["brief"]).strip(), ""]


def _section_library_inventory(conn: sqlite3.Connection, problem: str,
                               attempts_dir: Path) -> list[str]:
    """All proved goals in this problem (Forward's local toolkit).
    Slug index + `CATALOG.md` companion (2026-07-13, user call): at 147
    proved bricks the inline truncated statements were 17KB of every
    Forward context — slugs stay inline as the cue, exact statements
    move to the machine-generated companion (same lazy pattern as
    lessons). Header kept verbatim: forward.md points at `## Library`.
    Cross-problem Library promotion is out of Phase 2 scope; just
    same-problem proved lemmas for now."""
    rows = context.write_catalog_companion(conn, problem, attempts_dir)
    header = "## Library (proved lemmas in this problem)"
    if not rows:
        # Nothing proved yet, but the companion still exists when the
        # problem has alive goals — and its `## Alive goals` block is
        # the surface the mint dedupe rule reads. Say so, or the rule
        # points at a file the worker was told nothing about.
        if context.alive_goal_rows(conn, problem):
            return [header, "", "(none yet — but"
                    f" `{context.catalog_companion_path(attempts_dir)}`"
                    " lists this problem's"
                    " alive goals: a mint matching one is discarded,"
                    " citing one is legal.)", ""]
        return [header, "", "(none yet)", ""]
    # Recent tail only (2026-07-14, user call — same cut as the
    # Strategist index): the brief names the bricks to use; the inline
    # list only needs to cover what the brief may predate.
    recent = rows[-_CATALOG_RECENT_N:]
    out = [
        header,
        f"_{len(rows)} proved bricks — full list & exact statements in"
        f" `{context.catalog_companion_path(attempts_dir)}`"
        " (read-only, NOT in your cwd; grep it by slug). Read an entry there BEFORE"
        f" citing it or proposing anything similar."
        f" The {len(recent)} newest:_",
        "",
    ]
    out += [f"- `{r['slug']}`" for r in recent]
    out.append("")
    return out


def _section_forward_history(conn: sqlite3.Connection,
                             problem: str, k: int = 5) -> list[str]:
    """Previous Forward lemmas in this problem (goals.origin='forward')
    so the agent doesn't repropose the same shape."""
    rows = list(conn.execute(
        "SELECT slug, statement, status FROM goals"
        " WHERE problem = ? AND origin = 'forward'"
        " ORDER BY id DESC LIMIT ?",
        (problem, k),
    ))
    if not rows:
        return []
    out = ["## Past Forward proposals (newest first)", ""]
    for r in rows:
        st = str(r["statement"])
        if len(st) > 200:
            st = st[:200].rstrip() + "…"
        out.append(f"- `{r['slug']}` ({r['status']}): `{st}`")
    out.append("")
    return out


def _section_programme_proof(conn: sqlite3.Connection, problem: str,
                             decision_id: "int | None" = None) -> list[str]:
    """The `## Proof` of the revision that DISPATCHED this mint — the
    argued mathematics this batch's mints are drawn from. Always renders (mirroring the
    FORBIDDEN_LEMMAS precedent: intake.md references "the Programme
    `## Proof`" unconditionally, and a silently absent heading leaves
    the agent unsure whether it was empty or truncated)."""
    from ...state import programme as _programme
    header = "## Programme Proof"
    # When the Inject carries its own argument, that argument IS this
    # section's job and the rest of the batch is other bricks' business.
    # The observed forward context shipped both: a hand-written 906 B
    # `## Proof` inside the brief AND the whole 7,962 B Programme Proof,
    # the same mathematics twice.
    try:
        own = conn.execute(
            "SELECT brief FROM strategist_decisions WHERE id = ?",
            (int(decision_id),)).fetchone() if decision_id is not None else None
    except sqlite3.OperationalError:
        own = None
    has_own = bool(own is not None and str(own["brief"] or "").strip())
    try:
        # The rev that dispatched this mint, not the latest — a mint has
        # no goal yet, so the decision IS the whole provenance. See
        # `programme.rev_for_goal`.
        row = _programme.rev_for_goal(conn, problem, decision_id=decision_id)
    except sqlite3.Error:
        row = None
    if not row:
        return [header, "(none yet)", ""]
    sections, _err = _programme.parse_proposal(str(row["body"] or ""))
    proof = ((sections or {}).get("proof") or "").strip()
    if not proof:
        return [header, "(none yet)", ""]
    if has_own:
        return [f"{header} (rev {row['rev']})", "",
                "The argument for this brick is above. The whole batch's "
                "`## Proof` — the other bricks and how they compose — is "
                "in `PROGRAMME.md` beside the problem files.", ""]
    return [f"{header} (rev {row['rev']})", "", proof, ""]


def _group_of_decision(conn: sqlite3.Connection,
                       decision_id: "int | None") -> "int | None":
    """The authoring group of a strategist decision, or None (top)."""
    if decision_id is None:
        return None
    try:
        row = conn.execute(
            "SELECT group_id FROM strategist_decisions WHERE id = ?",
            (int(decision_id),)).fetchone()
    except Exception:  # noqa: BLE001
        return None
    return int(row["group_id"]) if row and row["group_id"] else None


def _section_conventions_for_decision(conn: sqlite3.Connection,
                                      problem: str,
                                      decision_id: "int | None"
                                      ) -> list[str]:
    """`## Conventions (standing)` for a mint spawn, resolved through the
    Inject decision's authoring group (goal jobs resolve through the
    goal's owning group instead — `context._section_strategist_directive`)."""
    gid: "int | None" = None
    if decision_id is not None:
        try:
            row = conn.execute(
                "SELECT group_id FROM strategist_decisions WHERE id = ?",
                (int(decision_id),)).fetchone()
            gid = int(row["group_id"]) if row and row["group_id"] else None
        except sqlite3.OperationalError:
            gid = None
    try:
        from ...state import programme as _programme
        conv = _programme.conventions_for_group(conn, problem, gid)
    except Exception:
        conv = ""
    if not conv:
        return []
    return ["## Conventions (standing)", "", conv, ""]


def _section_mint_presearch(problem_dir: Path,
                            decision_id: "int | None") -> list[str]:
    """The mint's cached `## Candidate lemmas`. Pure file-read of
    `.presearch/inject<N>.md`; [] when absent so the section shows up
    only once the search has run."""
    if decision_id is None:
        return []
    from ...pipeline import _presearch
    path = _presearch.mint_presearch_path(problem_dir, int(decision_id))
    try:
        text = path.read_text(encoding="utf-8").strip() if path.is_file() else ""
    except OSError:
        text = ""
    return [text, ""] if text else []


def compile_forward_context(conn: sqlite3.Connection, *,
                            problem: str, decision_id: int | None,
                            attempts_dir: Path,
                            workspace: Path,
                            intent: intent_mod.ProblemIntent,
                            ) -> Path:
    """Write Context.md for the Forward agent into attempts_dir.

    Sections:
      - The argument for this brick (load-bearing input)
      - Library inventory
      - Past Forward proposals
      - Active goals (alive open/attempting/pending — so Forward does not
        restate one and get dedup-rejected)
      - Lemma hints (Mathlib pointers — agent uses loogle Bash for
        type-pattern search)

    NOT the full decomposition tree. Forward writes ONE generic lemma from
    the (prescriptive) brief and cites proved lemmas from `## Library`; it
    does not navigate goal structure. On a mature problem the inlined TREE
    was ~400 lines that were ~99% proved sub-trees (redundant with the
    `## Library` signatures) plus dead/shelved branches (abandoned-route
    noise) — pure context bloat that slowed the agent and diluted focus
    (framework_backlog #3). The one thing Forward uses tree state for —
    not restating an alive goal — is exactly `_section_active_goals`.
    (The Strategist context still inlines the full tree; it plans over
    the whole structure.)
    """
    section_names = ["forward_brief", "conventions", "programme_proof",
                     "library_inventory", "presearch",
                     "forward_history", "active_goals", "charter",
                     "user_word", "forbidden", "paper_index"]
    sections: list[list[str]] = [
        _section_forward_brief(conn, decision_id),
        # Standing conventions (research_mission_design.md §3.1). Mint
        # workers NEVER received the old directive — the section list
        # here simply did not carry it, which is how SLC's namespace
        # convention could be briefed, unfollowed, and retired as
        # "unfollowed" while one brick died on exactly that gap. The
        # authoring group comes off the Inject decision row.
        _section_conventions_for_decision(conn, problem, decision_id),
        # NL-first on the mint arm (07-30 audit): goal jobs carry the
        # Programme; mints did not, so intake's falsification check had
        # no source independent of the brief (written by the same
        # Strategist whose transcription slips it exists to catch).
        _section_programme_proof(conn, problem, decision_id),
        _section_library_inventory(conn, problem, attempts_dir),
        # Candidate lemmas (2026-08-07, user call). `formalize.md` tells
        # BOTH arms to read this section first, but the mint arm never
        # rendered one and nothing on it ever searched — 5 workers in
        # one run reported re-deriving Mathlib by hand, one of them
        # spending most of its budget on it. Written by
        # `ensure_mint_presearch` between intake and the work turn;
        # empty until then, and on the retry compile the cache hits.
        _section_mint_presearch(db.problem_dir(workspace, problem),
                                decision_id),
        _section_forward_history(conn, problem),
        _section_active_goals(conn, workspace, problem),
        # The authoring group's charter (v40) — the claim this mint
        # serves; the group comes off the Inject decision row, same as
        # conventions above.
        _section_charter(conn, workspace, problem,
                         _group_of_decision(conn, decision_id)),
        context._section_user_word(intent),
        # Dropped in the v33 merge: mint.md says "Never use any name in
        # FORBIDDEN_LEMMAS" but no section carried the list — a 07-29 SG
        # worker burned two blocked Bash calls hunting the file, and on
        # benchmark problems the ban is load-bearing. Renders "(none)"
        # when empty by design.
        context._section_forbidden(intent),
        # Paper navigation — Forward mints the vocabulary; exact
        # hypotheses/definitions come from the paper (design D1).
        context._section_paper_index(intent, workspace, conn,
                                     attempts_dir=attempts_dir),
    ]
    parts: list[str] = [f"# Forward context — {problem}", ""]
    for sect in sections:
        parts.extend(sect)
    out = attempts_dir / "Context.md"
    out.write_text("\n".join(parts), encoding="utf-8")
    context.write_context_stats(
        attempts_dir, label=f"forward {problem}",
        names=section_names, sections=sections)
    return out
