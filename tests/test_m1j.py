"""Acceptance checks for the joining flow, step j1: what the server offers before the resident program exists.

Black box, same harness as test_m1b.py, with a server of its own (short-lived invitation links). The tests play
the resident program's part over HTTP: redeeming a link, reporting sessions, holding the computer's connection.

    python -m pytest tests/test_m1j.py -x -q
"""
import hashlib
import html
import json
import threading
import time

import httpx
import pytest

from test_m1b import ENV, SLUG, Agent, Person, build_world, connector_token, mention, remote_tool, until

INVITE_TTL_S, OFFLINE_S, REDELIVER_S, NOTICE_GRACE_S = 5, 3, 2, 3
ENVJ = dict(ENV, ASTERISM_AGENT_INVITE_TTL_S=str(INVITE_TTL_S), ASTERISM_OFFLINE_AFTER_S=str(OFFLINE_S),
            ASTERISM_REDELIVER_AFTER_S=str(REDELIVER_S), ASTERISM_NOTICE_GRACE_S=str(NOTICE_GRACE_S))

# Agent-facing wording, word for word from the specification.
INVITE_TEXT = ('You are invited to join the Asterism project "{project}" as an agent of {person}.\n'
               "Run one command, the one for this computer:\n"
               "macOS or Linux: `curl -fsSL {url}/install.sh | sh -s -- {link}`\n"
               'Windows: `powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-Command -ScriptBlock '
               '([scriptblock]::Create((irm {url}/install.ps1))) -ArgumentList {link}"`\n'
               "The command tells you what to do next.\n"
               "What it does: it installs the Asterism program in your user's home folder, adds its tools to the product "
               "you run in (an MCP server named `asterism-local`), lets you call those tools without asking your user each "
               "time (so that you can answer when you are woken while they are away), and connects this computer to the "
               "project.\n"
               "If you are not allowed to run it, show the command to your user so that they can run it themselves.")
EXPIRED = "This invitation link has expired or was already used. Ask your user for a new one."
HINT = ("You are connected through the remote connector, which cannot wake you: you will see messages only when you "
        "call messages or wait. If this session also has the Asterism tools of the local MCP server (named "
        "`asterism-local`), call its `register` with takeover=true and use those tools from now on. If it does not and "
        "you run on your user's computer, ask your user for an agent invitation link (from the \"my agents\" page of "
        "the project) and follow it.")
AGENT_LINE = ('If you are an agent: ask your user for an agent invitation link (from the "my agents" page of this '
              "project) and open it.")


@pytest.fixture(scope="module")
def j(tmp_path_factory):
    world = build_world(tmp_path_factory.mktemp("dataj"), ENVJ)
    yield world
    world.srv.stop()


def new_link(person: Person) -> str:
    r = person.c.post(f"/{SLUG}/api/my/agent-invites")
    assert r.status_code == 201, r.text
    assert 0 < r.json()["expires_in"] <= INVITE_TTL_S
    return r.json()["url"]


def redeem(url: str, computer="pc-9", product="codex", credential=None) -> httpx.Response:
    headers = {"Authorization": "Bearer " + credential} if credential else {}
    return httpx.post(url + "/redeem", json={"computer": computer, "product": product}, headers=headers, timeout=30)


def credentials(person: Person) -> list[dict]:
    return person.c.get(f"/{SLUG}/api/my").json()["credentials"]


def row(j, name) -> dict:
    return next(a for a in j.alice.members()["agents"] if a["name"] == name)


def logged(j, event: str, **fields) -> list[dict]:
    lines = (j.srv.data / "log.jsonl").read_text(encoding="utf-8").splitlines()
    out = [e for e in map(json.loads, filter(str.strip, lines)) if e.get("event") == event]
    return [e for e in out if all(e.get(k) == x for k, x in fields.items())]


# ------------------------------------------------------------------ invitation links

