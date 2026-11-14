"""Checks beyond the acceptance tests: the MCP face's protocol edges, real-mode sign-in, cross-site
refusal, the pages, and a rule that is easy to break by accident (no interface text outside the message
catalogue).

    python -m pytest tests/test_m1a_extra.py -q
"""
import base64
import hashlib
import json
import os
import re
import secrets
import socket
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
CLEAN = {k: v for k, v in os.environ.items() if not k.upper().startswith(("ASTERISM", "CLAUDE", "CODEX"))}
ENV = dict(CLEAN, PYTHONPATH=str(ROOT), PYTHONIOENCODING="utf-8")
sys.path.insert(0, str(ROOT))


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start(data: Path, test_mode: bool):
    port = free_port()
    args = [PY, "-m", "asterism.server", "--data", str(data), "--port", str(port)] + (["--test-mode"] if test_mode else [])
    p = subprocess.Popen(args, cwd=str(ROOT), env=ENV, stdout=open(data / "server.out", "ab"),
                         stderr=open(data / "server.err", "ab"))
    url = f"http://127.0.0.1:{port}"
    end = time.time() + 30
    while time.time() < end:
        try:
            httpx.get(url + "/api/me", timeout=2)
            return p, url
        except httpx.HTTPError:
            time.sleep(0.2)
    p.kill()
    raise AssertionError((data / "server.err").read_text(errors="replace"))


def stop(p):
    p.terminate()
    p.wait(10)


@pytest.fixture(scope="module")
def srv(tmp_path_factory):
    data = tmp_path_factory.mktemp("extra")
    r = subprocess.run([PY, "-m", "asterism.admin", "--data", str(data), "create-project", "--slug", "lab", "--name",
                        "Lab <b>&", "--repo", "https://github.com/example/lab", "--owner", "alice"],
                       cwd=str(ROOT), env=ENV, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    p, url = start(data, True)
    yield url
    stop(p)


def signed_in(url, login):
    c = httpx.Client(base_url=url, follow_redirects=False, timeout=30)
    assert c.post("/test/login", json={"github_login": login}).status_code == 200
    return c


def connector_token(url, person):
    reg = httpx.post(url + "/oauth/register", json={"redirect_uris": ["https://chatgpt.com/cb"], "client_name": "ChatGPT"}).json()
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    q = {"response_type": "code", "client_id": reg["client_id"], "redirect_uri": "https://chatgpt.com/cb", "state": "s",
         "code_challenge": challenge, "code_challenge_method": "S256", "resource": f"{url}/lab/mcp"}
    loc = person.post("/oauth/authorize", data=dict(q, decision="approve")).headers["location"]
    code = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(loc).query))["code"]
    r = httpx.post(url + "/oauth/token", data={"grant_type": "authorization_code", "code": code, "code_verifier": verifier,
                                               "client_id": reg["client_id"], "redirect_uri": "https://chatgpt.com/cb"})
    return r.json()["access_token"], q


# --------------------------------------------------------------------------- shared wording

def test_pages_hold_no_interface_text_of_their_own():
    """Interface text lives in the message catalogue; a page or the page script that contains CJK text
    (the only locale today) has a string that bypasses it."""
    cjk = re.compile(r"[　-鿿＀-￯]")
    for f in (ROOT / "asterism" / "pages.py", ROOT / "asterism" / "web.py", ROOT / "asterism" / "static" / "app.js"):
        hits = [line for line in f.read_text(encoding="utf-8").splitlines() if cjk.search(line)]
        assert not hits, f"{f.name}: {hits[:3]}"


def test_sign_in_only_returns_to_paths_on_this_server():
    from asterism.util import safe_next
    assert safe_next("/lab/my?tab=AB-CD") == "/lab/my?tab=AB-CD"
    for bad in ("//evil.example/x", "https://evil.example/", "/\\evil.example", "javascript:alert(1)", "", None,
                "/x\r\nSet-Cookie: a=b"):
        assert safe_next(bad) == "/", bad


# --------------------------------------------------------------------------- the MCP face

