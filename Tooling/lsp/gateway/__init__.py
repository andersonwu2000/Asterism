"""LSP Gateway — long-living HTTP MCP server with shared worker pool.

Phase 2: 1 server + W persistent workers + content swap on tool call.
N pipelines compete for W workers via tool-call-level LRU (not pipeline
hold). See `docs/archive/lsp_gateway.md` for design rationale.

Lifecycle:
  1. Daemon startup: launch this module as subprocess.
     `main()` starts ONE lake serve, then didOpens W slot files
     (`_gateway_slot_0.lean` ... `_gateway_slot_{W-1}.lean`) each with
     `import Mathlib\n` warmup. Each slot's worker pre-warms Mathlib
     namespace state so subsequent didChange swaps complete in ~3-4s.
  2. Per-spawn: framework POSTs /register with {pipeline_id,
     target_path, problem, workspace}. Gateway reads target_path off
     disk into an in-memory mirror, returns session_token. NO didOpen
     yet — that happens lazily at first tool call.
  3. Tool call: gateway resolves session via X-Asterism-Session header,
     borrows a slot (preferring one already loaded with this pipeline's
     content; LRU-evicts otherwise), didChange if needed, runs the LSP
     op against that slot's URI.
  4. Spawn end: framework POSTs /release/{token}. Gateway drops session
     metadata. Slot content stays loaded — next tool call from another
     pipeline will swap-in.

Wire format (MCP):
  POST http://127.0.0.1:8765/mcp
  Header: X-Asterism-Session: <token>
  Body:   JSON-RPC over streamable-http (FastMCP)

Wire format (REST):
  POST /register      JSON body {pipeline_id, target_path, problem,
                                 workspace, log_path?}
  POST /release/{tok} no body
  GET  /health        worker pool status + active session count
"""
from __future__ import annotations

import asyncio
import contextlib
import contextvars
import hashlib
import json
import os
import re
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from starlette.requests import Request
from starlette.responses import JSONResponse

from ...state import assemble, db, transitions
from ..client import LspClient


# ─── Package facade (2026-08-29: gateway.py → gateway/, splits A1-1..4a) ─
#
# Ten axes moved into their own modules; the names below are the ones
# code still in THIS file resolves by bare name, plus the ones callers
# and tests reach as `gateway.X`. Names whose only consumers live inside
# the moved module are deliberately absent, so a monkeypatch aimed at
# the facade fails loudly instead of becoming a silent no-op: patch
# `gateway.elab._ELAB_SEM` / `_ELAB_QUEUE_TIMEOUT_SEC`,
# `gateway.backend._await_backend` / `_start_workers` (for
# `_restart_backend`'s call), `gateway.weigh._slot_private_mb` (for
# `_slot_private_mb_cached`'s call), `gateway.sessions._owner_alive` /
# `_SWEEP_INTERVAL_SEC`, `gateway.leantext._DECL_SLUG_RE_TMPL` /
# `_needed_imports` / `_proved_sibling_import_lines` / `_SCOPE_*`,
# `gateway.rpc._ELABORATING_WARNING` / `_ECHO_END_CHARS` / `_HB_*`, and
# everything the governor alone consumes — `gateway.governor.
# _PRESSURE_DEBT` (rebound under `global`, so a facade patch reads back
# nothing), its kill/weigh helpers (`_await_worker_exit`,
# `_kill_worker_for_uri`, `_worker_pid_for_uri`, `_machine_gb`,
# `_slot_private_mb_fresh`), its histories and its thresholds — on the
# owning module.
#
# A module-level `from .x import name` COPIES the binding, so the patch
# target of a shared name is the CONSUMING module, not the defining one.
# `_ensure_backend_ready` is the split-brain example: `validate_file` and
# the /verify route here read this facade, `_register_session_internal`
# reads `gateway.sessions`, the four tools read `gateway.rpc`.
# `_current_session` and `_compilation_for` took the same shape with cut
# 4a. `_slot_private_mb_cached` and `_kick_warm_converger` stay
# double-bound because the /warm_target route here consumes both and the
# governor consumes both there. Patch the side whose consumer the test
# drives.
#
# The reach-backs are gone. `_compilation_for` (governor + sessions) and
# `_log_for` (register/release) were the last call-time imports into this
# facade; with 4a they live in `leantext` / `state` and are imported at
# module level. What replaces them runs the other way and stays
# call-time: `rpc.apply_edit` imports the submission gates
# (`_citation_submission`, `_locked_signature_submission`) from HERE,
# because they wait for cut 4b — so those two keep the facade as their
# patch target.
#
# `_offload_to_thread` and `mcp` live in `server.py` for one reason: a
# decorator has to resolve before this module finishes executing, and
# `rpc`'s four tools wear both. `gateway.mcp` is the same FastMCP object
# it always was, and the tool roster is unchanged at five.
#
# The `/health` route handler is `health_route`, NOT `health` — the
# bare name would have shadowed the `health` submodule on the package
# namespace and turned `monkeypatch.setattr(gateway.health, ...)` into
# a silent no-op against a coroutine function.

from .state import (
    WARMUP_CONTENT,
    WorkerSlot,
    SessionMetadata,
    GatewayState,
    _state,
    _session_ctx,
    _log_for,
    _ts_now,
)
from .elab import (
    ELAB_CREDIT_FILENAME,
    _elab_gate,
    elab_gate_stats,
)
from .backend import (
    WARMING_MSG,
    _start_workers,
    _ensure_backend_ready,
    _watch_initial_warm,
    _restart_backend,
)
from .weigh import (
    _slot_private_mb_cached,
    _SLOT_MB_CACHE,
)
from .governor import (
    SLOT_RECYCLE_MB_DEFAULT,
    WORKER_EXIT_WAIT_SEC,
    _GOVERNOR_INTERVAL_SEC,
    _pressure_debt,
    _pressure_outlet_step,
    _effective_target,
    _weight_kill_over_cap,
    _weight_watchdog_run,
    _recycle_wedged_slot,
    _wedge_watchdog_loop,
    _recycle_slot_if_heavy,
    _open_pipeline_slots_locked,
    _shed_slot_if_over_target,
    _midlease_residue_mb,
    _maybe_kick_midlease_rewarm,
    _midlease_rewarm_run,
    _freeze_tick,
    _kick_warm_converger,
    _warm_converger_run,
)
from .sessions import (
    _LEASE_TTL_SEC,
    _borrow_order,
    _acquire_slot,
    _register_session_internal,
    _release_session_internal,
    _current_session,
    _sweep_stale_claims,
    _stale_claim_sweep_loop,
)
from .health import (
    _HEALTH_SNAPSHOT,
    _HEALTH_SNAPSHOT_LOCK,
    _health_payload,
)
from .leantext import (
    _format_diag,
    _collapse_repeats,
    _metaprog_error,
    _ensure_imports,
    _inline_sibling_stubs,
    _collect_referenced_sibling_stubs,
    _toposort_siblings,
    _harvest_open_lines,
    _merge_opens,
    _parity_for,
    _build_compilation_unit,
    _commit_header_for,
    _merged_line_for,
    _compilation_for,
    _remap_inlined_diags,
    _summarize_goal,
    _goal_present,
    _sorry_start_col,
    _stub_fingerprint,
    _resync_buffer_from_disk,
    _scope_balance,
)
from .server import (
    mcp,
    _offload_to_thread,
)
from .rpc import (
    apply_edit,
    goal_at,
    errors_at,
    withdraw_stub,
    _echo_removed,
    _arg_help,
    _diags_converged,
    _hb_rank,
    _hb_declared,
    _note_diagnostics,
    _heartbeat_gate,
    _GOAL_AT_EDIT_END_NOTE,
)


# ── validate_file submission mirror (#8 / P2) ────────────────────────
# The commit-time gates an agent's patch must also pass, surfaced pre-commit
# so a validate≠commit disagreement no longer costs a whole retry round.
# Returned in a `submission` block kept SEPARATE from Lean `diagnostics`
# (elaboration result vs framework policy — the user's separation instinct,
# in one tool call so the agent's existing validate_file loop catches it).

# Formerly hand-maintained `_GW_*` copies of the pipeline regexes ("kept
# local so the gateway does not import the heavy pipeline package") — now
# the SAME objects via the state-layer leaf `state.assemble` (task #5 Step
# A): the pipeline re-exports these under its historical names, so the two
# sides structurally cannot drift. The citability VERDICT stays with the
# shared SoT `db.classify_cited_slug`.
_GW_PROBLEM_IMPORT_RE = assemble.PROBLEM_IMPORT_RE
_GW_THEOREM_RE = assemble.THEOREM_LINE_RE
_GW_SORRY_STUB_RE = assemble.SORRY_STUB_RE
_GW_SLUG_RE = assemble.SLUG_RE
_GW_DECL_HEAD_RE = assemble.DECL_HEAD_RE


def _gw_leading_comments(text: str) -> str:
    """`--` comment lines before the first declaration head (ANY kind — a
    data goal's patch is a `def`) — presence-mirror of
    `pipeline._extract_leading_comments` (commit's annotation source)."""
    m = _GW_DECL_HEAD_RE.search(text)
    region = text[:m.start()] if m else text
    return "".join(ln for ln in region.splitlines(keepends=True)
                   if ln.strip().startswith("--"))


def _citation_submission(content: str, problem: str, workspace: "Path",
                         declared: "set[str]",
                         kind: "str | None" = None) -> "dict | None":
    """Classify each `import Problems.<problem>.proofs.L_<slug>` in `content`
    via the shared `db.classify_cited_slug` SoT so validate_file predicts the
    commit citation gate. `declared` = sibling stubs inlined this call (legit
    — skip). Best-effort: any DB failure → None (must never break validate).

    `kind` (the session's pipeline) sharpens the non-proved verdict: a
    Backward / Formalizer commit auto-links a cited open sibling as a
    strategy sub-goal; Builder/Forward commits have no
    auto-link — the citation dies at their axiom gate (transitive sorryAx),
    so for those pipelines the mirror reports it as the ERROR it is instead
    of the historical one-size warn (feedback family: agents trusted the
    warn, burned the round trip).

    Task #123 retired the stub-count sharpening: commit auto-links a cited
    unproved sibling whether or not the patch declares stubs (the wait edge,
    not the stub, is what defers verification), so a stub-less Backward /
    Formalizer patch now gets the same auto-link warn as a decomposition."""
    try:
        conn = db.connect(workspace / "asterism.db")
    except Exception:
        return None
    issues: "list[dict]" = []
    try:
        seen: "set[str]" = set()
        for m in _GW_PROBLEM_IMPORT_RE.finditer(content):
            if m.group(1) != problem:
                continue
            slug = m.group(2)
            if slug in seen or slug in declared:
                continue
            seen.add(slug)
            try:
                _gid, status, orphan = db.classify_cited_slug(
                    conn, problem=problem, slug=slug, workspace=workspace)
            except Exception:
                continue
            if status == "proved":
                continue
            if status is None:
                if orphan:
                    issues.append({
                        "slug": slug, "status": "orphan", "severity": "error",
                        "hint": "stub on disk with no tracked goal — citing it "
                                "imports a sorry; declare your own "
                                "new_<slug>.lean sub-goal instead"})
                # else: typo / cross-problem — lake's unknown-identifier covers it
                continue
            if status in transitions.GOAL_FAILED_TERMINALS:
                issues.append({
                    "slug": slug, "status": status, "severity": "error",
                    "hint": "hard-terminal; re-declare its statement as your "
                            "own new_<slug>.lean sub-goal stub"})
            else:  # open / attempting / pending_strategist_review / shelved
                if (kind or "").lower() in ("builder", "forward"):
                    issues.append({
                        "slug": slug, "status": status, "severity": "error",
                        "hint": f"non-proved: a {kind} commit has no "
                                "auto-link — the citation imports a sorry "
                                "and dies at the axiom gate; cite proved "
                                "siblings only, or (forward) declare the "
                                "fact as your own lemma"})
                else:
                    issues.append({
                        "slug": slug, "status": status, "severity": "warn",
                        "hint": "non-proved: commit auto-links it as a "
                                "dependency and your strategy waits until "
                                "it proves — legitimate, but rejected if it "
                                "is an ancestor of your goal or restates it"})
    finally:
        conn.close()
    return {"ok": not any(i["severity"] == "error" for i in issues),
            "issues": issues}


