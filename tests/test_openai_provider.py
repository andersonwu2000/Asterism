"""OpenAIProvider: fence parser + HTTP integration (mocked)."""
from __future__ import annotations

import json
import socket
import urllib.error
from pathlib import Path
from unittest import mock

import pytest

from Tooling import llm
from Tooling.llm import openai_api


# ---------------------------------------------------------------------
# _parse_fenced_output (pure)
# ---------------------------------------------------------------------

def test_parse_fence_single_file() -> None:
    text = (
        "Some chatter from the model.\n"
        "==== FILE: PROPOSAL.md ====\n"
        "Decompose into 2 sub-goals: A and B.\n"
        "==== END ====\n"
    )
    out = openai_api._parse_fenced_output(text)
    assert out == {"PROPOSAL.md": "Decompose into 2 sub-goals: A and B."}


def test_parse_fence_multiple_files() -> None:
    text = (
        "==== FILE: PROPOSAL.md ====\nNarrative\n==== END ====\n"
        "==== FILE: patch_main.lean ====\n"
        "import Mathlib\ntheorem foo : T := by trivial\n"
        "==== END ====\n"
        "==== FILE: new_s7_sub_1.lean ====\n"
        "theorem s7_sub_1 : T := by sorry\n"
        "==== END ====\n"
    )
    out = openai_api._parse_fenced_output(text)
    assert set(out.keys()) == {
        "PROPOSAL.md", "patch_main.lean", "new_s7_sub_1.lean",
    }
    assert "import Mathlib" in out["patch_main.lean"]


def test_parse_fence_rejects_path_traversal() -> None:
    """Filenames containing slashes / parent traversal are silently
    discarded — provider must not be a write-anywhere primitive."""
    text = (
        "==== FILE: ../../etc/passwd ====\nbad\n==== END ====\n"
        "==== FILE: ok.md ====\ngood\n==== END ====\n"
    )
    out = openai_api._parse_fenced_output(text)
    assert "../../etc/passwd" not in out
    assert out == {"ok.md": "good"}


def test_parse_fence_no_blocks_returns_empty() -> None:
    text = "Just prose. No fences anywhere."
    assert openai_api._parse_fenced_output(text) == {}


def test_parse_fence_handles_blank_body() -> None:
    text = "==== FILE: empty.txt ====\n\n==== END ====\n"
    out = openai_api._parse_fenced_output(text)
    assert out == {"empty.txt": ""}


def test_parse_fence_strips_surrounding_markdown_fence() -> None:
    """Observed Qwen3 output: each FILE block wrapped in ``` markdown
    fence. Trailing ``` ends up in body and breaks Lean compilation.
    Provider strips them before writing."""
    text = (
        "==== FILE: patch.lean ====\n"
        "```lean\n"
        "theorem foo : True := trivial\n"
        "```\n"
        "==== END ====\n"
    )
    out = openai_api._parse_fenced_output(text)
    assert out == {"patch.lean": "theorem foo : True := trivial"}


def test_parse_fence_strip_no_fence_passes_through() -> None:
    """A body without surrounding markdown fence is not modified."""
    text = (
        "==== FILE: patch.lean ====\n"
        "theorem foo : True := trivial\n"
        "==== END ====\n"
    )
    out = openai_api._parse_fenced_output(text)
    assert out == {"patch.lean": "theorem foo : True := trivial"}


def test_strip_markdown_fence_only_outer_layer() -> None:
    """Internal ``` (e.g. inside docstrings) must not be stripped — only
    the outermost lines if they are the language-tagged fence."""
    body = (
        "```python\n"
        "def f():\n"
        "    \"\"\"docstring with ``` inside.\"\"\"\n"
        "    return 1\n"
        "```"
    )
    out = openai_api._strip_markdown_fence(body)
    assert "docstring with ```" in out
    assert not out.startswith("```")
    assert not out.rstrip().endswith("```")


# ---------------------------------------------------------------------
# _select_prompt_template
# ---------------------------------------------------------------------

def test_select_prompt_template_prefers_singleshot(tmp_path: Path) -> None:
    base = tmp_path / "backward.md"
    single = tmp_path / "backward_singleshot.md"
    base.write_text("multi-turn")
    single.write_text("single-shot")
    chosen = openai_api._select_prompt_template(base)
    assert chosen == single


def test_select_prompt_template_falls_back_to_base(tmp_path: Path) -> None:
    base = tmp_path / "backward.md"
    base.write_text("multi-turn")
    chosen = openai_api._select_prompt_template(base)
    assert chosen == base


# ---------------------------------------------------------------------
# _build_messages
# ---------------------------------------------------------------------

def test_build_messages_inlines_context() -> None:
    msgs = openai_api._build_messages(
        prompt_template="Decompose the goal.",
        context_text="Goal: T\nHints: x",
    )
    assert msgs[0]["role"] == "system"
    assert msgs[0]["content"] == "Decompose the goal."
    assert msgs[1]["role"] == "user"
    assert "Goal: T" in msgs[1]["content"]
    assert "Hints: x" in msgs[1]["content"]
    assert "==== CONTEXT ====" in msgs[1]["content"]


# ---------------------------------------------------------------------
# OpenAIProvider.spawn (HTTP mocked)
# ---------------------------------------------------------------------

