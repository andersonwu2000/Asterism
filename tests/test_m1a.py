"""Acceptance checks for M1 slice 1a: accounts, members, groups, authorising and registering agents.

Black box. A real server process runs in test mode (GitHub sign-in replaced by a stand-in) and is driven
over HTTP; the real helper is driven over stdio. Nothing here imports the server's code.

The tests run in file order and share one server: later tests build on the people created by earlier ones.

    python -m pytest tests/test_m1a.py -x -q
"""
import base64
import hashlib
import json
import os
import queue
import secrets
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
REPO = "https://github.com/example/lab"
OFFLINE_S, DEVICE_TTL_S, ACCESS_TTL_S = 3, 8, 8
# Nothing of the session that runs the tests may leak into the processes under test.
CLEAN = {k: v for k, v in os.environ.items() if not k.upper().startswith(("ASTERISM", "CLAUDE", "CODEX"))}
ENV = dict(CLEAN, PYTHONPATH=str(ROOT), PYTHONIOENCODING="utf-8", ASTERISM_OFFLINE_AFTER_S=str(OFFLINE_S),
           ASTERISM_DEVICE_TTL_S=str(DEVICE_TTL_S), ASTERISM_ACCESS_TTL_S=str(ACCESS_TTL_S))
SECRETS: list[str] = []          # every secret a test was handed; none may be stored in clear
REDIRECT = "https://chatgpt.com/connector_platform_oauth_redirect"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def until(fn, timeout=8.0, every=0.25):
    """Poll `fn` until it returns something truthy; return the last value either way."""
    end = time.time() + timeout
    while True:
        v = fn()
        if v or time.time() > end:
            return v
        time.sleep(every)


class Server:
    def __init__(self, data: Path, test_mode: bool = True):
        self.data, self.test_mode, self.port, self.p = data, test_mode, free_port(), None
        self.url = f"http://127.0.0.1:{self.port}"

    def start(self):
        args = [PY, "-m", "asterism.server", "--data", str(self.data), "--port", str(self.port)]
        self.p = subprocess.Popen(args + (["--test-mode"] if self.test_mode else []), cwd=str(ROOT), env=ENV,
                                  stdout=open(self.data / "server.out", "ab"), stderr=open(self.data / "server.err", "ab"))

        def up():
            try:
                return httpx.get(self.url + "/api/me", timeout=2).status_code in (200, 401)
            except httpx.HTTPError:
                return False
        assert until(up, 30), "the server did not come up: " + (self.data / "server.err").read_text(errors="replace")[-800:]

    def stop(self):
        if self.p:
            self.p.terminate()
            try:
                self.p.wait(10)
            except subprocess.TimeoutExpired:
                self.p.kill()
            self.p = None