def _annotation_submission(content: str, is_mint: bool = False) -> "dict":
    """Mirror commit's `agent_no_annotation` gate: a final patch needs a
    leading `--` comment block. Applies only when `content` is a real
    submission (declares SOMETHING — any decl kind, a data goal's patch
    is a `def`/`structure` — with a non-sorry body); probing a
    `:= by sorry` stub is not a submission, so skip (`checked: False`).
    Historically theorem-only, so a def patch validated with
    `checked: false` and no explanation (feedback family: the agent
    couldn't tell whether the gate applied).

    The mint arm has no such gate since the Forward-rationale comment
    was retired (07-29) — nagging for it there is a false requirement."""
    if is_mint:
        return {"checked": False,
                "note": "mint commits need no annotation"}
    if (not _GW_DECL_HEAD_RE.search(content)
            or _GW_SORRY_STUB_RE.search(content)):
        # Explain the skip (07-19 ×2: agents read a bare
        # `checked: false` on a stub as "annotation maybe required").
        # The forward warning is deliberate (autopsy 2026-08-24): a
        # silent skip here let a WIP patch sail to commit and only
        # then learn the annotation was due.
        return {"checked": False,
                "note": "no annotation needed while the body is sorry "
                        "(a sub-goal stub never needs one) — the FINAL "
                        "patch will: replace the `-- STRATEGY:` "
                        "placeholder when the proof closes"}
    ok = bool(assemble.strip_annotation_placeholder(
        _gw_leading_comments(content)).strip())
    return {"checked": True, "ok": ok,
            "note": "" if ok else
            "FINAL patch only: replace the `-- STRATEGY:` placeholder "
            "with a leading -- comment before commit "
            "(agent_no_annotation; the unreplaced placeholder does not "
            "count). Ignore on exploratory probes."}


def _locked_signature_submission(content: str,
                                 attempts_dir: "Path") -> "dict | None":
    """D-lite mirror of the Backward commit signature gate: the strategy
    skeleton's `<kind> s<sid> <binders> : <type>` is LOCKED — commit
    byte-compares it (whitespace-normalized) and rejects any edit, even a
    mathematically equivalent rewrite that elaborates fine. Backward seeds
    the normalized signature into `_locked_signature.txt`; compare the
    content's current signature against it via the SAME shared helpers.
    None when there is no seed file (non-Backward session) or `content`
    doesn't mention the locked name (probing a sub-goal stub, not the
    patch)."""
    f = attempts_dir / "_locked_signature.txt"
    try:
        if not f.is_file():
            return None
        locked = f.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    parts = locked.split()
    name = parts[1] if len(parts) >= 2 else ""
    if not name or not re.search(rf"\b{re.escape(name)}\b", content):
        return None
    agent_sig = assemble.normalize_signature(
        assemble.signature_prefix(content, name))
    if agent_sig == locked:
        return {"checked": True, "ok": True}
    return {
        "checked": True, "ok": False,
        "hint": (f"the `{name}` signature is LOCKED — commit rejects ANY "
                 "edit to it (even an equivalent rewrite that elaborates "
                 "fine); restore it exactly and make changes after `:= by` "
                 "only"),
        "locked": locked,
        "current": agent_sig or "(declaration head not parseable)",
    }


def _stale_olean_submission(content: str, problem: str,
                            workspace: "Path") -> "dict | None":
    """D-lite staleness warning: this probe resolves committed siblings via
    their on-disk build products; if a cited `L_<slug>`'s source is newer
    than its .olean (or the .olean is missing), the probe's verdict for
    that citation is based on a stale world — commit's real build will
    recompile. Detection only (whether the recompile changes the verdict
    needs the real build); None when content cites nothing."""
    cites = [m.group(2) for m in _GW_PROBLEM_IMPORT_RE.finditer(content)
             if m.group(1) == problem]
    if not cites:
        return None
    prel = Path(*problem.split(".")) if "." in problem else Path(problem)
    issues: "list[dict]" = []
    for slug in cites:
        src = (workspace / "Problems" / prel / "proofs" / f"L_{slug}.lean")
        if not src.exists():
            continue                    # citation gate reports missing goals
        rel = Path("Problems") / prel / "proofs" / f"L_{slug}.olean"
        oleans = [workspace / ".lake" / "build" / "lib" / "lean" / rel,
                  workspace / ".lake" / "build" / "lib" / rel]
        try:
            fresh = any(o.exists() and o.stat().st_mtime >= src.stat().st_mtime
                        for o in oleans)
        except OSError:
            continue
        if not fresh:
            issues.append({
                "slug": slug,
                "note": (f"L_{slug}.lean is newer than its .olean (or the "
                         ".olean is missing) — this probe's verdict for the "
                         "citation is based on a stale build; commit will "
                         "recompile it"),
            })
    return {"ok": not issues, "issues": issues}


def _slug_collision_submission(stub_map: "dict[str, str]", problem: str,
                               workspace: "Path") -> "dict | None":
    """Predict the commit-only slug fate for BATCH STUBS (agent_feedback
    #4b: LSP all-green, bounced at commit): a `new_<slug>.lean` whose
    slug already exists as a goal in this problem either auto-suffixes
    to `_2` at commit (breaking the decl-name match every citation in
    the batch relies on) or — when the twin is a strict ancestor with an
    identical head — dies as `circular_decomposition`.

    FORK (agent_feedback 2026-07-11, 12 contradiction reports): when the
    colliding twin is SHELVED and the stub's statement is byte-identical
    (normalized signature match — display heuristic only; the commit
    authority is the kernel defeq/reuse path), the SANCTIONED move is to
    keep the name and let commit dedupe-link to the twin — so the entry
    downgrades to `info` instead of scaring the agent into a rename that
    mints yet another fresh-slug twin. Scoped to stubs only: a patch
    legitimately declares its own goal's slug. Best-effort: DB failure →
    None."""
    if not stub_map:
        return None
    try:
        conn = db.connect(workspace / "asterism.db")
    except Exception:
        return None
    try:
        issues: "list[dict]" = []
        all_ok = True
        for slug in sorted(stub_map):
            row = conn.execute(
                "SELECT id, status, lean_path FROM goals WHERE problem = ?"
                "  AND slug = ? AND alias_target_id IS NULL LIMIT 1",
                (problem, slug),
            ).fetchone()
            if row is None:
                continue
            same_stmt = False
            if str(row["status"]) == "shelved":
                try:
                    twin_text = (workspace / str(row["lean_path"])
                                 ).read_text(encoding="utf-8")
                    twin_sig = assemble.signature_prefix(twin_text, slug)
                    cand_sig = assemble.signature_prefix(
                        stub_map[slug], slug)
                    same_stmt = (bool(twin_sig) and bool(cand_sig)
                                 and assemble.normalize_signature(twin_sig)
                                 == assemble.normalize_signature(cand_sig))
                except OSError:
                    same_stmt = False
            if same_stmt:
                issues.append({
                    "slug": slug, "existing_goal": int(row["id"]),
                    "status": str(row["status"]),
                    "severity": "info",
                    "hint": (f"`{slug}` is statement-identical to the "
                             f"existing SHELVED goal {int(row['id'])} — "
                             f"this is the sanctioned dedupe path: KEEP "
                             f"this name; at commit the stub links to "
                             f"that twin (link-and-wait, no new goal). "
                             f"Do NOT rename — a fresh slug just mints "
                             f"another twin."),
                })
                continue
            all_ok = False
            issues.append({
                "slug": slug, "existing_goal": int(row["id"]),
                "status": str(row["status"]),
                "severity": "warn",
                "hint": (f"a goal named `{slug}` already exists "
                         f"(status={row['status']}). At commit this stub "
                         f"auto-suffixes to `{slug}_2`, breaking every "
                         f"decl-name reference to it in this batch; if the "
                         f"twin is an ancestor on your chain with the same "
                         f"statement, commit rejects the whole strategy as "
                         f"circular_decomposition. Rename the sub-goal, or "
                         f"cite the existing goal instead of re-declaring "
                         f"it."),
            })
        if not issues:
            return {"checked": True, "ok": True}
        return {"checked": True, "ok": all_ok, "issues": issues}
    except Exception:
        return None
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _declhead_submission(content: str) -> "dict":
    """Mirror commit's slug gate: every top-level `<kind> <name>` declaration's
    name must be snake_case (`^[a-z][a-z0-9_]*$`). A camelCase def/theorem name
    elaborates clean but the Forward/Backward commit parser bounces it AFTER a
    full lake build — surface it pre-commit so the agent renames in-loop
    (agent_feedback green_theorem #69/#107). `checked: False` when the content
    declares nothing to slug (e.g. a pure import/open probe)."""
    bad: "list[str]" = []
    for m in _GW_DECL_HEAD_RE.finditer(content):
        name = m.group(2)
        if not _GW_SLUG_RE.match(name):
            bad.append(name)
    if not bad:
        return {"checked": _GW_DECL_HEAD_RE.search(content) is not None,
                "ok": True}
    return {"checked": True, "ok": False, "bad_slugs": sorted(set(bad)),
            "note": "declaration name(s) must be snake_case "
                    "(^[a-z][a-z0-9_]*$); commit rejects a camelCase slug after "
                    "a full lake build — rename now"}


#: Decline placeholder marker — kept in lockstep with
#: `pipeline.forward._DECLINE_RE` (the gateway subprocess stays free of
#: pipeline imports; a source pin in tests holds the two together).
_GW_DECLINE_RE = re.compile(r"^\s*--\s*decline\s*:\s*([a-z_]+)\b",
                            re.MULTILINE | re.IGNORECASE)


def _namespace_submission(content: str, problem: str) -> "dict | None":
    """Mirror the forward namespace-fidelity gate (forward.py): the file
    elaborates clean under ANY `namespace` wrapper, but commit resolves
    the declaration under the canonical `Problems.<problem>` — a
    respelled wrapper passed validate_file and only bounced at commit
    (Test.provider_probe, 2026-08-24 feedback: `Problems.provider_probe`
    vs `Problems.Test.provider_probe`). None when there is no namespace
    line, it already matches, or the file is a decline placeholder."""
    m = re.search(r"^namespace\s+(\S+)", content, re.M)
    if not m or _GW_DECLINE_RE.search(content):
        return None
    want = f"Problems.{problem}"
    if m.group(1) == want:
        return None
    return {"ok": False, "got": m.group(1), "want": want,
            "note": (f"commit resolves your declaration under the canonical "
                     f"`namespace {want}` (case included) — keep the seed's "
                     f"namespace/end lines exactly as seeded")}