def test_an_invitation_link_carries_the_steps_and_the_consent(j):
    assert httpx.post(f"{j.srv.url}/{SLUG}/api/my/agent-invites").status_code == 401
    assert Person(j.srv, "dave").c.post(f"/{SLUG}/api/my/agent-invites").status_code == 403, "members only"
    url = new_link(j.alice)
    assert url.startswith(f"{j.srv.url}/{SLUG}/a/")
    code = url.rsplit("/", 1)[1]
    for _ in range(2):                                      # reading it does not use it up
        r = httpx.get(url)
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/plain"), r.text
        assert r.text == INVITE_TEXT.format(project="Test Lab", person="alice", url=j.srv.url, link=url)
    assert redeem(url, product="emacs").status_code == 400, "an unknown product is refused, the link stays"

    r = redeem(url, computer="pc-9", product="codex")
    assert r.status_code == 200, r.text
    got = r.json()
    assert got["person"] == "alice" and got["project"] == {"name": "Test Lab", "slug": SLUG} and got["credential"]
    assert redeem(url).status_code == 410, "one use"
    gone = httpx.get(url)
    assert gone.status_code == 410 and gone.text == EXPIRED

    Agent(j.srv, got["credential"], "s-j1", client="codex").register("jay")        # the credential is a computer's
    assert row(j, "jay")["kind"] == "codex" and row(j, "jay")["owner"] == "alice"
    assert any(c["label"] == "pc-9" and c["kind"] == "computer" and c["via"] == "invite" for c in credentials(j.alice))
    assert logged(j, "agent_invite_created", project=SLUG)
    assert logged(j, "agent_invite_redeemed", project=SLUG, computer="pc-9", product="codex")
    for f in j.srv.data.rglob("*"):
        if f.is_file():
            data = f.read_bytes()
            assert code.encode() not in data and got["credential"].encode() not in data, f"{f.name} holds a secret in clear"


def test_a_link_dies_by_itself_and_an_authorised_computer_gets_no_second_credential(j):
    old = new_link(j.alice)
    time.sleep(INVITE_TTL_S + 1.5)
    assert httpx.get(old).status_code == 410 and redeem(old).status_code == 410, "expired"

    before = len(credentials(j.alice))
    r = redeem(new_link(j.alice), credential=j.cred_a)
    assert r.status_code == 200 and r.json()["credential"] is None and r.json()["person"] == "alice", r.text
    assert len(credentials(j.alice)) == before, "this computer was authorised already"

    link = new_link(j.alice)
    assert redeem(link, credential=j.cred_b).status_code == 403, "another person's computer cannot take alice's link"
    assert redeem(link).status_code == 200, "and the link is still good after that"


# ------------------------------------------------------------------ one connection per computer

class Computer:
    """The resident program's part: reports which local sessions it can wake and holds the computer's connection."""

    def __init__(self, srv, credential):
        self.c = httpx.Client(base_url=srv.url, timeout=30, headers={"Authorization": "Bearer " + credential})
        self.got, self.lock, self._stop = [], threading.Lock(), None

    def report(self, *sessions):
        r = self.c.post(f"/{SLUG}/api/computer/sessions",
                        json={"sessions": [{"session": s, "product": p} for s, p in sessions]})
        assert r.status_code == 200, r.text

    def connect(self):
        self._stop = threading.Event()

        def loop(stop=self._stop):
            while not stop.is_set():
                try:
                    r = self.c.get(f"/{SLUG}/api/computer/poll", params={"timeout": 2}, timeout=10)
                    ds = r.json().get("deliveries", []) if r.status_code == 200 else []
                except (httpx.HTTPError, ValueError):
                    time.sleep(0.2)
                    continue
                if ds:
                    with self.lock:
                        self.got.extend(ds)
                    self.c.post(f"/{SLUG}/api/computer/ack", json={"deliveries": [d["delivery"] for d in ds]})
        threading.Thread(target=loop, daemon=True).start()

    def disconnect(self):
        self._stop.set()
        time.sleep(2.3)                                     # let the poll in flight end

    def tagged(self, tag) -> list[dict]:
        with self.lock:
            return [d for d in self.got if d.get("kind") == "message" and tag in d["message"]["text"]]


