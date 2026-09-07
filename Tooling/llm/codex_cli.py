"""Codex CLI provider — `codex exec`, headless.

Behaviour is aligned to `claude_cli` wherever codex allows it, because
claude is the backend with the most production hours and every deviation
is a place where a failure looks different from the one the framework
already knows how to read. Eleven deviations were forced by the CLI, and
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
  DELTA 10 USAGE IS NOT THE CALL'S, AND WHOSE IT IS DEPENDS ON WHERE
           YOU READ IT. `input_tokens` INCLUDES `cached_input_tokens`
           where claude's excludes them, so the parser subtracts the
           cached share (measured 2026-08-15: a cache-hit rate of 49%
           where the truth was 97%). Beyond that there are two
           different figures, and the framework used to conflate them:
             * the STREAM's `turn.completed.usage` runs over the `codex
               exec` PROCESS. A resumed exec reports its own spend, not
               the thread's.
             * the ROLLOUT's `thread_token_usage` runs over the THREAD
               and keeps growing across every resume.
           Subtracting the second from the first is what turned every
           resumed spawn's row into zeros (`judge_continuity/
           strategist_c_r1`, 2026-09-07). What this adapter does now is
           read the LEDGER: `thread_token_usage` before the spawn and
           after it, and the difference is the row. `_USAGE_LEDGER`
           (beside `_SESSION_MAP`) carries the "before" per thread so
           the file is scanned once per spawn rather than twice, and
           `lab/session_resume` seeds it when it stages a historical
           session. The stream's figure stands only when no rollout can
           be read — see `_run_proc`.
  DELTA 11 THE STREAM HAS ITS OWN IDLE CLOCK, AND IT IS ONLY SETTABLE
           ON A PROVIDER YOU NAME. `stream_idle_timeout_ms` and its two
           retry siblings are `ModelProviderInfo` fields, and 0.153.0
           refuses `[model_providers.openai]` outright — built-in ids
           are reserved. So an NL seat routes through `openai-nl`, a
           renamed copy of the built-in carrying its ChatGPT auth,
           endpoint and websocket transport. claude has no such clock
           to disarm. See `_nl_provider_toml`.

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

from .base import (MCP_TOOL_TIMEOUT_SEC, LLMRequest, SpawnRC,
                   transcript_dest, which_launchable)
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
        # Above everything the framework may spend inside one tool —
        # the heavy elaboration wall + re-warm, and a queued `compute`
        # call. A client that hangs up first turns a measured failure
        # into a mystery tool error mid-elaboration. See
        # `base.MCP_TOOL_TIMEOUT_SEC`.
        out.append(f"tool_timeout_sec = {MCP_TOOL_TIMEOUT_SEC}")
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


#: The renamed copy of the built-in `openai` provider that NL seats
#: route through. See `_nl_provider_toml` (DELTA 11) for why it cannot
#: simply be `openai`.
_NL_PROVIDER_ID = "openai-nl"

#: The ChatGPT backend the built-in provider talks to. Ours because a
#: custom provider derives no default; it is a copy of the vendor's own
#: value and the one thing here that can go stale — it fails LOUDLY (a
#: connection error on every NL spawn), not silently.
_CHATGPT_CODEX_URL = "https://chatgpt.com/backend-api/codex"

#: Reconnect budget for an NL stream. Ten, against the default five —
#: the incident's `Reconnecting... 5/5` was that default running out.
_NL_STREAM_RETRIES = 10


def _stream_idle_kinds() -> "frozenset[str]":
    """The seats whose silence IS the work — the framework's own list,
    read rather than copied (`capabilities.STREAM_IDLE_KINDS`)."""
    from .capabilities import STREAM_IDLE_KINDS
    return STREAM_IDLE_KINDS


def _nl_provider_toml(req: LLMRequest) -> "list[str]":
    """DELTA 11 — THE STREAM'S IDLE CLOCK MUST NOT BE THE BINDING ONE.

    codex ends a turn whose stream has been quiet for
    `stream_idle_timeout_ms` and reconnects `stream_max_retries` times.
    An NL seat's work is exactly that quiet: `capabilities`
    .STREAM_IDLE_KINDS is the framework's own name for the kinds whose
    thinking cannot be read as tool cadence, and on codex they run
    TIMEOUT_ONLY for the same reason. union_closed g691, 2026-09-05:
    two gpt-6-astra/xhigh Theorist wakes died as `Reconnecting... 5/5
    (stream disconnected before completion: idle timeout waiting for
    websocket)` — 5/5 being the untouched default — and one of them had
    already written its document.

    THE VALUE IS THE SEAT'S OWN WALL, not a number chosen here (owner
    ruling 2026-09-05): the framework's timeout stays the only clock
    that can end a turn, raising a seat's budget raises this with it,
    and there is no second constant to drift from the first.

    WHY A RENAMED PROVIDER. All three keys are fields of
    `ModelProviderInfo`, i.e. they exist only under
    `model_providers.<id>`, and MEASURED on 0.153.0 the built-in id is
    closed: `Error loading config.toml: model_providers contains
    reserved built-in provider IDs: 'openai'. Built-in providers cannot
    be overridden.` A top-level spelling is not a fallback — codex
    accepts unknown top-level keys silently (measured with a nonsense
    key), so writing them there would look like it worked and do
    nothing. So the provider is renamed and carries the built-in's own
    fields, each of which was measured rather than assumed:

      requires_openai_auth  ChatGPT auth survives the rename: with
                            auth.json carrying `tokens` and a NULL
                            OPENAI_API_KEY, and no env key set, the
                            probe authenticated and answered.
      supports_websockets   WITHOUT IT THE TRANSPORT SILENTLY CHANGES:
                            the probe's failure said "idle timeout
                            waiting for SSE" where production says
                            "waiting for websocket". With it, the
                            message matches production again (websocket
                            first, SSE fallback).
      base_url / wire_api   a custom provider derives neither.

    And the keys are honoured, which is the point of the exercise:
    `stream_idle_timeout_ms = 1` + `stream_max_retries = 2` on this
    provider reproduced the incident verbatim — `Reconnecting... 2/2`,
    `stream disconnected before completion: idle timeout waiting for
    websocket`. Nothing else moved: the tool list the model reports is
    identical on both providers, and `rate_limits` still lands in the
    rollout (DELTA 5's quota signal survives).
    """
    return [
        "", f"[model_providers.{_NL_PROVIDER_ID}]",
        'name = "OpenAI"',
        f"base_url = {_toml_str(_CHATGPT_CODEX_URL)}",
        'wire_api = "responses"',
        "requires_openai_auth = true",
        "supports_websockets = true",
        f"stream_idle_timeout_ms = {max(1, int(req.timeout_sec)) * 1000}",
        f"stream_max_retries = {_NL_STREAM_RETRIES}",
        f"request_max_retries = {_NL_STREAM_RETRIES}",
    ]


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
        # codex reads every AGENTS.md from the cwd up to the git root as
        # instructions; our cwd is `.attempts/<pid>/` inside the repo, so
        # a stray root AGENTS.md (the frontend collaborator's rulebook,
        # 2026-08-25) became the first user message of every local codex
        # wake — measured on the 2026-08-26 strategist + judge rollouts.
        # Instructions come from the framework's prompt alone.
        "project_doc_max_bytes = 0",
        # TOML: top-level keys MUST precede the first [table] header —
        # appended after [windows] they silently become [windows].* keys
        # and codex ignores them (measured 2026-08-22: the first zen
        # fleet spawn went to api.openai.com with no bearer).
        *([
            'web_search = "disabled"',
            'model_provider = "zen"',
        ] if flavor == "zen" else []),
        # DELTA 11 — an NL seat routes through a RENAMED copy of the
        # built-in provider, because that is the only place codex will
        # accept a stream-idle setting. See `_nl_provider_toml`.
        *([f'model_provider = "{_NL_PROVIDER_ID}"']
          if flavor != "zen" and (req.kind or "") in _stream_idle_kinds()
          else []),
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
    if flavor != "zen" and (req.kind or "") in _stream_idle_kinds():
        lines += _nl_provider_toml(req)
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
        # (`/a/<relpath>/v1`): the shim used to recover it by regexing
        # the request text, and codex only carries those paths on SOME
        # turns — write_file flickered between working and "no attempts
        # directory" inside one session (2026-08-22). The per-spawn
        # config is already unique to this spawn; the URL is the one
        # deterministic in-band channel the shim always sees.
        # The segment is the FULL path relative to `.attempts`, not the
        # basename: adversary and judge rounds spawn from projection
        # dirs like `<uuid>/adversary/r2`, and the basename alone sent
        # `/a/r2/v1` — the shim's parse missed it and every write in
        # those legs was refused (2026-08-22, same evening).
        base = str(base).rstrip("/")
        if req.attempts_dir is not None and base.endswith("/v1"):
            parts = Path(req.attempts_dir).resolve().parts
            if ".attempts" in parts:
                i = len(parts) - 1 - parts[::-1].index(".attempts")
                rel = "/".join(parts[i + 1:])
                if rel:
                    # `/b/<sec>` carries the seat's TIME budget so the
                    # shim's wrap-up can fire before the wall does: at
                    # ~20-30s an iteration a 1800s formalizer buys only
                    # 65-90 of the 200-iteration cap, so the iteration
                    # wrap-up never triggered and turns died at the
                    # wall salvaging half-states (7 timeouts in one
                    # 37-min window, friend fleet 2026-08-22).
                    # The wrap-up margin scales with the wall: a flat
                    # 300s (calibrated on the 1800s formalizer) starved
                    # a 420s presearch to a 120s turn budget — tools
                    # locked before the first block could be written
                    # (friend-fleet report, 2026-08-23).
                    wall = int(req.timeout_sec)
                    budget = max(60, wall - min(300, max(60, wall // 4)))
                    # `/c/<problem-rel>` carries the spawn's cwd (its
                    # problem dir). A standalone MCP server inherits it
                    # as process cwd, but the shim runs tools
                    # in-process where cwd is the shim's own — bare
                    # problem-file reads (TREE.md) missed their first
                    # root and the basename fallback walked the repo
                    # into FOREIGN attempts (both fleets, 2026-08-24).
                    crel = ""
                    try:
                        pparts = Path(req.problem_dir).resolve().parts
                        if "Problems" in pparts:
                            j = pparts.index("Problems")
                            crel = "/".join(pparts[j:])
                    except (TypeError, ValueError, OSError):
                        pass
                    cseg = f"/c/{crel}" if crel else ""
                    base = (base[: -len("/v1")]
                            + f"/a/{rel}{cseg}/b/{budget}/v1")
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


#: A THREAD's running totals as of the end of the last spawn that
#: touched it — the "before" half of the subtraction that bills a
#: resumed spawn for its own turns. Beside `_SESSION_MAP` and
#: per-pipeline for the same reason (DELTA 2): the Strategist's rounds
#: share a directory and resume one thread; each Adversary round gets a
#: fresh projection and starts a new one.
_USAGE_LEDGER = "_codex_usage.json"

#: The four token counts, in the parser's own key names. `turns` is not
#: one of them: it counts events in a stream, not tokens in a ledger,
#: and adding or subtracting it across spawns means nothing.
_USAGE_KEYS = ("input_tokens", "output_tokens", "cache_read_input_tokens",
               "cache_creation_input_tokens")


def _usage_add(a: dict, b: dict) -> "dict[str, int]":
    return {k: int(a.get(k) or 0) + int(b.get(k) or 0) for k in _USAGE_KEYS}


def _usage_delta(after: dict, before: dict, *, label: str = ""
                 ) -> "dict[str, int]":
    """`after - before`, clamped at zero AND LOUD ABOUT IT.

    A component that would go negative means the "before" is not this
    thread's earlier state — the two figures are in different
    coordinates. That is exactly the 2026-09-07 bug (a per-exec stream
    figure minus a per-thread rollout total), and under a silent clamp
    it looked like a resumed judge that argued for four minutes and
    spent nothing."""
    out: "dict[str, int]" = {}
    negative: "list[str]" = []
    for k in _USAGE_KEYS:
        d = int(after.get(k) or 0) - int(before.get(k) or 0)
        if d < 0:
            negative.append(f"{k}={d}")
        out[k] = max(0, d)
    if negative:
        print(f"[llm:codex] usage baseline is not this thread's earlier "
              f"state{' for ' + label if label else ''} "
              f"({', '.join(negative)}) — the row is clamped and therefore "
              f"under-reports. Check that the ledger and the rollout "
              f"count the same thing.", flush=True)
    return out


def rollout_usage(rollout: "Path | str") -> "dict[str, int]":
    """A codex thread's cumulative totals, out of its own rollout, in
    `StreamParser`'s key names.

    THE PROVIDER'S OWN LEDGER. Read from the last
    `token_usage_record.thread_token_usage` in the file, which codex
    appends per API call and which therefore survives the exec process,
    a killed spawn, and a stream nobody parsed. Translated the way the
    parser translates a live `turn.completed`: codex's `input_tokens`
    INCLUDES the cached ones and the parser's does not, so the cached
    half is subtracted rather than counted twice.

    Empty when the file holds no usage record — a spawn that died before
    its first API call, and a case the caller has to keep meaning
    "unknown" rather than "zero"."""
    last: "dict | None" = None
    try:
        with open(rollout, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                # Cheap prefilter: these files run to megabytes and only
                # a few dozen lines are usage records.
                if '"token_usage_record"' not in line:
                    continue
                try:
                    obj = json.loads(line)
                except ValueError:
                    continue
                if obj.get("type") == "token_usage_record":
                    last = obj
    except OSError:
        return {}
    if last is None:
        return {}
    u = (last.get("payload") or {}).get("thread_token_usage") or {}
    total_in = int(u.get("input_tokens") or 0)
    cached = int(u.get("cached_input_tokens") or 0)
    return {"input_tokens": max(0, total_in - cached),
            "cache_read_input_tokens": cached,
            "cache_creation_input_tokens":
                int(u.get("cache_write_input_tokens") or 0),
            "output_tokens": int(u.get("output_tokens") or 0)}


def _thread_rollout(home: Path, thread_id: "str | None") -> "Path | None":
    """This thread's rollout inside the spawn's own CODEX_HOME.

    Largest wins, for the reason `lab/session_resume.find_rollout` gives:
    a resumed turn APPENDS to the file, so the longer copy is the later
    state of the conversation."""
    if not thread_id:
        return None
    root = Path(home) / "sessions"
    if not root.is_dir():
        return None
    hits = [p for p in root.rglob(f"rollout-*-{thread_id}.jsonl")
            if p.is_file()]
    if not hits:
        return None
    return max(hits, key=lambda p: p.stat().st_size)


def _usage_baseline(attempts_dir: Path, thread_id: "str | None") -> dict:
    """The thread's cumulative totals as of the last spawn that touched
    it, or `{}` when nothing is filed for it.

    Empty for a cold call — a new thread starts the count at zero, so
    the whole figure is this spawn's."""
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
    """Carry this THREAD's running totals to the next resume."""
    if not thread_id or not cumulative:
        return
    try:
        raw = (attempts_dir / _USAGE_LEDGER).read_text(encoding="utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            data = {}
    except (OSError, ValueError):
        data = {}
    data[thread_id] = {k: int(cumulative.get(k) or 0) for k in _USAGE_KEYS}
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


#: Mirrors `lsp.gateway.ELAB_CREDIT_FILENAME` (string duplicated on
#: purpose: the llm layer must not import the gateway module).
_ELAB_CREDIT_FILENAME = "_elab_queue_credit"


def _elab_queue_credit_sec(attempts_dir) -> float:
    """Cumulative seconds this spawn's tool calls spent queued at the
    gateway's elaboration gate — written by the gate, read by the wall
    loop. Missing/unreadable = 0 (no credit)."""
    if attempts_dir is None:
        return 0.0
    try:
        raw = (Path(attempts_dir) / _ELAB_CREDIT_FILENAME).read_text(
            encoding="utf-8").strip()
        return max(0.0, float(raw or 0))
    except (OSError, ValueError):
        return 0.0


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


def latest_rate_limits(workspace: "Path | str") -> "dict | None":
    """The newest quota reading ANY codex spawn in this workspace left
    behind — `_read_rate_limits`' workspace-wide twin, for a reader that
    is not inside a spawn (the console).

    Same material, different question. DELTA 5 says there is nothing to
    ASK: the reading exists only because a spawn already spent something
    and codex wrote `rate_limits` into its rollout. So the freshest
    truth available from outside is the last `token_count` event of the
    newest preserved rollout, and it comes with an AGE, which the caller
    must carry to the reader: "8% of the weekly window" measured four
    minutes ago and four hours ago are different claims, and a meter
    that hides which one it is showing is the same lie as a live meter
    that silently freezes.

    Tail-read, newest first, a handful of files deep: a rollout is a
    whole transcript (MBs), the last event is at its end, and the newest
    file can legitimately hold none (a spawn that died before its first
    turn). Returns {"limits": <the rate_limits payload>,
    "measured_at": <epoch>} or None."""
    root = Path(workspace) / ".asterism" / _TRANSCRIPT_DIRNAME
    try:
        files = sorted(root.rglob("rollout-*.jsonl"),
                       key=lambda p: p.stat().st_mtime)
    except OSError:
        return None
    for path in reversed(files[-8:]):
        try:
            limits = None
            for line in _tail_lines(path):
                if '"rate_limits"' not in line:
                    continue
                payload = (json.loads(line).get("payload") or {})
                if payload.get("type") == "token_count":
                    limits = payload.get("rate_limits") or limits
            if limits:
                return {"limits": limits, "measured_at": path.stat().st_mtime}
        except (OSError, ValueError):
            continue
    return None


def _tail_lines(path: Path, limit: int = 262_144) -> "list[str]":
    """The last `limit` bytes as whole lines (a truncated first line is
    dropped, never handed to a parser)."""
    with path.open("rb") as fh:
        fh.seek(0, os.SEEK_END)
        size = fh.tell()
        fh.seek(max(0, size - limit))
        blob = fh.read()
    if size > limit:
        _, _, blob = blob.partition(b"\n")
    return blob.decode("utf-8", "replace").splitlines()


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

        if not resuming:
            # codex-path only (user ruling 2026-08-22): the codex binary
            # hard-injects developer guidance mandating `apply_patch`
            # and a "Write tool" that do not exist behind the asterism
            # tool face — 12 self-reports of agents reconciling the two
            # worlds by guesswork. One alignment line, prepended at the
            # adapter so no other provider ever sees it.
            # Second sentence (user ruling 2026-08-24): codex 0.149's
            # native path can present the tools through its code-mode
            # host — a lone `functions.exec` plus an ALL_TOOLS array —
            # and 16 agents burned a discovery turn per spawn finding
            # the prompt's tool names inside it. The door cannot be
            # removed (`code_mode_host = false` does not flatten,
            # probed); name it instead.
            # Third shape (Oracle boarding, 2026-08-24, 6 reports in
            # the first hour): on Linux the same binary surfaces them
            # as TOP-LEVEL functions under an `mcp__asterism_tools__`
            # prefix — the note claiming only the exec door then read
            # as wrong and re-opened the guesswork it was built to
            # close. Name all three shapes; promise only the mapping.
            prompt = (
                "NOTE: your function list is the complete, "
                "authoritative toolset for this task — ignore any "
                "built-in guidance about `apply_patch` or other tools "
                "not in it. The prompt's tool names (`inspect`, "
                "`write_file`, …) may appear verbatim, under an "
                "`mcp__asterism_tools__` prefix (the prefixed function "
                "IS that tool), or inside a lone `functions.exec` "
                "(ALL_TOOLS) — same tools, different doors; don't "
                "spend turns rediscovering them.\n\n" + prompt)

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

        # What this thread had already cost, taken BEFORE the process
        # can append to its rollout. The ledger answers it without
        # reading a megabyte; the rollout is the fallback for a resume
        # whose ledger entry is missing — a session staged by hand, or
        # one whose previous spawn died before it could write.
        pre_usage = (_usage_baseline(req.attempts_dir, prior)
                     if resuming else {})
        if resuming and not pre_usage:
            staged = _thread_rollout(home, prior)
            if staged is not None:
                pre_usage = rollout_usage(staged)

        # THE SPAWN IS A TREE. `codex` resolves to `codex.cmd`, so the
        # direct child is `cmd.exe` and the agent itself is two levels
        # down; `Popen.kill()` would leave it running (measured
        # 2026-08-15 — see `claude_cli._proc_jobs`).
        job = create_capped_job(None)
        # POSIX: own session/process group, so `kill_proc_tree` can
        # `killpg` the whole `cmd.exe`-equivalent shim -> node -> agent
        # tree instead of `proc.kill()` reaping only the direct child.
        # Windows keeps the Job Object above — no session kwarg there.
        popen_kwargs: dict = {}
        if os.name != "nt":
            popen_kwargs["start_new_session"] = True
        try:
            proc = subprocess.Popen(
                cmd, env=env, cwd=str(req.problem_dir),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace",
                creationflags=no_window_creationflags(),
                **popen_kwargs,
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
            # `prior` is the thread this call resumes, or "" when cold.
            # Both it and what the thread had already cost are settled
            # BEFORE the stream starts rather than inferred from it.
            return self._run_proc(req, proc, prompt, home,
                                  resume_thread=prior if resuming else None,
                                  pre_usage=pre_usage)
        finally:
            untrack_proc(proc)

    def _run_proc(self, req: LLMRequest, proc: subprocess.Popen,
                  prompt: str, home: Path,
                  resume_thread: "str | None" = None,
                  pre_usage: "dict | None" = None) -> int:
        from .claude_cli import (_watchdog, _persist_parser_state,
                                 kill_proc_tree)
        from .stream_parser import StreamParser

        events = _Events()
        pre_usage = dict(pre_usage or {})
        parser = StreamParser(dialect="codex")
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
                        "trap_check_sec_override": req.trap_check_sec,
                        # Third clock: the zen shim touches this per
                        # tool-loop iteration — codex reports at item
                        # granularity, so a long healthy loop is
                        # silence on the other two (five working
                        # strategists reaped at 2400s, 2026-08-22).
                        "heartbeat_path": (
                            str(Path(req.attempts_dir) / "_shim_heartbeat")
                            if req.attempts_dir is not None else None)},
                daemon=True)
            wd.start()

        timed_out = False
        # The wall grows by the session's Lean-queue credit (owner
        # design 2026-08-26): time a tool call spends QUEUED at the
        # gateway's elaboration gate is machine congestion, not the
        # agent's — the gateway accrues it in the attempts dir and the
        # wall extends by the same amount, capped at one extra base
        # wall (queue credit can never more than double a spawn; the
        # 6h lease TTL stays far above). Re-read each poll: credit
        # accrues WHILE the spawn runs.
        _wall_t0 = time.monotonic()
        # Delta from THIS spawn's start — the file accrues across the
        # attempt's whole life, and an earlier turn's queue time must
        # not inflate a later turn's wall.
        _credit0 = _elab_queue_credit_sec(req.attempts_dir)
        while True:
            _credit = _elab_queue_credit_sec(req.attempts_dir) - _credit0
            wall = req.timeout_sec + min(max(0.0, _credit),
                                         float(req.timeout_sec))
            remaining = wall - (time.monotonic() - _wall_t0)
            if remaining <= 0:
                kill_proc_tree(proc)
                timed_out = True
                break
            try:
                proc.wait(timeout=min(30.0, remaining))
                break
            except subprocess.TimeoutExpired:
                continue
        for t in readers:
            t.join(timeout=2)
        if wd is not None:
            wd.join(timeout=2)
        rc = proc.returncode
        stdout = "".join(stdout_chunks)
        stderr = "".join(stderr_chunks)

        # WHAT THIS SPAWN COST, out of the provider's own ledger. The
        # rollout carries `thread_token_usage` per API call, so the
        # difference across the spawn is this exec's spend whatever the
        # stream chose to report — and it is there even when the stream
        # said nothing at all, which is every killed spawn: before this,
        # a codex worker reaped at its wall reported zero tokens for the
        # hour it had just spent. The stream's own figure stands only
        # when there is no rollout to read.
        thread = events.thread_id or resume_thread
        rollout = _thread_rollout(home, thread)
        post_usage = rollout_usage(rollout) if rollout is not None else {}
        if post_usage:
            parser.adopt_usage(_usage_delta(
                post_usage, pre_usage,
                label=f"{req.kind or 'codex'}/{thread}"))
        # Persisted after the adoption, because the row it writes is
        # what `spawn_usage` bills (`agent/runtime` reads it back out of
        # `_parser_state.json`).
        _persist_parser_state(req.attempts_dir, parser)

        if thread:
            if events.thread_id:
                _remember_thread(req.attempts_dir, req.session_id,
                                 events.thread_id)
            # …and what the THREAD has cost so far, which is the next
            # resume's baseline. Written after the persist above so a
            # crash between the two loses the carry-forward rather than
            # the spawn's own row — and losing it now costs a rollout
            # scan on the next resume rather than a wrong figure, since
            # the fallback reads the same number out of the file.
            _remember_usage(req.attempts_dir, thread,
                            post_usage or _usage_add(pre_usage,
                                                     parser.usage()))

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
