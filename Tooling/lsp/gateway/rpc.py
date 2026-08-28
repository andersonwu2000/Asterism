"""The four in-spawn MCP tools — apply_edit, goal_at, errors_at,
withdraw_stub.

Split out of `gateway.py` 2026-08-29 (A1-4a) unchanged, decorators and
all. `@mcp.tool` registers at IMPORT time, so the facade's
`from .rpc import …` is what keeps the roster at five tools (these four
plus `validate_file`, which moved to `verify.py` with cut 4b) in the
same registration order they were declared in.

`_echo_removed` and `_ECHO_END_CHARS` arrive here from `sessions.py`
with this cut: `apply_edit` is their only consumer, and what an edit
removed is a tool answer, not part of the session lifecycle.

The submission gates (`_citation_submission`,
`_locked_signature_submission`) were in the facade until cut 4b, so
`apply_edit` imported them at CALL time — a module-level import back
into the facade would have closed a cycle. They live in `gates.py` now,
a leaf, so the import is module-level like every other and their
tool-side patch target is `gateway.rpc`. Everything else is imported at
module level too, which copies the binding into THIS namespace — so a
tool-side test patches `gateway.rpc.<name>` (`_ensure_backend_ready`,
`_current_session`, `_compilation_for`, …), never the facade and never
the defining module.

`_ELABORATING_WARNING`, `_ECHO_END_CHARS` and the three `_HB_*`
constants do not re-export: their only consumers are in this file, so a
facade patch would go vacuous and an AttributeError is the better
answer.
"""
from __future__ import annotations

import hashlib
import json
import re
import time

from .. import edits as _edits
from .backend import _ensure_backend_ready
from .elab import _elab_gate
from .gates import _citation_submission, _locked_signature_submission
from .leantext import (
    _collapse_repeats,
    _compilation_for,
    _format_diag,
    _goal_present,
    _merged_line_for,
    _metaprog_error,
    _remap_inlined_diags,
    _resync_buffer_from_disk,
    _scope_balance,
    _sorry_start_col,
    _summarize_goal,
)
from .server import _offload_to_thread, mcp
from .sessions import _acquire_slot, _current_session
from .state import SessionMetadata, _log_for, _state, _ts_now


#: Head and tail of the echo of a removed region. A head-only cap put
#: the truncation exactly where the evidence lives: an edit that reaches
#: further than intended shows the opening the agent expected and hides
#: the tail it did not mean to lose. Both ends, plus the count of what
#: sits between them, so "I removed more than I thought" is legible
#: without shipping the whole region back (2026-08-11).
_ECHO_END_CHARS = 160


def _echo_removed(removed: str) -> str:
    """What an edit took out, as the agent needs to see it."""
    if len(removed) <= 2 * _ECHO_END_CHARS:
        return removed
    head = removed[:_ECHO_END_CHARS]
    tail = removed[-_ECHO_END_CHARS:]
    n_lines = removed.count("\n") - head.count("\n") - tail.count("\n")
    return (f"{head}\n… [{len(removed) - 2 * _ECHO_END_CHARS} chars / "
            f"{max(n_lines, 0)} lines removed here too] …\n{tail}")


