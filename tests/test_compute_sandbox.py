"""The compute sandbox: what it lets through, and what it must not.

The escape tests spawn the real sandbox interpreter — that is the point.
A containment claim verified against a stub is a claim about the stub.
They skip where the sandbox venv has not been provisioned (CI has no
Lean toolchain and no reason to build one either).
"""
from __future__ import annotations

import pytest

from Tooling import sandbox
from Tooling.knowledge import mcp_tools
from Tooling.sandbox import provision

_ready, _why = provision.verify()
live = pytest.mark.skipif(not _ready,
                          reason=f"sandbox venv not provisioned: {_why}")


# ----------------------------------------------------- the declaration

def test_polarity_travels_with_the_output() -> None:
    """The "not a proof" statement is prepended to the RESULT, not left
    in the tool description. The dangerous reader is a DOWNSTREAM agent
    seeing "checked 10^6 points, held" quoted in a dialogue — it never
    sees the tool docs, only the artifact (owner ruling 2026-08-10)."""
    rendered = sandbox.ComputeResult(rc=0, output="held", seconds=0.1).render()
    assert rendered.startswith(sandbox.RESULT_HEADER)
    low = sandbox.RESULT_HEADER.lower()
    assert "not a proof" in low and "lean kernel" in low
    # Both directions, not just "a clean sweep proves nothing".
    assert "either direction" in low


def test_timeout_is_not_in_the_tool_signature() -> None:
    """Framework-set and invisible to the agent. If it ever becomes a
    parameter, an agent under time pressure will raise it."""
    import inspect as _inspect
    params = _inspect.signature(mcp_tools.compute).parameters
    assert list(params) == ["code"]


def test_truncation_says_how_much_was_dropped() -> None:
    big = "x" * (sandbox.MAX_OUTPUT_CHARS + 500)
    rendered = sandbox.ComputeResult(rc=0, output=big, seconds=0.1).render()
    assert "500 more characters dropped" in rendered


def test_limit_kills_name_the_fixed_limit() -> None:
    """A gate message has to carry the way out (07-31 lesson). "Shrink
    the search" is actionable; "killed" is not."""
    t = sandbox.ComputeResult(0, "", 30.0, killed="timeout").render()
    assert str(sandbox.TIMEOUT_SEC) in t and "Shrink" in t
    m = sandbox.ComputeResult(0, "", 0.3, killed="memory").render()
    assert str(sandbox.MEMORY_MB) in m and "batches" in m


def test_env_is_an_allowlist_with_no_path_and_no_secrets(monkeypatch) -> None:
    """Allowlist, never a strip: a denylist rots the moment the host
    grows a variable, and with PATH intact a shell has something to
    find."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-secret")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "abc")
    env = sandbox._sandbox_env()
    assert "PATH" not in env and "Path" not in env
    assert not any(k.startswith(("ANTHROPIC", "CLAUDE", "OPENAI", "GEMINI"))
                   for k in env)
    # BLAS threads pinned: OpenBLAS reserves per-core buffers at import
    # and blew the whole memory cap before any agent code ran.
    assert env["OPENBLAS_NUM_THREADS"] == "1"


# --------------------------------------------------- the real sandbox

@live
def test_a_calculation_works() -> None:
    r = sandbox.run("print(sum(1/k**2 for k in range(1, 10**6)))")
    assert r.rc == 0
    assert r.output.startswith("1.6449")


@live
def test_numpy_is_available() -> None:
    """numpy survives the import policy — which it only does because the
    launcher imports it BEFORE tightening: numpy loads ctypes at module
    level, so an import blocklist applied first refuses numpy itself."""
    r = sandbox.run("import numpy as np; print(np.linspace(0,1,5).sum())")
    assert r.rc == 0 and "2.5" in r.output


@live
@pytest.mark.parametrize("label,code,expect", [
    ("framework package", "import Tooling", "No module named 'Tooling'"),
    ("network", "import socket", "not available"),
    ("shell", "import subprocess", "not available"),
    ("os.system", "import os; os.system('echo x')", "not available"),
    ("read the workspace",
     "open(r'D:/Asterism/docs/internal/STATUS.md')", "cannot read"),
    ("write a file", "open('x.txt','w')", "cannot write"),
    ("native code via ctypes",
     "import ctypes; ctypes.CDLL('kernel32')", "not available"),
])
def test_the_escapes_are_refused(label, code, expect) -> None:
    r = sandbox.run(code)
    assert r.rc != 0, f"{label}: allowed"
    assert expect in r.output, f"{label}: got {r.output[:200]}"


@live
def test_runaway_time_is_stopped_by_the_wall_clock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A busy loop accrues CPU; `sleep` does not. The wall clock has to
    catch both, which is why it is enforced out here and not by the Job
    Object's own limit (that one counts user-mode CPU).

    The limit is shrunk to 2s: the kill loop reads the module constant
    each tick, so the enforcement path under test is byte-identical to
    the production one — waiting out the real 30s bought nothing but a
    test that was 16% of the whole suite's wall time."""
    monkeypatch.setattr(sandbox, "TIMEOUT_SEC", 2)
    r = sandbox.run("while True: pass")
    assert r.killed == "timeout"
    assert r.seconds < sandbox.TIMEOUT_SEC + 10


