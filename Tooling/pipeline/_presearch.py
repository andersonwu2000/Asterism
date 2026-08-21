"""Per-node pre-search (target-1 v1).

Before a goal node is dispatched to a prover, a separate lightweight
pre-search agent searches for relevant lemmas across three sources —
Mathlib (via loogle), the project Library (via grep), and in-problem
proved siblings (via grep). The framework `#check`-verifies the
candidates (dropping hallucinated Mathlib names), ranks them, and caches
a `## Candidate lemmas` section that `compile_context` injects into the
node's Context.md. The agent's raw search stays in its own (discarded)
session; the prover only sees the clean ranked list — this separation is
what keeps the prover's working context on the proof rather than search.

Run ONCE per node: the persistent cache `problem_dir/.presearch/g<gid>.md`
is the once-per-node artifact (reused across the node's pipeline
dispatches and warm retries). v1 has no cross-node reuse (no shared
index, no parent->child seed — those are v2).

Best-effort throughout: any failure returns None and the prover proceeds
without the section (mirrors how reflection / drafts swallow errors).
"""
from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

# Import the `agent` PACKAGE (not the `runtime` module) so `agent.spawn_llm`
# is the same object the rest of the pipeline (backward/builder) references and
# tests stub via `monkeypatch.setattr(agent, "spawn_llm", …)`. Aliasing
# `runtime as agent` bound a DIFFERENT name that escaped the stub → pre-search
# spawned a REAL claude subprocess in unit tests, blocking on subprocess.wait
# for the full timeout ×3 retry stages (270s on one test; ~18 of 20 suite min).
from .. import agent
from ..knowledge import lemma_lookup

_DEFAULT_TIMEOUT_SEC = 240
_MAX_PER_BLOCK = 10
_PROMPT_FILENAME = "_presearch_prompt.md"
_OUT_FILENAME = "_presearch.json"

_SOURCE_TAG = {"mathlib": "Mathlib", "library": "Library",
               "in_problem": "this problem"}


def presearch_path(problem_dir: Path, goal_id: int) -> Path:
    """Persistent per-node cache: the rendered candidate section."""
    return problem_dir / ".presearch" / f"g{goal_id}.md"


def mint_presearch_path(problem_dir: Path, decision_id: int) -> Path:
    """Cache for a mint, which has no goal yet — the Inject decision is
    the only stable key at that point. `adopt_for_goal` renames it to
    the goal key at commit so the prove step reuses it instead of
    spawning a second search (user call 2026-08-07: one pre-search per
    brick, shared by the mint and prove steps)."""
    return problem_dir / ".presearch" / f"inject{decision_id}.md"


#: how much of an Inject brief may become the search key
_CLAIM_CAP = 2000
#: section heads strategists write the statement under, best first
_CLAIM_HEADS = ("## Declarations", "## Claim", "## Statement")


def claim_from_brief(brief: str) -> str:
    """The statement the mint will transcribe, taken from the Inject
    brief — a mint has no goal row to read it off.

    `## Declarations` (exact Lean) beats `## Claim` (prose + Lean), and
    both beat the whole brief, which also carries `## Strategy & Hints`
    — feeding those to the searcher drags it toward the route the
    Strategist already guessed instead of the statement."""
    if not brief:
        return ""
    for head in _CLAIM_HEADS:
        i = brief.find(head)
        if i < 0:
            continue
        rest = brief[i + len(head):]
        nxt = re.search(r"^## ", rest, re.M)
        body = (rest[:nxt.start()] if nxt else rest).strip()
        if body:
            return body[:_CLAIM_CAP]
    return brief.strip()[:_CLAIM_CAP]


def slug_from_brief(brief: str) -> str:
    """The brick slug the brief commissions (`Mint brick \\`slug\\``),
    used only to keep the searcher from proposing the very thing being
    minted. Empty when the brief does not name one — harmless."""
    m = re.search(r"[Mm]int\s+brick\s+`(?:L_)?([A-Za-z0-9_]+)`", brief or "")
    return m.group(1) if m else ""


def adopt_for_goal(problem_dir: Path, decision_id: int,
                   goal_id: int) -> None:
    """Re-key a mint's cached pre-search onto the goal the mint just
    created. Best-effort: a miss simply means the prove step runs its
    own search, which is the pre-2026-08-07 behaviour."""
    src = mint_presearch_path(problem_dir, decision_id)
    dst = presearch_path(problem_dir, goal_id)
    try:
        if src.is_file() and not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            src.replace(dst)
    except OSError:
        pass