def test_one_connection_serves_every_agent_of_the_computer(j):
    cred = redeem(new_link(j.alice), computer="pc-10").json()["credential"]
    cora = Agent(j.srv, cred, "s-c1", client="claude-code").register("cora")
    cody = Agent(j.srv, cred, "s-c2", client="codex").register("cody")
    assert (row(j, "cora")["online"], row(j, "cora")["offline_because"]) == (False, "no_computer")

    pc = Computer(j.srv, cred)
    pc.report(("s-c1", "claude-code"), ("s-c2", "codex"))
    pc.connect()
    assert until(lambda: row(j, "cora")["online"] and row(j, "cody")["online"], 6), "the computer's connection makes them online"
    assert row(j, "cody")["offline_because"] is None
    sent = j.alice.say("@cora @cody hello both [c1]")
    assert mention(sent, "cora")["result"] == "woken" and mention(sent, "cody")["result"] == "woken"
    assert until(lambda: len(pc.tagged("[c1]")) == 2, 8), "one connection hands out both"
    ds = pc.tagged("[c1]")
    assert {(d["agent"], d["session"]) for d in ds} == {("cora", "s-c1"), ("cody", "s-c2")}
    assert all(d["frame"].startswith("<asterism-message ") and d["message"]["id"] == sent["id"] for d in ds)
    time.sleep(REDELIVER_S + 1.5)
    assert len(pc.tagged("[c1]")) == 2, "acknowledged through the computer, not handed out again"
    cora.say("hi [c1a]", reply_to=sent["id"])
    cody.say("hi [c1b]", reply_to=sent["id"])

    pc.report(("s-c1", "claude-code"))                      # the Codex conversation was closed
    assert until(lambda: row(j, "cody")["offline_because"] == "session_closed", 5)
    assert row(j, "cora")["online"]
    late = j.alice.say("@cody are you there? [c2]")
    assert mention(late, "cody")["result"] == "offline"
    time.sleep(1.5)
    for_cody = lambda: [d for d in pc.tagged("[c2]") if d["agent"] == "cody"]      # cora, who just spoke here, hears it too
    assert not for_cody(), "nothing is handed out for a session the computer cannot wake"
    pc.report(("s-c1", "claude-code"), ("s-c2", "codex"))
    assert until(lambda: row(j, "cody")["online"], 5)
    assert until(for_cody, 8), "what waited is handed out when the session is back"
    cody.say("yes [c2a]", reply_to=late["id"])

    pc.disconnect()
    assert until(lambda: not row(j, "cora")["online"] and not row(j, "cody")["online"], OFFLINE_S + 5)
    assert row(j, "cora")["offline_because"] == "no_computer"
    assert logged(j, "computer_connected", project=SLUG) and logged(j, "computer_disconnected", project=SLUG)


# ------------------------------------------------------------------ the connector's hint

def test_the_connector_says_when_it_cannot_wake_and_what_to_do(j):
    token = connector_token(j.srv, j.alice)
    out, bad = remote_tool(j.srv, "register", token, "conv-h", name="dot-h")
    assert not bad and out["hint"] == HINT, out
    who, bad = remote_tool(j.srv, "whoami", token, "conv-h")
    assert not bad and who["hint"] == HINT
    local = Agent(j.srv, j.cred_a, "s-h1")
    r = local.c.post(f"/{SLUG}/api/agent/register", json={"name": "holly-h", "takeover": False})
    assert r.status_code == 200 and "hint" not in r.json(), "a local agent can be woken: no hint"
    assert "hint" not in local.c.get(f"/{SLUG}/api/agent/whoami").json()


