"""The console explainer's backend — one dialect per provider.

`serve/chat.py` owns the HTTP/SSE surface and the page context; this
module owns everything that differs BETWEEN backends, because that
difference is not one flag. The explainer was written against claude
and inherited three of claude's properties as if they were universal:

  * a session id the CALLER mints and replays (`--session-id` /
    `--resume`) — so "conversation continuity" was assumed, never read;
  * an incremental event stream (`stream-json`) — so the drawer's
    "thinking… / reading…" stages were assumed to exist;
  * a read fence expressible on the command line (`--allowedTools
    Read(<ws>/Problems/**)` …) — so "read-only, scoped to the
    workspace" was assumed to be enforceable.

`llm/capabilities.py` says none of the three is uniform, and each one
is a DIFFERENT answer for agy. Routing the explainer through
`get_provider`'s resolution chain while keeping those three assumptions
would replace "hardwired to claude" with "hardwired to the assumption
that every provider is claude" — the same lie one level in. So each
backend below declares what it actually gives the reader, and the two
places where the answer is worse than claude's are reported to the
USER rather than absorbed:

RESUME. `capabilities.session_resume` has three live shapes and
`plan_turn` reads it rather than the provider's name. A provider with
`RESUME_NONE` (the OpenAI-compatible endpoint) or `RESUME_UNDECLARED`
(a backend nobody measured) gets NO resume flag and
`remembers()` is False, which `/api/chat/state` publishes as
`conversation_memory: false` and the drawer says out loud. Follow-ups
are NOT disabled: a single-shot explainer still answers every question
correctly, it just answers each one cold, and refusing the feature
would be a bigger loss than the memory is. What must not happen is the
user asking "and why is that?" into a blank context and reading the
answer as continuous.

READ SCOPE — and this one is a genuine difference in the guarantee the
feature offers, not a degradation of comfort. claude's read surface is
an allowlist of path patterns plus deny rules, enforced by the CLI
(`ENFORCEMENT_HARD`, `allow_honoured_actions = {"*"}`). agy's
`read_file` permission was measured on 1.1.11 (2026-08-10, three
probes) to be honoured in NO direction — an allow scoped to a subdir
still read outside it, an explicit deny of a file still read it, and
with no rule at all the read succeeded. `read_file` is therefore absent
from agy's `allow_honoured_actions`, and `_spawn_permissions` says so
in the engine. The consequence for an explainer is exact: on agy the
assistant's reads are bounded by the OS account, not by the workspace —
`.asterism/backups/`, `docs/internal/`, another problem's proofs, the
operator's own dotfiles.

The ruling taken here (and it is a ruling, so it is written down rather
than left in a commit message): the agy-backed explainer SHIPS, with
the difference published as `read_scope` on `/api/chat/state` and shown
in the drawer, not silently and not refused. Three reasons.
  1. The explainer's soundness boundary is that it cannot ACT — no
     write tools, no engine commands, no DB. That boundary is
     unchanged here and is enforced on agy by the same file that
     enforces it in the engine (deny `command`/`write_file`/`read_url`
     plus the Ask-default). The read fence is a confidentiality
     property, and confidentiality about one's own workspace is a
     weaker claim than soundness.
  2. On a machine seated on agy the ENGINE's spawns already read that
     workspace unfenced, all day, by the same measurement. Gating the
     explainer while the Strategist runs unfenced would be a fence
     drawn where it is cheap rather than where the exposure is.
  3. Refusing would restore exactly the dead button this change exists
     to remove, for the machine that installed only agy.
The alternative — an explicit opt-in knob before an agy explainer may
run — is recorded in the report and remains available; it is the
owner's call, and backlog #162 (the read-fence question) is
deliberately still open. Nothing here pre-empts it: no grant was
widened, and the honest label makes the exposure visible to the person
who would have to decide.

A provider with no backend below is REFUSED with a message naming it,
not silently answered by claude. `openai` is the live example: it has
no tool surface at all (`ENFORCEMENT_NOT_APPLICABLE`), so it cannot
read the workspace, and an explainer that cannot read is not a cheaper
explainer — it is a confident stranger.
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path

from . import capabilities, drift_guard

# --------------------------------------------------------------- events
#
# The UI event vocabulary every backend must produce. `serve/chat.py`
# forwards these verbatim over SSE and the drawer renders them:
#
#   {"type": "status", "stage": "thinking"|"reading"|…, "tool"?: str}
#   {"type": "delta",  "text": str}
#   {"type": "done",   "ok": bool, "subtype": str, "turns": int|None,
#                      "output_tokens": int|None, "handle"?: str}
#
# `handle` appears only for a provider that MINTS the conversation id
# itself (agy); see `Turn`.

#: Reads are fenced to the workspace by rules the CLI enforces.
READ_SCOPE_WORKSPACE = "workspace"
#: Reads are bounded only by what the OS account can open. NOT a
#: synonym for "everything is allowed": writing, shell and outbound
#: fetch stay denied. It is the READ surface that has no fence.
READ_SCOPE_PROCESS = "process"

_SCOPE_NOTE = {
    READ_SCOPE_WORKSPACE: (
        "answers are about this page; it reads this workspace only — "
        "read-only, it explains, it never acts"),
    READ_SCOPE_PROCESS: (
        "answers are about this page; this backend cannot be scoped — "
        "it can read any file your computer account can read, not just "
        "this workspace. it still never writes, runs or fetches"),
}


@dataclass(frozen=True)
class Turn:
    """One question's resume state.

    `handle` is whatever identifies the conversation for THIS provider:
    a caller-minted uuid for claude, the CLI-minted conversation id for
    agy, and None where there is no resume at all. `resume` says
    whether this invocation continues `handle` or opens it.
    """

    handle: "str | None"
    resume: bool


def remembers(provider: "str | None") -> bool:
    """Can a second question reach the first one's context?

    Reads the DECLARATION. `RESUME_UNDECLARED` counts as no — an
    unmeasured backend must not be credited with a memory nobody
    observed (`capabilities`' whole default policy).
    """
    return capabilities.capabilities_for(provider).session_resume in (
        capabilities.RESUME_CALLER_SESSION_ID,
        capabilities.RESUME_PROVIDER_CONVERSATION_ID,
    )


def plan_turn(provider: "str | None", prior: "str | None") -> Turn:
    """The resume state for the next question, from the declaration.

    `prior` is the handle the last answer left behind (None = cold).
    """
    shape = capabilities.capabilities_for(provider).session_resume
    if shape == capabilities.RESUME_CALLER_SESSION_ID:
        # The framework owns the identifier: mint one now so the cold
        # call can pin it and every later call replay it.
        return Turn(handle=prior or str(uuid.uuid4()), resume=prior is not None)
    if shape == capabilities.RESUME_PROVIDER_CONVERSATION_ID:
        # Nothing to pin on the cold call — the id arrives in the
        # provider's own output and is replayed afterwards.
        return Turn(handle=prior, resume=prior is not None)
    return Turn(handle=None, resume=False)


# ------------------------------------------------------------ backends


class _Backend:
    """One provider's dialect. Subclasses fill in argv/env/reader."""

    #: canonical provider name in `llm/capabilities.py`
    name: str = ""
    #: what the drawer offers, cheapest first; index 1 is the default
    models: "tuple[str, ...]" = ()
    default_model: str = ""
    read_scope: str = READ_SCOPE_PROCESS

    def executable(self) -> "str | None":
        """The launchable CLI, or None. Delegates to the one resolver
        the drift guard already owns — a second `shutil.which` here is
        how `serve/app.claude_exe` and `drift_guard` came to disagree
        about whether claude was installed."""
        return drift_guard.resolve_executable(self.name)

    # -- construction ---------------------------------------------------

    def argv(self, *, exe: str, workspace: Path, system: str, prompt: str,
             model: str, turn: Turn, timeout_sec: int) -> "list[str]":
        raise NotImplementedError

    def env(self, workspace: Path) -> "dict[str, str]":
        raise NotImplementedError

    def reader(self, proc: "subprocess.Popen",
               out: "queue.Queue[dict | None]") -> None:
        raise NotImplementedError

    def launch(self, *, workspace: Path, system: str, prompt: str,
               model: str, turn: Turn, timeout_sec: int
               ) -> "tuple[list[str], dict[str, str]]":
        exe = self.executable()
        if not exe:  # pragma: no cover — the endpoint gates on this first
            raise FileNotFoundError(f"{self.name} CLI not found")
        return (self.argv(exe=exe, workspace=workspace, system=system,
                          prompt=prompt, model=model, turn=turn,
                          timeout_sec=timeout_sec),
                self.env(workspace))


class ClaudeExplainer(_Backend):
    """claude — the original, unchanged.

    Every flag below was already on the wire before this module existed;
    it moved here verbatim so that "what claude grants" and "what agy
    grants" can be read side by side. The read fence is the pair
    `--tools` (no write tool exists in the set at all) + `--allowedTools`
    (path patterns), and it is a real fence: claude declares
    `ENFORCEMENT_HARD`.
    """

    name = "claude"
    models = ("haiku", "sonnet", "opus")   # CLI aliases, cheapest first
    default_model = "sonnet"
    read_scope = READ_SCOPE_WORKSPACE

    #: The public notes site doubles as the mechanism knowledge base for
    #: zip installs (no docs/ in the package; user call 2026-07-18:
    #: fetch live, don't bundle).
    notes_domain = os.environ.get(
        "ASTERISM_EXPLAINER_NOTES_DOMAIN", "andersonwu2000.github.io")

    def allowed_tools(self, workspace: Path) -> str:
        ws = workspace.as_posix()
        patterns = [
            f"Read({ws}/Problems/**)", f"Grep({ws}/Problems/**)",
            f"Read({ws}/Library/**/*.lean)", f"Grep({ws}/Library/**)",
            f"Read({ws}/Papers/**/*.md)", f"Grep({ws}/Papers/**)",
            # dev machines carry design docs in-repo; absent in zip installs
            f"Read({ws}/docs/**/*.md)", f"Grep({ws}/docs/**)",
            f"Glob({ws}/**)",
            f"WebFetch(domain:{self.notes_domain})",
        ]
        return " ".join(patterns)

    def argv(self, *, exe: str, workspace: Path, system: str, prompt: str,
             model: str, turn: Turn, timeout_sec: int) -> "list[str]":
        from .claude_cli import (_operator_state_deny_rules,
                                 _spawn_guard_settings_path)
        # No handle = the declaration says this backend resumes nothing,
        # so nothing is pinned and nothing is replayed. Wired here rather
        # than assumed: `-p` without `--session-id` is a legal, one-shot
        # claude invocation, and that is exactly the honest shape for a
        # provider whose `session_resume` is `none`/`undeclared`.
        session_flags: "list[str]" = []
        if turn.handle:
            session_flags = (["--resume", turn.handle] if turn.resume
                             else ["--session-id", turn.handle])
        return [
            exe,
            "--model", model,
            "-p", prompt,
            "--append-system-prompt", system,
            # read-only surface: no Write/Edit/Bash in the tool set at all;
            # deny rules below are belt-over-braces for operator state
            "--tools", "Read Grep Glob WebFetch",
            "--allowed-tools", self.allowed_tools(workspace),
            "--disallowedTools",
            "Read(**/.env)", "Read(**/.env.*)",
            *_operator_state_deny_rules(),
            "--settings", str(_spawn_guard_settings_path()),
            # no turn cap flag in this CLI — the endpoint's wall timeout is
            # the runaway stop
            "--output-format", "stream-json", "--verbose",
            "--include-partial-messages",
            "--setting-sources", "",
            "--disable-slash-commands",
            "--exclude-dynamic-system-prompt-sections",
            *session_flags,
        ]

    def env(self, workspace: Path) -> "dict[str, str]":
        env = dict(os.environ)
        env["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] = "1"
        return env

    def reader(self, proc: "subprocess.Popen",
               out: "queue.Queue[dict | None]") -> None:
        """stdout JSONL → UI events. Runs on its own thread; the SSE
        generator drains the queue. None = stream ended."""
        try:
            assert proc.stdout is not None
            for raw in proc.stdout:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    obj = json.loads(raw)
                except ValueError:
                    continue
                t = obj.get("type")
                if t == "system" and obj.get("subtype") == "init":
                    out.put({"type": "status", "stage": "thinking"})
                elif t == "stream_event":
                    ev = obj.get("event") or {}
                    et = ev.get("type")
                    if et == "content_block_start":
                        cb = ev.get("content_block") or {}
                        if cb.get("type") == "tool_use":
                            out.put({"type": "status", "stage": "reading",
                                     "tool": str(cb.get("name") or "")})
                        elif cb.get("type") == "thinking":
                            out.put({"type": "status", "stage": "thinking"})
                    elif et == "content_block_delta":
                        d = ev.get("delta") or {}
                        if d.get("type") == "text_delta":
                            txt = d.get("text")
                            if isinstance(txt, str) and txt:
                                out.put({"type": "delta", "text": txt})
                elif t == "result":
                    usage = obj.get("usage") or {}
                    out.put({
                        "type": "done",
                        "ok": not bool(obj.get("is_error")),
                        "subtype": str(obj.get("subtype") or ""),
                        "turns": obj.get("num_turns"),
                        "output_tokens": usage.get("output_tokens"),
                    })
        finally:
            out.put(None)


class AntigravityExplainer(_Backend):
    """agy — same READ-ONLY intent, rendered in the dialect it has.

    Three things are not translations of claude's flags but different
    facts, and each is wired rather than commented:

    * NO system-prompt flag exists (`agy --help`, 1.1.11, 2026-08-10),
      so the explainer's rules are prepended to the prompt body. They
      are instructions either way; what changes is that the user's
      question and the rules share one channel.
    * NO stream (`capabilities.stream_events=False`): one JSON envelope
      at the end. The drawer therefore sits on "thinking…" for the whole
      answer and receives it in one delta. That is a visible
      degradation and it is the declaration's, not a bug to work around
      — `agy --help` on 1.1.11 does advertise `--output-format
      stream-json`, but whether it is INCREMENTAL has not been measured
      here, and a consumer that assumes it is would be inventing the
      one thing this package exists to stop.
    * The capability envelope is a HOME, not flags (`agy --help` has no
      config flag; measured 2026-08-01 — agy authenticates normally
      under a fake HOME). The explainer builds its own under
      `.asterism/`, deliberately NOT reusing the operator's global
      settings.json: that file grants `write_file(<ws>/.attempts)` for
      the engine, and an explainer must not inherit a write root.
    """

    name = "antigravity"
    # From `agy models` on 1.1.11 (2026-08-10 — the entitlement list of
    # this account, not a guess). Cheapest first, same shape as claude's
    # haiku/sonnet/opus ladder, and the middle rung is the default for
    # the same reason.
    models = ("gemini-3.6-flash-low", "gemini-3.6-flash-high",
              "gemini-3.1-pro-high")
    default_model = "gemini-3.6-flash-high"
    read_scope = READ_SCOPE_PROCESS

    #: agy's own clock must fire before the endpoint's wall, so the
    #: death arrives as a classifiable envelope instead of a kill.
    _wall_slack_sec = 15

    def home(self, workspace: Path) -> Path:
        """This explainer's private HOME, built fresh each launch.

        `.asterism/` is the workspace's machine-generated runtime state
        (gitignored in full) — the same home the drift guard's snapshot
        chose, for the same reason: it depends on this machine, not on
        the repo.
        """
        home = workspace / ".asterism" / "explainer_agy_home"
        (home / ".gemini" / "antigravity-cli").mkdir(parents=True,
                                                     exist_ok=True)
        (home / ".gemini" / "antigravity-cli" / "settings.json").write_text(
            json.dumps(self.permissions(workspace), indent=2),
            encoding="utf-8")
        return home

    def permissions(self, workspace: Path) -> dict:
        """The read-only posture in agy's dialect.

        The fence that actually holds is the Ask DEFAULT: an action with
        no matching rule is auto-denied headless (measured 2026-07-30,
        four probes), so granting nothing IS the deny. The explicit
        denies are belt-over-braces and are also documentation — a
        reader must be able to see that shell, writes and outbound fetch
        were considered and refused, rather than infer it from an empty
        list. (`write_file(*)`: the `*` matcher is measured for
        `command`, NOT for `write_file`; if agy ignores the wildcard the
        rule simply fails to match and the Ask default still denies —
        the failure direction is closed, which is why it is safe to
        write an unmeasured rule here.)

        There is deliberately NO `read_file` rule. Adding one would be
        decorative: agy honours neither allow nor deny for that action
        (three probes, 1.1.11, 2026-08-10), and a decorative rule is
        worse than none because the next reader believes reads are
        fenced. `read_scope` above carries the truth instead.
        """
        return {
            "permissions": {
                "allow": [],
                "deny": ["command(*)", "read_url(*)", "write_file(*)",
                         f"write_file({workspace})"],
            },
            "trustedWorkspaces": [str(workspace)],
        }

    def argv(self, *, exe: str, workspace: Path, system: str, prompt: str,
             model: str, turn: Turn, timeout_sec: int) -> "list[str]":
        print_timeout = max(60, int(timeout_sec) - self._wall_slack_sec)
        cmd = [
            exe,
            "-p", f"{system}\n\n{prompt}",
            "--model", model,
            "--output-format", "json",
            "--print-timeout", f"{print_timeout}s",
            "--disable-slash-commands",
        ]
        if turn.resume and turn.handle:
            cmd += ["--conversation", turn.handle]
        # No --dangerously-skip-permissions, no --mode, no --sandbox:
        # antigravity_cli AUTHORIZED OPERATIONS §4 applies here too.
        return cmd

    def env(self, workspace: Path) -> "dict[str, str]":
        from .antigravity_cli import _spawn_env
        return _spawn_env(self.home(workspace))

    def reader(self, proc: "subprocess.Popen",
               out: "queue.Queue[dict | None]") -> None:
        """One envelope at the end → one delta plus done.

        The whole answer arrives at once because that is all the
        provider emits; inventing intermediate `status` events here
        would manufacture the appearance of progress from nothing.
        """
        from .antigravity_cli import _parse_envelope
        try:
            assert proc.stdout is not None
            raw = proc.stdout.read() or ""
            envelope = _parse_envelope(raw) or {}
            text = str(envelope.get("response") or "")
            if text:
                out.put({"type": "delta", "text": text})
            usage = envelope.get("usage") or {}
            status = str(envelope.get("status") or "")
            conversation = str(envelope.get("conversation_id") or "")
            done: dict = {
                "type": "done",
                # SUCCESS is not proof of work and ERROR is not proof of
                # failure (antigravity_cli, THE HAZARD): here the artifact
                # IS the response text, so it decides.
                "ok": bool(text) and status.upper() == "SUCCESS",
                "subtype": status.lower() or "no_envelope",
                "turns": envelope.get("num_turns"),
                "output_tokens": usage.get("output_tokens"),
            }
            if conversation:
                done["handle"] = conversation
            out.put(done)
        finally:
            out.put(None)


CLAUDE = ClaudeExplainer()
ANTIGRAVITY = AntigravityExplainer()

#: canonical provider name -> backend. A provider ABSENT here has no
#: explainer at all and is refused by name; it never falls through to
#: claude's flags (which is what "hardwired to claude" looked like from
#: the inside).
BACKENDS: "dict[str, _Backend]" = {
    CLAUDE.name: CLAUDE,
    ANTIGRAVITY.name: ANTIGRAVITY,
}

#: The pipeline kind the explainer is seated as — so it resolves through
#: the same chain every other seat does (`<kind>.provider` →
#: `ASTERISM_<KIND>_PROVIDER` → `ASTERISM_LLM_PROVIDER` → claude) and an
#: installer that writes a provider default reaches it.
KIND = "explainer"


def provider(workspace: "Path | None" = None) -> str:
    """Which provider the explainer is seated on right now.

    Read per call, not cached: `Asterism.yaml` is live-editable and the
    console outlives any one setting (`capabilities.provider_for_kind`
    makes the same point for pipeline seats). `workspace` is the one
    serve must pass — it is not launched from the workspace root, and a
    seat read from the wrong directory is a seat nobody chose.
    """
    return capabilities.provider_for_kind(KIND, workspace)


def backend_for(name: "str | None") -> "_Backend | None":
    return BACKENDS.get(capabilities.canonical(name))


def read_scope(name: "str | None") -> str:
    b = backend_for(name)
    return b.read_scope if b else READ_SCOPE_PROCESS


def scope_note(name: "str | None") -> str:
    """The one sentence the drawer shows about what this backend may
    read. Derived from the declaration, so it cannot drift into
    flattery for a backend that acquires a different answer."""
    return _SCOPE_NOTE[read_scope(name)]


def availability(name: "str | None") -> "tuple[bool, str]":
    """(usable, why not) for the seated provider.

    The message is the teaching part: a 503 that says "Claude Code is
    not installed" on a machine seated on agy sends the reader to fix
    the wrong thing.
    """
    canon = capabilities.canonical(name)
    backend = BACKENDS.get(canon)
    if backend is None:
        return False, (
            f"the explainer has no backend for provider {canon!r} — it "
            f"needs a CLI that can read the workspace. Available: "
            f"{', '.join(sorted(BACKENDS))}. Set `{KIND}.provider` in "
            f"Asterism.yaml (or ASTERISM_{KIND.upper()}_PROVIDER).")
    if not backend.executable():
        return False, (
            f"the explainer is seated on {canon!r} and its CLI is not "
            f"installed on this machine. Install it, or point "
            f"`{KIND}.provider` in Asterism.yaml at a backend that is "
            f"({', '.join(sorted(BACKENDS))}).")
    return True, ""
