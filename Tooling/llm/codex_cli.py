"""Codex CLI provider — `codex exec`, headless.

Behaviour is aligned to `claude_cli` wherever codex allows it, because
claude is the backend with the most production hours and every deviation
is a place where a failure looks different from the one the framework
already knows how to read. Ten deviations were forced by the CLI, and
each is marked DELTA below and in the code:

  DELTA 1  NO READ TOOL AT ALL. With `shell_tool` and `apps` off (see
           `_render_config`) codex has no file-reading tool — measured
           2026-08-12: asked to read a file it answers "NO-READ-TOOL".
           Everything it learns about the workspace comes through our
           MCP (`inspect`). A claude worker has Read/Grep/Glob; a codex
           worker does not, and its prompt must not assume otherwise.
  DELTA 2  THE SESSION ID IS ITS, NOT OURS. claude pins a caller-minted
           uuid (`--session-id`) and replays it (`--resume`). codex only
           offers `codex exec resume <id>` on an id IT mints, so resume
           is the agy two-step: capture `thread.started` on the cold
           call, replay it on the retry. Same `_SESSION_MAP` shape agy
           uses, for the same reason.
  DELTA 3  PROMPT ON STDIN. claude passes `-p <prompt>` and pays the
           Windows 32,767-char command-line cap (`PromptTooLarge`).
           codex reads the prompt from stdin, so that cap does not
           apply here. The guard is not copied — there is nothing to
           guard against.
  DELTA 4  NO TEXT DELTAS. The documented event vocabulary is
           thread.started / turn.started / turn.completed / turn.failed
           / item.{started,updated,completed} / error; agent text
           arrives whole inside `item.completed`. `StreamParser` has a
           `codex` dialect for it, so the TOOL cadence clock and the
           token accounting are real — but the stream-idle clock the NL
           layer needs cannot be built from these events at all, which
           is why `capabilities` says an NL seat on codex is
           timeout-only rather than quietly reusing the tool clock.
  DELTA 5  QUOTA IS A THIRD SHAPE. Not an endpoint (claude) and not a
           refusal message (agy): codex writes `rate_limits` into its
           OWN rollout file, once per turn. Since CODEX_HOME is
           per-spawn, that file is this spawn's private ledger.
  DELTA 6  THE RC LIES IN BOTH DIRECTIONS. No vendor documentation
           lists exit codes, so they were measured: a bad config key
           and a missing credential both exit 1, and a hard API refusal
           (400, "model is not supported when using Codex with a
           ChatGPT account") exits ZERO. So the outcome is read off the
           event stream — `turn.failed` / `error` — and the rc only
           afterwards. `capabilities` declares RC_UNINFORMATIVE.
  DELTA 7  THE ENVELOPE IS A FILE TREE, NOT FLAGS. Like agy — but codex
           names the directory itself (`CODEX_HOME`), so no HOME
           impersonation is needed. MEASURED 2026-08-12: a CODEX_HOME
           under the system temp dir makes codex refuse to create its
           helper binaries, so this one lives in `attempts_dir`.
  DELTA 8  WRITE ROOTS NEED AN EXPLICIT GRANT. `.attempts/<pid>/` sits
           at the WORKSPACE root, not under `problem_dir`, so
           `--sandbox workspace-write` alone would not reach the one
           directory the agent must write. `--add-dir` carries it.
  DELTA 9  A DEAD MCP SERVER CAN FAIL THE SPAWN. `required = true` makes
           `codex exec` exit rather than run a worker with no tools —
           the loud failure the framework prefers over a silent one.
           claude has no equivalent.
  DELTA 10 USAGE IS THE SESSION'S, NOT THE CALL'S — twice over. Its
           `input_tokens` INCLUDES `cached_input_tokens` where claude's
           excludes them, and the figures are the whole conversation's
           running totals, re-reported in full by every `codex exec
           resume`. `spawn_usage` sums the rows it is handed and reads
           `input_tokens` as the fresh part, so both had to be undone
           at the source: the parser subtracts the cached share, and a
           per-thread ledger (`_USAGE_LEDGER`, beside `_SESSION_MAP`)
           carries each conversation's running totals so a resumed
           spawn is billed only for its own turns. Measured 2026-08-15
           on Test.provider_probe: 2.0x over-count per pipeline, and a
           cache-hit rate of 49% where the truth was 97%.

What is NOT a delta, and is load-bearing because of it: the prompt is
built by `claude_cli`'s own two helpers. They compose the template plus
"write outputs into <attempts_dir>" and reference nothing claude-
specific; importing them rather than forking a second copy is what keeps
the two backends from drifting apart one wording change at a time.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path

from .base import (LLMRequest, SpawnRC, transcript_dest,
                   which_launchable)
from ..core.process_group import (assign_to_job, create_capped_job,
                                  no_window_creationflags)

PROVIDER_NAME = "codex"

#: Fast and affordable agentic coding model, 272k context (95% usable).
#: Overridden per seat by `<kind>.model` in Asterism.yaml.
DEFAULT_MODEL = "gpt-5.6-luna"
#: `low | medium | high | xhigh | max` for the 5.6 family. The default
#: sits high because a formalizer's failure mode is giving up on a proof,
#: not spending too long on one.
DEFAULT_REASONING_EFFORT = "xhigh"

#: `attempts_dir/<this>` — this spawn's private CODEX_HOME (DELTA 7).
_SPAWN_HOME_DIRNAME = "_codex_home"
#: framework session id → codex thread id (DELTA 2).
_SESSION_MAP = "_codex_sessions.json"

#: Substring tables. UNVALIDATED — no usage-limit refusal has been
#: observed, so these are guesses. The quota signal actually trusted is
#: `rate_limits.rate_limit_reached_type` from the rollout, not prose;
#: these only catch a refusal that never reaches the rollout. When one
#: fires for real, replace the guess with the verbatim message and say
#: which version produced it.
_QUOTA_MARKERS = (
    "usage limit", "rate limit", "quota", "you've hit your",
    "resets at", "too many requests",
)
_MISCONFIG_MARKERS = (
    "not logged in", "no codex credentials", "authentication",
    "unknown configuration field", "unknown variant",
    "invalid type:", "error loading config.toml",
)


def resolve_codex_executable() -> "str | None":
    """The launchable path, not the bare name.

    codex is npm-installed, so PATH carries `codex` (a shell script) and
    `codex.cmd`, and `shutil.which` hands back the former — which Popen
    cannot execute. This cost the provider's first live spawn on
    2026-08-12: `[WinError 193]`, surfaced as a worker exception. Hence
    an argv[0] that is a resolved path rather than a name, unlike claude
    (whose own resolver exists but is deliberately not on its hot path)."""
    return which_launchable("codex")


def _resolve_model(kind: "str | None") -> str:
    from ..core import config
    if not kind:
        return DEFAULT_MODEL
    return str(config.get(f"{kind}.model",
                          env_var=f"ASTERISM_{kind.upper()}_MODEL",
                          default=DEFAULT_MODEL))


def _resolve_effort(kind: "str | None") -> str:
    from ..core import config
    if not kind:
        return DEFAULT_REASONING_EFFORT
    return str(config.get(f"{kind}.reasoning_effort",
                          env_var=f"ASTERISM_{kind.upper()}_REASONING_EFFORT",
                          default=DEFAULT_REASONING_EFFORT))


def operator_codex_home() -> Path:
    """Where the human's `codex login` left its credential."""
    env = os.environ.get("CODEX_HOME")
    return Path(env) if env else Path.home() / ".codex"


