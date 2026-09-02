"""Which OS process is running which pipeline — and the sink a person's
kill signal is delivered through (human_interface_design.md §3.7).

A person may stop one in-flight Formalizer. That is a kill, and a kill in
this repo is aimed at a specific PID/process tree, never at a name: a
`name + age` sweep of `claude.exe` once killed the operator's own
conversation, which is why CLAUDE.md rule 8 exists at all.

Aiming at a pipeline needs two facts that live in different layers and
never meet:

  * the dispatcher's worker thread knows the `pipeline_id`
    (`dispatcher/worker.py::_run_pipeline`), and knows nothing about
    processes — its spawn is several call frames down inside a provider;
  * the provider knows the `Popen` (and its Job Object), and knows
    nothing about pipelines — `LLMRequest` carries an `attempts_dir`, not
    an identity.

The two share exactly one thing: the THREAD. So the binding is
thread-local — the worker binds once at entry, and every provider's
`track_proc` (the one chokepoint every spawn already goes through, for
`request_shutdown`) records its process under whatever is bound. A spawn
made outside a pipeline (a probe, a rescue turn) binds nothing and is
recorded nowhere, which is the honest answer: the signal refuses on an
empty list rather than reaching for a neighbour's process.

`SignalSink` is the object `state/commands.apply_pending` is handed. It
exists so `state/` never imports the dispatcher: the applier runs inside
the daemon's tick and needs two facts only the loop has — whether a
pipeline is in THIS daemon's flight, and the process tree to kill —
so the loop passes them in rather than the state layer reaching up.

The sink also ARMS the outcome. Killing a spawn does not by itself tell
the dispatcher WHY the worker died, and a death with no reason is
finalised as an infra failure. So the signal is remembered here until the
future completes, and the loop's completion path (the existing one — the
kill invents no new cascade) takes it and cascades the pipeline as that
signal instead of as its own accidental ending.
"""
from __future__ import annotations

import threading
from typing import Callable

from ..llm.claude_cli import kill_proc_tree

#: pipeline_id -> the live spawn processes recorded under it. A list, not
#: one process: a pipeline's retry loop and its postmortem turn are
#: separate spawns, and mid-swap both can be live for an instant.
_procs: "dict[str, list]" = {}
_lock = threading.Lock()

#: The pipeline the CURRENT thread is spawning for. Thread-local, not a
#: parameter, because the layer that knows it and the layer that needs it
#: are separated by every provider's whole call stack.
_bound = threading.local()


def bind(pipeline_id: str) -> None:
    """Claim this thread for `pipeline_id`. Called once by the worker at
    entry, before anything it does can spawn."""
    _bound.pipeline_id = str(pipeline_id)


def unbind() -> None:
    """Release the thread. The pool REUSES threads, so a missed unbind
    would file the next pipeline's spawns under this one's id."""
    _bound.pipeline_id = None


def current() -> "str | None":
    return getattr(_bound, "pipeline_id", None)


def register(proc) -> None:  # noqa: ANN001 — any Popen-like
    """Record a live spawn under the calling thread's pipeline, if it has
    one. Silent no-op otherwise — see the module docstring."""
    pid = current()
    if pid is None:
        return
    with _lock:
        _procs.setdefault(pid, []).append(proc)


def unregister(proc) -> None:  # noqa: ANN001
    """Forget a spawn that has ended. Searches every pipeline rather than
    trusting the thread binding: `untrack_proc` runs in a `finally`, and
    a `finally` can run after an unbind."""
    with _lock:
        for pid, procs in list(_procs.items()):
            if proc in procs:
                procs.remove(proc)
            if not procs:
                _procs.pop(pid, None)


def procs_for(pipeline_id: str) -> list:
    with _lock:
        return list(_procs.get(str(pipeline_id), ()))


def in_flight_over(futures) -> "Callable[[str], bool]":  # noqa: ANN001
    """`SignalSink`'s predicate, over the dispatcher's live futures map.

    Reads the map at call time, deliberately: the loop POPS a future
    before it cascades, so a pipeline whose worker has just finished is
    already not in flight and its signal is refused rather than aimed at
    a pid the OS may have handed to somebody else."""
    return lambda pipeline_id: any(
        getattr(meta, "pipeline_id", None) == pipeline_id
        for meta in futures.values())


class SignalSink:
    """The daemon's half of §3.7's kill, handed to the command applier.

    `in_flight` answers "does THIS daemon hold a future for that
    pipeline?". The DB cannot answer it: a `pipelines` row reads
    `running` until somebody finalises it, so a daemon that died mid-run
    leaves rows that outlive every process they name — and on Windows a
    pid is reused, so a kill on the strength of such a row is a kill
    aimed at a stranger.
    """

    def __init__(self, in_flight: "Callable[[str], bool]") -> None:
        self._in_flight = in_flight
        self._armed: "dict[str, str]" = {}

    def deliver(self, pipeline_id: str, signal: str) -> int:
        """Kill this pipeline's process tree and arm its outcome. Returns
        how many trees were reaped. Raises rather than pretending:
        `KeyError` = not this daemon's work, `RuntimeError` = in flight
        but holding nothing killable."""
        pipeline_id = str(pipeline_id)
        if not self._in_flight(pipeline_id):
            raise KeyError(
                f"pipeline {pipeline_id} is not in flight in this daemon "
                f"— the DB row may be a previous run's; there is nothing "
                f"here to kill")
        procs = procs_for(pipeline_id)
        if not procs:
            raise RuntimeError(
                f"pipeline {pipeline_id} is in flight but no spawn "
                f"process is registered for it — either the worker has "
                f"not spawned yet, or its provider runs the CLI without a "
                f"handle to kill (agy). Killing by NAME is not an "
                f"alternative; re-issue the signal.")
        # Registered but already exited counts 0 and still arms: the
        # spawn IS this pipeline's, its completion is moments away, and
        # the signal is what decides how that completion cascades.
        killed = sum(1 for p in procs if kill_proc_tree(p))
        self._armed[pipeline_id] = str(signal)
        return killed

    def take(self, pipeline_id: str) -> "str | None":
        """The armed signal for a pipeline that has just completed, spent
        on read — a signal decides exactly one ending."""
        return self._armed.pop(str(pipeline_id), None)
