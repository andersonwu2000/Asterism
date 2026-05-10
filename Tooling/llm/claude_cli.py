"""Claude CLI provider — subprocess to `claude` executable.

Inherits the existing claude CLI workflow: `--add-dir` for sandboxing,
`acceptEdits` permission, text output. The agent reads `Context.md`
from `attempts_dir/` and writes outputs back there. The prompt
template content is inlined into `-p` (F45) so the agent doesn't
need read access to the workspace `Tooling/prompts/` directory.

Model selection: `ASTERISM_AGENT_MODEL` env (default: Sonnet).

System-prompt trim (F27): direct measurement of the claude CLI 2.1
default vs the optimized flags below shows ~20.7K → ~7.8K prefix
tokens per call (-62%) on Sonnet. The 4 flags strip tool descriptions
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

from .base import LLMRequest, RESCUE_BUDGET_SEC, SpawnRC


# F51 — extract names from "Unknown constant `X.Y.Z`" / "unknown identifier
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
            f"- `{n}` not found. Try: `python -m Tooling.loogle "
            f"'{loogle_q} _'`"
        )
    return "\n".join(lines)


# F53/3b — generic stderr-pattern → diagnostic-hint table. Each entry
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
    # matters. P1-#9 / review follow-up.
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
# Watchdog policy: at the wall-clock cap (= `timeout_sec -
# RESCUE_BUDGET_SEC`), kill the spawn ONLY if the agent has been idle
# (no tool_use in the session jsonl) for ≥ `idle_window_sec`. The
# wall_cap exists to guarantee the retry helper a rescue window before
# subprocess timeout; the idle-window guard avoids killing agents that
# are demonstrably making progress and would benefit from running to
# their full budget + the standard postmortem flow.
#
# Trade-off vs the older unconditional wall_cap kill: a stuck-thinking
# agent now wastes its rescue window if it had ANY tool_use within the
# last `idle_window_sec` before wall_cap. Empirically, runaway thinking
# is silent (no tool_use) so this is fine. Productive agents that hit
# wall_cap with recent tool_use no longer get force-shipped via rescue
# — they run to subprocess timeout and write a postmortem note instead,
# which is the cheaper outcome for them.
#
# Re-introduced after `ff94493` removed it: SG run #5 (2026-05-10)
# showed concrete cases where Backward agents hit wall_cap mid-active
# work (kept emitting tool_use up to wall_cap) and got force-shipped
# into bad splits — the multiplicative downstream cost (parent_needs_fix
# cascade-up) made the unconditional kill the wrong default for
# Backward, and the idle-window guard recovers the productive cases.
_WATCHDOG_POLL_SEC = 30
_DEFAULT_IDLE_WINDOW_SEC = 480
# Floor on the wall_cap so misconfigured `timeout_sec < rescue_budget`
# pairs (or tests that pass tiny timeouts) don't fire the watchdog
# immediately. 60s is a safe minimum for any real spawn; tests
# monkeypatch this down for fast watchdog assertions.
_MIN_WALL_CAP_SEC = 60


def _find_session_jsonl(sid: str) -> Path | None:
    """Locate the per-session jsonl claude CLI maintains under
    `~/.claude/projects/<encoded_cwd>/<sid>.jsonl`. Returns None if
    not yet created (cold start race) or if the .claude tree is
    missing entirely. Watchdog handles None by waiting another tick."""
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


def _count_tool_use_events(log_path: Path) -> int:
    """Count tool_use content blocks in a session jsonl. Tolerates
    the trailing line being mid-write (claude appends as model streams)
    via per-line try/except — partial JSON is silently skipped."""
    count = 0
    try:
        text = log_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return count
    for line in text.splitlines():
        if not line:
            continue
        try:
            d = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        msg = d.get("message", {}) or {}
        content = msg.get("content", [])
        if isinstance(content, list):
            for c in content:
                if isinstance(c, dict) and c.get("type") == "tool_use":
                    count += 1
    return count


def _watchdog(proc: subprocess.Popen, sid: str, *,
              stuck_flag: list, timeout_sec: int,
              poll_interval: float = _WATCHDOG_POLL_SEC) -> None:
    """Monitor `proc`; at the wall-clock cap
    (= `timeout_sec - dispatch.rescue_timeout_sec`), kill only if the
    agent has been silent for ≥ `dispatch.idle_window_sec`. Sets
    `stuck_flag[0] = True` on kill so the caller can route the spawn to
    the rescue path. If wall_cap is reached but the agent is still
    active (recent tool_use), exit the watchdog quietly — the spawn
    runs to its full subprocess timeout and the postmortem path takes
    over. Runs in a daemon thread; exits when `proc` finishes naturally.
    """
    from .. import config as _cfg
    rescue_budget = _cfg.get(
        "dispatch.rescue_timeout_sec",
        default=RESCUE_BUDGET_SEC,
        env_var="ASTERISM_RESCUE_TIMEOUT_SEC", cast=int,
    )
    idle_window_sec = _cfg.get(
        "dispatch.idle_window_sec",
        default=_DEFAULT_IDLE_WINDOW_SEC,
        env_var="ASTERISM_IDLE_WINDOW_SEC", cast=int,
    )
    spawn_start = time.monotonic()
    wall_cap_sec = max(_MIN_WALL_CAP_SEC, timeout_sec - rescue_budget)
    log_path: Path | None = None
    last_count = 0
    last_progress = spawn_start

    def _kill(reason: str) -> None:
        stuck_flag[0] = True
        print(f"[watchdog] sid={sid[:8]} {reason} — killing for rescue",
              flush=True)
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    while proc.poll() is None:
        time.sleep(poll_interval)
        now = time.monotonic()
        # Track tool_use progress so the wall_cap check below can
        # consult silence duration. The jsonl appears asynchronously
        # after claude opens the session; tolerate None.
        if log_path is None:
            log_path = _find_session_jsonl(sid)
        if log_path is not None:
            new_count = _count_tool_use_events(log_path)
            if new_count > last_count:
                last_count = new_count
                last_progress = now
        if now - spawn_start > wall_cap_sec:
            silence = now - last_progress
            if silence >= idle_window_sec:
                _kill(f"wall cap {int(wall_cap_sec)}s + idle "
                      f"{int(silence)}s reached")
            else:
                # Agent still active at wall_cap — yield to subprocess
                # timeout so the postmortem path (not rescue) handles it.
                print(f"[watchdog] sid={sid[:8]} wall cap "
                      f"{int(wall_cap_sec)}s reached but agent active "
                      f"(silence={int(silence)}s < "
                      f"{int(idle_window_sec)}s); deferring to "
                      f"subprocess timeout + postmortem", flush=True)
            return

# Asterism's pipelines need Read / Write / Edit for sandbox file
# manipulation, plus F50 search tools:
#   - `Grep`: keyword/name search over Mathlib source (e.g. find
#     `Finset.prod_involution`'s exact signature in <0.5s)
#   - `Bash`: scoped via `--allowed-tools` (see _spawn_allowed_tools
#     below) so the agent can ONLY invoke `python -m Tooling.loogle`
#     for type-pattern search via Loogle's HTTPS API. Other Bash
#     commands stay blocked. Adds ~3K tokens of system-prompt
#     overhead vs F27's strict trim, justified by removing the agent's
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
# F50: Loogle (Mathlib type-pattern search via HTTPS).
DEFAULT_BASH_ALLOWED = "Bash(python -m Tooling.loogle *)"


def resolve_model(kind: str | None) -> str:
    """Model resolution chain for the claude provider (per
    Tooling/config.get):

    1. `ASTERISM_<KIND>_MODEL` env  (kind in {'builder','backward'})
    2. Asterism.yaml `<kind>.model`
    3. `ASTERISM_AGENT_MODEL` env  (legacy provider-wide)
    4. `DEFAULT_MODEL`
    """
    from .. import config
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
    """Read the prompt template file. F45: inlined into `-p` instead
    of pointed-to so the agent never needs read access to the workspace
    `Tooling/prompts/` directory (which lives outside `--add-dir` after
    F44 narrowed cwd to problem_dir). On read error, return a marker
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

    When `is_fresh_rescue=True`, prepend an imperative instruction
    requiring the agent to Read `_prior_analysis.md` first — that file
    holds the prior killed spawn's thinking blocks, dumped by the
    retry helper. Without this directive the fresh agent often
    re-derives reasoning from scratch (probe finding 2026-05-10).
    """
    body = _load_prompt(req)
    rescue_note = ""
    if req.is_fresh_rescue:
        rescue_note = (
            f"\n\nIMPORTANT: This is a fresh session. The previous spawn "
            f"on this goal was killed mid-thinking (deadlocked on its own "
            f"deep reasoning). Its thinking has been preserved at "
            f"`{req.attempts_dir}/_prior_analysis.md`. You MUST Read that "
            f"file before any other action — it contains the prior agent's "
            f"reasoning. Then proceed with the {req.kind} task using that "
            f"reasoning as your starting point; do not redo analysis from "
            f"scratch."
        )
    return (
        f"You are running a {req.kind} task. Follow the instructions "
        f"below exactly.\n\nAfter reading them, read context at "
        f"{req.attempts_dir}/Context.md and write outputs into "
        f"{req.attempts_dir}/.{rescue_note}\n\n"
        f"=== INSTRUCTIONS ===\n{body}\n=== END INSTRUCTIONS ==="
    )


def _write_spawn_stderr(attempts_dir, stderr: str, stdout: str,
                        rc: int) -> None:
    """F46 — write captured stderr to `attempts_dir/_spawn.stderr`
    so pipeline forensics can include it in dead_attempts.failure_detail.
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
    # M1: cover the whole `.lake/packages/` tree, not just
    # `mathlib/Mathlib/`. Sonnet's natural `rg` query is rooted at
    # `.lake/packages/mathlib/` (the package root, not the Mathlib
    # source subdir), which the narrow prefix rejected — observed
    # 18 denied Grep ops in a single proj_nonexpansive run, each
    # wasting one agent turn. Allowing the whole packages tree also
    # covers batteries / proofwidgets / aesop / Qq when an agent
    # legitimately needs to look at them.
    packages = (workspace / ".lake" / "packages").as_posix()
    # NB: claude CLI's `--allowed-tools` parser is paren-aware (the
    # pre-existing `Bash(python -m Tooling.loogle *)` pattern carries
    # internal spaces unquoted), so a `Read(C:/My Project/...)` glob
    # does NOT need quoting either — pattern boundaries are pulled by
    # balanced parens, not whitespace. P1-#9 verified this empirically;
    # the pre-quoting attempt broke the Bash pattern's existing test.
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
        if not shutil.which("claude"):
            print("[llm:claude] claude CLI not found; skipping spawn",
                  flush=True)
            return 127

        model = resolve_model(req.kind)

        # F55 postmortem — main spawn timed out, agent's session memory
        # is intact on disk. Resume the session with a short prompt
        # asking for a state + blocker note (`_progress.md`) into the
        # SAME attempts_dir. The wrapper then captures _progress.md as
        # the partial draft for the next dispatch. Loaded prompt body
        # is short and self-contained — no _build_cold_prompt wrapping
        # (Context.md from the killed turn is already in session memory;
        # re-injecting it would distract the postmortem agent).
        if req.is_postmortem and req.session_id:
            session_flags = ["--resume", req.session_id]
            session_lifetime_flag: list[str] = []
            prompt = _load_prompt(req)
        # In-pipeline retry path uses `--resume`, a short inline prompt
        # with the lake error embedded directly (no separate
        # RETRY_NOTE.md file → agent doesn't need a Read tool round-
        # trip), and skips the file-based prompt fetch (prior turn's
        # context lives in claude's session memory).
        elif req.is_retry and req.session_id:
            session_flags = ["--resume", req.session_id]
            session_lifetime_flag = []  # session persists
            err = (req.retry_context or "(lake error not captured)").strip()
            # F51 — when the prior failure cites unknown constants,
            # nudge the agent to verify names via Loogle/Grep instead
            # of repeating the same guess. Empty hint when no match.
            unknown_hint = _retry_hint_for_unknowns(
                _extract_unknown_constants(err))
            # F53/3b — generic stderr → diagnostic hint table.
            # Catches expected-token / typeclass-stuck / tactic-no-
            # progress patterns the unknown-constant matcher misses.
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

        # M3 — F44 narrows cwd to problem_dir, after which claude CLI's
        # permission system treats `cwd subtree ∪ --add-dir paths` as the
        # implicit trust boundary; absolute paths outside that boundary
        # are denied even when listed in --allowed-tools. Mathlib lives
        # outside problem_dir, so M1's `Read(.lake/packages/**/*.lean)`
        # allowlist alone wasn't enough — proj_nonexpansive 2026-05-03
        # rerun saw 75 mathlib Grep denials per run despite M1. Adding
        # `.lake/packages` as a third --add-dir grants the explicit trust
        # so the allowlist's path patterns actually take effect.
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

        cmd = [
            "claude",
            "--model", model,
            "-p", prompt,
            "--permission-mode", "acceptEdits",
            "--add-dir", str(req.problem_dir),
            "--add-dir", str(req.attempts_dir),
            *add_dir_packages,
            *mcp_flags,
            "--output-format", "text",
            *session_flags,
            *session_lifetime_flag,
            *_trim_flags(req),
        ]
        env = dict(os.environ)
        # Watchdog policy: monitor the session jsonl for tool_use
        # events on normal spawns. Postmortem (180s) + rescue (180s)
        # are already short and skip the watchdog — for those the
        # subprocess timeout is the only kill mechanism. Cold spawns
        # without session_id can't be monitored (no jsonl path), so
        # they also skip; in practice every Asterism dispatch sets
        # session_id, so this branch is just defensive.
        # Fresh-rescue is a cold spawn that runs at full timeout (it
        # IS the rescue, not a tight follow-up); watchdog applies so
        # the new session can also be killed if it deadlocks.
        watchdog_eligible = (
            not req.is_postmortem
            and req.session_id is not None
        )
        proc = subprocess.Popen(
            cmd, env=env, cwd=str(req.problem_dir),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace",
        )
        stuck_flag: list[bool] = [False]
        wd_thread: threading.Thread | None = None
        if watchdog_eligible:
            wd_thread = threading.Thread(
                target=_watchdog,
                args=(proc, req.session_id),
                kwargs={
                    "stuck_flag": stuck_flag,
                    "timeout_sec": req.timeout_sec,
                },
                daemon=True,
            )
            wd_thread.start()
        try:
            stdout, stderr = proc.communicate(timeout=req.timeout_sec)
            rc = proc.returncode
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
            rc = 124
        if wd_thread is not None:
            wd_thread.join(timeout=2)
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
        # F46 — capture stderr to attempts_dir on failure so the
        # pipeline can surface it in dead_attempts.failure_detail.
        # Skipping on rc=0 keeps the sandbox tidy.
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
        stdout text rather than producing files. Used by F22 short
        auxiliary calls (idiom extract / curate). complete_text never
        invokes tools, but the same trim applies to the system prompt.
        F22 auxiliary calls inherit the 'builder' tier (cheap-LLM role)."""
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
