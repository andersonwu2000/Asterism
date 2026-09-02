"""`Popen.kill()` does not kill an npm-installed CLI.

On Windows it is `TerminateProcess` on the DIRECT CHILD, and for a CLI
installed by npm that child is `cmd.exe` — the shim — with the agent two
levels below (`cmd.exe → node.exe → <vendor>.exe`). Killing the shim
leaves the agent running.

Measured 2026-08-15 on the union_closed run: a codex spawn killed at
02:32:35 kept reasoning and calling tools until 02:37:33, and at
02:34:35 called the gateway's `withdraw_stub` — deleting a stub file
that the framework was, at that moment, reading as the dead spawn's
salvage. The FileNotFoundError then came back to the agent as
"your Lean failed to build".

So this is not a tidiness bug: a spawn the framework has recorded as
dead goes on mutating the workspace, and the framework attributes what
it finds to whoever comes next. Job Objects reap the whole tree —
membership survives re-parenting, which is why `taskkill /T` was never
enough either (`core/process_group.py`).
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from Tooling.core import process_group, spawn_registry
from Tooling.llm import claude_cli

ROOT = Path(__file__).resolve().parents[1]
PROVIDERS = [ROOT / "Tooling" / "llm" / "claude_cli.py",
             ROOT / "Tooling" / "llm" / "codex_cli.py"]


#: The only functions that may call `proc.kill()` on a spawn: the
#: fallbacks INSIDE the tree-kill machinery itself.
_MAY_KILL_BY_HANDLE = {"kill_proc_tree", "_kill_proc_group_posix"}


def _enclosing_function(tree: ast.AST, lineno: int):
    """The INNERMOST function containing `lineno` — the one whose name
    says whether this call site is legal."""
    best = None
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.lineno <= lineno <= (node.end_lineno or node.lineno):
            if best is None or node.lineno > best.lineno:
                best = node
    return best


def test_no_provider_kills_a_spawn_by_the_handle_it_holds() -> None:
    """The enumeration IS the audit: a new provider that calls
    `proc.kill()` on a spawn has to either route through the tree kill
    or add its function to `_MAY_KILL_BY_HANDLE`.

    Asked of the enclosing FUNCTION, not of a line number (2026-09-02).
    The bound used to be `i < 200`, which says "near the top of
    claude_cli.py" — a fact about the file's layout, not about the rule,
    and inserting three lines above the legal site made a green test
    red without anything the rule cares about having changed."""
    for path in PROVIDERS:
        src = path.read_text(encoding="utf-8")
        tree = ast.parse(src)
        for i, line in enumerate(src.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#") or "proc.kill()" not in stripped:
                continue
            fn = _enclosing_function(tree, i)
            assert fn is not None and fn.name in _MAY_KILL_BY_HANDLE, (
                f"{path.name}:{i} (in "
                f"{fn.name if fn else '<module>'}) kills a spawn by its "
                f"own handle — on an npm-installed CLI that reaps the "
                f"`cmd.exe` shim and leaves the agent running. Use "
                f"`kill_proc_tree`")


@pytest.mark.parametrize("path", PROVIDERS, ids=lambda p: p.name)
def test_every_spawn_is_put_in_a_job(path) -> None:
    src = path.read_text(encoding="utf-8")
    assert "create_capped_job(None)" in src, (
        f"{path.name}: a spawn must be created inside a Job Object — "
        f"`None` asks for a reaper with no memory ceiling")
    assert "assign_to_job(job, proc)" in src


def test_a_job_with_no_memory_cap_is_still_kill_on_close() -> None:
    """`per_process_mb=None` must not silently become a 0-byte limit —
    that would make every allocation in the tree fail instantly. It is
    the flag that has to go, not the number."""
    src = (ROOT / "Tooling" / "core" / "process_group.py").read_text("utf-8")
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef)
              and n.name == "create_capped_job")
    body = ast.get_source_segment(src, fn) or ""
    assert "if per_process_mb is not None:" in body
    # KILL_ON_JOB_CLOSE is unconditional; the memory flag is not.
    assert "flags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE" in body


def test_the_registry_is_the_one_home_for_killing() -> None:
    """Every provider registers into the same set, so the tree kill
    lives with the set — not copied per provider."""
    assert hasattr(claude_cli, "track_proc")
    assert hasattr(claude_cli, "untrack_proc")
    assert hasattr(claude_cli, "kill_proc_tree")
    codex = (ROOT / "Tooling" / "llm" / "codex_cli.py").read_text("utf-8")
    assert "track_proc(proc, job)" in codex
    assert "untrack_proc(proc)" in codex


def test_shutdown_reaps_trees(monkeypatch: pytest.MonkeyPatch) -> None:
    """`request_shutdown` is the dispatcher's teardown path; it must go
    through the tree kill for every live spawn."""
    reaped: list = []

    class _Proc:
        def kill(self):
            reaped.append("handle-only")

    monkeypatch.setattr(claude_cli, "_live_procs", set())
    monkeypatch.setattr(claude_cli, "_proc_jobs", {})
    p = _Proc()
    claude_cli.track_proc(p, job=None)          # no job (non-Windows path)
    try:
        assert claude_cli.request_shutdown() == 1
    finally:
        claude_cli._reset_shutdown_for_tests()
    # With no job the fallback is the bare handle — correct off-Windows,
    # where the direct child IS the agent.
    assert reaped == ["handle-only"]


def test_terminate_job_is_what_a_tracked_job_uses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called: list = []
    monkeypatch.setattr(process_group, "terminate_job",
                        lambda job: called.append(job) or True)
    monkeypatch.setattr(claude_cli, "_live_procs", set())
    monkeypatch.setattr(claude_cli, "_proc_jobs", {})

    class _Proc:
        def kill(self):
            called.append("BARE KILL — the tree would have survived")

    p = _Proc()
    claude_cli.track_proc(p, job="job-handle")
    claude_cli.kill_proc_tree(p)
    assert called == ["job-handle"]


# ---------------------------------------------------------------------
# which pid runs which pipeline (HID §3.7 — a person's kill signal)
# ---------------------------------------------------------------------

def test_a_spawn_is_recorded_against_the_pipeline_that_owns_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A kill aimed at one worker needs a PID, and the two halves of that
    fact are held by different layers: the dispatcher's worker thread
    knows the pipeline id, the provider knows the Popen. The binding is
    per-THREAD because that is the only thing they share."""
    monkeypatch.setattr(claude_cli, "_live_procs", set())
    monkeypatch.setattr(claude_cli, "_proc_jobs", {})
    monkeypatch.setattr(spawn_registry, "_procs", {})

    class _Proc:
        def kill(self):
            pass

    p = _Proc()
    spawn_registry.bind("pipe-1")
    try:
        claude_cli.track_proc(p, job=None)
    finally:
        spawn_registry.unbind()
    assert spawn_registry.procs_for("pipe-1") == [p]
    assert spawn_registry.procs_for("pipe-2") == []
    claude_cli.untrack_proc(p)
    assert spawn_registry.procs_for("pipe-1") == []


