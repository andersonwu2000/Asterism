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
         mcp(*)                              the ONLY capability channel
       permissions.deny:
         command(*)                          no shell — see below
         read_url(*)                         no outbound fetch — see below
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

   `command(*)` WAS allowed, from the measurement above: a shell was the
   only way to reach loogle, and "loogle only" is inexpressible here. It
   lasted one day. On 2026-07-30 a Strategist wake spent 32 minutes
   pinned on an agent-authored `python -c` loop scanning to 10**15 — a
   COMPUTE channel, while all the design attention had gone to the write
   channel. Patching per-channel is a losing game (writes yesterday,
   compute today), so the capability moved to MCP instead, where the
   framework owns the command line and the whitelist is a tool list:
   `knowledge/mcp_tools.py`, registered by `ensure_mcp_config`.

   MEASURED for the other two actions (11 + 4 probes, 2026-07-30):
     read_url — allow rules are IGNORED (it fetches with no rule at all,
       and with every scoping form). deny WORKS and is absolute: deny
       `read_url(*)` plus an allow for the exact URL still blocks. So it
       is all-or-nothing, and it is now denied — an ungated outbound
       fetch is a route to a published solution, which for a benchmark
       is a validity problem before it is a security one. (Audited: no
       agy leg ever fetched an external URL.)
     mcp — allow IS enforced headless (no rule → auto-denied, and agy
       says so in the envelope). `mcp(*)` grants it; `mcp(<server>)`
       does not match. Scoping costs nothing here: the server is ours,
       so "every MCP tool" means "every tool we chose to expose".

   The MCP config lives at `~/.gemini/config/mcp_config.json` — from
   agy's own bundled docs (`builtin/skills/agy-customizations/docs/
   mcp_servers.md`), NOT the path the web suggests. A probe written to
   `~/.gemini/antigravity-cli/mcp_config.json` was silently ignored,
   which is indistinguishable from "agy has no MCP support".

   Historical note, kept because the reasoning still applies to any
   future `command` allowance: with `command(*)` a spawn can write
   around the write_file deny rules via a command, so the sandbox is not
   the write fence. Two mitigations were built for that:
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
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from ..core.process_group import no_window_creationflags
from . import capabilities
from .base import LLMRequest, transcript_dest

#: This provider's canonical name in `llm/capabilities.py`, where its
#: gaps (no usage endpoint, no stream events, uninformative rc,
#: deny-only enforcement) are declared for consumers to read.
PROVIDER_NAME = "antigravity"


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

#: This spawn's private HOME, inside its attempts dir — see
#: `_spawn_home`. Under `attempts_dir` so the dispatcher's orphan sweep
#: is already its cleanup.
_SPAWN_HOME_DIRNAME = "_agy_home"

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
#: agy's own `--print-timeout` firing — the envelope this provider is
#: DESIGNED to receive (see `_SUBPROCESS_SLACK_SEC`: we let agy's clock
#: fire first precisely so the death has a classifiable envelope instead
#: of a SIGKILL). Without these markers it fell through to the generic
#: rc=1 → `agent_rc_nonzero`, which skips the retry helper's timeout
#: branch: no postmortem, so the next spawn got no `.drafts/` progress
#: note (2026-08-07, g7415: two 16-minute spawns, ~1M output tokens,
#: nothing handed on). Same attempts semantics as claude's 124 — a spawn
#: that used its whole budget without delivering still burns one.
_TIMEOUT_MARKERS = (
    "timeout waiting for response",
    "deadline_exceeded",
    "context deadline exceeded",
    "request timed out",
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


#: `agy_identity()` verdicts.
IDENTITY_IDE_SESSION = "ide_session"
IDENTITY_LEGACY_FILE = "legacy_file"


def agy_identity() -> "tuple[str, Path | None]":
    """WHICH ACCOUNT will pay for the next agy spawn.

    Not a formatted line, because two callers render it differently:
    `doctor` prints a WARN, the installer draws a decision page. Both
    need the same judgement, and it is a judgement — `agy` resolves
    `~/.gemini/oauth_creds.json` BEFORE the Antigravity IDE session, so
    the mere presence of that file moves the run onto whichever account
    wrote it, with nothing anywhere reporting the switch. That is how a
    long run once came out of the operator's own free tier while the IDE
    was signed in to the Pro account it was supposed to use.

    Returns (verdict, path): `IDENTITY_LEGACY_FILE` with the file that
    is overriding, or `IDENTITY_IDE_SESSION` with None."""
    legacy = legacy_oauth_creds_path()
    if legacy.is_file():
        return IDENTITY_LEGACY_FILE, legacy
    return IDENTITY_IDE_SESSION, None


def _spawn_home(req: LLMRequest) -> "Path | None":
    """Build this spawn's private HOME and return it, or None on failure.

    agy reads its permissions and its MCP servers from files under the
    home directory and from nowhere else: `agy --help` has no config
    flag, and its bundled docs give exactly two scopes, global and
    per-plugin (`builtin/skills/agy-customizations/docs/
    mcp_servers.md`). A global file cannot express a per-spawn envelope —
    with `dispatch.pool` > 1 four concurrent spawns would fight over one
    gateway session token, and the LSP entry that carries
    `mcp__lsp__validate_file` IS per-spawn. So the envelope becomes a
    home directory.

    MEASURED (2026-08-01, two probes): agy authenticates normally under a
    fake HOME — its credentials do not live there — and reaches an MCP
    server configured there. Only two files are needed; the install tree
    (`bin`, `builtin`, `brain`) does NOT have to be copied and agy does
    not re-provision. That is what makes this cheap enough to do per
    spawn.

    The home lives inside `attempts_dir`, so the dispatcher's existing
    orphan-attempts sweep is its cleanup and no new machinery is owed."""
    from .envelope import envelope_for
    env_spec = envelope_for(req)
    home = Path(req.attempts_dir) / _SPAWN_HOME_DIRNAME
    try:
        (home / ".gemini" / "config").mkdir(parents=True, exist_ok=True)
        (home / ".gemini" / "antigravity-cli").mkdir(parents=True,
                                                     exist_ok=True)
        workspace = _workspace_of(req.problem_dir)
        (home / ".gemini" / "antigravity-cli" / "settings.json").write_text(
            json.dumps(_spawn_permissions(env_spec, workspace), indent=2),
            encoding="utf-8")

        servers: dict = {}
        if env_spec.mcp_config_path is not None:
            # The pipeline's per-spawn config: `asterism_tools` plus the
            # `lsp` entry carrying this spawn's gateway session token.
            servers = json.loads(env_spec.mcp_config_path.read_text(
                encoding="utf-8")).get("mcpServers", {})
        elif workspace is not None:
            from ..pipeline import tools_mcp_entry
            servers = {"asterism_tools": tools_mcp_entry(workspace)}
        # Which attempt the tools server is serving. agy's own env
        # allowlist never carried it, and the server is a child agy
        # starts — so it travels in the config, the way this backend
        # already carries everything else per-spawn.
        if env_spec.write_roots:
            from .spawn_guard import ATTEMPT_DIR_ENV
            for entry in servers.values():
                if isinstance(entry, dict) and not entry.get("url"):
                    entry.setdefault("env", {})[ATTEMPT_DIR_ENV] = str(
                        env_spec.write_roots[0])
        (home / ".gemini" / "config" / "mcp_config.json").write_text(
            json.dumps({"mcpServers": servers}, indent=2), encoding="utf-8")
    except (OSError, ValueError) as e:
        print(f"[llm:agy] could not build the spawn's capability envelope "
              f"at {home}: {e}", flush=True)
        return None
    return home


def _spawn_permissions(env_spec, workspace: "Path | None") -> dict:
    """agy's dialect of the envelope: `permissions.allow` / `deny`.

    Same three grants claude gets via flags — read the workspace, write
    only this spawn's roots, reach only our MCP tools — with the two
    channel denies that make the tool list the whole capability surface
    (AUTHORIZED OPERATIONS §3). Deny beats allow in agy, and an unmatched
    action defaults to Ask which headless auto-denies, so listing the
    write roots IS the fence: no `write_file(.attempts)` blanket any
    more, one root per spawn."""
    allow = [f"write_file({p})" for p in env_spec.write_roots]
    allow.append("mcp(*)")
    deny = ["command(*)", "read_url(*)"]
    # `read_file` IS governed by this file, in every direction — RE-
    # MEASURED 2026-08-10 (five probes, agy 1.1.11, each under its own
    # fake HOME; raw envelopes and agy's own permission_manager lines in
    # `_spike/p162/`):
    #   deny read_file(*)                          → denied, and agy says
    #       "Matches user-configured deny rule"
    #   allow read_file(<ws>) + deny read_file(<d>) → <d> denied, a file
    #       elsewhere in <ws> read: a scalpel, not a switch
    #   allow read_file(<d>) only                  → a file outside <d>
    #       DENIED (agy log: "user denied permission for read_file")
    #   NO read_file rule at all                   → DENIED, same line
    # So reads are default-deny and the allow is a whitelist. The earlier
    # series (same day) concluded the exact opposite in all three
    # directions and the rule below was removed as "decorative"; that
    # removal was not behaviour-neutral, it silently BLINDED every agy
    # spawn — the denial never reaches the model (status stays SUCCESS,
    # the response is empty), so it would have surfaced as a formalizer
    # that read nothing and did nothing. The wrong conclusion survived
    # because a silent auto-deny and an ungated read look identical from
    # the outside; only agy's own log tells them apart.
    if workspace is not None:
        allow.append(f"read_file({workspace})")
    # Named grants that do NOT come with a workspace. The Adversary is
    # the case: its `problem_dir` is its projection, so `workspace` is
    # None above and this is its ONLY read. Without it agy soft-denies
    # `list_dir` on the proofs directory and ends the turn — see
    # `Envelope.read_allow_roots` for the incident.
    allow += [f"read_file({p})" for p in env_spec.read_allow_roots]
    # …and the operator-private subtrees carved back out of it (#162,
    # user ruling 2026-08-10). The list is provider-independent and lives
    # in `envelope.py`, because the same exposure was never agy-specific:
    # `spawn_guard._whitelist()` returns the whole repo root, so a claude
    # spawn read `docs/internal/` and the live DB just as freely.
    # Order does not matter — deny beats allow globally on agy (probe G).
    deny += [f"read_file({p})" for p in env_spec.read_deny_roots]
    return {"permissions": {"allow": allow, "deny": deny},
            "trustedWorkspaces": ([str(workspace)] if workspace else [])}


def _spawn_env(home: "Path | None" = None) -> "dict[str, str]":
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
    from .envelope import spawn_env
    # PATH first (see `spawn_env`): agy runs every command through
    # powershell, so a bare `python` here has the same PATH exposure the
    # claude spawns do.
    env = spawn_env()
    env["PYTHONPATH"] = (
        str(repo) + os.pathsep + env["PYTHONPATH"]
        if env.get("PYTHONPATH") else str(repo))
    if home is not None:
        # All four, because Go's os.UserHomeDir reads USERPROFILE on
        # Windows while other consumers read HOME.
        env["HOME"] = str(home)
        env["USERPROFILE"] = str(home)
        env["HOMEDRIVE"] = home.drive
        env["HOMEPATH"] = str(home)[len(home.drive):]
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
    agy reports it directly — no stream parsing needed.

    PER CALL, NOT PER CONVERSATION — checked rather than assumed when
    codex turned out to be the other way (DELTA 10 there). agy resumes a
    conversation id just as codex resumes a thread, so the question is
    the same one; the answer is different. Measured over the 95 recorded
    agy pipelines carrying more than one spawn: 62 have a LATER row with
    fewer output tokens than an earlier one, which a running total
    cannot do. So these figures are increments and `spawn_usage` may sum
    them, with no baseline to subtract."""
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


def _agent_artifact_present(attempts_dir: Path,
                            planted: "frozenset[str] | None" = None) -> bool:
    """Did the AGENT leave anything? See "THE HAZARD" in the module
    docstring: a silently-denied write returns SUCCESS, so the on-disk
    check is the only honest signal. `.json` counts — the old gemini
    provider's check listed only .lean/.md, which would have marked
    every successful Adversary run (verdict.json) as no-output.

    `planted` is the directory's contents BEFORE the spawn, and it is
    what makes the answer mean what it says. Without it this counted
    any `.md`/`.json` in the dir — and the Adversary's dir is its
    projection, which the framework itself fills with `proposal.md`,
    `Context.md`, `contract.md` and the rest before the judge starts.
    So the answer was YES for a judge that had written nothing, which
    turned OFF the one detector built for this exact case
    (`RC_MISCONFIGURED`: "a tool was almost certainly auto-denied…
    retrying will not help"). Measured 2026-08-15: a deterministic
    permission failure was laundered into retryable `agent_no_output`
    and re-run twelve times."""
    if not attempts_dir.is_dir():
        return False
    planted = planted if planted is not None else frozenset()
    for p in attempts_dir.iterdir():
        if p.name in _NON_ARTIFACTS or p.name in planted:
            continue
        if p.is_dir():
            continue
        if p.suffix in (".lean", ".md", ".json", ".txt"):
            return True
    return False


def _dir_snapshot(attempts_dir: Path) -> "frozenset[str]":
    """What was already in the spawn's dir before it ran."""
    try:
        return frozenset(p.name for p in attempts_dir.iterdir())
    except OSError:
        return frozenset()


#: agy's own wording for a refused action, in its own log. The refusal
#: never reaches the model and never reaches the envelope, so this file
#: is the only witness — see `Envelope.read_allow_roots`.
_DENIAL_MARKERS = ("permission check failed for ", "soft-denying tool ")


def _denied_actions(home: Path, limit: int = 4) -> "list[str]":
    """What agy refused this spawn, in agy's words.

    The framework used to report a denied spawn as "left no usable
    artifact" and stop there, and the sentence that named the actual
    path lived only inside a directory about to be deleted. Diagnosing
    one instance on 2026-08-15 took the whole evening; the line was
    always there."""
    out: "list[str]" = []
    try:
        logs = sorted((home / ".gemini" / "antigravity-cli" / "log")
                      .glob("*.log"))
    except OSError:
        return out
    for log in logs:
        try:
            text = log.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            if any(m in line for m in _DENIAL_MARKERS):
                # Drop the vendor's log preamble; keep the sentence.
                out.append(line.split("] ", 1)[-1].strip()[:200])
                if len(out) >= limit:
                    return out
    return out


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
        _record_quota_reset(text)
        return RC_QUOTA_EXHAUSTED
    if any(m in text for m in _TIMEOUT_MARKERS):
        return RC_TIMEOUT
    return rc if rc != 0 else 1


#: Epoch when agy said its quota comes back, or None. agy has no usage
#: API, but its refusal carries the answer in prose — "Individual quota
#: reached ... Resets in 2h46m25s" — and the framework used to drop it,
#: then retry on a 2-4 minute exponential backoff for the whole ~3-hour
#: window (5 wasted spawns in the first 20 minutes, 2026-08-07). Read by
#: the dispatcher when it records the block.
_last_quota_reset: "float | None" = None

_RESET_RE = re.compile(
    r"resets?\s+in\s+(?:(\d+)\s*h)?\s*(?:(\d+)\s*m)?\s*(?:(\d+)\s*s)?", re.I)


def _record_quota_reset(text: str) -> None:
    m = _RESET_RE.search(text)
    if not m or not any(m.groups()):
        return
    h, mi, s = (int(g) if g else 0 for g in m.groups())
    secs = h * 3600 + mi * 60 + s
    if secs <= 0:
        return
    global _last_quota_reset
    _last_quota_reset = time.time() + secs


def take_quota_reset() -> "float | None":
    """The reset epoch from the most recent refusal, consumed once."""
    global _last_quota_reset
    v, _last_quota_reset = _last_quota_reset, None
    return v


def mcp_config_path() -> Path:
    """Where agy reads MCP servers from — its OWN bundled docs
    (`builtin/skills/agy-customizations/docs/mcp_servers.md`), not the
    path the web suggests. The first probe wrote
    `~/.gemini/antigravity-cli/mcp_config.json` and agy silently ignored
    it, which looks exactly like "no MCP support"."""
    return Path.home() / ".gemini" / "config" / "mcp_config.json"


def ensure_mcp_config(problem_dir: "Path | None") -> None:
    """Keep the framework's tool server registered for agy.

    agy resolves MCP servers globally, so unlike claude (a config per
    spawn) there is nowhere to put a per-run entry — the provider
    refreshes the global file instead of leaving it to an operator step
    that would rot the first time the workspace path changed. Other
    servers in the file are left alone; only our key is written, and only
    when it differs.

    MEASURED (2026-07-30, four probes): the `mcp` permission IS enforced
    headless — with no allow rule the call is auto-denied, agy saying so
    in the envelope — and `mcp(*)` grants it. Per-server scoping
    (`mcp(asterism_probe)`) does NOT match, which costs nothing: the
    server is ours, so "every MCP tool" already means "every tool we
    chose to expose"."""
    if problem_dir is None:
        return
    try:
        from ..pipeline import tools_mcp_entry
        workspace = _workspace_of(problem_dir)
        if workspace is None:
            return
        want = tools_mcp_entry(workspace)
        path = mcp_config_path()
        cfg: dict = {}
        if path.exists():
            try:
                cfg = json.loads(path.read_text(encoding="utf-8") or "{}")
            except ValueError:
                cfg = {}
        servers = cfg.setdefault("mcpServers", {})
        if servers.get("asterism_tools") == want:
            return
        servers["asterism_tools"] = want
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        print(f"[llm:agy] registered asterism_tools in {path}", flush=True)
    except Exception as e:  # noqa: BLE001 — never fail a spawn over config
        print(f"[llm:agy] could not refresh MCP config: {e}", flush=True)


def _workspace_of(problem_dir: Path) -> "Path | None":
    """`<workspace>/Problems/<name…>` → `<workspace>`."""
    for parent in problem_dir.parents:
        if parent.name == "Problems":
            return parent.parent
    return None


#: Where an agy spawn's conversation goes to survive its home. Mirrors
#: `codex_cli._TRANSCRIPT_DIRNAME` because the cause is identical: the
#: home IS the capability envelope, so it must be per-spawn, and
#: `.attempts/<pid>/` is rmtree'd by `WorkArea.__exit__`.
#:
#: WHAT THIS COST, measured 2026-08-15. Asked why the agy formalizer
#: burned 74x the fresh input of the claude one, the answer was in agy's
#: own per-turn store and the store was gone: of 214 surviving
#: conversations, 122 are adversary and 43 strategist and NONE is a
#: formalizer — every one of them predates the per-spawn home (v.
#: 2026-08-02). The four expensive spawns were 08-07 and 08-10.
#:
#: The codex note next door said agy keeps its transcripts "in the CLI's
#: OWN home, outside the framework's scratch". That was true before
#: 08-02 and false after, and believing it is why codex got this fix in
#: this same session while agy did not.
_TRANSCRIPT_DIRNAME = "agy_sessions"




def _preserve_transcript(req: LLMRequest, home: Path) -> None:
    """Copy this spawn's conversation out of the doomed home; leave
    everything else in it to die.

    COPY THE -wal AND THE -shm, not just the `.db`. agy writes in WAL
    mode and the tail of the conversation can sit entirely in the
    sidecar: a `.db` lifted on its own opens as `database disk image is
    malformed` — measured while trying to read the surviving stores an
    hour before this was written, on the first file opened.

    Per artifact, never all-or-nothing: one unreadable conversation must
    not take the others down with it (`codex_cli._preserve_transcript`,
    same paragraph, learned the same way).

    The home still dies. It carries the spawn's permission surface and
    its gateway session token, and neither should outlive the attempt.
    Transcript survives, envelope does not."""
    cli_home = home / ".gemini" / "antigravity-cli"
    src = cli_home / "conversations"
    try:
        dbs = sorted(src.glob("*.db"))
        # agy's OWN per-turn log, and the one a human can actually read:
        # `brain/<id>/.system_generated/logs/transcript_full.jsonl` is one
        # JSON object per step with `source`, `type`, `content`,
        # `thinking` and `tool_calls`. The `.db` beside it holds the same
        # turns as protobuf blobs. Both travel: the db is what agy
        # resumes from, the jsonl is what the investigation reads —
        # 2026-08-15, the tool-discovery finding came out of the jsonl in
        # minutes after an hour of decoding the db got nowhere.
        logs = sorted((cli_home / "brain").rglob(
            ".system_generated/logs/*.jsonl"))
        # agy's OWN runtime log, and the only place a permission DECISION
        # is written down. The surface it dumps at startup —
        #   Allow:[write_file(<attempts>) mcp(*) read_file(<workspace>)]
        #   Deny:[command(*) read_url(*) …]  Permission=request-review
        # — is why a spawn can end mid-thought with no error and no
        # artifact: the default for an unmatched action is REVIEW, and
        # `-p` has nobody to review it. Measured 2026-08-15, an Adversary
        # died on its first call outside the projection and the framework
        # could only say `agent_no_output`. Carries no secret: the one
        # credential line is `keyringAuth: loaded token, expiry=…`, the
        # fact and the expiry, never the value.
        logs += sorted((cli_home / "log").glob("*.log"))
        if not dbs and not logs:
            return
        dest = transcript_dest(req.attempts_dir, _TRANSCRIPT_DIRNAME)
        if dest is None:
            print(f"[llm:agy] no .attempts ancestor for "
                  f"{req.attempts_dir} — transcript not preserved",
                  flush=True)
            return
        dest.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"[llm:agy] could not preserve the transcript: {exc}",
              flush=True)
        return
    saved: "list[str]" = []
    for db in dbs:
        for suffix in (".db", ".db-wal", ".db-shm"):
            part = db.with_suffix(suffix)
            if not part.is_file():
                continue
            try:
                shutil.copyfile(part, dest / part.name)
            except OSError as exc:
                print(f"[llm:agy] {part.name} not preserved: {exc}",
                      flush=True)
        saved.append(db.stem[:8])
    # Name the brain logs by conversation, not by their shared
    # basename: every brain dir calls its log `transcript_full.jsonl`,
    # so a flat copy would keep exactly one of however many turns the
    # spawn had. The runtime log already carries a timestamp and needs
    # no prefix.
    for log in logs:
        brain = log.suffix == ".jsonl"
        conv = log.parent.parent.parent.name[:8] if brain else ""
        try:
            shutil.copyfile(log, dest / (f"{conv}_{log.name}" if conv
                                         else log.name))
        except OSError as exc:
            print(f"[llm:agy] {log.name} not preserved: {exc}", flush=True)
    if saved or logs:
        print(f"[llm:agy] transcript preserved → {dest} "
              f"({', '.join(saved) or 'logs only'})", flush=True)


class AntigravityCliProvider:
    def spawn(self, req: LLMRequest) -> int:
        """Preservation is the outer `finally` of every exit path.

        The home is built inside the spawn and torn down with the
        attempts dir, so this cannot sit at either end alone — and the
        paths that most need a transcript are the ones that return
        early: the timeout, and the spawn killed mid-thought."""
        home_box: "list[Path]" = []
        try:
            return self._spawn_inner(req, home_box)
        finally:
            if home_box:
                _preserve_transcript(req, home_box[0])

    def _spawn_inner(self, req: LLMRequest,
                     home_box: "list[Path]") -> int:
        exe = resolve_agy_executable()
        if not exe:
            print("[llm:agy] agy CLI not found "
                  "(install: irm https://antigravity.google/cli/"
                  "install.ps1 | iex)", flush=True)
            return RC_MISSING_CLI

        model = _resolve_model(req.kind)
        ensure_mcp_config(req.problem_dir)
        home = _spawn_home(req)
        if home is None:
            # Loud, not silent. The 07-30 lesson: a config agy never
            # reads looks exactly like a provider with no MCP support,
            # and a spawn that runs without `mcp__lsp__validate_file`
            # cannot type-check a single line it writes.
            _write_spawn_stderr(req.attempts_dir,
                                "capability envelope could not be built",
                                RC_MISCONFIGURED)
            return RC_MISCONFIGURED
        home_box.append(home)
        # Before the agent runs, so "did it leave anything" can mean it.
        planted = _dir_snapshot(req.attempts_dir)
        prompt = self._build_prompt(req)
        # THE DEGRADATION, wired rather than merely declared. agy emits
        # ONE json envelope when it is finished and nothing before it,
        # so `capabilities.liveness_clock` returns TIMEOUT_ONLY: there
        # is no stream to sample, hence no StreamParser, hence no
        # watchdog, hence no silence threshold and no thinking-trap
        # detection. The entire liveness guarantee for an agy spawn is
        # that agy's own `--print-timeout` fires FIRST (the subprocess
        # wall is deliberately `_SUBPROCESS_SLACK_SEC` longer, so the
        # death arrives as a classifiable envelope instead of a
        # SIGKILL). That is why the timeout must be driven from
        # `req.timeout_sec` and never left at agy's 5-minute default,
        # and why `_TIMEOUT_MARKERS` has to recognise the envelope: on
        # this provider a missed timeout classification is not a
        # cosmetic mislabel, it is the only liveness signal being
        # dropped (g7415, 2026-08-07 — two 16-minute spawns, ~1M output
        # tokens, no postmortem, nothing handed on).
        liveness = capabilities.liveness_clock(PROVIDER_NAME, req.kind)
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
                # Never inherit stdin — see `claude_cli`'s note: a spawn
                # launched from inside the MCP tools server would block
                # on that server's JSON-RPC pipe.
                stdin=subprocess.DEVNULL,
                capture_output=True, text=True,
                encoding="utf-8", errors="replace",
                cwd=str(req.problem_dir), env=_spawn_env(home),
                creationflags=no_window_creationflags(),
            )
        except subprocess.TimeoutExpired:
            # agy's own clock did NOT fire first — the one thing this
            # provider's liveness design depends on. Name the degraded
            # clock in the forensic record: with `liveness=timeout`
            # there is no parser state to consult afterwards, so "the
            # wall ran out" is genuinely all anyone can say, and a
            # reader must not go looking for a detector verdict that
            # was never produced.
            note = (f"(subprocess.TimeoutExpired after {print_timeout}s; "
                    f"liveness={liveness} — this provider emits no stream, "
                    f"so the wall clock was the only signal)")
            print(f"[llm:agy] timed out after {print_timeout}s "
                  f"[liveness={liveness}]", flush=True)
            _write_spawn_stderr(req.attempts_dir, note, RC_TIMEOUT)
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
        # ERROR is not proof either — the converse of THE HAZARD, and the
        # live acceptance run found it: the model called `loogle` with the
        # wrong argument name, MCP raised, the model corrected itself and
        # answered — and agy still stamped the envelope ERROR and exited
        # 1. Failing there would discard a wake whose work is done, the
        # same class of loss as the 07-30 tripwire replacing an honest
        # spawn's rc. The artifact decides; a recovered tool error does
        # not.
        recovered = (status.upper() != "SUCCESS"
                     and str((envelope or {}).get("response") or "").strip()
                     and _agent_artifact_present(req.attempts_dir,
                                                planted))
        if recovered:
            print(f"[llm:agy] {req.kind}: status={status} but the agent "
                  f"recovered and left its artifact — "
                  f"{str((envelope or {}).get('error') or '')[:200]}",
                  flush=True)
        if not recovered and (r.returncode != 0
                              or status.upper() != "SUCCESS"):
            code = _classify(envelope, raw, r.returncode)
            detail = str((envelope or {}).get("error") or "")[:400]
            print(f"[llm:agy] {req.kind}: status={status or '?'} "
                  f"rc={r.returncode} → {code}"
                  + (f": {detail}" if detail else ""), flush=True)
            _write_spawn_stderr(req.attempts_dir, raw, code)
            return code

        # SUCCESS is not proof — see THE HAZARD.
        if not _agent_artifact_present(req.attempts_dir, planted):
            try:
                left = sorted(p.name for p in req.attempts_dir.iterdir())
            except OSError:
                left = []
            denials = _denied_actions(home)
            print(f"[llm:agy] {req.kind}: status=SUCCESS but the agent "
                  f"left no usable artifact in {req.attempts_dir} "
                  f"(files: {', '.join(left) or 'none'}) — "
                  + (f"agy denied: {'; '.join(denials)}" if denials else
                     "a tool was almost certainly auto-denied (no "
                     "matching permissions.allow rule)")
                  + ". Retrying will not help; the envelope is wrong, "
                    "not the agent.", flush=True)
            _write_spawn_stderr(
                req.attempts_dir,
                raw + ("\n\n[permission denials from agy's own log]\n"
                       + "\n".join(denials) if denials else ""),
                RC_MISCONFIGURED)
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