@pytest.fixture(scope="module")
def srv(tmp_path_factory):
    data = tmp_path_factory.mktemp("data")
    r = subprocess.run([PY, "-m", "asterism.admin", "--data", str(data), "create-project", "--slug", SLUG, "--name", "Test Lab",
                        "--repo", REPO, "--owner", "alice"], cwd=str(ROOT), env=ENV, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    s = Server(data)
    s.start()
    yield s
    s.stop()


def browser(srv, login=None) -> httpx.Client:
    c = httpx.Client(base_url=srv.url, follow_redirects=False, timeout=30)
    if login:
        r = c.post("/test/login", json={"github_login": login})
        assert r.status_code == 200, r.text
    return c


def invite(owner: httpx.Client, login=None) -> str:
    r = owner.post(f"/{SLUG}/api/invites", json={"github_login": login} if login else {})
    assert r.status_code == 201, r.text
    path = urllib.parse.urlparse(r.json()["url"]).path
    SECRETS.append(path.rsplit("/", 1)[1])
    return path


@pytest.fixture(scope="module")
def alice(srv):          # the owner: the project was created for the GitHub login "alice"
    return browser(srv, "alice")


@pytest.fixture(scope="module")
def bob(srv, alice):
    c = browser(srv, "bob")
    assert c.post(invite(alice, "bob")).status_code == 200
    return c


def members(c: httpx.Client) -> dict:
    r = c.get(f"/{SLUG}/api/members")
    assert r.status_code == 200, r.text
    return r.json()


def agent_row(c, name):
    return next((a for a in members(c)["agents"] if a["name"] == name), None)


def online(c, name):
    row = agent_row(c, name)
    return bool(row and row["online"])


def device_start(srv, kind="claude-code", computer="pc-1") -> dict:
    r = httpx.post(f"{srv.url}/{SLUG}/device/start", json={"kind": kind, "computer": computer}, timeout=30)
    assert r.status_code == 200, r.text
    SECRETS.append(r.json()["device_code"])
    return r.json()


def device_token(srv, d) -> httpx.Response:
    return httpx.post(f"{srv.url}/{SLUG}/device/token", json={"device_code": d["device_code"]}, timeout=30)


def authorise(srv, person: httpx.Client, kind="claude-code", computer="pc-1", switches=None) -> str:
    """The whole device flow: a helper asks, the person approves, the helper gets its credential."""
    d = device_start(srv, kind, computer)
    body = {"decision": "approve", **({"switches": switches} if switches else {})}
    r = person.post(f"/{SLUG}/api/device/{d['user_code']}", json=body)
    assert r.status_code == 200, r.text
    r = device_token(srv, d)
    assert r.status_code == 200, r.text
    SECRETS.append(r.json()["credential"])
    return r.json()["credential"]


class Agent:
    """One session of a local agent, speaking the helper-to-server API directly."""

    def __init__(self, srv, credential, sid, client="claude-code"):
        self.c = httpx.Client(base_url=srv.url, timeout=30, headers={
            "Authorization": "Bearer " + credential, "X-Asterism-Session": sid, "X-Asterism-Client": client})
        self._stop = None

    def register(self, name, takeover=False):
        return self.c.post(f"/{SLUG}/api/agent/register", json={"name": name, "takeover": takeover})

    def whoami(self):
        return self.c.get(f"/{SLUG}/api/agent/whoami")

    def leave(self):
        return self.c.post(f"/{SLUG}/api/agent/leave")

    def hold(self):
        """Keep the presence poll open, as a running helper does."""
        self._stop = threading.Event()

        def loop(stop=self._stop):
            while not stop.is_set():
                try:
                    self.c.get(f"/{SLUG}/api/agent/poll", params={"timeout": 2}, timeout=10)
                except httpx.HTTPError:
                    time.sleep(0.2)
        threading.Thread(target=loop, daemon=True).start()

    def drop(self):
        if self._stop:
            self._stop.set()
            time.sleep(2.2)          # let the poll in flight end


def err(r: httpx.Response) -> str:
    try:
        return r.json().get("error", "")
    except ValueError:
        return ""


# --------------------------------------------------------------------------------------------- sign-in and joining

def test_the_test_sign_in_exists_only_in_test_mode(tmp_path):
    (tmp_path / "config.json").write_text(json.dumps({"public_url": "http://127.0.0.1:1", "github_client_id": "x",
                                                      "github_client_secret": "y"}))
    real = Server(tmp_path, test_mode=False)
    real.start()
    try:
        assert httpx.post(real.url + "/test/login", json={"github_login": "mallory"}).status_code == 404
        assert httpx.get(real.url + "/api/me").status_code == 401
    finally:
        real.stop()


def test_the_owner_is_the_account_the_project_was_created_for(srv, alice):
    assert alice.get("/api/me").json()["person"]["github_login"] == "alice"
    m = members(alice)
    assert m["project"] == {"name": "Test Lab", "slug": SLUG, "repo": REPO}
    me = next(p for p in m["people"] if p["name"] == "alice")
    assert "owner" in me["groups"]
    assert {g["name"]: g["kind"] for g in m["groups"]}.items() >= {"owner": "default", "human": "default", "ai": "default",
                                                                  "alice-agents": "ownership"}.items()


def test_project_content_is_for_members_only(srv, alice):
    assert err(httpx.get(f"{srv.url}/{SLUG}/api/members")) == "not_signed_in"
    stranger = browser(srv, "carol")
    assert stranger.get(f"/{SLUG}/api/members").status_code == 403


def test_an_invitation_names_a_person_and_works_once(srv, alice):
    path = invite(alice, "bob")
    carol = browser(srv, "carol")
    r = carol.post(path)
    assert r.status_code == 403, "an invitation for bob must refuse carol: " + r.text
    bob = browser(srv, "bob")
    r = bob.post(path)
    assert r.status_code == 200 and r.json()["project"] == SLUG, r.text
    assert browser(srv, "dave").post(path).status_code == 410, "a used invitation is gone"
    m = members(bob)
    row = next(p for p in m["people"] if p["name"] == "bob")
    assert "human" in row["groups"] and "owner" not in row["groups"]
    assert any(g["name"] == "bob-agents" and g["kind"] == "ownership" for g in m["groups"])


def test_inviting_needs_the_permission(srv, bob):
    assert bob.post(f"/{SLUG}/api/invites", json={}).status_code == 403


# --------------------------------------------------------------------------------------------- authorising a local agent

def test_a_helper_gets_a_credential_only_after_its_person_approves(srv, alice):
    d = device_start(srv, computer="alice-laptop")
    assert d["user_code"] in d["verification_uri_complete"] and d["verification_uri_complete"].startswith(srv.url)
    assert err(device_token(srv, d)) == "authorization_pending"
    page = httpx.get(d["verification_uri_complete"], follow_redirects=False)
    assert page.status_code in (301, 302, 303, 307) and "/login" in page.headers["location"], "sign in first"
    seen = alice.get(f"/{SLUG}/api/device/{d['user_code']}").json()
    assert (seen["computer"], seen["kind"], seen["status"]) == ("alice-laptop", "claude-code", "pending")
    assert browser(srv, "carol").post(f"/{SLUG}/api/device/{d['user_code']}", json={"decision": "approve"}).status_code == 403
    assert err(device_token(srv, d)) == "authorization_pending", "a non-member's approval counts for nothing"
    assert alice.post(f"/{SLUG}/api/device/{d['user_code']}", json={"decision": "approve"}).status_code == 200
    r = device_token(srv, d)
    assert r.status_code == 200 and r.json()["person"] == "alice" and r.json()["credential"], r.text
    SECRETS.append(r.json()["credential"])
    assert device_token(srv, d).status_code == 400, "the credential is handed over once"


def test_a_denied_or_expired_request_yields_nothing(srv, bob):
    d = device_start(srv, computer="bob-pc")
    assert bob.post(f"/{SLUG}/api/device/{d['user_code']}", json={"decision": "deny"}).status_code == 200
    assert err(device_token(srv, d)) == "access_denied"
    d = device_start(srv, computer="bob-pc")
    time.sleep(DEVICE_TTL_S + 1.5)
    assert err(device_token(srv, d)) == "expired_token"
    assert bob.post(f"/{SLUG}/api/device/{d['user_code']}", json={"decision": "approve"}).status_code != 200


# --------------------------------------------------------------------------------------------- registering

@pytest.fixture(scope="module")
def cred_a(srv, alice):
    return authorise(srv, alice, computer="pc-1")


@pytest.fixture(scope="module")
def cred_b(srv, bob):
    return authorise(srv, bob, computer="bob-pc")


def test_a_session_registers_as_an_agent_of_its_person(srv, alice, cred_a):
    a = Agent(srv, cred_a, "s-a1")
    w = a.whoami().json()
    assert w["registered"] is False and w["project"]["repo"] == REPO and any(p["name"] == "alice" for p in w["people"])
    r = a.register("fern")
    assert r.status_code == 200 and (r.json()["agent"], r.json()["owner"], r.json()["how"]) == ("fern", "alice", "new"), r.text
    row = agent_row(alice, "fern")
    assert row["owner"] == "alice" and row["kind"] == "claude-code" and {"ai", "alice-agents"} <= set(row["groups"])
    w = a.whoami().json()
    assert w["registered"] is True and w["agent"] == "fern" and w["owner"] == "alice"
    assert a.register("fern").json()["how"] == "same"
    assert a.register("moss").status_code == 409, "one session is one agent; it must leave first"
    my = alice.get(f"/{SLUG}/api/my").json()
    assert my["switches"] == {"others_mention": False, "others_channel": False, "others_assign": False, "others_regroup": False}
    assert any(a_["name"] == "fern" for a_ in my["agents"]) and any(c["kind"] == "computer" for c in my["credentials"])


def test_names_belong_to_their_owner_and_are_unique_across_kinds(srv, cred_b):
    b = Agent(srv, cred_b, "s-b1", client="codex")
    for taken in ("fern", "alice", "human", "alice-agents"):
        assert b.register(taken).status_code == 409, taken
    assert b.register("two words").status_code in (400, 409, 422)
    r = b.register("birch")
    assert r.status_code == 200 and r.json()["owner"] == "bob", r.text


def test_presence_takeover_and_binding_generation(srv, alice, cred_a):
    s1, s2, s3 = (Agent(srv, cred_a, sid) for sid in ("s-p1", "s-p2", "s-p3"))
    gen = s1.register("pine").json()["generation"]
    s1.hold()
    assert until(lambda: online(alice, "pine")), "an open poll of a registered session is online"
    assert s2.register("pine").status_code == 409, "the name is held by a session that is online"
    assert s2.register("pine", takeover=True).status_code == 409, "even with takeover"
    s1.drop()
    assert until(lambda: not online(alice, "pine"), OFFLINE_S + 4), "no connection for the offline window is offline"
    s1.hold()
    assert until(lambda: online(alice, "pine")) and s1.whoami().json()["registered"] is True, "same session: no new registration"
    s1.drop()
    assert until(lambda: not online(alice, "pine"), OFFLINE_S + 4)
    r = s2.register("pine")
    assert r.status_code == 409 and "takeover" in r.json()["message"], "it must be told how to take over: " + r.text
    r = s2.register("pine", takeover=True)
    assert r.status_code == 200 and r.json()["how"] == "taken_over" and r.json()["generation"] == gen + 1, r.text
    assert err(s1.whoami()) == "superseded" and err(s1.register("pine")) == "superseded", "the old session is fenced off"
    assert agent_row(alice, "pine")["generation"] == gen + 1
    s2.hold()
    assert until(lambda: online(alice, "pine"))
    assert s2.leave().status_code == 200
    assert not online(alice, "pine"), "leaving is offline at once"
    s2.drop()
    assert agent_row(alice, "pine") is not None, "the name stays"
    assert s2.whoami().json()["registered"] is False, "a session that left is simply unregistered"
    r = s3.register("pine")
    assert r.status_code == 200 and r.json()["how"] == "bound", "nobody holds it now: " + r.text


# --------------------------------------------------------------------------------------------- groups and permissions

def test_an_agent_never_manages_and_groups_follow_the_owner(srv, alice, bob, cred_a, cred_b):
    as_agent = httpx.Client(base_url=srv.url, headers={"Authorization": "Bearer " + cred_a, "X-Asterism-Session": "s-a1"})
    assert as_agent.post(f"/{SLUG}/api/invites", json={}).status_code in (401, 403)
    assert alice.post(f"/{SLUG}/api/groups", json={"name": "stewards", "permissions": ["read", "manage_members"]}).status_code == 201
    assert bob.post(f"/{SLUG}/api/groups", json={"name": "rogues", "permissions": ["read"]}).status_code == 403
    # the owner may give her own agent any group she holds; it still cannot manage
    assert alice.post(f"/{SLUG}/api/members/fern/groups", json={"add": ["owner"], "remove": []}).status_code == 200
    assert "owner" in agent_row(alice, "fern")["groups"]
    assert as_agent.post(f"/{SLUG}/api/invites", json={}).status_code in (401, 403), "an agent never gets management permissions"
    assert as_agent.post(f"/{SLUG}/api/members/bob/remove").status_code in (401, 403)
    # a person gives an agent only groups the person holds
    assert bob.post(f"/{SLUG}/api/members/birch/groups", json={"add": ["owner"], "remove": []}).status_code == 403
    assert bob.post(f"/{SLUG}/api/members/birch/groups", json={"add": ["stewards"], "remove": []}).status_code == 403
    # someone else, even with the permission, needs the owner's switch
    assert alice.post(f"/{SLUG}/api/members/birch/groups", json={"add": ["stewards"], "remove": []}).status_code == 403
    r = bob.post(f"/{SLUG}/api/my/switches", json={"others_regroup": True})
    assert r.status_code == 200 and r.json()["switches"]["others_regroup"] is True and r.json()["switches"]["others_mention"] is False
    assert alice.post(f"/{SLUG}/api/members/birch/groups", json={"add": ["stewards"], "remove": []}).status_code == 200
    assert "stewards" in agent_row(bob, "birch")["groups"]
    assert bob.post(f"/{SLUG}/api/my/switches", json={"others_regroup": False}).status_code == 200
    assert alice.post(f"/{SLUG}/api/members/birch/groups", json={"add": [], "remove": ["stewards"]}).status_code == 403
    # nobody but the owner edits an ownership group
    assert alice.post(f"/{SLUG}/api/members/fern/groups", json={"add": ["bob-agents"], "remove": []}).status_code in (400, 403, 409)


def test_revoking_one_credential_leaves_the_others(srv, alice, cred_a):
    second = authorise(srv, alice, computer="pc-2")
    other = Agent(srv, second, "s-r1")
    assert other.register("reed").status_code == 200
    creds = alice.get(f"/{SLUG}/api/my").json()["credentials"]
    target = next(c for c in creds if c["label"] == "pc-2")
    assert alice.post(f"/{SLUG}/api/my/credentials/{target['id']}/revoke").status_code == 200
    assert err(other.whoami()) == "invalid_credential"
    assert Agent(srv, cred_a, "s-a1").whoami().json()["agent"] == "fern"
    assert not online(alice, "reed")


def test_removing_a_person_removes_what_was_theirs(srv, alice, bob):
    dave = browser(srv, "dave")
    assert dave.post(invite(alice, "dave")).status_code == 200
    cred = authorise(srv, dave, computer="dave-pc")
    d = Agent(srv, cred, "s-d1")
    assert d.register("dove").status_code == 200
    assert bob.post(f"/{SLUG}/api/members/dave/remove").status_code == 403, "removing people needs the permission"
    assert alice.post(f"/{SLUG}/api/members/dave/remove").status_code == 200
    m = members(alice)
    assert not any(p["name"] == "dave" for p in m["people"]) and not any(a["name"] == "dove" for a in m["agents"])
    assert err(d.whoami()) == "invalid_credential"
    assert dave.get(f"/{SLUG}/api/members").status_code == 403


def test_a_restart_loses_nothing(srv, alice, cred_a):
    before = members(alice)
    srv.stop()
    srv.start()
    assert alice.get("/api/me").status_code == 200, "people stay signed in"
    after = members(alice)
    assert [a["name"] for a in after["agents"]] == [a["name"] for a in before["agents"]]
    assert {a["name"]: a["generation"] for a in after["agents"]} == {a["name"]: a["generation"] for a in before["agents"]}
    assert Agent(srv, cred_a, "s-a1").whoami().json()["agent"] == "fern", "a session need not register again"


# --------------------------------------------------------------------------------------------- the ChatGPT connector

def rpc(srv, method, params=None, token=None, session=None) -> httpx.Response:
    h = {"Accept": "application/json, text/event-stream"}
    if token:
        h["Authorization"] = "Bearer " + token
    if session:
        h["x-openai-session"] = session
    return httpx.post(f"{srv.url}/{SLUG}/mcp", headers=h, timeout=30,
                      json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}})