#: Cap on decls probed per validate — a patch carries one theorem, a
#: batch stub file one decl; anything past this is pathological input.
_AXIOM_PROBE_DECL_CAP = 8


def _axioms_submission(backend, slot, content: str,
                       meta: "SessionMetadata") -> "dict | None":
    """The commit axiom gate, mirrored pre-commit (2026-08-18). g7941:
    a `native_decide` proof validated green here, built for 51 minutes,
    and died at the commit gate — a verdict knowable at this probe for
    one warm RPC per decl. Returns a failing submission entry when a
    decl's axioms exceed the problem whitelist, None when clean /
    unknowable (the commit gate stays the authority; this only warns).

    `sorryAx` is deliberately NOT flagged here: `:= by sorry` stubs are
    the legal decomposition currency pre-commit, and the commit gate's
    own tripwire handles the illegal cases."""
    try:
        from ...state import intent as _intent
        conn = db.connect_readonly(Path(meta.workspace) / "asterism.db")
        try:
            pintent = _intent.read(conn, meta.problem)
        finally:
            conn.close()
        if pintent is None:
            return None
        wl = set(_intent.effective_axioms(pintent, problem=meta.problem))
    except Exception:  # noqa: BLE001 — no intent, no verdict
        return None
    wl.add("sorryAx")
    names: "list[str]" = []
    for m in _GW_DECL_HEAD_RE.finditer(content):
        if m.group(2) not in names:
            names.append(m.group(2))
    rogue: "set[str]" = set()
    for name in names[:_AXIOM_PROBE_DECL_CAP]:
        try:
            r = backend.rpc_call(
                slot.slot_uri, "Asterism.printAxioms",
                {"fqName": f"Problems.{meta.problem}.{name}"},
                timeout=30)
        except Exception:  # noqa: BLE001 — probe is best-effort
            continue
        if r.get("found"):
            rogue |= set(r.get("axioms") or []) - wl
    if not rogue:
        return None
    from ...state.failures import rogue_axioms_message
    return {"ok": False, "rogue": sorted(rogue),
            "note": rogue_axioms_message(rogue)}


@mcp.tool(structured_output=False)
@_offload_to_thread
def validate_file(content: str = "", file: str = "") -> str:
    """Validate this session's file FROM DISK — `validate_file()` reads
    `patch.lean`, `validate_file(file="new_<slug>.lean")` reads that
    stub. The disk file is the authority: write first (`apply_edit` /
    `write_file`), then validate; there is no string mode (what you
    validate IS what commit reads — the response's `content_sha256`
    names the exact bytes). Auto-prepends Mathlib + the problem's Defs
    imports, pushes the file's content onto a borrowed slot, reads
    diagnostics, leaves the slot dirty (next caller will swap content
    as needed).

    If `content` cites a freshly-declared sibling sub-goal (`new_<slug>.
    lean` in the attempts dir, referenced but not declared here), that
    stub's declaration is inlined ahead of `content` so the citation
    resolves and its arg-order / arity is checked pre-commit — the
    sibling stubs aren't importable until commit-time (T3). Diagnostics
    are remapped back to this content's own line numbers; the response's
    `inlined_siblings` lists which stubs were folded in.

    Beyond Lean elaboration, the response carries a `submission` block that
    mirrors the framework gates the patch must ALSO pass at commit, so a file
    that elaborates clean but would still be bounced at commit is flagged here
    (no wasted retry round). `submission` is separate from `diagnostics`
    (Lean) — `diagnostics` says "it elaborates", `submission` says "commit
    will accept it":
      - `submission.citation`: { ok, issues:[{slug,status,severity,hint}] } —
        each `import Problems.<p>.proofs.L_<slug>` whose cited goal is not
        `proved`. severity `error` = rejected at commit no matter what
        (orphan/dead/disproved); `warn` = citable only via a Backward
        decomposition. Absent if the DB can't be read.
      - `submission.annotation`: { checked, ok[, note] } — whether a final
        patch (a real, non-`sorry` theorem) carries the required leading `--`
        comment block; commit rejects a missing one as `agent_no_annotation`.
        `checked:false` when `content` is a `:= by sorry` stub (not a
        submission).
      - `submission.namespace`: { ok:false, got, want, note } — present only
        when the file's `namespace` line differs from the canonical
        `Problems.<problem>` (case included); commit resolves your
        declaration under the canonical name and bounces a respelled one.

    The candidate also elaborates against the session patch's own `open`
    lines (not just Defs.lean's), so a stub using `MeasureTheory` / scoped
    `Topology` / a `Library.*` namespace validates the way it will at commit.

    The response's `commit_header` block lists the exact import/open lines
    the framework itself will inject into this file at commit (framework
    imports, Defs/patch opens, proved-sibling imports, intra-batch sub-goal
    imports) — they are already part of this validation, so do NOT write
    them yourself.

    `submission.slug_collision` predicts the commit-only slug fate of
    batch stubs: a `new_<slug>.lean` whose slug already names a goal in
    this problem auto-suffixes (breaking decl-name references) or dies as
    circular_decomposition when the twin is an identical ancestor.

    Args:
      file: Which file to validate — empty for this session's own
            target (patch.lean), or a `new_<slug>.lean` beside it.

    Returns: { ok, file, content_sha256, diagnostics, diagnostic_count
               [, inlined_siblings], commit_header, submission }.
    """
    _recv_ts = _ts_now()
    if (content or "").strip():
        # Owner ruling 2026-08-24: patch.lean is itself the draft of the
        # proofs/ text — no drafts stacked on drafts. The string mode let
        # an agent validate an in-memory candidate, never write it back,
        # and honestly report "validated" while the canonical file sat
        # unchanged (union_closed autopsy).
        return _arg_help(
            "validate_file",
            "`content` is not accepted — the DISK file is the authority. "
            "Write your candidate first (`apply_edit` edits patch.lean "
            "in place; `write_file` creates a stub), then call "
            "validate_file() for patch.lean or "
            'validate_file(file="new_<slug>.lean") for a stub')
    meta = _current_session()
    if meta is None:
        return json.dumps({"error": "no session",
            "_server_recv_ts": _recv_ts, "_server_send_ts": _ts_now()})
    err = _ensure_backend_ready()
    if err:
        return json.dumps({"error": err,
            "_server_recv_ts": _recv_ts, "_server_send_ts": _ts_now()})
    if not meta.problem:
        return json.dumps({"error": "no problem on session metadata",
            "_server_recv_ts": _recv_ts, "_server_send_ts": _ts_now()})
    _attempts = meta.target_path.parent.resolve()
    _fname = (file or "").strip() or meta.target_path.name
    _fpath = (_attempts / _fname).resolve()
    if (_fpath.parent != _attempts
            or (_fpath.name != meta.target_path.name
                and not _fpath.name.startswith("new_"))):
        return json.dumps({
            "error": (f"`file` must name this session's "
                      f"{meta.target_path.name} or a new_<slug>.lean "
                      f"beside it; got {file!r}"),
            "_server_recv_ts": _recv_ts, "_server_send_ts": _ts_now()})
    try:
        content = _fpath.read_text(encoding="utf-8")
    except OSError as e:
        return json.dumps({
            "error": (f"cannot read {_fname} ({e}) — write it first: "
                      f"`apply_edit` edits patch.lean in place, "
                      f"`write_file` creates a stub"),
            "_server_recv_ts": _recv_ts, "_server_send_ts": _ts_now()})
    if not content.strip():
        return json.dumps({
            "error": f"{_fname} is empty on disk — write it first",
            "_server_recv_ts": _recv_ts, "_server_send_ts": _ts_now()})
    _content_sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
    _hb = _heartbeat_gate(meta, content)
    if _hb is not None:
        return json.dumps(
            {"ok": False, "held": True, "heartbeat_budget": _hb,
             "diagnostics": [], "diagnostic_count": 0,
             "_server_recv_ts": _recv_ts, "_server_send_ts": _ts_now()},
            ensure_ascii=False)
    meta.hb_limit = _hb_declared(content) or meta.hb_limit
    # Metaprogramming gate — the candidate is about to be elaborated, and
    # the sibling stubs folded in with it are agent text too.
    _mp = _metaprog_error(content, "candidate")
    if _mp is not None:
        return json.dumps({"ok": False, "error": _mp, "diagnostic_count": 0,
                           "diagnostics": [],
                           "_server_recv_ts": _recv_ts,
                           "_server_send_ts": _ts_now()}, ensure_ascii=False)
    # Build the SAME single compilation unit the claimed-session tools
    # elaborate: framework imports + Defs opens + referenced sibling stubs
    # (`new_<slug>.lean` in the attempts dir, not importable until commit)
    # + content. `line_map` is always returned (imports/opens are prefix
    # even with no siblings) so diagnostics remap uniformly.
    full_content, line_map, inlined_slugs = _build_compilation_unit(
        content, meta.problem, meta.workspace, meta.target_path.parent,
        extra_opens=_harvest_open_lines(meta.file_content),
        own_name=_fpath.name)

    t0 = time.perf_counter()
    diags: list = []
    elaborate_failed = False
    elaborate_error = ""
    timed_out = False
    axioms_sub: "dict | None" = None
    _slot_kind: str = "unknown"
    backend = _state.backend
    # validate_file uses a slot like apply_edit — swap_in=False (we'll
    # overwrite). After the call we mark slot as orphan (None) so the
    # next caller doesn't think this candidate content "belongs" to
    # anyone.
    try:
        with _acquire_slot(meta, swap_in=False) as (slot, _slot_kind):
            with _elab_gate(slot.slot_uri, meta):
                slot.file_version += 1
                backend.clear_diagnostics(slot.slot_uri)
                backend.did_change_full(slot.slot_path, full_content,
                                        slot.file_version)
                try:
                    backend.wait_for_diagnostics(slot.slot_uri,
                                                 slot.file_version,
                                                 timeout=120)
                except (TimeoutError, RuntimeError):
                    # Elaboration didn't confirm within the budget. Do
                    # NOT swallow into a clean verdict — record it so
                    # the response reports indeterminate, not a false
                    # ok:true (#102).
                    timed_out = True
            try:
                diags = backend.diagnostics_for(slot.slot_uri)
                # Pre-commit axiom mirror — needs the slot while it
                # still holds this candidate, and a clean elaboration
                # (collectAxioms wants a final cmd state).
                if not timed_out and not any(
                        _format_diag(d).get("severity") == "error"
                        for d in diags):
                    axioms_sub = _axioms_submission(
                        backend, slot, content, meta)
            finally:
                # validate_file's content isn't the session's "real"
                # mirror, just a probe. Clear content_pipeline_id so the
                # next tool call (still on this claimed slot) didChanges
                # back to the session's `file_content`.
                #
                # IN A `finally` BECAUSE THE SLOT IS ALREADY DIRTY. The
                # candidate text went in at `did_change_full` above; if
                # anything after that raises, the outer handler reports
                # the failure and the slot keeps the CANDIDATE text
                # under the SESSION's ownership marker — every later
                # `errors_at` then serves the probe's diagnostics as the
                # file's, hot, until something else invalidates. Nothing
                # here is allowed to skip the disown.
                slot.content_pipeline_id = None
    except Exception as exc:  # noqa: BLE001 — reported, not swallowed
        # `ok: false` with zero diagnostics and no reason reads, to an
        # agent, as "your file is broken and I won't say where". Every
        # failure that lands here is the FRAMEWORK's (slot gone, backend
        # restarting, LSP transport dead), so name it: an agent that
        # cannot tell "your Lean is wrong" from "my Lean is down" will
        # rewrite a correct proof (2026-08-11, same flattening family as
        # the slot-claim message above).
        elaborate_failed = True
        elaborate_error = f"{type(exc).__name__}: {exc}"
        diags = []

    formatted = [_format_diag(d) for d in diags]
    if line_map is not None:
        formatted = _remap_inlined_diags(formatted, line_map)
    has_error = any(f.get("severity") == "error" for f in formatted)
    if elaborate_failed:
        has_error = True
    dur = time.perf_counter() - t0
    n_diags = len(formatted)
    formatted = _collapse_repeats(formatted)
    response = {
        # A timeout means we never confirmed the file is clean, so it must
        # not surface as ok:true — report indeterminate (#102).
        "ok": not has_error and not timed_out,
        "file": _fname,
        "content_sha256": _content_sha,
        "diagnostic_count": n_diags,
        "diagnostics": formatted,
        "elapsed_s": round(time.perf_counter() - t0, 1),
        "_server_recv_ts": _recv_ts,
        "_server_send_ts": _ts_now(),
    }
    # `ok` is the zero-ERRORS verdict and sorry is warning-severity, so
    # a sorry-bearing unit reads ok:true — legal for stubs and
    # decomposition patches, but ~20 agents read it as "done" (owner
    # ruling 2026-08-24: keep the boolean, surface the fact beside it).
    _sorries = [d for d in formatted
                if str(d.get("severity")) == "warning"
                and "sorry" in str(d.get("message", ""))]
    if _sorries:
        response["sorries"] = [
            {"line": d.get("line"), "message": d.get("message"),
             **({"also_lines": d["also_lines"]}
                if d.get("also_lines") else {})}
            for d in _sorries]
        if response["ok"]:
            response["sorries_note"] = (
                "`ok` means zero ERRORS; these sorry warnings remain — "
                "legal in a stub or decomposition patch, not in a "
                "finished proof")
    _note_diagnostics(meta, formatted, time.perf_counter() - t0)
    if timed_out:
        response["timed_out"] = True
        response["error"] = ("validate_file elaboration did not complete "
                             "within 120s; result indeterminate")
    if elaborate_failed:
        response["error"] = (
            f"validate_file could not run: {elaborate_error}. This is a "
            "FRAMEWORK-side fault (Lean slot or backend), not a verdict "
            "on your file — the empty diagnostics list says nothing "
            "about it. Retry this call; do not rewrite the proof on "
            "the strength of this result.")
        response["framework_fault"] = True
    if inlined_slugs:
        # Tell the agent which sibling sub-goal stubs were inlined so a
        # citation could be resolved; diagnostics are already remapped to
        # this content's own line numbers.
        response["inlined_siblings"] = inlined_slugs
    # The header the framework will inject into this file at commit
    # (already part of this probe's compilation unit) — visibility for
    # the agent, which writes none of these lines itself (task #84).
    response["commit_header"] = _commit_header_for(
        content, meta.problem, meta.workspace, meta.target_path.parent,
        extra_opens=_harvest_open_lines(meta.file_content))
    # 07-29 feedback: an agent read these as "my file was edited".
    # 08-02 feedback: and read the list as the file's FINAL imports, so a
    # sibling import it had written itself looked stripped. These are the
    # lines that still need ADDING — one already in the file needs none.
    response["commit_header"]["note"] = (
        "what the framework ADDS at commit; do not write these yourself. "
        "Imports already in your file are kept, and are absent here only "
        "because nothing needs adding")
    # Does this green mean what a green usually means? The sandbox inlines
    # sibling stubs; commit imports sibling MODULES. Where those two views
    # can disagree, say so here rather than letting the disagreement reach
    # the agent later disguised as `Unknown identifier` (#179 hid behind
    # exactly that reading for a week, 37 reports).
    response["parity"] = _parity_for(
        content, meta.problem, meta.workspace, inlined_slugs,
        response["commit_header"], goal_id=meta.goal_id)
    # Submission mirror (#8 / P2): the commit-time citation + annotation gates,
    # surfaced here so a clean Lean elaboration that would still be bounced at
    # commit is flagged pre-commit. Separate from `diagnostics` (Lean) so the
    # agent reads "elaborates" and "commit will accept" independently.
    submission: "dict" = {
        "annotation": _annotation_submission(
            content, is_mint=meta.target_path.name.startswith("new_forward")),
        "decl_head": _declhead_submission(content)}
    ns = _namespace_submission(content, meta.problem)
    if ns is not None:
        submission["namespace"] = ns
    if axioms_sub is not None:
        # Pre-commit mirror of the commit axiom gate (2026-08-18):
        # `ok: false` here rides `commit_will_reject` like every other
        # submission gate, so a native_decide proof learns its fate at
        # validate time instead of after the full build.
        submission["axioms"] = axioms_sub
    cite = _citation_submission(content, meta.problem, meta.workspace,
                                set(inlined_slugs), kind=meta.kind)
    if cite is not None:
        submission["citation"] = cite
    # D-lite (task #5): predict the SPLIT — the deterministic commit-policy
    # verdicts the single-unit elaboration structurally cannot surface.
    attempts_dir = meta.target_path.parent
    stub_map: "dict[str, str]" = {}
    for _slug, _text in _collect_referenced_sibling_stubs(
            attempts_dir, content, meta.target_path.name):
        stub_map[_slug] = _text
    # content itself may BE one of the batch stubs (agent validates
    # new_<slug>.lean directly) — include it under its own slug.
    _own = _GW_DECL_HEAD_RE.search(content)
    if _own and (attempts_dir / f"new_{_own.group(2)}.lean").is_file():
        stub_map.setdefault(_own.group(2), content)
    if stub_map:
        sv = assemble.split_visibility_issues(stub_map, problem=meta.problem)
        submission["split_visibility"] = {"ok": not sv, "issues": sv}
        sc = _slug_collision_submission(
            stub_map, meta.problem, meta.workspace)
        if sc is not None:
            submission["slug_collision"] = sc
    ls = _locked_signature_submission(content, attempts_dir)
    if ls is not None:
        submission["locked_signature"] = ls
    so = _stale_olean_submission(content, meta.problem, meta.workspace)
    if so is not None:
        submission["stale_oleans"] = so
    # Top-level `ok` is the LEAN verdict only (zero errors, no timeout);
    # the submission gates are the COMMIT verdict and were readable only
    # by walking into `submission`. Two workers keyed on `ok` and shipped
    # something commit then bounced (2026-08-06 feedback). Say it at the
    # top level too — the two axes stay separate, but a clean elaboration
    # can no longer read as "good to ship" while a gate is failing.
    _failing = sorted(k for k, v in submission.items()
                      if isinstance(v, dict) and v.get("ok") is False)
    if _failing:
        response["commit_will_reject"] = _failing
    response["submission"] = submission
    _log_for(meta, {"event": "tool_call", "name": "validate_file",
                    "args": {"content_lines": full_content.count("\n") + 1},
                    "duration_s": dur,
                    "slot_kind": _slot_kind,
                    "diagnostic_count": len(formatted),
                    "has_error": has_error,
                    "timed_out": timed_out})
    if _fpath == meta.target_path.resolve():
        # Identity record for the commit gate: the exact bytes the last
        # validate saw. Commit compares the file's hash against this —
        # an edit after the final validate is caught there instead of
        # sailing through on a stale green (autopsy 2026-08-24).
        try:
            (_attempts / "_validated.json").write_text(json.dumps({
                "sha256": _content_sha, "ok": response["ok"],
                "at": _ts_now()}), encoding="utf-8")
        except OSError:
            pass
    return json.dumps(response, ensure_ascii=False)


