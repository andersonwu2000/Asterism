"""Acceptance checks for the joining flow, step j2: the program `asterism` (Rust, in program/).

Black box: the real binary is built once and run against a real server in test mode. The Claude Code message
channel and `codex` are stand-ins, as in test_m1b.py. Every test has its own state folder (ASTERISM_HOME), and
the resident program it started is stopped when the test ends.

    python -m pytest tests/test_m1j2.py -x -q
"""
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx
import pytest

from test_helper_join import fake_command
from test_m1b import (CLEAN, DESCRIPTIONS, ENV, INSTRUCTIONS, ROOT, SLUG, Channel, build_world, frame, mention, until)

OFFLINE_S, REDELIVER_S = 3, 2
ENV2 = dict(ENV, ASTERISM_OFFLINE_AFTER_S=str(OFFLINE_S), ASTERISM_REDELIVER_AFTER_S=str(REDELIVER_S))
WIN = sys.platform == "win32"
ENDING = ("This computer is set up. If you can see the Asterism tools of `asterism-local` in this conversation, call "
          "`register` now with an agent name of your choice (or the one your user gave you). If you cannot see them, "
          "this conversation started before they were added: tell your user that Asterism is installed and ask them to "
          "reopen this conversation (close it and open the same conversation again; in a terminal, resume it; in a "
          "desktop app or an IDE, restart the app and come back to this conversation), then call `register` when you "
          "are back.")


@pytest.fixture(scope="session")
def exe():
    cargo_bin = Path.home() / ".cargo" / "bin"
    env = dict(os.environ, PATH=str(cargo_bin) + os.pathsep + os.environ.get("PATH", ""))
    cargo = shutil.which("cargo", path=env["PATH"]) or "cargo"
    r = subprocess.run([cargo, "build", "--release"], cwd=str(ROOT / "program"), env=env, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=3600)
    assert r.returncode == 0, "the program does not build:\n" + r.stderr[-3000:]
    built = ROOT / "program" / "target" / "release" / ("asterism.exe" if WIN else "asterism")
    assert built.is_file(), "no binary named asterism came out of the build"
    return built


@pytest.fixture(scope="module")
def v(tmp_path_factory):
    world = build_world(tmp_path_factory.mktemp("dataj2"), ENV2)
    yield world
    world.srv.stop()


def kill_pid(pid: int):
    if WIN:
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
    else:
        try:
            os.kill(pid, 9)
        except OSError:
            pass


def daemon_info(home: Path) -> dict | None:
    try:
        return json.loads((home / "daemon.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def alive(pid: int) -> bool:
    if WIN:
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True).stdout
        return str(pid) in out
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


@pytest.fixture
def home(tmp_path):
    h = tmp_path / "home"
    yield h
    info = daemon_info(h)
    if info and isinstance(info.get("pid"), int):
        kill_pid(info["pid"])


def run(exe, home, *args, timeout=90, **env) -> tuple[int, str]:
    r = subprocess.run([str(exe), *args], env=dict(CLEAN, ASTERISM_HOME=str(home), **env), capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=timeout, stdin=subprocess.DEVNULL)
    return r.returncode, r.stdout + r.stderr


def new_link(person) -> str:
    r = person.c.post(f"/{SLUG}/api/my/agent-invites")
    assert r.status_code == 201, r.text
    return r.json()["url"]


def join(exe, home, v, *more, **env) -> str:
    rc, out = run(exe, home, "join", new_link(v.alice), *more, **env)
    assert rc == 0 and "panicked" not in out, out
    return out


def secrets_of(home: Path) -> list[str]:
    found = []
    for f in (home / "projects").glob("*.json"):
        found.append(json.loads(f.read_text(encoding="utf-8"))["credential"])
    info = daemon_info(home)
    if info:
        found.append(str(info["token"]))
    return found


def row(v, name) -> dict | None:
    return next((a for a in v.alice.members()["agents"] if a["name"] == name), None)


def logged(v, event: str, **fields) -> list[dict]:
    lines = (v.srv.data / "log.jsonl").read_text(encoding="utf-8").splitlines()
    out = [e for e in map(json.loads, filter(str.strip, lines)) if e.get("event") == event]
    return [e for e in out if all(e.get(k) == x for k, x in fields.items())]


class Mcp:
    """`asterism mcp` as a product starts it in a session: an MCP server on stdio, newline-delimited JSON-RPC."""

    def __init__(self, exe, home, client_name="claude-code", **env):
        self.p = subprocess.Popen([str(exe), "mcp"], text=True, encoding="utf-8", stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  env=dict(CLEAN, ASTERISM_HOME=str(home), **env))
        self.q, self.n = queue.Queue(), 0
        threading.Thread(target=self._read, daemon=True).start()
        self.init = self.rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                            "clientInfo": {"name": client_name, "version": "0"}})["result"]
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self.tools = {t["name"]: t for t in self.rpc("tools/list")["result"]["tools"]}

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
        raise AssertionError(f"asterism mcp did not answer {method}")

    def tool(self, tool_name, meta=None, **args):
        params = {"name": tool_name, "arguments": args, **({"_meta": meta} if meta else {})}
        res = self.rpc("tools/call", params)["result"]
        text = res["content"][0]["text"]
        return (text if res.get("isError") else json.loads(text)), bool(res.get("isError"))

    def kill(self):
        self.p.kill()
        self.p.wait(10)