@mcp.tool(structured_output=False)
@_offload_to_thread
def apply_edit(edits: list = None) -> str:
    """Apply one or more anchored edits to the target Lean file.

    Each edit names the TEXT it acts on, not a line number:

        [{"replace": "<exact old text>", "with": "<new text>"},
         {"replace_between": ["<from>", "<to>"], "with": "<new text>"},
         {"insert_after": "<anchor>", "text": "<new text>"}]

    Anchors must match exactly and appear exactly once. For
    `replace_between` the closing anchor need only be unique AFTER the
    opening one — use it to swap a whole tactic block without quoting
    it. BOTH anchors are part of the replaced span: `with` is the
    complete new text, and anything you want kept must be in it. So
    anchor on your OWN block's first and last lines, never on the
    neighbouring declaration — an anchor placed on the next `theorem`
    line deletes that line with the span. Ambiguity is refused rather
    than resolved to the first match: guessing is what silently
    swallowed the lines between the intended close and a later one
    (2026-08-11). `insert_after` splices immediately after the anchor;
    when the anchor ends its line and `text` brings no newline of its
    own, the text starts on a new line (so an inserted import or
    comment never glues onto the anchor's last token).

    If any anchor fails to resolve, NOTHING is applied: the response says
    which edit and how to repair it, the file is unchanged, and your
    other anchors are still valid on resubmission.

    Args:
      edits: list of edit objects (see above).
    """
    _recv_ts = _ts_now()
    meta = _current_session()
    # A refusal is an outcome, and it was the only one that left no
    # trace: `_log_for` sits past every early return below, so when an
    # agent and the framework disagreed about whether an edit had landed
    # there was nothing to consult (08-11, unresolvable to this day).
    # Each refusal now logs before it returns. The no-session branch
    # cannot: there is no session to log against.
    if meta is None:
        return json.dumps({"error":
            "no session — X-Asterism-Session header missing or unknown",
            "_server_recv_ts": _recv_ts, "_server_send_ts": _ts_now()})
    err = _ensure_backend_ready()
    if err:
        _log_for(meta, {"event": "apply_edit", "outcome": "refused"})
        return json.dumps({"error": err,
            "_server_recv_ts": _recv_ts, "_server_send_ts": _ts_now()})
    t0 = time.perf_counter()

    # External Write/Edit may have advanced disk past the mirror; splice
    # against the current on-disk text, not a stale buffer (T1). A
    # FAILED resync aborts the edit: writing through a possibly-stale
    # mirror would overwrite newer on-disk content (resurrection
    # corruption, agent_feedback 2026-07-18).
    _resync_err = _resync_buffer_from_disk(meta)
    if _resync_err:
        _log_for(meta, {"event": "apply_edit", "outcome": "refused"})
        return json.dumps({"error": (
            f"{_resync_err}; edit aborted — the buffer may be stale and "
            "writing through it could clobber newer on-disk content. "
            "Retry, or Read the file and use Write."),
            "_server_recv_ts": _recv_ts, "_server_send_ts": _ts_now()})
    if not edits:
        return _arg_help(
            "apply_edit",
            'the parameter is `edits`, a list \u2014 e.g. '
            'apply_edit(edits=[{"replace": "by norm_num", "with": "by simp"}])')
    try:
        spans = _edits.resolve(meta.file_content, edits)
    except _edits.EditError as exc:
        # Refusal, PRE-elaboration: the file is untouched and the batch
        # cost milliseconds instead of a corrupted proof discovered a
        # round-trip later. That is the whole point of anchoring \u2014 a line
        # number has nothing to check itself against, so a stale one
        # spliced silently (42 agent reports in the week to 2026-08-10).
        _log_for(meta, {"event": "apply_edit", "outcome": "refused"})
        return json.dumps(
            {"edit": "rejected \u2014 file unchanged", **exc.as_dict(),
             "_server_recv_ts": _recv_ts, "_server_send_ts": _ts_now()},
            ensure_ascii=False)

    replaced_text = " | ".join(
        _echo_removed(meta.file_content[s.start:s.end])
        for s in spans if not s.is_insert) or "(insert only)"
    new_content = _edits.apply_spans(meta.file_content, spans)
    _hb = _heartbeat_gate(meta, new_content)
    if _hb is not None:
        # Refused PRE-write, like an unresolvable anchor: the file is
        # untouched and the cost was milliseconds. Asking after the
        # write would be asking after the bill.
        _log_for(meta, {"event": "apply_edit", "outcome": "refused"})
        return json.dumps(
            {"edit": "held — file unchanged", "heartbeat_budget": _hb,
             "_server_recv_ts": _recv_ts, "_server_send_ts": _ts_now()},
            ensure_ascii=False)
    meta.hb_limit = _hb_declared(new_content) or meta.hb_limit
    new_lines = new_content.split(chr(10))
    # Where each edit LANDED, measured on the produced file. Line numbers
    # are output only: the tool measured them, so they cannot be stale
    # the way a caller-supplied one could.
    _shift = 0
    _regions = []
    for s in sorted(spans, key=lambda x: x.start):
        lo = _edits.line_of(new_content, s.start + _shift)
        hi = _edits.line_of(new_content, s.start + _shift + len(s.new_text))
        _regions.append((lo, hi))
        _shift += len(s.new_text) - (s.end - s.start)
    start_line = _regions[0][0]
    end_line = _regions[-1][1]

    # Structural balance, reported UNCONDITIONALLY as a number. The old
    # version warned only when THIS edit broke a previously balanced
    # file, so once a file was unbalanced every later edit went quiet \u2014
    # including the one that added a second stray `end`. Computing a
    # value and then gating it into silence is the "knows but flattens"
    # shape this codebase keeps finding.
    _scope_warn = None
    _bal_after = _scope_balance(new_content)

    # Metaprogramming gate — BEFORE the mirror/disk write-through, so a
    # blocked edit leaves neither the buffer nor the file carrying it.
    _mp = _metaprog_error(new_content, meta.target_path.name)
    if _mp is not None:
        _log_for(meta, {"event": "apply_edit", "outcome": "refused"})
        return json.dumps({"error": _mp, "edit": "rejected — file unchanged",
                           "_server_recv_ts": _recv_ts,
                           "_server_send_ts": _ts_now()},
                          ensure_ascii=False)

    # Echo the post-edit region with CURRENT 1-indexed line numbers (±2 lines
    # of context) so the agent re-anchors from ground truth after every edit
    # instead of tracking line positions itself. Stale positions — line
    # numbers that drifted when a prior edit changed the line count — are what
    # made a later apply_edit splice at the wrong range (duplicated signature,
    # dropped `:= by`, clobbered `have`): the recurring corruption in
    # agent_feedback (C1). Seeing the actual result makes a misfire obvious
    # immediately rather than via a confusing downstream diagnostic.
    _echo = []
    for lo, hi in _regions:
        a, b = max(1, lo - 2), min(len(new_lines), hi + 2)
        _echo += [f"{i}: {new_lines[i - 1]}" for i in range(a, b + 1)]
        _echo.append("")
    # The TAIL, always. Two of the loudest failure reports were a dropped
    # `end` and a duplicated proof body, both at end-of-file, where an
    # echo anchored on the edited region never looks.
    _tail_from = max(1, len(new_lines) - 2)
    _echo.append(f"--- end of file ({len(new_lines)} lines) ---")
    _echo += [f"{i}: {new_lines[i - 1]}"
              for i in range(_tail_from, len(new_lines) + 1)]
    post_edit_region = "\n".join(_echo)

    # Locked-signature tripwire (warning, not a block): the commit gate
    # byte-compares the seeded `s<sid>` signature, so an edit touching
    # it — usually via a drifted range — is doomed at commit. Same
    # helper as validate_file's submission mirror.
    _locked_warn = _locked_signature_submission(
        new_content, meta.target_path.parent)
    if _locked_warn is not None and _locked_warn.get("ok", True):
        _locked_warn = None

    # Disk + mirror hold the RAW patch (write-through for the framework
    # cascade); the slot elaborates the MERGED compilation unit (patch +
    # Defs opens + referenced sibling stubs) so cited siblings resolve and
    # the goal / diagnostics match validate_file and post-commit lake.
    # Mirror must be set before building the unit.
    meta.file_content = new_content
    backend = _state.backend
    # apply_edit overwrites slot content anyway → skip swap-in.
    with _acquire_slot(meta, swap_in=False) as (slot, _slot_kind):
        with _elab_gate(slot.slot_uri, meta):
            slot.file_version += 1
            backend.clear_diagnostics(slot.slot_uri)
            merged, line_map = _compilation_for(meta)
            backend.did_change_full(slot.slot_path, merged,
                                    slot.file_version)
            # `textDocument/waitForDiagnostics` blocks server-side until
            # the doc reaches our version, the reporter has flushed all
            # publishDiagnostics for it, and all command snapshots have
            # elaborated. Replaces the prior fileProgress + 3s-settle
            # polling, which over-waited by ~3s on every tool call.
            converged = _diags_converged(backend, slot)
        diags = backend.diagnostics_for(slot.slot_uri)
        q_line = _merged_line_for(line_map, start_line)
        try:
            result = backend.plain_goal(slot.slot_path,
                                         line=q_line - 1, character=2,
                                         timeout=15)
            goal_text = _summarize_goal(result)
        except Exception as e:
            goal_text = f"<plainGoal failed: {type(e).__name__}: {e}>"
        # The goal at the END of what was just written (2026-08-06
        # feedback ×6, both arms): after a multi-line replacement the
        # agent wants the state at the new `sorry` / next open goal, and
        # `goal_at_edit_start` is the state at the top of the region —
        # so every tactic iteration paid a second `goal_at` round-trip
        # against a ~46s elaboration latency. Skipped when the edit is a
        # single line (both ends are the same query) or a deletion.
        goal_end_text: "str | None" = None
        end_line_after = _regions[-1][1]
        if end_line_after > start_line:
            try:
                q_end = _merged_line_for(line_map, end_line_after)
                goal_end_text = _summarize_goal(backend.plain_goal(
                    slot.slot_path, line=q_end - 1, character=2,
                    timeout=15))
            except Exception as e:
                goal_end_text = f"<plainGoal failed: {type(e).__name__}: {e}>"
        # Slot now has this pipeline's NEW content didChanged in.
        slot.content_pipeline_id = meta.pipeline_id
        slot.line_map = line_map

    # Write through to disk (RAW patch) so the framework cascade reads the
    # agent's edits.
    meta.target_path.write_text(new_content, encoding="utf-8")

    # Diagnostics are in the merged frame → remap to the agent's content
    # frame (drop sibling-region sorry noise, tag sibling-region errors).
    formatted = [_format_diag(d) for d in diags]
    if line_map is not None:
        formatted = _remap_inlined_diags(formatted, line_map)

    # Citation mirror on the live-file path too (2026-07-19, user call):
    # the predictor lived only in validate_file, but agents editing
    # patch.lean via apply_edit ship without ever calling validate — the
    # a5 run burned six commits on cite_unproved_sibling rejects the
    # mirror would have predicted. Cheap (a few classify queries, only
    # when the content carries Problems-imports); surfaced only when
    # something is wrong, so clean edits stay noise-free.
    _own_stubs = {p.stem[len("new_"):]
                  for p in meta.target_path.parent.glob("new_*.lean")}
    _cite = _citation_submission(
        new_content, meta.problem, meta.workspace, _own_stubs,
        kind=meta.kind)
    _n_diags = len(formatted)
    formatted = _collapse_repeats(formatted)
    response = {
        "edit": (f"applied {len(spans)} edit(s) at lines "
                 + ", ".join(f"{a}-{b}" for a, b in _regions)
                 + f"; file is now {len(new_lines)} lines"),
        # Always a number, never a conditional warning: see the note at
        # the splice above.
        "scope_balance": _bal_after,
        "replaced_text": replaced_text,
        "post_edit_region": post_edit_region,
        "goal_at_edit_start": goal_text,
        "diagnostics": formatted,
        **({"goal_at_edit_end": goal_end_text,
            "goal_at_edit_end_note": _GOAL_AT_EDIT_END_NOTE}
           if goal_end_text is not None else {}),
        "diagnostic_count": _n_diags,
        "elapsed_s": round(time.perf_counter() - t0, 1),
        "_server_recv_ts": _recv_ts,
        "_server_send_ts": _ts_now(),
    }
    _note_diagnostics(meta, formatted, time.perf_counter() - t0)
    if not converged:
        response["elaborating"] = True
        response["warning"] = _ELABORATING_WARNING
    if _cite is not None and _cite.get("issues"):
        response["citation"] = _cite
    if _locked_warn is not None:
        response["locked_signature"] = _locked_warn
    if _bal_after != 0:
        response["scope_warning"] = (
            f"{abs(_bal_after)} unclosed `namespace`/`section`/`mutual` — "
            f"add the matching `end`" if _bal_after > 0 else
            f"{abs(_bal_after)} more `end` than there are openers")
    dur = time.perf_counter() - t0
    _log_for(meta, {"event": "tool_call", "name": "apply_edit",
                    "args": {"edits": len(spans),
                             "kinds": [s.kind for s in spans]},
                    "duration_s": dur,
                    "slot_kind": _slot_kind, "converged": converged,
                    "diagnostic_count": len(diags)})
    return json.dumps(response, ensure_ascii=False)


