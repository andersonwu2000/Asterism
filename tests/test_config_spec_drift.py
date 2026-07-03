"""CONFIG_SPEC ↔ code two-way drift gate (task #10).

A typo'd config key silently returns the default — you believe a switch
is off while it is on, with zero signal. The registry (config.CONFIG_SPEC)
is therefore bound to the code by scanning every `config.get(...)` call:
  forward — every key read in code must be registered;
  reverse — every registered key must be read somewhere (the prose field
  map this replaced had accumulated six missing live keys and one dead
  one, `strategist.inject_batch_max`).
Dynamic per-kind keys (f"{kind}.model") normalize to `<kind>.model`.
"""
from __future__ import annotations

import re
from pathlib import Path

from Tooling.core.config import CONFIG_SPEC

_REPO = Path(__file__).resolve().parents[1]
_TOOLING = _REPO / "Tooling"

# `config.get(` / `_config.get(` / `_cfg.get(` followed (across whitespace/
# newlines) by the key literal — plain or f-string.
_CALL_RE = re.compile(
    r"(?:\bconfig|\b_config|\b_cfg)\s*\.get\(\s*(f?)\"([^\"]+)\"",
    re.MULTILINE)


def _keys_in_code() -> "set[str]":
    keys: "set[str]" = set()
    for py in _TOOLING.rglob("*.py"):
        text = py.read_text(encoding="utf-8", errors="replace")
        for m in _CALL_RE.finditer(text):
            key = m.group(2)
            if m.group(1) == "f":
                key = re.sub(r"\{[^}]+\}", "<kind>", key)
            keys.add(key)
    return keys


def test_every_code_key_is_registered():
    unregistered = _keys_in_code() - set(CONFIG_SPEC)
    assert not unregistered, (
        f"config.get keys not in CONFIG_SPEC (typo, or register them): "
        f"{sorted(unregistered)}")


def test_every_registered_key_is_read():
    dead = set(CONFIG_SPEC) - _keys_in_code()
    assert not dead, (
        f"CONFIG_SPEC entries no code reads (stale registry): "
        f"{sorted(dead)}")