def _toml_str(value: str) -> str:
    """A TOML *literal* string. Windows paths are full of backslashes and
    a basic (double-quoted) string treats them as escapes — measured
    2026-08-12, `config.toml:8:14: too few unicode value digits`. Literal
    strings have no escapes at all, so the only thing that can break one
    is a single quote, which no path of ours carries."""
    if "'" in value:
        raise ValueError(f"cannot express {value!r} as a TOML literal string")
    return f"'{value}'"


def _mcp_servers_toml(mcp_config_path: "Path | None",
                      attempts_dir: "Path | None" = None) -> str:
    """Translate the framework's `mcpServers` JSON into codex's TOML.

    Two shapes exist on our side (`pipeline.tools_mcp_entry` and the
    gateway's http entry) and codex expresses both. Two settings are
    attached to every server, and neither is cosmetic:

      `default_tools_approval_mode = "approve"` — WITHOUT it every MCP
      call comes back `user cancelled MCP tool call`, because headless
      `exec` has no reviewer and an approval request auto-cancels.
      MEASURED 2026-08-12: `auto` does NOT do this, `approve` does. The
      tool appears in the model's list either way, so the failure is not
      "no tools", it is "every tool refused" — which reads like a model
      that would not act.

      `required = true` — a server that cannot start fails the spawn
      instead of producing a worker with no tools (DELTA 9).
    """
    if mcp_config_path is None:
        return ""
    servers = json.loads(
        mcp_config_path.read_text(encoding="utf-8")).get("mcpServers", {})
    out: "list[str]" = []
    for name, entry in servers.items():
        out.append(f"\n[mcp_servers.{name}]")
        if entry.get("url"):
            out.append(f"url = {_toml_str(str(entry['url']))}")
        else:
            out.append(f"command = {_toml_str(str(entry.get('command', '')))}")
            args = entry.get("args") or []
            out.append("args = ["
                       + ", ".join(_toml_str(str(a)) for a in args) + "]")
        out.append('default_tools_approval_mode = "approve"')
        out.append("required = true")
        env = dict(entry.get("env") or {})
        if name == "asterism_tools":
            # codex's exec channel caps model-visible tool output at
            # ~10K tokens and amputates the middle of anything larger,
            # so `inspect` must defer whole queries at the source. The
            # number is the capability declaration's, not this file's;
            # the config env is the one route VERIFIED to reach the
            # server process (the JSON writers run before the provider
            # is known, so the adapter injects it at render time).
            from .capabilities import inspect_delivery_chars
            cap = inspect_delivery_chars("codex")
            if cap is not None:
                env["ASTERISM_INSPECT_DELIVERY_CHARS"] = str(cap)
            # Same route, same reason: which attempt `inspect` is
            # serving. The spawn's own env carries it too, but codex
            # gives its MCP children a fixed core set — measured
            # 2026-08-16 as 19-21 variables, none of them ours — so a
            # tool that read only the spawn env resolved bare
            # `Context.md` against nothing on every codex seat.
            if attempts_dir is not None:
                from .spawn_guard import ATTEMPT_DIR_ENV
                env[ATTEMPT_DIR_ENV] = str(attempts_dir)
        if env:
            out.append(f"\n[mcp_servers.{name}.env]")
            for k, v in env.items():
                out.append(f"{k} = {_toml_str(str(v))}")
        if entry.get("headers"):
            out.append(f"\n[mcp_servers.{name}.http_headers]")
            for k, v in entry["headers"].items():
                out.append(f"{_toml_str(k)} = {_toml_str(str(v))}")
    return "\n".join(out) + "\n"


