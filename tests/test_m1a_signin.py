"""Acceptance checks for the real sign-in path and for what the server writes down when something is refused.

Black box. A real server process runs in REAL mode (no --test-mode) against a stand-in for GitHub that this
file runs on localhost; the server is pointed at it with ASTERISM_GITHUB_WEB_URL and ASTERISM_GITHUB_API_URL.
Nothing here imports the server's code. What the server writes down is read from DIR/log.jsonl.

    python -m pytest tests/test_m1a_signin.py -x -q
"""
import http.server
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
SLUG = "lab"
CLIENT_ID = "Iv23testclientid"
GOOD_SECRET = "s" * 40
CLEAN = {k: v for k, v in os.environ.items() if not k.upper().startswith(("ASTERISM", "CLAUDE", "CODEX"))}


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def until(fn, timeout=8.0, every=0.2):
    end = time.time() + timeout
    while True:
        v = fn()
        if v or time.time() > end:
            return v
        time.sleep(every)


class FakeGitHub:
    """Answers the two calls the server makes: the code exchange and "who is this"."""

    def __init__(self):
        self.user_status = 200          # a test sets 401 to make "who is this" fail
        self.port = free_port()
        self.url = f"http://127.0.0.1:{self.port}"
        fake = self

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, status, obj):
                body = json.dumps(obj).encode()
                self.send_response(status)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                form = urllib.parse.parse_qs(self.rfile.read(int(self.headers.get("content-length") or 0)).decode())
                one = lambda k: (form.get(k) or [""])[0]  # noqa: E731
                if self.path != "/login/oauth/access_token":
                    return self._send(404, {})
                if one("client_id") != CLIENT_ID or one("client_secret") != GOOD_SECRET:
                    return self._send(200, {"error": "incorrect_client_credentials"})
                if not one("code").startswith("good-"):
                    return self._send(200, {"error": "bad_verification_code"})
                self._send(200, {"access_token": "tok-" + one("code")[5:], "token_type": "bearer"})

            def do_GET(self):
                auth = self.headers.get("authorization") or ""
                if self.path != "/user" or not auth.startswith("Bearer tok-"):
                    return self._send(404, {})
                if fake.user_status != 200:
                    return self._send(fake.user_status, {"message": "Bad credentials"})
                login = auth[len("Bearer tok-"):]
                self._send(200, {"id": 1000 + len(login), "login": login})

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", self.port), H)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()


