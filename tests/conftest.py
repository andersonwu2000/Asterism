"""A tripwire for the whole test run: the tests must never change what the person's real Codex and Claude Code hold
about Asterism. The entries are read before the first test and compared after the last one; a difference fails the run
loudly, with what changed.

Why: `join`, `allow` and `uninstall` edit the products' configuration, and a test that starts the program without
configuration folders of its own edits the real ones. On 2026-11-22 that put a pytest folder into the real Codex entry
(`env = { ASTERISM_HOME = ... }`), and the person's real Codex ran its Asterism tools against that folder for a day.
`test_m1j2.isolated` gives every started program folders of its own; this file is the check that it stays so.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

HOME = Path.home()


def _codex_entry() -> str | None:
    """The section [mcp_servers.asterism-local] of the real ~/.codex/config.toml, as text."""
    try:
        text = (HOME / ".codex" / "config.toml").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    m = re.search(r"(?ms)^\[mcp_servers\.asterism-local[^\]]*\]\r?\n.*?(?=^\[(?!mcp_servers\.asterism-local)|\Z)", text)
    return m.group(0).strip() if m else None


def _claude_entry() -> str | None:
    """The user-scope server `asterism-local` of the real ~/.claude.json."""
    try:
        data = json.loads((HOME / ".claude.json").read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        return None
    entry = (data.get("mcpServers") or {}).get("asterism-local") if isinstance(data, dict) else None
    return json.dumps(entry, sort_keys=True) if entry is not None else None


def _claude_allowed() -> str | None:
    """What the real ~/.claude/settings.json allows of Asterism's tools."""
    try:
        data = json.loads((HOME / ".claude" / "settings.json").read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        return None
    allow = ((data.get("permissions") or {}).get("allow") or []) if isinstance(data, dict) else []
    return json.dumps(sorted(x for x in allow if isinstance(x, str) and "asterism" in x.lower()))


WATCHED = {"the Asterism entry of the real ~/.codex/config.toml": _codex_entry,
           "the Asterism server of the real ~/.claude.json": _claude_entry,
           "the Asterism permissions of the real ~/.claude/settings.json": _claude_allowed}


@pytest.fixture(scope="session", autouse=True)
def the_real_configuration_is_left_alone():
    before = {name: read() for name, read in WATCHED.items()}
    yield
    changed = [name for name, read in WATCHED.items() if read() != before[name]]
    if changed:
        pytest.fail("A test changed " + "; ".join(changed) + ". A program started by a test must get configuration "
                    "folders of its own (test_m1j2.isolated). Put the real entry back by hand before anything else.",
                    pytrace=False)
