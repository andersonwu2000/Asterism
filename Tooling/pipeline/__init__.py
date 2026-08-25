"""Pipeline package: shared helpers + Backward dispatch.

Split layout (planned by docs/dev/goal_history_unified.md):
  __init__.py     — shared helpers, constants, common types, re-exports
  backward.py     — `run_backward` + decomposition + sub-goal placement
  _lake.py        — lake invocation helpers (already split)
  _skeleton.py    — strategy skeleton + alias promotion (already split)
  _drafts.py      — partial-output persistence

Public API surfaced from this module (preserves pre-split callers):
  - run_backward                                     — dispatch entry point
  - PipelineResult, collect_artifacts                — DTO + forensics
  - _parse_hint_winner                               — Phase 1 hint output parser
  - DECLINE_*, DECLINE_DIRECTIVES, DECLINE_TO_FAILURE_REASON — unified
                                                       decline vocabulary
                                                       (see docs/archive/decline_directives.md)
  - _extract_leading_comments, _extract_decline_reason — Phase 6 parsing
  - _drafts                                          — partial-output module

Test-only / dispatcher imports also keep working through underscore
re-exports below (e.g. `pipeline._lake_build`, `pipeline._safe_glob`,
`pipeline._is_sorry_stub`, `pipeline._ensure_imports_subgoal`, etc.).
Integrator atomicity = Hadamard backup-restore (no commit_state).
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess  # noqa: F401 — surface for `pipeline.subprocess` monkeypatch in tests
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .. import agent
from ..quality import diagnostics
from ..state import assemble


def tools_mcp_entry(workspace: Path, seat: "str | None") -> dict:
    """The `asterism_tools` stdio server entry, shared by every config.

    PYTHONPATH rather than cwd: the client spawns this from the spawn's
    own directory, and the MCP config schemas (claude's and agy's alike)
    carry `env` but not `cwd`.

    `seat` scopes the server (owner ruling 2026-08-22): it registers
    only the seat's whitelist (`envelope.SEAT_ASTERISM_TOOLS`), so every
    provider lists the same filtered surface. An undeclared seat fails
    loudly at config-write time, not silently at full-surface. `None`
    is the OPERATOR grant (agy's global config, tests) — full surface,
    never a spawn's."""
    env = {"PYTHONPATH": str(workspace)}
    if seat is not None:
        from ..llm.envelope import asterism_tools_for
        asterism_tools_for(seat)  # raise NOW on an undeclared seat
        env["ASTERISM_SEAT"] = seat
    return {
        "type": "stdio",
        "command": sys.executable,
        "args": ["-m", "Tooling.knowledge.mcp_tools"],
        "env": env,
    }


def write_tools_mcp_config(attempts_dir: Path, workspace: Path,
                           seat: str) -> Path:
    """MCP config for the spawns that need the framework's tools but not
    the Lean gateway — the NL layer. Registering a gateway session for
    them would open a Lean backend slot nobody uses, so this writes the
    tools server alone: the NL layer's no-Lean rule is constructive,
    not advisory."""
    path = attempts_dir / "_mcp_tools.json"
    path.write_text(
        json.dumps({"mcpServers": {"asterism_tools":
                                   tools_mcp_entry(workspace, seat)}},
                   indent=2),
        encoding="utf-8")
    return path


def _write_mcp_config(attempts_dir: Path, workspace: Path,
                      target: Path, *,
                      pipeline_id: str, problem: str,
                      kind: "str | None" = None) -> Path:
    """Generate the MCP config JSON claude CLI uses to connect to the
    long-living gateway. One HTTP MCP server per daemon; spawns
    connect over HTTP with a session token in the
    `X-Asterism-Session` header. The token is obtained by POST to
    `/register` immediately before writing this file; the gateway
    associates the token with `target` so tool calls operate on the
    right file.
    """
    import urllib.request as _u
    import urllib.error as _ue
    config_path = attempts_dir / "_mcp_config.json"
    # OUTSIDE the attempts dir, which is rmtree'd at cleanup. This is the
    # per-call record of every gateway tool the spawn used — slot kind,
    # convergence, timings — and nothing reads it back, so its only
    # purpose is being there afterwards. It used to live beside the
    # config: on 2026-08-15 a defect that produced 59 agent reports over
    # two days had to be diagnosed from feedback prose alone, because not
    # one of the 59 incidents had left a machine-readable trace. Same
    # class as the provider transcripts moved out on the same day.
    log_dir = workspace / ".asterism" / "mcp_logs"
    log_path = log_dir / f"{pipeline_id}.jsonl"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        # Best-effort: a log we cannot place must not stop a spawn.
        log_path = attempts_dir / "_mcp.jsonl"
    token_file = attempts_dir / "_gateway_session.token"
    from ..core import config as _cfg
    gateway_port = _cfg.get(
        "gateway.port", default=8765,
        env_var="ASTERISM_GATEWAY_PORT", cast=int,
        workspace=workspace,
    )
    base = f"http://127.0.0.1:{gateway_port}"

    # Release any leftover session from a prior retry on this pipeline.
    # Each warm retry calls back into here; without release the gateway
    # accumulates open files on the shared backend (gradual mem leak).
    if token_file.exists():
        old_token = token_file.read_text(encoding="utf-8").strip()
        if old_token:
            try:
                rel = _u.Request(f"{base}/release/{old_token}",
                                 method="POST")
                _u.urlopen(rel, timeout=5.0).read()
            except (_ue.URLError, OSError):
                pass

    register_body = json.dumps({
        "pipeline_id": pipeline_id,
        "target_path": str(target),
        "problem": problem,
        "workspace": str(workspace),
        "log_path": str(log_path),
        # Pipeline kind — lets the gateway's submission mirror give
        # pipeline-accurate verdicts (e.g. non-proved citation severity).
        "kind": kind,
    }).encode("utf-8")
    req = _u.Request(base + "/register", data=register_body,
                     headers={"Content-Type": "application/json"},
                     method="POST")
    # A 5xx here is the gateway TALKING, not the gateway being gone, and
    # what it says is the whole diagnosis: "no free worker slot — pool
    # exhausted" vs "target file not found: …" vs backend-not-ready all
    # arrive as the same 500. Letting the raw HTTPError fly discards the
    # body and leaves `str(exc)` = "HTTP Error 500: Internal Server
    # Error" — which is what the operator read for a whole night while
    # the answer sat in the response.
    try:
        with _u.urlopen(req, timeout=120) as resp:
            body = resp.read().decode("utf-8")
    except _ue.HTTPError as exc:
        from ..lsp.lifecycle import read_http_error
        raise read_http_error(exc, endpoint="/register") from exc
    payload = json.loads(body)
    token = payload.get("session_token")
    if not token:
        raise RuntimeError(
            f"gateway /register returned no session_token: {body}")

    # `asterism_tools` is the framework's tool surface — the whitelist,
    # moved to a layer that can express it. It rides the same MCP channel
    # as the gateway so both providers reach it the same way; see
    # `knowledge/mcp_tools.py` for why a shell allowlist could not.
    config = {
        "mcpServers": {
            "asterism_tools": tools_mcp_entry(workspace, "formalizer"),
            "lsp": {
                "type": "http",
                "url": f"{base}/mcp",
                "headers": {"X-Asterism-Session": token},
            },
        },
    }
    config_path.write_text(json.dumps(config, indent=2),
                           encoding="utf-8")
    # Also store the token in attempts_dir so the framework can
    # POST /release/{token} when the spawn completes (cleanup hook).
    (attempts_dir / "_gateway_session.token").write_text(
        token, encoding="utf-8")
    return config_path


def _release_session(attempts_dir: Path) -> bool:
    """Release the gateway session registered in `attempts_dir` (best-effort).
    Pairs with `_write_mcp_config`: each spawn registers a session token in
    `attempts_dir/_gateway_session.token`; a tight per-decl / per-file loop
    must release it before the next register or the gateway worker pool
    exhausts (the Nth /register 500s on slot exhaustion). Builder relies on
    `_write_mcp_config`'s inline release-of-prior-token across its own warm
    retries instead, so it is the per-iteration loops (migrate hole-fill,
    cleanup audit) that call this in a `finally`.

    Returns whether a token was found (so a caller that is about to DELETE
    `attempts_dir` can report how many slots it handed back). The release
    itself is best-effort by design — a gateway that is already gone owes
    nothing — so the return says "there was one to release", not "the
    gateway acknowledged"."""
    from ..lsp import lifecycle as _gw
    tok = attempts_dir / "_gateway_session.token"
    if not tok.exists():
        return False
    try:
        t = tok.read_text(encoding="utf-8").strip()
    except OSError:
        return False
    if not t:
        return False
    try:
        _gw.release_session(t)
    except Exception:  # noqa: BLE001 — best-effort teardown
        pass
    return True


# Regression fix from the pipeline.py → pipeline/ package split: that
# bumped `__file__` one directory deeper. The prompts/ dir lives at
# Tooling/prompts/ — go up one level to reach it. Without this, the
# claude provider silently spawns with an "(prompt file unavailable)"
# stub on every Builder/Backward dispatch.
PROMPT_DIR = Path(__file__).parent.parent / "prompts"

# Wall-clock threshold under which a non-zero spawn is reclassified
# as `spawn_fast_fail`. Real claude.exe launches take ~3-5s and the
# fastest legitimate failure (e.g. compilation rejection of malformed
# patch) needs at least one model turn, so 10s is a conservative bound.
# Below this floor, the rc≠0 is almost certainly an infra fault (cwd /
# permission / network / claude.exe crash) rather than agent error.
SPAWN_FAST_FAIL_SEC = 10.0


# ---------------------------------------------------------------------
# DTO + forensic snapshot
# ---------------------------------------------------------------------

@dataclass
class PipelineResult:
    outcome: str  # 'proved' | 'success' | 'failed' | 'exhausted' | 'moot'
    failure_reason: str = ""
    failure_detail: str = ""
    proposal_md: str = ""
    artifacts: dict[str, str] = field(default_factory=dict)
    # (v38) `pending_failures` is GONE: per-retry failure records are
    # written eagerly by the retry helper — one dead_attempts row + one
    # `goals.attempts++` per failed retry, in-loop, because the
    # pipelines row (FK target) exists from dispatch time
    # (`db.record_pipeline_start`). The old buffer-until-normal-return
    # protocol lost the rows whenever the worker thread died by
    # exception while the increments stayed banked (goal 7486,
    # 2026-08-08).
    # Phase 2 — Forward pipeline only. When Forward commits a new lemma
    # goal, populate this so cascade_one can link the Inject decision
    # row to its produced goal. Cascade then defers the decision's
    # `outcome` until the produced goal reaches a terminal status
    # (proved / shelved / disproved), instead of filling outcome as
    # soon as the agent writes the (possibly sorry-bearing) statement.
    # See `docs/archive/design/phase2/pipelines.md` §4.2 for the rationale.
    produced_goal_id: int | None = None


def collect_artifacts(attempts_dir: Path) -> dict[str, str]:
    """Snapshot all .md / .lean / .txt files in attempts_dir for forensic
    preservation in dead_attempts.artifacts JSON column. .txt covers
    `_raw_response.txt` written by the OpenAI provider (raw model output
    before fence parsing) — needed when fence-parse failures point
    blame at the model's output schema.
    """
    out: dict[str, str] = {}
    for f in _safe_glob(attempts_dir, "*"):
        if f.suffix not in {".md", ".lean", ".txt"}:
            continue
        try:
            out[f.name] = f.read_text(encoding="utf-8")
        except OSError:
            pass
    return out


# ---------------------------------------------------------------------
# Spawn classification
# ---------------------------------------------------------------------

def _is_runtime_crash(stderr_tail: str) -> bool:
    """The provider CLI's runtime crash banner (claude.exe is a Bun
    standalone; a panic prints `Bun v… / Args: … / Features: …` before
    exiting with a small rc). Agent stderr never carries this banner —
    it only exists when the CLI itself died."""
    return "Bun v" in stderr_tail and "Args:" in stderr_tail


def _spawn_failure(rc: int, attempts_dir: Path, spawn_dur: float,
                   *, kind: "str | None" = None) -> tuple[str, str]:
    """Classify a non-zero `agent.spawn_llm` rc into
    (failure_reason, failure_detail). Four classes:

      - `spawn_fast_fail` — wall-clock < 10s; agent almost certainly
        never ran (claude.exe crashed at startup, prompt parser
        rejected, cwd unreachable, ...). Cascade: no goal-attempt
        increment, dispatcher sets per-target cooldown.
      - `agent_timeout` — rc=124, SIGKILL'd at WORKER_TIMEOUT_SEC.
        Pipeline runs a postmortem on this same session before
        returning so next dispatch sees a `.drafts/` progress note.
      - `system_killed` — NTSTATUS-shaped rc (≥ 0x40000000) or the CLI
        runtime's crash banner: the OS/runtime terminated the spawn.
        Provider infra — no attempts increment (2026-08-08).
      - `unclassified_spawn_failure` — anything else (rc≠0, wall ≥ 10s,
        rc≠124). Cause unknown, so the goal is NOT charged; the rc and
        duration are recorded and the dispatcher's consecutive-
        unclassified breaker escalates repetition to the operator
        (2026-08-08 owner ruling: the counter measures mathematical /
        decomposition difficulty, and only a fair chance consumed
        belongs in it).

    `kind` names the pipeline, which is how the SEATED PROVIDER (and
    therefore its `rc_contract` declaration) is resolved. It is the only
    provider-shaped input this function takes: the branches below are
    otherwise about duration and about OS-level exit shapes, both of
    which are provider-independent.

    THIS FUNCTION IS WHERE `rc_contract='undeclared'` IS DECIDED, and
    the decision is made once, here, rather than scattered:

      degrade conservatively AND warn once.

    An undeclared provider is read exactly like an `uninformative` one
    (an unrecognised rc becomes `unclassified_spawn_failure`, charging
    no goal attempt), and `capabilities.warn_if_undeclared` prints one
    `[capabilities]` line per daemon naming the provider. Refusing to
    dispatch was rejected: adding a backend would become a two-step
    landing whose first step is a dead framework, and the pressure would
    be to paste an unmeasured declaration — worse than an honest
    "undeclared". Warning alone was rejected too: a warning that leaves
    the permissive reading in place is precisely the unknown
    masquerading as a confident answer, which is the class this whole
    layer exists to close.

    Reads `attempts_dir/_spawn.stderr` (written by the provider on
    rc≠0) and folds the first ~600 chars into failure_detail so
    forensic visibility doesn't depend on grovelling through orphan
    sandbox dirs.
    """
    from ..llm import capabilities as _caps
    from ..llm.base import SpawnRC
    from ..state import failures as _failures
    _provider = _caps.provider_for_kind(kind)
    _contract = _caps.capabilities_for(_provider).rc_contract
    _caps.warn_if_undeclared(_provider, context=f"kind={kind or '?'}")
    stderr_tail = ""
    sf = attempts_dir / "_spawn.stderr"
    if sf.exists():
        try:
            stderr_tail = sf.read_text(encoding="utf-8")[:600].strip()
        except OSError:
            stderr_tail = ""
    base = f"agent rc={rc}"
    if rc == SpawnRC.TIMEOUT:
        # rc=124 is unambiguous: SIGKILL at WORKER_TIMEOUT_SEC. The
        # wall-clock check below cannot apply (timeout is several
        # minutes); this ordering also defends against artificial
        # spawn_dur values in unit tests.
        reason = "agent_timeout"
    elif rc >= 0x40000000 or _is_runtime_crash(stderr_tail):
        # The OS or the CLI's own runtime killed the process — the agent
        # never chose to exit like this. NTSTATUS-shaped exit codes sit
        # at 0x40000000+ (0xC0000409 fail-fast, 0xC0000142 DLL-init,
        # 0x40010004 debugger-terminate) — no CLI or agent exit code is
        # ever that large (SpawnRC tops out at 129). A Bun panic exits
        # small (rc=3) but stamps its crash banner on stderr. Both are
        # provider infra: burning goal budget on them shoved five
        # healthy goals into strategist review while the workstation
        # was dying (2026-08-08 post-mortem).
        base = f"agent rc={rc} (0x{rc:08X} — OS/system termination)" \
            if rc >= 0x40000000 else \
            f"agent rc={rc} (provider CLI runtime crashed)"
        reason = "system_killed"
    elif _failures.is_network_failure(stderr_tail):
        # Transport evidence outranks the duration heuristics below: a
        # dead network kills a spawn fast OR slow (37s-454s in the 08-17
        # outage), and both shapes carry the same stderr prose. The
        # dispatcher probes connectivity and parks (`core/network_wait`)
        # instead of counting this toward the unclassified breaker
        # (2026-08-18 owner ruling: a network drop is a park, not a
        # fault needing an operator).
        base = (f"agent rc={rc} (network failure in {spawn_dur:.0f}s — "
                f"not charged; the daemon probes connectivity and parks "
                f"until it returns)")
        reason = "provider_network"
    elif _failures.is_local_overload_failure(stderr_tail):
        # The MACHINE could not serve the spawn's startup (MCP
        # handshake > codex's fixed 30s, local route timeout) — a
        # CPU-oversubscription symptom, not the agent's and not the
        # provider's. Named so it cools instead of feeding the
        # unclassified breaker (2026-08-25: 50+ of these in one load-41
        # hour, five consecutive, dispatch halted).
        base = (f"agent rc={rc} (local overload in {spawn_dur:.0f}s — "
                f"the machine could not serve the spawn's handshake in "
                f"time; not charged)")
        reason = "local_overload"
    elif spawn_dur < SPAWN_FAST_FAIL_SEC:
        # Duration evidence, not rc evidence — so it survives an
        # `uninformative` / `undeclared` rc contract unchanged: a
        # process that died in under ten seconds never ran an agent, and
        # that is true whatever its exit code did or did not mean.
        base = f"agent rc={rc} (fast-fail in {spawn_dur:.1f}s)"
        reason = "spawn_fast_fail"
    else:
        # Unknown cause ⇒ do not charge the goal (2026-08-08 owner
        # ruling; see the registry entry). This used to be
        # `agent_rc_nonzero`, and it was the leak: an rc nobody had
        # classified yet defaulted to "the agent's fault" and burned a
        # goal attempt. The rc and the duration go in the detail so the
        # cause stays traceable — that is the whole price of not
        # guessing.
        base = (f"agent rc={rc} (unclassified; ran {spawn_dur:.0f}s "
                f"— cause unknown, not charged to the goal)")
        reason = "unclassified_spawn_failure"
        # Say WHY the rc taught us nothing, so the operator reading the
        # consecutive-unclassified breaker is not sent to hunt a number
        # that never meant anything. `_classify` already mined the
        # envelope for this provider — an rc that reached here is the
        # residue it could not name.
        if _contract == "uninformative":
            base += (f" [provider {_provider!r} declares its rc "
                     f"UNINFORMATIVE — the cause, if any, is in "
                     f"_spawn.stderr, not in the exit code]")
        elif _contract == "undeclared":
            base += (f" [provider {_provider!r} has declared no rc "
                     f"contract — see Tooling/llm/capabilities.py]")
    detail = base if not stderr_tail else f"{base}\n{stderr_tail}"
    return reason, detail


# ---------------------------------------------------------------------
# Filesystem / parsing helpers
# ---------------------------------------------------------------------

_IMPORT_LINE_RE = re.compile(r"(?m)^import\s")


def _live_stubs(attempts_dir: Path) -> list[Path]:
    """The `new_<slug>.lean` stubs this attempt actually declares.

    An EMPTY one is withdrawn, not malformed. `withdraw_stub` is the
    tool for that and the commit gate names it, but emptying the file is
    what an agent reaches for when a tool call fails: g7557 did exactly
    that on 2026-08-12, was refused (the gate wanted a declaration in
    it), and invented `theorem <slug> : True := trivial` to satisfy the
    name check — a sub-goal born proved that proves nothing. Reading the
    empty file as the withdrawal it plainly is removes the motive.

    Every caller that asks "did this attempt decompose?" goes through
    here, so the answer cannot differ between the commit gate and the
    bail detector."""
    out: list[Path] = []
    for p in _safe_glob(attempts_dir, "new_*.lean"):
        try:
            if p.read_text(encoding="utf-8", errors="replace").strip():
                out.append(p)
        except OSError:
            out.append(p)   # unreadable is not "withdrawn" — keep it
    return out


def _safe_glob(directory: Path, pattern: str) -> list[Path]:
    """Drop-in replacement for `directory.glob(pattern)` that survives
    Windows-reserved characters in sibling filenames.

    `pathlib.Path.glob()` traverses the directory by stat'ing each
    entry; on Windows, `<>:"|?*` in any filename make those stats raise
    `OSError [Errno 22]`, propagating up and killing the entire glob
    even when the bad-named file doesn't match the pattern. Agents
    occasionally write files like `won_exact?.lean` (mistakenly using
    Lean tactic names like `exact?` as identifiers in slugs), and
    `attempts_dir.glob("patch*.lean")` then crashes the whole spawn's
    validation.

    `os.scandir` enumerates raw NTFS entries without per-entry stat;
    `fnmatch.fnmatch` is pure string matching. Together we get the
    pattern semantics without ever resolving the bad-named path.
    """
    import os
    import fnmatch
    out: list[Path] = []
    try:
        with os.scandir(directory) as it:
            for entry in it:
                if fnmatch.fnmatch(entry.name, pattern):
                    out.append(Path(entry.path))
    except OSError:
        pass
    return out


# ---------------------------------------------------------------------
# Phase 1 — Mathlib `hint` invocation + output parsing
# ---------------------------------------------------------------------

# Phase 1 uses Mathlib's `Mathlib.Tactic.Hint` (`by hint`) instead of a
# framework-maintained tactic list. `hint` runs every tactic registered
# via `register_hint <prio> tac` in priority order, emits a `Try these:`
# info message listing all that succeeded, and uses the first goal-
# closing one as the proof. We parse the info message to recover the
# precise winning tactic and rewrite the patch as `:= by <winner>` for
# a forensically clear final artifact.
#
# Trade-off vs the previous `by first | t1 | t2 | …` design:
#   + Forensic: artifact records the exact winning tactic, not an
#     opaque `first` block.
#   + Coverage: tracks Mathlib's curated hint set automatically (24+
#     tactics; see `register_hint` call sites under
#     `.lake/packages/mathlib/Mathlib/`).
#   + No framework-side list to maintain.
#   - Cost: 2 lake builds on success (probe + confirm) instead of 1.
#     In practice the second build hits warm cache for almost everything
#     except the swapped tactic body.
#   - Coverage gap: a few common tactics (rfl, assumption, norm_cast,
#     ring_nf, simp, nlinarith) are not in Mathlib's `register_hint`
#     defaults; goals that only those close fall through to Phase 2.

# Output format (from Mathlib/Tactic/Hint.lean + lake build observation):
#     info: <file>:<line>:<col>: Try these:
#       [apply] 🎉️ <tactic that closed the goal>      ← winner
#       [apply] <tactic that left subgoals>           ← non-winner, skip
# Failure: rc != 0 + "error: No suggestions available".
_HINT_WINNER_RE = re.compile(
    r"^\s*\[apply\]\s*🎉️\s*(.+?)\s*$", re.MULTILINE
)


def _parse_hint_winner(output: str) -> str | None:
    """First 🎉️-marked tactic from `hint`'s `Try these:` block, or None.

    The 🎉️ marker is added by `Mathlib.Tactic.Hint.suggestion` only
    when the candidate tactic closed all goals. `hint` orders by
    `register_hint` priority desc, so the first 🎉️ entry is the
    highest-priority successful close — the same tactic `hint` itself
    used to seal the proof.
    """
    m = _HINT_WINNER_RE.search(output)
    return m.group(1).strip() if m else None


# Shared SoT (state.assemble) — the gateway mirrors the same object
# (task #5 Step A).
from ..state.assemble import SORRY_STUB_RE as _SORRY_STUB_RE  # noqa: E402


def _is_sorry_stub(content: str) -> bool:
    """True iff the file's proof body is a fresh `:= by sorry` placeholder.

    Phase 1 tactic_try rewrites the proof body via textual substitution and
    is only safe on this canonical form. After Backward replaces the body
    with a structured `have ... ; final_tac` patch, this returns False and
    Phase 1 must skip.
    """
    return _SORRY_STUB_RE.search(content) is not None


def _replace_proof_body(content: str, tactic: str) -> str:
    """Replace `:= by sorry` with `:= by <tactic>`. Caller must check
    `_is_sorry_stub` first; behavior on non-stub input is undefined."""
    cleaned = tactic.lstrip()
    if cleaned.startswith("by "):
        cleaned = cleaned[3:].lstrip()
    return _SORRY_STUB_RE.sub(f":= by {cleaned}", content, count=1)


def _grep_forbidden(text: str, forbidden: list[str]) -> str | None:
    """Return the first forbidden lemma found, or None."""
    for lemma in forbidden:
        if "*" in lemma:
            pat = re.escape(lemma).replace(r"\*", r"[\w.]*")
        else:
            pat = re.escape(lemma)
        rx = re.compile(r"(?<![\w.])" + pat + r"(?![\w])")
        if rx.search(text):
            return lemma
    return None


# ---------------------------------------------------------------------
# Decline directives (unified vocabulary, see docs/archive/decline_directives.md)
# ---------------------------------------------------------------------

# Recognized values for the `-- decline: <directive>` directive an
# agent writes at the top of patch.lean to opt out of the success
# path. Routing semantics live in cascade_one; description (the
# agent's `## ...` block under the directive) is preserved in
# dead_attempts.proposal_md and projected to downstream context.
#
#   unprovable          — false in this hypothesis scope; description
#                         must give a counterexample.  Persisted as
#                         failure_reason='agent_infeasible' (legacy).
#   return_to_parent    — provable after parent strategy is fixed;
#                         description must name the fix.  Cascades up
#                         to parent re-decompose with description as
#                         fix hint.  failure_reason='parent_needs_fix'.
#   shelve              — lacks math tools / scaffolding to proceed;
#                         description must name needed Forward lemma
#                         statements / supporting defs / theorems.
#                         Cascade routes to pending_strategist_review;
#                         Strategist decides next move (Inject Forward
#                         with the agent's brief / ConfirmShelve /
#                         Reopen with directive).
#                         failure_reason='agent_shelved'.
#   needs_decomposition — Builder-only; routes to Backward via
#                         entry_kind switch (legacy too_hard channel).
#                         failure_reason='agent_declined'.
DECLINE_UNPROVABLE = "unprovable"
#: Kernel-certified disproof submission (owner design 2026-08-25): the
#: agent rewrote patch.lean to PROVE the negation and marks the intent
#: here. Backward routes it through `_disprove.run_disproof_gate`
#: BEFORE the generic decline mapping — it is a submission with an
#: intent marker, not an exit.
DECLINE_DISPROVE = "disprove"
DECLINE_RETURN_TO_PARENT = "return_to_parent"
DECLINE_SHELVE = "shelve"
DECLINE_NEEDS_DECOMPOSITION = "needs_decomposition"
# NL-first (2026-07-25, user call): the goal (or a sub-goal the worker
# would have to invent) traces to no Programme Proof step — a claim
# with no argued basis is the Strategist's to justify or retire, not
# the worker's to grind (b6_1 postmortem: every false statement was
# minted in the argument-free region, d5-d15).
DECLINE_RETURN_TO_NL = "return_to_nl"

# Set of every recognized directive (parser uses for membership check;
# unknown directives fall through to the generic `agent_declined`
# branch downstream).
DECLINE_DIRECTIVES = frozenset({
    DECLINE_UNPROVABLE,
    DECLINE_DISPROVE,
    DECLINE_RETURN_TO_PARENT,
    DECLINE_SHELVE,
    DECLINE_NEEDS_DECOMPOSITION,
    DECLINE_RETURN_TO_NL,
})

# Map directive → DB failure_reason. Keeps existing enum values for
# unprovable / needs_decomposition (no schema migration needed); adds
# two new values for the new directives.
#
# `unprovable` NO LONGER maps to agent_infeasible (owner ruling
# 2026-08-25): that mapping let a bare assertion flip a goal to
# `disproved` — a hard terminal that also poisons dedupe #112a — and
# ox-alpha condemned the TRUE kelly_core with it (sylvester_gallai,
# 2026-08-24; the intake channel demanded a counterexample, the
# work-turn channel demanded nothing). The ONLY road to
# agent_infeasible → disproved is now the kernel-certified
# `-- decline: disprove` gate (`_disprove.run_disproof_gate`);
# `unprovable` lands as a NON-terminal agent_declined whose detail
# teaches that road. `disprove` is deliberately absent from this map —
# backward intercepts it before the generic branch.
DECLINE_TO_FAILURE_REASON = {
    DECLINE_UNPROVABLE: "agent_declined",
    DECLINE_RETURN_TO_PARENT: "parent_needs_fix",
    DECLINE_SHELVE: "agent_shelved",
    DECLINE_NEEDS_DECOMPOSITION: "agent_declined",
    DECLINE_RETURN_TO_NL: "return_to_nl",
}


# ---------------------------------------------------------------------
# Cross-pipeline helpers
# ---------------------------------------------------------------------

def resume_mcp_config(attempts_dir: Path) -> "Path | None":
    """The SAME MCP config the work spawn used — for every tail turn
    that resumes its session (postmortem / reflection / feedback).

    codex re-renders config.toml on EVERY spawn from the request's
    mcp_config_path: a tail turn that omits it re-homes the resumed
    session onto a TOOLLESS envelope — the parting-note turn had only
    codex builtins ("my function list only shows update_plan and
    request_user_input", its own reasoning, 2026-08-24) and 124
    consecutive codex-path deaths left no `_progress.md` (0/105 local
    codex era + 0/19 cloud). The feedback tail fixed this for itself
    and the fix never propagated (rule 4) — this helper is now the one
    place all three tails get the answer. Prompt-cache identity rides
    the same file (feedback's two-arm probe: resume WITH the config
    cached 11,008 of 12,056; without it, 0).

    Whichever file the work spawn wrote is the one that matches:
    `_mcp_config.json` (gateway + tools) for a formalizer,
    `_mcp_tools.json` (tools alone) for the Strategist and judge."""
    return next((p for p in (attempts_dir / "_mcp_config.json",
                             attempts_dir / "_mcp_tools.json")
                 if p.is_file()), None)


def _attempt_postmortem(*, seat: str, prompt_path: Path,
                        problem_dir: Path, attempts_dir: Path,
                        session_id: str) -> None:
    """Short follow-up spawn after a main-spawn timeout.

    Resumes `session_id` so the killed agent's session memory is
    intact; the postmortem prompt asks the agent to write a brief
    state + blocker note into `attempts_dir/_progress.md`. The wrapper
    around `run_backward` then captures that file as the partial draft
    for the next dispatch.

    Best-effort: any failure (postmortem also times out, session GC'd,
    provider unavailable) is silently absorbed — the next dispatch
    just cold-starts as it would have without postmortem persistence.
    We log the rc to the daemon log via the provider's own
    `[llm:claude] timed out after Ns` line; no extra exception path
    needed.
    """
    try:
        agent.spawn_llm(
            # The seat the WORK spawn used — see `_hooks.make_goal_hooks`.
            kind=seat,
            prompt_path=prompt_path,
            problem_dir=problem_dir,
            attempts_dir=attempts_dir,
            session_id=session_id,
            mcp_config_path=resume_mcp_config(attempts_dir),
            is_postmortem=True,
        )
    except Exception:  # noqa: BLE001 — postmortem must not block timeout flow
        pass


def _slug_from_filename(name: str) -> str:
    """`new_<slug>.lean` → `<slug>` (Backward sub-goal placement)."""
    base = name.removesuffix(".lean")
    return base.removeprefix("new_") if base.startswith("new_") else base


# First declaration head of ANY kind (attrs/modifiers tolerated) — the
# leading-comment region ends at the first declaration. Historically
# theorem-only, which made a data goal's `def` patch bound at nothing:
# ALL its comment lines (even ones after the decl) counted as
# "annotation", so the commit gate was vacuous for def patches and the
# harvested annotation could be tactic-comment garbage (validate/commit
# 預審 family, 2026-07-05). Shared SoT with the gateway mirror.
_FIRST_DECL_RE = assemble.DECL_HEAD_RE


def _extract_leading_comments(text: str) -> str:
    """Return all `--` comment lines that appear before the first
    `theorem` declaration in a Lean source, in source order. Imports,
    namespace lines, blank lines, and other non-`--` lines that
    intersperse with comments are skipped — they're framework /
    boilerplate, not the agent's annotation.

    Captures both placements agents naturally use:
      * file-top docstring (above imports), and
      * Mathlib-style doc-comment immediately preceding the theorem
        (after `namespace ...` etc).

    Blank lines that fall *between* two captured comment lines are
    preserved as bare `--` paragraph separators; pure-blank lines from
    the boilerplate region are dropped. Empty result if the file has
    no comments before the theorem (or no theorem at all).

    Phase 6 single-output design: this block is the agent's annotation
    source (Builder success summary / Backward strategy rationale /
    `-- decline: <reason>` directive).
    """
    m = _FIRST_DECL_RE.search(text)
    upper_bound = m.start() if m else len(text)
    region = text[:upper_bound]
    # Block comments count too: `/- … -/` and the Mathlib doc-comment
    # `/-- … -/` are the forms the models naturally write (12 complete
    # patches — one a finished CRT induction — died agent_no_annotation
    # on the friend-machine fleet, 2026-08-22, for spelling the
    # rationale the MATHLIB way). Normalized to `--` lines so the
    # decline directive and annotation propagation see one shape.
    # (Non-greedy match: a NESTED block comment truncates the capture —
    # acceptable, the gate only needs a non-empty rationale.)
    def _blocks_to_lines(mt: "re.Match[str]") -> str:
        inner = mt.group(1).strip("-").strip()
        return "".join(f"-- {ln.strip()}\n"
                       for ln in inner.splitlines() if ln.strip())
    region = re.sub(r"/-(.*?)-/", _blocks_to_lines, region, flags=re.S)
    out: list[str] = []
    buffered_blanks: list[str] = []
    for ln in region.splitlines(keepends=True):
        stripped = ln.strip()
        if stripped.startswith("--"):
            if buffered_blanks:
                out.extend(buffered_blanks)
                buffered_blanks = []
            out.append(ln)
        elif stripped == "":
            if out:
                buffered_blanks.append(ln)
            # else: blank in the boilerplate region before any comment → drop
        # else: import / namespace / open / etc — skip without breaking
    return "".join(out)


_DECLINE_DIRECTIVE_RE = re.compile(r"^\s*--\s*decline\s*:\s*(\S+)",
                                   re.MULTILINE)


def _extract_decline_reason(comment_block: str) -> str | None:
    """If the leading comment block opens with a `-- decline: <reason>`
    directive, return the reason. Otherwise None. The directive must
    appear in the leading-comment region (caller already extracted via
    `_extract_leading_comments`); placing it deeper in the file is
    ignored on purpose so an agent describing prior declines in a
    paragraph can't accidentally trigger the path.
    """
    m = _DECLINE_DIRECTIVE_RE.search(comment_block)
    return m.group(1) if m else None


# def/abbrev included (2026-07-05, feedback audit): the theorem-only head
# left every data sub-goal with statement='' — blank Context and, worse, a
# BLIND statement-keyed dedupe (byte-identical twins 5065/5026 ground 6+
# attempts before a strategist caught them by hand). A def's "statement" is
# its explicit type ascription — guaranteed present on sorry-bearing defs
# by the 8fb8291 Forward gate. Comments stripped before the search
# (cbe5bc3 extractor-family discipline: `def`/`theorem` appear in rationale
# prose far more often than a decl head).
_THM_HEAD_RE = re.compile(r"\b(?:theorem|lemma|def|abbrev)\s+\S+")
_COMMENT_RE = re.compile(r"/-.*?-/|--[^\n]*", re.DOTALL)


def _extract_statement(text: str) -> str:
    """Extract the type expression of the first declaration head
    (`theorem` / `lemma` / `def` / `abbrev`).

    Handles explicit args `(x : T)`, implicit args `{α : Type*}`,
    instance args `[Inhabited α]`, and arbitrary depth of paren/brace/bracket
    nesting in the type itself. Returns the substring between the decl's
    top-level `:` and the top-level `:=` — '' when there is no top-level
    type colon (inferred-type def) or no declaration at all.
    """
    text = _COMMENT_RE.sub(" ", text)
    m = _THM_HEAD_RE.search(text)
    if not m:
        return ""
    pos = m.end()
    n = len(text)

    # Skip leading arg blocks: ( ... ), { ... }, [ ... ]
    while pos < n:
        while pos < n and text[pos].isspace():
            pos += 1
        if pos >= n:
            return ""
        ch = text[pos]
        if ch in "({[":
            close = {"(": ")", "{": "}", "[": "]"}[ch]
            depth = 1
            pos += 1
            while pos < n and depth > 0:
                if text[pos] == ch:
                    depth += 1
                elif text[pos] == close:
                    depth -= 1
                pos += 1
            continue
        if ch == ":":
            pos += 1
            break
        return ""

    # Capture type until the BODY's `:=` — let/have binders in the type
    # own their `:=` and must not truncate it (same hole as the skeleton
    # seed, PutnamCmp b6_1 2026-07-19; single impl in state.assemble).
    from ..state.assemble import body_assign_index
    idx = body_assign_index(text, pos)
    if idx < 0:
        return ""
    return text[pos:idx].strip()


def _extract_statement_from_lean(path: Path) -> str:
    return _extract_statement(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------
# Re-exports from sub-modules (must come AFTER helper defs above so
# late-imports inside builder.py / backward.py find them ready).
# ---------------------------------------------------------------------

# Lake invocation helpers (split out of this package).
from ._lake import (  # noqa: E402
    lean_path_to_module as _lean_path_to_module,
    lake_build_modules as _lake_build_modules,
    lake_build as _lake_build,
    lake_build_batch as _lake_build_batch,
)

# Strategy skeleton + alias helpers (split out of this package).
from ._skeleton import (  # noqa: E402
    signature_prefix as _signature_prefix,
    normalize_signature as _normalize_signature,
    build_strategy_skeleton as _build_strategy_skeleton,
    inject_imports_for_subs as _inject_imports_for_subs,
    verify_backup_path as _verify_backup_path,
    promote_to_alias as _promote_to_alias,
    rollback_promote as _rollback_promote,
)

# Partial-output persistence so a timed-out / failed spawn's
# in-flight work survives into the next attempt's Context.md.
from . import _drafts  # noqa: E402

# Pipeline-specific helpers (split; re-exported for tests / dispatcher
# that import via `pipeline.<name>`).
from .backward import (  # noqa: E402
    _ensure_imports_subgoal,
    _try_promote_sorry_free,
    _strip_entry_kind,
    _SORRY_RE,
    run_backward,
)
