"""Slice 1k: a closed Claude Code session is reopened to deliver. The resident program remembers how a session that
holds an agent is reopened, keeps reporting it while its record exists, and for a delivery reads which sessions run
(`claude agents --json`), reopens the session (`claude --bg --resume <id>`, nothing else), waits for its tool
process and writes the frame to its channel. `claude` is a stand-in laid out as npm installs it.

    python -m pytest tests/test_m1k.py -q
"""
from __future__ import annotations

import json
import os
import shutil
import time
import uuid
from pathlib import Path

import pytest

from test_m1b import Channel, build_world, frame, mention, until
from test_m1j2 import CLEAN, ENV2, OFFLINE_S, REDELIVER_S, WIN, Mcp, exe, home, join, logged, row, run  # noqa: F401  (fixtures)

pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="the stand-in claude is laid out as npm installs it and needs node")

# What the stand-in does: every call is written down (its arguments and CLAUDE_CONFIG_DIR); `agents --json` prints
# active.json (or []); `--bg --resume <id>` answers as mode.txt says: ok (the session's own short id), fail (not
# trusted, exit 1) or copy (another id, with the product's note).
CLI_JS = r'''
const fs = require("fs"), path = require("path");
const dir = path.resolve(__dirname, "../../..");
const a = process.argv.slice(2);
const f = path.join(dir, "calls.json");
const all = fs.existsSync(f) ? JSON.parse(fs.readFileSync(f, "utf8")) : [];
all.push({argv: a, config: process.env.CLAUDE_CONFIG_DIR || null});
fs.writeFileSync(f, JSON.stringify(all));
const read = (name, otherwise) => fs.existsSync(path.join(dir, name)) ? fs.readFileSync(path.join(dir, name), "utf8").trim() : otherwise;
if (a[0] === "agents") { process.stdout.write(read("active.json", "[]")); process.exit(0); }
if (a[0] === "--bg" && a[1] === "--resume") {
  const mode = read("mode.txt", "ok");
  if (mode === "fail") { process.stderr.write("Workspace not trusted. Run `claude` in this folder once and accept the trust prompt, then retry.\n"); process.exit(1); }
  if (mode === "copy") {
    process.stdout.write("backgrounded \u00b7 0badc0de (idle \u00b7 send a prompt to start)\n");
    process.stderr.write("note: session " + a[2].slice(0, 8) + " is already running in the background, so this started a copy as 0badc0de.\n");
    process.exit(0);
  }
  process.stdout.write("backgrounded \u00b7 " + a[2].slice(0, 8) + " (idle \u00b7 send a prompt to start)\n");
  process.exit(0);
}
process.exit(0);
'''


@pytest.fixture(scope="module")
def v(tmp_path_factory):
    world = build_world(tmp_path_factory.mktemp("datak"), ENV2)
    yield world
    world.srv.stop()