def tool(srv, tool_name, token, session, **args):
    r = rpc(srv, "tools/call", {"name": tool_name, "arguments": args}, token, session)
    assert r.status_code == 200, r.text
    res = r.json()["result"]
    text = res["content"][0]["text"]
    return (text if res.get("isError") else json.loads(text)), bool(res.get("isError"))


def test_a_connector_is_approved_by_a_signed_in_member(srv, alice):
    mcp_url = f"{srv.url}/{SLUG}/mcp"
    r = rpc(srv, "tools/list")
    hint = r.headers.get("www-authenticate", "")
    assert r.status_code == 401 and hint.startswith("Bearer") and 'resource_metadata="' in hint
    prm = httpx.get(hint.split('resource_metadata="')[1].split('"')[0]).json()
    assert prm["resource"] == mcp_url and prm["authorization_servers"] == [srv.url], "the issuer has no path"
    assert httpx.get(f"{srv.url}/.well-known/oauth-protected-resource/{SLUG}/mcp").json()["resource"] == mcp_url
    asm = httpx.get(srv.url + "/.well-known/oauth-authorization-server").json()
    assert asm["issuer"] == srv.url and "S256" in asm["code_challenge_methods_supported"]
    assert asm["authorization_response_iss_parameter_supported"] is True
    r = httpx.post(asm["registration_endpoint"], json={"redirect_uris": [REDIRECT], "client_name": "ChatGPT",
                                                       "token_endpoint_auth_method": "none"})
    assert r.status_code in (200, 201), r.text
    cid = r.json()["client_id"]
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    q = {"response_type": "code", "client_id": cid, "redirect_uri": REDIRECT, "state": "st-1",
         "code_challenge": challenge, "code_challenge_method": "S256", "resource": mcp_url}
    r = httpx.get(asm["authorization_endpoint"], params=q, follow_redirects=False)
    assert r.status_code in (301, 302, 303, 307) and "/login" in r.headers["location"], "sign in first"
    page = alice.get(asm["authorization_endpoint"], params=q)
    assert page.status_code == 200 and "<form" in page.text

    def decide(person, decision="approve", **change):
        r = person.post(asm["authorization_endpoint"], data=dict(q, decision=decision, **change))
        loc = r.headers.get("location", "")
        return r, loc, dict(urllib.parse.parse_qsl(urllib.parse.urlparse(loc).query))

    r, loc, back = decide(browser(srv, "carol"))
    assert not back.get("code"), "someone who is not a member of the project approves nothing"
    r, loc, back = decide(alice, "deny")
    assert not back.get("code") and (not loc or loc.startswith(REDIRECT))
    r, loc, back = decide(alice, redirect_uri="https://example.org/steal")
    assert not loc.startswith("https://example.org"), "an unregistered return address is refused, not followed"
    r, loc, back = decide(alice)
    assert r.status_code in (302, 303) and loc.startswith(REDIRECT) and back["state"] == "st-1" and back["iss"] == srv.url, loc
    SECRETS.append(back["code"])
    ex = {"grant_type": "authorization_code", "redirect_uri": REDIRECT, "client_id": cid, "resource": mcp_url}
    assert httpx.post(asm["token_endpoint"], data=dict(ex, code=back["code"], code_verifier="x" * 50)).status_code >= 400
    r, loc, back = decide(alice)
    SECRETS.append(back["code"])
    r = httpx.post(asm["token_endpoint"], data=dict(ex, code=back["code"], code_verifier=verifier))
    assert r.status_code == 200 and r.json()["token_type"].lower() == "bearer" and r.json()["refresh_token"], r.text
    tok = r.json()
    issued = time.time()
    SECRETS.extend([tok["access_token"], tok["refresh_token"]])
    assert httpx.post(asm["token_endpoint"], data=dict(ex, code=back["code"], code_verifier=verifier)).status_code >= 400

    assert rpc(srv, "tools/list", token="not-a-token").status_code == 401
    who, bad = tool(srv, "whoami", tok["access_token"], "conv-1")
    assert not bad and who["registered"] is False
    one, bad = tool(srv, "register", tok["access_token"], "conv-1", name="dot-a")
    assert not bad and one["owner"] == "alice", one
    two, bad = tool(srv, "register", tok["access_token"], "conv-2", name="dot-b")
    assert not bad and two["owner"] == "alice", two
    msg, bad = tool(srv, "register", tok["access_token"], "conv-3", name="birch")
    assert bad and isinstance(msg, str), "another person's agent name is refused in words an agent can act on"
    assert tool(srv, "whoami", tok["access_token"], "conv-1")[0]["agent"] == "dot-a"
    assert tool(srv, "whoami", tok["access_token"], "conv-2")[0]["agent"] == "dot-b"
    assert agent_row(alice, "dot-a")["kind"] == "chatgpt"
    assert any(c["kind"] == "connector" for c in alice.get(f"/{SLUG}/api/my").json()["credentials"])

    time.sleep(max(0.0, ACCESS_TTL_S + 1.5 - (time.time() - issued)))
    assert rpc(srv, "tools/list", token=tok["access_token"]).status_code == 401, "access tokens expire"
    fresh = {"grant_type": "refresh_token", "refresh_token": tok["refresh_token"], "client_id": cid, "resource": mcp_url}
    r = httpx.post(asm["token_endpoint"], data=fresh)
    assert r.status_code == 200, r.text
    SECRETS.extend([r.json()["access_token"], r.json()["refresh_token"]])
    assert tool(srv, "whoami", r.json()["access_token"], "conv-1")[0]["agent"] == "dot-a", "the same person, the same agent"
    assert httpx.post(asm["token_endpoint"], data=fresh).status_code >= 400, "a refresh token is used once"