# ------------------------------------------------------------------ the project address and the downloads

def test_the_project_address_greets_people_and_agents(j):
    r = httpx.get(f"{j.srv.url}/{SLUG}", follow_redirects=False)
    assert r.status_code == 200 and "text/html" in r.headers["content-type"], r.status_code
    page = html.unescape(r.text)
    assert f"/login?next=/{SLUG}" in page.replace("%2F", "/") and AGENT_LINE in page
    assert "general" not in page, "nothing of the project's content is shown without a session"
    assert httpx.get(f"{j.srv.url}/nowhere", follow_redirects=False).status_code == 404
    assert "general" in j.alice.c.get(f"/{SLUG}").text
    r = httpx.get(f"{j.srv.url}/{SLUG}/members", follow_redirects=False)
    assert r.status_code in (301, 302, 303, 307) and "/login" in r.headers["location"], "other pages still ask to sign in"


def test_the_server_hands_out_the_program_it_was_given(j):
    assert httpx.get(j.srv.url + "/dl/manifest.json").json() == {"version": None, "files": {}}
    dist = j.srv.data / "dist"
    dist.mkdir()
    blob = b"not really a program\n" * 3
    (dist / "asterism-linux-x64").write_bytes(blob)
    (dist / "notes.txt").write_text("not listed, not served")
    sha = hashlib.sha256(blob).hexdigest()
    (dist / "manifest.json").write_text(json.dumps({"version": "0.0.1", "files": {
        "linux-x64": {"name": "asterism-linux-x64", "sha256": sha, "size": len(blob)}}}))
    m = httpx.get(j.srv.url + "/dl/manifest.json").json()
    assert m["version"] == "0.0.1" and m["files"]["linux-x64"] == {
        "name": "asterism-linux-x64", "sha256": sha, "size": len(blob), "url": j.srv.url + "/dl/asterism-linux-x64"}
    got = httpx.get(m["files"]["linux-x64"]["url"])
    assert got.status_code == 200 and got.content == blob and got.headers["content-type"] == "application/octet-stream"
    for name in ("notes.txt", "manifest.json.bak", "..%2Faccounts.db", "%2e%2e/accounts.db"):
        assert httpx.get(f"{j.srv.url}/dl/{name}").status_code == 404, name
    sh = httpx.get(j.srv.url + "/install.sh")
    assert sh.status_code == 200 and sh.headers["content-type"].startswith("text/plain") and j.srv.url in sh.text
    assert "sha256" in sh.text.lower() and "join" in sh.text
    ps = httpx.get(j.srv.url + "/install.ps1")
    assert ps.status_code == 200 and j.srv.url in ps.text and "join" in ps.text


# ------------------------------------------------------------------ inviting an agent from the page

SAY = 'Please join the Asterism project "{project}": open {link} and follow what it says.'
STALE = ("This computer's credential was revoked or is unknown. Ask your user for a new agent invitation link "
         '(from the "my agents" page of the project) and follow it.')


def test_an_invitation_comes_with_what_to_paste_and_what_to_run(j):
    r = j.alice.c.post(f"/{SLUG}/api/my/agent-invites")
    assert r.status_code == 201, r.text
    got = r.json()
    url, srv = got["url"], j.srv.url
    assert got["say"] == SAY.format(project="Test Lab", link=url), "the sentence a person pastes to their agent"
    assert got["commands"] == {
        "macos-linux": {"claude-code": f"curl -fsSL {srv}/install.sh | sh -s -- {url} --client claude",
                        "codex": f"curl -fsSL {srv}/install.sh | sh -s -- {url} --client codex"},
        "windows": {"claude-code": 'powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-Command -ScriptBlock '
                                   f'([scriptblock]::Create((irm {srv}/install.ps1))) -ArgumentList {url},--client,claude"',
                    "codex": 'powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-Command -ScriptBlock '
                             f'([scriptblock]::Create((irm {srv}/install.ps1))) -ArgumentList {url},--client,codex"'},
    }, "what a person runs to set a computer up themselves, per system and product"
    assert got["program"] in ({"version": None, "available": False}, {"version": "0.0.1", "available": True})


