"""Claude CLI provider — subprocess to `claude` executable.

Inherits the existing claude CLI workflow: `--add-dir` for sandboxing,
`acceptEdits` permission, text output. The agent reads `Context.md`
from `attempts_dir/` and writes outputs back there. The prompt
template content is inlined into `-p` so the agent doesn't need read
access to the workspace `Tooling/prompts/` directory.

Model selection: `ASTERISM_AGENT_MODEL` env (default: Sonnet).

System-prompt trim: direct measurement of the claude CLI 2.1 default
vs the optimized flags below shows ~20.7K → ~7.8K prefix tokens per
call (-62%) on Sonnet. The 4 flags strip tool descriptions
Asterism doesn't use (Bash, Glob, Grep, WebFetch, WebSearch,
NotebookEdit, mcp__*), skip CLAUDE.md / auto-memory / settings load,
and stabilize per-machine sections so prompt caching reuses across
calls. Override the tool list via `ASTERISM_CLAUDE_TOOLS` if a future
flow needs a different surface.

In-pipeline same-session retry: when LLMRequest.session_id is
provided, the cold path uses `--session-id <uuid>` to pin the session
id; warm retries (is_retry=True) within the same pipeline use
`--resume <uuid>` and a short prompt (builder_retry.md) that relies
on the session memory carrying the prior turn's reasoning.
`--no-session-persistence` is dropped on those calls — sessions
persist to disk so the in-pipeline retry helper can resume them.
Sessions without session_id keep the `--no-session-persistence`
behavior.

Stale session sentinel: `claude --resume <uuid>` against a session
id whose on-disk file is gone (GC'd / never existed) returns rc=1
with stderr `"No conversation found with session ID"`. spawn maps
that to rc=125; the in-pipeline retry helper detects the warm-spawn
stale on the next iteration and re-mints sid + falls back to a cold
spawn within the same iteration (no budget consumed).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path

from .base import LLMRequest, SpawnRC
from .stream_parser import StreamParser


# Dispatcher abort signal: tracks every in-flight claude CLI subprocess
# so the dispatcher's exit paths (budget exceeded, gateway permanently
# unreachable, ...) can kill them all in one shot. Without this, when
# the main loop returns, Python's concurrent.futures._python_exit atexit
# hook joins each ThreadPoolExecutor worker thread regardless of
# `pool.shutdown(wait=False)`, and each worker blocks in proc.wait
# until subprocess_timeout (default 960s) — worst-case shutdown was
# ~16min × pool_size before the bash wrapper saw the daemon exit and
# the harness fired its task-notification. Killing the subprocess lets
# proc.wait return immediately so worker threads exit naturally through
# their dead_attempt cleanup paths in seconds.
_live_procs: set[subprocess.Popen] = set()
_live_procs_lock = threading.Lock()
_shutdown_event = threading.Event()


def request_shutdown() -> int:
    """Signal in-flight and future `spawn_llm` calls to bail and kill
    every currently-running claude subprocess. Returns the count killed
    for log visibility. Idempotent — safe for multiple dispatcher exit
    paths to call without coordination."""
    _shutdown_event.set()
    with _live_procs_lock:
        procs = list(_live_procs)
    killed = 0
    for proc in procs:
        try:
            proc.kill()
            killed += 1
        except OSError:
            pass
    return killed


def is_shutdown_requested() -> bool:
    """True after `request_shutdown` has been called. Checked by the
    in-pipeline retry loop at iteration entry so the worker bails
    instead of spawning fresh CLI invocations during teardown."""
    return _shutdown_event.is_set()


def _reset_shutdown_for_tests() -> None:
    """Clear the module-level shutdown state. Tests that exercise
    `request_shutdown` use this in their teardown so test order doesn't
    leak shutdown state into unrelated cases."""
    _shutdown_event.clear()
    with _live_procs_lock:
        _live_procs.clear()


# Extract names from "Unknown constant `X.Y.Z`" / "unknown identifier
# `X.Y.Z`" lake errors so the retry prompt can point the agent at Loogle/
# Grep before it guesses again. Cap to keep prompt size bounded.
_UNKNOWN_CONSTANT_RE = re.compile(
    r"[Uu]nknown\s+(?:constant|identifier)\s+`([^`]+)`"
)
_MAX_HINTED_UNKNOWNS = 3


def _extract_unknown_constants(stderr: str) -> list[str]:
    """Return up to MAX deduped unknown-constant names parsed from
    `stderr` (typically lake build output). Order is first-seen so the
    agent's attention lands on the earliest failures."""
    seen: list[str] = []
    for m in _UNKNOWN_CONSTANT_RE.finditer(stderr or ""):
        name = m.group(1).strip()
        if name and name not in seen:
            seen.append(name)
            if len(seen) >= _MAX_HINTED_UNKNOWNS:
                break
    return seen


def _retry_hint_for_unknowns(names: list[str]) -> str:
    """Compact verification hint for unknown-constant errors. Empty
    when no unknowns. Per-name overhead is one Loogle command line —
    so even hitting the cap (3) adds < 400 chars to the prompt."""
    if not names:
        return ""
    lines = [
        "",
        "Lake reports unknown constant(s) — verify the name in Mathlib "
        "BEFORE rewriting (the same guess will fail the same way):",
    ]
    for n in names:
        # Build Loogle query by keeping the namespace path + the
        # underscore-prefix of the leaf identifier. e.g.
        # `Multiplicative.toAdd_zpow` → query `Multiplicative.toAdd _`
        # (most lemmas about a function `toAdd` start `toAdd_*`, so
        # this catches the family). For a bare name with no dot, just
        # use the leaf prefix as-is.
        parts = n.split(".")
        leaf_prefix = parts[-1].split("_", 1)[0]
        if len(parts) >= 2:
            loogle_q = ".".join(parts[:-1] + [leaf_prefix])
        else:
            loogle_q = parts[0]  # bare identifier — query whole name
        lines.append(
            f"- `{n}` not found. Try: `python -m Tooling.knowledge.loogle "
            f"'{loogle_q} _'`"
        )
    return "\n".join(lines)