def _request(tmp_path: Path) -> llm.LLMRequest:
    """Build a real LLMRequest pointing at a tmp dir with required
    Context.md + prompt template."""
    attempts = tmp_path / "attempts"
    attempts.mkdir()
    (attempts / "Context.md").write_text("Goal statement: T\n", encoding="utf-8")
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "backward.md").write_text("Multi-turn template", encoding="utf-8")
    (prompts / "backward_singleshot.md").write_text(
        "Single-shot template", encoding="utf-8")
    return llm.LLMRequest(
        kind="backward",
        prompt_path=prompts / "backward.md",
        problem_dir=tmp_path / "Problems" / "p",
        attempts_dir=attempts,
        timeout_sec=30,
    )


def test_spawn_writes_files_on_200(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ASTERISM_LLM_MODEL", "tester")
    req = _request(tmp_path)

    api_response = {
        "choices": [{"message": {"content":
            "==== FILE: PROPOSAL.md ====\nplan\n==== END ====\n"
            "==== FILE: patch_main.lean ====\nlean code\n==== END ====\n"
        }}]
    }

    def fake_post(url, payload, *, headers, timeout_sec):
        return api_response

    monkeypatch.setattr(openai_api, "_http_post_json", fake_post)
    rc = openai_api.OpenAIProvider().spawn(req)
    assert rc == 0
    assert (req.attempts_dir / "PROPOSAL.md").read_text() == "plan"
    assert (req.attempts_dir / "patch_main.lean").read_text() == "lean code"
    # Raw response captured for forensics
    assert (req.attempts_dir / "_raw_response.txt").exists()


def test_spawn_returns_127_when_model_env_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ASTERISM_LLM_MODEL", raising=False)
    req = _request(tmp_path)
    assert openai_api.OpenAIProvider().spawn(req) == 127


def test_spawn_returns_98_when_no_fences(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ASTERISM_LLM_MODEL", "tester")
    req = _request(tmp_path)

    def fake_post(url, payload, *, headers, timeout_sec):
        return {"choices": [{"message": {"content": "Just prose. No fences."}}]}

    monkeypatch.setattr(openai_api, "_http_post_json", fake_post)
    rc = openai_api.OpenAIProvider().spawn(req)
    assert rc == 98
    # Raw response saved even on parse failure (forensics)
    assert (req.attempts_dir / "_raw_response.txt").exists()


def test_spawn_returns_99_on_http_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ASTERISM_LLM_MODEL", "tester")
    req = _request(tmp_path)

    def fake_post(url, payload, *, headers, timeout_sec):
        raise urllib.error.URLError("Connection refused")

    monkeypatch.setattr(openai_api, "_http_post_json", fake_post)
    assert openai_api.OpenAIProvider().spawn(req) == 99


def test_spawn_returns_124_on_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ASTERISM_LLM_MODEL", "tester")
    req = _request(tmp_path)

    def fake_post(url, payload, *, headers, timeout_sec):
        raise socket.timeout("timed out")

    monkeypatch.setattr(openai_api, "_http_post_json", fake_post)
    assert openai_api.OpenAIProvider().spawn(req) == 124


def test_spawn_returns_99_on_malformed_response(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ASTERISM_LLM_MODEL", "tester")
    req = _request(tmp_path)

    def fake_post(url, payload, *, headers, timeout_sec):
        return {"unexpected": "shape"}

    monkeypatch.setattr(openai_api, "_http_post_json", fake_post)
    assert openai_api.OpenAIProvider().spawn(req) == 99


def test_spawn_uses_singleshot_template_when_available(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Provider must transparently swap to the *_singleshot.md variant."""
    monkeypatch.setenv("ASTERISM_LLM_MODEL", "tester")
    req = _request(tmp_path)
    captured: dict = {}

    def fake_post(url, payload, *, headers, timeout_sec):
        captured["payload"] = payload
        return {"choices": [{"message": {"content":
            "==== FILE: PROPOSAL.md ====\nx\n==== END ====\n"
        }}]}

    monkeypatch.setattr(openai_api, "_http_post_json", fake_post)
    openai_api.OpenAIProvider().spawn(req)
    system_msg = captured["payload"]["messages"][0]["content"]
    assert system_msg == "Single-shot template"


def test_spawn_authorization_header_when_api_key_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ASTERISM_LLM_MODEL", "tester")
    monkeypatch.setenv("ASTERISM_LLM_API_KEY", "sk-fake")
    req = _request(tmp_path)
    captured: dict = {}

    def fake_post(url, payload, *, headers, timeout_sec):
        captured["headers"] = headers
        return {"choices": [{"message": {"content":
            "==== FILE: x.md ====\ny\n==== END ====\n"
        }}]}

    monkeypatch.setattr(openai_api, "_http_post_json", fake_post)
    openai_api.OpenAIProvider().spawn(req)
    assert captured["headers"].get("Authorization") == "Bearer sk-fake"


def test_provider_registry_loads_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    """Now that openai_api is implemented, registry should return it."""
    monkeypatch.setenv("ASTERISM_LLM_PROVIDER", "openai")
    p = llm.get_provider()
    assert p.__class__.__name__ == "OpenAIProvider"