# --------------------------------------------------------------------------------------------- the real helper

class Stdio:
    """The helper as an agent runs it: an MCP server on stdio, newline-delimited JSON-RPC."""

    def __init__(self, script, project_url, home, cwd, client_name="claude-code", **env):
        self.p = subprocess.Popen([PY, str(script), "--project", project_url], cwd=str(cwd), text=True, encoding="utf-8",
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  env=dict(ENV, ASTERISM_HOME=str(home), **env))
        self.q, self.n = queue.Queue(), 0
        threading.Thread(target=self._read, daemon=True).start()
        self.rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                "clientInfo": {"name": client_name, "version": "0"}})
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self.rpc("tools/list")

    def _read(self):
        for line in self.p.stdout:
            try:
                self.q.put(json.loads(line))
            except ValueError:
                pass

    def _send(self, msg):
        self.p.stdin.write(json.dumps(msg) + "\n")
        self.p.stdin.flush()

    def rpc(self, method, params=None, timeout=30):
        self.n += 1
        self._send({"jsonrpc": "2.0", "id": self.n, "method": method, "params": params or {}})
        end = time.time() + timeout
        while time.time() < end:
            try:
                m = self.q.get(timeout=0.5)
            except queue.Empty:
                continue
            if m.get("id") == self.n:
                return m
        raise AssertionError(f"the helper did not answer {method}: " + self.p.stderr.read()[-500:] if self.p.poll() is not None else method)

    def tool(self, tool_name, meta=None, **args):
        params = {"name": tool_name, "arguments": args, **({"_meta": meta} if meta else {})}
        res = self.rpc("tools/call", params)["result"]
        text = res["content"][0]["text"]
        return (text if res.get("isError") else json.loads(text)), bool(res.get("isError"))

    def kill(self):
        self.p.kill()
        self.p.wait(10)


