"""OpenAI-compatible HTTP API provider.

Targets vLLM / Ollama / LM Studio / any server speaking the OpenAI
`/v1/chat/completions` protocol. Single-shot completion: no tool use,
no multi-turn — the prompt template + Context.md are inlined into the
user message; the model's response is parsed for `==== FILE: ... ====`
fenced blocks which the provider writes back into `attempts_dir`.

This shape lets `pipeline.run_backward` consume agent
output identically regardless of provider — they still glob
`PROPOSAL.md`, `patch*.lean`, `new_*.lean` from the attempts dir.

Env config:
  ASTERISM_LLM_BASE_URL    default http://localhost:8000/v1
  ASTERISM_LLM_MODEL       required (no sensible default per backend)
  ASTERISM_LLM_API_KEY     optional (most local servers don't need one)
  ASTERISM_LLM_MAX_TOKENS  default 8000
  ASTERISM_LLM_TEMPERATURE default 0.3

Return codes:
  0     success (output files written)
  98    fence parsing failed (no FILE blocks recovered)
  99    HTTP non-200 / malformed JSON response
  124   request timed out
  127   ASTERISM_LLM_MODEL not set
"""
from __future__ import annotations

import json
import os
import re
import socket
import urllib.error
import urllib.request
from pathlib import Path

from .base import LLMRequest


_FENCE_RE = re.compile(
    r"==== FILE:\s*(?P<name>[^\s=]+)\s*====\s*\n"
    r"(?P<body>.*?)\n?"
    r"==== END ====",
    re.DOTALL,
)


def _resolve_model(kind: str | None) -> str | None:
    """Model resolution chain for the openai provider (per
    Tooling/config.get):

    1. `ASTERISM_<KIND>_MODEL` env  (kind in {'builder','backward'})
    2. Asterism.yaml `<kind>.model`
    3. `ASTERISM_LLM_MODEL` env  (legacy openai-wide)
    4. None — caller surfaces rc=127 / returns None
    """
    from ..core import config
    if kind:
        v = config.get(
            f"{kind}.model",
            env_var=f"ASTERISM_{kind.upper()}_MODEL",
            legacy_env=("ASTERISM_LLM_MODEL",),
            default=None,
        )
        if v is not None:
            return str(v)
        return None
    return os.environ.get("ASTERISM_LLM_MODEL")


def _select_prompt_template(prompt_path: Path) -> Path:
    """If the caller passed `prompts/<kind>.md`, prefer the
    `<kind>_singleshot.md` variant when present. Falls back to the
    original if no single-shot file exists (no such variants ship
    today — the pre-v33 backward/builder ones are deleted).

    This lets `pipeline.py` keep using the canonical prompt names while
    the provider transparently picks the right variant for its
    interaction model.
    """
    parent = prompt_path.parent
    stem = prompt_path.stem
    suffix = prompt_path.suffix
    candidate = parent / f"{stem}_singleshot{suffix}"
    return candidate if candidate.exists() else prompt_path


def _build_messages(*, prompt_template: str, context_text: str) -> list[dict]:
    """One system message (the prompt template), one user message (the
    Context block). The model sees the full task in one turn."""
    return [
        {"role": "system", "content": prompt_template},
        {"role": "user", "content":
            f"==== CONTEXT ====\n{context_text}\n==== END ====\n"},
    ]


def _strip_markdown_fence(body: str) -> str:
    """Strip surrounding ``` markdown fences from a body block.

    Some models (observed: Qwen3-Instruct) habitually wrap each
    `==== FILE ====` block in a markdown ``` ... ``` fence. The
    closing ``` ends up captured as a trailing token of the body
    (Lean rejects it as syntax error). Strip them before writing.

    Conservative: only removes a leading ``` (with optional language
    tag) on its own line, and a trailing ``` on its own line.
    """
    lines = body.split("\n")
    if lines and lines[0].lstrip().startswith("```"):
        lines = lines[1:]
    while lines and lines[-1].strip() == "":
        lines.pop()
    if lines and lines[-1].strip() == "```":
        lines.pop()
    return "\n".join(lines)


