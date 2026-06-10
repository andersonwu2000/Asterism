"""§13 (c) decl-cleanup stage — marked-only per-decl proof simplification."""
from __future__ import annotations

from pathlib import Path

from . import _common as C
from ._common import _Decl


# ---------------------------------------------------------------------
# P2b — proof simplification (§13 (c) decl-cleanup, marked-only per-decl)
#
# Whole-proof rewrite is too expensive to attempt on every decl, so a per-file
# marker (one agent) first picks which proofs are worth shortening; only those
# pay the per-decl cost. Each marked survivor is then simplified in isolation:
# spawn → `_build_decl_isolated` (sig-preserving probe, reused from bridge) → on
# build failure feed the lake error & re-spawn up to a threshold → exhaustion
# (or a decline / no-change) keeps the original proof (safe no-op on the green
# baseline). Sig-preserving → no consumer rewrite. Runs on POST-dedup text, and
# skips dropped (gone) / bridged (already one-liners) decls (precedence
# drop > bridge > simplify).
# ---------------------------------------------------------------------

_SIMPLIFY_MARK_PROMPT = "cleanup_mark.md"
_SIMPLIFY_PROMPT = "decl_simplify.md"
_SIMPLIFY_MAX_RETRIES = 2


def _parse_simplify_marks(text: str) -> "set[str]":
    """Parse the simplify marker's JSON array → a set of decl (leaf) names.
    Accepts `["a","b"]` or `[{"decl":"a"}, …]`; ignores malformed entries."""
    import json
    try:
        data = json.loads(C._strip_json_fence(text))
    except Exception:  # noqa: BLE001
        return set()
    out: set[str] = set()
    if isinstance(data, list):
        for it in data:
            if isinstance(it, str) and it.strip():
                out.add(it.strip())
            elif isinstance(it, dict) and isinstance(it.get("decl"), str):
                out.add(it["decl"].strip())
    return out


def _simplify_mark_context(workspace: Path, problem: str, rel: str,
                           decl_names: "list[str]") -> str:
    try:
        body = (workspace / rel).read_text(encoding="utf-8")
    except OSError:
        body = ""
    return "\n".join([
        f"# Proof-simplification triage — {problem} — `{rel}`", "",
        f"Module: `{C._mod_of_rel(rel)}`.",
        f"Candidate declarations: {', '.join(decl_names) or '(none)'}", "",
        "## Current file", "", "```lean", body.rstrip(), "```", "",
    ]) + "\n"


def _simplify_decl_context(workspace: Path, problem: str, rel: str, name: str,
                           sig: str, proof: str, prev_error: str = "") -> str:
    lines = [
        f"# Simplify one proof — {problem} — `{name}`", "",
        f"Module: `{C._mod_of_rel(rel)}` (its declarations + imports are in scope).",
        "", "## Statement (keep verbatim)", "", "```lean", sig.strip(), "```",
        "", "## Current proof (everything after `:=`)", "",
        "```lean", proof.strip(), "```", "",
    ]
    if prev_error:
        lines += ["## Your previous attempt failed to build — fix and retry", "",
                  "```", prev_error[-1500:], "```", ""]
    return "\n".join(lines) + "\n"


def _mark_simplify_file(workspace: Path, problem: str, rel: str,
                        decl_names: "list[str]", problem_dir: Path) -> "set[str]":
    """Spawn the simplify marker over one file; return the subset of `decl_names`
    worth proof-simplifying. No-op (empty) if the prompt is absent."""
    prompt_path = (workspace / "Tooling" / "prompts" / "librarian"
                   / _SIMPLIFY_MARK_PROMPT)
    if not prompt_path.exists() or not decl_names:
        return set()
    got = C.spawn_collect(
        workspace, problem, prompt_path,
        _simplify_mark_context(workspace, problem, rel, decl_names),
        ["simplify.json"])
    if got is None:
        return set()
    return _parse_simplify_marks(got["simplify.json"]) & set(decl_names)


def _propose_simplify(workspace: Path, problem: str, rel: str, name: str,
                      sig: str, proof: str, problem_dir: Path,
                      prev_error: str = "") -> "str | None":
    """One simplify spawn for decl `name`; return the proposed new proof body
    (text after `:=`), or None on decline / failure."""
    prompt_path = (workspace / "Tooling" / "prompts" / "librarian"
                   / _SIMPLIFY_PROMPT)
    if not prompt_path.exists():
        return None
    got = C.spawn_collect(
        workspace, problem, prompt_path,
        _simplify_decl_context(workspace, problem, rel, name, sig, proof,
                               prev_error),
        ["simplified.txt"])
    if got is None:
        return None
    new_proof = got["simplified.txt"].strip()
    return new_proof or None


def decl_cleanup_simplify_file(workspace: Path, problem: str, target_file: str,
                               decls: "list[_Decl]", marked: "set[str]", *,
                               max_retries: int = _SIMPLIFY_MAX_RETRIES) -> int:
    """§13 (c) per-decl proof simplification for ONE file. For each `marked`
    survivor (source order): spawn → `_build_decl_isolated` (sig-preserving) →
    on fail feed the error & retry (≤ max_retries) → decline / no-change /
    exhaustion keeps the original proof. Writes `target_file` in place if any
    proof changed. Returns the count simplified. No-op (0) if the prompt is
    absent or nothing is marked."""
    if not marked:
        return 0
    problem_dir = workspace.joinpath("Problems", *problem.split("."))
    try:
        text = (workspace / target_file).read_text(encoding="utf-8")
    except OSError:
        return 0
    n = 0
    for d in decls:                                # source order, marked only
        if d.name not in marked:
            continue
        cur = C.decl_proof_body(text, d.name)
        if cur is None:
            continue
        prev_error = ""
        for _attempt in range(max_retries + 1):
            new_proof = _propose_simplify(
                workspace, problem, target_file, d.name, d.sig, cur,
                problem_dir, prev_error)
            if not new_proof or new_proof.strip() == cur.strip():
                break                              # decline / no change → keep
            ok, detail = C._build_decl_isolated(
                workspace, sig=d.sig, proof=new_proof,
                modules=[d.module], namespaces=[d.module])
            if ok:
                nt, replaced = C.replace_proof(text, d.name, new_proof)
                if replaced:
                    text = nt
                    n += 1
                    print(f"[staged] simplified {d.name}", flush=True)
                break
            prev_error = detail
    if n:
        (workspace / target_file).write_text(text, encoding="utf-8")
    return n
