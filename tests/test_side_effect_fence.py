"""Side-effect fence (conftest `_side_effect_fence`, task #6) + the
conftest verify_file stub's shape drift gate.

The fence is the mechanism form of "unit tests never spawn the toolchain":
the pre-search escape (1488da4 — a real claude subprocess idling 270s per
test, suite green throughout) proved the fixture-discipline form fails
silently. These tests are the adversarial proof the fence actually fires,
plus a reproduction of that incident's shape.
"""
from __future__ import annotations

import ast
import socket
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------
# The fence fires
# ---------------------------------------------------------------------

def test_fence_blocks_claude_spawn():
    with pytest.raises(pytest.fail.Exception, match="side-effect fence"):
        subprocess.Popen(["claude", "-p", "hi"])


def test_fence_blocks_lake_spawn_via_run():
    # subprocess.run routes through Popen → the fence covers it too.
    with pytest.raises(pytest.fail.Exception, match="side-effect fence"):
        subprocess.run(["lake", "env", "lean", "x.lean"])


def test_fence_blocks_full_path_and_case():
    with pytest.raises(pytest.fail.Exception, match="side-effect fence"):
        subprocess.Popen([r"C:\somewhere\bin\Claude.EXE", "-p", "x"])


def test_fence_blocks_external_network():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(pytest.fail.Exception, match="side-effect fence"):
            s.connect(("8.8.8.8", 53))
    finally:
        s.close()


def test_fence_allows_benign_subprocess():
    # git/python etc. stay allowed — the fence targets the toolchain.
    p = subprocess.run(["git", "--version"], capture_output=True)
    assert p.returncode == 0


def test_fence_reproduces_the_presearch_escape_shape(tmp_path, monkeypatch):
    """The 1488da4 incident shape: presearch's spawn path reaching a real
    `claude` subprocess. With the fence, an unstubbed spawn is an instant
    named failure instead of a silent 270s idle. We simulate the escape by
    restoring the REAL spawn implementation (bypassing the conftest spawn
    stubs the way the inconsistent import did) — the fence is the layer
    that must still catch it."""
    from Tooling import agent as _agent

    def _escaped_spawn(**kw):
        # what runtime.spawn_llm ultimately does: Popen(["claude", ...])
        return subprocess.Popen(["claude", "-p", "escaped"])

    monkeypatch.setattr(_agent, "spawn_llm", _escaped_spawn)
    with pytest.raises(pytest.fail.Exception, match="side-effect fence"):
        _agent.spawn_llm(kind="presearch")


# ---------------------------------------------------------------------
# conftest verify_file stub — shape drift gate. The stub mirrors the
# gateway's `_verify_sync` response dict; a new response field the real
# gateway grows would otherwise lag in the stub silently until some test
# breaks obliquely (audit note from the fence review).
# ---------------------------------------------------------------------

def _dict_keys_of_return(fn_node: ast.FunctionDef,
                         last_only: bool = False) -> "set[str]":
    """String keys of dict-literal returns. `last_only` takes the LAST
    such return in source order — for `_verify_sync` that is the terminal
    success shape (earlier returns are error dicts: `error`/`transient`/
    `_status`, which the stub deliberately doesn't model)."""
    rets = sorted(
        (node for node in ast.walk(fn_node)
         if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict)),
        key=lambda n: n.lineno)          # ast.walk is BFS, not source order
    dicts = [r.value for r in rets]
    if last_only:
        dicts = dicts[-1:]
    keys: "set[str]" = set()
    for d in dicts:
        for k in d.keys:
            if isinstance(k, ast.Constant) and isinstance(k.value, str):
                keys.add(k.value)
    return keys


def _function_node(path: Path, name: str) -> ast.FunctionDef:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and node.name == name:
            return node
    raise AssertionError(f"{name} not found in {path}")


def test_conftest_verify_stub_covers_gateway_response_shape():
    gateway_keys = _dict_keys_of_return(
        _function_node(ROOT / "Tooling" / "lsp" / "gateway.py",
                       "_verify_sync"), last_only=True)
    stub_keys = _dict_keys_of_return(
        _function_node(ROOT / "tests" / "conftest.py", "_stub_verify_file"))
    # The success-shape keys the gateway returns must all exist in the
    # stub (error-only keys like `transient` appear in failure dicts the
    # stub deliberately doesn't model — the gateway's terminal return is
    # the success shape).
    missing = sorted(gateway_keys - stub_keys)
    assert not missing, (
        f"conftest._stub_verify_file lags the gateway response shape: "
        f"missing keys {missing} — add them to the stub")