def _render_config(req: LLMRequest, model: str, effort: str,
                   flavor: str = "openai") -> str:
    """codex's dialect of the capability envelope.

    The same three grants claude gets from flags. The tool half is the
    part that needed measuring, because the obvious knob is the wrong
    one: `[tools]` carries exactly ONE field (`web_search`) and cannot
    remove the shell. The switches that work are FEATURE FLAGS, and
    turning the two big ones off is what makes a codex worker a worker
    rather than a general assistant (all measured 2026-08-12, by asking
    the model to list its tools and corroborating with behaviour):

      `shell_tool = false`  removes `shell_command` — the capability the
                            framework closed on 2026-08-11 (#181).
      `apps = false`        removes the ChatGPT account's CONNECTORS.
                            Left on, a worker holds `gmail_send_email`,
                            `gmail_delete_emails`, calendar writes, site
                            deploys and `plugin_management_uninstall_app`.
                            Also 25k of tool schema on EVERY turn: the
                            same trivial task cost 63k input with apps on
                            and 38.6k with them off.
      `[agents] enabled = false`
                            removes `multi_agent_v1__*`, i.e. the ability
                            to spawn sub-agents and spend quota outside
                            the framework's ledger. `--disable multi_agent`
                            does NOT do this; only the `[agents]` block.

    What survives and cannot be removed locally: `web__run`. `[tools]
    web_search = false` is inert — with it set the model still ran a real
    search (measured). Recorded rather than papered over; whether a
    formalizer should have live web access is a policy question for the
    operator, not something this renderer can decide.
    """
    from .envelope import envelope_for
    spec = envelope_for(req)
    lines = [
        "# Rendered per spawn by Tooling/llm/codex_cli.py — do not edit.",
        f"model = {_toml_str(model)}",
        f'model_reasoning_effort = "{effort}"',
        # No human is attached; an approval request would auto-cancel.
        'approval_policy = "never"',
        # The agent must write patch.lean / PROPOSAL.md / decision.json.
        'sandbox_mode = "workspace-write"',
        # TOML: top-level keys MUST precede the first [table] header —
        # appended after [windows] they silently become [windows].* keys
        # and codex ignores them (measured 2026-08-22: the first zen
        # fleet spawn went to api.openai.com with no bearer).
        *([
            'web_search = "disabled"',
            'model_provider = "zen"',
        ] if flavor == "zen" else []),
        "",
        "[features]",
        "shell_tool = false",
        "apps = false",
        "image_generation = false",
        "view_image = false",
        "browser_use = false",
        "computer_use = false",
        "in_app_browser = false",
        "goals = false",
        "plugins = false",
        "skill_search = false",
        "tool_suggest = false",
        "memories = false",
        "",
        "[agents]",
        "enabled = false",
        "",
        # WITHOUT THIS, EVERY WRITE IS REFUSED ON WINDOWS. Measured
        # 2026-08-13 with three probes on the same workspace, one
        # variable each:
        #   --sandbox workspace-write, cwd untrusted   → "patch
        #       rejected: writing is blocked by read-only sandbox"
        #   …+ [projects.<cwd>] trust_level="trusted"  → identical
        #       refusal (so trust is NOT the gate — that hypothesis was
        #       measured and killed before it shipped)
        #   …+ this line                               → file written
        # In all three the session recorded `sandbox_policy: read-only`
        # until this was set: the command-line flag alone cannot turn
        # the Windows sandbox on. The operator's own `~/.codex` has
        # carried this line since June, which is exactly why nothing
        # looked wrong in the TUI while every spawn wrote nothing.
        # What it cost before it was found: the intake sentinel and the
        # feedback record, both of which are files the agent must write
        # ITSELF — the work turn survived only because its writes go
        # through the gateway MCP, server-side.
        "[windows]",
        'sandbox = "unelevated"',
    ]
    if flavor == "zen":
        # OpenCode Zen (free ox-alpha window, 2026-08-21): route through
        # the local translation shim — Zen's /responses stream is
        # nonconformant and its upstream 500s on codex's hard-injected
        # `web_search` tool type; the shim fixes both and adds the
        # per-request nonce that defuses Zen's poisonable prefix cache.
        # Start the shim first: `python -m Tooling.llm.zen_shim`.
        from ..core import config as _config
        base = _config.get("zen.base_url",
                           env_var="ASTERISM_ZEN_BASE_URL",
                           default="http://127.0.0.1:8898/v1")
        # This spawn's attempts dir travels IN THE URL PATH
        # (`/a/<uuid>/v1`): the shim used to recover it by regexing the
        # request text, and codex only carries those paths on SOME
        # turns — write_file flickered between working and "no attempts
        # directory" inside one session (2026-08-22). The per-spawn
        # config is already unique to this spawn; the URL is the one
        # deterministic in-band channel the shim always sees.
        base = str(base).rstrip("/")
        if req.attempts_dir is not None and base.endswith("/v1"):
            base = (base[: -len("/v1")]
                    + f"/a/{Path(req.attempts_dir).name}/v1")
        lines += [
            "",
            "[model_providers.zen]",
            'name = "OpenCode Zen"',
            f'base_url = {_toml_str(str(base))}',
            'env_key = "OPENCODE_ZEN_API_KEY"',
            'wire_api = "responses"',
        ]
    # THE WRITABLE ROOTS BELONG IN THE CONFIG, not only on the command
    # line. `codex exec resume` accepts no `--add-dir` (nor `-C`, nor
    # `--sandbox`): a resumed turn inherits what the SESSION recorded,
    # and the session only ever knew the cwd. Measured 2026-08-13 — the
    # feedback turn, which resumes, reported "the current sandbox
    # permits writes only inside <problem_dir>, and no Write tool is
    # available" and left no record. The work turn never noticed because
    # its writes go through the gateway MCP, server-side. Config is read
    # on EVERY invocation of this per-spawn home, so putting the roots
    # here covers the cold line and the resume with one statement.
    if spec.write_roots:
        lines += ["", "[sandbox_workspace_write]",
                  "writable_roots = ["
                  + ", ".join(_toml_str(str(p)) for p in spec.write_roots)
                  + "]"]

    # `spec.read_allow_roots` is DECLARED NOT APPLICABLE here, not
    # dropped. Per DELTA 1 codex has no file-reading tool at all with
    # `shell_tool` and `apps` off, so there is no read to widen: every
    # byte it learns arrives through our MCP, whose scope the framework
    # sets. Saying so in code is the point — the same field was silently
    # ignored by agy, where reads DO exist and an ungranted one is
    # soft-denied mid-turn (2026-08-15, twelve wakes). If codex ever
    # regains a read tool, this is the line that has to change with it.
    _ = spec.read_allow_roots

    # Project trust. Kept because the operator's own config carries it
    # and it costs nothing — but NOT the thing that makes writing work:
    # a probe with the cwd trusted was refused identically to one
    # without (2026-08-13). Recorded so the next reader does not repeat
    # the guess this comment used to assert.
    for root in spec.write_roots:
        lines += ["", f"[projects.{_toml_str(str(root))}]",
                  'trust_level = "trusted"']
    return "\n".join(lines) + "\n" + _mcp_servers_toml(
        spec.mcp_config_path,
        spec.write_roots[0] if spec.write_roots else None)