# ─── REST endpoints ─────────────────────────

@mcp.custom_route("/register", methods=["POST"])
async def register(request: Request):
    """Open a new session. Phase 2: stash metadata only, lazy-load
    target content into a slot at first tool call."""
    try:
        data = await request.json()
    except Exception as e:
        return JSONResponse({"error": f"invalid JSON: {e}"},
                            status_code=400)
    required = ("pipeline_id", "target_path", "problem", "workspace")
    missing = [k for k in required if k not in data]
    if missing:
        return JSONResponse({"error": f"missing keys: {missing}"},
                            status_code=400)
    log_path = data.get("log_path")
    kind = data.get("kind")
    try:
        _goal_id = int(data["goal_id"]) if data.get("goal_id") else None
    except (TypeError, ValueError):
        _goal_id = None
    token, err = _register_session_internal(
        pipeline_id=str(data["pipeline_id"]),
        target_path=Path(data["target_path"]),
        problem=str(data["problem"]),
        workspace=Path(data["workspace"]),
        log_path=Path(log_path) if log_path else None,
        kind=str(kind) if kind else None,
        goal_id=_goal_id,
    )
    if err:
        return JSONResponse({"error": err}, status_code=500)
    return JSONResponse({"session_token": token}, status_code=200)


@mcp.custom_route("/release/{token}", methods=["POST"])
async def release(request: Request):
    """Drop session metadata. Idempotent on unknown tokens."""
    token = request.path_params["token"]
    _release_session_internal(token)
    return JSONResponse({"ok": True}, status_code=200)


# ─── Interactive editor session (serve UI) ────────────────
#
# The browser's InfoView: one RESERVED slot, claimed via
# /interactive/register, full-buffer synced via /interactive/sync
# (one didChange + elaborate, goal at the cursor rides the same
# response), cursor-only moves via /interactive/goal (no re-elaborate
# on the hot slot). The buffer lives on a scratch file under
# `.asterism/eval/` (apply_edit's write-through lands there — never on
# real problem files). Stale sessions fall to the same 900s claim
# sweep as pipelines.

def _interactive_meta(token: str) -> "SessionMetadata | None":
    with _state.sessions_lock:
        meta = _state.sessions.get(token)
    return meta if meta is not None and meta.kind == "interactive" else None