# Generic stderr-pattern → diagnostic-hint table. Each entry
# is (regex on stderr, short hint string). Hints are appended to the
# retry prompt so the resumed agent gets a pointed clue instead of
# spending several minutes inferring the failure class. Patterns use
# re.IGNORECASE; first match wins per family. Order matters — more
# specific patterns first.
_RETRY_PATTERN_HINTS: list[tuple[re.Pattern[str], str]] = [
    # Unicode / notation parser issues: `expected token` at a column
    # often means a notation symbol's scope isn't open or a hidden
    # character snuck in via copy-paste. Always-on grep tip.
    (re.compile(r"error:.*expected token", re.IGNORECASE),
     "`expected token` is usually a notation/scope problem. If the "
     "line uses ⟪⟫, ⟨⟩, ‖, etc, either `open scoped <Namespace>` or "
     "use the function form (e.g. `inner ℝ x y` instead of `⟪x, y⟫_ℝ`). "
     "Also check for stray zero-width chars from copy-paste."),
    # Typeclass metavariable — implicit/explicit binder shape mismatch.
    (re.compile(r"typeclass\s+instance\s+problem\s+is\s+stuck",
                re.IGNORECASE),
     "`typeclass instance problem is stuck` means Lean can't figure "
     "out a type argument. Add an explicit type annotation "
     "(e.g. `(x : ℝ)`) or pass the carrier explicitly via `@` form."),
    # `Function expected at, identifier ?m unknown` — autoImplicit
    # bound an undeclared identifier.
    (re.compile(r"Function expected at.*identifier.*unknown",
                re.IGNORECASE | re.DOTALL),
     "`Function expected at … identifier unknown` usually means a "
     "binder name (e.g. `P`) isn't declared in the theorem's signature. "
     "Make sure every variable in the conclusion appears as a binder."),
    # Tactic made no progress — use a different tactic family.
    # Lake quotes the tactic with either single quotes or backticks
    # (`ring_nf` made no progress / `tactic 'simp' made no progress`).
    (re.compile(r"(?:tactic\s+['`][^'`]+['`]|`[^`]+`)\s+made no progress",
                re.IGNORECASE),
     "The chosen tactic didn't progress on the current goal — pick a "
     "different family (e.g. for inner-product symmetry use "
     "`inner_sub_left`/`inner_neg_right`, not `ring_nf`)."),
    # Sorry warning attributed to a strategy patch. Sub-stub warnings
    # for `new_*.lean` and goal stubs `L_*.lean` are legitimate
    # (intentional `:= by sorry` placeholders) and are NOT flagged.
    # Builder patches: lake reports the warning under the goal's
    # lean_path (Builder copies patch onto goal_lean before building),
    # so we don't have a reliable filename signature for them — Builder
    # rarely emits `sorry` in practice; the strategy-patch case is what
    # matters.
    (re.compile(
        r"_strategy_s\d+\.lean[^\n]*declaration uses\s+`sorry`",
        re.IGNORECASE),
     "Your strategy patch (`_strategy_s<id>.lean`) still has "
     "`:= by sorry`. Sub-goal stubs (`new_*.lean` / `L_*.lean`) carry "
     "intentional sorry placeholders, but the strategy patch must "
     "compose them via real tactics."),
]


def _retry_hint_for_patterns(stderr: str) -> str:
    """Apply _RETRY_PATTERN_HINTS to `stderr`, return a short joined
    hint string (or '' if no matches). Cap to first 2 hits to bound
    prompt growth — multiple matching errors usually share one root
    cause."""
    if not stderr:
        return ""
    out: list[str] = []
    for pat, hint in _RETRY_PATTERN_HINTS:
        if pat.search(stderr):
            out.append(f"- {hint}")
            if len(out) >= 2:
                break
    if not out:
        return ""
    return "\n\nRetry hints based on the lake error above:\n" + "\n".join(out)


DEFAULT_MODEL = "claude-sonnet-4-6"

# Marker substring of claude's "No conversation found with session
# ID: ..." stderr output, lowercased. spawn returns
# SpawnRC.STALE_SESSION (= 125) when a warm spawn (`--resume`) hits
# this so the in-pipeline retry helper (`Tooling/pipeline/_retry.py`)
# can re-mint sid + fall back to a cold spawn within the same
# iteration without consuming retry budget.
_STALE_SESSION_MARKER = "no conversation found with session id"