#: Same rule as `knowledge/mcp_tools`: NO TOOL ON THIS SERVER HAS A
#: REQUIRED PARAMETER. A model that guesses a parameter name wrong makes
#: FastMCP's pydantic model raise, and on the Antigravity CLI a raising
#: MCP tool stamps the whole envelope `status: ERROR` — killing the run
#: AND the `--resume` turn that would have collected its feedback.
#: Measured 2026-08-10: `inspect(inspect_requests=…)` cost six spawns
#: their feedback records in one fifteen-minute window. Optional
#: parameters plus a teaching string turn that into one recoverable
#: round-trip. Enumerating plausible aliases is NOT the fix — the next
#: model invents a new name.
def _arg_help(tool: str, hint: str) -> str:
    return json.dumps({"error": f"{tool}: {hint}"}, ensure_ascii=False)


@mcp.tool(structured_output=False)
@_offload_to_thread
def goal_at(line: int = 0, col: int = 0) -> str:
    """Get the Lean proof goal state at a specific position.

    Args:
      line: 1-indexed line number.
      col:  0-indexed character column.
    """
    if not line:
        return _arg_help(
            "goal_at",
            "the parameters are `line` (1-indexed) and `col` (0-indexed), "
            "e.g. goal_at(line=42, col=2)")
    _recv_ts = _ts_now()
    meta = _current_session()
    if meta is None:
        return json.dumps({"error": "no session",
            "_server_recv_ts": _recv_ts, "_server_send_ts": _ts_now()})
    err = _ensure_backend_ready()
    if err:
        return json.dumps({"error": err,
            "_server_recv_ts": _recv_ts, "_server_send_ts": _ts_now()})
    t0 = time.perf_counter()
    backend = _state.backend
    # Pick up any external Write/Edit before swap_in didChanges the
    # mirror into the slot, so the goal query sees current disk (T1).
    _resync_buffer_from_disk(meta)
    # The Write/Edit tools bypass apply_edit's gate — this is where such
    # content would first reach an elaborator, so it is scanned here.
    _mp = _metaprog_error(meta.file_content, meta.target_path.name)
    if _mp is not None:
        return json.dumps({"error": _mp, "_server_recv_ts": _recv_ts,
                           "_server_send_ts": _ts_now()}, ensure_ascii=False)
    resolved_at_sorry: "int | None" = None
    with _acquire_slot(meta, swap_in=True) as (slot, _slot_kind):
        # The slot holds the merged compilation unit; the agent's `line`
        # is in its own content frame, so translate to the merged frame.
        q_line = _merged_line_for(slot.line_map, line)
        # Same honesty signal as errors_at/apply_edit (#106; 07-19: a
        # goal_at blocked ~2min and the agent could not tell timeout
        # from truth): an unconverged elaboration must say so.
        converged = _diags_converged(backend, slot)
        try:
            result = backend.plain_goal(
                slot.slot_path, line=q_line - 1, character=col, timeout=15
            )
            # B#4 fallback: a query at/inside/after a `sorry` token sees the
            # goal already admitted → "no goals". Retry once at the token's
            # START (where the goal is still live — verified 2026-06-22) so
            # peeking at an unedited stub (the documented Builder step 1, and
            # any mid-proof `sorry`) returns the real goal, not a misleading
            # "proof complete".
            if not _goal_present(result):
                s_col = _sorry_start_col(meta, line)
                if s_col is not None and s_col != col:
                    retry = backend.plain_goal(
                        slot.slot_path, line=q_line - 1, character=s_col,
                        timeout=15)
                    if _goal_present(retry):
                        result, resolved_at_sorry = retry, s_col
            goal_text = _summarize_goal(result)
        except Exception as e:
            goal_text = f"<plainGoal failed: {type(e).__name__}: {e}>"
    dur = time.perf_counter() - t0
    _log_for(meta, {"event": "tool_call", "name": "goal_at",
                    "args": {"line": line, "col": col},
                    "duration_s": dur,
                    "slot_kind": _slot_kind})
    resp = {"line": line, "col": col, "goal": goal_text,
            "_server_recv_ts": _recv_ts, "_server_send_ts": _ts_now()}
    if not converged:
        resp["elaborating"] = True
        resp["warning"] = _ELABORATING_WARNING
    if resolved_at_sorry is not None:
        resp["note"] = ("queried position had no goal (a `sorry` admits its "
                        "goal); showing the goal at the `sorry` token "
                        f"(col {resolved_at_sorry})")
    return json.dumps(resp, ensure_ascii=False)