def _spawn_home(req: LLMRequest, model: str, effort: str,
                flavor: str = "openai") -> "Path | None":
    """Build this spawn's CODEX_HOME and return it, or None on failure.

    Two files: the credential, copied from the operator's own home
    (codex authenticates fine from a copy — same property agy has), and
    the rendered envelope. Everything else codex needs it creates itself.

    Lives inside `attempts_dir` so the dispatcher's orphan sweep is its
    cleanup, and so it is NOT under the system temp dir, which codex
    refuses to provision helper binaries into (measured 2026-08-12)."""
    home = Path(req.attempts_dir) / _SPAWN_HOME_DIRNAME
    auth_src = operator_codex_home() / "auth.json"
    try:
        home.mkdir(parents=True, exist_ok=True)
        if flavor == "zen":
            # NO auth.json for zen: the credential is OPENCODE_ZEN_API_KEY
            # via the provider's env_key. With a ChatGPT auth.json present
            # codex routes to the subscription backend instead and 400s:
            # "The 'x-preview-f-free' model is not supported when using
            # Codex with a ChatGPT account" (measured 2026-08-22, first
            # fleet spawn).
            pass
        elif not auth_src.is_file():
            print(f"[llm:codex] no credential at {auth_src} — run "
                  f"`codex login` as the operator", flush=True)
            return None
        else:
            shutil.copyfile(auth_src, home / "auth.json")
        (home / "config.toml").write_text(_render_config(req, model, effort,
                                                          flavor=flavor),
                                          encoding="utf-8")
    except (OSError, ValueError) as e:
        print(f"[llm:codex] could not build the spawn's capability envelope "
              f"at {home}: {e}", flush=True)
        return None
    return home


