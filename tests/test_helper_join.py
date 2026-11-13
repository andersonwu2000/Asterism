"""Acceptance check: `--join --client codex|claude` adds the helper to the agent with the agent's own command,
also when that command is installed the way npm installs it on Windows.

Why: on a real Windows computer `codex` is three files side by side (`codex`, a shell script without an extension;
`codex.cmd`; `codex.ps1`). Looking the name up found the shell script, starting it failed with WinError 193, and the
join crashed with a traceback after the approval instead of adding the MCP server.

    python -m pytest tests/test_helper_join.py -x -q
"""
import os
import subprocess
import sys
import urllib.parse

import httpx
import pytest

from test_m1b import CLEAN, ENV, PY, SLUG, build_world, until


@pytest.fixture(scope="module")
def w(tmp_path_factory):
    world = build_world(tmp_path_factory.mktemp("data"))
    yield world
    world.srv.stop()


def fake_command(folder, name):
    """A stand-in for an agent's command that records its arguments, laid out as on the platform we run on."""
    folder.mkdir(parents=True, exist_ok=True)
    log = folder / f"{name}_called.txt"
    if sys.platform == "win32":
        (folder / name).write_text(f'#!/bin/sh\necho "$@" >> "$(dirname "$0")/{name}_called.txt"\n', encoding="ascii")
        (folder / f"{name}.cmd").write_text(f'@echo %* >> "%~dp0{name}_called.txt"\n', encoding="ascii")
        (folder / f"{name}.ps1").write_text(f'$args -join " " | Add-Content "$PSScriptRoot\\{name}_called.txt"\n', encoding="ascii")
    else:
        (folder / name).write_text(f'#!/bin/sh\necho "$@" >> "$(dirname "$0")/{name}_called.txt"\n')
        (folder / name).chmod(0o755)
    return log


def join(w, script, home, box, client, path, approve=True):
    p = subprocess.Popen([PY, str(script), "--join", f"{w.srv.url}/{SLUG}", "--client", client], cwd=str(box), text=True,
                         encoding="utf-8", errors="replace", stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         env=dict(ENV, ASTERISM_HOME=str(home), PATH=path))
    out = ""
    if approve:
        for _ in range(30):
            line = p.stdout.readline()
            out += line
            if not line or line.startswith("Open this address to approve: "):
                break
        assert "Open this address to approve: " in out, out
        link = out.rsplit("Open this address to approve: ", 1)[1].strip()
        code = urllib.parse.parse_qs(urllib.parse.urlparse(link).query)["code"][0]
        assert w.alice.c.post(f"/{SLUG}/api/device/{code}", json={"decision": "approve"}).status_code == 200
    out += p.communicate(timeout=60)[0]
    return p.returncode, out


def test_join_adds_the_helper_to_the_agent_with_its_own_command(w, tmp_path):
    script, home, fake = tmp_path / "asterism_helper.py", tmp_path / "home", tmp_path / "bin"
    script.write_bytes(httpx.get(w.srv.url + "/helper.py").content)
    codex_log, claude_log = fake_command(fake, "codex"), fake_command(fake, "claude")
    path = str(fake) + os.pathsep + CLEAN.get("PATH", "")
    url = f"{w.srv.url}/{SLUG}"

    rc, out = join(w, script, home, tmp_path, "codex", path)
    assert "Traceback" not in out and rc == 0, out
    assert "Added the MCP server" in out and "start a new agent session" in out, out
    calls = until(lambda: codex_log.read_text(encoding="utf-8", errors="replace").splitlines() if codex_log.exists() else [], 5)
    assert len(calls) == 2, calls
    assert calls[0].split() == ["mcp", "remove", "asterism-" + SLUG]
    added = calls[1].replace('"', "").split()
    assert added[:4] == ["mcp", "add", "asterism-" + SLUG, "--"] and added[-2:] == ["--project", url], calls[1]
    assert str(home / "asterism_helper.py") in calls[1], "the installed copy is what the agent starts"

    rc, out = join(w, script, home, tmp_path, "claude", path, approve=False)      # a second agent: no new approval
    assert "Traceback" not in out and rc == 0 and "no approval needed" in out, out
    calls = claude_log.read_text(encoding="utf-8", errors="replace").splitlines()
    assert len(calls) == 2 and calls[1].replace('"', "").split()[:3] == ["mcp", "add", "asterism-" + SLUG], calls


def test_join_says_what_to_run_when_the_command_cannot_be_started(w, tmp_path):
    script, home, fake = tmp_path / "asterism_helper.py", tmp_path / "home", tmp_path / "bin"
    script.write_bytes(httpx.get(w.srv.url + "/helper.py").content)
    fake.mkdir()
    (fake / "codex").write_text("this is not a program\n", encoding="ascii")       # found by name, cannot be started
    if sys.platform != "win32":
        (fake / "codex").chmod(0o755)
    path = str(fake) + os.pathsep + os.path.dirname(PY)
    rc, out = join(w, script, home, tmp_path, "codex", path)
    assert "Traceback" not in out, out
    assert rc != 0 and "Run this yourself" in out and "codex mcp add" in out, out
    assert "Approved." in out, "the approval itself went through and is kept"