def _presearch_enabled(workspace: Path | None) -> bool:
    """Read `presearch.enabled` from Asterism.yaml / env (default True).
    Operator switch: `presearch.enabled: false` (or
    `ASTERISM_PRESEARCH_ENABLED=false`) disables it without redeploying."""
    from ..core import config
    raw = config.get(
        "presearch.enabled", default=True,
        env_var="ASTERISM_PRESEARCH_ENABLED", workspace=workspace,
    )
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in ("true", "1", "yes", "on")


def _timeout_sec(workspace: Path | None) -> int:
    """Pre-search agent budget in seconds (Asterism.yaml `presearch.timeout_sec`
    / env, default `_DEFAULT_TIMEOUT_SEC`). The 3-source search (in-problem +
    Library + Mathlib loogle) legitimately takes longer than the old Mathlib-only
    pass — the budget must cover all three plus writing the output."""
    from ..core import config
    raw = config.get(
        "presearch.timeout_sec", default=_DEFAULT_TIMEOUT_SEC,
        env_var="ASTERISM_PRESEARCH_TIMEOUT_SEC", workspace=workspace,
    )
    try:
        return max(60, int(raw))
    except (TypeError, ValueError):
        return _DEFAULT_TIMEOUT_SEC


def _clean(entry) -> tuple:
    """`(name, why)` from a candidate entry; `('', '')` if malformed."""
    if not isinstance(entry, dict):
        return "", ""
    return (str(entry.get("name") or "").strip(),
            str(entry.get("why") or "").strip())


def _verify(blocks, workspace: Path, problem_dir: Path,
            conn=None, exclude_slug: str = "", problem: str = "") -> list:
    """Verify a 3-block pre-search result `{in_problem, library, mathlib}`,
    each a list of `{name, why}`. Per source:
      - in_problem: keep names whose decl appears in the problem's `proofs/`
        or `TREE.md` (grep-found siblings; light guard against padded names);
      - library: keep names among the DB's placed+bridged decls
        (`db.library_decl_names` — exact membership; was: an INDEX.md
        substring probe with short-name false positives, whose missing-file
        fallback silently kept EVERYTHING);
      - mathlib: `#check` via `lemma_lookup`, drop hallucinations, attach
        signatures; keep unverified if the lookup is unavailable.
    Each block is capped at `_MAX_PER_BLOCK`. Output is a flat list ordered
    in_problem → library → mathlib (cleanest cite first), each entry
    `{name, source, why[, signature]}`."""
    if not isinstance(blocks, dict):
        return []

    def _block(key: str) -> list:
        b = blocks.get(key)
        return b[:_MAX_PER_BLOCK] if isinstance(b, list) else []

    out: list = []

    # in_problem — keep only names that actually appear in the problem's proved
    # files (the agent should have grep-found them; guards padded/invented names).
    ip = _block("in_problem")
    if ip:
        hay = ""
        try:
            parts = []
            proofs = problem_dir / "proofs"
            if proofs.is_dir():
                for f in proofs.glob("*.lean"):
                    parts.append(f.read_text(encoding="utf-8", errors="ignore"))
            tree = problem_dir / "TREE.md"
            if tree.is_file():
                parts.append(tree.read_text(encoding="utf-8", errors="ignore"))
            hay = "\n".join(parts)
        except OSError:
            hay = ""
        # Status layer (agent_feedback 2026-07-09/10, 91 entries): a bare
        # name list let agents nearly cite a DISPROVED sibling as true and
        # gave no way to tell proved from open. Attach the DB status + a
        # one-line statement to every in-problem candidate the goals table
        # knows. Best-effort: no conn / no problem name → names-only.
        status_map: dict = {}
        if conn is not None and problem:
            try:
                status_map = {
                    str(r["slug"]): (str(r["status"]),
                                     str(r["statement"] or ""))
                    for r in conn.execute(
                        "SELECT slug, status, statement FROM goals"
                        " WHERE problem = ? AND alias_target_id IS NULL",
                        (problem,))}
            except Exception:  # noqa: BLE001 — enrichment is best-effort
                status_map = {}
        for entry in ip:
            name, why = _clean(entry)
            if not name:
                continue
            # Self-exclusion (2026-07-05 audit): the goal's OWN sorry stub
            # sits in proofs/, so the hay check below "verifies" it and the
            # candidate list then invites citing an open goal as if proved.
            if exclude_slug and name.rsplit(".", 1)[-1] == exclude_slug:
                continue
            short = name.rsplit(".", 1)[-1]
            if (not hay) or (short and short in hay):
                item = {"name": name, "source": "in_problem", "why": why}
                if short in status_map:
                    status, stmt = status_map[short]
                    item["status"] = status
                    one_line = " ".join(stmt.split())
                    if one_line:
                        item["statement"] = (one_line[:157] + "..."
                                             if len(one_line) > 160
                                             else one_line)
                out.append(item)

    # library — keep names among the DB-indexed placed decls. Match on the
    # full FQN or its leaf (agents report `Library.<Domain>.<File>.<decl>`
    # module-qualified names while the DB stores the declared FQN — leaf
    # equality bridges the two). conn=None (defensive) keeps all, the old
    # missing-INDEX fallback.
    known: "set[str] | None" = None
    if conn is not None:
        try:
            from ..state import db as _db
            known = _db.library_decl_names(conn)
        except Exception:  # noqa: BLE001 — filter is best-effort
            known = None
    known_leaves = ({n.rsplit(".", 1)[-1] for n in known}
                    if known is not None else None)
    for entry in _block("library"):
        name, why = _clean(entry)
        if not name:
            continue
        if (known is None or name in known
                or name.rsplit(".", 1)[-1] in known_leaves):
            out.append({"name": name, "source": "library", "why": why})

    # mathlib — #check; drop hallucinations, attach signatures.
    mathlib = _block("mathlib")
    names = [n for n, _ in (_clean(e) for e in mathlib) if n]
    infos: dict = {}
    if names:
        try:
            infos = lemma_lookup.lookup_batch(names, workspace)
        except Exception:  # noqa: BLE001 — offline / lake hiccup: keep unverified
            infos = {}
    for entry in mathlib:
        name, why = _clean(entry)
        if not name:
            continue
        info = infos.get(name)
        if info is not None and getattr(info, "found", False):
            out.append({"name": name, "source": "mathlib", "why": why,
                        "signature": (getattr(info, "signature", "")
                                      or "").strip()})
        elif not infos:
            # Whole-batch lookup failure (offline / lake hiccup): keep
            # the names but say so — rendering them under the section's
            # "#check-verified" banner sent agents chasing lemmas that
            # don't exist (agent_feedback 2026-07-13).
            out.append({"name": name, "source": "mathlib", "why": why,
                        "unverified": True})
        # else: name didn't resolve → hallucination, drop
    return out