def _load_session_map(attempts_dir: Path) -> "dict[str, str]":
    try:
        data = json.loads(
            (attempts_dir / _SESSION_MAP).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _remember_thread(attempts_dir: Path, sid: "str | None",
                     thread_id: str) -> None:
    """Record codex's thread id against the framework's session id.

    See DELTA 2. The map lives in attempts_dir, which is per-pipeline:
    the Strategist's revision rounds share one directory and must
    resume; each Adversary round gets its own projection directory and
    must not — a fresh judge per round is the design."""
    if not sid or not thread_id:
        return
    data = _load_session_map(attempts_dir)
    data[sid] = thread_id
    try:
        (attempts_dir / _SESSION_MAP).write_text(json.dumps(data),
                                                 encoding="utf-8")
    except OSError:
        pass


#: Per-thread running totals, so a resumed spawn is billed for its own
#: turns rather than for the conversation. Beside `_SESSION_MAP` and
#: per-pipeline for the same reason (DELTA 2): the Strategist's rounds
#: share a directory and resume one thread; each Adversary round gets a
#: fresh projection and starts a new one.
_USAGE_LEDGER = "_codex_usage.json"


def _usage_baseline(attempts_dir: Path, thread_id: "str | None") -> dict:
    """What codex has already reported for `thread_id`.

    Empty for a cold call — a new thread starts the count at zero, so
    the whole figure is this spawn's. THIS IS THE WHOLE OF DELTA 10:
    codex's `usage` block is the SESSION's totals and it keeps growing
    across `codex exec resume`, while `spawn_usage` sums the rows it is
    given. Handing it the raw figure billed every earlier turn again on
    every wake — measured 2026-08-15 at 2.0x on a three-stage formalizer.
    """
    if not thread_id:
        return {}
    try:
        data = json.loads(
            (attempts_dir / _USAGE_LEDGER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    got = data.get(thread_id) if isinstance(data, dict) else None
    return got if isinstance(got, dict) else {}


def _remember_usage(attempts_dir: Path, thread_id: "str | None",
                    cumulative: dict) -> None:
    """Carry this conversation's running totals to the next resume."""
    if not thread_id or not cumulative:
        return
    try:
        raw = (attempts_dir / _USAGE_LEDGER).read_text(encoding="utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            data = {}
    except (OSError, ValueError):
        data = {}
    data[thread_id] = {k: int(v) for k, v in cumulative.items()
                       if isinstance(v, int)}
    try:
        (attempts_dir / _USAGE_LEDGER).write_text(json.dumps(data),
                                                  encoding="utf-8")
    except OSError:
        pass


#: Epoch when codex says the weekly window resets, or None. Read (and
#: consumed) by the dispatcher when it records a quota block, exactly
#: like `antigravity_cli.take_quota_reset`.
_last_quota_reset: "float | None" = None


def take_quota_reset() -> "float | None":
    global _last_quota_reset
    v, _last_quota_reset = _last_quota_reset, None
    return v


def _read_rate_limits(home: Path) -> "dict | None":
    """This spawn's own quota ledger (DELTA 5).

    codex appends a `token_count` event carrying `rate_limits` to its
    rollout file once per turn: `primary.used_percent`, `window_minutes`,
    `resets_at` (epoch), and `rate_limit_reached_type`. The rollout lives
    under this spawn's private CODEX_HOME, so the LAST such event in the
    newest file is this spawn's final reading — no cross-spawn filtering
    is needed, which is the one thing per-spawn homes buy us here."""
    try:
        files = sorted((home / "sessions").rglob("rollout-*.jsonl"),
                       key=lambda p: p.stat().st_mtime)
    except OSError:
        return None
    if not files:
        return None
    limits = None
    try:
        for line in files[-1].read_text(encoding="utf-8").splitlines():
            if '"rate_limits"' not in line:
                continue
            payload = (json.loads(line).get("payload") or {})
            if payload.get("type") == "token_count":
                limits = payload.get("rate_limits") or limits
    except (OSError, ValueError):
        return None
    return limits


def _note_quota(limits: "dict | None") -> bool:
    """Record the reset epoch and say whether the window is spent."""
    if not limits:
        return False
    if not limits.get("rate_limit_reached_type"):
        return False
    resets_at = (limits.get("primary") or {}).get("resets_at")
    if isinstance(resets_at, (int, float)) and resets_at > time.time():
        global _last_quota_reset
        _last_quota_reset = float(resets_at)
    return True


#: Where a codex spawn's reasoning goes to survive its sandbox. Chosen
#: to match claude, which keeps its transcripts in
#: `~/.claude/projects/<munged-cwd>/*.jsonl` — the CLI's own home,
#: outside the framework's scratch, never pruned (measured 2026-08-12:
#: 2.7 GB / 6,310 files back to 06-10).
#:
#: CORRECTED 2026-08-15: this note used to name agy alongside claude and
#: call codex "the odd one out". agy's home has been per-spawn since
#: 2026-08-02 for the same reason codex's is — the home IS the
#: capability envelope — so its conversations were going down with
#: `.attempts/<pid>/` too. The 744 MB measured here on 08-12 was the
#: pre-08-02 residue, still sitting in the global home; nothing had been
#: added to it for ten days. Two backends had the bug and this comment
#: is why only one was fixed. See `antigravity_cli._preserve_transcript`.
_TRANSCRIPT_DIRNAME = "codex_sessions"



def _preserve_transcript(req: LLMRequest, home: Path) -> None:
    """Move this spawn's rollout out of the doomed home, keep the
    credential in it.

    THE COST OF NOT DOING THIS, measured the day the provider landed:
    the framework's own diagnostic reported `[feedback] forward/
    inject3171: spawn rc=1, scratch_written=False (no record landed)`
    and the reason was unknowable — the rollout carrying every tool
    call, and `_spawn.stderr` beside it, had gone down with the
    directory. claude and agy both keep theirs; a backend whose failures
    cannot be read afterwards cannot be debugged in production, and the
    whole of 2026-08-12 was an argument about what an empty failure
    record costs.

    COPY, never move. The first version of this moved the rollout, and
    the next spawn died instantly: `thread/resume failed: failed to
    resolve rollout path ...: file does not exist (code -32600)`. codex
    resolves a resumed thread by opening THAT FILE in CODEX_HOME, so the
    original has to stay where it is until the home is torn down. It is
    also why the copy is refreshed on every spawn rather than written
    once — a resumed turn keeps appending to the same rollout, so an
    early snapshot would freeze a partial transcript.

    The HOME still dies, deliberately: it holds a copy of the operator's
    `auth.json`, and a credential that outlives its attempt is a worse
    problem than the one being solved. Transcript survives, secret does
    not — which is cleaner than either of the other two manages.

    No pruning is added here. Neither of the other backends prunes, and
    a provider that silently deletes its own evidence is precisely the
    bug above. Retention is a decision for all three at once."""
    try:
        attempts = Path(req.attempts_dir)
        dest = transcript_dest(req.attempts_dir, _TRANSCRIPT_DIRNAME)
        rollouts = sorted((home / "sessions").rglob("rollout-*.jsonl"))
        err = attempts / "_spawn.stderr"
        if not rollouts and not err.is_file():
            return
        if dest is None:
            print(f"[llm:codex] no .attempts ancestor for "
                  f"{req.attempts_dir} — transcript not preserved",
                  flush=True)
            return
        dest.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"[llm:codex] could not preserve the transcript: {exc}",
              flush=True)
        return
    # EACH ITEM GUARDED SEPARATELY. The first version wrapped the whole
    # body in one try, and a single failing rollout copy skipped the
    # stderr copy underneath it — which is how the 2026-08-13 feedback
    # failure stayed unexplained through three runs: the one artifact
    # this helper exists to save was the one silently dropped. A
    # best-effort helper must be best-effort per artifact, not
    # all-or-nothing.
    saved: "list[str]" = []
    for roll in rollouts:
        try:
            # Overwrite: the resumed turns append to the same file, so
            # the newest copy is the complete one.
            shutil.copyfile(roll, dest / roll.name)
            saved.append(roll.name)
        except OSError as exc:
            print(f"[llm:codex] rollout {roll.name} not preserved: {exc}",
                  flush=True)
    # One attempts_dir hosts several spawns (intake, work, the feedback
    # turn), and each overwrites `_spawn.stderr`. Number them so the
    # intake's failure is not erased by the work turn's.
    if err.is_file():
        try:
            n = 0
            while (dest / f"_spawn.{n}.stderr").exists():
                n += 1
            shutil.copyfile(err, dest / f"_spawn.{n}.stderr")
            saved.append(f"_spawn.{n}.stderr")
        except OSError as exc:
            print(f"[llm:codex] stderr not preserved: {exc}", flush=True)
    # Say what was kept. Silence here is what made the gap invisible.
    print(f"[llm:codex] transcript → {dest.name}: "
          f"{', '.join(saved) if saved else 'NOTHING'}", flush=True)


def _write_spawn_stderr(attempts_dir: Path, body: str, rc: int) -> None:
    try:
        (attempts_dir / "_spawn.stderr").write_text(
            f"rc={rc}\n{body[:10240]}", encoding="utf-8")
    except OSError:
        pass


class _Events:
    """The PROVIDER-specific facts, alongside the parser.

    `StreamParser(dialect="codex")` owns the state machine and the token
    accounting — everything the watchdog and `spawn_usage` need, in the
    shape they already read. What it deliberately does not carry is
    codex's own vocabulary: the minted thread id (there is no such thing
    on claude, whose id we mint ourselves) and the failure message that
    rides an rc of ZERO. Those live here, so the parser stays a state
    machine rather than growing a per-provider bag."""

    def __init__(self) -> None:
        self.thread_id: "str | None" = None
        self.usage: dict = {}
        self.turns: int = 0
        self.failed: "str | None" = None
        self.last_event_at: float = time.time()

    def feed_line(self, line: str) -> None:
        line = line.strip()
        if not line or not line.startswith("{"):
            return
        try:
            event = json.loads(line)
        except ValueError:
            return
        self.last_event_at = time.time()
        kind = event.get("type")
        if kind == "thread.started":
            self.thread_id = event.get("thread_id") or self.thread_id
        elif kind == "turn.completed":
            self.usage = event.get("usage") or self.usage
            self.turns += 1
        elif kind == "turn.failed":
            self.failed = str((event.get("error") or {}).get("message") or "")
        elif kind == "error":
            self.failed = str(event.get("message") or "")


class CodexCliProvider:
    def __init__(self, flavor: str = "openai") -> None:
        #: "openai" = the subscription backend; "zen" = OpenCode Zen via
        #: the local shim (free ox-alpha window). Chosen by
        #: `llm.get_provider` from the seat's `provider:` value.
        self.flavor = flavor

    def spawn(self, req: LLMRequest) -> int:
        from .claude_cli import (_build_cold_prompt, _load_prompt,
                                 is_shutdown_requested, track_proc,
                                 untrack_proc)
        if is_shutdown_requested():
            return SpawnRC.SHUTDOWN
        exe = resolve_codex_executable()
        if not exe:
            print("[llm:codex] codex CLI not found; skipping spawn",
                  flush=True)
            return SpawnRC.MISSING_DEP

        model = _resolve_model(req.kind)
        effort = _resolve_effort(req.kind)
        home = _spawn_home(req, model, effort, flavor=self.flavor)
        if home is None:
            return SpawnRC.MISSING_DEP

        # Resume only when a thread id was captured on the cold call.
        # Without one a bare retry note would reach an agent with no
        # memory of what it is correcting, so fall back to the full
        # prompt rather than waste the round (agy learned this first).
        prior = _load_session_map(req.attempts_dir).get(req.session_id or "")
        resuming = bool(prior) and (req.is_retry or req.continuation
                                    or req.is_postmortem)
        if resuming and req.is_retry:
            err = (req.retry_context or "(reason not captured)").strip()
            prompt = (
                f"Your previous output was rejected:\n\n```\n{err}\n```\n\n"
                f"Produce a corrected version. The instructions and context "
                f"from this session are unchanged. Write outputs into "
                f"{req.attempts_dir}/.")
        elif resuming:
            prompt = _load_prompt(req)
        elif req.inline_prompt is not None:
            prompt = req.inline_prompt
        else:
            prompt = _build_cold_prompt(req)

        # The two subcommands take DIFFERENT option sets, and copying
        # the cold flags onto the resume line is not a style choice —
        # it fails the spawn in 2.2s with `unexpected argument '-C'`
        # (measured 2026-08-12, the codex formalizer's second live
        # attempt). `codex exec resume` accepts only: --last --all
        # -c/--config --enable/--disable --strict-config -i/--image
        # -m/--model --dangerously-* --skip-git-repo-check --ephemeral
        # --ignore-user-config --ignore-rules --output-schema --json
        # -o/--output-last-message. No -C, no --add-dir, no --sandbox:
        # the resumed turn inherits the workspace roots recorded in the
        # session, and the process cwd below is the problem dir either
        # way.
        common = ["--json", "--skip-git-repo-check"]
        if resuming:
            cmd = [exe, "exec", "resume", str(prior), *common, "-"]
        else:
            cmd = [exe, "exec", *common,
                   # The FLAG, not just the config key. MEASURED
                   # 2026-08-12: with `sandbox_mode = "workspace-write"`
                   # in config.toml and no flag, the session still
                   # recorded `sandbox_policy: {"type": "read-only"}` —
                   # the CLI's own default wins. (Which of the two
                   # layers is at fault is not isolated; passing the
                   # flag is correct either way.) It mattered less than
                   # it looks only because our agent never writes with
                   # its own filesystem access — the MCP tools write
                   # server-side — but `apply_patch` would have failed
                   # the moment anything reached for it.
                   "--sandbox", "workspace-write",
                   "-C", str(req.problem_dir),
                   # DELTA 8 — the sandbox root is problem_dir; the
                   # directory the agent must write is elsewhere.
                   "--add-dir", str(req.attempts_dir),
                   # The prompt arrives on stdin (DELTA 3).
                   "-"]

        from .envelope import spawn_env, envelope_for
        from .spawn_guard import READ_DENY_ROOTS_ENV, WRITE_ROOTS_ENV
        env = spawn_env()
        spec = envelope_for(req)
        env[WRITE_ROOTS_ENV] = spec.write_roots_env()
        env[READ_DENY_ROOTS_ENV] = spec.read_deny_roots_env()
        env["CODEX_HOME"] = str(home)
        if self.flavor == "zen":
            key = os.environ.get("OPENCODE_ZEN_API_KEY", "")
            if not key:
                from ..core import config as _config
                key = str(_config.get("zen.api_key",
                                      env_var="OPENCODE_ZEN_API_KEY",
                                      default="") or "")
            if not key:
                print("[llm:codex] zen flavor but no OPENCODE_ZEN_API_KEY"
                      " (env or .env) — spawn will fail auth", flush=True)
            env["OPENCODE_ZEN_API_KEY"] = key
        _repo_root = str(Path(__file__).resolve().parents[2])
        env["PYTHONPATH"] = (
            _repo_root + os.pathsep + env["PYTHONPATH"]
            if env.get("PYTHONPATH") else _repo_root)

        # THE SPAWN IS A TREE. `codex` resolves to `codex.cmd`, so the
        # direct child is `cmd.exe` and the agent itself is two levels
        # down; `Popen.kill()` would leave it running (measured
        # 2026-08-15 — see `claude_cli._proc_jobs`).
        job = create_capped_job(None)
        try:
            proc = subprocess.Popen(
                cmd, env=env, cwd=str(req.problem_dir),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace",
                creationflags=no_window_creationflags(),
            )
            assign_to_job(job, proc)
        except OSError as exc:
            # The CLI could not be STARTED — a different thing from an
            # agent that ran and failed, and the distinction is worth
            # real money. On 2026-08-12 a `[WinError 193]` here escaped
            # as a worker exception, so the framework read it as "the
            # attempt was made and did not work": it charged the
            # attempt, re-woke the Strategist, and four Programme
            # debates later had spent ~106k output tokens on a provider
            # that had never once launched. MISSING_DEP is infra — it
            # does not charge the goal and it does not manufacture NL
            # work for a pipeline that cannot consume it.
            print(f"[llm:codex] could not launch {cmd[0]!r}: {exc}",
                  flush=True)
            _write_spawn_stderr(req.attempts_dir,
                                f"(could not launch {cmd[0]!r}: {exc})",
                                SpawnRC.MISSING_DEP)
            return SpawnRC.MISSING_DEP
        track_proc(proc, job)
        try:
            # `prior` is the thread this call resumes, or "" when cold —
            # which is exactly the key its running totals are filed
            # under, so the baseline is known BEFORE the stream starts
            # rather than inferred from it.
            return self._run_proc(req, proc, prompt, home,
                                  resume_thread=prior if resuming else None)
        finally:
            untrack_proc(proc)

    def _run_proc(self, req: LLMRequest, proc: subprocess.Popen,
                  prompt: str, home: Path,
                  resume_thread: "str | None" = None) -> int:
        from .claude_cli import (_watchdog, _persist_parser_state,
                                 kill_proc_tree)
        from .stream_parser import StreamParser

        events = _Events()
        parser = StreamParser(
            dialect="codex",
            usage_baseline=_usage_baseline(req.attempts_dir, resume_thread))
        stdout_chunks: "list[str]" = []
        stderr_chunks: "list[str]" = []

        def _drain(pipe, buf: "list[str]", feed: bool) -> None:
            try:
                for line in pipe:
                    buf.append(line)
                    if feed:
                        events.feed_line(line)
                        parser.feed_line(line)
            except (OSError, ValueError):
                pass

        readers = [
            threading.Thread(target=_drain, args=(proc.stdout, stdout_chunks,
                                                  True), daemon=True),
            threading.Thread(target=_drain, args=(proc.stderr, stderr_chunks,
                                                  False), daemon=True),
        ]
        for t in readers:
            t.start()
        try:
            proc.stdin.write(prompt)
            proc.stdin.close()
        except OSError:
            pass

        # Same watchdog claude runs, sampling the same state machine —
        # the only provider-specific input is which clock the (provider,
        # kind) pair chooses. Skipped for the short rescue/postmortem
        # spawns for the same reason it is on claude: their budget is
        # too small for a trap check to mean anything.
        stuck_flag: "list[bool]" = [False]
        done_flag: "list[bool]" = [False]
        wd: "threading.Thread | None" = None
        if not req.is_postmortem and req.inline_prompt is None:
            wd = threading.Thread(
                target=_watchdog, args=(proc, req.session_id or "codex"),
                kwargs={"stuck_flag": stuck_flag, "done_flag": done_flag,
                        "timeout_sec": req.timeout_sec, "parser": parser,
                        "kind": req.kind, "provider": PROVIDER_NAME,
                        "trap_check_sec_override": req.trap_check_sec},
                daemon=True)
            wd.start()

        timed_out = False
        try:
            proc.wait(timeout=req.timeout_sec)
        except subprocess.TimeoutExpired:
            kill_proc_tree(proc)
            timed_out = True
        for t in readers:
            t.join(timeout=2)
        if wd is not None:
            wd.join(timeout=2)
        _persist_parser_state(req.attempts_dir, parser)
        rc = proc.returncode
        stdout = "".join(stdout_chunks)
        stderr = "".join(stderr_chunks)

        if events.thread_id:
            _remember_thread(req.attempts_dir, req.session_id,
                             events.thread_id)
            # …and what the conversation has cost SO FAR, which is the
            # next resume's baseline. Written after the persist above so
            # a crash between the two loses the carry-forward (the next
            # spawn over-reports) rather than the spawn's own row.
            _remember_usage(req.attempts_dir, events.thread_id,
                            parser.cumulative_usage())

        # The quota reading is taken BEFORE any rc branch: a spawn that
        # times out still spent tokens, and its rollout still carries the
        # window state. Reading it only on the failure path would make
        # the ledger blind exactly when the window is closing. It also
        # has to happen before `_preserve_transcript` moves the rollout.
        spent = _note_quota(_read_rate_limits(home))
        try:
            return self._classify(req, rc, timed_out, spent, events,
                                  stdout, stderr, stuck_flag, done_flag)
        finally:
            # Every exit path, including the two watchdog verdicts and
            # the timeout — a spawn killed mid-thought is exactly the
            # one whose reasoning someone will want to read.
            _preserve_transcript(req, home)

    def _classify(self, req: LLMRequest, rc: int, timed_out: bool,
                  spent: bool, events: "_Events", stdout: str, stderr: str,
                  stuck_flag: "list[bool]", done_flag: "list[bool]") -> int:
        """What the spawn's outcome WAS, decided on the event stream
        first and the rc second — see DELTA 6: a hard API refusal exits
        zero, so rc alone would report the vendor's rejection as the
        agent's fair chance."""
        from .claude_cli import is_shutdown_requested

        if stuck_flag[0]:
            _write_spawn_stderr(req.attempts_dir,
                                "(watchdog stuck-kill: wall cap or tool "
                                "silence — see [watchdog] log line above)",
                                SpawnRC.STUCK_THINKING)
            return SpawnRC.STUCK_THINKING
        if done_flag[0]:
            print("[llm:codex] watchdog completion-reclaim (agent done, "
                  "process hung) — salvaging", flush=True)
            _write_spawn_stderr(req.attempts_dir,
                                "(watchdog completion-reclaim: turn "
                                "completed but process hung)",
                                SpawnRC.TIMEOUT)
            return SpawnRC.TIMEOUT
        if timed_out:
            print(f"[llm:codex] timed out after {req.timeout_sec}s",
                  flush=True)
            _write_spawn_stderr(req.attempts_dir,
                                f"(subprocess.TimeoutExpired after "
                                f"{req.timeout_sec}s)", SpawnRC.TIMEOUT)
            return SpawnRC.TIMEOUT
        # WE killed it — same branch as `claude_cli`, same reason. On
        # this backend the corpse is a SILENT rc=1 with an empty stderr,
        # which reads exactly like a CLI that failed on its own; the
        # 08-15 probe legs lost the last pipeline's feedback turn to
        # teardown three times and reported it as rc=129 once and rc=1
        # twice, differing only in whether the kill landed before or
        # after the start. Guarded on `rc != 0` so a spawn that finished
        # as shutdown fired keeps its success, and placed BEFORE the
        # quota/misconfig marker tables so our own kill cannot be read
        # as an exhausted window.
        if rc != 0 and is_shutdown_requested():
            _write_spawn_stderr(req.attempts_dir,
                                "(killed by daemon shutdown)",
                                SpawnRC.SHUTDOWN)
            return SpawnRC.SHUTDOWN
        if rc != 0 or events.failed:
            _write_spawn_stderr(
                req.attempts_dir,
                (events.failed or "") + "\n" + (stderr or ""), rc)
        if spent:
            print(f"[llm:codex] quota window spent (rc={rc}) → "
                  f"{SpawnRC.QUOTA_EXHAUSTED}", flush=True)
            return SpawnRC.QUOTA_EXHAUSTED
        combined = ((events.failed or "") + " " + stdout + " "
                    + stderr).lower()
        if rc != 0 and any(m in combined for m in _QUOTA_MARKERS):
            print(f"[llm:codex] quota exhausted (rc={rc} → "
                  f"{SpawnRC.QUOTA_EXHAUSTED})", flush=True)
            return SpawnRC.QUOTA_EXHAUSTED
        if rc != 0 and any(m in combined for m in _MISCONFIG_MARKERS):
            print(f"[llm:codex] misconfigured (rc={rc}): "
                  f"{(events.failed or stderr or '')[:200]}", flush=True)
            return rc
        # `turn.failed` / `error` with rc=0: the CLI ran, the turn did
        # not. rc=0 would tell the pipeline the agent had its fair
        # chance, which is the opposite of what happened.
        if rc == 0 and events.failed:
            print(f"[llm:codex] turn failed: {events.failed[:200]}",
                  flush=True)
            return 1
        return rc
