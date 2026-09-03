"""Anchor+claim review data — the sign-off surface's single source.

`review_data` computes the structured per-deliverable review (anchors /
claims / paper provenance) that BOTH `asterism review` and the serve API
render, so the two can never disagree about what is being vouched for
(frontend charter §5-4).

Snapshot model (charter §5-4, load-bearing): computing a closure needs a
warm gateway (30s+ cold), so it must never hide behind a GET. The
Strategist's Ingest commit calls `store_review_snapshot` while the
gateway is already warm; readers (CLI default, serve API) consume the
stored JSON via `load_review_snapshot`. Recomputing is an explicit act
(`asterism review --fresh` / the API's refresh job), which also
refreshes the stored snapshot.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..state import db


def review_data(conn, workspace: Path, *,
                problem: "str | None" = None) -> dict:
    """Structured anchor+claim review. Per deliverable: {fq, problem,
    slug, ok, error, kind, module, paper, anchors, claims, folded};
    plus the distinct pending-name union count. Warms the gateway iff
    there are deliverables to compute — callers on a cold machine
    should prefer the snapshot readers below."""
    from ..lsp import lifecycle as gateway_lifecycle
    from ..pipeline._constants import (anchor_closure_goal,
                                       canonicalize_anchor_pending,
                                       fold_generated_companions)
    # The human signs off on what the TOP group claimed. A sub-group's
    # MarkDeliverable is a result handed up to its parent to track, not
    # a claim addressed to a person — see `db.deliverables`. Unscoped,
    # union_closed asked for a vouch on 24 items of which 23 were
    # inter-group scaffolding. `None` (a problem older than groups)
    # keeps the whole list, which is what those problems always showed.
    dels = db.deliverables(conn, problem=problem,
                           group_id=db.top_group_id(conn, problem)
                           if problem else None)
    out: "list[dict]" = []
    union: set[str] = set()
    # Intent text + change history (self-audit 2026-07-12 §3-1b; v40
    # DB-resident): the sign-off seal (snapshot_sha) must cover WHAT
    # WAS ASKED, not just what was delivered — a mid-run rewrite of
    # the charter would otherwise let the reviewer sign against a
    # doctored promise with zero diff surfaced. Body = current charter
    # (+ word); history = (sha, seen_at) per recorded change since the
    # init baseline (full bodies live in `user_file_history`; the key
    # stays "manifest" so older snapshots keep reading).
    manifest_section: "dict" = {"body": "", "history": []}
    try:
        from ..state import intent as _intent
        pintent = _intent.read(conn, problem)
        if pintent is not None:
            manifest_section["body"] = pintent.charter + (
                "\n\n# The user's word\n\n" + pintent.word
                if pintent.word else "")
        manifest_section["history"] = [
            {"sha": str(r["sha"]), "seen_at": str(r["seen_at"])}
            for r in conn.execute(
                "SELECT sha, seen_at FROM user_file_history"
                " WHERE problem = ? AND file IN ('charter', 'word')"
                " ORDER BY id", (problem,))
        ]
    except Exception as e:  # noqa: BLE001 — visibility, never a blocker
        manifest_section["error"] = f"{type(e).__name__}: {e}"
    if not dels:
        return {"deliverables": out, "union_count": 0,
                "manifest": manifest_section}
    gateway_lifecycle.start_gateway(workspace)
    _papers: dict[str, str] = {}  # problem → paper id ('' = unbound)
    for g in dels:
        dest = workspace / g["lean_path"]
        r = anchor_closure_goal(
            workspace, dest, problem=g["problem"], slug=g["slug"])
        fq = f"Problems.{g['problem']}.{g['slug']}"
        entry = {"fq": fq, "problem": str(g["problem"]),
                 "slug": str(g["slug"]), "ok": bool(r.ok),
                 "error": None if r.ok else str(r.error),
                 "kind": None, "module": None, "paper": "",
                 "anchors": [], "claims": [], "folded": 0}
        if r.ok:
            # Canonicalize internal strategy names (`s<N>`) → public goal
            # slugs so the sign-off surface shows only human-meaningful
            # names (and each stays rejectable). #71.
            r.pending = canonicalize_anchor_pending(
                conn, workspace, g["problem"], r.pending)
            # Presentation only — reject/harvest consume the raw closure.
            r.pending, folded = fold_generated_companions(r.pending)
            entry.update({
                "kind": ("claim" if r.top_is_claim
                         else f"anchor:{r.top_kind}"),
                "module": r.top_module or None,
                "paper": _deliverable_paper_line(
                    conn, workspace, g, papers_cache=_papers),
                "anchors": r.anchors, "claims": r.claims,
                "folded": folded,
            })
            union.update(c["name"] for c in r.pending)
        out.append(entry)
    return {"deliverables": out, "union_count": len(union),
            "manifest": manifest_section}


def store_review_snapshot(conn, workspace: Path, problem: str) -> bool:
    """Compute + persist the problem's review snapshot (Ingest-commit
    hook: the gateway is warm there, so this is the cheap moment).
    Best-effort: a failure prints loudly and returns False — a missing
    snapshot degrades readers to live compute, never blocks Ingest."""
    try:
        data = review_data(conn, workspace, problem=problem)
        db.set_review_snapshot(
            conn, problem, json.dumps(data, ensure_ascii=False))
        return True
    except Exception as exc:  # noqa: BLE001 — never block Ingest
        print(f"[review] snapshot failed for {problem}: "
              f"{type(exc).__name__}: {exc} — readers will live-compute",
              flush=True)
        return False


def load_review_snapshot(conn, problem: str) -> "tuple[dict, str] | None":
    """(data, stored_at) for the problem's stored snapshot, or None
    (never stored / pre-v22 ingest / unparseable)."""
    row = db.get_review_snapshot(conn, problem)
    if row is None:
        return None
    raw, at = row
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(data, dict) or "deliverables" not in data:
        return None
    return data, at


def _deliverable_paper_line(conn, workspace: Path, g,
                            *, papers_cache: dict) -> str:
    """Paper-provenance line for one deliverable (paper pipeline Phase
    2): the `paper_ref` the Strategist recorded in the MarkDeliverable
    payload, so the human signs 'claim = paper theorem' against a pinned
    location instead of hunting. '' for problems with no paper
    binding; a LOUD placeholder when the binding exists but no ref was
    recorded (visibility, not a gate)."""
    prob = str(g["problem"])
    if prob not in papers_cache:
        try:
            rows = db.paper_bindings(conn, prob)
            papers_cache[prob] = str(rows[0]["paper_id"]) if rows else ""
        except Exception:  # noqa: BLE001 — display only
            papers_cache[prob] = ""
    pid = papers_cache[prob]
    if not pid:
        return ""
    # The workspace-relative path of the actual document (§3.9) — the
    # human signing off has to be able to OPEN it, and the console's
    # ReviewTree parses the Project out of this same string.
    from ..papers import shelf as _shelf
    from ..state import projects as _projects
    project = _projects.project_of(conn, prob) or prob.split(".", 1)[0]
    pdir = _shelf.paper_dir(workspace, pid, project=project)
    where = (pdir / "text.md").relative_to(workspace).as_posix() \
        if pdir is not None else \
        f"Problems/{project}/_docs/*/papers/{pid}/text.md (missing)"
    row = conn.execute(
        "SELECT payload FROM strategist_decisions"
        " WHERE decision_kind = 'MarkDeliverable' AND target_id = ?"
        " ORDER BY id DESC LIMIT 1", (int(g["id"]),)).fetchone()
    ref = ""
    if row is not None:
        try:
            ref = str((json.loads(row["payload"] or "{}")
                       ).get("paper_ref") or "").strip()
        except ValueError:
            ref = ""
    if ref:
        return f"paper: {ref}   ({where})"
    return (f"paper: (no paper_ref recorded — locate the claim in "
            f"{where} yourself before signing)")