def _render_section(candidates: list) -> str:
    """Render the `## Candidate lemmas` Context.md section."""
    lines = ["## Candidate lemmas (pre-search)",
             "",
             "Likely-relevant lemmas found for this goal (Mathlib names "
             "`#check`-verified). Cite by full name; grep for more if needed.",
             ""]
    if any(c.get("status") for c in candidates):
        lines[2] += (" In-problem siblings carry their status: a "
                     "non-proved one is citable — it auto-links and "
                     "your strategy waits for it. `disproved` means "
                     "the statement is FALSE — do not assume it.")
    for c in candidates:
        name = str(c.get("name") or "")
        tag = _SOURCE_TAG.get(str(c.get("source") or ""), str(c.get("source") or "?"))
        status = str(c.get("status") or "").strip()
        if status:
            tag += f", {status if status == 'proved' else status.upper()}"
        if c.get("unverified"):
            tag += ", UNVERIFIED — lookup unavailable, #check before use"
        why = str(c.get("why") or "").strip()
        sig = str(c.get("signature") or "").strip()
        stmt = str(c.get("statement") or "").strip()
        head = f"- `{name}`  [{tag}]" + (f" — {why}" if why else "")
        lines.append(head)
        if sig:
            lines.append(f"    `{sig}`")
        if stmt:
            lines.append(f"    `{stmt}`")
    return "\n".join(lines) + "\n"


_DRY_SECTION = (
    "## Candidate lemmas (pre-search)\n"
    "\n"
    "Pre-search ran for this goal and verified NO candidates — in-problem "
    "siblings, Library and Mathlib all came up dry. If you believe a "
    "relevant lemma exists, search yourself (grep / loogle).\n"
)


def ensure_presearch(*, goal, workspace: Path, problem_dir: Path,
                     attempts_dir: Path, prompt_dir: Path,
                     conn=None) -> Path | None:
    """Once-per-node: return the cached candidate section, spawning a
    pre-search agent on the first call for this goal. Best-effort — None
    on any failure (prover proceeds without the section)."""
    try:
        gid = int(goal["id"])
    except Exception:  # noqa: BLE001
        return None
    try:
        statement = str(goal["statement"] or "").strip()
        slug = str(goal["slug"])
        problem = str(goal["problem"] or "")
    except Exception:  # noqa: BLE001
        return None
    return _ensure(cache=presearch_path(problem_dir, gid),
                   label=f"g{gid}", statement=statement,
                   exclude_slug=slug, problem=problem,
                   workspace=workspace, problem_dir=problem_dir,
                   attempts_dir=attempts_dir, prompt_dir=prompt_dir,
                   conn=conn)


