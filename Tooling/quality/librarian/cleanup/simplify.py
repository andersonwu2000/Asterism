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
                           sig: str) -> str:
    """Cold-spawn Context.md: `patch.lean` holds the declaration as
    `_cleanup_probe` with its current proof; the agent shortens that proof in
    place via LSP, keeping the statement. Retry feedback (a build error) flows
    through `run_with_session_retries`' `retry_context`, not here."""
    return "\n".join([
        f"# Shorten one proof — {problem} — `{name}`", "",
        f"Module: `{C._mod_of_rel(rel)}` (its declarations + imports are in scope).",
        "", "`patch.lean` holds the declaration as `_cleanup_probe` with its "
        "current proof. Shorten that proof; keep the statement (everything up "
        "to `:=`) byte-identical.", "",
        "## Statement (keep verbatim)", "", "```lean", sig.strip(), "```", "",
    ]) + "\n"


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


def decl_cleanup_simplify_file(workspace: Path, problem: str, target_file: str,
                               decls: "list[_Decl]", marked: "set[str]", *,
                               conn=None, pipeline_id: "str | None" = None,
                               max_retries: int = _SIMPLIFY_MAX_RETRIES) -> int:
    """§13 (c) per-decl proof simplification for ONE file. Each `marked`
    survivor (source order) is shortened through the shared LSP edit loop
    (`run_lsp_edit_loop`, like migrate-hole-fill): an isolated probe —
    `theorem _cleanup_probe <sig> := <current proof>` importing + opening the
    decl's own module so siblings resolve — is seeded into `patch.lean`, and the
    agent edits the proof against live diagnostics. The extracted proof is
    re-verified cold (`_build_decl_isolated`, sig-preserving) before it is
    spliced back via `replace_proof`. A build failure retries within the same
    session (≤ max_retries); a decline / no-change / exhaustion keeps the
    original. Writes `target_file` in place if any proof changed. Returns the
    count simplified. No-op (0) if the prompt is absent or nothing is marked."""
    if not marked:
        return 0
    from .... import agent
    from ....core import dispatcher
    from ....pipeline import PipelineResult
    from ....pipeline._retry import run_lsp_edit_loop

    prompt_path = (workspace / "Tooling" / "prompts" / "librarian"
                   / _SIMPLIFY_PROMPT)
    if not prompt_path.exists():
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
        raw_sig = " ".join(d.sig.split())
        seed = (f"import Mathlib\nimport {d.module}\n\n"
                f"open {d.module}\n\n"
                f"theorem _cleanup_probe {raw_sig} := {cur}\n")
        dpid = f"{pipeline_id or agent.new_pipeline_id()}-simplify-{d.name}"
        dattempts = agent.attempts_dir_for(workspace, dpid)
        patch = dattempts / "patch.lean"
        cap: dict = {}

        def cold_prep(ctx, _patch=patch, _seed=seed, _d=d) -> None:
            (ctx.attempts_dir / "Context.md").write_text(
                _simplify_decl_context(workspace, problem, target_file,
                                       _d.name, _d.sig), encoding="utf-8")
            _patch.write_text(_seed, encoding="utf-8")

        def parse(_patch=patch, _cur=cur, _cap=cap, _d=d) -> PipelineResult:
            if not _patch.exists():
                return PipelineResult(
                    outcome="failed", failure_reason="agent_no_output",
                    failure_detail=f"{_d.name}: no patch.lean")
            new_proof = C.decl_proof_body(
                _patch.read_text(encoding="utf-8"), "_cleanup_probe")
            if not new_proof or new_proof.strip() == _cur.strip():
                _cap["proof"] = None               # no improvement → keep
                return PipelineResult(outcome="success")
            ok, detail = C._build_decl_isolated(
                workspace, sig=_d.sig, proof=new_proof,
                modules=[_d.module], namespaces=[_d.module])
            if not ok:                             # retry with the error
                return PipelineResult(
                    outcome="failed", failure_reason="librarian_gate_failed",
                    failure_detail=detail)
            _cap["proof"] = new_proof
            return PipelineResult(outcome="success")

        # release_session_after=True: a tight per-decl loop must free the
        # gateway slot before the next decl registers.
        run_lsp_edit_loop(
            conn=conn, goal_id=None, pipeline_id=dpid,
            budget_threshold=max_retries + 1,
            shelve_threshold=dispatcher.SHELVE_THRESHOLD,
            attempts_dir=dattempts, workspace=workspace,
            problem=problem, problem_dir=problem_dir,
            kind="librarian", prompt_path=prompt_path, target=patch,
            cold_prep_fn=cold_prep, parse_fn=parse,
            release_session_after=True)
        if cap.get("proof"):
            nt, replaced = C.replace_proof(text, d.name, cap["proof"])
            if replaced:
                text = nt
                n += 1
                print(f"[staged] simplified {d.name}", flush=True)
    if n:
        # Whole-file gate (#38) + batch revert. Each proof above passed only the
        # PER-DECL isolation gate (`_build_decl_isolated`, against the migrated
        # olean) — which can't see that simplifying a `def` body breaks a sibling
        # that unfolds it (`rw`/`rfl`/`ring`). So before committing, build the
        # WHOLE accumulated file; if it doesn't build, REVERT the entire batch
        # (don't write — the on-disk file stays at its pre-simplify state).
        # simplify is optional polish: a reverted file keeps verbose-but-correct
        # proofs, never a broken file (residue keystone STALL, 2026-06-20).
        ok, _detail = C._build_file_copy_isolated(workspace, text)
        if not ok:
            print(f"[staged] simplify `{target_file.split('/')[-1]}` — reverted "
                  f"all {n} simplification(s) (whole-file build failed)",
                  flush=True)
            return 0
        (workspace / target_file).write_text(text, encoding="utf-8")
    return n
