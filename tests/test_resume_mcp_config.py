"""Every tail turn that resumes a work spawn's session must carry the
work spawn's own MCP config: codex re-renders config.toml per spawn,
so a resume without it is re-homed onto a TOOLLESS envelope — the
parting-note turn had only codex builtins and 124 consecutive
codex-path deaths left no `_progress.md` (0/105 local codex era +
0/19 cloud, 2026-08-24). The feedback tail fixed this for itself and
the fix never propagated (rule 4); `pipeline.resume_mcp_config` is
now the one source and these tests hold all three tails to it."""
from pathlib import Path

import Tooling.pipeline as pipeline


def test_resume_mcp_config_prefers_the_gateway_config(tmp_path):
    assert pipeline.resume_mcp_config(tmp_path) is None
    (tmp_path / "_mcp_tools.json").write_text("{}", encoding="utf-8")
    assert (pipeline.resume_mcp_config(tmp_path)
            == tmp_path / "_mcp_tools.json")
    (tmp_path / "_mcp_config.json").write_text("{}", encoding="utf-8")
    assert (pipeline.resume_mcp_config(tmp_path)
            == tmp_path / "_mcp_config.json")


def test_postmortem_resume_carries_the_work_spawns_mcp_config(
        tmp_path, monkeypatch):
    captured: dict = {}

    def fake_spawn(**kw):
        captured.update(kw)
        return 0

    from Tooling.pipeline import agent as agent_mod
    monkeypatch.setattr(agent_mod, "spawn_llm", fake_spawn)
    (tmp_path / "_mcp_config.json").write_text("{}", encoding="utf-8")
    pipeline._attempt_postmortem(
        seat="formalizer", prompt_path=tmp_path / "p.md",
        problem_dir=tmp_path, attempts_dir=tmp_path, session_id="sid")
    assert captured["mcp_config_path"] == tmp_path / "_mcp_config.json"
    assert captured["is_postmortem"] is True


def test_all_three_tails_route_through_the_one_helper():
    """Mechanism pin: postmortem / reflection / feedback must all call
    resume_mcp_config — a fourth tail added without it re-opens the
    toolless-resume class."""
    root = Path(pipeline.__file__).resolve().parent
    for name in ("__init__.py", "_reflection.py", "_feedback.py"):
        src = (root / name).read_text(encoding="utf-8")
        assert "resume_mcp_config(" in src, f"{name} lost the helper"
    # and none of them re-inlines the file probe
    for name in ("_reflection.py", "_feedback.py"):
        src = (root / name).read_text(encoding="utf-8")
        assert '"_mcp_config.json"' not in src, (
            f"{name}: use resume_mcp_config, not an inline probe")
