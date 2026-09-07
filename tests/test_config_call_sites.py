"""A registered key is read by NAME — the registry owns its default.

`test_config_spec_drift.py` binds the key SET to the code. This file
binds the key's VALUE: `CONFIG_SPEC` carries each key's default, cast
and env var, so a production reader spells `config.get(key)` and
nothing else.

The bug this kills is not hypothetical. On 2026-09-07
`dispatch.spawn_timeout_sec` had four answers — 900 in the registry,
1800 in `dispatcher/loop.py`, 1800 in the gateway, 960 in the librarian
— and no way to say which one a run used; the librarian budgeted a
classify's post-trap tail against a 960s cap nothing was running on.
A per-call `default=` is exactly how that happens, so it fails here.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from Tooling.core import config

_REPO = Path(__file__).resolve().parents[1]
_TOOLING = _REPO / "Tooling"

#: config.py DEFINES `get`; its docstrings quote the call form.
_NOT_A_CALLER = {"Tooling/core/config.py"}

_CALL_RE = re.compile(r"(?:\bconfig|\b_config|\b_cfg)\s*\.get\(")
#: the arguments the registry now owns. `legacy_env` is deliberately
#: absent: a provider-specific compat spelling (ASTERISM_AGY_MODEL on
#: antigravity, ASTERISM_LLM_MODEL on the openai adapter) is a fact
#: about that backend, not about the key.
_OWNED_ARGS = re.compile(r"\b(default|cast|env_var)\s*=")


def _call_args(text: str, open_paren: int) -> str:
    """The text between a call's parens, skipping string literals so a
    paren inside one cannot unbalance the scan."""
    depth, i, n = 0, open_paren, len(text)
    while i < n:
        ch = text[i]
        if ch in "\"'":
            quote, i = ch, i + 1
            while i < n:
                if text[i] == "\\":
                    i += 2
                    continue
                if text[i] == quote:
                    break
                i += 1
        elif ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
            if depth == 0:
                return text[open_paren + 1:i]
        i += 1
    return text[open_paren + 1:]


def _key_of(args: str) -> "str | None":
    """The literal key a call reads, `<kind>`-normalized, or None when
    the key is not a literal (nothing to check against the registry)."""
    m = re.match(r"\s*(f?)([\"'])(.+?)\2", args)
    if not m:
        return None
    key = m.group(3)
    return re.sub(r"\{[^}]+\}", "<kind>", key) if m.group(1) == "f" else key


def _call_sites() -> "list[tuple[str, int, str, str]]":
    """(relpath, line, key, args) for every literal-key config read."""
    out: "list[tuple[str, int, str, str]]" = []
    for py in _TOOLING.rglob("*.py"):
        rel = py.relative_to(_REPO).as_posix()
        if rel in _NOT_A_CALLER:
            continue
        text = py.read_text(encoding="utf-8", errors="replace")
        for m in _CALL_RE.finditer(text):
            args = _call_args(text, m.end() - 1)
            key = _key_of(args)
            if key is None:
                continue
            out.append((rel, text.count("\n", 0, m.start()) + 1, key, args))
    return out


def test_no_call_site_carries_its_own_default() -> None:
    offenders = [
        f"{rel}:{line} — {key} passes "
        f"{', '.join(sorted(set(_OWNED_ARGS.findall(args))))}"
        for rel, line, key, args in _call_sites()
        if config._spec_for(key) is not None and _OWNED_ARGS.search(args)
    ]
    assert not offenders, (
        "these readers keep a second opinion about a registered key — "
        "the default, cast and env var belong to CONFIG_SPEC, so read "
        "the key alone:\n" + "\n".join(offenders))


def test_every_literal_key_read_resolves_against_a_registry_row() -> None:
    """A reader that resolves against nothing gets a silent None."""
    unknown = sorted({
        f"{rel}:{line} — {key}"
        for rel, line, key, _ in _call_sites()
        if config._spec_for(key) is None})
    assert not unknown, (
        "config reads with no CONFIG_SPEC row (typo, or register "
        "them):\n" + "\n".join(unknown))


# ---------------------------------------------------------------------
# the key that had four answers
# ---------------------------------------------------------------------

_SPAWN_KEY = "dispatch.spawn_timeout_sec"
#: the readers the 2026-09-07 divergence was found in
_KNOWN_SPAWN_READERS = {
    "Tooling/core/dispatcher/loop.py",
    "Tooling/lsp/gateway/__init__.py",
    "Tooling/pipeline/librarian/run.py",
}


def test_the_spawn_cap_readers_are_all_registry_readers() -> None:
    sites = {rel for rel, _, key, _ in _call_sites() if key == _SPAWN_KEY}
    missing = _KNOWN_SPAWN_READERS - sites
    assert not missing, f"expected these to read {_SPAWN_KEY}: {missing}"


@pytest.mark.parametrize("yaml_text,expected", [
    ("", 900),                                        # registry default
    ("dispatch:\n  spawn_timeout_sec: 1800\n", 1800),  # the yaml wins
])
def test_the_spawn_cap_resolves_to_one_number(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    yaml_text: str, expected: int,
) -> None:
    """Every reader of the cap now asks the same question, so there is
    one answer — including the librarian's derived classify budget,
    which used to carry a 960 of its own."""
    from Tooling.agent import runtime
    from Tooling.pipeline import _retry

    monkeypatch.delenv("ASTERISM_SPAWN_TIMEOUT_SEC", raising=False)
    monkeypatch.delenv("ASTERISM_TRAP_CHECK_SEC", raising=False)
    if yaml_text:
        (tmp_path / "Asterism.yaml").write_text(yaml_text, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    config._reset_cache()

    resolved = config.get(_SPAWN_KEY, workspace=tmp_path)
    assert resolved == expected
    assert runtime.spawn_timeout_sec() == expected
    # the rescue leg's budget is the cap minus the watchdog check point
    trap = config.get("dispatch.trap_check_sec", workspace=tmp_path)
    assert _retry._derive_stage2_budget(tmp_path) == max(60, expected - trap)


def test_a_caller_may_still_pin_a_value() -> None:
    """The registry is the default, not a cage: tests and the odd
    provider-compat read still pass their own."""
    assert config.get(_SPAWN_KEY, default=7, workspace=Path("/nonexistent")) \
        == 7
