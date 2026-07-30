r"""Antigravity CLI provider — subprocess to the `agy` executable.

Google retired the Gemini CLI for individual accounts on 2026-06-18:
free tier, Google AI Pro AND AI Ultra all stopped being served (only
enterprise Code Assist licences and API-key auth survived there). The
replacement terminal product is the Antigravity CLI (`agy`), and it is
the ONLY subscription-priced path to Gemini models — the API key route
is per-token. `gemini_cli.py` stays for API-key / enterprise users; it
cannot serve a personal subscription any more.

Interface fit (measured 2026-07-30, agy 1.1.8 — every claim below was
probed, not read off the docs):

  * `-p` headless, `--output-format json` → ONE envelope:
    {"conversation_id","status","response","duration_seconds",
     "num_turns","usage":{input_tokens,output_tokens,thinking_tokens,
     cache_read_tokens,total_tokens}}  — status is "SUCCESS"/"ERROR",
    and an ERROR envelope carries "error".
  * `--conversation <id>` resumes by id and the model REMEMBERS the
    prior turn (probe: second call returned num_turns=2 and quoted
    turn 1 verbatim). This is what makes the Strategist revision loop
    possible; the old gemini provider ignored session_id entirely, so
    the Adversary's rebuttal never reached the strategist.
  * `--print-timeout` defaults to **5m** — far below a Strategist wake.
    Always set it from `req.timeout_sec`.
  * Model slugs come from `agy models` and encode effort:
    gemini-3.1-pro-high / -low, gemini-3.6-flash-high/medium/low,
    gemini-3.5-flash-*, plus claude-sonnet-4-6,
    claude-opus-4-6-thinking, gpt-oss-120b-medium.
    There is NO `gemini-3-pro`: five spellings were probed
    (gemini-3-pro, -high, gemini-3.0-pro-high, -preview,
    gemini-3.6-pro-high) and all came back
    `invalid model selection ... not recognized`.

=====================================================================
AUTHORIZED OPERATIONS — read this before changing anything here
=====================================================================
This provider only works because of grants that live OUTSIDE the repo.
They were made once, by the user, on 2026-07-30. Recorded here so a
later session can find them instead of re-deriving:

1. `agy` install (user ran it; not automatable by an agent — it
   downloads and executes a remote script):
       irm https://antigravity.google/cli/install.ps1 | iex
   Lands `agy.exe` at `%LOCALAPPDATA%\\agy\\bin\\agy.exe`. Self-updating
   Go binary; no node/npm.

2. Authentication: NO login step was needed. `agy` picked up the
   cached credentials of the interactive Antigravity IDE session
   already on the machine. There is no API key and no service account
   — the subscription IS the credential. If a future run fails to
   authenticate, the fix is an interactive `agy` session by the USER,
   not anything this file can do.

2b. CREDENTIAL PRECEDENCE — a silent-downgrade trap (measured
   2026-07-30). `agy` resolves credentials in this order:
       (1) `~/.gemini/oauth_creds.json`   (the gemini-CLI style file)
       (2) the Antigravity IDE's signed-in session
   Both were live on this machine under DIFFERENT accounts, and (1)
   won: agy ran on the operator's own free tier while the IDE was
   signed in to the Google AI Pro account we actually wanted. Renaming
   (1) out of the way (`oauth_creds.json.own`) made the Pro account
   take over — the interactive banner then printed
   `... (Google AI Pro)` and headless `-p` followed suit.
   Why it matters: NOTHING errors when the wrong account wins. Quota
   just comes out of the wrong subscription, and a long run can die on
   a free-tier ceiling with no diagnostic. So:
     - Do NOT restore `~/.gemini/oauth_creds.json` while the IDE
       session is the intended identity.
     - Anything that re-creates that file (running the old `gemini`
       CLI, some other Google login) silently flips the account back.
     - `asterism doctor` warns whenever that file exists, precisely
       because presence — not content — is the detectable signal.
   The IDE session is therefore load-bearing state: signing out of the
   Antigravity IDE, or resetting it, costs a fresh interactive login.
   The token is NOT in a file we control (Electron app storage), so it
   cannot be backed up by copying.

3. Tool permissions — `~/.gemini/antigravity-cli/settings.json`
   (agy's own log names this path; global — there is no project-scoped
   settings file). Installed content, approved by the user:

       permissions.allow:
         read_file(D:\Asterism)              whole workspace, incl. Mathlib
         write_file(D:\Asterism\.attempts)   the only writable root
         command(*)                          see the measurement below
       permissions.deny:
         write_file(D:\Asterism\Problems)
         write_file(D:\Asterism\Library)
         write_file(D:\Asterism\Tooling)

   Precedence is Deny > Ask > Allow and an unmatched action defaults to
   Ask, which headless mode auto-DENIES — so the posture is
   deny-by-default. Every pipeline's write root is
   `.attempts/<pipeline_id>/` (WorkArea; the Adversary projection is
   `.attempts/<pid>/adversary/rN`), so one allow rule covers all spawns
   while `proofs/`, `Root.lean`, `Defs.lean` and `Manifest.md` stay
   unwritable through the write_file tool. Verified: a write into
   `.attempts/` landed; a write into `Problems/` came back
   `Permission denied ... Matches user-configured deny rule`.

   MEASURED — the `command` matcher takes an exact literal or `*`, and
   NOTHING between (2026-07-30, seven probes). Auto-denied:
   `command(python -m Tooling\.knowledge\.loogle)`,
   `command(python -m Tooling.knowledge.loogle)`, `command(python)`,
   `command(python*)`, `command(python -m Tooling.knowledge.loogle .*)`,
   and the last one paired with an `unsandboxed(...)` allow. Accepted:
   `command(*)` and the full literal
   `command(python -m Tooling.knowledge.loogle "Nat.even_mul_succ_self")`.
   The docs' "each whitespace-separated token is an anchored regex" does
   not describe the behaviour. `--sandbox` is not an alternative: it
   demands an `escalate_admin` permission that headless cannot prompt
   for (the run is CANCELED), and granting admin escalation would be
   strictly worse than what it buys.

   THE COST, recorded deliberately (user call): with `command(*)` a
   spawn can write around the write_file deny rules via a command, so
   the sandbox is no longer the write fence. Two mitigations replace it:
     - PATH narrowing was tried and ABANDONED: agy shells out through
       `powershell`, so any command channel implies a reachable shell and
       a shell is a write channel; narrowing only broke loogle. See
       `_spawn_env`.
     - the post-spawn artifact tripwire in `agent.runtime` verifies the
       problem's user files and `proofs/` across every spawn, catching a
       write through ANY channel. That is the actual guarantee, and it
       covers the claude side too (a Bash write there was never checked
       either).
   Soundness never rested on any of this: the commit chokepoint
   (`state/proof_store`), the per-decl axiom gate, the user-file
   baseline pin (`user_file_history` + root gate) and `drift-check` are
   what make a hand-written proof file fail.

4. NEVER pass `--dangerously-skip-permissions`. It auto-approves every
   tool and voids all of the above. `--mode accept-edits` is also
   unnecessary (the allow rule alone let the write through) and would
   only widen the surface.

5. A new pipeline that needs a new capability = a new rule in that
   settings.json, and the user should see the diff first. Per-spawn
   scoping (one write root per spawn, as claude gets via
   `ASTERISM_SPAWN_WRITE_ROOTS`) is NOT expressible in a single global
   file; the known upgrade is a per-spawn fake HOME containing its own
   settings.json, which also means carrying the credential files into
   it. Deliberately not done yet — recorded as the next step if
   per-spawn precision is ever needed.

=====================================================================
THE HAZARD: `status: "SUCCESS"` IS NOT PROOF OF WORK
=====================================================================
When a tool is denied by the *Ask default* (no matching rule), the run
still reports `status:"SUCCESS"` and the model answers confidently —
observed twice: asked to write a file, replied "DONE", wrote nothing,
emitted no warning. Only a `command` denial printed an explicit note,
and only an explicit DENY rule surfaces the denial to the model.
Therefore this provider NEVER trusts the status field: it checks that
the agent actually left an artifact in attempts_dir, and treats
"SUCCESS with nothing written" as a failure. Every pipeline reads its
output (`decision.json` / `verdict.json` / `patch.lean`) off disk, so
the worst case degrades to "no output" rather than a phantom landing —
but it must be reported loudly, because the cause is a permissions
config error that retrying cannot fix.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from ..core.process_group import no_window_creationflags
from .base import LLMRequest


#: Pro tier as of 2026-07-30. Effort is baked into the slug (`-high` /
#: `-low`), so `--effort` is redundant for these and is not passed.
DEFAULT_MODEL = "gemini-3.1-pro-high"

#: rc contract (llm/base.py + rc_to_reason). 123 is this provider's
#: addition: the CLI/config is structurally unusable — bad model slug,
#: refused credentials, or a permission denial that silently produced
#: nothing. Distinct from 126 (quota: wait and it comes back) and 127
#: (CLI absent) because the cure is an operator edit, not time.
RC_MISCONFIGURED = 123
RC_TIMEOUT = 124
RC_QUOTA_EXHAUSTED = 126
RC_MISSING_CLI = 127

#: Wall-clock slack on top of `--print-timeout` so agy's own timeout
#: fires first and it exits with an envelope we can classify.
_SUBPROCESS_SLACK_SEC = 60

#: Envelope-level phrases. Matched lowercased against status+error.
_MISCONFIG_MARKERS = (
    "invalid model selection",
    "not recognized as a known model",
    "ineligibletier",
    "no longer supported",
    "unauthorized",
    "not authenticated",
    "permission denied for",
)
_QUOTA_MARKERS = (
    "exhausted your capacity",
    "resource_exhausted",
    "too many requests",
    "rate limit",
    "status: 429",
    "quota",
)

#: Files this provider (or the framework) writes into attempts_dir —
#: never evidence that the AGENT produced something.
_NON_ARTIFACTS = ("Context.md", "_parser_state.json", "_agy_session.json",
                  "_spawn.stderr")

_SESSION_MAP = "_agy_session.json"


def legacy_oauth_creds_path() -> Path:
    """`~/.gemini/oauth_creds.json` — the gemini-CLI credential file,
    which `agy` prefers over the Antigravity IDE session (see
    AUTHORIZED OPERATIONS §2b). Its mere PRESENCE decides which account
    serves the run, and picking the wrong one is silent, so doctor
    surfaces it."""
    return Path.home() / ".gemini" / "oauth_creds.json"


def _spawn_env() -> "dict[str, str]":
    """Environment for an agy spawn: the inherited env plus PYTHONPATH.

    PYTHONPATH must carry the repo root or the advertised search tool
    (`python -m Tooling.knowledge.loogle`) is dead on arrival from any
    cwd but the root — claude_cli does the same for its own spawns
    (agent_feedback 2026-07-13 ×5).

    NOT narrowed further, and that was measured rather than assumed
    (2026-07-30): the first attempt pointed PATH at a policy shim that
    forwarded only the loogle module, so `command(*)` could not become a
    write channel. It failed for a structural reason — agy executes
    every command through `powershell`, so a reachable shell is a
    precondition for ANY command, and a reachable shell IS a write
    channel (`Set-Content`). Narrowing PATH only broke loogle
    (`exec: "powershell": executable file not found in %PATH%`), and
    wrapping powershell to inspect its `-Command` payload is defeated by
    quoting / `-EncodedCommand`. So the write control is the post-spawn
    artifact tripwire in `agent.runtime`, not the sandbox.
    """
    repo = Path(__file__).resolve().parents[2]
    env = dict(os.environ)
    env["PYTHONPATH"] = (
        str(repo) + os.pathsep + env["PYTHONPATH"]
        if env.get("PYTHONPATH") else str(repo))
    return env


def permissions_path() -> Path:
    """Where `agy` reads its `permissions.allow` / `deny` rules — the
    file that IS the write fence (AUTHORIZED OPERATIONS §3). Global and
    single: agy has no project-scoped settings file and no `--policy`
    flag. Its own log names this path when the file is absent."""
    return Path.home() / ".gemini" / "antigravity-cli" / "settings.json"


def resolve_agy_executable() -> "str | None":
    """Launchable path for `agy`, or None.

    The PowerShell installer drops it in `%LOCALAPPDATA%\\agy\\bin` and
    edits the *user* PATH, which a long-lived daemon process started
    before the install will not see — so probe the install location
    first and only then fall back to PATH.
    """
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA")
        if local:
            cand = Path(local) / "agy" / "bin" / "agy.exe"
            if cand.is_file():
                return str(cand)
        for ext in (".exe", ".cmd", ".bat"):
            p = shutil.which(f"agy{ext}")
            if p:
                return p
    return shutil.which("agy")


def _resolve_model(kind: "str | None") -> str:
    """`<kind>.model` → `ASTERISM_<KIND>_MODEL` → DEFAULT_MODEL, the
    same chain every other provider uses (Tooling/core/config.get)."""
    from ..core import config
    if not kind:
        return os.environ.get("ASTERISM_AGY_MODEL", DEFAULT_MODEL)
    return str(config.get(
        f"{kind}.model",
        env_var=f"ASTERISM_{kind.upper()}_MODEL",
        legacy_env=("ASTERISM_AGY_MODEL",),
        default=DEFAULT_MODEL,
    ))


def _write_spawn_stderr(attempts_dir: Path, body: str, rc: int) -> None:
    """Forensics mirror of the claude/gemini helper. Best-effort."""
    try:
        (attempts_dir / "_spawn.stderr").write_text(
            f"rc={rc}\n{body[:10240]}", encoding="utf-8")
    except OSError:
        pass


def _load_session_map(attempts_dir: Path) -> "dict[str, str]":
    try:
        raw = (attempts_dir / _SESSION_MAP).read_text(encoding="utf-8")
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _remember_conversation(attempts_dir: Path, sid: "str | None",
                           conversation_id: str) -> None:
    """Map the framework's session id onto agy's conversation id.

    agy cannot be told which id to use — it MINTS one and reports it in
    the envelope — so resume is a two-step: record it on the cold call,
    replay it on the retry. The map lives in attempts_dir, which is
    per-pipeline: the Strategist's revision rounds share one dir (they
    must resume), while each Adversary round gets its own projection
    dir (it must NOT — a fresh judge per round is the design)."""
    if not sid or not conversation_id:
        return
    data = _load_session_map(attempts_dir)
    data[sid] = conversation_id
    try:
        (attempts_dir / _SESSION_MAP).write_text(
            json.dumps(data), encoding="utf-8")
    except OSError:
        pass


def _record_usage(attempts_dir: Path, envelope: dict) -> None:
    """Translate agy's usage block into the `_parser_state.json` shape
    `agent.runtime._record_spawn_usage` reads, so judge/strategist cost
    lands in `spawn_usage` exactly like a claude spawn (#107 / #126).
    agy reports it directly — no stream parsing needed."""
    u = envelope.get("usage") or {}
    try:
        (attempts_dir / "_parser_state.json").write_text(
            json.dumps({"usage": {
                "turns": int(envelope.get("num_turns") or 0),
                "input_tokens": int(u.get("input_tokens") or 0),
                "output_tokens": int(u.get("output_tokens") or 0),
                "cache_read_input_tokens": int(u.get("cache_read_tokens")
                                               or 0),
                # agy exposes no cache-creation counter; 0 keeps the
                # five-tuple dedup key stable rather than absent.
                "cache_creation_input_tokens": 0,
            }}), encoding="utf-8")
    except OSError:
        pass


def _agent_artifact_present(attempts_dir: Path) -> bool:
    """Did the AGENT leave anything? See "THE HAZARD" in the module
    docstring: a silently-denied write returns SUCCESS, so the on-disk
    check is the only honest signal. `.json` counts — the old gemini
    provider's check listed only .lean/.md, which would have marked
    every successful Adversary run (verdict.json) as no-output."""
    if not attempts_dir.is_dir():
        return False
    for p in attempts_dir.iterdir():
        if p.name in _NON_ARTIFACTS:
            continue
        if p.is_dir():
            continue
        if p.suffix in (".lean", ".md", ".json", ".txt"):
            return True
    return False


def _classify(envelope: "dict | None", raw: str, rc: int) -> int:
    """Envelope-first classification; process rc is only a fallback.

    agy exits 1 for every ERROR envelope regardless of cause, so the rc
    alone cannot tell a bad model slug from a dead credential from a
    transient blip — and mapping all of them to the default
    `spawn_fast_fail` would make the daemon retry a config error
    forever with nothing in the log but a cooldown.
    """
    text = raw.lower()
    if envelope is not None:
        text = (str(envelope.get("status", "")) + " "
                + str(envelope.get("error", ""))).lower() + " " + text
    if any(m in text for m in _MISCONFIG_MARKERS):
        return RC_MISCONFIGURED
    if any(m in text for m in _QUOTA_MARKERS):
        return RC_QUOTA_EXHAUSTED
    return rc if rc != 0 else 1


class AntigravityCliProvider:
    def spawn(self, req: LLMRequest) -> int:
        exe = resolve_agy_executable()
        if not exe:
            print("[llm:agy] agy CLI not found "
                  "(install: irm https://antigravity.google/cli/"
                  "install.ps1 | iex)", flush=True)
            return RC_MISSING_CLI

        model = _resolve_model(req.kind)
        prompt = self._build_prompt(req)
        print_timeout = max(60, int(req.timeout_sec or 900))

        cmd = [
            exe,
            "-p", prompt,
            "--model", model,
            "--output-format", "json",
            "--print-timeout", f"{print_timeout}s",
            # cwd anchors the workspace at problem_dir (mirrors
            # claude_cli); attempts_dir is elsewhere for worker spawns
            # and must be joined explicitly. For the Adversary both are
            # the projection dir, so this is a no-op there.
            "--add-dir", str(req.attempts_dir),
        ]
        conversation = None
        if req.is_retry and req.session_id:
            conversation = _load_session_map(
                req.attempts_dir).get(req.session_id)
            if conversation:
                cmd += ["--conversation", conversation]
        # No --dangerously-skip-permissions, no --mode: see AUTHORIZED
        # OPERATIONS §4.

        try:
            r = subprocess.run(
                cmd, timeout=print_timeout + _SUBPROCESS_SLACK_SEC,
                capture_output=True, text=True,
                encoding="utf-8", errors="replace",
                cwd=str(req.problem_dir), env=_spawn_env(),
                creationflags=no_window_creationflags(),
            )
        except subprocess.TimeoutExpired:
            print(f"[llm:agy] timed out after {print_timeout}s", flush=True)
            _write_spawn_stderr(req.attempts_dir,
                                f"(subprocess.TimeoutExpired after "
                                f"{print_timeout}s)", RC_TIMEOUT)
            return RC_TIMEOUT
        except FileNotFoundError as e:
            print(f"[llm:agy] launch failed ({e})", flush=True)
            _write_spawn_stderr(req.attempts_dir, str(e), RC_MISSING_CLI)
            return RC_MISSING_CLI

        raw = (r.stdout or "") + "\n" + (r.stderr or "")
        envelope = _parse_envelope(r.stdout or "")
        if envelope is not None:
            _record_usage(req.attempts_dir, envelope)
            _remember_conversation(req.attempts_dir, req.session_id,
                                   str(envelope.get("conversation_id") or ""))

        status = str((envelope or {}).get("status") or "")
        if r.returncode != 0 or status.upper() != "SUCCESS":
            code = _classify(envelope, raw, r.returncode)
            detail = str((envelope or {}).get("error") or "")[:400]
            print(f"[llm:agy] {req.kind}: status={status or '?'} "
                  f"rc={r.returncode} → {code}"
                  + (f": {detail}" if detail else ""), flush=True)
            _write_spawn_stderr(req.attempts_dir, raw, code)
            return code

        # SUCCESS is not proof — see THE HAZARD.
        if not _agent_artifact_present(req.attempts_dir):
            try:
                left = sorted(p.name for p in req.attempts_dir.iterdir())
            except OSError:
                left = []
            print(f"[llm:agy] {req.kind}: status=SUCCESS but the agent "
                  f"left no usable artifact in {req.attempts_dir} "
                  f"(files: {', '.join(left) or 'none'}) — a tool was "
                  f"almost certainly auto-denied (no matching "
                  f"permissions.allow rule). Retrying will not help; fix "
                  f"~/.gemini/antigravity-cli/settings.json.", flush=True)
            _write_spawn_stderr(req.attempts_dir, raw, RC_MISCONFIGURED)
            return RC_MISCONFIGURED
        return 0

    def _build_prompt(self, req: LLMRequest) -> str:
        """Cold spawn = the full inlined prompt template (the agent never
        needs read access to `Tooling/prompts/`, which sits outside its
        workspace). Retry = the short in-session note, but ONLY when a
        conversation id was captured: without resume the agent would see
        a bare rebuttal with no memory of what it is rebutting, so fall
        back to the full prompt instead of wasting the round."""
        from Tooling.agent import render_prompt_template
        resumable = bool(
            req.is_retry and req.session_id
            and _load_session_map(req.attempts_dir).get(req.session_id))
        if resumable:
            err = (req.retry_context or "(reason not captured)").strip()
            return (
                f"Your previous output was rejected:\n\n```\n{err}\n```\n\n"
                f"Produce a corrected version. The instructions and "
                f"context from this session are unchanged. Write outputs "
                f"into {req.attempts_dir}/."
            )
        try:
            body = req.prompt_path.read_text(encoding="utf-8")
        except OSError as e:
            body = f"(prompt file unavailable: {e})"
        else:
            body = render_prompt_template(
                body, is_postmortem=req.is_postmortem,
                flags=req.prompt_flags)
        ctx = req.attempts_dir / "Context.md"
        context_clause = (f"read context at {ctx} and "
                          if ctx.exists() else "")
        return (
            f"You are running a {req.kind} task. Follow the instructions "
            f"below exactly.\n\nAfter reading them, {context_clause}write "
            f"outputs into {req.attempts_dir}/.\n\n"
            f"=== INSTRUCTIONS ===\n{body}\n=== END INSTRUCTIONS ==="
        )

    def complete_text(self, *, prompt: str,
                      timeout_sec: int = 60) -> "str | None":
        """One-shot completion for short auxiliary calls. Returns the
        response text, or None on any failure."""
        exe = resolve_agy_executable()
        if not exe:
            return None
        cmd = [
            exe, "-p", prompt,
            "--model", _resolve_model(None),
            "--output-format", "json",
            "--print-timeout", f"{max(30, int(timeout_sec))}s",
        ]
        try:
            r = subprocess.run(
                cmd, timeout=timeout_sec + _SUBPROCESS_SLACK_SEC,
                capture_output=True, text=True,
                encoding="utf-8", errors="replace", env=_spawn_env(),
                creationflags=no_window_creationflags(),
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None
        envelope = _parse_envelope(r.stdout or "")
        if envelope is None or str(envelope.get("status")).upper() != "SUCCESS":
            return None
        text = str(envelope.get("response") or "").strip()
        return text or None


def _parse_envelope(stdout: str) -> "dict | None":
    """The json envelope is the LAST json object on stdout — agy prints
    human notes (e.g. the `command`-permission denial) before it."""
    for line in reversed([ln.strip() for ln in stdout.splitlines()]):
        if not line.startswith("{"):
            continue
        try:
            data = json.loads(line)
        except ValueError:
            continue
        if isinstance(data, dict):
            return data
    # Some runs emit the envelope as pretty-printed multi-line json.
    start = stdout.find("{")
    if start >= 0:
        try:
            data = json.loads(stdout[start:])
            if isinstance(data, dict):
                return data
        except ValueError:
            pass
    return None