def test_the_mcp_face_answers_the_protocol(srv):
    alice = signed_in(srv, "alice")
    token, _ = connector_token(srv, alice)
    h = {"Authorization": "Bearer " + token, "x-openai-session": "conv-x"}

    def post(body):
        return httpx.post(f"{srv}/lab/mcp", headers=h, content=json.dumps(body), timeout=30)
    r = post({"jsonrpc": "2.0", "id": 1, "method": "initialize",
              "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}})
    assert r.status_code == 200 and r.json()["result"]["protocolVersion"] == "2025-06-18"
    assert "tools" in r.json()["result"]["capabilities"]
    assert post({"jsonrpc": "2.0", "method": "notifications/initialized"}).status_code == 202
    names = [t["name"] for t in post({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}).json()["result"]["tools"]]
    assert names == ["register", "leave", "whoami", "send", "messages", "wait"]      # slice 1b adds the message tools
    assert post({"jsonrpc": "2.0", "id": 3, "method": "resources/list"}).json()["error"]["code"] == -32601
    assert post({"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "nope"}}).json()["error"]["code"] == -32602
    assert post([{"jsonrpc": "2.0", "id": 5, "method": "ping"}]).json()["error"]["code"] == -32600
    r = httpx.post(f"{srv}/lab/mcp", headers=h, content=b"{not json", timeout=30)
    assert r.json()["error"]["code"] == -32700
    left = post({"jsonrpc": "2.0", "id": 6, "method": "tools/call", "params": {"name": "leave", "arguments": {}}}).json()
    assert left["result"]["isError"] is True and "register" in left["result"]["content"][0]["text"]
    assert httpx.get(f"{srv}/lab/mcp", headers=h).status_code == 405


# --------------------------------------------------------------------------- web security

def test_cross_site_posts_with_the_session_cookie_are_refused(srv):
    alice = signed_in(srv, "alice")
    assert alice.post("/lab/api/invites", json={}, headers={"Origin": "https://evil.example"}).status_code == 403
    assert alice.post("/lab/api/invites", json={}, headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
    assert alice.post("/lab/api/invites", json={}, headers={"Origin": srv}).status_code == 201


def test_the_session_cookie_is_httponly_and_lax(srv):
    r = httpx.post(srv + "/test/login", json={"github_login": "alice"})
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie and "secure" not in cookie   # http here


def test_real_mode_sends_the_browser_to_github_with_a_state(tmp_path):
    (tmp_path / "config.json").write_text(json.dumps({"public_url": "https://hub.example", "github_client_id": "cid",
                                                      "github_client_secret": "sec"}))
    p, url = start(tmp_path, False)
    try:
        r = httpx.get(url + "/login", params={"next": "//evil.example/"}, follow_redirects=False)
        assert r.status_code == 302
        loc = urllib.parse.urlsplit(r.headers["location"])
        q = dict(urllib.parse.parse_qsl(loc.query))
        assert loc.netloc == "github.com" and q["client_id"] == "cid" and q["redirect_uri"] == "https://hub.example/login/callback"
        assert q["state"] and q["state"] in r.headers["set-cookie"] and "secure" in r.headers["set-cookie"].lower()
        bad = httpx.get(url + "/login/callback", params={"code": "c", "state": "forged"}, cookies={"asterism_login": q["state"]})
        assert bad.status_code == 400, "a state that is not the one this browser started with is refused"
        assert httpx.get(url + "/").status_code == 200
    finally:
        stop(p)
    assert q["state"] not in (tmp_path / "accounts.db").read_bytes().decode("latin-1")


# --------------------------------------------------------------------------- pages

def test_every_page_renders_and_escapes(srv):
    alice = signed_in(srv, "alice")
    for path in ("/", "/lab/members", "/lab/my", "/lab/admin"):
        r = alice.get(path)
        assert r.status_code == 200 and "<html" in r.text, path
        assert "Lab <b>&" not in r.text, "the project name is escaped"
    assert "Lab &lt;b&gt;&amp;" in alice.get("/lab/members").text
    _, q = connector_token(srv, alice)
    consent = alice.get("/oauth/authorize", params=q)
    assert consent.status_code == 200 and all(k in consent.text for k in
                                              ("others_mention", "others_channel", "others_assign", "others_regroup"))
    assert httpx.get(srv + "/lab/members", follow_redirects=False).headers["location"].startswith("/login?next=")
    bob = signed_in(srv, "bob")
    assert bob.get("/lab/members").status_code == 403 and bob.get("/lab/admin").status_code == 403
