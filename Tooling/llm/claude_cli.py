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
import sys
import threading
import time
from pathlib import Path

from ..core.process_group import no_window_creationflags
from . import capabilities
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

# Anthropic API floor for `thinking.budget_tokens`: a request with a smaller
# budget is rejected (400 `thinking.enabled.budget_tokens: Input should be
# greater than or equal to 1024`), which fails the WHOLE spawn rc=1.
_THINKING_MIN_TOKENS = 1024


def _thinking_budget(timeout_sec: int) -> int:
    """`MAX_THINKING_TOKENS` for one spawn: 1000 tokens per minute of wall-clock
    budget, floored at the API's `_THINKING_MIN_TOKENS` minimum.

    The floor matters for SHORT spawns: a 90s framework-feedback turn yields
    `(90 // 60) * 1000 = 1000`, which is BELOW 1024 — so before this floor every
    short-timeout, thinking-enabled resume (notably the `cleanup:*` feedback
    questionnaire, which resolves to the sonnet default) died with an API 400 and
    silently dropped its record (#33 root cause). Long spawns (≥120s) clear 1024
    on their own."""
    return max(_THINKING_MIN_TOKENS, (timeout_sec // 60) * 1000)

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
# Grace window for the completion-reclaim branch: how long a clean
# finish (finalized + end_turn) must PERSIST with the process still
# alive before the watchdog terminates it. Must exceed normal claude
# self-exit latency after end_turn (~1-3s) so cleanly-exiting spawns
# are never cut; small enough to reclaim most of a hung tail.
_DEFAULT_COMPLETION_GRACE_SEC = 20

#: This provider's canonical name in `llm/capabilities.py`.
PROVIDER_NAME = "claude"


def resolve_claude_executable() -> "str | None":
    """Launchable path for `claude`, or None — the provider's own answer.

    PATH first, then the installer's known homes. The official
    installer's PATH edit lands in NEW sessions (and on a fresh Windows
    it can miss entirely), so a long-lived process started before or
    during the install would otherwise conclude the CLI is absent about
    one sitting right there. `serve/app.py` learned that the hard way
    and grew its own copy; `drift_guard` kept a bare `shutil.which` and
    silently checked NOTHING on such a machine. One resolver per
    provider, beside `antigravity_cli.resolve_agy_executable`, so the
    next consumer inherits the knowledge instead of a third variant.

    NOT used by `spawn` below, deliberately: the spawn's argv[0] is the
    bare name and its gate is the matching `shutil.which`, so those two
    agree with each other. Changing the engine's launch path is a
    behaviour change on the hot path and belongs to whoever needs it.
    """
    p = shutil.which("claude")
    if p:
        return p
    candidates = [Path.home() / ".local" / "bin" / "claude.exe"]
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidates.append(Path(appdata) / "npm" / "claude.cmd")
    for c in candidates:
        if c.exists():
            return str(c)
    return None

#: Kinds whose silence is measured as STREAM idleness rather than
#: tool-call cadence. The table moved to `llm/capabilities.py` when the
#: choice became `capabilities.liveness_clock(provider, kind)` — the
#: same question a provider WITHOUT a stream has to answer, and it has
#: to answer it "there is no silence clock at all". Re-exported here
#: because this is where it was born and where the tests look.
_STREAM_IDLE_KINDS = capabilities.STREAM_IDLE_KINDS


def _watchdog(proc: subprocess.Popen, sid: str, *,
              stuck_flag: list, done_flag: list, timeout_sec: int,
              parser: StreamParser,
              kind: str = "",
              trap_check_sec_override: int | None = None) -> None:
    """Two jobs while the spawn runs:

    (1) Completion reclaim (rolling): poll the parser; if a CLEAN finish
    (state=finalized, last_stop_reason=end_turn) PERSISTS for
    `completion_grace_sec` while the process is still alive, the agent
    is done but the subprocess is hung (e.g. a stranded background shell
    keeps `claude -p` from exiting — primary_decomposition sid 77403824
    wasted ~535s). Terminate and set `done_flag[0]=True` so the spawn
    routes through the normal parse/salvage path (the on-disk output is
    complete). A new message_start resets the timer (the parser clears
    last_stop_reason), so a still-working agent is never cut; a normally
    exiting spawn closes its pipes well within the grace window and is
    picked up by the natural-exit return below.

    (2) Trap check at `trap_check_sec` (single-shot): sample BOTH
    parser-trap state AND silence; kill iff both fire. Which clock
    "silence" means is chosen by `kind` (see `_STREAM_IDLE_KINDS`):
    tool cadence for the formalizer family, stream liveness for the NL
    layer. `stuck_flag[0]`
    on kill routes the spawn to STUCK_THINKING → combined fresh-sid
    takeover. When AND fails, exit quietly — the spawn runs to its full
    subprocess timeout and the TIMEOUT path's parser-only trap check
    picks up the trap-without-silence cases.

    If `proc` finishes naturally before the trap-check moment, exit
    without sampling (no decision to make).

    Runs in a daemon thread.
    """
    from ..core import config as _cfg
    if trap_check_sec_override is not None:
        # Per-spawn override (classify: scales with the kept-decl count, see
        # librarian._classify_trap_budget) — a legitimately long single think
        # over N decls must not be mistaken for a trap at the global 660s.
        trap_check_sec = trap_check_sec_override
    else:
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

    completion_grace_sec = _cfg.get(
        "dispatch.completion_grace_sec",
        default=_DEFAULT_COMPLETION_GRACE_SEC,
        env_var="ASTERISM_COMPLETION_GRACE_SEC", cast=int,
    )

    # Rolling poll until the trap-check moment. Each slice also runs the
    # completion-reclaim check (job 1). 2s slices keep the thread cheap
    # and responsive to a fast-finishing spawn.
    completion_since: float | None = None
    while proc.poll() is None:
        now = time.monotonic()
        if now >= trigger_at:
            break
        snap = parser.snapshot()
        if (snap.state.value == "finalized"
                and snap.last_stop_reason == "end_turn"):
            # Clean terminal finish. Start (or continue) the grace timer.
            if completion_since is None:
                completion_since = now
            elif now - completion_since >= completion_grace_sec:
                # Held the whole grace window but proc still alive → the
                # agent is done and the subprocess is hung. Terminate and
                # flag for the parse/salvage path (on-disk output is
                # complete; a real timeout would salvage it identically).
                if proc.poll() is None:
                    done_flag[0] = True
                    print(f"[watchdog] sid={sid[:8]} agent finalized "
                          f"(end_turn) and idle {completion_grace_sec}s "
                          f"but proc alive; terminating to reclaim — "
                          f"salvaging on-disk output", flush=True)
                    try:
                        proc.terminate()
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                return
        else:
            # A new turn started (parser cleared last_stop_reason) or the
            # agent is mid-work — reset the grace timer.
            completion_since = None
        time.sleep(min(2.0, max(0.0, trigger_at - time.monotonic())))

    if proc.poll() is not None:
        return  # Proc finished naturally before trap_check_sec.

    snap = parser.snapshot()
    _now = time.monotonic()
    tool_idle = parser.silence_seconds(_now)
    stream_idle = parser.stream_idle_seconds(_now)
    stream_metric = (capabilities.liveness_clock(PROVIDER_NAME, kind)
                     == capabilities.LIVENESS_STREAM)
    silence = stream_idle if stream_metric else tool_idle
    verdict_state = snap.state.value
    verdict_stop = snap.last_stop_reason or "—"
    is_trap = parser.is_thinking_trap()
    is_silent = silence > silence_threshold_sec
    # Both clocks in the log whichever one decides: the pair is what a
    # later calibration of the threshold has to read.
    label = (f"state={verdict_state} last_stop_reason={verdict_stop} "
             f"silence={int(silence)}s "
             f"[{'stream' if stream_metric else 'tool'}-clock; "
             f"tool_idle={int(tool_idle)}s stream_idle={int(stream_idle)}s]")
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
# EMPTY, and that is the point: with no `Bash(...)` pattern an unmatched
# Bash call falls to the permission prompt, which headless auto-denies.
# The general kinds reach the framework's tools over MCP instead
# (`knowledge/mcp_tools.py`) — one whitelist, same for every provider.
#
# Both former entries left on 2026-07-30/31. Loogle became an MCP tool.
# `json.tool` followed once `validate_json` existed, and its removal was
# not cosmetic: `python -m json.tool <in> <out>` takes an OUTFILE, so the
# trailing `*` in `Bash(python -m json.tool *)` was a write channel —
# enough to overwrite a proved brick with valid JSON. It was described
# for two months as "a structured, side-effect-free validator", which is
# what the module does in the shape the agents used, not what the module
# can do. Scholar still adds its two curated network commands; that is
# the whole remaining shell surface.
DEFAULT_BASH_ALLOWED = ""

#: Framework tools, exposed over MCP so every provider reaches them the
#: same way. claude CLI names MCP tools `mcp__<server>__<tool>`.
_TOOLS_MCP_PATTERNS = ("mcp__asterism_tools__loogle",
                       "mcp__asterism_tools__validate_json")


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


# Windows CreateProcess caps the WHOLE command line at 32,767 chars;
# exceeding it fails the spawn with WinError 206 (ERROR_FILENAME_EXCED_RANGE,
# rendered as "檔名或副檔名太長"). The reflection prompt hit this live once
# its dynamic {global_lessons} block grew past ~30KB (sphere_homology
# 2026-07-05) — the error was best-effort-swallowed, silently losing every
# lesson writeback. A prompt this large is a DESIGN BUG in its producer
# (an unbounded dynamic section); transporting it anyway (a briefly-shipped
# stdin fallback) would hide exactly that signal, so the guard fails the
# spawn LOUDLY instead (user call, 2026-07-05). Threshold leaves headroom
# for the other flags/paths that share the command line.
_ARGV_PROMPT_MAX = 25_000


class PromptTooLarge(RuntimeError):
    """Prompt exceeds the safe argv budget — fix the PRODUCER, don't raise
    the cap: every dynamic prompt section must be bounded by design."""


def _assert_prompt_fits(prompt: str) -> None:
    if len(prompt) > _ARGV_PROMPT_MAX:
        raise PromptTooLarge(
            f"prompt is {len(prompt)} chars > {_ARGV_PROMPT_MAX} argv budget "
            f"(Windows CreateProcess caps the command line at 32767). A "
            f"prompt this large means an UNBOUNDED dynamic section in its "
            f"producer — fix that, don't transport it. Head: "
            f"{prompt[:160]!r}")


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
    return render_prompt_template(text, is_postmortem=req.is_postmortem,
                                  flags=req.prompt_flags)


def _build_cold_prompt(req: LLMRequest) -> str:
    """Compose the `-p` payload for a cold (non-retry) spawn: the full
    prompt template content, followed by short framework instructions
    pointing at Context.md and the output directory. The Context.md
    clause only renders when the file exists — adversary spawns point
    `attempts_dir` at the projection, which has no Context.md and whose
    reading order the prompt template itself dictates (07-19 ×5:
    spurious file-not-found as the judge's first action).
    """
    body = _load_prompt(req)
    ctx = req.attempts_dir / "Context.md"
    context_clause = (f"read context at {ctx} and " if ctx.exists()
                      else "")
    return (
        f"You are running a {req.kind} task. Follow the instructions "
        f"below exactly.\n\nAfter reading them, {context_clause}write "
        f"outputs into {req.attempts_dir}/.\n\n"
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
        usage = parser.usage()
        body = json.dumps({
            "state": snap.state.value,
            "last_stop_reason": snap.last_stop_reason,
            "messages_seen": snap.messages_seen,
            "is_thinking_trap": parser.is_thinking_trap(),
            # Token accounting (task #7) — rides this existing forensic
            # artifact (WorkArea packs attempts_dir into
            # dead_attempts.artifacts, so per-spawn spend stays queryable
            # with no schema change).
            "usage": usage,
        })
        (attempts_dir / "_parser_state.json").write_text(
            body, encoding="utf-8")
        if usage.get("turns") or usage.get("output_tokens"):
            print(f"[usage] {attempts_dir.name}: "
                  f"in={usage['input_tokens']} "
                  f"out={usage['output_tokens']} "
                  f"cache_read={usage['cache_read_input_tokens']} "
                  f"cache_new={usage['cache_creation_input_tokens']} "
                  f"turns={usage['turns']}", flush=True)
    except (OSError, ValueError, KeyError):
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
    # Any spawn may carry additional read-only directories beyond its
    # kind's standard scope (req.extra_read_dirs; the Adversary's
    # landed-proofs grant is the first user — see LLMRequest).
    extra_reads = [
        pat for d in (req.extra_read_dirs or ())
        for pat in (f"Read({Path(d).as_posix()}/**)",
                    f"Grep({Path(d).as_posix()}/**)")
    ]
    # Adversary (research_mode_design.md §3) — projection isolation:
    # the judge's whole world is its assembled directory (problem_dir
    # IS the projection) plus the problem's landed `proofs/` in place
    # (extra_read_dirs, 2026-08-04 — the cited-file staging + cap
    # truncated the judge's evidence on big problems); no
    # Library/Papers/mathlib surfaces. Loogle stays available for
    # checking "mathlib has X" claims.
    if req.kind == "adversary":
        return " ".join(p for p in [
            os.environ.get("ASTERISM_CLAUDE_ALLOWED_BASH",
                           DEFAULT_BASH_ALLOWED),
            f"Read({problem}/**)",
            f"Read({attempts}/**)",
            f"Grep({problem}/**)",
            *extra_reads,
            *(_TOOLS_MCP_PATTERNS
              if req.mcp_config_path is not None else ()),
        ] if p)
    patterns = [
        # Bash (Loogle, plus operator override)
        os.environ.get("ASTERISM_CLAUDE_ALLOWED_BASH", DEFAULT_BASH_ALLOWED),
        # Scholar (paper v2, D12): the two curated network commands are
        # this kind's ONLY extra surface — the LLM judges, the commands
        # touch the network (search = open metadata APIs; fetch =
        # whitelisted hosts + caps, see Tooling/papers/fetch.py).
        # (Scholar's two curated commands used to be granted here as
        # `Bash(python -m Tooling.papers.… *)`. They are MCP tools now —
        # `paper_search` / `paper_fetch` — which is what made closing
        # Bash possible without decapitating that role. A trailing `*`
        # in a Bash pattern was also a write channel, the way
        # `json.tool <in> <out>` was.)
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
        *extra_reads,
    ]
    # Library/ is the Librarian (cleanup/migrate) pipeline's working set: it
    # reads/greps sibling Library files for cross-file alignment + call sites.
    # `--add-dir Library` (spawn cmd) already grants FS access, but WITHOUT the
    # matching Grep/Read allow-pattern the agent's Grep/Read on Library are
    # permission-denied; it falls back to `Bash grep`, which is ALSO blocked
    # (Bash = loogle only), leaving it no tool to explore Library — so it loops
    # on denied calls until the spawn times out (residue_thm cleanup spawns each
    # burned their full 960s × retries this way, 2026-06-17). Proving pipelines
    # never hit this: their working set is problem_dir + Mathlib, both scoped.
    library = workspace / "Library"
    if library.is_dir():
        lib = library.as_posix()
        patterns += [f"Read({lib}/**/*.lean)", f"Grep({lib}/**)"]
    # Papers/ (paper pipeline bookshelf): agents Read normalized text /
    # maps on demand; the original .pdf is the extraction-failure
    # fallback (Read renders PDF pages). Whole-shelf grant mirrors
    # Library — steering to THIS problem's paper is the Context
    # section's job, enforcement stays coarse.
    papers = workspace / "Papers"
    if papers.is_dir():
        pp = papers.as_posix()
        patterns += [f"Read({pp}/**/*.md)", f"Read({pp}/**/*.pdf)",
                     f"Grep({pp}/**)"]
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
            *_TOOLS_MCP_PATTERNS,
        ])
    return " ".join(p for p in patterns if p)


def _workspace_from_problem_dir(problem_dir: Path) -> Path:
    """problem_dir = <workspace>/Problems/<name…>; return <workspace>.

    `<name>` may be namespaced (dot→slash, e.g. `LinearAlgebra/jordan_normal_form`
    → 3 levels deep), so locate the `Problems` path component instead of
    assuming a fixed `.parent.parent` depth — the old hard-coded 2-level walk
    silently returned `…/Problems` for namespaced problems, which dropped the
    `.lake/packages` (mathlib) and `Library/` --add-dir grants."""
    p = Path(problem_dir)
    for parent in p.parents:
        if parent.name == "Problems":
            return parent.parent
    return p.parent.parent  # fallback: legacy flat layout


def _trim_flags(req: LLMRequest | None = None) -> list[str]:
    """CLI flags that strip system-prompt overhead Asterism doesn't
    benefit from + per-spawn allowlist for Read/Grep/Bash.

    `req=None` is for callers that don't run agent tools. The
    path-scoped allowlist is dropped in that case; the Bash allowlist is
    still emitted for back-compat with tests. (Its only user was
    `complete_text`, retired 2026-08-07 — the branch stays because
    `_trim_flags()` is called req-less from tests and would otherwise
    need a second signature.)
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


def _operator_state_deny_rules() -> list[str]:
    """Deny rules pinning spawns out of the operator's Claude state
    (~/.claude/projects/**: auto-memory dir + all session transcripts).

    Claude Code auto-memory is keyed by GIT REPO ROOT (docs
    memory.md#storage-location), so a spawn cwd'd inside Problems/<p>/
    resolves to the OPERATOR's memory dir and is told it is its own —
    spawns read AND wrote it routinely from 2026-06-12 (stokes) to
    2026-07-13 (audit: 300+ reads / 400+ writes across 12 problems).
    That is an unsanctioned bidirectional channel: operator memory can
    carry soundness-sensitive material (e.g. official benchmark
    solutions), and spawn writes land in every future operator session
    context. Two layers close it: CLAUDE_CODE_DISABLE_AUTO_MEMORY
    strips the memory section from the spawn system prompt (root
    cause); these deny rules block re-entry via absolute paths learned
    from month-old notes. Bash cat/echo stays physically possible —
    same accepted porosity as the Manifest deny in the spawn cmd.
    Sanctioned cross-wake stores remain the plan note, LESSONS.md,
    directives and Library.

    Permission rules match paths in POSIX form; on Windows C:\\Users\\x
    is addressed as //c/Users/x (docs permissions.md#read-and-edit).
    """
    home = Path.home().as_posix()          # 'C:/Users/x' or '/home/x'
    if len(home) > 1 and home[1] == ":":
        home = "/" + home[0].lower() + home[2:]
    subtree = f"/{home}/.claude/projects/**"
    return [f"{kind}({subtree})" for kind in ("Read", "Write", "Edit")]


def _spawn_guard_settings_path() -> Path:
    """Generated settings file wiring the spawn_guard PreToolUse hook
    into every spawn (whitelist fence — see spawn_guard.py docstring).

    Injected via `--settings <path>`, which the docs confirm still
    applies under `--setting-sources ""` (cli-reference: with empty
    setting-sources only --settings values apply). Content embeds this
    interpreter's absolute path (bare `python` resolves to the wrong
    venv on this machine), so the file is machine-generated under
    .asterism/, never committed, and rewritten whenever stale."""
    guard = Path(__file__).resolve().parent / "spawn_guard.py"
    settings = {
        "hooks": {
            "PreToolUse": [{
                "matcher": ("Read|Grep|Glob|Edit|Write|MultiEdit"
                            "|NotebookEdit|Bash"),
                "hooks": [{
                    "type": "command",
                    "command": f'"{sys.executable}" "{guard}"',
                    "timeout": 30,
                }],
            }],
        },
    }
    path = guard.parents[2] / ".asterism" / "spawn_guard.settings.json"
    body = json.dumps(settings, indent=2)
    try:
        if not path.exists() or path.read_text(encoding="utf-8") != body:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
    except OSError as exc:
        # Fence degraded, not fatal: the permission deny rules remain.
        print(f"[llm:claude] spawn_guard settings write failed: {exc}",
              flush=True)
    return path


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
        # Staged-pipeline work turn (Formalizer): the intake turn opened
        # this session; resume it and send the work-stage prompt file
        # verbatim (rendered). Unlike is_postmortem this is a FULL work
        # attempt — normal timeout and watchdog apply (the watchdog
        # bucket below only exempts postmortem/inline spawns).
        elif req.continuation and req.session_id:
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
            elif req.retry_reason == "agent_stuck_thinking":
                # Prior attempt died mid-thinking (watchdog / subprocess-
                # timeout trap), NOT a lake error — rc=0, no build ran.
                # Framing it as "failed lake build" with the `combined
                # rc=0` detail sent agents hunting a phantom error and
                # burning the next budget re-deriving the plan (P13 4284
                # spin, 2026-06-15). Frame it honestly and steer toward
                # shipping a tactic.
                prompt = (
                    f"Your previous attempt ran out of time mid-thinking "
                    f"and shipped no usable patch — there was no lake error "
                    f"(it never reached a build). Write patch.lean directly "
                    f"this time; don't re-derive the whole plan. Reuse the "
                    f"prior PROPOSAL.md. Write outputs into "
                    f"{req.attempts_dir}/."
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
        # `Library/` (reusable theorems harvested from prior proved
        # Problems) lives outside problem_dir. Granted to ALL spawn kinds:
        #   - librarian (migrate / cleanup / bridge) edits Library files in
        #     place and must Read/Grep them + their call-site importers.
        #   - proving / forward / strategist workers READ it to CITE existing
        #     Library theorems instead of re-deriving (Library-as-input;
        #     surfaced in Context.md by `_section_library_available`). A
        #     cross-problem citation is sound — Library holds only OTHER,
        #     already-proved problems, so no cycle is possible, and the verify
        #     lake build resolves the `import Library.…` against its olean.
        library_dir = _workspace_from_problem_dir(req.problem_dir) / "Library"
        add_dir_library: list[str] = (
            ["--add-dir", str(library_dir)] if library_dir.is_dir() else [])
        # Adversary hard isolation (research_mode_design.md §3): the
        # projection directory IS req.problem_dir, and the trust
        # boundary must stop there — no mathlib/Library/Papers grants.
        if req.kind == "adversary":
            add_dir_packages = []
            add_dir_library = []
        # Papers/ bookshelf — same trust-boundary reasoning as Library:
        # the allowlist patterns above only take effect inside
        # `cwd ∪ --add-dir`.
        papers_dir = _workspace_from_problem_dir(req.problem_dir) / "Papers"
        add_dir_papers: list[str] = (
            ["--add-dir", str(papers_dir)] if papers_dir.is_dir() else [])
        if req.kind == "adversary":
            add_dir_papers = []
        # extra_read_dirs (LLMRequest): explicit read-only grants beyond
        # the kind's standard scope, rendered BOTH ways — the permission
        # trust boundary is `cwd ∪ --add-dir` and the Read/Grep
        # allowlist only takes effect inside it (see packages_dir note
        # above). Placed after the adversary zeroing on purpose: the
        # landed-proofs grant is the judge's one sanctioned exception
        # to projection isolation (2026-08-04). Read-only stays true
        # via the write fence (proofs/ is not a write root).
        add_dir_extra: list[str] = []
        for _extra in (req.extra_read_dirs or ()):
            if Path(_extra).is_dir():
                add_dir_extra += ["--add-dir", str(_extra)]
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
        # The first clause is the DECLARATION, not a claude fact: a
        # watchdog exists only where there is a stream to sample. Read
        # from `capabilities` so a future provider that reuses this
        # module (or a claude release that drops stream-json) degrades
        # to the timeout-only clock instead of starting a watchdog
        # thread that samples an empty parser forever.
        watchdog_eligible = (
            capabilities.liveness_clock(PROVIDER_NAME, req.kind)
            != capabilities.LIVENESS_TIMEOUT_ONLY
            and not req.is_postmortem
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
        _assert_prompt_fits(prompt)
        cmd = [
            "claude",
            "--model", model,
            "-p", prompt,
            "--permission-mode", "acceptEdits",
            # User-file write-deny (self-audit 2026-07-12 §3-1a):
            # Manifest.md / Defs.lean / Root.lean are the user-intent
            # SoT — no spawn has a legitimate write path to them (the
            # sanctioned change channel is RequestUserAmend → operator;
            # framework-side amend/promote writers are Python, not
            # spawn tools). Bash writes remain physically possible —
            # the Ingest snapshot's Manifest history (§3-1b) is the
            # any-channel detection backstop.
            "--disallowedTools",
            # The shell closes here (2026-08-10). `--allowedTools` never
            # shut it: that list is ADDITIVE pre-approval, and with
            # `--permission-mode acceptEdits` a headless spawn ran Bash
            # whether or not a pattern named it — measured, twice. Once
            # by transcript (a `sed … > D:\…` whose unquoted redirect
            # bash flattened into the problem dir, four days after the
            # shell was believed closed) and once by probe: the same
            # prompt runs `echo` with no deny and answers "I don't have
            # a shell execution tool" with it.
            # What replaced the 33k measured calls: `inspect` for the
            # ~91% that was reading, `compute` for the ~3% that was
            # arithmetic, `paper_search`/`paper_fetch` for the Scholar's
            # two curated commands. spawn_guard's refusal names them.
            "Bash",
            "Write(**/Manifest.md)", "Edit(**/Manifest.md)",
            "Write(**/Defs.lean)", "Edit(**/Defs.lean)",
            "Write(**/Root.lean)", "Edit(**/Root.lean)",
            # PROGRAMME.md is a read-only render of the adversarially
            # reviewed Programme (research_mode_design.md §2); the only
            # write path is state.programme on a passed proposal commit.
            "Write(**/PROGRAMME.md)", "Edit(**/PROGRAMME.md)",
            *_operator_state_deny_rules(),
            # Whitelist fence (spawn_guard.py): PreToolUse hook denies
            # file tools outside {repo, scratchpad, ~/.elan} and Bash
            # touching home outside {scratchpad, ~/.elan}.
            "--settings", str(_spawn_guard_settings_path()),
            "--add-dir", str(req.problem_dir),
            "--add-dir", str(req.attempts_dir),
            *add_dir_packages,
            *add_dir_library,
            *add_dir_papers,
            *add_dir_extra,
            *mcp_flags,
            *output_flags,
            *session_flags,
            *session_lifetime_flag,
            *_trim_flags(req),
        ]
        from .envelope import spawn_env
        env = spawn_env()
        # Per-spawn write whitelist for spawn_guard's write-family fence
        # (task #128): file-tool WRITES are default-deny outside these
        # roots — the attempts sandbox, plus the kind's sanctioned edit
        # surface (the librarian family edits Library in place; every
        # other persisted artifact is written by framework code, not
        # spawn tools). Attempts dir stays FIRST — the deny message
        # points at roots[0].
        # The roots themselves come from `envelope.envelope_for` — the
        # same grants agy renders into its per-spawn settings.json, so a
        # third provider inherits one definition instead of a third copy.
        from .envelope import envelope_for
        from .spawn_guard import READ_DENY_ROOTS_ENV, WRITE_ROOTS_ENV
        spec = envelope_for(req, library_dir=library_dir)
        env[WRITE_ROOTS_ENV] = spec.write_roots_env()
        # Reads keep the broad repo whitelist MINUS the operator-private
        # subtrees (#162, 2026-08-10). Until that ruling the repo root was
        # readable whole, so a spawn could open `docs/internal/`, the live
        # `asterism.db`, or another problem's proofs — the exposure that
        # was written up as agy-specific and never was.
        env[READ_DENY_ROOTS_ENV] = spec.read_deny_roots_env()
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
        # Cap formula: 1000 tokens/min of wall-clock budget, floored at the
        # Anthropic API's 1024-token minimum (`_thinking_budget`). A sub-1024
        # budget is rejected 400 and fails the spawn — silently dropping every
        # short-timeout feedback turn before this floor (#33).
        env["CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING"] = "1"
        env["MAX_THINKING_TOKENS"] = str(_thinking_budget(req.timeout_sec))
        # The allowlisted `python -m Tooling.knowledge.loogle` must be
        # runnable from the spawn's cwd (problem_dir, not repo root) —
        # without PYTHONPATH the advertised search tool was dead on
        # arrival for every agent (agent_feedback 2026-07-13, 5 reports).
        _repo_root = str(Path(__file__).resolve().parents[2])
        env["PYTHONPATH"] = (
            _repo_root + os.pathsep + env["PYTHONPATH"]
            if env.get("PYTHONPATH") else _repo_root)
        # Spawn memory isolation (2026-07-13): see
        # _operator_state_deny_rules for the whole story. This env var
        # is the root-cause layer — no memory section in the spawn
        # system prompt, so the spawn never learns the shared dir.
        env["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] = "1"
        proc = subprocess.Popen(
            cmd, env=env, cwd=str(req.problem_dir),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace",
            creationflags=no_window_creationflags(),
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
        done_flag: list[bool] = [False]
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
                    "done_flag": done_flag,
                    "timeout_sec": req.timeout_sec,
                    "parser": parser,
                    "kind": req.kind,
                    "trap_check_sec_override": req.trap_check_sec,
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
        # Watchdog completion-reclaim: agent finalized (end_turn) but the
        # process hung past the grace window. The on-disk output is
        # complete, so route through the same TIMEOUT salvage path
        # (parse_fn) a real subprocess timeout uses — rc=124. Distinct
        # log so this isn't mistaken for a genuine wall-cap timeout.
        if done_flag[0]:
            print(f"[llm:claude] watchdog completion-reclaim "
                  f"(agent done, process hung) — salvaging", flush=True)
            _write_spawn_stderr(req.attempts_dir,
                                "(watchdog completion-reclaim: agent "
                                "finalized end_turn but process hung — "
                                "see [watchdog] log line above)", "", 124)
            return 124
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