def _diags_converged(backend, slot) -> bool:
    """True iff Lean finished elaborating the slot's current version and
    flushed its publishDiagnostics — i.e. `diagnostics_for` is the FINAL
    answer. False (wait expired / client error) means the stash is a
    snapshot of an unfinished elaborate: an empty list is NOT "clean",
    it is "no news yet". Every tool that returns diagnostics to the
    agent must surface this bit instead of letting a timeout masquerade
    as a clean file (the `errors_at`-fake-clean class, 2026-07-18)."""
    try:
        backend.wait_for_diagnostics(slot.slot_uri, slot.file_version,
                                     timeout=120)
        return True
    except (TimeoutError, RuntimeError):
        return False


#: `set_option maxHeartbeats N`. Lean syntax, not prose — the value is
#: a structured signal the way a decision kind is.
_HB_SET_RE = re.compile(r"set_option\s+maxHeartbeats\s+(\d+)")
_HB_TIMEOUT_MARK = "maximum number of heartbeats"
#: Above this, the gate asks once. NOT a limit on what may land: 11 of
#: this workspace's proved bricks sit at 4M — `_strategy_s24405` among
#: them, a sibling of the strategy this gate was written for — and their
#: comments name the same technique ("large literal-set peeling needs
#: the extra budget"). A big budget is normal practice here; being SLOW
#: about it while blind to the cost is what is not.
_HB_ASK_ABOVE = 1_000_000


