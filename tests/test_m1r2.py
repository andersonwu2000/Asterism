"""A write that is retried is done once, through the program: `asterism mcp` keys `send` and `task_update`, tries again
by itself when the answer is lost, and reuses the key when the agent repeats a call that failed.

A proxy between the program and the server loses answers on purpose (the request reaches the server and is done; the
connection is then closed with no answer), or stands for a server that is away (502, nothing forwarded).

    python -m pytest tests/test_m1r2.py -x -q
"""
from __future__ import annotations

import http.server
import threading

import httpx
import pytest

from test_m1b import SLUG, build_world
from test_m1j2 import ENV2, Mcp, exe, home, join, new_link, run  # noqa: F401  (fixtures)

RETRY_S = 4


class Proxy:
    """Forwards to the server. `lose` (a path suffix -> how many answers to lose) forwards and then hangs up;
    `away` answers 502 without forwarding."""

    def __init__(self, target: str):
        self.target, self.lose, self.away, self.seen = target, {}, False, []
        proxy = self

        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a):
                pass

            def _go(self):
                n = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(n) if n else None
                path = self.path.split("?")[0]
                proxy.seen.append((self.command, path, self.headers.get("Idempotency-Key")))
                if proxy.away:
                    self.send_response(502)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                headers = {k: v for k, v in self.headers.items() if k.lower() not in ("host", "content-length", "connection")}
                with httpx.Client(timeout=120) as c:
                    res = c.request(self.command, proxy.target + self.path, content=body, headers=headers)
                for suffix, left in list(proxy.lose.items()):
                    if path.endswith(suffix) and left > 0:
                        proxy.lose[suffix] = left - 1
                        self.close_connection = True
                        return                     # done on the server; the answer is lost
                self.send_response(res.status_code)
                for hk, hv in res.headers.items():
                    if hk.lower() not in ("content-length", "transfer-encoding", "connection", "content-encoding"):
                        self.send_header(hk, hv)
                self.send_header("Content-Length", str(len(res.content)))
                self.end_headers()
                self.wfile.write(res.content)

            do_GET = do_POST = do_DELETE = _go

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def keys(self, suffix: str) -> list[str | None]:
        return [key for (m, p, key) in self.seen if m == "POST" and p.endswith(suffix)]

    def stop(self):
        self.httpd.shutdown()


@pytest.fixture(scope="module")
def v(tmp_path_factory):
    world = build_world(tmp_path_factory.mktemp("datar2"), ENV2)
    world.proxy = Proxy(world.srv.url)
    yield world
    world.proxy.stop()
    world.srv.stop()


def join_through_proxy(exe, home, v):
    link = new_link(v.alice).replace(v.srv.url, v.proxy.url)
    rc, out = run(exe, home, "join", link, "--client", "none")
    assert rc == 0 and "panicked" not in out, out


def tagged(v, tag: str) -> list[dict]:
    return [m for m in v.alice.read("#general") if tag in m["text"]]


def tasks_with(v, tag: str) -> list[dict]:
    got = v.alice.c.get(f"/{SLUG}/api/tasks").json()["groups"]
    return [x for g in got for x in g["tasks"] if tag in x["text"]]


def started(exe, home, sid: str, name: str) -> Mcp:
    m = Mcp(exe, home, CLAUDE_CODE_SESSION_ID=sid, ASTERISM_RETRY_S=str(RETRY_S))
    assert not m.tool("register", name=name)[1]
    return m


def test_a_lost_answer_is_tried_again_and_the_message_is_posted_once(exe, v, home):
    join_through_proxy(exe, home, v)
    m = started(exe, home, "s-rr-1", "rory")
    try:
        v.proxy.lose["/api/agent/send"] = 1
        got, bad = m.tool("send", to="#general", text="through a cut [p1]")
        assert not bad, got
        assert len(tagged(v, "[p1]")) == 1
        keys = v.proxy.keys("/api/agent/send")[-2:]
        assert len(keys) == 2 and keys[0] and keys[0] == keys[1], f"the retry carries the same key: {keys}"
        assert 32 <= len(keys[0]) <= 64
    finally:
        m.kill()


def test_each_call_has_its_own_key_so_saying_it_twice_says_it_twice(exe, v, home):
    join_through_proxy(exe, home, v)
    m = started(exe, home, "s-rr-2", "rhea")
    try:
        for _ in range(2):
            got, bad = m.tool("send", to="#general", text="twice on purpose [p2]")
            assert not bad, got
        assert len(tagged(v, "[p2]")) == 2
        keys = v.proxy.keys("/api/agent/send")[-2:]
        assert keys[0] and keys[1] and keys[0] != keys[1]
    finally:
        m.kill()


def test_when_every_answer_is_lost_the_agent_is_told_and_its_repeat_is_not_posted_twice(exe, v, home):
    join_through_proxy(exe, home, v)
    m = started(exe, home, "s-rr-3", "remy")
    try:
        v.proxy.lose["/api/agent/send"] = 1000
        got, bad = m.tool("send", to="#general", text="answers lost [p3]")
        v.proxy.lose["/api/agent/send"] = 0
        assert bad and "cannot be reached" in got and "Try again later." in got, got
        assert len(tagged(v, "[p3]")) == 1, "it was done once, however often it was tried"
        again, bad = m.tool("send", to="#general", text="answers lost [p3]")
        assert not bad, again
        assert len(tagged(v, "[p3]")) == 1, "the agent's repeat of a failed call reuses its key"
        third, bad = m.tool("send", to="#general", text="answers lost [p3]")
        assert not bad and len(tagged(v, "[p3]")) == 2, "after a success the same call is a new message"
    finally:
        m.kill()


def test_a_server_away_for_the_whole_time_is_reported_and_nothing_is_posted(exe, v, home):
    join_through_proxy(exe, home, v)
    m = started(exe, home, "s-rr-4", "reed")
    try:
        before = len(v.proxy.keys("/api/agent/send"))
        v.proxy.away = True
        try:
            got, bad = m.tool("send", to="#general", text="nobody home [p4]")
        finally:
            v.proxy.away = False
        assert bad and "cannot be reached" in got, got
        tried = v.proxy.keys("/api/agent/send")[before:]
        assert len(tried) >= 3 and len(set(tried)) == 1 and tried[0], f"tried again with one key: {tried}"
        assert tagged(v, "[p4]") == []
        got, bad = m.tool("send", to="#general", text="nobody home [p4]")
        assert not bad and len(tagged(v, "[p4]")) == 1
    finally:
        m.kill()


def test_a_task_whose_answer_is_lost_is_made_once(exe, v, home):
    join_through_proxy(exe, home, v)
    m = started(exe, home, "s-rr-5", "ruth")
    try:
        v.proxy.lose["/api/agent/task"] = 1
        got, bad = m.tool("task_update", group="alice-agents", text="through a cut [p5]")
        assert not bad, got
        found = tasks_with(v, "[p5]")
        assert len(found) == 1
        assert v.alice.c.post(f"/{SLUG}/api/tasks/{found[0]['id']}/remove").status_code == 200
    finally:
        m.kill()


def test_reads_carry_no_key(exe, v, home):
    join_through_proxy(exe, home, v)
    m = started(exe, home, "s-rr-6", "rita")
    try:
        assert not m.tool("messages", all=True)[1]
        assert not m.tool("tasks")[1]
        reads = [key for (meth, p, key) in v.proxy.seen if meth == "GET" and "/api/agent/" in p]
        assert reads and all(key is None for key in reads)
    finally:
        m.kill()