# ------------------------------------------------------------------ join and the resident program

def test_join_authorises_the_computer_and_starts_the_resident_program(exe, v, home):
    link = new_link(v.alice)
    rc, out = run(exe, home, "join", link, "--client", "none")
    assert rc == 0, out
    assert out.strip().endswith(ENDING), out
    assert "Not added to any agent. To add it, run one of:" in out and "mcp add asterism-local" in out
    assert httpx.get(link).status_code == 410, "the link was used"
    info = daemon_info(home)
    assert info and alive(info["pid"]) and info["port"] and info["token"], "the resident program runs"
    assert until(lambda: logged(v, "computer_connected", project=SLUG), 10), "and holds the computer's connection"
    assert all(s not in out for s in secrets_of(home)), "no secret is printed"

    rc, shown = run(exe, home, "status")
    assert rc == 0 and SLUG in shown and all(s not in shown for s in secrets_of(home)), shown

    before = len(v.alice.c.get(f"/{SLUG}/api/my").json()["credentials"])
    rc, out = run(exe, home, "join", new_link(v.alice), "--client", "none")
    assert rc == 0 and len(v.alice.c.get(f"/{SLUG}/api/my").json()["credentials"]) == before, "no second credential"
    assert daemon_info(home)["pid"] == info["pid"], "and no second resident program"

    rc, out = run(exe, home, "join", link, "--client", "none")              # a used link
    assert rc != 0 and "panicked" not in out and "expired" in out.lower(), out


def test_join_adds_the_tools_to_the_invited_product_only(exe, v, home, tmp_path):
    fake = tmp_path / "bin"
    codex_log, claude_log = fake_command(fake, "codex"), fake_command(fake, "claude")
    path = str(fake) + os.pathsep + CLEAN.get("PATH", "")
    out = join(exe, home, v, PATH=path, CODEX_THREAD_ID="thread-j2-1")        # run by a Codex conversation
    assert out.strip().endswith(ENDING) and "Not added to any agent" not in out, out
    calls = until(lambda: codex_log.read_text(encoding="utf-8", errors="replace").splitlines() if codex_log.exists() else [], 5)
    assert len(calls) == 2 and calls[0].split() == ["mcp", "remove", "asterism-local"], calls
    added = calls[1].replace('"', "").split()
    assert added[:4] == ["mcp", "add", "asterism-local", "--"] and added[-1] == "mcp", calls[1]
    assert Path(added[4]).resolve() == Path(exe).resolve(), "the product starts this very program"
    assert not claude_log.exists(), "Claude Code was not invited, so it is not touched"


# ------------------------------------------------------------------ waking sessions

def test_a_claude_code_session_is_woken_through_the_resident_program(exe, v, home, tmp_path):
    join(exe, home, v, "--client", "none")
    ch = Channel(tmp_path)
    m = Mcp(exe, home, CLAUDE_CODE_SESSION_ID="s-cc-1", CLAUDE_CODE_MESSAGING_SOCKET=ch.address,
            CLAUDE_CODE_MESSAGING_TOKEN="tok-j2")
    try:
        assert m.init["instructions"] == INSTRUCTIONS
        assert {n: t["description"] for n, t in m.tools.items()} == DESCRIPTIONS
        got, bad = m.tool("register", name="clara")
        assert not bad and got["owner"] == "alice", got
        assert until(lambda: v.alice.is_online("clara"), 8), "online through the computer's connection"
        assert row(v, "clara")["kind"] == "claude-code"
        text = '@clara line one [jc1]\nline two with "quotes" and 數學 $x^2$'
        sent = v.alice.say(text)
        assert mention(sent, "clara")["result"] == "woken"
        shown = until(lambda: ch.users("[jc1]"), 10)
        assert shown, "nothing was written to the session's message channel"
        assert shown[0] == frame({"id": sent["id"], "in": "#general", "from": "alice", "relation": "your own user",
                                  "level": "important", "text": text})
        assert {"type": "auth", "token": "tok-j2"} in ch.lines()
        time.sleep(REDELIVER_S * 2 + 1.5)
        assert len(ch.users("[jc1]")) == 1, "acknowledged, so not written twice"
        back, bad = m.tool("send", text="got it [jc1a]", reply_to=sent["id"])
        assert not bad and back["id"] > sent["id"]
        who, bad = m.tool("whoami")
        assert not bad and who["agent"] == "clara" and "unread" in who
    finally:
        m.kill()
    assert until(lambda: row(v, "clara")["offline_because"] == "session_closed", 10), \
        "the session is gone, the computer is still connected"