class Stand:
    """The stand-in claude on a PATH of its own, a configuration folder, and one session's record in it."""

    def __init__(self, tmp_path: Path, record=True):
        self.fake, self.cfg, self.session = tmp_path / "bin", tmp_path / "claude_cfg", str(uuid.uuid4())
        js = self.fake / "node_modules" / "@anthropic-ai" / "claude-code"
        js.mkdir(parents=True)
        (js / "cli.js").write_text(CLI_JS, encoding="utf-8")
        sh = '#!/bin/sh\nexec node "$(dirname "$0")/node_modules/@anthropic-ai/claude-code/cli.js" "$@"\n'
        if WIN:
            (self.fake / "claude").write_text(sh, encoding="ascii")
            (self.fake / "claude.cmd").write_text('@node "%~dp0node_modules\\@anthropic-ai\\claude-code\\cli.js" %*\n', encoding="ascii")
        else:
            (self.fake / "claude").write_text(sh)
            (self.fake / "claude").chmod(0o755)
        self.record = self.cfg / "projects" / "D--work" / f"{self.session}.jsonl"
        self.record.parent.mkdir(parents=True)
        if record:
            self.record.write_text('{"type":"user","cwd":"D:\\\\work","sessionId":"%s"}\n' % self.session, encoding="utf-8")
        self.env = {"PATH": str(self.fake) + os.pathsep + CLEAN.get("PATH", ""), "CLAUDE_CONFIG_DIR": str(self.cfg)}
        self.channels = 0

    def calls(self) -> list[dict]:
        try:
            return json.loads((self.fake / "calls.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []

    def reopened(self) -> list[dict]:
        return [c for c in self.calls() if c["argv"][:1] == ["--bg"]]

    def mcp(self, exe, home, token="tok-k"):
        """The session's tool process, as Claude Code starts it with the session: (the process, its channel)."""
        self.channels += 1
        folder = self.cfg / f"channel{self.channels}"       # a channel of its own each time the session starts
        folder.mkdir()
        ch = Channel(folder)
        m = Mcp(exe, home, CLAUDE_CODE_SESSION_ID=self.session, CLAUDE_CODE_MESSAGING_SOCKET=ch.address,
                CLAUDE_CODE_MESSAGING_TOKEN=token, **self.env)
        return m, ch

    def close_after_registering(self, exe, home, v, name):
        """A session that registered `name` and was closed: its tool process is gone, the agent is still online."""
        m, _ = self.mcp(exe, home)
        try:
            got, bad = m.tool("register", name=name)
            assert not bad, got
            assert until(lambda: v.alice.is_online(name), 8)
        finally:
            m.kill()
        time.sleep(OFFLINE_S + 1.5)


def test_a_closed_session_is_reopened_and_the_message_goes_through_its_channel(exe, v, home, tmp_path):
    st = Stand(tmp_path)
    join(exe, home, v, "--client", "none", **st.env)
    st.close_after_registering(exe, home, v, "kira")
    assert v.alice.is_online("kira"), "closed, but it can be reopened: still reachable"
    assert not st.reopened(), "nothing is reopened before there is something to deliver"
    rc, out = run(exe, home, "status", **st.env)
    assert rc == 0 and st.session in out, "status lists the closed session: " + out

    text = "@kira wake up [k1]"
    sent = v.alice.say(text)
    assert mention(sent, "kira")["result"] == "woken"
    calls = until(st.reopened, 15)
    assert calls and calls[0]["argv"] == ["--bg", "--resume", st.session], "the session's id and nothing else"
    assert calls[0]["config"] == str(st.cfg), "with the session's own configuration folder"
    argvs = [c["argv"] for c in st.calls()]
    assert ["agents", "--json"] in argvs[:argvs.index(calls[0]["argv"])], "which sessions run is read first"
    m, ch = st.mcp(exe, home, token="tok-k2")                # Claude Code starts the session's tool process again
    try:
        shown = until(lambda: ch.users("[k1]"), 20)
        assert shown and shown[0] == frame({"id": sent["id"], "in": "#general", "from": "alice", "relation": "your own user",
                                            "level": "important", "text": text})
        assert until(lambda: logged(v, "delivered", message=sent["id"], to="kira"), 8)
        again = v.alice.say("@kira and again [k2]")
        assert until(lambda: ch.users("[k2]"), 10), "open now: through the channel"
        assert len(st.reopened()) == 1, "and not reopened a second time"
        assert not m.tool("send", text="here [k2a]", reply_to=again["id"])[1]
        assert not m.tool("send", text="and here [k1a]", reply_to=sent["id"])[1]
    finally:
        m.kill()


def test_a_session_that_runs_already_is_not_reopened(exe, v, home, tmp_path):
    st = Stand(tmp_path)
    join(exe, home, v, "--client", "none", **st.env)
    st.close_after_registering(exe, home, v, "kuno")
    (st.fake / "active.json").write_text(json.dumps([{"pid": 1, "id": st.session[:8], "kind": "background",
                                                       "sessionId": st.session, "status": "idle", "state": "done"}]))
    sent = v.alice.say("@kuno are you there? [k3]")
    assert until(lambda: ["agents", "--json"] in [c["argv"] for c in st.calls()], 15)
    time.sleep(2.0)
    assert not st.reopened(), "it runs: reopening would start a copy"
    m, ch = st.mcp(exe, home)                                # its tool process connects a moment later
    try:
        assert until(lambda: ch.users("[k3]"), 20), "and the message goes through its channel"
        assert not st.reopened()
        assert not m.tool("send", text="yes [k3a]", reply_to=sent["id"])[1]
    finally:
        m.kill()


def test_a_reopening_that_fails_is_a_failed_handshake(exe, v, home, tmp_path):
    st = Stand(tmp_path)
    join(exe, home, v, "--client", "none", **st.env)
    st.close_after_registering(exe, home, v, "kato")
    (st.fake / "mode.txt").write_text("fail")
    lost = v.alice.say("@kato hello? [k4]")
    assert until(st.reopened, 15), "it was tried"
    assert until(lambda: not v.alice.is_online("kato"), REDELIVER_S * 3 + 40), "not acknowledged twice: offline"
    assert logged(v, "agent_offline", agent="kato", reason="unanswered")
    assert not logged(v, "delivered", message=lost["id"], to="kato")
    (st.fake / "mode.txt").write_text("ok")
    tried = len(st.reopened())
    later = v.alice.say("@kato and now? [k5]")
    assert until(lambda: len(st.reopened()) > tried, 20), "offline does not stop delivery (1o): it is tried again"
    m, ch = st.mcp(exe, home)
    try:
        assert until(lambda: ch.users("[k5]"), 20)
        assert until(lambda: v.alice.is_online("kato"), 8), "the handshake that succeeds brings it back"
        assert not m.tool("send", text="here [k5a]", reply_to=later["id"])[1]
        assert not m.tool("send", text="and that [k4a]", reply_to=lost["id"])[1]
    finally:
        m.kill()


def test_a_copy_is_stopped_and_removed_and_nothing_is_acknowledged(exe, v, home, tmp_path):
    st = Stand(tmp_path)
    join(exe, home, v, "--client", "none", **st.env)
    st.close_after_registering(exe, home, v, "kopi")
    (st.fake / "mode.txt").write_text("copy")
    sent = v.alice.say("@kopi hello [k6]")
    assert until(st.reopened, 15)
    def tidied():
        return [c["argv"] for c in st.calls() if c["argv"][:1] in (["stop"], ["rm"])]
    assert until(lambda: tidied() == [["stop", "0badc0de"], ["rm", "0badc0de"]], 20), tidied()
    time.sleep(1.5)
    assert not logged(v, "delivered", message=sent["id"], to="kopi"), "a copy is not the session: nothing was delivered"


def test_a_session_whose_record_is_gone_is_closed_as_before(exe, v, home, tmp_path):
    st = Stand(tmp_path)
    join(exe, home, v, "--client", "none", **st.env)
    st.close_after_registering(exe, home, v, "kali")
    assert v.alice.is_online("kali")
    st.record.unlink()
    assert until(lambda: row(v, "kali")["offline_because"] == "session_closed", 90), "nothing to reopen: closed"
    sent = v.alice.say("@kali anyone? [k7]")
    assert mention(sent, "kali")["result"] == "offline"
    time.sleep(2.0)
    assert not st.reopened()
