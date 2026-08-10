"""Scholar pipeline (paper v2, D11) — resolve + fetch a cited paper.

Single-stage: the Strategist's FetchPaper decision enqueued this with
`decision_id`; we read query/reason off that row, compile a small
Context.md, and spawn one agent whose only extra tool surface is the
two curated network commands (`papers.search` / `papers.fetch`, see
claude_cli._compose_allowed_tools). `papers.fetch --problem <p>` does
the whole shelve→index→bind chain itself, so the DB is the outcome
truth: a new scholar-origin binding appeared → 'paper_fetched';
otherwise the agent's `_scholar_result.md` carries the precise
human-path request (DOI/URL) → 'paper_unfetchable' with the request
in the decision's outcome_detail (Strategist sees it next wake).
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path

from .. import agent
from ..state import db

RESULT_FILENAME = "_scholar_result.md"


def _decision_query_reason(conn: sqlite3.Connection,
                           decision_id: int | None) -> tuple[str, str]:
    if decision_id is None:
        return "", ""
    row = conn.execute(
        "SELECT reason, payload FROM strategist_decisions WHERE id = ?",
        (decision_id,)).fetchone()
    if row is None:
        return "", ""
    try:
        query = str(json.loads(row["payload"] or "{}").get("query") or "")
    except ValueError:
        query = ""
    return query, str(row["reason"] or "")


def _fill_outcome(conn: sqlite3.Connection, decision_id: int | None,
                  outcome: str, detail: str = "") -> None:
    if decision_id is None:
        return
    conn.execute(
        "UPDATE strategist_decisions SET outcome = ?, outcome_detail = ?,"
        " updated_at = ? WHERE id = ?",
        (outcome, detail or None, db.now(), decision_id))
    conn.commit()


def run_scholar(conn: sqlite3.Connection, *, problem: str,
                workspace: Path, pipeline_id: str,
                decision_id: int | None) -> "object":
    """Returns a PipelineResult-shaped object (outcome / failure_*)."""
    from . import PipelineResult, PROMPT_DIR

    query, reason = _decision_query_reason(conn, decision_id)
    if not query:
        return PipelineResult(
            outcome="failed", failure_reason="scholar_no_query",
            failure_detail=f"decision {decision_id} carries no query")

    before = {r["paper_id"]
              for r in db.paper_bindings(conn, problem)}
    attempts_dir = agent.attempts_dir_for(workspace, pipeline_id)
    attempts_dir.mkdir(parents=True, exist_ok=True)

    bound = [f"- Papers/{r['paper_id']} ({r['origin']})"
             for r in db.paper_bindings(conn, problem)]
    context = "\n".join([
        f"# Scholar context — {problem}",
        "",
        "## Requested paper",
        f"Citation / query: {query}",
        f"Why needed: {reason}",
        "",
        "## Already bound to this problem (do not re-fetch)",
        *(bound or ["(none)"]),
        "",
    ])
    (attempts_dir / "Context.md").write_text(context, encoding="utf-8")

    rendered = (
        (PROMPT_DIR / "scholar" / "scholar.md")
        .read_text(encoding="utf-8")
        .replace("__PROBLEM__", problem)
        .replace("__WORKSPACE__", workspace.as_posix())
        .replace("__RESULT_PATH__",
                 (attempts_dir / RESULT_FILENAME).as_posix())
    )
    prompt_file = attempts_dir / "prompt.md"
    prompt_file.write_text(rendered, encoding="utf-8")

    # Scholar's two commands became MCP tools when the shell closed
    # (2026-08-10), so this spawn needs a tools config — it never had one,
    # because `python -m Tooling.papers.…` reached them through Bash.
    # Without it the prompt would name `paper_search` / `paper_fetch` to
    # an agent holding no server at all: the role would go quiet rather
    # than fail, which is the silent-capability-gap shape.
    from . import write_tools_mcp_config as _write_tools_cfg
    tools_cfg = _write_tools_cfg(attempts_dir, workspace)
    agent.spawn_llm(
        kind="scholar", prompt_path=prompt_file,
        problem_dir=db.problem_dir(workspace, problem),
        attempts_dir=attempts_dir,
        session_id=str(uuid.uuid4()),
        mcp_config_path=tools_cfg,
    )

    after = db.paper_bindings(conn, problem)
    new = [r for r in after if r["paper_id"] not in before]
    if new:
        ids = ", ".join(f"Papers/{r['paper_id']}" for r in new)
        print(f"[scholar] {problem}: fetched+bound {ids}", flush=True)
        _fill_outcome(conn, decision_id, "paper_fetched", ids)
        return PipelineResult(outcome="success")

    try:
        detail = (attempts_dir / RESULT_FILENAME).read_text(
            encoding="utf-8").strip()
    except OSError:
        detail = ""
    detail = detail or ("agent finished without a fetch and without "
                        f"{RESULT_FILENAME} — no trace of why")
    print(f"[scholar] {problem}: unfetchable — {detail[:160]}", flush=True)
    _fill_outcome(conn, decision_id, "paper_unfetchable", detail)
    # 'failed' pipeline status keeps the forensic dead_attempt trail;
    # the precise human-path request lives in the decision row.
    return PipelineResult(
        outcome="failed", failure_reason="paper_unfetchable",
        failure_detail=detail[:1000])