class RealServer:
    def __init__(self, data: Path, github_url: str, secret: str = GOOD_SECRET):
        self.data, self.port, self.p = data, free_port(), None
        self.url = f"http://127.0.0.1:{self.port}"
        self.secret = secret
        (data / "config.json").write_text(json.dumps({"public_url": self.url, "github_client_id": CLIENT_ID,
                                                      "github_client_secret": secret}), encoding="utf-8")
        self.env = dict(CLEAN, PYTHONPATH=str(ROOT), PYTHONIOENCODING="utf-8",
                        ASTERISM_GITHUB_WEB_URL=github_url, ASTERISM_GITHUB_API_URL=github_url)
        r = subprocess.run([PY, "-m", "asterism.admin", "--data", str(data), "create-project", "--slug", SLUG,
                            "--name", "Test Lab", "--repo", "https://github.com/example/lab", "--owner", "alice"],
                           cwd=str(ROOT), env=self.env, capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr

    def start(self):
        self.p = subprocess.Popen([PY, "-m", "asterism.server", "--data", str(self.data), "--port", str(self.port)],
                                  cwd=str(ROOT), env=self.env, stdout=open(self.data / "server.out", "ab"),
                                  stderr=open(self.data / "server.err", "ab"))

        def up():
            try:
                return httpx.get(self.url + "/api/me", timeout=2).status_code in (200, 401)
            except httpx.HTTPError:
                return False
        assert until(up, 30), "the server did not come up: " + (self.data / "server.err").read_text(errors="replace")[-800:]
        return self

    def stop(self):
        if self.p:
            self.p.terminate()
            try:
                self.p.wait(10)
            except subprocess.TimeoutExpired:
                self.p.kill()
            self.p = None

    def log(self) -> list[dict]:
        path = self.data / "log.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def events(self, name: str) -> list[dict]:
        return [e for e in self.log() if e.get("event") == name]

    def raw_log(self) -> str:
        path = self.data / "log.jsonl"
        return path.read_text(encoding="utf-8") if path.exists() else ""


@pytest.fixture(scope="module")
def github():
    g = FakeGitHub()
    yield g
    g.stop()


@pytest.fixture(scope="module")
def srv(tmp_path_factory, github):
    s = RealServer(tmp_path_factory.mktemp("real"), github.url).start()
    yield s
    s.stop()


def begin(srv) -> tuple[httpx.Client, str]:
    """Open /login in a fresh browser; return the browser and the state the server sent to GitHub."""
    c = httpx.Client(base_url=srv.url, follow_redirects=False, timeout=30)
    r = c.get("/login")
    assert r.status_code == 302, r.text
    return c, r.headers["location"]


def state_of(location: str) -> str:
    return urllib.parse.parse_qs(urllib.parse.urlparse(location).query)["state"][0]


def failures(srv, since: int) -> list[dict]:
    return srv.events("github_sign_in_failed")[since:]


# ------------------------------------------------------------------ the real sign-in path

def test_login_sends_the_browser_to_the_configured_github(srv, github):
    _, location = begin(srv)
    assert location.startswith(github.url + "/login/oauth/authorize?"), location
    q = urllib.parse.parse_qs(urllib.parse.urlparse(location).query)
    assert q["client_id"] == [CLIENT_ID]
    assert q["redirect_uri"] == [srv.url + "/login/callback"]


def test_sign_in_through_github_works(srv):
    c, location = begin(srv)
    r = c.get("/login/callback", params={"code": "good-alice", "state": state_of(location)})
    assert r.status_code == 303, r.text
    me = c.get("/api/me")
    assert me.status_code == 200, me.text
    assert me.json()["person"]["github_login"] == "alice"
    assert srv.events("signed_in"), "a successful sign-in is written down"


# ------------------------------------------------------------------ a failed sign-in says why, in the log

def test_code_github_rejects_is_logged_with_githubs_reason(srv):
    n = len(srv.events("github_sign_in_failed"))
    c, location = begin(srv)
    r = c.get("/login/callback", params={"code": "stale-code-123", "state": state_of(location)})
    assert r.status_code == 502
    assert c.get("/api/me").status_code == 401
    new = failures(srv, n)
    assert len(new) == 1, new
    assert new[0]["step"] == "token" and new[0]["reason"] == "bad_verification_code", new[0]
    assert "stale-code-123" not in srv.raw_log(), "the code itself is not written down"


def test_github_not_saying_who_signed_in_is_logged(srv, github):
    n = len(srv.events("github_sign_in_failed"))
    github.user_status = 401
    try:
        c, location = begin(srv)
        r = c.get("/login/callback", params={"code": "good-carol", "state": state_of(location)})
    finally:
        github.user_status = 200
    assert r.status_code == 502
    new = failures(srv, n)
    assert len(new) == 1, new
    assert new[0]["step"] == "user" and new[0]["reason"] == "http_401", new[0]
    assert "tok-carol" not in srv.raw_log(), "GitHub's token is not written down"


def test_callback_in_another_browser_is_logged(srv):
    n = len(srv.events("github_sign_in_failed"))
    _, location = begin(srv)
    other = httpx.Client(base_url=srv.url, follow_redirects=False, timeout=30)
    r = other.get("/login/callback", params={"code": "good-alice", "state": state_of(location)})
    assert r.status_code == 400
    new = failures(srv, n)
    assert len(new) == 1, new
    assert new[0]["step"] == "state", new[0]
    assert state_of(location) not in srv.raw_log()


def test_wrong_client_secret_is_logged_and_the_secret_is_not(tmp_path, github):
    wrong = "w" * 14
    s = RealServer(tmp_path, github.url, secret=wrong).start()
    try:
        c, location = begin(s)
        r = c.get("/login/callback", params={"code": "good-alice", "state": state_of(location)})
        assert r.status_code == 502
        new = s.events("github_sign_in_failed")
        assert len(new) == 1, new
        assert new[0]["step"] == "token" and new[0]["reason"] == "incorrect_client_credentials", new[0]
        assert wrong not in s.raw_log()
    finally:
        s.stop()


def test_github_unreachable_is_logged(tmp_path):
    s = RealServer(tmp_path, f"http://127.0.0.1:{free_port()}").start()      # nothing listens there
    try:
        c, location = begin(s)
        r = c.get("/login/callback", params={"code": "good-alice", "state": state_of(location)})
        assert r.status_code == 502
        new = s.events("github_sign_in_failed")
        assert len(new) == 1, new
        assert new[0]["step"] == "token" and new[0]["reason"] == "unreachable", new[0]
    finally:
        s.stop()


# ------------------------------------------------------------------ refused connector calls are visible

RPC = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
HEAD = {"accept": "application/json, text/event-stream"}


def test_connector_call_without_a_token_is_logged_once_a_minute(srv):
    n = len(srv.events("mcp_refused"))
    for _ in range(3):
        r = httpx.post(f"{srv.url}/{SLUG}/mcp", json=RPC, headers=dict(HEAD, **{"user-agent": "probe-one/1.0"}), timeout=30)
        assert r.status_code == 401
    new = srv.events("mcp_refused")[n:]
    assert len(new) == 1, "the same refusal from the same client is written down once a minute, not every time"
    assert new[0]["project"] == SLUG and new[0]["reason"] == "no_token" and new[0]["client"] == "probe-one/1.0", new[0]


def test_connector_call_with_an_unknown_token_is_logged(srv):
    n = len(srv.events("mcp_refused"))
    token = "at_this-token-was-never-issued"
    r = httpx.post(f"{srv.url}/{SLUG}/mcp", json=RPC, timeout=30,
                   headers=dict(HEAD, **{"user-agent": "probe-two/1.0", "authorization": "Bearer " + token}))
    assert r.status_code == 401
    new = srv.events("mcp_refused")[n:]
    assert len(new) == 1, new
    assert new[0]["reason"] == "bad_token" and new[0]["client"] == "probe-two/1.0", new[0]
    assert token not in srv.raw_log()


def test_a_long_client_name_is_cut(srv):
    n = len(srv.events("mcp_refused"))
    r = httpx.post(f"{srv.url}/{SLUG}/mcp", json=RPC, headers=dict(HEAD, **{"user-agent": "x" * 500}), timeout=30)
    assert r.status_code == 401
    new = srv.events("mcp_refused")[n:]
    assert len(new) == 1 and len(new[0]["client"]) <= 80, new


def test_a_state_with_unusual_characters_is_refused_not_a_crash(srv):
    n = len(srv.events("github_sign_in_failed"))
    c, _ = begin(srv)
    r = c.get("/login/callback", params={"code": "good-alice", "state": "狀態-é"})
    assert r.status_code == 400, r.status_code
    new = failures(srv, n)
    assert len(new) == 1 and new[0]["step"] == "state" and new[0]["reason"] == "mismatch", new
