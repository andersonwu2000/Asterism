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

Provider-specific knobs (gemini model / openai base url / claude
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
    "dispatch.budget_sec": "daemon wall budget (ASTERISM_BUDGET_SEC; 1800)",
    "dispatch.builder_threshold": "attempts before Builder→Backward — legacy yaml key (3)",
    "builder.threshold": "modern alias of dispatch.builder_threshold (ASTERISM_BUILDER_THRESHOLD; falls back to legacy key)",
    "dispatch.shelve_threshold": "attempts before shelve (ASTERISM_SHELVE_THRESHOLD; 8)",
    "dispatch.handoff_on_code_change": "daemon drains + hands off to a fresh daemon when the source tree changes under it (ASTERISM_HANDOFF_ON_CODE_CHANGE; true)",
    "dispatch.quota_wait": "confirmed-exhausted subscription window pauses dispatch until resets_at instead of exiting (ASTERISM_QUOTA_WAIT; true)",
    "dispatch.spawn_timeout_sec": "main spawn SIGKILL cap (ASTERISM_SPAWN_TIMEOUT_SEC; 900)",
    "dispatch.postmortem_timeout_sec": "postmortem spawn cap (ASTERISM_POSTMORTEM_TIMEOUT_SEC; 180)",
    "dispatch.trap_check_sec": "watchdog thinking-trap check point (ASTERISM_TRAP_CHECK_SEC; 660)",
    "dispatch.silence_threshold_sec": "watchdog silence AND-condition (ASTERISM_SILENCE_THRESHOLD_SEC; 300)",
    "dispatch.completion_grace_sec": "watchdog completion-reclaim grace (ASTERISM_COMPLETION_GRACE_SEC; 120)",
    "dispatch.classify_trap_cap_sec": "librarian classify trap cap ceiling (3600)",
    "dispatch.classify_trap_per_decl_sec": "classify trap budget per kept decl (12)",
    "gateway.port": "LSP gateway HTTP port (ASTERISM_GATEWAY_PORT; 8765)",
    "gateway.interactive_slots": "reserved gateway slots for the serve UI editor (ASTERISM_INTERACTIVE_SLOTS; 1)",
    "strategist.interval_min": "T1 routine wake cadence (ASTERISM_STRATEGIST_INTERVAL_MIN; 60.0)",
    "strategist.audit_interval_min": "epistemic-auditor wake cadence, 0 disables (ASTERISM_AUDIT_INTERVAL_MIN; 180.0)",
    "strategist.verify_retry": "strategist verify/Adversary revision rounds per wake (ASTERISM_STRATEGIST_VERIFY_RETRY; 4)",
    "strategist.timeout_sec": "strategist wake spawn cap — hang guard, not a work budget (ASTERISM_STRATEGIST_TIMEOUT_SEC; 7200)",
    "adversary.timeout_sec": "adversary spawn cap — hang guard, not a work budget (ASTERISM_ADVERSARY_TIMEOUT_SEC; 7200)",
    "verify.olean_warm": "background olean warmer kill switch #103 (ASTERISM_OLEAN_WARM; True)",
    "lessons.reflection_enabled": "reflection spawn kill switch (ASTERISM_LESSONS_REFLECTION_ENABLED; True)",
    "feedback.enabled": "dev-mode agent feedback questionnaire (ASTERISM_FEEDBACK_ENABLED; False)",
    "presearch.enabled": "target-1 per-node pre-search toggle (True)",
    "presearch.timeout_sec": "pre-search agent budget (ASTERISM_PRESEARCH_TIMEOUT_SEC)",
    "library.require_signoff": "Ingest pauses for approve-ingest (True)",
    "paper_index.timeout_sec": "paper-map one-shot spawn budget (1200)",
    "<kind>.model": "per-pipeline model override (ASTERISM_<KIND>_MODEL → ASTERISM_AGENT_MODEL)",
    "<kind>.provider": "per-pipeline LLM provider (ASTERISM_<KIND>_PROVIDER → ASTERISM_LLM_PROVIDER; 'claude')",
}

# Module-level cache so reading the file once per daemon-run avoids
# repeated yaml.safe_load() on hot paths (every spawn_llm reads model;
# every dispatcher tick reads thresholds). Tests reset via _reset_cache.
_cache: dict[str, Any] | None = None
_cache_workspace: Path | None = None


def _reset_cache() -> None:
    """Test helper — invalidate the in-process cache so the next
    `load()` re-reads the file. Safe to call between test cases."""
    global _cache, _cache_workspace, _dotenv, _dotenv_workspace
    _cache = None
    _cache_workspace = None
    _dotenv = None
    _dotenv_workspace = None