@pytest.fixture(scope="module")
def installed(srv, alice, tmp_path_factory):
    """The helper downloaded from the server and joined on a computer of alice's."""
    box = tmp_path_factory.mktemp("box")
    script, home = box / "asterism_helper.py", box / "home"
    r = httpx.get(srv.url + "/helper.py")
    assert r.status_code == 200
    script.write_bytes(r.content)
    p = subprocess.Popen([PY, str(script), "--join", f"{srv.url}/{SLUG}", "--client", "none"], cwd=str(box), text=True,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=dict(ENV, ASTERISM_HOME=str(home)))
    line = ""
    for _ in range(30):                      # it may say other things first
        line = p.stdout.readline()
        if not line or line.startswith("Open this address to approve: "):
            break
    assert line.startswith("Open this address to approve: "), line
    link = line.split(": ", 1)[1].strip()
    code = urllib.parse.parse_qs(urllib.parse.urlparse(link).query)["code"][0]
    assert alice.post(f"/{SLUG}/api/device/{code}", json={"decision": "approve"}).status_code == 200
    rest = p.communicate(timeout=30)[0]
    assert p.returncode == 0, rest
    creds = _credentials_in(home)
    assert creds and not any(c in line + rest for c in creds), "the credential is stored, and not printed"
    return script, home, box