# Anthropic API quota / usage-limit sentinels. claude.exe surfaces
# these as a normal rc=1 with the limit message printed to stdout
# (NOT stderr), so the dispatcher's generic agent_rc_nonzero path
# would otherwise consume retry budget on a deterministically-failing
# spawn. Reclassify to SpawnRC.QUOTA_EXHAUSTED (= 126) so the retry
# helper short-circuits and the dispatcher applies cooldown via the
# standard infra-reason path. Markers chosen from observed claude.exe
# output ("You've hit your limit · resets … 8am") plus standard
# Anthropic API error phrasings. Lowercased before matching.
_QUOTA_MARKERS = (
    "you've hit your limit",
    "you have hit your limit",
    "usage limit reached",
    "rate limit",
    "rate_limit_exceeded",
)
# Watchdog policy: single point-in-time check at `trap_check_sec` (the
# in-spawn wall-clock when the framework decides whether to abandon
# the broken session for a fresh-sid takeover). At that moment we
# sample the stream parser and kill iff BOTH conditions hold:
#   (1) parser.is_thinking_trap() — currently mid-thinking, OR
#       finalized + last_stop_reason == max_tokens
#   (2) parser.silence_seconds(now) > silence_threshold_sec —
#       agent has been silent (no tool_use) for ≥ threshold
#
# Why AND (not OR):
#   Conservative discrimination — at trap_check_sec, an agent that
#   recently emitted tool_use (silence < threshold) but happens to be
#   mid-thinking right now is plausibly between productive turns; we
#   prefer false negatives at this trigger over false positives,
#   because the TIMEOUT path (subprocess timeout + parser-final-state
#   check) catches the trap-only case ~5 min later via two-stage
#   takeover. AND-at-trap_check trades a few minutes of detection
#   latency for substantially fewer wasted rescues on borderline
#   cases.
#
# Watchdog kills route to STUCK_THINKING → single-stage combined
# fresh-sid takeover (no separate stage 3) with budget = spawn_timeout
# + postmortem_timeout - trap_check_sec.
#
# False-positive safety net: the takeover prompt tells the agent to
# Read the broken session's jsonl and decide ship-or-bail. If
# watchdog kills an active agent that meets both AND conditions only
# borderline, the takeover still recovers shipped work from disk.
_MIN_TRAP_CHECK_SEC = 60


def _find_session_jsonl(sid: str) -> Path | None:
    """Locate the per-session jsonl claude CLI maintains under
    `~/.claude/projects/<encoded_cwd>/<sid>.jsonl`. Returns None if
    not yet created or if the .claude tree is missing.

    Used by the fresh-sid stage 2/3 takeover (`_retry.py`'s
    `_copy_broken_session_jsonl`) to copy the broken session's
    history into `attempts_dir/_broken_session.jsonl` so the fresh
    agent can Read it from inside its sandbox without needing
    add-dir access to ~/.claude/projects/."""
    base = Path.home() / ".claude" / "projects"
    if not base.exists():
        return None
    target = f"{sid}.jsonl"
    try:
        for project_dir in base.iterdir():
            cand = project_dir / target
            if cand.exists():
                return cand
    except OSError:
        pass
    return None


_DEFAULT_TRAP_CHECK_SEC = 660
_DEFAULT_SILENCE_THRESHOLD_SEC = 300


def _watchdog(proc: subprocess.Popen, sid: str, *,
              stuck_flag: list, timeout_sec: int,
              parser: StreamParser) -> None:
    """Sleep until `trap_check_sec`. At that single trigger point
    sample BOTH parser-trap state AND silence; kill iff both fire.
    `stuck_flag[0] = True` on kill routes the spawn to STUCK_THINKING
    → combined fresh-sid takeover (no separate stage 3). When AND
    fails (one signal but not the other), exit quietly — the spawn
    runs to its full subprocess timeout and the TIMEOUT path's
    parser-only trap check picks up the trap-without-silence cases
    via two-stage takeover.

    If `proc` finishes naturally before the trap-check moment, exit
    without sampling (no decision to make).

    Runs in a daemon thread; one spawn = one trigger.
    """
    from ..core import config as _cfg
    trap_check_sec = _cfg.get(
        "dispatch.trap_check_sec",
        default=_DEFAULT_TRAP_CHECK_SEC,
        env_var="ASTERISM_TRAP_CHECK_SEC", cast=int,
    )
    silence_threshold_sec = _cfg.get(
        "dispatch.silence_threshold_sec",
        default=_DEFAULT_SILENCE_THRESHOLD_SEC,
        env_var="ASTERISM_SILENCE_THRESHOLD_SEC", cast=int,
    )
    spawn_start = time.monotonic()
    # Floor on trap_check_sec so misconfigured tiny timeouts don't
    # fire the watchdog immediately. 60s is a safe minimum for any
    # real spawn; tests monkeypatch this down for fast assertions.
    trap_check_sec = max(_MIN_TRAP_CHECK_SEC, trap_check_sec)
    trigger_at = spawn_start + trap_check_sec

    # Wait until trigger time, in short slices so a fast-finishing
    # spawn unblocks the thread promptly. 1s slice keeps the thread
    # responsive without burning CPU.
    while proc.poll() is None:
        now = time.monotonic()
        remaining = trigger_at - now
        if remaining <= 0:
            break
        time.sleep(min(1.0, remaining))

    if proc.poll() is not None:
        return  # Proc finished naturally before trap_check_sec.

    snap = parser.snapshot()
    silence = parser.silence_seconds(time.monotonic())
    verdict_state = snap.state.value
    verdict_stop = snap.last_stop_reason or "—"
    is_trap = parser.is_thinking_trap()
    is_silent = silence > silence_threshold_sec
    label = (f"state={verdict_state} last_stop_reason={verdict_stop} "
             f"silence={int(silence)}s")
    if is_trap and is_silent:
        # Race re-check: if the proc finished between the wait-loop
        # exit and this sample, sticking a STUCK_THINKING rc on a
        # finished spawn would route a legitimately-completed agent
        # into the ~7-min combined takeover. Window is narrow
        # (parser may finalize a max_tokens turn microseconds before
        # OS reaps proc) but real.
        if proc.poll() is not None:
            print(f"[watchdog] sid={sid[:8]} trap_check "
                  f"{int(trap_check_sec)}s reached; trap+silent "
                  f"({label}) but proc already finished; deferring "
                  f"to natural rc path", flush=True)
            return
        stuck_flag[0] = True
        print(f"[watchdog] sid={sid[:8]} trap_check "
              f"{int(trap_check_sec)}s reached; trap AND silent "
              f"({label}); killing for rescue", flush=True)
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    else:
        # AND failed: log which signal was missing. The TIMEOUT
        # path's parser-only check will catch trap-without-silence
        # cases ~5 min later when subprocess.TimeoutExpired fires.
        verdict = "active"
        if is_trap and not is_silent:
            verdict = "trap-but-not-silent"
        elif not is_trap and is_silent:
            verdict = "silent-but-not-trap"
        print(f"[watchdog] sid={sid[:8]} trap_check "
              f"{int(trap_check_sec)}s reached; {verdict} "
              f"({label}); deferring to subprocess timeout",
              flush=True)

