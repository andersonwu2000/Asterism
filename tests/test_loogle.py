"""F50 — Loogle wrapper: type-pattern search via the public HTTPS API.

Three contracts:
1. `query()` returns (rc=0, formatted_text) on success — including 0
   hits (a valid answer; agent learns to refine).
2. Network / HTTP / parse errors → (rc=1, diagnosis text). Never raises.
3. Format is one line per hit (`<name>  ::  <type>  [<module>]`) with
   header preserved and a top-K cap so the prompt stays small.

Real network is mocked — these tests don't hit loogle.lean-lang.org.
"""
from __future__ import annotations

import io
import json
from contextlib import contextmanager
from urllib.error import HTTPError, URLError

import pytest

from Tooling.knowledge import loogle


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

@contextmanager
def _mock_response(monkeypatch: pytest.MonkeyPatch, payload: dict) -> None:
    """Patch urlopen to return a canned JSON payload."""
    body = json.dumps(payload).encode("utf-8")

    class _R:
        def read(self):
            return body

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(loogle.urllib.request, "urlopen",
                        lambda *a, **kw: _R())
    yield


@contextmanager
def _mock_error(monkeypatch: pytest.MonkeyPatch, exc: Exception) -> None:
    def _raise(*a, **kw):
        raise exc
    monkeypatch.setattr(loogle.urllib.request, "urlopen", _raise)
    yield


# ---------------------------------------------------------------------
# 1. Successful query path
# ---------------------------------------------------------------------

def test_query_returns_formatted_hits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "count": 9,
        "header": "Found 250 declarations mentioning Nat.factorial.",
        "hits": [
            {"name": "Nat.factorial_one",
             "type": " : Nat.factorial 1 = 1",
             "module": "Mathlib.Data.Nat.Factorial.Basic"},
            {"name": "Nat.factorial_two",
             "type": " : Nat.factorial 2 = 2",
             "module": "Mathlib.Data.Nat.Factorial.Basic"},
        ],
    }
    with _mock_response(monkeypatch, payload):
        rc, text = loogle.query("Nat.factorial _ = _")
    assert rc == 0
    assert "Found 250 declarations" in text
    assert "Nat.factorial_one  ::  Nat.factorial 1 = 1" in text
    assert "[Mathlib.Data.Nat.Factorial.Basic]" in text


def test_query_zero_hits_is_rc0(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """0 hits is a valid response — refine the pattern. Caller doesn't
    treat this as failure (rc=0)."""
    with _mock_response(monkeypatch, {"count": 0, "header": "no match", "hits": []}):
        rc, text = loogle.query("nonsense_pattern")
    assert rc == 0
    assert "no hits" in text.lower()


def test_query_caps_to_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Even when Loogle returns many hits, formatted output respects
    the limit so the agent's prompt doesn't bloat."""
    hits = [
        {"name": f"thm_{i}", "type": f": foo {i} = 1",
         "module": "Mathlib.X"} for i in range(50)
    ]
    payload = {"count": 50, "header": "Found 50.", "hits": hits}
    with _mock_response(monkeypatch, payload):
        rc, text = loogle.query("anything", limit=5)
    assert rc == 0
    assert "showing 5 of 50" in text
    # Last shown should be thm_4 (0-indexed); thm_5 must be absent
    assert "thm_4  ::" in text
    assert "thm_5  ::" not in text


def test_query_strips_leading_colon_from_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Loogle returns type as `: ...` — trim the colon for compactness."""
    payload = {"count": 1, "header": "h", "hits": [
        {"name": "x", "type": ": A = B", "module": "M"},
    ]}
    with _mock_response(monkeypatch, payload):
        _, text = loogle.query("any")
    assert "x  ::  A = B  [M]" in text
    # Verify no double colon remains
    assert "::  : " not in text


def test_query_limit_clamped_to_max(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Misuse: --limit 9999 should be clamped to MAX_LIMIT, not flood."""
    hits = [{"name": f"t{i}", "type": ": x", "module": "M"}
            for i in range(100)]
    with _mock_response(monkeypatch, {"count": 100, "header": "h", "hits": hits}):
        _, text = loogle.query("any", limit=9999)
    # MAX_LIMIT is 50
    assert f"showing {loogle.MAX_LIMIT} of 100" in text


def test_query_limit_floored_to_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bad input: --limit 0 or negative should still show ≥ 1 hit."""
    payload = {"count": 5, "header": "h", "hits": [
        {"name": "t1", "type": ": x", "module": "M"},
        {"name": "t2", "type": ": x", "module": "M"},
    ]}
    with _mock_response(monkeypatch, payload):
        _, text = loogle.query("any", limit=0)
    assert "t1  ::" in text
    assert "t2  ::" not in text


# ---------------------------------------------------------------------
# 2. Error paths
# ---------------------------------------------------------------------

def test_query_network_error_returns_rc1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DNS / TCP failure → rc=1 + descriptive message. Caller can fall
    back to Grep without crashing."""
    with _mock_error(monkeypatch, URLError("getaddrinfo failed")):
        rc, text = loogle.query("any")
    assert rc == 1
    assert "network error" in text
    assert "getaddrinfo" in text


def test_query_http_error_returns_rc1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HTTP 5xx from Loogle → rc=1 with status code surfaced."""
    err = HTTPError(url="x", code=503, msg="Service Unavailable",
                    hdrs=None, fp=None)
    with _mock_error(monkeypatch, err):
        rc, text = loogle.query("any")
    assert rc == 1
    assert "503" in text
    assert "Service Unavailable" in text


def test_query_timeout_returns_rc1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _mock_error(monkeypatch, TimeoutError("timed out")):
        rc, text = loogle.query("any", timeout=1)
    assert rc == 1
    assert "network error" in text or "timed out" in text


def test_query_invalid_json_returns_rc1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unexpected non-JSON payload (e.g. captive portal HTML) → rc=1
    with parse-error message rather than blowing up."""
    class _R:
        def read(self):
            return b"<html>not json</html>"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(loogle.urllib.request, "urlopen",
                        lambda *a, **kw: _R())
    rc, text = loogle.query("any")
    assert rc == 1
    assert "parse error" in text


# ---------------------------------------------------------------------
# 3. CLI entry point
# ---------------------------------------------------------------------

def test_main_prints_and_exits_zero(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture,
) -> None:
    payload = {"count": 1, "header": "h", "hits": [
        {"name": "Foo.bar", "type": ": A = B", "module": "Mathlib.X"},
    ]}
    with _mock_response(monkeypatch, payload):
        rc = loogle.main(["Foo.bar"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Foo.bar  ::  A = B" in out


def test_main_propagates_error_rc(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture,
) -> None:
    with _mock_error(monkeypatch, URLError("offline")):
        rc = loogle.main(["any"])
    assert rc == 1
    assert "network error" in capsys.readouterr().out