def _hb_rank(limit: "int | None") -> float:
    """Order two budgets. `0` means UNLIMITED in Lean, so it sorts above
    every finite value rather than below all of them; `None` is "never
    set", i.e. Lean's own default."""
    if limit is None:
        return 200_000.0
    return float("inf") if limit == 0 else float(limit)


def _hb_declared(content: str) -> "int | None":
    """The largest budget this content asks for, or None."""
    found = [int(m.group(1)) for m in _HB_SET_RE.finditer(content or "")]
    return max(found, key=_hb_rank) if found else None


def _note_diagnostics(meta: SessionMetadata, diags: list,
                      elapsed_s: float) -> None:
    """Remember what a diagnostics call cost and whether Lean gave up on
    a heartbeat budget. Both are inputs the gate quotes back."""
    meta.hb_last_check_s = elapsed_s
    for d in diags or []:
        if _HB_TIMEOUT_MARK in str(d.get("message", "")):
            meta.hb_saw_timeout = True
            return


def _heartbeat_gate(meta: SessionMetadata, content: str) -> "str | None":
    """Ask once before a write buys a slower feedback loop — or None.

    Raising `maxHeartbeats` does not make an elaboration converge; it
    buys a LATER refusal, and every diagnostics call in the session pays
    the difference. Measured 2026-08-12 on g7554: 200k → 1M → 4M took
    the check latency 20s → 96s → 240s, the same three positions timed
    out at every budget, and the spawn died on its 30-minute wall with
    the file never once compiling. Its own last words were "still
    elaborating — let's wait and re-check".

    Two triggers, union, because each is blind where the other sees:
      (a) the budget is large — catches a file that opens at 4M and
          never learns why its checks take minutes;
      (b) the budget goes UP after this session has already been shown a
          heartbeat timeout — catches the 200k→1M step, which (a) would
          sleep through, and it is deliberately not keyed on the timing
          out LINE: an agent's own edits shift line numbers, so an
          exact-position match would mostly miss.

    Confirmation is the identical write resent. That is why the message
    has to SAY so: an agent whose write was refused will otherwise edit
    the content, changing the hash, and read the gate as random."""
    declared = _hb_declared(content)
    if declared is None:
        return None
    # BOTH triggers require this write to RAISE the budget. Without it,
    # (a) re-asks on every edit while the file sits at 4M — each edit is
    # a new content hash — which is a nag, not a gate.
    raised = _hb_rank(declared) > _hb_rank(meta.hb_limit)
    if not raised:
        return None
    escalating = meta.hb_saw_timeout
    if not (escalating or _hb_rank(declared) > _HB_ASK_ABOVE):
        return None
    key = hashlib.sha1((content or "").encode("utf-8")).hexdigest()
    if key in meta.hb_confirmed:
        return None
    meta.hb_confirmed.add(key)

    budget = "UNLIMITED" if declared == 0 else f"{declared:,}"
    cost = (f" Your last diagnostics call took "
            f"{meta.hb_last_check_s:.0f}s" if meta.hb_last_check_s else "")
    if escalating:
        was = ("Lean's default" if meta.hb_limit is None
               else "UNLIMITED" if meta.hb_limit == 0
               else f"{meta.hb_limit:,}")
        head = (
            f"This session has already been shown a heartbeat timeout, and "
            f"this write raises the budget from {was} to {budget}. A "
            f"timeout is Lean saying the elaboration does not converge — a "
            f"larger budget moves the same refusal further away and makes "
            f"every check until then slower.{cost}, against a spawn budget "
            f"measured in minutes. What works instead: bound the quantity "
            f"rather than evaluating it, or lift the heavy step into its "
            f"own `new_<slug>.lean` with a small context and cite it. If "
            f"neither fits, the claim itself is too coarse for one check "
            f"— decline with the cut you would make, and the review loop "
            f"will re-plan it as smaller bricks.")
    else:
        head = (
            f"This file asks for {budget} heartbeats. That is allowed and "
            f"normal here — several proved bricks in this workspace use "
            f"it — but every diagnostics call in this session now waits "
            f"proportionally longer before Lean will answer.{cost}. Budget "
            f"your remaining checks accordingly.")
    return head + (" — Resend this identical write to confirm and it will "
                   "be applied; changing the content asks again.")


