

# ---------------------------------------------------------------------
# Politeness (user call 2026-08-22: a fleet of concurrent strategists
# chain-429'd OpenAlex's free API)
# ---------------------------------------------------------------------

def test_requests_to_one_host_are_spaced(monkeypatch) -> None:
    from Tooling.papers import search as s
    clock = {"t": 100.0}
    slept: list = []
    monkeypatch.setattr(s, "_now", lambda: clock["t"])

    def fake_sleep(sec):
        slept.append(sec)
        clock["t"] += sec

    monkeypatch.setattr(s, "_sleep", fake_sleep)
    s._HOST_LAST.clear()
    s._polite_slot("api.openalex.org")
    assert not slept, "first request goes straight through"
    s._polite_slot("api.openalex.org")
    assert slept and sum(slept) >= s._HOST_MIN_INTERVAL - 0.2
    slept.clear()
    s._polite_slot("api.crossref.org")
    assert not slept, "hosts are independent"
    s._HOST_LAST.clear()


def test_a_429_backs_off_per_retry_after_then_retries_once(
        monkeypatch) -> None:
    import urllib.error
    import io
    from Tooling.papers import search as s
    calls = {"n": 0}
    slept: list = []
    monkeypatch.setattr(s, "_polite_slot", lambda host: None)
    monkeypatch.setattr(s, "_sleep", lambda sec: slept.append(sec))

    def fake_urlopen(req, timeout=0):
        calls["n"] += 1
        if calls["n"] == 1:
            raise urllib.error.HTTPError(
                req.full_url, 429, "Too Many Requests",
                {"Retry-After": "7"}, io.BytesIO(b""))

        class _R(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        return _R(b'{"ok": 1}')

    monkeypatch.setattr(s.urllib.request, "urlopen", fake_urlopen)
    assert s._get_json("https://api.openalex.org/works?q=x") == {"ok": 1}
    assert 7 in slept and calls["n"] == 2