@mcp.custom_route("/interactive/register", methods=["POST"])
async def interactive_register(request: Request):
    """Claim the reserved slot for a browser editor session."""
    try:
        data = await request.json()
    except Exception as e:
        return JSONResponse({"error": f"invalid JSON: {e}"},
                            status_code=400)
    ws = _state.workspace
    if ws is None:
        return JSONResponse({"error": "backend not ready"},
                            status_code=503)
    content = str(data.get("content") or WARMUP_CONTENT)
    scratch_dir = ws / ".asterism" / "eval"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    scratch = scratch_dir / f"interactive_{uuid.uuid4().hex[:8]}.lean"
    scratch.write_text(content, encoding="utf-8")
    def _claim() -> "tuple[str, str | None]":
        return _register_session_internal(
            pipeline_id=f"interactive-{scratch.stem.split('_')[1]}",
            target_path=scratch, problem="", workspace=ws,
            log_path=None, kind="interactive", interactive=True,
        )

    token, err = _claim()
    if err and err.startswith("interactive slot busy"):
        # Last editor wins. The holder is either an orphan (serve
        # hard-killed before its release — otherwise it waits out the
        # 900s sweep) or another live tab; either way the session the
        # user is opening NOW is the one that matters. Pipeline slots
        # are untouchable by construction — this evicts interactive
        # claims only.
        with _state.sessions_lock:
            stale = [t for t, m in _state.sessions.items()
                     if m.kind == "interactive"]
        for t in stale:
            _release_session_internal(t)
        token, err = _claim()
    if err:
        scratch.unlink(missing_ok=True)
        busy = err.startswith("interactive slot busy")
        return JSONResponse({"error": err},
                            status_code=409 if busy else 500)
    return JSONResponse({"session_token": token}, status_code=200)


@mcp.custom_route("/interactive/sync", methods=["POST"])
async def interactive_sync(request: Request):
    """Replace the session buffer with the browser's full text, wait
    for elaboration, return diagnostics — plus the goal at the cursor
    when (line, col) ride along."""
    try:
        data = await request.json()
    except Exception as e:
        return JSONResponse({"error": f"invalid JSON: {e}"},
                            status_code=400)
    token = str(data.get("token") or "")
    meta = _interactive_meta(token)
    if meta is None:
        return JSONResponse({"error": "unknown interactive session"},
                            status_code=404)
    _session_ctx.set(token)
    # A FULL-BUFFER SET, not an edit. The editor sends what the buffer
    # now contains; there is no anchor and no old text to name. This
    # used to call `apply_edit(1, end, content)` — the line-range
    # signature retired on 2026-08-10 (`1d7ad006`) — so every sync since
    # has been a TypeError surfacing as HTTP 500. The guard test could
    # not see it: it greps this module for the string "apply_edit"
    # rather than calling the endpoint, so it passed on a call that
    # could never run.
    _content = str(data.get("content") or "")
    # ITS OWN SCAN NOW. This entry used to be exempt from the
    # metaprogramming gate on the grounds that it delegated to
    # `apply_edit`, which has one — and that delegation is what has just
    # been removed, so the exemption's premise went with it. Every
    # gateway path that hands text to a worker calls this first.
    _mp = _metaprog_error(_content, meta.target_path.name)
    if _mp is not None:
        return JSONResponse({"error": _mp}, status_code=400)
    meta.file_content = _content
    # Write through to the scratch file, exactly as `apply_edit` did for
    # this endpoint before. Not bookkeeping: `goal_at` — which the same
    # request calls when a cursor rides along, and which every cursor
    # move calls — starts by adopting DISK as the source of truth. A
    # mirror-only sync would be reverted to the registration-time text
    # by the next goal query, and the editor would show goals for a file
    # the owner no longer has.
    try:
        meta.target_path.write_text(_content, encoding="utf-8")
    except OSError as e:
        return JSONResponse({"error": f"scratch write failed: {e}"},
                            status_code=500)
    backend = _state.backend
    diags: list = []
    converged = False
    try:
        with _acquire_slot(meta, swap_in=False) as (slot, _kind):
            with _elab_gate(slot.slot_uri, meta):
                slot.file_version += 1
                backend.clear_diagnostics(slot.slot_uri)
                merged, _line_map = _compilation_for(meta)
                backend.did_change_full(slot.slot_path, merged,
                                        slot.file_version)
                converged = _diags_converged(backend, slot)
            diags = backend.diagnostics_for(slot.slot_uri)
    except Exception as exc:  # noqa: BLE001 — reported, not swallowed
        return JSONResponse({"error": f"sync failed: {exc}"},
                            status_code=500)
    resp = {
        "diagnostics": diags,
        "goal": None,
        "note": None,
        # Whether Lean FINISHED. Every agent-facing tool already carries
        # this bit; the editor discarded it, so a timed-out elaborate
        # showed the owner an empty error list — the same fake-clean the
        # bit exists to prevent, on the one surface a human trusts most.
        "converged": converged,
    }
    if not converged:
        resp["note"] = ("still elaborating — an empty diagnostic list "
                        "here means 'no news yet', not 'clean'")
    line, col = data.get("line"), data.get("col")
    if isinstance(line, int):
        goal_raw = await goal_at(line, int(col or 0))
        goal = json.loads(goal_raw)
        resp["goal"] = goal.get("goal")
        resp["note"] = goal.get("note") or resp["note"]
    return JSONResponse(resp, status_code=200)


@mcp.custom_route("/interactive/goal", methods=["POST"])
async def interactive_goal(request: Request):
    """Cursor moved, text unchanged: goal only (hot slot, no swap)."""
    try:
        data = await request.json()
    except Exception as e:
        return JSONResponse({"error": f"invalid JSON: {e}"},
                            status_code=400)
    token = str(data.get("token") or "")
    if _interactive_meta(token) is None:
        return JSONResponse({"error": "unknown interactive session"},
                            status_code=404)
    _session_ctx.set(token)
    goal_raw = await goal_at(int(data.get("line") or 1),
                             int(data.get("col") or 0))
    goal = json.loads(goal_raw)
    if goal.get("error"):
        return JSONResponse({"error": goal["error"]}, status_code=500)
    return JSONResponse({"goal": goal.get("goal"),
                         "note": goal.get("note")}, status_code=200)


@mcp.custom_route("/interactive/release", methods=["POST"])
async def interactive_release(request: Request):
    """Release the editor session and its scratch file. Idempotent."""
    try:
        data = await request.json()
    except Exception:
        data = {}
    token = str(data.get("token") or "")
    meta = _interactive_meta(token)
    _release_session_internal(token)
    if meta is not None:
        try:
            meta.target_path.unlink(missing_ok=True)
        except OSError:
            pass
    return JSONResponse({"ok": True}, status_code=200)


def _olean_dest_for(workspace: Path, target_path: Path) -> Path | None:
    """Derive `.lake/build/lib/lean/<module path>.olean` for a Lean
    source under `workspace`. Returns None if the path isn't under
    workspace or doesn't end in `.lean`."""
    try:
        rel = target_path.resolve().relative_to(workspace.resolve())
    except ValueError:
        return None
    if rel.suffix != ".lean":
        return None
    return (workspace / ".lake" / "build" / "lib" / "lean"
            / rel.with_suffix(".olean"))


def _verify_sync(target: Path, content: str, *, write_olean: bool,
                  axioms_for: str | None, constants_for: str | None = None,
                  decl_info: bool = False,
                  decl_info_constants: bool = False,
                  rpc_timeout: int) -> dict:
    """Sync core of /verify. MUST run off the asyncio event loop —
    `_acquire_slot` does blocking polling on a per-slot lock, which
    starves all other handlers (/register, /release, /health, MCP tool
    calls) when concurrent verify requests pile up.

    miniF2F 20-problem pilot 2026-05-12 hit this: 15 simultaneous
    Builder spawns each calling /verify → event loop frozen for
    cumulative slot-acquire durations → subsequent /register
    requests time out at urllib's 120s budget → entire daemon
    deadlocks despite gateway being technically alive.

    The fix is to offload this whole sync section into asyncio's
    default threadpool via `asyncio.to_thread(_verify_sync, ...)`
    from the async handler. Event loop stays responsive; the slot-
    acquire's blocking polling no longer blocks other endpoints."""
    _mp = _metaprog_error(content, Path(target).name)
    if _mp is not None:
        return {"ok": False, "error": _mp, "diagnostic_count": 0,
                "diagnostics": [], "_status": 400}
    backend = _state.backend
    workspace = _state.workspace or target.parent
    probe_id = f"verify:{uuid.uuid4().hex[:8]}"
    meta = SessionMetadata(
        pipeline_id=probe_id,
        target_path=target,
        problem="",
        workspace=workspace,
        log_path=None,
        file_content=content,
    )

    olean_path: Path | None = None
    olean_written = False
    axioms: list[str] | None = None
    axiom_error: str | None = None
    pending_anchors: list[dict] | None = None
    top_kind: str | None = None
    top_is_prop: bool | None = None
    top_module: str | None = None
    closure_error: str | None = None
    decl_info_result: dict | None = None
    decl_info_error: str | None = None
    diags: list = []

    try:
        # /verify is a one-shot probe with no registered session →
        # use borrow mode to grab any free slot. After release the
        # slot's content_pipeline_id is cleared so the slot's
        # registered owner (if any) re-loads its own content on its
        # next acquire (paying one cold_warmup).
        with _acquire_slot(meta, swap_in=True, borrow=True) as (slot, _slot_kind):
            # Confirm the slot's diagnostics correspond to the content we
            # just swapped in, BEFORE reading them. `_acquire_slot`'s swap
            # wait is silently swallowed on a transient (a fresh slot still
            # flushing warmup diagnostics at startup; a prior borrow's
            # elaborate still in flight), and `diagnostics_for` is
            # versionless — it returns the last-published set for the slot
            # URI. Without this re-wait, an unconfirmed swap leaves
            # `diagnostics_for` reflecting a prior/concurrent occupant's
            # stale diagnostics, surfacing a phantom error (e.g. an
            # "expected token" parse error) against our target even though
            # it elaborates clean. Re-wait at our version; on failure mark
            # the probe transient so the caller retries rather than trusts
            # a stale verdict. (Root-caused 2026-06-29: the Backward
            # decomposition gate logged spurious `lake_build_error:
            # <stub>:L:C expected token` on freshly-placed stubs that build
            # clean cold — 2/2 at gateway startup.) A genuine parse error
            # still surfaces: the wait succeeds (version applied, reporter
            # done) and `diagnostics_for` returns the real error.
            try:
                backend.wait_for_diagnostics(
                    slot.slot_uri, slot.file_version, timeout=60)
            except (TimeoutError, RuntimeError) as _diag_exc:
                return {
                    "error": f"diagnostics unconfirmed for swapped-in "
                             f"content (v{slot.file_version}): {_diag_exc}",
                    "transient": True,
                }
            diags = backend.diagnostics_for(slot.slot_uri)
            formatted = [_format_diag(d) for d in diags]
            has_error = any(f.get("severity") == "error" for f in formatted)

            # Optional RPC calls — only on successful elaborate, since
            # writeOlean / collectAxioms need a final cmd state. The
            # custom RPCs run inside the slot worker via lake serve's
            # `$/lean/rpc/call` dispatch.
            if not has_error:
                if write_olean:
                    olean_path = _olean_dest_for(workspace, target)
                    if olean_path is not None:
                        olean_path.parent.mkdir(parents=True, exist_ok=True)
                        try:
                            r = backend.rpc_call(
                                slot.slot_uri,
                                "Asterism.writeOlean",
                                {"destPath": str(olean_path)},
                                timeout=rpc_timeout,
                            )
                            olean_written = bool(r.get("ok"))
                            if not olean_written:
                                axiom_error = (
                                    f"writeOlean error: {r.get('error')}"
                                )
                        except Exception as e:
                            olean_written = False
                            axiom_error = (
                                f"writeOlean RPC failed: "
                                f"{type(e).__name__}: {e}"
                            )

                if axioms_for:
                    try:
                        r = backend.rpc_call(
                            slot.slot_uri,
                            "Asterism.printAxioms",
                            {"fqName": axioms_for},
                            timeout=rpc_timeout,
                        )
                        if r.get("found"):
                            axioms = list(r.get("axioms") or [])
                        else:
                            axiom_error = (
                                f"printAxioms: {r.get('error') or 'not found'}"
                            )
                    except Exception as e:
                        axiom_error = (
                            f"printAxioms RPC failed: "
                            f"{type(e).__name__}: {e}"
                        )

                if constants_for:
                    try:
                        r = backend.rpc_call(
                            slot.slot_uri,
                            "Asterism.anchorClosure",
                            {"fqName": constants_for},
                            timeout=rpc_timeout,
                        )
                        if r.get("found"):
                            pending_anchors = list(r.get("pending") or [])
                            top_kind = r.get("topKind")
                            top_is_prop = bool(r.get("topIsProp"))
                            top_module = r.get("topModule")
                        else:
                            closure_error = (
                                f"anchorClosure: {r.get('error') or 'not found'}"
                            )
                    except Exception as e:
                        closure_error = (
                            f"anchorClosure RPC failed: "
                            f"{type(e).__name__}: {e}"
                        )

                if decl_info:
                    try:
                        r = backend.rpc_call(
                            slot.slot_uri,
                            "Asterism.declInfo",
                            {"includeSignatures": True,
                             "includeUsedConstants": decl_info_constants},
                            timeout=rpc_timeout,
                        )
                        if r.get("ok"):
                            decl_info_result = {
                                "commands": list(r.get("commands") or []),
                                "decls": list(r.get("decls") or []),
                            }
                        else:
                            decl_info_error = (
                                f"declInfo: {r.get('error') or 'not ok'}"
                            )
                    except Exception as e:
                        decl_info_error = (
                            f"declInfo RPC failed: "
                            f"{type(e).__name__}: {e}"
                        )

            # Probe (verify_file) wrote stand-alone content into the
            # slot; clear so next tool call didChanges the session's
            # actual content back in.
            slot.content_pipeline_id = None
    except Exception as e:
        return {
            "error": f"slot acquire failed: {type(e).__name__}: {e}",
            "_status": 500,
        }

    formatted = [_format_diag(d) for d in diags]
    has_error = any(f.get("severity") == "error" for f in formatted)
    return {
        "ok": not has_error,
        "diagnostic_count": len(formatted),
        "diagnostics": formatted,
        "olean_written": olean_written,
        "olean_path": str(olean_path) if olean_path else None,
        "axioms": axioms,
        "axiom_error": axiom_error,
        "pending_anchors": pending_anchors,
        "top_kind": top_kind,
        "top_is_prop": top_is_prop,
        "top_module": top_module,
        "closure_error": closure_error,
        "decl_info": decl_info_result,
        "decl_info_error": decl_info_error,
    }


