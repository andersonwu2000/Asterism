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

Same-session retry (F33): when LLMRequest.session_id is provided,
the cold path uses `--session-id <uuid>` to pin the session id; a
retry (is_retry=True) uses `--resume <uuid>` and a short prompt
(builder_retry.md) that relies on the session memory carrying the
prior turn's reasoning. `--no-session-persistence` is dropped on
those calls — sessions persist to disk so Asterism can resume them.
Sessions without session_id (e.g. Backward) keep the old
`--no-session-persistence` behavior.

Stale session sentinel (F33): `claude --resume <uuid>` against a
session id whose on-disk file is gone (GC'd / never existed) returns
rc=1 with stderr `"No conversation found with session ID"`. spawn
maps that to rc=125 so the caller (pipeline) knows to clear the
DB session_id and retry with a fresh uuid (cold path).
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess

from .base import LLMRequest


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
    # Sorry warning specifically attributed to a patch file — sub-stub
    # warnings for `new_*.lean` are legitimate (those carry intentional
    # `:= by sorry`) and emit the same lake warning text. Scope the
    # match to filenames the framework would *not* expect to contain
    # sorry: the strategy patch (`_strategy_s<id>.lean`) and the
    # Builder leaf (`<problem-root>.lean` resolves to the agent's
    # `patch.lean` via copy). P1-#9.
    (re.compile(
        r"(?:_strategy_s\d+|patch)\.lean[^\n]*declaration uses\s+`sorry`",
        re.IGNORECASE),
     "Your patch.lean still has `:= by sorry` — that's only legal in "
     "`new_*.lean` sub-goal stubs, NOT in the strategy patch / Builder "
     "patch. Replace the body with real tactics."),
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

# F33 — sentinel rc returned when claude reports "No conversation
# found with session ID: ...". Caller's contract: on rc=125, clear
# the goal's builder_session_id and retry once with a fresh uuid.
RC_STALE_SESSION = 125
_STALE_SESSION_MARKER = "no conversation found with session id"

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


def _resolve_model(kind: str | None) -> str:
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
    normal agent error rather than a silent crash."""
    try:
        return req.prompt_path.read_text(encoding="utf-8")
    except OSError as e:
        return f"(prompt file unavailable: {e})"


def _build_cold_prompt(req: LLMRequest) -> str:
    """Compose the `-p` payload for a cold (non-retry) spawn: the full
    prompt template content, followed by short framework instructions
    pointing at Context.md and the output directory."""
    body = _load_prompt(req)
    return (
        f"You are running a {req.kind} task. Follow the instructions "
        f"below exactly.\n\nAfter reading them, read context at "
        f"{req.attempts_dir}/Context.md and write outputs into "
        f"{req.attempts_dir}/.\n\n"
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
    mathlib = (workspace / ".lake" / "packages" / "mathlib" /
               "Mathlib").as_posix()
    # NB: claude CLI's `--allowed-tools` parser is paren-aware (the
    # pre-existing `Bash(python -m Tooling.loogle *)` pattern carries
    # internal spaces unquoted), so a `Read(C:/My Project/...)` glob
    # does NOT need quoting either — pattern boundaries are pulled by
    # balanced parens, not whitespace. P1-#9 verified this empirically;
    # the pre-quoting attempt broke the Bash pattern's existing test.
    patterns = [
        # Bash (Loogle, plus operator override)
        os.environ.get("ASTERISM_CLAUDE_ALLOWED_BASH", DEFAULT_BASH_ALLOWED),
        # Read scope: this problem's dir, the agent's sandbox, Mathlib
        f"Read({problem}/**)",
        f"Read({attempts}/**)",
        f"Read({mathlib}/**)",
        # Grep needs explicit path patterns too
        f"Grep({problem}/**)",
        f"Grep({mathlib}/**)",
    ]
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

        model = _resolve_model(req.kind)

        # F33 — retry path uses `--resume`, a short inline prompt with
        # the lake error embedded directly (no separate RETRY_NOTE.md
        # file → agent doesn't need a Read tool round-trip), and skips
        # the file-based prompt fetch (prior turn's context lives in
        # claude's session memory).
        if req.is_retry and req.session_id:
            session_flags = ["--resume", req.session_id]
            session_lifetime_flag: list[str] = []  # session persists
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

        cmd = [
            "claude",
            "--model", model,
            "-p", prompt,
            "--permission-mode", "acceptEdits",
            "--add-dir", str(req.problem_dir),
            "--add-dir", str(req.attempts_dir),
            "--output-format", "text",
            *session_flags,
            *session_lifetime_flag,
            *_trim_flags(req),
        ]
        try:
            r = subprocess.run(
                cmd, timeout=req.timeout_sec,
                capture_output=True, text=True,
                encoding="utf-8", errors="replace",
                # F44 — anchor agent cwd at problem_dir, not workspace.
                # Soft-sandbox: relative paths the agent writes resolve
                # under the Problem; reduces wandering reads to other
                # Problems / workspace-root files. attempts_dir is still
                # passed as absolute path in the prompt above so reads
                # there continue to work regardless of cwd.
                cwd=str(req.problem_dir),
            )
            # F46 — capture stderr to attempts_dir on failure so the
            # pipeline can surface it in dead_attempts.failure_detail.
            # Skipping on rc=0 keeps the sandbox tidy.
            if r.returncode != 0:
                _write_spawn_stderr(req.attempts_dir, r.stderr or "",
                                    r.stdout or "", r.returncode)
            # F33 — detect stale session: claude returns rc=1 with
            # "No conversation found with session ID: ..." in stderr.
            # Surface as RC_STALE_SESSION so pipeline can clear the
            # DB session_id and retry with a fresh one.
            if (r.returncode != 0 and req.is_retry
                    and _STALE_SESSION_MARKER in (r.stderr or "").lower()):
                print(f"[llm:claude] stale session "
                      f"{req.session_id[:8] if req.session_id else '?'}",
                      flush=True)
                return RC_STALE_SESSION
            return r.returncode
        except subprocess.TimeoutExpired:
            print(f"[llm:claude] timed out after {req.timeout_sec}s",
                  flush=True)
            _write_spawn_stderr(req.attempts_dir,
                                f"(subprocess.TimeoutExpired after "
                                f"{req.timeout_sec}s)", "", 124)
            return 124

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
        model = _resolve_model("builder")
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
