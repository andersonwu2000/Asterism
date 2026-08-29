"""The editor's sync endpoint, CALLED — not grepped.

`interactive_sync` used to delegate to `apply_edit(1, end, content)`.
That line-range signature retired on 2026-08-10 (`1d7ad006`), so every
sync since raised TypeError and surfaced as HTTP 500 — for five days,
under a green test. The guard that should have caught it read the
module's SOURCE for the string "apply_edit" and was satisfied by a call
that could never run.

So this file invokes the route. A signature drift now fails here rather
than in the owner's browser, and the metaprogramming scan the entry
grew when the delegation went (`test_metaprog_guard.py`) is exercised
end-to-end rather than asserted lexically.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from Tooling.lsp import gateway as lsp_gateway
from Tooling.lsp.gateway import _state


class _FakeRequest:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    async def json(self) -> dict:
        return self._payload


class _FakeBackend:
    """Records what the sync pushed into the worker."""

    def __init__(self) -> None:
        self.pushed: list[tuple[str, int]] = []

    def did_change_full(self, path, content, version) -> None:
        self.pushed.append((content, version))

    def clear_diagnostics(self, *a) -> None: ...

    def wait_for_diagnostics(self, *a, **kw) -> None: ...

    def diagnostics_for(self, uri) -> list:
        return []


def _editor_session(monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
                    ) -> tuple[str, _FakeBackend]:
    slot = lsp_gateway.WorkerSlot(
        slot_id=0, slot_path=tmp_path / "slot_0.lean",
        slot_uri="file:///fake/slot_0.lean", claimed_by="interactive-x",
        content_pipeline_id="interactive-x", reserved=True,
    )
    monkeypatch.setattr(_state, "workers", [slot])
    backend = _FakeBackend()
    monkeypatch.setattr(_state, "backend", backend)
    meta = lsp_gateway.SessionMetadata(
        pipeline_id="interactive-x", target_path=tmp_path / "scratch.lean",
        problem="", workspace=tmp_path, log_path=None, kind="interactive",
        file_content="-- old\n",
    )
    token = "tok-editor"
    with _state.sessions_lock:
        _state.sessions[token] = meta
    monkeypatch.setattr(_state, "sessions",
                        dict(_state.sessions), raising=False)
    return token, backend


def _sync(token: str, content: str, **extra) -> tuple[int, dict]:
    resp = asyncio.run(lsp_gateway.interactive_sync(
        _FakeRequest({"token": token, "content": content, **extra})))
    return resp.status_code, json.loads(bytes(resp.body).decode("utf-8"))


def test_a_sync_reaches_the_worker(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    token, backend = _editor_session(monkeypatch, tmp_path)

    status, body = _sync(token, "theorem t : True := trivial\n")

    assert status == 200, body
    assert backend.pushed, (
        "the editor's text never reached a worker — this is exactly the "
        "shape of the delegation bug (the call raised before pushing)")
    content, _version = backend.pushed[-1]
    assert "theorem t : True := trivial" in content
    # The buffer IS the compilation unit for an interactive session: no
    # framework prefix, no sibling stubs (`_compilation_for`).
    assert content.strip() == "theorem t : True := trivial"


def test_the_mirror_holds_what_the_editor_sent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """A full-buffer SET, not an edit: whatever arrives replaces the
    mirror outright, so a later `goal_at` sees the editor's text."""
    token, _backend = _editor_session(monkeypatch, tmp_path)
    _sync(token, "def g := 1\n")
    with _state.sessions_lock:
        assert _state.sessions[token].file_content == "def g := 1\n"


def test_the_scratch_file_follows_the_buffer(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Disk, not the mirror, is what a goal query trusts: `goal_at`
    opens by adopting `target_path` (the T1 resync, for agents editing
    through Write/Edit). A sync that updated only the mirror would be
    silently reverted by the cursor query riding the same request."""
    token, _backend = _editor_session(monkeypatch, tmp_path)
    (tmp_path / "scratch.lean").write_text("-- stale\n", encoding="utf-8")

    _sync(token, "theorem t : True := trivial\n")

    assert (tmp_path / "scratch.lean").read_text(encoding="utf-8") == (
        "theorem t : True := trivial\n")


def test_unfinished_elaboration_does_not_read_as_clean(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """An empty diagnostic list means "no news yet" when Lean has not
    converged. Every agent-facing tool carries that bit; the editor
    dropped it, which made the owner's surface the one place a timeout
    looked like a clean file."""
    token, backend = _editor_session(monkeypatch, tmp_path)
    from Tooling.lsp.gateway import rpc
    # the wall in miniature: a fake that gives up at once would
    # otherwise sleep the real 300s budget (2026-08-29)
    monkeypatch.setattr(rpc, "ELAB_WALL_SEC", 0.05)
    monkeypatch.setattr(rpc, "ELAB_WALL_SLICE_SEC", 0.005)

    def _timeout(*a, **kw):
        raise TimeoutError("still elaborating")
    monkeypatch.setattr(backend, "wait_for_diagnostics", _timeout)

    status, body = _sync(token, "theorem t : True := trivial\n")
    assert status == 200
    assert body["diagnostics"] == []
    assert body["converged"] is False
    # 2026-08-29: the wall is a hard failure — the note carries the
    # verdict's teaching and the structured wall info rides alongside.
    assert "FAILURE" in (body["note"] or "")
    assert body["elab_wall"]["wall_s"] == rpc.ELAB_WALL_SEC, "the default wall"


def test_converged_sync_says_so(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    token, _backend = _editor_session(monkeypatch, tmp_path)
    _status, body = _sync(token, "theorem t : True := trivial\n")
    assert body["converged"] is True
    assert body["note"] is None


def test_metaprogramming_is_refused_before_it_elaborates(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """The scan this entry grew when it stopped delegating to
    `apply_edit` — checked by calling it, not by grepping for the name.
    Elab-time code runs with the framework's privileges the moment a
    worker sees it, so the refusal must land BEFORE the push."""
    token, backend = _editor_session(monkeypatch, tmp_path)
    (tmp_path / "scratch.lean").write_text("-- clean\n", encoding="utf-8")

    status, body = _sync(token, 'elab "x" : tactic => pure ()\n')

    assert status == 400, body
    assert "elab" in body["error"]
    assert backend.pushed == [], (
        "the metaprogramming reached a worker anyway — the scan must "
        "come before did_change_full, not after")
    assert (tmp_path / "scratch.lean").read_text(encoding="utf-8") == (
        "-- clean\n"), "the blocked text reached disk, where lake can see it"


def test_an_unknown_token_is_not_a_crash(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    _token, _backend = _editor_session(monkeypatch, tmp_path)
    status, body = _sync("no-such-token", "def g := 1\n")
    assert status == 404
    assert "unknown interactive session" in body["error"]
