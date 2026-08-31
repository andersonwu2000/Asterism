"""`validate_file`, and the sync cores the two /verify routes offload.

Split out of `gateway.py` 2026-08-29 (A1-4b) unchanged, decorators and
all: the agent's pre-commit probe (`validate_file` — the fifth MCP tool,
and the last one still registered from the facade's own body), the
interactive-session lookup the three `/interactive/*` routes share, the
olean destination map, and the two sync bodies `/verify` and
`/verify_session` hand to `asyncio.to_thread`.

Those HTTP handlers stay in the package `__init__` with the rest of the
route table, so `_verify_sync`, `_verify_session_sync` and
`_interactive_meta` keep the FACADE as their patch target — the
consumer never moved. `validate_file`'s own dependencies move WITH it:
a module-level `from .x import name` copies the binding, so the patch
target is the CONSUMING module, and a `validate_file` test now patches
`gateway.verify._ensure_backend_ready` / `_build_compilation_unit`.
`_ensure_backend_ready` is four-sided as of this cut — here for
`validate_file`, `gateway.sessions` for register, `gateway.rpc` for the
four tools, the facade for the two /verify routes.

Naming: the `/verify` handler is `verify_route`, NOT `verify` — the bare
name shadowed this module on the package namespace exactly as the
`/health` handler shadowed `health.py` (`1bfcebb9`), and it would have
turned every `monkeypatch.setattr(gateway.verify, ...)` into a silent
no-op against a coroutine function.

`_olean_dest_for` does not re-export: both its consumers are the two
sync cores in this file.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from pathlib import Path

from ...quality import names as _names
from ...state import assemble
from ...state import db as _db
from .backend import _ensure_backend_ready
from .elab import _elab_gate
from .gates import (
    _ancestor_cycle,
    _GW_DECL_HEAD_RE,
    _annotation_submission,
    _axioms_submission,
    _citation_submission,
    _declhead_submission,
    _locked_signature_submission,
    _namespace_submission,
    _slug_collision_submission,
    _stale_olean_submission,
)
from .leantext import (
    _build_compilation_unit,
    _collapse_repeats,
    _collect_referenced_sibling_stubs,
    _commit_header_for,
    _format_diag,
    _harvest_open_lines,
    _metaprog_error,
    _parity_for,
    _remap_inlined_diags,
)
from .rpc import (
    _await_elaboration,
    _arg_help,
    _hb_declared,
    _heartbeat_gate,
    _note_diagnostics,
)
from .server import _offload_to_thread, mcp
from .sessions import _acquire_slot, _current_session
from .state import SessionMetadata, _log_for, _state, _ts_now


def _hoist_conditional(response: dict) -> dict:
    """#5 (owner approval 2026-08-31): a green whose truth depends on
    unproved sub-goals must SAY so at the headline. The facts already
    lived in this response — `parity.state == "conditional"` and the
    warn-severity `submission.citation` issues (shelved siblings
    included) — but workers key on `ok`/`diagnostic_count` and read a
    decomposition patch's clean probe as a finished proof (21 reports;
    4 on 2026-08-31 alone). Rebuild the dict so `conditional_on` sits
    DIRECTLY after `ok`. `unresolved` parity is left alone: that is a
    framework defect with its own loud note, not legitimate waiting."""
    deps: "set[str]" = set()
    parity = response.get("parity")
    if isinstance(parity, dict) and parity.get("state") == "conditional":
        deps.update(str(x) for x in (parity.get("depends_on") or ()))
    sub = response.get("submission")
    cite = sub.get("citation") if isinstance(sub, dict) else None
    if isinstance(cite, dict):
        for issue in cite.get("issues") or ():
            if (isinstance(issue, dict)
                    and issue.get("severity") == "warn"
                    and issue.get("slug")):
                deps.add(str(issue["slug"]))
    if not deps:
        return response
    note = ("`ok` is CONDITIONAL on these unproved sub-goals: this "
            "deliverable is a decomposition step, not a finished proof "
            "— each listed goal still needs its own proof (details: "
            "`parity`, `submission.citation`)")
    out: dict = {}
    for k, v in response.items():
        out[k] = v
        if k == "ok":
            out["conditional_on"] = sorted(deps)
            out["conditional_note"] = note
    if "conditional_on" not in out:  # no `ok` key — still say it
        out["conditional_on"] = sorted(deps)
        out["conditional_note"] = note
    return out


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
               [, inlined_siblings]
               [, conditional_on, conditional_note], commit_header, submission }.
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
    _wall_info: "dict | None" = None
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
                # Compute to completion or hit the wall (worker killed,
                # slot re-warmed, hard failure) — never an indeterminate
                # "maybe clean" verdict (#102, owner design 2026-08-29).
                _conv, _wall_info = _await_elaboration(
                    backend, slot, meta, content=content)
                timed_out = not _conv
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
        **({"status": "elab_wall", "elab_wall": _wall_info}
           if timed_out else {}),
        "file": _fname,
        "content_sha256": _content_sha,
        "diagnostic_count": n_diags if not timed_out else None,
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
        response["error"] = (
            "validate_file hit the elaboration wall: the worker was killed "
            "and its slot re-warmed — a FAILURE, not an indeterminate result "
            "(see `elab_wall.teaching`)")
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
    # Pre-commit mirror of the name gate (owner ruling 2026-08-29): a
    # top-level name another file of the problem already declares.
    nm = _names.submission(
        content, _db.problem_dir(meta.workspace, meta.problem),
        own_rel=f"proofs/{meta.target_path.name}")
    if nm is not None:
        submission["names"] = nm
    # The editing tools refuse an ancestor citation outright; a file that
    # carries one anyway (written outside apply_edit) is told here.
    cy = _ancestor_cycle(content, meta)
    if cy is not None:
        submission["ancestor_cycle"] = cy
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
    response = _hoist_conditional(response)
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


def _interactive_meta(token: str) -> "SessionMetadata | None":
    with _state.sessions_lock:
        meta = _state.sessions.get(token)
    return meta if meta is not None and meta.kind == "interactive" else None


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
    wall_info: "dict | None" = None
    try:
        # Claimed mode (borrow=False), swap_in=False: locate the session's own
        # slot, then didChange the candidate ourselves (like validate_file).
        with _acquire_slot(meta, swap_in=False) as (slot, _slot_kind):
            with _elab_gate(slot.slot_uri, meta):
                slot.file_version += 1
                backend.clear_diagnostics(slot.slot_uri)
                backend.did_change_full(slot.slot_path, content,
                                        slot.file_version)
                # One wall for every elaboration (owner ruling 2026-08-30):
                # the commit verify used a bare wait on the caller's
                # timeout — no CPU/RAM meter, no re-warm, no teaching —
                # and a heavy candidate ran for 100 minutes at commit
                # after hitting the CPU wall four times through
                # apply_edit. `wait_timeout` is accepted for the API and
                # superseded by the wall's own budgets.
                _conv, wall_info = _await_elaboration(
                    backend, slot, meta, content=content)
                timed_out = not _conv
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
    if wall_info is not None:
        # the wall's verdict rides the response like validate_file's:
        # a hard failure with the teaching, never a count to misread
        return {
            "ok": False, "timed_out": True, "status": "elab_wall",
            "elab_wall": wall_info, "error": wall_info["teaching"],
            "diagnostic_count": None, "diagnostics": [],
            "olean_written": False, "olean_path": None, "axioms": None,
            "axiom_error": None, "decl_info": None, "decl_info_error": None,
        }
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
