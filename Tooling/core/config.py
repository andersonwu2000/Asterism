"""Asterism.yaml — project-level config with env override.

Each tunable field resolves through:

    1. env var (ASTERISM_X)            — process env first, then the
                                         workspace `.env` file (gitignored;
                                         KEY=VALUE lines — machine-local /
                                         temporary tuning lives there, so
                                         the committed Asterism.yaml stays
                                         canonical)
    2. Asterism.yaml at workspace root — project canonical (committed)
    3. legacy env var(s)               — backwards compat (same .env
                                         fallback)
    4. built-in default

A real process env var always beats a .env entry, so one-off
`ASTERISM_X=… command` overrides keep working.
Asterism.yaml is optional; the file's absence is identical to writing
an empty `{}`.

The key registry is CONFIG_SPEC below — the single source of truth for
every dotted key the codebase reads, and since 2026-09-08 for its
DEFAULT, CAST and ENV VAR as well: a reader spells `config.get(key)` and
nothing else, so a key cannot mean 900 seconds here and 1800 there. A
typo'd key silently returns the default, so the registry is bound to the
code by tests/test_config_spec_drift.py in BOTH directions (an
unregistered `config.get` key fails CI, and a registered key nobody
reads fails too) and by tests/test_config_call_sites.py, which fails any
production caller that carries its own `default=` / `cast=` / `env_var=`
for a registered key.

Provider-specific knobs (openai base url / claude
tools) stay env-only — they're cross-cutting toggles that don't
fit the per-Problem mental model and are seldom changed.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, NamedTuple, Sequence


_CONFIG_FILENAME = "Asterism.yaml"


class Key(NamedTuple):
    """One tunable's whole truth: what it means, what it resolves to
    when nothing sets it, how a string form is read, and which env var
    overrides it.

    Until 2026-09-08 the registry held only prose and every reader
    supplied its own `default=` / `cast=` / `env_var=`, so a key had as
    many defaults as it had call sites: `dispatch.spawn_timeout_sec`
    read 900 in the registry, 1800 in the dispatcher AND the gateway,
    960 in the librarian — four answers, and nothing could say which
    one a run would use. The fields below ARE the answer now;
    `config.get(key)` with no other argument resolves exactly what is
    written here.

    `env` may carry `{KIND}`, replaced by the key's own first segment,
    so the per-pipeline families declare their env var once for every
    seat (`<kind>.model` → ASTERISM_FORMALIZER_MODEL, …).

    `legacy_env` holds only the aliases a key ALWAYS honours. A
    provider-specific compat spelling (ASTERISM_AGY_MODEL on
    antigravity, ASTERISM_LLM_MODEL on the openai adapter) stays at its
    adapter's call site: those are facts about a backend, not about the
    key, and folding them in here would make every seat honour every
    backend's old name.
    """
    description: str
    default: Any = None
    cast: "Callable[[str], Any] | None" = None
    env: "str | None" = None
    legacy_env: "tuple[str, ...]" = ()


#: The per-pipeline families, declared ONCE for every seat. The three
#: `adversary.*` rows below share these very objects (the judge stamps
#: its own seat into the verdict, so it reads them by literal name) —
#: sharing the object is what keeps the stamp and the spawn from
#: disagreeing about which model the seat is on.
_KIND_MODEL = Key(
    "per-pipeline model override; unset = the provider adapter's own "
    "default", env="ASTERISM_{KIND}_MODEL")
_KIND_PROVIDER = Key(
    "per-pipeline LLM provider", default="claude",
    env="ASTERISM_{KIND}_PROVIDER", legacy_env=("ASTERISM_LLM_PROVIDER",))
_KIND_EFFORT = Key(
    "per-pipeline reasoning depth, codex only. claude carries no such "
    "knob — its thinking budget is set per spawn from the wall-clock "
    "budget.", default="xhigh", env="ASTERISM_{KIND}_REASONING_EFFORT")

# ── CONFIG_SPEC — the key registry (task #10) ──────────────────────────
# key → Key(...). `<kind>` is the dynamic per-pipeline placeholder
# (formalizer/strategist/librarian/…); a concrete `formalizer.model`
# resolves against the `<kind>.model` row.
# Adding a `config.get` call with a new key? Register it here — the drift
# test fails otherwise (typo → silent-default is the bug class this
# kills). Removing a call? Delete the entry (reverse direction fails too).
CONFIG_SPEC: "dict[str, Key]" = {
    "dispatch.pool": Key(
        "worker pool == gateway workers, 1:1 #118",
        4, int, "ASTERISM_POOL"),
    "ledger.idle_spares": Key(
        "warm-pool idle spares above in-use slots — the pool follows "
        "demand, not the calm clock",
        4, int, "ASTERISM_IDLE_SPARES"),
    "ledger.pressure_headroom_gb": Key(
        "pressure band: pause dispatch when the cgroup footprint climbs "
        "within this many GB of the budget — scale DOWN on small-budget "
        "machines",
        8.0, float, "ASTERISM_PRESSURE_HEADROOM_GB"),
    "ledger.pressure_release_slack_gb": Key(
        "pressure band: extra calm below the pause line before dispatch "
        "resumes",
        4.0, float, "ASTERISM_PRESSURE_RELEASE_SLACK_GB"),
    "dispatch.ram_budget": Key(
        "adaptive RAM ledger budget, '28G' or '85%' — splits the worker "
        "economy: Lean slots follow target_slots(budget - NL reserve), NL "
        "kinds admit on measured available RAM; unset = legacy static "
        "dispatch.pool semantics",
        "", None, "ASTERISM_RAM_BUDGET"),
    "dispatch.blocked_kinds": Key(
        "operator hold — comma list of queue kinds this machine must not "
        "dispatch, e.g. 'Formalizer,Librarian'; unknown names are ignored, "
        "so a typo holds nothing",
        "", None, "ASTERISM_BLOCKED_KINDS"),
    "dispatch.budget_sec": Key(
        "daemon wall budget", 1800, int, "ASTERISM_BUDGET_SEC"),
    "dispatch.intake_timeout_sec": Key(
        "Formalizer intake turn spawn cap",
        300, int, "ASTERISM_INTAKE_TIMEOUT_SEC"),
    "dispatch.shelve_threshold": Key(
        "attempts before shelve", 8, int, "ASTERISM_SHELVE_THRESHOLD"),
    "dispatch.handoff_on_code_change": Key(
        "daemon drains + hands off to a fresh daemon when the source tree "
        "OR Asterism.yaml/.env changes under it",
        True, None, "ASTERISM_HANDOFF_ON_CODE_CHANGE"),
    "dispatch.quota_wait": Key(
        "confirmed-exhausted subscription window pauses dispatch until "
        "resets_at instead of exiting (off: riding further windows is "
        "opt-in, user 2026-07-18)",
        False, None, "ASTERISM_QUOTA_WAIT"),
    # 900s = 15 min. Phase 2 LSP cantor_xi had six spawns hit the prior
    # 600s wall while making real progress; fewer-but-longer spawns
    # paired with the shelve threshold keep the cost of a stuck goal
    # bounded. The production Asterism.yaml overrides it to 1800 (the
    # 2026-08-11 union_closed reading: 29 of 55 goal-level deaths were
    # the clock, not the mathematics) — the yaml is where that decision
    # lives, and every reader now derives from the resolved value.
    "dispatch.spawn_timeout_sec": Key(
        "main spawn SIGKILL cap",
        900, int, "ASTERISM_SPAWN_TIMEOUT_SEC"),
    # 180s: the postmortem --resumes the dead session and writes a short
    # state + blocker note. 120 was empirically too tight to write a
    # usable note on dense root-level state.
    "dispatch.postmortem_timeout_sec": Key(
        "postmortem spawn cap",
        180, int, "ASTERISM_POSTMORTEM_TIMEOUT_SEC"),
    "dispatch.trap_check_sec": Key(
        "watchdog thinking-trap check point",
        660, int, "ASTERISM_TRAP_CHECK_SEC"),
    "dispatch.silence_threshold_sec": Key(
        "watchdog silence AND-condition",
        300, int, "ASTERISM_SILENCE_THRESHOLD_SEC"),
    "dispatch.silent_kill_sec": Key(
        "watchdog silent-kill: joint silence on BOTH clocks that kills "
        "without a trap signature; 0=off",
        2400, int, "ASTERISM_SILENT_KILL_SEC"),
    "dispatch.completion_grace_sec": Key(
        "watchdog completion-reclaim grace",
        20, int, "ASTERISM_COMPLETION_GRACE_SEC"),
    "dispatch.classify_trap_cap_sec": Key(
        "librarian classify trap cap ceiling", 2400, int),
    "dispatch.classify_trap_per_decl_sec": Key(
        "classify trap budget per kept decl", 4, int),
    "gateway.port": Key(
        "LSP gateway HTTP port", 8765, int, "ASTERISM_GATEWAY_PORT"),
    "gateway.interactive_slots": Key(
        "reserved gateway slots for the serve UI editor",
        1, int, "ASTERISM_INTERACTIVE_SLOTS"),
    "gateway.lean_memory_cap_mb": Key(
        "per-process commit cap on the lake/lean tree via Job Object, "
        "0 disables",
        8192, int, "ASTERISM_LEAN_MEMORY_CAP_MB"),
    "gateway.slot_recycle_mb": Key(
        "private-bytes above which an IDLE, UNCLAIMED slot restarts its "
        "worker; far below the job cap on purpose — that one caps one "
        "elaboration, this one caps accumulation across many",
        1500, int, "ASTERISM_SLOT_RECYCLE_MB"),
    "strategist.interval_min": Key(
        "T1 routine wake cadence",
        120.0, float, "ASTERISM_STRATEGIST_INTERVAL_MIN"),
    "strategist.verify_retry": Key(
        "strategist verify/Adversary revision rounds per wake",
        6, int, "ASTERISM_STRATEGIST_VERIFY_RETRY"),
    "strategist.timeout_sec": Key(
        "strategist wake spawn cap — hang guard, not a work budget",
        10800, int, "ASTERISM_STRATEGIST_TIMEOUT_SEC"),
    # The judge seat, read by literal name for the verdict's provenance
    # stamp (survey P1, 2026-08-29) as well as by the spawn resolver.
    "adversary.provider": _KIND_PROVIDER,
    "adversary.model": _KIND_MODEL,
    "adversary.reasoning_effort": _KIND_EFFORT,
    "adversary.timeout_sec": Key(
        "adversary spawn cap — hang guard, not a work budget",
        7200, int, "ASTERISM_ADVERSARY_TIMEOUT_SEC"),
    "theorist.timeout_sec": Key(
        "theory author spawn cap — hang guard, not a work budget",
        10800, int, "ASTERISM_THEORIST_TIMEOUT_SEC"),
    "theorist.rounds": Key(
        "revision rounds a fired theory verdict may buy, on the author's "
        "own session",
        3, int, "ASTERISM_THEORIST_ROUNDS"),
    "theory_reviewer.timeout_sec": Key(
        "theory reviewer spawn cap — hang guard, not a work budget",
        7200, int, "ASTERISM_THEORY_REVIEWER_TIMEOUT_SEC"),
    "verify.olean_warm": Key(
        "background olean warmer kill switch #103",
        True, None, "ASTERISM_OLEAN_WARM"),
    "lessons.reflection_enabled": Key(
        "reflection spawn kill switch",
        True, None, "ASTERISM_LESSONS_REFLECTION_ENABLED"),
    "feedback.enabled": Key(
        "dev-mode agent feedback questionnaire",
        False, None, "ASTERISM_FEEDBACK_ENABLED"),
    "presearch.enabled": Key(
        "target-1 per-node pre-search toggle",
        True, None, "ASTERISM_PRESEARCH_ENABLED"),
    # No cast: the reader owns the coercion because it also owns the
    # 60s floor and the fall-back-to-default on a malformed value.
    "presearch.timeout_sec": Key(
        "pre-search agent budget",
        420, None, "ASTERISM_PRESEARCH_TIMEOUT_SEC"),
    "library.require_signoff": Key(
        "Ingest pauses for approve-ingest", True),
    "paper_index.timeout_sec": Key(
        "paper-map one-shot spawn budget", 1200, int),
    "explainer.model": Key(
        "serve chat-explainer spawn model (teammate serve/chat.py); "
        "unset = the chosen explainer backend's own default",
        env="ASTERISM_EXPLAINER_MODEL"),
    "explainer.idle_sec": Key(
        "Assistant turn IDLE deadline — seconds of SILENCE from the "
        "explainer before the turn is killed, not a budget for the whole "
        "answer; also agy's --print-timeout, which has no stream and "
        "whose whole-answer clock IS its idle clock",
        600, int, "ASTERISM_EXPLAINER_IDLE_SEC"),
    "<kind>.model": _KIND_MODEL,
    "<kind>.provider": _KIND_PROVIDER,
    "<kind>.reasoning_effort": _KIND_EFFORT,
    "zen.base_url": Key(
        "zen-flavor codex upstream — the local shim that translates "
        "/responses to OpenRouter and self-executes tools",
        "http://127.0.0.1:8898/v1", None, "ASTERISM_ZEN_BASE_URL"),
    "zen.api_key": Key(
        "yaml fallback for the zen seat's key when OPENCODE_ZEN_API_KEY "
        "is unset; the shim itself reads OPENROUTER_API_KEY from .env",
        "", None, "OPENCODE_ZEN_API_KEY"),
}


def _spec_for(key_path: str) -> "Key | None":
    """The registry row a key resolves against — its own, or the
    `<kind>.<leaf>` family row for the per-pipeline keys (there is no
    `formalizer.model` row; there is one row for every seat)."""
    spec = CONFIG_SPEC.get(key_path)
    if spec is not None:
        return spec
    _, dot, leaf = key_path.partition(".")
    return CONFIG_SPEC.get(f"<kind>.{leaf}") if dot else None


def spec_default(key_path: str) -> Any:
    """The registry's default for a key.

    For the handful of module constants that ARE a key's default and are
    ALSO read for something else (`ram_ledger.SLOT_RECYCLE_MB_DEFAULT`
    prices a slot as well as seeding the knob): they read it from here
    instead of restating the number, so the constant cannot drift away
    from what an unset key resolves to."""
    spec = _spec_for(key_path)
    return spec.default if spec is not None else None


def _env_name(key_path: str, spec: "Key | None") -> "str | None":
    """The env var this key reads, with `{KIND}` filled in from the
    key's own first segment."""
    if spec is None or not spec.env:
        return None
    if "{KIND}" not in spec.env:
        return spec.env
    return spec.env.replace("{KIND}", key_path.split(".", 1)[0].upper())


