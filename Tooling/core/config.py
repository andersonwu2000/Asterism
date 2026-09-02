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
every dotted key the codebase reads (the prose field map that used to sit
here had drifted: six live keys missing, one dead key listed). A typo'd
key silently returns the default, so the registry is bound to the code by
tests/test_config_spec_drift.py in BOTH directions: an unregistered
`config.get` key fails CI, and a registered key nobody reads fails too.

Provider-specific knobs (openai base url / claude
tools) stay env-only — they're cross-cutting toggles that don't
fit the per-Problem mental model and are seldom changed.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Sequence


_CONFIG_FILENAME = "Asterism.yaml"

# ── CONFIG_SPEC — the key registry (task #10) ──────────────────────────
# key → one-line doc "(env fallback; default)". `<kind>` is the dynamic
# per-pipeline placeholder (builder/backward/forward/strategist/…).
# Adding a `config.get` call with a new key? Register it here — the drift
# test fails otherwise (typo → silent-default is the bug class this
# kills). Removing a call? Delete the entry (reverse direction fails too).
CONFIG_SPEC: "dict[str, str]" = {
    "dispatch.pool": "worker pool == gateway workers, 1:1 #118 (ASTERISM_POOL; 4)",
    "ledger.idle_spares": "warm-pool idle spares above in-use slots — the pool follows demand, not the calm clock (ASTERISM_IDLE_SPARES; 4)",
    "ledger.pressure_headroom_gb": "pressure band: pause dispatch when the cgroup footprint climbs within this many GB of the budget — scale DOWN on small-budget machines (ASTERISM_PRESSURE_HEADROOM_GB; 8.0)",
    "ledger.pressure_release_slack_gb": "pressure band: extra calm below the pause line before dispatch resumes (ASTERISM_PRESSURE_RELEASE_SLACK_GB; 4.0)",
    "dispatch.ram_budget": "adaptive RAM ledger budget, '28G' or '85%' — splits the worker economy: Lean slots follow target_slots(budget - NL reserve), NL kinds admit on measured available RAM; unset = legacy static dispatch.pool semantics (ASTERISM_RAM_BUDGET; '')",
    "dispatch.blocked_kinds": "operator hold — comma list of queue kinds this machine must not dispatch, e.g. 'Formalizer,Librarian'; unknown names are ignored, so a typo holds nothing (ASTERISM_BLOCKED_KINDS; '')",
    "dispatch.budget_sec": "daemon wall budget (ASTERISM_BUDGET_SEC; 1800)",
    "dispatch.intake_timeout_sec": "Formalizer intake turn spawn cap (ASTERISM_INTAKE_TIMEOUT_SEC; 300)",
    "dispatch.shelve_threshold": "attempts before shelve (ASTERISM_SHELVE_THRESHOLD; 8)",
    "dispatch.handoff_on_code_change": "daemon drains + hands off to a fresh daemon when the source tree OR Asterism.yaml/.env changes under it (ASTERISM_HANDOFF_ON_CODE_CHANGE; true)",
    "dispatch.quota_wait": "confirmed-exhausted subscription window pauses dispatch until resets_at instead of exiting (ASTERISM_QUOTA_WAIT; false — riding further windows is opt-in, user 2026-07-18)",
    "dispatch.spawn_timeout_sec": "main spawn SIGKILL cap (ASTERISM_SPAWN_TIMEOUT_SEC; 900)",
    "dispatch.postmortem_timeout_sec": "postmortem spawn cap (ASTERISM_POSTMORTEM_TIMEOUT_SEC; 180)",
    "dispatch.trap_check_sec": "watchdog thinking-trap check point (ASTERISM_TRAP_CHECK_SEC; 660)",
    "dispatch.silence_threshold_sec": "watchdog silence AND-condition (ASTERISM_SILENCE_THRESHOLD_SEC; 300)",
    "dispatch.silent_kill_sec": "watchdog silent-kill: joint silence on BOTH clocks that kills without a trap signature (ASTERISM_SILENT_KILL_SEC; 2400; 0=off)",
    "dispatch.completion_grace_sec": "watchdog completion-reclaim grace (ASTERISM_COMPLETION_GRACE_SEC; 120)",
    "dispatch.classify_trap_cap_sec": "librarian classify trap cap ceiling (3600)",
    "dispatch.classify_trap_per_decl_sec": "classify trap budget per kept decl (12)",
    "gateway.port": "LSP gateway HTTP port (ASTERISM_GATEWAY_PORT; 8765)",
    "gateway.interactive_slots": "reserved gateway slots for the serve UI editor (ASTERISM_INTERACTIVE_SLOTS; 1)",
    "gateway.lean_memory_cap_mb": "per-process commit cap on the lake/lean tree via Job Object, 0 disables (ASTERISM_LEAN_MEMORY_CAP_MB; 8192)",
    "gateway.slot_recycle_mb": "private-bytes above which an IDLE, UNCLAIMED slot restarts its worker; far below the job cap on purpose — that one caps one elaboration, this one caps accumulation across many (ASTERISM_SLOT_RECYCLE_MB; 1500)",
    "strategist.interval_min": "T1 routine wake cadence (ASTERISM_STRATEGIST_INTERVAL_MIN; 120.0)",
    "strategist.verify_retry": "strategist verify/Adversary revision rounds per wake (ASTERISM_STRATEGIST_VERIFY_RETRY; 6)",
    "strategist.timeout_sec": "strategist wake spawn cap — hang guard, not a work budget (ASTERISM_STRATEGIST_TIMEOUT_SEC; 10800)",
    "adversary.provider": "judge seat backend — spawn resolution + provenance stamp (survey P1, 2026-08-29)",
    "adversary.model": "judge seat model — spawn resolution + provenance stamp (survey P1)",
    "adversary.reasoning_effort": "judge effort knob (codex seats) — also stamped into provenance (survey P1)",
    "adversary.timeout_sec": "adversary spawn cap — hang guard, not a work budget (ASTERISM_ADVERSARY_TIMEOUT_SEC; 7200)",
    "verify.olean_warm": "background olean warmer kill switch #103 (ASTERISM_OLEAN_WARM; True)",
    "lessons.reflection_enabled": "reflection spawn kill switch (ASTERISM_LESSONS_REFLECTION_ENABLED; True)",
    "feedback.enabled": "dev-mode agent feedback questionnaire (ASTERISM_FEEDBACK_ENABLED; False)",
    "presearch.enabled": "target-1 per-node pre-search toggle (True)",
    "presearch.timeout_sec": "pre-search agent budget (ASTERISM_PRESEARCH_TIMEOUT_SEC)",
    "library.require_signoff": "Ingest pauses for approve-ingest (True)",
    "paper_index.timeout_sec": "paper-map one-shot spawn budget (1200)",
    "explainer.model": "serve chat-explainer spawn model (teammate serve/chat.py; registered here to keep the drift gate green)",
    "<kind>.model": "per-pipeline model override (ASTERISM_<KIND>_MODEL → ASTERISM_AGENT_MODEL)",
    "<kind>.provider": "per-pipeline LLM provider (ASTERISM_<KIND>_PROVIDER → ASTERISM_LLM_PROVIDER; 'claude')",
    "<kind>.reasoning_effort": "per-pipeline reasoning depth, codex only (ASTERISM_<KIND>_REASONING_EFFORT; 'xhigh'). claude carries no such knob — its thinking budget is set per spawn from the wall-clock budget.",
    "zen.base_url": "zen-flavor codex upstream — the local shim that translates /responses to OpenRouter and self-executes tools (ASTERISM_ZEN_BASE_URL; http://127.0.0.1:8898/v1)",
    "zen.api_key": "yaml fallback for the zen seat's key when OPENCODE_ZEN_API_KEY is unset; the shim itself reads OPENROUTER_API_KEY from .env (OPENCODE_ZEN_API_KEY; '')",
}

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