def _credentials_in(home):
    """The `credential` fields of the helper's JSON state files."""
    found = []
    def walk(v):
        if isinstance(v, dict):
            found.extend(x for k, x in v.items() if k == "credential" and isinstance(x, str))
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
    for f in home.rglob("*.json"):
        walk(json.loads(f.read_text(encoding="utf-8")))
    SECRETS.extend(found)
    return found


def test_the_helper_joins_once_per_computer_and_carries_a_session(srv, alice, installed):
    script, home, box = installed
    again = subprocess.run([PY, str(script), "--join", f"{srv.url}/{SLUG}", "--client", "none"], cwd=str(box), text=True,
                           capture_output=True, env=dict(ENV, ASTERISM_HOME=str(home)), timeout=30)
    assert again.returncode == 0 and "Open this address" not in again.stdout, "a second agent on this computer needs no approval"
    h = Stdio(script, f"{srv.url}/{SLUG}", home, box, ASTERISM_SESSION="s-h1")
    try:
        who, bad = h.tool("whoami")
        assert not bad and who["registered"] is False
        got, bad = h.tool("register", name="holly")
        assert not bad and got["owner"] == "alice", got
        assert until(lambda: online(alice, "holly")), "the helper keeps the connection that makes its agent online"
        msg, bad = h.tool("register", name="alice")
        assert bad and isinstance(msg, str)
    finally:
        h.kill()
    assert until(lambda: not online(alice, "holly"), OFFLINE_S + 5), "the session is gone, the agent is offline"


