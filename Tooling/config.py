"""Asterism.yaml — project-level config with env override.

Each tunable field has a 4-step resolution chain:

    1. env var (ASTERISM_X)            — one-off override (CI / debug)
    2. Asterism.yaml at workspace root — project default
    3. legacy env var(s)               — backwards compat for setups
                                         predating Asterism.yaml
    4. built-in default                — used when none of the above set

env always wins so testing can override without touching the file.
Asterism.yaml is optional; the file's absence is identical to writing
an empty `{}`.

Field map (Asterism.yaml → env var fallback → built-in default):

    dispatch.pool                  ASTERISM_POOL                4
    dispatch.budget_sec            ASTERISM_BUDGET_SEC          1800
    dispatch.shelve_threshold      ASTERISM_SHELVE_THRESHOLD    8
    dispatch.spawn_timeout_sec     ASTERISM_SPAWN_TIMEOUT_SEC   900
    dispatch.postmortem_timeout_sec  ASTERISM_POSTMORTEM_TIMEOUT_SEC  180
    dispatch.rescue_timeout_sec    ASTERISM_RESCUE_TIMEOUT_SEC  180
    dispatch.stop_timeout_sec      ASTERISM_STOP_TIMEOUT_SEC    30
    dispatch.idle_window_sec       ASTERISM_IDLE_WINDOW_SEC     480
    gateway.workers                ASTERISM_GATEWAY_WORKERS     4
    gateway.port                   ASTERISM_GATEWAY_PORT        8765
    builder.threshold              ASTERISM_BUILDER_THRESHOLD   3
                                                                (legacy yaml
                                                                key:
                                                                dispatch.builder_threshold)
    builder.provider               ASTERISM_BUILDER_PROVIDER →
                                   ASTERISM_LLM_PROVIDER        'claude'
    builder.model                  ASTERISM_BUILDER_MODEL →
                                   ASTERISM_AGENT_MODEL         provider-default
    backward.provider              ASTERISM_BACKWARD_PROVIDER →
                                   ASTERISM_LLM_PROVIDER        'claude'
    backward.model                 ASTERISM_BACKWARD_MODEL →
                                   ASTERISM_AGENT_MODEL         provider-default

Provider-specific knobs (gemini model / openai base url / claude
tools) stay env-only — they're cross-cutting toggles that don't
fit the per-Problem mental model and are seldom changed.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Sequence


_CONFIG_FILENAME = "Asterism.yaml"

# Module-level cache so reading the file once per daemon-run avoids
# repeated yaml.safe_load() on hot paths (every spawn_llm reads model;
# every dispatcher tick reads thresholds). Tests reset via _reset_cache.
_cache: dict[str, Any] | None = None
_cache_workspace: Path | None = None


def _reset_cache() -> None:
    """Test helper — invalidate the in-process cache so the next
    `load()` re-reads the file. Safe to call between test cases."""
    global _cache, _cache_workspace
    _cache = None
    _cache_workspace = None


def load(workspace: Path | None = None) -> dict[str, Any]:
    """Read Asterism.yaml from workspace (default cwd). Empty dict
    when the file is missing or unparseable (a warning is emitted on
    parse failure but the daemon continues — env+default chain still
    works)."""
    global _cache, _cache_workspace
    workspace = workspace or Path.cwd()
    if _cache is not None and _cache_workspace == workspace:
        return _cache

    cfg_path = workspace / _CONFIG_FILENAME
    if not cfg_path.exists():
        _cache = {}
        _cache_workspace = workspace
        return _cache

    try:
        import yaml  # PyYAML already a dep (Manifest frontmatter)
        data = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
        _cache = data if isinstance(data, dict) else {}
    except Exception as exc:
        # Don't crash the daemon over a malformed config — warn and
        # fall back to env+default. This matches manifest.parse's
        # lenient-parse policy.
        print(f"[config] WARNING: {cfg_path} unparseable ({exc}); "
              f"falling back to env+defaults", flush=True)
        _cache = {}
    _cache_workspace = workspace
    return _cache


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
    # 1. primary env var
    if env_var:
        v = os.environ.get(env_var)
        if v is not None and v != "":
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

    # 3. legacy env(s)
    for legacy in legacy_env:
        v = os.environ.get(legacy)
        if v is not None and v != "":
            return cast(v) if cast else v

    # 4. default
    return default
