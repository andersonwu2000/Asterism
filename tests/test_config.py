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
        "builder:\n  provider: codex\n  model: gpt-5.6-luna\n",
        encoding="utf-8",
    )
    assert config.get(
        "builder.provider", default="claude", workspace=tmp_path,
    ) == "codex"
    assert config.get(
        "builder.model", default="x", workspace=tmp_path,
    ) == "gpt-5.6-luna"


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

def test_dispatcher_shelve_threshold_via_yaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """shelve_threshold lives under dispatch.* (goal-level cap). The
    builder.threshold / dispatch.builder_threshold keys are retired
    with the Formalizer merge — no worker escalation to size for."""
    monkeypatch.delenv("ASTERISM_SHELVE_THRESHOLD", raising=False)
    (tmp_path / "Asterism.yaml").write_text(
        "dispatch:\n"
        "  shelve_threshold: 10\n",
        encoding="utf-8",
    )
    st = config.get("dispatch.shelve_threshold", default=8,
                    env_var="ASTERISM_SHELVE_THRESHOLD",
                    cast=int, workspace=tmp_path)
    assert st == 10


def test_provider_resolution_via_yaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """builder.provider in yaml routes get_provider('builder') there."""
    from Tooling import llm
    for v in ("ASTERISM_BUILDER_PROVIDER", "ASTERISM_LLM_PROVIDER"):
        monkeypatch.delenv(v, raising=False)
    (tmp_path / "Asterism.yaml").write_text(
        "builder:\n  provider: openai\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    config._reset_cache()
    p = llm.get_provider(kind="builder")
    assert type(p).__name__ == "OpenAIProvider"


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


# ---------------------------------------------------------------------
# task #13 — .env file (file-form env vars; user design: no extra
# precedence tier — real env > .env > yaml > legacy > default)
# ---------------------------------------------------------------------

def test_dotenv_beats_yaml_loses_to_real_env(tmp_path, monkeypatch):
    monkeypatch.delenv("ASTERISM_POOL", raising=False)
    (tmp_path / "Asterism.yaml").write_text(
        "dispatch:\n  pool: 4\n", encoding="utf-8")
    (tmp_path / ".env").write_text(
        "# local tuning\nASTERISM_POOL=2\n", encoding="utf-8")
    config._reset_cache()
    assert config.get("dispatch.pool", default=99, cast=int,
                      env_var="ASTERISM_POOL", workspace=tmp_path) == 2
    # real process env still wins over the file
    monkeypatch.setenv("ASTERISM_POOL", "7")
    config._reset_cache()
    assert config.get("dispatch.pool", default=99, cast=int,
                      env_var="ASTERISM_POOL", workspace=tmp_path) == 7
    config._reset_cache()


def test_dotenv_parsing_and_absence(tmp_path, monkeypatch):
    monkeypatch.delenv("ASTERISM_X_TEST", raising=False)
    monkeypatch.delenv("ASTERISM_POOL", raising=False)
    # absent .env → yaml/default chain untouched
    (tmp_path / "Asterism.yaml").write_text(
        "dispatch:\n  pool: 3\n", encoding="utf-8")
    config._reset_cache()
    assert config.get("dispatch.pool", default=99, cast=int,
                      env_var="ASTERISM_POOL", workspace=tmp_path) == 3
    # quotes stripped, comments/blank/malformed lines ignored
    (tmp_path / ".env").write_text(
        '\n# comment\nnot a pair\nASTERISM_X_TEST="hello"\n',
        encoding="utf-8")
    config._reset_cache()
    assert config.get("x.test", default="d",
                      env_var="ASTERISM_X_TEST", workspace=tmp_path) == "hello"
    config._reset_cache()


# ---------------------------------------------------------------------
# resolve_workspace — the single workspace-resolution entrypoint
# (frontend charter §5-1): breaks the chicken-and-egg of "reading config
# requires the workspace" for serve / managed-workspace launches.
# ---------------------------------------------------------------------

def test_resolve_workspace_explicit_wins(tmp_path, monkeypatch):
    from Tooling.core import config
    ws = tmp_path / "w"
    ws.mkdir()
    monkeypatch.setenv("ASTERISM_WORKSPACE", str(tmp_path / "other"))
    assert config.resolve_workspace(ws) == ws.resolve()


def test_resolve_workspace_env_then_cwd(tmp_path, monkeypatch):
    from Tooling.core import config
    env_ws = tmp_path / "envws"
    env_ws.mkdir()
    monkeypatch.setenv("ASTERISM_WORKSPACE", str(env_ws))
    assert config.resolve_workspace() == env_ws.resolve()
    # env unset + cwd looks like a workspace -> cwd (historical behavior)
    monkeypatch.delenv("ASTERISM_WORKSPACE")
    cwd_ws = tmp_path / "cwdws"
    (cwd_ws / "Problems").mkdir(parents=True)
    monkeypatch.chdir(cwd_ws)
    assert config.resolve_workspace() == cwd_ws


def test_resolve_workspace_errors_are_actionable(tmp_path, monkeypatch):
    from Tooling.core import config
    import pytest
    monkeypatch.delenv("ASTERISM_WORKSPACE", raising=False)
    bare = tmp_path / "bare"
    bare.mkdir()
    monkeypatch.chdir(bare)
    monkeypatch.setattr(config.Path, "home", lambda: bare)  # no ~/Asterism
    with pytest.raises(FileNotFoundError, match="ASTERISM_WORKSPACE"):
        config.resolve_workspace()
    with pytest.raises(FileNotFoundError, match="does not exist"):
        config.resolve_workspace(tmp_path / "nope")


def test_load_error_set_on_unparseable_yaml(tmp_path, monkeypatch):
    """B4 (2026-07-24): a present-but-unparseable config must be
    detectable so state-changing commands refuse instead of silently
    running on defaults."""
    from Tooling.core import config as cfg
    cfg._reset_cache()
    (tmp_path / "Asterism.yaml").write_text(
        "dispatch:\n  pool: [unclosed", encoding="utf-8")
    try:
        assert cfg.load(tmp_path) == {}
        err = cfg.load_error(tmp_path)
        assert err and "Asterism.yaml" in err
    finally:
        cfg._reset_cache()


def test_load_error_none_on_good_or_missing_yaml(tmp_path):
    from Tooling.core import config as cfg
    cfg._reset_cache()
    try:
        assert cfg.load_error(tmp_path) is None  # missing file
        (tmp_path / "Asterism.yaml").write_text(
            "dispatch:\n  pool: 4\n", encoding="utf-8")
        cfg._reset_cache()
        assert cfg.load_error(tmp_path) is None
    finally:
        cfg._reset_cache()


def test_daemon_start_refuses_on_unparseable_config(tmp_path):
    from Tooling.core import cli as _cli
    from Tooling.core import config as cfg
    cfg._reset_cache()
    (tmp_path / "Asterism.yaml").write_text(
        "dispatch:\n  pool: [unclosed", encoding="utf-8")
    try:
        code, msg = _cli.daemon_start(tmp_path)
        assert code == 1 and "unparseable" in msg
    finally:
        cfg._reset_cache()


def test_dotenv_reload_on_file_change(tmp_path, monkeypatch):
    """SP7 autopsy 2026-09-02: the gateway survives daemon handoffs, so
    its process-lifetime dotenv cache froze ASTERISM_BUILD_NEED_GB at
    birth — a .env retune never reached the build gate and every lease
    saturated at 900s against a stale threshold. The cache must follow
    the file's mtime; a real process env var still wins."""
    import os
    import time as _t
    from Tooling.core import config as cfg
    monkeypatch.delenv("PROBE_DOTENV_KEY", raising=False)
    p = tmp_path / ".env"
    p.write_text("PROBE_DOTENV_KEY=first\n", encoding="utf-8")
    monkeypatch.setattr(cfg, "_dotenv", None)
    monkeypatch.setattr(cfg, "_dotenv_workspace", None)
    assert cfg._env("PROBE_DOTENV_KEY", tmp_path) == "first"
    _t.sleep(0.02)
    p.write_text("PROBE_DOTENV_KEY=second\n", encoding="utf-8")
    os.utime(p, (_t.time() + 5, _t.time() + 5))  # force a visible mtime step
    assert cfg._env("PROBE_DOTENV_KEY", tmp_path) == "second", \
        "a .env edit must reach a long-lived process without a restart"


# ---------------------------------------------------------------------
# UI settings chokepoint (`/api/config` → set_ui_setting / ui_settings)
# ---------------------------------------------------------------------
#
# The two str knobs the console gained on 2026-09-03 (HID §1.4) carry
# grammars the generic `[A-Za-z0-9._-]+` guard rejects outright — a
# comma list and a percentage. A knob whose legal value the writer
# refuses is a control that promises nothing, which is the exact
# failure `test_config_ui_keys.py` exists to watch.

def test_ui_blocked_kinds_takes_a_comma_list_and_canonicalizes_it(
        tmp_path: Path) -> None:
    rc, msg = config.set_ui_setting(tmp_path, "dispatch.blocked_kinds",
                                    " formalizer , LIBRARIAN ")
    assert rc == 0, msg
    assert config.get("dispatch.blocked_kinds",
                      workspace=tmp_path) == "Formalizer,Librarian"


def test_ui_blocked_kinds_refuses_a_kind_the_queue_never_heard_of(
        tmp_path: Path) -> None:
    """Unknown names are IGNORED by the reader (a typo holds nothing
    rather than everything) — so the writer is the only place that can
    tell the person their hold will not hold."""
    rc, msg = config.set_ui_setting(tmp_path, "dispatch.blocked_kinds",
                                    "Formalizer,Adversary")
    assert rc == 1 and "Adversary" in msg
    assert not (tmp_path / "Asterism.yaml").exists()


def test_ui_ram_budget_takes_the_parse_budget_grammar(
        tmp_path: Path) -> None:
    for spec in ("26G", "85%", "31.5GB"):
        rc, msg = config.set_ui_setting(tmp_path, "dispatch.ram_budget",
                                        spec)
        assert rc == 0, msg
        config._reset_cache()
        assert config.get("dispatch.ram_budget", workspace=tmp_path) == spec
    rc, msg = config.set_ui_setting(tmp_path, "dispatch.ram_budget",
                                    "plenty")
    assert rc == 1 and "plenty" in msg


def test_ui_str_knobs_can_be_cleared_back_to_unset(tmp_path: Path) -> None:
    """Empty is a legal VALUE for both (no hold / legacy static pool),
    so the page must be able to write it back — a bare `key:` parses as
    None and would fail the writer's own read-back check."""
    assert config.set_ui_setting(
        tmp_path, "dispatch.blocked_kinds", "Strategist")[0] == 0
    rc, msg = config.set_ui_setting(tmp_path, "dispatch.blocked_kinds", "")
    assert rc == 0, msg
    config._reset_cache()
    assert config.get("dispatch.blocked_kinds", default="",
                      workspace=tmp_path) == ""


def test_ui_rows_resolve_the_way_a_run_resolves(
        tmp_path: Path, monkeypatch) -> None:
    """`resolved` is "what a run would actually use". The env var is the
    top of that chain for every dispatch knob, and a page that shows the
    yaml while the daemon reads the env is two answers to one question
    (the `.provider` rows have resolved through their env var since
    2026-08-14; the rest did not)."""
    (tmp_path / "Asterism.yaml").write_text(
        "dispatch:\n  pool: 4\n  blocked_kinds: Strategist\n",
        encoding="utf-8")
    monkeypatch.setenv("ASTERISM_POOL", "9")
    monkeypatch.setenv("ASTERISM_BLOCKED_KINDS", "Formalizer")
    rows = {r["key"]: r for r in config.ui_settings(tmp_path)}
    assert rows["dispatch.pool"]["yaml"] == 4
    assert rows["dispatch.pool"]["resolved"] == 9
    assert rows["dispatch.blocked_kinds"]["yaml"] == "Strategist"
    assert rows["dispatch.blocked_kinds"]["resolved"] == "Formalizer"


def test_a_seats_reasoning_effort_is_settable_from_the_console(
    tmp_path: Path,
) -> None:
    """The one axis that changes what a codex wake COSTS was env/yaml
    only, so the Seats section could show a seat's model and not the
    depth it thinks at (owner, 2026-09-06). It writes like every other
    knob — one line, the file's comments untouched — and it refuses a
    value the provider does not have."""
    (tmp_path / "Asterism.yaml").write_text(
        "strategist:\n"
        "  provider: codex   # the seat's backend\n"
        "  model: gpt-5.6-luna\n"
        "\n"
        "# a comment nothing may eat\n"
        "dispatch:\n"
        "  pool: 2\n",
        encoding="utf-8")
    rc, msg = config.set_ui_setting(tmp_path, "strategist.reasoning_effort",
                                    "high")
    assert rc == 0, msg
    text = (tmp_path / "Asterism.yaml").read_text(encoding="utf-8")
    assert "# a comment nothing may eat" in text
    assert "# the seat's backend" in text
    assert config.get("strategist.reasoning_effort", workspace=tmp_path,
                      default="") == "high"
    assert config.get("dispatch.pool", workspace=tmp_path, cast=int) == 2

    rc, msg = config.set_ui_setting(tmp_path, "strategist.reasoning_effort",
                                    "ludicrous")
    assert rc != 0
    assert "xhigh" in msg


def test_the_effort_row_says_which_backends_have_the_knob(
    tmp_path: Path,
) -> None:
    """A control is a promise that turning it does something. claude
    derives its thinking budget per spawn from the wall clock, so the
    row has to name the backends the knob is real on rather than sit
    there looking live on a seat that ignores it."""
    (tmp_path / "Asterism.yaml").write_text(
        "strategist:\n  provider: claude\n  model: claude-opus-5\n",
        encoding="utf-8")
    rows = {str(r["key"]): r for r in config.ui_settings(tmp_path)}
    row = rows["strategist.reasoning_effort"]
    assert row["choices"] == list(config.EFFORT_CHOICES)
    assert row["provider"] == "claude"
    assert row["applies"] is False
    assert "claude" in str(row["description"])