@mcp.custom_route("/verify", methods=["POST"])
async def verify(request: Request):
    """Unified verify endpoint: didChange the file's content into a
    worker slot, optionally write the resulting `.olean` to disk,
    optionally run `Asterism.printAxioms` on a constant in it.

    Body: {
      "target_path":  "/abs/path.lean",        # required
      "write_olean":  true,                    # default: true
      "axioms_for":   "Problems.foo.main",     # optional fq name
      "decl_info":    false,                   # per-decl structured facts
                                               #   via Asterism.declInfo —
                                               #   the syntactic oracle that
                                               #   replaces regex extraction
                                               #   (task: declInfo RPC)
      "rpc_timeout":  60,                      # default: 30 — applied to
                                               #   writeOlean + printAxioms
                                               #   RPCs. Caller-driven so
                                               #   library promotion can
                                               #   raise it for big Roots
                                               #   without bloating
                                               #   short-path callers.
    }
    Returns: {
      "ok":               bool,
      "diagnostics":      [{line,col,severity,message}, ...],
      "diagnostic_count": int,
      "olean_written":    bool,
      "olean_path":       str | null,
      "axioms":           [str, ...] | null,
      "axiom_error":      str | null,
      "decl_info":        {commands: [...], decls: [...]} | null,
      "decl_info_error":  str | null,
    }

    Replaces the prior `lake build` + `lake env lean #print axioms`
    pair: the verify, the olean publish, and the axiom probe all run
    in the same worker process against the same just-elaborated
    environment.

    Slot ownership: the slot stays claimed by this session for its
    lifetime (1:1 binding); only `content_pipeline_id` is cleared
    after the verify call so the next tool call from the same session
    didChanges the session's `file_content` back into the slot.

    Concurrency: the sync slot-acquire + LSP RPC work runs in a
    thread offloaded from the asyncio event loop via
    `asyncio.to_thread`. Without this, sync polling in
    `_acquire_slot` would freeze the event loop and starve other
    handlers (/register, /release, /health, MCP tool calls) under
    concurrent verify load — observed under the miniF2F 20-problem
    benchmark, 2026-05-12.
    """
    import asyncio
    try:
        data = await request.json()
    except Exception as e:
        return JSONResponse({"error": f"invalid JSON: {e}"},
                            status_code=400)
    target_path = data.get("target_path")
    if not target_path:
        return JSONResponse({"error": "missing target_path"},
                            status_code=400)
    target = Path(target_path).resolve()
    if not target.exists():
        return JSONResponse({"error": f"file not found: {target}"},
                            status_code=404)
    write_olean: bool = bool(data.get("write_olean", True))
    axioms_for: str | None = data.get("axioms_for")
    constants_for: str | None = data.get("constants_for")
    decl_info: bool = bool(data.get("decl_info", False))
    decl_info_constants: bool = bool(data.get("decl_info_constants", False))
    try:
        rpc_timeout = int(data.get("rpc_timeout", 30))
        if rpc_timeout <= 0:
            rpc_timeout = 30
    except (TypeError, ValueError):
        rpc_timeout = 30

    err = _ensure_backend_ready()
    if err:
        return JSONResponse({"error": err}, status_code=503)
    try:
        content = target.read_text(encoding="utf-8")
    except OSError as e:
        return JSONResponse({"error": f"read failed: {e}"},
                            status_code=500)

    # Off-load the blocking slot acquire + RPC work to a thread so the
    # asyncio event loop stays free to serve /register, /release,
    # /health, MCP tool calls, and other concurrent /verify requests.
    result = await asyncio.to_thread(
        _verify_sync, target, content,
        write_olean=write_olean, axioms_for=axioms_for,
        constants_for=constants_for, decl_info=decl_info,
        decl_info_constants=decl_info_constants,
        rpc_timeout=rpc_timeout,
    )
    status = result.pop("_status", 200)
    return JSONResponse(result, status_code=status)


def _verify_session_sync(token: str, content: str, *, write_olean: bool,
                         axioms_for: str | None, rpc_timeout: int,
                         wait_timeout: int,
                         decl_info: bool = False,
                         decl_info_constants: bool = False) -> dict:
    """Sync core of /verify_session: verify `content` on the slot CLAIMED by the
    registered session `token` (claimed mode — NOT a borrow), so the session's
    OWN warm slot serves the check.

    Why this exists alongside `/verify` (borrow): a borrow evicts the slot's
    content (forcing the owner a re-warmup) and grabs an arbitrary slot, so it
    can't reuse a held session's already-loaded import closure. A framework
    caller that holds a session (the Library cleanup mechanical gates: ONE
    file-level session per file) wants the OPPOSITE — verify whole-file
    candidates against the slot whose closure is already that file's. The first
    didChange pays the import load (~25s); every subsequent whole-file gate on
    the held slot is a ~4-5s body re-elaborate instead of a fresh ~25s `lake env
    lean`. Mirrors `_verify_sync` but uses the claimed slot + an explicit
    didChange of the candidate (no `_compilation_for` swap, no eviction).

    NOTE the warm win only applies to SAME-closure (whole-file) candidates; a
    minimal-import isolate (e.g. a single decl on `import Mathlib`) is a
    different closure → re-warmup → no faster (#108), and would evict the file's
    closure, so those stay on cold `lake env lean`."""
    backend = _state.backend
    if backend is None:
        return {"error": "backend not ready", "_status": 503}
    with _state.sessions_lock:
        meta = _state.sessions.get(token)
    if meta is None:
        return {"error": f"unknown session token {token[:8]}", "_status": 404}
    _mp = _metaprog_error(content, meta.target_path.name)
    if _mp is not None:
        return {"ok": False, "error": _mp, "diagnostic_count": 0,
                "diagnostics": [], "_status": 400}

    olean_path: Path | None = None
    olean_written = False
    axioms: list[str] | None = None
    axiom_error: str | None = None
    decl_info_result: dict | None = None
    decl_info_error: str | None = None
    diags: list = []
    timed_out = False
    try:
        # Claimed mode (borrow=False), swap_in=False: locate the session's own
        # slot, then didChange the candidate ourselves (like validate_file).
        with _acquire_slot(meta, swap_in=False) as (slot, _slot_kind):
            with _elab_gate(slot.slot_uri, meta):
                slot.file_version += 1
                backend.clear_diagnostics(slot.slot_uri)
                backend.did_change_full(slot.slot_path, content,
                                        slot.file_version)
                try:
                    backend.wait_for_diagnostics(slot.slot_uri,
                                                 slot.file_version,
                                                 timeout=wait_timeout)
                except (TimeoutError, RuntimeError):
                    timed_out = True
            diags = backend.diagnostics_for(slot.slot_uri)
            formatted0 = [_format_diag(d) for d in diags]
            has_error0 = any(f.get("severity") == "error" for f in formatted0)
            if not has_error0 and not timed_out and decl_info:
                # Mirrors /verify's declInfo block: per-decl structured
                # facts off the elaboration just paid for (statement mint
                # piggyback — backward's placed-file verify runs here when
                # the pipeline holds its own session slot).
                try:
                    r = backend.rpc_call(
                        slot.slot_uri, "Asterism.declInfo",
                        {"includeSignatures": True,
                         "includeUsedConstants": decl_info_constants},
                        timeout=rpc_timeout)
                    if r.get("ok"):
                        decl_info_result = {
                            "commands": list(r.get("commands") or []),
                            "decls": list(r.get("decls") or []),
                        }
                    else:
                        decl_info_error = (
                            f"declInfo: {r.get('error') or 'not ok'}")
                except Exception as e:
                    decl_info_error = (f"declInfo RPC failed: "
                                       f"{type(e).__name__}: {e}")
            if not has_error0 and not timed_out and (write_olean or axioms_for):
                if write_olean:
                    olean_path = _olean_dest_for(meta.workspace,
                                                 meta.target_path)
                    if olean_path is not None:
                        olean_path.parent.mkdir(parents=True, exist_ok=True)
                        try:
                            r = backend.rpc_call(
                                slot.slot_uri, "Asterism.writeOlean",
                                {"destPath": str(olean_path)},
                                timeout=rpc_timeout)
                            olean_written = bool(r.get("ok"))
                            if not olean_written:
                                axiom_error = f"writeOlean error: {r.get('error')}"
                        except Exception as e:
                            axiom_error = (f"writeOlean RPC failed: "
                                           f"{type(e).__name__}: {e}")
                if axioms_for:
                    try:
                        r = backend.rpc_call(
                            slot.slot_uri, "Asterism.printAxioms",
                            {"fqName": axioms_for}, timeout=rpc_timeout)
                        if r.get("found"):
                            axioms = list(r.get("axioms") or [])
                        else:
                            axiom_error = (f"printAxioms: "
                                           f"{r.get('error') or 'not found'}")
                    except Exception as e:
                        axiom_error = (f"printAxioms RPC failed: "
                                       f"{type(e).__name__}: {e}")
            # The candidate is a probe, not the session's committed mirror —
            # clear so the session's next tool call didChanges its own content
            # back in (mirror validate_file).
            slot.content_pipeline_id = None
    except Exception as e:
        return {"error": f"claimed slot acquire failed: "
                f"{type(e).__name__}: {e}", "_status": 500}

    formatted = [_format_diag(d) for d in diags]
    has_error = any(f.get("severity") == "error" for f in formatted)
    return {
        "ok": not has_error and not timed_out,
        "diagnostic_count": len(formatted),
        "diagnostics": formatted,
        "olean_written": olean_written,
        "olean_path": str(olean_path) if olean_path else None,
        "axioms": axioms,
        "axiom_error": axiom_error,
        "decl_info": decl_info_result,
        "decl_info_error": decl_info_error,
        "timed_out": timed_out,
    }