@pytest.mark.skipif(not shutil.which("node"), reason="the stand-in codex is laid out as npm installs it and needs node")
def test_a_codex_thread_stays_wakeable_when_its_tool_process_is_gone(exe, v, home, tmp_path):
    fake = tmp_path / "bin"
    jsdir = fake / "node_modules" / "@openai" / "codex" / "bin"
    jsdir.mkdir(parents=True)
    (jsdir / "codex.js").write_text(
        'const fs=require("fs"),path=require("path");const dir=path.resolve(__dirname,"../../../..");'
        'const a=process.argv.slice(2);const f=path.join(dir,"calls.json");'
        'const all=fs.existsSync(f)?JSON.parse(fs.readFileSync(f,"utf8")):[];all.push(a);'
        'fs.writeFileSync(f,JSON.stringify(all));\n', encoding="utf-8")
    if WIN:
        (fake / "codex").write_text('#!/bin/sh\nexec node "$(dirname "$0")/node_modules/@openai/codex/bin/codex.js" "$@"\n', encoding="ascii")
        (fake / "codex.cmd").write_text('@node "%~dp0node_modules\\@openai\\codex\\bin\\codex.js" %*\n', encoding="ascii")
    else:
        (fake / "codex").write_text('#!/bin/sh\nexec node "$(dirname "$0")/node_modules/@openai/codex/bin/codex.js" "$@"\n')
        (fake / "codex").chmod(0o755)
    path = str(fake) + os.pathsep + CLEAN.get("PATH", "")

    def queued(tag):
        f = fake / "calls.json"
        try:
            return [c for c in json.loads(f.read_text(encoding="utf-8")) if c[:1] == ["queue"] and any(tag in x for x in c)]
        except (OSError, ValueError):
            return []

    join(exe, home, v, "--client", "none", PATH=path)
    meta = {"threadId": "thread-j2-9"}
    m = Mcp(exe, home, client_name="codex-mcp-client", PATH=path)
    try:
        got, bad = m.tool("register", meta=meta, name="cedric")
        assert not bad, got
        assert until(lambda: v.alice.is_online("cedric"), 8) and row(v, "cedric")["kind"] == "codex"
        text = '@cedric first line [jx1]\nsecond line & echo hacked > "%TEMP%\\x" | $(whoami) `id`'
        sent = v.alice.say(text)
        got = until(lambda: queued("[jx1]"), 12)
        assert got, "codex queue was not run"
        assert got[0] == ["queue", "--thread", "thread-j2-9", "--message",
                          frame({"id": sent["id"], "in": "#general", "from": "alice", "relation": "your own user",
                                 "level": "important", "text": text})], "the whole frame, one argument, no shell"
        assert not m.tool("send", meta=meta, text="here [jx1a]", reply_to=sent["id"])[1]
    finally:
        m.kill()                                            # Codex restarts or drops the tool process on its own
    time.sleep(OFFLINE_S + 1.5)
    assert v.alice.is_online("cedric"), "the thread can still be woken: the resident program does it"
    again = v.alice.say("@cedric still there? [jx2]")
    assert mention(again, "cedric")["result"] == "woken"
    assert until(lambda: queued("[jx2]"), 12), "and it is"


