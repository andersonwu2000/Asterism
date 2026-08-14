"""The per-call gateway log must not be deleted with the attempt.

`_mcp.jsonl` is the only machine-readable record of what a spawn asked
the gateway for — which slot served it, whether elaboration converged,
how long each call took. Nothing reads it back, so its entire value is
being there afterwards.

It used to be written into `attempts_dir`, which `WorkArea.__exit__`
rmtree's. On 2026-08-15 a gateway defect that had produced 59 agent
complaints over two days was diagnosed from the agents' own prose,
because not one of the 59 incidents had left a trace: every per-call
record had gone down with its attempt. The provider transcripts moved
out of that tree the same day for the same reason.
"""
from __future__ import annotations

from pathlib import Path

from Tooling import pipeline


def test_the_log_is_written_outside_the_attempts_tree(
        tmp_path: Path, monkeypatch):
    workspace = tmp_path / "ws"
    attempts = workspace / ".attempts" / "pid-1"
    attempts.mkdir(parents=True)

    seen: dict = {}

    class _Resp:
        def read(self):
            return b'{"session_token": "tok"}'

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def _urlopen(req, *a, **k):
        import json
        seen.update(json.loads(req.data.decode("utf-8")))
        return _Resp()

    import urllib.request as _u
    monkeypatch.setattr(_u, "urlopen", _urlopen)

    pipeline._write_mcp_config(
        attempts, workspace, attempts / "patch.lean",
        pipeline_id="pid-1", problem="P", kind="backward")

    log = seen.get("log_path")
    assert log, f"no log_path was registered: {seen}"
    log = Path(log)
    assert ".attempts" not in log.parts, (
        f"the per-call log is inside the tree that gets deleted: {log}")
    assert log.parent == workspace / ".asterism" / "mcp_logs"
    assert log.name == "pid-1.jsonl", (
        "named by pipeline, or concurrent spawns overwrite each other")
    assert log.parent.is_dir(), "the directory was not created"