@live
def test_runaway_memory_is_stopped() -> None:
    r = sandbox.run("x=[]\nwhile True: x.append(bytearray(10**7))")
    assert r.rc != 0 or r.killed == "memory"
    assert "MemoryError" in r.output or r.killed == "memory"


@live
def test_the_hook_selftest_guards_its_own_installation() -> None:
    """The launcher proves the hook is live before running agent code.
    A guard that quietly stopped guarding is the failure mode this whole
    design exists to avoid, so it refuses to run rather than trust its
    own installation."""
    from Tooling.sandbox import launcher
    src = (launcher.__file__ or "")
    assert src
    assert "selftest()" in open(src, encoding="utf-8").read()


# ------------------------------------------------------- provisioning

def test_isolation_is_verified_not_assumed() -> None:
    """`verify` must check the thing that IS the isolation — that
    `import Tooling` fails — rather than a proxy like PYTHONPATH being
    unset. Stripping PYTHONPATH does not work (an editable install
    reaches the interpreter through site-packages) and neither does
    `-I`; both measured 2026-08-10."""
    src = open(provision.__file__, encoding="utf-8").read()
    assert "import Tooling" in src and "import numpy" in src
    assert "ISOLATION BROKEN" in src


def test_a_broken_sandbox_is_reported_not_silently_rebuilt() -> None:
    """Rebuilding on a failed verify would erase the evidence of what
    changed underneath it."""
    src = open(provision.__file__, encoding="utf-8").read()
    assert "not silently rebuilt" in src or "would erase the evidence" in src


# ─── the probe stops being a load source, and starts leaving evidence ───
#
# `ensure_ready` ran three subprocesses on EVERY compute call, each able
# to wait 60s. On 2026-08-11 twelve consecutive in-spawn calls came back
# "sandbox interpreter will not start" while the same interpreter
# started in 95ms from a shell — and none of them was diagnosable
# afterwards, because the message is cut at 200 chars and the attempts
# dir it was written from gets deleted. One strategist, left with no
# calculator, did a 256-family sweep in its own output and hit the 64k
# token ceiling: 258k tokens, 50 minutes, nothing kept.

def test_a_verified_sandbox_is_not_re_verified_every_call(monkeypatch):
    """The MCP server is per-spawn, so caching a success re-proves the
    isolation once per agent — the scope "every startup" always meant."""
    monkeypatch.setattr(provision, "_verified", False)
    calls = []
    monkeypatch.setattr(provision, "verify",
                        lambda: (calls.append(1), (True, ""))[1])
    monkeypatch.setattr(provision, "sandbox_python",
                        lambda: __import__("pathlib").Path(__file__))
    assert provision.ensure_ready() == (True, "")
    assert provision.ensure_ready() == (True, "")
    assert provision.ensure_ready() == (True, "")
    assert len(calls) == 1