def test_a_conversation_invited_with_a_name_registers_when_it_comes_back(exe, v, home, tmp_path):
    join(exe, home, v, "--client", "none", "--name", "piper", CLAUDE_CODE_SESSION_ID="s-pp-1")
    assert row(v, "piper") is None, "join itself registers nothing: the conversation has no tools yet"
    ch = Channel(tmp_path)
    m = Mcp(exe, home, CLAUDE_CODE_SESSION_ID="s-pp-1", CLAUDE_CODE_MESSAGING_SOCKET=ch.address)   # reopened
    try:
        assert until(lambda: row(v, "piper") and row(v, "piper")["online"], 10), "registered by itself, as piper"
        who, bad = m.tool("whoami")
        assert not bad and who["registered"] is True and who["agent"] == "piper"
    finally:
        m.kill()
    other = Mcp(exe, home, CLAUDE_CODE_SESSION_ID="s-pp-2", CLAUDE_CODE_MESSAGING_SOCKET=ch.address)
    try:
        time.sleep(2)
        who, bad = other.tool("whoami")
        assert not bad and who["registered"] is False, "another conversation was not invited: it registers nothing"
    finally:
        other.kill()


def test_the_resident_program_comes_back_when_a_session_needs_it(exe, v, home, tmp_path):
    join(exe, home, v, "--client", "none")
    first = daemon_info(home)["pid"]
    kill_pid(first)
    assert until(lambda: not alive(first), 5)
    rc, shown = run(exe, home, "status")
    assert rc == 0, shown
    ch = Channel(tmp_path)
    m = Mcp(exe, home, CLAUDE_CODE_SESSION_ID="s-rs-1", CLAUDE_CODE_MESSAGING_SOCKET=ch.address)
    try:
        assert until(lambda: (daemon_info(home) or {}).get("pid") not in (None, first) and alive(daemon_info(home)["pid"]), 10)
        assert not m.tool("register", name="rosa")[1]
        assert until(lambda: v.alice.is_online("rosa"), 10)
    finally:
        m.kill()


# ------------------------------------------------------------------ no approval prompt for the Asterism tools

@pytest.mark.skipif(not shutil.which("codex"), reason="needs the real codex: the test reads what its own command writes")
def test_join_lets_codex_call_the_asterism_tools_without_asking(exe, v, home, tmp_path):
    """An agent is woken while its user is away: a prompt asking to approve `send` would leave it stuck.
    The real codex runs here against a configuration folder of its own (CODEX_HOME)."""
    import tomllib
    codex_home = tmp_path / "codex_home"
    codex_home.mkdir()
    (codex_home / "config.toml").write_text('[mcp_servers.other]\ncommand = "other"\n', encoding="utf-8")
    for _ in range(2):                                      # joining twice leaves one clean entry
        out = join(exe, home, v, CODEX_THREAD_ID="thread-ap-1", CODEX_HOME=str(codex_home))
        assert "Not added to any agent" not in out, out
        conf = tomllib.loads((codex_home / "config.toml").read_text(encoding="utf-8"))
        entry = conf["mcp_servers"]["asterism-local"]
        assert Path(entry["command"]).resolve() == Path(exe).resolve() and entry["args"] == ["mcp"], entry
        assert entry["default_tools_approval_mode"] == "approve", "its tools need no approval"
        assert conf["mcp_servers"]["other"] == {"command": "other"}, "nothing else in the file is touched"


@pytest.mark.skipif(not shutil.which("claude"), reason="needs the real claude: the test reads what its own command writes")
def test_join_lets_claude_code_call_the_asterism_tools_without_asking(exe, v, home, tmp_path):
    """The real claude runs here against a configuration folder of its own (CLAUDE_CONFIG_DIR)."""
    cfg = tmp_path / "claude_cfg"
    cfg.mkdir()
    before = {"permissions": {"allow": ["Bash(ls:*)"], "deny": ["Read(./.env)"]}, "theme": "dark"}
    (cfg / "settings.json").write_text(json.dumps(before), encoding="utf-8")
    for _ in range(2):
        out = join(exe, home, v, CLAUDE_CODE_SESSION_ID="s-ap-1", CLAUDE_CONFIG_DIR=str(cfg))
        assert "Not added to any agent" not in out, out
        servers = json.loads((cfg / ".claude.json").read_text(encoding="utf-8")).get("mcpServers", {})
        assert "asterism-local" in servers and servers["asterism-local"]["args"] == ["mcp"], servers
        after = json.loads((cfg / "settings.json").read_text(encoding="utf-8"))
        assert after["permissions"]["allow"].count("mcp__asterism-local") == 1, "the server's tools are allowed, once"
        assert "Bash(ls:*)" in after["permissions"]["allow"] and after["permissions"]["deny"] == ["Read(./.env)"]
        assert after["theme"] == "dark", "nothing else in the file is touched"