# Asterism's pipelines need Read / Write / Edit for sandbox file
# manipulation, plus lemma-discovery search tools:
#   - `Grep`: keyword/name search over Mathlib source (e.g. find
#     `Finset.prod_involution`'s exact signature in <0.5s)
#   - `Bash`: scoped via `--allowed-tools` (see _spawn_allowed_tools
#     below) so the agent can ONLY invoke `python -m Tooling.knowledge.loogle`
#     for type-pattern search via Loogle's HTTPS API. Other Bash
#     commands stay blocked. Adds ~3K tokens of system-prompt
#     overhead vs the strict trim, justified by removing the agent's
#     "guess Mathlib lemma names without ground truth" failure mode
#     (wilson 2026-05-02 evidence: 6.7-min thinking on a single goal
#     was ~30% lemma-name enumeration).
# Override via env if a future use case needs different surface.
DEFAULT_TOOLS = "Read Write Edit Grep Bash"

# Bash invocations the agent is allowed (whitespace-separated patterns
# joined into a single --allowed-tools argument). Path-scoped Read /
# Grep patterns are appended per-spawn from problem_dir + Mathlib by
# `_compose_allowed_tools` below.
#
# Loogle: Mathlib type-pattern search via HTTPS.
DEFAULT_BASH_ALLOWED = "Bash(python -m Tooling.knowledge.loogle *)"


def resolve_model(kind: str | None) -> str:
    """Model resolution chain for the claude provider (per
    Tooling/config.get):

    1. `ASTERISM_<KIND>_MODEL` env  (kind in {'builder','backward'})
    2. Asterism.yaml `<kind>.model`
    3. `ASTERISM_AGENT_MODEL` env  (legacy provider-wide)
    4. `DEFAULT_MODEL`
    """
    from ..core import config
    if kind:
        v = config.get(
            f"{kind}.model",
            env_var=f"ASTERISM_{kind.upper()}_MODEL",
            legacy_env=("ASTERISM_AGENT_MODEL",),
            default=DEFAULT_MODEL,
        )
        return str(v)
    return os.environ.get("ASTERISM_AGENT_MODEL", DEFAULT_MODEL)


def _load_prompt(req: LLMRequest) -> str:
    """Read the prompt template file. Inlined into `-p` instead of
    pointed-to so the agent never needs read access to the workspace
    `Tooling/prompts/` directory (which lives outside `--add-dir` after
    cwd was narrowed to problem_dir). On read error, return a marker
    string so the spawn still proceeds and the failure surfaces as a
    normal agent error rather than a silent crash.

    Substitutes `{timeout_min}` with the live spawn timeout (in
    minutes) so the prompt's wall-clock hint stays in sync with
    `WORKER_TIMEOUT_SEC` / `POSTMORTEM_TIMEOUT_SEC`.
    """
    from Tooling.agent import render_prompt_template
    try:
        text = req.prompt_path.read_text(encoding="utf-8")
    except OSError as e:
        return f"(prompt file unavailable: {e})"
    return render_prompt_template(text, is_postmortem=req.is_postmortem)


def _build_cold_prompt(req: LLMRequest) -> str:
    """Compose the `-p` payload for a cold (non-retry) spawn: the full
    prompt template content, followed by short framework instructions
    pointing at Context.md and the output directory.
    """
    body = _load_prompt(req)
    return (
        f"You are running a {req.kind} task. Follow the instructions "
        f"below exactly.\n\nAfter reading them, read context at "
        f"{req.attempts_dir}/Context.md and write outputs into "
        f"{req.attempts_dir}/.\n\n"
        f"=== INSTRUCTIONS ===\n{body}\n=== END INSTRUCTIONS ==="
    )


def _persist_parser_state(attempts_dir: Path,
                          parser: StreamParser) -> None:
    """Write the parser's final snapshot to
    `attempts_dir/_parser_state.json` so the retry helper's TIMEOUT
    branch can re-check trap symmetrically with the watchdog. The
    file is also a forensic artifact (operator can inspect last
    parser state without restarting the daemon).

    Best-effort: silent on IO errors. The retry helper treats a
    missing file as 'no parser data — assume active' (defaults to the
    legacy `--resume` postmortem path)."""
    try:
        snap = parser.snapshot()
        body = json.dumps({
            "state": snap.state.value,
            "last_stop_reason": snap.last_stop_reason,
            "messages_seen": snap.messages_seen,
            "is_thinking_trap": parser.is_thinking_trap(),
        })
        (attempts_dir / "_parser_state.json").write_text(
            body, encoding="utf-8")
    except (OSError, ValueError):
        pass