def test_a_failure_is_never_cached(monkeypatch):
    """A sandbox that just failed gets asked again. Caching the failure
    would turn one unlucky probe into a whole turn without a calculator
    — which is the shape that cost 258k tokens."""
    monkeypatch.setattr(provision, "_verified", False)
    calls = []
    monkeypatch.setattr(provision, "verify",
                        lambda: (calls.append(1), (False, "nope"))[1])
    monkeypatch.setattr(provision, "sandbox_python",
                        lambda: __import__("pathlib").Path(__file__))
    for _ in range(3):
        assert provision.ensure_ready() == (False, "nope")
    assert len(calls) == 3


def test_a_failed_probe_writes_forensics_that_outlive_the_run(tmp_path,
                                                              monkeypatch):
    """The failure has to carry its own evidence: elapsed time (a 60s
    cap tells you nothing about what took 60s), the resolved cwd, and
    the environment it ran under."""
    monkeypatch.setattr(provision, "_workspace", lambda: tmp_path)
    provision._forensics(["py", "-c", "print(1)"], str(tmp_path), 61.3,
                         TimeoutError("timed out after 60 seconds"))
    log = tmp_path / ".asterism" / "logs" / "compute_probe.log"
    assert log.is_file()
    text = log.read_text(encoding="utf-8")
    assert "elapsed=61.3s" in text
    assert "TimeoutError" in text
    assert "env_keys=" in text          # the thing we could not read back
    assert "cwd=" in text


def test_forensics_never_breaks_the_probe(monkeypatch):
    """It runs only when something already went wrong; it must not be
    able to make that worse."""
    def boom():
        raise RuntimeError("no workspace")
    monkeypatch.setattr(provision, "_workspace", boom)
    provision._forensics(["py"], "nowhere", 1.0, TimeoutError("x"))


# ─── the sandbox runs in the gateway, because the tool server can't ───
#
# `compute` shipped 2026-08-10 on the stdio MCP server that claude
# spawns as its own child, and never worked once in production: twelve
# consecutive calls timed out at 60s on a bare `print('alive')`. The
# control spawn settled it — the very interpreter hosting that server,
# same flags, same cwd, hung identically, while a shell runs the same
# command in 95ms. No subprocess started from that server ever runs, so
# the venv was never the problem and no amount of fixing it would have
# helped.

def test_the_tool_does_not_spawn_the_sandbox_itself() -> None:
    """The regression that matters: a future edit that "simplifies" the
    tool back to calling `sandbox.run` locally restores a path that has
    never once worked."""
    import inspect as _inspect
    src = _inspect.getsource(mcp_tools.compute)
    assert "_compute_via_gateway" in src
    assert "sandbox" not in src, (
        "compute must not reach the sandbox from this process — no "
        "subprocess started here runs (2026-08-11)")


def test_a_gateway_that_does_not_answer_says_whose_fault_it_is(monkeypatch):
    """The old message named the venv and guessed "base Python upgraded
    under it?" — a hard-coded explanation for a generic failure, and it
    sent every reader after the wrong thing for two days. The agent must
    be told this is the framework's fault and that working around it is
    not the move."""
    import urllib.request

    def boom(*a, **kw):
        raise OSError("connection refused")
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    out = mcp_tools._compute_via_gateway("print(1)")
    assert "framework fault" in out
    assert "retry once" in out
    assert "working around it" in out
    assert "base Python upgraded" not in out


def test_the_gateway_endpoint_runs_the_same_sandbox() -> None:
    """Moving WHERE `sandbox.run` is called must not change what it
    does — same isolation, same caps, same contract."""
    import pathlib
    src = (pathlib.Path(__file__).resolve().parents[1] / "Tooling" / "lsp"
           / "gateway.py").read_text(encoding="utf-8")
    i = src.index('@mcp.custom_route("/compute"')
    body = src[i:i + 2500]
    assert "from ..sandbox import run as _sandbox_run" in body
    assert "asyncio.to_thread" in body      # never block the event loop