@mcp.custom_route("/verify_session", methods=["POST"])
async def verify_session(request: Request):
    """Verify candidate `content` on the slot CLAIMED by a registered session
    (claimed mode, no borrow eviction) — the warm-slot path for framework-side
    gates that hold a session, notably the Library cleanup mechanical gates
    (ONE file-level session per file, verifying whole-file candidates against
    its already-loaded import closure).

    Body: { "token": <session token>, "content": <full Lean source>,
            "write_olean": false, "axioms_for": null, "decl_info": false,
            "rpc_timeout": 30, "wait_timeout": 240 }
    Returns: same shape as /verify, plus "timed_out"."""
    import asyncio
    try:
        data = await request.json()
    except Exception as e:
        return JSONResponse({"error": f"invalid JSON: {e}"}, status_code=400)
    token = data.get("token")
    content = data.get("content")
    if not token:
        return JSONResponse({"error": "missing token"}, status_code=400)
    if content is None:
        return JSONResponse({"error": "missing content"}, status_code=400)
    write_olean = bool(data.get("write_olean", False))
    axioms_for = data.get("axioms_for")
    decl_info = bool(data.get("decl_info", False))
    decl_info_constants = bool(data.get("decl_info_constants", False))
    try:
        rpc_timeout = int(data.get("rpc_timeout", 30))
        if rpc_timeout <= 0:
            rpc_timeout = 30
    except (TypeError, ValueError):
        rpc_timeout = 30
    try:
        wait_timeout = int(data.get("wait_timeout", 240))
        if wait_timeout <= 0:
            wait_timeout = 240
    except (TypeError, ValueError):
        wait_timeout = 240

    err = _ensure_backend_ready()
    if err:
        return JSONResponse({"error": err}, status_code=503)
    result = await asyncio.to_thread(
        _verify_session_sync, str(token), str(content),
        write_olean=write_olean, axioms_for=axioms_for,
        rpc_timeout=rpc_timeout, wait_timeout=wait_timeout,
        decl_info=decl_info, decl_info_constants=decl_info_constants)
    status = result.pop("_status", 200)
    return JSONResponse(result, status_code=status)


@mcp.custom_route("/compute", methods=["POST"])
async def compute_endpoint(request: Request):
    """Run sandboxed Python here, because the tool server cannot.

    `compute` shipped on 2026-08-10 as a tool on the `asterism_tools`
    STDIO server, which claude spawns as its own child. Measured
    2026-08-11: **no subprocess started from that server ever runs** —
    the sandbox interpreter timed out at 60s on a bare `print('alive')`
    twelve consecutive times, and the control spawn (the very
    interpreter hosting the server, same flags, same cwd) hung
    identically. From a shell the same command takes 95ms. So it was
    never the venv, and the tool had not worked once in production.

    This process has no such problem: it spawns `lake serve` and a
    pool of lean workers continuously. And the stdio server already
    reaches it over plain HTTP (`knowledge/pin_check._gateway_probe`
    borrows `/verify` on every loogle call), so the client side is a
    proven path rather than a new one.

    Body:    {"code": "<python>"}
    Returns: {"rc": int, "output": str, "seconds": float, "killed": str}

    `killed` carries the limit that stopped the run ("timeout" /
    "memory" / ""), and it is part of the wire format rather than a
    detail because it is the half of the answer that says what to do
    next. It was omitted at first, and the caller rebuilt the result
    with `killed=""`: a timed-out sweep reached the Strategist as the
    standing header and NOTHING else — no output (the kill took the
    buffer), no "stopped at the 30s limit, shrink the search". The
    agent's next act was to spend a call on `print("hello", 1+1)` to
    find out whether the tool was alive at all (2026-08-12).

    The sandbox's own guarantees are unchanged — separate interpreter,
    no framework on `sys.path`, memory/wall-clock caps, PEP 578 audit
    hook — because this moves WHERE `sandbox.run` is called, not what
    it does.
    """
    try:
        data = await request.json()
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"error": f"invalid JSON: {e}"}, status_code=400)
    code = str(data.get("code") or "")
    from ...sandbox import run as _sandbox_run
    try:
        res = await asyncio.to_thread(_sandbox_run, code)
    except Exception as e:  # noqa: BLE001 — reported, never swallowed
        return JSONResponse(
            {"rc": 1, "output": f"[compute] gateway-side failure: "
                                f"{type(e).__name__}: {e}", "seconds": 0.0})
    return JSONResponse({"rc": res.rc, "output": res.output,
                         "seconds": res.seconds, "killed": res.killed})


@mcp.custom_route("/warm_target", methods=["POST"])
async def warm_target(request: Request):
    """RAM-ledger control plane (owner design 2026-08-25): the
    dispatcher's ledger tick POSTs {target, min_available_gb}; the
    gateway converges its open-slot count toward it (up via the
    background converger, down at release time). The reply reports the
    current open/free counts — the dispatcher's Lean admission gates on
    `open`, which keeps the /register "no free slot" contract intact
    while the pool moves."""
    try:
        data = await request.json()
    except Exception:  # noqa: BLE001 — malformed body is a client bug
        return JSONResponse({"error": "JSON body required"},
                            status_code=400)
    try:
        from ...core.ram_ledger import MAX_SLOTS
        target = max(1, min(int(data.get("target")), MAX_SLOTS))
    except (TypeError, ValueError):
        return JSONResponse({"error": "target must be an int"},
                            status_code=400)
    _state.warm_target = target
    try:
        _state.warm_min_available_gb = float(
            data.get("min_available_gb") or 0.0)
    except (TypeError, ValueError):
        _state.warm_min_available_gb = 0.0
    with _state.sessions_lock:
        open_n = _open_pipeline_slots_locked()
        free_n = sum(1 for s in _state.workers
                     if not s.reserved and not s.closed
                     and s.claimed_by is None)
    if open_n != target and _state.first_warm_done:
        _kick_warm_converger()
    return JSONResponse({"target": target, "open": open_n,
                         "free": free_n,
                         "warming": _state.warm_converger_on,
                         # the ledger's slot-coefficient instrument —
                         # same TTL-cached reading /health serves
                         "slot_private_mb": _slot_private_mb_cached(),
                         # CPU-gate congestion (owner call 2026-08-25):
                         # sustained elab_waiting > 0 means the machine,
                         # not RAM, is the binding axis.
                         **elab_gate_stats()})


@mcp.custom_route("/health", methods=["GET"])
async def health_route(request: Request):
    """Liveness check. Reports worker pool status + active sessions
    + slot acquire counters (so operator can compute hot/cold ratio
    over the run, especially relevant at pool > W where churn
    dominates framework overhead).

    503 while the first warm runs. HTTP opens before that warm now, so
    this endpoint answers minutes earlier than it used to — and every
    reader of it means "is the gateway USABLE", not "is the port open".
    `lifecycle._ping_health` catches `URLError`, of which `HTTPError` is
    a subclass, so a 503 reads as absent exactly like the old connection
    refusal did: the warm window stays invisible to the reuse gate and
    `gateway-starting.txt` stays its only presence signal."""
    if not _state.first_warm_done:
        return JSONResponse(
            {"warming": True, "backend_ready": False, "pid": os.getpid(),
             "error": WARMING_MSG}, status_code=503)
    # Snapshot fast-path (owner approval 2026-08-27): the governor
    # thread rebuilds the payload every pass, so a /health under a
    # saturated accept queue costs the event loop a dict lookup, not a
    # pool walk — status polling stops feeding the very backlog it is
    # trying to observe (flagship: accept queue 157 deep at 83% CPU).
    with _HEALTH_SNAPSHOT_LOCK:
        snap_at = _HEALTH_SNAPSHOT["at"]
        snap = _HEALTH_SNAPSHOT["val"]
    age = time.monotonic() - snap_at
    if snap is not None and age < 3 * _GOVERNOR_INTERVAL_SEC:
        return JSONResponse({**snap, "snapshot_age_s": round(age, 1)})
    # Governor hiccup: compute inline rather than serve a dead reading.
    return JSONResponse({**_health_payload(), "snapshot_age_s": 0.0})


# ─── Session header → contextvar middleware ──────────────