def test_the_my_agents_page_invites_agents_and_no_longer_mentions_the_helper(j):
    page = j.alice.c.get(f"/{SLUG}/my")
    assert page.status_code == 200
    text = html.unescape(page.text)
    assert 'id="invite-agent"' in page.text and 'id="invite-result"' in page.text, "a button and where its result goes"
    assert 'id="invite-consent"' in page.text, "what the person agrees to by sending a link is said next to the button"
    assert "helper.py" not in text and "--join" not in text and "asterism_helper" not in text
    my = j.alice.c.get(f"/{SLUG}/api/my").json()
    assert set(my["program"]) == {"version", "available"}
    assert all({"label", "via", "connected"} <= set(c) for c in my["credentials"] if c["kind"] == "computer"),         "each authorised computer says whether its program is connected now"


def test_a_stale_credential_is_told_to_ask_for_a_new_link(j):
    ghost = Agent(j.srv, "not-a-credential", "s-ghost")
    r = ghost.c.get(f"/{SLUG}/api/agent/whoami")
    assert r.status_code == 401 and r.json()["error"] == "invalid_credential" and r.json()["message"] == STALE
    r = httpx.get(f"{j.srv.url}/{SLUG}/api/computer/poll", params={"timeout": 1},
                  headers={"Authorization": "Bearer not-a-credential"})
    assert r.status_code == 401 and r.json()["message"] == STALE


# ------------------------------------------------------------------ a session that blinks is not announced

def system_notes(person, text: str) -> list[dict]:
    return [m for m in person.read() if m["from_kind"] == "system" and m["text"] == text]


def test_a_session_that_blinks_is_not_announced(j):
    """Seen live on 2026-11-14: a resident program dropped and re-made a session's connection every eleven
    seconds, and the channel got an "is offline." and an "is online." notice each time. A session that leaves
    its computer's list is offline at once for delivery, but nobody is told unless it stays away."""
    cred = redeem(new_link(j.alice), computer="pc-11").json()["credential"]
    Agent(j.srv, cred, "s-bl1", client="claude-code").register("blinky")
    pc = Computer(j.srv, cred)
    pc.report(("s-bl1", "claude-code"))
    pc.connect()
    assert until(lambda: row(j, "blinky")["online"], 6)
    assert until(lambda: len(system_notes(j.alice, "blinky is online.")) == 1, 5)
    offline_logged = len(logged(j, "agent_offline", agent="blinky"))

    for _ in range(4):                                      # gone for a moment, back again
        pc.report()
        assert until(lambda: row(j, "blinky")["offline_because"] == "session_closed", 3), "offline at once, for delivery"
        pc.report(("s-bl1", "claude-code"))
        assert until(lambda: row(j, "blinky")["online"], 3)
    time.sleep(NOTICE_GRACE_S + 2)
    assert system_notes(j.alice, "blinky is offline.") == [], "a blink is not announced"
    assert len(system_notes(j.alice, "blinky is online.")) == 1, "and neither is coming back from one"
    assert len(logged(j, "agent_offline", agent="blinky")) == offline_logged, "nor written down as going offline"

    pc.report()                                             # this time it stays away
    time.sleep(1.0)
    assert system_notes(j.alice, "blinky is offline.") == [], "not before the grace has passed"
    assert until(lambda: len(system_notes(j.alice, "blinky is offline.")) == 1, NOTICE_GRACE_S + 4), "then it is said, once"
    assert logged(j, "agent_offline", agent="blinky")
    pc.report(("s-bl1", "claude-code"))
    assert until(lambda: len(system_notes(j.alice, "blinky is online.")) == 2, 5), "a real return is announced at once"
    pc.disconnect()