def test_an_unbound_spawn_is_recorded_nowhere(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A spawn nobody bound (a probe, a rescue turn outside a pipeline)
    must not land under some other pipeline's id — an empty answer is
    the honest one, and the signal refuses on it."""
    monkeypatch.setattr(claude_cli, "_live_procs", set())
    monkeypatch.setattr(claude_cli, "_proc_jobs", {})
    monkeypatch.setattr(spawn_registry, "_procs", {})
    claude_cli.track_proc(object(), job=None)
    assert spawn_registry._procs == {}


def test_the_signal_sink_kills_the_tree_and_arms_the_outcome(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The sink is what `state/commands` is handed: it kills by the
    process tree recorded for THAT pipeline, then remembers the signal so
    the dispatcher's own completion path cascades it as that outcome."""
    killed: list = []
    monkeypatch.setattr(spawn_registry, "_procs", {})
    monkeypatch.setattr(spawn_registry, "kill_proc_tree",
                        lambda p: killed.append(p) or True)
    proc = object()
    spawn_registry._procs["pipe-1"] = [proc]
    sink = spawn_registry.SignalSink(lambda pid: pid == "pipe-1")

    assert sink.deliver("pipe-1", "shelve") == 1
    assert killed == [proc]
    assert sink.take("pipe-1") == "shelve"
    assert sink.take("pipe-1") is None, "a signal is spent when taken"


def test_the_sink_refuses_a_pipeline_this_daemon_does_not_hold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A `running` row can outlive the daemon that wrote it. Killing on
    the strength of that row alone would be a kill aimed at nothing —
    or, with a reused pid, at somebody else."""
    monkeypatch.setattr(spawn_registry, "_procs", {})
    sink = spawn_registry.SignalSink(lambda pid: False)
    with pytest.raises(KeyError):
        sink.deliver("pipe-1", "shelve")
    assert sink.take("pipe-1") is None


def test_the_sink_refuses_when_no_process_was_ever_registered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """In flight, but with nothing to kill by pid (a provider that spawns
    through `subprocess.run`, or a worker still assembling its context).
    Refusing is the loud answer: the alternative is a receipt that says
    the worker was stopped while it goes on writing into the workspace —
    the 2026-08-15 failure with a person's name on it. Killing by NAME is
    not an alternative (CLAUDE.md rule 8)."""
    monkeypatch.setattr(spawn_registry, "_procs", {})
    sink = spawn_registry.SignalSink(lambda pid: True)
    with pytest.raises(RuntimeError) as e:
        sink.deliver("pipe-1", "shelve")
    assert "pipe-1" in str(e.value)
    assert sink.take("pipe-1") is None


def test_the_sink_still_arms_when_the_tree_had_already_exited(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Registered but already dead: the spawn IS this pipeline's, its
    completion is moments away, and the signal must still decide how that
    completion cascades. Zero trees reaped is a count, not a refusal."""
    monkeypatch.setattr(spawn_registry, "_procs", {})
    monkeypatch.setattr(spawn_registry, "kill_proc_tree", lambda p: False)
    spawn_registry._procs["pipe-1"] = [object()]
    sink = spawn_registry.SignalSink(lambda pid: True)
    assert sink.deliver("pipe-1", "return_to_nl") == 0
    assert sink.take("pipe-1") == "return_to_nl"


def test_the_worker_binds_its_pipeline_before_it_spawns_anything() -> None:
    """The enumeration IS the audit, like the `proc.kill()` scan above: a
    dispatch path that stops binding leaves every spawn it makes
    unkillable by id, and nothing else would notice."""
    src = (ROOT / "Tooling" / "core" / "dispatcher"
           / "worker.py").read_text("utf-8")
    assert "spawn_registry.bind(pipeline_id)" in src
    assert "spawn_registry.unbind()" in src


def test_in_flight_is_read_off_the_live_futures_map() -> None:
    """The predicate the dispatcher hands the sink. It must read the map
    at CALL time: the loop pops a future before it cascades, so a
    pipeline whose worker has just finished is already not in flight —
    and killing on a pid the OS may have reassigned is the whole failure
    this aims away from."""
    class _Meta:
        def __init__(self, pipeline_id):
            self.pipeline_id = pipeline_id

    futures = {"fut-a": _Meta("pipe-1")}
    in_flight = spawn_registry.in_flight_over(futures)
    assert in_flight("pipe-1") is True
    assert in_flight("pipe-2") is False
    futures.pop("fut-a")
    assert in_flight("pipe-1") is False


def test_the_loop_hands_the_sink_to_the_command_applier() -> None:
    """The wiring, as an enumeration: without it every `Signal` on a live
    daemon is refused for want of a registry, and only a person trying to
    stop a worker would ever find out."""
    src = (ROOT / "Tooling" / "core" / "dispatcher"
           / "loop.py").read_text("utf-8")
    assert "_spawn_registry.SignalSink(" in src
    assert "signal_sink=signals" in src
    assert "_commands.finalise_signalled(" in src