_ELABORATING_WARNING = (
    "Lean has NOT finished elaborating this file (120s wait expired) — "
    "the diagnostics here are INCOMPLETE and a count of 0 does NOT mean "
    "the file is clean. Re-run this tool to check again."
)

# `goal_at_edit_end` is a CURSOR SNAPSHOT at the edited region's end
# position, not a verdict on the file — ~38 agent reports treated a
# non-empty goal there as "proof incomplete" and burned a turn
# cross-checking with validate_file, which already answers that
# question. Attached as a sibling key (never inline in the value
# itself) so the field stays machine-parseable while still teaching.
_GOAL_AT_EDIT_END_NOTE = (
    "this is the goal state AT THE CURSOR after the edited region, not "
    "a verdict on the whole file — an open goal here is expected mid-proof. "
    "Use `diagnostics` (or `validate_file`) to know whether the FILE is done."
)


@mcp.tool(structured_output=False)
@_offload_to_thread
def errors_at(line: int | None = None) -> str:
    """Get current diagnostics for the file.

    Args:
      line: Optional 1-indexed line. If set, return only diagnostics
            on that line. If None, return all.
    """
    _recv_ts = _ts_now()
    meta = _current_session()
    if meta is None:
        return json.dumps({"error": "no session",
            "_server_recv_ts": _recv_ts, "_server_send_ts": _ts_now()})
    err = _ensure_backend_ready()
    if err:
        return json.dumps({"error": err,
            "_server_recv_ts": _recv_ts, "_server_send_ts": _ts_now()})
    t0 = time.perf_counter()
    backend = _state.backend
    # Pick up any external Write/Edit before swap_in didChanges the
    # mirror into the slot, so diagnostics track current disk (T1).
    _resync_buffer_from_disk(meta)
    # Same disk-side entry as goal_at (Write/Edit bypass apply_edit).
    _mp = _metaprog_error(meta.file_content, meta.target_path.name)
    if _mp is not None:
        return json.dumps({"error": _mp, "_server_recv_ts": _recv_ts,
                           "_server_send_ts": _ts_now()}, ensure_ascii=False)
    with _acquire_slot(meta, swap_in=True) as (slot, _slot_kind):
        converged = _diags_converged(backend, slot)
        diags = backend.diagnostics_for(slot.slot_uri)
        formatted = [_format_diag(d) for d in diags]
        slot_line_map = slot.line_map
    # Diagnostics come from the merged compilation unit; remap their lines
    # back to the agent's content frame (and drop sibling-region sorry
    # noise / tag sibling-region errors) before any line filter.
    if slot_line_map is not None:
        formatted = _remap_inlined_diags(formatted, slot_line_map)
    if line is not None:
        formatted = [f for f in formatted if f["line"] == line]
    dur = time.perf_counter() - t0
    _log_for(meta, {"event": "tool_call", "name": "errors_at",
                    "args": {"line": line}, "duration_s": dur,
                    "slot_kind": _slot_kind, "converged": converged,
                    "returned_count": len(formatted)})
    # `elapsed_s` as a number, not two timestamps to subtract: a worker
    # blind to what a check costs cannot budget its checks, and this one
    # ran eight of them at 92s average against a 30-minute wall
    # (g7554, 2026-08-12).
    _elapsed = time.perf_counter() - t0
    _note_diagnostics(meta, formatted, _elapsed)
    response = {"diagnostics": formatted, "count": len(formatted),
                "elapsed_s": round(_elapsed, 1),
                "_server_recv_ts": _recv_ts,
                "_server_send_ts": _ts_now()}
    if not converged:
        response["elaborating"] = True
        response["warning"] = _ELABORATING_WARNING
    return json.dumps(response, ensure_ascii=False)