def _write_spawn_stderr(attempts_dir, stderr: str, stdout: str,
                        rc: int) -> None:
    """Write captured stderr to `attempts_dir/_spawn.stderr` so pipeline
    forensics can include it in dead_attempts.failure_detail.
    Best-effort: silent on IO errors (the spawn already failed; making
    forensics fatal would mask the real diagnosis).

    Combines stderr + stdout because some claude / gemini errors land
    on stdout (rare). Caps the saved file at ~10KB to bound disk usage
    on pathological loops."""
    try:
        body = (stderr + ("\n--- stdout ---\n" + stdout if stdout else ""))
        body = body[:10240]
        (attempts_dir / "_spawn.stderr").write_text(
            f"rc={rc}\n{body}", encoding="utf-8")
    except OSError:
        pass


def _compose_allowed_tools(req: LLMRequest) -> str:
    """Build the `--allowed-tools` argument: Bash patterns joined with
    Read/Grep path-scoped patterns derived from problem_dir + the
    workspace's Mathlib package. Claude CLI matches glob-like patterns
    in the form `Read(<path>)` / `Grep(<path>)`.

    Deliberately NOT in the allowlist: other `Problems/<...>/` dirs
    under the same workspace. The Sonnet rerun of proj_nonexpansive
    showed agents wandering into `inner_zero_iff_smul/proofs/` and
    `gen_generates/proofs/` for unrelated examples; those reads tripped
    permission prompts but cost a turn each. Restricting Read to the
    active problem's dir + Mathlib makes the boundary explicit.
    """
    workspace = _workspace_from_problem_dir(req.problem_dir)
    # Forward-slash form for the patterns; claude CLI matches glob-style
    # and Windows users naturally write backslashes, but the patterns
    # round-trip through subprocess argv as strings, so we normalize.
    problem = req.problem_dir.as_posix()
    attempts = req.attempts_dir.as_posix()
    # Cover the whole `.lake/packages/` tree, not just `mathlib/Mathlib/`.
    # Sonnet's natural `rg` query is rooted at `.lake/packages/mathlib/`
    # (the package root, not the Mathlib source subdir), which the narrow
    # prefix rejected — observed 18 denied Grep ops in a single
    # proj_nonexpansive run, each wasting one agent turn. Allowing the
    # whole packages tree also covers batteries / proofwidgets / aesop /
    # Qq when an agent legitimately needs to look at them.
    packages = (workspace / ".lake" / "packages").as_posix()
    # NB: claude CLI's `--allowed-tools` parser is paren-aware (the
    # pre-existing `Bash(python -m Tooling.knowledge.loogle *)` pattern carries
    # internal spaces unquoted), so a `Read(C:/My Project/...)` glob
    # does NOT need quoting either — pattern boundaries are pulled by
    # balanced parens, not whitespace. Verified empirically; the
    # pre-quoting attempt broke the Bash pattern's existing test.
    patterns = [
        # Bash (Loogle, plus operator override)
        os.environ.get("ASTERISM_CLAUDE_ALLOWED_BASH", DEFAULT_BASH_ALLOWED),
        # Read scope: this problem's dir, the agent's sandbox, and
        # only `*.lean` under Lake-packages — keeps `.olean` binary
        # blobs out of agent context (an accidental Read on one
        # would dump megabytes of garbage). Mathlib + transitive
        # deps' source files remain fully accessible.
        f"Read({problem}/**)",
        f"Read({attempts}/**)",
        f"Read({packages}/**/*.lean)",
        # Grep mirrors Read; rg skips binaries by default but the
        # narrowed pattern keeps the allowlist self-consistent.
        f"Grep({problem}/**)",
        f"Grep({packages}/**)",
    ]
    # When the request carries an MCP config (Builder pipeline +
    # Phase 1 LSP swap), allow the LSP-backed MCP tools without
    # per-call permission prompts. claude CLI exposes MCP tools as
    # `mcp__<server-name>__<tool>`; our server name is `lsp`.
    if req.mcp_config_path is not None:
        patterns.extend([
            "mcp__lsp__apply_edit",
            "mcp__lsp__goal_at",
            "mcp__lsp__errors_at",
            "mcp__lsp__validate_file",
        ])
    return " ".join(p for p in patterns if p)


def _workspace_from_problem_dir(problem_dir: Path) -> Path:
    """problem_dir = <workspace>/Problems/<name>; walk up two."""
    return problem_dir.parent.parent


def _trim_flags(req: LLMRequest | None = None) -> list[str]:
    """CLI flags that strip system-prompt overhead Asterism doesn't
    benefit from + per-spawn allowlist for Read/Grep/Bash.

    `req=None` is for callers that don't run agent tools (e.g.
    complete_text). The path-scoped allowlist is dropped in that case;
    Bash allowlist still emitted for back-compat with tests.
    """
    tools = os.environ.get("ASTERISM_CLAUDE_TOOLS", DEFAULT_TOOLS)
    flags = [
        "--tools", tools,
        "--setting-sources", "",
        "--disable-slash-commands",
        "--exclude-dynamic-system-prompt-sections",
    ]
    if req is not None:
        allowed = os.environ.get(
            "ASTERISM_CLAUDE_ALLOWED_TOOLS",
            _compose_allowed_tools(req))
        if allowed:
            flags += ["--allowed-tools", allowed]
    else:
        bash_only = os.environ.get(
            "ASTERISM_CLAUDE_ALLOWED_BASH", DEFAULT_BASH_ALLOWED)
        if bash_only:
            flags += ["--allowed-tools", bash_only]
    return flags


