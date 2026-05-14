"""Asterism.yaml + resolution chain (Tooling/config.get).

Each `config.get(...)` call walks env → yaml → legacy_env → default.
These tests pin every transition because the dispatcher /
provider modules now lean on this single function for *all*
thresholds and provider/model selection — silent breakage here
shifts the whole framework's behavior."""
from __future__ import annotations

from pathlib import Path

import pytest

from Tooling.core import config


# Reset the module-level cache around every test so workspace=tmp_path
# is fresh; otherwise the second test in a file would still see the
# first one's loaded data.
@pytest.fixture(autouse=True)
def _reset_config_cache() -> None:
    config._reset_cache()
    yield
    config._reset_cache()


# ---------------------------------------------------------------------
# load() — file presence / parse failure tolerance
# ---------------------------------------------------------------------

def test_load_missing_file_is_empty(tmp_path: Path) -> None:
    assert config.load(tmp_path) == {}


def test_load_parses_valid_yaml(tmp_path: Path) -> None:
    (tmp_path / "Asterism.yaml").write_text(
        "dispatch:\n  pool: 8\n  budget_sec: 3600\n",
        encoding="utf-8",
    )
    data = config.load(tmp_path)
    assert data == {"dispatch": {"pool": 8, "budget_sec": 3600}}


