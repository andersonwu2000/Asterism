"""What each provider CAN ANSWER — declared once, by the provider.

`llm/base.py` says a Provider is one method, `spawn(req) -> int`, and
that is right: the ACTION is uniform. What is not uniform is what the
backend can tell us about that action, and every one of those gaps
arrived in core as an `if provider == "<name>"`:

  * `core/quota.py` registered `_no_endpoint` against the literal
    string `"antigravity"`, because agy has no usage API at all.
  * `state/failures.rc_to_reason` reads claude's rc vocabulary, while
    `antigravity_cli._classify` exists solely to manufacture that
    vocabulary out of an envelope, because agy exits 1 for every error.
  * the stream watchdog (`claude_cli._watchdog` + `stream_parser`) is
    claude-only; an agy spawn runs with no parser at all, and the
    retry helper's timeout branch still printed a confident
    `[detector verdict: active]` for it — a detector that never ran.
  * `--resume <uuid>` vs agy's minted `conversation_id`.
  * agy's permission surface enforces `deny` absolutely and IGNORES
    `allow` for `read_url` (11 probes, 2026-07-30) — "the permission
    file says X" is not the same sentence on both providers.

A name-keyed special case is invisible to the next backend. `codex` is
coming and an OpenAI-compatible HTTP provider is already here; each one
that is not thought about inherits whatever the branch's `else` happened
to be. That is not hypothetical: on 2026-08-07 the quota ledger spoke
seat names while the dispatcher asked in queue kinds and BOTH halves
silently no-oped for an hour, because a lookup miss returned a
plausible-looking `None`.

So the gaps become a DECLARATION the provider owns, and the consumers
read the declaration. The defaults on `ProviderCapabilities` are all
the "we were never told" values — a new backend that declares nothing
gets `rc_contract='undeclared'`, `usage_endpoint=False`,
`stream_events=False`, and every consumer degrades conservatively. It
cannot inherit a safe-looking answer it never gave. That mirrors the
2026-08-08 `unclassified_spawn_failure` ruling one level up: an unknown
must not masquerade as a confident answer.

WHERE `undeclared` IS DECIDED: exactly one consumer — rc
classification (`state/failures.rc_to_reason` +
`pipeline._spawn_failure`). See `RC_UNDECLARED` below for the ruling
and why it is degradation-plus-warning rather than refuse-to-dispatch.

A CONSEQUENCE, written down so it is not re-litigated: a provider with
`usage_endpoint=False` can never receive a POSITIVE quota confirmation.
`core/quota_wait` only sleeps to a `resets_at` the endpoint stated, and
the dispatcher's breaker charges a spawn that died without a recognised
quota marker as an agent failure. So an agy timeout is billed to the
agent even when the true cause was a silent throttle. That is the
correct consequence of `usage_endpoint=False`, not agy being treated
unfairly: the framework declines to invent a confirmation nobody gave
it. The cure is an endpoint, not a heuristic.

ALSO RECORDED (production data, both providers, all of 2026-07/08):
neither CLI takes a per-directory single-instance lock. `dispatch.pool`
= 4 concurrent spawns share one `Problems/<p>/` cwd all day, on claude
and on agy, with no contention and no lockfile. An external project hit
exactly such a lock with a different CLI; ours is clear, so a future
reader does not have to re-derive it. `single_instance_lock` carries
the fact per provider.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, replace as _dc_replace
from pathlib import Path

# --------------------------------------------------------------- rc

#: The provider's exit codes mean what `llm/base.py::SpawnRC` says they
#: mean: 0/124/125/126/127/128/129 are a vocabulary, and an rc outside
#: it is a real, provider-authored error signal.
RC_STRUCTURED = "structured"
#: The process rc carries NO information and must not be read as one.
#: agy exits 1 for every ERROR envelope regardless of cause — a bad
#: model slug, a refused credential and a transient blip are the same
#: integer (`antigravity_cli._classify`, which exists because of this).
#: A consumer that reads such an rc as a cause is guessing.
RC_UNINFORMATIVE = "uninformative"
#: Nobody ever said. The DEFAULT, and it must stay the default: the
#: cost of a wrong guess here is a goal charged for a failure whose
#: cause was mechanical (the 2026-08-08 post-mortem: six OS-level exits
#: burned attempts and shoved five healthy goals into review).
#:
#: THE RULING (one consumer, one decision — rc classification):
#: `undeclared` degrades exactly like `uninformative` — an rc outside
#: the framework vocabulary becomes `unclassified_spawn_failure`, which
#: does not charge the goal and whose repetition escalates to the
#: OPERATOR — and additionally emits a one-time `[capabilities]`
#: warning naming the provider.
#:
#: Why not refuse to dispatch: adding a backend would then be a
#: two-step landing whose first step is a dead framework, and the
#: pressure would be to paste a declaration nobody measured — which is
#: worse than an honest "undeclared". Why not warn-only: a warning that
#: leaves the permissive reading in place IS the unknown masquerading
#: as an answer. Degrade AND warn is the only pair that keeps both.
RC_UNDECLARED = "undeclared"

# ------------------------------------------------------ session resume

#: Caller mints the id and pins it (`--session-id`), then replays it
#: (`--resume`). The framework owns the identifier.
RESUME_CALLER_SESSION_ID = "caller_session_id"
#: The CLI MINTS the id and reports it back; resuming means recording
#: it on the cold call and replaying it (`--conversation <id>`). agy.
#: Consequence the Strategist paid for: without the recorded map a
#: retry cannot resume, so a bare rebuttal would reach an amnesiac
#: agent — `antigravity_cli._build_prompt` falls back to the full
#: prompt rather than waste the round.
RESUME_PROVIDER_CONVERSATION_ID = "provider_conversation_id"
#: No resume of any kind; every invocation is a fresh context.
RESUME_NONE = "none"
RESUME_UNDECLARED = "undeclared"

# --------------------------------------------- permission enforcement

#: Every rule in the permission surface is enforced as written.
ENFORCEMENT_HARD = "hard"
#: `deny` is absolute, `allow` is not universally honoured. MEASURED on
#: agy 2026-07-30 (11 + 4 probes): a `read_url` ALLOW is ignored in
#: every scoping form (it fetches with no rule at all), while a
#: `read_url(*)` DENY blocks even with an exact-URL allow beside it; and
#: the `command` matcher takes only a full literal or `*`, nothing
#: between. So a capability is safe to REMOVE here and never safe to
#: narrow — the closed posture (deny `command(*)` + `read_url(*)`, reach
#: everything else over MCP) is a consequence of this field, not a
#: preference.
ENFORCEMENT_DENY_ONLY = "deny_only"
#: No enforceable tool surface (the OpenAI HTTP provider has no tools).
ENFORCEMENT_NOT_APPLICABLE = "not_applicable"
ENFORCEMENT_UNDECLARED = "undeclared"

#: Which ACTIONS a provider actually honours an `allow` rule for
#: (2026-08-10 owner call). The single `enforcement_strength` string
#: above was itself a flattening — agy's real behaviour is per action,
#: not per provider, and the coarse word hid the one case that bites:
#:
#:   write_file  allow ENFORCED   (a write into `.attempts` landed; the
#:                                 same write into `Problems/` came back
#:                                 "Matches user-configured deny rule")
#:   mcp         allow ENFORCED   (no rule at all → auto-denied headless)
#:   command     allow enforced, but the matcher takes only a full
#:               literal or `*` — nothing between (7 probes)
#:   read_url    allow IGNORED    (fetches with no rule, every scoping
#:                                 form) — deny is the ONLY control
#:   read_file   allow ENFORCED and SCOPING (re-measured 2026-08-10, five
#:               probes in `_spike/p162/`): no matching allow → denied,
#:               a deny inside an allowed tree wins for that subtree.
#:               It was declared unenforceable here that morning on the
#:               strength of an earlier series that read the silent
#:               auto-deny as a successful read — the two are
#:               indistinguishable from outside the process.
#:
#: The trap this exists to catch: a future edit that tries to NARROW an
#: unenforceable action by writing an allow rule — e.g. "allow only
#: arxiv.org" for `read_url` — produces UNRESTRICTED fetching on agy, not
#: narrowed fetching, and says nothing while doing it. For a benchmark an
#: ungated outbound fetch is a validity problem (a route to a published
#: solution) before it is a security one.
#:
#: Enforced by a static invariant test, deliberately NOT by a runtime
#: gate: this condition can only be created by editing the permission
#: renderer, and a code edit is what tests are for. A runtime check would
#: add a production failure mode for a state production cannot reach.
ALLOW_HONOURED_ALL = frozenset({"*"})  # every action (claude, hard)
ALLOW_HONOURED_NONE: frozenset = frozenset()   # no tool surface at all

#: Reading a file — named because it is the action whose absence from a
#: provider's honoured set changes what a FEATURE can promise, not just
#: what a spawn may do. The console explainer is scoped to the workspace
#: on a provider that honours it and scoped to the OS account on one
#: that does not (`llm/explainer.py` publishes which).
ACTION_READ_FILE = "read_file"

# ------------------------------------------------------- provisioning
#
# The installer needs three facts before it can offer a provider, and
# until 2026-08-10 all three lived in prose: the install one-liner in
# `setup-orchestrator.ps1`, the auth story in `antigravity_cli`'s header,
# and the readability of auth state only in the negative — a comment in
# serve's accounts panel explaining why agy has no `logged_in`.
#
# They belong here for the same reason `rc_contract` does. An installer
# that writes `if provider == "antigravity"` is guessing from the name,
# grows a branch per backend, and is exactly what this module exists to
# stop. The scope of the module was never "runtime only" — `version_argv`
# and `tested_version` already ask about the BINARY, not about a spawn.
# The line that matters is declaration vs observation: what is true of
# this provider everywhere lives here; whether THIS machine has it
# installed and authenticated is measured by the caller and never cached.

#: The installer can run `install_command`.
INSTALL_BY_COMMAND = "by_command"
#: Nothing to install — the HTTP providers are a library call.
INSTALL_NOT_NEEDED = "not_needed"
#: Nobody wrote one down, or it cannot be automated (the Antigravity IDE
#: is a GUI login). Renders as "you do this part".
INSTALL_UNDECLARED = "undeclared"

#: The vendor's own OAuth, with its own credential file.
AUTH_OWN_OAUTH = "own_oauth"
#: Rides an already-signed-in session belonging to another product. agy
#: takes the Antigravity IDE's — there is no login step and no file we
#: own, which also makes the IDE session load-bearing state.
AUTH_BORROWED_SESSION = "borrowed_session"
#: A key from the environment or config.
AUTH_API_KEY = "api_key"
AUTH_UNDECLARED = "undeclared"

#: The framework can read the credential state locally (a file, an env
#: var) and answer "authenticated?" without a call.
AUTH_STATE_READABLE = "readable"
#: There IS no local answer. agy authenticates fine from a fake HOME, so
#: no file on this machine decides it; only a live call does.
AUTH_STATE_OPAQUE = "opaque"
AUTH_STATE_UNDECLARED = "undeclared"

# ---------------------------------------------------- liveness clocks

#: Silence measured on the raw event stream (any delta counts).
LIVENESS_STREAM = "stream"
#: Silence measured on tool-call cadence (`tool_use` events).
LIVENESS_TOOL = "tool"
#: The provider emits nothing incremental, so NO silence clock exists
#: and the overall wall timeout is the whole liveness guarantee. This
#: is a degradation, and it is named so that a consumer can say so out
#: loud instead of reporting an observation it never made.
LIVENESS_TIMEOUT_ONLY = "timeout"

#: Kinds whose silence is STREAM idleness rather than tool cadence.
#: A property of the KIND, not the provider: the tool clock was built
#: for the formalizer family, where thinking-instead-of-acting is the
#: failure and a tool call every few seconds is health. The NL layer's
#: work IS the thinking, and measuring it on tool cadence killed seven
#: healthy Strategist spawns in one day (2026-08-07, sonnet-5 + opus-5:
#: four minutes into one thinking block the tool clock read 240s of
#: silence while the stream had never been quiet for 3.5s). Lives here
#: rather than in `claude_cli` because the choice is now made through
#: `liveness_clock`, which every provider consults.
STREAM_IDLE_KINDS: "frozenset[str]" = frozenset({"strategist", "adversary"})


@dataclass(frozen=True)
class ProviderCapabilities:
    """One provider's answer to "what can you tell us?".

    EVERY default is the pessimistic / unknown value. Constructing
    `ProviderCapabilities(name='no-such-backend')` yields one that cannot
    report quota, emits no stream, resumes nothing, has an undeclared
    rc contract and an undeclared enforcement surface — which is the
    truth about a backend nobody has measured.
    """

    name: str
    #: Can we ASK how much quota is left? claude: yes (the subscription
    #: usage endpoint, `core/usage_quota.fetch_usage`). agy: NO —
    #: verified 2026-08-07, `agy --help` carries no usage/quota
    #: subcommand, and re-verified against agy 1.1.11 on 2026-08-09.
    #: Read by `core/quota` to decide whether a provider gets a live
    #: probe or only the observed-from-failures channel.
    usage_endpoint: bool = False
    #: The THIRD shape of the same question, and it needs its own field
    #: rather than a third state on the boolean above, because the two
    #: are answered by different machinery at different times. codex
    #: cannot be ASKED how much quota is left — but it WRITES the answer
    #: (`rate_limits`: used_percent / window_minutes / resets_at /
    #: rate_limit_reached_type) into its own rollout file, once per turn.
    #: With a per-spawn CODEX_HOME that file is the spawn's private
    #: ledger, so the reading is exact and needs no attribution. What it
    #: is NOT: a pre-flight probe. Nothing can be known before the first
    #: spawn of a window, which is why this does not set
    #: `usage_endpoint` — a consumer that wants to ask BEFORE spending
    #: must still treat this provider as unmeasurable.
    usage_from_session_log: bool = False
    #: Can this provider SAY when a spent window reopens? Independent of
    #: both fields above, because the material differs: agy has no usage
    #: API at all yet its refusal carries "Resets in 2h46m25s", and codex
    #: has no endpoint yet writes `resets_at` into its own rollout. What
    #: the consumer needs is neither an endpoint nor a log format, just
    #: "is there an epoch to sleep to" — `core.quota.reset_epoch` reads
    #: this and dispatches to the wired source. False means the caller
    #: must fall back to its blind backoff instead of inventing a time.
    states_quota_reset: bool = False
    #: The HTTPS host this provider's CLI must reach to work at all —
    #: the network-park probe's first target (`core/network_wait`,
    #: 2026-08-18). None = undeclared; the probe falls back to its
    #: generic anchors. Declare only a VERIFIED host (the 08-17/18
    #: outage verified both live ones: claude stayed alive on
    #: api.anthropic.com over IPv6 while codex died with chatgpt.com).
    api_host: "str | None" = None
    #: Does the CLI emit parseable incremental events? claude: yes
    #: (`--output-format stream-json --include-partial-messages`, which
    #: `llm/stream_parser.py` consumes). agy: no — one JSON envelope at
    #: the end and nothing before it. False means the watchdog has
    #: nothing to sample and the retry helper must NOT report a
    #: detector verdict.
    stream_events: bool = False
    #: …and are those events FINER than one per tool call? The stream
    #: clock exists to tell "four minutes into one thinking block" apart
    #: from "dead", and only a text/thinking delta can do that: claude
    #: emits one every ~1.5s, codex emits none at all (agent prose
    #: arrives whole inside `item.completed`). Without this field a
    #: `stream_events=True` codex would be handed the stream clock and
    #: measure a healthy NL spawn as silent — the 2026-08-07 failure,
    #: rebuilt out of a coarser stream instead of the wrong clock.
    #: Meaningless when `stream_events` is False; `liveness_clock` reads
    #: the pair.
    stream_text_deltas: bool = False
    #: How a second turn reaches the first turn's memory.
    session_resume: str = RESUME_UNDECLARED
    #: What the process exit code means. TRI-STATE — see the RC_*
    #: constants; `undeclared` is the default on purpose.
    rc_contract: str = RC_UNDECLARED
    #: Is the tool-permission surface a hard boundary or advisory?
    enforcement_strength: str = ENFORCEMENT_UNDECLARED
    #: Does a worker on this backend have file tools of its OWN — a
    #: Read, a Grep — or does every byte of the workspace arrive through
    #: our MCP (`inspect`)? The prompts state a tool list in their first
    #: line, and that line was written for claude: a codex worker was
    #: told it had `Read / Grep / Write / Edit` and had none of them, so
    #: it spent two turns enumerating `ALL_TOOLS` to find out what it
    #: really had (2026-08-12 rollout). This is what the tool line is
    #: rendered from, so the fact has one home instead of a copy per
    #: prompt file. Default FALSE is the pessimistic answer for the same
    #: reason as every other field here: promising a tool that is not
    #: there is the failure that was measured; the reverse is not.
    native_file_tools: bool = False
    #: The largest MCP tool result this backend DELIVERS to the model
    #: uncut, in chars — the transport's ceiling, which the framework's
    #: reply must respect because whole queries can be deferred by name
    #: at the source (`knowledge/workspace_query.run_queries`) while the
    #: transport can only amputate. None = nobody has measured this
    #: backend; NO ceiling is applied — a guessed number would re-ration
    #: a channel that delivers whole. A backend that declares one must
    #: also render it into the tools server's env
    #: (`ASTERISM_INSPECT_DELIVERY_CHARS`) in its own adapter.
    mcp_result_delivery_chars: "int | None" = None
    #: The ACTIONS whose `allow` rules this provider actually honours —
    #: `{"*"}` for all, `frozenset()` for none. `enforcement_strength`
    #: above is the headline; this is the fact a gate can act on, because
    #: the headline word ("deny_only") averages over actions that behave
    #: differently. Default empty = "nothing is known to be grantable",
    #: so an undeclared provider cannot silently be handed a capability
    #: the framework merely ASSUMES will be enforced.
    allow_honoured_actions: frozenset = ALLOW_HONOURED_NONE
    #: The CLI version everything above was VERIFIED against, and the
    #: version that validated `marker_tables`. Version equality alone
    #: cannot catch a server-side wording change, which is why
    #: `llm/drift_guard.py` also diffs a behaviour snapshot — but when
    #: a marker stops matching, the first question is "validated
    #: against which version?" and this is the answer.
    tested_version: "str | None" = None
    #: Dotted paths of the STRING-MATCH tables validated at
    #: `tested_version`. These are the most brittle thing in the
    #: system: every quota / misconfig / timeout / stale-session
    #: detector is a substring test against vendor prose that can
    #: change without a version bump. Naming them here lets the drift
    #: guard say WHICH tables a warning puts in doubt, and lets a test
    #: assert every named table still exists and is non-empty.
    marker_tables: "tuple[str, ...]" = ()
    #: Does the CLI take a per-directory single-instance lock? False
    #: for both live providers — production data, `dispatch.pool` = 4
    #: spawns sharing one problem directory all day for months, on
    #: claude and on agy, with no lockfile and no contention. Recorded
    #: because an external project DID hit such a lock with a different
    #: CLI; a future reader should not have to re-derive that ours is
    #: clear.
    single_instance_lock: bool = False
    #: argv tail that prints the version without touching the network
    #: or the quota. `()` = no free version probe.
    version_argv: "tuple[str, ...]" = ("--version",)

    # ------------------------------------------------- provisioning
    # How this backend gets onto a machine and proves it can be used.
    # Same rule as everything above: these are FACTS ABOUT THE PROVIDER,
    # constant across machines — not observations of this machine, which
    # belong to whoever probes (serve's accounts panel, the installer).
    #: `INSTALL_BY_COMMAND` / `INSTALL_NOT_NEEDED` / `INSTALL_UNDECLARED`.
    #: Split from the command itself because "there is nothing to
    #: install" and "nobody wrote down how" are different answers that a
    #: single nullable command would flatten into one.
    install_method: str = INSTALL_UNDECLARED
    #: Meaningful only under `INSTALL_BY_COMMAND` (invariant test pins
    #: the two together). A shell one-liner, run by the installer.
    install_command: "str | None" = None
    #: Where the credential comes from — see the AUTH_* constants.
    auth_flow: str = AUTH_UNDECLARED
    #: Under `AUTH_API_KEY`: the env var (also honoured as a `.env`
    #: line) that carries the key. Declared so serve's provider rows can
    #: report key-PRESENCE by looking for the line — never the value.
    #: None everywhere else (invariant test pins the pairing).
    env_key: "str | None" = None
    #: The executable this provider actually runs, when it is not the
    #: provider's own name — zen rides the codex binary, so an
    #: installed-check must resolve `codex`, not a `zen` that will never
    #: exist. None = "same as `name`" (every provider with its own CLI).
    exe_name: "str | None" = None
    #: Whether the framework can READ that credential's state locally.
    #: Tri-state on purpose: `opaque` means "no local answer exists",
    #: `undeclared` means "nobody has looked", and an installer renders
    #: those differently — the first offers a live probe, the second
    #: says do it yourself.
    auth_state: str = AUTH_STATE_UNDECLARED
    #: argv tail for a NON-spawn call that only a usable install can
    #: answer — the honest readiness check where `auth_state` is opaque.
    #: Costs a round-trip, no tokens. `()` = none known.
    readiness_argv: "tuple[str, ...]" = ()
    notes: str = ""

    @property
    def declared(self) -> bool:
        """False for a backend that never declared its rc contract —
        the single flag consumers use to decide whether to warn."""
        return self.rc_contract != RC_UNDECLARED


def _undeclared(name: str) -> ProviderCapabilities:
    """A provider nobody has measured. Every field pessimistic."""
    return ProviderCapabilities(
        name=name,
        notes=("no declaration in llm/capabilities.py — every consumer "
               "degrades conservatively until one is measured"))


#: canonical provider name -> declaration. Keys match the names
#: `llm/get_provider` resolves; `ALIASES` covers the spellings config
#: accepts.
CAPABILITIES: "dict[str, ProviderCapabilities]" = {
    "claude": ProviderCapabilities(
        name="claude",
        usage_endpoint=True,
        # …AND it states its own reset time, which is not redundant with
        # the endpoint — it is the fallback for the one moment the
        # endpoint is least reliable. 2026-08-13: a five-hour window
        # died, every client asked the usage API at once, four
        # consecutive probes failed, and the daemon exited unable to
        # tell quota from a broken exe. The refusing spawn had carried
        # `resetsAt` in its own output the whole time.
        states_quota_reset=True,
        # Verified in the 08-17/18 split-stack outage: claude spawns
        # stayed alive on this host over IPv6 while the IPv4 default
        # route was dead.
        api_host="api.anthropic.com",
        stream_events=True,
        # `--include-partial-messages`: a `content_block_delta` every
        # ~1.5s inside a thinking block (measured 2026-08-07 on both
        # sonnet-5 and opus-5). This is what makes the stream clock
        # possible at all, and claude is the only backend that has it.
        stream_text_deltas=True,
        # Read / Grep / Glob / Write / Edit, and it prefers them:
        # measured on the 08-14 Test.provider_probe leg, 31 Read + 12
        # Grep against 9 `inspect` calls.
        native_file_tools=True,
        session_resume=RESUME_CALLER_SESSION_ID,
        rc_contract=RC_STRUCTURED,
        enforcement_strength=ENFORCEMENT_HARD,
        # Flags on the command line; what is granted is what applies.
        allow_honoured_actions=ALLOW_HONOURED_ALL,
        # Measured 2026-08-13 (`claude --version` → "2.1.226"), the
        # version whose refusal is the corpus in
        # `tests/test_quota_refusal.py`.
        tested_version="2.1.226",
        # This guard checks the tables EXIST, which is not the same as
        # checking they still match. `_QUOTA_MARKERS` passed it happily
        # for the six weeks its wording was stale (2026-08-13): the
        # stale-session marker beside it kept working — it reads stderr,
        # which stream-json never touched — so string matching looked
        # reliable from here while the quota half silently matched
        # nothing. The structured `rate_limit_event` path is the real
        # answer to that; the prose below it is the fallback.
        marker_tables=("Tooling.llm.claude_cli._QUOTA_PROSE_RE",
                       "Tooling.llm.claude_cli._STALE_SESSION_MARKER"),
        single_instance_lock=False,
        install_method=INSTALL_BY_COMMAND,
        # The one-liner `installer/setup-orchestrator.ps1` already runs.
        install_command="irm https://claude.ai/install.ps1 | iex",
        auth_flow=AUTH_OWN_OAUTH,
        # `~/.claude/.credentials.json` — serve's accounts panel reads
        # it for `logged_in` and the subscription tier.
        auth_state=AUTH_STATE_READABLE,
        # None needed: the credential file IS the answer, for free.
        readiness_argv=(),
        notes=("usage endpoint = the subscription usage API read by "
               "core/usage_quota; stream = stream-json + partial "
               "messages, the watchdog's only sampling surface"),
    ),
    "antigravity": ProviderCapabilities(
        name="antigravity",
        # NO usage API. Probed 2026-08-07 and re-probed against 1.1.11
        # on 2026-08-09: `agy --help` has no usage/quota subcommand.
        # Its exhaustion is knowable ONLY from a refusal it has already
        # made — `_QUOTA_MARKERS` → rc=126 → `Ledger.observe`.
        usage_endpoint=False,
        # False = "no liveness stream WE CAN SAMPLE", which as of
        # 1.1.11 is no longer the same sentence as "the CLI emits
        # nothing incremental". MEASURED 2026-08-10: `--output-format
        # stream-json` on 1.1.11 IS incremental —
        #   {"event":"init", ...}
        #   {"event":"step_update","step_update":{"state":"ACTIVE",
        #     "step_type":"agent_response","text_delta":"1. One is..."}}
        #   {"event":"step_update", ..., "state":"DONE","usage":{...}}
        # — first line at 2.9s, further lines spread over the turn. The
        # 1.1.8 measurement this entry was born with ("one envelope at
        # the end") has been overtaken by the vendor.
        #
        # The VALUE still holds, for a different reason than the one
        # originally written: `stream_parser.StreamParser` speaks
        # claude's `{"type":"stream_event","event":{...}}` dialect and
        # nothing else, so agy's stream is unsampled — there is no
        # detector, exactly as the consumers assume. What is missing is
        # a parser dialect, not a stream. Writing one would give agy a
        # real liveness clock (and its `text_delta` cadence is what the
        # stream clock wants); until then LIVENESS_TIMEOUT_ONLY is
        # correct and `[detector verdict: none]` stays true.
        #
        # HOW THIS SLIPPED: `tested_version` below was refreshed to
        # 1.1.11 on 2026-08-09 by running `--version`, while the facts
        # it vouches for were still the 1.1.8 ones. The field promises
        # "everything above was VERIFIED against this version" — so the
        # table caught the very disease it was built to cure. Re-measure
        # the FACTS when bumping the version, or the bump is a lie.
        stream_events=False,
        session_resume=RESUME_PROVIDER_CONVERSATION_ID,
        # agy exits 1 for EVERY ERROR envelope regardless of cause.
        rc_contract=RC_UNINFORMATIVE,
        # No usage API, but the refusal itself says when it comes back
        # ("Individual quota reached … Resets in 2h46m25s"), parsed by
        # `antigravity_cli._record_quota_reset`.
        states_quota_reset=True,
        # `deny` absolute, `allow` partly ignored (read_url) — 15 probes
        # on 2026-07-30; see ENFORCEMENT_DENY_ONLY.
        enforcement_strength=ENFORCEMENT_DENY_ONLY,
        # It has `read_file` — that is the whole reason the action below
        # is in `allow_honoured_actions` and has a scoping contract.
        native_file_tools=True,
        # Measured per action, NOT inferred from the headline word.
        # `read_url` is absent on purpose: its allow is ignored, so the
        # only control there is deny, and any attempt to narrow it with
        # an allow rule would silently open it wide.
        allow_honoured_actions=frozenset({"write_file", "mcp", "command",
                                          ACTION_READ_FILE}),
        # Interface claims in `antigravity_cli`'s module docstring were
        # measured against 1.1.8; the marker tables have been carried
        # forward unchanged since. Installed today: 1.1.11 (measured
        # 2026-08-09). An external project pins 1.1.10.
        tested_version="1.1.11",
        marker_tables=("Tooling.llm.antigravity_cli._QUOTA_MARKERS",
                       "Tooling.llm.antigravity_cli._MISCONFIG_MARKERS",
                       "Tooling.llm.antigravity_cli._TIMEOUT_MARKERS"),
        single_instance_lock=False,
        install_method=INSTALL_BY_COMMAND,
        install_command=("irm https://antigravity.google/cli/install.ps1 "
                         "| iex"),
        # No login step exists: agy picks up the Antigravity IDE's
        # already-signed-in session. Which makes that session
        # load-bearing state — signing out of the IDE costs a fresh
        # interactive login, and the token lives in Electron app
        # storage, so it cannot be backed up by copying.
        auth_flow=AUTH_BORROWED_SESSION,
        # …and therefore no file on this machine decides it. A spawn
        # authenticates normally from a FAKE HOME (measured 2026-08-01),
        # which is exactly why serve's accounts panel reports `installed`
        # and roles but no `logged_in`: there is nothing to read.
        auth_state=AUTH_STATE_OPAQUE,
        # The honest readiness check where nothing is readable. `agy
        # models` makes a server round-trip ("Fetching available
        # models…", ~2.5s, zero tokens) and returns THIS ACCOUNT's model
        # list, so it proves the binary reaches Google with some
        # identity — and the installer needs that list anyway.
        # NOT proof of the negative: this machine cannot produce an
        # unauthenticated control (the credential is the IDE's, and
        # logging out to test would cost a real login), so nobody has
        # measured how it fails without one. Report what it proves —
        # "reached the service and listed N models at HH:MM" — not
        # "logged in".
        readiness_argv=("models",),
        notes=("capability surface is a per-spawn HOME (no config "
               "flag); `status: SUCCESS` is not proof of work — the "
               "artifact on disk is"),
    ),
    "gemini": ProviderCapabilities(
        name="gemini",
        usage_endpoint=False,
        stream_events=False,
        # `gemini --resume` takes a session INDEX, not a UUID, so the
        # claude contract does not map; the provider ignores session_id
        # outright.
        session_resume=RESUME_NONE,
        # The CLI returns rc=0 even when every internal retry failed on
        # quota (observed: 5 attempts, all "You have exhausted your
        # capacity", final rc=0). An rc that is 0 on failure carries no
        # information — the provider infers from output presence.
        rc_contract=RC_UNINFORMATIVE,
        enforcement_strength=ENFORCEMENT_UNDECLARED,
        tested_version=None,
        single_instance_lock=False,
        notes=("API-key / enterprise Code Assist only since Google cut "
               "the individual tiers off 2026-06-18 — kept for those "
               "users; not exercised by this workspace, so nothing "
               "below the rc contract has been re-measured"),
    ),
    "openai": ProviderCapabilities(
        name="openai",
        usage_endpoint=False,
        stream_events=False,
        session_resume=RESUME_NONE,
        # In-process HTTP, not a subprocess: the rc is manufactured by
        # `openai_api.py` itself from the HTTP outcome, so it is a
        # structured framework value by construction (98 fence-parse,
        # 99 HTTP, 124 timeout, 127 unconfigured).
        rc_contract=RC_STRUCTURED,
        # No tools at all — single-shot fence parsing. There is no
        # permission surface to enforce, which is a property of the
        # provider, not an omission.
        enforcement_strength=ENFORCEMENT_NOT_APPLICABLE,
        # No tools to grant, so nothing is grantable — same empty set as
        # `undeclared`, reached for the opposite reason (known-none vs
        # unknown). `enforcement_strength` is what tells them apart.
        allow_honoured_actions=ALLOW_HONOURED_NONE,
        tested_version=None,
        version_argv=(),
        single_instance_lock=False,
        # There is no binary — the same fact that empties `version_argv`.
        # `not_needed` rather than `undeclared`: an installer should show
        # "nothing to install", not "you do this part".
        install_method=INSTALL_NOT_NEEDED,
        auth_flow=AUTH_API_KEY,
        # An env var / config key the framework reads directly.
        auth_state=AUTH_STATE_READABLE,
        notes="no subprocess, no CLI version to probe",
    ),
    "codex": ProviderCapabilities(
        name="codex",
        # Nothing to ask. See `usage_from_session_log` below for the
        # shape the answer actually takes.
        usage_endpoint=False,
        usage_from_session_log=True,
        # `rate_limits.primary.resets_at` in the same rollout event.
        states_quota_reset=True,
        # `StreamParser(dialect="codex")` consumes it: `turn.started`,
        # `item.started`/`item.completed` per tool call, `turn.completed`
        # with the turn's usage. So the tool-cadence clock and the token
        # books are real here.
        #
        # THE LIMIT, and it is a real one: codex emits NO text deltas —
        # agent prose arrives whole inside `item.completed`. The
        # stream-idle clock exists to tell "four minutes into one
        # thinking block" apart from "dead", and these events cannot do
        # that. So a formalizer on codex is fully covered while a
        # STRATEGIST or ADVERSARY on codex would be measured by a clock
        # that reads long, healthy thinking as silence — the exact
        # mistake that killed seven healthy claude spawns on 2026-08-07.
        # `STREAM_IDLE_KINDS` is what keeps that honest: those two kinds
        # ask for the stream clock, codex cannot serve it, and
        # `liveness_clock` must therefore hand them TIMEOUT_ONLY rather
        # than quietly substituting the tool clock.
        stream_events=True,
        # `codex exec resume <id>` on an id CODEX mints and reports in
        # `thread.started` — the agy contract, not claude's.
        session_resume=RESUME_PROVIDER_CONVERSATION_ID,
        # No vendor documentation lists exit codes, so this was
        # measured (2026-08-12, four probes, 0.147.0) — and the answer
        # is that the rc cannot be read as a cause IN EITHER DIRECTION:
        #   bad config key         rc=1
        #   missing credential     rc=1
        #   success                rc=0
        #   API 400, model refused rc=0  ← and this is the dangerous one
        # A hard API refusal exits ZERO. Reading rc=0 as "the agent had
        # its fair chance" would charge a goal for the vendor rejecting
        # the request. The real outcome rides the event stream instead:
        # `{"type":"error"}` and `{"type":"turn.failed"}` both carry the
        # message while rc stays 0, which is why `codex_cli` classifies
        # on events first and rc second.
        # NOT covered: a usage-limit refusal has never been observed, so
        # `_QUOTA_MARKERS` is still a guess — the quota signal we DO
        # trust is `rate_limits.rate_limit_reached_type` from the
        # rollout, not prose.
        rc_contract=RC_UNINFORMATIVE,
        # Verified in the 08-17/18 outage: every codex spawn died
        # `stream disconnected` the moment this host became
        # unreachable (IPv4-only endpoint, dead default route).
        api_host="chatgpt.com",
        # Measured 2026-08-12: the tool surface is governed by FEATURE
        # FLAGS, and the two that matter behave as written — with
        # `shell_tool=false` the shell is gone, with `apps=false` the
        # account's Gmail/Calendar/Sites connectors are gone, with
        # `[agents] enabled=false` the sub-agent tools are gone. One
        # documented switch is INERT in the other direction:
        # `[tools] web_search = false` leaves `web__run` live and it
        # really searches. So removal works, granting is not uniformly
        # honoured — the same asymmetry agy has, reached by a different
        # road.
        enforcement_strength=ENFORCEMENT_DENY_ONLY,
        # NO file tool of its own (DELTA 1): with `shell_tool` and
        # `apps` off, a worker asked to read a file answers
        # "NO-READ-TOOL" (measured 2026-08-12). Everything it learns
        # about the workspace comes through `inspect` — the 08-15 probe
        # leg used it 30 times and Read zero times, because there is no
        # Read to use.
        native_file_tools=False,
        # MCP is the one action measured to honour its grant: with
        # `default_tools_approval_mode = "approve"` the call executes
        # (proved out-of-band by the probe server's own log), and
        # without it every call comes back `user cancelled MCP tool
        # call`. Nothing else has been measured, and the default empty
        # set is the right answer for the rest.
        allow_honoured_actions=frozenset({"mcp"}),
        # The exec channel that carries every tool result caps the
        # model-visible output at 10,000 tokens ("Output token budget.
        # Defaults to 10000 tokens" — the binary's own tool spec) and
        # keeps head+tail of anything larger. Measured 2026-08-15
        # across 1,501 outputs: cap-hits land between 36,289 and
        # 39,869 chars (unicode density moves the char count), so
        # 30,000 leaves margin for labels. The per-call
        # `max_output_tokens` pragma can raise it, but compliance is
        # the model's choice — the framework budgets for the default.
        mcp_result_delivery_chars=30_000,
        # 0.149 smoke: a full production night (2026-08-22, Erdős
        # fleet on the zen shim) after the strict-response family it
        # shipped was absorbed shim-side (total_tokens, response id,
        # forward-slash skills paths).
        tested_version="0.149.0",
        marker_tables=("Tooling.llm.codex_cli._QUOTA_MARKERS",
                       "Tooling.llm.codex_cli._MISCONFIG_MARKERS"),
        single_instance_lock=False,
        install_method=INSTALL_BY_COMMAND,
        install_command="npm install -g @openai/codex",
        auth_flow=AUTH_OWN_OAUTH,
        # `~/.codex/auth.json` — readable, and copyable: a spawn
        # authenticates from a copy under its own CODEX_HOME (measured
        # 2026-08-12), which is what makes the per-spawn envelope cheap.
        auth_state=AUTH_STATE_READABLE,
        readiness_argv=("login", "status"),
        notes=("capability surface is a per-spawn CODEX_HOME + "
               "config.toml; `[features]` is the tool gate, not "
               "`[tools]`; a worker with the shell off has NO file-read "
               "tool and reaches the workspace only through MCP"),
    ),
}

#: OpenCode Zen rides the SAME codex CLI binary through the local
#: translation shim (`Tooling/llm/zen_shim.py`), so its runtime shape
#: is codex's. What differs: the endpoint host, and the quota story —
#: no rate_limits events observed on the free window, so nothing
#: states a reset epoch (quota_wait gets UNKNOWN, which is correct).
CAPABILITIES["zen"] = _dc_replace(
    CAPABILITIES["codex"], name="zen", api_host="openrouter.ai",
    states_quota_reset=False,
    # The runtime SHAPE is codex's (same binary through the local
    # shim), but install and auth are NOT: there is no `zen`
    # executable (the codex binary carries the seat), and the
    # credential is an API key in env/.env — no OAuth, no auth.json
    # (codex_cli deliberately skips the auth copy for this flavor).
    exe_name="codex",
    install_method=INSTALL_NOT_NEEDED,
    install_command=None,
    auth_flow=AUTH_API_KEY,
    env_key="OPENROUTER_API_KEY")


#: config spellings -> canonical name (mirrors `llm.get_provider`).
ALIASES: "dict[str, str]" = {"agy": "antigravity"}


def canonical(provider: "str | None") -> str:
    name = str(provider or "claude").strip().lower()
    return ALIASES.get(name, name)


def capabilities_for(provider: "str | None") -> ProviderCapabilities:
    """The declaration for `provider`, or a fully-undeclared one.

    Never raises and never returns None: a consumer asking about an
    unknown backend gets the pessimistic answer, not an exception it
    would have to decide how to swallow.
    """
    name = canonical(provider)
    return CAPABILITIES.get(name) or _undeclared(name)


def honours_allow(provider: "str | None", action: str) -> bool:
    """Does an `allow` rule for `action` actually bind on this provider?

    The wildcard lives in the data (`ALLOW_HONOURED_ALL == {"*"}`), so
    every consumer would otherwise re-derive the same two-line set
    test — and the one that got it wrong would silently read "claude
    honours nothing" or "agy honours everything". False for an
    undeclared backend, by the same rule as everything else here.
    """
    honoured = capabilities_for(provider).allow_honoured_actions
    return "*" in honoured or action in honoured


def provider_for_kind(kind: "str | None",
                      workspace: "Path | None" = None) -> str:
    """Which provider a pipeline kind is seated on RIGHT NOW.

    Same resolution chain as `llm.get_provider` and
    `dispatcher._pipeline_seats` — read per call, because `Asterism.yaml`
    is live-editable and a seat can move between providers inside one
    run (2026-08-06: the judge moved off an exhausted model mid-run).

    `workspace` matters for callers that do not run from the workspace
    root: `config.get` defaults to cwd, and `asterism serve` is launched
    from wherever the user's shortcut points. A seat written into the
    workspace's Asterism.yaml that the reader looks for in some other
    directory resolves to the default and says nothing — the console
    would then answer with a provider the config never chose.
    """
    if not kind:
        return canonical(os.environ.get("ASTERISM_LLM_PROVIDER", "claude"))
    from ..core import config
    return canonical(config.get(
        f"{kind}.provider",
        env_var=f"ASTERISM_{kind.upper()}_PROVIDER",
        legacy_env=("ASTERISM_LLM_PROVIDER",),
        default="claude",
        workspace=workspace,
    ))


def for_kind(kind: "str | None") -> ProviderCapabilities:
    """The declaration of the provider currently seated for `kind`."""
    return capabilities_for(provider_for_kind(kind))


def prompt_tool_flags(provider: "str | None") -> "dict[str, bool]":
    """The prompt-template flags that depend on the BACKEND, not on the
    problem: which tool line a spawn should be told about.

    Both names are returned, always, and that is deliberate — the
    template renderer is fail-OPEN (an absent flag keeps its block), so
    a caller that passed only one of them would render BOTH tool lines
    and the worker would read two contradictory sentences about what it
    can do. Handing back the complete pair makes that unrepresentable.
    """
    native = capabilities_for(provider).native_file_tools
    return {"native_file_tools": native, "mcp_only_reads": not native}


def inspect_delivery_chars(provider: "str | None") -> "int | None":
    """The `inspect` reply ceiling for this backend, or None.

    None means UNMEASURED, and unmeasured means uncapped: the ceiling
    exists to keep a reply inside a transport that would amputate it,
    and applying a guessed one to a backend that delivers whole would
    re-ration what nothing rations. Same declaration-consumer shape as
    `prompt_tool_flags`; the adapter that spawns the tools server
    renders the value into `ASTERISM_INSPECT_DELIVERY_CHARS`."""
    return capabilities_for(provider).mcp_result_delivery_chars


def liveness_clock(provider: "str | None", kind: str) -> str:
    """Which signal proves a spawn of `kind` on `provider` is alive.

    THE DEGRADATION IS HERE, not in a comment: a provider that declares
    `stream_events=False` has no incremental output, therefore no
    silence to measure, therefore no watchdog. Its ONLY liveness
    guarantee is the overall wall timeout. Consumers must branch on
    this rather than on "did a parser state file appear" — agy writes
    `_parser_state.json` too (usage accounting only, no `state` key),
    so file presence answered "yes, a detector ran" for a provider that
    has never had one, and the retry helper duly printed
    `[detector verdict: active]` about a detector that does not exist.
    """
    caps = capabilities_for(provider)
    if not caps.stream_events:
        return LIVENESS_TIMEOUT_ONLY
    if kind not in STREAM_IDLE_KINDS:
        return LIVENESS_TOOL
    # An NL kind asks for the stream clock. A stream with no sub-tool
    # granularity cannot serve it, and substituting the tool clock here
    # would be the 2026-08-07 kill rebuilt from a different cause. Say
    # "no clock" out loud instead.
    return (LIVENESS_STREAM if caps.stream_text_deltas
            else LIVENESS_TIMEOUT_ONLY)


# -------------------------------------------------- undeclared warning

#: Providers already warned about, so the log carries the message once
#: per daemon rather than once per spawn.
_warned: "set[str]" = set()


def warn_if_undeclared(provider: "str | None", *, context: str = "") -> bool:
    """Emit the one-time `[capabilities]` warning. Returns True if the
    provider is undeclared (whether or not this call printed).

    The warning is half of the `undeclared` ruling; the other half is
    the conservative rc reading in `state/failures.rc_to_reason` and
    `pipeline._spawn_failure`. Neither half is sufficient alone.
    """
    caps = capabilities_for(provider)
    if caps.declared:
        return False
    if caps.name not in _warned:
        _warned.add(caps.name)
        print(f"[capabilities] provider {caps.name!r} has no declaration "
              f"in Tooling/llm/capabilities.py"
              + (f" ({context})" if context else "")
              + " — its exit codes will be read as UNCLASSIFIED (no goal "
                "is charged), it gets no quota probe, no stream watchdog "
                "and no session resume. Measure it and add an entry.",
              flush=True)
    return True


def _reset_warned_for_tests() -> None:
    _warned.clear()
