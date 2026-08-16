"""A spawned process must never inherit our stdin.

THE INCIDENT (2026-08-16). `paper_index` — the one-shot agent that
writes a fetched paper's `map.md` — is launched from inside
`paper_fetch`, which since 2026-08-10 (`5a81d348`, "the Scholar's two
commands come in from the shell") runs inside the MCP tools server. That
server's stdin IS the JSON-RPC pipe from its parent CLI. `claude_cli`'s
`Popen` passed no `stdin=`, so the nested CLI inherited that pipe,
blocked on it for its full 1200-second budget, and was killed: zero
messages, zero tokens, no session ever created. Three fetches since that
date, three identical hangs, no `map.md` — while the six fetches before
it, which ran under the Bash tool, all succeeded. The same code run
outside that nesting finishes in 64 seconds.

Two costs, not one: the spawn hangs, and a second reader on a JSON-RPC
pipe can consume bytes meant for the server it is running inside.

Checked by AST, not by grepping for a string: the point is that the
keyword is PRESENT on every launcher, which is a fact about the call,
and a launcher added tomorrow must not be able to omit it quietly.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: Modules that start a process the framework then talks to (or waits
#: on). A new one belongs here the day it is written.
LAUNCHER_MODULES = (
    "Tooling/llm/claude_cli.py",
    "Tooling/llm/codex_cli.py",
    "Tooling/llm/antigravity_cli.py",
    "Tooling/llm/gemini_cli.py",
    "Tooling/llm/drift_guard.py",
    "Tooling/agent/runtime.py",
)


def _subprocess_calls(tree: ast.AST):
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if (isinstance(fn, ast.Attribute)
                and fn.attr in ("Popen", "run", "call", "check_output")
                and isinstance(fn.value, ast.Name)
                and fn.value.id == "subprocess"):
            yield node


def test_every_launcher_declares_its_stdin() -> None:
    missing = []
    for rel in LAUNCHER_MODULES:
        path = ROOT / rel
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for call in _subprocess_calls(tree):
            if not any(kw.arg == "stdin" for kw in call.keywords):
                missing.append(f"{rel}:{call.lineno}")
    assert not missing, (
        "these start a process without saying what its stdin is, so it "
        "inherits ours — which for anything launched inside the MCP "
        "tools server is that server's JSON-RPC pipe:\n  "
        + "\n  ".join(missing))


#: Modules that execute INSIDE the MCP tools server — where the
#: inherited stdin is a live JSON-RPC pipe, so a process started with
#: it both hangs and can eat the protocol. This is the blast radius of
#: the 2026-08-16 incident, not a repo-wide style rule: elsewhere a
#: process inherits an operator terminal, which is harmless and
#: sometimes wanted.
MCP_REACHABLE = (
    "Tooling/knowledge/mcp_tools.py",
    "Tooling/knowledge/workspace_query.py",
    "Tooling/knowledge/lemma_lookup.py",
    "Tooling/knowledge/loogle.py",
    "Tooling/sandbox/provision.py",
    "Tooling/papers/fetch.py",
    "Tooling/papers/index.py",
    "Tooling/papers/search.py",
)


def test_nothing_started_inside_the_tools_server_inherits_its_pipe() -> None:
    """`paper_index` is the instance; `compute`'s sandbox probe and
    `loogle`'s lean query are the same shape one call away."""
    missing = []
    for rel in MCP_REACHABLE:
        path = ROOT / rel
        if not path.is_file():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for call in _subprocess_calls(tree):
            if not any(kw.arg == "stdin" for kw in call.keywords):
                missing.append(f"{rel}:{call.lineno}")
    assert not missing, (
        "started from inside the MCP tools server with an inherited "
        "stdin — that handle is the server's JSON-RPC pipe:\n  "
        + "\n  ".join(missing))


def test_every_provider_tells_the_prompt_where_its_outputs_go() -> None:
    """`{attempts_dir}` is substituted from the value the spawn already
    carries. A backend that renders the template without passing it
    shows the agent the fallback wording instead of the path — the
    silent-per-backend class `test_envelope_rendered_by_every_backend`
    exists for, one layer up."""
    import re
    missing = []
    for rel in ("Tooling/llm/claude_cli.py", "Tooling/llm/gemini_cli.py",
                "Tooling/llm/antigravity_cli.py",
                "Tooling/llm/openai_api.py"):
        src = (ROOT / rel).read_text(encoding="utf-8")
        for call in re.finditer(r"render_prompt_template\((.{0,300}?)\)",
                                src, re.S):
            if "attempts_dir=" not in call.group(1):
                missing.append(rel)
    assert not missing, (
        "these render the prompt without telling it where outputs go: "
        + ", ".join(sorted(set(missing))))