def _parse_fenced_output(text: str) -> dict[str, str]:
    """Extract `{filename: content}` from `==== FILE: x ==== ... ==== END ====`
    blocks. Returns empty dict if no blocks found.

    Allows arbitrary text before/between/after blocks (models often
    chat). Filenames are taken verbatim — caller is responsible for
    sandboxing (writing only into a known dir). Surrounding markdown
    ``` fences are stripped from each body before writing.
    """
    out: dict[str, str] = {}
    for m in _FENCE_RE.finditer(text):
        name = m.group("name").strip()
        if not name or "/" in name or "\\" in name or name.startswith(".."):
            continue  # reject path-traversal attempts silently
        out[name] = _strip_markdown_fence(m.group("body"))
    return out


def _http_post_json(url: str, payload: dict, *, headers: dict,
                    timeout_sec: int) -> dict:
    """POST JSON, return parsed JSON. Raises on non-200 / malformed."""
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
        if resp.status != 200:
            raise RuntimeError(f"HTTP {resp.status}")
        raw = resp.read().decode("utf-8")
    return json.loads(raw)


class OpenAIProvider:
    def spawn(self, req: LLMRequest) -> int:
        model = _resolve_model(req.kind)
        if not model:
            print("[llm:openai] no model env set "
                  "(ASTERISM_<KIND>_MODEL or ASTERISM_LLM_MODEL)",
                  flush=True)
            return 127

        base_url = os.environ.get(
            "ASTERISM_LLM_BASE_URL", "http://localhost:8000/v1"
        ).rstrip("/")
        api_key = os.environ.get("ASTERISM_LLM_API_KEY", "")
        try:
            max_tokens = int(os.environ.get("ASTERISM_LLM_MAX_TOKENS", "8000"))
        except ValueError:
            max_tokens = 8000
        try:
            temperature = float(
                os.environ.get("ASTERISM_LLM_TEMPERATURE", "0.3"))
        except ValueError:
            temperature = 0.3

        prompt_path = _select_prompt_template(req.prompt_path)
        try:
            prompt_template = prompt_path.read_text(encoding="utf-8")
        except OSError as e:
            print(f"[llm:openai] prompt read failed: {e}", flush=True)
            return 99
        from Tooling.agent import render_prompt_template
        prompt_template = render_prompt_template(
            prompt_template, is_postmortem=req.is_postmortem,
            attempts_dir=req.attempts_dir)

        context_path = req.attempts_dir / "Context.md"
        try:
            context_text = context_path.read_text(encoding="utf-8")
        except OSError as e:
            print(f"[llm:openai] Context.md read failed: {e}", flush=True)
            return 99

        messages = _build_messages(
            prompt_template=prompt_template,
            context_text=context_text,
        )

        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        try:
            data = _http_post_json(
                f"{base_url}/chat/completions", payload,
                headers=headers, timeout_sec=req.timeout_sec,
            )
        except (urllib.error.URLError, socket.timeout) as e:
            if isinstance(e, socket.timeout) or "timed out" in str(e).lower():
                print(f"[llm:openai] timeout after {req.timeout_sec}s",
                      flush=True)
                return 124
            print(f"[llm:openai] HTTP error: {e}", flush=True)
            return 99
        except (RuntimeError, ValueError, json.JSONDecodeError) as e:
            print(f"[llm:openai] response error: {e}", flush=True)
            return 99

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            print(f"[llm:openai] response shape error: {e}", flush=True)
            return 99

        # Persist the raw response for forensics (dead_attempts artifacts
        # only catch what's in attempts_dir).
        try:
            (req.attempts_dir / "_raw_response.txt").write_text(
                content, encoding="utf-8")
        except OSError:
            pass

        files = _parse_fenced_output(content)
        if not files:
            print("[llm:openai] no FILE fences parsed from response",
                  flush=True)
            return 98

        for fname, body in files.items():
            target = req.attempts_dir / fname
            try:
                target.write_text(body, encoding="utf-8")
            except OSError as e:
                print(f"[llm:openai] write {fname} failed: {e}", flush=True)
                # Continue with remaining files — partial output may still
                # be enough for pipeline to glob.

        return 0