class SessionHeaderMiddleware:
    """ASGI middleware: read X-Asterism-Session header, set
    `_session_ctx` so tool bodies (which run in the same asyncio task
    → same contextvar scope) can resolve their session via
    `_current_session()`."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope.get("headers", []))
            raw = headers.get(b"x-asterism-session")
            token = raw.decode("ascii") if raw else None
            ctx_token = _session_ctx.set(token)
            try:
                await self.app(scope, receive, send)
            finally:
                _session_ctx.reset(ctx_token)
        else:
            await self.app(scope, receive, send)


# ─── Entrypoint ─────────────────────────────

def main() -> None:
    # Install SelectorEventLoop policy at the VERY TOP of main, before
    # any thread or asyncio interaction. _start_workers (launched as a
    # daemon thread below) uses asyncio internally via lsp_client, and
    # uvicorn.run() creates its own event loop. Both must see the
    # Selector policy at construction time. Doing this AFTER thread
    # start (as the prior implementation did) was racy and uvicorn
    # ignored the global policy because its default `loop="auto"`
    # bypasses asyncio policy on Windows.
    _install_windows_event_loop_policy()

    workspace_env = os.environ.get("ASTERISM_WORKSPACE")
    if not workspace_env:
        print("[gateway] ASTERISM_WORKSPACE env required",
              file=sys.stderr, flush=True)
        sys.exit(2)
    workspace = Path(workspace_env).resolve()
    from ...core import config as _cfg
    port = _cfg.get(
        "gateway.port", default=8765,
        env_var="ASTERISM_GATEWAY_PORT", cast=int,
        workspace=workspace,
    )
    # Worker count is locked to dispatch.pool — every spawn claims one
    # dedicated worker for its lifetime (#118, 1:1 binding). No separate
    # gateway.workers knob.
    w_count = _cfg.get(
        "dispatch.pool", default=4,
        env_var="ASTERISM_POOL", cast=int,
        workspace=workspace,
    )
    # Adaptive RAM ledger (owner design 2026-08-25): the dispatcher's
    # ledger tick will own the slot count via /warm_target, so the
    # LAUNCH count only decides how fast first_warm opens the Lean
    # plane — start small, let the converger grow the pool in the
    # background while work already flows.
    try:
        from ...core import ram_ledger as _rl
        _budget_gb = _rl.parse_budget(_rl.env_budget_spec(workspace),
                                      _rl.total_gb())
    except Exception:  # noqa: BLE001 — the ledger must not stop launch
        _budget_gb = None
    _state.ram_budget_gb = _budget_gb   # the freezer reads this
    if _budget_gb is not None:
        _target0 = _rl.compute_target_slots(budget_gb=_budget_gb,
                                            nl_demand=0)
        w_count = max(1, min(8, _target0))
        _state.warm_target = _target0
        print(f"[gateway] RAM ledger active — budget {_budget_gb:.1f} GB,"
              f" launch warms {w_count} slot(s), converger grows toward "
              f"{_target0}", file=sys.stderr, flush=True)
    # Reserved slots for the serve UI's interactive editor — outside
    # the pipeline pool entirely (pipeline=slot identity holds both
    # ways: spawns never see them, the editor never sees spawn slots).
    n_interactive = _cfg.get(
        "gateway.interactive_slots", default=1,
        env_var="ASTERISM_INTERACTIVE_SLOTS", cast=int,
        workspace=workspace,
    )
    # The claim ceiling is DERIVED, never a second hand-tuned constant:
    # the previous literal was chosen against a 780s worker life, and
    # when `spawn_timeout_sec` doubled nobody came back to it (2026-08-11
    # — the sweep then took slots from live workers). Twice the spawn
    # budget covers a main spawn plus its rescue/postmortem successor
    # under the same claim, and anything past that is an anomaly the
    # sweep should report rather than accommodate.
    _spawn_budget = _cfg.get(
        "dispatch.spawn_timeout_sec", default=1800,
        env_var="ASTERISM_SPAWN_TIMEOUT_SEC", cast=int,
        workspace=workspace,
    )
    _state.claim_ceiling_sec = max(2.0 * float(_spawn_budget),
                                   _LEASE_TTL_SEC + 900.0)

    # Downsize to what physical memory can hold — an overcommitted pool
    # pages its own warm-up to death (5 workers × multi-GB Mathlib on an
    # 8 GB machine: slot 0 not done after 300s). Yaml is intent; RAM is
    # law. The configured value still goes to /health so the daemon's
    # reuse gate compares yaml-to-yaml.
    from ..lifecycle import ram_clamped_pool
    _state.workers_configured = w_count
    w_count, clamp_msg = ram_clamped_pool(w_count, n_interactive)
    if clamp_msg:
        print(f"[gateway] RAM clamp: {clamp_msg}",
              file=sys.stderr, flush=True)

    print(f"[gateway] starting; workspace={workspace} port={port} "
          f"workers={w_count}+{n_interactive} interactive",
          file=sys.stderr, flush=True)

    # Claim the port BEFORE warming, and hold the socket for uvicorn.
    # A collision must fail in seconds — the 2026-07-07 Test.Test3 run
    # warmed 7 minutes and then died on bind (Errno 10048) because an
    # earlier gateway held the port. bind-only (no listen): probes get
    # instant refusals during warm; asyncio listens when serving starts.
    import socket as _socket
    try:
        http_sock = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
        if os.name != "nt":
            # TIME_WAIT remnants of a just-killed gateway's accepted
            # connections block a bare bind for up to ~60s on POSIX even
            # after the listener is provably gone — _kill_stale_gateway's
            # three-signal proof passed and this bind still EADDRINUSE'd,
            # twice on boarding day (2026-08-24; same family as the zen
            # shim's rebind). POSIX SO_REUSEADDR admits no second LIVE
            # listener, so the port-singleton guarantee is intact where
            # exclusivity is real; Windows keeps the bare bind (its
            # REUSEADDR would let a rival bind over a live gateway).
            http_sock.setsockopt(_socket.SOL_SOCKET,
                                 _socket.SO_REUSEADDR, 1)
        http_sock.bind(("127.0.0.1", port))
    except OSError as e:
        print(f"[gateway] FATAL: port {port} is already taken ({e}) — "
              f"another gateway is running or warming; refusing to race it",
              file=sys.stderr, flush=True)
        sys.exit(4)

    # Presence signal for the warm window (HTTP opens only after the
    # pool warms, so /health can't see us yet): daemon-side
    # `start_gateway` waits on this marker instead of spawning a rival.
    from ..lifecycle import gateway_starting_marker
    _marker = gateway_starting_marker(workspace)
    try:
        _marker.parent.mkdir(parents=True, exist_ok=True)
        _marker.write_text(str(os.getpid()), encoding="utf-8")
    except OSError:
        pass
    import atexit as _atexit
    _atexit.register(lambda: _marker.unlink(missing_ok=True))

    threading.Thread(target=_start_workers,
                     args=(workspace, w_count, n_interactive),
                     daemon=True).start()
    # Cross-platform memory-cap enforcement (the Windows Job Object
    # does not exist off-Windows; see _weight_kill_over_cap).
    threading.Thread(target=_weight_watchdog_run,
                     name="weight-watchdog", daemon=True).start()
    # Stale-claim sweep: reclaims gateway slots whose /release was
    # dropped (urlopen failure during teardown, worker crash before
    # AttemptsContext.__exit__, etc.). Cheap when nothing is stale.
    threading.Thread(target=_stale_claim_sweep_loop,
                     daemon=True, name="gateway-stale-claim-sweep").start()
    # Wedge recovery: replace the backend if a non-terminating elaborate
    # pins a worker (2026-06-12 hang fix — see `_wedge_watchdog_loop`).
    threading.Thread(target=_wedge_watchdog_loop,
                     daemon=True, name="gateway-wedge-watchdog").start()
    # The warm is watched from a thread and HTTP opens NOW, rather than
    # after it (2026-08-12). `core/warmup` dispatches Strategist and
    # Scholar during this window on purpose — a cold slot-0 warm was
    # measured at 300s+, once seven minutes — and `compute` lives in
    # this process, so waiting here left the NL layer without its
    # calculator for exactly the minutes it is the only thing running.
    #
    # Nothing about the warm moves ONTO the serving thread: the pool
    # already inits on `_start_workers`'s thread and only the WAIT was
    # here. Every Lean surface refuses fast until `first_warm_done`
    # (`_ensure_backend_ready`), so no request can put that wait back
    # on the event loop.
    #
    # Inner warm budget scales with the EFFECTIVE slot count: the warm
    # loop legally tolerates 300s per slot serially, so a flat 600s
    # contradicted our own tolerance at any pool ≥ 2. The daemon's
    # outer wait scales from the CONFIGURED (≥ effective) count and
    # stays the more generous of the two.
    _warm_budget = 300.0 * (w_count + n_interactive) + 300.0

    app = mcp.streamable_http_app()
    app = SessionHeaderMiddleware(app)

    import uvicorn
    # Important: uvicorn.run / uvicorn.Config(loop="asyncio") would
    # internally call `asyncio.set_event_loop_policy(
    # WindowsProactorEventLoopPolicy())` on Windows, OVERRIDING our
    # earlier WindowsSelectorEventLoopPolicy install at main() top.
    # Observed in SG run #18: gateway died at +82min with the same
    # IocpProactor.accept WinError 64 race that 475c318 / 1db4e8c
    # attempted to fix.
    #
    # Fix: build the asyncio loop manually with SelectorEventLoop,
    # then use uvicorn.Config(loop="none") so uvicorn doesn't touch
    # the policy. `Server.serve()` is an async coroutine — we run it
    # on our pre-built loop directly. This is the only way to keep
    # SelectorEventLoop active across uvicorn's startup.
    # Serve on the socket bound at startup (asyncio listens on it) —
    # the port was ours for the whole warm, so no bind can fail here.
    #
    # The Server object exists BEFORE the warm watcher starts: the
    # watcher's only way to end this process is `should_exit`, and a
    # warm that fails in the first second must not find that handle
    # still unset.
    if sys.platform == "win32":
        import asyncio as _asyncio
        loop = _asyncio.SelectorEventLoop()
        _asyncio.set_event_loop(loop)
        config = uvicorn.Config(app, host="127.0.0.1", port=port,
                                log_level="warning", loop="none")
    else:
        loop = None
        # Non-Windows: manual Server so the pre-bound socket is used.
        config = uvicorn.Config(app, host="127.0.0.1", port=port,
                                log_level="warning")
    server = uvicorn.Server(config)
    _state.http_server = server
    threading.Thread(target=_watch_initial_warm, daemon=True,
                     name="gateway-warm-watch",
                     args=(_warm_budget, _marker)).start()
    print(f"[gateway] HTTP open on {port} — pool warming in background",
          file=sys.stderr, flush=True)

    try:
        if loop is not None:
            try:
                loop.run_until_complete(server.serve(sockets=[http_sock]))
            finally:
                loop.close()
        else:
            server.run(sockets=[http_sock])
    finally:
        # Reap the Lean backend subtree on gateway exit (SIGTERM from the
        # daemon's atexit, or any shutdown). Without this, `lake serve`'s
        # `lean --server`/`--worker` children orphan on every gateway
        # exit/restart and accumulate (rule-8 / 2026-06-12 smoke-test
        # finding). uvicorn handles SIGTERM gracefully → serve() returns
        # → this finally runs.
        _b = _state.backend
        if _b is not None:
            try:
                _b.shutdown()
            except Exception:
                try:
                    _b._kill_tree()
                except Exception:
                    pass

    # A warm that never finished is still fatal, and still rc 3: the
    # daemon's `start_gateway` distinguishes "died" from "still coming"
    # by this exit, and a process that served 503s forever would hang
    # every retry behind a gateway that can never do Lean work.
    if _state.warm_failed:
        sys.exit(3)


def _install_windows_event_loop_policy() -> None:
    """Switch the asyncio event loop policy to Selector on Windows.

    Default Python 3.8+ on Windows is ProactorEventLoop (IOCP-based).
    Under sustained HTTP load with frequent connection churn we hit
    `OSError(WinError 64, '指定的網路名稱無法使用 / The specified
    network name is no longer available')` inside
    `IocpProactor.accept.accept_coro()` — the accept task raises but
    asyncio's default handler does NOT re-arm the accept loop, so the
    listening socket stays bound while no new connections are accepted.
    The HTTP endpoint becomes "half-working": in-flight worker sessions
    keep responding, but framework `/verify` POSTs from the daemon get
    WinError 10061 connection-refused (kernel rejects SYN because
    nothing's calling AcceptEx anymore).

    SelectorEventLoop on Windows uses select() instead of IOCP and
    doesn't run into this race. Throughput ceiling is lower (~few
    hundred concurrent connections) but Asterism gateway concurrency
    is bounded by `gateway.workers` (default 3) — well within the
    Selector ceiling.

    Observed in SG run #14 (2026-05-11): gateway crash at +~4h45min
    of sustained pool=15 / workers=3 load. See
    `runs/sg_run_14.md` CUT REASON for forensic detail.
    """
    if sys.platform != "win32":
        return
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