def ensure_mint_presearch(*, decision_id: int, statement: str, slug: str,
                          problem: str, workspace: Path, problem_dir: Path,
                          attempts_dir: Path, prompt_dir: Path,
                          conn=None) -> Path | None:
    """Pre-search for a MINT, which runs before its goal exists.

    The mint invents the declaration from the Inject brief and then
    proves it, so it needs candidates exactly as much as the prove step
    does — but `compile_forward_context` carried no section and nothing
    on this arm ever searched, while `formalize.md` told both arms to
    read `## Candidate lemmas` first. Workers re-derived Mathlib by hand
    and said so 5× in one run's feedback (2026-08-06).

    Statement source is the brief's `## Claim` (what the mint
    transcribes), not a goal row — hence the separate entry point.
    `adopt_for_goal` hands the result to the prove step, so this stays
    ONE search per brick (user call 2026-08-07)."""
    return _ensure(cache=mint_presearch_path(problem_dir, decision_id),
                   label=f"inject{decision_id}", statement=statement,
                   exclude_slug=slug, problem=problem,
                   workspace=workspace, problem_dir=problem_dir,
                   attempts_dir=attempts_dir, prompt_dir=prompt_dir,
                   conn=conn)


def _ensure(*, cache: Path, label: str, statement: str, exclude_slug: str,
            problem: str, workspace: Path, problem_dir: Path,
            attempts_dir: Path, prompt_dir: Path,
            conn=None) -> Path | None:
    try:
        if cache.is_file() and cache.read_text(encoding="utf-8").strip():
            return cache  # once-per-node cache hit (across dispatches/retries)
    except OSError:
        pass
    if not _presearch_enabled(workspace):
        return None
    template = prompt_dir / "_shared" / "presearch.md"
    if not template.exists():
        return None
    try:
        if not statement:
            return None
        timeout = _timeout_sec(workspace)
        # Own sandbox subdir so the agent's raw search files (_presearch.json,
        # prompt, session stderr) don't collide with the prover's attempts_dir.
        sandbox = attempts_dir / "_presearch"
        sandbox.mkdir(parents=True, exist_ok=True)
        out_path = sandbox / _OUT_FILENAME
        try:
            out_path.unlink()
        except OSError:
            pass
        rendered = (
            template.read_text(encoding="utf-8")
            .replace("__GOAL__", statement)
            .replace("__PACKAGES__", (workspace / ".lake" / "packages").as_posix())
            .replace("__LIBRARY_DIR__", (workspace / "Library").as_posix())
            .replace("__PROBLEM_DIR__", problem_dir.as_posix())
            .replace("__OUT_PATH__", out_path.as_posix())
            .replace("__TIMEOUT_MIN__", str(max(1, timeout // 60)))
        )
        prompt_file = sandbox / _PROMPT_FILENAME
        prompt_file.write_text(rendered, encoding="utf-8")

        from . import write_tools_mcp_config as _write_tools_cfg
        agent.spawn_llm(
            kind="presearch", prompt_path=prompt_file,
            problem_dir=problem_dir, attempts_dir=sandbox,
            session_id=str(uuid.uuid4()),
            timeout_sec_override=timeout,
            # Searching Mathlib IS this spawn's whole job, and loogle is
            # an MCP tool now — without the config the prompt would name
            # a tool the agent cannot call.
            mcp_config_path=_write_tools_cfg(sandbox, workspace,
                                             seat="presearch"),
        )

        if not out_path.is_file():
            return None
        raw = json.loads(out_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return None
        verified = _verify(raw, workspace, problem_dir, conn=conn,
                           exclude_slug=exclude_slug, problem=problem)
        # Ran-but-dry is INFORMATION (agent_feedback: an absent section is
        # indistinguishable from "presearch never ran", so provers re-search
        # from scratch). Cache an explicit dry section; infra failures above
        # still return None (unknown ≠ dry).
        section = _render_section(verified) if verified else _DRY_SECTION
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(section, encoding="utf-8")
        return cache
    except Exception as exc:  # noqa: BLE001 — never break dispatch
        print(f"[presearch] {label}: skipped — {exc}", flush=True)
        return None