class ClaudeCliProvider:
    def spawn(self, req: LLMRequest) -> int:
        # Dispatcher abort already fired — skip the CLI invocation so
        # the worker thread can exit through its dead_attempt + cleanup
        # path without burning another `claude` subprocess startup.
        if is_shutdown_requested():
            return SpawnRC.SHUTDOWN
        if not shutil.which("claude"):
            print("[llm:claude] claude CLI not found; skipping spawn",
                  flush=True)
            return 127

        model = resolve_model(req.kind)

        # Fresh-rescue stage 2 / stage 3 (2026-05-10): the broken
        # session is unrecoverable; this is a fresh-cold session
        # picking up the original session's stage-2 (rescue) or
        # stage-3 (postmortem) workflow. session_id is freshly minted
        # by the helper. inline_prompt is the helper-crafted prompt
        # (with broken jsonl path baked in). No template loading, no
        # Context.md reference inside the prompt — Context.md was
        # already compiled by spawn_fn's cold-prep step and the inline
        # prompt may reference it indirectly via the broken jsonl
        # contents. Watchdog skipped (short budget, not a full attempt).
        if req.inline_prompt is not None and req.session_id:
            session_flags = ["--session-id", req.session_id]
            session_lifetime_flag: list[str] = []
            prompt = req.inline_prompt
        # Timeout postmortem — main spawn timed out, agent's session memory
        # is intact on disk. Resume the session with a short prompt
        # asking for a state + blocker note (`_progress.md`) into the
        # SAME attempts_dir. The wrapper then captures _progress.md as
        # the partial draft for the next dispatch. Loaded prompt body
        # is short and self-contained — no _build_cold_prompt wrapping
        # (Context.md from the killed turn is already in session memory;
        # re-injecting it would distract the postmortem agent).
        elif req.is_postmortem and req.session_id:
            session_flags = ["--resume", req.session_id]
            session_lifetime_flag = []
            prompt = _load_prompt(req)
        # In-pipeline retry path uses `--resume`, a short inline prompt
        # with the lake error embedded directly (no separate
        # RETRY_NOTE.md file → agent doesn't need a Read tool round-
        # trip), and skips the file-based prompt fetch (prior turn's
        # context lives in claude's session memory).
        elif req.is_retry and req.session_id:
            session_flags = ["--resume", req.session_id]
            session_lifetime_flag = []  # session persists
            if req.kind == "strategist":
                # Strategist retries on `verify_decisions` failure, not
                # lake build. The prior turn already produced
                # decision.json in this attempts_dir; the framework
                # rejected it for the reason below. Same output target,
                # different content.
                err = (req.retry_context
                       or "(verify error not captured)").strip()
                prompt = (
                    f"Your previous decision.json failed verification:"
                    f"\n\n```\n{err}\n```\n\n"
                    f"Produce a fresh decision.json fixing this. The "
                    f"schema and rules from your initial Context.md are "
                    f"unchanged. Write to "
                    f"{req.attempts_dir}/decision.json."
                )
            else:
                err = (req.retry_context
                       or "(lake error not captured)").strip()
                # When the prior failure cites unknown constants, nudge
                # the agent to verify names via Loogle/Grep instead of
                # repeating the same guess. Empty hint when no match.
                unknown_hint = _retry_hint_for_unknowns(
                    _extract_unknown_constants(err))
                # Generic stderr → diagnostic hint table. Catches
                # expected-token / typeclass-stuck / tactic-no-progress
                # patterns the unknown-constant matcher misses.
                pattern_hint = _retry_hint_for_patterns(err)
                prompt = (
                    f"Previous attempt failed lake build with:\n\n"
                    f"```\n{err}\n```{unknown_hint}{pattern_hint}\n\n"
                    f"Produce a fresh patch.lean (same scope) addressing "
                    f"this error. Reuse the prior PROPOSAL.md unless the "
                    f"strategy needs to change. Write outputs into "
                    f"{req.attempts_dir}/."
                )
        elif req.session_id:
            # Cold path with a caller-pinned session id (so a future
            # retry can resume).
            session_flags = ["--session-id", req.session_id]
            session_lifetime_flag = []  # persist
            prompt = _build_cold_prompt(req)
        else:
            # Legacy non-session path: ephemeral session, original prompt.
            session_flags = []
            session_lifetime_flag = ["--no-session-persistence"]
            prompt = _build_cold_prompt(req)

        # Cwd narrowed to problem_dir, after which claude CLI's permission
        # system treats `cwd subtree ∪ --add-dir paths` as the implicit
        # trust boundary; absolute paths outside that boundary are denied
        # even when listed in --allowed-tools. Mathlib lives outside
        # problem_dir, so `Read(.lake/packages/**/*.lean)` allowlist alone
        # wasn't enough — proj_nonexpansive 2026-05-03 rerun saw 75
        # mathlib Grep denials per run. Adding `.lake/packages` as a third
        # --add-dir grants the explicit trust so the allowlist's path
        # patterns actually take effect.
        # Conditional: skip when the dir doesn't exist (fresh checkout
        # before `lake build`) — claude CLI errors on missing --add-dir.
        packages_dir = (_workspace_from_problem_dir(req.problem_dir)
                        / ".lake" / "packages")
        add_dir_packages: list[str] = (
            ["--add-dir", str(packages_dir)] if packages_dir.is_dir() else [])
        # MCP config — Builder pipeline (Phase 1 LSP swap) sets
        # mcp_config_path to a JSON file describing the LSP MCP
        # server. claude spawns the server itself as a child process
        # over stdio, so the server's lifecycle naturally tracks
        # claude's lifetime (which == this pipeline spawn).
        # `--strict-mcp-config` keeps any user-level globally
        # configured MCPs out of the agent's surface.
        mcp_flags: list[str] = []
        if req.mcp_config_path is not None:
            mcp_flags = [
                "--mcp-config", str(req.mcp_config_path),
                "--strict-mcp-config",
            ]

        # Watchdog policy: short rescue / postmortem spawns skip the
        # watchdog (no rescue window math, subprocess timeout is the
        # only kill mechanism). Cold spawns without session_id can't
        # be tracked across retries either — defensive guard, every
        # real dispatch sets session_id.
        # Fresh-rescue stages 2/3 (inline_prompt) and timeout postmortem
        # (is_postmortem) both fall in the no-watchdog bucket.
        watchdog_eligible = (
            not req.is_postmortem
            and req.inline_prompt is None
            and req.session_id is not None
        )
        # Stream-json + partial-messages enables real-time event
        # parsing: claude CLI emits one JSON line per Anthropic SSE
        # event (message_start, content_block_start with
        # type=thinking/tool_use, content_block_delta, message_delta
        # with stop_reason, message_stop). The parser maintains a
        # state machine the watchdog samples at wall_cap.
        # Non-watchdog spawns (postmortem / fresh-rescue) keep text
        # output — they don't need parser visibility and text mode
        # avoids the JSON Lines volume / parser overhead.
        if watchdog_eligible:
            output_flags = [
                "--output-format", "stream-json", "--verbose",
                "--include-partial-messages",
            ]
        else:
            output_flags = ["--output-format", "text"]
        cmd = [
            "claude",
            "--model", model,
            "-p", prompt,
            "--permission-mode", "acceptEdits",
            "--add-dir", str(req.problem_dir),
            "--add-dir", str(req.attempts_dir),
            *add_dir_packages,
            *mcp_flags,
            *output_flags,
            *session_flags,
            *session_lifetime_flag,
            *_trim_flags(req),
        ]
        env = dict(os.environ)
        # Per-spawn thinking-token cap (restored 2026-05-10 from 9d05d19).
        # Sonnet 4.6's adaptive thinking can produce 30-90K-character
        # single thinking blocks that hit Anthropic's max_tokens stop
        # before the agent calls any Write tool — empirically observed
        # on 74% of SG Backward spawns at 9d05d19. With the cap,
        # Sonnet hits the per-turn cap, the API forces a transition,
        # and the agent commits its current output via tool_use
        # (write patch.lean / new_*.lean). Multi-step reasoning still
        # accumulates across turns (after each tool result the next
        # turn gets a fresh thinking budget).
        # MAX_THINKING_TOKENS only takes effect in legacy non-adaptive
        # mode, so we also disable adaptive routing.
        # Cap formula: 1000 tokens/min of wall-clock budget, with a
        # 1000-token floor for short rescue/postmortem spawns.
        env["CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING"] = "1"
        env["MAX_THINKING_TOKENS"] = str(
            max(1000, (req.timeout_sec // 60) * 1000))
        proc = subprocess.Popen(
            cmd, env=env, cwd=str(req.problem_dir),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace",
        )
        # Register so dispatcher's request_shutdown can kill us on
        # budget-exceeded / gateway-permadown exit paths. Without this
        # the proc.wait below blocks for up to req.timeout_sec (~960s)
        # even after the dispatcher main loop has returned, dragging
        # daemon shutdown out 16min × pool_size.
        with _live_procs_lock:
            _live_procs.add(proc)
        try:
            return self._run_proc(req, proc, watchdog_eligible)
        finally:
            with _live_procs_lock:
                _live_procs.discard(proc)

    def _run_proc(self, req: LLMRequest, proc: subprocess.Popen,
                  watchdog_eligible: bool) -> int:
        """Body of `spawn` once the Popen has been created and tracked.
        Split out so the parent can wrap the lifetime in a register/
        unregister try/finally without indenting the entire ~150 lines."""
        stuck_flag: list[bool] = [False]
        wd_thread: threading.Thread | None = None
        reader_thread: threading.Thread | None = None
        parser: StreamParser | None = None
        stdout_chunks: list[str] = []
        stderr_chunks: list[str] = []

        def _drain_stream(pipe, buf: list[str],
                          parser_ref: StreamParser | None) -> None:
            """Read `pipe` line by line; append to `buf` and (if
            parser given) feed each line to the parser. Exits on EOF
            (proc closes pipe). Tolerant of decode errors via the
            parent Popen's encoding/errors settings."""
            try:
                for line in pipe:
                    buf.append(line)
                    if parser_ref is not None:
                        parser_ref.feed_line(line)
            except (OSError, ValueError):
                # Pipe closed mid-read (proc killed) — stop draining.
                pass

        if watchdog_eligible:
            parser = StreamParser()
            reader_thread = threading.Thread(
                target=_drain_stream,
                args=(proc.stdout, stdout_chunks, parser),
                daemon=True,
            )
            reader_thread.start()
            # stderr also needs a reader so the OS pipe buffer doesn't
            # fill and deadlock the proc. Parser only consumes stdout.
            stderr_thread = threading.Thread(
                target=_drain_stream,
                args=(proc.stderr, stderr_chunks, None),
                daemon=True,
            )
            stderr_thread.start()
            wd_thread = threading.Thread(
                target=_watchdog,
                args=(proc, req.session_id),
                kwargs={
                    "stuck_flag": stuck_flag,
                    "timeout_sec": req.timeout_sec,
                    "parser": parser,
                },
                daemon=True,
            )
            wd_thread.start()
        try:
            if watchdog_eligible:
                proc.wait(timeout=req.timeout_sec)
                rc = proc.returncode
                # Drain any remaining buffered output (reader threads
                # exit on EOF after proc closes its pipes).
                if reader_thread is not None:
                    reader_thread.join(timeout=2)
                stderr_thread.join(timeout=2)
                stdout = "".join(stdout_chunks)
                stderr = "".join(stderr_chunks)
            else:
                stdout, stderr = proc.communicate(
                    timeout=req.timeout_sec)
                rc = proc.returncode
        except subprocess.TimeoutExpired:
            proc.kill()
            if watchdog_eligible:
                # Reader threads see EOF on the killed pipes and exit.
                if reader_thread is not None:
                    reader_thread.join(timeout=2)
                stderr_thread.join(timeout=2)
                stdout = "".join(stdout_chunks)
                stderr = "".join(stderr_chunks)
            else:
                stdout, stderr = proc.communicate()
            rc = 124
        if wd_thread is not None:
            wd_thread.join(timeout=2)
        # Persist parser final state so the retry helper's TIMEOUT
        # branch (in _retry.py) can re-check trap symmetrically with
        # the watchdog's at-trigger check, and so dead_attempts
        # forensic detail can record the verdict. Best-effort — IO
        # errors don't fail the spawn.
        if parser is not None:
            _persist_parser_state(req.attempts_dir, parser)
        # Watchdog stuck-kill takes precedence over the OS-level rc
        # (TerminateProcess returns a platform-dependent code that
        # collides with our normal failure semantics). Reclassify so
        # the retry helper can route to a rescue spawn.
        if stuck_flag[0]:
            _write_spawn_stderr(req.attempts_dir,
                                "(watchdog stuck-kill: wall cap or "
                                "tool_use silence — see [watchdog] log "
                                "line above)", stdout or "",
                                SpawnRC.STUCK_THINKING)
            return SpawnRC.STUCK_THINKING
        # Subprocess timeout (full wall budget hit without watchdog
        # firing — i.e., agent kept emitting tool_use but couldn't
        # converge). Distinct from stuck-thinking; falls through to
        # the existing TIMEOUT path in the retry helper.
        if rc == 124:
            print(f"[llm:claude] timed out after {req.timeout_sec}s",
                  flush=True)
            _write_spawn_stderr(req.attempts_dir,
                                f"(subprocess.TimeoutExpired after "
                                f"{req.timeout_sec}s)", "", 124)
            return 124
        # Capture stderr to attempts_dir on failure so the pipeline can
        # surface it in dead_attempts.failure_detail. Skipping on rc=0
        # keeps the sandbox tidy.
        if rc != 0:
            _write_spawn_stderr(req.attempts_dir, stderr or "",
                                stdout or "", rc)
        # Detect stale session: claude returns rc=1 with "No
        # conversation found with session ID: ..." in stderr.
        # Surface as SpawnRC.STALE_SESSION so the in-pipeline retry
        # helper falls back to a cold spawn with a fresh sid
        # without consuming retry budget.
        if (rc != 0 and req.is_retry
                and _STALE_SESSION_MARKER in (stderr or "").lower()):
            print(f"[llm:claude] stale session "
                  f"{req.session_id[:8] if req.session_id else '?'}",
                  flush=True)
            return SpawnRC.STALE_SESSION
        # Detect quota / usage-limit refusals. claude.exe writes the
        # limit message to stdout AND returns rc=1, indistinguishable
        # at the rc level from a real model error. Without this check,
        # the dispatcher consumes retry budget retrying a
        # deterministically-failing spawn until CONSEC_SPAWN_FAIL_LIMIT
        # bails the daemon. Reclassify to QUOTA_EXHAUSTED so the
        # standard infra-reason cooldown path applies.
        if rc != 0:
            combined = ((stdout or "") + "\n" + (stderr or "")).lower()
            if any(m in combined for m in _QUOTA_MARKERS):
                print(f"[llm:claude] quota exhausted (rc={rc} → "
                      f"{SpawnRC.QUOTA_EXHAUSTED})", flush=True)
                return SpawnRC.QUOTA_EXHAUSTED
        return rc

    def complete_text(
        self, *, prompt: str, timeout_sec: int = 60,
    ) -> str | None:
        """One-shot completion via `claude -p <prompt>`. Captures
        stdout text rather than producing files. Used by short auxiliary
        calls (idiom extract / curate). complete_text never invokes
        tools, but the same trim applies to the system prompt. Auxiliary
        calls inherit the 'builder' tier (cheap-LLM role)."""
        if not shutil.which("claude"):
            return None
        model = resolve_model("builder")
        cmd = [
            "claude",
            "--model", model,
            "-p", prompt,
            "--no-session-persistence",
            "--output-format", "text",
            *_trim_flags(),
        ]
        try:
            r = subprocess.run(
                cmd, timeout=timeout_sec,
                capture_output=True, text=True,
                encoding="utf-8", errors="replace",
            )
            if r.returncode != 0:
                return None
            return r.stdout.strip()
        except subprocess.TimeoutExpired:
            return None