def get(
    key_path: str,
    *,
    default: Any = None,
    env_var: str | None = None,
    legacy_env: Sequence[str] = (),
    cast: Callable[[str], Any] | None = None,
    workspace: Path | None = None,
) -> Any:
    """Resolve a single field via env → yaml → legacy_env → default.

    `key_path`: dotted path into Asterism.yaml, e.g. 'dispatch.pool'.
    `cast`: applied to env-var strings AND yaml values (in case yaml
            stores e.g. '4' as a string). None means no transform.
    `legacy_env`: ordered list of additional env vars consulted after
                  yaml but before default; first non-empty wins.
    """
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
            "adversary")

UI_EDITABLE_KEYS: "dict[str, tuple[type, str]]" = {
    "formalizer.model": (str, "model that turns the argued proof into Lean (prove/split/mint)"),
    "strategist.model": (str, "model that plans the campaign"),
    "presearch.model": (str, "model that scouts Mathlib before proving"),
    "librarian.model": (str, "model that curates the Library"),
    "adversary.model": (str, "model that adversarially reviews the research programme"),
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

#: dropdown choices for `.model` keys — what the UI offers (free text
#: stays possible via yaml/.env; the UI's job is killing typos). Keep
#: in sync with the model tiers the pipelines actually target.
MODEL_CHOICES_BY_PROVIDER: "dict[str, list[str]]" = {
    "claude": [
        "claude-fable-5",
        "claude-opus-4-8",
        "claude-sonnet-5",
        "claude-haiku-4-5",
    ],
    # `agy models` is the live list (11 as of 2026-08-09) and the UI asks
    # the CLI for it; these are the tiers we actually seat, so the picker
    # is useful before the probe returns.
    "antigravity": [
        "gemini-3.1-pro-high",
        "gemini-3.6-flash-high",
        "gemini-3.6-flash-medium",
    ],
    "codex": [
        "gpt-5.6-luna",
    ],
}

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


#: per-key grammar for str knobs whose legal values the generic
#: `[A-Za-z0-9._-]+` guard would reject (a comma list, a percentage).
#: Each returns (canonical value, error) — one of the two is empty.
_STR_VALIDATORS: "dict[str, Callable[[str], tuple[str, str | None]]]" = {
    "dispatch.blocked_kinds": _check_blocked_kinds,
    "dispatch.ram_budget": _check_ram_budget,
}

#: the env var the ENGINE reads for a key. `resolved` claims to be
#: "what a run would actually use", and the env var is the top of that
#: chain — a row that skips it shows the yaml while the daemon runs on
#: the environment, which is two answers to one question. The `.model`
#: / `.provider` rows have resolved this way since 2026-08-14; the
#: dispatch knobs joined them 2026-09-03.
_UI_ENV_VAR = {
    "dispatch.pool": "ASTERISM_POOL",
    "ledger.idle_spares": "ASTERISM_IDLE_SPARES",
    "dispatch.budget_sec": "ASTERISM_BUDGET_SEC",
    "dispatch.shelve_threshold": "ASTERISM_SHELVE_THRESHOLD",
    "dispatch.quota_wait": "ASTERISM_QUOTA_WAIT",
    "dispatch.blocked_kinds": "ASTERISM_BLOCKED_KINDS",
    "dispatch.ram_budget": "ASTERISM_RAM_BUDGET",
}

#: engine-side defaults for UI bool keys (must mirror the reader's
#: `config.get(..., default=…)` — the Settings select shows what a run
#: would actually do when the key is unset)
_UI_BOOL_DEFAULTS = {
    "dispatch.quota_wait": False,  # riding further windows is opt-in
}


def ui_settings(workspace: Path) -> "list[dict[str, object]]":
    """Snapshot of every UI-editable key: yaml value (None = unset) +
    resolved value (env > yaml > default chain, i.e. what a run would
    actually use)."""
    _reset_cache()
    data = load(workspace)
    out: list[dict[str, object]] = []
    for key, (typ, desc) in UI_EDITABLE_KEYS.items():
        cur: object = data
        for part in key.split("."):
            cur = cur.get(part) if isinstance(cur, dict) else None
        resolved = get(key, workspace=workspace,
                       env_var=_UI_ENV_VAR.get(key),
                       cast=int if typ is int else None)
        if key.endswith(".provider"):
            # resolve it the way the ENGINE resolves it, or this row and
            # the model row beside it — which asks with the default —
            # would disagree about the same seat on the same page
            resolved = get(key,
                           env_var=f"ASTERISM_{key.split('.')[0].upper()}_PROVIDER",
                           legacy_env=("ASTERISM_LLM_PROVIDER",),
                           default="claude", workspace=workspace)
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
            prov = get(f"{seat}.provider",
                       env_var=f"ASTERISM_{seat.upper()}_PROVIDER",
                       legacy_env=("ASTERISM_LLM_PROVIDER",),
                       default="claude", workspace=workspace)
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
        elif typ is bool:
            # booleans render as a two-way select, never a free-text box.
            # Unset resolves to the ENGINE's default (mirrored below) —
            # showing "false" for an engine that defaults true is a lie.
            row["choices"] = ["true", "false"]
            if resolved is None:
                resolved = _UI_BOOL_DEFAULTS.get(key, False)
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