@mcp.tool(structured_output=False)
@_offload_to_thread
def withdraw_stub(slug: str = "") -> str:
    """Withdraw a sub-goal you declared this session: deletes
    `new_<slug>.lean` from your attempts directory.

    Use it when a `new_<slug>.lean` turned out redundant — its content
    got folded into `patch.lean`, or the decomposition went another way.
    A stub left behind is submitted as a sub-goal, and one that declares
    nothing (or the wrong name) is rejected at commit.

    Nothing else is reachable: the path is built from `slug`, must be a
    `new_*.lean`, and must resolve inside this session's attempts
    directory. `patch.lean` is not withdrawable.

    Args:
      slug: the sub-goal's slug — `new_<slug>.lean`, without the prefix
            or the extension.
    """
    # 2026-08-12, g7557: the commit gate told an agent to "delete the
    # file", and the agent has no delete tool — Bash closed on 08-11 and
    # its file surface is write-only. It emptied the file (refused: the
    # gate wants a declaration), then wrote `theorem r4_scratch : True
    # := trivial` purely to satisfy the name check, and did the same to
    # a second dead stub. Two vacuous sub-goals, born proved, proving
    # nothing — and 48 minutes with two `parse_proposal_fail` deaths on
    # the way. A gate must name an action the agent can perform.
    #
    # Deleting adds no destructive power it lacked: it can already
    # overwrite any of these files with `Write`, and `WorkArea.__exit__`
    # rmtrees the whole attempts directory at pipeline exit. What it
    # adds is a way to SAY "withdrawn" instead of inventing one.
    _recv_ts = _ts_now()
    meta = _current_session()
    if meta is None:
        return json.dumps({"error":
            "no session — X-Asterism-Session header missing or unknown",
            "_server_recv_ts": _recv_ts, "_server_send_ts": _ts_now()})
    name = (slug or "").strip()
    if not name:
        return _arg_help(
            "withdraw_stub",
            'the parameter is `slug`, the sub-goal name — e.g. '
            'withdraw_stub(slug="r4_scratch") to drop new_r4_scratch.lean')
    # Strip what an agent is likely to pass by mistake, then demand the
    # remainder be a bare slug: a path separator or `..` never survives.
    if name.startswith("new_"):
        name = name[4:]
    if name.endswith(".lean"):
        name = name[:-5]
    if not re.fullmatch(r"[A-Za-z0-9_]+", name):
        return json.dumps({"error": (
            f"{slug!r} is not a slug. Pass the sub-goal name alone "
            f"(letters, digits, underscore) — the file path is built "
            f"here, not passed in."),
            "_server_recv_ts": _recv_ts, "_server_send_ts": _ts_now()})
    attempts_dir = meta.target_path.parent.resolve()
    target = (attempts_dir / f"new_{name}.lean").resolve()
    if target.parent != attempts_dir or not target.name.startswith("new_"):
        return json.dumps({"error": (
            f"refusing: {target} is outside this session's attempts "
            f"directory or is not a new_<slug>.lean stub."),
            "_server_recv_ts": _recv_ts, "_server_send_ts": _ts_now()})
    if not target.is_file():
        return json.dumps(
            {"withdrawn": False, "slug": name,
             "note": f"new_{name}.lean is not in the attempts directory — "
                     f"nothing to withdraw.",
             "_server_recv_ts": _recv_ts, "_server_send_ts": _ts_now()},
            ensure_ascii=False)
    try:
        target.unlink()
    except OSError as exc:
        return json.dumps({"error": f"could not remove {target.name}: {exc}",
                           "_server_recv_ts": _recv_ts,
                           "_server_send_ts": _ts_now()})
    _log_for(meta, {"event": "stub_withdrawn", "slug": name})
    return json.dumps(
        {"withdrawn": True, "slug": name,
         "note": (f"new_{name}.lean is gone; it will not be submitted as a "
                  f"sub-goal. Make sure nothing still cites {name} — a "
                  f"citation with no declaration fails the build."),
         "_server_recv_ts": _recv_ts, "_server_send_ts": _ts_now()},
        ensure_ascii=False)