# Module-level cache so reading the file once per daemon-run avoids
# repeated yaml.safe_load() on hot paths (every spawn_llm reads model;
# every dispatcher tick reads thresholds). Tests reset via _reset_cache.
_cache: dict[str, Any] | None = None
_cache_workspace: Path | None = None
_load_error: str | None = None


def _reset_cache() -> None:
    """Test helper — invalidate the in-process cache so the next
    `load()` re-reads the file. Safe to call between test cases."""
    global _cache, _cache_workspace, _dotenv, _dotenv_workspace, _load_error
    _cache = None
    _cache_workspace = None
    _dotenv = None
    _dotenv_workspace = None
    _load_error = None


def load(workspace: Path | None = None) -> dict[str, Any]:
    """Read Asterism.yaml from workspace (default cwd). Empty dict
    when the file is missing or unparseable (a warning is emitted on
    parse failure but the daemon continues — env+default chain still
    works)."""
    global _cache, _cache_workspace, _load_error
    workspace = workspace or Path.cwd()
    if _cache is not None and _cache_workspace == workspace:
        return _cache
    _load_error = None

    def _read_one(path: Path) -> "dict[str, Any]":
        global _load_error
        if not path.exists():
            return {}
        try:
            import yaml  # PyYAML already a dep
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception as exc:
            # Don't crash read-only commands over a malformed config —
            # warn and fall back to env+default. State-changing commands
            # must consult `load_error` and refuse instead (B4).
            _load_error = f"{path}: {exc}"
            print(f"[config] WARNING: {path} unparseable ({exc}); "
                  f"skipping it", flush=True)
            return {}

    _cache = _read_one(workspace / _CONFIG_FILENAME)
    _cache_workspace = workspace
    return _cache


