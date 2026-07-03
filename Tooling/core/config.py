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
    "dispatch.spawn_timeout_sec": "main spawn SIGKILL cap (ASTERISM_SPAWN_TIMEOUT_SEC; 900)",
    "dispatch.postmortem_timeout_sec": "postmortem spawn cap (ASTERISM_POSTMORTEM_TIMEOUT_SEC; 180)",
    "dispatch.trap_check_sec": "watchdog thinking-trap check point (ASTERISM_TRAP_CHECK_SEC; 660)",
    "dispatch.silence_threshold_sec": "watchdog silence AND-condition (ASTERISM_SILENCE_THRESHOLD_SEC; 300)",
    "dispatch.completion_grace_sec": "watchdog completion-reclaim grace (ASTERISM_COMPLETION_GRACE_SEC; 120)",
    "dispatch.classify_trap_cap_sec": "librarian classify trap cap ceiling (3600)",
    "dispatch.classify_trap_per_decl_sec": "classify trap budget per kept decl (12)",
    "gateway.port": "LSP gateway HTTP port (ASTERISM_GATEWAY_PORT; 8765)",
    "strategist.interval_min": "T1 routine wake cadence (ASTERISM_STRATEGIST_INTERVAL_MIN; 60.0)",
    "strategist.verify_retry": "strategist in-pipeline verify retry toggle (True)",
    "verify.olean_warm": "background olean warmer kill switch #103 (ASTERISM_OLEAN_WARM; True)",
    "lessons.reflection_enabled": "reflection spawn kill switch (ASTERISM_LESSONS_REFLECTION_ENABLED; True)",
    "feedback.enabled": "dev-mode agent feedback questionnaire (ASTERISM_FEEDBACK_ENABLED; False)",
    "presearch.enabled": "target-1 per-node pre-search toggle (True)",
    "presearch.timeout_sec": "pre-search agent budget (ASTERISM_PRESEARCH_TIMEOUT_SEC)",
    "library.require_signoff": "Ingest pauses for approve-ingest (True)",
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
