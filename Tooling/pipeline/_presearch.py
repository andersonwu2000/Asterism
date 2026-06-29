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
import uuid
from pathlib import Path

from ..agent import runtime as agent
from ..knowledge import lemma_lookup

_PRESEARCH_TIMEOUT_SEC = 150
_MAX_PER_BLOCK = 10
_PROMPT_FILENAME = "_presearch_prompt.md"
_OUT_FILENAME = "_presearch.json"

_SOURCE_TAG = {"mathlib": "Mathlib", "library": "Library",
               "in_problem": "this problem"}


def presearch_path(problem_dir: Path, goal_id: int) -> Path:
    """Persistent per-node cache: the rendered candidate section."""
    return problem_dir / ".presearch" / f"g{goal_id}.md"


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


def _clean(entry) -> tuple:
    """`(name, why)` from a candidate entry; `('', '')` if malformed."""
    if not isinstance(entry, dict):
        return "", ""
    return (str(entry.get("name") or "").strip(),
            str(entry.get("why") or "").strip())


def _verify(blocks, workspace: Path, problem_dir: Path) -> list:
    """Verify a 3-block pre-search result `{in_problem, library, mathlib}`,
    each a list of `{name, why}`. Per source:
      - in_problem: keep names whose decl appears in the problem's `proofs/`
        or `TREE.md` (grep-found siblings; light guard against padded names);
      - library: keep names present in `Library/INDEX.md`;
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
        for entry in ip:
            name, why = _clean(entry)
            if not name:
                continue
            short = name.rsplit(".", 1)[-1]
            if (not hay) or (short and short in hay):
                out.append({"name": name, "source": "in_problem", "why": why})

    # library — keep names present in INDEX.md (or all, if no index yet).
    index = workspace / "Library" / "INDEX.md"
    index_text = index.read_text(encoding="utf-8") if index.is_file() else ""
    for entry in _block("library"):
        name, why = _clean(entry)
        if not name:
            continue
        if (not index_text) or (name in index_text):
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
            out.append({"name": name, "source": "mathlib", "why": why})
        # else: name didn't resolve → hallucination, drop
    return out


def _render_section(candidates: list) -> str:
    """Render the `## Candidate lemmas` Context.md section."""
    lines = ["## Candidate lemmas (pre-search)",
             "",
             "Likely-relevant lemmas found for this goal (Mathlib names "
             "`#check`-verified). Cite by full name; grep for more if needed.",
             ""]
    for c in candidates:
        name = str(c.get("name") or "")
        tag = _SOURCE_TAG.get(str(c.get("source") or ""), str(c.get("source") or "?"))
        why = str(c.get("why") or "").strip()
        sig = str(c.get("signature") or "").strip()
        head = f"- `{name}`  [{tag}]" + (f" — {why}" if why else "")
        lines.append(head)
        if sig:
            lines.append(f"    `{sig}`")
    return "\n".join(lines) + "\n"


def ensure_presearch(*, goal, workspace: Path, problem_dir: Path,
                     attempts_dir: Path, prompt_dir: Path) -> Path | None:
    """Once-per-node: return the cached candidate section, spawning a
    pre-search agent on the first call for this goal. Best-effort — None
    on any failure (prover proceeds without the section)."""
    try:
        gid = int(goal["id"])
    except Exception:  # noqa: BLE001
        return None
    cache = presearch_path(problem_dir, gid)
    try:
        if cache.is_file() and cache.read_text(encoding="utf-8").strip():
            return cache  # once-per-node cache hit (across dispatches/retries)
    except OSError:
        pass
    if not _presearch_enabled(workspace):
        return None
    template = prompt_dir / "presearch.md"
    if not template.exists():
        return None
    try:
        statement = str(goal["statement"] or "").strip()
        if not statement:
            return None
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
            .replace("__TIMEOUT_MIN__", str(max(1, _PRESEARCH_TIMEOUT_SEC // 60)))
        )
        prompt_file = sandbox / _PROMPT_FILENAME
        prompt_file.write_text(rendered, encoding="utf-8")

        agent.spawn_llm(
            kind="presearch", prompt_path=prompt_file,
            problem_dir=problem_dir, attempts_dir=sandbox,
            session_id=str(uuid.uuid4()),
            timeout_sec_override=_PRESEARCH_TIMEOUT_SEC,
        )

        if not out_path.is_file():
            return None
        raw = json.loads(out_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return None
        verified = _verify(raw, workspace, problem_dir)
        if not verified:
            return None
        section = _render_section(verified)
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(section, encoding="utf-8")
        return cache
    except Exception as exc:  # noqa: BLE001 — never break dispatch
        print(f"[presearch] g{gid}: skipped — {exc}", flush=True)
        return None