def test_a_restarted_helper_keeps_its_codex_session(srv, alice, installed):
    script, home, box = installed
    work = box / "codex-work"
    work.mkdir()
    first = Stdio(script, f"{srv.url}/{SLUG}", home, work, client_name="codex-mcp-client")
    got, bad = first.tool("register", meta={"sessionId": "thread-9"}, name="cedar")
    assert not bad and got["agent"] == "cedar", got
    assert until(lambda: online(alice, "cedar"))
    first.kill()
    second = Stdio(script, f"{srv.url}/{SLUG}", home, work, client_name="codex-mcp-client")     # no tool call is made
    try:
        time.sleep(OFFLINE_S + 3)
        assert online(alice, "cedar"), "restarted by the same parent in the same folder: the session carries on"
        who, bad = second.tool("whoami", meta={"sessionId": "thread-9"})
        assert not bad and who["agent"] == "cedar"
    finally:
        second.kill()


# --------------------------------------------------------------------------------------------- storage

def test_no_secret_is_stored_in_clear(srv):
    assert len(SECRETS) > 10
    srv.stop()                      # let the databases settle on disk
    try:
        blob = b"".join(f.read_bytes() for f in srv.data.rglob("*") if f.is_file())
    finally:
        srv.start()
    leaked = [s[:6] + "..." for s in set(SECRETS) if len(s) >= 12 and s.encode() in blob]
    assert not leaked, f"{len(leaked)} secret(s) are stored or logged in clear"