def test_load_handles_unparseable_file_gracefully(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """A broken YAML file must not crash the daemon — empty dict + warning."""
    (tmp_path / "Asterism.yaml").write_text(
        "dispatch:\n  pool: [unclosed\n", encoding="utf-8",
    )
    data = config.load(tmp_path)
    assert data == {}
    err = capsys.readouterr().out
    assert "WARNING" in err
    assert "Asterism.yaml" in err


def test_load_handles_non_dict_top_level(tmp_path: Path) -> None:
    """yaml.safe_load on `[1, 2, 3]` returns a list — must coerce to {}."""
    (tmp_path / "Asterism.yaml").write_text("- a\n- b\n", encoding="utf-8")
    assert config.load(tmp_path) == {}


def test_load_caches_per_workspace(tmp_path: Path) -> None:
    """Two calls with the same workspace should hit the cache (we don't
    assert the cache contents directly, but mutating the file between
    calls without _reset_cache() should still return the original)."""
    cfg = tmp_path / "Asterism.yaml"
    cfg.write_text("dispatch: {pool: 4}\n", encoding="utf-8")
    first = config.load(tmp_path)
    cfg.write_text("dispatch: {pool: 999}\n", encoding="utf-8")
    second = config.load(tmp_path)  # cached
    assert first == second
    config._reset_cache()
    third = config.load(tmp_path)  # re-read
    assert third == {"dispatch": {"pool": 999}}


# ---------------------------------------------------------------------
# get() — resolution chain
# ---------------------------------------------------------------------

def test_get_default_when_all_sources_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ASTERISM_POOL", raising=False)
    assert config.get(
        "dispatch.pool", default=4,
        env_var="ASTERISM_POOL", cast=int, workspace=tmp_path,
    ) == 4


def test_get_yaml_overrides_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ASTERISM_POOL", raising=False)
    (tmp_path / "Asterism.yaml").write_text(
        "dispatch:\n  pool: 12\n", encoding="utf-8")
    assert config.get(
        "dispatch.pool", default=4,
        env_var="ASTERISM_POOL", cast=int, workspace=tmp_path,
    ) == 12


def test_get_env_overrides_yaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """env var must beat Asterism.yaml — preserves CI / one-off override."""
    monkeypatch.setenv("ASTERISM_POOL", "20")
    (tmp_path / "Asterism.yaml").write_text(
        "dispatch:\n  pool: 12\n", encoding="utf-8")
    assert config.get(
        "dispatch.pool", default=4,
        env_var="ASTERISM_POOL", cast=int, workspace=tmp_path,
    ) == 20


def test_get_legacy_env_falls_through_after_yaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When primary env + yaml are both unset, legacy_env wins over default."""
    monkeypatch.delenv("ASTERISM_BUILDER_MODEL", raising=False)
    monkeypatch.setenv("ASTERISM_AGENT_MODEL", "claude-opus-4-7")
    assert config.get(
        "builder.model",
        env_var="ASTERISM_BUILDER_MODEL",
        legacy_env=("ASTERISM_AGENT_MODEL",),
        default="claude-sonnet-4-6",
        workspace=tmp_path,
    ) == "claude-opus-4-7"


def test_get_yaml_beats_legacy_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Project default in Asterism.yaml must beat legacy env fallback;
    legacy env is for setups predating the file."""
    monkeypatch.setenv("ASTERISM_AGENT_MODEL", "claude-opus-4-7")
    (tmp_path / "Asterism.yaml").write_text(
        "builder:\n  model: claude-haiku-4-5\n", encoding="utf-8")
    assert config.get(
        "builder.model",
        env_var="ASTERISM_BUILDER_MODEL",
        legacy_env=("ASTERISM_AGENT_MODEL",),
        default="x",
        workspace=tmp_path,
    ) == "claude-haiku-4-5"


def test_get_first_legacy_env_wins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When two legacy envs are listed, the first one set wins."""
    monkeypatch.setenv("FIRST", "alpha")
    monkeypatch.setenv("SECOND", "beta")
    assert config.get(
        "missing.key",
        legacy_env=("FIRST", "SECOND"),
        default="z",
        workspace=tmp_path,
    ) == "alpha"


def test_get_skips_empty_string_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An env var set to '' should be treated as unset (not an empty
    model name) — falls through to next source."""
    monkeypatch.setenv("ASTERISM_POOL", "")
    assert config.get(
        "dispatch.pool", default=4,
        env_var="ASTERISM_POOL", cast=int, workspace=tmp_path,
    ) == 4


def test_get_dotted_path_navigates_yaml(tmp_path: Path) -> None:
    (tmp_path / "Asterism.yaml").write_text(
        "builder:\n  provider: gemini\n  model: gemini-2.5-flash\n",
        encoding="utf-8",
    )
    assert config.get(
        "builder.provider", default="claude", workspace=tmp_path,
    ) == "gemini"
    assert config.get(
        "builder.model", default="x", workspace=tmp_path,
    ) == "gemini-2.5-flash"


def test_get_missing_dotted_path_falls_to_default(tmp_path: Path) -> None:
    """Partial yaml structure: builder section missing — falls to default."""
    (tmp_path / "Asterism.yaml").write_text(
        "dispatch:\n  pool: 8\n", encoding="utf-8")
    assert config.get(
        "builder.model", default="claude-sonnet-4-6", workspace=tmp_path,
    ) == "claude-sonnet-4-6"


def test_get_cast_applies_to_yaml_int(tmp_path: Path) -> None:
    """yaml may store numbers as int already; cast=int still works."""
    (tmp_path / "Asterism.yaml").write_text(
        "dispatch:\n  pool: 7\n", encoding="utf-8")
    v = config.get(
        "dispatch.pool", default=4, cast=int, workspace=tmp_path,
    )
    assert v == 7
    assert isinstance(v, int)


def test_get_cast_applies_to_env_string(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """env var strings must pass through cast (otherwise int math
    against the result blows up)."""
    monkeypatch.setenv("ASTERISM_POOL", "16")
    v = config.get(
        "dispatch.pool", default=4, cast=int,
        env_var="ASTERISM_POOL", workspace=tmp_path,
    )
    assert v == 16
    assert isinstance(v, int)


# ---------------------------------------------------------------------
# Wired-in callers — smoke that dispatcher + providers honor the chain
# ---------------------------------------------------------------------

def test_dispatcher_thresholds_via_yaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F47 — canonical placement: builder.threshold sits next to the
    Builder model it's sized for; shelve_threshold stays under
    dispatch.* (it's a goal-level cap spanning Builder + Backward)."""
    monkeypatch.delenv("ASTERISM_BUILDER_THRESHOLD", raising=False)
    monkeypatch.delenv("ASTERISM_SHELVE_THRESHOLD", raising=False)
    (tmp_path / "Asterism.yaml").write_text(
        "builder:\n"
        "  threshold: 5\n"
        "dispatch:\n"
        "  shelve_threshold: 10\n",
        encoding="utf-8",
    )
    bt = config.get("builder.threshold", default=3,
                    env_var="ASTERISM_BUILDER_THRESHOLD",
                    cast=int, workspace=tmp_path)
    st = config.get("dispatch.shelve_threshold", default=8,
                    env_var="ASTERISM_SHELVE_THRESHOLD",
                    cast=int, workspace=tmp_path)
    assert (bt, st) == (5, 10)


def test_dispatcher_threshold_legacy_yaml_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F47 — projects that wrote `dispatch.builder_threshold` (the
    pre-F47 layout) must keep working. Resolution goes builder.threshold
    first; falls back to the old key when the new one is absent."""
    monkeypatch.delenv("ASTERISM_BUILDER_THRESHOLD", raising=False)
    (tmp_path / "Asterism.yaml").write_text(
        "dispatch:\n"
        "  builder_threshold: 5\n",
        encoding="utf-8",
    )
    # Mirror the dispatcher's two-step lookup
    bt = config.get("builder.threshold", default=None,
                    env_var="ASTERISM_BUILDER_THRESHOLD",
                    cast=int, workspace=tmp_path)
    if bt is None:
        bt = config.get("dispatch.builder_threshold", default=3,
                        cast=int, workspace=tmp_path)
    assert bt == 5


def test_provider_resolution_via_yaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """builder.provider in yaml routes get_provider('builder') to gemini."""
    from Tooling import llm
    for v in ("ASTERISM_BUILDER_PROVIDER", "ASTERISM_LLM_PROVIDER"):
        monkeypatch.delenv(v, raising=False)
    (tmp_path / "Asterism.yaml").write_text(
        "builder:\n  provider: gemini\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    config._reset_cache()
    p = llm.get_provider(kind="builder")
    assert type(p).__name__ == "GeminiCliProvider"


def test_claude_model_resolution_via_yaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """builder.model in yaml selects Haiku even with no env vars set."""
    from Tooling.llm.claude_cli import resolve_model
    for v in ("ASTERISM_BUILDER_MODEL", "ASTERISM_AGENT_MODEL"):
        monkeypatch.delenv(v, raising=False)
    (tmp_path / "Asterism.yaml").write_text(
        "builder:\n  model: claude-haiku-4-5\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    config._reset_cache()
    assert resolve_model("builder") == "claude-haiku-4-5"


# ---------------------------------------------------------------------
# Phase 2 — new keys surfaced in Asterism.yaml (Task #69 batch)
# ---------------------------------------------------------------------

def test_yaml_overrides_spawn_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`dispatch.spawn_timeout_sec` resolves through the standard
    chain. Pre-Phase-2 this was a hardcoded `WORKER_TIMEOUT_SEC=900`
    constant in agent.py; surfacing makes spawn timeout tunable
    per-project without touching code."""
    monkeypatch.delenv("ASTERISM_SPAWN_TIMEOUT_SEC", raising=False)
    (tmp_path / "Asterism.yaml").write_text(
        "dispatch:\n  spawn_timeout_sec: 1200\n",
        encoding="utf-8",
    )
    assert config.get(
        "dispatch.spawn_timeout_sec", default=900,
        env_var="ASTERISM_SPAWN_TIMEOUT_SEC", cast=int,
        workspace=tmp_path,
    ) == 1200


def test_yaml_overrides_trap_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`dispatch.trap_check_sec` (2026-05-10 v4 watchdog) controls when
    the watchdog samples parser state for the AND trap condition. yaml
    override must propagate to the consumer without code edits."""
    monkeypatch.delenv("ASTERISM_TRAP_CHECK_SEC", raising=False)
    (tmp_path / "Asterism.yaml").write_text(
        "dispatch:\n  trap_check_sec: 540\n",
        encoding="utf-8",
    )
    assert config.get(
        "dispatch.trap_check_sec", default=660,
        env_var="ASTERISM_TRAP_CHECK_SEC", cast=int,
        workspace=tmp_path,
    ) == 540


def test_yaml_overrides_silence_threshold(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`dispatch.silence_threshold_sec` is the AND-condition silence
    threshold checked at trap_check_sec. yaml override must propagate."""
    monkeypatch.delenv("ASTERISM_SILENCE_THRESHOLD_SEC", raising=False)
    (tmp_path / "Asterism.yaml").write_text(
        "dispatch:\n  silence_threshold_sec: 240\n",
        encoding="utf-8",
    )
    assert config.get(
        "dispatch.silence_threshold_sec", default=300,
        env_var="ASTERISM_SILENCE_THRESHOLD_SEC", cast=int,
        workspace=tmp_path,
    ) == 240


def test_yaml_overrides_gateway_workers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`gateway.workers` is the primary RAM knob in Phase 2 (each
    worker holds ~3 GB of Mathlib elaborated state). Must be settable
    in the project's Asterism.yaml so the operator can tune to their
    machine's RAM budget."""
    monkeypatch.delenv("ASTERISM_GATEWAY_WORKERS", raising=False)
    (tmp_path / "Asterism.yaml").write_text(
        "gateway:\n  workers: 8\n",
        encoding="utf-8",
    )
    assert config.get(
        "gateway.workers", default=4,
        env_var="ASTERISM_GATEWAY_WORKERS", cast=int,
        workspace=tmp_path,
    ) == 8


def test_yaml_overrides_gateway_port(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`gateway.port` lets ops avoid port conflicts without setting
    env on every shell."""
    monkeypatch.delenv("ASTERISM_GATEWAY_PORT", raising=False)
    (tmp_path / "Asterism.yaml").write_text(
        "gateway:\n  port: 9090\n",
        encoding="utf-8",
    )
    assert config.get(
        "gateway.port", default=8765,
        env_var="ASTERISM_GATEWAY_PORT", cast=int,
        workspace=tmp_path,
    ) == 9090