def load_error(workspace: Path | None = None) -> "str | None":
    """The parse error from the config read, or None. A present-but-
    unparseable config must hard-block state-changing commands (daemon
    start / run) instead of silently running on defaults — a timed
    run's entire settings would evaporate (2026-07-19)."""
    load(workspace)
    return _load_error


# ── .env — file-form env vars (task #13; user design call: no extra
# precedence tier — a .env entry IS an env var, just persisted) ──
# Simple KEY=VALUE lines at the workspace root, gitignored. A real
# process env var always beats the .env entry (standard dotenv
# semantics, keeps one-off `ASTERISM_X=… command` overrides working).
# Deliberately NOT injected into os.environ: kept in a module dict so
# test monkeypatching of the environment stays isolated.
_dotenv: "dict[str, str] | None" = None
_dotenv_workspace: Path | None = None
_dotenv_mtime: "float | None" = None


def _load_dotenv(workspace: Path) -> "dict[str, str]":
    global _dotenv, _dotenv_workspace, _dotenv_mtime
    path = workspace / ".env"
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = None
    # Cache follows the FILE, not the process (SP7 autopsy 2026-09-02:
    # the gateway outlives daemon handoffs, so a birth-time cache froze
    # a .env retune out of the build gate until every lease saturated).
    if (_dotenv is not None and _dotenv_workspace == workspace
            and _dotenv_mtime == mtime):
        return _dotenv
    _dotenv_mtime = mtime
    out: "dict[str, str]" = {}
    try:
        for ln in path.read_text(encoding="utf-8").splitlines():
            s = ln.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, _, v = s.partition("=")
            out[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    _dotenv = out
    _dotenv_workspace = workspace
    return out


def _env(name: str, workspace: "Path | None") -> "str | None":
    """Process env var, falling back to the workspace .env file."""
    v = os.environ.get(name)
    if v is not None and v != "":
        return v
    v = _load_dotenv(workspace or Path.cwd()).get(name)
    return v if v else None


#: "the caller said nothing", as distinct from "the caller said None"
#: — `default=None` is a real answer for the model keys, so the two
#: cannot share a sentinel.
_UNSET: Any = object()


def get(
    key_path: str,
    *,
    default: Any = _UNSET,
    env_var: "str | None" = _UNSET,
    legacy_env: Sequence[str] = _UNSET,
    cast: "Callable[[str], Any] | None" = _UNSET,
    workspace: Path | None = None,
) -> Any:
    """Resolve a single field via env → yaml → legacy_env → default.

    `key_path`: dotted path into Asterism.yaml, e.g. 'dispatch.pool'.

    Everything else comes from CONFIG_SPEC by default, and a registered
    key should be READ AS `get(key)` — the whole point of the registry
    is that the default, the cast and the env var are properties of the
    KEY, not of whoever happens to be reading it. The arguments remain
    for the two cases a registry cannot cover: a provider-specific
    compat alias (`legacy_env`), and a test pinning a value explicitly.
    `tests/test_config_call_sites.py` holds production callers to the
    registry.

    `cast`: applied to env-var strings AND yaml values (in case yaml
            stores e.g. '4' as a string). None means no transform; the
            default is never cast (it is already the right type).
    `legacy_env`: ordered list of additional env vars consulted after
                  yaml but before default; first non-empty wins.
    """
    spec = _spec_for(key_path)
    if default is _UNSET:
        default = spec.default if spec is not None else None
    if cast is _UNSET:
        cast = spec.cast if spec is not None else None
    if env_var is _UNSET:
        env_var = _env_name(key_path, spec)
    if legacy_env is _UNSET:
        legacy_env = spec.legacy_env if spec is not None else ()

    # 1. primary env var (process env, then the workspace .env file)
    if env_var:
        v = _env(env_var, workspace)
        if v is not None:
            return cast(v) if cast else v

    # 2. yaml path
    data = load(workspace)
    cur: Any = data
    for k in key_path.split("."):
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        else:
            cur = None
            break
    if cur is not None:
        return cast(cur) if cast else cur

    # 3. legacy env(s) (same .env fallback)
    for legacy in legacy_env:
        v = _env(legacy, workspace)
        if v is not None:
            return cast(v) if cast else v

    # 4. default
    return default


def resolve_workspace(explicit: "Path | str | None" = None) -> Path:
    """The single workspace-resolution entrypoint (frontend charter §5-1).

    Historically every caller assumed cwd == repo root, which holds for
    the operator but not for a `asterism serve` launched from anywhere,
    nor for the product's managed workspace (`~/Asterism`). Resolution
    order:

      1. `explicit` (a `--workspace` flag) — verbatim, must exist;
      2. `ASTERISM_WORKSPACE` env var (process env only — the .env file
         cannot answer this: finding .env REQUIRES the workspace, which
         is exactly the chicken-and-egg this function exists to break);
      3. cwd, when it looks like a workspace (has Asterism.yaml or
         Problems/) — the operator's historical behavior, unchanged;
      4. `~/Asterism`, when it looks like a workspace (the managed
         workspace the Phase-2 first-run wizard creates).

    Raises FileNotFoundError with actionable guidance otherwise —
    launching against a half-guessed workspace corrupts nothing but
    confuses everything."""
    def _looks_like(p: Path) -> bool:
        return (p / _CONFIG_FILENAME).exists() or (p / "Problems").is_dir()

    if explicit is not None:
        p = Path(explicit).resolve()
        if not p.is_dir():
            raise FileNotFoundError(f"workspace {p} does not exist")
        return p
    env = os.environ.get("ASTERISM_WORKSPACE")
    if env:
        p = Path(env).resolve()
        if not p.is_dir():
            raise FileNotFoundError(
                f"ASTERISM_WORKSPACE={env} does not exist")
        return p
    cwd = Path.cwd()
    if _looks_like(cwd):
        return cwd
    home_ws = Path.home() / "Asterism"
    if _looks_like(home_ws):
        return home_ws
    raise FileNotFoundError(
        "no Asterism workspace found: pass --workspace, set "
        "ASTERISM_WORKSPACE, or run from a directory containing "
        "Asterism.yaml / Problems/")


# ---------------------------------------------------------------------
# UI settings chokepoint (curated Asterism.yaml keys)
# ---------------------------------------------------------------------
#
# The web UI exposes a small allowlist of yaml keys (per-pipeline model
# + the dispatch knobs a mathematician actually tunes). Edits are
# targeted text substitutions on Asterism.yaml so the file's extensive
# comments survive; the result must re-parse and resolve to the value
# written. Everything else stays operator territory (editor + .env).
# Values apply from the NEXT engine start (the daemon caches config
# per run).

#: dotted key -> (python type, human description)
#:
#: Only keys a LIVE spawn resolves. `builder.model` / `backward.model` /
#: `forward.model` sat here after the v33 merge, described in their own
#: tooltip as "unread post-v33" — three dropdowns for pipelines that no
#: longer run (last Backward 2026-07-17, last Forward 2026-07-18; every
#: Inject since names Formalizer). Worse than clutter: unset, they
#: rendered as whatever option came first, so the page showed a model
#: nothing had chosen and nothing would read. Removed 2026-08-07; the
#: keys still parse from an old yaml, they are simply not offered.
#: `test_config_ui_keys.py` ratchets this set.
#: the seats a model/provider can be chosen for. One list so the two
#: key families cannot drift apart — a seat that can pick a model must
#: be able to pick the backend that runs it (2026-08-14: three backends
#: are live and `<kind>.provider` was yaml-only).
UI_SEATS = ("formalizer", "strategist", "presearch", "librarian",
            "adversary", "theorist", "theory_reviewer")

UI_EDITABLE_KEYS: "dict[str, tuple[type, str]]" = {
    "formalizer.model": (str, "model that turns the argued proof into Lean (prove/split/mint)"),
    "strategist.model": (str, "model that plans the campaign"),
    "presearch.model": (str, "model that scouts Mathlib before proving"),
    "librarian.model": (str, "model that curates the Library"),
    "adversary.model": (str, "model that adversarially reviews the research programme"),
    "theorist.model": (str, "model that writes the theory the programme is missing"),
    "theory_reviewer.model": (str, "model that reviews the theory document"),
    "dispatch.pool": (int, "max agents working at once"),
    "ledger.idle_spares": (int, "warm-pool idle spares above in-use slots"),
    "dispatch.budget_sec": (int, "wall-clock budget per engine run (seconds)"),
    "dispatch.shelve_threshold": (int, "failed attempts before a goal is shelved"),
    # re-admitted (owner, 2026-07-18, reversing the 2026-07-14 hold):
    # the user must be able to choose whether an unattended run rides
    # quota window after quota window — "ask it to prove Riemann and
    # close the tab" must not silently spend every future window.
    "dispatch.quota_wait": (
        bool,
        "when the subscription window runs out: wait for the reset and keep going (off: the run stops instead)",
    ),
    # run/machine knobs the console names (HID §1.4, owner 2026-09-03):
    # the hold rides the Run controls, the budget the gear. Both were
    # env-only, so setting either meant editing a file the UI cannot see.
    "dispatch.blocked_kinds": (
        str,
        "queue kinds this machine must not dispatch (comma list: Formalizer, Strategist, Librarian; empty = no hold)",
    ),
    "dispatch.ram_budget": (
        str,
        "RAM the worker economy may use — '26G' or '85%' of the machine (empty = size the pool by the agent count alone)",
    ),
}

#: `<kind>.provider` for every seat, appended rather than written out:
#: the seat list above is the single source, so adding a seat cannot
#: leave its backend unchoosable.
for _seat in UI_SEATS:
    UI_EDITABLE_KEYS[f"{_seat}.provider"] = (
        str, f"which backend runs the {_seat} seat")
del _seat

#: How deep a codex seat thinks. The one axis that changes what a wake
#: COSTS, and it was env/yaml-only until 2026-09-06 — the console could
#: show a seat's model and not its depth. The values are codex's own
#: ladder (`llm/codex_cli.py`); every other backend ignores the key, and
#: the row says so rather than sitting there looking live.
EFFORT_CHOICES: "tuple[str, ...]" = ("low", "medium", "high", "xhigh",
                                     "max")

def reads_effort(provider: "str | None") -> bool:
    """Does this backend read the knob at all?

    Asked of the DECLARATION (`capabilities.reasoning_effort`), never of
    a list of provider names kept here: a name-keyed copy of a declared
    table is the copy that goes stale, and `capabilities.py` exists to
    abolish exactly that. Not a refusal either — a seat may move to
    codex a moment after its effort is set — but the row is marked, so
    the reader is never turning a dial nobody reads."""
    from ..llm import capabilities as _caps
    return _caps.capabilities_for(provider).reasoning_effort

for _seat in UI_SEATS:
    UI_EDITABLE_KEYS[f"{_seat}.reasoning_effort"] = (
        str,
        f"how deep the {_seat} seat thinks — codex seats only; claude "
        f"derives its thinking budget per spawn from the wall clock")
del _seat

def _declared_models() -> "dict[str, list[str]]":
    """Dropdown choices for `.model` keys, read off each provider's own
    declaration (`llm/capabilities.models`).

    It used to be a hand-kept table here, and it rotted exactly the way
    a second copy always does: on 2026-09-06 it offered four retired
    claude tiers while the running board sat on `claude-opus-5` and
    `claude-fable-5-1`, and named ONE codex model out of seven. A list
    of what a backend can run is a fact about the BACKEND, so it is
    declared beside install, auth and the rc contract, and this is the
    read. Free text stays possible via yaml/.env; the UI's job here is
    killing typos, not narrowing the machine."""
    from ..llm import capabilities as _caps
    return {name: list(cap.models)
            for name, cap in _caps.CAPABILITIES.items() if cap.models}


MODEL_CHOICES_BY_PROVIDER: "dict[str, list[str]]" = _declared_models()

#: claude's list under its old name — the one place that still wants a
#: bare list is a caller that has not asked which provider it means.
MODEL_CHOICES: "list[str]" = MODEL_CHOICES_BY_PROVIDER["claude"]


def models_for(provider: "str | None") -> "list[str]":
    """What the picker may offer for a seat on this provider.

    Empty means "nobody wrote a list down" — and the UI must then take
    free text rather than offering another backend's names. A select of
    claude models on a `provider: codex` seat is the exact failure the
    select was introduced to prevent (a wrong model name only explodes
    at the next spawn), one level up (2026-08-14).
    """
    from ..llm import capabilities as _caps
    return list(MODEL_CHOICES_BY_PROVIDER.get(_caps.canonical(provider), []))

_INT_BOUNDS = {
    "dispatch.pool": (1, 32),
    "ledger.idle_spares": (1, 32),
    "dispatch.budget_sec": (60, 604800),
    "dispatch.shelve_threshold": (1, 50),
}


def _check_blocked_kinds(value: str) -> "tuple[str, str | None]":
    """The dispatch hold, canonicalized against the queue's own kind
    table. The READER ignores an unknown name on purpose (a typo holds
    nothing rather than everything), so this writer is the only place
    that can tell the person their hold would not hold. Empty = none."""
    from .quota import DISPATCH_KIND
    canon = {v.lower(): v for v in DISPATCH_KIND.values()}
    out: "list[str]" = []
    for tok in value.split(","):
        t = tok.strip()
        if not t:
            continue
        if t.lower() not in canon:
            return "", (f"unknown queue kind {t!r} — pick from "
                        + ", ".join(sorted(canon.values())))
        out.append(canon[t.lower()])
    return ",".join(out), None


def _check_ram_budget(value: str) -> "tuple[str, str | None]":
    """The budget spec, validated by the grammar the ledger parses —
    `parse_budget` answers None for anything it cannot read, and an
    unreadable spec silently means "legacy static pool", which is a
    different machine from the one the person asked for."""
    from .ram_ledger import parse_budget
    if value and parse_budget(value, 100.0) is None:
        return "", (f"{value!r} is not a RAM budget — write '26G' (an "
                    f"absolute size) or '85%' (a share of the machine)")
    return value, None


def _check_effort(value: str) -> "tuple[str, str | None]":
    """One rung of codex's own ladder. The generic guard would take
    `ludicrous` — a value the CLI refuses at spawn, which is a run that
    dies for a reason nothing before the spawn said out loud."""
    v = value.strip().lower()
    if v in EFFORT_CHOICES:
        return v, None
    return "", (f"{value!r} is not a reasoning effort — pick one of "
                + ", ".join(EFFORT_CHOICES))


#: per-key grammar for str knobs whose legal values the generic
#: `[A-Za-z0-9._-]+` guard would reject (a comma list, a percentage) or
#: would wrongly accept (a made-up effort rung).
_STR_VALIDATORS: "dict[str, Callable[[str], tuple[str, str | None]]]" = {
    "dispatch.blocked_kinds": _check_blocked_kinds,
    "dispatch.ram_budget": _check_ram_budget,
    **{f"{_s}.reasoning_effort": _check_effort for _s in UI_SEATS},
}

def ui_settings(workspace: Path) -> "list[dict[str, object]]":
    """Snapshot of every UI-editable key: yaml value (None = unset) +
    resolved value (env > yaml > default chain, i.e. what a run would
    actually use).

    "What a run would actually use" is a claim only CONFIG_SPEC can
    make good on, so every row here resolves through the bare
    `get(key)` the engine itself uses. This page used to keep its own
    env-var table beside the registry's, and the copy had holes: a
    `.model` row read the yaml while the daemon ran on
    ASTERISM_<SEAT>_MODEL — two answers to one question, on the page
    whose whole job is answering it."""
    _reset_cache()
    data = load(workspace)
    out: list[dict[str, object]] = []
    for key, (typ, desc) in UI_EDITABLE_KEYS.items():
        cur: object = data
        for part in key.split("."):
            cur = cur.get(part) if isinstance(cur, dict) else None
        resolved = get(key, workspace=workspace)
        if typ is bool and resolved is not None:
            # env/.env supplies a string, yaml a real bool — one shape out
            resolved = str(resolved).strip().lower() in (
                "true", "1", "yes", "on")
        row: dict[str, object] = {
            "key": key, "yaml": cur, "resolved": resolved,
            "type": typ.__name__, "description": desc,
        }
        if key.endswith(".provider"):
            from ..llm import capabilities as _caps
            # every DECLARED backend, so a seat can be moved to one the
            # machine has not installed yet — the accounts panel is where
            # "installed" is answered, and refusing the choice here would
            # make the two panels argue
            row["choices"] = sorted(_caps.CAPABILITIES)
            if resolved and str(resolved) not in row["choices"]:
                row["choices"] = [str(resolved), *row["choices"]]
        elif key.endswith(".model"):
            # the models of THIS SEAT's backend. A flat claude-only list
            # offered `claude-fable-5` for a `provider: codex` seat —
            # the very failure a select was introduced to prevent, one
            # level up (2026-08-14).
            seat = key.split(".", 1)[0]
            prov = get(f"{seat}.provider", workspace=workspace)
            choices = models_for(prov)
            # the resolved value (env/yaml may name anything) is always
            # a legal choice — never render a select that can't show
            # the current truth
            if resolved and str(resolved) not in choices:
                choices.insert(0, str(resolved))
            # empty = nobody wrote a list for this backend; the UI must
            # take free text rather than offer another backend's names
            row["choices"] = choices
            row["provider"] = prov
        elif key.endswith(".reasoning_effort"):
            # marked with whether the seat's CURRENT backend reads the
            # knob at all — a control that does nothing is a promise the
            # page must not make silently
            seat = key.split(".", 1)[0]
            prov = get(f"{seat}.provider", workspace=workspace)
            row["choices"] = list(EFFORT_CHOICES)
            row["provider"] = prov
            row["applies"] = reads_effort(prov)
        elif typ is bool:
            # booleans render as a two-way select, never a free-text box.
            # Unset resolves to the ENGINE's default (CONFIG_SPEC's, the
            # one the run reads) — showing "false" for an engine that
            # defaults true is a lie.
            row["choices"] = ["true", "false"]
            row["resolved"] = "true" if resolved else "false"
        out.append(row)
    return out


def set_ui_setting(workspace: Path, key: str,
                   value: "str | int") -> "tuple[int, str]":
    """Write one allowlisted key into Asterism.yaml, preserving the
    file's comments (targeted line substitution, then re-parse)."""
    import re as _re
    if key not in UI_EDITABLE_KEYS:
        return 1, f"FAIL: {key!r} is not UI-editable"
    typ, _ = UI_EDITABLE_KEYS[key]
    if typ is int:
        try:
            value = int(value)
        except (TypeError, ValueError):
            return 1, f"FAIL: {key} expects an integer"
        lo, hi = _INT_BOUNDS[key]
        if not (lo <= value <= hi):
            return 1, f"FAIL: {key} must be in [{lo}, {hi}]"
    elif typ is bool:
        sval = str(value).strip().lower()
        if sval not in ("true", "false", "1", "0", "yes", "no", "on", "off"):
            return 1, f"FAIL: {key} expects true/false"
        value = "true" if sval in ("true", "1", "yes", "on") else "false"
    else:
        value = str(value).strip()
        check = _STR_VALIDATORS.get(key)
        if check is not None:
            value, err = check(value)
            if err:
                return 1, f"FAIL: {key} — {err}"
        elif not _re.fullmatch(r"[A-Za-z0-9._-]+", value):
            return 1, f"FAIL: {key} value looks malformed"

    # What goes on the LINE. Empty is a legal value for the str knobs
    # with a validator (no hold / no budget), and a bare `key:` parses
    # back as None — which the read-back check below would then refuse,
    # leaving the person unable to clear a knob they could set.
    written = "''" if (typ is str and value == "") else value
    section, leaf = key.split(".", 1)
    path = workspace / _CONFIG_FILENAME
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = text.split("\n")

    sec_idx = None
    for i, line in enumerate(lines):
        if _re.match(rf"^{_re.escape(section)}\s*:\s*(#.*)?$", line):
            sec_idx = i
            break
    if sec_idx is None:
        # section absent: append a minimal one at the end
        if lines and lines[-1].strip() != "":
            lines.append("")
        lines += [f"{section}:", f"  {leaf}: {written}"]
    else:
        # section extent: until the next top-level key
        end = len(lines)
        for j in range(sec_idx + 1, len(lines)):
            if _re.match(r"^[A-Za-z_]+\s*:", lines[j]):
                end = j
                break
        hit = None
        for j in range(sec_idx + 1, end):
            if _re.match(rf"^\s{{2}}{_re.escape(leaf)}\s*:", lines[j]):
                hit = j
                break
        if hit is not None:
            m = _re.match(
                rf"^(\s{{2}}{_re.escape(leaf)}\s*:\s*)([^#]*?)(\s*#.*)?$",
                lines[hit])
            assert m is not None
            lines[hit] = f"{m.group(1)}{written}{m.group(3) or ''}"
        else:
            lines.insert(sec_idx + 1, f"  {leaf}: {written}")

    new_text = "\n".join(lines)
    # validation: must parse, and the key must resolve to what we wrote
    try:
        import yaml
        parsed = yaml.safe_load(new_text)
        cur: object = parsed
        for part in key.split("."):
            cur = cur.get(part) if isinstance(cur, dict) else None
        if typ is int:
            assert int(str(cur)) == value
        elif typ is bool:
            # yaml parses the bare true/false token into a real bool
            assert isinstance(cur, bool) and cur == (value == "true")
        else:
            assert str(cur) == str(value)
    except Exception as e:  # noqa: BLE001
        return 1, f"FAIL: edit would corrupt Asterism.yaml ({e}) — not written"
    tmp = path.with_suffix(".yaml.tmp")
    tmp.write_text(new_text, encoding="utf-8", newline="\n")
    tmp.replace(path)
    _reset_cache()
    # A live daemon notices the file change on its drift cadence and
    # gracefully hands off to a fresh process on the new settings.
    return 0, (f"OK: {key} = {value} (a live engine applies it within "
               f"~1 min via handoff; otherwise from the next run)")