def load(workspace: Path | None = None) -> dict[str, Any]:
    """Read Asterism.yaml from workspace (default cwd). Empty dict
    when the file is missing or unparseable (a warning is emitted on
    parse failure but the daemon continues — env+default chain still
    works)."""
    global _cache, _cache_workspace
    workspace = workspace or Path.cwd()
    if _cache is not None and _cache_workspace == workspace:
        return _cache

    def _read_one(path: Path) -> "dict[str, Any]":
        if not path.exists():
            return {}
        try:
            import yaml  # PyYAML already a dep (Manifest frontmatter)
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception as exc:
            # Don't crash the daemon over a malformed config — warn and
            # fall back to env+default. This matches manifest.parse's
            # lenient-parse policy.
            print(f"[config] WARNING: {path} unparseable ({exc}); "
                  f"skipping it", flush=True)
            return {}

    _cache = _read_one(workspace / _CONFIG_FILENAME)
    _cache_workspace = workspace
    return _cache


# ── .env — file-form env vars (task #13; user design call: no extra
# precedence tier — a .env entry IS an env var, just persisted) ──
# Simple KEY=VALUE lines at the workspace root, gitignored. A real
# process env var always beats the .env entry (standard dotenv
# semantics, keeps one-off `ASTERISM_X=… command` overrides working).
# Deliberately NOT injected into os.environ: kept in a module dict so
# test monkeypatching of the environment stays isolated.
_dotenv: "dict[str, str] | None" = None
_dotenv_workspace: Path | None = None


def _load_dotenv(workspace: Path) -> "dict[str, str]":
    global _dotenv, _dotenv_workspace
    if _dotenv is not None and _dotenv_workspace == workspace:
        return _dotenv
    out: "dict[str, str]" = {}
    path = workspace / ".env"
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
UI_EDITABLE_KEYS: "dict[str, tuple[type, str]]" = {
    "builder.model": (str, "model that writes proofs (bulk work)"),
    "backward.model": (str, "model that decomposes goals"),
    "strategist.model": (str, "model that plans the campaign"),
    "forward.model": (str, "model that builds vocabulary and claims"),
    "presearch.model": (str, "model that scouts Mathlib before proving"),
    "librarian.model": (str, "model that curates the Library"),
    "scholar.model": (str, "model that searches and fetches cited papers"),
    "dispatch.pool": (int, "max agents working at once"),
    "dispatch.budget_sec": (int, "wall-clock budget per engine run (seconds)"),
    "dispatch.shelve_threshold": (int, "failed attempts before a goal is shelved"),
    # dispatch.quota_wait deliberately NOT UI-editable (owner,
    # 2026-07-14): the feature hasn't met a real quota exhaustion yet —
    # an untested switch doesn't belong on the product surface. It
    # stays fully operable via Asterism.yaml / ASTERISM_QUOTA_WAIT;
    # re-admit it as a proper toggle once it has survived the field.
}

#: dropdown choices for `.model` keys — what the UI offers (free text
#: stays possible via yaml/.env; the UI's job is killing typos). Keep
#: in sync with the model tiers the pipelines actually target.
MODEL_CHOICES: "list[str]" = [
    "claude-fable-5",
    "claude-opus-4-8",
    "claude-sonnet-5",
    "claude-haiku-4-5",
]

_INT_BOUNDS = {
    "dispatch.pool": (1, 32),
    "dispatch.budget_sec": (60, 604800),
    "dispatch.shelve_threshold": (1, 50),
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
                       cast=int if typ is int else None)
        if typ is bool and resolved is not None:
            # env/.env supplies a string, yaml a real bool — one shape out
            resolved = str(resolved).strip().lower() in (
                "true", "1", "yes", "on")
        row: dict[str, object] = {
            "key": key, "yaml": cur, "resolved": resolved,
            "type": typ.__name__, "description": desc,
        }
        if key.endswith(".model"):
            choices = list(MODEL_CHOICES)
            # the resolved value (env/yaml may name anything) is always
            # a legal choice — never render a select that can't show
            # the current truth
            if resolved and str(resolved) not in choices:
                choices.insert(0, str(resolved))
            row["choices"] = choices
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
        if not _re.fullmatch(r"[A-Za-z0-9._-]+", value):
            return 1, f"FAIL: {key} value looks malformed"

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
        lines += [f"{section}:", f"  {leaf}: {value}"]
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
            lines[hit] = f"{m.group(1)}{value}{m.group(3) or ''}"
        else:
            lines.insert(sec_idx + 1, f"  {leaf}: {value}")

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
    return 0, f"OK: {key} = {value} (applies from the next engine run)"
